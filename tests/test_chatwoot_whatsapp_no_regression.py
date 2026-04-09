"""Phase 9.4 — Integration E2E: WhatsApp non-regression test.

Verifies that WhatsApp channel is NEVER affected by social mode — even when the
tenant has social_ig_active=True. WhatsApp must:
  - NOT get is_social_channel=True from compute_social_context
  - NOT receive the social preamble in build_system_prompt
  - RETAIN the ANTI-MARKDOWN block (WhatsApp formatting rules)
  - Produce byte-identical output to the committed golden file
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service"))

import pytest

GOLDEN_PATH = Path(__file__).parent / "fixtures" / "golden_prompt_whatsapp.txt"

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


class TestWhatsAppNonRegression:

    def test_whatsapp_compute_social_context_is_false_even_with_ig_flag_on(self):
        """WhatsApp channel MUST return is_social_channel=False even when tenant has social_ig_active=True."""
        from services.buffer_task import compute_social_context

        tenant_row = {
            "social_ig_active": True,  # intentionally True to test bypass
            "social_landings": {"blanqueamiento": "https://blanqueamiento.dralauradelgado.com/"},
            "instagram_handle": "@dralauradelgado",
            "facebook_page_id": "dralauradelgado",
        }

        ctx = compute_social_context("whatsapp", tenant_row)

        assert ctx["is_social_channel"] is False, (
            "WhatsApp must NEVER activate social mode, even when social_ig_active=True"
        )

    def test_whatsapp_social_landings_is_none(self):
        """For WhatsApp, social_landings must be None (not forwarded)."""
        from services.buffer_task import compute_social_context

        tenant_row = {
            "social_ig_active": True,
            "social_landings": {"blanqueamiento": "https://example.com"},
            "instagram_handle": "@dralauradelgado",
            "facebook_page_id": None,
        }

        ctx = compute_social_context("whatsapp", tenant_row)

        assert ctx["social_landings"] is None

    def test_whatsapp_instagram_handle_is_none(self):
        """For WhatsApp, instagram_handle must be None."""
        from services.buffer_task import compute_social_context

        tenant_row = {
            "social_ig_active": True,
            "social_landings": None,
            "instagram_handle": "@dralauradelgado",
            "facebook_page_id": None,
        }

        ctx = compute_social_context("whatsapp", tenant_row)

        assert ctx["instagram_handle"] is None

    def test_whatsapp_facebook_page_id_is_none(self):
        """For WhatsApp, facebook_page_id must be None."""
        from services.buffer_task import compute_social_context

        tenant_row = {
            "social_ig_active": True,
            "social_landings": None,
            "instagram_handle": None,
            "facebook_page_id": "dralauradelgado",
        }

        ctx = compute_social_context("whatsapp", tenant_row)

        assert ctx["facebook_page_id"] is None

    def test_whatsapp_build_system_prompt_no_social_preamble(self):
        """build_system_prompt with channel=whatsapp must NOT contain MODO REDES SOCIALES."""
        from main import build_system_prompt

        result = build_system_prompt(
            **_BASE_KWARGS,
            channel="whatsapp",
            is_social_channel=False,
            social_landings=None,
            instagram_handle=None,
            facebook_page_id=None,
        )

        assert "MODO REDES SOCIALES" not in result, (
            "Social preamble found in WhatsApp prompt — REGRESSION!"
        )

    def test_whatsapp_build_system_prompt_has_antimarkdown(self):
        """WhatsApp channel MUST retain the ANTI-MARKDOWN block."""
        from main import build_system_prompt

        result = build_system_prompt(
            **_BASE_KWARGS,
            channel="whatsapp",
            is_social_channel=False,
        )

        assert "REGLA ANTI-MARKDOWN (WHATSAPP)" in result, (
            "WhatsApp ANTI-MARKDOWN block is missing — REGRESSION!"
        )

    def test_whatsapp_no_amigo_lead_detection(self):
        """WhatsApp prompt must NOT contain friend-vs-lead detection rules."""
        from main import build_system_prompt

        result = build_system_prompt(
            **_BASE_KWARGS,
            channel="whatsapp",
            is_social_channel=False,
        )

        # The friend detection section is ONLY injected for social channels
        # We check that the specific social-mode AMIGO/LEAD block is absent
        # (Note: the word LEAD may appear in other context, but MODO REDES SOCIALES is exclusive)
        assert "MODO REDES SOCIALES" not in result

    def test_whatsapp_golden_file_byte_identical(self):
        """WhatsApp prompt with social defaults must be byte-identical to golden file."""
        if not GOLDEN_PATH.exists():
            pytest.skip(f"Golden file not found: {GOLDEN_PATH}")

        from main import build_system_prompt

        golden = GOLDEN_PATH.read_text(encoding="utf-8")
        result = build_system_prompt(
            **_BASE_KWARGS,
            channel="whatsapp",
            is_social_channel=False,
            social_landings=None,
            instagram_handle=None,
            facebook_page_id=None,
        )

        assert result == golden, (
            "WhatsApp prompt is NOT byte-identical to golden file — REGRESSION!\n"
            f"Expected length: {len(golden)}, actual: {len(result)}"
        )

    def test_channel_none_treated_as_whatsapp(self):
        """channel_type=None should default to 'whatsapp' and NOT activate social mode."""
        from services.buffer_task import compute_social_context

        tenant_row = {
            "social_ig_active": True,
            "social_landings": None,
            "instagram_handle": "@dralauradelgado",
            "facebook_page_id": None,
        }

        ctx = compute_social_context(None, tenant_row)

        assert ctx["channel"] == "whatsapp"
        assert ctx["is_social_channel"] is False
