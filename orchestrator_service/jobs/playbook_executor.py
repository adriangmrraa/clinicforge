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
    if step["action_type"] in ("send_template", "send_text", "send_instructions", "send_ai_message"):
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
        result = await _action_send_template(pool, tenant_id, phone, step, variables)
        if not result and not step.get("template_name"):
            logger.warning(
                f"⚠️ Step {step.get('step_order', '?')} skipped: no template configured "
                f"— configure it in Playbooks UI (playbook_id={execution.get('playbook_id')})"
            )
            return True  # Advance to next step, don't block the sequence
        return result
    elif action == "send_ai_message":
        return await _action_send_ai_message(pool, tenant_id, phone, step, execution, variables)
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
        import httpx
        import re

        template_name = step.get("template_name")
        if not template_name:
            logger.warning("send_template step has no template_name — skipping")
            return False

        api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
        if not api_key:
            logger.warning(f"No YCloud API key for tenant {tenant_id}")
            return False

        # Resolve from_number: tenants.bot_phone_number first, then credential vault
        biz_num = await pool.fetchval(
            "SELECT bot_phone_number FROM tenants WHERE id = $1", tenant_id
        )
        if not biz_num:
            biz_num = await get_tenant_credential(tenant_id, YCLOUD_WHATSAPP_NUMBER)

        # Fetch template from YCloud to get REAL language code and variable structure
        real_lang = step.get("template_lang") or "es"
        tpl_components = None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.ycloud.com/v2/whatsapp/templates",
                    params={"filter.name": template_name, "limit": 10},
                    headers={"X-API-Key": api_key},
                )
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    for tpl in items:
                        if tpl.get("status") == "APPROVED" and tpl.get("name") == template_name:
                            real_lang = tpl.get("language") or real_lang
                            tpl_components = tpl.get("components", [])
                            logger.info(f"📋 Template '{template_name}' found: lang={real_lang}")
                            break
        except Exception as fetch_err:
            logger.warning(f"⚠️ Template metadata fetch failed, using fallback: {fetch_err}")

        # Parse var_mapping defensively
        var_mapping = step.get("template_vars") or {}
        if isinstance(var_mapping, str):
            try:
                var_mapping = json.loads(var_mapping)
            except (json.JSONDecodeError, TypeError):
                var_mapping = {}

        # Build components matching the REAL template structure if available
        if tpl_components:
            send_components = []
            for comp in tpl_components:
                comp_type = comp.get("type", "").upper()
                text = comp.get("text", "")
                comp_vars = re.findall(r'\{\{(\w+)\}\}', text)
                if not comp_vars:
                    continue
                parameters = []
                for var_name in comp_vars:
                    # Priority: explicit mapping > resolved variables > auto-detect > empty
                    value = ""
                    if var_mapping and isinstance(var_mapping, dict):
                        # Check if any mapping key points to this var_name
                        for _k, _v in var_mapping.items():
                            if _v == var_name or _k == var_name:
                                value = str(variables.get(_v, "") or "")
                                break
                    if not value:
                        value = str(variables.get(var_name, "") or "")
                    parameters.append({"type": "text", "text": value})
                send_components.append({"type": comp_type.lower(), "parameters": parameters})
            components = send_components if send_components else None
        else:
            # Fallback: use explicit mapping or auto-detect (original behavior)
            body_params = []
            if var_mapping and isinstance(var_mapping, dict):
                for key in sorted(var_mapping.keys()):
                    var_name = var_mapping[key]
                    body_params.append({"type": "text", "text": str(variables.get(var_name, "") or "")})
            else:
                _auto_vars = _auto_detect_template_vars(template_name)
                for var_name in _auto_vars:
                    body_params.append({"type": "text", "text": str(variables.get(var_name, "") or "")})
            components = [{"type": "body", "parameters": body_params}] if body_params else None

        yc = YCloudClient(api_key=api_key, business_number=biz_num)
        await yc.send_template(
            to=phone,
            template_name=template_name,
            language_code=real_lang,
            components=components,
        )
        await _update_message_counters(pool, tenant_id, phone, step)
        logger.info(f"✅ Template '{template_name}' sent to {phone} (lang={real_lang})")
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


