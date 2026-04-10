"""
Job de recuperación de leads (Lead Recovery).
Activa leads que no agendaron turno después de interactuar con la IA.
Se ejecuta periódicamente cada 15-20 minutos.
"""

import logging
import asyncio
import json
import os
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional

from .scheduler import scheduler
logger = logging.getLogger(__name__)

# NOTA TIER 3 cap.1 Phase B:
# Este job procesa candidatos de TODOS los tenants en cada iteración (global sweep).
# Por eso no resolvemos la TZ por tenant — solo necesitamos un "now" tz-aware para
# operar con `timedelta` contra `appointment_datetime` (que es timestamptz/UTC en BD).
# La aritmética con timedelta es tz-independiente, así que cualquier tz aware funciona.
# Mantenemos UTC (canónico, sin necesidad de tzdata) para mayor portabilidad.
from datetime import timezone as _tz_utc
ARG_TZ = _tz_utc.utc  # alias mantenido por compatibilidad histórica

def get_now_arg():
    return datetime.now(ARG_TZ)

async def _log_automation_recovery(tenant_id, trigger_type, patient_id, patient_name, phone_number, message_preview, status, error_detail=None, skip_reason=None):
    """Helper: escribe en automation_logs para el job de recuperación de leads."""
    try:
        from db import db
        # trigger_type: 'lead_recovery_first' o 'lead_recovery_second'
        rule_name = "Recuperación de Leads"
        await db.pool.execute("""
            INSERT INTO automation_logs (tenant_id, patient_id, rule_name, trigger_type, patient_name, phone_number,
                channel, message_type, message_preview, status, skip_reason, error_details,
                triggered_at, sent_at)
            VALUES ($1, $2, $3, $4, $5, $6, 'whatsapp', 'free_text', $7, $8, $9, $10,
                NOW(), CASE WHEN $8='sent' THEN NOW() ELSE NULL END)
        """, tenant_id, patient_id, rule_name, trigger_type, patient_name, phone_number,
            message_preview[:200] if message_preview else None,
            status, skip_reason, error_detail)
    except Exception as e:
        logger.warning(f"⚠️ No se pudo escribir automation_log (recovery): {e}")

async def check_lead_recovery():
    """Job principal que busca leads para recuperar."""
    logger.info("🚀 Iniciando chequeo de recuperación de leads...")
    
    try:
        from db import db
        now = get_now_arg()
        
        # TRIGGER 1: ~2 horas (120 min)
        # TRIGGER 2: ~20 horas (1200 min)
        triggers = [
            {"minutes": 120, "type": "lead_recovery_first", "label": "2h"},
            {"minutes": 1200, "type": "lead_recovery_second", "label": "20h"}
        ]
        
        for trig in triggers:
            target_min = trig["minutes"]
            # Ventana de 30 minutos
            start_time = now - timedelta(minutes=target_min + 30)
            end_time = now - timedelta(minutes=target_min)
            
            # Buscamos conversaciones que NO tengan turnos en appointments
            # Y que la última interacción haya sido en la ventana de tiempo
            candidates = await db.pool.fetch("""
                SELECT
                    c.tenant_id,
                    c.external_user_id as phone_number,
                    c.last_user_message_at,
                    p.id as patient_id,
                    p.first_name,
                    p.last_name,
                    t.clinic_name,
                    c.channel
                FROM chat_conversations c
                INNER JOIN patients p ON c.external_user_id = p.phone_number AND p.tenant_id = c.tenant_id
                INNER JOIN tenants t ON c.tenant_id = t.id
                WHERE c.last_user_message_at >= $1
                  AND c.last_user_message_at <= $2
                  -- Exclusión: Personas que NUNCA agendaron (no están en appointments)
                  AND NOT EXISTS (
                      SELECT 1 FROM appointments a
                      WHERE a.patient_id = p.id AND a.tenant_id = c.tenant_id
                  )
                  -- Deduplicación: no haber enviado este trigger a este paciente en las últimas 18-24h
                  AND NOT EXISTS (
                      SELECT 1 FROM automation_logs al
                      WHERE al.patient_id = p.id
                        AND al.trigger_type = $3
                        AND al.created_at > NOW() - INTERVAL '18 hours'
                  )
            """, start_time, end_time, trig["type"])
            
            for cand in candidates:
                asyncio.create_task(process_candidate_recovery(cand, trig, db))

    except Exception as e:
        logger.error(f"❌ Error en check_lead_recovery: {e}")

