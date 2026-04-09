"""Social mode tests for build_system_prompt (Phase 4).

Tests verify:
- Social preamble injected when is_social_channel=True
- ANTI-MARKDOWN block absent on social channels
- Preamble appears BEFORE the base prompt
- WhatsApp path keeps ANTI-MARKDOWN block
- Flag off (is_social_channel=False) → no preamble even when channel=instagram
- New kwargs have safe defaults (no change to existing callers)

These tests must FAIL before the Phase 4 code change and PASS after.
"""

from pathlib import Path

import pytest

from main import build_system_prompt

# ---------------------------------------------------------------------------
# Shared input fixture (same as golden_prompt regression)
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

_SOCIAL_EXTRA = dict(
    channel="instagram",
    is_social_channel=True,
    social_landings={
        "main": "https://dralauradelgado.com/",
        "blanqueamiento": "https://blanqueamiento.dralauradelgado.com/",
    },
    instagram_handle="@dralauradelgado",
    facebook_page_id="123",
)

# The exact anti-markdown block text as it appears in main.py (for assertion)
_ANTI_MARKDOWN_MARKER = "REGLA ANTI-MARKDOWN (WHATSAPP)"


# ---------------------------------------------------------------------------
# Golden file path — used to compare WhatsApp baseline length
# ---------------------------------------------------------------------------
_GOLDEN_PATH = Path(__file__).parent / "fixtures" / "golden_prompt_whatsapp.txt"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_social_mode_injects_preamble():
    result = build_system_prompt(**_BASE_KWARGS, **_SOCIAL_EXTRA)
    assert "## MODO REDES SOCIALES" in result, (
        "Social preamble header not found in IG prompt"
    )
    assert "AMIGO" in result, "Friend detection block missing"
    assert "LEAD" in result, "Lead detection block missing"
    assert "BLANQUEAMIENTO" in result.upper(), "CTA group not found in prompt"


def test_social_mode_strips_antimarkdown_block():
    result = build_system_prompt(**_BASE_KWARGS, **_SOCIAL_EXTRA)
    assert _ANTI_MARKDOWN_MARKER not in result, (
        "WhatsApp ANTI-MARKDOWN block should be ABSENT on Instagram channel"
    )


def test_social_mode_preamble_before_base_prompt():
    result = build_system_prompt(**_BASE_KWARGS, **_SOCIAL_EXTRA)
    preamble_pos = result.find("## MODO REDES SOCIALES")
    # The base prompt identity line always starts early
    identity_pos = result.find("REGLA DE IDIOMA")
    assert preamble_pos != -1, "Preamble not found"
    assert identity_pos != -1, "Base prompt identity not found"
    assert preamble_pos < identity_pos, (
        f"Preamble ({preamble_pos}) should appear BEFORE base prompt ({identity_pos})"
    )


def test_whatsapp_keeps_antimarkdown_block():
    result = build_system_prompt(**_BASE_KWARGS, channel="whatsapp", is_social_channel=False)
    assert _ANTI_MARKDOWN_MARKER in result, (
        "WhatsApp ANTI-MARKDOWN block must be PRESENT on WhatsApp channel"
    )


def test_flag_off_no_preamble():
    """channel=instagram but is_social_channel=False → preamble absent."""
    result = build_system_prompt(
        **_BASE_KWARGS,
        channel="instagram",
        is_social_channel=False,
        social_landings=_SOCIAL_EXTRA["social_landings"],
        instagram_handle="@dralauradelgado",
        facebook_page_id="123",
    )
    assert "## MODO REDES SOCIALES" not in result, (
        "Preamble injected even with is_social_channel=False"
    )


def test_new_kwargs_have_safe_defaults():
    """Calling build_system_prompt with zero new kwargs must work (no TypeError)."""
    result = build_system_prompt(**_BASE_KWARGS)
    assert isinstance(result, str)
    assert len(result) > 0


def test_social_prompt_is_longer_than_whatsapp():
    """Social mode prompt should be longer than WhatsApp (preamble adds ~2KB)."""
    if not _GOLDEN_PATH.exists():
        pytest.skip("Golden file not found")

    golden_len = len(_GOLDEN_PATH.read_text(encoding="utf-8"))
    social_result = build_system_prompt(**_BASE_KWARGS, **_SOCIAL_EXTRA)
    assert len(social_result) > golden_len, (
        f"Social prompt ({len(social_result)}) should be longer than WhatsApp ({golden_len})"
    )


def test_facebook_channel_injects_facebook_label():
    result = build_system_prompt(
        **_BASE_KWARGS,
        channel="facebook",
        is_social_channel=True,
        social_landings=_SOCIAL_EXTRA["social_landings"],
        instagram_handle=None,
        facebook_page_id="DraLauraDelgado",
    )
    assert "Facebook" in result
    assert "## MODO REDES SOCIALES" in result
    # Facebook should not show Instagram in channel context
    assert "MODO REDES SOCIALES — FACEBOOK" in result


def test_social_mode_contains_triage_urgency_prohibition():
    result = build_system_prompt(**_BASE_KWARGS, **_SOCIAL_EXTRA)
    assert "triage_urgency" in result
    lower = result.lower()
    assert "nunca" in lower or "prohibid" in lower
