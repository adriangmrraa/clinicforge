"""
Tests for SLOT_LOCKED loop booking fixes (v8.2: loop-booking-and-slot-locked-fixes).

Covers:
- Deterministic routing in SupervisorAgent.route() during SLOT_LOCKED state.
- Handoff bypass logic when handoff patterns match during SLOT_LOCKED.
- State hint injection in buffer_task during SLOT_LOCKED.
"""

import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from contextvars import ContextVar
from datetime import datetime

# Add project root and services to path
PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "orchestrator_service")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services"))

# 1. Setup mock main module to prevent loading heavy dependencies of main.py
mock_main = MagicMock()
mock_main.get_agent_executable_for_tenant = AsyncMock()
mock_main.build_system_prompt = MagicMock(return_value="Mocked Prompt")
mock_main.get_now_arg = MagicMock(return_value=datetime.now())
mock_main.normalize_phone_digits = MagicMock(side_effect=lambda x: x)
mock_main.CLINIC_NAME = "Mock Clinic"
mock_main.CLINIC_HOURS_START = "08:00"
mock_main.CLINIC_HOURS_END = "19:00"
mock_main._format_special_conditions = MagicMock(return_value="")
mock_main._format_support_policy = MagicMock(return_value="")
mock_main.get_active_tz = MagicMock()
mock_main._get_adjuntos_section = MagicMock(return_value="")
mock_main.app = MagicMock()

mock_main.current_customer_phone = ContextVar("current_customer_phone", default=None)
mock_main.current_tenant_id = ContextVar("current_tenant_id", default=None)
mock_main.current_patient_id = ContextVar("current_patient_id", default=None)
mock_main.current_source_channel = ContextVar("current_source_channel", default=None)
mock_main.current_tenant_tz = ContextVar("current_tenant_tz", default=None)

mock_db = MagicMock()
mock_db.get_chat_history = AsyncMock(return_value=[])
mock_main.db = mock_db

# Inject into sys.modules and keep track of original main
original_main = sys.modules.get('main')
sys.modules['main'] = mock_main


class TestSupervisorSlotLockedRouting(unittest.IsolatedAsyncioTestCase):
    """Test supervisor routing decisions during SLOT_LOCKED state."""

    @patch("services.conversation_state.get_state")
    async def test_slot_locked_routing_to_booking(self, mock_get_state):
        """Under SLOT_LOCKED, route to booking if user message is normal."""
        from agents.supervisor import SupervisorAgent
        from agents.state import AgentState

        mock_get_state.return_value = {"state": "SLOT_LOCKED"}

        state: AgentState = {
            "tenant_id": 1,
            "phone_number": "5491112345678",
            "user_message": "Mi DNI es 12345678",
            "patient_profile": {},
        }

        supervisor = SupervisorAgent()
        next_agent = await supervisor.route(state)
        self.assertEqual(next_agent, "booking")

        # Verify with another normal message
        state["user_message"] = "Hola, confirmo"
        next_agent = await supervisor.route(state)
        self.assertEqual(next_agent, "booking")

    @patch("services.conversation_state.get_state")
    async def test_slot_locked_routing_exception_to_handoff(self, mock_get_state):
        """Under SLOT_LOCKED, route to handoff if user message contains handoff keywords."""
        from agents.supervisor import SupervisorAgent
        from agents.state import AgentState

        mock_get_state.return_value = {"state": "SLOT_LOCKED"}

        supervisor = SupervisorAgent()

        # Test handoff pattern message
        state: AgentState = {
            "tenant_id": 1,
            "phone_number": "5491112345678",
            "user_message": "Quiero hablar con un humano por favor",
            "patient_profile": {},
        }
        next_agent = await supervisor.route(state)
        self.assertEqual(next_agent, "handoff")

        # Another handoff keyword
        state["user_message"] = "Tengo una queja del servicio"
        next_agent = await supervisor.route(state)
        self.assertEqual(next_agent, "handoff")

    @patch("services.conversation_state.get_state")
    async def test_normal_state_does_not_trigger_bypass(self, mock_get_state):
        """When not in SLOT_LOCKED, routing is determined by normal patterns or LLM fallback."""
        from agents.supervisor import SupervisorAgent
        from agents.state import AgentState

        mock_get_state.return_value = {"state": "IDLE"}

        supervisor = SupervisorAgent()
        
        # Patch the LLM fallback so it doesn't trigger API call
        with patch.object(supervisor, "_llm_route", new_callable=AsyncMock) as mock_llm_route:
            mock_llm_route.return_value = "reception"

            state: AgentState = {
                "tenant_id": 1,
                "phone_number": "5491112345678",
                "user_message": "hola",
                "patient_profile": {},
            }
            next_agent = await supervisor.route(state)
            # greeting pattern matches Rule 9 -> reception
            self.assertEqual(next_agent, "reception")


