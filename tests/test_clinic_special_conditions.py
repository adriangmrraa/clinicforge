"""Unit + scenario tests — clinic-special-conditions (Phases 3 + 5).

Cubre:
- Phase 3: _format_special_conditions unit tests + build_system_prompt wiring
- Phase 5: 5 acceptance scenarios (SC-1..SC-5) + anti-medical-advice guardrails

No requieren DB ni LLM. Son tests sobre funciones puras y sobre el contrato
del prompt inyectado al LLM.

Run: pytest tests/test_clinic_special_conditions.py -v
"""

import sys
from pathlib import Path

import pytest

_ORCH = (
    Path(__file__).resolve().parent.parent / "orchestrator_service"
)
if str(_ORCH) not in sys.path:
    sys.path.insert(0, str(_ORCH))

# Helpers must be importable regardless of pytest working directory
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR.parent))

from tests.helpers.medical_guardrails import assert_no_medical_advice  # noqa: E402

from main import _format_special_conditions, build_system_prompt  # noqa: E402


# --- Phase 3: formatter unit tests -------------------------------------------


class TestFormatSpecialConditions:
    def test_empty_returns_empty_string(self):
        assert _format_special_conditions({}) == ""

    def test_all_defaults_returns_empty_string(self):
        assert (
            _format_special_conditions(
                {
                    "accepts_pregnant_patients": True,
                    "pregnancy_restricted_treatments": [],
                    "pregnancy_notes": "",
                    "accepts_pediatric": True,
                    "min_pediatric_age_years": None,
                    "pediatric_notes": "",
                    "high_risk_protocols": {},
                    "requires_anamnesis_before_booking": False,
                }
            )
            == ""
        )

    def test_accepts_pregnant_false(self):
        out = _format_special_conditions({"accepts_pregnant_patients": False})
        assert "no se atienden pacientes embarazadas" in out
        assert "## CONDICIONES ESPECIALES" in out

    def test_pregnancy_notes_verbatim(self):
        out = _format_special_conditions(
            {"pregnancy_notes": "Consultar con médico"}
        )
        assert "Consultar con médico" in out

    def test_pregnancy_restricted_resolves_code(self):
        out = _format_special_conditions(
            {"pregnancy_restricted_treatments": ["xray_panoramic"]},
            treatment_name_map={"xray_panoramic": "Radiografía panorámica"},
        )
        assert "Radiografía panorámica" in out

    def test_pregnancy_restricted_fallback_code(self):
        out = _format_special_conditions(
            {"pregnancy_restricted_treatments": ["xray_panoramic"]},
        )
        assert "xray_panoramic" in out

    def test_min_pediatric_age(self):
        out = _format_special_conditions({"min_pediatric_age_years": 6})
        assert "desde los 6 años" in out

    def test_accepts_pediatric_false(self):
        out = _format_special_conditions({"accepts_pediatric": False})
        assert "no se atienden pacientes pediátricos" in out

    def test_high_risk_clearance(self):
        out = _format_special_conditions(
            {
                "high_risk_protocols": {
                    "diabetes": {
                        "requires_medical_clearance": True,
                        "notes": "Pedir HbA1c",
                    }
                }
            }
        )
        assert "diabetes" in out
        assert "clearance médico" in out
        assert "Pedir HbA1c" in out

    def test_high_risk_pre_call(self):
        out = _format_special_conditions(
            {
                "high_risk_protocols": {
                    "anticoagulants": {
                        "requires_pre_appointment_call": True,
                    }
                }
            }
        )
        assert "llamada del equipo antes del turno" in out

    def test_anamnesis_gate_active(self):
        out = _format_special_conditions(
            {"requires_anamnesis_before_booking": True}
        )
        assert "ANAMNESIS GATE (ACTIVO)" in out
        assert "EXCEPCIÓN" in out

    def test_anamnesis_gate_inactive(self):
        out = _format_special_conditions({"accepts_pregnant_patients": False})
        # Config de embarazo activa, pero gate off → no debe aparecer ANAMNESIS GATE
        assert "ANAMNESIS GATE" not in out

    def test_regla_de_oro_always_present_when_configured(self):
        out = _format_special_conditions({"accepts_pregnant_patients": False})
        assert "NUNCA dar consejo médico" in out

    def test_fallback_rule_always_present_when_configured(self):
        out = _format_special_conditions({"accepts_pregnant_patients": False})
        assert "condición NO listada" in out

    def test_jsonb_as_string_defensive_parse_restricted_list(self):
        """asyncpg edge case: pregnancy_restricted_treatments viene como string JSON."""
        out = _format_special_conditions(
            {"pregnancy_restricted_treatments": '["xray_panoramic"]'}
        )
        assert "xray_panoramic" in out

    def test_jsonb_as_string_defensive_parse_high_risk(self):
        """asyncpg edge case: high_risk_protocols viene como string JSON."""
        out = _format_special_conditions(
            {
                "high_risk_protocols": '{"diabetes":{"requires_medical_clearance":true}}'
            }
        )
        assert "diabetes" in out
        assert "clearance médico" in out


