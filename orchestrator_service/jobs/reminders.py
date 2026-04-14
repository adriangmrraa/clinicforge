"""
Job de recordatorios automáticos de turnos por WhatsApp.
Se ejecuta diariamente a las 10:00 AM para recordar turnos del día siguiente.

Respeta la regla 'appointment_reminder' de automation_rules:
- Si la regla está inactiva → no envía
- Si message_type == 'hsm' → envía plantilla YCloud con botones (Confirmar/Reprogramar)
- Si message_type == 'free_text' → usa el mensaje configurado con variables
- Si no hay regla → usa fallback genérico (texto libre)
- Usa credenciales encriptadas del vault (no whatsapp_credentials legacy)

Button response handling is in routes/chat_webhooks.py (intercept before AI agent).
"""

import logging
import json
from datetime import datetime, timedelta, date
from typing import Optional

from .scheduler import schedule_daily_at

logger = logging.getLogger(__name__)

_DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


@schedule_daily_at(hour=10, minute=0)
async def send_appointment_reminders():
    """Envía recordatorios de turnos para el día siguiente."""
    logger.info("🚀 Iniciando job de recordatorios de turnos...")

    try:
        from db import db

        # Use Argentina timezone for "tomorrow" (server runs in UTC)
        try:
            from zoneinfo import ZoneInfo
            _ar_tz = ZoneInfo("America/Argentina/Buenos_Aires")
            today_local = datetime.now(_ar_tz).date()
        except Exception:
            today_local = date.today()
        tomorrow = today_local + timedelta(days=1)
        tomorrow_start = datetime.combine(tomorrow, datetime.min.time())
        tomorrow_end = datetime.combine(tomorrow, datetime.max.time())

        logger.info(f"📅 Buscando turnos para: {tomorrow.strftime('%Y-%m-%d')}")

        appointments = await db.pool.fetch("""
            SELECT
                a.id as appointment_id,
                a.appointment_datetime,
                a.appointment_type,
                a.tenant_id,
                p.id as patient_id,
                p.first_name,
                p.last_name,
                p.phone_number
            FROM appointments a
            INNER JOIN patients p ON a.patient_id = p.id AND p.tenant_id = a.tenant_id
            WHERE a.status IN ('scheduled', 'confirmed')
                AND a.appointment_datetime >= $1
                AND a.appointment_datetime <= $2
                AND (a.reminder_sent IS NULL OR a.reminder_sent = false)
                AND p.phone_number IS NOT NULL
                AND p.phone_number != ''
            ORDER BY a.tenant_id, a.appointment_datetime
        """, tomorrow_start, tomorrow_end)

        logger.info(f"📊 Turnos encontrados: {len(appointments)}")

        if not appointments:
            logger.info("✅ No hay turnos pendientes de recordatorio para mañana")
            return

        # Cache rules per tenant
        _rule_cache: dict[int, Optional[dict]] = {}
        _active_cache: dict[int, bool] = {}

        sent_count = 0
        skip_count = 0
        error_count = 0

        for apt in appointments:
            try:
                tenant_id = apt["tenant_id"]

                # Load rule for tenant (cached) — V2 playbook first, V1 fallback
                if tenant_id not in _rule_cache:
                    # Try V2 playbook (Escudo Anti-Ausencias)
                    pb_row = await db.pool.fetchrow("""
                        SELECT p.id, p.is_active, s.action_type, s.template_name,
                               s.template_lang, s.template_vars, s.message_text
                        FROM automation_playbooks p
                        JOIN automation_steps s ON s.playbook_id = p.id AND s.step_order = 0
                        WHERE p.tenant_id = $1 AND p.trigger_type = 'appointment_reminder'
                        ORDER BY p.is_system DESC LIMIT 1
                    """, tenant_id)
                    if pb_row:
                        _rule_cache[tenant_id] = {
                            "id": pb_row["id"],
                            "is_active": pb_row["is_active"],
                            "message_type": "hsm" if pb_row["action_type"] == "send_template" else "free_text",
                            "ycloud_template_name": pb_row["template_name"],
                            "ycloud_template_lang": pb_row["template_lang"] or "es",
                            "ycloud_template_vars": pb_row["template_vars"],
                            "free_text_message": pb_row["message_text"],
                        }
                        _active_cache[tenant_id] = bool(pb_row["is_active"])
                    else:
                        # Fallback V1
                        rule_row = await db.pool.fetchrow("""
                            SELECT id, is_active, message_type, free_text_message,
                                   ycloud_template_name, ycloud_template_lang,
                                   ycloud_template_vars
                            FROM automation_rules
                            WHERE tenant_id = $1 AND trigger_type = 'appointment_reminder'
                            ORDER BY is_system DESC, created_at ASC LIMIT 1
                        """, tenant_id)
                        _rule_cache[tenant_id] = dict(rule_row) if rule_row else None
                        _active_cache[tenant_id] = bool(rule_row and rule_row["is_active"])

                if not _active_cache.get(tenant_id, True):
                    skip_count += 1
                    continue

                rule = _rule_cache.get(tenant_id)

                # Build variables — convert to tenant timezone for display
                patient_name = apt["first_name"] or "paciente"
                apt_time = apt["appointment_datetime"]
                try:
                    from services.tz_resolver import get_tenant_tz
                    _tz = await get_tenant_tz(tenant_id)
                except Exception:
                    from zoneinfo import ZoneInfo
                    _tz = ZoneInfo("America/Argentina/Buenos_Aires")
                # Convert to local time if naive or UTC
                if apt_time.tzinfo is None:
                    apt_time_local = apt_time  # Assume already local if naive
                else:
                    apt_time_local = apt_time.astimezone(_tz)
                formatted_time = apt_time_local.strftime("%H:%M")
                formatted_date = apt_time_local.strftime("%d/%m")
                day_of_week = _DAYS_ES[apt_time_local.weekday()]

                sent = False
                message_preview = ""

                # --- Decision: HSM template or free text ---
                if rule and rule.get("message_type") == "hsm" and rule.get("ycloud_template_name"):
                    # Use the template configured in the automation rule
                    template_name = rule["ycloud_template_name"]
                    template_lang = rule.get("ycloud_template_lang") or "es"

                    # Build template variables from rule config + appointment data
                    var_map = {
                        "nombre_paciente": patient_name,
                        "first_name": patient_name,
                        "dia_semana": day_of_week,
                        "fecha_turno": formatted_date,
                        "appointment_date": formatted_date,
                        "hora_turno": formatted_time,
                        "appointment_time": formatted_time,
                        "last_name": apt.get("last_name") or "",
                        "treatment_name": apt.get("appointment_type") or "",
                    }

                    # Override with any custom var mappings from the rule
                    rule_vars = rule.get("ycloud_template_vars")
                    if rule_vars and isinstance(rule_vars, dict):
                        for tpl_var, source_key in rule_vars.items():
                            if source_key in var_map:
                                var_map[tpl_var] = var_map[source_key]
                    elif rule_vars and isinstance(rule_vars, str):
                        try:
                            parsed = json.loads(rule_vars)
                            if isinstance(parsed, dict):
                                for tpl_var, source_key in parsed.items():
                                    if source_key in var_map:
                                        var_map[tpl_var] = var_map[source_key]
                        except (json.JSONDecodeError, TypeError):
                            pass

                    # Pass all values in order — _send_template fetches real structure from YCloud
                    components = [
                        {"type": "body", "parameters": [
                            {"type": "text", "text": str(var_map.get("nombre_paciente", "")).strip()},
                            {"type": "text", "text": str(var_map.get("dia_semana", "")).strip()},
                            {"type": "text", "text": str(var_map.get("fecha_turno", "")).strip()},
                            {"type": "text", "text": str(var_map.get("hora_turno", "")).strip()},
                        ]},
                    ]

                    sent = await _send_template(
                        tenant_id, apt["phone_number"],
                        template_name, template_lang, components,
                        patient_name=f"{apt['first_name'] or ''} {apt.get('last_name') or ''}".strip(),
                        appointment_info={
                            "treatment": apt.get("appointment_type") or "Consulta",
                            "date": formatted_date,
                            "time": formatted_time,
                            "day_name": day_of_week,
                            "professional": "Laura Delgado",
                            "appointment_id": str(apt["appointment_id"]),
                        },
                    )
                    message_preview = f"[HSM:{template_name}] {patient_name} - {day_of_week} {formatted_date} {formatted_time}"

                # Fallback: free text (either from rule or generic)
                if not sent:
                    if rule and rule.get("free_text_message"):
                        message = rule["free_text_message"]
                        message = message.replace("{{first_name}}", patient_name)
                        message = message.replace("{{last_name}}", apt.get("last_name") or "")
                        message = message.replace("{{appointment_time}}", formatted_time)
                        message = message.replace("{{appointment_date}}", formatted_date)
                        message = message.replace("{{treatment_name}}", apt.get("appointment_type") or "")
                    else:
                        message = (
                            f"Hola {patient_name}, te recordamos tu turno de mañana "
                            f"a las {formatted_time}. ¿Nos confirmás tu asistencia?"
                        )
                    sent = await _send_text(tenant_id, apt["phone_number"], message, patient_name=f"{apt['first_name'] or ''} {apt.get('last_name') or ''}".strip())
                    message_preview = message

                if sent:
                    await db.pool.execute(
                        "UPDATE appointments SET reminder_sent = true, reminder_sent_at = NOW() WHERE id = $1 AND tenant_id = $2",
                        apt["appointment_id"], tenant_id,
                    )
                    await _log_reminder(tenant_id, "sent", patient_name, apt["phone_number"], message_preview, rule_id=rule["id"] if rule else None, patient_id=apt.get("patient_id"), appointment_id=apt.get("appointment_id"))
                    logger.info(f"✅ Recordatorio enviado a {patient_name} ({apt['phone_number']}) para las {formatted_time}")
                    sent_count += 1
                else:
                    await _log_reminder(tenant_id, "failed", patient_name, apt["phone_number"], message_preview, error_detail="send_failed", rule_id=rule["id"] if rule else None, patient_id=apt.get("patient_id"), appointment_id=apt.get("appointment_id"))
                    error_count += 1

            except Exception as e:
                logger.error(f"❌ Error procesando turno {apt.get('appointment_id')}: {e}")
                error_count += 1

        logger.info(f"📊 RESUMEN RECORDATORIOS: {sent_count} enviados, {skip_count} regla inactiva, {error_count} errores")

    except Exception as e:
        logger.error(f"❌ Error en job de recordatorios: {e}")


