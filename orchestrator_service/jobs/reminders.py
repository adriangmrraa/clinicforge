"""
Job de recordatorios automáticos de turnos por WhatsApp.
Se ejecuta diariamente a las 10:00 AM para recordar turnos del día siguiente.

CLINICASV1.0 - Sistema Automatizado de Recordatorios
"""

import logging
import asyncio
from datetime import datetime, timedelta, date
from typing import List, Dict, Any
import json

from .scheduler import schedule_daily_at

logger = logging.getLogger(__name__)


async def _log_automation_reminder(tenant_id, status, patient_name, phone_number, message_preview, error_detail=None, skip_reason=None):
    """Helper: escribe en automation_logs para el job de recordatorios."""
    try:
        from db import db
        await db.pool.execute("""
            INSERT INTO automation_logs (tenant_id, rule_name, trigger_type, patient_name, phone_number,
                channel, message_type, message_preview, status, skip_reason, error_details,
                triggered_at, sent_at)
            VALUES ($1,'Recordatorio 24h','appointment_reminder',$2,$3,'whatsapp','free_text',$4,$5,$6,$7,
                NOW(), CASE WHEN $5='sent' THEN NOW() ELSE NULL END)
        """, tenant_id, patient_name, phone_number,
            message_preview[:200] if message_preview else None,
            status, skip_reason, error_detail)
    except Exception as e:
        logger.warning(f"⚠️ No se pudo escribir automation_log (reminders): {e}")


@schedule_daily_at(hour=10, minute=0)  # Ejecutar todos los días a las 10:00 AM
async def send_appointment_reminders():
    """
    Job principal: Envía recordatorios de turnos para el día siguiente.
    
    Flujo:
    1. Busca turnos con status='scheduled' para mañana
    2. Filtra aquellos sin reminder_sent=True
    3. Obtiene datos del paciente y credenciales del tenant
    4. Envía mensaje por WhatsApp usando whatsapp_service
    5. Actualiza reminder_sent y reminder_sent_at
    """
    logger.info("🚀 Iniciando job de recordatorios de turnos...")
    
    try:
        from db import db
        
        # Calcular fecha de mañana
        tomorrow = date.today() + timedelta(days=1)
        tomorrow_start = datetime.combine(tomorrow, datetime.min.time())
        tomorrow_end = datetime.combine(tomorrow, datetime.max.time())
        
        logger.info(f"📅 Buscando turnos para: {tomorrow.strftime('%Y-%m-%d')}")
        
        # Query para obtener turnos del día siguiente
        appointments = await db.pool.fetch("""
            SELECT 
                a.id as appointment_id,
                a.appointment_datetime,
                a.status,
                a.reminder_sent,
                p.id as patient_id,
                p.first_name,
                p.last_name,
                p.phone_number,
                t.id as tenant_id,
                t.name as tenant_name,
                t.whatsapp_credentials
            FROM appointments a
            INNER JOIN patients p ON a.patient_id = p.id AND p.tenant_id = a.tenant_id
            INNER JOIN tenants t ON a.tenant_id = t.id
            WHERE a.status = 'scheduled'
                AND a.appointment_datetime >= $1
                AND a.appointment_datetime <= $2
                AND (a.reminder_sent IS NULL OR a.reminder_sent = false)
                AND p.phone_number IS NOT NULL
                AND p.phone_number != ''
            ORDER BY a.appointment_datetime
        """, tomorrow_start, tomorrow_end)
        
        logger.info(f"📊 Turnos encontrados: {len(appointments)}")
        
        if not appointments:
            logger.info("✅ No hay turnos pendientes de recordatorio para mañana")
            return
        
        # Contadores para estadísticas
        sent_count = 0
        error_count = 0
        
        for apt in appointments:
            try:
                # Formatear hora del turno
                apt_time = apt["appointment_datetime"]
                formatted_time = apt_time.strftime("%H:%M")
                
                # Construir mensaje personalizado
                patient_name = apt["first_name"]
                message = (
                    f"Hola {patient_name}, te escribimos del consultorio de la Dra. Delgado "
                    f"para recordarte tu turno de mañana a las {formatted_time}. "
                    f"¿Me confirmás tu asistencia?"
                )
                
                # Obtener credenciales de WhatsApp del tenant
                whatsapp_creds = apt["whatsapp_credentials"]
                if not whatsapp_creds:
                    logger.warning(f"⚠️ Tenant {apt['tenant_id']} no tiene credenciales de WhatsApp configuradas")
                    await _log_automation_reminder(apt["tenant_id"], "skipped", patient_name, apt["phone_number"], message, skip_reason="Sin credenciales WhatsApp")
                    error_count += 1
                    continue
                
                # Enviar mensaje por WhatsApp
                success = await send_whatsapp_message(
                    phone_number=apt["phone_number"],
                    message=message,
                    tenant_id=apt["tenant_id"],
                    whatsapp_creds=whatsapp_creds
                )
                
                if success:
                    # Actualizar estado del recordatorio
                    await db.pool.execute("""
                        UPDATE appointments 
                        SET reminder_sent = true, 
                            reminder_sent_at = NOW(),
                            updated_at = NOW()
                        WHERE id = $1 AND tenant_id = $2
                    """, apt["appointment_id"], apt["tenant_id"])
                    await _log_automation_reminder(apt["tenant_id"], "sent", patient_name, apt["phone_number"], message)
                    logger.info(f"✅ Recordatorio enviado a {patient_name} ({apt['phone_number']}) para las {formatted_time}")
                    sent_count += 1
                else:
                    await _log_automation_reminder(apt["tenant_id"], "failed", patient_name, apt["phone_number"], message, error_detail="WhatsApp service error")
                    logger.error(f"❌ Error al enviar recordatorio a {patient_name}")
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"❌ Error procesando turno {apt.get('appointment_id')}: {e}")
                error_count += 1
        
        # Log de resumen
        logger.info(f"📊 RESUMEN JOB: {sent_count} enviados, {error_count} errores")
        
    except Exception as e:
        logger.error(f"❌ Error en job de recordatorios: {e}")
        raise


