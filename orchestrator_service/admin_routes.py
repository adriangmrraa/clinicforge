import os
import uuid
import json
import asyncpg
import httpx
import logging
import re
from datetime import datetime, timedelta, date, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Header, Depends, Request, status, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from db import db
from gcal_service import gcal_service
from analytics_service import analytics_service

logger = logging.getLogger(__name__)

# Configuración
from core.credentials import get_tenant_credential, CREDENTIALS_FERNET_KEY, encrypt_value, decrypt_value
from core.auth import verify_admin_token, get_resolved_tenant_id, ADMIN_TOKEN

INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "internal-secret-token")
WHATSAPP_SERVICE_URL = os.getenv("WHATSAPP_SERVICE_URL", "http://whatsapp:8002")

# Usar encrypt_value y decrypt_value importados de core.credentials

ARG_TZ = timezone(timedelta(hours=-3))

from services.whisper_service import transcribe_audio_url
import glob

router = APIRouter(prefix="/admin", tags=["Dental Admin"])

# ============================================
# DEBUG ENDPOINTS - Para diagnóstico en producción
# ============================================

@router.get("/debug/auth-test")
async def debug_auth_test(request: Request, x_admin_token: str = Header(None)):
    """
    Endpoint de debug para verificar problemas de autenticación 401.
    Público - no requiere auth.
    """
    headers = dict(request.headers)
    
    # Obtener X-Admin-Token de headers (case-insensitive)
    received_admin_token = None
    for key, value in headers.items():
        if key.lower() == 'x-admin-token':
            received_admin_token = value
            break
    
    debug_info = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "received_admin_token_present": received_admin_token is not None,
        "received_admin_token_preview": received_admin_token[:10] + "..." if received_admin_token else None,
        "expected_admin_token_defined": bool(ADMIN_TOKEN),
        "expected_admin_token_length": len(ADMIN_TOKEN) if ADMIN_TOKEN else 0,
        "tokens_match": received_admin_token == ADMIN_TOKEN if received_admin_token and ADMIN_TOKEN else False,
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": headers.get('User-Agent', 'unknown')[:100],
        "cors_origin": headers.get('Origin', 'none'),
        "authorization_header_present": 'Authorization' in headers,
        "cookie_header_present": 'Cookie' in headers,
    }
    
    logger.info(f"DEBUG_AUTH_TEST: {debug_info}")
    
    return debug_info


@router.get("/debug/health")
async def debug_health():
    """
    Health check público.
    """
    return {
        "status": "healthy",
        "service": "orchestrator",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": os.getenv("API_VERSION", "1.0.0"),
    }


