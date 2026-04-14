"""
Playbook CRUD routes — Automation Engine V2.
Endpoints for managing playbooks, steps, executions, and stats.
"""

import logging
import json
from typing import Any, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, validator

from db import db
from core.auth import verify_admin_token, get_resolved_tenant_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/playbooks", tags=["Playbooks"])


# --- Pydantic Models ---

class PlaybookCreate(BaseModel):
    class Config:
        extra = "ignore"

    name: str
    description: Optional[str] = None
    icon: Optional[str] = "📋"
    category: Optional[str] = "custom"
    trigger_type: str
    trigger_config: Optional[Any] = {}
    conditions: Optional[Any] = {}
    is_active: Optional[bool] = False
    max_messages_per_day: Optional[int] = 2
    frequency_cap_hours: Optional[int] = 24
    schedule_hour_min: Optional[int] = 9
    schedule_hour_max: Optional[int] = 20
    abort_on_booking: Optional[bool] = True
    abort_on_human: Optional[bool] = True
    abort_on_optout: Optional[bool] = True
    steps: Optional[list] = None

    @validator("trigger_config", "conditions", pre=True, always=True)
    def parse_json_fields(cls, v):
        return _ensure_dict(v) or {}


def _ensure_dict(v: Any) -> Optional[dict]:
    """Accept dict, JSON string, or None — always return dict or None."""
    if v is None:
        return None
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


class PlaybookUpdate(BaseModel):
    class Config:
        extra = "ignore"

    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    category: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[Any] = None
    conditions: Optional[Any] = None
    is_active: Optional[bool] = None
    max_messages_per_day: Optional[int] = None
    frequency_cap_hours: Optional[int] = None
    schedule_hour_min: Optional[int] = None
    schedule_hour_max: Optional[int] = None
    abort_on_booking: Optional[bool] = None
    abort_on_human: Optional[bool] = None
    abort_on_optout: Optional[bool] = None

    @validator("trigger_config", "conditions", pre=True, always=True)
    def parse_json_fields(cls, v):
        return _ensure_dict(v)


def _ensure_list(v: Any) -> list:
    """Accept list, JSON string, or None — always return list."""
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


class StepCreate(BaseModel):
    class Config:
        extra = "ignore"

    step_label: Optional[str] = None
    action_type: str = "send_text"
    delay_minutes: Optional[int] = 0
    schedule_hour_min: Optional[int] = None
    schedule_hour_max: Optional[int] = None
    template_name: Optional[str] = None
    template_lang: Optional[str] = "es"
    template_vars: Optional[Any] = {}
    message_text: Optional[str] = None
    instruction_source: Optional[str] = "from_treatment"
    custom_instructions: Optional[str] = None
    notify_channel: Optional[str] = "telegram"
    notify_message: Optional[str] = None
    update_field: Optional[str] = None
    update_value: Optional[str] = None
    wait_timeout_minutes: Optional[int] = 120
    response_rules: Optional[Any] = []
    on_no_response: Optional[str] = "continue"
    on_unclassified: Optional[str] = "pass_to_ai"
    on_response_next_step: Optional[int] = None
    on_no_response_next_step: Optional[int] = None

    @validator("template_vars", pre=True, always=True)
    def parse_template_vars(cls, v):
        return _ensure_dict(v) or {}

    @validator("response_rules", pre=True, always=True)
    def parse_response_rules(cls, v):
        return _ensure_list(v)


class StepUpdate(StepCreate):
    action_type: Optional[str] = None


# ========================
# MANUAL TRIGGERS
# ========================

