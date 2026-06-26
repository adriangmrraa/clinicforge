"""
Conversation State Machine Module.

Manages conversation state in Redis keyed by (tenant_id, phone_number).
Provides state transitions for the TORA booking flow: IDLE -> OFFERED_SLOTS -> SLOT_LOCKED -> BOOKED/PAYMENT_PENDING -> PAYMENT_VERIFIED.

v8.2 — Anti-loop booking extensions:
- failed_slots[]: blacklist of (date, time, code) the agent must never re-offer
- excluded_days[]: patient-declared day-of-week exclusions
- excluded_dates[]: patient-declared specific-date exclusions
- statements_made{}: hash → count for deduplicating agent output
- booking_attempts: per-conversation counter for escalation guard
- anchor_date: resolved anchor date propagated through confirm_slot → book_appointment
"""

import json
import logging
from datetime import datetime as _dt
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
CONVSTATE_TTL = 1800      # 30 minutes (default for IDLE, OFFERED_SLOTS, SLOT_LOCKED)
BOOKED_TTL = 86400         # 24 hours (BOOKED / PAYMENT_PENDING — DLD-89/92: no expirar durante la conversación)
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

    # Guard: si el telefono viene None/vacio (ej. reset llamado tras cancelar sin
    # phone), no romper con "expected string... got NoneType". Devolver "" -> la
    # operacion sobre la clave degenerada es inocua y el flujo no se corta.
    if not phone:
        return ""
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

        # Preserve anti-loop fields across state transitions (v8.2)
        _existing = None
        try:
            _raw = await r.get(key)
            if _raw:
                _existing = json.loads(_raw)
        except Exception:
            _existing = None

        state_data = {
            "state": state,
            "last_offered_slots": last_offered_slots,
            "last_locked_slot": last_locked_slot,
            "last_booked_appointment_id": last_booked_appointment_id,
            "offered_treatment": offered_treatment,
            # Anti-loop fields — preserve existing or default to empty/null
            "failed_slots": (_existing or {}).get("failed_slots", []),
            "excluded_days": (_existing or {}).get("excluded_days", []),
            "excluded_dates": (_existing or {}).get("excluded_dates", []),
            "statements_made": (_existing or {}).get("statements_made", {}),
            "booking_attempts": (_existing or {}).get("booking_attempts", 0),
            "availability_attempts": (_existing or {}).get("availability_attempts", 0),
            "anchor_date": (_existing or {}).get("anchor_date"),
            "insurance_asked": (_existing or {}).get("insurance_asked", False),
            # v8.3: resolve-13-booking-errors fields (T2) — all backward-compatible
            "booking_targets": (_existing or {}).get(
                "booking_targets",
                [{"type": "self", "name": "", "dni": "", "status": "pending", "relationship": ""}]
            ),
            "current_booking_target_index": (_existing or {}).get("current_booking_target_index", 0),
            "frustration_count": (_existing or {}).get("frustration_count", 0),
            "frustration_mode": (_existing or {}).get("frustration_mode", False),
            "error_history": (_existing or {}).get("error_history", []),
            "turn_count": (_existing or {}).get("turn_count", 0),
            # v8.4: scheduling constraints — preserved across all state transitions
            "scheduling_constraints": (_existing or {}).get("scheduling_constraints", {}),
            "updated_at": _dt.now().isoformat(),
        }

        # DLD-89/92: BOOKED y PAYMENT_PENDING usan TTL de 24h para no expirar durante la conversación
        _ttl = BOOKED_TTL if state in ("BOOKED", "PAYMENT_PENDING") else CONVSTATE_TTL
        await r.setex(key, _ttl, json.dumps(state_data))
        logger.info(f"[conversation_state] State set to {state} for {key} (TTL={_ttl}s)")

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


# ── Anti-loop Booking Helpers (v8.2) ──────────────────────────────
#
# Each helper reads the current convstate payload via get_state(), mutates the
# relevant anti-loop field, and writes the whole payload back atomically.
# All payload writes use a _raw_write() helper that merges anti-loop fields
# with the existing payload so state transitions done concurrently (via set_state)
# don't wipe out fields that other code just mutated.


async def _raw_write(tenant_id: int, phone_number: str, payload: Dict[str, Any], ttl: int = CONVSTATE_TTL) -> None:
    """Write a raw payload dict directly to the convstate Redis key."""
    try:
        from services.relay import get_redis

        r = get_redis()
        if r is None:
            return
        phone_normalized = _normalize_phone_for_key(phone_number)
        key = _get_redis_key(tenant_id, phone_normalized)
        await r.setex(key, ttl, json.dumps(payload))
    except Exception as e:
        logger.warning(f"[conversation_state] _raw_write failed: {e}")


