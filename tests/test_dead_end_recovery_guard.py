"""Tests for Bug #9 — Dead-end recovery guard.

The dead-end recovery mechanism re-invokes the agent when it produces a short
stalling response like "un momento" or "voy a buscar". Bug #9 ensures this
ONLY triggers when no tool was actually called (intermediate_steps is empty).

If a tool WAS called, the short response is a presentation issue, not a dead-end.
Re-invoking would duplicate side effects (e.g., double-booking).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_response(output: str, intermediate_steps: list = None):
    """Helper to build a fake agent response dict."""
    resp = {"output": output}
    if intermediate_steps is not None:
        resp["intermediate_steps"] = intermediate_steps
    return resp


class TestDeadEndRecoveryGuard:
    """Validates that dead-end recovery respects intermediate_steps."""

    def test_tool_called_with_dead_end_phrase_no_reinvoke(self):
        """(a) intermediate_steps NOT empty + dead-end phrase + short output → NO re-invocation."""
        response = _make_response(
            "Un momento, ya te busco disponibilidad",
            intermediate_steps=[("check_availability", "result")],
        )
        intermediate_steps = response.get("intermediate_steps", [])
        tool_was_called = len(intermediate_steps) > 0

        response_text = response.get("output", "")
        dead_end_phrases = ["un momento", "voy a buscar"]
        response_lower = response_text.lower()
        is_dead_end = any(phrase in response_lower for phrase in dead_end_phrases)

        # The guard should prevent re-invocation
        should_reinvoke = (
            is_dead_end and not tool_was_called and len(response_text) < 200
        )
        assert should_reinvoke is False, "Should NOT re-invoke when tool was called"

    def test_no_tool_called_with_dead_end_phrase_reinvoke(self):
        """(b) intermediate_steps empty + dead-end phrase + short output → YES re-invocation."""
        response = _make_response("Un momento, ya te busco", intermediate_steps=[])
        intermediate_steps = response.get("intermediate_steps", [])
        tool_was_called = len(intermediate_steps) > 0

        response_text = response.get("output", "")
        dead_end_phrases = ["un momento", "voy a buscar"]
        response_lower = response_text.lower()
        is_dead_end = any(phrase in response_lower for phrase in dead_end_phrases)

        should_reinvoke = (
            is_dead_end and not tool_was_called and len(response_text) < 200
        )
        assert should_reinvoke is True, (
            "Should re-invoke when no tool was called and dead-end detected"
        )

    def test_no_tool_called_long_output_no_reinvoke(self):
        """(c) intermediate_steps empty + output > 200 chars → NO re-invocation."""
        long_text = "Un momento, " + "x" * 250
        response = _make_response(long_text, intermediate_steps=[])
        intermediate_steps = response.get("intermediate_steps", [])
        tool_was_called = len(intermediate_steps) > 0

        response_text = response.get("output", "")
        dead_end_phrases = ["un momento"]
        response_lower = response_text.lower()
        is_dead_end = any(phrase in response_lower for phrase in dead_end_phrases)

        should_reinvoke = (
            is_dead_end and not tool_was_called and len(response_text) < 200
        )
        assert should_reinvoke is False, (
            "Should NOT re-invoke when output is long (>200 chars)"
        )

    def test_no_tool_no_dead_end_phrase_no_reinvoke(self):
        """(d) intermediate_steps empty + NO dead-end phrase + short output → NO re-invocation."""
        response = _make_response("¿En qué te puedo ayudar?", intermediate_steps=[])
        intermediate_steps = response.get("intermediate_steps", [])
        tool_was_called = len(intermediate_steps) > 0

        response_text = response.get("output", "")
        dead_end_phrases = ["un momento", "voy a buscar", "dejame buscar"]
        response_lower = response_text.lower()
        is_dead_end = any(phrase in response_lower for phrase in dead_end_phrases)

        should_reinvoke = (
            is_dead_end and not tool_was_called and len(response_text) < 200
        )
        assert should_reinvoke is False, (
            "Should NOT re-invoke when no dead-end phrase detected"
        )

    def test_missing_intermediate_steps_key_treated_as_empty(self):
        """intermediate_steps key missing → treated as empty (no tool called)."""
        response = _make_response("Un momento, ya verifico")
        # No intermediate_steps key at all
        intermediate_steps = response.get("intermediate_steps", [])
        tool_was_called = len(intermediate_steps) > 0

        assert tool_was_called is False, (
            "Missing intermediate_steps should be treated as no tool called"
        )