@router.get("/debug/env-safe")
async def debug_env_safe():
    """
    Variables de entorno seguras (sin exponer valores sensibles).
    """
    return {
        "ADMIN_TOKEN_defined": bool(ADMIN_TOKEN),
        "ADMIN_TOKEN_length": len(ADMIN_TOKEN) if ADMIN_TOKEN else 0,
        "CORS_ALLOWED_ORIGINS": os.getenv("CORS_ALLOWED_ORIGINS", "not_set"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
        "backend_version": os.getenv("API_VERSION", "1.0.0"),
        "environment": os.getenv("NODE_ENV", "production"),
    }

def normalize_phone(phone: str) -> str:
    """Asegura que el número tenga el formato +123456789 (E.164)"""
    clean = re.sub(r'\D', '', phone)
    if not phone.startswith('+'):
        return '+' + clean
    return '+' + clean

# --- Helper para emitir eventos de Socket.IO ---
async def emit_appointment_event(event_type: str, data: Dict[str, Any], request: Request):
    """Emit appointment events via Socket.IO through the app state."""
    if hasattr(request.app.state, 'emit_appointment_event'):
        await request.app.state.emit_appointment_event(event_type, data)

# --- Background Task para envío a WhatsApp ---
async def send_to_whatsapp_task(phone: str, message: str, business_number: str):
    """Tarea en segundo plano para no bloquear la UI mientras se envía el mensaje."""
    normalized = normalize_phone(phone)
    logger.info(f"📤 Intentando envío manual a WhatsApp: {normalized} via {WHATSAPP_SERVICE_URL}")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            ws_resp = await client.post(
                f"{WHATSAPP_SERVICE_URL}/send",
                json={
                    "to": normalized,
                    "message": message
                },
                headers={
                    "X-Internal-Token": INTERNAL_API_TOKEN,
                    "X-Correlation-Id": str(uuid.uuid4())
                },
                params={"from_number": business_number}
            )
            if ws_resp.status_code != 200:
                logger.error(f"❌ Error en WhatsApp Service ({ws_resp.status_code}): {ws_resp.text}")
            else:
                logger.info(f"✅ WhatsApp background send success for {normalized}")
    except Exception as e:
        logger.error(f"❌ WhatsApp background send CRITICAL failed for {normalized}: {str(e)}")

# --- Dependencias de Seguridad (Triple Capa Nexus v7.6) ---
from core.auth import verify_admin_token, verify_ceo_token, get_resolved_tenant_id


async def get_allowed_tenant_ids(user_data=Depends(verify_admin_token)) -> List[int]:
    """
    Lista de tenant_id que el usuario puede ver (chats, sesiones).
    CEO: todos los tenants. Secretary/Professional: solo su clínica resuelta.
    """
    try:
        if user_data.role == "ceo":
            rows = await db.pool.fetch("SELECT id FROM tenants ORDER BY id ASC")
            return [int(r["id"]) for r in rows] if rows else [1]
        try:
            tid = await db.pool.fetchval(
                "SELECT tenant_id FROM professionals WHERE user_id = $1",
                uuid.UUID(user_data.user_id),
            )
            if tid is not None:
                return [int(tid)]
        except (ValueError, TypeError):
            pass
        first = await db.pool.fetchval("SELECT id FROM tenants ORDER BY id ASC LIMIT 1")
        return [int(first)] if first is not None else [1]
    except Exception:
        return [1]  # Fallback para no devolver 500


@router.get("/patients/phone/{phone}/context", tags=["Pacientes"])
async def get_patient_clinical_context(
    phone: str,
    request: Request,
    tenant_id_override: Optional[int] = None,
    user_data=Depends(verify_admin_token),
    resolved_tenant_id: int = Depends(get_resolved_tenant_id),
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
):
    """
    Retorna el contexto clínico completo de un paciente por su teléfono.
    Si se pasa tenant_id_override (ej. CEO eligió una clínica en Chats), se usa si el usuario tiene acceso.
    """
    tenant_id = tenant_id_override if (tenant_id_override is not None and tenant_id_override in allowed_ids) else resolved_tenant_id
    
    # 1. Resolver paciente (por Teléfono o por ID de Plataforma)
    # Si el "phone" no empieza con + o no son solo números, lo tratamos como plataforma_id
    is_pure_platform_id = not (phone.startswith('+') or phone.isdigit())
    
    patient = None
    if not is_pure_platform_id:
        normalized_phone = normalize_phone(phone)
        patient = await db.pool.fetchrow("""
            SELECT id, first_name, last_name, phone_number, status, urgency_level, urgency_reason, preferred_schedule,
                   acquisition_source, meta_ad_id, meta_ad_headline, meta_ad_body, external_ids
            FROM patients 
            WHERE tenant_id = $1 AND (phone_number = $2 OR phone_number = $3)
            AND status != 'deleted'
        """, tenant_id, normalized_phone, phone)
    
    if not patient:
        # Buscar por external_ids (IG/FB)
        # Probamos el ID contra todas las claves del JSONB
        patient = await db.pool.fetchrow("""
            SELECT id, first_name, last_name, phone_number, status, urgency_level, urgency_reason, preferred_schedule,
                   acquisition_source, meta_ad_id, meta_ad_headline, meta_ad_body, external_ids
            FROM patients 
            WHERE tenant_id = $1 
            AND (
                external_ids->>'instagram' = $2 OR 
                external_ids->>'facebook' = $2 OR 
                external_ids->>'chatwoot' = $2
            )
            AND status != 'deleted'
        """, tenant_id, phone)

    if patient:
        from core.auth import log_pii_access
        await log_pii_access(request, user_data, patient['id'], action="read_clinical_context")
        return patient
    
    # Si no existe, es un lead puro sin registro previo
    return {
        "patient": None,
        "last_appointment": None,
        "upcoming_appointment": None,
        "treatment_plan": None,
        "is_guest": True
    }

    # 2. Última cita (pasada) - Mapeo a 'date' para el frontend
    last_apt = await db.pool.fetchrow("""
        SELECT a.id, a.appointment_datetime AS date, a.appointment_type AS type, a.status, 
               a.duration_minutes, p.first_name as professional_name
        FROM appointments a
        LEFT JOIN professionals p ON a.professional_id = p.id
        WHERE a.tenant_id = $1 AND a.patient_id = $2 AND a.appointment_datetime < NOW()
        ORDER BY a.appointment_datetime DESC LIMIT 1
    """, tenant_id, patient['id'])

    # 3. Próxima cita (futura) - Mapeo a 'date' para el frontend
    upcoming_apt = await db.pool.fetchrow("""
        SELECT a.id, a.appointment_datetime AS date, a.appointment_type AS type, a.status,
               a.duration_minutes, p.first_name as professional_name
        FROM appointments a
        LEFT JOIN professionals p ON a.professional_id = p.id
        WHERE a.tenant_id = $1 AND a.patient_id = $2 AND a.appointment_datetime >= NOW()
        AND a.status IN ('scheduled', 'confirmed')
        ORDER BY a.appointment_datetime ASC LIMIT 1
    """, tenant_id, patient['id'])

    # 4. Plan de tratamiento (del último registro clínico)
    clinical_record = await db.pool.fetchrow("""
        SELECT treatment_plan, diagnosis, record_date
        FROM clinical_records
        WHERE tenant_id = $1 AND patient_id = $2
        ORDER BY created_at DESC LIMIT 1
    """, tenant_id, patient['id'])

    return {
        "patient": dict(patient),
        "last_appointment": dict(last_apt) if last_apt else None,
        "upcoming_appointment": dict(upcoming_apt) if upcoming_apt else None,
        "treatment_plan": clinical_record['treatment_plan'] if clinical_record else None,
        "diagnosis": clinical_record['diagnosis'] if clinical_record else None,
        "is_guest": patient['status'] == 'guest'
    }

class StatusUpdate(BaseModel):
    status: str # active, suspended, pending

# --- RUTAS DE ADMINISTRACIÓN DE USUARIOS ---

@router.get("/users/pending", tags=["Usuarios"], summary="Listar usuarios pendientes de aprobación")
async def get_pending_users(user_data = Depends(verify_admin_token)):
    """ Retorna la lista de usuarios con estado 'pending' (Solo CEO/Secretary) """
    if user_data.role not in ['ceo', 'secretary']:
        raise HTTPException(status_code=403, detail="Solo el personal administrador puede ver usuarios pendientes.")
        
    users = await db.fetch("""
        SELECT id, email, role, status, created_at, first_name, last_name
        FROM users 
        WHERE status = 'pending'
        ORDER BY created_at DESC
    """)
    return [dict(u) for u in users]

@router.get("/users", tags=["Usuarios"], summary="Listar todos los usuarios del sistema")
async def get_all_users(user_data = Depends(verify_admin_token)):
    """ Retorna la lista de todos los usuarios de la clínica (Solo CEO/Secretary) """
    if user_data.role not in ['ceo', 'secretary']:
        raise HTTPException(status_code=403, detail="Solo el personal administrador puede listar usuarios.")
        
    users = await db.fetch("""
        SELECT id, email, role, status, created_at, updated_at, first_name, last_name
        FROM users 
        ORDER BY status ASC, created_at DESC
    """)
    return [dict(u) for u in users]

@router.post("/users/{user_id}/status", tags=["Usuarios"], summary="Aprobar o suspender un usuario")
async def update_user_status(user_id: str, payload: StatusUpdate, user_data = Depends(verify_ceo_token)):
    """ Actualiza el estado de un usuario (Aprobación/Suspensión) - Solo CEO.
    Al aprobar (active): si es professional/secretary y no tiene fila en professionals, se crea una para la primera sede. """

    target_user = await db.fetchrow(
        "SELECT id, email, role, COALESCE(first_name, '') as first_name, COALESCE(last_name, '') as last_name FROM users WHERE id = $1",
        user_id
    )
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    await db.execute("UPDATE users SET status = $1, updated_at = NOW() WHERE id = $2", payload.status, user_id)

    uid = uuid.UUID(user_id)
    if target_user['role'] in ('professional', 'secretary'):
        is_active = (payload.status == 'active')
        # Sincronizar is_active en professionals si ya tiene fila(s)
        await db.execute("UPDATE professionals SET is_active = $1 WHERE user_id = $2", is_active, uid)
        # Al aprobar: si no tiene ninguna fila en professionals, crear una para la primera sede (puede usar la plataforma)
        if payload.status == 'active':
            has_row = await db.pool.fetchval("SELECT 1 FROM professionals WHERE user_id = $1", uid)
            if not has_row:
                first_tenant = await db.pool.fetchval("SELECT id FROM tenants ORDER BY id ASC LIMIT 1")
                tenant_id = int(first_tenant) if first_tenant is not None else 1
                first_name = (target_user["first_name"] or "").strip() or "Profesional"
                last_name = (target_user["last_name"] or "").strip() or " "
                email = (target_user["email"] or "").strip()
                wh_json = json.dumps(generate_default_working_hours())
                try:
                    await db.pool.execute("""
                        INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email, phone_number,
                        specialty, registration_id, is_active, working_hours, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, NULL, NULL, NULL, TRUE, $6::jsonb, NOW(), NOW())
                    """, tenant_id, uid, first_name, last_name, email, wh_json)
                except asyncpg.UndefinedColumnError as e:
                    err_str = str(e).lower()
                    if "phone_number" in err_str:
                        await db.pool.execute("""
                            INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email,
                            specialty, registration_id, is_active, working_hours, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5, NULL, NULL, TRUE, $6::jsonb, NOW(), NOW())
                        """, tenant_id, uid, first_name, last_name, email, wh_json)
                    elif "updated_at" in err_str:
                        await db.pool.execute("""
                            INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email, phone_number,
                            specialty, registration_id, is_active, working_hours, created_at)
                            VALUES ($1, $2, $3, $4, $5, NULL, NULL, NULL, TRUE, $6::jsonb, NOW())
                        """, tenant_id, uid, first_name, last_name, email, wh_json)
                    else:
                        raise

    return {"message": f"Usuario {target_user['email']} actualizado a {payload.status}."}

class PatientCreate(BaseModel):
    first_name: str
    last_name: Optional[str] = ""
    phone_number: str
    email: Optional[str] = None
    dni: Optional[str] = None
    insurance: Optional[str] = None # Obra Social

class AppointmentCreate(BaseModel):
    patient_id: Optional[int] = None
    patient_phone: Optional[str] = None # Si es paciente nuevo rápido
    professional_id: int
    appointment_datetime: datetime
    appointment_type: str = "checkup"
    notes: Optional[str] = None
    check_collisions: bool = True # Por defecto verificar colisiones

class GCalendarBlockCreate(BaseModel):
    google_event_id: str
    title: str
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: datetime
    all_day: bool = False
    professional_id: Optional[int] = None

class ClinicalNote(BaseModel):
    content: str
    odontogram_data: Optional[Dict] = None

class ProfessionalCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    specialty: Optional[str] = None
    license_number: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True
    availability: Dict[str, Any] = {}
    working_hours: Optional[Dict[str, Any]] = None
    tenant_id: Optional[int] = None  # Clínica a la que se vincula; si viene y está permitido, se usa; si no, contexto

class ProfessionalUpdate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    specialty: Optional[str] = None
    license_number: Optional[str] = None
    is_active: bool
    availability: Dict[str, Any]
    working_hours: Optional[Dict[str, Any]] = None
    google_calendar_id: Optional[str] = None

def generate_default_working_hours():
    """Genera el JSON de horarios por defecto (Mon-Sat, 09:00-18:00)"""
    start = os.getenv("CLINIC_START_TIME", "09:00")
    end = os.getenv("CLINIC_END_TIME", "18:00")
    slot = {"start": start, "end": end}
    wh = {}
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        is_working_day = day != "sunday"
        wh[day] = {
            "enabled": is_working_day,
            "slots": [slot] if is_working_day else []
        }
    return wh

class TreatmentTypeCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = ""
    default_duration_minutes: int = 30
    min_duration_minutes: int = 15
    max_duration_minutes: int = 60
    complexity_level: str = "medium"
    category: str = "restorative"
    requires_multiple_sessions: bool = False
    session_gap_days: int = 0
    is_active: bool = True
    is_available_for_booking: bool = True
    internal_notes: Optional[str] = ""

class TreatmentTypeUpdate(BaseModel):
    name: str
    description: Optional[str] = ""
    default_duration_minutes: int
    min_duration_minutes: int
    max_duration_minutes: int
    complexity_level: str
    category: str
    requires_multiple_sessions: bool
    session_gap_days: int
    is_active: bool
    is_available_for_booking: bool
    internal_notes: Optional[str] = ""


class ChatSendMessage(BaseModel):
    phone: str
    tenant_id: int
    message: str

class HumanInterventionToggle(BaseModel):
    phone: str
    tenant_id: int  # Clínica: override/silencio es por (tenant_id, phone), independiente por clínica
    activate: bool
    duration: Optional[int] = 86400000  # 24 horas en ms


class ConnectSovereignPayload(BaseModel):
    """Token de Auth0 para conectar Google Calendar de forma soberana por clínica."""
    access_token: str  # Token de Auth0 (se guarda cifrado en credentials)
    tenant_id: Optional[int] = None  # Solo CEO puede especificar; si no, se usa la clínica resuelta

class CredentialPayload(BaseModel):
    id: Optional[int] = None
    name: str
    value: str
    category: str
    description: Optional[str] = ""
    scope: str = "global"  # global | tenant
    tenant_id: Optional[int] = None

# ==================== INTEGRATIONS WIZARD ENDPOINTS (Spec 16) ====================

class IntegrationConfig(BaseModel):
    provider: str # ycloud | chatwoot
    # Chatwoot fields
    chatwoot_base_url: Optional[str] = None
    chatwoot_api_token: Optional[str] = None
    chatwoot_account_id: Optional[str] = None # String to handle potential non-numeric IDs in future or masks
    # YCloud fields
    ycloud_api_key: Optional[str] = None
    ycloud_webhook_secret: Optional[str] = None
    
    tenant_id: Optional[int] = None # Optional override for multi-tenant setup

@router.get("/integrations/{provider}/config", tags=["Integraciones"])
async def get_integration_config(
    provider: str, 
    request: Request,
    tenant_id: Optional[int] = None, 
    user_data = Depends(verify_admin_token), 
    resolved_tenant_id: int = Depends(get_resolved_tenant_id)
):
    """
    Obtiene la configuración enmascarada para un proveedor específico.
    Provider: 'chatwoot' | 'ycloud'
    Query param 'tenant_id' permite a CEO ver config de otra sede.
    """
    if user_data.role != 'ceo':
        raise HTTPException(status_code=403, detail="Acceso denegado.")
        
    # Use query param if provided (CEO override), otherwise current context
    target_tenant_id = tenant_id if tenant_id else resolved_tenant_id
    
    config = {}
    
    if provider == "chatwoot":
        # Retrieve Chatwoot credentials
        rows = await db.fetch("""
            SELECT name, value FROM credentials 
            WHERE tenant_id = $1 AND name IN ('CHATWOOT_BASE_URL', 'CHATWOOT_API_TOKEN', 'CHATWOOT_ACCOUNT_ID')
        """, target_tenant_id)
        
        data = {r['name']: r['value'] for r in rows}
        
        # Base URL (Visible)
        config['chatwoot_base_url'] = data.get('CHATWOOT_BASE_URL', 'https://app.chatwoot.com')
        
        # API Token (Masked)
        token = data.get('CHATWOOT_API_TOKEN')
        if token:
             decrypted = decrypt_value(token) or token
             config['chatwoot_api_token'] = f"••••••••{decrypted[-4:]}" if len(decrypted) > 4 else "••••••••"
        
        # Account ID (Visible)
        config['chatwoot_account_id'] = data.get('CHATWOOT_ACCOUNT_ID', '')

        # --- Generate Webhook URL (Moved from chat_api.py) ---
        # 1. Get/Create Webhook Token
        webhook_token = await db.pool.fetchval(
            "SELECT value FROM credentials WHERE tenant_id = $1 AND name = 'WEBHOOK_ACCESS_TOKEN'",
            target_tenant_id
        )
        if not webhook_token:
            webhook_token = uuid.uuid4().hex + uuid.uuid4().hex
            await db.pool.execute("""
                INSERT INTO credentials (tenant_id, name, value, category, description, scope, created_at, updated_at)
                VALUES ($1, 'WEBHOOK_ACCESS_TOKEN', $2, 'system', 'Token para webhook de Chatwoot', 'tenant', NOW(), NOW())
                ON CONFLICT (tenant_id, name) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """, target_tenant_id, webhook_token)
        
        config['access_token'] = webhook_token
        
        # 2. Construct URL
        api_base = os.getenv("BASE_URL", "").rstrip("/")
        if not api_base:
             # Fallback using request
             scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
             host = request.headers.get("x-forwarded-host", request.url.netloc)
             api_base = f"{scheme}://{host}"
             
        config['api_base'] = api_base
        config['webhook_path'] = "/admin/chatwoot/webhook"
        config['full_webhook_url'] = f"{api_base}/admin/chatwoot/webhook?access_token={webhook_token}"

    elif provider == "ycloud":
        rows = await db.fetch("""
            SELECT name, value FROM credentials 
            WHERE tenant_id = $1 AND name IN ('YCLOUD_API_KEY', 'YCLOUD_WEBHOOK_SECRET')
        """, tenant_id)
        data = {r['name']: r['value'] for r in rows}
        
        # API Key (Masked)
        key = data.get('YCLOUD_API_KEY')
        if key:
            decrypted = decrypt_value(key) or key
            config['ycloud_api_key'] = f"••••••••{decrypted[-4:]}" if len(decrypted) > 4 else "••••••••"
            
        # Webhook Secret (Masked)
        secret = data.get('YCLOUD_WEBHOOK_SECRET')
        if secret:
            decrypted = decrypt_value(secret) or secret
            config['ycloud_webhook_secret'] = f"••••••••{decrypted[-4:]}" if len(decrypted) > 4 else "••••••••"
            
    else:
        raise HTTPException(status_code=400, detail=f"Proveedor no soportado: {provider}")
        
    return config

@router.post("/integrations/{provider}/config", tags=["Integraciones"])
async def save_integration_config(provider: str, payload: IntegrationConfig, user_data = Depends(verify_admin_token), resolved_tenant_id: int = Depends(get_resolved_tenant_id)):
    """
    Guarda la configuración de integración para YCloud o Chatwoot.
    Maneja encriptación y upsert de múltiples credenciales.
    """
    if user_data.role != 'ceo':
        raise HTTPException(status_code=403, detail="Acceso denegado.")
    
    target_tenant_id = payload.tenant_id if payload.tenant_id else resolved_tenant_id
    
    creds_to_save = []
    
    if provider == "chatwoot":
        if payload.chatwoot_base_url:
            creds_to_save.append(("CHATWOOT_BASE_URL", payload.chatwoot_base_url, "Chatwoot URL", False))
        
        if payload.chatwoot_api_token and not payload.chatwoot_api_token.startswith("••••"):
            creds_to_save.append(("CHATWOOT_API_TOKEN", payload.chatwoot_api_token, "Chatwoot API Token", True))
            
        if payload.chatwoot_account_id:
            creds_to_save.append(("CHATWOOT_ACCOUNT_ID", payload.chatwoot_account_id, "Chatwoot Account ID", False))
            
    elif provider == "ycloud":
        if payload.ycloud_api_key and not payload.ycloud_api_key.startswith("••••"):
             creds_to_save.append(("YCLOUD_API_KEY", payload.ycloud_api_key, "YCloud API Key", True))
             
        if payload.ycloud_webhook_secret and not payload.ycloud_webhook_secret.startswith("••••"):
             creds_to_save.append(("YCLOUD_WEBHOOK_SECRET", payload.ycloud_webhook_secret, "YCloud Webhook Secret", True))
             
    else:
        raise HTTPException(status_code=400, detail="Proveedor no reconocido")

    # Execute Upserts
    for key, value, desc, encrypt in creds_to_save:
        final_val = value.strip()
        if encrypt:
            encrypted = encrypt_value(final_val)
            if not encrypted:
                 raise HTTPException(status_code=500, detail="Error de encriptación")
            final_val = encrypted
            
        # Check integrity: if exists update, else insert
        existing = await db.fetchval("SELECT id FROM credentials WHERE tenant_id = $1 AND name = $2", target_tenant_id, key)
        
        if existing:
            await db.execute("""
                UPDATE credentials SET value = $1, updated_at = NOW()
                WHERE id = $2
            """, final_val, existing)
        else:
            await db.execute("""
                INSERT INTO credentials (name, value, category, description, scope, tenant_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4, 'tenant', $5, NOW(), NOW())
            """, key, final_val, provider, desc, target_tenant_id)
            
    return {"message": f"Integración {provider} actualizada correctamente."}
    """Lista simple de tenants para selectores (id, name)."""
    # Permitir a CEO y Secretary (para selectores de contexto)
    rows = await db.fetch("SELECT id, clinic_name FROM tenants ORDER BY id ASC")
    return [{"id": r["id"], "name": r["clinic_name"]} for r in rows]

# ==================== ENDPOINTS CHAT MANAGEMENT ====================

@router.get("/chat/tenants", dependencies=[Depends(verify_admin_token)], tags=["Chat"])
async def get_chat_tenants(allowed_ids: List[int] = Depends(get_allowed_tenant_ids)):
    """
    Lista de clínicas que el usuario puede ver en Chats.
    CEO: todas. Secretary/Professional: una sola (su clínica).
    Usado por el selector de Clínicas en ChatsView.
    """
    if not allowed_ids:
        return []
    rows = await db.pool.fetch(
        "SELECT id, clinic_name FROM tenants WHERE id = ANY($1::int[]) ORDER BY id ASC",
        allowed_ids,
    )
    return [{"id": r["id"], "clinic_name": r["clinic_name"]} for r in rows]


@router.get("/chat/sessions", dependencies=[Depends(verify_admin_token)], tags=["Chat"])
async def get_chat_sessions(
    tenant_id: int,
    request: Request,
    user_data = Depends(verify_admin_token),
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
):
    """
    Sesiones de chat activas para la clínica indicada.
    El usuario solo ve sesiones cuyo tenant_id coincide con su clínica (o cualquiera si es CEO).
    Human Override y ventana de 24h son por (tenant_id, phone): independientes por clínica.
    """
    if tenant_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta clínica.")
    # Sesiones = pacientes de esta clínica que tienen al menos un mensaje en esta clínica
    has_tenant_in_cm = await db.pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='chat_messages' AND column_name='tenant_id')"
    )
    if not has_tenant_in_cm:
        # Fallback: DB sin parche 15, filtrar solo por patients.tenant_id (mensajes sin tenant)
        rows = await db.pool.fetch("""
            SELECT * FROM (
                SELECT DISTINCT ON (p.phone_number)
                    p.phone_number,
                    p.id as patient_id,
                    p.first_name || ' ' || COALESCE(p.last_name, '') as patient_name,
                    cm.content as last_message,
                    cm.created_at as last_message_time,
                    p.human_handoff_requested,
                    p.human_override_until,
                    p.last_derivhumano_at,
                    CASE 
                        WHEN p.human_handoff_requested AND p.human_override_until > NOW() THEN 'human_handling'
                        WHEN p.human_override_until > NOW() THEN 'silenced'
                        ELSE 'active'
                    END as status,
                    urgency.urgency_level
                FROM patients p
                LEFT JOIN LATERAL (
                    SELECT content, created_at FROM chat_messages
                    WHERE from_number = p.phone_number
                    ORDER BY created_at DESC LIMIT 1
                ) cm ON true
                LEFT JOIN LATERAL (
                    SELECT urgency_level FROM appointments
                    WHERE tenant_id = $1 AND patient_id = p.id
                    ORDER BY created_at DESC LIMIT 1
                ) urgency ON true
                WHERE p.tenant_id = $1
                AND EXISTS (SELECT 1 FROM chat_messages WHERE from_number = p.phone_number)
                ORDER BY p.phone_number, cm.created_at DESC
            ) sub
            ORDER BY last_message_time DESC NULLS LAST
        """, tenant_id)
    else:
        rows = await db.pool.fetch("""
            SELECT * FROM (
                SELECT DISTINCT ON (p.phone_number)
                    p.phone_number,
                    p.id as patient_id,
                    p.first_name || ' ' || COALESCE(p.last_name, '') as patient_name,
                    cm.content as last_message,
                    cm.created_at as last_message_time,
                    p.human_handoff_requested,
                    p.human_override_until,
                    p.last_derivhumano_at,
                    CASE 
                        WHEN p.human_handoff_requested AND p.human_override_until > NOW() THEN 'human_handling'
                        WHEN p.human_override_until > NOW() THEN 'silenced'
                        ELSE 'active'
                    END as status,
                    urgency.urgency_level,
                    cc.last_read_at,
                    cc.last_user_message_at as conv_last_user_msg_at,
                    cc.id as conversation_id
                FROM patients p
                LEFT JOIN chat_conversations cc ON cc.tenant_id = p.tenant_id AND cc.channel = 'whatsapp' AND cc.external_user_id = p.phone_number
                LEFT JOIN LATERAL (
                    SELECT content, created_at FROM chat_messages
                    WHERE tenant_id = $1 AND from_number = p.phone_number AND conversation_id = cc.id
                    ORDER BY created_at DESC LIMIT 1
                ) cm ON true
                LEFT JOIN LATERAL (
                    SELECT urgency_level FROM appointments
                    WHERE tenant_id = $1 AND patient_id = p.id
                    ORDER BY created_at DESC LIMIT 1
                ) urgency ON true
                WHERE p.tenant_id = $1
                AND EXISTS (SELECT 1 FROM chat_messages WHERE tenant_id = $1 AND from_number = p.phone_number)
                ORDER BY p.phone_number, cm.created_at DESC
            ) sub
            ORDER BY last_message_time DESC NULLS LAST
        """, tenant_id)
    sessions = []
    for row in rows:
        unread_sql = """
            SELECT COUNT(*) FROM chat_messages
            WHERE correlation_id = (SELECT id FROM chat_conversations WHERE tenant_id = $1 AND id = $2) -- Just a safety check, or use conversation_id directly
            OR conversation_id = $2
            AND role = 'user'
            AND tenant_id = $1
            AND created_at > GREATEST(
                COALESCE(
                    (SELECT created_at FROM chat_messages
                     WHERE (conversation_id = $2 OR (from_number = $3 AND tenant_id = $1)) AND role = 'assistant'
                     ORDER BY created_at DESC LIMIT 1),
                    '1970-01-01'::timestamptz
                ),
                COALESCE($4, '1970-01-01'::timestamptz)
            )
        """
        # unread_sql simplificado con ID de conversación (Spec 14 isolation)
        unread_sql = """
            SELECT COUNT(*) FROM chat_messages
            WHERE (conversation_id = $1 OR (from_number = $2 AND tenant_id = $3))
            AND role = 'user'
            AND tenant_id = $3
            AND created_at > GREATEST(
                COALESCE(
                    (SELECT created_at FROM chat_messages
                     WHERE (conversation_id = $1 OR (from_number = $2 AND tenant_id = $3)) 
                     AND role = 'assistant' AND tenant_id = $3
                     ORDER BY created_at DESC LIMIT 1),
                    '1970-01-01'::timestamptz
                ),
                COALESCE($4, '1970-01-01'::timestamptz)
            )
        """
        unread = await db.pool.fetchval(unread_sql, row.get("conversation_id"), row["phone_number"], tenant_id, row.get("last_read_at"))
        
        last_user_msg = row.get("conv_last_user_msg_at")
        is_window_open = False
        if last_user_msg:
            # Ventana estricta de 24h (Spec 14 / Clarificación)
            now_utc = datetime.now(timezone.utc)
            msg_utc = last_user_msg if last_user_msg.tzinfo else last_user_msg.replace(tzinfo=timezone.utc)
            is_window_open = (now_utc - msg_utc) < timedelta(hours=24)
        sessions.append({
            "phone_number": row["phone_number"],
            "patient_id": row["patient_id"],
            "patient_name": row["patient_name"],
            "tenant_id": tenant_id,
            "last_message": row["last_message"] or "",
            "last_message_time": row["last_message_time"].isoformat() if row["last_message_time"] else None,
            "unread_count": unread or 0,
            "status": row["status"],
            "human_override_until": row["human_override_until"].isoformat() if row["human_override_until"] else None,
            "urgency_level": row["urgency_level"],
            "last_derivhumano_at": row["last_derivhumano_at"].isoformat() if row["last_derivhumano_at"] else None,
            "is_window_open": is_window_open,
            "last_user_message_time": last_user_msg.isoformat() if last_user_msg else None,
        })
    if sessions:
        from core.auth import log_pii_access
        await log_pii_access(request, user_data, f"Tenant:{tenant_id}", action="list_chat_sessions")
    return sessions


@router.get("/chat/messages/{phone}", dependencies=[Depends(verify_admin_token)], tags=["Chat"])
async def get_chat_messages(
    phone: str,
    tenant_id: int,
    request: Request,
    limit: int = 50,
    offset: int = 0,
    user_data = Depends(verify_admin_token),
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
):
    """Historial de mensajes para un número en la clínica indicada. Aislado por tenant_id."""
    if tenant_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta clínica.")
    has_tenant = await db.pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='chat_messages' AND column_name='tenant_id')"
    )
    if has_tenant:
        rows = await db.pool.fetch("""
            SELECT id, from_number, role, content, created_at, correlation_id, content_attributes
            FROM chat_messages
            WHERE from_number = $1 AND tenant_id = $2
            ORDER BY created_at DESC
            LIMIT $3 OFFSET $4
        """, phone, tenant_id, limit, offset)
    else:
        rows = await db.pool.fetch("""
            SELECT id, from_number, role, content, created_at, correlation_id, content_attributes
            FROM chat_messages
            WHERE from_number = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """, phone, limit, offset)
    
    # Invertir para que lleguen en orden cronológico al frontend
    rows = sorted(rows, key=lambda x: x['created_at'])
    
    messages = []
    for row in rows:
        # Detectar si es un mensaje de derivhumano (sistema indica handoff)
        is_derivhumano = row['role'] == 'assistant' and 'representante humano' in row['content'].lower()
        
        # Parse content_attributes if it's a JSON string
        attachments = []
        raw_attrs = row.get('content_attributes')
        if raw_attrs:
            if isinstance(raw_attrs, str):
                try:
                    attachments = json.loads(raw_attrs)
                except (json.JSONDecodeError, TypeError):
                    attachments = []
            elif isinstance(raw_attrs, list):
                attachments = raw_attrs
        
        messages.append({
            "id": row['id'],
            "from_number": row['from_number'],
            "role": row['role'],
            "content": row['content'],
            "created_at": row['created_at'].isoformat(),
            "is_derivhumano": is_derivhumano,
            "attachments": attachments
        })
    
    logger.info(f"📤 Devueltos {len(messages)} mensajes para {phone} (attachments check: {[len(m.get('attachments', []) or []) for m in messages]})")
    if messages:
        from core.auth import log_pii_access
        await log_pii_access(request, user_data, f"Phone:{phone}", action="read_chat_messages")
    return messages


