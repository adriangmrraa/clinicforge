"""
Playbook Executor — Automation Engine V2.

Runs every 5 minutes via JobScheduler. Processes pending automation_executions:
1. Query executions WHERE next_step_at <= NOW() AND status IN (running, waiting_response)
2. Pre-flight checks (daily cap, cooldown, human override, abort conditions, schedule window)
3. Execute step action (send_template, send_text, send_instructions, notify_team, update_status)
4. Log automation_event
5. Advance to next step or complete execution
"""

import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from .scheduler import scheduler

logger = logging.getLogger(__name__)


async def process_pending_executions():
    """Main executor loop — called every 5 minutes."""
    try:
        from db import db
        if not db.pool:
            return

        now = datetime.now(timezone.utc)

        # 1. Fetch pending executions
        executions = await db.pool.fetch("""
            SELECT e.*, p.name as playbook_name, p.max_messages_per_day,
                   p.frequency_cap_hours, p.schedule_hour_min, p.schedule_hour_max,
                   p.abort_on_booking, p.abort_on_human, p.abort_on_optout,
                   p.trigger_type, p.conditions
            FROM automation_executions e
            JOIN automation_playbooks p ON e.playbook_id = p.id AND p.is_active = true
            WHERE e.status IN ('running', 'waiting_response')
              AND e.next_step_at IS NOT NULL
              AND e.next_step_at <= $1
            ORDER BY e.next_step_at ASC
            LIMIT 50
        """, now)

        if not executions:
            return

        logger.info(f"⚙️ Playbook executor: {len(executions)} pending executions")

        for exec_row in executions:
            try:
                await _process_execution(db.pool, dict(exec_row), now)
            except Exception as e:
                logger.error(f"❌ Executor error for execution {exec_row['id']}: {e}")

    except Exception as e:
        logger.error(f"❌ Playbook executor global error: {e}")


async def _process_execution(pool, execution: dict, now: datetime):
    """Process a single execution: pre-flight → execute step → advance."""
    exec_id = execution["id"]
    tenant_id = execution["tenant_id"]
    phone = execution["phone_number"]
    playbook_id = execution["playbook_id"]
    current_order = execution["current_step_order"]

    # Handle waiting_response timeout
    if execution["status"] == "waiting_response":
        await _handle_response_timeout(pool, execution)
        return

    # Load current step
    step = await pool.fetchrow(
        "SELECT * FROM automation_steps WHERE playbook_id = $1 AND step_order = $2",
        playbook_id, current_order,
    )
    if not step:
        # No more steps — complete
        await _complete_execution(pool, exec_id, "completed")
        return

    step = dict(step)

    # --- Pre-flight checks ---
    ok, reason = await _preflight_check(pool, execution, step, now)
    if not ok:
        if reason == "schedule_window":
            # Defer to next valid window
            next_morning = now.replace(hour=execution["schedule_hour_min"], minute=0, second=0)
            if next_morning <= now:
                next_morning += timedelta(days=1)
            await pool.execute(
                "UPDATE automation_executions SET next_step_at = $1, updated_at = NOW() WHERE id = $2",
                next_morning, exec_id,
            )
            logger.info(f"⏰ Execution {exec_id} deferred to {next_morning} (outside schedule)")
        elif reason == "daily_cap":
            # Defer to tomorrow morning
            tomorrow = (now + timedelta(days=1)).replace(
                hour=execution["schedule_hour_min"], minute=0, second=0
            )
            await pool.execute(
                "UPDATE automation_executions SET next_step_at = $1, messages_sent_today = 0, updated_at = NOW() WHERE id = $2",
                tomorrow, exec_id,
            )
            logger.info(f"📬 Execution {exec_id} deferred to tomorrow (daily cap reached)")
        elif reason in ("abort_booking", "abort_human", "abort_optout"):
            await _complete_execution(pool, exec_id, "aborted", pause_reason=reason)
        else:
            logger.warning(f"⏭️ Execution {exec_id} skipped: {reason}")
        return

    # --- Execute step ---
    logger.info(f"▶️ Executing step {current_order} ({step['action_type']}) for execution {exec_id}")
    success = await _execute_step(pool, execution, step)

    # Log event
    await pool.execute(
        """INSERT INTO automation_events (execution_id, step_id, event_type, event_data)
           VALUES ($1, $2, $3, $4)""",
        exec_id, step["id"],
        "step_executed" if success else "step_failed",
        json.dumps({"action_type": step["action_type"], "success": success}),
    )

    if not success:
        logger.warning(f"⚠️ Step {current_order} failed for execution {exec_id}, continuing anyway")

    # --- Advance ---
    if step["action_type"] == "wait_response":
        # Enter waiting state
        timeout = step.get("wait_timeout_minutes") or 120
        await pool.execute(
            """UPDATE automation_executions
               SET status = 'waiting_response', next_step_at = $1, updated_at = NOW()
               WHERE id = $2""",
            now + timedelta(minutes=timeout), exec_id,
        )
        logger.info(f"⏳ Execution {exec_id} waiting for response (timeout: {timeout}min)")
    else:
        await _advance_to_next_step(pool, execution, step)


