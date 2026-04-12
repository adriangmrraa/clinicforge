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

        tomorrow = date.today() + timedelta(days=1)
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

                # Load rule for tenant (cached)
                if tenant_id not in _rule_cache:
                    rule_row = await db.pool.fetchrow("""
                        SELECT id, is_active, message_type, free_text_message,
                               ycloud_template_name, ycloud_template_lang,
                               ycloud_template_vars,
                               send_hour_min, send_hour_max
                        FROM automation_rules
                        WHERE tenant_id = $1
                          AND trigger_type = 'appointment_reminder'
                        ORDER BY is_system DESC, created_at ASC
                        LIMIT 1
                    """, tenant_id)
                    _rule_cache[tenant_id] = dict(rule_row) if rule_row else None
                    _active_cache[tenant_id] = bool(rule_row and rule_row["is_active"])

                if not _active_cache.get(tenant_id, True):
                    skip_count += 1
                    continue

                rule = _rule_cache.get(tenant_id)

                # Build variables
                patient_name = apt["first_name"] or "paciente"
                apt_time = apt["appointment_datetime"]
                formatted_time = apt_time.strftime("%H:%M")
                formatted_date = apt_time.strftime("%d/%m")
                day_of_week = _DAYS_ES[apt_time.weekday()]

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

                    # Build components list ordered by variable position
                    # Default order: nombre_paciente, dia_semana, fecha_turno, hora_turno
                    default_var_order = ["nombre_paciente", "dia_semana", "fecha_turno", "hora_turno"]
                    parameters = []
                    for var_name in default_var_order:
                        parameters.append({"type": "text", "text": var_map.get(var_name, "")})

                    components = [{"type": "body", "parameters": parameters}]

                    sent = await _send_template(
                        tenant_id, apt["phone_number"],
                        template_name, template_lang, components,
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
                    sent = await _send_text(tenant_id, apt["phone_number"], message)
                    message_preview = message

                if sent:
                    await db.pool.execute(
                        "UPDATE appointments SET reminder_sent = true, reminder_sent_at = NOW() WHERE id = $1 AND tenant_id = $2",
                        apt["appointment_id"], tenant_id,
                    )
                    await _log_reminder(tenant_id, "sent", patient_name, apt["phone_number"], message_preview, rule_id=rule["id"] if rule else None)
                    logger.info(f"✅ Recordatorio enviado a {patient_name} ({apt['phone_number']}) para las {formatted_time}")
                    sent_count += 1
                else:
                    await _log_reminder(tenant_id, "failed", patient_name, apt["phone_number"], message_preview, error_detail="send_failed", rule_id=rule["id"] if rule else None)
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
) -> bool:
    """Send a YCloud HSM template (with buttons)."""
    try:
        from core.credentials import get_tenant_credential, YCLOUD_API_KEY, YCLOUD_WHATSAPP_NUMBER
        from ycloud_client import YCloudClient

        api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
        business_number = await get_tenant_credential(tenant_id, YCLOUD_WHATSAPP_NUMBER)
        if not api_key:
            logger.warning(f"⚠️ No YCloud API key for tenant {tenant_id}")
            return False

        yc = YCloudClient(api_key=api_key, business_number=business_number)
        await yc.send_template(
            to=phone,
            template_name=template_name,
            language_code=language_code,
            components=components,
        )
        logger.info(f"✅ Template '{template_name}' sent to {phone} (tenant {tenant_id})")
        return True

    except Exception as e:
        logger.warning(f"⚠️ Template send failed for {phone}: {e}")
        return False


async def _send_text(tenant_id: int, phone: str, message: str) -> bool:
    """Send a text message using ResponseSender (conversation-aware) or YCloud direct."""
    try:
        from db import db

        conv = await db.pool.fetchrow(
            "SELECT id, provider, channel, external_account_id, external_chatwoot_id "
            "FROM chat_conversations WHERE tenant_id = $1 AND external_user_id = $2 "
            "ORDER BY updated_at DESC LIMIT 1",
            tenant_id, phone,
        )

        if conv:
            from services.response_sender import ResponseSender
            await ResponseSender.send_sequence(
                tenant_id=tenant_id,
                external_user_id=phone,
                conversation_id=str(conv["id"]),
                provider=conv.get("provider") or "ycloud",
                channel=conv.get("channel") or "whatsapp",
                account_id=str(conv.get("external_account_id") or ""),
                cw_conv_id=str(conv.get("external_chatwoot_id") or ""),
                messages_text=message,
            )
            return True

        from core.credentials import get_tenant_credential, YCLOUD_API_KEY, YCLOUD_WHATSAPP_NUMBER
        from ycloud_client import YCloudClient

        api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
        business_number = await get_tenant_credential(tenant_id, YCLOUD_WHATSAPP_NUMBER)
        if not api_key:
            logger.warning(f"⚠️ No YCloud API key for tenant {tenant_id}")
            return False

        yc = YCloudClient(api_key=api_key, business_number=business_number)
        await yc.send_text_message(to=phone, text=message)
        return True

    except Exception as e:
        logger.error(f"❌ reminder send failed ({phone}): {e}")
        return False


async def _log_reminder(
    tenant_id: int, status: str, patient_name: str, phone: str,
    message_preview: str = None, error_detail: str = None,
    skip_reason: str = None, rule_id: int = None,
):
    """Insert into automation_logs."""
    try:
        from db import db
        await db.pool.execute("""
            INSERT INTO automation_logs (
                tenant_id, automation_rule_id, rule_name, trigger_type,
                patient_name, phone_number, channel, message_type,
                message_preview, status, skip_reason, error_details,
                triggered_at, sent_at
            ) VALUES ($1, $2, 'Recordatorio 24h', 'appointment_reminder',
                $3, $4, 'whatsapp', 'hsm', $5, $6, $7, $8,
                NOW(), CASE WHEN $6 = 'sent' THEN NOW() ELSE NULL END)
        """, tenant_id, rule_id, patient_name, phone,
            (message_preview or "")[:200], status, skip_reason, error_detail)
    except Exception as e:
        logger.warning(f"⚠️ automation_log insert failed (reminders): {e}")
