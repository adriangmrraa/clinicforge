"""Unit tests for orchestrator_service.services.social_prompt.

TDD phase 3: all tests must FAIL before implementation, PASS after.
"""

import pytest
from orchestrator_service.services.social_prompt import build_social_preamble
from orchestrator_service.services.social_routes import CTA_ROUTES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SOCIAL_LANDINGS = {
    "main": "https://dralauradelgado.com/",
    "blanqueamiento": "https://blanqueamiento.dralauradelgado.com/",
    "implantes": "https://implantes.dralauradelgado.com/",
    "lift": "https://lift.dralauradelgado.com/",
    "evaluacion": "https://evaluacion.dralauradelgado.com/",
}


def _preamble(
    channel="instagram",
    social_landings=SOCIAL_LANDINGS,
    instagram_handle="@dralauradelgado",
    facebook_page_id="12345",
    cta_routes=None,
):
    if cta_routes is None:
        cta_routes = CTA_ROUTES
    return build_social_preamble(
        tenant_id=1,
        channel=channel,
        social_landings=social_landings,
        instagram_handle=instagram_handle,
        facebook_page_id=facebook_page_id,
        cta_routes=cta_routes,
    )


# ---------------------------------------------------------------------------
# P3-1 tests
# ---------------------------------------------------------------------------


def test_preamble_is_nonempty_string():
    result = _preamble()
    assert isinstance(result, str)
    assert len(result) > 0


def test_preamble_contains_channel_identity_instagram():
    result = _preamble(channel="instagram")
    assert "Instagram" in result


def test_preamble_contains_channel_identity_facebook():
    result = _preamble(channel="facebook")
    assert "Facebook" in result


def test_preamble_contains_self_reference_when_handle_provided():
    result = _preamble(instagram_handle="@dralauradelgado")
    assert "@dralauradelgado" in result


def test_preamble_omits_self_reference_when_handle_none():
    result = _preamble(instagram_handle=None)
    # Should not crash and should not contain "None" literally
    assert "None" not in result


def test_preamble_does_not_crash_with_facebook_channel():
    result = _preamble(channel="facebook")
    assert isinstance(result, str)
    assert len(result) > 0


def test_preamble_contains_cta_group_names():
    result = _preamble()
    for route in CTA_ROUTES:
        assert route.group.upper() in result.upper(), (
            f"CTA group '{route.group}' not found in preamble"
        )


def test_preamble_contains_blanqueamiento_landing_url():
    result = _preamble()
    assert "https://blanqueamiento.dralauradelgado.com/" in result


def test_preamble_contains_main_landing_url():
    result = _preamble()
    assert "https://dralauradelgado.com/" in result


def test_preamble_handles_none_landings_gracefully():
    # Must not raise; section may be absent or use defaults
    result = build_social_preamble(
        tenant_id=1,
        channel="instagram",
        social_landings=None,
        instagram_handle="@dralauradelgado",
        facebook_page_id="12345",
        cta_routes=CTA_ROUTES,
    )
    assert isinstance(result, str)
    assert len(result) > 0


def test_preamble_contains_friend_detection_rules():
    result = _preamble()
    assert "AMIGO" in result
    assert "LEAD" in result


def test_preamble_forbidden_triage_urgency():
    result = _preamble()
    # Must mention triage_urgency by name and prohibit it
    assert "triage_urgency" in result
    # Should have a prohibition word nearby
    lower = result.lower()
    assert "nunca" in lower or "prohibid" in lower or "forbidden" in lower


def test_preamble_markdown_allowed():
    result = _preamble()
    lower = result.lower()
    assert "markdown" in lower or "formato" in lower


def test_preamble_voseo():
    result = _preamble()
    lower = result.lower()
    # Should instruct voseo or use voseo naturally
    assert "voseo" in lower or "vos " in lower or "agendamos" in lower or "tenés" in lower


def test_preamble_medical_ethics_rule():
    result = _preamble()
    lower = result.lower()
    # Should mention presencial evaluation or diagnosis ethics
    assert "presencial" in lower or "diagnóstico" in lower or "diagnostico" in lower


def test_preamble_contains_list_services_tool_mention():
    result = _preamble()
    assert "list_services" in result


def test_preamble_does_not_redirect_to_whatsapp():
    result = _preamble()
    # Should NOT contain WhatsApp redirect patterns
    assert "¿Te paso el WhatsApp?" not in result
    assert "link de WhatsApp" not in result
    assert "pasarte el WhatsApp" not in result


def test_preamble_contains_friend_response_template():
    result = _preamble()
    # The friend response base template should be present
    lower = result.lower()
    assert "hola" in lower and ("cómo vas" in lower or "como vas" in lower)


def test_preamble_is_pure_function():
    r1 = _preamble()
    r2 = _preamble()
    assert r1 == r2


def test_preamble_with_custom_single_landing():
    landings = {"main": "https://example.com/", "blanqueamiento": "https://blanq.example.com/"}
    result = build_social_preamble(
        tenant_id=1,
        channel="instagram",
        social_landings=landings,
        instagram_handle="@test",
        facebook_page_id=None,
        cta_routes=CTA_ROUTES,
    )
    assert "https://blanq.example.com/" in result


def test_preamble_facebook_page_id_not_required():
    result = build_social_preamble(
        tenant_id=1,
        channel="facebook",
        social_landings=SOCIAL_LANDINGS,
        instagram_handle=None,
        facebook_page_id=None,
        cta_routes=CTA_ROUTES,
    )
    assert isinstance(result, str)
    assert len(result) > 0
