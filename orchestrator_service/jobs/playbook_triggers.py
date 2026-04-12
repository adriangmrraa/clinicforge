"""
Playbook Triggers — Automation Engine V2.

Functions that detect events and create automation_executions for matching playbooks.
Called from admin_routes.py (appointment status changes) and chat_webhooks.py (new leads).
"""

import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


async def create_execution_for_event(
    pool,
    tenant_id: int,
    trigger_type: str,
    phone_number: str,
    patient_id: Optional[int] = None,
    appointment_id: Optional[str] = None,
    context: Optional[dict] = None,
) -> list[int]:
    """
    Find matching active playbooks for this trigger event and create executions.
    Returns list of created execution IDs.
    """
    created_ids = []

    try:
        # Find all active playbooks matching this trigger
        playbooks = await pool.fetch(
            """SELECT id, conditions, trigger_config
               FROM automation_playbooks
               WHERE tenant_id = $1 AND trigger_type = $2 AND is_active = true""",
            tenant_id, trigger_type,
        )

        if not playbooks:
            return []

        for pb in playbooks:
            pb_id = pb["id"]
            conditions = pb["conditions"] or {}
            if isinstance(conditions, str):
                conditions = json.loads(conditions)

            # --- Check conditions ---
            if not await _check_conditions(pool, tenant_id, conditions, context or {}):
                continue

            # --- Check no duplicate execution running ---
            existing = await pool.fetchval(
                """SELECT id FROM automation_executions
                   WHERE playbook_id = $1 AND tenant_id = $2 AND phone_number = $3
                     AND status IN ('running', 'waiting_response', 'paused')""",
                pb_id, tenant_id, phone_number,
            )
            if existing:
                logger.info(f"⏭️ Playbook {pb_id} already running for {phone_number} (exec {existing})")
                continue

            # --- Load first step to calculate initial delay ---
            first_step = await pool.fetchrow(
                "SELECT delay_minutes FROM automation_steps WHERE playbook_id = $1 ORDER BY step_order ASC LIMIT 1",
                pb_id,
            )
            delay = first_step["delay_minutes"] if first_step else 0
            next_at = datetime.now(timezone.utc) + timedelta(minutes=delay)

            # --- Create execution ---
            exec_id = await pool.fetchval(
                """INSERT INTO automation_executions
                   (playbook_id, tenant_id, patient_id, phone_number, appointment_id,
                    current_step_order, status, next_step_at, context)
                   VALUES ($1, $2, $3, $4, $5, 0, 'running', $6, $7)
                   RETURNING id""",
                pb_id, tenant_id, patient_id, phone_number,
                appointment_id, next_at,
                json.dumps(context or {}),
            )

            created_ids.append(exec_id)
            logger.info(
                f"🚀 Created execution {exec_id} for playbook {pb_id} "
                f"(trigger={trigger_type}, phone={phone_number}, next_at={next_at})"
            )

    except Exception as e:
        logger.error(f"❌ create_execution_for_event failed: {e}")

    return created_ids


async def _check_conditions(pool, tenant_id: int, conditions: dict, context: dict) -> bool:
    """Check if event context matches playbook conditions."""
    # Treatment filter
    treatments = conditions.get("treatments")
    if treatments and isinstance(treatments, list):
        event_treatment = context.get("appointment_type") or context.get("treatment_code") or ""
        if not _match_treatment_filter(event_treatment, treatments):
            return False

    # Professional filter
    professionals = conditions.get("professionals")
    if professionals and isinstance(professionals, list):
        event_prof = context.get("professional_id")
        if event_prof and int(event_prof) not in [int(p) for p in professionals]:
            return False

    # Patient type filter
    patient_type = conditions.get("patient_type")
    if patient_type and patient_type != "all":
        patient_id = context.get("patient_id")
        if patient_id:
            has_past_apt = await pool.fetchval(
                """SELECT EXISTS(
                    SELECT 1 FROM appointments
                    WHERE tenant_id = $1 AND patient_id = $2 AND status = 'completed'
                )""",
                tenant_id, patient_id,
            )
            if patient_type == "new_only" and has_past_apt:
                return False
            if patient_type == "existing_only" and not has_past_apt:
                return False

    return True


def _match_treatment_filter(treatment_code: str, filters: list) -> bool:
    """Check if treatment code matches any filter (supports wildcards like 'implante_*')."""
    if not treatment_code:
        return False
    for f in filters:
        if f.endswith("*"):
            prefix = f[:-1]
            if treatment_code.startswith(prefix):
                return True
        elif f == treatment_code:
            return True
    return False


# --- Convenience trigger functions (called from routes) ---

async def on_appointment_completed(pool, tenant_id: int, appointment: dict):
    """Trigger when appointment status → completed."""
    phone = appointment.get("phone_number")
    if not phone:
        patient = await pool.fetchrow(
            "SELECT phone_number FROM patients WHERE id = $1 AND tenant_id = $2",
            appointment.get("patient_id"), tenant_id,
        )
        phone = patient["phone_number"] if patient else None

    if not phone:
        return

    context = {
        "appointment_type": appointment.get("appointment_type"),
        "professional_id": appointment.get("professional_id"),
        "patient_id": appointment.get("patient_id"),
        "appointment_datetime": str(appointment.get("appointment_datetime", "")),
    }

    await create_execution_for_event(
        pool, tenant_id, "appointment_completed", phone,
        patient_id=appointment.get("patient_id"),
        appointment_id=str(appointment.get("id", "")),
        context=context,
    )


async def on_no_show(pool, tenant_id: int, appointment: dict):
    """Trigger when appointment is marked as no-show."""
    phone = appointment.get("phone_number")
    if not phone:
        patient = await pool.fetchrow(
            "SELECT phone_number FROM patients WHERE id = $1 AND tenant_id = $2",
            appointment.get("patient_id"), tenant_id,
        )
        phone = patient["phone_number"] if patient else None

    if not phone:
        return

    context = {
        "appointment_type": appointment.get("appointment_type"),
        "patient_id": appointment.get("patient_id"),
    }

    await create_execution_for_event(
        pool, tenant_id, "no_show", phone,
        patient_id=appointment.get("patient_id"),
        appointment_id=str(appointment.get("id", "")),
        context=context,
    )


async def on_appointment_created(pool, tenant_id: int, appointment: dict):
    """Trigger when a new appointment is created (for reminders, payment pending, etc.)."""
    phone = appointment.get("phone_number")
    if not phone:
        patient = await pool.fetchrow(
            "SELECT phone_number FROM patients WHERE id = $1 AND tenant_id = $2",
            appointment.get("patient_id"), tenant_id,
        )
        phone = patient["phone_number"] if patient else None

    if not phone:
        return

    context = {
        "appointment_type": appointment.get("appointment_type"),
        "professional_id": appointment.get("professional_id"),
        "patient_id": appointment.get("patient_id"),
        "appointment_datetime": str(appointment.get("appointment_datetime", "")),
        "payment_status": appointment.get("payment_status"),
    }

    await create_execution_for_event(
        pool, tenant_id, "appointment_created", phone,
        patient_id=appointment.get("patient_id"),
        appointment_id=str(appointment.get("id", "")),
        context=context,
    )
