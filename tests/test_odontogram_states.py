"""Tests para shared/odontogram_states.py — Catálogo de 42 estados"""
import pytest
from shared.odontogram_states import (
    ODONTOGRAM_STATES,
    ODONTOGRAM_STATES_BY_ID,
    PREEXISTENTE_STATES,
    LESION_STATES,
    VALID_STATE_IDS,
    LEGACY_STATE_MAP,
    get_state_by_id,
    get_states_by_category,
    normalize_legacy_state_id,
    is_valid_state,
    resolve_print_color,
)


class TestCatalogCompleteness:
    """Verificar que el catálogo tiene todos los estados esperados"""

    def test_total_states_is_42(self):
        assert len(ODONTOGRAM_STATES) == 42

    def test_preexistente_count(self):
        assert len(PREEXISTENTE_STATES) == 25

    def test_lesion_count(self):
        assert len(LESION_STATES) == 17

    def test_all_ids_unique(self):
        ids = [s.id for s in ODONTOGRAM_STATES]
        assert len(ids) == len(set(ids))

    def test_all_symbols_present(self):
        for state in ODONTOGRAM_STATES:
            assert len(state.symbol) >= 1
            assert len(state.symbol) <= 3

    def test_all_colors_valid_hex(self):
        import re
        hex_pattern = re.compile(r'^#[0-9a-fA-F]{6}$')
        for state in ODONTOGRAM_STATES:
            assert hex_pattern.match(state.default_color), f"{state.id}: invalid default_color {state.default_color}"
            assert hex_pattern.match(state.print_fill), f"{state.id}: invalid print_fill {state.print_fill}"
            assert hex_pattern.match(state.print_stroke), f"{state.id}: invalid print_stroke {state.print_stroke}"

    def test_all_label_keys_follow_convention(self):
        for state in ODONTOGRAM_STATES:
            assert state.label_key == f"odontogram.states.{state.id}"

    def test_categories_are_valid(self):
        for state in ODONTOGRAM_STATES:
            assert state.category in ("preexistente", "lesion")

    def test_healthy_is_first(self):
        assert ODONTOGRAM_STATES[0].id == "healthy"


class TestLookups:
    """Tests para funciones de lookup"""

    def test_get_state_by_id_found(self):
        state = get_state_by_id("caries")
        assert state is not None
        assert state.id == "caries"
        assert state.category == "lesion"

    def test_get_state_by_id_not_found(self):
        assert get_state_by_id("nonexistent") is None

    def test_get_states_by_category_preexistente(self):
        states = get_states_by_category("preexistente")
        assert len(states) == 25
        assert all(s.category == "preexistente" for s in states)

    def test_get_states_by_category_lesion(self):
        states = get_states_by_category("lesion")
        assert len(states) == 17
        assert all(s.category == "lesion" for s in states)

    def test_is_valid_state_true(self):
        assert is_valid_state("caries") is True
        assert is_valid_state("healthy") is True
        assert is_valid_state("implante") is True

    def test_is_valid_state_false(self):
        assert is_valid_state("nonexistent") is False
        assert is_valid_state("") is False


class TestLegacyMapping:
    """Tests para retrocompatibilidad"""

    def test_all_10_v2_states_mapped(self):
        v2_states = ["healthy", "caries", "restoration", "root_canal", "crown",
                     "implant", "prosthesis", "extraction", "missing", "treatment_planned"]
        for old in v2_states:
            new = normalize_legacy_state_id(old)
            assert is_valid_state(new), f"Legacy state '{old}' maps to invalid '{new}'"

    def test_unknown_state_passes_through(self):
        assert normalize_legacy_state_id("some_new_state") == "some_new_state"

    def test_specific_mappings(self):
        assert normalize_legacy_state_id("restoration") == "restauracion_resina"
        assert normalize_legacy_state_id("crown") == "corona_porcelana"
        assert normalize_legacy_state_id("extraction") == "indicacion_extraccion"
        assert normalize_legacy_state_id("treated") == "restauracion_resina"


class TestResolvePrintColor:
    """Tests para resolve_print_color"""

    def test_known_state(self):
        result = resolve_print_color("caries")
        assert "fill" in result
        assert "stroke" in result
        assert result["stroke"] == "#dc2626"

    def test_custom_color_override(self):
        result = resolve_print_color("caries", "#ff0000")
        assert result["stroke"] == "#ff0000"
        assert result["fill"] == "#ff000033"

    def test_unknown_state_falls_back_to_healthy(self):
        result = resolve_print_color("nonexistent_state")
        healthy = get_state_by_id("healthy")
        assert result["fill"] == healthy.print_fill
        assert result["stroke"] == healthy.print_stroke
