"""Phase 9.5 — Integration E2E: Flag-off regression for social IG agent.

Tests that when social_ig_active=False (even on an IG channel), the social
preamble is NOT injected. Also verifies that:
- get_route_for_text still works (route-level logic is flag-independent)
- The ANTI-MARKDOWN block is absent for IG channel (block is channel-gated, not flag-gated)
- compute_social_context returns is_social_channel=False

Note (from tasks.md §P9-5):
  The ANTI-MARKDOWN block is gated by `channel == "whatsapp"`, not by
  `is_social_channel`. So for an IG message regardless of the flag, the
  ANTI-MARKDOWN block will not appear. The preamble is gated by
  `is_social_channel` (flag + channel together). This is the expected behavior.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service"))


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


class TestSocialFlagOffRegression:

    def test_compute_social_context_is_false_when_flag_off_on_instagram(self):
        """social_ig_active=False on IG channel → is_social_channel=False."""
        from services.buffer_task import compute_social_context

        tenant_row = {
            "social_ig_active": False,  # FLAG OFF
            "social_landings": {"blanqueamiento": "https://blanqueamiento.dralauradelgado.com/"},
            "instagram_handle": "@dralauradelgado",
            "facebook_page_id": None,
        }

        ctx = compute_social_context("instagram", tenant_row)

        assert ctx["is_social_channel"] is False, (
            "social_ig_active=False must prevent social mode activation"
        )

    def test_social_landings_none_when_flag_off(self):
        """When flag is off, social_landings must not be forwarded."""
        from services.buffer_task import compute_social_context

        tenant_row = {
            "social_ig_active": False,
            "social_landings": {"blanqueamiento": "https://example.com"},
            "instagram_handle": "@dralauradelgado",
            "facebook_page_id": None,
        }

        ctx = compute_social_context("instagram", tenant_row)

        assert ctx["social_landings"] is None

    def test_instagram_handle_none_when_flag_off(self):
        """When flag is off, instagram_handle must not be forwarded."""
        from services.buffer_task import compute_social_context

        tenant_row = {
            "social_ig_active": False,
            "social_landings": None,
            "instagram_handle": "@dralauradelgado",
            "facebook_page_id": None,
        }

        ctx = compute_social_context("instagram", tenant_row)

        assert ctx["instagram_handle"] is None

    def test_facebook_page_id_none_when_flag_off(self):
        """When flag is off, facebook_page_id must not be forwarded."""
        from services.buffer_task import compute_social_context

        tenant_row = {
            "social_ig_active": False,
            "social_landings": None,
            "instagram_handle": None,
            "facebook_page_id": "dralauradelgado",
        }

        ctx = compute_social_context("instagram", tenant_row)

        assert ctx["facebook_page_id"] is None

    def test_no_social_preamble_when_flag_off(self):
        """build_system_prompt with is_social_channel=False must NOT inject preamble."""
        from main import build_system_prompt

        result = build_system_prompt(
            **_BASE_KWARGS,
            channel="instagram",
            is_social_channel=False,  # FLAG OFF even though channel is instagram
            social_landings={"blanqueamiento": "https://blanqueamiento.dralauradelgado.com/"},
            instagram_handle="@dralauradelgado",
            facebook_page_id=None,
        )

        assert "MODO REDES SOCIALES" not in result, (
            "Social preamble must NOT appear when is_social_channel=False"
        )

    def test_no_antimarkdown_on_instagram_channel_regardless_of_flag(self):
        """Instagram channel = no ANTI-MARKDOWN block, regardless of is_social_channel flag.

        The ANTI-MARKDOWN block is gated ONLY by channel == "whatsapp".
        Even when is_social_channel=False (flag off), if channel=instagram,
        the block should be absent.
        """
        from main import build_system_prompt

        result = build_system_prompt(
            **_BASE_KWARGS,
            channel="instagram",
            is_social_channel=False,  # flag off
            social_landings=None,
            instagram_handle=None,
            facebook_page_id=None,
        )

        assert "REGLA ANTI-MARKDOWN (WHATSAPP)" not in result, (
            "ANTI-MARKDOWN block should NOT appear on Instagram channel "
            "(it is gated by channel='whatsapp', not by is_social_channel)"
        )

    def test_get_route_for_text_works_regardless_of_flag(self):
        """get_route_for_text is route-level logic, not flag-level — works always."""
        from services.social_routes import get_route_for_text

        # CTA routes work at all times (they are static definitions)
        route = get_route_for_text("BLANQUEAMIENTO")
        assert route is not None
        assert route.group == "blanqueamiento"

    def test_get_route_for_text_still_returns_none_for_unknown(self):
        """Non-CTA keywords still return None regardless of any flag state."""
        from services.social_routes import get_route_for_text

        result = get_route_for_text("ortodoncia")
        assert result is None

    def test_compute_social_context_all_five_keys_always_present(self):
        """All 5 keys must always be in the returned dict, even with flag off."""
        from services.buffer_task import compute_social_context

        tenant_row = {
            "social_ig_active": False,
            "social_landings": None,
            "instagram_handle": None,
            "facebook_page_id": None,
        }

        ctx = compute_social_context("instagram", tenant_row)

        assert "channel" in ctx
        assert "is_social_channel" in ctx
        assert "social_landings" in ctx
        assert "instagram_handle" in ctx
        assert "facebook_page_id" in ctx

    def test_facebook_channel_flag_off_also_blocked(self):
        """Facebook channel with social_ig_active=False → is_social_channel=False."""
        from services.buffer_task import compute_social_context

        tenant_row = {
            "social_ig_active": False,
            "social_landings": None,
            "instagram_handle": None,
            "facebook_page_id": "dralauradelgado",
        }

        ctx = compute_social_context("facebook", tenant_row)

        assert ctx["is_social_channel"] is False
