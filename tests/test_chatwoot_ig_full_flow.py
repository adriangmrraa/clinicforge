"""Phase 9.1 — Integration E2E: Instagram full booking flow (mocked).

Simulates the complete IG booking flow:
1. Chatwoot webhook with channel="instagram", social_ig_active=True
2. compute_social_context returns is_social_channel=True
3. Social preamble is built with correct content
4. CTA keyword "BLANQUEAMIENTO" routes to blanqueamiento group with landing URL
5. The pitch resolves {landing_url} to the tenant's configured URL
6. Preamble contains booking tools and is free of WhatsApp redirect text
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tenant_row(
    social_ig_active: bool = True,
    social_landings: object = None,
    instagram_handle: str = "@dralauradelgado",
    facebook_page_id: str = "dralauradelgado",
) -> dict:
    return {
        "social_ig_active": social_ig_active,
        "social_landings": social_landings or {
            "main": "https://dralauradelgado.com/",
            "blanqueamiento": "https://blanqueamiento.dralauradelgado.com/",
            "implantes": "https://implantes.dralauradelgado.com/",
            "lift": "https://lift.dralauradelgado.com/",
            "evaluacion": "https://evaluacion.dralauradelgado.com/",
        },
        "instagram_handle": instagram_handle,
        "facebook_page_id": facebook_page_id,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIGFullFlow:

    def test_compute_social_context_returns_is_social_channel_true(self):
        """IG channel + flag enabled → is_social_channel=True."""
        from services.buffer_task import compute_social_context

        tenant = _make_tenant_row()
        ctx = compute_social_context("instagram", tenant)

        assert ctx["is_social_channel"] is True
        assert ctx["channel"] == "instagram"

    def test_compute_social_context_preserves_landings(self):
        """social_landings dict is forwarded when is_social_channel=True."""
        from services.buffer_task import compute_social_context

        landings = {"blanqueamiento": "https://blanqueamiento.dralauradelgado.com/"}
        tenant = _make_tenant_row(social_landings=landings)
        ctx = compute_social_context("instagram", tenant)

        assert ctx["social_landings"] == landings

    def test_social_preamble_contains_modo_redes_sociales_header(self):
        """Preamble must open with MODO REDES SOCIALES for Instagram."""
        from services.social_prompt import build_social_preamble
        from services.social_routes import CTA_ROUTES

        tenant = _make_tenant_row()
        preamble = build_social_preamble(
            tenant_id=1,
            channel="instagram",
            social_landings=tenant["social_landings"],
            instagram_handle=tenant["instagram_handle"],
            facebook_page_id=tenant["facebook_page_id"],
            cta_routes=CTA_ROUTES,
        )

        assert "MODO REDES SOCIALES" in preamble
        assert "Instagram" in preamble or "INSTAGRAM" in preamble

    def test_blanqueamiento_keyword_routes_to_blanqueamiento_group(self):
        """'BLANQUEAMIENTO' message → get_route_for_text returns blanqueamiento route."""
        from services.social_routes import get_route_for_text

        route = get_route_for_text("BLANQUEAMIENTO")

        assert route is not None
        assert route.group == "blanqueamiento"

    def test_blanqueamiento_pitch_resolves_landing_url(self):
        """The blanqueamiento pitch template should resolve {landing_url} to the configured URL."""
        from services.social_routes import get_route_for_text

        route = get_route_for_text("BLANQUEAMIENTO")
        assert route is not None

        landing_url = "https://blanqueamiento.dralauradelgado.com/"
        resolved_pitch = route.pitch_template.replace("{landing_url}", landing_url)

        assert landing_url in resolved_pitch
        assert "{landing_url}" not in resolved_pitch

    def test_preamble_contains_blanqueamiento_landing_url(self):
        """When social_landings has blanqueamiento URL, preamble should contain it."""
        from services.social_prompt import build_social_preamble
        from services.social_routes import CTA_ROUTES

        landings = {
            "blanqueamiento": "https://blanqueamiento.dralauradelgado.com/",
            "main": "https://dralauradelgado.com/",
        }

        preamble = build_social_preamble(
            tenant_id=1,
            channel="instagram",
            social_landings=landings,
            instagram_handle="@dralauradelgado",
            facebook_page_id=None,
            cta_routes=CTA_ROUTES,
        )

        assert "https://blanqueamiento.dralauradelgado.com/" in preamble

    def test_preamble_contains_check_availability_tool(self):
        """Preamble must mention check_availability (booking tool allowed)."""
        from services.social_prompt import build_social_preamble
        from services.social_routes import CTA_ROUTES

        preamble = build_social_preamble(
            tenant_id=1,
            channel="instagram",
            social_landings=None,
            instagram_handle="@dralauradelgado",
            facebook_page_id=None,
            cta_routes=CTA_ROUTES,
        )

        assert "check_availability" in preamble

    def test_preamble_contains_book_appointment_tool(self):
        """Preamble must mention book_appointment (booking tool allowed)."""
        from services.social_prompt import build_social_preamble
        from services.social_routes import CTA_ROUTES

        preamble = build_social_preamble(
            tenant_id=1,
            channel="instagram",
            social_landings=None,
            instagram_handle="@dralauradelgado",
            facebook_page_id=None,
            cta_routes=CTA_ROUTES,
        )

        assert "book_appointment" in preamble

    def test_preamble_does_not_contain_whatsapp_redirect(self):
        """Preamble MUST NOT contain any '¿Te paso el WhatsApp?' redirect."""
        from services.social_prompt import build_social_preamble
        from services.social_routes import CTA_ROUTES

        preamble = build_social_preamble(
            tenant_id=1,
            channel="instagram",
            social_landings=None,
            instagram_handle="@dralauradelgado",
            facebook_page_id=None,
            cta_routes=CTA_ROUTES,
        )

        # None of these WhatsApp redirect phrases should appear
        lower = preamble.lower()
        assert "¿te paso el whatsapp?" not in lower
        assert "te paso el whatsapp" not in lower
        # The preamble explicitly PROHIBITS WhatsApp redirect
        assert "PROHIBIDO" in preamble or "prohibido" in lower or "NO redirijas" in preamble

    def test_build_system_prompt_injects_preamble_for_instagram(self):
        """build_system_prompt with channel=instagram, is_social_channel=True injects preamble."""
        from main import build_system_prompt

        result = build_system_prompt(
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
            channel="instagram",
            is_social_channel=True,
            social_landings={
                "blanqueamiento": "https://blanqueamiento.dralauradelgado.com/",
                "main": "https://dralauradelgado.com/",
            },
            instagram_handle="@dralauradelgado",
            facebook_page_id=None,
        )

        assert "MODO REDES SOCIALES" in result
        assert "AMIGO" in result
        assert "LEAD" in result

    def test_build_system_prompt_no_antimarkdown_on_instagram(self):
        """Instagram channel must NOT have the WhatsApp ANTI-MARKDOWN block."""
        from main import build_system_prompt

        result = build_system_prompt(
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
            channel="instagram",
            is_social_channel=True,
            social_landings=None,
            instagram_handle="@dralauradelgado",
            facebook_page_id=None,
        )

        assert "REGLA ANTI-MARKDOWN (WHATSAPP)" not in result