async def send_whatsapp_message(phone_number: str, message: str, tenant_id: int, whatsapp_creds: Dict[str, Any]) -> bool:
    """
    Envía mensaje por WhatsApp usando el servicio existente.
    
    Args:
        phone_number: Número de teléfono del paciente
        message: Mensaje a enviar
        tenant_id: ID del tenant para aislamiento
        whatsapp_creds: Credenciales de WhatsApp del tenant
        
    Returns:
        bool: True si se envió correctamente, False en caso de error
    """
    try:
        # El servicio de WhatsApp está en un contenedor separado
        # Usamos HTTP para comunicarnos con él
        import httpx
        import os
        
        # Obtener URL del servicio de WhatsApp desde variables de entorno
        whatsapp_service_url = os.getenv("WHATSAPP_SERVICE_URL", "http://whatsapp_service:8000")
        
        # Headers para autenticación interna
        internal_token = os.getenv("INTERNAL_API_TOKEN")
        if not internal_token:
            logger.error("❌ INTERNAL_API_TOKEN no configurado")
            return False
        
        headers = {
            "X-Internal-Token": internal_token,
            "Content-Type": "application/json",
            "X-Correlation-Id": f"reminder-{tenant_id}-{datetime.now().timestamp()}"
        }
        
        # Payload para enviar mensaje
        payload = {
            "to": phone_number,
            "text": message,
            "tenant_id": tenant_id  # Para que el servicio use las credenciales correctas
        }
        
        # Enviar mensaje
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{whatsapp_service_url}/send",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Mensaje enviado a {phone_number}: {result.get('status', 'unknown')}")
                return True
            else:
                logger.error(f"❌ Error al enviar mensaje: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error enviando WhatsApp: {e}")
        return False


async def send_whatsapp_fallback(phone_number: str, message: str, tenant_id: int) -> bool:
    """
    Fallback para enviar mensajes si WhatsAppService no está disponible.
    Usa el endpoint HTTP del whatsapp_service.
    """
    try:
        import httpx
        
        # URL del servicio de WhatsApp (ajustar según configuración)
        whatsapp_url = "http://whatsapp_service:8000/send_message"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(whatsapp_url, json={
                "tenant_id": tenant_id,
                "phone_number": phone_number,
                "message": message,
                "message_type": "text"
            })
            
            return response.status_code == 200
            
    except Exception as e:
        logger.error(f"❌ Error en fallback de WhatsApp: {e}")
        return False


async def test_reminder_for_today():
    """
    Función de testing: envía recordatorios para turnos de hoy.
    Útil para pruebas sin tener que esperar a mañana.
    """
    logger.info("🧪 Ejecutando TEST de recordatorios para hoy...")
    
    try:
        from db import db
        
        # Usar fecha de hoy en lugar de mañana
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # Buscar un turno de prueba (el primero que encuentre)
        test_appointment = await db.pool.fetchrow("""
            SELECT 
                a.id as appointment_id,
                a.appointment_datetime,
                p.first_name,
                p.phone_number,
                t.id as tenant_id,
                t.whatsapp_credentials
            FROM appointments a
            INNER JOIN patients p ON a.patient_id = p.id
            INNER JOIN tenants t ON a.tenant_id = t.id
            WHERE a.status = 'scheduled'
                AND a.appointment_datetime >= $1
                AND a.appointment_datetime <= $2
                AND p.phone_number IS NOT NULL
            LIMIT 1
        """, today_start, today_end)
        
        if not test_appointment:
            logger.warning("⚠️ No hay turnos de hoy para probar")
            return False
        
        # Enviar mensaje de prueba
        apt_time = test_appointment["appointment_datetime"]
        formatted_time = apt_time.strftime("%H:%M")
        patient_name = test_appointment["first_name"]
        
        test_message = (
            f"🔧 [TEST] Hola {patient_name}, este es un mensaje de prueba del sistema "
            f"de recordatorios. Tu turno de hoy es a las {formatted_time}."
        )
        
        success = await send_whatsapp_message(
            phone_number=test_appointment["phone_number"],
            message=test_message,
            tenant_id=test_appointment["tenant_id"],
            whatsapp_creds=test_appointment["whatsapp_credentials"]
        )
        
        if success:
            logger.info(f"✅ Test exitoso: mensaje enviado a {patient_name}")
        else:
            logger.error(f"❌ Test fallido: no se pudo enviar a {patient_name}")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ Error en test: {e}")
        return False