"""Appointment audit log helper.

Best-effort logging of appointment mutations. NEVER raises — failures are logged
as warnings so they cannot break the underlying booking/cancel/reschedule flow.
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger("audit_log")


def _to_json_safe(value: Any) -> Any:
    """Make a value JSON-serializable for storage in JSONB columns."""
    if value is None:
        return None
    try:
        json.dumps(value, default=str)
        return value
    except Exception:
        try:
            return json.loads(json.dumps(value, default=str))
        except Exception:
            return str(value)


async def log_appointment_mutation(
    pool,
    tenant_id: int,
    appointment_id: Optional[str],
    action: str,
    actor_type: str,
    actor_id: Optional[str] = None,
    before_values: Optional[dict] = None,
    after_values: Optional[dict] = None,
    source_channel: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Insert one row into appointment_audit_log.

    Args:
        pool: asyncpg pool (db.pool)
        tenant_id: tenant the appointment belongs to
        appointment_id: UUID string of the appointment, or None if not yet created
        action: one of 'created' | 'rescheduled' | 'cancelled' | 'status_changed' | 'payment_updated'
        actor_type: one of 'ai_agent' | 'staff_user' | 'patient_self' | 'system'
        actor_id: identifier of the actor (users.id UUID for staff, or descriptive tag)
        before_values: dict of fields before the mutation (null for 'created')
        after_values: dict of fields after the mutation (null for 'cancelled' if no payload)
        source_channel: one of 'whatsapp' | 'instagram' | 'facebook' | 'web_admin' | 'nova_voice' | 'api' | 'system'
        reason: optional human-readable reason
    """
    try:
        before_json = _to_json_safe(before_values) if before_values is not None else None
        after_json = _to_json_safe(after_values) if after_values is not None else None
        await pool.execute(
            """
            INSERT INTO appointment_audit_log
                (tenant_id, appointment_id, action, actor_type, actor_id,
                 before_values, after_values, source_channel, reason)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9)
            """,
            tenant_id,
            appointment_id,
            action,
            actor_type,
            actor_id,
            json.dumps(before_json) if before_json is not None else None,
            json.dumps(after_json) if after_json is not None else None,
            source_channel,
            reason,
        )
        logger.info(
            f"📝 audit_log: {action} apt={appointment_id} actor={actor_type}/{actor_id} channel={source_channel}"
        )
    except Exception as e:
        logger.warning(
            f"📝 audit_log INSERT failed (non-blocking): {e} | "
            f"action={action} apt={appointment_id} actor={actor_type}"
        )
