"""
Tests for conversation state module.

Bug #4: Test cases for conversation state machine in Redis.
"""

import pytest
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

# Add orchestrator_service to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service")
)
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service", "services")
)

# Create mock before importing
mock_redis_instance = MagicMock()


def mock_get_redis():
    """Returns mock Redis instance."""
    return mock_redis_instance


class TestConversationState:
    """Test conversation state machine functions."""

    @pytest.mark.asyncio
    async def test_get_state_not_found_returns_idle(self):
        """Case 1: Get state when not found - returns IDLE"""
        # Setup fresh mock
        mock_r = MagicMock()
        mock_r.get = AsyncMock(return_value=None)

        with patch("services.relay.get_redis", return_value=mock_r):
            from conversation_state import get_state

            result = await get_state(1, "5491112345678")

        assert result["state"] == "IDLE"

    @pytest.mark.asyncio
    async def test_set_and_get_roundtrip(self):
        """Case 2: Set state then get - returns same state"""
        mock_r = MagicMock()
        mock_r.setex = AsyncMock(return_value=True)
        mock_r.get = AsyncMock(
            return_value=b'{"state": "OFFERED_SLOTS", "last_offered_slots": [], "last_locked_slot": null, "updated_at": "2026-01-01T00:00:00"}'
        )

        with patch("services.relay.get_redis", return_value=mock_r):
            from conversation_state import set_state, get_state

            await set_state(
                1,
                "5491112345678",
                "OFFERED_SLOTS",
                last_offered_slots=[{"date": "2026-05-12", "time": "10:00"}],
            )
            result = await get_state(1, "5491112345678")

        assert result["state"] == "OFFERED_SLOTS"

    @pytest.mark.asyncio
    async def test_transition_happy(self):
        """Case 3: Transition from expected state - succeeds"""
        mock_r = MagicMock()
        mock_r.get = AsyncMock(return_value=b'{"state": "OFFERED_SLOTS"}')
        mock_r.setex = AsyncMock(return_value=True)

        with patch("services.relay.get_redis", return_value=mock_r):
            from conversation_state import transition

            result = await transition(
                1,
                "5491112345678",
                "OFFERED_SLOTS",
                "SLOT_LOCKED",
                last_locked_slot={"date": "2026-05-12", "time": "10:00"},
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_transition_conflict_returns_false(self):
        """Case 4: Transition from wrong state - returns False"""
        mock_r = MagicMock()
        mock_r.get = AsyncMock(return_value=b'{"state": "IDLE"}')

        with patch("services.relay.get_redis", return_value=mock_r):
            from conversation_state import transition

            result = await transition(
                1, "5491112345678", "OFFERED_SLOTS", "SLOT_LOCKED"
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_reset_deletes_key(self):
        """Case 5: Reset deletes the Redis key"""
        mock_r = MagicMock()
        mock_r.delete = AsyncMock(return_value=1)

        with patch("services.relay.get_redis", return_value=mock_r):
            from conversation_state import reset

            await reset(1, "5491112345678")

        assert mock_r.delete.called

    @pytest.mark.asyncio
    async def test_redis_fail_on_get_returns_idle(self):
        """Case 6: Redis fail on get - returns IDLE gracefully"""
        with patch("services.relay.get_redis", side_effect=Exception("Redis down")):
            from conversation_state import get_state

            result = await get_state(1, "5491112345678")

        assert result["state"] == "IDLE"

    @pytest.mark.asyncio
    async def test_redis_fail_on_set_warns_no_raise(self):
        """Case 7: Redis fail on set - logs warning, no exception"""
        mock_r = MagicMock()
        mock_r.setex = AsyncMock(side_effect=Exception("Redis down"))

        with patch("services.relay.get_redis", return_value=mock_r):
            from conversation_state import set_state

            # Should not raise
            await set_state(1, "5491112345678", "OFFERED_SLOTS")

    def test_invalid_state_raises_value_error(self):
        """Case 8: Invalid state name - raises ValueError"""
        import asyncio
        from conversation_state import set_state

        async def test():
            with pytest.raises(ValueError):
                await set_state(1, "5491112345678", "INVALID_STATE")

        asyncio.run(test())


class TestHelperFunctions:
    """Test helper functions."""

    def test_normalize_phone_for_key(self):
        """Normalize phone for Redis key"""
        from conversation_state import _normalize_phone_for_key

        assert _normalize_phone_for_key("+5491112345678") == "5491112345678"
        assert _normalize_phone_for_key("5491112345678") == "5491112345678"
        assert _normalize_phone_for_key("0111-234-5678") == "01112345678"

    def test_get_redis_key_format(self):
        """Redis key format is correct"""
        from conversation_state import _get_redis_key

        key = _get_redis_key(1, "5491112345678")
        assert key == "convstate:1:5491112345678"