async def _preflight_check(pool, execution: dict, step: dict, now: datetime):
    """Run pre-flight checks. Returns (ok, reason)."""
    tenant_id = execution["tenant_id"]
    phone = execution["phone_number"]

    # 1. Schedule window
    current_hour = now.hour
    hour_min = step.get("schedule_hour_min") or execution["schedule_hour_min"]
    hour_max = step.get("schedule_hour_max") or execution["schedule_hour_max"]
    if current_hour < hour_min or current_hour >= hour_max:
        return (False, "schedule_window")

    # 2. Daily message cap
    if step["action_type"] in ("send_template", "send_text", "send_instructions"):
        if execution["messages_sent_today"] >= execution["max_messages_per_day"]:
            return (False, "daily_cap")

        # Global cooldown: check patient's last_automation_message_at
        patient_last = await pool.fetchval(
            "SELECT last_automation_message_at FROM patients WHERE tenant_id = $1 AND phone_number = $2",
            tenant_id, phone,
        )
        if patient_last:
            cap_hours = execution.get("frequency_cap_hours") or 24
            if (now - patient_last.replace(tzinfo=timezone.utc)).total_seconds() < cap_hours * 3600:
                # Check if it's from THIS execution (allow) or another playbook (block)
                if execution.get("last_message_at"):
                    own_last = execution["last_message_at"]
                    if own_last.replace(tzinfo=timezone.utc) < patient_last.replace(tzinfo=timezone.utc):
                        return (False, "cooldown_other_playbook")

    # 3. Abort: patient booked appointment
    if execution.get("abort_on_booking") and execution["trigger_type"] in (
        "lead_no_booking", "patient_inactive", "no_show"
    ):
        has_future = await pool.fetchval(
            """SELECT EXISTS(
                SELECT 1 FROM appointments
                WHERE tenant_id = $1 AND patient_id = $2
                  AND status IN ('scheduled', 'confirmed')
                  AND appointment_datetime > NOW()
            )""",
            tenant_id, execution.get("patient_id"),
        )
        if has_future:
            return (False, "abort_booking")

    # 4. Abort: human override active
    if execution.get("abort_on_human"):
        override = await pool.fetchval(
            """SELECT human_override_until FROM chat_conversations
               WHERE tenant_id = $1 AND external_user_id = $2
               AND human_override_until > NOW()
               LIMIT 1""",
            tenant_id, phone,
        )
        if override:
            return (False, "abort_human")

    return (True, None)


async def _execute_step(pool, execution: dict, step: dict) -> bool:
    """Execute a single step action. Returns True on success."""
    action = step["action_type"]
    tenant_id = execution["tenant_id"]
    phone = execution["phone_number"]

    # Resolve variables
    from services.playbook_variables import resolve_variables, substitute_variables
    variables = await resolve_variables(
        pool, tenant_id, phone,
        appointment_id=execution.get("appointment_id"),
        context=execution.get("context") or {},
    )

    if action == "send_template":
        return await _action_send_template(pool, tenant_id, phone, step, variables)
    elif action == "send_text":
        return await _action_send_text(pool, tenant_id, phone, step, variables)
    elif action == "send_instructions":
        return await _action_send_instructions(pool, tenant_id, phone, step, execution)
    elif action == "notify_team":
        return await _action_notify_team(tenant_id, step, variables)
    elif action == "update_status":
        return await _action_update_status(pool, execution, step)
    elif action == "wait":
        return True  # Just a delay, no action
    elif action == "wait_response":
        return True  # Handled by caller (sets status to waiting_response)
    else:
        logger.warning(f"Unknown action type: {action}")
        return False


