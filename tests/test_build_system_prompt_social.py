"""Social mode tests — updated post-refactor.

The social preamble injection was removed from build_system_prompt() because it
was dead code at runtime (buffer_task never passed is_social_channel=True).
The actual injection happens in:
  - buffer_task.py (solo path) — calls build_social_preamble() directly
  - specialists.py (multi-agent path) — calls build_social_preamble() directly

These tests now verify:
  - build_social_preamble() output contract (the real source of truth)
  - ANTI-MARKDOWN block controlled by channel param in build_system_prompt()
  - Backward compat: build_system_prompt() without social params
"""

from pathlib import Path

import pytest

from main import build_system_prompt
from services.social_prompt import build_social_preamble
from services.social_routes import CTA_ROUTES

# ---------------------------------------------------------------------------
# Shared input fixture
# ---------------------------------------------------------------------------

_BASE_KWARGS = dict(
    clinic_name="Clínica Dra. Laura Delgado",
    current_time="2026-01-01 10:00",
    response_language="es",
    hours_start="09:00",
    hours_end="18:00",
    ad_context="",
    patient_context="",
    clinic_address="Av. Corrientes 1234, CABA",
    clinic_maps_url="https://maps.google.com/?q=test",
    clinic_working_hours=None,
    faqs=[],
    patient_status="new_lead",
    consultation_price=5000.0,
    sede_info=None,
    anamnesis_url="",
    bank_cbu="",
    bank_alias="",
    bank_holder_name="",
    upcoming_holidays=None,
    insurance_providers=None,
    derivation_rules=None,
    specialty_pitch="",
    professional_name="Laura Delgado",
    bot_name="TORA",
    intent_tags=None,
    is_greeting_pending=True,
    treatment_types=None,
    payment_methods=None,
    financing_available=False,
    max_installments=None,
    installments_interest_free=True,
    financing_provider="",
    financing_notes="",
    cash_discount_percent=None,
    accepts_crypto=False,
    special_conditions_block="",
    support_policy_block="",
)

_SOCIAL_LANDINGS = {
    "main": "https://dralauradelgado.com/",
    "blanqueamiento": "https://blanqueamiento.dralauradelgado.com/",
}

# The exact anti-markdown block text as it appears in main.py (for assertion)
_ANTI_MARKDOWN_MARKER = "REGLA ANTI-MARKDOWN (WHATSAPP)"

# Golden file path
_GOLDEN_PATH = Path(__file__).parent / "fixtures" / "golden_prompt_whatsapp.txt"


# ---------------------------------------------------------------------------
# build_social_preamble() contract tests (real runtime injection source)
# ---------------------------------------------------------------------------


def test_preamble_injects_modo_redes_sociales_header():
    """build_social_preamble must include the MODO REDES SOCIALES header."""
    result = build_social_preamble(
        tenant_id=0,
        channel="instagram",
        social_landings=_SOCIAL_LANDINGS,
        instagram_handle="@dralauradelgado",
        facebook_page_id=None,
        cta_routes=CTA_ROUTES,
    )
    assert "## MODO REDES SOCIALES" in result
    assert "AMIGO" in result
    assert "LEAD" in result


def test_preamble_contains_cta_groups():
    """build_social_preamble must include CTA groups from CTA_ROUTES."""
    result = build_social_preamble(
        tenant_id=0,
        channel="instagram",
        social_landings=_SOCIAL_LANDINGS,
        instagram_handle="@dralauradelgado",
        facebook_page_id=None,
        cta_routes=CTA_ROUTES,
    )
    assert "BLANQUEAMIENTO" in result.upper()
    assert "IMPLANTES" in result.upper()
    assert "LIFT" in result.upper()
    assert "EVALUACION" in result.upper()


def test_preamble_instagram_label():
    """Instagram channel must show Instagram label."""
    result = build_social_preamble(
        tenant_id=0,
        channel="instagram",
        social_landings=_SOCIAL_LANDINGS,
        instagram_handle="@dralauradelgado",
        facebook_page_id=None,
        cta_routes=CTA_ROUTES,
    )
    assert "MODO REDES SOCIALES — INSTAGRAM" in result


def test_preamble_facebook_label():
    """Facebook channel must show Facebook label."""
    result = build_social_preamble(
        tenant_id=0,
        channel="facebook",
        social_landings=_SOCIAL_LANDINGS,
        instagram_handle=None,
        facebook_page_id="DraLauraDelgado",
        cta_routes=CTA_ROUTES,
    )
    assert "MODO REDES SOCIALES — FACEBOOK" in result


def test_preamble_contains_triage_urgency_prohibition():
    """Social preamble must prohibit triage_urgency."""
    result = build_social_preamble(
        tenant_id=0,
        channel="instagram",
        social_landings=_SOCIAL_LANDINGS,
        instagram_handle="@dralauradelgado",
        facebook_page_id=None,
        cta_routes=CTA_ROUTES,
    )
    assert "triage_urgency" in result
    lower = result.lower()
    assert "nunca" in lower or "prohibid" in lower


def test_preamble_contains_whatsapp_link_rule():
    """Post-booking phone collection + WhatsApp link must be present."""
    result = build_social_preamble(
        tenant_id=0,
        channel="instagram",
        social_landings=_SOCIAL_LANDINGS,
        instagram_handle="@dralauradelgado",
        facebook_page_id=None,
        cta_routes=CTA_ROUTES,
        whatsapp_link="https://wa.me/5491123456789",
    )
    assert "wa.me" in result
    assert "DESPUÉS DEL booking" in result or "save_patient_email" in result


# ---------------------------------------------------------------------------
# build_system_prompt — channel controls anti-markdown
# ---------------------------------------------------------------------------


def test_whatsapp_keeps_antimarkdown_block():
    result = build_system_prompt(**_BASE_KWARGS, channel="whatsapp")
    assert _ANTI_MARKDOWN_MARKER in result, (
        "WhatsApp ANTI-MARKDOWN block must be PRESENT on WhatsApp channel"
    )


def test_instagram_strips_antimarkdown_block():
    """channel=instagram must NOT have anti-markdown (social channels support it)."""
    result = build_system_prompt(**_BASE_KWARGS, channel="instagram")
    assert _ANTI_MARKDOWN_MARKER not in result, (
        "WhatsApp ANTI-MARKDOWN block should be ABSENT on Instagram channel"
    )


def test_facebook_strips_antimarkdown_block():
    """channel=facebook must NOT have anti-markdown."""
    result = build_system_prompt(**_BASE_KWARGS, channel="facebook")
    assert _ANTI_MARKDOWN_MARKER not in result, (
        "WhatsApp ANTI-MARKDOWN block should be ABSENT on Facebook channel"
    )


# ---------------------------------------------------------------------------
# build_system_prompt — backward compat
# ---------------------------------------------------------------------------


def test_no_channel_defaults_to_whatsapp():
    """Calling build_system_prompt without channel must default to WhatsApp."""
    result = build_system_prompt(**_BASE_KWARGS)
    assert _ANTI_MARKDOWN_MARKER in result, (
        "Default channel must be WhatsApp with ANTI-MARKDOWN"
    )


def test_backward_compat_no_new_kwargs():
    """Calling build_system_prompt with only original kwargs must work."""
    result = build_system_prompt(**_BASE_KWARGS)
    assert isinstance(result, str)
    assert len(result) > 0