async def _action_send_ai_message(pool, tenant_id, phone, step, execution, variables) -> bool:
    """Generate a personalized message using LLM based on conversation history."""
    try:
        # 1. Load conversation history
        recent_messages = await pool.fetch(
            """SELECT role, content, created_at FROM chat_messages
               WHERE tenant_id = $1 AND from_number = $2
               ORDER BY created_at DESC LIMIT 20""",
            tenant_id, phone,
        )

        if not recent_messages:
            logger.info(f"[ai_message] No conversation history for {phone}, skipping")
            return True  # No messages = nothing to follow up on

        # Build conversation context
        conversation = "\n".join([
            f"{'Paciente' if m['role'] == 'user' else 'Bot'}: {m['content'][:200]}"
            for m in reversed(recent_messages) if m.get('content')
        ])

        # 2. Get model from system_config
        model = "gpt-4o-mini"
        try:
            model_row = await pool.fetchrow(
                "SELECT value FROM system_config WHERE key = 'OPENAI_MODEL' AND tenant_id = $1",
                tenant_id,
            )
            if model_row and model_row.get("value"):
                model = str(model_row["value"]).strip()
        except Exception:
            pass

        # 3. Build prompt
        custom_instructions = step.get("message_text") or ""
        patient_name = variables.get("nombre_paciente", "")
        treatment = variables.get("tratamiento", "")

        prompt = f"""Sos un asistente de seguimiento para una clínica dental. Analizá esta conversación con un paciente y generá UN mensaje de seguimiento personalizado.

CONVERSACIÓN RECIENTE:
{conversation}

DATOS DEL PACIENTE:
- Nombre: {patient_name}
- Tratamiento de interés: {treatment or 'No especificado'}

REGLAS:
1. Si el paciente ya dijo que no le interesa, ya agendó, o pidió que no le escriban → respondé EXACTAMENTE "NO_ENVIAR" (sin nada más)
2. Si tiene sentido hacer seguimiento → generá un mensaje corto, cálido, consultivo
3. Tono: humano, empático, no vendedor, no robótico
4. Máximo 3 líneas
5. NO uses emojis excesivos (máximo 1-2)
6. NO menciones que sos un bot o IA
{f'7. INSTRUCCIONES ADICIONALES: {custom_instructions}' if custom_instructions else ''}

Respondé SOLO con el mensaje a enviar, o "NO_ENVIAR" si no corresponde."""

        # 4. Call LLM
        import openai
        client = openai.AsyncOpenAI()
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.7,
        )

        message = (response.choices[0].message.content or "").strip()

        # 5. Check if LLM says to skip
        if not message or message.upper() == "NO_ENVIAR" or "NO_ENVIAR" in message.upper():
            logger.info(f"[ai_message] LLM decided not to send message to {phone} — skipping")
            return True  # Not a failure, LLM decided it's not worth it

        # 6. Send the message
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
        logger.info(f"✅ AI-generated message sent to {phone}: {message[:60]}...")
        return True

    except Exception as e:
        logger.error(f"❌ send_ai_message failed for {phone}: {e}")
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

    is_message = current_step["action_type"] in ("send_template", "send_text", "send_instructions", "send_ai_message")
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