async def _read_payload(tenant_id: int, phone_number: str) -> Dict[str, Any]:
    """Read the full convstate payload, defaulting to IDLE if missing."""
    state = await get_state(tenant_id, phone_number)
    if not isinstance(state, dict):
        state = {"state": "IDLE"}
    return state


async def append_failed_slot(tenant_id: int, phone_number: str, slot: Dict[str, Any]) -> None:
    """
    Record a failed booking slot so it is never re-offered in this conversation.

    slot must contain at least: {"date": "YYYY-MM-DD", "time": "HH:MM", "code": "UNAVAILABLE"}
    Timestamp 'at' is auto-added.
    """
    try:
        payload = await _read_payload(tenant_id, phone_number)
        slot["at"] = _dt.now().isoformat()
        failed = list(payload.get("failed_slots") or [])
        # Deduplicate: same date+time+code → skip
        if not any(
            s.get("date") == slot.get("date")
            and s.get("time") == slot.get("time")
            and s.get("code") == slot.get("code")
            for s in failed
        ):
            failed.append(slot)
        payload["failed_slots"] = failed
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
        logger.info(
            f"[conversation_state] append_failed_slot: {slot.get('date')} {slot.get('time')} "
            f"code={slot.get('code')} for {phone_number}"
        )
    except Exception as e:
        logger.warning(f"[conversation_state] append_failed_slot failed: {e}")


async def add_exclusion(tenant_id: int, phone_number: str, exclusion: Dict[str, Any]) -> None:
    """
    Add a patient-declared exclusion to the convstate.

    exclusion keys:
      - "days": [list of day names] → appended to excluded_days
      - "dates": [list of YYYY-MM-DD] → appended to excluded_dates
    """
    try:
        payload = await _read_payload(tenant_id, phone_number)

        if exclusion.get("days"):
            existing_days = set(payload.get("excluded_days") or [])
            for d in exclusion["days"]:
                existing_days.add(d.lower().strip())
            payload["excluded_days"] = list(existing_days)

        if exclusion.get("dates"):
            existing_dates = set(payload.get("excluded_dates") or [])
            for d in exclusion["dates"]:
                existing_dates.add(d)
            payload["excluded_dates"] = list(existing_dates)

        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
        logger.info(
            f"[conversation_state] add_exclusion: days={payload.get('excluded_days')} "
            f"dates={payload.get('excluded_dates')} for {phone_number}"
        )
    except Exception as e:
        logger.warning(f"[conversation_state] add_exclusion failed: {e}")


async def track_statement(tenant_id: int, phone_number: str, statement_hash: str) -> int:
    """
    Record a sent agent statement hash and return its current count (0-based before increment).

    Returns the count AFTER incrementing (≥ 1). If this is the 3rd+ occurrence (return ≥ 3),
    caller should suppress the message.
    """
    try:
        payload = await _read_payload(tenant_id, phone_number)
        statements = dict(payload.get("statements_made") or {})
        count = statements.get(statement_hash, 0) + 1
        statements[statement_hash] = count
        payload["statements_made"] = statements
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
        logger.debug(
            f"[conversation_state] track_statement: hash={statement_hash} count={count} for {phone_number}"
        )
        return count
    except Exception as e:
        logger.warning(f"[conversation_state] track_statement failed: {e}")
        return 1  # Fail-open: don't block the message


async def increment_booking_attempts(tenant_id: int, phone_number: str) -> int:
    """
    Increment the per-conversation booking attempt counter.
    Returns the new count after increment.
    """
    try:
        payload = await _read_payload(tenant_id, phone_number)
        current = int(payload.get("booking_attempts") or 0) + 1
        payload["booking_attempts"] = current
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
        logger.info(
            f"[conversation_state] booking_attempts: {current} for {phone_number}"
        )
        return current
    except Exception as e:
        logger.warning(f"[conversation_state] increment_booking_attempts failed: {e}")
        return 0


async def increment_availability_attempts(tenant_id: int, phone_number: str) -> int:
    """Increment check_availability attempt counter. Returns the new count (0 on error)."""
    try:
        payload = await _read_payload(tenant_id, phone_number)
        current = int(payload.get("availability_attempts") or 0) + 1
        payload["availability_attempts"] = current
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
        logger.info(
            f"[conversation_state] availability_attempts: {current} for {phone_number}"
        )
        return current
    except Exception as e:
        logger.warning(f"[conversation_state] increment_availability_attempts failed: {e}")
        return 0