async def _send_template(
    tenant_id: int, phone: str,
    template_name: str, language_code: str, components: list,
    patient_name: str = "",
    appointment_info: dict = None,
) -> bool:
    """
    Send a YCloud HSM template. Clean implementation per YCloud v2 docs.

    1. Fetch template details from YCloud API to get the EXACT language code
    2. Build components matching the template structure (header vs body)
    3. Send once with correct params — no blind retries
    """
    try:
        from core.credentials import get_tenant_credential, YCLOUD_API_KEY
        from ycloud_client import YCloudClient
        from db import db as _db_ref
        import httpx

        api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
        if not api_key:
            logger.warning(f"⚠️ No YCloud API key for tenant {tenant_id}")
            return False

        # Resolve from_number: tenants.bot_phone_number first
        business_number = await _db_ref.pool.fetchval(
            "SELECT bot_phone_number FROM tenants WHERE id = $1", tenant_id
        )
        if not business_number:
            from core.credentials import YCLOUD_WHATSAPP_NUMBER
            business_number = await get_tenant_credential(tenant_id, YCLOUD_WHATSAPP_NUMBER)

        logger.info(f"📱 Reminder from_number={business_number} tenant={tenant_id}")

        # Step 1: Fetch template from YCloud to get the REAL language code and structure
        real_lang = None
        tpl_components = None
        try:
            async with httpx.AsyncClient(timeout=10.0) as diag:
                resp = await diag.get(
                    "https://api.ycloud.com/v2/whatsapp/templates",
                    params={"filter.name": template_name, "limit": 10},
                    headers={"X-API-Key": api_key},
                )
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    # Find the APPROVED template
                    for tpl in items:
                        if tpl.get("status") == "APPROVED" and tpl.get("name") == template_name:
                            real_lang = tpl.get("language")
                            tpl_components = tpl.get("components", [])
                            logger.info(f"📋 Template found: lang={real_lang} components={tpl_components}")
                            break
        except Exception as diag_err:
            logger.warning(f"⚠️ Template fetch failed: {diag_err}")

        if not real_lang:
            logger.error(f"❌ Template '{template_name}' not found in YCloud API (no APPROVED version)")
            return False

        # Step 2: Build components matching the EXACT template structure
        # Count variables in each component type
        header_var_count = 0
        body_var_count = 0
        for comp in (tpl_components or []):
            comp_type = comp.get("type", "").upper()
            text = comp.get("text", "")
            # Count {{var}} placeholders
            import re
            var_count = len(re.findall(r'\{\{[^}]+\}\}', text))
            if comp_type == "HEADER":
                header_var_count = var_count
            elif comp_type == "BODY":
                body_var_count = var_count

        logger.info(f"📋 Template vars: header={header_var_count} body={body_var_count}")

        # Count ALL variables across all components (header + body)
        all_var_names = []
        for comp in (tpl_components or []):
            text = comp.get("text", "")
            var_names = re.findall(r'\{\{(\w+)\}\}', text)
            all_var_names.extend(var_names)

        total_vars = len(all_var_names)
        logger.info(f"📋 Template total vars: {total_vars} names={all_var_names}")

        # Flatten all values from input components
        all_values = []
        for comp in (components or []):
            for p in comp.get("parameters", []):
                all_values.append(str(p.get("text", "")).strip())

        # Build components: header params separate from body params, NO parameter_name
        # Meta requires header and body as separate components with correct param counts
        send_components = []
        idx = 0
        for comp in (tpl_components or []):
            comp_type = comp.get("type", "").upper()
            text = comp.get("text", "")
            var_count = len(re.findall(r'\{\{[^}]+\}\}', text))
            if var_count > 0 and comp_type in ("HEADER", "BODY"):
                params = []
                for _ in range(var_count):
                    val = all_values[idx] if idx < len(all_values) else ""
                    params.append({"type": "text", "text": val})
                    idx += 1
                send_components.append({"type": comp_type.lower(), "parameters": params})

        logger.info(f"📤 Sending template: lang={real_lang} components={send_components}")

        # Step 3: Send ONCE with the correct language and components
        yc = YCloudClient(api_key=api_key, business_number=business_number)
        try:
            await yc.send_template(
                to=phone,
                template_name=template_name,
                language_code=real_lang,
                components=send_components if send_components else None,
            )
            logger.info(f"✅ Template '{template_name}' sent to {phone} (lang={real_lang})")
        except httpx.HTTPStatusError as http_err:
            # Log the FULL error response for debugging
            try:
                err_json = http_err.response.json()
                logger.error(f"❌ Template send error FULL: {err_json}")
            except Exception:
                logger.error(f"❌ Template send error: {http_err.response.text}")
            return False

        # Persist in chat_conversations + chat_messages so it appears in the UI
        try:
            from db import db as _db
            import uuid as _uuid
            import json as _json

            # Upsert conversation
            conv = await _db.pool.fetchrow(
                "SELECT id FROM chat_conversations WHERE tenant_id = $1 AND external_user_id = $2 AND channel = 'whatsapp' ORDER BY updated_at DESC LIMIT 1",
                tenant_id, phone,
            )
            if conv:
                conv_id = conv["id"]
                await _db.pool.execute(
                    "UPDATE chat_conversations SET last_message_preview = $1, updated_at = NOW() WHERE id = $2",
                    f"[Recordatorio: {template_name}]", conv_id,
                )
            else:
                conv_id = _uuid.uuid4()
                await _db.pool.execute(
                    "INSERT INTO chat_conversations (id, tenant_id, channel, provider, external_user_id, display_name, last_message_preview, status, updated_at) VALUES ($1, $2, 'whatsapp', 'ycloud', $3, $4, $5, 'active', NOW())",
                    conv_id, tenant_id, phone, patient_name or None, f"[Recordatorio: {template_name}]",
                )

            # Persist message with full clinical context
            apt_info = appointment_info or {}
            preview = f"📅 Recordatorio de turno enviado"
            if apt_info.get("treatment"):
                preview += f"\n🦷 {apt_info['treatment']}"
            if apt_info.get("date") and apt_info.get("time"):
                preview += f"\n📆 {apt_info.get('day_name', '')} {apt_info['date']} a las {apt_info['time']}"
            if apt_info.get("professional"):
                preview += f"\n👩‍⚕️ Con {apt_info['professional']}"
            if patient_name:
                preview += f"\n👤 {patient_name}"

            await _db.pool.execute(
                "INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, platform_metadata) VALUES ($1, $2, 'assistant', $3, $4, $5::jsonb)",
                tenant_id, conv_id, preview, phone,
                _json.dumps({
                    "source": "reminder_template",
                    "template": template_name,
                    "patient_name": patient_name,
                    "appointment": apt_info,
                }),
            )
        except Exception as _persist_err:
            logger.warning(f"⚠️ Reminder persist failed (non-blocking): {_persist_err}")

        return True

    except Exception as e:
        logger.warning(f"⚠️ Template send failed for {phone}: {e}")
        return False