@router.put("/chat/sessions/{phone}/read", dependencies=[Depends(verify_admin_token)], tags=["Chat"])
async def mark_chat_session_read(
    phone: str,
    tenant_id: int,
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
):
    """Marca la conversación (tenant_id, phone) como leída. Por clínica."""
    if tenant_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta clínica.")
    
    # Persistir estado de lectura (Spec 14 / Fase 3)
    await db.execute("""
        UPDATE chat_conversations 
        SET last_read_at = NOW(), updated_at = NOW()
        WHERE tenant_id = $1 AND channel = 'whatsapp' AND external_user_id = $2
    """, tenant_id, phone)
    
    return {"status": "ok", "phone": phone, "tenant_id": tenant_id}


@router.post("/chat/human-intervention", dependencies=[Depends(verify_admin_token)], tags=["Chat"])
async def toggle_human_intervention(
    payload: HumanInterventionToggle,
    request: Request,
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
):
    """
    Activa o desactiva la intervención humana para un chat (tenant_id + phone).
    Independiente por clínica: intervención en Clínica A no afecta Clínica B.
    """
    if payload.tenant_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta clínica.")
    if payload.activate:
        override_until = datetime.now(ARG_TZ) + timedelta(milliseconds=payload.duration)
        await db.pool.execute("""
            UPDATE patients
            SET human_handoff_requested = TRUE,
                human_override_until = $1,
                last_derivhumano_at = NULL,
                updated_at = NOW()
            WHERE tenant_id = $2 AND phone_number = $3
        """, override_until, payload.tenant_id, payload.phone)
        # Spec 24 / Phase 5: Sync with chat_conversations for omnichannel buffering parity
        await db.pool.execute("""
            UPDATE chat_conversations
            SET human_override_until = $1,
                updated_at = NOW()
            WHERE tenant_id = $2 AND channel = 'whatsapp' AND external_user_id = $3
        """, override_until, payload.tenant_id, payload.phone)

        logger.info(f"👤 Intervención humana activada para {payload.phone} (tenant={payload.tenant_id}) hasta {override_until}")
        await emit_appointment_event("HUMAN_OVERRIDE_CHANGED", {
            "phone_number": payload.phone,
            "tenant_id": payload.tenant_id,
            "enabled": True,
            "until": override_until.isoformat(),
        }, request)
        return {"status": "activated", "phone": payload.phone, "tenant_id": payload.tenant_id, "until": override_until.isoformat()}
    else:
        await db.pool.execute("""
            UPDATE patients
            SET human_handoff_requested = FALSE,
                human_override_until = NULL,
                updated_at = NOW()
            WHERE tenant_id = $1 AND phone_number = $2
        """, payload.tenant_id, payload.phone)
        # Spec 24 / Phase 5: Sync with chat_conversations for omnichannel buffering parity
        await db.pool.execute("""
            UPDATE chat_conversations
            SET human_override_until = NULL,
                updated_at = NOW()
            WHERE tenant_id = $1 AND channel = 'whatsapp' AND external_user_id = $2
        """, payload.tenant_id, payload.phone)

        logger.info(f"🤖 IA reactivada para {payload.phone} (tenant={payload.tenant_id})")
        await emit_appointment_event("HUMAN_OVERRIDE_CHANGED", {
            "phone_number": payload.phone,
            "tenant_id": payload.tenant_id,
            "enabled": False,
        }, request)
        return {"status": "deactivated", "phone": payload.phone, "tenant_id": payload.tenant_id}


@router.post("/chat/remove-silence", dependencies=[Depends(verify_admin_token)], tags=["Chat"])
async def remove_silence(
    payload: dict,
    request: Request,
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
):
    """Remueve el silencio de la IA para (tenant_id, phone). Por clínica."""
    phone = payload.get("phone")
    tenant_id = payload.get("tenant_id")
    if not phone or tenant_id is None:
        raise HTTPException(status_code=400, detail="phone y tenant_id requeridos")
    if tenant_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta clínica.")
    await db.pool.execute("""
        UPDATE patients
        SET human_handoff_requested = FALSE,
            human_override_until = NULL,
            updated_at = NOW()
        WHERE tenant_id = $1 AND phone_number = $2
    """, tenant_id, phone)
    await emit_appointment_event("HUMAN_OVERRIDE_CHANGED", {
        "phone_number": phone,
        "tenant_id": tenant_id,
        "enabled": False,
    }, request)
    return {"status": "removed", "phone": phone, "tenant_id": tenant_id}


