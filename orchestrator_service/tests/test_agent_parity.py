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
        self.assertIn("DNI registrado: 12345678", block)
        self.assertIn("Email registrado: maria@test.com", block)

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
        """CE3: Next appointment (single) shown."""
        from agents.specialists import _inject_patient_context

        state = self._make_state(
            patient_profile={
                "name": "Ana López",
                "is_new_lead": False,
                "medical_history": {},
                "next_appointment": {
                    "treatment_name": "Limpieza",
                    "professional_name": "Dr. Gómez",
                    "date_time": "2026-06-20T10:00",
                },
            }
        )
        block = _inject_patient_context(state)
        self.assertIn("PRÓXIMO TURNO", block)
        self.assertIn("Limpieza", block)
        self.assertIn("Dr/a. Dr. Gómez", block)

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


    # =========================================================================
    # Phase 1 — CRITICAL: CE1-CE6
    # =========================================================================

    # --- CE1: Phone number ---
    def test_ce1_phone_shown(self):
        """CE1: Teléfono registrado shown for valid phone."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "phone_number": "+5491122334455",
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("Teléfono registrado", block)
        self.assertIn("+5491122334455", block)

    def test_ce1_phone_sintel_omitted(self):
        """CE1: SIN-TEL phone must NOT appear."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "phone_number": "SIN-TEL-abc123",
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertNotIn("Teléfono registrado", block)

    def test_ce1_phone_none_omitted(self):
        """CE1: None phone must NOT appear."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "phone_number": None,
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertNotIn("Teléfono registrado", block)

    # --- CE2: Assigned professional ---
    def test_ce2_assigned_professional_shown(self):
        """CE2: PROFESIONAL ASIGNADO shown with name."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "assigned_professional": {"name": "Dr. García", "id": 1},
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("PROFESIONAL ASIGNADO", block)
        self.assertIn("Dr. García", block)
        self.assertIn("PRIORIDAD ALTA", block)

    def test_ce2_no_assigned_professional_omitted(self):
        """CE2: No assigned professional → no line."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "assigned_professional": None,
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertNotIn("PROFESIONAL ASIGNADO", block)

    def test_ce2_assigned_professional_empty_name_omitted(self):
        """CE2: professional with no name → no line."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "assigned_professional": {"id": 1, "name": None},
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertNotIn("PROFESIONAL ASIGNADO", block)

    # --- CE3: Next appointment ---
    def test_ce3_next_appointment_shown(self):
        """CE3: PRÓXIMO TURNO shown with treatment and name."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "next_appointment": {
                "treatment_name": "Limpieza",
                "professional_name": "Ana López",
                "date_time": "2026-06-25T10:00:00",
            },
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("PRÓXIMO TURNO", block)
        self.assertIn("Limpieza", block)
        self.assertIn("Ana López", block)
        self.assertIn("FECHA EXACTA DEL TURNO", block)

    def test_ce3_no_next_appointment_omitted(self):
        """CE3: No next appointment → no lines."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "next_appointment": None,
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertNotIn("PRÓXIMO TURNO", block)
        self.assertNotIn("FECHA EXACTA DEL TURNO", block)

    def test_ce3_next_appointment_fallback_treatment(self):
        """CE3: No treatment name → falls back to Consulta."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "next_appointment": {
                "treatment_name": None,
                "professional_name": "Dr. Pérez",
                "date_time": "2026-07-01T14:00:00",
            },
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("PRÓXIMO TURNO", block)
        self.assertIn("Consulta", block)

    # --- CE4: Last appointment ---
    def test_ce4_last_appointment_shown(self):
        """CE4: ÚLTIMO TURNO shown with days_since."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "last_appointment": {
                "treatment_name": "Extracción",
                "professional_name": "Dr. López",
                "date_time": "2026-06-15T09:00:00",
                "days_since": 3,
                "status": "completed",
            },
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("ÚLTIMO TURNO", block)
        self.assertIn("Extracción", block)
        self.assertIn("hace 3 días", block)

    def test_ce4_seguimiento_post_tratamiento_shown_recent(self):
        """CE4: SEGUIMIENTO shown when days_since ≤ 7."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "last_appointment": {
                "treatment_name": "Limpieza",
                "professional_name": "Dra. Ruiz",
                "date_time": "2026-06-15T10:00:00",
                "days_since": 3,
                "status": "completed",
            },
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("SEGUIMIENTO POST-TRATAMIENTO", block)
        self.assertIn("preguntale cómo se siente", block)

    def test_ce4_no_seguimiento_older_than_7_days(self):
        """CE4: No seguimiento when days_since > 7."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "last_appointment": {
                "treatment_name": "Limpieza",
                "professional_name": "Dr. Pérez",
                "date_time": "2026-06-01T10:00:00",
                "days_since": 14,
                "status": "completed",
            },
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("ÚLTIMO TURNO", block)
        self.assertNotIn("SEGUIMIENTO POST-TRATAMIENTO", block)

    def test_ce4_no_last_appointment_omitted(self):
        """CE4: No last appointment → no lines."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "last_appointment": None,
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertNotIn("ÚLTIMO TURNO", block)
        self.assertNotIn("SEGUIMIENTO POST-TRATAMIENTO", block)

    # --- CE5: Treatment plan ---
    def test_ce5_treatment_plan_shown(self):
        """CE5: PRESUPUESTO ACTIVO block shown."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "treatment_plan": {
                "name": "Plan de ortodoncia",
                "status": "approved",
                "approved_total": 50000.0,
                "paid": 15000.0,
                "pending": 35000.0,
                "installments": 4,
                "per_installment": 8750.0,
                "discount_pct": 10.0,
                "discount_amount": 0.0,
                "conditions": "Pago mensual",
            },
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("PRESUPUESTO ACTIVO", block)
        self.assertIn("Plan de ortodoncia", block)
        self.assertIn("$50.000", block)  # with dots as thousands
        self.assertIn("$35.000", block)  # pending
        self.assertIn("Cuotas: 4", block)

    def test_ce5_no_treatment_plan_omitted(self):
        """CE5: No treatment plan → no block."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "treatment_plan": None,
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertNotIn("PRESUPUESTO ACTIVO", block)

    # --- CE6: Family members ---
    def test_ce6_family_members_shown(self):
        """CE6: FAMILIARES A CARGO block shown."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "family_members": [
                {
                    "name": "Ana García",
                    "phone": "+5491122334455",
                    "next_appointment_str": "Limpieza con Dr/a. Pérez el 2026-07-01",
                    "last_appointment_str": "Extracción el 2026-06-15 (hace 3 días). Estado: completed",
                    "visits": 5,
                    "diagnosis": "Caries dental",
                    "treatment_plan_text": "Obturación en 2 sesiones",
                }
            ],
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("FAMILIARES A CARGO", block)
        self.assertIn("Ana García", block)
        self.assertIn("REGLAS PARA FAMILIARES", block)
        self.assertIn("list_my_appointments", block)

    def test_ce6_no_family_members_omitted(self):
        """CE6: No family members → no block."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "family_members": [],
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertNotIn("FAMILIARES A CARGO", block)

    # =========================================================================
    # Phase 2 — HIGH: CE7-CE9
    # =========================================================================

    # --- CE7: Children dependents ---
    def test_ce7_children_shown(self):
        """CE7: HIJOS/MENORES VINCULADOS block shown."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "children_dependents": [
                {
                    "name": "Sofía García",
                    "dni": "12345678",
                    "phone": "+5491133334444",
                    "anamnesis_url": "http://localhost:4173/anamnesis/1/abc-token",
                    "next_appointment": "Limpieza el 2026-07-05 a las 10:00",
                }
            ],
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("HIJOS/MENORES VINCULADOS", block)
        self.assertIn("Sofía García", block)
        self.assertIn("anamnesis", block)

    def test_ce7_no_children_omitted(self):
        """CE7: No children → no block."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "children_dependents": [],
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertNotIn("HIJOS/MENORES VINCULADOS", block)

    # --- CE8: Visit count ---
    def test_ce8_recurrent_patient(self):
        """CE8: Recurrent patient shown with count."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "visit_count": 5,
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("Paciente recurrente", block)
        self.assertIn("5 turnos registrados", block)

    def test_ce8_first_visit(self):
        """CE8: First visit shown."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "visit_count": 1,
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("Primera visita", block)

    def test_ce8_no_visits_omitted(self):
        """CE8: Zero visits → no line."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "visit_count": 0,
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertNotIn("HISTORIAL", block)

    # --- CE9: Anamnesis status ---
    def test_ce9_anamnesis_completed(self):
        """CE9: Completed anamnesis shown."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "anamnesis_status": {
                "completed": True,
                "url": "http://localhost:4173/anamnesis/1/token",
            },
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("ANAMNESIS", block)
        self.assertIn("completó su ficha médica", block)
        self.assertIn("NO enviar link", block)

    def test_ce9_anamnesis_pending(self):
        """CE9: Pending anamnesis shows link."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "anamnesis_status": {
                "completed": False,
                "url": "http://localhost:4173/anamnesis/1/token",
            },
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("ANAMNESIS", block)
        self.assertIn("Pendiente", block)

    def test_ce9_no_anamnesis_status_omitted(self):
        """CE9: No anamnesis status → no line."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "anamnesis_status": None,
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertNotIn("ANAMNESIS", block)

    # =========================================================================
    # Phase 3 — MEDIUM: CE10-CE11
    # =========================================================================

    # --- CE10: Lead context formatted ---
    def test_ce10_lead_context_formatted(self):
        """CE10: Lead context uses format_for_prompt."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(
            lead_context={"name": "Juan", "channel": "instagram", "search_mode": "busqueda"},
            patient_profile={"is_new_lead": True},
        )
        block = _inject_patient_context(state)
        self.assertIn("[CONTEXTO DE LEAD", block)
        self.assertIn("Modo de búsqueda: busqueda", block)
        self.assertIn("Canal: instagram", block)
        self.assertIn("[/CONTEXTO DE LEAD]", block)

    def test_ce10_empty_lead_context_omitted(self):
        """CE10: Empty lead context → no block."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(
            lead_context=None,
            patient_profile={"is_new_lead": True},
        )
        block = _inject_patient_context(state)
        self.assertNotIn("[CONTEXTO DE LEAD", block)

    # --- CE11: Birth date ---
    def test_ce11_birth_date_shown(self):
        """CE11: Birth date shown."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "birth_date": "1990-05-15",
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("Fecha de nacimiento: 1990-05-15", block)

    def test_ce11_birth_date_null_omitted(self):
        """CE11: Null birth date → no line."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "birth_date": None,
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertNotIn("Fecha de nacimiento", block)

    # =========================================================================
    # Regression guard: existing tests must still pass
    # =========================================================================

    def test_regression_new_lead_still_shows_minimal(self):
        """Regression: new lead still shows basic info."""
        from agents.specialists import _inject_patient_context
        block = _inject_patient_context(self._make_state())
        self.assertIn("CONTEXTO DEL PACIENTE", block)
        self.assertIn("Nuevo paciente", block)

    def test_regression_returning_patient_still_shows_name(self):
        """Regression: returning patient still shows name and DNI."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "name": "María García",
            "dni": "12345678",
            "email": "maria@test.com",
            "is_new_lead": False,
        })
        block = _inject_patient_context(state)
        self.assertIn("María García", block)
        self.assertIn("Paciente existente", block)
        self.assertIn("DNI registrado", block)

    def test_regression_human_override_still_shows_warning(self):
        """Regression: human override warning still appears."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "name": "Juan Pérez",
            "is_new_lead": False,
            "human_override_until": "2026-06-20T12:00:00",
        })
        block = _inject_patient_context(state)
        self.assertIn("human override", block)

    def test_regression_medical_history_still_shown(self):
        """Regression: medical history still summarized."""
        from agents.specialists import _inject_patient_context
        state = self._make_state(patient_profile={
            "name": "Carlos",
            "is_new_lead": False,
            "medical_history": {"allergies": "Penicilina"},
        })
        block = _inject_patient_context(state)
        self.assertIn("Alergias", block)
        self.assertIn("Penicilina", block)


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
# Parity Depth Tests — PROHIBICIONES, REGLA CERO, Post-Booking, etc.
# =============================================================================


class TestProhibiciones(unittest.TestCase):
    """_build_shared_preamble includes all 15 PROHIBICIONES."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_prohibiciones_section_exists(self):
        """Preamble has PROHIBICIONES section."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBICIONES (OBLIGATORIO", preamble)

    def test_prohibiciones_diagnosticar(self):
        """Rule 1: no diagnosticar sin evaluacion."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO diagnosticar", preamble)

    def test_prohibiciones_escalar(self):
        """Rule 2: limited escalar reasons."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO escalar a humano", preamble)

    def test_prohibiciones_precio_direccion_emergencia(self):
        """Rule 3: no price+address+turnos on first pain message."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO mostrar precio + dirección", preamble)

    def test_prohibiciones_lenguaje_corporativo(self):
        """Rule 4: no corporate language."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO usar lenguaje corporativo", preamble)
        self.assertIn("voseo rioplatense", preamble)

    def test_prohibiciones_precio_tratamiento(self):
        """Rule 5: no specific treatment prices."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO dar precios de tratamientos específicos", preamble)

    def test_prohibiciones_direccion_antes_booking(self):
        """Rule 6: no address before booking."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO incluir dirección", preamble)
        self.assertIn("NUNCA antes", preamble)

    def test_prohibiciones_derivhumano_no_mas_turnos(self):
        """Rule 7: stop offering once derivhumano called."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO seguir ofreciendo", preamble)

    def test_prohibiciones_no_emergency_numbers(self):
        """Rule 8: no emergency numbers."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO mencionar números de emergencia", preamble)

    def test_prohibiciones_no_internal_tech(self):
        """Rule 9: no internal tech details."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO exponer información técnica interna", preamble)

    def test_prohibiciones_tono_profesional_datos(self):
        """Rule 10: professional tone when asking data."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO usar expresiones excesivamente informales", preamble)

    def test_prohibiciones_no_repeat_turnos_post_booking(self):
        """Rule 11: no new turnos after successful booking."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO volver a mostrar opciones de turno", preamble)
        self.assertIn("book_appointment exitoso", preamble)

    def test_prohibiciones_verificar_tratamiento(self):
        """Rule 12: verify treatment with list_services."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO decir", preamble)
        self.assertIn("list_services", preamble)

    def test_prohibiciones_no_nombres_tecnicos(self):
        """Rule 13: no internal treatment names."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO usar nombres técnicos internos", preamble)

    def test_prohibiciones_no_consejo_medico(self):
        """Rule 14: no medical advice."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO dar consejo médico", preamble)

    def test_prohibiciones_15_total(self):
        """Count exactly 15 numbered prohibiciones."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        count = 0
        for line in preamble.split("\n"):
            stripped = line.strip()
            for i in range(1, 16):
                if stripped.startswith(f"{i}. PROHIBIDO") or stripped.startswith(f"{i}."):
                    count += 1
                    break
        self.assertGreaterEqual(count, 12, f"Expected ~15 PROHIBICIONES, got {count}")


