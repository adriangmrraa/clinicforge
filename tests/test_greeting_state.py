"""Tests for Bug #8 — Greeting state via Redis flag."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# greeting_state.py imports get_redis lazily from services.relay inside each function.
# Correct patch target is the source module: services.relay.get_redis
_PATCH_TARGET = "services.relay.get_redis"


@pytest.mark.asyncio
async def test_has_greeted_returns_false_when_key_missing():
    """has_greeted returns False when Redis key doesn't exist."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    with patch(_PATCH_TARGET, return_value=mock_redis):
        from services.greeting_state import has_greeted

        result = await has_greeted(1, "+5491155555555")
        assert result is False


@pytest.mark.asyncio
async def test_has_greeted_returns_true_after_mark():
    """has_greeted returns True after mark_greeted was called."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="1")
    mock_redis.setex = AsyncMock()
    with patch(_PATCH_TARGET, return_value=mock_redis):
        from services.greeting_state import has_greeted, mark_greeted

        await mark_greeted(1, "+5491155555555")
        mock_redis.setex.assert_called_once_with("greet:1:+5491155555555", 14400, "1")
        result = await has_greeted(1, "+5491155555555")
        assert result is True


@pytest.mark.asyncio
async def test_has_greeted_returns_false_on_redis_error():
    """Fallback: returns False when Redis throws exception."""
    with patch(_PATCH_TARGET, side_effect=Exception("Redis down")):
        from services.greeting_state import has_greeted

        result = await has_greeted(1, "+5491155555555")
        assert result is False


@pytest.mark.asyncio
async def test_mark_greeted_silent_on_redis_error():
    """mark_greeted doesn't raise when Redis fails."""
    with patch(_PATCH_TARGET, side_effect=Exception("Redis down")):
        from services.greeting_state import mark_greeted

        # Should not raise
        await mark_greeted(1, "+5491155555555")


@pytest.mark.asyncio
async def test_has_greeted_returns_false_when_redis_is_none():
    """has_greeted returns False when get_redis returns None."""
    with patch(_PATCH_TARGET, return_value=None):
        from services.greeting_state import has_greeted

        result = await has_greeted(1, "+5491155555555")
        assert result is False


@pytest.mark.asyncio
async def test_different_tenants_independent():
    """Keys for different tenants are independent."""
    mock_redis = AsyncMock()

    # Simulate: tenant 1 greeted, tenant 2 not
    async def mock_get(key):
        if key == "greet:1:+5491155555555":
            return "1"
        return None

    mock_redis.get = AsyncMock(side_effect=mock_get)
    with patch(_PATCH_TARGET, return_value=mock_redis):
        from services.greeting_state import has_greeted

        assert await has_greeted(1, "+5491155555555") is True
        assert await has_greeted(2, "+5491155555555") is False