@router.get("/internal/credentials/{name}", tags=["Internal"])
async def get_internal_credential(name: str, x_internal_token: str = Header(None)):
    """Permite a servicios internos obtener credenciales de forma segura."""
    if not INTERNAL_API_TOKEN or x_internal_token != INTERNAL_API_TOKEN:
        raise HTTPException(status_code=401, detail="Internal token invalid")
    
    # Mapeo de nombres a variables de entorno o valores de BD
    creds = {
        "YCLOUD_API_KEY": os.getenv("YCLOUD_API_KEY"),
        "YCLOUD_WEBHOOK_SECRET": os.getenv("YCLOUD_WEBHOOK_SECRET"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "YCLOUD_Phone_Number_ID": os.getenv("YCLOUD_Phone_Number_ID") or os.getenv("BOT_PHONE_NUMBER")
    }
    
    val = creds.get(name)
    if val is None: # Solo 404 si la clave no existe en nuestro mapeo
        raise HTTPException(status_code=404, detail=f"Credential '{name}' not supported by this endpoint")
        
    return {"name": name, "value": val}


# ==================== ENDPOINTS CREDENCIALES (SEGURIDAD) ====================

# --- SPEC 19: MEDIA MANAGEMENT & MAINTENANCE ---

@router.get("/chat/media/proxy", tags=["Chat"])
async def media_proxy(url: str, user_data=Depends(verify_admin_token)):
    """
    Proxy seguro para servir archivos multimedia (YCloud, Local, Chatwoot).
    Permite visualizar contenido sin exponer URLs directas o lidiar con CORS/Expiración.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                 raise HTTPException(status_code=resp.status_code, detail="Remote media unreachable")
            
            return StreamingResponse(
                resp.iter_bytes(),
                media_type=resp.headers.get("Content-Type", "application/octet-stream")
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

@router.post("/chat/transcribe-again", tags=["Chat"])
async def transcribe_again(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    user_data=Depends(verify_admin_token),
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids)
):
    """
    Manual re-trigger of Whisper transcription for a given audio message.
    Payload: { 'url': str, 'tenant_id': int, 'conversation_id': str, 'external_user_id': str }
    """
    tid = payload.get("tenant_id")
    if tid not in allowed_ids:
        raise HTTPException(status_code=403, detail="Sin permiso para este tenant.")
        
    background_tasks.add_task(
        transcribe_audio_url,
        url=payload.get("url"),
        tenant_id=tid,
        conversation_id=payload.get("conversation_id"),
        external_user_id=payload.get("external_user_id")
    )
    return {"message": "Transcription re-queued successfully."}

@router.post("/maintenance/clean-media", tags=["Mantenimiento"])
async def clean_media_maintenance(
    payload: Dict[str, Any], 
    user_data=Depends(verify_admin_token)
):
    """
    Elimina archivos de medios antiguos en el servidor.
    Payload: { 'days': int } (e.g. 180 para 6 meses)
    Solo CEO.
    """
    if user_data.role != 'ceo':
        raise HTTPException(status_code=403, detail="Acceso denegado.")
    
    days = payload.get("days", 180)
    cutoff = datetime.now() - timedelta(days=days)
    
    # Directorio de medios (ajustar según despliegue)
    media_dir = os.getenv("MEDIA_DIR", "/public/media")
    if not os.path.exists(media_dir):
        return {"message": "Dircetorio de medios no encontrado.", "deleted": 0}
        
    deleted_count = 0
    # Buscar archivos recursivamente
    for filepath in glob.glob(os.path.join(media_dir, "**", "*"), recursive=True):
        if os.path.isfile(filepath):
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            if mtime < cutoff:
                try:
                    os.remove(filepath)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete {filepath}: {e}")
                    
    return {"message": f"Limpieza completada.", "deleted": deleted_count}


# ==================== ENDPOINTS CREDENCIALES (SEGURIDAD) ====================

@router.get("/credentials", dependencies=[Depends(verify_admin_token)], tags=["Credenciales"])
async def list_credentials(
    resolved_tenant_id: int = Depends(get_resolved_tenant_id),
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
    user_data=Depends(verify_admin_token)
):
    """
    Lista credenciales.
    - Globales: Solo visibles por CEO.
    - Tenant: Visibles por CEO y Admin de esa sede.
    Las valores se devuelven enmascarados (Sanitized).
    """
    try:
        # Consulta base
        query = "SELECT id, name, value, category, description, scope, tenant_id FROM credentials"
        params = []
        conditions = []

        if user_data.role != 'ceo':
            # No CEO: solo scope='tenant' y tenant_id en allowed_ids (o tenant_id NULL para algunos casos?)
            # Asumimos que secretarias solo ven credenciales de SU tenant.
            conditions.append("scope = 'tenant'")
            conditions.append(f"tenant_id = ANY(${len(params) + 1}::int[])")
            params.append(allowed_ids)
        else:
            # CEO: ve todo global + todo tenant
            pass

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY category, name"
        
        rows = await db.pool.fetch(query, *params)
        
        results = []
        for r in rows:
            val = r['value']
            # Enmascarar valor para UI
            masked = "••••••••" 
            if val and len(str(val)) > 4:
                 masked = f"••••••••{str(val)[-4:]}"
            
            # Ocultar valor real
            results.append({
                "id": r['id'],
                "name": r['name'],
                "value": masked, # Frontend espera string, no enviamos el real
                "category": r['category'],
                "description": r['description'],
                "scope": r['scope'],
                "tenant_id": r['tenant_id']
            })
        return results
    except Exception as e:
        logger.error(f"Error listing credentials: {e}")
        raise HTTPException(status_code=500, detail="Error al listar credenciales")

@router.post("/credentials", dependencies=[Depends(verify_admin_token)], tags=["Credenciales"])
async def create_or_update_credential(
    payload: CredentialPayload,
    resolved_tenant_id: int = Depends(get_resolved_tenant_id),
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
    user_data=Depends(verify_admin_token)
):
    """
    Crea o actualiza una credencial.
    - SIEMPRE encripta el valor (Fernet) antes de guardar.
    - Validación de permisos por scope/tenant.
    """
    # 1. Validaciones de Seguridad
    if payload.scope == 'global' and user_data.role != 'ceo':
        raise HTTPException(status_code=403, detail="Solo el CEO puede gestionar credenciales globales.")
    
    target_tenant_id = payload.tenant_id
    if payload.scope == 'tenant':
        if target_tenant_id is None:
             # Si no viene, usamos el resuelto (propia clínica)
             target_tenant_id = resolved_tenant_id
        
        # Verificar acceso
        if target_tenant_id not in allowed_ids:
             raise HTTPException(status_code=403, detail="No tienes permiso para gestionar credenciales de esta clínica.")
    else:
        target_tenant_id = None # Global
        
    # 2. Encriptación
    encrypted_value = encrypt_value(payload.value)
    if not encrypted_value:
        raise HTTPException(status_code=503, detail="Error de encriptación. Verificar CREDENTIALS_FERNET_KEY.")
        
    try:
        # 3. Upsert vs Update vs Insert
        # La UI envia ID si edita.
        if payload.id:
            # Update existente
            # Verificar ownership antes de update
            existing = await db.pool.fetchrow("SELECT id, scope, tenant_id FROM credentials WHERE id = $1", payload.id)
            if not existing:
                raise HTTPException(status_code=404, detail="Credencial no encontrada")
            
            # Si era global y user no es CEO -> ya validado arriba, pero por si acaso cambio de scope
            if existing['scope'] == 'global' and user_data.role != 'ceo':
                 raise HTTPException(status_code=403, detail="No puedes editar credenciales globales.")
            if existing['scope'] == 'tenant' and existing['tenant_id'] not in allowed_ids:
                 raise HTTPException(status_code=403, detail="No tienes acceso a esta credencial.")

            await db.pool.execute("""
                UPDATE credentials 
                SET name = $1, value = $2, category = $3, description = $4, scope = $5, tenant_id = $6, updated_at = NOW()
                WHERE id = $7
            """, payload.name, encrypted_value, payload.category, payload.description, payload.scope, target_tenant_id, payload.id)
            action = "updated"
        else:
            # Insert
            await db.pool.execute("""
                INSERT INTO credentials (name, value, category, description, scope, tenant_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
            """, payload.name, encrypted_value, payload.category, payload.description, payload.scope, target_tenant_id)
            action = "created"
            
        logger.info(f"Credential {action}: name={payload.name} scope={payload.scope} tenant={target_tenant_id} by {user_data.email}")
        return {"status": "ok", "action": action}
        
    except Exception as e:
        logger.error(f"Error saving credential: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/credentials/{id}", dependencies=[Depends(verify_admin_token)], tags=["Credenciales"])
async def delete_credential(
    id: int,
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
    user_data=Depends(verify_admin_token)
):
    try:
        existing = await db.pool.fetchrow("SELECT scope, tenant_id FROM credentials WHERE id = $1", id)
        if not existing:
             return {"status": "deleted"} # Idempotente
             
        if existing['scope'] == 'global' and user_data.role != 'ceo':
             raise HTTPException(status_code=403, detail="Solo CEO puede eliminar credenciales globales.")
        
        if existing['scope'] == 'tenant' and existing['tenant_id'] not in allowed_ids:
             raise HTTPException(status_code=403, detail="No tienes acceso a esta clínica.")
             
        await db.pool.execute("DELETE FROM credentials WHERE id = $1", id)
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting credential: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar credencial")


@router.put("/credentials/{cred_id}", dependencies=[Depends(verify_admin_token)], tags=["Credenciales"])
async def update_credential(
    cred_id: int,
    payload: CredentialPayload,
    resolved_tenant_id: int = Depends(get_resolved_tenant_id),
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
    user_data=Depends(verify_admin_token)
):
    """
    Actualiza una credencial existente.
    - Verifica ownership antes de modificar.
    - Si el valor llega enmascarado (••••), conserva el valor encriptado anterior.
    - Solo CEO puede editar credenciales globales.
    """
    try:
        existing = await db.pool.fetchrow(
            "SELECT id, scope, tenant_id, value FROM credentials WHERE id = $1", cred_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Credencial no encontrada.")

        if existing['scope'] == 'global' and user_data.role != 'ceo':
            raise HTTPException(status_code=403, detail="Solo CEO puede editar credenciales globales.")

        if existing['scope'] == 'tenant' and existing['tenant_id'] not in allowed_ids:
            raise HTTPException(status_code=403, detail="No tienes acceso a esta credencial.")

        if payload.scope == 'global' and user_data.role != 'ceo':
            raise HTTPException(status_code=403, detail="Solo CEO puede asignar scope global.")

        target_tenant_id = payload.tenant_id
        if payload.scope == 'tenant' and target_tenant_id is None:
            target_tenant_id = resolved_tenant_id

        # Conservar valor encriptado anterior si el frontend envía el valor enmascarado
        if payload.value and not payload.value.startswith("••••"):
            new_value = encrypt_value(payload.value)
            if not new_value:
                raise HTTPException(status_code=503, detail="Error de encriptación. Verificar CREDENTIALS_FERNET_KEY.")
        else:
            new_value = existing['value']

        await db.pool.execute("""
            UPDATE credentials
            SET name = $1, value = $2, category = $3, description = $4, scope = $5, tenant_id = $6, updated_at = NOW()
            WHERE id = $7
        """, payload.name, new_value, payload.category, payload.description, payload.scope, target_tenant_id, cred_id)

        logger.info(f"Credential updated: id={cred_id} name={payload.name} scope={payload.scope} by {user_data.email}")
        return {"status": "ok", "action": "updated"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating credential {cred_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/send", dependencies=[Depends(verify_admin_token)], tags=["Chat"])
async def send_chat_message(
    payload: ChatSendMessage,
    request: Request,
    background_tasks: BackgroundTasks,
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
):
    """Envía un mensaje manual por WhatsApp; guarda en BD con tenant_id. Ventana 24h por clínica."""
    if payload.tenant_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta clínica.")
    try:
        has_tenant = await db.pool.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='chat_messages' AND column_name='tenant_id')"
        )
        if has_tenant:
            last_user_msg = await db.pool.fetchval("""
                SELECT created_at FROM chat_messages
                WHERE from_number = $1 AND role = 'user' AND tenant_id = $2
                ORDER BY created_at DESC LIMIT 1
            """, payload.phone, payload.tenant_id)
        else:
            last_user_msg = await db.pool.fetchval("""
                SELECT created_at FROM chat_messages
                WHERE from_number = $1 AND role = 'user'
                ORDER BY created_at DESC LIMIT 1
            """, payload.phone)
        if not last_user_msg:
            raise HTTPException(status_code=403, detail="No se puede enviar un mensaje si el usuario nunca ha escrito.")
        now_localized = datetime.now(last_user_msg.tzinfo if last_user_msg.tzinfo else ARG_TZ)
        if (now_localized - last_user_msg) > timedelta(hours=24):
            raise HTTPException(status_code=403, detail="La ventana de 24hs de WhatsApp ha expirado. El paciente debe escribir primero.")
        correlation_id = str(uuid.uuid4())
        await db.append_chat_message(
            from_number=payload.phone,
            role="assistant",
            content=payload.message,
            correlation_id=correlation_id,
            tenant_id=payload.tenant_id,
        )
        if hasattr(request.app.state, "emit_appointment_event"):
            await request.app.state.emit_appointment_event("NEW_MESSAGE", {
                "phone_number": payload.phone,
                "tenant_id": payload.tenant_id,
                "message": payload.message,
                "role": "assistant",
            })
        business_number = os.getenv("YCLOUD_Phone_Number_ID") or os.getenv("BOT_PHONE_NUMBER") or "default"
        background_tasks.add_task(send_to_whatsapp_task, payload.phone, payload.message, business_number)
        return {"status": "sent", "correlation_id": correlation_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending manual message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ENDPOINTS DASHBOARD ====================

@router.get("/stats/summary", tags=["Estadísticas"], summary="Obtener resumen de métricas del dashboard")
async def get_dashboard_stats(
    range: str = 'all',
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Devuelve métricas avanzadas filtradas por rango temporal. Aislado por tenant_id (Regla de Oro)."""
    try:
        # Normalizar el mapeo de intervalos para Postgres
        interval_map = {
            'weekly': "INTERVAL '7 days'",
            'monthly': "INTERVAL '30 days'",
            'yearly': "INTERVAL '1 year'",
            'all': "INTERVAL '100 years'"
        }
        interval_expr = interval_map.get(range, "INTERVAL '100 years'")
        
        # 1. IA Conversations (Unificado de chat_conversations para todos los canales e hilos)
        ia_conversations = await db.pool.fetchval(f"""
            SELECT COUNT(*) FROM chat_conversations
            WHERE tenant_id = $1 AND created_at >= CURRENT_DATE - {interval_expr}
        """, tenant_id) or 0
        
        # 2. IA Appointments (Turnos de IA en el rango seleccionado)
        ia_count = await db.pool.fetchval(f"""
            SELECT COUNT(*) FROM appointments 
            WHERE tenant_id = $1 AND source = 'ai' AND appointment_datetime >= CURRENT_DATE - {interval_expr}
        """, tenant_id) or 0
        
        # 3. Urgencias activas (Total acumulado de urgencias detectadas en el rango)
        active_urgencies = await db.pool.fetchval(f"""
            SELECT COUNT(*) FROM appointments 
            WHERE tenant_id = $1 AND urgency_level IN ('high', 'emergency') 
            AND status NOT IN ('cancelled', 'completed')
            AND appointment_datetime >= CURRENT_DATE - {interval_expr}
        """, tenant_id) or 0
        
        # 4. Revenue Dual (Real vs Estimado)
        # 4a. Real Revenue (Pagos confirmados)
        confirmed_revenue = await db.pool.fetchval(f"""
            SELECT COALESCE(SUM(at.amount), 0) 
            FROM accounting_transactions at
            WHERE at.tenant_id = $1 
            AND at.transaction_type = 'payment' 
            AND at.status = 'completed'
            AND at.created_at >= CURRENT_DATE - {interval_expr}
        """, tenant_id) or 0

        # 4b. Estimated Revenue (Valor de agenda IA - Basado en precios de tratamientos)
        # Si un turno no tiene tipo de tratamiento, usamos un falback de 100? No, mejor 0 o valor por defecto de la clínica.
        # Buscamos el precio base asignado a cada tipo de tratamiento.
        estimated_revenue = await db.pool.fetchval(f"""
            SELECT COALESCE(SUM(tt.base_price), 0)
            FROM appointments a
            JOIN treatment_types tt ON a.appointment_type = tt.code AND tt.tenant_id = a.tenant_id
            WHERE a.tenant_id = $1 AND a.source = 'ai'
            AND a.status NOT IN ('cancelled')
            AND a.appointment_datetime >= CURRENT_DATE - {interval_expr}
        """, tenant_id) or 0
        
        # 5. Datos de crecimiento (Agrupación Inteligente: DÍA para Weekly/Monthly, MES para Anual/All)
        if range in ('yearly', 'all'):
            growth_rows = await db.pool.fetch(f"""
                SELECT 
                    DATE_TRUNC('month', appointment_datetime) as period,
                    COUNT(*) FILTER (WHERE source = 'ai') as ia_referrals,
                    COUNT(*) FILTER (WHERE status IN ('completed', 'attended')) as completed_appointments
                FROM appointments
                WHERE tenant_id = $1 AND appointment_datetime >= CURRENT_DATE - {interval_expr}
                GROUP BY period
                ORDER BY period ASC
            """, tenant_id)
        else:
            growth_rows = await db.pool.fetch(f"""
                SELECT 
                    DATE(appointment_datetime) as period,
                    COUNT(*) FILTER (WHERE source = 'ai') as ia_referrals,
                    COUNT(*) FILTER (WHERE status IN ('completed', 'attended')) as completed_appointments
                FROM appointments
                WHERE tenant_id = $1 AND appointment_datetime >= CURRENT_DATE - {interval_expr}
                GROUP BY period
                ORDER BY period ASC
            """, tenant_id)
        
        growth_data = []
        for row in growth_rows:
            p = row['period']
            date_str = p.strftime('%Y-%m') if range in ('yearly', 'all') else p.strftime('%Y-%m-%d')
            growth_data.append({
                "date": date_str,
                "ia_referrals": row['ia_referrals'],
                "completed_appointments": row['completed_appointments']
            })

        if not growth_data:
            growth_data = [{"date": date.today().isoformat(), "ia_referrals": 0, "completed_appointments": 0}]

        # 6. Calcular Rangos Previos para Tendencias (Crecimiento Real)
        prev_interval_expr = interval_expr # El mismo intervalo pero desplazado
        
        # Consultas Previas
        prev_ia_conversations = await db.pool.fetchval(f"""
            SELECT COUNT(*) FROM chat_conversations
            WHERE tenant_id = $1 
            AND created_at < CURRENT_DATE - {interval_expr}
            AND created_at >= CURRENT_DATE - {interval_expr} * 2
        """, tenant_id) or 0
        
        prev_ia_count = await db.pool.fetchval(f"""
            SELECT COUNT(*) FROM appointments 
            WHERE tenant_id = $1 AND source = 'ai' 
            AND appointment_datetime < CURRENT_DATE - {interval_expr}
            AND appointment_datetime >= CURRENT_DATE - {interval_expr} * 2
        """, tenant_id) or 0
        
        prev_confirmed_revenue = await db.pool.fetchval(f"""
            SELECT COALESCE(SUM(at.amount), 0) 
            FROM accounting_transactions at
            WHERE at.tenant_id = $1 
            AND at.transaction_type = 'payment' 
            AND at.status = 'completed'
            AND at.created_at < CURRENT_DATE - {interval_expr}
            AND at.created_at >= CURRENT_DATE - {interval_expr} * 2
        """, tenant_id) or 0

        def calc_trend(current, previous):
            if previous == 0:
                return "+100%" if current > 0 else "0%"
            change = ((current - previous) / previous) * 100
            return f"{'+' if change >= 0 else ''}{change:.1f}%"

        return {
            "ia_conversations": ia_conversations,
            "ia_conversations_trend": calc_trend(ia_conversations, prev_ia_conversations),
            "ia_appointments": ia_count,
            "ia_appointments_trend": calc_trend(ia_count, prev_ia_count),
            "active_urgencies": active_urgencies,
            "total_revenue": float(confirmed_revenue),
            "total_revenue_trend": calc_trend(float(confirmed_revenue), float(prev_confirmed_revenue)),
            "estimated_revenue": float(estimated_revenue),
            "growth_data": growth_data
        }
    except Exception as e:
        logger.error(f"Error en get_dashboard_stats: {e}")
        raise HTTPException(status_code=500, detail="Error al cargar estadísticas.")

# --- CLÍNICAS (TENANTS) - CEO ONLY ---
# Tratamos "Tenant" como "Clínica". config (JSONB) incluye calendar_provider: 'local' | 'google'.

@router.get("/tenants", tags=["Sedes"], summary="Listar todas las sedes (clínicas)")
async def get_tenants(user_data=Depends(verify_admin_token)):
    """Lista todas las clínicas (tenants). Solo CEO. Incluye config (JSONB) con calendar_provider."""
    if user_data.role != 'ceo':
        raise HTTPException(status_code=403, detail="Solo el CEO puede gestionar clínicas.")
    rows = await db.pool.fetch(
        "SELECT id, clinic_name, bot_phone_number, config, created_at, updated_at FROM tenants ORDER BY id ASC"
    )
    return [dict(r) for r in rows]

@router.post("/tenants", tags=["Sedes"], summary="Crear una nueva sede")
async def create_tenant(data: Dict[str, Any], user_data=Depends(verify_admin_token)):
    """Crea una nueva clínica. config.calendar_provider obligatorio: 'local' o 'google'."""
    if user_data.role != 'ceo':
        raise HTTPException(status_code=403, detail="Solo el CEO puede gestionar clínicas.")
    calendar_provider = (data.get("calendar_provider") or data.get("config", {}).get("calendar_provider") or "local").lower()
    if calendar_provider not in ("local", "google"):
        calendar_provider = "local"
    config_json = json.dumps({"calendar_provider": calendar_provider})
    query = """
    INSERT INTO tenants (clinic_name, bot_phone_number, config, created_at)
    VALUES ($1, $2, $3::jsonb, NOW())
    RETURNING id
    """
    try:
        new_id = await db.pool.fetchval(
            query,
            data.get("clinic_name"),
            data.get("bot_phone_number"),
            config_json,
        )
        return {"id": new_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/tenants/{tenant_id}", tags=["Sedes"], summary="Actualizar datos de una sede")
async def update_tenant(tenant_id: int, data: Dict[str, Any], user_data=Depends(verify_admin_token)):
    """Actualiza datos de una clínica. Incluye config.calendar_provider si se envía."""
    if user_data.role != 'ceo':
        raise HTTPException(status_code=403, detail="Solo el CEO puede gestionar clínicas.")
    updates = []
    params = []
    if "clinic_name" in data and data["clinic_name"] is not None:
        params.append(data["clinic_name"])
        updates.append(f"clinic_name = ${len(params)}")
    if "bot_phone_number" in data and data["bot_phone_number"] is not None:
        params.append(data["bot_phone_number"])
        updates.append(f"bot_phone_number = ${len(params)}")
    if "calendar_provider" in data and data["calendar_provider"] is not None:
        cp = str(data["calendar_provider"]).lower() if data["calendar_provider"] else "local"
        if cp not in ("local", "google"):
            cp = "local"
        # Persistir config como JSON explícito para evitar problemas de tipo en PostgreSQL
        config_patch = json.dumps({"calendar_provider": cp})
        params.append(config_patch)
        updates.append(f"config = COALESCE(config, '{{}}')::jsonb || ${len(params)}::jsonb")
    if not updates:
        return {"status": "updated"}
    params.append(tenant_id)
    updates.append("updated_at = NOW()")
    query = f"UPDATE tenants SET {', '.join(updates)} WHERE id = ${len(params)}"
    await db.pool.execute(query, *params)
    logger.info(f"Tenant {tenant_id} updated: calendar_provider={data.get('calendar_provider')} (persisted)")
    return {"status": "updated"}

@router.delete("/tenants/{tenant_id}", tags=["Sedes"], summary="Eliminar una sede")
async def delete_tenant(tenant_id: int, user_data=Depends(verify_admin_token)):
    """Elimina una clínica. Solo CEO."""
    if user_data.role != 'ceo':
        raise HTTPException(status_code=403, detail="Solo el CEO puede gestionar clínicas.")
    await db.pool.execute("DELETE FROM tenants WHERE id = $1", tenant_id)
    return {"status": "deleted"}

@router.get("/chat/urgencies", dependencies=[Depends(verify_admin_token)], tags=["Chat"], summary="Listar urgencias recientes detectadas")
async def get_recent_urgencies(limit: int = 10, tenant_id: int = Depends(get_resolved_tenant_id)):
    """Retorna los últimos casos de urgencia. Aislado por tenant_id (Regla de Oro)."""
    try:
        rows = await db.pool.fetch("""
            SELECT 
                a.id,
                p.first_name || ' ' || COALESCE(p.last_name, '') as patient_name,
                p.phone_number as phone,
                UPPER(a.urgency_level) as urgency_level,
                COALESCE(a.urgency_reason, 'Consulta IA detectada') as reason,
                a.appointment_datetime as timestamp
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            WHERE a.tenant_id = $1 AND a.urgency_level IN ('high', 'emergency')
            ORDER BY a.created_at DESC
            LIMIT $2
        """, tenant_id, limit)
        
        return [
            {
                "id": str(row['id']),
                "patient_name": row['patient_name'],
                "phone": row['phone'],
                "urgency_level": "CRITICAL" if row['urgency_level'] == "EMERGENCY" else row['urgency_level'],
                "reason": row['reason'],
                "timestamp": row['timestamp'].strftime('%d/%m %H:%M') if hasattr(row['timestamp'], 'strftime') else str(row['timestamp'])
            } for row in rows
        ]
    except Exception as e:
        logger.error(f"Error fetching urgencies: {e}")
        return []

@router.get("/config/deployment", dependencies=[Depends(verify_admin_token)], tags=["Configuración"], summary="Obtener configuración de despliegue")
async def get_deployment_config(request: Request):
    """Retorna configuración dinámica de despliegue (Webhooks, URLs)."""
    # Detectamos la URL base actual si no está forzada en ENV
    host = request.headers.get("host", "localhost:8000")
    protocol = "https" if request.headers.get("x-forwarded-proto") == "https" else "http"
    base_url = f"{protocol}://{host}"
    
    return {
        "webhook_ycloud_url": f"{base_url}/webhook/ycloud",
        "webhook_ycloud_internal_port": os.getenv("WHATSAPP_SERVICE_PORT", "8002"),
        "orchestrator_url": base_url,
        "environment": os.getenv("ENVIRONMENT", "development")
    }

@router.get("/settings/clinic", dependencies=[Depends(verify_admin_token)], tags=["Configuración"], summary="Obtener configuración operativa de la clínica")
async def get_clinic_settings(resolved_tenant_id: int = Depends(get_resolved_tenant_id)):
    """Retorna la configuración operativa de la clínica (nombre, horarios, ui_language) desde el tenant."""
    try:
        row = await db.pool.fetchrow(
            "SELECT clinic_name, config FROM tenants WHERE id = $1",
            resolved_tenant_id
        )
        if not row:
            return _fallback_clinic_settings()
        config = row["config"] or {}
        ui_lang = (config.get("ui_language") or "en") if isinstance(config, dict) else "en"
        return {
            "name": row["clinic_name"] or os.getenv("CLINIC_NAME", "Clínica Dental"),
            "location": os.getenv("CLINIC_LOCATION", ""),
            "hours_start": os.getenv("CLINIC_HOURS_START", "08:00"),
            "hours_end": os.getenv("CLINIC_HOURS_END", "19:00"),
            "working_days": [0, 1, 2, 3, 4, 5],
            "time_zone": "America/Argentina/Buenos_Aires",
            "ui_language": ui_lang,
        }
    except Exception as e:
        logger.warning(f"get_clinic_settings failed: {e}")
        return _fallback_clinic_settings()


def _fallback_clinic_settings():
    """Config por defecto cuando no hay tenant o falla la consulta."""
    return {
        "name": os.getenv("CLINIC_NAME", "Clínica Dental"),
        "location": os.getenv("CLINIC_LOCATION", ""),
        "hours_start": os.getenv("CLINIC_HOURS_START", "08:00"),
        "hours_end": os.getenv("CLINIC_HOURS_END", "19:00"),
        "working_days": [0, 1, 2, 3, 4, 5],
        "time_zone": "America/Argentina/Buenos_Aires",
        "ui_language": "en",
    }


class ClinicSettingsUpdate(BaseModel):
    ui_language: Optional[str] = None  # "es" | "en" | "fr"


@router.patch("/settings/clinic", dependencies=[Depends(verify_admin_token)], tags=["Configuración"], summary="Actualizar configuración operativa de la clínica")
async def update_clinic_settings(
    payload: ClinicSettingsUpdate,
    resolved_tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Actualiza configuración de la clínica (ej. idioma de la UI). Solo campos enviados."""
    if payload.ui_language is not None:
        if payload.ui_language not in ("es", "en", "fr"):
            raise HTTPException(status_code=400, detail="ui_language debe ser 'es', 'en' o 'fr'.")
        try:
            await db.pool.execute(
                """
                UPDATE tenants
                SET config = jsonb_set(COALESCE(config, '{}'), '{ui_language}', to_jsonb($1::text))
                WHERE id = $2
                """,
                payload.ui_language,
                resolved_tenant_id,
            )
        except Exception as e:
            logger.error(f"update_clinic_settings failed: {e}")
            raise HTTPException(status_code=500, detail="Error al guardar la configuración.")
    return {"status": "ok", "ui_language": getattr(payload, "ui_language", None)}

# ==================== ENDPOINTS BÚSQUEDA SEMÁNTICA ====================

@router.get("/patients/search-semantic", tags=["Pacientes"], summary="Búsqueda semántica de pacientes por síntomas")
async def search_patients_by_symptoms(
    query: str,
    limit: int = 20,
    user_data=Depends(verify_admin_token),
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Búsqueda semántica de pacientes por síntomas. Aislado por tenant_id (Regla de Oro).
    - CEO: retorna pacientes de todas sus sedes (allowed_ids).
    - Staff/Profesional: retorna pacientes solo de su sede activa.
    """
    try:
        is_ceo = user_data.role == 'ceo'

        if is_ceo:
            # CEO: buscar en chat_messages sin filtro de sede (los patient_ids luego se filtran)
            chat_matches = await db.pool.fetch("""
                SELECT DISTINCT patient_id
                FROM chat_messages
                WHERE content ILIKE $1
                LIMIT $2
            """, f"%{query}%", limit)
        else:
            # Staff: filtrar chat_messages por tenant_id de la sede activa
            chat_matches = await db.pool.fetch("""
                SELECT DISTINCT cm.patient_id
                FROM chat_messages cm
                JOIN patients p ON cm.patient_id = p.id
                WHERE cm.content ILIKE $1
                  AND p.tenant_id = $2
                LIMIT $3
            """, f"%{query}%", tenant_id, limit)

        patient_ids = [row['patient_id'] for row in chat_matches if row['patient_id'] is not None]

        if not patient_ids:
            return []

        if is_ceo:
            # CEO: filtrar por sus sedes permitidas
            patients = await db.pool.fetch("""
                SELECT id, first_name, last_name, phone_number, email, insurance_provider, dni, created_at
                FROM patients
                WHERE id = ANY($1::int[])
                  AND tenant_id = ANY($2::int[])
                  AND status = 'active'
            """, patient_ids, allowed_ids)
        else:
            # Staff: filtrar por su sede activa
            patients = await db.pool.fetch("""
                SELECT id, first_name, last_name, phone_number, email, insurance_provider, dni, created_at
                FROM patients
                WHERE id = ANY($1::int[])
                  AND tenant_id = $2
                  AND status = 'active'
            """, patient_ids, tenant_id)

        return [dict(row) for row in patients]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en búsqueda semántica: {str(e)}")

# ==================== ENDPOINTS SEGURO / OBRAS SOCIALES ====================

@router.get("/patients/{patient_id}/insurance-status", dependencies=[Depends(verify_admin_token)], tags=["Pacientes"], summary="Verificar estado de obra social del paciente")
async def get_patient_insurance_status(
    patient_id: int,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Verifica el estado de la credencial de obra social de un paciente.
    
    Returns:
        - status: 'ok' | 'warning' | 'expired'
        - requires_token: boolean (ej: OSDE requiere token)
        - message: string con descripción del estado
        - expiration_days: días hasta el vencimiento (negativo = vencido)
        - insurance_provider: nombre de la obra social
    """
    try:
        # Obtener datos del paciente y su obra social
        patient = await db.pool.fetchrow("""
            SELECT id, first_name, last_name, phone_number, insurance_provider,
                   insurance_id, insurance_valid_until, status
            FROM patients
            WHERE id = $1 AND tenant_id = $2 AND status = 'active'
        """, patient_id, tenant_id)
        
        if not patient:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")
        
        insurance_provider = patient.get('insurance_provider') or ''
        expiry_date = patient.get('insurance_valid_until')
        
        # Si no tiene obra social configurada
        if not insurance_provider:
            return {
                "status": "ok",
                "requires_token": False,
                "message": "Sin obra social configurada",
                "expiration_days": None,
                "insurance_provider": None
            }
        
        # Verificar si requiere token (algunas obras sociales específicas)
        requires_token = insurance_provider.upper() in ['OSDE', 'SWISS MEDICAL', 'GALENO', 'MEDICINA PREPAGA']
        
        # Calcular días hasta vencimiento
        expiration_days = None
        if expiry_date:
            # Asegurar que sea objeto date para la resta
            if isinstance(expiry_date, str):
                expiry_dt = date.fromisoformat(expiry_date.split('T')[0])
            elif isinstance(expiry_date, datetime):
                expiry_dt = expiry_date.date()
            else:
                expiry_dt = expiry_date # Asumimos que ya es date
            
            today = date.today()
            delta = expiry_dt - today
            expiration_days = delta.days
        
        # Determinar estado
        if expiration_days is not None and expiration_days < 0:
            # Credencial vencida
            return {
                "status": "expired",
                "requires_token": requires_token,
                "message": f"Credencial vencida hace {abs(expiration_days)} días. Requiere renovación.",
                "expiration_days": expiration_days,
                "insurance_provider": insurance_provider
            }
        elif expiration_days is not None and expiration_days <= 30:
            # Credencial próxima a vencer (30 días)
            return {
                "status": "warning",
                "requires_token": requires_token,
                "message": f"Credencial vence en {expiration_days} días. Considera renovar.",
                "expiration_days": expiration_days,
                "insurance_provider": insurance_provider
            }
        else:
            # Todo bien
            message = "Credencial vigente"
            if requires_token:
                message += ". Requiere validación de token"
            
            return {
                "status": "ok",
                "requires_token": requires_token,
                "message": message,
                "expiration_days": expiration_days,
                "insurance_provider": insurance_provider
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error verificando seguro: {str(e)}")

# ==================== ENDPOINTS PACIENTES ====================

@router.post("/patients", dependencies=[Depends(verify_admin_token)], tags=["Pacientes"], summary="Crear un nuevo paciente")
async def create_patient(
    p: PatientCreate,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Crear un paciente nuevo en la sede actual. Aislado por tenant_id (Regla de Oro)."""
    try:
        row = await db.pool.fetchrow("""
            INSERT INTO patients (tenant_id, first_name, last_name, phone_number, email, dni, insurance_provider, status, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'active', NOW())
            RETURNING id
        """,
            tenant_id,
            (p.first_name or "").strip() or "Sin nombre",
            (p.last_name or "").strip() or "",
            (p.phone_number or "").strip(),
            (p.email or "").strip() or None,
            (p.dni or "").strip() or None,
            (p.insurance or "").strip() or None,
        )
        return {"id": row["id"]}
    except asyncpg.UniqueViolationError as e:
        if "patients_tenant_id_phone_number_key" in str(e) or "tenant_id" in str(e).lower() and "phone" in str(e).lower():
            raise HTTPException(status_code=409, detail="Ya existe un paciente con ese número de teléfono en esta sede. Podés buscarlo en la lista o usar otro teléfono.")
        raise HTTPException(status_code=409, detail="Paciente duplicado (mismo DNI o teléfono en esta sede).")
    except Exception as e:
        logger.error(f"Error creating patient: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/patients", dependencies=[Depends(verify_admin_token)], tags=["Pacientes"], summary="Listar pacientes con turnos asociados")
async def list_patients(
    search: str = None,
    limit: int = 50,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Listar pacientes del tenant. Solo aparecen quienes tienen al menos un turno (Lead vs Paciente).
    Aislado por tenant_id (Regla de Oro).
    """
    query = """
        SELECT p.id, p.first_name, p.last_name, p.phone_number, p.email,
               p.insurance_provider as obra_social, p.dni, p.created_at, p.status
        FROM patients p
        WHERE p.tenant_id = $1 AND p.status != 'deleted'
          AND EXISTS (
              SELECT 1 FROM appointments a
              WHERE a.patient_id = p.id AND a.tenant_id = p.tenant_id
          )
    """
    params: List[Any] = [tenant_id]
    if search:
        query += " AND (p.first_name ILIKE $2 OR p.last_name ILIKE $2 OR p.phone_number ILIKE $2 OR p.dni ILIKE $2)"
        params.append(f"%{search}%")
        query += " ORDER BY p.created_at DESC LIMIT $3"
        params.append(limit)
    else:
        query += " ORDER BY p.created_at DESC LIMIT $2"
        params.append(limit)
    rows = await db.pool.fetch(query, *params)
    return [dict(row) for row in rows]

@router.post("/professionals", dependencies=[Depends(verify_admin_token)], tags=["Profesionales"], summary="Crear un nuevo profesional de la salud")
async def create_professional(
    professional: ProfessionalCreate,
    resolved_tenant_id: int = Depends(get_resolved_tenant_id),
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
):
    """
    Crear un nuevo profesional. Soberanía: se asocia a la clínica elegida.
    Si el body trae tenant_id y el usuario tiene acceso a esa clínica, se usa; si no, la del contexto.
    Así el agente y el sistema saben a qué clínica pertenece el profesional.
    """
    try:
        tid_raw = professional.tenant_id
        tid_int = int(tid_raw) if tid_raw is not None else None
        tenant_id = (
            tid_int
            if tid_int is not None and tid_int in allowed_ids
            else resolved_tenant_id
        )
    except (TypeError, ValueError):
        tenant_id = resolved_tenant_id

    email = (professional.email or "").strip() or f"prof_{uuid.uuid4().hex[:8]}@dentalogic.local"
    name_part = (professional.name or "").strip()
    first_name = name_part.split(maxsplit=1)[0] if name_part else "Profesional"
    last_name = name_part.split(maxsplit=1)[1] if name_part and len(name_part.split(maxsplit=1)) > 1 else " "

    # 1. Usuario: crear nuevo o reutilizar si el email ya existe (vincular a esta sede)
    existing_user = await db.pool.fetchrow("SELECT id FROM users WHERE email = $1", email)
    if existing_user:
        user_id = existing_user["id"]
        # ¿Ya tiene fila en professionals para esta sede? Entonces es duplicado real.
        already_linked = await db.pool.fetchval(
            "SELECT 1 FROM professionals WHERE user_id = $1 AND tenant_id = $2",
            user_id, tenant_id,
        )
        if already_linked:
            raise HTTPException(
                status_code=409,
                detail="Ese profesional ya está vinculado a esta sede. Buscalo en la lista de Profesionales.",
            )
        # Si no está vinculado a esta sede: creamos la fila en professionals (aparece como activo)
    else:
        user_id = uuid.uuid4()
        try:
            await db.pool.execute("""
                INSERT INTO users (id, email, password_hash, role, first_name, status, created_at)
                VALUES ($1, $2, $3, 'professional', $4, 'active', NOW())
            """, user_id, email, "hash_placeholder", first_name)
        except asyncpg.UndefinedColumnError:
            await db.pool.execute("""
                INSERT INTO users (id, email, password_hash, role, status, created_at)
                VALUES ($1, $2, $3, 'professional', 'active', NOW())
            """, user_id, email, "hash_placeholder")

    try:

        # 2. Crear profesional (tenant_id = clínica elegida)
        wh = professional.working_hours or generate_default_working_hours()
        if not isinstance(wh, dict):
            wh = generate_default_working_hours()
        try:
            wh_json = json.dumps(wh)
        except (TypeError, ValueError):
            wh_json = json.dumps(generate_default_working_hours())
        matricula = professional.license_number or None
        phone_val = professional.phone or None
        specialty_val = professional.specialty or None

        params = [tenant_id, user_id, first_name, last_name, email, phone_val,
                  specialty_val, matricula, professional.is_active, wh_json]
        try:
            await db.pool.execute("""
                INSERT INTO professionals (
                    tenant_id, user_id, first_name, last_name, email, phone_number,
                    specialty, registration_id, is_active, working_hours, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, NOW(), NOW())
            """, *params)
        except asyncpg.UndefinedColumnError as e:
            err_str = str(e).lower()
            if "registration_id" in err_str:
                await db.pool.execute("""
                    INSERT INTO professionals (
                        tenant_id, user_id, first_name, last_name, email, phone_number,
                        specialty, license_number, is_active, working_hours, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, NOW(), NOW())
                """, *params)
            elif "updated_at" in err_str:
                await db.pool.execute("""
                    INSERT INTO professionals (
                        tenant_id, user_id, first_name, last_name, email, phone_number,
                        specialty, registration_id, is_active, working_hours, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, NOW())
                """, *params)
            elif "phone_number" in err_str:
                # BD antigua sin columna phone_number (solo columnas típicas en esquemas viejos)
                params_no_phone = [tenant_id, user_id, first_name, last_name, email,
                                   specialty_val, matricula, professional.is_active, wh_json]
                try:
                    await db.pool.execute("""
                        INSERT INTO professionals (
                            tenant_id, user_id, first_name, last_name, email,
                            specialty, registration_id, is_active, working_hours, created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, NOW(), NOW())
                    """, *params_no_phone)
                except asyncpg.UndefinedColumnError as e2:
                    if "updated_at" in str(e2).lower():
                        await db.pool.execute("""
                            INSERT INTO professionals (
                                tenant_id, user_id, first_name, last_name, email,
                                specialty, registration_id, is_active, working_hours, created_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, NOW())
                        """, *params_no_phone)
                    else:
                        raise
            elif "email" in err_str:
                params_no_email = [tenant_id, user_id, first_name, last_name, phone_val,
                                    specialty_val, matricula, professional.is_active, wh_json]
                await db.pool.execute("""
                    INSERT INTO professionals (
                        tenant_id, user_id, first_name, last_name, phone_number,
                        specialty, registration_id, is_active, working_hours, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, NOW(), NOW())
                """, *params_no_email)
            elif "specialty" in err_str:
                # BD sin columna specialty: INSERT sin especialidad
                params_no_spec = [tenant_id, user_id, first_name, last_name, email, phone_val,
                                  matricula, professional.is_active, wh_json]
                try:
                    await db.pool.execute("""
                        INSERT INTO professionals (
                            tenant_id, user_id, first_name, last_name, email, phone_number,
                            registration_id, is_active, working_hours, created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, NOW(), NOW())
                    """, *params_no_spec)
                except asyncpg.UndefinedColumnError as e2:
                    err2 = str(e2).lower()
                    if "phone_number" in err2:
                        params_no_spec_phone = [tenant_id, user_id, first_name, last_name, email,
                                                matricula, professional.is_active, wh_json]
                        await db.pool.execute("""
                            INSERT INTO professionals (
                                tenant_id, user_id, first_name, last_name, email,
                                registration_id, is_active, working_hours, created_at, updated_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, NOW(), NOW())
                        """, *params_no_spec_phone)
                    elif "updated_at" in err2:
                        await db.pool.execute("""
                            INSERT INTO professionals (
                                tenant_id, user_id, first_name, last_name, email, phone_number,
                                registration_id, is_active, working_hours, created_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, NOW())
                        """, *params_no_spec)
                    else:
                        raise
            else:
                logger.exception("create_professional INSERT column error")
                raise HTTPException(status_code=500, detail=f"Columna no reconocida en professionals: {e}")
        except asyncpg.UniqueViolationError as e:
            logger.warning(f"create_professional duplicate: {e}")
            raise HTTPException(status_code=409, detail="Ya existe un usuario o profesional con ese email o datos.")
        except asyncpg.ForeignKeyViolationError as e:
            logger.warning(f"create_professional FK: {e}")
            raise HTTPException(status_code=400, detail="La clínica elegida no existe. Creá una sede primero en Sedes (Clínicas).")

        return {"status": "created", "user_id": str(user_id)}
    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e).lower()
        if "unique" in err_msg or "duplicate" in err_msg:
            raise HTTPException(status_code=409, detail="Ya existe un usuario o profesional con ese email o datos.")
        if "foreign key" in err_msg or "violates foreign key" in err_msg or "tenant" in err_msg:
            raise HTTPException(status_code=400, detail="La clínica elegida no existe. Creá una sede primero en Sedes (Clínicas).")
        logger.exception("Error creating professional")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/professionals/{id}", dependencies=[Depends(verify_admin_token)], tags=["Profesionales"], summary="Actualizar datos de un profesional")
async def update_professional(
    id: int,
    payload: ProfessionalUpdate,
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
):
    """Actualizar datos de un profesional por su ID numérico."""
    try:
        # Verificar existencia Y ownership multi-tenant (Regla de Oro)
        prof_row = await db.pool.fetchrow("SELECT tenant_id FROM professionals WHERE id = $1", id)
        if not prof_row:
            raise HTTPException(status_code=404, detail="Profesional no encontrado")
        if prof_row['tenant_id'] not in allowed_ids:
            raise HTTPException(status_code=403, detail="No tienes acceso a esta sede")

        # Actualizar datos básicos, disponibilidad y google_calendar_id
        current_wh = payload.working_hours
        gcal_id = (payload.google_calendar_id or "").strip() or None
        if current_wh:
             sql_update = """
                UPDATE professionals SET
                    first_name = $1, specialty = $2, license_number = $3,
                    phone_number = $4, email = $5, is_active = $6,
                    availability = $7::jsonb, working_hours = $8::jsonb,
                    google_calendar_id = $9,
                    updated_at = NOW()
                WHERE id = $10
            """
             params = [payload.name, payload.specialty, payload.license_number, 
                      payload.phone, payload.email, payload.is_active, 
                      json.dumps(payload.availability), json.dumps(current_wh), gcal_id, id]
        else:
             sql_update = """
                UPDATE professionals SET
                    first_name = $1, specialty = $2, license_number = $3,
                    phone_number = $4, email = $5, is_active = $6,
                    availability = $7::jsonb,
                    google_calendar_id = $8,
                    updated_at = NOW()
                WHERE id = $9
            """
             params = [payload.name, payload.specialty, payload.license_number, 
                      payload.phone, payload.email, payload.is_active, 
                      json.dumps(payload.availability), gcal_id, id]

        try:
            await db.pool.execute(sql_update, *params)
        except asyncpg.UndefinedColumnError as e:
            err_str = str(e).lower()
            if "google_calendar_id" in err_str:
                # BD sin columna google_calendar_id: actualizar sin ella
                if current_wh:
                    await db.pool.execute("""
                        UPDATE professionals SET
                            first_name = $1, specialty = $2, license_number = $3,
                            phone_number = $4, email = $5, is_active = $6,
                            availability = $7::jsonb, working_hours = $8::jsonb,
                            updated_at = NOW()
                        WHERE id = $9
                    """, payload.name, payload.specialty, payload.license_number,
                         payload.phone, payload.email, payload.is_active,
                         json.dumps(payload.availability), json.dumps(current_wh), id)
                else:
                    await db.pool.execute("""
                        UPDATE professionals SET
                            first_name = $1, specialty = $2, license_number = $3,
                            phone_number = $4, email = $5, is_active = $6,
                            availability = $7::jsonb,
                            updated_at = NOW()
                        WHERE id = $8
                    """, payload.name, payload.specialty, payload.license_number,
                         payload.phone, payload.email, payload.is_active,
                         json.dumps(payload.availability), id)
            elif "phone_number" in err_str:
                # BD sin columna phone_number: actualizar sin ella
                if current_wh:
                    await db.pool.execute("""
                        UPDATE professionals SET
                            first_name = $1, specialty = $2, license_number = $3,
                            email = $4, is_active = $5,
                            availability = $6::jsonb, working_hours = $7::jsonb,
                            updated_at = NOW()
                        WHERE id = $8
                    """, payload.name, payload.specialty, payload.license_number,
                         payload.email, payload.is_active,
                         json.dumps(payload.availability), json.dumps(current_wh), id)
                else:
                    await db.pool.execute("""
                        UPDATE professionals SET
                            first_name = $1, specialty = $2, license_number = $3,
                            email = $4, is_active = $5,
                            availability = $6::jsonb,
                            updated_at = NOW()
                        WHERE id = $7
                    """, payload.name, payload.specialty, payload.license_number,
                         payload.email, payload.is_active,
                         json.dumps(payload.availability), id)
            else:
                raise
             
        return {"id": id, "status": "updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating professional {id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/patients/{id}", dependencies=[Depends(verify_admin_token)], tags=["Pacientes"], summary="Obtener detalle de un paciente específico")
async def get_patient(id: int, tenant_id: int = Depends(get_resolved_tenant_id)):
    """Obtener un paciente por ID. Aislado por tenant_id (Regla de Oro)."""
    row = await db.pool.fetchrow("""
        SELECT id, first_name, last_name, phone_number, email, insurance_provider as obra_social, dni, birth_date, created_at, status, notes
        FROM patients 
        WHERE id = $1 AND tenant_id = $2
    """, id, tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return dict(row)

@router.put("/patients/{id}", dependencies=[Depends(verify_admin_token)], tags=["Pacientes"], summary="Actualizar datos de un paciente")
async def update_patient(id: int, p: PatientCreate, tenant_id: int = Depends(get_resolved_tenant_id)):
    """Actualizar datos de un paciente. Aislado por tenant_id (Regla de Oro)."""
    try:
        result = await db.pool.execute("""
            UPDATE patients SET
                first_name = $1, last_name = $2, phone_number = $3, 
                email = $4, dni = $5, insurance_provider = $6,
                updated_at = NOW()
            WHERE id = $7 AND tenant_id = $8
        """, p.first_name, p.last_name, p.phone_number, p.email, p.dni, p.insurance, id, tenant_id)
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Paciente no encontrado")
        return {"id": id, "status": "updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating patient {id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/patients/{id}", dependencies=[Depends(verify_admin_token)], tags=["Pacientes"], summary="Eliminar (soft-delete) un paciente")
async def delete_patient(id: int, tenant_id: int = Depends(get_resolved_tenant_id)):
    """Marcar paciente como eliminado. Aislado por tenant_id (Regla de Oro)."""
    try:
        result = await db.pool.execute(
            "UPDATE patients SET status = 'deleted', updated_at = NOW() WHERE id = $1 AND tenant_id = $2",
            id, tenant_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Paciente no encontrado")
        return {"status": "deleted", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting patient {id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/patients/{id}/records", dependencies=[Depends(verify_admin_token)], tags=["Pacientes"], summary="Obtener historia clínica del paciente")
async def get_clinical_records(id: int, tenant_id: int = Depends(get_resolved_tenant_id)):
    """Obtener historia clínica de un paciente. Aislado por tenant_id (Regla de Oro)."""
    rows = await db.pool.fetch("""
        SELECT cr.id, cr.appointment_id, cr.diagnosis, cr.treatment_plan, cr.created_at 
        FROM clinical_records cr
        JOIN patients p ON cr.patient_id = p.id
        WHERE cr.patient_id = $1 AND p.tenant_id = $2
        ORDER BY cr.created_at DESC
    """, id, tenant_id)
    return [dict(row) for row in rows]

@router.post("/patients/{id}/records", dependencies=[Depends(verify_admin_token)], tags=["Pacientes"], summary="Agregar nota a la historia clínica")
async def add_clinical_note(id: int, note: ClinicalNote, tenant_id: int = Depends(get_resolved_tenant_id)):
    """Agregar una evolución/nota a la historia clínica. Aislado por tenant_id (Regla de Oro)."""
    patient = await db.pool.fetchrow("SELECT id FROM patients WHERE id = $1 AND tenant_id = $2", id, tenant_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    await db.pool.execute("""
        INSERT INTO clinical_records (id, tenant_id, patient_id, diagnosis, odontogram, created_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
    """, str(uuid.uuid4()), tenant_id, id, note.content, json.dumps(note.odontogram_data) if note.odontogram_data else '{}')
    return {"status": "ok"}

# ==================== ENDPOINTS TURNOS (AGENDA) ====================

@router.get("/appointments", dependencies=[Depends(verify_admin_token)], tags=["Turnos"], summary="Listar turnos en un rango de fechas")
async def list_appointments(
    start_date: str,
    end_date: str,
    professional_id: Optional[int] = None,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Obtener turnos del calendario. Aislado por tenant_id (Regla de Oro)."""
    query = """
        SELECT a.id, a.patient_id, a.appointment_datetime, a.duration_minutes, a.status, a.urgency_level,
               a.source, a.appointment_type, a.notes,
               (p.first_name || ' ' || COALESCE(p.last_name, '')) as patient_name, 
               p.phone_number as patient_phone,
               prof.first_name as professional_name, prof.id as professional_id
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        LEFT JOIN professionals prof ON a.professional_id = prof.id
        WHERE a.tenant_id = $1 AND a.appointment_datetime BETWEEN $2 AND $3
    """
    params = [tenant_id, datetime.fromisoformat(start_date), datetime.fromisoformat(end_date)]
    if professional_id:
        query += f" AND a.professional_id = ${len(params) + 1}"
        params.append(professional_id)
    query += " ORDER BY a.appointment_datetime ASC"
    rows = await db.pool.fetch(query, *params)
    return [dict(row) for row in rows]


# ==================== ENDPOINT COLISION DETECTION ====================

@router.get("/appointments/check-collisions", dependencies=[Depends(verify_admin_token)], tags=["Turnos"], summary="Verificar colisiones de horario para un turno")
async def check_collisions(
    professional_id: int,
    datetime_str: str,
    duration_minutes: int = 60,
    exclude_appointment_id: str = None,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Verificar colisiones de horario. Aislado por tenant_id (Regla de Oro)."""
    target_datetime = datetime.fromisoformat(datetime_str)
    target_end = target_datetime + timedelta(minutes=duration_minutes)
    overlap_query = """
        SELECT id, appointment_datetime, duration_minutes, status, source
        FROM appointments
        WHERE tenant_id = $1 AND professional_id = $2
        AND status NOT IN ('cancelled', 'no-show')
        AND appointment_datetime < $4
        AND appointment_datetime + (duration_minutes || ' minutes')::interval > $3
    """
    params = [tenant_id, professional_id, target_datetime, target_end]
    if exclude_appointment_id:
        overlap_query += " AND id != $5"
        params.append(exclude_appointment_id)
    overlapping = await db.pool.fetch(overlap_query, *params)
    gcal_blocks = await db.pool.fetch("""
        SELECT id, title, start_datetime, end_datetime
        FROM google_calendar_blocks
        WHERE tenant_id = $1 AND (professional_id = $2 OR professional_id IS NULL)
        AND start_datetime < $4
        AND end_datetime > $3
    """, tenant_id, professional_id, target_datetime, target_end)
    
    has_collisions = len(overlapping) > 0 or len(gcal_blocks) > 0
    
    return {
        "has_collisions": has_collisions,
        "conflicting_appointments": [dict(row) for row in overlapping],
        "conflicting_blocks": [dict(row) for row in gcal_blocks]
    }

@router.post("/appointments", dependencies=[Depends(verify_admin_token)], tags=["Turnos"], summary="Agendar un turno manualmente")
async def create_appointment_manual(
    apt: AppointmentCreate,
    request: Request,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Agendar turno manualmente. Aislado por tenant_id (Regla de Oro)."""
    try:
        if apt.check_collisions:
            collision_response = await check_collisions(
                apt.professional_id,
                apt.appointment_datetime.isoformat(),
                60,
                None,
                tenant_id=tenant_id,
            )
            if collision_response["has_collisions"]:
                conflicts = []
                for apt_conflict in collision_response["conflicting_appointments"]:
                    conflicts.append(f"Turno existente: {apt_conflict['appointment_datetime']}")
                for block in collision_response["conflicting_blocks"]:
                    conflicts.append(f"Bloqueo GCalendar: {block['title']} ({block['start_datetime']})")
                raise HTTPException(
                    status_code=409, 
                    detail=f"Hay colisiones de horario: {'; '.join(conflicts)}"
                )
        
        # 1. Validar que professional_id existe y pertenece al tenant
        prof_exists = await db.pool.fetchval(
            "SELECT id FROM professionals WHERE id = $1 AND tenant_id = $2 AND is_active = true",
            apt.professional_id, tenant_id,
        )
        if not prof_exists:
            raise HTTPException(status_code=400, detail="Profesional inválido o inactivo")
        
        # 2. Resolver patient_id (solo dentro del tenant)
        pid = apt.patient_id
        if not pid and apt.patient_phone:
            exist = await db.pool.fetchrow(
                "SELECT id FROM patients WHERE tenant_id = $1 AND phone_number = $2",
                tenant_id, apt.patient_phone,
            )
            if exist:
                pid = exist['id']
            else:
                new_p = await db.pool.fetchrow(
                    "INSERT INTO patients (tenant_id, phone_number, first_name, created_at) VALUES ($1, $2, $3, NOW()) RETURNING id",
                    tenant_id, apt.patient_phone, "Paciente Manual",
                )
                pid = new_p['id']
        if not pid:
            raise HTTPException(status_code=400, detail="Se requiere ID de paciente o teléfono válido.")
        patient_exists = await db.pool.fetchval("SELECT id FROM patients WHERE id = $1 AND tenant_id = $2", pid, tenant_id)
        if not patient_exists:
            raise HTTPException(status_code=400, detail="Paciente no encontrado")
        # 4. Crear turno (source='manual')
        new_id = str(uuid.uuid4())
        await db.pool.execute("""
            INSERT INTO appointments (
                id, tenant_id, patient_id, professional_id, appointment_datetime, 
                duration_minutes, appointment_type, status, urgency_level, source, created_at
            ) VALUES ($1, $2, $3, $4, $5, 60, $6, 'confirmed', 'normal', 'manual', NOW())
        """, new_id, tenant_id, pid, apt.professional_id, apt.appointment_datetime, apt.appointment_type)
        
        # 5. Obtener datos completos del turno para evento y GCal
        appointment_data = await db.pool.fetchrow("""
            SELECT a.id, a.patient_id, a.professional_id, a.appointment_datetime, 
                   a.appointment_type, a.status, a.urgency_level,
                   (p.first_name || ' ' || COALESCE(p.last_name, '')) as patient_name, 
                   p.phone_number as patient_phone,
                   p.first_name, p.last_name, -- Para el summary de GCal
                   prof.first_name as professional_name
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN professionals prof ON a.professional_id = prof.id
            WHERE a.id = $1
        """, new_id)

        # 6. Sincronizar con Google Calendar
        try:
            # Obtener google_calendar_id del profesional
            google_calendar_id = await db.pool.fetchval(
                "SELECT google_calendar_id FROM professionals WHERE id = $1", 
                apt.professional_id
            )
            
            if google_calendar_id and appointment_data:
                summary = f"Cita Dental: {appointment_data['first_name']} {appointment_data['last_name'] or ''} - {apt.appointment_type}"
                start_time = apt.appointment_datetime.isoformat()
                end_time = (apt.appointment_datetime + timedelta(minutes=60)).isoformat()
                
                gcal_event = gcal_service.create_event(
                    calendar_id=google_calendar_id,
                    summary=summary,
                    start_time=start_time,
                    end_time=end_time,
                    description=f"Paciente: {appointment_data['first_name']}\nTel: {appointment_data['patient_phone']}\nNotas: {apt.notes or ''}"
                )
                
                if gcal_event:
                    await db.pool.execute(
                        "UPDATE appointments SET google_calendar_event_id = $1, google_calendar_sync_status = 'synced' WHERE id = $2",
                        gcal_event['id'], new_id
                    )
        except Exception as ge:
            logger.warning(f"GCal sync failed for appointment {new_id}: {ge}")

        # 7. Emitir evento de Socket.IO para actualización en tiempo real (no fallar la respuesta si falla el emit)
        if appointment_data:
            try:
                await emit_appointment_event("NEW_APPOINTMENT", dict(appointment_data), request)
            except Exception as emit_err:
                logger.warning(f"Socket emit failed for NEW_APPOINTMENT {new_id}: {emit_err}")
        
        return {"id": new_id, "status": "confirmed", "patient_id": pid, "source": "manual"}
        
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(status_code=400, detail="ID de profesional o paciente no válido")
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Turno duplicado para ese horario")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando turno: {str(e)}")

@router.put("/appointments/{id}/status", dependencies=[Depends(verify_admin_token)], tags=["Turnos"], summary="Actualizar el estado de un turno (confirmed, cancelled, etc.)")
@router.patch("/appointments/{id}/status", dependencies=[Depends(verify_admin_token)], tags=["Turnos"], summary="Actualizar el estado de un turno (vía PATCH)")
async def update_appointment_status(
    id: str,
    payload: StatusUpdate,
    request: Request,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Cambiar estado: confirmed, cancelled, attended, no_show. Aislado por tenant_id (Regla de Oro)."""
    result = await db.pool.execute(
        "UPDATE appointments SET status = $1 WHERE id = $2 AND tenant_id = $3",
        payload.status, id, tenant_id
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Turno no encontrado o sin acceso")
    
    # Obtener datos actualizados del turno para emitir evento
    appointment_data = await db.pool.fetchrow("""
        SELECT a.id, a.patient_id, a.professional_id, a.appointment_datetime, 
               a.appointment_type, a.status, a.urgency_level,
               (p.first_name || ' ' || COALESCE(p.last_name, '')) as patient_name, 
               p.phone_number as patient_phone,
               prof.first_name as professional_name,
               a.google_calendar_event_id, a.google_calendar_sync_status
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN professionals prof ON a.professional_id = prof.id
        WHERE a.id = $1
    """, id)
    
    if appointment_data:
        # 1. Sincronizar cancelación con Google Calendar
        if payload.status == 'cancelled' and appointment_data['google_calendar_event_id']:
            try:
                # Need to fetch professional's calendar ID
                google_calendar_id = await db.pool.fetchval(
                    "SELECT google_calendar_id FROM professionals WHERE id = $1", 
                    appointment_data['professional_id']
                )
                
                if google_calendar_id:
                    gcal_service.delete_event(calendar_id=google_calendar_id, event_id=appointment_data['google_calendar_event_id'])
                    await db.pool.execute(
                        "UPDATE appointments SET google_calendar_sync_status = 'cancelled' WHERE id = $1",
                        id
                    )
            except Exception as ge:
                print(f"Error deleting GCal event: {ge}")

        # 2. Emitir evento según el nuevo estado
        if payload.status == 'cancelled':
            await emit_appointment_event("APPOINTMENT_DELETED", id, request)
        else:
            await emit_appointment_event("APPOINTMENT_UPDATED", dict(appointment_data), request)
    
    return {"status": "updated", "appointment_id": str(id), "new_status": payload.status}

@router.put("/appointments/{id}", dependencies=[Depends(verify_admin_token)], tags=["Turnos"], summary="Actualizar datos completos de un turno")
async def update_appointment(id: str, apt: AppointmentCreate, request: Request, tenant_id: int = Depends(get_resolved_tenant_id)):
    """Actualizar datos de un turno (fecha, profesional, tipo, notas)."""
    try:
        # 1. Obtener datos actuales (solo del tenant del usuario)
        old_apt = await db.pool.fetchrow("""
            SELECT id, professional_id, appointment_datetime, google_calendar_event_id, status
            FROM appointments WHERE id = $1 AND tenant_id = $2
        """, id, tenant_id)
        
        if not old_apt:
            raise HTTPException(status_code=404, detail="Turno no encontrado")

        # 2. Verificar colisiones si la fecha o el profesional cambiaron
        date_changed = old_apt['appointment_datetime'] != apt.appointment_datetime
        prof_changed = old_apt['professional_id'] != apt.professional_id
        
        if apt.check_collisions and (date_changed or prof_changed):
            collision_response = await check_collisions(
                apt.professional_id,
                apt.appointment_datetime.isoformat(),
                60,
                id,  # Excluir este mismo turno de la búsqueda de colisiones
                tenant_id=tenant_id,
            )
            if collision_response["has_collisions"]:
                raise HTTPException(status_code=409, detail="Hay colisiones de horario en la nueva fecha/profesional")

        # 3. Actualizar en Base de Datos (solo si pertenece al tenant)
        await db.pool.execute("""
            UPDATE appointments SET 
                patient_id = $1,
                professional_id = $2,
                appointment_datetime = $3,
                appointment_type = $4,
                notes = $5,
                updated_at = NOW()
            WHERE id = $6 AND tenant_id = $7
        """, apt.patient_id, apt.professional_id, apt.appointment_datetime, apt.appointment_type, apt.notes, id, tenant_id)

        # 4. Sincronizar con Google Calendar
        try:
            # Obtener datos completos para GCal
            appointment_data = await db.pool.fetchrow("""
                SELECT a.id, p.first_name, p.last_name, p.phone_number as patient_phone,
                       prof.first_name as professional_name, prof.google_calendar_id
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                JOIN professionals prof ON a.professional_id = prof.id
                WHERE a.id = $1
            """, id)

            if appointment_data:
                # Si cambió el profesional, hay que borrar el evento del calendario viejo y crear uno en el nuevo
                if prof_changed and old_apt['google_calendar_event_id']:
                    old_prof_gcal = await db.pool.fetchval("SELECT google_calendar_id FROM professionals WHERE id = $1", old_apt['professional_id'])
                    if old_prof_gcal:
                        gcal_service.delete_event(calendar_id=old_prof_gcal, event_id=old_apt['google_calendar_event_id'])
                    
                    # Crear nuevo evento en el nuevo calendario
                    if appointment_data['google_calendar_id']:
                        summary = f"Cita Dental: {appointment_data['first_name']} {appointment_data['last_name'] or ''} - {apt.appointment_type}"
                        new_gcal = gcal_service.create_event(
                            calendar_id=appointment_data['google_calendar_id'],
                            summary=summary,
                            start_time=apt.appointment_datetime.isoformat(),
                            end_time=(apt.appointment_datetime + timedelta(minutes=60)).isoformat(),
                            description=f"Paciente: {appointment_data['first_name']}\nTel: {appointment_data['patient_phone']}\nNotas: {apt.notes or ''}"
                        )
                        if new_gcal:
                            await db.pool.execute("UPDATE appointments SET google_calendar_event_id = $1 WHERE id = $2", new_gcal['id'], id)
                
                # Si no cambió el profesional pero sí la fecha u otros datos, intentar actualizar el evento existente
                elif old_apt['google_calendar_event_id'] and appointment_data['google_calendar_id']:
                    # Por ahora el gcal_service solo tiene create y delete, así que borramos y creamos
                    # TODO: Implementar update_event en gcal_service para mayor eficiencia
                    gcal_service.delete_event(calendar_id=appointment_data['google_calendar_id'], event_id=old_apt['google_calendar_event_id'])
                    summary = f"Cita Dental: {appointment_data['first_name']} {appointment_data['last_name'] or ''} - {apt.appointment_type}"
                    new_gcal = gcal_service.create_event(
                        calendar_id=appointment_data['google_calendar_id'],
                        summary=summary,
                        start_time=apt.appointment_datetime.isoformat(),
                        end_time=(apt.appointment_datetime + timedelta(minutes=60)).isoformat(),
                        description=f"Paciente: {appointment_data['first_name']}\nTel: {appointment_data['patient_phone']}\nNotas: {apt.notes or ''}"
                    )
                    if new_gcal:
                        await db.pool.execute("UPDATE appointments SET google_calendar_event_id = $1 WHERE id = $2", new_gcal['id'], id)

        except Exception as ge:
            logger.error(f"Error syncing GCal on update: {ge}")

        # 5. Emitir evento Socket.IO
        full_data = await db.pool.fetchrow("""
            SELECT a.id, a.patient_id, a.professional_id, a.appointment_datetime, 
                   a.appointment_type, a.status, a.urgency_level,
                   (p.first_name || ' ' || COALESCE(p.last_name, '')) as patient_name, 
                   p.phone_number as patient_phone, prof.first_name as professional_name
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN professionals prof ON a.professional_id = prof.id
            WHERE a.id = $1
        """, id)
        if full_data:
            await emit_appointment_event("APPOINTMENT_UPDATED", dict(full_data), request)

        return {"status": "updated", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating appointment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/appointments/{id}", dependencies=[Depends(verify_admin_token)], tags=["Turnos"], summary="Eliminar físicamente un turno de la agenda")
async def delete_appointment(id: str, request: Request, tenant_id: int = Depends(get_resolved_tenant_id)):
    """Eliminar turno físicamente de la base de datos y de GCal. Aislado por tenant_id (Regla de Oro)."""
    try:
        # 1. Obtener datos antes de borrar — verificar ownership
        apt = await db.pool.fetchrow("""
            SELECT google_calendar_event_id, professional_id
            FROM appointments WHERE id = $1 AND tenant_id = $2
        """, id, tenant_id)
        
        if not apt:
             raise HTTPException(status_code=404, detail="Turno no encontrado")
             
        # 2. Borrar de Google Calendar si existe
        if apt['google_calendar_event_id']:
            try:
                google_calendar_id = await db.pool.fetchval(
                    "SELECT google_calendar_id FROM professionals WHERE id = $1", 
                    apt['professional_id']
                )
                if google_calendar_id:
                    gcal_service.delete_event(calendar_id=google_calendar_id, event_id=apt['google_calendar_event_id'])
            except Exception as ge:
                logger.error(f"Error borrando de GCal: {ge}")

        # 3. Borrar de la base de datos — con doble verificación de tenant_id
        await db.pool.execute("DELETE FROM appointments WHERE id = $1 AND tenant_id = $2", id, tenant_id)
        
        # 4. Notificar a la UI
        await emit_appointment_event("APPOINTMENT_DELETED", id, request)
        
        return {"status": "deleted", "id": id}
    except Exception as e:
        logger.error(f"Error deleting appointment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ENDPOINTS SLOTS DISPONIBLES ====================

class NextSlotsResponse(BaseModel):
    slot_start: str
    slot_end: str
    duration_minutes: int
    professional_id: int
    professional_name: str

@router.get("/appointments/next-slots", response_model=List[NextSlotsResponse], dependencies=[Depends(verify_admin_token)], tags=["Turnos"], summary="Consultar próximos huecos disponibles para turnos")
async def get_next_available_slots(
    days_ahead: int = 3,
    slot_duration_minutes: int = 20,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Próximos huecos disponibles para urgencias. Aislado por tenant_id (Regla de Oro).
    """
    professionals = await db.pool.fetch("""
        SELECT id, first_name, last_name 
        FROM professionals 
        WHERE tenant_id = $1 AND is_active = true
    """, tenant_id)
    if not professionals:
        return []
    available_slots: List[Dict[str, Any]] = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for day_offset in range(days_ahead + 1):
        current_date = today + timedelta(days=day_offset)
        if current_date.weekday() >= 5:
            continue
        day_start = current_date.replace(hour=9, minute=0, second=0, microsecond=0)
        day_end = current_date.replace(hour=18, minute=0, second=0, microsecond=0)
        for prof in professionals:
            prof_id = prof['id']
            prof_name = f"{prof['first_name']} {prof.get('last_name', '')}".strip()
            appointments = await db.pool.fetch("""
                SELECT appointment_datetime, duration_minutes
                FROM appointments
                WHERE tenant_id = $1 AND professional_id = $2
                AND DATE(appointment_datetime) = $3
                AND status NOT IN ('cancelled', 'no-show')
                ORDER BY appointment_datetime ASC
            """, tenant_id, prof_id, current_date.date())
            gcal_blocks = await db.pool.fetch("""
                SELECT start_datetime, end_datetime
                FROM google_calendar_blocks
                WHERE tenant_id = $1 AND (professional_id = $2 OR professional_id IS NULL)
                AND DATE(start_datetime) = $3
                ORDER BY start_datetime ASC
            """, tenant_id, prof_id, current_date.date())
            
            # Crear lista de busy periods (turnos + bloques)
            busy_periods = []
            
            for apt in appointments:
                apt_start = apt['appointment_datetime']
                apt_end = apt_start + timedelta(minutes=apt.get('duration_minutes', 60))
                busy_periods.append((apt_start, apt_end))
            
            for block in gcal_blocks:
                busy_periods.append((block['start_datetime'], block['end_datetime']))
            
            # Ordenar por inicio
            busy_periods.sort(key=lambda x: x[0])
            
            # Encontrar gaps
            current_time = day_start
            
            for busy_start, busy_end in busy_periods:
                # Verificar gap antes del primer ocupado
                if current_time < busy_start:
                    gap_duration = int((busy_start - current_time).total_seconds() / 60)
                    if gap_duration >= slot_duration_minutes - 5:  # Allow 5 min tolerance
                        slot_start = current_time
                        slot_end = slot_start + timedelta(minutes=slot_duration_minutes)
                        available_slots.append({
                            "slot_start": slot_start.isoformat(),
                            "slot_end": slot_end.isoformat(),
                            "duration_minutes": slot_duration_minutes,
                            "professional_id": prof_id,
                            "professional_name": prof_name
                        })
                
                current_time = max(current_time, busy_end)
            
            # Verificar gap después del último ocupado hasta fin del día
            if current_time < day_end:
                gap_duration = int((day_end - current_time).total_seconds() / 60)
                if gap_duration >= slot_duration_minutes - 5:
                    slot_start = current_time
                    slot_end = slot_start + timedelta(minutes=slot_duration_minutes)
                    available_slots.append({
                        "slot_start": slot_start.isoformat(),
                        "slot_end": slot_end.isoformat(),
                        "duration_minutes": slot_duration_minutes,
                        "professional_id": prof_id,
                        "professional_name": prof_name
                    })
    
    # Ordenar por fecha y hora, tomar los primeros 5
    available_slots.sort(key=lambda x: x['slot_start'])
    return available_slots[:5]


# ==================== ENDPOINTS PROFESIONALES ====================

@router.get("/professionals", dependencies=[Depends(verify_admin_token)], tags=["Profesionales"], summary="Listar profesionales activos y aprobados")
async def list_professionals(
    resolved_tenant_id: int = Depends(get_resolved_tenant_id),
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
):
    """
    Lista profesionales aprobados y activos. CEO ve todos los de sus sedes; secretary/professional solo los de su clínica.
    Solo se incluyen profesionales cuyo usuario tiene status = 'active' (aprobados por el CEO).
    """
    # Solo listar profesionales dentales aprobados (u.role = 'professional' y u.status = 'active').
    base_join = "FROM professionals p INNER JOIN users u ON p.user_id = u.id AND u.role = 'professional' AND u.status = 'active'"
    # CEO (varias sedes): listar profesionales de todas las sedes permitidas
    if len(allowed_ids) > 1:
        try:
            rows = await db.pool.fetch(
                f"SELECT p.id, p.first_name, p.last_name, p.specialty, p.is_active, p.tenant_id {base_join} WHERE p.tenant_id = ANY($1::int[])",
                allowed_ids,
            )
            return [dict(row) for row in rows]
        except Exception as e:
            err_str = str(e).lower()
            if "last_name" in err_str or "tenant_id" in err_str:
                try:
                    rows = await db.pool.fetch(
                        f"SELECT p.id, p.first_name, p.specialty, p.is_active, p.tenant_id {base_join} WHERE p.tenant_id = ANY($1::int[])",
                        allowed_ids,
                    )
                    return [dict(r) | {"last_name": ""} for r in rows]
                except Exception:
                    pass
            try:
                rows = await db.pool.fetch(
                    "SELECT p.id, p.first_name, p.last_name, p.specialty, p.is_active FROM professionals p INNER JOIN users u ON p.user_id = u.id AND u.role = 'professional' AND u.status = 'active' WHERE p.tenant_id = ANY($1::int[])",
                    allowed_ids,
                )
                return [dict(row) for row in rows]
            except Exception:
                pass
        try:
            rows = await db.pool.fetch(
                "SELECT p.id, p.first_name, p.last_name, p.specialty, p.is_active FROM professionals p INNER JOIN users u ON p.user_id = u.id AND u.role = 'professional' AND u.status = 'active'"
            )
            return [dict(row) for row in rows]
        except Exception as e2:
            logger.warning(f"list_professionals CEO fallback failed: {e2}")
            return []

    tenant_id = resolved_tenant_id
    try:
        rows = await db.pool.fetch(
            f"SELECT p.id, p.first_name, p.last_name, p.specialty, p.is_active {base_join} WHERE p.tenant_id = $1",
            tenant_id,
        )
        return [dict(row) for row in rows]
    except Exception as e:
        logger.warning(f"list_professionals primary query failed: {e}")

    try:
        rows = await db.pool.fetch(
            "SELECT p.id, p.first_name, p.specialty, p.is_active FROM professionals p INNER JOIN users u ON p.user_id = u.id AND u.role = 'professional' AND u.status = 'active' WHERE p.tenant_id = $1",
            tenant_id,
        )
        return [dict(r) | {"last_name": ""} for r in rows]
    except Exception as e:
        logger.warning(f"list_professionals fallback (no last_name) failed: {e}")

    try:
        rows = await db.pool.fetch(
            "SELECT p.id, p.first_name, p.last_name, p.specialty, p.is_active FROM professionals p INNER JOIN users u ON p.user_id = u.id AND u.role = 'professional' AND u.status = 'active'"
        )
        return [dict(row) for row in rows]
    except Exception as e:
        logger.warning(f"list_professionals fallback (no tenant) failed: {e}")
    try:
        rows = await db.pool.fetch(
            "SELECT p.id, p.first_name, p.specialty, p.is_active FROM professionals p INNER JOIN users u ON p.user_id = u.id AND u.role = 'professional' AND u.status = 'active'"
        )
        return [dict(r) | {"last_name": ""} for r in rows]
    except Exception as e:
        logger.error(f"list_professionals all fallbacks failed: {e}", exc_info=True)
        return []


@router.get("/professionals/by-user/{user_id}", dependencies=[Depends(verify_admin_token)], tags=["Profesionales"], summary="Obtener sedes de un profesional por su user_id")
async def get_professionals_by_user(
    user_id: str,
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
):
    """
    Devuelve las filas de professionals asociadas a un usuario (por user_id).
    Usado por el modal de detalle al hacer clic en un miembro de Personal Activo.
    Solo se devuelven sedes a las que el requestor tiene acceso.
    """
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="user_id inválido")
    try:
        rows = await db.pool.fetch(
            """
            SELECT id, tenant_id, user_id, first_name, last_name, email, specialty,
                   is_active, working_hours, created_at, phone_number, registration_id, google_calendar_id
            FROM professionals
            WHERE user_id = $1 AND tenant_id = ANY($2::int[])
            ORDER BY tenant_id
            """,
            uid,
            allowed_ids,
        )
        return [dict(r) for r in rows]
    except Exception as e:
        err_str = str(e).lower()
        if "working_hours" in err_str or "tenant_id" in err_str or "phone_number" in err_str or "registration_id" in err_str or "google_calendar_id" in err_str:
            try:
                rows = await db.pool.fetch(
                    "SELECT id, tenant_id, user_id, first_name, last_name, email, specialty, is_active, working_hours, phone_number, registration_id FROM professionals WHERE user_id = $1 AND tenant_id = ANY($2::int[]) ORDER BY tenant_id",
                    uid,
                    allowed_ids,
                )
                return [dict(r) for r in rows]
            except Exception:
                pass
        try:
            rows = await db.pool.fetch(
                "SELECT id, first_name, last_name, email, specialty, is_active FROM professionals WHERE user_id = $1",
                uid,
            )
            return [dict(r) for r in rows]
        except Exception as e2:
            logger.warning(f"get_professionals_by_user failed: {e2}")
            return []


@router.get("/professionals/{id}/analytics", dependencies=[Depends(verify_admin_token)], tags=["Profesionales"], summary="Obtener analíticas detalladas de un profesional")
async def get_professional_analytics(
    id: int,
    tenant_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
):
    """
    Métricas de un solo profesional para un tenant y rango de fechas.
    Usado por el modal de datos del profesional (acordeón). Solo sedes permitidas.
    """
    if tenant_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta sede.")
    if not start_date or not end_date:
        today = datetime.now()
        start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if today.month == 12:
            end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    else:
        start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    result = await analytics_service.get_professional_summary(id, start, end, tenant_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Profesional no encontrado en esta sede.")
    return result


# ==================== ENDPOINTS GOOGLE CALENDAR ====================

@router.post("/calendar/connect-sovereign", dependencies=[Depends(verify_admin_token)], tags=["Calendario"], summary="Conectar calendario de Google vía Auth0 (Soberano)")
async def connect_sovereign_calendar(
    payload: ConnectSovereignPayload,
    user_data=Depends(verify_admin_token),
    resolved_tenant_id: int = Depends(get_resolved_tenant_id),
    allowed_ids: List[int] = Depends(get_allowed_tenant_ids),
):
    """
    Guarda el token de Auth0 cifrado (Fernet) en credentials para la clínica
    y cambia calendar_provider a 'google'. Preparación para integración Auth0.
    """
    tenant_id = payload.tenant_id if (payload.tenant_id is not None and payload.tenant_id in allowed_ids) else resolved_tenant_id
    if tenant_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta clínica.")
    encrypted = encrypt_value(payload.access_token)
    if not encrypted:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cifrado no configurado. Definí CREDENTIALS_FERNET_KEY en el entorno.",
        )
    try:
        existing = await db.pool.fetchrow(
            """
            SELECT id FROM credentials
            WHERE tenant_id = $1 AND category = 'google_calendar' AND name = 'access_token'
            LIMIT 1
            """,
            tenant_id,
        )
        if existing:
            await db.pool.execute(
                """
                UPDATE credentials SET value = $1
                WHERE tenant_id = $2 AND category = 'google_calendar' AND name = 'access_token'
                """,
                encrypted,
                tenant_id,
            )
        else:
            await db.pool.execute(
                """
                INSERT INTO credentials (name, value, category, scope, tenant_id, description)
                VALUES ('access_token', $1, 'google_calendar', 'tenant', $2, 'Auth0/Google Calendar token (encrypted)')
                """,
                encrypted,
                tenant_id,
            )
        await db.pool.execute(
            """
            UPDATE tenants
            SET config = COALESCE(config, '{}')::jsonb || jsonb_build_object('calendar_provider', 'google'),
                updated_at = NOW()
            WHERE id = $1
            """,
            tenant_id,
        )
        logger.info(f"Calendar connect-sovereign: tenant_id={tenant_id}, calendar_provider=google")
        return {"status": "connected", "tenant_id": tenant_id, "calendar_provider": "google"}
    except Exception as e:
        logger.error(f"connect-sovereign failed: {e}")
        raise HTTPException(status_code=500, detail="Error al guardar el token o actualizar la clínica.")


@router.get("/calendar/blocks", dependencies=[Depends(verify_admin_token)], tags=["Calendario"], summary="Listar bloqueos manuales o de GCalendar")
async def get_calendar_blocks(
    start_date: str,
    end_date: str,
    professional_id: Optional[int] = None,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Obtener bloques de calendario. Aislado por tenant_id (Regla de Oro)."""
    try:
        query = """
            SELECT id, google_event_id, title, description,
                   start_datetime, end_datetime, all_day,
                   professional_id, sync_status
            FROM google_calendar_blocks
            WHERE tenant_id = $1 AND start_datetime < $3 AND end_datetime > $2
        """
        params = [
            tenant_id,
            datetime.fromisoformat(start_date.replace('Z', '+00:00')),
            datetime.fromisoformat(end_date.replace('Z', '+00:00')),
        ]
        if professional_id:
            query += " AND professional_id = $4"
            params.append(professional_id)
        query += " ORDER BY start_datetime ASC"
        rows = await db.pool.fetch(query, *params)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching calendar blocks: {e}")
        return []


@router.post("/calendar/blocks", dependencies=[Depends(verify_admin_token)], tags=["Calendario"], summary="Crear un nuevo bloqueo en el calendario")
async def create_calendar_block(
    block: GCalendarBlockCreate,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Crear un bloque de calendario. Aislado por tenant_id (Regla de Oro)."""
    try:
        new_id = str(uuid.uuid4())
        await db.pool.execute("""
            INSERT INTO google_calendar_blocks (
                id, tenant_id, google_event_id, title, description,
                start_datetime, end_datetime, all_day, professional_id, sync_status, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'synced', NOW())
        """, new_id, tenant_id, block.google_event_id, block.title, block.description,
             block.start_datetime, block.end_datetime, block.all_day, block.professional_id)
        return {"id": new_id, "status": "created"}
    except Exception as e:
        return {"id": str(uuid.uuid4()), "status": "simulated", "message": str(e)}


@router.delete("/calendar/blocks/{block_id}", dependencies=[Depends(verify_admin_token)], tags=["Calendario"], summary="Eliminar un bloqueo del calendario")
async def delete_calendar_block(block_id: str, tenant_id: int = Depends(get_resolved_tenant_id)):
    """Eliminar un bloque de calendario. Aislado por tenant_id (Regla de Oro)."""
    await db.pool.execute("DELETE FROM google_calendar_blocks WHERE id = $1 AND tenant_id = $2", block_id, tenant_id)
    return {"status": "deleted"}


@router.post("/sync/calendar", dependencies=[Depends(verify_admin_token)], tags=["Calendario"], summary="Disparar sincronización manual de GCalendar (Alias)")
@router.post("/calendar/sync", dependencies=[Depends(verify_admin_token)], tags=["Calendario"], summary="Disparar sincronización manual de GCalendar")
async def trigger_sync(tenant_id: int = Depends(get_resolved_tenant_id)):
    """
    Sincronización con Google Calendar para profesionales activos del tenant.
    Aislado por tenant_id (Regla de Oro).
    """
    try:
        professionals = await db.pool.fetch("""
            SELECT id, first_name, google_calendar_id 
            FROM professionals 
            WHERE tenant_id = $1 AND is_active = true AND google_calendar_id IS NOT NULL
        """, tenant_id)

        if not professionals:
            return {"status": "warning", "message": "No hay profesionales con calendario configurado."}

        appointment_google_ids = await db.pool.fetch(
            "SELECT google_calendar_event_id FROM appointments WHERE tenant_id = $1 AND google_calendar_event_id IS NOT NULL",
            tenant_id,
        )
        apt_ids_set = {row['google_calendar_event_id'] for row in appointment_google_ids}

        total_created = 0
        total_updated = 0
        total_processed = 0
        
        # Sync from yesterday to ensure we catch today's earlier events
        time_min = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace('+00:00', 'Z')
        time_max = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat().replace('+00:00', 'Z')

        for prof in professionals:
            prof_id = prof['id']
            cal_id = prof['google_calendar_id']
            
            logger.info(f"🔄 Syncing GCal for {prof['first_name']} (ID: {prof_id}) on {cal_id}")
            logger.info(f"   Time Range: {time_min} to {time_max}")
            
            events = gcal_service.list_events(calendar_id=cal_id, time_min=time_min, time_max=time_max)
            logger.info(f"   Found {len(events)} events in GCal.")
            total_processed += len(events)
            
            # Obtener IDs ya existentes para este profesional
            existing_blocks = await db.pool.fetch("SELECT google_event_id FROM google_calendar_blocks WHERE professional_id = $1", prof_id)
            existing_ids_set = {row['google_event_id'] for row in existing_blocks}

            for event in events:
                g_id = event['id']
                summary = event.get('summary', 'Sin Título')
                
                # Ignorar si es un turno ya registrado
                if g_id in apt_ids_set:
                    logger.info(f"   Skipping event {g_id} ({summary}) - Already linked to appointment")
                    continue
                    
                description = event.get('description', '')
                start = event['start'].get('dateTime') or event['start'].get('date')
                end = event['end'].get('dateTime') or event['end'].get('date')
                all_day = 'date' in event['start']
                
                # Parsing dates with safety
                try:
                    dt_start = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    dt_end = datetime.fromisoformat(end.replace('Z', '+00:00'))
                except Exception as de:
                    logger.warning(f"   Error parsing date {start}/{end} for event {g_id}: {de}")
                    continue

                if g_id in existing_ids_set:
                    await db.pool.execute("""
                        UPDATE google_calendar_blocks SET
                            title = $1, description = $2, start_datetime = $3, end_datetime = $4,
                            all_day = $5, updated_at = NOW()
                        WHERE google_event_id = $6 AND professional_id = $7
                    """, summary, description, dt_start, dt_end, all_day, g_id, prof_id)
                    total_updated += 1
                else:
                    await db.pool.execute("""
                        INSERT INTO google_calendar_blocks (
                            tenant_id, google_event_id, title, description,
                            start_datetime, end_datetime, all_day, professional_id
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, tenant_id, g_id, summary, description, dt_start, dt_end, all_day, prof_id)
                    total_created += 1
        
        # Registrar sync global en log
        await db.pool.execute("""
            INSERT INTO calendar_sync_log (
                tenant_id, sync_type, direction, events_processed, 
                events_created, events_updated, completed_at
            ) VALUES ($1, 'manual', 'inbound', $2, $3, $4, NOW())
        """, tenant_id, total_processed, total_created, total_updated)
        
        return {
            "status": "success",
            "professionals_synced": len(professionals),
            "events_processed": total_processed,
            "created": total_created,
            "updated": total_updated,
            "message": f"Sincronización completada para {len(professionals)} profesionales."
        }
    except Exception as e:
        logger.error(f"Error en trigger_sync: {e}")
        return {
            "status": "error",
            "message": f"Error en sincronización: {str(e)}"
        }
# --- Función Helper de Entorno (Legacy support) ---
async def sync_environment():
    """Crea la clínica por defecto si no existe (startup main.py)."""
    exists = await db.pool.fetchval("SELECT id FROM tenants LIMIT 1")
    if not exists:
        await db.pool.execute("""
            INSERT INTO tenants (clinic_name, bot_phone_number, config)
            VALUES ('Clínica Dental', '5491100000000', '{"calendar_provider": "local"}'::jsonb)
        """)
# ==================== ENDPOINTS TRATAMIENTOS ====================

class TreatmentTypeUpdate(BaseModel):
    name: str
    description: Optional[str] = None
    default_duration_minutes: int
    min_duration_minutes: int
    max_duration_minutes: int
    complexity_level: str
    category: str
    requires_multiple_sessions: bool = False
    session_gap_days: int = 0
    is_active: bool = True
    is_available_for_booking: bool = True
    internal_notes: Optional[str] = None


@router.get("/treatment-types", dependencies=[Depends(verify_admin_token)], tags=["Tratamientos"], summary="Listar tipos de tratamientos ofrecidos")
async def list_treatment_types(tenant_id: int = Depends(get_resolved_tenant_id)):
    """Listar tipos de tratamiento de la clínica. Aislado por tenant_id (Regla de Oro)."""
    rows = await db.pool.fetch("""
        SELECT id, code, name, description, default_duration_minutes,
               min_duration_minutes, max_duration_minutes, complexity_level,
               category, requires_multiple_sessions, session_gap_days,
               is_active, is_available_for_booking, internal_notes
        FROM treatment_types
        WHERE tenant_id = $1
        ORDER BY category, name
    """, tenant_id)
    return [dict(row) for row in rows]


@router.get("/treatment-types/{code}", dependencies=[Depends(verify_admin_token)], tags=["Tratamientos"], summary="Obtener detalle de un tratamiento por su código")
async def get_treatment_type(code: str, tenant_id: int = Depends(get_resolved_tenant_id)):
    """Obtener un tipo de tratamiento. Aislado por tenant_id (Regla de Oro)."""
    row = await db.pool.fetchrow("""
        SELECT id, code, name, description, default_duration_minutes,
               min_duration_minutes, max_duration_minutes, complexity_level,
               category, requires_multiple_sessions, session_gap_days,
               is_active, is_available_for_booking, internal_notes
        FROM treatment_types
        WHERE tenant_id = $1 AND code = $2
    """, tenant_id, code)
    if not row:
        raise HTTPException(status_code=404, detail="Tipo de tratamiento no encontrado")
    return dict(row)


@router.post("/treatment-types", dependencies=[Depends(verify_admin_token)], tags=["Tratamientos"], summary="Crear un nuevo tipo de tratamiento")
async def create_treatment_type(treatment: TreatmentTypeCreate, tenant_id: int = Depends(get_resolved_tenant_id)):
    """Crear un nuevo tipo de tratamiento. Aislado por tenant_id (Regla de Oro)."""
    try:
        await db.pool.execute("""
            INSERT INTO treatment_types (
                tenant_id, code, name, description, default_duration_minutes,
                min_duration_minutes, max_duration_minutes, complexity_level,
                category, requires_multiple_sessions, session_gap_days,
                is_active, is_available_for_booking, internal_notes, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, NOW())
        """, tenant_id, treatment.code, treatment.name, treatment.description, treatment.default_duration_minutes,
            treatment.min_duration_minutes, treatment.max_duration_minutes,
            treatment.complexity_level, treatment.category, treatment.requires_multiple_sessions,
            treatment.session_gap_days, treatment.is_active, treatment.is_available_for_booking,
            treatment.internal_notes)
        return {"status": "created", "code": treatment.code}
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=400, detail=f"El código de tratamiento '{treatment.code}' ya existe.")
    except Exception as e:
        logger.error(f"Error creating treatment type: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/treatment-types/{code}", dependencies=[Depends(verify_admin_token)], tags=["Tratamientos"], summary="Actualizar datos de un tipo de tratamiento")
async def update_treatment_type(code: str, treatment: TreatmentTypeUpdate, tenant_id: int = Depends(get_resolved_tenant_id)):
    """Actualizar tipo de tratamiento. Aislado por tenant_id (Regla de Oro)."""
    result = await db.pool.execute("""
        UPDATE treatment_types SET
            name = $1, description = $2, default_duration_minutes = $3,
            min_duration_minutes = $4, max_duration_minutes = $5,
            complexity_level = $6, category = $7, requires_multiple_sessions = $8,
            session_gap_days = $9, is_active = $10, is_available_for_booking = $11,
            internal_notes = $12, updated_at = NOW()
        WHERE tenant_id = $13 AND code = $14
    """, treatment.name, treatment.description, treatment.default_duration_minutes,
        treatment.min_duration_minutes, treatment.max_duration_minutes,
        treatment.complexity_level, treatment.category, treatment.requires_multiple_sessions,
        treatment.session_gap_days, treatment.is_active, treatment.is_available_for_booking,
        treatment.internal_notes, tenant_id, code)
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Tipo de tratamiento no encontrado")
    return {"status": "updated", "code": code}


@router.delete("/treatment-types/{code}", dependencies=[Depends(verify_admin_token)], tags=["Tratamientos"], summary="Eliminar o desactivar un tipo de tratamiento")
async def delete_treatment_type(code: str, tenant_id: int = Depends(get_resolved_tenant_id)):
    """Eliminar o desactivar tipo de tratamiento. Aislado por tenant_id (Regla de Oro)."""
    has_appointments = await db.pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM appointments WHERE tenant_id = $1 AND appointment_type = $2)",
        tenant_id, code,
    )
    if has_appointments:
        await db.pool.execute(
            "UPDATE treatment_types SET is_active = false, is_available_for_booking = false WHERE tenant_id = $1 AND code = $2",
            tenant_id, code,
        )
        return {"status": "deactivated", "code": code, "message": "Tratamiento desactivado por tener citas asociadas."}
    result = await db.pool.execute("DELETE FROM treatment_types WHERE tenant_id = $1 AND code = $2", tenant_id, code)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Tipo de tratamiento no encontrado")
    return {"status": "deleted", "code": code}


@router.get("/treatment-types/{code}/duration", dependencies=[Depends(verify_admin_token)], tags=["Tratamientos"], summary="Obtener duración estimada según nivel de urgencia")
async def get_treatment_duration(code: str, urgency_level: str = "normal", tenant_id: int = Depends(get_resolved_tenant_id)):
    """
    Obtener duración calculada para un tratamiento según urgencia.
    
    Args:
        code: Código del tratamiento (ej: 'root_canal', 'cleaning')
        urgency_level: 'low', 'normal', 'high', 'emergency'
    
    Returns:
        duration_minutes: Duración calculada en minutos
    """
    row = await db.pool.fetchrow("""
        SELECT default_duration_minutes, min_duration_minutes, max_duration_minutes
        FROM treatment_types
        WHERE tenant_id = $1 AND code = $2 AND is_active = TRUE AND is_available_for_booking = TRUE
    """, tenant_id, code)
    
    if not row:
        # Return default duration if treatment not found
        return {"duration_minutes": 30, "source": "default"}
    
    default_duration = row['default_duration_minutes']
    min_duration = row['min_duration_minutes']
    max_duration = row['max_duration_minutes']
    
    # Calculate duration based on urgency
    if urgency_level == 'emergency':
        calculated_duration = min(min_duration, default_duration)
    elif urgency_level == 'high':
        calculated_duration = default_duration
    elif urgency_level == 'normal':
        calculated_duration = default_duration
    else:  # low
        calculated_duration = max(default_duration, max_duration)
    
    return {
        "duration_minutes": calculated_duration,
        "source": "calculated",
        "treatment_code": code,
        "urgency_level": urgency_level,
        "details": {
            "default": default_duration,
            "min": min_duration,
            "max": max_duration
        }
    }


# Analytics endpoints already handle below

# ==================== ENDPOINTS ANALYTICS ====================

@router.get("/analytics/professionals/summary", tags=["Analítica"], summary="Obtener reporte analítico de profesionales para el CEO")
async def get_professionals_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Retorna métricas estratégicas de los profesionales para el dashboard del CEO.
    """
    try:
        # Default to current month if not specified
        if not start_date or not end_date:
            today = datetime.now()
            start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # End of month roughly
            if today.month == 12:
                 end = today.replace(year=today.year+1, month=1, day=1) - timedelta(days=1)
            else:
                 end = today.replace(month=today.month+1, day=1) - timedelta(days=1)
        else:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
            
        data = await analytics_service.get_professionals_summary(start, end, tenant_id=tenant_id)
        return data
        
    except Exception as e:
        logger.error(f"Error in analytics endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== END OF ANALYTICS ====================



# =============================================
# Spec 12: HEALTH CHECK — INTEGRACIONES
# =============================================

@router.get("/health/integrations", tags=["Mantenimiento"], summary="Health-Check de integraciones externas (Facebook/Meta Ads)")
async def health_check_integrations(
    user_data=Depends(verify_admin_token),
):
    """
    Spec 12: Verifica el estado de las integraciones externas (Meta Ads).
    Retorna status de conexión, validez de token y cuentas activas.
    """
    if user_data.role not in ['ceo', 'secretary']:
        raise HTTPException(status_code=403, detail="Solo administradores pueden ver estado de integraciones.")

    from scripts.check_meta_health import check_meta_health
    result = await check_meta_health()

    status_code = 200 if result.get("status") == "ok" else 503
    return JSONResponse(content=result, status_code=status_code)

@router.get("/marketing/automation-logs", tags=["Marketing Analytics"], summary="Consultar logs de automatización de marketing")
async def get_automation_logs(
    limit: int = Query(50, ge=1, le=200),
    resolved_tenant_id: int = Depends(get_resolved_tenant_id),
    user_data=Depends(verify_admin_token),
):
    """
    Spec 08: Auditoría de logs de automatización (UI Transparente).
    Muestra el historial de recordatorios y seguimientos enviados.
    """
    if user_data.role not in ['ceo', 'secretary']:
        raise HTTPException(status_code=403, detail="Acceso denegado.")

    try:
        rows = await db.pool.fetch("""
            SELECT l.id, l.patient_id, p.first_name || ' ' || COALESCE(p.last_name, '') as patient_name,
                   l.trigger_type, l.status, l.created_at, l.error_details, l.meta
            FROM automation_logs l
            JOIN patients p ON l.patient_id = p.id
            WHERE l.tenant_id = $1
            ORDER BY l.created_at DESC
            LIMIT $2
        """, resolved_tenant_id, limit)

        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error fetching automation logs: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo logs de automatización.")