async def _action_send_template(pool, tenant_id, phone, step, variables) -> bool:
    """Send a YCloud HSM template."""
    try:
        from core.credentials import get_tenant_credential, YCLOUD_API_KEY, YCLOUD_WHATSAPP_NUMBER
        from ycloud_client import YCloudClient

        template_name = step.get("template_name")
        if not template_name:
            logger.warning("send_template step has no template_name — skipping")
            return False

        api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
        biz_num = await get_tenant_credential(tenant_id, YCLOUD_WHATSAPP_NUMBER)
        if not api_key:
            logger.warning(f"No YCloud API key for tenant {tenant_id}")
            return False

        # Parse var_mapping defensively
        var_mapping = step.get("template_vars") or {}
        if isinstance(var_mapping, str):
            try:
                var_mapping = json.loads(var_mapping)
            except (json.JSONDecodeError, TypeError):
                var_mapping = {}

        body_params = []
        if var_mapping and isinstance(var_mapping, dict):
            # Explicit mapping: {"1": "nombre_paciente", "2": "dia_semana", ...}
            for key in sorted(var_mapping.keys()):
                var_name = var_mapping[key]
                body_params.append({"type": "text", "text": str(variables.get(var_name, "") or "")})
        else:
            # Auto-detect: use common variable order based on template name patterns
            # This covers the case where CEO selected a template but didn't configure vars
            _auto_vars = _auto_detect_template_vars(template_name)
            for var_name in _auto_vars:
                body_params.append({"type": "text", "text": str(variables.get(var_name, "") or "")})

        components = [{"type": "body", "parameters": body_params}] if body_params else None

        yc = YCloudClient(api_key=api_key, business_number=biz_num)
        await yc.send_template(
            to=phone,
            template_name=template_name,
            language_code=step.get("template_lang") or "es",
            components=components,
        )
        await _update_message_counters(pool, tenant_id, phone, step)
        logger.info(f"✅ Template '{template_name}' sent to {phone} ({len(body_params)} vars)")
        return True
    except Exception as e:
        logger.error(f"❌ send_template failed for {phone}: {e}")
        return False


def _auto_detect_template_vars(template_name: str) -> list:
    """Auto-detect variable order for known template patterns."""
    name = (template_name or "").lower()
    # Recordatorio de Asistencia: nombre_paciente, dia_semana, fecha_turno, hora_turno
    if "recordatorio" in name or "reminder" in name or "asistencia" in name:
        return ["nombre_paciente", "dia_semana", "fecha_turno", "hora_turno"]
    # Seguimiento Rápido: nombre_paciente
    if "seguimiento" in name:
        return ["nombre_paciente"]
    # Post-Cirugía, Post-Implantes: nombre_paciente
    if "post" in name or "cirugia" in name or "implante" in name:
        return ["nombre_paciente"]
    # Blanqueamiento: nombre_paciente, nombre_servicio
    if "blanqueamiento" in name:
        return ["nombre_paciente", "nombre_servicio"]
    # Armonización: nombre_paciente
    if "armoniza" in name:
        return ["nombre_paciente"]
    # Default: just send patient name as first variable
    return ["nombre_paciente"]


