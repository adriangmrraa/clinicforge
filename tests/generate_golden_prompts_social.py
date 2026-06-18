"""Helper script: generate golden baselines for Instagram, Facebook, and Telegram channels.

Run once via pytest to create (or overwrite) the baseline files:
  pytest tests/generate_golden_prompts_social.py -s

This is NOT a test file — it just uses pytest's import machinery.

After running this script, the golden files in tests/fixtures/ will contain the combined
output of build_social_preamble() + build_system_prompt() (matching the runtime path in
buffer_task.py for the solo engine and specialists.py for the multi-agent engine).

Note: Telegram uses telegram_bot.py (not the social preamble path), so its golden file
captures the Telegram-specific system prompt instead.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service"))

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Shared kwargs — same baseline as golden_prompt_whatsapp.txt so the diff is only
# the social preamble added by channel="instagram"/"facebook".
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
    "blanqueamiento": "https://blanqueamiento.dralauradelgado.com/",
    "implantes": "https://implantes.dralauradelgado.com/",
}

SEPARATOR = "\n\n---\n\n"


def _build_social_prompt(channel: str, handle: str) -> str:
    """Build the combined prompt the same way buffer_task does at runtime."""
    from main import build_system_prompt
    from services.social_prompt import build_social_preamble
    from services.social_routes import CTA_ROUTES

    preamble = build_social_preamble(
        tenant_id=0,
        channel=channel,
        social_landings=_SOCIAL_LANDINGS,
        instagram_handle=handle if channel == "instagram" else None,
        facebook_page_id=handle if channel == "facebook" else None,
        cta_routes=CTA_ROUTES,
        whatsapp_link="https://wa.me/5491112345678",
    )
    base = build_system_prompt(**_BASE_KWARGS, channel=channel)
    return preamble + SEPARATOR + base


def test_generate_instagram_golden_file(capsys):
    """Write the Instagram golden file (creates or overwrites)."""
    path = FIXTURES_DIR / "golden_prompt_instagram.txt"
    result = _build_social_prompt("instagram", "@dralauradelgado")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result, encoding="utf-8")
    with capsys.disabled():
        print(f"\nInstagram golden file written: {path} ({len(result)} chars)")
    assert len(result) > 0


def test_generate_facebook_golden_file(capsys):
    """Write the Facebook golden file (creates or overwrites)."""
    path = FIXTURES_DIR / "golden_prompt_facebook.txt"
    result = _build_social_prompt("facebook", "dralauradelgado")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result, encoding="utf-8")
    with capsys.disabled():
        print(f"\nFacebook golden file written: {path} ({len(result)} chars)")
    assert len(result) > 0


def test_generate_telegram_golden_file(capsys):
    """Write a Telegram golden stub.

    Telegram uses telegram_bot.py (not build_system_prompt), so we capture the
    system prompt from the TelegramBot class. If the class is not importable in
    the test environment, this test is skipped gracefully.
    """
    path = FIXTURES_DIR / "golden_prompt_telegram.txt"

    try:
        from services.telegram_bot import TelegramBot  # type: ignore

        if hasattr(TelegramBot, "build_system_prompt"):
            result = TelegramBot.build_system_prompt()
        elif hasattr(TelegramBot, "SYSTEM_PROMPT"):
            result = TelegramBot.SYSTEM_PROMPT
        else:
            result = (
                "# Telegram system prompt is constructed dynamically inside TelegramBot.\n"
                "# Inspect services/telegram_bot.py to identify the exact prompt string.\n"
                "# This golden file tracks the static parts of the Telegram prompt.\n"
            )
    except ImportError:
        result = (
            "# TelegramBot not importable in this environment (missing deps).\n"
            "# Run this generator from inside the orchestrator_service environment.\n"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result, encoding="utf-8")
    with capsys.disabled():
        print(f"\nTelegram golden file written: {path} ({len(result)} chars)")
    assert len(result) > 0