# --- Phase 3: triage cross-reference (task 3.6 / 3.7) -----------------------


class TestTriageCrossReference:
    def test_triage_instruction_present_when_high_risk_configured(self):
        out = _format_special_conditions(
            {
                "high_risk_protocols": {
                    "diabetes": {"requires_medical_clearance": True}
                }
            }
        )
        assert "triage_urgency" in out
        assert "POST-TRIAGE" in out

    def test_triage_instruction_absent_when_no_high_risk(self):
        out = _format_special_conditions({"accepts_pregnant_patients": False})
        assert "POST-TRIAGE" not in out


# --- Phase 3: build_system_prompt wiring (tasks 3.3 / 3.4) -------------------


class TestBuildSystemPromptSpecialConditions:
    def _base_kwargs(self) -> dict:
        return {
            "clinic_name": "Test Clinic",
            "current_time": "2026-04-08 10:00",
            "response_language": "es",
        }

    def test_special_conditions_injected_when_present(self):
        prompt = build_system_prompt(
            **self._base_kwargs(),
            special_conditions_block="TEST BLOCK ESPECIALES",
        )
        assert "TEST BLOCK ESPECIALES" in prompt

    def test_special_conditions_absent_when_empty(self):
        prompt = build_system_prompt(
            **self._base_kwargs(),
            special_conditions_block="",
        )
        assert "## CONDICIONES ESPECIALES" not in prompt

    def test_backward_compatible_no_param(self):
        # Llamada sin el kwarg nuevo → no debe romper ni mostrar bloque
        prompt = build_system_prompt(**self._base_kwargs())
        assert "## CONDICIONES ESPECIALES" not in prompt


# --- Phase 5: acceptance scenarios ------------------------------------------