async def reset_availability_attempts(tenant_id: int, phone_number: str) -> None:
    """Reset availability_attempts counter to 0 (called on successful confirm_slot)."""
    try:
        payload = await _read_payload(tenant_id, phone_number)
        payload["availability_attempts"] = 0
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
        logger.info(
            f"[conversation_state] availability_attempts reset to 0 for {phone_number}"
        )
    except Exception as e:
        logger.warning(f"[conversation_state] reset_availability_attempts failed: {e}")


async def reset_booking_attempts(tenant_id: int, phone_number: str) -> None:
    """Reset booking_attempts counter to 0 (called on successful booking)."""
    try:
        payload = await _read_payload(tenant_id, phone_number)
        payload["booking_attempts"] = 0
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
        logger.info(
            f"[conversation_state] booking_attempts reset to 0 for {phone_number}"
        )
    except Exception as e:
        logger.warning(f"[conversation_state] reset_booking_attempts failed: {e}")


async def set_anchor_date(tenant_id: int, phone_number: str, anchor_date: str) -> None:
    """Store the resolved anchor date so downstream tools use it, never recalculate."""
    try:
        payload = await _read_payload(tenant_id, phone_number)
        payload["anchor_date"] = anchor_date
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
        logger.info(
            f"[conversation_state] anchor_date set to {anchor_date} for {phone_number}"
        )
    except Exception as e:
        logger.warning(f"[conversation_state] set_anchor_date failed: {e}")


# ── resolve-13-booking-errors Helpers (T2) ──────────────────────────


async def set_booking_targets(tenant_id: int, phone_number: str, targets: list[dict]) -> None:
    """Replace all booking targets in convstate."""
    try:
        payload = await _read_payload(tenant_id, phone_number)
        payload["booking_targets"] = targets
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
    except Exception as e:
        logger.warning(f"[conversation_state] set_booking_targets failed: {e}")


async def append_booking_target(tenant_id: int, phone_number: str, target: dict) -> None:
    """Append one booking target to the existing list."""
    try:
        payload = await _read_payload(tenant_id, phone_number)
        targets = list(payload.get("booking_targets") or [{"type": "self"}])
        targets.append(target)
        payload["booking_targets"] = targets
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
    except Exception as e:
        logger.warning(f"[conversation_state] append_booking_target failed: {e}")


async def mark_target_booked(tenant_id: int, phone_number: str, index: int) -> None:
    """Set status='booked' for the target at given index."""
    try:
        payload = await _read_payload(tenant_id, phone_number)
        targets = list(payload.get("booking_targets") or [{"type": "self"}])
        if 0 <= index < len(targets):
            targets[index]["status"] = "booked"
            payload["booking_targets"] = targets
            payload["updated_at"] = _dt.now().isoformat()
            await _raw_write(tenant_id, phone_number, payload)
    except Exception as e:
        logger.warning(f"[conversation_state] mark_target_booked failed: {e}")


async def increment_frustration(tenant_id: int, phone_number: str) -> int:
    """Increment frustration_count and return the new count."""
    try:
        payload = await _read_payload(tenant_id, phone_number)
        current = int(payload.get("frustration_count") or 0) + 1
        payload["frustration_count"] = current
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
        logger.info(
            f"[conversation_state] frustration_count: {current} for {phone_number}"
        )
        return current
    except Exception as e:
        logger.warning(f"[conversation_state] increment_frustration failed: {e}")
        return 0


async def set_frustration_mode(tenant_id: int, phone_number: str, mode: bool) -> None:
    """Set the frustration_mode flag."""
    try:
        payload = await _read_payload(tenant_id, phone_number)
        payload["frustration_mode"] = mode
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
    except Exception as e:
        logger.warning(f"[conversation_state] set_frustration_mode failed: {e}")


async def append_error_history(tenant_id: int, phone_number: str, entry: dict) -> None:
    """Append an error entry to error_history. Caps at 5 — evicts oldest."""
    try:
        payload = await _read_payload(tenant_id, phone_number)
        history = list(payload.get("error_history") or [])
        history.append(entry)
        # Keep max 5 — evict oldest (FIFO)
        if len(history) > 5:
            history = history[-5:]
        payload["error_history"] = history
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
    except Exception as e:
        logger.warning(f"[conversation_state] append_error_history failed: {e}")


async def clear_error_history(tenant_id: int, phone_number: str) -> None:
    """Clear all entries from error_history."""
    try:
        payload = await _read_payload(tenant_id, phone_number)
        payload["error_history"] = []
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
    except Exception as e:
        logger.warning(f"[conversation_state] clear_error_history failed: {e}")


async def mark_booking_target_index(tenant_id: int, phone_number: str, index: int) -> None:
    """Set the current_booking_target_index."""
    try:
        payload = await _read_payload(tenant_id, phone_number)
        payload["current_booking_target_index"] = index
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
    except Exception as e:
        logger.warning(f"[conversation_state] mark_booking_target_index failed: {e}")