@router.post("/send-reminders-now")
async def send_reminders_now(
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """
    Manually send appointment reminder templates for ALL of tomorrow's appointments.
    Useful when the daily job didn't fire, or new appointments were just added.
    """
    from datetime import datetime, timedelta, date as date_type
    import json as _json

    # Use tenant timezone for "tomorrow" calculation (server is UTC)
    try:
        from services.tz_resolver import get_tenant_tz
        _tz = await get_tenant_tz(tenant_id)
    except Exception:
        from zoneinfo import ZoneInfo
        _tz = ZoneInfo("America/Argentina/Buenos_Aires")
    today_local = datetime.now(_tz).date()
    tomorrow = today_local + timedelta(days=1)
    tomorrow_start = datetime.combine(tomorrow, datetime.min.time())
    tomorrow_end = datetime.combine(tomorrow, datetime.max.time())

    appointments = await db.pool.fetch("""
        SELECT
            a.id as appointment_id,
            a.appointment_datetime,
            a.appointment_type,
            a.tenant_id,
            a.reminder_sent,
            p.id as patient_id,
            p.first_name,
            p.last_name,
            p.phone_number
        FROM appointments a
        INNER JOIN patients p ON a.patient_id = p.id AND p.tenant_id = a.tenant_id
        WHERE a.tenant_id = $1
            AND a.status IN ('scheduled', 'confirmed')
            AND a.appointment_datetime >= $2
            AND a.appointment_datetime <= $3
            AND p.phone_number IS NOT NULL
            AND p.phone_number != ''
        ORDER BY a.appointment_datetime
    """, tenant_id, tomorrow_start, tomorrow_end)

    if not appointments:
        return {"status": "ok", "message": "No hay turnos para mañana", "sent": 0, "total": 0}

    # Load reminder config from V2 playbook (Escudo Anti-Ausencias) first, fallback to V1
    rule = None
    playbook_row = await db.pool.fetchrow("""
        SELECT p.id as playbook_id, s.action_type, s.template_name, s.template_lang,
               s.template_vars, s.message_text
        FROM automation_playbooks p
        JOIN automation_steps s ON s.playbook_id = p.id AND s.step_order = 0
        WHERE p.tenant_id = $1 AND p.trigger_type = 'appointment_reminder' AND p.is_active = true
        ORDER BY p.is_system DESC LIMIT 1
    """, tenant_id)
    if playbook_row:
        rule = {
            "id": playbook_row["playbook_id"],
            "message_type": "hsm" if playbook_row["action_type"] == "send_template" else "free_text",
            "ycloud_template_name": playbook_row["template_name"],
            "ycloud_template_lang": playbook_row["template_lang"] or "es",
            "ycloud_template_vars": playbook_row["template_vars"],
            "free_text_message": playbook_row["message_text"],
        }
        logger.info(f"📋 Reminder config from playbook V2: action={playbook_row['action_type']} template={playbook_row['template_name']}")
    else:
        # Fallback to V1 automation_rules
        rule_row = await db.pool.fetchrow("""
            SELECT id, is_active, message_type, free_text_message,
                   ycloud_template_name, ycloud_template_lang, ycloud_template_vars
            FROM automation_rules
            WHERE tenant_id = $1 AND trigger_type = 'appointment_reminder'
            ORDER BY is_system DESC, created_at ASC LIMIT 1
        """, tenant_id)
        rule = dict(rule_row) if rule_row else None

    _DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

    sent_count = 0
    skip_count = 0
    errors = []

    for apt in appointments:
        try:
            patient_name = apt["first_name"] or "paciente"
            apt_time = apt["appointment_datetime"]
            # Convert to tenant timezone for correct display
            try:
                from services.tz_resolver import get_tenant_tz
                _tz = await get_tenant_tz(tenant_id)
            except Exception:
                from zoneinfo import ZoneInfo
                _tz = ZoneInfo("America/Argentina/Buenos_Aires")
            if apt_time.tzinfo is not None:
                apt_time = apt_time.astimezone(_tz)
            formatted_time = apt_time.strftime("%H:%M")
            formatted_date = apt_time.strftime("%d/%m")
            day_of_week = _DAYS_ES[apt_time.weekday()]

            sent = False
            full_name = f"{apt['first_name'] or ''} {apt.get('last_name') or ''}".strip()
            message = ""
            used_template = False

            # Try HSM template first
            if rule and rule.get("message_type") == "hsm" and rule.get("ycloud_template_name"):
                from jobs.reminders import _send_template
                template_name = rule["ycloud_template_name"]
                template_lang = rule.get("ycloud_template_lang") or "es"

                var_map = {
                    "nombre_paciente": patient_name,
                    "dia_semana": day_of_week,
                    "fecha_turno": formatted_date,
                    "hora_turno": formatted_time,
                }
                # Build parameters matching the template's actual variables (3: dia_semana, fecha_turno, hora_turno)
                parameters = [{"type": "text", "text": var_map.get(k, "")} for k in ["dia_semana", "fecha_turno", "hora_turno"]]
                components = [{"type": "body", "parameters": parameters}]

                sent = await _send_template(
                    tenant_id, apt["phone_number"], template_name, template_lang, components,
                    patient_name=full_name,
                    appointment_info={
                        "treatment": apt.get("appointment_type") or "Consulta",
                        "date": formatted_date,
                        "time": formatted_time,
                        "day_name": day_of_week,
                        "professional": "Laura Delgado",
                        "appointment_id": str(apt["appointment_id"]),
                    },
                )
                if sent:
                    used_template = True
                    message = f"[HSM:{template_name}]"

            # Fallback: free text
            if not sent:
                from jobs.reminders import _send_text
                if rule and rule.get("free_text_message"):
                    message = rule["free_text_message"]
                    message = message.replace("{{first_name}}", patient_name)
                    message = message.replace("{{appointment_time}}", formatted_time)
                    message = message.replace("{{appointment_date}}", formatted_date)
                else:
                    message = f"Hola {patient_name}, te recordamos tu turno de mañana a las {formatted_time}. Nos confirmás tu asistencia?"
                sent = await _send_text(tenant_id, apt["phone_number"], message, patient_name=full_name)

            msg_preview = f"[HSM:{rule.get('ycloud_template_name', '')}] {full_name} - {day_of_week} {formatted_date} {formatted_time}" if used_template else message[:200]

            if sent:
                await db.pool.execute(
                    "UPDATE appointments SET reminder_sent = true, reminder_sent_at = NOW() WHERE id = $1 AND tenant_id = $2",
                    apt["appointment_id"], tenant_id,
                )
                # Log in automation_logs (same as daily job)
                from jobs.reminders import _log_reminder
                await _log_reminder(
                    tenant_id, "sent", full_name, apt["phone_number"],
                    message_preview=msg_preview or f"Recordatorio {formatted_date} {formatted_time}",
                    rule_id=rule["id"] if rule else None,
                    patient_id=apt.get("patient_id"),
                    appointment_id=apt.get("appointment_id"),
                )
                sent_count += 1
                logger.info(f"✅ Manual reminder sent to {full_name} ({apt['phone_number']})")
            else:
                from jobs.reminders import _log_reminder
                await _log_reminder(
                    tenant_id, "failed", full_name, apt["phone_number"],
                    message_preview=msg_preview,
                    error_detail="send_failed",
                    rule_id=rule["id"] if rule else None,
                    patient_id=apt.get("patient_id"),
                    appointment_id=apt.get("appointment_id"),
                )
                skip_count += 1

        except Exception as e:
            errors.append(f"{apt.get('first_name')}: {str(e)[:100]}")
            logger.error(f"❌ Manual reminder error: {e}")

    return {
        "status": "ok",
        "sent": sent_count,
        "skipped": skip_count,
        "errors": len(errors),
        "total": len(appointments),
        "error_details": errors[:5],
        "message": f"Enviados {sent_count} de {len(appointments)} recordatorios para mañana {tomorrow.strftime('%d/%m')}",
    }


# ========================
# PLAYBOOK CRUD
# ========================

@router.get("")
async def list_playbooks(
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """List all playbooks for the tenant (with stats)."""
    rows = await db.pool.fetch("""
        SELECT p.*,
               (SELECT COUNT(*) FROM automation_steps WHERE playbook_id = p.id) as step_count,
               (SELECT COUNT(*) FROM automation_executions WHERE playbook_id = p.id AND status = 'running') as active_executions
        FROM automation_playbooks p
        WHERE p.tenant_id = $1
        ORDER BY p.is_system DESC, p.category, p.name
    """, tenant_id)
    return {"playbooks": [dict(r) for r in rows]}


@router.post("")
async def create_playbook(
    payload: PlaybookCreate,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """Create a new playbook, optionally with steps."""
    row = await db.pool.fetchrow("""
        INSERT INTO automation_playbooks
        (tenant_id, name, description, icon, category, trigger_type, trigger_config,
         conditions, is_active, max_messages_per_day, frequency_cap_hours,
         schedule_hour_min, schedule_hour_max,
         abort_on_booking, abort_on_human, abort_on_optout)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
        RETURNING *
    """,
        tenant_id, payload.name, payload.description, payload.icon, payload.category,
        payload.trigger_type, json.dumps(payload.trigger_config or {}),
        json.dumps(payload.conditions or {}), payload.is_active,
        payload.max_messages_per_day, payload.frequency_cap_hours,
        payload.schedule_hour_min, payload.schedule_hour_max,
        payload.abort_on_booking, payload.abort_on_human, payload.abort_on_optout,
    )

    playbook_id = row["id"]

    # Create steps if provided
    if payload.steps:
        for i, step_data in enumerate(payload.steps):
            await _insert_step(playbook_id, i, step_data)

    return dict(row)


@router.get("/{playbook_id}")
async def get_playbook(
    playbook_id: int,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """Get playbook with all its steps."""
    pb = await db.pool.fetchrow(
        "SELECT * FROM automation_playbooks WHERE id = $1 AND tenant_id = $2",
        playbook_id, tenant_id,
    )
    if not pb:
        raise HTTPException(404, "Playbook no encontrado")

    steps = await db.pool.fetch(
        "SELECT * FROM automation_steps WHERE playbook_id = $1 ORDER BY step_order",
        playbook_id,
    )

    result = dict(pb)
    result["steps"] = [dict(s) for s in steps]
    return result


@router.patch("/{playbook_id}")
async def update_playbook(
    playbook_id: int,
    payload: PlaybookUpdate,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """Update playbook configuration."""
    existing = await db.pool.fetchrow(
        "SELECT id FROM automation_playbooks WHERE id = $1 AND tenant_id = $2",
        playbook_id, tenant_id,
    )
    if not existing:
        raise HTTPException(404, "Playbook no encontrado")

    # exclude_unset=True keeps only fields the client explicitly sent
    # Don't filter None — allow setting fields to null if needed
    # But DO filter the validator-generated defaults for unset fields
    updates = payload.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No hay campos para actualizar")

    set_clauses = []
    params = []
    idx = 1
    for key, value in updates.items():
        if key in ("trigger_config", "conditions"):
            set_clauses.append(f"{key} = ${idx}::jsonb")
            params.append(json.dumps(value if isinstance(value, dict) else {}))
        elif isinstance(value, bool):
            set_clauses.append(f"{key} = ${idx}")
            params.append(value)
        else:
            set_clauses.append(f"{key} = ${idx}")
            params.append(value)
        idx += 1

    set_clauses.append("updated_at = NOW()")
    params.extend([playbook_id, tenant_id])

    query = f"UPDATE automation_playbooks SET {', '.join(set_clauses)} WHERE id = ${idx} AND tenant_id = ${idx+1} RETURNING *"
    row = await db.pool.fetchrow(query, *params)
    return dict(row)


@router.delete("/{playbook_id}")
async def delete_playbook(
    playbook_id: int,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """Delete a playbook (cascades steps + executions)."""
    deleted = await db.pool.fetchval(
        "DELETE FROM automation_playbooks WHERE id = $1 AND tenant_id = $2 RETURNING id",
        playbook_id, tenant_id,
    )
    if not deleted:
        raise HTTPException(404, "Playbook no encontrado")
    return {"deleted": True, "id": deleted}


@router.patch("/{playbook_id}/toggle")
async def toggle_playbook(
    playbook_id: int,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """Toggle playbook active/inactive."""
    current = await db.pool.fetchval(
        "SELECT is_active FROM automation_playbooks WHERE id = $1 AND tenant_id = $2",
        playbook_id, tenant_id,
    )
    if current is None:
        raise HTTPException(404, "Playbook no encontrado")

    new_state = not current
    await db.pool.execute(
        "UPDATE automation_playbooks SET is_active = $1, updated_at = NOW() WHERE id = $2",
        new_state, playbook_id,
    )

    # If deactivating, abort all running executions
    if not new_state:
        await db.pool.execute(
            """UPDATE automation_executions
               SET status = 'aborted', pause_reason = 'playbook_deactivated', completed_at = NOW()
               WHERE playbook_id = $1 AND status IN ('running', 'waiting_response', 'paused')""",
            playbook_id,
        )

    return {"id": playbook_id, "is_active": new_state}


@router.post("/{playbook_id}/duplicate")
async def duplicate_playbook(
    playbook_id: int,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """Clone a playbook with all its steps."""
    pb = await db.pool.fetchrow(
        "SELECT * FROM automation_playbooks WHERE id = $1 AND tenant_id = $2",
        playbook_id, tenant_id,
    )
    if not pb:
        raise HTTPException(404, "Playbook no encontrado")

    new_row = await db.pool.fetchrow("""
        INSERT INTO automation_playbooks
        (tenant_id, name, description, icon, category, trigger_type, trigger_config,
         conditions, is_active, max_messages_per_day, frequency_cap_hours,
         schedule_hour_min, schedule_hour_max,
         abort_on_booking, abort_on_human, abort_on_optout)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,false,$9,$10,$11,$12,$13,$14,$15)
        RETURNING *
    """,
        tenant_id, f"{pb['name']} (copia)", pb["description"], pb["icon"], pb["category"],
        pb["trigger_type"], json.dumps(pb["trigger_config"] or {}),
        json.dumps(pb["conditions"] or {}),
        pb["max_messages_per_day"], pb["frequency_cap_hours"],
        pb["schedule_hour_min"], pb["schedule_hour_max"],
        pb["abort_on_booking"], pb["abort_on_human"], pb["abort_on_optout"],
    )

    # Copy steps
    steps = await db.pool.fetch(
        "SELECT * FROM automation_steps WHERE playbook_id = $1 ORDER BY step_order",
        playbook_id,
    )
    for s in steps:
        await db.pool.execute("""
            INSERT INTO automation_steps
            (playbook_id, step_order, step_label, action_type, delay_minutes,
             schedule_hour_min, schedule_hour_max, template_name, template_lang, template_vars,
             message_text, instruction_source, custom_instructions,
             notify_channel, notify_message, update_field, update_value,
             wait_timeout_minutes, response_rules, on_no_response, on_unclassified,
             on_response_next_step, on_no_response_next_step)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23)
        """,
            new_row["id"], s["step_order"], s["step_label"], s["action_type"], s["delay_minutes"],
            s["schedule_hour_min"], s["schedule_hour_max"],
            s["template_name"], s["template_lang"], json.dumps(s["template_vars"] or {}),
            s["message_text"], s["instruction_source"], s["custom_instructions"],
            s["notify_channel"], s["notify_message"], s["update_field"], s["update_value"],
            s["wait_timeout_minutes"], json.dumps(s["response_rules"] or []),
            s["on_no_response"], s["on_unclassified"],
            s["on_response_next_step"], s["on_no_response_next_step"],
        )

    return dict(new_row)


# ========================
# STEP CRUD
# ========================

@router.get("/{playbook_id}/steps")
async def list_steps(
    playbook_id: int,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """List steps ordered by step_order."""
    # Verify ownership
    pb = await db.pool.fetchval(
        "SELECT id FROM automation_playbooks WHERE id = $1 AND tenant_id = $2",
        playbook_id, tenant_id,
    )
    if not pb:
        raise HTTPException(404, "Playbook no encontrado")

    rows = await db.pool.fetch(
        "SELECT * FROM automation_steps WHERE playbook_id = $1 ORDER BY step_order",
        playbook_id,
    )
    return {"steps": [dict(r) for r in rows]}


@router.post("/{playbook_id}/steps")
async def add_step(
    playbook_id: int,
    payload: StepCreate,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """Add a step to the end of the playbook."""
    pb = await db.pool.fetchval(
        "SELECT id FROM automation_playbooks WHERE id = $1 AND tenant_id = $2",
        playbook_id, tenant_id,
    )
    if not pb:
        raise HTTPException(404, "Playbook no encontrado")

    max_order = await db.pool.fetchval(
        "SELECT COALESCE(MAX(step_order), -1) FROM automation_steps WHERE playbook_id = $1",
        playbook_id,
    )
    next_order = max_order + 1

    row = await _insert_step(playbook_id, next_order, payload.dict())
    return row


@router.patch("/{playbook_id}/steps/{step_id}")
async def update_step(
    playbook_id: int,
    step_id: int,
    payload: StepUpdate,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """Update a step's configuration."""
    # Verify ownership
    pb = await db.pool.fetchval(
        "SELECT id FROM automation_playbooks WHERE id = $1 AND tenant_id = $2",
        playbook_id, tenant_id,
    )
    if not pb:
        raise HTTPException(404, "Playbook no encontrado")

    updates = {k: v for k, v in payload.dict(exclude_unset=True).items()}
    if not updates:
        raise HTTPException(400, "No hay campos para actualizar")

    set_clauses = []
    params = []
    idx = 1
    for key, value in updates.items():
        if key in ("template_vars",):
            set_clauses.append(f"{key} = ${idx}::jsonb")
            params.append(json.dumps(value or {}))
        elif key in ("response_rules",):
            set_clauses.append(f"{key} = ${idx}::jsonb")
            params.append(json.dumps(value or []))
        else:
            set_clauses.append(f"{key} = ${idx}")
            params.append(value)
        idx += 1

    params.extend([step_id, playbook_id])
    query = f"UPDATE automation_steps SET {', '.join(set_clauses)} WHERE id = ${idx} AND playbook_id = ${idx+1} RETURNING *"
    row = await db.pool.fetchrow(query, *params)
    if not row:
        raise HTTPException(404, "Step no encontrado")
    return dict(row)


@router.delete("/{playbook_id}/steps/{step_id}")
async def delete_step(
    playbook_id: int,
    step_id: int,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """Delete a step and reorder remaining steps."""
    pb = await db.pool.fetchval(
        "SELECT id FROM automation_playbooks WHERE id = $1 AND tenant_id = $2",
        playbook_id, tenant_id,
    )
    if not pb:
        raise HTTPException(404, "Playbook no encontrado")

    deleted_order = await db.pool.fetchval(
        "DELETE FROM automation_steps WHERE id = $1 AND playbook_id = $2 RETURNING step_order",
        step_id, playbook_id,
    )
    if deleted_order is None:
        raise HTTPException(404, "Step no encontrado")

    # Reorder remaining steps
    await db.pool.execute(
        "UPDATE automation_steps SET step_order = step_order - 1 WHERE playbook_id = $1 AND step_order > $2",
        playbook_id, deleted_order,
    )

    return {"deleted": True, "id": step_id}


@router.post("/{playbook_id}/steps/reorder")
async def reorder_steps(
    playbook_id: int,
    request: Request,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """Reorder steps: body = {"order": [step_id_1, step_id_2, ...]}"""
    pb = await db.pool.fetchval(
        "SELECT id FROM automation_playbooks WHERE id = $1 AND tenant_id = $2",
        playbook_id, tenant_id,
    )
    if not pb:
        raise HTTPException(404, "Playbook no encontrado")

    body = await request.json()
    order = body.get("order", [])

    for idx, step_id in enumerate(order):
        await db.pool.execute(
            "UPDATE automation_steps SET step_order = $1 WHERE id = $2 AND playbook_id = $3",
            idx, step_id, playbook_id,
        )

    return {"reordered": True}


# ========================
# EXECUTIONS & STATS
# ========================

@router.get("/{playbook_id}/executions")
async def list_executions(
    playbook_id: int,
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """List executions for a playbook."""
    query = """
        SELECT e.*, pat.first_name, pat.last_name
        FROM automation_executions e
        LEFT JOIN patients pat ON e.patient_id = pat.id
        WHERE e.playbook_id = $1 AND e.tenant_id = $2
    """
    params = [playbook_id, tenant_id]
    if status:
        query += f" AND e.status = ${len(params)+1}"
        params.append(status)
    query += " ORDER BY e.created_at DESC LIMIT $" + str(len(params)+1) + " OFFSET $" + str(len(params)+2)
    params.extend([limit, offset])

    rows = await db.pool.fetch(query, *params)
    total = await db.pool.fetchval(
        "SELECT COUNT(*) FROM automation_executions WHERE playbook_id = $1 AND tenant_id = $2",
        playbook_id, tenant_id,
    )
    return {"executions": [dict(r) for r in rows], "total": total}


@router.get("/{playbook_id}/stats")
async def get_stats(
    playbook_id: int,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """Aggregated KPIs for a playbook."""
    stats = await db.pool.fetchrow("""
        SELECT
            COUNT(*) as total_executions,
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(*) FILTER (WHERE status = 'aborted') as aborted,
            COUNT(*) FILTER (WHERE status IN ('running', 'waiting_response')) as active,
            COUNT(*) FILTER (WHERE status = 'paused') as paused,
            SUM(messages_sent) as total_messages_sent,
            AVG(EXTRACT(EPOCH FROM (completed_at - started_at))/3600)
                FILTER (WHERE completed_at IS NOT NULL) as avg_completion_hours
        FROM automation_executions
        WHERE playbook_id = $1 AND tenant_id = $2
    """, playbook_id, tenant_id)

    # Button-level stats from events
    confirm_count = await db.pool.fetchval("""
        SELECT COUNT(*) FROM automation_events ae
        JOIN automation_executions ex ON ae.execution_id = ex.id
        WHERE ex.playbook_id = $1 AND ex.tenant_id = $2
          AND ae.event_type = 'response_classified'
          AND ae.event_data->>'classification' = 'confirm'
    """, playbook_id, tenant_id)

    result = dict(stats) if stats else {}
    result["confirm_count"] = confirm_count or 0
    total = result.get("total_executions") or 0
    completed = result.get("completed") or 0
    result["completion_rate"] = round(completed / total * 100, 1) if total > 0 else 0
    result["confirm_rate"] = round((confirm_count or 0) / total * 100, 1) if total > 0 else 0

    # Update cached stats on playbook
    await db.pool.execute(
        "UPDATE automation_playbooks SET stats_cache = $1::jsonb WHERE id = $2",
        json.dumps(result, default=str), playbook_id,
    )

    return result


@router.post("/{playbook_id}/executions/{exec_id}/abort")
async def abort_execution(
    playbook_id: int,
    exec_id: int,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """Manually abort an execution."""
    updated = await db.pool.fetchval(
        """UPDATE automation_executions
           SET status = 'aborted', pause_reason = 'manual_abort', completed_at = NOW()
           WHERE id = $1 AND playbook_id = $2 AND tenant_id = $3
             AND status IN ('running', 'waiting_response', 'paused')
           RETURNING id""",
        exec_id, playbook_id, tenant_id,
    )
    if not updated:
        raise HTTPException(404, "Ejecución no encontrada o ya finalizada")
    return {"aborted": True, "id": updated}


@router.post("/{playbook_id}/executions/{exec_id}/resume")
async def resume_execution(
    playbook_id: int,
    exec_id: int,
    tenant_id: int = Depends(get_resolved_tenant_id),
    _=Depends(verify_admin_token),
):
    """Resume a paused execution."""
    from datetime import datetime, timezone
    updated = await db.pool.fetchval(
        """UPDATE automation_executions
           SET status = 'running', pause_reason = NULL, next_step_at = $1
           WHERE id = $2 AND playbook_id = $3 AND tenant_id = $4 AND status = 'paused'
           RETURNING id""",
        datetime.now(timezone.utc), exec_id, playbook_id, tenant_id,
    )
    if not updated:
        raise HTTPException(404, "Ejecución no encontrada o no está pausada")
    return {"resumed": True, "id": updated}


# ========================
# HELPERS
# ========================

async def _insert_step(playbook_id: int, order: int, data: dict) -> dict:
    """Insert a step into the database."""
    # Defensive JSON serialization for JSONB fields
    tv = data.get("template_vars") or {}
    if isinstance(tv, str):
        try: tv = json.loads(tv)
        except: tv = {}
    rr = data.get("response_rules") or []
    if isinstance(rr, str):
        try: rr = json.loads(rr)
        except: rr = []

    row = await db.pool.fetchrow("""
        INSERT INTO automation_steps
        (playbook_id, step_order, step_label, action_type, delay_minutes,
         schedule_hour_min, schedule_hour_max, template_name, template_lang, template_vars,
         message_text, instruction_source, custom_instructions,
         notify_channel, notify_message, update_field, update_value,
         wait_timeout_minutes, response_rules, on_no_response, on_unclassified,
         on_response_next_step, on_no_response_next_step)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23)
        RETURNING *
    """,
        playbook_id, order,
        data.get("step_label"),
        data.get("action_type", "send_text"),
        int(data.get("delay_minutes") or 0),
        data.get("schedule_hour_min"),
        data.get("schedule_hour_max"),
        data.get("template_name"),
        data.get("template_lang", "es"),
        json.dumps(tv),
        data.get("message_text"),
        data.get("instruction_source", "from_treatment"),
        data.get("custom_instructions"),
        data.get("notify_channel", "telegram"),
        data.get("notify_message"),
        data.get("update_field"),
        data.get("update_value"),
        int(data.get("wait_timeout_minutes") or 120),
        json.dumps(rr),
        data.get("on_no_response", "continue"),
        data.get("on_unclassified", "pass_to_ai"),
        data.get("on_response_next_step"),
        data.get("on_no_response_next_step"),
    )
    return dict(row)
