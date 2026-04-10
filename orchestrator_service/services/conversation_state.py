"""
Conversation State Machine Module.

Manages conversation state in Redis keyed by (tenant_id, phone_number).
Provides state transitions for the TORA booking flow: IDLE -> OFFERED_SLOTS -> SLOT_LOCKED -> BOOKED/PAYMENT_PENDING -> PAYMENT_VERIFIED.
"""

import json
import logging
from typing import Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)

# State constants
VALID_STATES = [
    "IDLE",
    "OFFERED_SLOTS",
    "SLOT_LOCKED",
    "BOOKED",
    "PAYMENT_PENDING",
    "PAYMENT_VERIFIED",
]
CONVSTATE_TTL = 1800  # 30 minutes
REDIS_KEY_PREFIX = "convstate"


class ConversationState(Enum):
    """Enum for conversation states."""

    IDLE = "IDLE"
    OFFERED_SLOTS = "OFFERED_SLOTS"
    SLOT_LOCKED = "SLOT_LOCKED"
    BOOKED = "BOOKED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_VERIFIED = "PAYMENT_VERIFIED"


def _get_redis_key(tenant_id: int, phone_number: str) -> str:
    """Generate Redis key for conversation state."""
    return f"{REDIS_KEY_PREFIX}:{tenant_id}:{phone_number}"


def _normalize_phone_for_key(phone: str) -> str:
    """Normalize phone for Redis key (only digits)."""
    import re

    return re.sub(r"\D", "", phone)


async def get_state(tenant_id: int, phone_number: str) -> Dict[str, Any]:
    """
    Get conversation state from Redis.

    Returns:
        Dict with 'state' key (defaults to 'IDLE' if not found or Redis fails).
    """
    try:
        from services.relay import get_redis

        r = get_redis()
        if r is None:
            logger.warning("[conversation_state] Redis not available, returning IDLE")
            return {"state": "IDLE"}

        # r is an async redis client
        phone_normalized = _normalize_phone_for_key(phone_number)
        key = _get_redis_key(tenant_id, phone_normalized)

        data = await r.get(key)
        if data is None:
            return {"state": "IDLE"}

        return json.loads(data)
    except Exception as e:
        logger.warning(f"[conversation_state] get_state failed: {e}")
        return {"state": "IDLE"}


async def set_state(
    tenant_id: int,
    phone_number: str,
    state: str,
    last_offered_slots: Optional[List[Dict]] = None,
    last_locked_slot: Optional[Dict] = None,
    last_booked_appointment_id: Optional[int] = None,
    offered_treatment: Optional[str] = None,
) -> None:
    """
    Set conversation state in Redis with TTL.

    Args:
        tenant_id: Tenant ID
        phone_number: Patient phone number
        state: New state (must be in VALID_STATES)
        last_offered_slots: List of slots offered (for OFFERED_SLOTS state)
        last_locked_slot: Slot that was locked (for SLOT_LOCKED state)
        last_booked_appointment_id: ID of booked appointment
        offered_treatment: Treatment name from check_availability (for OFFERED_SLOTS state)
    """
    if state not in VALID_STATES:
        raise ValueError(f"Invalid state: {state}. Must be one of {VALID_STATES}")

    try:
        from services.relay import get_redis

        r = get_redis()
        if r is None:
            logger.warning(
                "[conversation_state] Redis not available, skipping set_state"
            )
            return

        phone_normalized = _normalize_phone_for_key(phone_number)
        key = _get_redis_key(tenant_id, phone_normalized)

        state_data = {
            "state": state,
            "last_offered_slots": last_offered_slots,
            "last_locked_slot": last_locked_slot,
            "last_booked_appointment_id": last_booked_appointment_id,
            "offered_treatment": offered_treatment,
            "updated_at": __import__("datetime").datetime.now().isoformat(),
        }

        await r.setex(key, CONVSTATE_TTL, json.dumps(state_data))
        logger.info(f"[conversation_state] State set to {state} for {key}")

    except Exception as e:
        logger.warning(f"[conversation_state] set_state failed: {e}")
        # Fail silently - don't raise


async def transition(
    tenant_id: int, phone_number: str, expected_from: str, to: str, **fields
) -> bool:
    """
    Atomic check-and-set transition.

    Returns:
        True if transition succeeded, False if current state != expected_from
    """
    try:
        current = await get_state(tenant_id, phone_number)
        if current.get("state") != expected_from:
            return False

        await set_state(tenant_id, phone_number, to, **fields)
        return True
    except Exception as e:
        logger.warning(f"[conversation_state] transition failed: {e}")
        return False


async def reset(tenant_id: int, phone_number: str) -> None:
    """
    Reset conversation state to IDLE (delete Redis key).
    """
    try:
        from services.relay import get_redis

        r = get_redis()
        if r is None:
            logger.warning("[conversation_state] Redis not available, skipping reset")
            return

        phone_normalized = _normalize_phone_for_key(phone_number)
        key = _get_redis_key(tenant_id, phone_normalized)

        await r.delete(key)
        logger.info(f"[conversation_state] State reset for {key}")

    except Exception as e:
        logger.warning(f"[conversation_state] reset failed: {e}")
        # Fail silently