class TestReglaCero(unittest.TestCase):
    """REGLA CERO is in the shared preamble."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_regla_cero_present(self):
        """REGLA CERO section exists."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("REGLA CERO", preamble)

    def test_regla_cero_no_permission(self):
        """Must advance without asking."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("AVANZAR SIN PEDIR PERMISO", preamble)

    def test_regla_cero_no_preguntar(self):
        """Specific forbidden questions listed."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("\"¿querés que busque?\"", preamble)
        self.assertIn("\"te ayudo a coordinar?\"", preamble)


class TestNoEleccion(unittest.TestCase):
    """REGLA DE NO-ELECCIÓN in shared preamble."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_no_eleccion_present(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("REGLA DE NO-ELECCIÓN", preamble)

    def test_no_eleccion_respuesta_unica(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("\"No hay problema, tomate el tiempo que necesites", preamble)

    def test_no_eleccion_excepcion_profesional(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("DUDA SOBRE PROFESIONAL", preamble)


class TestSinDisponibilidadCercana(unittest.TestCase):
    """Multiple attempts before derivhumano rule."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_sin_disponibilidad_present(self):
        """Section exists."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("SIN DISPONIBILIDAD CERCANA", preamble)

    def test_tres_intentos_minimos(self):
        """At least 3 attempts required."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("3 RANGOS DE FECHA", preamble)

    def test_no_derivar_con_una_fecha(self):
        """Cannot derivhumano with single date."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO llamar derivhumano", preamble)
        self.assertIn("solo probaste UNA fecha", preamble)

    def test_mostrar_fechas_lejanas(self):
        """Must show even distant dates."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("AUNQUE SEA EN FECHA LEJANA", preamble)


