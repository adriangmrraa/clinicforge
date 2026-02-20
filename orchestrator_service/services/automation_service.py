import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
import json
from db import db
import pytz
from typing import List, Dict, Any

logger = logging.getLogger("automation")

# Importar YCloudClient (asumiendo que está en el path o en el mismo nivel/service)
try:
    from ycloud_client import YCloudClient
except ImportError:
    # Fallback si se ejecuta desde el orquestador y la estructura es distinta
    try:
        from routes.chat_api import YCloudClient
    except ImportError:
        # Si no, intentaremos importarlo dinámicamente o usar httpx directamente
        YCloudClient = None

class AutomationService:
    def __init__(self):
        self.is_running = False
        self._task = None

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._main_loop())
        logger.info("🚀 Motor de Automatización iniciado.")

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Motor de Automatización detenido.")

    async def _main_loop(self):
        """Bucle principal que corre cada 15 minutos."""
        while self.is_running:
            try:
                logger.info("🤖 Ejecutando ciclo de automatización...")
                await self.process_all_tenants()
            except Exception as e:
                logger.error(f"❌ Error en el bucle de automatización: {e}", exc_info=True)
            
            # Esperar 15 minutos (configurable)
            await asyncio.sleep(900)

    async def process_all_tenants(self):
        """Itera sobre cada tenant y procesa sus triggers."""
        tenants = await db.pool.fetch("SELECT id, timezone, config FROM tenants")
        for tenant in tenants:
            try:
                await self.process_tenant_triggers(tenant)
            except Exception as e:
                logger.error(f"❌ Error procesando tenant {tenant['id']}: {e}")

    async def process_tenant_triggers(self, tenant: Dict[str, Any]):
        tenant_id = tenant['id']
        tz_name = tenant.get('timezone') or 'America/Argentina/Buenos_Aires'
        tz = pytz.timezone(tz_name)
        now_local = datetime.now(tz)

        # 1. Recordatorios de Citas (24h antes)
        await self.trigger_reminders(tenant_id, now_local)

        # 2. Seguimiento/Feedback (45m después)
        await self.trigger_feedback(tenant_id, now_local)

        # 3. Recuperación de Leads (2h después de captura sin cita)
        await self.trigger_lead_recovery(tenant_id, now_local)

    async def trigger_reminders(self, tenant_id: int, now_local: datetime):
        """Busca citas para mañana que no hayan sido recordadas."""
        target_start = now_local + timedelta(days=1)
        target_end = target_start + timedelta(minutes=15) # Ventana del job

        appointments = await db.pool.fetch("""
            SELECT a.id, a.patient_id, a.appointment_datetime, p.phone_number, p.first_name, 
                   a.appointment_type as treatment_name, pr.first_name as prof_name
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN professionals pr ON a.professional_id = pr.id
            LEFT JOIN automation_logs l ON l.target_id = a.id::text AND l.trigger_type = 'appointment_reminder'
            WHERE a.tenant_id = $1 
              AND a.status = 'scheduled'
              AND a.appointment_datetime BETWEEN $2 AND $3
              AND l.id IS NULL
        """, tenant_id, target_start, target_end)

        for apt in appointments:
            await self.send_hsm(
                tenant_id=tenant_id,
                to=apt['phone_number'],
                template_name="recordatorio_cita_v1",
                language="es",
                components=[
                    {"type": "body", "parameters": [{"type": "text", "text": apt['first_name']}, {"type": "text", "text": apt['appointment_datetime'].strftime('%H:%M')}]}
                ],
                trigger_type="appointment_reminder",
                target_id=str(apt['id']),
                patient_id=apt['patient_id']
            )

    async def trigger_feedback(self, tenant_id: int, now_local: datetime):
        """Busca citas finalizadas hace 45-60 min sin feedback enviado."""
        target_time = now_local - timedelta(minutes=45)
        # Solo procesamos citas de HOY
        
        appointments = await db.pool.fetch("""
            SELECT a.id, a.patient_id, p.phone_number, p.first_name
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            WHERE a.tenant_id = $1 
              AND a.status = 'completed'
              AND a.feedback_sent = false
              AND a.appointment_datetime < $2
        """, tenant_id, target_time)

        for apt in appointments:
            success = await self.send_hsm(
                tenant_id=tenant_id,
                to=apt['phone_number'],
                template_name="feedback_cita_v1",
                language="es",
                components=[
                    {"type": "body", "parameters": [{"type": "text", "text": apt['first_name']}]}
                ],
                trigger_type="appointment_feedback",
                target_id=str(apt['id']),
                patient_id=apt['patient_id']
            )
            if success:
                await db.pool.execute("UPDATE appointments SET feedback_sent = true WHERE id = $1", apt['id'])

    async def trigger_lead_recovery(self, tenant_id: int, now_local: datetime):
        """Recupera leads de Meta Ads capturados hace 2h sin cita agendada."""
        two_hours_ago = now_local - timedelta(hours=2)
        three_hours_ago = two_hours_ago - timedelta(minutes=15)

        leads = await db.pool.fetch("""
            SELECT p.id, p.phone_number, p.first_name
            FROM patients p
            LEFT JOIN appointments a ON a.patient_id = p.id
            LEFT JOIN automation_logs l ON l.patient_id = p.id AND l.trigger_type = 'lead_recovery'
            WHERE p.tenant_id = $1
              AND p.acquisition_source = 'META_ADS'
              AND p.created_at BETWEEN $2 AND $3
              AND a.id IS NULL
              AND l.id IS NULL
        """, tenant_id, three_hours_ago, two_hours_ago)

        for lead in leads:
            await self.send_hsm(
                tenant_id=tenant_id,
                to=lead['phone_number'],
                template_name="lead_recovery_v1",
                language="es",
                components=[
                    {"type": "body", "parameters": [{"type": "text", "text": lead['first_name']}]}
                ],
                trigger_type="lead_recovery",
                target_id=str(lead['id']),
                patient_id=lead['id']
            )

    async def send_hsm(self, tenant_id: int, to: str, template_name: str, language: str, components: list, trigger_type: str, target_id: str, patient_id: int) -> bool:
        """Helper para enviar HSM vía YCloud y registrar log."""
        from core.credentials import YCLOUD_API_KEY, get_tenant_credential
        
        api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
        from_number = await get_tenant_credential(tenant_id, "YCLOUD_WHATSAPP_NUMBER")
        
        if not api_key:
            logger.error(f"❌ No hay API Key de YCloud para tenant {tenant_id}")
            return False

        try:
            # Instanciar cliente dinámicamente si es necesario
            from ycloud_client import YCloudClient
            client = YCloudClient(api_key)
            if from_number:
                client.business_number = from_number

            response = await client.send_template(
                to=to,
                template_name=template_name,
                language_code=language,
                components=components,
                correlation_id=f"auto_{trigger_type}_{target_id}"
            )

            # Registrar log exitoso
            await db.pool.execute("""
                INSERT INTO automation_logs (tenant_id, patient_id, trigger_type, target_id, status, meta)
                VALUES ($1, $2, $3, $4, 'sent', $5)
            """, tenant_id, patient_id, trigger_type, target_id, json.dumps(response))
            
            logger.info(f"✅ HSM {trigger_type} enviado a {to} (Tenant {tenant_id})")
            return True

        except Exception as e:
            logger.error(f"❌ Error enviando HSM {trigger_type} a {to}: {e}")
            # Registrar log con error
            await db.pool.execute("""
                INSERT INTO automation_logs (tenant_id, patient_id, trigger_type, target_id, status, error_details)
                VALUES ($1, $2, $3, $4, 'failed', $5)
            """, tenant_id, patient_id, trigger_type, target_id, str(e))
            return False

# Instancia singleton
automation_service = AutomationService()
