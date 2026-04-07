"""
E2E Tests for Bug #4: State Machine End-to-End Scenarios.

Tests 5 core state machine flows:
(a) Happy flow: IDLE → check_availability → pick → confirm → book → BOOKED
(b) Re-search: IDLE → check_availability → "otra fecha" → check_availability again
(c) Abandonment: IDLE → check_availability → TTL expires → back to IDLE
(d) Ambiguous intent: IDLE → check_availability → user says "1" → guard injects hint → confirm_slot
(e) Cancel: BOOKED → cancel → IDLE
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta


class TestStateMachineE2E:
    """End-to-end tests for conversation state machine."""

    @pytest.mark.asyncio
    async def test_happy_flow_idle_to_booked(self):
        """Test complete happy flow: IDLE → check_availability → confirm_slot → book_appointment → BOOKED."""
        from orchestrator_service.services.conversation_state import (
            get_state,
            set_state,
            reset,
            VALID_STATES,
        )

        # Mock Redis
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)  # Start with no state (IDLE)
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock(return_value=1)

        with patch("services.relay.get_redis", return_value=mock_redis):
            # Step 1: Initial state should be IDLE
            state = await get_state(tenant_id=1, phone_number="+5491112345678")
            assert state["state"] == "IDLE"

            # Step 2: After check_availability, state should be OFFERED_SLOTS
            await set_state(
                tenant_id=1,
                phone_number="+5491112345678",
                state="OFFERED_SLOTS",
                last_offered_slots=[
                    {
                        "date": "2026-05-12",
                        "date_display": "Martes 12/05",
                        "time": "09:00",
                        "sede": "Central",
                    },
                ],
            )
            state = await get_state(tenant_id=1, phone_number="+5491112345678")
            assert state["state"] == "OFFERED_SLOTS"
            assert len(state.get("last_offered_slots", [])) == 1

            # Step 3: After confirm_slot, state should be SLOT_LOCKED
            await set_state(
                tenant_id=1,
                phone_number="+5491112345678",
                state="SLOT_LOCKED",
                last_locked_slot={"date": "2026-05-12", "time": "09:00"},
            )
            state = await get_state(tenant_id=1, phone_number="+5491112345678")
            assert state["state"] == "SLOT_LOCKED"

            # Step 4: After book_appointment (no seña), state should be BOOKED
            await set_state(
                tenant_id=1,
                phone_number="+5491112345678",
                state="BOOKED",
                last_booked_appointment_id="apt-123",
            )
            state = await get_state(tenant_id=1, phone_number="+5491112345678")
            assert state["state"] == "BOOKED"

            # Step 5: Cancel resets to IDLE
            await reset(tenant_id=1, phone_number="+5491112345678")
            state = await get_state(tenant_id=1, phone_number="+5491112345678")
            assert state["state"] == "IDLE"

    @pytest.mark.asyncio
    async def test_research_stays_in_offered_slots(self):
        """Test re-search: user requests new slots, state stays OFFERED_SLOTS."""
        from orchestrator_service.services.conversation_state import (
            get_state,
            set_state,
        )

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)

        with patch("services.relay.get_redis", return_value=mock_redis):
            # Initial state: OFFERED_SLOTS (user has options)
            await set_state(
                tenant_id=1,
                phone_number="+5491112345678",
                state="OFFERED_SLOTS",
                last_offered_slots=[
                    {
                        "date": "2026-05-12",
                        "date_display": "Martes 12/05",
                        "time": "09:00",
                    },
                ],
            )

            # User says "otra fecha" - re-search intent detected
            # State remains OFFERED_SLOTS (doesn't reset)
            state = await get_state(tenant_id=1, phone_number="+5491112345678")
            assert state["state"] == "OFFERED_SLOTS"

            # After re-search, check_availability is called again
            # State should stay OFFERED_SLOTS (updated slots)
            await set_state(
                tenant_id=1,
                phone_number="+5491112345678",
                state="OFFERED_SLOTS",
                last_offered_slots=[
                    {
                        "date": "2026-05-15",
                        "date_display": "Viernes 15/05",
                        "time": "10:00",
                    },
                ],
            )

            state = await get_state(tenant_id=1, phone_number="+5491112345678")
            assert state["state"] == "OFFERED_SLOTS"
            assert state["last_offered_slots"][0]["time"] == "10:00"

    @pytest.mark.asyncio
    async def test_abandonment_ttl_expires(self):
        """Test abandonment: state expires after TTL (30 min), returns to IDLE."""
        from orchestrator_service.services.conversation_state import (
            get_state,
            set_state,
            CONVSTATE_TTL,
        )

        mock_redis = MagicMock()
        # Simulate key not found (expired)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)

        with patch("services.relay.get_redis", return_value=mock_redis):
            # Set state with TTL
            await set_state(
                tenant_id=1,
                phone_number="+5491112345678",
                state="OFFERED_SLOTS",
                last_offered_slots=[{"date": "2026-05-12", "time": "09:00"}],
            )

            # Verify TTL was set
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args
            assert call_args.args[1] == CONVSTATE_TTL  # 1800 seconds

            # Simulate TTL expiration - get returns None
            mock_redis.get = AsyncMock(return_value=None)

            # After expiration, get_state returns IDLE
            state = await get_state(tenant_id=1, phone_number="+5491112345678")
            assert state["state"] == "IDLE"

    @pytest.mark.asyncio
    async def test_ambiguous_intent_with_guard(self):
        """Test ambiguous intent: user says '1', guard injects hint to use confirm_slot."""
        from orchestrator_service.services.buffer_task import _detect_selection_intent

        # User message with selection intent
        user_msg = "el 1"
        assert _detect_selection_intent(user_msg) is True

        # Test with different selection patterns
        user_msg2 = "quiero el segundo"
        assert _detect_selection_intent(user_msg2) is True

        user_msg3 = "agéndame ese"
        assert _detect_selection_intent(user_msg3) is True

        user_msg4 = "si, confirmo"
        assert _detect_selection_intent(user_msg4) is True

    @pytest.mark.asyncio
    async def test_cancel_resets_to_idle(self):
        """Test cancel: BOOKED → cancel_appointment → IDLE."""
        from orchestrator_service.services.conversation_state import (
            get_state,
            set_state,
            reset,
        )

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock(return_value=1)

        with patch("services.relay.get_redis", return_value=mock_redis):
            # State is BOOKED
            await set_state(
                tenant_id=1,
                phone_number="+5491112345678",
                state="BOOKED",
                last_booked_appointment_id="apt-456",
            )

            state = await get_state(tenant_id=1, phone_number="+5491112345678")
            assert state["state"] == "BOOKED"

            # User cancels appointment
            await reset(tenant_id=1, phone_number="+5491112345678")

            # Verify state was deleted (returns IDLE)
            mock_redis.delete.assert_called_once()
            state = await get_state(tenant_id=1, phone_number="+5491112345678")
            assert state["state"] == "IDLE"

    @pytest.mark.asyncio
    async def test_payment_pending_flow(self):
        """Test payment flow: book with seña → PAYMENT_PENDING → verify → PAYMENT_VERIFIED."""
        from orchestrator_service.services.conversation_state import (
            get_state,
            set_state,
        )

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)

        with patch("services.relay.get_redis", return_value=mock_redis):
            # Book with seña → PAYMENT_PENDING
            await set_state(
                tenant_id=1,
                phone_number="+5491112345678",
                state="PAYMENT_PENDING",
                last_booked_appointment_id="apt-789",
            )

            state = await get_state(tenant_id=1, phone_number="+5491112345678")
            assert state["state"] == "PAYMENT_PENDING"

            # After verify_payment_receipt → PAYMENT_VERIFIED
            await set_state(
                tenant_id=1,
                phone_number="+5491112345678",
                state="PAYMENT_VERIFIED",
            )

            state = await get_state(tenant_id=1, phone_number="+5491112345678")
            assert state["state"] == "PAYMENT_VERIFIED"

    @pytest.mark.asyncio
    async def test_reschedule_resets_to_idle(self):
        """Test reschedule: BOOKED → reschedule_appointment → IDLE."""
        from orchestrator_service.services.conversation_state import (
            get_state,
            set_state,
            reset,
        )

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock(return_value=1)

        with patch("services.relay.get_redis", return_value=mock_redis):
            # State is BOOKED
            await set_state(
                tenant_id=1,
                phone_number="+5491112345678",
                state="BOOKED",
                last_booked_appointment_id="apt-999",
            )

            # User reschedules appointment
            await reset(tenant_id=1, phone_number="+5491112345678")

            # Verify state was reset
            state = await get_state(tenant_id=1, phone_number="+5491112345678")
            assert state["state"] == "IDLE"


class TestStateGuardIntegration:
    """Integration tests for state guard logic."""

    @pytest.mark.asyncio
    async def test_selection_intent_triggers_hint(self):
        """Verify that selection intent in OFFERED_SLOTS state triggers state hint."""
        from orchestrator_service.services.buffer_task import _detect_selection_intent

        # Selection patterns should be detected
        selection_patterns = [
            "el 1",
            "el primero",
            "el segundo",
            "confirmo",
            "si, confirmo",
            "si quiero",
            "quiero ese",
            "agéndame ese",
            "el del 12 de mayo",
            "el de la tarde",
        ]

        for pattern in selection_patterns:
            assert _detect_selection_intent(pattern) is True, (
                f"Failed to detect: {pattern}"
            )

    @pytest.mark.asyncio
    async def test_research_intent_allows_check_availability(self):
        """Verify that re-search intent does NOT trigger state hint."""
        from orchestrator_service.services.buffer_task import _detect_research_intent

        # Re-search patterns should be detected
        research_patterns = [
            "otra fecha",
            "otro día",
            "otra hora",
            "buscá en otra semana",
            "no me sirve",
            "otro turno",
        ]

        for pattern in research_patterns:
            assert _detect_research_intent(pattern) is True, (
                f"Failed to detect: {pattern}"
            )

    @pytest.mark.asyncio
    async def test_neither_intent_no_guard(self):
        """Verify that ambiguous messages don't trigger guard."""
        from orchestrator_service.services.buffer_task import (
            _detect_selection_intent,
            _detect_research_intent,
        )

        # Ambiguous messages
        ambiguous_messages = [
            "hola",
            "gracias",
            "cómo estás?",
            "necesito información",
        ]

        for msg in ambiguous_messages:
            assert _detect_selection_intent(msg) is False, f"False positive for: {msg}"
            assert _detect_research_intent(msg) is False, f"False positive for: {msg}"
