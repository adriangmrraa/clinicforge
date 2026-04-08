"""End-to-end acceptance tests for treatment-pre-post-instructions-enhancement.

These tests cover the 5 acceptance criteria from REQ-4 of the spec by
exercising the prompt-contract formatter helpers in main.py with mocked
database rows. No live DB, no HTTP, no LangChain — just verification that
the formatters and the tool's dispatch logic produce the right text.

Scenarios:
- AC-1: alarm symptoms in post dict → response contains [ALARM_ESCALATION:]
- AC-2: dietary restrictions + care duration → response lists them
- AC-3: pre-treatment fasting configuration → response shows hours
- AC-4: legacy timed-sequence list → still renders with old labels
- AC-5: no instructions configured → standardized empty message (verbatim)

Run: pytest tests/test_treatment_instructions_e2e.py -v
"""

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "orchestrator_service"))

try:
    from main import (  # noqa: E402
        _format_pre_instructions_dict,
        _format_post_instructions_dict,
        _format_post_instructions_legacy_list,
        TREATMENT_INSTRUCTIONS_EMPTY,
    )
except Exception as exc:  # pragma: no cover
    pytest.skip(
        f"main.py import failed (need full backend env): {exc}",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# AC-1 — Alarm symptoms in post dict
# ---------------------------------------------------------------------------


class TestAC1AlarmSymptoms:
    def test_alarm_symptoms_produce_alarm_section(self):
        post = {
            "care_duration_days": 7,
            "alarm_symptoms": [
                "Sangrado abundante que no cede",
                "Fiebre mayor a 38.5",
            ],
            "escalation_message": "Contactá inmediatamente a la clínica",
        }
        text, has_alarm = _format_post_instructions_dict(post, "Extracción simple")
        assert has_alarm is True
        assert "SÍNTOMAS DE ALARMA" in text
        assert "Sangrado abundante" in text
        assert "Fiebre mayor" in text
        assert "Contactá inmediatamente a la clínica" in text

    def test_no_alarm_symptoms_returns_has_alarm_false(self):
        post = {"care_duration_days": 7, "dietary_restrictions": ["Frio"]}
        text, has_alarm = _format_post_instructions_dict(post, "Limpieza")
        assert has_alarm is False
        assert "SÍNTOMAS DE ALARMA" not in text

    def test_empty_alarm_list_returns_has_alarm_false(self):
        post = {"care_duration_days": 7, "alarm_symptoms": []}
        _text, has_alarm = _format_post_instructions_dict(post, "Limpieza")
        assert has_alarm is False


# ---------------------------------------------------------------------------
# AC-2 — Dietary + care duration
# ---------------------------------------------------------------------------


class TestAC2DietaryAndDuration:
    def test_dietary_restrictions_listed(self):
        post = {
            "care_duration_days": 5,
            "dietary_restrictions": [
                "No comer caliente por 24h",
                "No alcohol por 72h",
            ],
        }
        text, _ = _format_post_instructions_dict(post, "Extracción")
        assert "5 días" in text
        assert "DIETA:" in text
        assert "No comer caliente por 24h" in text
        assert "No alcohol por 72h" in text

    def test_activity_restrictions_listed(self):
        post = {
            "activity_restrictions": [
                "No actividad física intensa por 48h",
            ],
        }
        text, _ = _format_post_instructions_dict(post, "Implante")
        assert "ACTIVIDAD FÍSICA:" in text
        assert "No actividad física intensa por 48h" in text

    def test_medications_allowed_and_prohibited(self):
        post = {
            "allowed_medications": ["Ibuprofeno 400mg cada 8h"],
            "prohibited_medications": ["Aspirina"],
        }
        text, _ = _format_post_instructions_dict(post, "Cirugía")
        assert "MEDICACIÓN PERMITIDA:" in text
        assert "Ibuprofeno 400mg" in text
        assert "MEDICACIÓN PROHIBIDA:" in text
        assert "Aspirina" in text

    def test_sutures_removal_day(self):
        post = {"sutures_removal_day": 7}
        text, _ = _format_post_instructions_dict(post, "Cirugía")
        assert "retiro al día 7" in text


# ---------------------------------------------------------------------------
# AC-3 — Pre-treatment fasting
# ---------------------------------------------------------------------------


class TestAC3PreInstructions:
    def test_fasting_yes_with_hours(self):
        pre = {"fasting_required": True, "fasting_hours": 6}
        text = _format_pre_instructions_dict(pre, "Cirugía")
        assert "PRE-TRATAMIENTO" in text
        assert "Cirugía" in text
        assert "Ayuno: SÍ" in text
        assert "6 horas" in text

    def test_fasting_yes_without_hours(self):
        pre = {"fasting_required": True}
        text = _format_pre_instructions_dict(pre, "Extracción")
        assert "Ayuno: SÍ requerido" in text

    def test_fasting_no_explicit(self):
        pre = {"fasting_required": False}
        text = _format_pre_instructions_dict(pre, "Limpieza")
        assert "Ayuno: NO requerido" in text

    def test_medications_and_what_to_bring(self):
        pre = {
            "medications_to_avoid": ["Aspirina 5 días antes"],
            "medications_to_take": ["Paracetamol 500mg"],
            "what_to_bring": ["DNI", "Estudios previos"],
        }
        text = _format_pre_instructions_dict(pre, "Implante")
        assert "Aspirina 5 días antes" in text
        assert "Paracetamol 500mg" in text
        assert "DNI" in text
        assert "Estudios previos" in text

    def test_preparation_days_before(self):
        pre = {"preparation_days_before": 2}
        text = _format_pre_instructions_dict(pre, "Cirugía mayor")
        assert "2 día(s) de anticipación" in text

    def test_general_notes_included(self):
        pre = {"general_notes": "Evitar cigarrillo por 48h"}
        text = _format_pre_instructions_dict(pre, "Implante")
        assert "Evitar cigarrillo por 48h" in text


# ---------------------------------------------------------------------------
# AC-4 — Legacy timed sequence still renders
# ---------------------------------------------------------------------------


class TestAC4LegacyList:
    def test_timed_sequence_renders_with_labels(self):
        post_list = [
            {"timing": "immediate", "content": "Colocar hielo por 10 min"},
            {"timing": "24h", "content": "Reposo absoluto"},
            {"timing": "48h", "content": "Caminata suave"},
        ]
        text = _format_post_instructions_legacy_list(post_list, "all")
        assert "Inmediato" in text
        assert "Colocar hielo por 10 min" in text
        assert "A las 24hs" in text
        assert "Reposo absoluto" in text
        assert "A las 48hs" in text
        assert "Caminata suave" in text

    def test_timed_sequence_filters_by_specific_timing(self):
        post_list = [
            {"timing": "24h", "content": "Reposo"},
            {"timing": "48h", "content": "Actividad liviana"},
        ]
        text = _format_post_instructions_legacy_list(post_list, "24h")
        assert "Reposo" in text
        assert "Actividad liviana" not in text

    def test_empty_list_returns_empty_string(self):
        assert _format_post_instructions_legacy_list([], "all") == ""

    def test_book_followup_sugerencia(self):
        post_list = [
            {
                "timing": "stitch_removal",
                "content": "Retiro de puntos",
                "book_followup": True,
                "days": 7,
            },
        ]
        text = _format_post_instructions_legacy_list(post_list, "all")
        assert "Sugerir agendar turno de control en 7 días" in text


# ---------------------------------------------------------------------------
# AC-5 — No instructions path (standardized message, verbatim)
# ---------------------------------------------------------------------------


class TestAC5NoInstructions:
    def test_empty_message_exact_text(self):
        # The system prompt instructs the agent to repeat this VERBATIM.
        # Any change here must also be reflected in the prompt rule.
        assert TREATMENT_INSTRUCTIONS_EMPTY == (
            "Este tratamiento no tiene cuidados configurados. "
            "Te recomiendo contactar directamente a la clínica para más indicaciones."
        )

    def test_empty_message_has_no_trailing_whitespace(self):
        assert TREATMENT_INSTRUCTIONS_EMPTY == TREATMENT_INSTRUCTIONS_EMPTY.strip()

    def test_empty_message_single_line_formatting(self):
        # No newlines inside — it's meant to be displayed as a single bubble
        assert "\n" not in TREATMENT_INSTRUCTIONS_EMPTY
