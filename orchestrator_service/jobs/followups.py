"""
Job de seguimiento post-atención para pacientes de cirugía.
Se ejecuta diariamente a las 11:00 AM para contactar pacientes atendidos el día anterior.

CLINICASV1.0 - Sistema de Seguimiento Clínico Automatizado
"""

import logging
import asyncio
from datetime import datetime, timedelta, date
from typing import List, Dict, Any
import json

from .scheduler import schedule_daily_at

logger = logging.getLogger(__name__)


@schedule_daily_at(hour=11, minute=0)  # Ejecutar todos los días a las 11:00 AM
async def send_post_treatment_followups():
    """
    Job principal: Envía seguimientos post-atención a pacientes atendidos ayer.
    
    Flujo:
    1. Busca turnos con status='completed' de ayer
    2. Filtra aquellos sin followup_sent=True
    3. Obtiene datos del paciente y credenciales del tenant
    4. Envía mensaje de seguimiento por WhatsApp
    5. Actualiza followup_sent y followup_sent_at
    6. Marca el hilo como "seguimiento post-atención" para el agente LLM
    """
    logger.info("🚀 Iniciando job de seguimiento post-atención...")
    
    try:
        from db import db
        
        # Calcular fecha de ayer
        yesterday = date.today() - timedelta(days=1)
        yesterday_start = datetime.combine(yesterday, datetime.min.time())
        yesterday_end = datetime.combine(yesterday, datetime.max.time())
        
        logger.info(f"📅 Buscando turnos completados para: {yesterday.strftime('%Y-%m-%d')}")
        
        # Query para obtener turnos completados ayer
        appointments = await db.pool.fetch("""
            SELECT 
                a.id as appointment_id,
                a.appointment_datetime,
                a.status,
                a.followup_sent,
                a.treatment_type,
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
            WHERE a.status = 'completed'
                AND a.appointment_datetime >= $1
                AND a.appointment_datetime <= $2
                AND (a.followup_sent IS NULL OR a.followup_sent = false)
                AND p.phone_number IS NOT NULL
                AND p.phone_number != ''
                -- Solo seguimiento para tratamientos/cirugías (no consultas simples)
                AND (a.treatment_type IS NOT NULL OR a.treatment_type != 'consultation')
            ORDER BY a.appointment_datetime
        """, yesterday_start, yesterday_end)
        
        logger.info(f"📊 Turnos para seguimiento encontrados: {len(appointments)}")
        
        if not appointments:
            logger.info("✅ No hay pacientes para seguimiento post-atención de ayer")
            return
        
        # Contadores para estadísticas
        sent_count = 0
        error_count = 0
        
        for apt in appointments:
            try:
                # Formatear fecha del turno
                apt_date = apt["appointment_datetime"].strftime("%d/%m")
                
                # Construir mensaje personalizado
                patient_name = apt["first_name"]
                message = (
                    f"Hola {patient_name}, soy la asistente de la Dra. Delgado. "
                    f"Te escribo para saber cómo te sentís hoy después de la atención de ayer ({apt_date}). "
                    f"¿Tuviste alguna molestia o va todo bien?"
                )
                
                # Obtener credenciales de WhatsApp del tenant
                whatsapp_creds = apt["whatsapp_credentials"]
                if not whatsapp_creds:
                    logger.warning(f"⚠️ Tenant {apt['tenant_id']} no tiene credenciales de WhatsApp configuradas")
                    error_count += 1
                    continue
                
                # Enviar mensaje por WhatsApp
                success = await send_whatsapp_message(
                    phone_number=apt["phone_number"],
                    message=message,
                    tenant_id=apt["tenant_id"],
                    whatsapp_creds=whatsapp_creds,
                    appointment_id=apt["appointment_id"],
                    is_followup=True  # Marcar como mensaje de seguimiento
                )
                
                if success:
                    # Actualizar estado del seguimiento
                    await db.pool.execute("""
                        UPDATE appointments 
                        SET followup_sent = true, 
                            followup_sent_at = NOW(),
                            updated_at = NOW()
                        WHERE id = $1 AND tenant_id = $2
                    """, apt["appointment_id"], apt["tenant_id"])
                    
                    # Crear registro en chat_messages para tracking
                    await create_followup_message_record(
                        tenant_id=apt["tenant_id"],
                        patient_id=apt["patient_id"],
                        appointment_id=apt["appointment_id"],
                        phone_number=apt["phone_number"],
                        message=message
                    )
                    
                    logger.info(f"✅ Seguimiento enviado a {patient_name} ({apt['phone_number']})")
                    sent_count += 1
                else:
                    logger.error(f"❌ Error al enviar seguimiento a {patient_name}")
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"❌ Error procesando seguimiento para turno {apt.get('appointment_id')}: {e}")
                error_count += 1
        
        # Log de resumen
        logger.info(f"📊 RESUMEN JOB SEGUIMIENTO: {sent_count} enviados, {error_count} errores")
        
    except Exception as e:
        logger.error(f"❌ Error en job de seguimiento post-atención: {e}")
        raise


