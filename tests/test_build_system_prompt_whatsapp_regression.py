"""WhatsApp regression test for build_system_prompt.

Golden-file contract: build_system_prompt with all new social kwargs at their
defaults and channel="whatsapp" MUST produce a string byte-identical to
tests/fixtures/golden_prompt_whatsapp.txt.

If this test fails BEFORE the Phase 4 code change, the golden file is wrong —
regenerate it with tests/generate_golden_prompt.py.

If this test fails AFTER the Phase 4 code change, the WhatsApp path was
accidentally modified — STOP and fix before proceeding.
"""

from pathlib import Path

import pytest

from main import build_system_prompt

GOLDEN_PATH = Path(__file__).parent / "fixtures" / "golden_prompt_whatsapp.txt"

# Exact same inputs used to generate the golden file in generate_golden_prompt.py
GOLDEN_KWARGS = dict(
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


def test_whatsapp_prompt_matches_golden_file():
    """Output must be byte-identical to the committed golden file."""
    if not GOLDEN_PATH.exists():
        pytest.skip(f"Golden file not found: {GOLDEN_PATH} — run generate_golden_prompt.py first")

    golden = GOLDEN_PATH.read_text(encoding="utf-8")
    result = build_system_prompt(**GOLDEN_KWARGS)

    assert result == golden, (
        "WhatsApp prompt DOES NOT match golden file!\n"
        f"Expected length: {len(golden)}\n"
        f"Actual length:   {len(result)}\n"
        "Diff hint: look for the first char position that differs:\n"
        f"  {next((i for i, (a, b) in enumerate(zip(result, golden)) if a != b), 'lengths differ')} chars in"
    )


def test_whatsapp_prompt_with_new_defaults_matches_golden_file():
    """Adding new social kwargs with defaults MUST NOT change the WhatsApp output."""
    if not GOLDEN_PATH.exists():
        pytest.skip(f"Golden file not found: {GOLDEN_PATH}")

    golden = GOLDEN_PATH.read_text(encoding="utf-8")

    # Call with the 5 new social kwargs explicitly set to their defaults
    result = build_system_prompt(
        **GOLDEN_KWARGS,
        channel="whatsapp",
        is_social_channel=False,
        social_landings=None,
        instagram_handle=None,
        facebook_page_id=None,
    )

    assert result == golden, (
        "Adding new social kwargs with defaults changed the WhatsApp prompt! "
        "The WhatsApp default path is NOT byte-identical. STOP and fix."
    )
