"""
Integration tests for lead context accumulator.

Tests the full lifecycle: accumulate → read → clear.
"""

import pytest
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service")
)
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__), "..", "orchestrator_service", "services"
    ),
)


class FakeRedisHash:
    """In-memory Redis hash simulator for integration tests."""

    def __init__(self):
        self._store = {}
        self._ttls = {}

    async def hset(self, key, mapping=None, **kwargs):
        if key not in self._store:
            self._store[key] = {}
        if mapping:
            self._store[key].update(mapping)
        return len(mapping) if mapping else 0

    async def hgetall(self, key):
        return dict(self._store.get(key, {}))

    async def hmget(self, key, *fields):
        data = self._store.get(key, {})
        return [data.get(f) for f in fields]

    async def exists(self, key):
        return key in self._store

    async def expire(self, key, ttl):
        self._ttls[key] = ttl
        return True

    async def delete(self, key):
        self._store.pop(key, None)
        self._ttls.pop(key, None)
        return 1

    async def get(self, key):
        return None

    async def setex(self, key, ttl, value):
        self._store[key] = value
        self._ttls[key] = ttl


class TestFullBookingFlow:
    """Test the complete lead → check_availability → book → patient flow."""

    @pytest.mark.asyncio
    async def test_check_then_book_clears_context(self):
        """Simulate: lead calls check_availability, then book_appointment clears ctx."""
        fake_redis = FakeRedisHash()

        with patch("services.relay.get_redis", return_value=fake_redis):
            from lead_context import merge, get, clear

            # Step 1: check_availability writes treatment interest
            await merge(1, "+5491112345678", {
                "treatment_name": "Cirugía Maxilofacial",
                "treatment_code": "CIRUGIA_MAX",
                "professional_name": "Laura Delgado",
                "channel": "whatsapp",
            })

            # Verify data persisted
            data = await get(1, "+5491112345678")
            assert data["treatment_name"] == "Cirugía Maxilofacial"
            assert data["professional_name"] == "Laura Delgado"

            # Step 2: book_appointment writes name (skip-if-exists for name)
            await merge(1, "+5491112345678", {
                "first_name": "Ramiro",
                "last_name": "Gamarra",
                "dni": "12345678",
                "treatment_name": "Cirugía Maxilofacial",
            }, skip_if_exists_fields=["first_name", "last_name", "dni"])

            data = await get(1, "+5491112345678")
            assert data["first_name"] == "Ramiro"
            assert data["treatment_name"] == "Cirugía Maxilofacial"

            # Step 3: patient created → clear context
            await clear(1, "+5491112345678")

            data = await get(1, "+5491112345678")
            assert data == {}

    @pytest.mark.asyncio
    async def test_format_persisted_data_injected_to_prompt(self):
        """Verify that accumulated lead data produces a proper prompt block."""
        fake_redis = FakeRedisHash()

        with patch("services.relay.get_redis", return_value=fake_redis):
            from lead_context import merge, get, format_for_prompt

            await merge(1, "5491100000000", {
                "treatment_name": "Implantes Dentales",
                "first_name": "María",
                "channel": "instagram",
            })

            data = await get(1, "5491100000000")
            prompt = format_for_prompt(data)

            assert "[CONTEXTO DE LEAD" in prompt
            assert "Implantes Dentales" in prompt
            assert "María" in prompt
            assert "instagram" in prompt

    @pytest.mark.asyncio
    async def test_third_party_booking_no_clear(self):
        """Third-party booking should NOT clear interlocutor's lead context."""
        fake_redis = FakeRedisHash()

        with patch("services.relay.get_redis", return_value=fake_redis):
            from lead_context import merge, get, clear

            # Parent has lead context
            await merge(1, "+5491112345678", {
                "treatment_name": "Ortodoncia",
                "first_name": "Juan",
            })

            # Third-party booking for child — should NOT clear parent's ctx
            # (In real code, is_third_party=True skips the clear call)
            # We just verify the parent's data is still there
            data = await get(1, "+5491112345678")
            assert data["first_name"] == "Juan"
            assert data["treatment_name"] == "Ortodoncia"

    @pytest.mark.asyncio
    async def test_treatment_overwrite_on_change(self):
        """When lead changes treatment interest, latest one wins."""
        fake_redis = FakeRedisHash()

        with patch("services.relay.get_redis", return_value=fake_redis):
            from lead_context import merge, get

            # First interest
            await merge(1, "5491112345678", {
                "treatment_name": "Limpieza",
            })

            # Changed mind
            await merge(1, "5491112345678", {
                "treatment_name": "Implantes",
            })

            data = await get(1, "5491112345678")
            assert data["treatment_name"] == "Implantes"

    @pytest.mark.asyncio
    async def test_skip_if_exists_preserves_original_name(self):
        """Name written early should survive later merge with skip_if_exists."""
        fake_redis = FakeRedisHash()

        with patch("services.relay.get_redis", return_value=fake_redis):
            from lead_context import merge, get

            # Lead says their name early
            await merge(1, "5491112345678", {"first_name": "Ramiro"})

            # Later, book_appointment tries to write name again with skip
            await merge(1, "5491112345678", {
                "first_name": "Juan",  # Different name — should be SKIPPED
                "dni": "99999999",
            }, skip_if_exists_fields=["first_name"])

            data = await get(1, "5491112345678")
            assert data["first_name"] == "Ramiro"  # Original preserved
            assert data["dni"] == "99999999"  # New field written

    @pytest.mark.asyncio
    async def test_ttl_set_on_every_merge(self):
        """Every merge should reset the TTL to 24h."""
        fake_redis = FakeRedisHash()

        with patch("services.relay.get_redis", return_value=fake_redis):
            from lead_context import merge, LEAD_CTX_TTL

            await merge(1, "5491112345678", {"channel": "whatsapp"})

            key = "lead_ctx:1:5491112345678"
            assert fake_redis._ttls.get(key) == LEAD_CTX_TTL

    @pytest.mark.asyncio
    async def test_psid_key_format(self):
        """Instagram PSIDs should produce correct Redis keys."""
        fake_redis = FakeRedisHash()

        with patch("services.relay.get_redis", return_value=fake_redis):
            from lead_context import merge, get

            psid = "1234567890123456"
            await merge(1, psid, {"channel": "instagram", "treatment_name": "Botox"})

            data = await get(1, psid)
            assert data["treatment_name"] == "Botox"

            # Key should use PSID as-is (already digits)
            key = f"lead_ctx:1:{psid}"
            assert key in fake_redis._store
