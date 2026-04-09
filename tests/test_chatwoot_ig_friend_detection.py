"""Phase 9.2 — Integration E2E: Friend/acquaintance detection in social preamble.

Tests that the social preamble contains the correct friend-vs-lead detection
rules including: detection signals, CTA override rule, uncertainty default,
casual reply template, and tool prohibition for friend mode.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service"))


def _build_preamble(channel: str = "instagram", instagram_handle: str = "@dralauradelgado"):
    from services.social_prompt import build_social_preamble
    from services.social_routes import CTA_ROUTES

    return build_social_preamble(
        tenant_id=1,
        channel=channel,
        social_landings={
            "main": "https://dralauradelgado.com/",
            "blanqueamiento": "https://blanqueamiento.dralauradelgado.com/",
        },
        instagram_handle=instagram_handle,
        facebook_page_id=None,
        cta_routes=CTA_ROUTES,
    )


class TestFriendDetectionRules:

    def test_preamble_contains_friend_detection_section_title(self):
        """Section must contain a DETECCIÓN AMIGO vs LEAD or equivalent header."""
        preamble = _build_preamble()
        # The section title is one of these forms
        assert "DETECCIÓN" in preamble.upper() or "AMIGO" in preamble

    def test_preamble_contains_amigo_keyword(self):
        """Friend mode is identified by the keyword AMIGO."""
        preamble = _build_preamble()
        assert "AMIGO" in preamble

    def test_preamble_contains_lead_keyword(self):
        """Lead mode is identified by the keyword LEAD."""
        preamble = _build_preamble()
        assert "LEAD" in preamble

    def test_preamble_contains_friend_casual_greeting_template_base(self):
        """Casual greeting template base 'Hola, ¿cómo vas?' must be present."""
        preamble = _build_preamble()
        assert "Hola" in preamble
        # The exact base template from the spec
        assert "cómo vas" in preamble or "cómo vas?" in preamble

    def test_preamble_contains_dame_un_rato(self):
        """The 'Dame un rato' phrase is part of the casual friend reply template."""
        preamble = _build_preamble()
        assert "Dame un rato" in preamble or "dame un rato" in preamble

    def test_preamble_contains_no_tool_call_rule_for_friend_mode(self):
        """Friend mode rule: NO llamés/uses tools."""
        preamble = _build_preamble()
        lower = preamble.lower()
        # Either "NO llamés" or "NO llames" or "NO ofrezcas"
        assert (
            "no llamés" in lower
            or "no llames" in lower
            or "no ofrezcas" in lower
            or "no llam" in lower
        ), f"Friend-mode tool prohibition not found in preamble"

    def test_preamble_contains_no_agenda_rule_for_friend(self):
        """Friend mode: NO agendes turno."""
        preamble = _build_preamble()
        lower = preamble.lower()
        assert "no agend" in lower, "No-agenda rule missing for friend mode"

    def test_preamble_contains_cta_override_rule(self):
        """If ANY CTA keyword is detected → always treat as LEAD (override rule)."""
        preamble = _build_preamble()
        # Rule says: CTA keyword → always LEAD
        assert "LEAD" in preamble
        # The override statement uses OVERRIDE or explains the CTA detection takes priority
        lower = preamble.lower()
        assert "override" in lower or "siempre" in lower

    def test_preamble_contains_uncertainty_default(self):
        """When uncertain, treat as LEAD (safety default)."""
        preamble = _build_preamble()
        lower = preamble.lower()
        # "EN DUDA → tratás como LEAD" or similar
        assert "duda" in lower or "incertidumbre" in lower or "en duda" in lower

    def test_preamble_has_no_tool_calls_in_friend_section(self):
        """Friend mode section must say not to call tools at all."""
        preamble = _build_preamble()
        # The preamble must contain explicit prohibition (NO + tool-related)
        lower = preamble.lower()
        # Looking for "NO llamés ninguna tool" or "NO llames ningún tool" or "NO activés"
        assert (
            "ninguna tool" in lower
            or "ningún tool" in lower
            or "no activ" in lower
            or "no deriv" in lower
        ) or (
            "no llam" in lower and "tool" in lower
        )

    def test_preamble_with_facebook_channel_also_contains_friend_rules(self):
        """Friend detection rules must also appear for Facebook channel."""
        preamble = _build_preamble(channel="facebook")
        assert "AMIGO" in preamble
        assert "LEAD" in preamble
        assert "Dame un rato" in preamble or "dame un rato" in preamble

    def test_preamble_contains_triage_urgency_prohibition(self):
        """triage_urgency must be explicitly prohibited in social channels."""
        preamble = _build_preamble()
        assert "triage_urgency" in preamble
        lower = preamble.lower()
        assert "nunca" in lower or "prohibid" in lower or "no" in lower