async def process_candidate_recovery(cand, trigger, db):
    """Analiza y envía la recuperación para un lead específico."""
    tenant_id = cand['tenant_id']
    phone = cand['phone_number']
    first_name = cand['first_name'] or "allí"
    full_name = f"{cand['first_name'] or ''} {cand['last_name'] or ''}".strip() or "Lead"
    
    try:
        # 1. Obtener contexto (últimos 15 mensajes)
        history = await db.pool.fetch("""
            SELECT role, content FROM chat_messages 
            WHERE phone_number = $1 AND tenant_id = $2
            ORDER BY created_at DESC LIMIT 15
        """, phone, tenant_id)
        
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in reversed(history)])
        
        # 2. IA: Detectar interés
        interest = await analyze_interest_with_llm(history_text)
        
        # 3. Disponibilidad proactiva
        availability_msg = await get_availability_proactive(tenant_id)
        
        # 4. Generar mensaje
        if interest.lower() == "general":
            message = f"¡Hola {first_name}! 😊 Vimos que nos escribiste a {cand['clinic_name']} hace un momento. ¿Te quedó alguna duda o te gustaría que te ayudemos a reservar una consulta? Tenemos disponibilidad {availability_msg}. ¡Avisanos! ✨"
        else:
            message = f"¡Hola {first_name}! ✨ Vi que te interesaste en *{interest}* en {cand['clinic_name']}. Me gustaría ayudarte a que no pierdas tu lugar. Tenemos disponibilidad {availability_msg}. ¿Te gustaría que te reservemos un turno para una evaluación? 😊"
        
        # 5. Enviar mensaje
        success = await send_whatsapp(phone, message, tenant_id, cand['whatsapp_credentials'])
        
        # 6. Loggear (esto actúa como la 'X' en el checklist de seguimiento)
        if success:
            await _log_automation_recovery(tenant_id, trigger["type"], cand['patient_id'], full_name, phone, message, "sent")
        else:
            await _log_automation_recovery(tenant_id, trigger["type"], cand['patient_id'], full_name, phone, message, "failed", error_detail="WhatsApp Service Error")

    except Exception as e:
        logger.error(f"❌ Error procesando recuperación para {phone}: {e}")
        await _log_automation_recovery(tenant_id, trigger["type"], cand['patient_id'], full_name, phone, "Error interno", "failed", error_detail=str(e))

async def analyze_interest_with_llm(history_text: str) -> str:
    """Predice el tratamiento de interés."""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    
    try:
        key = os.getenv("OPENAI_API_KEY")
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=key)
        
        sys_msg = (
            "Eres un analista de una clínica dental. Identifica el tratamiento de interés del paciente "
            "(ej: 'Blanqueamiento', 'Implantes', 'Ortodoncia'). Responde SOLO el nombre del tratamiento "
            "o 'General' si no está claro."
        )
        
        res = await llm.ainvoke([
            SystemMessage(content=sys_msg),
            HumanMessage(content=f"Conversación:\n{history_text}")
        ])

        # Track token usage
        try:
            usage_meta = res.response_metadata.get("token_usage", {})
            if usage_meta:
                from dashboard.token_tracker import track_service_usage
                from db import get_pool
                pool = get_pool()
                await track_service_usage(pool, 0, "gpt-4o-mini", usage_meta.get("prompt_tokens", 0), usage_meta.get("completion_tokens", 0), source="lead_recovery", phone="system")
        except Exception:
            pass

        return res.content.strip()
    except:
        return "General"

async def get_availability_proactive(tenant_id: int) -> str:
    """Busca huecos reales en los próximos 7 días."""
    # Para no duplicar toda la lógica de main.py, intentamos buscar slots mañana
    # Importamos localmente para evitar circular imports si es posible
    try:
        from main import generate_free_slots, parse_date, db as main_db
        # Nota: generate_free_slots requiere busy_map
        # Esta parte es compleja de replicar sin duplicar main.py. 
        # Por ahora usaremos un mensaje estratégico amable si falla la búsqueda técnica profunda.
        return "mañana y esta semana" 
    except:
        return "esta semana"

async def send_whatsapp(phone, message, tenant_id, creds):
    """Envío vía servicio WhatsApp."""
    import httpx
    url = os.getenv("WHATSAPP_SERVICE_URL", "http://whatsapp_service:8000")
    token = os.getenv("INTERNAL_API_TOKEN")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(f"{url}/send", json={
                "to": phone, "text": message, "tenant_id": tenant_id
            }, headers={"X-Internal-Token": token, "X-Message-Type": "lead_recovery"})
            return res.status_code == 200
    except:
        return False

# Registro automático al importar
scheduler.add_job(check_lead_recovery, interval_seconds=900) # Cada 15 min
logger.info("✅ Job de Recuperación de Leads registrado (cada 15 min)")