async def _action_send_text(pool, tenant_id, phone, step, variables) -> bool:
    """Send a free text message."""
    try:
        from services.playbook_variables import substitute_variables
        message = substitute_variables(step.get("message_text") or "", variables)
        if not message:
            return False

        conv = await pool.fetchrow(
            "SELECT id, provider, channel, external_account_id, external_chatwoot_id "
            "FROM chat_conversations WHERE tenant_id = $1 AND external_user_id = $2 "
            "ORDER BY updated_at DESC LIMIT 1",
            tenant_id, phone,
        )
        if conv:
            from services.response_sender import ResponseSender
            await ResponseSender.send_sequence(
                tenant_id=tenant_id, external_user_id=phone,
                conversation_id=str(conv["id"]),
                provider=conv.get("provider") or "ycloud",
                channel=conv.get("channel") or "whatsapp",
                account_id=str(conv.get("external_account_id") or ""),
                cw_conv_id=str(conv.get("external_chatwoot_id") or ""),
                messages_text=message,
            )
        else:
            from core.credentials import get_tenant_credential, YCLOUD_API_KEY, YCLOUD_WHATSAPP_NUMBER
            from ycloud_client import YCloudClient
            api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
            biz_num = await get_tenant_credential(tenant_id, YCLOUD_WHATSAPP_NUMBER)
            if not api_key:
                return False
            yc = YCloudClient(api_key=api_key, business_number=biz_num)
            await yc.send_text_message(to=phone, text=message)

        await _update_message_counters(pool, tenant_id, phone, step)
        return True
    except Exception as e:
        logger.error(f"❌ send_text failed: {e}")
        return False


async def _action_send_instructions(pool, tenant_id, phone, step, execution) -> bool:
    """Send treatment pre/post instructions."""
    try:
        source = step.get("instruction_source") or "from_treatment"

        if source == "custom":
            text = step.get("custom_instructions") or ""
        else:
            # Load from treatment_types.post_instructions
            apt_type = (execution.get("context") or {}).get("appointment_type")
            if not apt_type:
                if execution.get("appointment_id"):
                    apt_type = await pool.fetchval(
                        "SELECT appointment_type FROM appointments WHERE id = $1",
                        execution["appointment_id"],
                    )
            if apt_type:
                row = await pool.fetchrow(
                    "SELECT post_instructions FROM treatment_types WHERE tenant_id = $1 AND code = $2",
                    tenant_id, apt_type,
                )
                instructions = row["post_instructions"] if row else None
                if instructions and isinstance(instructions, dict):
                    text = instructions.get("general_notes") or json.dumps(instructions, ensure_ascii=False)
                elif instructions and isinstance(instructions, str):
                    text = instructions
                else:
                    text = ""
            else:
                text = ""

        if not text:
            logger.info("send_instructions: no instructions found, skipping")
            return True  # Not a failure, just nothing to send

        # Send via text
        conv = await pool.fetchrow(
            "SELECT id, provider, channel, external_account_id, external_chatwoot_id "
            "FROM chat_conversations WHERE tenant_id = $1 AND external_user_id = $2 "
            "ORDER BY updated_at DESC LIMIT 1",
            tenant_id, phone,
        )
        if conv:
            from services.response_sender import ResponseSender
            await ResponseSender.send_sequence(
                tenant_id=tenant_id, external_user_id=phone,
                conversation_id=str(conv["id"]),
                provider=conv.get("provider") or "ycloud",
                channel=conv.get("channel") or "whatsapp",
                account_id=str(conv.get("external_account_id") or ""),
                cw_conv_id=str(conv.get("external_chatwoot_id") or ""),
                messages_text=text,
            )

        await _update_message_counters(pool, tenant_id, phone, step)
        return True
    except Exception as e:
        logger.error(f"❌ send_instructions failed: {e}")
        return False


async def _action_notify_team(tenant_id, step, variables) -> bool:
    """Notify the team via Telegram."""
    try:
        from services.playbook_variables import substitute_variables
        message = substitute_variables(step.get("notify_message") or "", variables)
        if not message:
            message = f"⚠️ Alerta de playbook para paciente {variables.get('nombre_paciente', '?')}"

        channel = step.get("notify_channel") or "telegram"

        if channel in ("telegram", "both"):
            from services.telegram_notifier import send_proactive_message
            await send_proactive_message(tenant_id, message)

        if channel in ("dashboard", "both"):
            try:
                from main import app
                sio = getattr(app.state, "sio", None)
                if sio:
                    await sio.emit("PLAYBOOK_ALERT", {
                        "tenant_id": tenant_id,
                        "message": message,
                        "phone": variables.get("telefono", ""),
                        "patient_name": variables.get("nombre_paciente", ""),
                    })
            except Exception:
                pass

        return True
    except Exception as e:
        logger.error(f"❌ notify_team failed: {e}")
        return False


