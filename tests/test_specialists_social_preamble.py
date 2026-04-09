"""Phase 5.2 — Tests for social preamble injection in _with_tenant_blocks.

Verifies that when state["is_social_channel"] = True, the assembled prompt
contains the social preamble ("MODO REDES SOCIALES"), and when False/absent it
does not.

Import strategy: we import _with_tenant_blocks as a standalone function via
importlib so we can avoid the langchain/pydantic collision in conftest. The
function itself only depends on services.social_prompt, services.social_routes,
and agents.tenant_context — all of which are importable without live infra.
"""
from __future__ import annotations

import sys
import os
import types
import importlib
from unittest.mock import MagicMock, patch

# Add orchestrator_service to path before any imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service"))

import pytest


def _stub_langchain():
    """Stub out langchain/pydantic-heavy modules so specialists.py imports cleanly."""
    # We need a proper class (not MagicMock) for AgentExecutor and ChatOpenAI
    # so pydantic v1 doesn't choke when specialists.py is imported.

    class _FakeLLM:
        pass

    class _FakeAgentExecutor:
        def __init__(self, *args, **kwargs):
            pass
        async def ainvoke(self, *args, **kwargs):
            return {"output": "fake"}

    class _FakeChatOpenAI(_FakeLLM):
        def __init__(self, *args, **kwargs):
            pass

    # langchain.agents
    _la = types.ModuleType("langchain.agents")
    _la.AgentExecutor = _FakeAgentExecutor
    _la.create_openai_tools_agent = MagicMock(return_value=MagicMock())
    sys.modules["langchain.agents"] = _la

    # langchain_openai
    _lo = types.ModuleType("langchain_openai")
    _lo.ChatOpenAI = _FakeChatOpenAI
    sys.modules["langchain_openai"] = _lo

    # langchain_core.prompts
    class _FakePromptTemplate:
        @classmethod
        def from_messages(cls, *args, **kwargs):
            return cls()

    _lcp = types.ModuleType("langchain_core.prompts")
    _lcp.ChatPromptTemplate = _FakePromptTemplate
    _lcp.MessagesPlaceholder = MagicMock()
    sys.modules["langchain_core.prompts"] = _lcp
    sys.modules.setdefault("langchain_core", types.ModuleType("langchain_core"))


_stub_langchain()


def _get_with_tenant_blocks():
    """Import _with_tenant_blocks freshly, forcing module reload to apply stubs."""
    if "agents.specialists" in sys.modules:
        del sys.modules["agents.specialists"]
    if "agents.base" in sys.modules:
        del sys.modules["agents.base"]
    from agents.specialists import _with_tenant_blocks
    return _with_tenant_blocks


def _make_social_state(is_social: bool, channel: str = "instagram") -> dict:
    """Minimal AgentState dict for preamble injection tests."""
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
        "channel": channel,
        "is_social_channel": is_social,
        "social_landings": {"blanqueamiento": "https://blanqueamiento.example.com"} if is_social else None,
        "instagram_handle": "@dralauradelgado" if is_social else None,
        "facebook_page_id": None,
    }


class TestWithTenantBlocksSocialPreamble:
    """_with_tenant_blocks should prepend social preamble when is_social_channel=True."""

    def test_social_mode_injects_preamble_into_reception(self):
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=True)
        result = _with_tenant_blocks("base_prompt_text", state, "reception")
        assert "MODO REDES SOCIALES" in result

    def test_social_mode_injects_preamble_into_booking(self):
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=True)
        result = _with_tenant_blocks("base_prompt_text", state, "booking")
        assert "MODO REDES SOCIALES" in result

    def test_social_mode_injects_preamble_into_triage(self):
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=True)
        result = _with_tenant_blocks("base_prompt_text", state, "triage")
        assert "MODO REDES SOCIALES" in result

    def test_social_mode_injects_preamble_into_billing(self):
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=True)
        result = _with_tenant_blocks("base_prompt_text", state, "billing")
        assert "MODO REDES SOCIALES" in result

    def test_social_mode_injects_preamble_into_anamnesis(self):
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=True)
        result = _with_tenant_blocks("base_prompt_text", state, "anamnesis")
        assert "MODO REDES SOCIALES" in result

    def test_social_mode_injects_preamble_into_handoff(self):
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=True)
        result = _with_tenant_blocks("base_prompt_text", state, "handoff")
        assert "MODO REDES SOCIALES" in result

    def test_preamble_positioned_before_base_prompt(self):
        """Social preamble must come BEFORE the base prompt text."""
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=True)
        result = _with_tenant_blocks("BASE_PROMPT_MARKER", state, "reception")
        preamble_pos = result.index("MODO REDES SOCIALES")
        base_pos = result.index("BASE_PROMPT_MARKER")
        assert preamble_pos < base_pos, (
            "Social preamble must appear BEFORE the base prompt"
        )

    def test_preamble_contains_amigo_lead_keywords(self):
        """Preamble from build_social_preamble contains AMIGO and LEAD for friend detection."""
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=True)
        result = _with_tenant_blocks("base", state, "reception")
        assert "AMIGO" in result
        assert "LEAD" in result

    def test_no_preamble_when_not_social_reception(self):
        """When is_social_channel=False, preamble is absent."""
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=False)
        result = _with_tenant_blocks("base_prompt_text", state, "reception")
        assert "MODO REDES SOCIALES" not in result

    def test_no_preamble_when_not_social_booking(self):
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=False)
        result = _with_tenant_blocks("base_prompt_text", state, "booking")
        assert "MODO REDES SOCIALES" not in result

    def test_no_preamble_when_not_social_triage(self):
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=False)
        result = _with_tenant_blocks("base_prompt_text", state, "triage")
        assert "MODO REDES SOCIALES" not in result

    def test_no_preamble_when_not_social_billing(self):
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=False)
        result = _with_tenant_blocks("base_prompt_text", state, "billing")
        assert "MODO REDES SOCIALES" not in result

    def test_no_preamble_when_not_social_anamnesis(self):
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=False)
        result = _with_tenant_blocks("base_prompt_text", state, "anamnesis")
        assert "MODO REDES SOCIALES" not in result

    def test_no_preamble_when_not_social_handoff(self):
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=False)
        result = _with_tenant_blocks("base_prompt_text", state, "handoff")
        assert "MODO REDES SOCIALES" not in result

    def test_no_preamble_when_key_missing_from_state(self):
        """When is_social_channel key is absent, no preamble injected."""
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=False)
        del state["is_social_channel"]
        result = _with_tenant_blocks("base_prompt_text", state, "reception")
        assert "MODO REDES SOCIALES" not in result

    def test_facebook_channel_injects_preamble(self):
        """Facebook channel also triggers preamble."""
        _with_tenant_blocks = _get_with_tenant_blocks()
        state = _make_social_state(is_social=True, channel="facebook")
        result = _with_tenant_blocks("base", state, "reception")
        assert "MODO REDES SOCIALES" in result

    def test_build_social_preamble_importable(self):
        """build_social_preamble is importable from services.social_prompt."""
        from services.social_prompt import build_social_preamble
        assert callable(build_social_preamble)

    def test_cta_routes_importable(self):
        """CTA_ROUTES is importable from services.social_routes."""
        from services.social_routes import CTA_ROUTES
        assert isinstance(CTA_ROUTES, list)
        assert len(CTA_ROUTES) > 0