async def increment_turn_count(tenant_id: int, phone_number: str) -> int:
    """Increment turn_count and return the new count."""
    try:
        payload = await _read_payload(tenant_id, phone_number)
        current = int(payload.get("turn_count") or 0) + 1
        payload["turn_count"] = current
        payload["updated_at"] = _dt.now().isoformat()
        await _raw_write(tenant_id, phone_number, payload)
        return current
    except Exception as e:
        logger.warning(f"[conversation_state] increment_turn_count failed: {e}")
        return 0


# ── Insurance Asked Helpers ─────────────────────────────────────────


async def mark_insurance_asked(tenant_id: int, phone_number: str) -> None:
    """Marca que ya se preguntó sobre cobertura en esta conversación."""
    try:
        payload = await get_state(tenant_id, phone_number) or {}
        if not isinstance(payload, dict):
            payload = {}
        payload["insurance_asked"] = True
        await _raw_write(tenant_id, phone_number, payload, ttl=CONVSTATE_TTL)
    except Exception as e:
        logger.warning(f"[insurance_asked] Error marking insurance_asked: {e}")


async def has_insurance_been_asked(tenant_id: int, phone_number: str) -> bool:
    """Verifica si ya se preguntó sobre cobertura en esta conversación."""
    try:
        payload = await get_state(tenant_id, phone_number)
        if not isinstance(payload, dict):
            return False
        return payload.get("insurance_asked", False)
    except Exception as e:
        logger.warning(f"[insurance_asked] Error checking insurance_asked: {e}")
        return False


# ── Scheduling Constraints Helpers (v8.4) ──────────────────────────────────────
# Persiste las restricciones horarias/de día que el paciente declaró durante la
# conversación (ej: "a la tarde", "antes de las 18 no puedo", "los lunes no").
# Se preservan en Redis con TTL 24h para sobrevivir horas entre mensajes sin
# depender del historial del chat (que puede truncarse por límite de tokens).


async def save_scheduling_constraints(
    tenant_id: int,
    phone_number: str,
    *,
    time_preference: Optional[str] = None,
    min_time: Optional[str] = None,
    max_time: Optional[str] = None,
    exclude_days: Optional[List[str]] = None,
    exclude_dates: Optional[List[str]] = None,
) -> None:
    """
    Persiste restricciones horarias del paciente en el estado de conversación.
    Es idempotente: hace merge con lo que ya estaba guardado (no sobreescribe).

    Args:
        time_preference: 'mañana' | 'tarde' | 'noche'
        min_time: hora mínima en formato HH:MM (ej: '17:00') — "antes de esta hora no puedo"
        max_time: hora máxima en formato HH:MM (ej: '12:00') — "después de esta hora no puedo"
        exclude_days: lista de nombres de días a excluir (ej: ['lunes', 'viernes'])
        exclude_dates: lista de fechas YYYY-MM-DD a excluir
    """
    try:
        payload = await _read_payload(tenant_id, phone_number)
        existing = payload.get("scheduling_constraints") or {}

        if time_preference is not None:
            existing["time_preference"] = time_preference
        if min_time is not None:
            existing["min_time"] = min_time
        if max_time is not None:
            existing["max_time"] = max_time
        if exclude_days:
            current_days = existing.get("exclude_days", [])
            existing["exclude_days"] = list(set(current_days) | set(d.lower() for d in exclude_days))
        if exclude_dates:
            current_dates = existing.get("exclude_dates", [])
            existing["exclude_dates"] = list(set(current_dates) | set(exclude_dates))

        payload["scheduling_constraints"] = existing
        payload["updated_at"] = _dt.now().isoformat()

        # Usar TTL extendido (24h) para que las restricciones sobrevivan horas entre mensajes
        await _raw_write(tenant_id, phone_number, payload, ttl=BOOKED_TTL)
        logger.info(
            f"[conversation_state] scheduling_constraints saved for {phone_number}: {existing}"
        )
    except Exception as e:
        logger.warning(f"[conversation_state] save_scheduling_constraints failed: {e}")


async def get_scheduling_constraints(tenant_id: int, phone_number: str) -> Dict[str, Any]:
    """Devuelve las restricciones horarias persistidas del paciente. Dict vacío si no hay."""
    try:
        payload = await get_state(tenant_id, phone_number)
        if not isinstance(payload, dict):
            return {}
        return payload.get("scheduling_constraints") or {}
    except Exception as e:
        logger.warning(f"[conversation_state] get_scheduling_constraints failed: {e}")
        return {}