async def _action_update_status(pool, execution, step) -> bool:
    """Update appointment or patient status."""
    try:
        field = step.get("update_field")
        value = step.get("update_value")
        if not field or not value:
            return False

        if field == "appointment_status" and execution.get("appointment_id"):
            await pool.execute(
                "UPDATE appointments SET status = $1, updated_at = NOW() WHERE id = $2 AND tenant_id = $3",
                value, execution["appointment_id"], execution["tenant_id"],
            )
        return True
    except Exception as e:
        logger.error(f"❌ update_status failed: {e}")
        return False


async def _update_message_counters(pool, tenant_id, phone, step):
    """Update message counters after sending a message."""
    now = datetime.now(timezone.utc)
    # Update execution counters (will be done by caller via _advance_to_next_step)
    # Update patient global cooldown
    await pool.execute(
        "UPDATE patients SET last_automation_message_at = $1 WHERE tenant_id = $2 AND phone_number = $3",
        now, tenant_id, phone,
    )


async def _advance_to_next_step(pool, execution: dict, current_step: dict):
    """Move execution to the next step or complete it."""
    exec_id = execution["id"]
    playbook_id = execution["playbook_id"]
    next_order = execution["current_step_order"] + 1

    # Check if next step exists
    next_step = await pool.fetchrow(
        "SELECT * FROM automation_steps WHERE playbook_id = $1 AND step_order = $2",
        playbook_id, next_order,
    )

    is_message = current_step["action_type"] in ("send_template", "send_text", "send_instructions")
    sent_increment = 1 if is_message else 0

    if not next_step:
        # Complete
        await pool.execute(
            """UPDATE automation_executions
               SET status = 'completed', completed_at = NOW(), current_step_order = $1,
                   messages_sent = messages_sent + $2, messages_sent_today = messages_sent_today + $2,
                   last_message_at = CASE WHEN $2 > 0 THEN NOW() ELSE last_message_at END,
                   updated_at = NOW()
               WHERE id = $3""",
            next_order, sent_increment, exec_id,
        )
        logger.info(f"✅ Execution {exec_id} completed (all steps done)")
        return

    # Calculate next execution time
    delay = next_step["delay_minutes"] or 0
    next_at = datetime.now(timezone.utc) + timedelta(minutes=delay)

    await pool.execute(
        """UPDATE automation_executions
           SET current_step_order = $1, next_step_at = $2, status = 'running',
               messages_sent = messages_sent + $3, messages_sent_today = messages_sent_today + $3,
               last_message_at = CASE WHEN $3 > 0 THEN NOW() ELSE last_message_at END,
               updated_at = NOW()
           WHERE id = $4""",
        next_order, next_at, sent_increment, exec_id,
    )
    logger.info(f"➡️ Execution {exec_id} advanced to step {next_order} (next_at: {next_at})")


async def _handle_response_timeout(pool, execution: dict):
    """Handle a waiting_response execution that timed out."""
    exec_id = execution["id"]
    playbook_id = execution["playbook_id"]
    current_order = execution["current_step_order"]

    step = await pool.fetchrow(
        "SELECT * FROM automation_steps WHERE playbook_id = $1 AND step_order = $2",
        playbook_id, current_order,
    )

    if not step:
        await _complete_execution(pool, exec_id, "completed")
        return

    on_no_response = step["on_no_response"] or "continue"

    # Log timeout event
    await pool.execute(
        """INSERT INTO automation_events (execution_id, step_id, event_type, event_data)
           VALUES ($1, $2, 'timeout', $3)""",
        exec_id, step["id"],
        json.dumps({"on_no_response": on_no_response}),
    )

    if on_no_response == "abort":
        await _complete_execution(pool, exec_id, "aborted", pause_reason="no_response_abort")
    elif on_no_response == "notify_team":
        from services.playbook_variables import resolve_variables
        variables = await resolve_variables(
            pool, execution["tenant_id"], execution["phone_number"],
            context=execution.get("context") or {},
        )
        await _action_notify_team(execution["tenant_id"], {
            "notify_channel": "both",
            "notify_message": f"⏰ {variables.get('nombre_paciente', 'Paciente')} no respondió al playbook",
        }, variables)
        await _complete_execution(pool, exec_id, "aborted", pause_reason="no_response_notified")
    elif on_no_response == "continue":
        # Check for override next step
        override_step = step.get("on_no_response_next_step")
        if override_step is not None:
            next_step = await pool.fetchrow(
                "SELECT * FROM automation_steps WHERE playbook_id = $1 AND step_order = $2",
                playbook_id, override_step,
            )
            if next_step:
                delay = next_step["delay_minutes"] or 0
                await pool.execute(
                    """UPDATE automation_executions
                       SET current_step_order = $1, status = 'running',
                           next_step_at = $2, updated_at = NOW()
                       WHERE id = $3""",
                    override_step,
                    datetime.now(timezone.utc) + timedelta(minutes=delay),
                    exec_id,
                )
                return

        # Default: advance to next sequential step
        step_dict = dict(step)
        await _advance_to_next_step(pool, execution, step_dict)
    else:
        # retry or unknown — just continue
        step_dict = dict(step)
        await _advance_to_next_step(pool, execution, step_dict)