class TestBufferTaskSlotLockedHint(unittest.IsolatedAsyncioTestCase):
    """Test state hint injection in buffer_task when state is SLOT_LOCKED."""

    @patch("services.buffer_task.get_pool")
    @patch("services.buffer_task.get_state")
    @patch("services.engine_router.get_engine_for_tenant")
    @patch("services.tz_resolver.get_tenant_tz")
    async def test_slot_locked_hint_injection(self, mock_get_tz, mock_get_engine, mock_get_state, mock_get_pool):
        """Verify process_buffer_task correctly builds and injects state_hint during SLOT_LOCKED state."""
        from services.buffer_task import process_buffer_task

        # Mock timezone and engine router
        mock_get_tz.return_value = "America/Argentina/Buenos_Aires"
        mock_engine = MagicMock()
        mock_engine.name = "solo"
        mock_get_engine.return_value = mock_engine

        # Mock pool fetchrow behavior to return dummy rows based on the query
        def mock_fetchrow(query, *args):
            q = query.lower()
            if "from chat_conversations" in q:
                return {
                    "provider": "chatwoot",
                    "external_chatwoot_id": "123",
                    "external_account_id": "456",
                    "channel": "whatsapp",
                    "human_override_until": None,
                }
            elif "from tenants" in q:
                return {
                    "clinic_name": "Mock Clinic",
                    "address": "Calle Falsa 123",
                    "google_maps_url": "http://maps.com",
                    "working_hours": None,
                    "consultation_price": 5000,
                    "bank_cbu": "123456",
                    "bank_alias": "mock.alias",
                    "bank_holder_name": "Dr. Delgado",
                    "system_prompt_template": "Test template",
                    "bot_name": "TORA",
                    "payment_methods": ["cash", "transfer"],
                    "financing_available": True,
                    "max_installments": 3,
                    "installments_interest_free": True,
                    "financing_provider": "Visa",
                    "financing_notes": "Cuotas fijas",
                    "cash_discount_percent": 10,
                    "accepts_crypto": False,
                    "accepts_pregnant_patients": True,
                    "pregnancy_restricted_treatments": [],
                    "pregnancy_notes": "",
                    "accepts_pediatric": True,
                    "min_pediatric_age_years": 5,
                    "pediatric_notes": "",
                    "high_risk_protocols": {},
                    "requires_anamnesis_before_booking": False,
                    "complaint_escalation_email": "admin@clinic.com",
                    "complaint_escalation_phone": "12345678",
                    "expected_wait_time_minutes": 30,
                    "revision_policy": "",
                    "review_platforms": [],
                    "complaint_handling_protocol": "",
                    "auto_send_review_link_after_followup": False,
                    "social_ig_active": False,
                    "social_landings": {},
                    "instagram_handle": None,
                    "facebook_page_id": None,
                    "bot_phone_number": "123456",
                    "config": {},
                }
            elif "from patients" in q:
                return {
                    "id": 1,
                    "first_name": "Juan",
                    "last_name": "Pérez",
                    "phone_number": "5491112345678",
                    "dni": "12345678",
                    "email": "juan@perez.com",
                    "human_override_until": None,
                }
            return {}

        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(side_effect=mock_fetchrow)
        mock_pool.fetch = AsyncMock(return_value=[])
        mock_pool.fetchval = AsyncMock(return_value=0)
        mock_pool.execute = AsyncMock()
        mock_get_pool.return_value = mock_pool

        # Mock global db pool so that ResponseSender can query it
        import db
        db.get_pool = lambda: mock_pool
        db.pool = mock_pool

        # Mock db history
        mock_db.get_chat_history = AsyncMock(return_value=[
            {"role": "user", "content": "hola", "content_attributes": None}
        ])

        # Mock get_state to return SLOT_LOCKED
        mock_get_state.return_value = {
            "state": "SLOT_LOCKED",
            "last_locked_slot": {
                "date_display": "Jueves 18 de Junio",
                "time": "15:00",
                "professional": "Dr. Delgado",
                "treatment": "Implante",
            }
        }

        # Mock executor
        mock_executor = AsyncMock()
        mock_executor.ainvoke = AsyncMock(return_value={"output": "Respuesta"})
        mock_main.get_agent_executable_for_tenant.return_value = mock_executor

        # Run process_buffer_task
        await process_buffer_task(
            tenant_id=1,
            conversation_id="conv_123",
            external_user_id="5491112345678",
            messages=["mi dni es 12345678"],
            channel="whatsapp",
        )

        # Retrieve arguments of executor.ainvoke
        mock_executor.ainvoke.assert_called_once()
        call_args = mock_executor.ainvoke.call_args[0][0]
        user_input_passed = call_args["input"]

        # Assertions on user_input_passed
        self.assertIn("[STATE_HINT: El paciente tiene un turno pre-reservado (bloqueado)", user_input_passed)
        self.assertIn("Fecha: Jueves 18 de Junio", user_input_passed)
        self.assertIn("Hora: 15:00", user_input_passed)
        self.assertIn("Profesional: Dr. Delgado", user_input_passed)
        self.assertIn("Tratamiento: Implante", user_input_passed)
        self.assertIn("INSTRUCCIONES CRÍTICAS PARA SLOT_LOCKED:", user_input_passed)
        self.assertIn("REGLA ESTRICTA CONTRA LOOPS Y RE-OFERTAS:", user_input_passed)
        self.assertIn("PROHIBIDO llamar a check_availability", user_input_passed)

    @patch("services.conversation_state.get_state")
    async def test_route_quiero_un_turno_para_hacerme_una_ficha_to_booking(self, mock_get_state):
        """Verify message "quiero un turno para hacerme una ficha" routes to booking."""
        from agents.supervisor import SupervisorAgent
        from agents.state import AgentState

        mock_get_state.return_value = {"state": "IDLE"}

        state: AgentState = {
            "tenant_id": 1,
            "phone_number": "5491112345678",
            "user_message": "quiero un turno para hacerme una ficha",
            "patient_profile": {},
        }

        supervisor = SupervisorAgent()
        next_agent = await supervisor.route(state)
        self.assertEqual(next_agent, "booking")