async def send_whatsapp_message(phone_number: str, message: str, tenant_id: int, 
                               whatsapp_creds: Dict[str, Any], appointment_id: int, 
                               is_followup: bool = False) -> bool:
    """
    Envía mensaje por WhatsApp marcando como seguimiento post-atención.
    
    Args:
        phone_number: Número de teléfono del paciente
        message: Mensaje a enviar
        tenant_id: ID del tenant para aislamiento
        whatsapp_creds: Credenciales de WhatsApp del tenant
        appointment_id: ID del turno para tracking
        is_followup: Si es True, marca el mensaje como seguimiento
        
    Returns:
        bool: True si se envió correctamente, False en caso de error
    """
    try:
        # El servicio de WhatsApp está en un contenedor separado
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
            "X-Correlation-Id": f"followup-{tenant_id}-{appointment_id}-{datetime.now().timestamp()}",
            "X-Message-Type": "followup" if is_followup else "regular"
        }
        
        # Payload para enviar mensaje
        payload = {
            "to": phone_number,
            "text": message,
            "tenant_id": tenant_id,
            "metadata": {
                "appointment_id": appointment_id,
                "message_type": "post_treatment_followup",
                "followup_date": date.today().isoformat()
            }
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
                logger.info(f"✅ Mensaje de seguimiento enviado a {phone_number}")
                return True
            else:
                logger.error(f"❌ Error al enviar mensaje de seguimiento: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error enviando WhatsApp de seguimiento: {e}")
        return False


async def create_followup_message_record(tenant_id: int, patient_id: int, 
                                        appointment_id: int, phone_number: str, 
                                        message: str):
    """
    Crea un registro en chat_messages para tracking del seguimiento.
    Esto permite al agente LLM identificar respuestas a seguimientos.
    
    Args:
        tenant_id: ID del tenant
        patient_id: ID del paciente
        appointment_id: ID del turno
        phone_number: Número de teléfono
        message: Mensaje enviado
    """
    try:
        from db import db
        
        # Crear registro en chat_messages
        await db.pool.execute("""
            INSERT INTO chat_messages (
                tenant_id, conversation_id, role, content,
                external_user_id, phone_number, content_attributes,
                created_at, updated_at
            ) VALUES (
                $1, 
                CONCAT('followup_', $2, '_', $3),
                'assistant',
                $4,
                $5,
                $6,
                $7::jsonb,
                NOW(),
                NOW()
            )
        """, 
            tenant_id,
            patient_id,
            appointment_id,
            message,
            f"patient_{patient_id}",
            phone_number,
            json.dumps({
                "message_type": "post_treatment_followup",
                "appointment_id": appointment_id,
                "is_followup": True,
                "requires_triage_evaluation": True,
                "followup_date": date.today().isoformat(),
                "system_note": "RESPUESTA A ESTE MENSAJE DEBE ACTIVAR EVALUACIÓN DE TRIAGE DE URGENCIA"
            })
        )
        
        logger.debug(f"📝 Registro de seguimiento creado para paciente {patient_id}, turno {appointment_id}")
        
    except Exception as e:
        logger.error(f"❌ Error creando registro de seguimiento: {e}")
        # No fallar el job principal por error en registro


async def test_followup_for_today():
    """
    Función de testing: envía seguimientos para turnos de hoy.
    Útil para pruebas sin tener que esperar a mañana.
    """
    logger.info("🧪 Ejecutando TEST de seguimiento post-atención para hoy...")
    
    try:
        from db import db
        
        # Usar fecha de hoy en lugar de ayer
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # Buscar un turno de prueba (el primero que encuentre)
        test_appointment = await db.pool.fetchrow("""
            SELECT 
                a.id as appointment_id,
                a.appointment_datetime,
                a.treatment_type,
                p.first_name,
                p.phone_number,
                t.id as tenant_id,
                t.whatsapp_credentials
            FROM appointments a
            INNER JOIN patients p ON a.patient_id = p.id
            INNER JOIN tenants t ON a.tenant_id = t.id
            WHERE a.status = 'completed'
                AND a.appointment_datetime >= $1
                AND a.appointment_datetime <= $2
                AND p.phone_number IS NOT NULL
                AND (a.treatment_type IS NOT NULL OR a.treatment_type != 'consultation')
            LIMIT 1
        """, today_start, today_end)
        
        if not test_appointment:
            logger.warning("⚠️ No hay turnos completados de hoy para probar seguimiento")
            return False
        
        # Enviar mensaje de prueba
        apt_date = test_appointment["appointment_datetime"].strftime("%d/%m")
        patient_name = test_appointment["first_name"]
        
        test_message = (
            f"🔧 [TEST] Hola {patient_name}, soy la asistente de la Dra. Delgado. "
            f"Te escribo para saber cómo te sentís hoy después de la atención de hoy ({apt_date}). "
            f"¿Tuviste alguna molestia o va todo bien? (Este es un mensaje de prueba del sistema)"
        )
        
        success = await send_whatsapp_message(
            phone_number=test_appointment["phone_number"],
            message=test_message,
            tenant_id=test_appointment["tenant_id"],
            whatsapp_creds=test_appointment["whatsapp_credentials"],
            appointment_id=test_appointment["appointment_id"],
            is_followup=True
        )
        
        if success:
            logger.info(f"✅ Test exitoso: seguimiento enviado a {patient_name}")
        else:
            logger.error(f"❌ Test fallido: no se pudo enviar seguimiento a {patient_name}")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ Error en test de seguimiento: {e}")
        return False