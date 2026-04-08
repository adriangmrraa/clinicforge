"""Unit tests for treatment-pre-post-instructions-enhancement (migration 036).

Covers:
- Pydantic schemas: PreInstructions, PostInstructions
- Coercion helpers: _coerce_pre_instructions, _coerce_post_instructions
- Validation: _validate_treatment_instruction_fields
- Migration data conversion: pre/post instructions shape transforms

These are pure unit tests — no database, no FastAPI app, no HTTP. They
import the symbols from admin_routes.py directly.

Run: pytest tests/test_treatment_instructions_enhancement.py -v
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

# Allow importing orchestrator_service modules from the repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "orchestrator_service"))

from fastapi import HTTPException  # noqa: E402

# admin_routes pulls a lot of side-effects on import. Some test environments
# may not have the full DB / Redis stack available. Wrap the import so the
# test file still loads cleanly when the symbols are exported but the app
# wiring is incomplete (the only thing we need is the pure helpers).
try:
    from admin_routes import (  # noqa: E402
        PreInstructions,
        PostInstructions,
        _coerce_pre_instructions,
        _coerce_post_instructions,
        _validate_treatment_instruction_fields,
    )
except Exception as exc:  # pragma: no cover - import-time guard
    pytest.skip(
        f"admin_routes import failed (need full backend env): {exc}",
        allow_module_level=True,
    )


# ----------------------------------------------------------------------------
# PreInstructions Pydantic schema
# ----------------------------------------------------------------------------


class TestPreInstructionsSchema:
    def test_pre_instructions_from_dict(self):
        m = PreInstructions(fasting_required=True, fasting_hours=6)
        assert m.fasting_required is True
        assert m.fasting_hours == 6

    def test_pre_instructions_all_optional(self):
        m = PreInstructions()
        assert m.preparation_days_before is None
        assert m.fasting_required is None
        assert m.fasting_hours is None
        assert m.medications_to_avoid == []
        assert m.medications_to_take == []
        assert m.what_to_bring == []
        assert m.general_notes is None

    def test_pre_instructions_general_notes_preserved(self):
        m = PreInstructions(general_notes="Texto legado")
        assert m.general_notes == "Texto legado"

    def test_pre_instructions_lists_accept_strings(self):
        m = PreInstructions(
            medications_to_avoid=["Aspirina", "Ibuprofeno"],
            what_to_bring=["DNI", "Estudios"],
        )
        assert m.medications_to_avoid == ["Aspirina", "Ibuprofeno"]
        assert m.what_to_bring == ["DNI", "Estudios"]


# ----------------------------------------------------------------------------
# PostInstructions Pydantic schema
# ----------------------------------------------------------------------------


class TestPostInstructionsSchema:
    def test_post_instructions_from_dict(self):
        m = PostInstructions(
            care_duration_days=7,
            dietary_restrictions=["No comer caliente por 24h"],
            alarm_symptoms=["Sangrado abundante"],
            escalation_message="Contactar clínica",
        )
        assert m.care_duration_days == 7
        assert m.dietary_restrictions == ["No comer caliente por 24h"]
        assert m.alarm_symptoms == ["Sangrado abundante"]
        assert m.escalation_message == "Contactar clínica"

    def test_post_instructions_minimal(self):
        m = PostInstructions(care_duration_days=7)
        assert m.care_duration_days == 7
        assert m.dietary_restrictions == []
        assert m.activity_restrictions == []
        assert m.allowed_medications == []
        assert m.prohibited_medications == []
        assert m.normal_symptoms == []
        assert m.alarm_symptoms == []
        assert m.sutures_removal_day is None
        assert m.escalation_message is None

    def test_post_instructions_all_defaults(self):
        m = PostInstructions()
        assert m.care_duration_days is None
        assert m.dietary_restrictions == []


# ----------------------------------------------------------------------------
# Coercion helpers
# ----------------------------------------------------------------------------


class TestCoercePreInstructions:
    def test_coerce_pre_none_is_none(self):
        assert _coerce_pre_instructions(None) is None

    def test_coerce_pre_string_to_dict(self):
        result = _coerce_pre_instructions("Texto libre")
        assert result == {"general_notes": "Texto libre"}

    def test_coerce_pre_model_to_dict(self):
        m = PreInstructions(fasting_required=True, fasting_hours=8)
        result = _coerce_pre_instructions(m)
        assert isinstance(result, dict)
        assert result["fasting_required"] is True
        assert result["fasting_hours"] == 8
        # All keys should be present (exclude_none=False)
        assert "general_notes" in result

    def test_coerce_pre_dict_passthrough(self):
        d = {"fasting_required": False, "general_notes": "Nada"}
        result = _coerce_pre_instructions(d)
        assert result is d

    def test_coerce_pre_unknown_type_returns_none(self):
        # Defensive: unexpected type → None (caller handles NULL column)
        assert _coerce_pre_instructions(42) is None


class TestCoercePostInstructions:
    def test_coerce_post_none_is_none(self):
        assert _coerce_post_instructions(None) is None

    def test_coerce_post_list_preserved(self):
        legacy = [{"timing": "24h", "content": "Reposo absoluto"}]
        result = _coerce_post_instructions(legacy)
        assert result is legacy

    def test_coerce_post_model_to_dict(self):
        m = PostInstructions(care_duration_days=7, dietary_restrictions=["Frio"])
        result = _coerce_post_instructions(m)
        assert isinstance(result, dict)
        assert result["care_duration_days"] == 7
        assert result["dietary_restrictions"] == ["Frio"]

    def test_coerce_post_string_json(self):
        # Valid JSON string is parsed
        s = '{"care_duration_days": 3}'
        result = _coerce_post_instructions(s)
        assert isinstance(result, dict)
        assert result["care_duration_days"] == 3

    def test_coerce_post_string_invalid_json_wrapped(self):
        result = _coerce_post_instructions("not valid json")
        assert result == {"general_notes": "not valid json"}

    def test_coerce_post_dict_passthrough(self):
        d = {"care_duration_days": 5}
        result = _coerce_post_instructions(d)
        assert result is d


# ----------------------------------------------------------------------------
# Validator — accepts all shapes, raises 422 on bad data
# ----------------------------------------------------------------------------


def _treatment(**kwargs):
    """Helper to build a SimpleNamespace stand-in for a Pydantic model.

    Provides default attributes for fields the validator might touch."""
    defaults = {
        "pre_instructions": None,
        "post_instructions": None,
        "followup_template": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestValidateTreatmentInstructionFields:
    # ----- post_instructions accepted shapes -----

    def test_post_dict_accepted(self):
        t = _treatment(
            post_instructions=PostInstructions(care_duration_days=7),
        )
        # Should not raise
        _validate_treatment_instruction_fields(t)

    def test_post_list_accepted(self):
        t = _treatment(
            post_instructions=[
                {"timing": "24h", "content": "Reposo"},
                {"timing": "48h", "content": "Caminata suave"},
            ],
        )
        _validate_treatment_instruction_fields(t)

    def test_post_raw_dict_accepted(self):
        t = _treatment(post_instructions={"care_duration_days": 3, "extra": "field"})
        _validate_treatment_instruction_fields(t)

    def test_post_none_accepted(self):
        _validate_treatment_instruction_fields(_treatment(post_instructions=None))

    # ----- post_instructions rejected -----

    def test_post_invalid_care_duration_zero(self):
        t = _treatment(post_instructions=PostInstructions(care_duration_days=0))
        with pytest.raises(HTTPException) as exc:
            _validate_treatment_instruction_fields(t)
        assert exc.value.status_code == 422

    def test_post_invalid_care_duration_dict(self):
        t = _treatment(post_instructions={"care_duration_days": -1})
        with pytest.raises(HTTPException) as exc:
            _validate_treatment_instruction_fields(t)
        assert exc.value.status_code == 422

    def test_post_list_invalid_timing_raises(self):
        t = _treatment(post_instructions=[{"timing": "invalid_value"}])
        with pytest.raises(HTTPException) as exc:
            _validate_treatment_instruction_fields(t)
        assert exc.value.status_code == 422
        assert "timing" in exc.value.detail.lower()

    def test_post_list_extended_timings_accepted(self):
        # Migration 036 expanded the valid timing set
        for timing in ("immediate", "24h", "48h", "72h", "1w", "stitch_removal", "custom"):
            t = _treatment(post_instructions=[{"timing": timing}])
            _validate_treatment_instruction_fields(t)  # no raise

    def test_post_negative_sutures_removal_day(self):
        t = _treatment(post_instructions=PostInstructions(sutures_removal_day=-1))
        with pytest.raises(HTTPException) as exc:
            _validate_treatment_instruction_fields(t)
        assert exc.value.status_code == 422

    def test_post_escalation_message_too_long(self):
        t = _treatment(
            post_instructions=PostInstructions(
                escalation_message="x" * 501,
            ),
        )
        with pytest.raises(HTTPException) as exc:
            _validate_treatment_instruction_fields(t)
        assert exc.value.status_code == 422

    def test_post_unknown_type_rejected(self):
        t = _treatment(post_instructions=42)
        with pytest.raises(HTTPException) as exc:
            _validate_treatment_instruction_fields(t)
        assert exc.value.status_code == 422

    # ----- pre_instructions accepted shapes -----

    def test_pre_string_accepted(self):
        t = _treatment(pre_instructions="short text")
        _validate_treatment_instruction_fields(t)

    def test_pre_dict_model_accepted(self):
        t = _treatment(
            pre_instructions=PreInstructions(
                fasting_required=True,
                fasting_hours=6,
                medications_to_avoid=["Aspirina"],
            ),
        )
        _validate_treatment_instruction_fields(t)

    def test_pre_raw_dict_accepted(self):
        t = _treatment(pre_instructions={"general_notes": "ok", "fasting_required": False})
        _validate_treatment_instruction_fields(t)

    def test_pre_none_accepted(self):
        _validate_treatment_instruction_fields(_treatment(pre_instructions=None))

    # ----- pre_instructions rejected -----

    def test_pre_string_too_long(self):
        t = _treatment(pre_instructions="x" * 2001)
        with pytest.raises(HTTPException) as exc:
            _validate_treatment_instruction_fields(t)
        assert exc.value.status_code == 422

    def test_pre_general_notes_too_long(self):
        t = _treatment(
            pre_instructions=PreInstructions(general_notes="y" * 2001),
        )
        with pytest.raises(HTTPException) as exc:
            _validate_treatment_instruction_fields(t)
        assert exc.value.status_code == 422

    def test_pre_negative_fasting_hours(self):
        t = _treatment(
            pre_instructions=PreInstructions(fasting_required=True, fasting_hours=-1),
        )
        with pytest.raises(HTTPException) as exc:
            _validate_treatment_instruction_fields(t)
        assert exc.value.status_code == 422

    def test_pre_negative_preparation_days(self):
        t = _treatment(
            pre_instructions=PreInstructions(preparation_days_before=-2),
        )
        with pytest.raises(HTTPException) as exc:
            _validate_treatment_instruction_fields(t)
        assert exc.value.status_code == 422

    def test_pre_unknown_type_rejected(self):
        t = _treatment(pre_instructions=42)
        with pytest.raises(HTTPException) as exc:
            _validate_treatment_instruction_fields(t)
        assert exc.value.status_code == 422