class TestBufferTaskSlotLockedTransition(unittest.IsolatedAsyncioTestCase):
    """Test state transition from SLOT_LOCKED to OFFERED_SLOTS on rejection."""

    @patch("services.buffer_task.get_pool")
    @patch("services.buffer_task.get_state")
    @patch("services.conversation_state.set_state")
    @patch("services.relay.get_redis")
    @patch("services.engine_router.get_engine_for_tenant")
    @patch("services.tz_resolver.get_tenant_tz")
    async def test_slot_locked_rejection_releases_lock_and_transitions(
        self, mock_get_tz, mock_get_engine, mock_get_redis, mock_set_state, mock_get_state, mock_get_pool
    ):
        from services.buffer_task import process_buffer_task

        # Mock Redis
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        # Mock pool & db calls
        mock_get_tz.return_value = "America/Argentina/Buenos_Aires"
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        mock_pool = MagicMock()
        def mock_fetchrow(query, *args):
            q = query.lower()
            if "from chat_conversations" in q:
                return {
                    "provider": "chatwoot",
                    "external_chatwoot_id": "123",
                    "external_account_id": "456",
                    "channel": "whatsapp",
                    "human_override_until": None,
                }
            elif "from tenants" in q:
                return {
                    "clinic_name": "Mock Clinic",
                    "address": "Calle Falsa 123",
                    "google_maps_url": "http://maps.com",
                    "working_hours": None,
                    "consultation_price": 5000,
                    "bank_cbu": "123456",
                    "bank_alias": "mock.alias",
                    "bank_holder_name": "Dr. Delgado",
                    "system_prompt_template": "Test template",
                    "bot_name": "TORA",
                    "payment_methods": ["cash", "transfer"],
                    "financing_available": True,
                    "max_installments": 3,
                    "installments_interest_free": True,
                    "financing_provider": "Visa",
                    "financing_notes": "Cuotas fijas",
                    "cash_discount_percent": 10,
                    "accepts_crypto": False,
                    "accepts_pregnant_patients": True,
                    "pregnancy_restricted_treatments": [],
                    "pregnancy_notes": "",
                    "accepts_pediatric": True,
                    "min_pediatric_age_years": 5,
                    "pediatric_notes": "",
                    "high_risk_protocols": {},
                    "requires_anamnesis_before_booking": False,
                    "complaint_escalation_email": "admin@clinic.com",
                    "complaint_escalation_phone": "12345678",
                    "expected_wait_time_minutes": 30,
                    "revision_policy": "",
                    "review_platforms": [],
                    "complaint_handling_protocol": "",
                    "auto_send_review_link_after_followup": False,
                    "social_ig_active": False,
                    "social_landings": {},
                    "instagram_handle": None,
                    "facebook_page_id": None,
                    "bot_phone_number": "123456",
                    "config": {},
                }
            elif "from patients" in q:
                return {
                    "id": 1,
                    "first_name": "Juan",
                    "last_name": "Pérez",
                    "phone_number": "5491112345678",
                    "dni": "12345678",
                    "email": "juan@perez.com",
                    "human_override_until": None,
                }
            return {}
        mock_pool.fetchrow = AsyncMock(side_effect=mock_fetchrow)
        mock_pool.fetch = AsyncMock(return_value=[])
        mock_pool.fetchval = AsyncMock(return_value=0)
        mock_pool.execute = AsyncMock()
        mock_get_pool.return_value = mock_pool

        # Mock state to start as SLOT_LOCKED
        mock_get_state.return_value = {
            "state": "SLOT_LOCKED",
            "last_locked_slot": {
                "date": "2026-06-25",
                "time": "10:00",
                "professional_id": 14,
            },
            "last_offered_slots": [{"date": "2026-06-25", "time": "10:00"}]
        }

        # Run process_buffer_task with a rejection keyword like "no, prefiero otro dia"
        await process_buffer_task(
            tenant_id=1,
            conversation_id="conv_123",
            external_user_id="5491112345678",
            messages=["no, prefiero otro dia"],
            channel="whatsapp",
        )

        # Assert Redis keys were deleted
        mock_redis.delete.assert_any_call("slot_lock:1:14:2026-06-25:10:00")
        mock_redis.delete.assert_any_call("slot_lock:1:0:2026-06-25:10:00")

        # Assert set_state was called to transition to OFFERED_SLOTS
        mock_set_state.assert_called_with(
            1,
            "5491112345678",
            "OFFERED_SLOTS",
            last_offered_slots=[{"date": "2026-06-25", "time": "10:00"}]
        )


class TestTriageBypassAndContextInjection(unittest.TestCase):
    """Test that specialists.py correctly handles urgency_level in context and preamble."""

    def test_urgency_level_injection(self):
        from agents.specialists import _inject_patient_context
        from agents.state import AgentState

        state: AgentState = {
            "patient_profile": {
                "name": "Juan Pérez",
                "phone_number": "5491112345678",
                "urgency_level": "high",
            }
        }
        context_str = _inject_patient_context(state)
        self.assertIn("NIVEL DE URGENCIA TRIADO: high", context_str)

    def test_preamble_triage_bypass_instructions(self):
        from agents.specialists import _build_shared_preamble
        from agents.state import AgentState

        state: AgentState = {
            "channel": "whatsapp",
            "patient_profile": {
                "urgency_level": "high"
            }
        }
        preamble = _build_shared_preamble(state)
        self.assertIn("BYPASS DE TRIAJE: Si el paciente ya tiene un NIVEL DE URGENCIA TRIADO en su contexto, OMITIR M1 y M2.", preamble)


def tearDownModule():
    # Restore original main to avoid polluting other test suites
    if original_main:
        sys.modules['main'] = original_main
    else:
        sys.modules.pop('main', None)


if __name__ == "__main__":
    unittest.main()