async def _send_text(tenant_id: int, phone: str, message: str, patient_name: str = "") -> bool:
    """Send a text message via YCloud and persist in chat_messages."""
    try:
        from db import db
        import uuid as _uuid
        import json as _json
        from core.credentials import get_tenant_credential, YCLOUD_API_KEY
        from ycloud_client import YCloudClient

        api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
        if not api_key:
            logger.warning(f"⚠️ No YCloud API key for tenant {tenant_id}")
            return False

        # Use bot_phone_number from tenants
        business_number = await db.pool.fetchval(
            "SELECT bot_phone_number FROM tenants WHERE id = $1", tenant_id
        )
        if not business_number:
            from core.credentials import YCLOUD_WHATSAPP_NUMBER
            business_number = await get_tenant_credential(tenant_id, YCLOUD_WHATSAPP_NUMBER)

        # Send via YCloud
        yc = YCloudClient(api_key=api_key, business_number=business_number)
        await yc.send_text_message(to=phone, text=message, from_number=business_number)

        # Persist: upsert conversation + insert message
        try:
            conv = await db.pool.fetchrow(
                "SELECT id FROM chat_conversations WHERE tenant_id = $1 AND external_user_id = $2 ORDER BY updated_at DESC LIMIT 1",
                tenant_id, phone,
            )
            if conv:
                conv_id = conv["id"]
                await db.pool.execute(
                    "UPDATE chat_conversations SET last_message_preview = $1, updated_at = NOW() WHERE id = $2",
                    message[:200], conv_id,
                )
            else:
                conv_id = _uuid.uuid4()
                await db.pool.execute(
                    "INSERT INTO chat_conversations (id, tenant_id, channel, provider, external_user_id, display_name, last_message_preview, status, updated_at) VALUES ($1, $2, 'whatsapp', 'ycloud', $3, $4, $5, 'active', NOW())",
                    conv_id, tenant_id, phone, patient_name or None, message[:200],
                )

            await db.pool.execute(
                "INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, platform_metadata) VALUES ($1, $2, 'assistant', $3, $4, $5::jsonb)",
                tenant_id, conv_id, message, phone,
                _json.dumps({"source": "reminder_text"}),
            )
        except Exception as _p:
            logger.warning(f"⚠️ Reminder text persist failed (non-blocking): {_p}")

        return True

    except Exception as e:
        logger.error(f"❌ reminder send failed ({phone}): {e}")
        return False


