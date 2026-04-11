"""
Job de seguimiento post-atención para pacientes atendidos.
Se ejecuta diariamente a las 11:00 AM.

Lógica:
- Si el tratamiento tiene una regla HSM en automation_rules (post_treatment_followup),
  SKIP — el profesional debe marcar "Finalizar Tratamiento" manualmente para disparar
  el HSM (ver admin_routes.complete_treatment).
- Si NO tiene regla HSM, envía un mensaje genérico de seguimiento por WhatsApp
  como fallback (solo para turnos completados ayer que no sean consultas simples).
"""

import logging
import os
import json
from datetime import datetime, timedelta, date
from typing import Dict, Any

from .scheduler import schedule_daily_at

logger = logging.getLogger(__name__)


@schedule_daily_at(hour=11, minute=0)
async def send_post_treatment_followups():
    """Envía seguimientos post-atención a pacientes atendidos ayer (fallback sin HSM)."""
    logger.info("🚀 Iniciando job de seguimiento post-atención...")

    try:
        from db import db

        yesterday = date.today() - timedelta(days=1)
        yesterday_start = datetime.combine(yesterday, datetime.min.time())
        yesterday_end = datetime.combine(yesterday, datetime.max.time())

        logger.info(f"📅 Buscando turnos completados para: {yesterday.strftime('%Y-%m-%d')}")

        # FIX #1: appointment_type (not treatment_type)
        # FIX #5: AND + != instead of broken OR
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
            WHERE a.status = 'completed'
                AND a.appointment_datetime >= $1
                AND a.appointment_datetime <= $2
                AND (a.followup_sent IS NULL OR a.followup_sent = false)
                AND p.phone_number IS NOT NULL
                AND p.phone_number != ''
                AND a.appointment_type IS NOT NULL
                AND a.appointment_type != 'consultation'
            ORDER BY a.appointment_datetime
        """, yesterday_start, yesterday_end)

        logger.info(f"📊 Turnos para seguimiento encontrados: {len(appointments)}")

        if not appointments:
            logger.info("✅ No hay pacientes para seguimiento post-atención de ayer")
            return

        sent_count = 0
        skip_count = 0
        error_count = 0

        for apt in appointments:
            try:
                tenant_id = apt["tenant_id"]
                treatment_code = apt["appointment_type"]

                # FIX #2: Skip if an HSM rule exists for this treatment
                # (profesional should use "Finalizar Tratamiento" manually)
                hsm_rule = await db.pool.fetchval("""
                    SELECT id FROM automation_rules
                    WHERE tenant_id = $1
                      AND trigger_type = 'post_treatment_followup'
                      AND is_active = TRUE
                      AND condition_json->>'treatment_code' = $2
                    LIMIT 1
                """, tenant_id, treatment_code)

                if hsm_rule:
                    logger.info(
                        f"⏭️ Skip followup for {apt['first_name']} — HSM rule #{hsm_rule} exists "
                        f"for '{treatment_code}' (requires manual completion)"
                    )
                    skip_count += 1
                    continue

                # No HSM rule — send generic fallback message
                apt_date = apt["appointment_datetime"].strftime("%d/%m")
                patient_name = apt["first_name"]
                message = (
                    f"Hola {patient_name}, te escribimos para saber cómo te sentís "
                    f"después de la atención de ayer ({apt_date}). "
                    f"¿Tuviste alguna molestia o va todo bien?"
                )

                sent = await _send_via_response_sender(
                    tenant_id=tenant_id,
                    phone=apt["phone_number"],
                    message=message,
                )

                if sent:
                    await db.pool.execute(
                        "UPDATE appointments SET followup_sent = true, followup_sent_at = NOW() WHERE id = $1 AND tenant_id = $2",
                        apt["appointment_id"], tenant_id,
                    )
                    # Log to automation_logs
                    await _log_followup(tenant_id, "sent", patient_name, apt["phone_number"], message)
                    logger.info(f"✅ Seguimiento enviado a {patient_name} ({apt['phone_number']})")
                    sent_count += 1
                else:
                    await _log_followup(tenant_id, "failed", patient_name, apt["phone_number"], message, error_detail="send_failed")
                    error_count += 1

            except Exception as e:
                logger.error(f"❌ Error procesando seguimiento para turno {apt.get('appointment_id')}: {e}")
                error_count += 1

        logger.info(f"📊 RESUMEN FOLLOWUP: {sent_count} enviados, {skip_count} con HSM (skip), {error_count} errores")

    except Exception as e:
        logger.error(f"❌ Error en job de seguimiento post-atención: {e}")


async def _send_via_response_sender(tenant_id: int, phone: str, message: str) -> bool:
    """Send a message using the ResponseSender (same as lead recovery)."""
    try:
        from db import db

        # Find the conversation for this phone
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

        # No conversation found — send directly via YCloud
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
        logger.error(f"❌ followup send failed ({phone}): {e}")
        return False


async def _log_followup(
    tenant_id: int, status: str, patient_name: str, phone: str,
    message_preview: str = None, error_detail: str = None,
):
    """Insert into automation_logs."""
    try:
        from db import db
        await db.pool.execute("""
            INSERT INTO automation_logs (
                tenant_id, rule_name, trigger_type, patient_name, phone_number,
                channel, message_type, message_preview, status, error_details,
                triggered_at, sent_at
            ) VALUES ($1, 'Seguimiento Post-Atención (Auto)', 'post_treatment_followup',
                $2, $3, 'whatsapp', 'free_text', $4, $5, $6,
                NOW(), CASE WHEN $5 = 'sent' THEN NOW() ELSE NULL END)
        """, tenant_id, patient_name, phone,
            (message_preview or "")[:200], status, error_detail)
    except Exception as e:
        logger.warning(f"⚠️ automation_log insert failed (followup): {e}")
