"""
Tests for lead context accumulator module.

Verifies Redis-backed lead context persistence for pre-patient leads.
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
    0,
    os.path.join(
        os.path.dirname(__file__), "..", "orchestrator_service", "services"
    ),
)


class TestLeadContextHelpers:
    """Test helper functions."""

    def test_normalize_identifier_phone(self):
        from lead_context import _normalize_identifier

        assert _normalize_identifier("+5491112345678") == "5491112345678"
        assert _normalize_identifier("549-111-234-5678") == "5491112345678"

    def test_normalize_identifier_psid(self):
        from lead_context import _normalize_identifier

        # PSIDs are already digits
        assert _normalize_identifier("1234567890123456") == "1234567890123456"

    def test_build_key_format(self):
        from lead_context import _build_key

        key = _build_key(1, "+5491112345678")
        assert key == "lead_ctx:1:5491112345678"

    def test_build_key_tenant_scoped(self):
        from lead_context import _build_key

        k1 = _build_key(1, "5491112345678")
        k2 = _build_key(2, "5491112345678")
        assert k1 != k2


class TestMerge:
    """Test merge function."""

    @pytest.mark.asyncio
    async def test_merge_creates_hash(self):
        mock_r = MagicMock()
        mock_r.hmget = AsyncMock(return_value=[])
        mock_r.exists = AsyncMock(return_value=False)
        mock_r.hset = AsyncMock(return_value=True)
        mock_r.expire = AsyncMock(return_value=True)

        with patch("services.relay.get_redis", return_value=mock_r):
            from lead_context import merge

            await merge(1, "+5491112345678", {"treatment_name": "Implantes"})

        assert mock_r.hset.called
        call_kwargs = mock_r.hset.call_args
        mapping = call_kwargs.kwargs.get("mapping") or call_kwargs[1].get("mapping")
        assert mapping["treatment_name"] == "Implantes"
        assert "first_seen_at" in mapping
        assert "last_updated_at" in mapping

    @pytest.mark.asyncio
    async def test_merge_overwrites_treatment(self):
        mock_r = MagicMock()
        mock_r.exists = AsyncMock(return_value=True)
        mock_r.hset = AsyncMock(return_value=True)
        mock_r.expire = AsyncMock(return_value=True)

        with patch("services.relay.get_redis", return_value=mock_r):
            from lead_context import merge

            await merge(
                1, "5491112345678", {"treatment_name": "Cirugía Maxilofacial"}
            )

        call_kwargs = mock_r.hset.call_args
        mapping = call_kwargs.kwargs.get("mapping") or call_kwargs[1].get("mapping")
        assert mapping["treatment_name"] == "Cirugía Maxilofacial"

    @pytest.mark.asyncio
    async def test_merge_skip_if_exists(self):
        mock_r = MagicMock()
        mock_r.hmget = AsyncMock(return_value=["Ramiro"])  # first_name already set
        mock_r.exists = AsyncMock(return_value=True)
        mock_r.hset = AsyncMock(return_value=True)
        mock_r.expire = AsyncMock(return_value=True)

        with patch("services.relay.get_redis", return_value=mock_r):
            from lead_context import merge

            await merge(
                1,
                "5491112345678",
                {"first_name": "Juan", "last_name": "Perez"},
                skip_if_exists_fields=["first_name"],
            )

        call_kwargs = mock_r.hset.call_args
        mapping = call_kwargs.kwargs.get("mapping") or call_kwargs[1].get("mapping")
        # first_name should NOT be in mapping (already exists)
        assert "first_name" not in mapping
        # last_name SHOULD be written
        assert mapping["last_name"] == "Perez"

    @pytest.mark.asyncio
    async def test_merge_empty_fields_skipped(self):
        mock_r = MagicMock()

        with patch("services.relay.get_redis", return_value=mock_r):
            from lead_context import merge

            await merge(1, "5491112345678", {"treatment_name": "", "email": ""})

        # hset should not be called — all fields empty
        assert not mock_r.hset.called

    @pytest.mark.asyncio
    async def test_merge_resets_ttl(self):
        mock_r = MagicMock()
        mock_r.exists = AsyncMock(return_value=True)
        mock_r.hset = AsyncMock(return_value=True)
        mock_r.expire = AsyncMock(return_value=True)

        with patch("services.relay.get_redis", return_value=mock_r):
            from lead_context import merge, LEAD_CTX_TTL

            await merge(1, "5491112345678", {"channel": "whatsapp"})

        mock_r.expire.assert_called_once()
        ttl_arg = mock_r.expire.call_args[0][1]
        assert ttl_arg == LEAD_CTX_TTL


class TestGet:
    """Test get function."""

    @pytest.mark.asyncio
    async def test_get_returns_dict(self):
        mock_r = MagicMock()
        mock_r.hgetall = AsyncMock(
            return_value={"treatment_name": "Implantes", "channel": "whatsapp"}
        )

        with patch("services.relay.get_redis", return_value=mock_r):
            from lead_context import get

            result = await get(1, "+5491112345678")

        assert result["treatment_name"] == "Implantes"
        assert result["channel"] == "whatsapp"

    @pytest.mark.asyncio
    async def test_get_empty_on_missing(self):
        mock_r = MagicMock()
        mock_r.hgetall = AsyncMock(return_value={})

        with patch("services.relay.get_redis", return_value=mock_r):
            from lead_context import get

            result = await get(1, "5491100000000")

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_empty_on_redis_none(self):
        with patch("services.relay.get_redis", return_value=None):
            from lead_context import get

            result = await get(1, "5491112345678")

        assert result == {}


class TestClear:
    """Test clear function."""

    @pytest.mark.asyncio
    async def test_clear_deletes_hash(self):
        mock_r = MagicMock()
        mock_r.delete = AsyncMock(return_value=1)

        with patch("services.relay.get_redis", return_value=mock_r):
            from lead_context import clear

            await clear(1, "+5491112345678")

        mock_r.delete.assert_called_once()
        key_arg = mock_r.delete.call_args[0][0]
        assert key_arg == "lead_ctx:1:5491112345678"

    @pytest.mark.asyncio
    async def test_clear_silent_on_failure(self):
        mock_r = MagicMock()
        mock_r.delete = AsyncMock(side_effect=Exception("Redis down"))

        with patch("services.relay.get_redis", return_value=mock_r):
            from lead_context import clear

            # Should not raise
            await clear(1, "5491112345678")


class TestFormatForPrompt:
    """Test format_for_prompt function."""

    def test_format_with_data(self):
        from lead_context import format_for_prompt

        data = {
            "treatment_name": "Cirugía Maxilofacial",
            "professional_name": "Laura Delgado",
            "first_name": "Ramiro",
            "channel": "whatsapp",
            "last_updated_at": "2026-04-10T10:00:00",
        }
        result = format_for_prompt(data)

        assert "[CONTEXTO DE LEAD" in result
        assert "Cirugía Maxilofacial" in result
        assert "Laura Delgado" in result
        assert "Ramiro" in result
        assert "whatsapp" in result
        # Internal fields should NOT appear
        assert "last_updated_at" not in result

    def test_format_empty_returns_empty(self):
        from lead_context import format_for_prompt

        assert format_for_prompt({}) == ""
        assert format_for_prompt(None) == ""

    def test_format_only_internal_fields_returns_empty(self):
        from lead_context import format_for_prompt

        data = {
            "first_seen_at": "2026-04-10T10:00:00",
            "last_updated_at": "2026-04-10T10:00:00",
            "treatment_code": "CIRUGIA_MAX",
        }
        result = format_for_prompt(data)
        assert result == ""


class TestRedisFailureSilent:
    """Test that all operations fail silently when Redis is unavailable."""

    @pytest.mark.asyncio
    async def test_merge_silent_on_redis_exception(self):
        with patch(
            "services.relay.get_redis", side_effect=Exception("Connection refused")
        ):
            from lead_context import merge

            # Should not raise
            await merge(1, "5491112345678", {"treatment_name": "Implantes"})

    @pytest.mark.asyncio
    async def test_get_silent_on_redis_exception(self):
        with patch(
            "services.relay.get_redis", side_effect=Exception("Connection refused")
        ):
            from lead_context import get

            result = await get(1, "5491112345678")

        assert result == {}

    @pytest.mark.asyncio
    async def test_clear_silent_on_redis_exception(self):
        with patch(
            "services.relay.get_redis", side_effect=Exception("Connection refused")
        ):
            from lead_context import clear

            # Should not raise
            await clear(1, "5491112345678")