async def check_appointment_reminders():
    """Periodic check: find appointments happening tomorrow and create executions for reminder playbooks."""
    try:
        from db import db
        if not db.pool:
            return

        # Find all active playbooks with appointment_reminder trigger
        playbooks = await db.pool.fetch("""
            SELECT id, tenant_id, trigger_config, conditions
            FROM automation_playbooks
            WHERE trigger_type = 'appointment_reminder' AND is_active = true
        """)

        if not playbooks:
            return

        from jobs.playbook_triggers import create_execution_for_event

        for pb in playbooks:
            tenant_id = pb["tenant_id"]
            config = pb["trigger_config"] or {}
            if isinstance(config, str):
                import json as _json
                try:
                    config = _json.loads(config)
                except (json.JSONDecodeError, TypeError):
                    config = {}
            hours_before = config.get("hours_before", 24)

            # Find appointments in the reminder window that don't already have an execution
            appointments = await db.pool.fetch("""
                SELECT a.id, a.patient_id, a.professional_id, a.appointment_datetime,
                       a.appointment_type, a.status,
                       p.phone_number
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id AND p.tenant_id = a.tenant_id
                WHERE a.tenant_id = $1
                  AND a.status IN ('scheduled', 'confirmed')
                  AND a.appointment_datetime > NOW()
                  AND a.appointment_datetime <= NOW() + INTERVAL '1 hour' * $2
                  AND p.phone_number IS NOT NULL AND p.phone_number != ''
                  AND NOT EXISTS (
                      SELECT 1 FROM automation_executions ae
                      WHERE ae.playbook_id = $3 AND ae.appointment_id = a.id::text
                        AND ae.status IN ('running', 'waiting_response', 'paused', 'completed')
                  )
                LIMIT 50
            """, tenant_id, hours_before, pb["id"])

            for apt in appointments:
                context = {
                    "appointment_type": apt["appointment_type"],
                    "professional_id": apt["professional_id"],
                    "patient_id": apt["patient_id"],
                    "appointment_datetime": str(apt["appointment_datetime"]),
                }
                await create_execution_for_event(
                    db.pool, tenant_id, "appointment_reminder",
                    apt["phone_number"],
                    patient_id=apt["patient_id"],
                    appointment_id=str(apt["id"]),
                    context=context,
                )

            if appointments:
                logger.info(f"📋 Appointment reminder trigger: {len(appointments)} appointments for tenant {tenant_id}")

    except Exception as e:
        logger.error(f"❌ check_appointment_reminders error: {e}")


async def check_leads_without_booking():
    """Periodic check: find leads who chatted in the last 24h but have no appointment."""
    try:
        from db import db
        if not db.pool:
            return

        # Find all active playbooks with lead_no_booking trigger
        playbooks = await db.pool.fetch("""
            SELECT id, tenant_id, trigger_config, conditions
            FROM automation_playbooks
            WHERE trigger_type = 'lead_no_booking' AND is_active = true
        """)

        if not playbooks:
            return

        from jobs.playbook_triggers import create_execution_for_event

        for pb in playbooks:
            tenant_id = pb["tenant_id"]

            # Find patients with chat messages in the last 24h but no appointments at all
            leads = await db.pool.fetch("""
                SELECT DISTINCT p.id, p.phone_number, p.first_name
                FROM patients p
                WHERE p.tenant_id = $1
                  AND p.phone_number IS NOT NULL AND p.phone_number != ''
                  AND p.created_at > NOW() - INTERVAL '24 hours'
                  AND EXISTS (
                      SELECT 1 FROM chat_messages cm
                      JOIN chat_conversations cc ON cm.conversation_id = cc.id
                      WHERE cc.tenant_id = $1 AND cc.external_user_id = p.phone_number
                        AND cm.created_at > NOW() - INTERVAL '24 hours'
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM appointments a
                      WHERE a.patient_id = p.id AND a.tenant_id = $1
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM automation_executions ae
                      WHERE ae.playbook_id = $2 AND ae.phone_number = p.phone_number
                        AND ae.status IN ('running', 'waiting_response', 'paused', 'completed')
                        AND ae.created_at > NOW() - INTERVAL '48 hours'
                  )
                LIMIT 30
            """, tenant_id, pb["id"])

            for lead in leads:
                await create_execution_for_event(
                    db.pool, tenant_id, "lead_no_booking",
                    lead["phone_number"],
                    patient_id=lead["id"],
                    context={"patient_name": lead["first_name"] or ""},
                )

            if leads:
                logger.info(f"📋 Lead no-booking trigger: {len(leads)} leads for tenant {tenant_id}")

    except Exception as e:
        logger.error(f"❌ check_leads_without_booking error: {e}")


# Register with scheduler
scheduler.add_job(process_pending_executions, 300, run_at_startup=False)
scheduler.add_job(check_inactive_patients, 86400, run_at_startup=False)  # Daily
scheduler.add_job(daily_reset_counters, 86400, run_at_startup=False)  # Daily
scheduler.add_job(check_appointment_reminders, 86400, run_at_startup=False)  # Daily
scheduler.add_job(check_leads_without_booking, 1800, run_at_startup=False)  # Every 30 min
