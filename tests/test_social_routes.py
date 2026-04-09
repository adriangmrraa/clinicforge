"""Tests for orchestrator_service/services/social_routes.py.

Validates CTA route keyword matching (case/accent insensitive), route structure,
pitch content rules (no WhatsApp redirect, direct booking trigger), and
load_routes_from_file graceful fallback.
"""

import pytest

# --- import the module under test ---
from orchestrator_service.services.social_routes import (
    CTARoute,
    CTA_ROUTES,
    get_route_for_text,
    load_routes_from_file,
)


class TestCTARoutesStructure:
    """Validates the shape and content of CTA_ROUTES list."""

    def test_cta_routes_is_non_empty_list(self):
        assert isinstance(CTA_ROUTES, list)
        assert len(CTA_ROUTES) > 0

    def test_cta_routes_has_four_groups(self):
        groups = {r.group for r in CTA_ROUTES}
        assert len(CTA_ROUTES) == 4
        assert groups == {"blanqueamiento", "implantes", "lift", "evaluacion"}

    def test_each_route_is_cta_route_instance(self):
        for route in CTA_ROUTES:
            assert isinstance(route, CTARoute)

    def test_each_route_has_group(self):
        for route in CTA_ROUTES:
            assert route.group and isinstance(route.group, str)

    def test_each_route_has_keywords(self):
        for route in CTA_ROUTES:
            assert route.keywords
            assert len(route.keywords) > 0

    def test_each_route_has_pitch_template(self):
        for route in CTA_ROUTES:
            assert route.pitch_template and isinstance(route.pitch_template, str)

    def test_each_route_has_landing_url_key(self):
        for route in CTA_ROUTES:
            assert route.landing_url_key and isinstance(route.landing_url_key, str)

    def test_groups_include_required_four(self):
        groups = {r.group for r in CTA_ROUTES}
        assert "blanqueamiento" in groups
        assert "implantes" in groups
        assert "lift" in groups
        assert "evaluacion" in groups


class TestPitchContentRules:
    """Validates pitch template content: no WhatsApp redirect, direct booking trigger."""

    def test_no_pitch_contains_whatsapp_redirect(self):
        """Pitches must NOT drive to WhatsApp — they book directly on IG/FB."""
        for route in CTA_ROUTES:
            lower = route.pitch_template.lower()
            assert "whatsapp" not in lower, (
                f"Route '{route.group}' pitch contains 'whatsapp' — "
                "rewrite to drive direct booking instead"
            )

    def test_each_pitch_contains_booking_trigger(self):
        """Every pitch must end with a direct booking trigger."""
        booking_triggers = [
            "horario",
            "evaluar",
            "evaluación",
            "evaluacion",
            "turno",
            "agendar",
            "agend",
            "día",
            "dia",
        ]
        for route in CTA_ROUTES:
            pitch_lower = route.pitch_template.lower()
            has_trigger = any(t in pitch_lower for t in booking_triggers)
            assert has_trigger, (
                f"Route '{route.group}' pitch does not contain a booking trigger. "
                f"Expected one of: {booking_triggers}"
            )


class TestGetRouteForText:
    """Tests for get_route_for_text() keyword matching logic."""

    def test_blanqueamiento_exact(self):
        route = get_route_for_text("quiero blanqueamiento")
        assert route is not None
        assert route.group == "blanqueamiento"

    def test_blanqueamiento_uppercase(self):
        """Case insensitive matching."""
        route = get_route_for_text("BLANQUEAMIENTO")
        assert route is not None
        assert route.group == "blanqueamiento"

    def test_blanqueamiento_mixed_case(self):
        route = get_route_for_text("Blanqueamiento")
        assert route is not None
        assert route.group == "blanqueamiento"

    def test_evaluacion_no_accent(self):
        """Accent-insensitive: 'EVALUACION' must match 'evaluacion' route."""
        route = get_route_for_text("EVALUACION")
        assert route is not None
        assert route.group == "evaluacion"

    def test_evaluacion_with_accent(self):
        """'EVALUACIÓN' with accent must also match."""
        route = get_route_for_text("EVALUACIÓN")
        assert route is not None
        assert route.group == "evaluacion"

    def test_implantes_keyword(self):
        route = get_route_for_text("quiero implantes dentales")
        assert route is not None
        assert route.group == "implantes"

    def test_lift_keyword(self):
        route = get_route_for_text("me interesa el LIFT")
        assert route is not None
        assert route.group == "lift"

    def test_empty_string_returns_none(self):
        result = get_route_for_text("")
        assert result is None

    def test_none_returns_none(self):
        result = get_route_for_text(None)
        assert result is None

    def test_whitespace_only_returns_none(self):
        result = get_route_for_text("   ")
        assert result is None

    def test_no_match_returns_none(self):
        result = get_route_for_text("hola cómo estás")
        assert result is None

    def test_no_match_generic_greeting(self):
        result = get_route_for_text("buenas tardes")
        assert result is None

    def test_case_insensitive_evaluacion(self):
        route = get_route_for_text("evaluacion")
        assert route is not None
        assert route.group == "evaluacion"

    def test_keyword_in_longer_sentence(self):
        """Keyword should match even when embedded in a sentence."""
        route = get_route_for_text("hola, quisiera saber más sobre blanqueamiento porque tengo una boda")
        assert route is not None
        assert route.group == "blanqueamiento"


class TestLoadRoutesFromFile:
    """Tests for load_routes_from_file() graceful fallback."""

    def test_nonexistent_path_returns_cta_routes(self):
        result = load_routes_from_file("/nonexistent/path/that/does/not/exist.md")
        assert result == CTA_ROUTES

    def test_returns_list_of_cta_routes(self):
        result = load_routes_from_file("/dev/null")
        assert isinstance(result, list)
        assert all(isinstance(r, CTARoute) for r in result)

    def test_does_not_raise_on_invalid_path(self):
        """Must not raise any exception for any path."""
        try:
            load_routes_from_file("/completely/invalid/path")
        except Exception as e:
            pytest.fail(
                f"load_routes_from_file raised an exception for invalid path: {e}"
            )