async def _log_reminder(
    tenant_id: int, status: str, patient_name: str, phone: str,
    message_preview: str = None, error_detail: str = None,
    skip_reason: str = None, rule_id: int = None,
    patient_id: int = None, appointment_id: str = None,
):
    """Insert into automation_logs with patient and appointment linkage."""
    try:
        from db import db
        import json as _json
        meta = {}
        if appointment_id:
            meta["appointment_id"] = str(appointment_id)
        if patient_name:
            meta["patient_name"] = patient_name

        _status = str(status) if status else 'unknown'
        # rule_id may be a playbook ID (not in automation_rules) — validate FK exists
        _valid_rule_id = None
        if rule_id:
            _exists = await db.pool.fetchval(
                "SELECT id FROM automation_rules WHERE id = $1", rule_id
            )
            if _exists:
                _valid_rule_id = rule_id

        await db.pool.execute("""
            INSERT INTO automation_logs (
                tenant_id, automation_rule_id, rule_name, trigger_type,
                patient_name, phone_number, channel, message_type,
                message_preview, status, skip_reason, error_details,
                patient_id, target_id, meta,
                triggered_at, sent_at
            ) VALUES ($1, $2, 'Recordatorio 24h', 'appointment_reminder',
                $3, $4, 'whatsapp', 'hsm', $5, $6::varchar, $7, $8,
                $9, $10, $11::jsonb,
                NOW(), CASE WHEN $6::varchar = 'sent' THEN NOW() ELSE NULL END)
        """, tenant_id, _valid_rule_id, patient_name, phone,
            (message_preview or "")[:200], _status, skip_reason, error_detail,
            patient_id, str(appointment_id) if appointment_id else None,
            _json.dumps(meta) if meta else '{}')
    except Exception as e:
        logger.warning(f"⚠️ automation_log insert failed (reminders): {e}")