class TestAcceptanceScenarios:
    def test_sc1_pregnant_restricted_treatment(self):
        """SC-1: Pregnant patient + restricted treatment."""
        out = _format_special_conditions(
            {
                "accepts_pregnant_patients": True,
                "pregnancy_restricted_treatments": ["xray_panoramic"],
                "pregnancy_notes": "Se pospone post primer trimestre",
            },
            treatment_name_map={"xray_panoramic": "Radiografía panorámica"},
        )
        assert "Radiografía panorámica" in out
        assert "Se pospone post primer trimestre" in out
        # Anti-medical-advice: el formatter no debe generar consejo médico real.
        # Usamos regex contextuales — "peligroso" puede aparecer legítimamente
        # dentro de la REGLA DE ORO del formatter ("NUNCA decir... 'es peligroso'").
        assert_no_medical_advice(out, context="SC-1")

    def test_sc2_min_age_6(self):
        """SC-2a: Pediatric minimum age 6."""
        out = _format_special_conditions({"min_pediatric_age_years": 6})
        assert "desde los 6 años" in out

    def test_sc2_no_pediatric(self):
        """SC-2b: Clinic doesn't accept pediatric."""
        out = _format_special_conditions({"accepts_pediatric": False})
        assert "no se atienden pacientes pediátricos" in out

    def test_sc3_diabetes_clearance(self):
        """SC-3: Diabetic patient needs clearance."""
        out = _format_special_conditions(
            {
                "high_risk_protocols": {
                    "diabetes": {
                        "requires_medical_clearance": True,
                        "notes": "Pedimos HbA1c reciente",
                    }
                }
            }
        )
        assert "diabetes" in out
        assert "clearance médico" in out
        assert "Pedimos HbA1c reciente" in out
        # Anti-medical-advice: usamos regex contextuales para evitar falsos
        # positivos con la REGLA DE ORO del formatter.
        assert_no_medical_advice(out, context="SC-3")

    def test_sc4_anticoagulants_pre_call(self):
        """SC-4: Anticoagulated patient needs pre-appointment call."""
        out = _format_special_conditions(
            {
                "high_risk_protocols": {
                    "anticoagulants": {
                        "requires_medical_clearance": True,
                        "requires_pre_appointment_call": True,
                        "notes": "Requiere autorización del hematólogo",
                    }
                }
            }
        )
        assert "llamada del equipo antes del turno" in out
        assert "Requiere autorización del hematólogo" in out
        # No debe haber consejo sobre medicación
        assert "suspender la medicación" not in out.lower()

    def test_sc5_anamnesis_gate_active(self):
        """SC-5: Anamnesis gate + high-risk."""
        out = _format_special_conditions(
            {
                "requires_anamnesis_before_booking": True,
                "high_risk_protocols": {
                    "immunosuppression": {"requires_medical_clearance": True}
                },
            }
        )
        assert "ANAMNESIS GATE (ACTIVO)" in out
        assert "EXCEPCIÓN" in out

    def test_sc5_gate_inactive_by_default(self):
        out = _format_special_conditions(
            {
                "high_risk_protocols": {
                    "immunosuppression": {"requires_medical_clearance": True}
                }
            }
        )
        assert "ANAMNESIS GATE" not in out


# --- Phase 5: anti-medical-advice guardrails --------------------------------


class TestAntiMedicalAdviceGuardrails:
    """El texto GENERADO por el formatter NO debe contener consejo médico real.

    IMPORTANTE: las notas del clinician (pregnancy_notes, high_risk notes)
    se pasan verbatim — acá sólo validamos que el formatter no agregue por su
    cuenta lenguaje de consejo médico (dosificaciones, prescripciones,
    diagnósticos absolutos).

    Usamos regex contextuales en vez de substrings simples porque palabras
    como "peligroso" aparecen legítimamente dentro de la REGLA DE ORO que el
    formatter emite ("NUNCA decir que algo 'es peligroso'") — un substring
    check daría falso positivo sobre el propio texto de seguridad.
    """

    def test_no_dangerous_language_pregnancy_restricted(self):
        # Pasamos notas NEUTRAS para aislar el output generado por el formatter
        out = _format_special_conditions(
            {
                "pregnancy_restricted_treatments": ["xray_panoramic"],
                "pregnancy_notes": "Se posterga el procedimiento.",
            }
        )
        assert_no_medical_advice(out, context="pregnancy restricted")

    def test_no_dangerous_language_high_risk(self):
        out = _format_special_conditions(
            {
                "high_risk_protocols": {
                    "diabetes": {
                        "requires_medical_clearance": True,
                        "notes": "Coordinamos con su médico de cabecera.",
                    }
                }
            }
        )
        assert_no_medical_advice(out, context="high risk diabetes")

    def test_no_dangerous_language_anamnesis_gate(self):
        out = _format_special_conditions(
            {"requires_anamnesis_before_booking": True}
        )
        assert_no_medical_advice(out, context="anamnesis gate")

    def test_no_dangerous_language_pediatric(self):
        out = _format_special_conditions(
            {
                "accepts_pediatric": False,
                "pediatric_notes": "Coordinar derivación a pediatra odontológico.",
            }
        )
        assert_no_medical_advice(out, context="pediatric")