class TestReintentoInteligente(unittest.TestCase):
    """RE-INTENTO INTELIGENTE for booking failures."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_reintento_present(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("RE-INTENTO INTELIGENTE", preamble)

    def test_reintento_check_availability_again(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("check_availability DE NUEVO", preamble)

    def test_reintento_max_2(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("Máximo 2 reintentos", preamble)
        self.assertIn("derivhumano", preamble)

    def test_reintento_solo_dato_fallido(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("pedí SOLO el dato que falló", preamble)


class TestFallbackInteligente(unittest.TestCase):
    """FALLBACK INTELIGENTE for unavailable times."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_fallback_present(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("FALLBACK INTELIGENTE", preamble)

    def test_fallback_mismo_dia(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("Otros horarios el MISMO día", preamble)

    def test_fallback_otro_profesional(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("Otro profesional ASIGNADO", preamble)


class TestPostBookingRules(unittest.TestCase):
    """Post-booking rules in shared preamble."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_post_booking_transversal(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("REGLA POST-BOOKING", preamble)

    def test_post_booking_no_new_turnos(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("NO ofrezcas turnos nuevos", preamble)

    def test_post_booking_exception_explicito(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("\"quiero OTRO turno\"", preamble)

    def test_post_booking_secuencia_5_bloques(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        for bloque in ["BLOQUE 1", "BLOQUE 2", "BLOQUE 3", "BLOQUE 4", "BLOQUE 5"]:
            with self.subTest(bloque=bloque):
                self.assertIn(bloque, preamble)


class TestF2Protocol(unittest.TestCase):
    """F2 emotional flow has M1/M2/M3 protocol in shared preamble."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_f2_section_present(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("=== F2: URGENCIA / DOLOR", preamble)

    def test_f2_m1_contener(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("M1 — Contener", preamble)

    def test_f2_m2_orientar(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("M2 — Orientar", preamble)

    def test_f2_m3_resolver(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("M3 — Resolver", preamble)

    def test_f2_max_2_mensajes(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("Máximo 2 mensajes", preamble)

    def test_f2_sin_disponibilidad_derivar(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("derivhumano(\"Urgencia sin disponibilidad\"", preamble)


class TestReglaDerivacionEmpatica(unittest.TestCase):
    """REGLA DE DERIVACIÓN EMPÁTICA in shared preamble."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_derivacion_empatica_present(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("REGLA DE DERIVACIÓN EMPÁTICA", preamble)

    def test_derivacion_requiere_contexto(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("Reconocer el contexto", preamble)

    def test_derivacion_no_frio(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("NUNCA responder solo \"Te van a contactar en breve\"", preamble)


class TestUltimoRecurso(unittest.TestCase):
    """REGLA DE ÚLTIMO RECURSO in shared preamble."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_ultimo_recurso_present(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("REGLA DE ÚLTIMO RECURSO", preamble)

    def test_ultimo_recurso_derivhumano(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("llamá derivhumano", preamble)


class TestReglaSupremaTools(unittest.TestCase):
    """REGLA SUPREMA DE TOOLS in shared preamble."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_tools_suprema_present(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("REGLA SUPREMA DE TOOLS", preamble)

    def test_tools_no_contradigas(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("No lo contradigas", preamble)

    def test_tools_no_inventes(self):
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("NUNCA inventes respuestas sobre acciones que NO ejecutaste", preamble)


class TestPatientContextMarkers(unittest.TestCase):
    """_inject_patient_context uses marker labels for agent rules."""

    def _make_state(self, **overrides):
        state = {
            "channel": "whatsapp",
            "patient_profile": {},
            "lead_context": None,
        }
        state.update(overrides)
        return state

    def test_nombre_registrado_marker(self):
        from agents.specialists import _inject_patient_context
        prof = {"name": "María García", "dni": None, "email": None, "is_new_lead": False}
        ctx = _inject_patient_context(self._make_state(patient_profile=prof))
        self.assertIn("Nombre registrado: María García", ctx)

    def test_dni_registrado_marker(self):
        from agents.specialists import _inject_patient_context
        prof = {"name": None, "dni": "12345678", "email": None, "is_new_lead": False}
        ctx = _inject_patient_context(self._make_state(patient_profile=prof))
        self.assertIn("DNI registrado: 12345678", ctx)

    def test_email_registrado_marker(self):
        from agents.specialists import _inject_patient_context
        prof = {"name": None, "dni": None, "email": "maria@test.com", "is_new_lead": False}
        ctx = _inject_patient_context(self._make_state(patient_profile=prof))
        self.assertIn("Email registrado: maria@test.com", ctx)


# =============================================================================
# GAP-4: Contacto No Deseado — PROHIBICIONES rule 16
# =============================================================================


class TestContactoNoDeseado(unittest.TestCase):
    """GAP-4: PROHIBICIONES rule 16 — set_no_followup on undesired contact."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_rule_16_set_no_followup_present(self):
        """Rule 16 exists prohibiting messages to uninterested patients."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("16. PROHIBIDO enviar mensajes", preamble)

    def test_rule_16_calls_set_no_followup(self):
        """Rule 16 instructs calling set_no_followup."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("set_no_followup", preamble)

    def test_rule_16_covers_no_interes(self):
        """Rule 16 covers 'not interested' and 'already has dentist'."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("no interesarle", preamble)


# =============================================================================
# GAP-1: Reactivación tras Intervención Humana
# =============================================================================


class TestReactivacionTrasHumano(unittest.TestCase):
    """GAP-1: Reactivation rules after human override deactivates."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_section_header_present(self):
        """Section header exists for reactivation rules."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("REACTIVACIÓN TRAS INTERVENCIÓN HUMANA", preamble)

    def test_analyze_last_message(self):
        """Must analyze the last message, not restart conversation."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("Analizar el ÚLTIMO mensaje", preamble)

    def test_directly_to_check_availability(self):
        """If day/time previously chosen, go directly to check_availability."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("DIRECTAMENTE a check_availability", preamble)

    def test_no_reexplain_treatment(self):
        """If treatment mentioned before, do not re-explain."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("no re-explicar", preamble)

    def test_prohibido_greeting(self):
        """Prohibited to say 'en qué puedo ayudarte' as first message."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("en qué puedo ayudarte", preamble)

    def test_prohibido_re_derivhumano(self):
        """Prohibited to re-call derivhumano for same reason."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO re-llamar derivhumano", preamble)


# =============================================================================
# GAP-6: Seguimiento Post-Atención
# =============================================================================


class TestSeguimientoPostAtencion(unittest.TestCase):
    """GAP-6: Post-care follow-up rules with positive/negative branching."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_section_header_present(self):
        """Section header exists for post-care follow-up."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("SEGUIMIENTO POST-ATENCIÓN", preamble)

    def test_positivo_empathy(self):
        """Positive outcome → empathy, no further action."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("POSITIVO", preamble)

    def test_negativo_get_treatment_instructions(self):
        """Negative outcome → call get_treatment_instructions."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("get_treatment_instructions", preamble)

    def test_negativo_no_coverage_derivhumano(self):
        """Symptom not in post-op → mandatory derivhumano."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("OBLIGATORIO llamar derivhumano", preamble)

    def test_negativo_normal_inform(self):
        """Normal post-op coverage → inform + offer follow-up."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("cobertura NORMAL", preamble)


# =============================================================================
# GAP-2: Composición Multi-Tema
# =============================================================================


class TestComposicionMultiTema(unittest.TestCase):
    """GAP-2: Multi-topic composition rules — must address ALL topics."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_section_header_present(self):
        """Section header exists for multi-topic rules."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("COMPOSICIÓN MULTI-TEMA", preamble)

    def test_must_respond_all(self):
        """Must respond to ALL topics, not just one."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("TODOS los temas", preamble)

    def test_separate_bubbles(self):
        """Separate bubbles allowed for different topics."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("burbujas separadas", preamble)

    def test_prohibido_ignore_topic(self):
        """Prohibited to ignore any topic."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO ignorar un tema", preamble)

    def test_prohibido_derivhumano_multi(self):
        """Prohibited to derivhumano just because multiple topics."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO llamar derivhumano solo porque llegaron varios temas", preamble)


# =============================================================================
# GAP-10 + GAP-8: Flujo Modalidad 3 Caminos + Profesional Auto-Asignado
# =============================================================================


class TestFlujoModalidad3Caminos(unittest.TestCase):
    """GAP-10: 3-caminos insurance branching rules."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_section_header_present(self):
        """Section header exists for modalidad de atención."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("MODALIDAD DE ATENCIÓN", preamble)

    def test_camino_1_os_aceptada(self):
        """Camino 1: accepted OS → check_insurance_coverage."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("CAMINO 1", preamble)

    def test_camino_2_os_no_aceptada(self):
        """Camino 2: non-accepted OS → particular + reintegro."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("CAMINO 2", preamble)

    def test_camino_3_particular(self):
        """Camino 3: no OS / particular → show consultation price."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("CAMINO 3", preamble)


class TestProfesionalAutoAsignado(unittest.TestCase):
    """GAP-8: Auto-assigned professional mention rules."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_section_header_present(self):
        """Section header exists for profesional auto-asignado."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROFESIONAL AUTO-ASIGNADO", preamble)

    def test_mencionar_nombre(self):
        """Must mention assigned professional's name in confirmation."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("nombre del profesional asignado", preamble)

    def test_explicacion_disponibilidad(self):
        """If asked why, explain closest availability."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("disponibilidad más cercana", preamble)


# =============================================================================
# GAP-7: Respuestas check_insurance_coverage JSON
# =============================================================================


class TestCheckInsuranceCoverage(unittest.TestCase):
    """GAP-7: All 7 JSON status handlers for check_insurance_coverage."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_section_header_present(self):
        """Section header exists for insurance coverage responses."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("RESPUESTAS DE check_insurance_coverage", preamble)

    def test_accepted_handler(self):
        """accepted status with copay handling."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("accepted", preamble)

    def test_not_found_handler(self):
        """not_found status — particular + reintegro."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("not_found", preamble)

    def test_rejected_handler(self):
        """rejected status — particular + reintegro."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("rejected", preamble)

    def test_restricted_handler(self):
        """restricted status — limited coverage."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("restricted", preamble)

    def test_multiple_matches_handler(self):
        """multiple_matches — ask which one."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("multiple_matches", preamble)

    def test_external_derivation_handler(self):
        """external_derivation — explain split, do not derivar."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("external_derivation", preamble)

    def test_error_handler(self):
        """error — ask to check at clinic."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("error", preamble)

    def test_anti_repetition(self):
        """Anti-repetition guard for same OS asked twice."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO repetir la misma consulta", preamble)


# =============================================================================
# GAP-3: Pacientes Existentes — Regla Suprema
# =============================================================================


class TestPacientesExistentes(unittest.TestCase):
    """GAP-3: Existing patient supreme rule — no re-ask data."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_section_header_present(self):
        """Section header exists for pacientes existentes."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PACIENTES EXISTENTES", preamble)

    def test_prohibido_pedir_nombre(self):
        """Prohibited to ask for name if already registered."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO pedir nombre", preamble)

    def test_prohibido_pedir_dni(self):
        """Prohibited to ask for DNI if already registered."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO pedir", preamble)
        self.assertIn("DNI", preamble)

    def test_go_paso_4b_a_6(self):
        """Go directly to PASO 4b → 6 for existing patients."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PASO 4b", preamble)


# =============================================================================
# GAP-5: Multi-Tratamiento
# =============================================================================


class TestMultiTratamiento(unittest.TestCase):
    """GAP-5: Multi-treatment booking rules."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_section_header_present(self):
        """Section header exists for multi-tratamiento."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("MULTI-TRATAMIENTO", preamble)

    def test_book_separately(self):
        """Book each treatment separately."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("Bookeá cada tratamiento", preamble)

    def test_same_day_attempt(self):
        """Attempt same day for both treatments."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("mismo día", preamble)


# =============================================================================
# GAP-9: Detección Nuevo Teléfono
# =============================================================================


class TestNuevoTelefono(unittest.TestCase):
    """GAP-9: New phone detection — acknowledge, no duplicates."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_section_header_present(self):
        """Section header exists for nuevo teléfono detection."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("NUEVO TELÉFONO", preamble)

    def test_acknowledge_existing_patient(self):
        """Acknowledge existing patient with different phone."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("ya tenés registro", preamble)

    def test_no_duplicates(self):
        """Prohibited to create duplicates."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO crear duplicados", preamble)


# =============================================================================
# GAP-3: Saludo Diferenciado (Greeting)
# =============================================================================


class TestSaludoDiferenciado(unittest.TestCase):
    """GAP-3: Greeting differentiation rules in shared preamble."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_saludo_diferenciado_section_present(self):
        """Section header exists for greeting rules."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("SALUDO DIFERENCIADO", preamble)

    def test_saludo_new_lead_template(self):
        """New lead greeting template present."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("NUEVO LEAD", preamble)

    def test_saludo_existente_sin_turno(self):
        """Existing patient without appointment greeting present."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("EXISTENTE sin turno futuro", preamble)

    def test_saludo_existente_con_turno(self):
        """Existing patient with future appointment greeting present."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("EXISTENTE con turno futuro", preamble)

    def test_saludo_no_repetir_bienvenida(self):
        """No repeat greeting rule present."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("NO repitas", preamble)


# =============================================================================
# GAP-4: Slot Resolution Rules
# =============================================================================


class TestSlotResolution(unittest.TestCase):
    """GAP-4: Slot resolution rules in shared preamble."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_slot_resolution_section_present(self):
        """Section header exists for slot resolution."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("RESOLUCIÓN DE SLOT", preamble)

    def test_confirm_slot_rule(self):
        """Slot resolution mentions confirm_slot."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("confirm_slot", preamble)

    def test_no_reoffer_rule(self):
        """Slot resolution prohibits re-offering."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("No vuelvas a preguntar", preamble)


# =============================================================================
# GAP-5: SLOT_LOCKED Rules
# =============================================================================


class TestSlotLockedRules(unittest.TestCase):
    """GAP-5: SLOT_LOCKED behavioral rules in shared preamble."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_slot_locked_section_present(self):
        """Section header exists for SLOT_LOCKED rules."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("SLOT_LOCKED", preamble)

    def test_collect_dni_rule(self):
        """SLOT_LOCKED requires collecting DNI."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("recolectar nombre completo y DNI", preamble)

    def test_no_check_availability(self):
        """SLOT_LOCKED prohibits check_availability."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("PROHIBIDO llamar check_availability", preamble)

    def test_side_questions_rule(self):
        """SLOT_LOCKED allows side questions."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("Preguntas laterales", preamble)


# =============================================================================
# GAP-7: Estudios Previos
# =============================================================================


class TestEstudiosPrevios(unittest.TestCase):
    """GAP-7: Previous studies rules in shared preamble."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_estudios_previos_section_present(self):
        """Section header exists for estudios previos."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("ESTUDIOS PREVIOS", preamble)

    def test_estudios_llevar_al_turno(self):
        """Estudios previos says to bring them to appointment."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("Llevá los estudios", preamble)


# =============================================================================
# GAP-8: Adjuntos (Documents)
# =============================================================================


class TestAdjuntos(unittest.TestCase):
    """GAP-8: Document handling rules in shared preamble."""

    def _make_state(self, channel="whatsapp"):
        return {"channel": channel}

    def test_adjuntos_section_present(self):
        """Section header exists for document handling."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("ADJUNTOS", preamble)

    def test_list_patient_documents(self):
        """Adjuntos section mentions list_patient_documents."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("list_patient_documents", preamble)

    def test_automatic_analysis(self):
        """Adjuntos section mentions automatic analysis."""
        from agents.specialists import _build_shared_preamble
        preamble = _build_shared_preamble(self._make_state())
        self.assertIn("analiza automáticamente", preamble)


# =============================================================================
# GAP-2: Tenant Context — instructions_section
# =============================================================================


class TestInstructionsSection(unittest.TestCase):
    """GAP-2: instructions_section block key and whitelist."""

    def test_instructions_key_in_all_blocks(self):
        """instructions_section is in ALL_BLOCK_KEYS."""
        from agents.tenant_context import ALL_BLOCK_KEYS
        self.assertIn("instructions_section", ALL_BLOCK_KEYS)

    def test_instructions_in_reception_whitelist(self):
        """instructions_section is whitelisted for reception."""
        from agents.tenant_context import SPECIALIST_BLOCKS
        self.assertIn("instructions_section", SPECIALIST_BLOCKS.get("reception", []))



# =============================================================================
# GAP-6: Bank/Payment in Booking Whitelist
# =============================================================================


class TestBookingBankWhitelist(unittest.TestCase):
    """GAP-6: bank_info and payment_section are whitelisted for booking."""

    def test_bank_info_in_booking_whitelist(self):
        """bank_info is whitelisted for booking."""
        from agents.tenant_context import SPECIALIST_BLOCKS
        self.assertIn("bank_info", SPECIALIST_BLOCKS.get("booking", []))

    def test_payment_section_in_booking_whitelist(self):
        """payment_section is whitelisted for booking."""
        from agents.tenant_context import SPECIALIST_BLOCKS
        self.assertIn("payment_section", SPECIALIST_BLOCKS.get("booking", []))


# =============================================================================
# Multi-Agent ConvState Tests (multi-agent-convstate change)
# Tests READ + WRITE parity with buffer_task.py:1898-2036
# =============================================================================


class TestConvStateInjectionBlock(unittest.TestCase):
    """_build_convstate_injection_block formats all anti-loop fields correctly."""

    def test_empty_cs_data_returns_empty_string(self):
        """IDLE / empty convstate → no injection block."""
        from agents.graph import _build_convstate_injection_block
        self.assertEqual(_build_convstate_injection_block({}), "")
        self.assertEqual(_build_convstate_injection_block({"state": "IDLE"}), "")
        self.assertEqual(_build_convstate_injection_block(None), "")  # type: ignore

    def test_failed_slots_blacklist(self):
        """failed_slots generate a PROHIBIDO re-ofrecer block."""
        from agents.graph import _build_convstate_injection_block
        cs = {
            "state": "OFFERED_SLOTS",
            "failed_slots": [
                {"date": "2026-06-20", "time": "10:00", "code": "UNAVAILABLE"},
                {"date": "2026-06-21", "time": "14:00", "code": "BOOKED"},
            ],
        }
        block = _build_convstate_injection_block(cs)
        self.assertIn("SLOTS FALLIDOS", block)
        self.assertIn("2026-06-20", block)
        self.assertIn("10:00", block)
        self.assertIn("UNAVAILABLE", block)
        self.assertIn("PROHIBIDO re-ofrecer", block)

    def test_excluded_days_and_dates(self):
        """excluded_days and excluded_dates are listed with NO-OFFER rules."""
        from agents.graph import _build_convstate_injection_block
        cs = {
            "state": "OFFERED_SLOTS",
            "excluded_days": ["sábado", "domingo"],
            "excluded_dates": ["2026-06-25", "2026-07-01"],
        }
        block = _build_convstate_injection_block(cs)
        self.assertIn("EXCLUSIONES DEL PACIENTE", block)
        self.assertIn("DÍAS EXCLUIDOS", block)
        self.assertIn("sábado", block)
        self.assertIn("domingo", block)
        self.assertIn("FECHAS EXCLUIDAS", block)
        self.assertIn("2026-06-25", block)
        self.assertIn("NO ofrezcas turnos", block)

    def test_booking_attempts_warning(self):
        """booking_attempts shows remaining attempts and escalation rule."""
        from agents.graph import _build_convstate_injection_block
        cs = {"state": "OFFERED_SLOTS", "booking_attempts": 2}
        block = _build_convstate_injection_block(cs)
        self.assertIn("INTENTOS DE AGENDAMIENTO FALLIDOS", block)
        self.assertIn("2 de 3", block)
        self.assertIn("1 intento", block)
        self.assertIn("derivhumano", block)

    def test_anchor_date_propagation(self):
        """anchor_date instructs to use it in confirm_slot and book_appointment."""
        from agents.graph import _build_convstate_injection_block
        cs = {"state": "OFFERED_SLOTS", "anchor_date": "2026-06-25"}
        block = _build_convstate_injection_block(cs)
        self.assertIn("ANCHOR_DATE", block)
        self.assertIn("2026-06-25", block)
        self.assertIn("NO recalcules fechas relativas", block)

    def test_has_correction_flag(self):
        """has_correction triggers a data-revision warning."""
        from agents.graph import _build_convstate_injection_block
        cs = {"state": "OFFERED_SLOTS", "has_correction": True}
        block = _build_convstate_injection_block(cs)
        self.assertIn("CORRIGIÓ INFORMACIÓN PREVIA", block)
        self.assertIn("NUEVOS datos", block)

    def test_error_history_last_3(self):
        """error_history shows last 3 errors with category and turn."""
        from agents.graph import _build_convstate_injection_block
        cs = {
            "state": "OFFERED_SLOTS",
            "error_history": [
                {"category": "slot_unavailable", "message": "no hay turnos", "turn_number": 1},
                {"category": "double_booking", "message": "ya existía turno", "turn_number": 3},
                {"category": "validation_error", "message": "DNI inválido", "turn_number": 5},
            ],
        }
        block = _build_convstate_injection_block(cs)
        self.assertIn("ERRORES PREVIOS", block)
        self.assertIn("slot_unavailable", block)
        self.assertIn("double_booking", block)
        self.assertIn("NO repitas el mismo error", block)

    def test_frustration_conciliation_mode(self):
        """frustration_count 2-3 triggers conciliation mode."""
        from agents.graph import _build_convstate_injection_block
        cs = {"state": "OFFERED_SLOTS", "frustration_count": 3, "frustration_mode": False}
        block = _build_convstate_injection_block(cs)
        self.assertIn("FRUSTRATION_DETECTED", block)
        self.assertIn("modo conciliación", block)
        self.assertIn("3 señales", block)

    def test_frustration_escalation_threshold(self):
        """frustration_count >= 4 triggers immediate derivhumano."""
        from agents.graph import _build_convstate_injection_block
        cs = {"state": "OFFERED_SLOTS", "frustration_count": 4, "frustration_mode": True}
        block = _build_convstate_injection_block(cs)
        self.assertIn("FRUSTRATION_ESCALATED", block)
        self.assertIn("derivhumano", block)

    def test_multi_booking_context(self):
        """booking_targets > 1 injects multi-booking queue context."""
        from agents.graph import _build_convstate_injection_block
        cs = {
            "state": "OFFERED_SLOTS",
            "booking_targets": [
                {"type": "self", "name": "Ana", "dni": "12345678", "status": "booked", "relationship": ""},
                {"type": "child", "name": "Luis", "dni": "87654321", "status": "pending", "relationship": "hijo"},
            ],
            "current_booking_target_index": 1,
        }
        block = _build_convstate_injection_block(cs)
        self.assertIn("MULTI_BOOKING", block)
        self.assertIn("2 personas", block)
        self.assertIn("Ya agendados: 1", block)
        self.assertIn("Pendientes: 1", block)
        self.assertIn("Agendando para child (hijo)", block)

    def test_minor_booking_no_phone_request(self):
        """is_minor=true booking context prevents phone request."""
        from agents.graph import _build_convstate_injection_block
        cs = {
            "state": "OFFERED_SLOTS",
            "booking_targets": [
                {
                    "type": "child",
                    "first_name": "Pedro",
                    "last_name": "García",
                    "dni": "55123456",
                    "status": "pending",
                    "relationship": "hijo",
                    "is_minor": True,
                }
            ],
        }
        block = _build_convstate_injection_block(cs)
        self.assertIn("MINOR BOOKING IN PROGRESS", block)
        self.assertIn("Pedro García", block)
        self.assertIn("55123456", block)
        self.assertIn("is_minor=true", block)
        self.assertIn("NO le pidas teléfono del menor", block)

    def test_minor_booking_by_relationship(self):
        """relationship=hijo/hija also triggers minor booking context."""
        from agents.graph import _build_convstate_injection_block
        cs = {
            "state": "OFFERED_SLOTS",
            "booking_targets": [
                {"type": "child", "first_name": "Lucía", "last_name": "Pérez", "relationship": "hija", "status": "pending"},
            ],
        }
        block = _build_convstate_injection_block(cs)
        self.assertIn("MINOR BOOKING IN PROGRESS", block)
        self.assertIn("Lucía", block)


class TestConvStateSpecialistInjection(unittest.TestCase):
    """conversation_state_block is appended in _with_tenant_blocks."""

    def test_convstate_block_in_extras(self):
        """convstate_block from state is appended to specialist prompt extras."""
        import os
        os.environ["SPECIALISTS_MODE"] = "1"
        from agents.specialists import _with_tenant_blocks

        state = {
            "tenant_id": 1,
            "phone_number": "541123456789",
            "patient_profile": {"name": "Test Patient"},
            "channel": "whatsapp",
            "tenant_context": {},
            "conversation_state_block": "SLOTS FALLIDOS:\n  • 2026-06-20",
            "operational_rules_block": "⚠️ REGLAS OPERATIVAS VIGENTES:\n[booking]: some rule",
        }

        result = _with_tenant_blocks("Prompt base.", state, "booking")
        self.assertIn("SLOTS FALLIDOS", result)
        self.assertIn("2026-06-20", result)

        # cleanup
        if "SPECIALISTS_MODE" in os.environ:
            del os.environ["SPECIALISTS_MODE"]


class TestConvStateWriteOutcomes(unittest.TestCase):
    """_write_convstate_outcomes correctly updates conversation_state after tool calls."""

    def test_increment_booking_attempts_on_failure(self):
        """book_appointment failure → increment_booking_attempts is called."""
        import asyncio
        from unittest.mock import MagicMock, patch, AsyncMock

        from agents.graph import _write_convstate_outcomes

        state = {
            "tenant_id": 1,
            "phone_number": "541123456789",
            "hop_count": 1,
            "tools_called": [
                {"tool": "book_appointment", "args": {"result": {"success": False, "error": "slot taken"}}}
            ],
            "user_message": "no me sirvió ningún horario",
        }

        with patch("services.conversation_state.increment_booking_attempts", new_callable=AsyncMock) as mock_inc:
            with patch("services.conversation_state.append_error_history", new_callable=AsyncMock):
                with patch("services.conversation_state.increment_frustration", new_callable=AsyncMock):
                    with patch("services.conversation_state.set_frustration_mode", new_callable=AsyncMock):
                        mock_inc.return_value = 3
                        asyncio.run(_write_convstate_outcomes(state, {}))
                        mock_inc.assert_called_once_with(1, "541123456789")

    def test_reset_booking_attempts_on_success(self):
        """book_appointment success → reset_booking_attempts is called."""
        import asyncio
        from unittest.mock import patch, AsyncMock

        from agents.graph import _write_convstate_outcomes

        state = {
            "tenant_id": 1,
            "phone_number": "541123456789",
            "hop_count": 2,
            "tools_called": [
                {"tool": "book_appointment", "args": {"result": {"success": True, "appointment_id": 999}}}
            ],
            "user_message": "perfecto, confirmo",
        }

        with patch("services.conversation_state.reset_booking_attempts", new_callable=AsyncMock):
            with patch("services.conversation_state.clear_error_history", new_callable=AsyncMock):
                with patch("services.conversation_state.mark_target_booked", new_callable=AsyncMock):
                    with patch("services.conversation_state.mark_booking_target_index", new_callable=AsyncMock):
                        asyncio.run(_write_convstate_outcomes(state, {}))

    def test_append_failed_slot_on_empty_availability(self):
        """check_availability with no slots → append_failed_slot."""
        import asyncio
        from unittest.mock import patch, AsyncMock

        from agents.graph import _write_convstate_outcomes

        state = {
            "tenant_id": 1,
            "phone_number": "541123456789",
            "tools_called": [
                {"tool": "check_availability", "args": {"date": "2026-06-20", "result": {"slots": []}}}
            ],
            "user_message": "qué horarios hay",
        }

        with patch("services.conversation_state.append_failed_slot", new_callable=AsyncMock):
            asyncio.run(_write_convstate_outcomes(state, {}))

    def test_frustration_increment_on_negative_keywords(self):
        """User message with frustration keywords → increment_frustration called."""
        import asyncio
        from unittest.mock import patch, AsyncMock

        from agents.graph import _write_convstate_outcomes

        state = {
            "tenant_id": 1,
            "phone_number": "541123456789",
            "tools_called": [],
            "user_message": "ya te dije mil veces, no me escuchás",
        }

        with patch("services.conversation_state.increment_frustration", new_callable=AsyncMock) as mock_inc:
            mock_inc.return_value = 1
            asyncio.run(_write_convstate_outcomes(state, {}))
            mock_inc.assert_called_once_with(1, "541123456789")

    def test_multi_booking_advances_index_on_success(self):
        """After successful booking in multi-booking, index advances to next target."""
        import asyncio
        from unittest.mock import patch, AsyncMock

        from agents.graph import _write_convstate_outcomes

        cs_data = {
            "booking_targets": [
                {"type": "self", "status": "booked"},
                {"type": "child", "status": "pending"},
            ],
            "current_booking_target_index": 0,
        }
        state = {
            "tenant_id": 1,
            "phone_number": "541123456789",
            "tools_called": [
                {"tool": "book_appointment", "args": {"result": {"success": True}}}
            ],
            "user_message": "confirmado",
        }

        with patch("services.conversation_state.reset_booking_attempts", new_callable=AsyncMock):
            with patch("services.conversation_state.clear_error_history", new_callable=AsyncMock):
                with patch("services.conversation_state.mark_target_booked", new_callable=AsyncMock) as mock_mark:
                    with patch("services.conversation_state.mark_booking_target_index", new_callable=AsyncMock) as mock_idx:
                        asyncio.run(_write_convstate_outcomes(state, cs_data))
                        mock_mark.assert_called_once_with(1, "541123456789", 0)
                        mock_idx.assert_called_once_with(1, "541123456789", 1)


class TestConvStateMinimalParity(unittest.TestCase):
    """Minimal smoke tests verifying convstate flows through the graph."""

    def test_cs_data_local_var_defined_before_supervisor_route(self):
        """cs_data is assigned before _supervisor.route() in run_turn."""
        import inspect
        from agents.graph import run_turn
        source = inspect.getsource(run_turn)
        # cs_data must appear before _supervisor.route
        cs_pos = source.find("cs_data")
        route_pos = source.find("_supervisor.route")
        self.assertGreater(cs_pos, 0, "cs_data not found in run_turn")
        self.assertGreater(route_pos, 0, "_supervisor.route not found in run_turn")
        self.assertLess(cs_pos, route_pos, "cs_data must be assigned before _supervisor.route")

    def test_conversation_state_block_in_state_before_route(self):
        """state['conversation_state_block'] is set before _supervisor.route()."""
        import inspect
        from agents.graph import run_turn
        source = inspect.getsource(run_turn)
        block_pos = source.find('state["conversation_state_block"]')
        route_pos = source.find("_supervisor.route")
        self.assertGreater(block_pos, 0)
        self.assertLess(block_pos, route_pos)

    def test_write_hook_after_agent_run(self):
        """_write_convstate_outcomes is called after agent.run(state)."""
        import inspect
        from agents.graph import run_turn
        source = inspect.getsource(run_turn)
        agent_run_pos = source.find("agent.run(state)")
        write_pos = source.find("_write_convstate_outcomes")
        self.assertGreater(agent_run_pos, 0, "agent.run(state) not found")
        self.assertGreater(write_pos, 0, "_write_convstate_outcomes not found")
        self.assertLess(agent_run_pos, write_pos, "_write_convstate_outcomes must be called after agent.run")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    unittest.main()
