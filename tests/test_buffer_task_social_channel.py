"""Phase 6.1 — Tests for compute_social_context helper in buffer_task.

Tests the `compute_social_context(channel_type, tenant_row)` helper function
which encapsulates the social-channel detection logic independently of the
full buffer_task machinery (no DB, no Redis, no AsyncMock maze).

TDD: written BEFORE the function is implemented in buffer_task.py.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service"))

import pytest


def _get_compute_social_context():
    """Freshly import compute_social_context from services.buffer_task."""
    if "services.buffer_task" in sys.modules:
        del sys.modules["services.buffer_task"]
    from services.buffer_task import compute_social_context
    return compute_social_context


def _make_tenant_row(
    *,
    social_ig_active: bool = False,
    social_landings: object = None,
    instagram_handle: object = None,
    facebook_page_id: object = None,
) -> dict:
    """Return a minimal tenant dict as asyncpg would return it."""
    return {
        "social_ig_active": social_ig_active,
        "social_landings": social_landings,
        "instagram_handle": instagram_handle,
        "facebook_page_id": facebook_page_id,
    }


class TestComputeSocialContext:
    """Unit tests for compute_social_context(channel_type, tenant_row) -> dict."""

    # ---- Instagram, flag enabled ----

    def test_ig_message_sets_is_social_channel_true_when_flag_enabled(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=True, instagram_handle="@dra")
        result = fn("instagram", tenant)
        assert result["is_social_channel"] is True

    def test_ig_message_channel_key_is_instagram(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=True)
        result = fn("instagram", tenant)
        assert result["channel"] == "instagram"

    def test_ig_message_instagram_handle_propagated(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=True, instagram_handle="@dralauradelgado")
        result = fn("instagram", tenant)
        assert result["instagram_handle"] == "@dralauradelgado"

    def test_ig_message_social_landings_propagated(self):
        fn = _get_compute_social_context()
        landings = {"blanqueamiento": "https://b.example.com"}
        tenant = _make_tenant_row(social_ig_active=True, social_landings=landings)
        result = fn("instagram", tenant)
        assert result["social_landings"] == landings

    # ---- Instagram, flag disabled ----

    def test_ig_message_sets_is_social_channel_false_when_flag_disabled(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=False)
        result = fn("instagram", tenant)
        assert result["is_social_channel"] is False

    def test_ig_message_social_landings_none_when_flag_disabled(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=False, social_landings={"k": "v"})
        result = fn("instagram", tenant)
        assert result["social_landings"] is None

    def test_ig_message_instagram_handle_none_when_flag_disabled(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=False, instagram_handle="@dra")
        result = fn("instagram", tenant)
        assert result["instagram_handle"] is None

    # ---- Facebook, flag enabled ----

    def test_fb_message_with_flag_sets_social_true(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=True, facebook_page_id="DraLaura")
        result = fn("facebook", tenant)
        assert result["is_social_channel"] is True

    def test_fb_message_channel_key_is_facebook(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=True)
        result = fn("facebook", tenant)
        assert result["channel"] == "facebook"

    def test_fb_message_facebook_page_id_propagated(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=True, facebook_page_id="DraLaura")
        result = fn("facebook", tenant)
        assert result["facebook_page_id"] == "DraLaura"

    # ---- WhatsApp — never social regardless of flag ----

    def test_whatsapp_always_not_social_regardless_of_flag(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=True)
        result = fn("whatsapp", tenant)
        assert result["is_social_channel"] is False

    def test_whatsapp_channel_key_is_whatsapp(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=True)
        result = fn("whatsapp", tenant)
        assert result["channel"] == "whatsapp"

    def test_whatsapp_social_landings_none(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=True, social_landings={"k": "v"})
        result = fn("whatsapp", tenant)
        assert result["social_landings"] is None

    # ---- None / empty channel ----

    def test_none_channel_defaults_to_whatsapp(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=True)
        result = fn(None, tenant)
        assert result["channel"] == "whatsapp"
        assert result["is_social_channel"] is False

    def test_empty_string_channel_defaults_to_whatsapp(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=True)
        result = fn("", tenant)
        assert result["channel"] == "whatsapp"

    # ---- Return shape: all five keys always present ----

    def test_result_always_has_five_keys(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row()
        result = fn("whatsapp", tenant)
        expected_keys = {"channel", "is_social_channel", "social_landings", "instagram_handle", "facebook_page_id"}
        assert expected_keys.issubset(result.keys())

    def test_result_has_five_keys_when_social_active(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=True)
        result = fn("instagram", tenant)
        expected_keys = {"channel", "is_social_channel", "social_landings", "instagram_handle", "facebook_page_id"}
        assert expected_keys.issubset(result.keys())

    # ---- JSONB string handling (asyncpg gotcha from CLAUDE.md) ----

    def test_social_landings_string_is_parsed_to_dict(self):
        """asyncpg may return JSONB as a raw string — should be parsed defensively."""
        import json
        fn = _get_compute_social_context()
        landings_str = json.dumps({"blanqueamiento": "https://b.example.com"})
        tenant = _make_tenant_row(social_ig_active=True, social_landings=landings_str)
        result = fn("instagram", tenant)
        assert isinstance(result["social_landings"], dict)
        assert result["social_landings"]["blanqueamiento"] == "https://b.example.com"

    # ---- Chatwoot channel — not a social channel ----

    def test_chatwoot_channel_not_social(self):
        fn = _get_compute_social_context()
        tenant = _make_tenant_row(social_ig_active=True)
        result = fn("chatwoot", tenant)
        assert result["is_social_channel"] is False

    # ---- Tenant row with missing social fields (backward compat) ----

    def test_missing_social_ig_active_defaults_to_false(self):
        fn = _get_compute_social_context()
        tenant = {}  # completely empty tenant row
        result = fn("instagram", tenant)
        assert result["is_social_channel"] is False

    def test_missing_instagram_handle_stays_none(self):
        fn = _get_compute_social_context()
        tenant = {"social_ig_active": True}
        result = fn("instagram", tenant)
        assert result["instagram_handle"] is None
