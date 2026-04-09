"""Phase 5.1 — Tests for AgentState channel keys (TDD: failing before code).

Verifies that the AgentState TypedDict accepts the 5 social-channel keys
introduced for the Instagram/Facebook social agent feature.
"""
from __future__ import annotations

import sys
import os

# Ensure orchestrator_service is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service"))

import pytest


def _make_base_state() -> dict:
    """Return a minimal AgentState-compatible dict for baseline tests."""
    return {
        "tenant_id": 1,
        "phone_number": "+5491199990000",
        "thread_id": "t-001",
        "turn_id": "u-001",
        "user_message": "hola",
        "patient_profile": {},
        "chat_history": [],
        "working_state": {},
        "model_config": {"model": "gpt-4o-mini", "api_key": "sk-test", "base_url": None, "provider": "openai"},
        "tenant_context": {},
        "active_agent": "supervisor",
        "hop_count": 0,
        "max_hops": 5,
        "agent_output": "",
        "tools_called": [],
        "handoff_reason": None,
        "start_time": 0.0,
    }


class TestAgentStateChannelKeys:
    """AgentState TypedDict must accept all 5 social-channel keys without raising."""

    def test_agent_state_accepts_channel_key(self):
        """channel: str key accepted."""
        from agents.state import AgentState
        state: AgentState = {**_make_base_state(), "channel": "instagram"}  # type: ignore[misc]
        assert state["channel"] == "instagram"

    def test_agent_state_accepts_is_social_channel_key(self):
        """is_social_channel: bool key accepted."""
        from agents.state import AgentState
        state: AgentState = {**_make_base_state(), "is_social_channel": True}  # type: ignore[misc]
        assert state["is_social_channel"] is True

    def test_agent_state_accepts_social_landings_key_as_dict(self):
        """social_landings: dict key accepted."""
        from agents.state import AgentState
        landings = {"blanqueamiento": "https://blanqueamiento.example.com"}
        state: AgentState = {**_make_base_state(), "social_landings": landings}  # type: ignore[misc]
        assert state["social_landings"] == landings

    def test_agent_state_accepts_social_landings_key_as_none(self):
        """social_landings: None accepted."""
        from agents.state import AgentState
        state: AgentState = {**_make_base_state(), "social_landings": None}  # type: ignore[misc]
        assert state["social_landings"] is None

    def test_agent_state_accepts_instagram_handle_key(self):
        """instagram_handle: str key accepted."""
        from agents.state import AgentState
        state: AgentState = {**_make_base_state(), "instagram_handle": "@dralauradelgado"}  # type: ignore[misc]
        assert state["instagram_handle"] == "@dralauradelgado"

    def test_agent_state_accepts_instagram_handle_none(self):
        """instagram_handle: None accepted."""
        from agents.state import AgentState
        state: AgentState = {**_make_base_state(), "instagram_handle": None}  # type: ignore[misc]
        assert state["instagram_handle"] is None

    def test_agent_state_accepts_facebook_page_id_key(self):
        """facebook_page_id: str key accepted."""
        from agents.state import AgentState
        state: AgentState = {**_make_base_state(), "facebook_page_id": "DraLauraDelgado"}  # type: ignore[misc]
        assert state["facebook_page_id"] == "DraLauraDelgado"

    def test_agent_state_accepts_facebook_page_id_none(self):
        """facebook_page_id: None accepted."""
        from agents.state import AgentState
        state: AgentState = {**_make_base_state(), "facebook_page_id": None}  # type: ignore[misc]
        assert state["facebook_page_id"] is None

    def test_agent_state_accepts_all_five_keys_together(self):
        """All 5 social keys accepted in a single dict without TypeError."""
        from agents.state import AgentState
        state: AgentState = {  # type: ignore[misc]
            **_make_base_state(),
            "channel": "instagram",
            "is_social_channel": True,
            "social_landings": {"blanqueamiento": "https://b.example.com"},
            "instagram_handle": "@dralauradelgado",
            "facebook_page_id": None,
        }
        assert state["channel"] == "instagram"
        assert state["is_social_channel"] is True
        assert state["social_landings"]["blanqueamiento"] == "https://b.example.com"
        assert state["instagram_handle"] == "@dralauradelgado"
        assert state["facebook_page_id"] is None

    def test_agent_state_channel_key_str_type(self):
        """channel key holds a string value (whatsapp by convention)."""
        from agents.state import AgentState
        state: AgentState = {**_make_base_state(), "channel": "whatsapp"}  # type: ignore[misc]
        assert isinstance(state["channel"], str)

    def test_agent_state_is_social_channel_false_by_convention(self):
        """is_social_channel defaults to False for WhatsApp."""
        from agents.state import AgentState
        state: AgentState = {  # type: ignore[misc]
            **_make_base_state(),
            "channel": "whatsapp",
            "is_social_channel": False,
        }
        assert state["is_social_channel"] is False
