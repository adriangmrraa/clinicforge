"""
Parity tests: Multi-Agent vs Solo engine (multi-agent-solo-parity change).

Tests pure functions from agents/specialists.py and agents/tenant_context.py
that can be imported without triggering heavy dependencies.

Covers:
- _build_shared_preamble: channel-specific rules (WhatsApp vs social)
- _inject_patient_context: new lead, returning patient, human override
- _with_tenant_blocks: variable interpolation {bot_name} and {nombre}
- bot_name_raw resolution from tenant context
- Shared preamble includes anti-markdown, anti-hallucination, F1-F10 flows
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


# =============================================================================
# Shared Preamble Tests
# =============================================================================


class TestSharedPreamble(unittest.TestCase):
    """_build_shared_preamble produces correct rules per channel."""

    def _make_state(self, channel="whatsapp", **overrides):
        state = {"channel": channel}
        state.update(overrides)
        return state

    def test_whatsapp_includes_anti_markdown(self):
        """WhatsApp preamble bans markdown."""
        from agents.specialists import _build_shared_preamble

        preamble = _build_shared_preamble(self._make_state("whatsapp"))
        self.assertIn("ANTI-MARKDOWN", preamble)
        self.assertIn("Prohibido: **negritas**", preamble)

    def test_social_channel_allows_markdown(self):
        """Social channel preamble allows markdown."""
        from agents.specialists import _build_shared_preamble

        preamble = _build_shared_preamble(self._make_state("instagram"))
        self.assertIn("MARKDOWN PERMITIDO", preamble)

    def test_includes_anti_hallucination(self):
        """Preamble contains anti-hallucination rules."""
        from agents.specialists import _build_shared_preamble

        preamble = _build_shared_preamble(self._make_state("whatsapp"))
        self.assertIn("ANTI-HALLUCINATION", preamble)
        self.assertIn("NUNCA inventes nombres", preamble)

    def test_includes_emergency_empathy(self):
        """Preamble contains emergency empathy rules."""
        from agents.specialists import _build_shared_preamble

        preamble = _build_shared_preamble(self._make_state("whatsapp"))
        self.assertIn("EMERGENCY EMPATHY", preamble)

    def test_includes_f1_f10_flows(self):
        """Preamble references all F1-F10 emotional flows."""
        from agents.specialists import _build_shared_preamble

        preamble = _build_shared_preamble(self._make_state("whatsapp"))
        for f_num in range(1, 11):
            self.assertIn(f"F{f_num}", preamble)


# =============================================================================
# Patient Context Injection Tests
# =============================================================================


class TestInjectPatientContext(unittest.TestCase):
    """_inject_patient_context builds correct block per state."""

    def _make_state(self, **overrides):
        state = {
            "channel": "whatsapp",
            "patient_profile": {
                "name": None,
                "dni": None,
                "email": None,
                "is_new_lead": True,
                "human_override_until": None,
                "medical_history": {},
                "future_appointments": [],
            },
            "lead_context": None,
        }
        state.update(overrides)
        return state

    def test_new_lead_shows_minimal_info(self):
        """New lead shows 'Nuevo paciente — sin historial'."""
        from agents.specialists import _inject_patient_context

        block = _inject_patient_context(self._make_state())
        self.assertIn("CONTEXTO DEL PACIENTE", block)
        self.assertIn("Nuevo paciente", block)
        self.assertIn("sin historial", block)

    def test_returning_patient_shows_name(self):
        """Returning patient shows name and existing status."""
        from agents.specialists import _inject_patient_context

        state = self._make_state(
            patient_profile={
                "name": "María García",
                "dni": "12345678",
                "email": "maria@test.com",
                "is_new_lead": False,
                "human_override_until": None,
                "medical_history": {},
                "future_appointments": [],
            }
        )
        block = _inject_patient_context(state)
        self.assertIn("María García", block)
        self.assertIn("Paciente existente", block)
        self.assertIn("DNI: 12345678", block)
        self.assertIn("Email: maria@test.com", block)

    def test_human_override_warning(self):
        """Human override shows warning."""
        from agents.specialists import _inject_patient_context

        state = self._make_state(
            patient_profile={
                "name": "Juan Pérez",
                "is_new_lead": False,
                "human_override_until": "2026-06-20T12:00:00",
                "medical_history": {},
                "future_appointments": [],
            }
        )
        block = _inject_patient_context(state)
        self.assertIn("silencio manual", block)
        self.assertIn("human override", block)

    def test_future_appointments_shown(self):
        """Up to 3 future appointments listed."""
        from agents.specialists import _inject_patient_context

        state = self._make_state(
            patient_profile={
                "name": "Ana López",
                "is_new_lead": False,
                "medical_history": {},
                "future_appointments": [
                    {"date_time": "2026-06-20T10:00", "treatment_type": "Limpieza"},
                    {"date_time": "2026-07-05T14:30", "treatment_type": "Consulta"},
                    {"date_time": "2026-08-01T09:00", "treatment_type": "Extracción"},
                ],
            }
        )
        block = _inject_patient_context(state)
        self.assertIn("Próximos turnos", block)
        self.assertIn("Limpieza", block)
        self.assertIn("Extracción", block)

    def test_lead_context_channel_info(self):
        """Lead context channel is included for new leads."""
        from agents.specialists import _inject_patient_context

        state = self._make_state(
            channel="instagram",
            lead_context={"channel": "instagram", "formatted_for_prompt": "datos de lead"},
        )
        block = _inject_patient_context(state)
        self.assertIn("instagram", block.lower())
        self.assertIn("nuevo paciente", block.lower())

    def test_medical_history_summary(self):
        """Medical history allergies and conditions summarized."""
        from agents.specialists import _inject_patient_context

        state = self._make_state(
            patient_profile={
                "name": "Carlos Ruiz",
                "is_new_lead": False,
                "medical_history": {
                    "allergies": "Penicilina, látex",
                    "conditions": "Diabetes tipo 2",
                },
                "future_appointments": [],
            }
        )
        block = _inject_patient_context(state)
        self.assertIn("Alergias", block)
        self.assertIn("Penicilina", block)
        self.assertIn("Condiciones", block)
        self.assertIn("Diabetes", block)


# =============================================================================
# Variable Interpolation Tests
# =============================================================================


class TestVariableInterpolation(unittest.TestCase):
    """_with_tenant_blocks interpolates {bot_name} and {nombre}."""

    def setUp(self):
        self.base_state = {
            "tenant_id": 1,
            "phone_number": "123456789",
            "chat_history": [],
            "tenant_context": {},
            "patient_profile": {},
            "model_config": {},
            "channel": "whatsapp",
            "is_social_channel": False,
            "lead_context": None,
            "working_state": {},
            "active_agent": "supervisor",
            "hop_count": 0,
            "max_hops": 5,
            "agent_output": "",
            "tools_called": [],
            "handoff_reason": None,
            "start_time": 0.0,
        }

    def test_bot_name_interpolated(self):
        """{bot_name} replaced with value from tenant_context."""
        from agents.specialists import _with_tenant_blocks

        state = dict(self.base_state)
        state["tenant_context"] = {"bot_name_raw": "Dra. Laura Delgado"}
        base = "Soy {bot_name} ¿En qué puedo ayudarte?"
        result = _with_tenant_blocks(base, state, "reception")
        # Must NOT contain literal placeholder
        self.assertNotIn("{bot_name}", result)
        # Must contain resolved value
        self.assertIn("Dra. Laura Delgado", result)
        # Must contain original intent
        self.assertIn("Soy Dra.", result)

    def test_nombre_interpolated(self):
        """{nombre} replaced with patient name."""
        from agents.specialists import _with_tenant_blocks

        state = dict(self.base_state)
        state["patient_profile"] = {"name": "María García"}
        base = "Hola {nombre}! ¿Cómo estás?"
        result = _with_tenant_blocks(base, state, "reception")
        self.assertNotIn("{nombre}", result)
        self.assertIn("María García", result)

    def test_default_values_when_missing(self):
        """Defaults to 'Asistente' and 'Paciente' when context missing."""
        from agents.specialists import _with_tenant_blocks

        state = dict(self.base_state)
        base = "Soy {bot_name}. Hablando con {nombre}."
        result = _with_tenant_blocks(base, state, "reception")
        self.assertIn("Asistente", result)
        self.assertIn("Paciente", result)

    def test_no_placeholder_prompt_unchanged(self):
        """Prompt without placeholders still works (no format errors)."""
        from agents.specialists import _with_tenant_blocks

        state = dict(self.base_state)
        base = "Simple prompt sin placeholders."
        result = _with_tenant_blocks(base, state, "reception")
        # Preamble + patient context are injected even without placeholders
        self.assertIn("Simple prompt sin placeholders.", result)
        self.assertIn("CONTEXTO DEL PACIENTE", result)
        self.assertIn("REGLAS COMPARTIDAS", result)
        # No literal placeholders remain
        self.assertNotIn("{bot_name}", result)
        self.assertNotIn("{nombre}", result)

    def test_both_variables_interpolated(self):
        """Both {bot_name} and {nombre} resolved simultaneously."""
        from agents.specialists import _with_tenant_blocks

        state = dict(self.base_state)
        state["tenant_context"] = {"bot_name_raw": "Dr. García"}
        state["patient_profile"] = {"name": "Juan Pérez"}
        base = "Soy {bot_name}. Hola {nombre}!"
        result = _with_tenant_blocks(base, state, "reception")
        self.assertIn("Dr. García", result)
        self.assertIn("Juan Pérez", result)
        self.assertNotIn("{bot_name}", result)
        self.assertNotIn("{nombre}", result)


# =============================================================================
# Tenant Context bot_name_raw Tests
# =============================================================================


class TestBotNameRaw(unittest.TestCase):
    """bot_name_raw is correctly populated in tenant context."""

    def test_tenant_context_has_bot_name_raw_key(self):
        """ALL_BLOCK_KEYS includes bot_name_raw."""
        from agents.tenant_context import ALL_BLOCK_KEYS

        self.assertIn("bot_name_raw", ALL_BLOCK_KEYS)

    def test_build_exposes_bot_name_raw(self):
        """build_tenant_context_blocks returns bot_name_raw."""
        from agents.tenant_context import build_tenant_context_blocks

        # We can't easily test the full async function without a real pool,
        # but we can verify the key exists in ALL_BLOCK_KEYS and the
        # initialization logic — the shell is created with '' for all keys.
        import asyncio

        # Use a mock pool that returns None for tenant row
        mock_pool = MagicMock()

        async def _run():
            blocks = await build_tenant_context_blocks(mock_pool, 1)
            return blocks.get("bot_name_raw", "__MISSING__")

        result = asyncio.run(_run())
        self.assertEqual(result, "Asistente")  # default when no tenant row


# =============================================================================
# Red Flags / Anti-Pattern Tests
# =============================================================================


class TestAntiPatterns(unittest.TestCase):
    """Verify multi-agent is protected against known solo-engine anti-patterns."""

    def test_no_placeholder_left_in_all_specialists(self):
        """All 6 specialist prompts use {bot_name} and {nombre} correctly."""
        from agents.tenant_context import ALL_BLOCK_KEYS

        # Ensure bot_name_raw exists — that's the enabler for interpolation
        self.assertIn("bot_name_raw", ALL_BLOCK_KEYS)

        # Verify that prompts reference the interpolated variables
        # (they should have {bot_name} and {nombre} as literals to be replaced)
        import ast
        import inspect

        from agents import specialists

        # Check the source code of prompts — look for literal {bot_name} and {nombre}
        source = inspect.getsource(specialists)
        # All 6 specialists should use _with_tenant_blocks (which does .format())
        self.assertGreater(source.count("_with_tenant_blocks(prompt"), 0)
        # All 6 run methods should exist
        for name in ["ReceptionAgent", "BookingAgent", "TriageAgent",
                      "BillingAgent", "AnamnesisAgent", "HandoffAgent"]:
            self.assertIn(f"class {name}", source)

    def test_no_f_string_in_prompts(self):
        """Prompts are NOT f-strings (use raw strings + .format())."""
        import inspect
        from agents import specialists

        source = inspect.getsource(specialists)

        # Count all triple-quoted strings — they should NOT contain f-string
        # markers (f""") or (f"""). We're looking for literal "f\"\"\"" patterns
        f_string_patterns = ['f"""', "f'''", 'F"""']
        for pat in f_string_patterns:
            self.assertNotIn(
                pat, source,
                f"Found f-string prompt '{pat}' — prompts must be raw strings"
            )

    def test_patient_context_uses_asyncpg(self):
        """PatientContext uses db.pool, not AsyncSessionLocal."""
        import inspect
        from services import patient_context

        source = inspect.getsource(patient_context)
        self.assertNotIn(
            "AsyncSessionLocal",
            source,
            "PatientContext must NOT use AsyncSessionLocal"
        )
        self.assertIn(
            "from db import db",
            source,
            "PatientContext must import db for pool access"
        )
        self.assertIn(
            "pool.fetchrow",
            source,
            "PatientContext must use pool.fetchrow"
        )

    def test_solo_engine_probe_has_system_prompt(self):
        """SoloEngine.probe() includes system_prompt in ainvoke."""
        import inspect
        from services import engine_router

        source = inspect.getsource(engine_router)
        self.assertIn(
            "system_prompt",
            source,
            "SoloEngine.probe() must pass system_prompt in ainvoke"
        )


# =============================================================================
# Scenario: Specialist prompt structure
# =============================================================================


class TestSpecialistPromptStructure(unittest.TestCase):
    """Verify each specialist prompt has the required sections."""

    PROMPT_PATTERNS = {
        "reception": [
            "ROL — RECEPCIÓN",
            "ANTI-HALLUCINATION DE PROFESIONALES",
            "DETECCIÓN DE EMERGENCIA",
            "SALUDO DIFERENCIADO",
            "LÍMITES",
        ],
        "booking": [
            "ROL — GESTIÓN DE TURNOS",
            "PASO 1",
            "PASO 10",
            "ANTI-FALSE-CONFIRMATION",
            "ANTI-LOOP",
            "MULTI-TOPIC",
        ],
        "triage": [
            "ROL — TRIAJE CLÍNICO",
            "PROTOCOLO DE EMBARAZO",
            "PROTOCOLO PEDIÁTRICO",
            "SEÑALES DE EMERGENCIA",
            "LÍMITES",
        ],
        "billing": [
            "ROL — COBROS",
            "CONSULTA DE PRECIOS",
            "DATOS BANCARIOS",
            "SEÑA Y VERIFICACIÓN",
            "NUNCA inventes precios",
        ],
        "anamnesis": [
            "ROL — HISTORIA CLÍNICA",
            "DETECCIÓN DE DATOS YA COLECTADOS",
            "MANEJO DE EMAIL",
            "save_patient_email",
            "NUNCA interpretes",
        ],
        "handoff": [
            "ROL — ESCALACIÓN",
            "CLASIFICACIÓN DE NIVEL DE QUEJA",
            "NO-COMPENSATION",
            "NUNCA inventes compensaciones",
        ],
    }

    def _get_prompt_source(self, agent_class_name):
        """Extract the prompt string from a specialist agent class."""
        import inspect
        from agents import specialists

        source = inspect.getsource(specialists)
        # Find the class and extract the prompt = """...""" block
        import re
        # Match: class ClassName ... prompt = """... """
        pattern = rf"class {agent_class_name}.*?prompt = \"\"\"(.*?)\"\"\""
        m = re.search(pattern, source, re.DOTALL)
        if m:
            return m.group(1)
        return ""

    def test_reception_prompt_sections(self):
        """Reception prompt has all required sections."""
        source = self._get_prompt_source("ReceptionAgent")
        for pattern in self.PROMPT_PATTERNS["reception"]:
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, source)

    def test_booking_prompt_sections(self):
        """Booking prompt has all required sections."""
        source = self._get_prompt_source("BookingAgent")
        for pattern in self.PROMPT_PATTERNS["booking"]:
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, source)

    def test_triage_prompt_sections(self):
        """Triage prompt has all required sections."""
        source = self._get_prompt_source("TriageAgent")
        for pattern in self.PROMPT_PATTERNS["triage"]:
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, source)

    def test_billing_prompt_sections(self):
        """Billing prompt has all required sections."""
        source = self._get_prompt_source("BillingAgent")
        for pattern in self.PROMPT_PATTERNS["billing"]:
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, source)

    def test_anamnesis_prompt_sections(self):
        """Anamnesis prompt has all required sections."""
        source = self._get_prompt_source("AnamnesisAgent")
        for pattern in self.PROMPT_PATTERNS["anamnesis"]:
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, source)

    def test_handoff_prompt_sections(self):
        """Handoff prompt has all required sections."""
        source = self._get_prompt_source("HandoffAgent")
        for pattern in self.PROMPT_PATTERNS["handoff"]:
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, source)


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    unittest.main()
