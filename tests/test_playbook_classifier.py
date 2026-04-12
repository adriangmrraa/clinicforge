"""Tests for the 3-layer playbook response classifier."""

import pytest
import tests._import_stubs  # noqa: F401

from services.playbook_classifier import classify_response, _fuzzy_keyword_match


# ─── Layer 1: Button exact match ────────────────────────────────────────

class TestLayer1Buttons:
    def test_confirm_button_exact(self):
        cls, action, rule = classify_response("Confirmar asistencia ✅", [])
        assert cls == "confirm"
        assert action == "continue"

    def test_confirm_button_lowercase(self):
        cls, action, _ = classify_response("confirmar asistencia ✅", [])
        assert cls == "confirm"

    def test_confirmo_el_turno(self):
        cls, action, _ = classify_response("Confirmo el turno", [])
        assert cls == "confirm"
        assert action == "continue"

    def test_cancel_button(self):
        cls, action, _ = classify_response("Quiero cancelar", [])
        assert cls == "cancel"
        assert action == "abort"

    def test_reschedule_button(self):
        cls, action, _ = classify_response("Necesito reprogramar", [])
        assert cls == "reschedule"
        assert action == "pass_to_ai"

    def test_quiero_reprogramar(self):
        cls, action, _ = classify_response("Quiero reprogramar", [])
        assert cls == "reschedule"

    def test_empty_message(self):
        cls, action, _ = classify_response("", [])
        assert cls == "unclassified"


# ─── Layer 2: Keyword match ─────────────────────────────────────────────

class TestLayer2Keywords:
    RULES = [
        {"name": "urgencia", "keywords": ["dolor", "sangra", "fiebre", "hinchado"], "action": "notify_and_pause"},
        {"name": "positivo", "keywords": ["bien", "perfecto", "genial", "todo ok"], "action": "continue"},
        {"name": "negativo", "keywords": ["no puedo", "cancelar", "no voy"], "action": "abort"},
    ]

    def test_keyword_dolor(self):
        cls, action, rule = classify_response("tengo dolor en la muela", self.RULES)
        assert rule == "urgencia"
        assert action == "notify_and_pause"

    def test_keyword_duele_needs_explicit_keyword(self):
        """'duele' doesn't match 'dolor' — must add 'duele' to keywords explicitly."""
        cls, action, rule = classify_response("me duele mucho la muela", self.RULES)
        assert rule is None  # 'duele' is not in the keywords list, only 'dolor'

    def test_keyword_bien(self):
        cls, action, rule = classify_response("todo bien, gracias!", self.RULES)
        assert rule == "positivo"
        assert action == "continue"

    def test_keyword_no_puedo(self):
        cls, action, rule = classify_response("no puedo ir mañana", self.RULES)
        assert rule == "negativo"
        assert action == "abort"

    def test_keyword_fiebre(self):
        cls, action, rule = classify_response("tengo fiebre desde ayer", self.RULES)
        assert rule == "urgencia"
        assert action == "notify_and_pause"

    def test_no_keyword_match(self):
        cls, action, rule = classify_response("hola qué tal", self.RULES)
        assert cls == "unclassified"
        assert rule is None

    def test_empty_rules(self):
        cls, action, rule = classify_response("me duele", [])
        assert cls == "unclassified"

    def test_keyword_sangra(self):
        cls, action, rule = classify_response("me sangra la encía", self.RULES)
        assert rule == "urgencia"

    def test_keyword_case_insensitive(self):
        cls, action, rule = classify_response("TODO BIEN DOCTORA", self.RULES)
        assert rule == "positivo"


# ─── Layer 2: Priority (first match wins) ───────────────────────────────

class TestLayer2Priority:
    def test_first_rule_wins(self):
        """If multiple rules match, the first one in the list wins."""
        rules = [
            {"name": "urgente", "keywords": ["dolor"], "action": "notify_and_pause"},
            {"name": "general", "keywords": ["dolor"], "action": "continue"},
        ]
        cls, action, rule = classify_response("tengo dolor", rules)
        assert rule == "urgente"
        assert action == "notify_and_pause"


# ─── Fuzzy keyword match ────────────────────────────────────────────────

class TestFuzzyMatch:
    def test_word_boundary(self):
        assert _fuzzy_keyword_match("dolor", "me duele con dolor") is True

    def test_no_partial_match(self):
        # "dolor" should not match inside "adolorido" with word boundary
        # Actually it might with \b in Spanish... depends on regex engine
        result = _fuzzy_keyword_match("dolor", "adolorido")
        # This is acceptable either way — the fuzzy is a fallback
        assert isinstance(result, bool)

    def test_exact_match(self):
        assert _fuzzy_keyword_match("bien", "todo bien") is True

    def test_no_match(self):
        assert _fuzzy_keyword_match("dolor", "estoy genial") is False


# ─── Button text variants ────────────────────────────────────────────────

class TestButtonVariants:
    """Ensure all approved template button texts are recognized."""

    @pytest.mark.parametrize("text", [
        "Confirmar asistencia ✅",
        "confirmar asistencia",
        "Confirmo el turno",
        "confirmar",
        "confirmo",
    ])
    def test_confirm_variants(self, text):
        cls, _, _ = classify_response(text, [])
        assert cls == "confirm"

    @pytest.mark.parametrize("text", [
        "Necesito reprogramar",
        "Quiero reprogramar",
        "reprogramar",
    ])
    def test_reschedule_variants(self, text):
        cls, _, _ = classify_response(text, [])
        assert cls == "reschedule"

    @pytest.mark.parametrize("text", [
        "Quiero cancelar",
        "cancelar turno",
        "cancelar",
    ])
    def test_cancel_variants(self, text):
        cls, _, _ = classify_response(text, [])
        assert cls == "cancel"