async def _complete_execution(pool, exec_id: int, status: str, pause_reason: str = None):
    """Mark execution as completed/aborted."""
    await pool.execute(
        """UPDATE automation_executions
           SET status = $1, completed_at = NOW(), pause_reason = $2, updated_at = NOW()
           WHERE id = $3""",
        status, pause_reason, exec_id,
    )
    logger.info(f"🏁 Execution {exec_id} → {status}" + (f" ({pause_reason})" if pause_reason else ""))


# --- Handle incoming patient response (called from chat_webhooks.py) ---

async def handle_patient_response(pool, tenant_id: int, phone: str, message_text: str) -> bool:
    """
    Check if patient has an active execution in waiting_response.
    If yes, classify response and advance/abort/pause accordingly.
    Returns True if handled (skip AI agent), False otherwise.
    """
    execution = await pool.fetchrow(
        """SELECT e.*
           FROM automation_executions e
           JOIN automation_playbooks p ON e.playbook_id = p.id AND p.is_active = true
           WHERE e.tenant_id = $1 AND e.phone_number = $2
             AND e.status = 'waiting_response'
           ORDER BY e.updated_at DESC LIMIT 1""",
        tenant_id, phone,
    )
    if not execution:
        return False

    execution = dict(execution)
    exec_id = execution["id"]

    # Load current step's response rules
    step = await pool.fetchrow(
        "SELECT * FROM automation_steps WHERE playbook_id = $1 AND step_order = $2",
        execution["playbook_id"], execution["current_step_order"],
    )
    if not step:
        return False

    response_rules = step["response_rules"] or []
    if isinstance(response_rules, str):
        try:
            response_rules = json.loads(response_rules)
        except (json.JSONDecodeError, TypeError):
            response_rules = []

    # Classify response
    from services.playbook_classifier import classify_response, classify_with_llm

    classification, action, rule_name = classify_response(message_text, response_rules)

    # If unclassified and step says to use LLM
    if classification == "unclassified" and (step["on_unclassified"] or "pass_to_ai") == "classify_with_ai":
        classification, action = await classify_with_llm(message_text, tenant_id)

    # Log classification event
    await pool.execute(
        """INSERT INTO automation_events (execution_id, step_id, event_type, event_data)
           VALUES ($1, $2, 'response_classified', $3)""",
        exec_id, step["id"],
        json.dumps({
            "classification": classification,
            "action": action,
            "rule_name": rule_name,
            "message_preview": message_text[:100],
        }),
    )

    # Update last_response_at
    await pool.execute(
        "UPDATE automation_executions SET last_response_at = NOW(), updated_at = NOW() WHERE id = $1",
        exec_id,
    )

    # Apply action
    if action == "continue":
        # Check for response override next step
        override_step = step.get("on_response_next_step")
        if override_step is not None:
            next_step_row = await pool.fetchrow(
                "SELECT * FROM automation_steps WHERE playbook_id = $1 AND step_order = $2",
                execution["playbook_id"], override_step,
            )
            if next_step_row:
                delay = next_step_row["delay_minutes"] or 0
                await pool.execute(
                    """UPDATE automation_executions
                       SET current_step_order = $1, status = 'running',
                           next_step_at = $2, updated_at = NOW()
                       WHERE id = $3""",
                    override_step,
                    datetime.now(timezone.utc) + timedelta(minutes=delay),
                    exec_id,
                )
                return True

        step_dict = dict(step)
        await _advance_to_next_step(pool, execution, step_dict)
        return True

    elif action == "abort":
        await _complete_execution(pool, exec_id, "aborted", pause_reason=f"response:{classification}")
        return False  # Let AI handle the conversation

    elif action in ("pause", "notify_and_pause"):
        await pool.execute(
            """UPDATE automation_executions
               SET status = 'paused', pause_reason = $1, updated_at = NOW()
               WHERE id = $2""",
            f"response:{classification}:{rule_name or 'auto'}",
            exec_id,
        )
        if action == "notify_and_pause":
            from services.playbook_variables import resolve_variables
            variables = await resolve_variables(
                pool, tenant_id, phone,
                context=execution.get("context") or {},
            )
            await _action_notify_team(tenant_id, {
                "notify_channel": "both",
                "notify_message": f"⚠️ Paciente {variables.get('nombre_paciente', phone)} respondió: \"{message_text[:80]}\" — Requiere atención",
            }, variables)
        return False  # Let AI/human handle

    elif action == "pass_to_ai":
        # Don't advance execution, let AI handle this message
        return False

    return False


