"""E2E wiring verification — clinic-special-conditions (Phase 5).

Verifica el contrato end-to-end: build_system_prompt recibe tenant_data
pre-formateado vía _format_special_conditions y el prompt final contiene
toda la información que el LLM necesita para los 5 acceptance scenarios
(SC-1..SC-5) + no contiene lenguaje prohibido.

Complementa los unit tests en test_clinic_special_conditions.py. Acá nos
aseguramos de que el pipeline completo (formatter → prompt) está intacto.

Run: pytest tests/test_clinic_special_conditions_e2e.py -v
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


def _baseline() -> dict:
    return {
        "clinic_name": "Clínica Delgado Test",
        "current_time": "2026-04-08 10:00",
        "response_language": "es",
    }


def _prompt_with_conditions(tenant_data: dict, treatment_map: dict | None = None) -> str:
    """Pipeline completo: formatter → build_system_prompt."""
    block = _format_special_conditions(tenant_data, treatment_name_map=treatment_map)
    return build_system_prompt(**_baseline(), special_conditions_block=block)


class TestE2EPipeline:
    def test_sc1_pregnant_restricted_xray_reaches_prompt(self):
        prompt = _prompt_with_conditions(
            {
                "accepts_pregnant_patients": True,
                "pregnancy_restricted_treatments": ["xray_panoramic"],
                "pregnancy_notes": "Se pospone post primer trimestre",
            },
            treatment_map={"xray_panoramic": "Radiografía panorámica"},
        )
        assert "## CONDICIONES ESPECIALES" in prompt
        assert "Radiografía panorámica" in prompt
        assert "Se pospone post primer trimestre" in prompt

    def test_sc2_min_age_reaches_prompt(self):
        prompt = _prompt_with_conditions({"min_pediatric_age_years": 6})
        assert "desde los 6 años" in prompt

    def test_sc3_diabetes_clearance_reaches_prompt(self):
        prompt = _prompt_with_conditions(
            {
                "high_risk_protocols": {
                    "diabetes": {
                        "requires_medical_clearance": True,
                        "notes": "Pedimos HbA1c reciente",
                    }
                }
            }
        )
        assert "diabetes" in prompt
        assert "clearance médico" in prompt
        assert "Pedimos HbA1c reciente" in prompt
        # Triage cross-reference debe estar cuando hay high_risk
        assert "POST-TRIAGE" in prompt

    def test_sc4_anticoagulants_pre_call_reaches_prompt(self):
        prompt = _prompt_with_conditions(
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
        assert "llamada del equipo antes del turno" in prompt
        assert "Requiere autorización del hematólogo" in prompt

    def test_sc5_anamnesis_gate_reaches_prompt(self):
        prompt = _prompt_with_conditions(
            {
                "requires_anamnesis_before_booking": True,
                "high_risk_protocols": {
                    "immunosuppression": {"requires_medical_clearance": True}
                },
            }
        )
        assert "ANAMNESIS GATE (ACTIVO)" in prompt
        assert "EXCEPCIÓN" in prompt

    def test_backward_compat_no_conditions_zero_impact(self):
        """Tenant sin configuración de condiciones → prompt no cambia."""
        prompt_with = _prompt_with_conditions({})
        prompt_baseline = build_system_prompt(**_baseline())
        assert "## CONDICIONES ESPECIALES" not in prompt_with
        # Idéntico al baseline — zero footprint
        assert prompt_with == prompt_baseline


class TestE2EGuardrails:
    """Guardrails críticos: el pipeline NO debe generar lenguaje de consejo médico.

    Usamos regex contextuales (assert_no_medical_advice) en vez de substrings
    simples. La REGLA DE ORO que el formatter emite contiene palabras como
    "es peligroso" dentro de comillas para instruir al LLM — un substring check
    daría falso positivo sobre el propio texto de seguridad del sistema.
    """

    def test_no_medical_advice_in_full_pipeline(self):
        prompt = _prompt_with_conditions(
            {
                "accepts_pregnant_patients": True,
                "pregnancy_restricted_treatments": ["xray_panoramic"],
                "pregnancy_notes": "Coordinamos con tu obstetra.",
                "accepts_pediatric": True,
                "min_pediatric_age_years": 6,
                "high_risk_protocols": {
                    "diabetes": {
                        "requires_medical_clearance": True,
                        "notes": "Coordinamos con médico de cabecera.",
                    },
                    "anticoagulants": {
                        "requires_pre_appointment_call": True,
                        "notes": "Equipo te llama antes del turno.",
                    },
                },
                "requires_anamnesis_before_booking": True,
            },
            treatment_map={"xray_panoramic": "Radiografía panorámica"},
        )
        # El prompt completo no debe contener patrones de consejo médico real
        # generados por el formatter (las notas verbatim son responsabilidad
        # del clinician — acá pusimos notas neutras a propósito)
        assert_no_medical_advice(prompt, context="full pipeline")
        # Y debe contener la REGLA DE ORO (anti-consejo médico)
        assert "NUNCA dar consejo médico" in prompt