async def check_inactive_patients():
    """Daily check: find patients inactive for X days and trigger matching playbooks."""
    try:
        from db import db
        if not db.pool:
            return

        # Find all active playbooks with patient_inactive trigger
        playbooks = await db.pool.fetch("""
            SELECT id, tenant_id, trigger_config, conditions
            FROM automation_playbooks
            WHERE trigger_type = 'patient_inactive' AND is_active = true
        """)

        if not playbooks:
            return

        from jobs.playbook_triggers import create_execution_for_event

        for pb in playbooks:
            tenant_id = pb["tenant_id"]
            config = pb["trigger_config"] or {}
            inactive_days = config.get("inactive_days", 90)

            # Find patients with no appointment in X days
            inactive_patients = await db.pool.fetch("""
                SELECT p.id, p.phone_number, p.first_name
                FROM patients p
                WHERE p.tenant_id = $1
                  AND p.phone_number IS NOT NULL AND p.phone_number != ''
                  AND p.no_followup = false
                  AND NOT EXISTS (
                      SELECT 1 FROM appointments a
                      WHERE a.patient_id = p.id AND a.tenant_id = $1
                        AND a.appointment_datetime > NOW() - INTERVAL '1 day' * $2
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM automation_executions ae
                      WHERE ae.playbook_id = $3 AND ae.phone_number = p.phone_number
                        AND ae.status IN ('running', 'waiting_response', 'paused', 'completed')
                        AND ae.created_at > NOW() - INTERVAL '30 days'
                  )
                LIMIT 20
            """, tenant_id, inactive_days, pb["id"])

            for patient in inactive_patients:
                await create_execution_for_event(
                    db.pool, tenant_id, "patient_inactive",
                    patient["phone_number"],
                    patient_id=patient["id"],
                    context={"patient_name": patient["first_name"] or ""},
                )

            if inactive_patients:
                logger.info(f"📋 Inactive patient trigger: {len(inactive_patients)} patients for tenant {tenant_id}")

    except Exception as e:
        logger.error(f"❌ check_inactive_patients error: {e}")


async def daily_reset_counters():
    """Reset messages_sent_today counter for all running executions."""
    try:
        from db import db
        if not db.pool:
            return
        await db.pool.execute(
            "UPDATE automation_executions SET messages_sent_today = 0 WHERE status IN ('running', 'waiting_response')"
        )
        logger.info("🔄 Playbook daily counters reset")
    except Exception as e:
        logger.error(f"❌ daily_reset_counters error: {e}")


# Register with scheduler
scheduler.add_job(process_pending_executions, 300, run_at_startup=False)
scheduler.add_job(check_inactive_patients, 86400, run_at_startup=False)  # Daily
scheduler.add_job(daily_reset_counters, 86400, run_at_startup=False)  # Daily
