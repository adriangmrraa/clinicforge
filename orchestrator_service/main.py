import os
import json
import logging
import asyncio
import uuid
from datetime import datetime, timedelta, date, timezone
from typing import List, Optional, Dict, Any
from contextvars import ContextVar
from contextlib import asynccontextmanager
from dateutil.parser import parse as dateutil_parse
import re
from gcal_service import gcal_service
import httpx
import mimetypes
from urllib.parse import urlparse

from fastapi import BackgroundTasks, FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text

from langchain_openai import ChatOpenAI
# Busca la línea que falla y reemplázala por estas:
from langchain.agents import AgentExecutor
from langchain.agents import create_openai_tools_agent

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain.tools import tool

import socketio
from db import db
from admin_routes import router as admin_router
from auth_routes import router as auth_router
from routes import chat_webhooks, chat_api
from email_service import email_service
from services.automation_service import automation_service

# --- CONFIGURACIÓN ---
import logging
logger = logging.getLogger("orchestrator")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
from core.log_sanitizer import install_log_sanitizer  # noqa: E402
install_log_sanitizer()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "")
CLINIC_NAME = os.getenv("CLINIC_NAME", "Consultorio Dental")
CLINIC_LOCATION = os.getenv("CLINIC_LOCATION", "Buenos Aires, Argentina")
CLINIC_HOURS_START = os.getenv("CLINIC_HOURS_START", "08:00")
CLINIC_HOURS_END = os.getenv("CLINIC_HOURS_END", "19:00")
ARG_TZ = timezone(timedelta(hours=-3))

def get_now_arg():
    """Obtiene la fecha y hora actual garantizando zona horaria de Argentina."""
    return datetime.now(ARG_TZ)

# download_media moved to services.media_downloader
from services.media_downloader import download_media

def normalize_whatsapp_attachments(media_items: list) -> list:
    """
    Normaliza attachments de WhatsApp a estructura estándar (Spec 20).
    Compatible con estructura de Chatwoot.
    
    Args:
        media_items: Lista de items de media del payload de YCloud/WhatsApp
    
    Returns:
        Lista normalizada con estructura: {type, url, file_name, file_size, mime_type, transcription}
    """
    if not media_items:
        return []
    
    normalized = []
    
    for item in media_items:
        media_type = (item.get("type") or "file").lower()
        
        # Normalización de tipos
        if media_type in ["voice", "ptt"]:
            media_type = "audio"
        elif media_type == "document":
            media_type = "file"
        elif media_type in ["picture", "photo"]:
            media_type = "image"
        
        normalized.append({
            "type": media_type,
            "url": item.get("url", ""),
            "file_name": item.get("file_name") or item.get("filename") or "attachment",
            "file_size": item.get("file_size") or item.get("size"),
            "mime_type": item.get("mime_type") or item.get("mimeType"),
            "provider_id": item.get("provider_id"),  # Para referencia
            "transcription": item.get("transcription")  # Para audios
        })
    
    return normalized

# ContextVars para rastrear el usuario en la sesión de LangChain
current_customer_phone: ContextVar[Optional[str]] = ContextVar("current_customer_phone", default=None)
current_patient_id: ContextVar[Optional[int]] = ContextVar("current_patient_id", default=None)
current_tenant_id: ContextVar[int] = ContextVar("current_tenant_id", default=1)

# --- DATABASE SETUP ---
# Normalize DSN for SQLAlchemy: must be postgresql+asyncpg://
_sa_dsn = POSTGRES_DSN
if _sa_dsn.startswith("postgres://"):
    _sa_dsn = _sa_dsn.replace("postgres://", "postgresql+asyncpg://", 1)
elif _sa_dsn.startswith("postgresql://"):
    _sa_dsn = _sa_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
elif not _sa_dsn.startswith("postgresql+asyncpg://"):
    _sa_dsn = "postgresql+asyncpg://" + _sa_dsn.split("://", 1)[-1] if "://" in _sa_dsn else _sa_dsn
engine = create_async_engine(_sa_dsn, echo=False) if _sa_dsn else None
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# --- MODELOS DE DATOS (API) ---
class ChatRequest(BaseModel):
    # Support both internal naming and WhatsApp service naming
    message: Optional[str] = None
    text: Optional[str] = None
    phone: Optional[str] = None
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    name: Optional[str] = "Paciente"
    customer_name: Optional[str] = None
    media: List[Dict[str, Any]] = Field(default_factory=list)
    # Deduplicación: si el WhatsApp service envía provider_message_id (wamid/event_id), evitamos procesar el mismo mensaje dos veces
    provider: Optional[str] = None
    event_id: Optional[str] = None
    provider_message_id: Optional[str] = None
    referral: Optional[Dict[str, Any]] = None # Meta Ads Referral Data
    role: Optional[str] = "user" # 'user' or 'assistant' (for echoes)

    @property
    def final_message(self) -> str:
        return self.message or self.text or ""

    @property
    def final_phone(self) -> str:
        phone = self.phone or self.from_number or ""
        # Normalización E.164 básica para consistencia en BD (con +)
        clean = re.sub(r'\D', '', phone)
        if clean and not phone.startswith('+'):
            return '+' + clean
        return phone # Si ya tiene + o está vacío
    
    @property
    def final_name(self) -> str:
        return self.customer_name or self.name or "Paciente"

def to_json_safe(obj: Any) -> Any:
    """Helper para serializar objetos datetime/date para JSON/SocketIO."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj

# --- HELPERS PARA PARSING DE FECHAS ---

def get_next_weekday(target_weekday: int) -> date:
    """Obtiene el próximo día de la semana (0=lunes, 6=domingo)."""
    today = get_now_arg()
    days_ahead = target_weekday - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (today + timedelta(days=days_ahead)).date()

def parse_date(date_query: str) -> date:
    """Convierte 'mañana', 'lunes', '2025-02-05' a date."""
    query = date_query.lower().strip()
    
    # Palabras clave españolas/inglesas
    today = get_now_arg().date()
    day_map = {
        'mañana': lambda: (get_now_arg() + timedelta(days=1)).date(),
        'tomorrow': lambda: (get_now_arg() + timedelta(days=1)).date(),
        'pasado mañana': lambda: (get_now_arg() + timedelta(days=2)).date(),
        'day after tomorrow': lambda: (get_now_arg() + timedelta(days=2)).date(),
        'hoy': lambda: today,
        'today': lambda: today,
        'lunes': lambda: get_next_weekday(0),
        'monday': lambda: get_next_weekday(0),
        'martes': lambda: get_next_weekday(1),
        'tuesday': lambda: get_next_weekday(1),
        'miércoles': lambda: get_next_weekday(2),
        'miercoles': lambda: get_next_weekday(2),
        'wednesday': lambda: get_next_weekday(2),
        'jueves': lambda: get_next_weekday(3),
        'thursday': lambda: get_next_weekday(3),
        'viernes': lambda: get_next_weekday(4),
        'friday': lambda: get_next_weekday(4),
        'sábado': lambda: get_next_weekday(5),
        'sabado': lambda: get_next_weekday(5),
        'saturday': lambda: get_next_weekday(5),
        'domingo': lambda: get_next_weekday(6),
        'sunday': lambda: get_next_weekday(6),
    }
    
    # Frases de dos palabras primero (ej. "pasado mañana")
    if "pasado mañana" in query or "day after tomorrow" in query:
        return (get_now_arg() + timedelta(days=2)).date()
    for key, func in day_map.items():
        if key in query:
            return func()
    
    # Intentar parsear como fecha
    try:
        return dateutil_parse(query, dayfirst=True).date()
    except:
        return get_now_arg().date()

def parse_datetime(datetime_query: str) -> datetime:
    """Convierte 'lunes 15:30', 'mañana 14:00', '2025-02-05 14:30' a datetime localizado."""
    query = datetime_query.lower().strip()
    target_date = None
    target_time = (14, 0) # Default

    # 1. Extraer hora (HH:MM, HH:00, o "17 hs" / "17h")
    time_match = re.search(r'(\d{1,2})[:h](\d{2})', query)
    if time_match:
        target_time = (int(time_match.group(1)), int(time_match.group(2)))
    else:
        # "17 hs", "a las 17", "17 horas", "5 pm", "10 am" -> 17:00, 17:00, 10:00
        hour_only = re.search(r'(?:las?\s+)?(\d{1,2})\s*(?:hs?|horas?)?\b', query)
        if hour_only:
            h = int(hour_only.group(1))
            if 0 <= h <= 23:
                target_time = (h, 0)
        # Formato 12h: "5 pm", "5pm", "10 am" (12 am = medianoche, 12 pm = mediodía)
        pm_am = re.search(r'(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)', query, re.IGNORECASE)
        if pm_am:
            h = int(pm_am.group(1))
            is_pm = 'p' in pm_am.group(2).lower()
            if h == 12:
                target_time = (0, 0) if not is_pm else (12, 0)
            elif is_pm:
                target_time = (h + 12, 0)
            else:
                target_time = (h, 0)
    
    # 2. Extraer fecha (usando la lógica de parse_date)
    # Buscamos palabras clave o fechas en la query
    words = query.split()
    for word in words:
        try:
            # Intentamos parsear la palabra individualmente como fecha (mañana, lunes, etc)
            d = parse_date(word)
            # Si no es hoy, o si la query explícitamente dice 'hoy', lo tomamos
            if d != get_now_arg().date() or 'hoy' in query or 'today' in query:
                target_date = d
                break
        except:
            continue

    # 3. Fallback a dateutil para formatos estándar (YYYY-MM-DD)
    if not target_date:
        try:
            dt = dateutil_parse(query, dayfirst=True)
            if dt.year > 2000: # Evitar años raros
                target_date = dt.date()
                if not time_match: target_time = (dt.hour, dt.minute)
        except:
            target_date = (get_now_arg() + timedelta(days=1)).date()

    return datetime.combine(target_date, datetime.min.time()).replace(
        hour=target_time[0], minute=target_time[1], second=0, microsecond=0, tzinfo=ARG_TZ
    )

def to_json_safe(data):
    """
    Convierte recursivamente UUIDs y datetimes a tipos serializables por JSON.
    """
    if isinstance(data, dict):
        return {k: to_json_safe(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [to_json_safe(i) for i in data]
    elif isinstance(data, uuid.UUID):
        return str(data)
    elif isinstance(data, (datetime, date)):
        return data.isoformat()
    return data

def is_time_in_working_hours(time_str: str, day_config: Dict[str, Any]) -> bool:
    """Verifica si un HH:MM está dentro de los slots habilitados del día."""
    if not day_config.get("enabled", False):
        return False
    
    # Normalizar time_str a minutos desde medianoche para comparación fácil
    try:
        th, tm = map(int, time_str.split(':'))
        current_m = th * 60 + tm
        
        for slot in day_config.get("slots", []):
            sh, sm = map(int, slot['start'].split(':'))
            eh, em = map(int, slot['end'].split(':'))
            start_m = sh * 60 + sm
            end_m = eh * 60 + em
            
            if start_m <= current_m < end_m:
                return True
    except:
        pass
    return False

def generate_free_slots(target_date: date, busy_intervals_by_prof: Dict[int, set], 
                        start_time_str="09:00", end_time_str="18:00", interval_minutes=30, 
                        duration_minutes=30, limit=20, time_preference: Optional[str] = None) -> List[str]:
    """Genera lista de horarios disponibles (si al menos un profesional tiene el hueco completo)."""
    slots = []
    
    # Parse start and end times
    try:
        sh, sm = map(int, start_time_str.split(':'))
        eh, em = map(int, end_time_str.split(':'))
    except:
        sh, sm = 9, 0
        eh, em = 18, 0

    current = datetime.combine(target_date, datetime.min.time()).replace(hour=sh, minute=sm, tzinfo=ARG_TZ)
    end_limit = datetime.combine(target_date, datetime.min.time()).replace(hour=eh, minute=em, tzinfo=ARG_TZ)
    
    now = get_now_arg()
    
    # Un horario está libre si AL MENOS UN profesional está libre durante toda la duración solicitada
    while current < end_limit:
        # No ofrecer turnos en el pasado (si es hoy)
        if target_date == now.date() and current <= now:
            current += timedelta(minutes=interval_minutes)
            continue

        # Filtro por preferencia de horario
        if time_preference == 'mañana' and current.hour >= 13:
            current += timedelta(minutes=interval_minutes)
            continue
        if time_preference == 'tarde' and current.hour < 13:
            current += timedelta(minutes=interval_minutes)
            continue

        # Saltar almuerzo (opcional)
        if current.hour >= 13 and current.hour < 14 and not time_preference:
            current += timedelta(minutes=interval_minutes)
            continue
        
        # Verificar si algún profesional tiene el hueco libre
        time_needed = current + timedelta(minutes=duration_minutes)
        if time_needed > end_limit: # No cabe al final del día
            current += timedelta(minutes=interval_minutes)
            continue

        any_prof_free = False
        for prof_id, busy_set in busy_intervals_by_prof.items():
            slot_free = True
            # Revisar cada intervalo de 30 min dentro de la duración
            check_time = current
            while check_time < time_needed:
                if check_time.strftime("%H:%M") in busy_set:
                    slot_free = False
                    break
                check_time += timedelta(minutes=30)
            
            if slot_free:
                any_prof_free = True
                break
        
        if any_prof_free:
            slots.append(current.strftime("%H:%M"))
        
        if len(slots) >= limit:
            break

        current += timedelta(minutes=interval_minutes)
    
    return slots


def slots_to_ranges(slots: List[str], interval_minutes: int = 30) -> str:
    """
    Convierte una lista de horarios (ej. 09:00, 09:30, 10:00...) en rangos legibles.
    Ej: ["09:00","09:30","10:00","14:00","14:30"] -> "de 09:00 a 10:30 y de 14:00 a 15:00"
    Así la respuesta parece más humana (no listar cada media hora).
    """
    if not slots:
        return ""
    try:
        def to_minutes(hhmm: str) -> int:
            h, m = map(int, hhmm.split(":"))
            return h * 60 + m
        def to_hhmm(m: int) -> str:
            h, m = divmod(m, 60)
            return f"{h:02d}:{m:02d}"
        minutes_list = sorted(set(to_minutes(s) for s in slots))
        ranges = []
        i = 0
        while i < len(minutes_list):
            start = minutes_list[i]
            end = start + interval_minutes
            while i + 1 < len(minutes_list) and minutes_list[i + 1] == end:
                i += 1
                end = minutes_list[i] + interval_minutes
            ranges.append((to_hhmm(start), to_hhmm(end)))
            i += 1
        if not ranges:
            return ""
        if len(ranges) == 1:
            return f"de {ranges[0][0]} a {ranges[0][1]}"
        return " y ".join(f"de {a} a {b}" for a, b in ranges)
    except Exception:
        return ", ".join(slots)


# --- CEREBRO HÍBRIDO: calendar_provider por clínica ---
async def get_tenant_calendar_provider(tenant_id: int) -> str:
    """
    Devuelve 'google' o 'local' según tenant.config.calendar_provider.
    Aislamiento: cada clínica decide si usa Google Calendar o solo BD local.
    """
    row = await db.pool.fetchrow(
        "SELECT config FROM tenants WHERE id = $1",
        tenant_id,
    )
    if not row or row.get("config") is None:
        return "local"
    cfg = row["config"]
    if isinstance(cfg, dict):
        cp = (cfg.get("calendar_provider") or "local").lower()
    elif isinstance(cfg, str):
        try:
            cfg = json.loads(cfg)
            cp = (cfg.get("calendar_provider") if isinstance(cfg, dict) else "local") or "local"
            cp = str(cp).lower()
        except Exception:
            cp = "local"
    else:
        cp = "local"
    return cp if cp in ("google", "local") else "local"


# --- TOOLS DENTALES ---

@tool
async def check_availability(date_query: str, professional_name: Optional[str] = None, 
                             treatment_name: Optional[str] = None, time_preference: Optional[str] = None):
    """
    Consulta la disponibilidad REAL de turnos para una fecha. Llamar UNA sola vez por pregunta del paciente.
    date_query: Día a consultar: 'mañana', 'lunes', 'martes', 'jueves', etc. Si dice "miércoles a la tarde" usar date_query='miércoles' y time_preference='tarde'.
    professional_name: (Opcional) Nombre del profesional (uno de list_professionals).
    treatment_name: (Opcional) Tratamiento ya definido (ej. limpieza profunda, consulta).
    time_preference: OBLIGATORIO cuando el paciente pide horarios de un momento del día: si pide 'a la tarde', 'por la tarde', 'tarde' -> 'tarde'; si pide 'a la mañana', 'por la mañana', 'mañana' (en sentido horario) -> 'mañana'; si no especifica -> 'todo' o no pasar.
    La tool devuelve rangos (ej. "de 09:00 a 12:00 y de 14:00 a 17:00"). Responde al paciente UNA sola vez con ese texto; no repitas ni des variaciones.
    """
    try:
        tid = current_tenant_id.get()
        logger.info(f"📅 check_availability date_query={date_query!r} tenant_id={tid} treatment={treatment_name!r} prof={professional_name!r}")
        # 0. A) Limpiar nombre y obtener profesionales activos
        clean_name = professional_name
        if professional_name:
            # Remover títulos comunes y normalizar
            clean_name = re.sub(r'^(dr|dra|doctor|doctora)\.?\s+', '', professional_name, flags=re.IGNORECASE).strip()
        
        tenant_id = current_tenant_id.get()
        # Solo profesionales aprobados (users.status = 'active') y activos en la sede
        query = """SELECT p.id, p.first_name, p.last_name, p.google_calendar_id, p.working_hours
                   FROM professionals p
                   INNER JOIN users u ON p.user_id = u.id AND u.role = 'professional' AND u.status = 'active'
                   WHERE p.is_active = true AND p.tenant_id = $1"""
        params = [tenant_id]
        if clean_name:
            query += " AND (p.first_name ILIKE $2 OR p.last_name ILIKE $2 OR (p.first_name || ' ' || COALESCE(p.last_name, '')) ILIKE $2)"
            params.append(f"%{clean_name}%")
        
        active_professionals = await db.pool.fetch(query, *params)
        if not active_professionals and professional_name:
            return f"❌ No encontré al profesional '{professional_name}'. ¿Querés consultar disponibilidad general?"
        if not active_professionals:
            return "❌ No hay profesionales activos en esta sede para consultar disponibilidad. Por favor contactá a la clínica."

        target_date = parse_date(date_query)
        
        # 0. B) Validar contra Working Hours antes de GCal (Primer Filtro)
        # Usamos número de día (0=Monday, 6=Sunday) para evitar problemas de locale
        day_idx = target_date.weekday()
        days_en = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_name_en = days_en[day_idx]
        
        # Si se pidió un profesional específico, verificar si atiende ese día
        if clean_name and active_professionals:
            prof = active_professionals[0]
            wh = prof.get('working_hours')
            if isinstance(wh, str):
                try:
                    wh = json.loads(wh) if wh else {}
                except Exception:
                    wh = {}
            if not isinstance(wh, dict):
                wh = {}
            day_config = wh.get(day_name_en, {"enabled": False, "slots": []})
            
            if not day_config.get("enabled"):
                return f"Lo siento, el/la Dr/a. {prof['first_name']} no atiende los {target_date.strftime('%A')}. ¿Querés que busquemos disponibilidad con otros profesionales?"

        if day_idx == 6:
            return f"Lo siento, el {date_query} es domingo y la clínica está cerrada. Atendemos Lunes a Sábados."

        # 0. B) Obtener duración del tratamiento (solo los cargados en Tratamientos)
        duration = 30  # Default cuando no se especifica tratamiento
        if treatment_name:
            t_data = await db.pool.fetchrow("""
                SELECT default_duration_minutes FROM treatment_types
                WHERE tenant_id = $1 AND (name ILIKE $2 OR code ILIKE $2) AND is_active = true AND is_available_for_booking = true
                LIMIT 1
            """, tenant_id, f"%{treatment_name}%")
            if not t_data:
                return "❌ Ese tratamiento no está en la lista de servicios de esta clínica. Los horarios solo se pueden consultar para tratamientos que devuelve 'list_services'. Llamá a list_services y usá solo uno de esos nombres para consultar disponibilidad."
            duration = t_data['default_duration_minutes']

        # --- CEREBRO HÍBRIDO: google → gcal_service; local → solo tabla appointments ---
        calendar_provider = await get_tenant_calendar_provider(tenant_id)
        if calendar_provider == "google":
            existing_apt_gids = await db.pool.fetch(
                "SELECT google_calendar_event_id FROM appointments WHERE google_calendar_event_id IS NOT NULL AND tenant_id = $1",
                tenant_id,
            )
            apt_gids_set = {row["google_calendar_event_id"] for row in existing_apt_gids}
            for prof in active_professionals:
                prof_id = prof["id"]
                cal_id = prof.get("google_calendar_id")
                if not cal_id:
                    continue
                try:
                    g_events = gcal_service.get_events_for_day(calendar_id=cal_id, date_obj=target_date)
                    start_day = datetime.combine(target_date, datetime.min.time(), tzinfo=ARG_TZ)
                    end_day = datetime.combine(target_date, datetime.max.time(), tzinfo=ARG_TZ)
                    await db.pool.execute("""
                        DELETE FROM google_calendar_blocks
                        WHERE professional_id = $1 AND (start_datetime < $3 AND end_datetime > $2) AND tenant_id = $4
                    """, prof_id, start_day, end_day, tenant_id)
                    for event in g_events:
                        g_id = event["id"]
                        if g_id in apt_gids_set:
                            continue
                        summary = event.get("summary", "Ocupado (GCal)")
                        description = event.get("description", "")
                        start = event["start"].get("dateTime") or event["start"].get("date")
                        end = event["end"].get("dateTime") or event["end"].get("date")
                        all_day = "date" in event["start"]
                        try:
                            dt_start = datetime.fromisoformat(start.replace("Z", "+00:00"))
                            dt_end = datetime.fromisoformat(end.replace("Z", "+00:00"))
                            await db.pool.execute("""
                                INSERT INTO google_calendar_blocks (
                                    tenant_id, google_event_id, title, description,
                                    start_datetime, end_datetime, all_day, professional_id, sync_status
                                ) VALUES ($8, $1, $2, $3, $4, $5, $6, $7, 'synced')
                                ON CONFLICT (google_event_id) DO NOTHING
                            """, g_id, summary, description, dt_start, dt_end, all_day, prof_id, tenant_id)
                        except Exception as ins_err:
                            logger.error(f"Error inserting GCal block {g_id}: {ins_err}")
                except Exception as e:
                    logger.error(f"JIT Fetch error for prof {prof_id}: {e}")

        # 2. Ocupación: siempre appointments (tenant_id); bloques solo si provider google
        prof_ids = [p["id"] for p in active_professionals]
        start_day = datetime.combine(target_date, datetime.min.time(), tzinfo=ARG_TZ)
        end_day = datetime.combine(target_date, datetime.max.time(), tzinfo=ARG_TZ)

        appointments = await db.pool.fetch("""
            SELECT professional_id, appointment_datetime as start, duration_minutes
            FROM appointments
            WHERE tenant_id = $1 AND professional_id = ANY($2) AND status IN ('scheduled', 'confirmed')
            AND (appointment_datetime < $4 AND (appointment_datetime + interval '1 minute' * COALESCE(duration_minutes, 60)) > $3)
        """, tenant_id, prof_ids, start_day, end_day)

        if calendar_provider == "google":
            gcal_blocks = await db.pool.fetch("""
                SELECT professional_id, start_datetime as start, end_datetime as end
                FROM google_calendar_blocks
                WHERE tenant_id = $1 AND (professional_id = ANY($2) OR professional_id IS NULL)
                AND (start_datetime < $4 AND end_datetime > $3)
            """, tenant_id, prof_ids, start_day, end_day)
        else:
            gcal_blocks = []

        # Mapear intervalos ocupados por profesional
        busy_map = {pid: set() for pid in prof_ids}
        
        # --- Pre-llenar busy_map con horarios NO LABORALES del profesional ---
        # Si working_hours está vacío o el día no tiene slots, el profesional se considera disponible en horario clínica (no se marca nada como ocupado).
        for prof in active_professionals:
            wh = prof.get('working_hours')
            if isinstance(wh, str):
                try:
                    wh = json.loads(wh) if wh else {}
                except Exception:
                    wh = {}
            if not isinstance(wh, dict):
                wh = {}
            day_config = wh.get(day_name_en, {"enabled": False, "slots": []})
            prof_id = prof['id']
            # Solo marcar como ocupados los horarios fuera de working_hours cuando el día tiene slots configurados
            if day_config.get("enabled") and day_config.get("slots"):
                check_time = datetime.combine(target_date, datetime.min.time()).replace(hour=8, minute=0)
                for _ in range(24):
                    h_m = check_time.strftime("%H:%M")
                    if not is_time_in_working_hours(h_m, day_config):
                        busy_map[prof_id].add(h_m)
                    check_time += timedelta(minutes=30)
                    if check_time.hour >= 20:
                        break
            # Si enabled=False o slots=[], no añadimos ocupación → profesional disponible en horario clínica

        # Agregar bloqueos de GCal
        global_busy = set()
        for b in gcal_blocks:
            it = b['start'].astimezone(ARG_TZ)
            while it < b['end'].astimezone(ARG_TZ):
                h_m = it.strftime("%H:%M")
                if b['professional_id']:
                    if b['professional_id'] in busy_map:
                        busy_map[b['professional_id']].add(h_m)
                else:
                    global_busy.add(h_m)
                it += timedelta(minutes=30)
        
        for appt in appointments:
            it = appt['start'].astimezone(ARG_TZ)
            end_it = it + timedelta(minutes=appt['duration_minutes'])
            while it < end_it:
                if appt['professional_id'] in busy_map:
                    busy_map[appt['professional_id']].add(it.strftime("%H:%M"))
                it += timedelta(minutes=30)
        
        # Unir globales a todos
        for pid in busy_map:
            busy_map[pid].update(global_busy)

        # 3. Generar slots libres
        available_slots = generate_free_slots(
            target_date, 
            busy_map, 
            duration_minutes=duration,
            start_time_str=CLINIC_HOURS_START, 
            end_time_str=CLINIC_HOURS_END,
            time_preference=time_preference,
            limit=50
        )
        
        if available_slots:
            ranges_str = slots_to_ranges(available_slots, interval_minutes=30)
            logger.info(f"📅 check_availability OK slots={len(available_slots)} for {date_query} -> ranges: {ranges_str}")
            resp = f"Para {date_query} ({duration} min), tenemos disponibilidad {ranges_str}. "
            if professional_name:
                resp += f"Consultando con Dr/a. {professional_name}."
            return resp
        else:
            logger.info(f"📅 check_availability no slots for {date_query} (duration={duration} min)")
            return f"No encontré huecos libres de {duration} min para {date_query}. ¿Probamos otro día o momento?"
            
    except Exception as e:
        import traceback
        logger.exception(f"Error en check_availability (tenant_id={current_tenant_id.get()}): {e}")
        logger.warning(f"check_availability FAIL date_query={date_query!r} error={e!r} traceback={traceback.format_exc()}")
        return f"No pude consultar la disponibilidad para {date_query}. ¿Probamos una fecha diferente?"

@tool
async def book_appointment(date_time: str, treatment_reason: str, 
                         first_name: Optional[str] = None, last_name: Optional[str] = None, 
                         dni: Optional[str] = None, insurance_provider: Optional[str] = None,
                         professional_name: Optional[str] = None):
    """
    Registra un turno en la BD. 
    Para pacientes NUEVOS (status='guest'), OBLIGATORIAMENTE debes proveer first_name, last_name, dni e insurance_provider.
    Si faltan esos datos en un usuario nuevo, el turno será rechazado.
    
    date_time: Fecha y hora en un solo string (ej: 'miércoles 17:00', 'miércoles 17 hs', 'mañana 14:00').
    treatment_reason: Nombre del tratamiento tal como en list_services (ej. limpieza profunda, consulta).
    first_name, last_name: Nombre y apellido por separado (ej. Adrian / Rodolfo Argañaraz).
    professional_name: (Opcional) Nombre del profesional (ej. Facundo).
    """
    phone = current_customer_phone.get()
    if not phone:
        return "❌ Error: No pude identificar tu teléfono. Reinicia la conversación."
    tenant_id = current_tenant_id.get()
    try:
        apt_datetime = parse_datetime(date_time)
        # No agendar en el pasado
        if apt_datetime < get_now_arg():
            return "❌ No se pueden agendar turnos para horarios que ya pasaron. Indicá un día y hora futuros. Formato esperado: date_time como 'día 17:00' (ej. miércoles 17:00)."
        first_name = str(first_name).strip() if first_name and str(first_name).strip() else None
        last_name = str(last_name).strip() if last_name and str(last_name).strip() else None
        dni_raw = str(dni).strip() if dni and str(dni).strip() else None
        dni = re.sub(r"\D", "", dni_raw) if dni_raw else None  # Solo dígitos (quitar puntos, espacios)
        insurance_raw = str(insurance_provider).strip() if insurance_provider and str(insurance_provider).strip() else None
        # Normalizar "particular" / "no tengo obra social" / "pago yo" etc.
        if insurance_raw and re.search(r"particular|no tengo|pago yo|sin obra|privado", insurance_raw, re.IGNORECASE):
            insurance_provider = "PARTICULAR"
        else:
            insurance_provider = insurance_raw

        t_data = await db.pool.fetchrow("""
            SELECT code, default_duration_minutes FROM treatment_types
            WHERE tenant_id = $1 AND (name ILIKE $2 OR code ILIKE $2) AND is_active = true AND is_available_for_booking = true
            LIMIT 1
        """, tenant_id, f"%{treatment_reason}%")
        if not t_data:
            return "❌ Ese tratamiento no está disponible en esta clínica. Los únicos que se pueden agendar son los que devuelve la tool 'list_services'. Llamá a list_services y ofrecé solo esos al paciente; si pide otro, decile que en esta sede solo se agendan los de esa lista."
        duration = t_data["default_duration_minutes"]
        treatment_code = t_data["code"]
        end_apt = apt_datetime + timedelta(minutes=duration)

        # 2. Verificar/Crear paciente (aislado por tenant)
        existing_patient = await db.pool.fetchrow(
            "SELECT id, status FROM patients WHERE tenant_id = $1 AND phone_number = $2",
            tenant_id, phone,
        )
        if existing_patient:
            await db.pool.execute("""
                UPDATE patients
                SET first_name = COALESCE($1, first_name), last_name = COALESCE($2, last_name),
                    dni = COALESCE($3, dni), insurance_provider = COALESCE($4, insurance_provider),
                    status = 'active', updated_at = NOW()
                WHERE id = $5
            """, first_name, last_name, dni, insurance_provider, existing_patient["id"])
            patient_id = existing_patient["id"]
        else:
            if not (first_name and last_name and dni and insurance_provider):
                return "❌ Necesito Nombre, Apellido, DNI (solo números) y Obra Social (o decir 'particular') para agendar por primera vez. Formato esperado: first_name y last_name por separado; dni solo dígitos; insurance_provider 'PARTICULAR' o nombre de obra social."
            row = await db.pool.fetchrow("""
                INSERT INTO patients (tenant_id, phone_number, first_name, last_name, dni, insurance_provider, status, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, 'active', NOW())
                RETURNING id
            """, tenant_id, phone, first_name, last_name, dni, insurance_provider)
            patient_id = row["id"]

        # 3. Profesionales del tenant (solo aprobados: u.status = 'active')
        clean_p_name = re.sub(r"^(dr|dra|doctor|doctora)\.?\s+", "", (professional_name or ""), flags=re.IGNORECASE).strip()
        p_query = """SELECT p.id, p.first_name, p.last_name, p.google_calendar_id, p.working_hours
                     FROM professionals p
                     INNER JOIN users u ON p.user_id = u.id AND u.role = 'professional' AND u.status = 'active'
                     WHERE p.tenant_id = $1 AND p.is_active = true"""
        p_params = [tenant_id]
        if clean_p_name:
            p_query += " AND (p.first_name ILIKE $2 OR p.last_name ILIKE $2 OR (p.first_name || ' ' || COALESCE(p.last_name, '')) ILIKE $2)"
            p_params.append(f"%{clean_p_name}%")
        candidates = await db.pool.fetch(p_query, *p_params)
        if not candidates:
            return f"❌ No encontré al profesional '{professional_name or ''}' disponible. ¿Querés agendar con otro profesional?"

        calendar_provider = await get_tenant_calendar_provider(tenant_id)
        if calendar_provider == "google":
            existing_apt_gids = await db.pool.fetch(
                "SELECT google_calendar_event_id FROM appointments WHERE tenant_id = $1 AND google_calendar_event_id IS NOT NULL",
                tenant_id,
            )
            apt_gids_set = {row["google_calendar_event_id"] for row in existing_apt_gids}
        target_prof = None

        for cand in candidates:
            wh = cand.get("working_hours")
            if isinstance(wh, str):
                try:
                    wh = json.loads(wh) if wh else {}
                except Exception:
                    wh = {}
            if not isinstance(wh, dict):
                wh = {}
            day_idx = apt_datetime.weekday()
            days_en = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            day_config = wh.get(days_en[day_idx], {"enabled": False, "slots": []})
            # Solo exigir horario laboral si el profesional tiene ese día configurado; si no, considerarlo disponible (igual que check_availability)
            if day_config.get("enabled") and day_config.get("slots"):
                if not is_time_in_working_hours(apt_datetime.strftime("%H:%M"), day_config):
                    continue
            if calendar_provider == "google" and cand.get("google_calendar_id"):
                try:
                    g_events = gcal_service.get_events_for_day(calendar_id=cand["google_calendar_id"], date_obj=apt_datetime.date())
                    day_start = datetime.combine(apt_datetime.date(), datetime.min.time(), tzinfo=ARG_TZ)
                    day_end = datetime.combine(apt_datetime.date(), datetime.max.time(), tzinfo=ARG_TZ)
                    await db.pool.execute(
                        "DELETE FROM google_calendar_blocks WHERE tenant_id = $1 AND professional_id = $2 AND start_datetime < $4 AND end_datetime > $3",
                        tenant_id, cand["id"], day_start, day_end,
                    )
                    for event in g_events:
                        g_id = event["id"]
                        if g_id in apt_gids_set:
                            continue
                        start = event["start"].get("dateTime") or event["start"].get("date")
                        end = event["end"].get("dateTime") or event["end"].get("date")
                        dt_start = datetime.fromisoformat(start.replace("Z", "+00:00"))
                        dt_end = datetime.fromisoformat(end.replace("Z", "+00:00"))
                        await db.pool.execute("""
                            INSERT INTO google_calendar_blocks (tenant_id, google_event_id, title, start_datetime, end_datetime, professional_id, sync_status)
                            VALUES ($1, $2, $3, $4, $5, $6, 'synced') ON CONFLICT (google_event_id) DO NOTHING
                        """, tenant_id, g_id, event.get("summary", "Ocupado"), dt_start, dt_end, cand["id"])
                except Exception as jit_err:
                    logger.error(f"JIT GCal error in booking: {jit_err}")

            if calendar_provider == "google":
                conflict = await db.pool.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM appointments WHERE tenant_id = $1 AND professional_id = $2 AND status IN ('scheduled', 'confirmed')
                        AND (appointment_datetime < $4 AND (appointment_datetime + interval '1 minute' * COALESCE(duration_minutes, 60)) > $3)
                        UNION ALL
                        SELECT 1 FROM google_calendar_blocks WHERE tenant_id = $1 AND (professional_id = $2 OR professional_id IS NULL)
                        AND (start_datetime < $4 AND end_datetime > $3)
                    )
                """, tenant_id, cand["id"], apt_datetime, end_apt)
            else:
                conflict = await db.pool.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM appointments
                        WHERE tenant_id = $1 AND professional_id = $2 AND status IN ('scheduled', 'confirmed')
                        AND (appointment_datetime < $4 AND (appointment_datetime + interval '1 minute' * COALESCE(duration_minutes, 60)) > $3)
                    )
                """, tenant_id, cand["id"], apt_datetime, end_apt)
            if not conflict:
                target_prof = cand
                break

        if not target_prof:
            return f"❌ Lo siento, no hay disponibilidad a las {apt_datetime.strftime('%H:%M')} para el tratamiento de {duration} min. ¿Probamos otro horario?"

        apt_id = str(uuid.uuid4())
        await db.pool.execute("""
            INSERT INTO appointments (id, tenant_id, patient_id, professional_id, appointment_datetime, duration_minutes, appointment_type, status, source, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'scheduled', 'ai', NOW())
        """, apt_id, tenant_id, patient_id, target_prof["id"], apt_datetime, duration, treatment_code)

        if calendar_provider == "google" and target_prof.get("google_calendar_id"):
            try:
                summary = f"Cita Dental AI: {first_name or 'Paciente'} - {treatment_code}"
                gcal_service.create_event(
                    calendar_id=target_prof["google_calendar_id"],
                    summary=summary,
                    start_time=apt_datetime.isoformat(),
                    end_time=end_apt.isoformat(),
                    description=f"Paciente: {first_name} {last_name or ''}\nDNI: {dni}\nOS: {insurance_provider}\nMotivo: {treatment_reason}",
                )
            except Exception as ge:
                logger.error(f"GCal sync error: {ge}")

        # 6. Notificar Socket.IO si está disponible
        try:
            from main import sio # Ensure we have sio
            # Sanitizar para evitar errores de serialización
            safe_data = to_json_safe({
                "id": apt_id, 
                "patient_name": f"{first_name} {last_name or ''}",
                "appointment_datetime": apt_datetime.isoformat(),
                "professional_name": target_prof['first_name']
            })
            await sio.emit("NEW_APPOINTMENT", safe_data)
        except: pass

        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        dia_nombre = dias[apt_datetime.weekday()]
        return f"✅ ¡Turno confirmado con el/la Dr/a. {target_prof['first_name']}! {dia_nombre} {apt_datetime.strftime('%d/%m')} a las {apt_datetime.strftime('%H:%M')} ({duration} min)."

    except Exception as e:
        import traceback
        logger.exception(f"Error en book_appointment: {e}")
        logger.warning(f"book_appointment FAIL traceback={traceback.format_exc()}")
        return "⚠️ Tuve un problema al procesar la reserva. Por favor, intenta de nuevo indicando fecha y hora. Formato esperado: día de la semana + hora 24h (ej. miércoles 17:00, Wednesday 17:00)."

@tool
async def triage_urgency(symptoms: str):
    """
    Analiza síntomas para clasificar urgencia.
    Devuelve: Nivel de urgencia (emergency, high, normal, low) + recomendación
    """
    phone = current_customer_phone.get()
    urgency_keywords = {
        'emergency': ['dolor fuerte', 'sangrado', 'traumatismo', 'accidente', 'golpe', 'roto', 'fractura'],
        'high': ['dolor', 'hinchazón', 'inflamación', 'infección'],
        'normal': ['revisión', 'limpieza', 'control', 'checkup'],
    }
    
    symptoms_lower = symptoms.lower()
    
    # Clasificar urgencia
    urgency_level = 'low'
    for level, keywords in urgency_keywords.items():
        if any(kw in symptoms_lower for kw in keywords):
            urgency_level = level
            break
    
    # Persistir urgencia en el paciente si lo identificamos
    if phone:
        try:
            patient_row = await db.ensure_patient_exists(phone)
            
            # --- Spec 06: Registrar ad_intent_match ---
            ad_intent_match = False
            meta_headline = patient_row.get("meta_ad_headline") or "" if patient_row else ""
            if meta_headline:
                ad_urgency_kws = ["urgencia", "dolor", "emergencia", "trauma", "emergency", "pain", "urgent"]
                ad_is_urgency = any(kw in meta_headline.lower() for kw in ad_urgency_kws)
                clinical_is_urgency = urgency_level in ('emergency', 'high')
                ad_intent_match = ad_is_urgency and clinical_is_urgency
                if ad_intent_match:
                    logger.info(f"🎯 ad_intent_match=True para {phone}: ad='{meta_headline}', triage={urgency_level}")
            # -------------------------------------------
            
            await db.pool.execute("""
                UPDATE patients 
                SET urgency_level = $1, urgency_reason = $2, updated_at = NOW()
                WHERE id = $3
            """, urgency_level, symptoms, patient_row['id'])
            
            # Notificar al dashboard el cambio de prioridad
            await sio.emit("PATIENT_UPDATED", to_json_safe({
                "phone_number": phone,
                "urgency_level": urgency_level,
                "urgency_reason": symptoms,
                "ad_intent_match": ad_intent_match,
            }))
        except Exception as e:
            logger.error(f"Error persisting triage: {e}")

    responses = {
        'emergency': "🚨 URGENCIA DETECTADA. Deberías venir HOY mismo. Si es muy grave, llama directamente: Llamá al consultorio.",
        'high': "⚠️ Deberías agendar un turno lo antes posible, preferentemente esta semana.",
        'normal': "✅ Puedes agendar un turno en la fecha que te venga bien.",
        'low': "ℹ️ Puedes agendar una revisión de rutina cuando lo necesites."
    }
    
    return responses.get(urgency_level, responses['normal'])

@tool
async def list_my_appointments(upcoming_days: int = 14):
    """
    Lista los turnos del paciente que tiene la conversación (próximos o recientes).
    Usar cuando pregunten si tienen turno, cuándo es su próximo turno, qué turnos tienen, etc.
    upcoming_days: Cantidad de días hacia adelante a partir de hoy (default 14).
    """
    phone = current_customer_phone.get()
    if not phone:
        return "No pude identificar tu número. Escribime desde el mismo WhatsApp con el que te registraste."
    tenant_id = current_tenant_id.get()
    try:
        start = get_now_arg().date()
        end = start + timedelta(days=max(1, min(upcoming_days, 90)))
        rows = await db.pool.fetch("""
            SELECT a.appointment_datetime, a.status, a.appointment_type,
                   p_prof.first_name || ' ' || COALESCE(p_prof.last_name, '') as professional_name
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            LEFT JOIN professionals p_prof ON a.professional_id = p_prof.id
            WHERE p.tenant_id = $1 AND p.phone_number = $2
            AND DATE(a.appointment_datetime) >= $3 AND DATE(a.appointment_datetime) <= $4
            AND a.status IN ('scheduled', 'confirmed')
            ORDER BY a.appointment_datetime ASC
        """, tenant_id, phone, start, end)
        if not rows:
            return f"No tenés turnos registrados en los próximos {upcoming_days} días. ¿Querés que busquemos disponibilidad para agendar?"
        lines = []
        for r in rows:
            dt = r['appointment_datetime']
            if hasattr(dt, 'astimezone'):
                dt = dt.astimezone(ARG_TZ)
            fecha_hora = dt.strftime("%d/%m/%Y %H:%M") if hasattr(dt, 'strftime') else str(dt)
            prof = (r['professional_name'] or '').strip() or "Profesional"
            lines.append(f"• {fecha_hora} con {prof} ({r['appointment_type'] or 'consulta'})")
        return "Tus próximos turnos:\n" + "\n".join(lines) + "\n\n¿Querés cancelar o reprogramar alguno?"
    except Exception as e:
        logger.error(f"Error en list_my_appointments: {e}")
        return "Hubo un error al buscar tus turnos. ¿Probamos de nuevo?"

@tool
async def cancel_appointment(date_query: str):
    """
    Cancela un turno existente. 
    date_query: Fecha del turno a cancelar (ej: 'mañana', '2025-05-10', 'el martes')
    """
    phone = current_customer_phone.get()
    if not phone:
        return "⚠️ No pude identificar tu teléfono. Por favor, contactame de nuevo."

    tenant_id = current_tenant_id.get()
    try:
        target_date = parse_date(date_query)
        apt = await db.pool.fetchrow("""
            SELECT a.id, a.google_calendar_event_id
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            WHERE p.tenant_id = $1 AND p.phone_number = $2 AND DATE(a.appointment_datetime) = $3
            AND a.status IN ('scheduled', 'confirmed')
            LIMIT 1
        """, tenant_id, phone, target_date)
        if not apt:
            return f"No encontré ningún turno activo para el día {date_query}. ¿Querés que revisemos otra fecha?"

        calendar_provider = await get_tenant_calendar_provider(tenant_id)
        if apt["google_calendar_event_id"] and calendar_provider == "google":
            # Fetch professional's calendar ID
            google_calendar_id = await db.pool.fetchval(
                "SELECT google_calendar_id FROM professionals WHERE id = (SELECT professional_id FROM appointments WHERE id = $1)",
                apt["id"],
            )
            if google_calendar_id:
                gcal_service.delete_event(calendar_id=google_calendar_id, event_id=apt["google_calendar_event_id"])
        # 2. Marcar como cancelado en BD
        await db.pool.execute("""
            UPDATE appointments SET status = 'cancelled', google_calendar_sync_status = 'cancelled'
            WHERE id = $1
        """, apt['id'])
        
        # 3. Notificar a la UI (Borrado visual)
        from main import sio
        await sio.emit("APPOINTMENT_DELETED", apt['id'])

        logger.info(f"🚫 Turno cancelado por IA: {apt['id']} ({phone})")
        return f"Entendido. He cancelado tu turno del {date_query}. ¿Te puedo ayudar con algo más?"
        
    except Exception as e:
        logger.error(f"Error en cancel_appointment: {e}")
        return "⚠️ Hubo un error al intentar cancelar el turno. Por favor, intenta nuevamente."

@tool
async def reschedule_appointment(original_date: str, new_date_time: str):
    """
    Reprograma un turno existente a una nueva fecha/hora.
    original_date: Fecha del turno actual (ej: 'hoy', 'lunes')
    new_date_time: Nueva fecha y hora deseada (ej: 'mañana 15:00')
    """
    phone = current_customer_phone.get()
    if not phone:
        return "⚠️ No pude identificar tu teléfono."
    tenant_id = current_tenant_id.get()
    try:
        orig_date = parse_date(original_date)
        new_dt = parse_datetime(new_date_time)
        apt = await db.pool.fetchrow("""
            SELECT a.id, a.google_calendar_event_id, a.professional_id
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            WHERE p.tenant_id = $1 AND p.phone_number = $2 AND DATE(a.appointment_datetime) = $3
            AND a.status IN ('scheduled', 'confirmed')
            LIMIT 1
        """, tenant_id, phone, orig_date)
        if not apt:
            return f"No encontré tu turno para el {original_date}. ¿Podrías confirmarme la fecha original?"

        overlap = await db.pool.fetchval("""
            SELECT COUNT(*) FROM appointments
            WHERE tenant_id = $1 AND professional_id = $2 AND status IN ('scheduled', 'confirmed') AND id != $3
            AND appointment_datetime < $4 + interval '30 minutes'
            AND appointment_datetime + interval '30 minutes' > $4
        """, tenant_id, apt["professional_id"], apt["id"], new_dt)
        
        if overlap and overlap > 0:
            return f"Lo siento, el horario {new_date_time} ya está ocupado. ¿Probamos con otro?"

        calendar_provider = await get_tenant_calendar_provider(tenant_id)
        google_calendar_id = await db.pool.fetchval(
            "SELECT google_calendar_id FROM professionals WHERE id = $1",
            apt["professional_id"],
        )
        new_gcal = None
        if calendar_provider == "google" and apt.get("google_calendar_event_id") and google_calendar_id:
            gcal_service.delete_event(calendar_id=google_calendar_id, event_id=apt["google_calendar_event_id"])
            summary = f"Cita Dental AI (Reprogramada): {phone}"
            new_gcal = gcal_service.create_event(
                calendar_id=google_calendar_id,
                summary=summary,
                start_time=new_dt.isoformat(),
                end_time=(new_dt + timedelta(minutes=60)).isoformat(),
            )
        sync_status = "synced" if new_gcal else "local"
        await db.pool.execute("""
            UPDATE appointments SET
                appointment_datetime = $1,
                google_calendar_event_id = COALESCE($2, google_calendar_event_id),
                google_calendar_sync_status = $3,
                updated_at = NOW()
            WHERE id = $4
        """, new_dt, new_gcal["id"] if new_gcal else None, sync_status, apt["id"])
        
        # 5. Emitir evento Socket.IO (Actualizar UI)
        try:
            # Obtener datos actualizados para el frontend
            updated_apt = await db.pool.fetchrow("""
                SELECT a.*, p.first_name, p.last_name, p.phone_number, prof.first_name as professional_name
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                JOIN professionals prof ON a.professional_id = prof.id
                WHERE a.id = $1
            """, apt['id'])
            if updated_apt:
                await sio.emit("APPOINTMENT_UPDATED", to_json_safe(dict(updated_apt)))
        except Exception as se:
            logger.error(f"Error emitiendo APPOINTMENT_UPDATED via Socket: {se}")

        logger.info(f"🔄 Turno reprogramado por IA: {apt['id']} para {new_dt}")
        return f"¡Listo! Tu turno ha sido reprogramado para el {new_date_time}. Te esperamos."

    except Exception as e:
        logger.error(f"Error en reschedule_appointment: {e}")
        return "⚠️ No pude reprogramar el turno. Por favor, intenta de nuevo."

@tool
async def list_professionals():
    """
    Lista los profesionales que trabajan en la clínica (odontólogos/as activos y aprobados).
    Usar SIEMPRE que el paciente pregunte qué profesionales hay, quién atiende, con quién puede sacar turno, etc.
    Devuelve nombres y especialidad reales de la base de datos. NUNCA inventes nombres.
    """
    tenant_id = current_tenant_id.get()
    try:
        rows = await db.pool.fetch("""
            SELECT p.first_name, p.last_name, p.specialty
            FROM professionals p
            INNER JOIN users u ON p.user_id = u.id AND u.role = 'professional' AND u.status = 'active'
            WHERE p.tenant_id = $1 AND p.is_active = true
            ORDER BY p.first_name, p.last_name
        """, tenant_id)
        if not rows:
            return "No hay profesionales cargados en esta sede por el momento. El paciente puede contactar a la clínica por otro medio."
        res = "👨‍⚕️ Profesionales de la clínica:\n"
        for r in rows:
            name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or "Profesional"
            specialty = (r['specialty'] or "Odontología general").strip()
            res += f"• {name} - {specialty}\n"
        return res
    except Exception as e:
        logger.error(f"Error en list_professionals: {e}")
        return "⚠️ Error al consultar profesionales."

@tool
async def list_services(category: str = None):
    """
    Lista los tratamientos/servicios dentales disponibles para reservar en la clínica.
    Usar SIEMPRE que el paciente pregunte qué tratamientos tienen, qué servicios ofrecen, qué se puede agendar, etc.
    Devuelve solo tratamientos reales de la base de datos (nombre, duración). NUNCA inventes tratamientos.
    category: Filtro opcional (prevention, restorative, surgical, orthodontics, emergency)
    """
    tenant_id = current_tenant_id.get()
    try:
        query = """SELECT code, name, description, default_duration_minutes
                   FROM treatment_types
                   WHERE tenant_id = $1 AND is_active = true AND is_available_for_booking = true"""
        params = [tenant_id]
        if category:
            query += " AND category = $2"
            params.append(category)
        rows = await db.pool.fetch(query, *params)
        if not rows:
            return "No hay tratamientos disponibles para reservar en esta sede en este momento."
        res = "🦷 Tratamientos disponibles para agendar:\n"
        for r in rows:
            desc = (r['description'] or '').strip()
            res += f"• {r['name']} ({r['default_duration_minutes']} min)" + (f": {desc}\n" if desc else "\n")
        return res
    except Exception as e:
        logger.error(f"Error en list_services: {e}")
        return "⚠️ Error al consultar servicios."

@tool
async def derivhumano(reason: str):
    """
    Deriva la conversación a un humano cuando la IA no puede ayudar, el paciente lo solicita 
    o hay una situación que requiere atención personalizada.
    reason: El motivo de la derivación.
    """
    phone = current_customer_phone.get()
    tenant_id = current_tenant_id.get()
    try:
        override_until = datetime.now(timezone.utc) + timedelta(hours=24)
        await db.pool.execute("""
            UPDATE patients SET
                human_handoff_requested = true,
                human_override_until = $1,
                last_derivhumano_at = NOW(),
                updated_at = NOW()
            WHERE tenant_id = $2 AND phone_number = $3
        """, override_until, tenant_id, phone)
        logger.info(f"👤 Derivación humana solicitada para {phone} (tenant={tenant_id}): {reason}")
        from main import sio
        await sio.emit("HUMAN_HANDOFF", to_json_safe({"phone_number": phone, "tenant_id": tenant_id, "reason": reason}))
        patient = await db.pool.fetchrow(
            "SELECT first_name, last_name, email FROM patients WHERE tenant_id = $1 AND phone_number = $2",
            tenant_id, phone,
        )
        patient_name = f"{patient['first_name']} {patient['last_name'] or ''}".strip()
        
        history = await db.pool.fetch("""
            SELECT role, content, created_at FROM chat_messages
            WHERE from_number = $1 AND tenant_id = $2 ORDER BY created_at DESC LIMIT 5
        """, phone, tenant_id)
        
        history_text = "<br>".join([f"<b>{msg['role']}:</b> {msg['content']}" for msg in reversed(history)])
        
        # Obtener email destino (del tenant o env var)
        destination_email = os.getenv("NOTIFICATIONS_EMAIL", "gamarradrian200@gmail.com")
        
        email_sent = email_service.send_handoff_email(
            to_email=destination_email, 
            patient_name=patient_name, 
            phone=phone, 
            reason=reason,
            chat_history_preview=history_text
        )
        
        if email_sent:
            return "He notificado a un asesor humano. Te contactará por WhatsApp en breve."
        else:
            return "Ya he solicitado que un humano revise tu caso. Aguardanos un momento."
            
    except Exception as e:
        logger.error(f"Error en derivhumano: {e}")
        return "Hubo un problema al derivarte, pero ya he dejado el aviso en el sistema."

DENTAL_TOOLS = [list_professionals, list_services, check_availability, book_appointment, list_my_appointments, cancel_appointment, reschedule_appointment, triage_urgency, derivhumano]

# --- DETECCIÓN DE IDIOMA (para respuesta del agente) ---
def detect_message_language(text: str) -> str:
    """
    Detecta si el mensaje está predominantemente en español, inglés o francés.
    Devuelve 'es', 'en' o 'fr'. Por defecto 'es'.
    """
    if not text or not text.strip():
        return "es"
    t = text.lower().strip()
    en = 0
    fr = 0
    es = 0
    en_markers = ["hello", "hi", "please", "thank", "thanks", "appointment", "schedule", "want", "need", "pain", "tooth", "teeth", "doctor", "when", "available", "how", "what", "can you", "would like", "good morning", "good afternoon", "help"]
    fr_markers = ["bonjour", "merci", "s'il vous plaît", "s'il te plaît", "rendez-vous", "voulez", "j'ai", "mal", "dent", "docteur", "quand", "disponible", "aide", "besoin", "bonsoir", "oui", "non", "je voudrais", "pouvez"]
    es_markers = ["hola", "gracias", "por favor", "turno", "quiero", "necesito", "dolor", "muela", "diente", "doctor", "cuándo", "disponible", "ayuda", "buenos días", "tarde", "sí", "no", "me gustaría", "puede", "podría", "agendar", "cita"]
    for w in en_markers:
        if w in t:
            en += 1
    for w in fr_markers:
        if w in t:
            fr += 1
    for w in es_markers:
        if w in t:
            es += 1
    if en > fr and en > es:
        return "en"
    if fr > en and fr > es:
        return "fr"
    return "es"


def build_system_prompt(
    clinic_name: str,
    current_time: str,
    response_language: str,
    hours_start: str = "08:00",
    hours_end: str = "19:00",
    ad_context: str = "",
) -> str:
    """
    Construye el system prompt del agente de forma agnóstica: usa el nombre de la clínica
    inyectado y la instrucción de idioma de respuesta (es/en/fr).
    ad_context: (Spec 06) Directiva contextual del anuncio de Meta Ads, si aplica.
    """
    lang_instructions = {
        "es": "RESPONDE ÚNICAMENTE EN ESPAÑOL. Todo tu mensaje (saludos, explicaciones, preguntas) debe estar en español. Mantené el voseo rioplatense cuando sea natural.",
        "en": "RESPOND ONLY IN ENGLISH. Your entire message (greetings, explanations, questions) must be in English. Keep a warm, professional tone.",
        "fr": "RÉPONDS UNIQUEMENT EN FRANÇAIS. Tout ton message (salutations, explications, questions) doit être en français. Garde un ton chaleureux et professionnel.",
    }
    lang_rule = lang_instructions.get(response_language, lang_instructions["es"])

    # Spec 06: Bloque de contexto de anuncio (se inyecta al inicio si existe)
    ad_block = ""
    if ad_context:
        ad_block = f"""\n\nCONTEXTO DE ANUNCIO (Meta Ads):\n{ad_context}\n"""

    return f"""REGLA DE IDIOMA (OBLIGATORIA): {lang_rule}{ad_block}

REGLA DE ORO DE IDENTIDAD: En tu primer mensaje de cada conversación, presentate como la asistente de la clínica. Ejemplo en español: "Hola! Soy la asistente de {clinic_name}, es un gusto saludarte. 😊". Adaptá esta presentación al idioma en el que debés responder.
Sos la asistente virtual de {clinic_name}. No sos un bot corporativo ni de ninguna otra clínica.

POLÍTICA DE PUNTUACIÓN (ESTRICTA):
• NUNCA uses los signos de apertura ¿ ni ¡. 
• SOLAMENTE usá los signos de cierre ? y ! al final de las frases (ej: "Cómo estás?", "Qué alegría!"). 
• El incumplimiento de esta regla rompe la ilusión de humanidad en WhatsApp.

Tu objetivo es ayudar a pacientes a: (a) informarse sobre tratamientos, (b) consultar disponibilidad, (c) agendar/reprogramar/cancelar turnos y (d) realizar triaje inicial de urgencias.

IDENTIDAD Y TONO:
• PERSONALIDAD: Sos una persona real, cálida, que se preocupa por el paciente. 
• TONO: En español usá voseo natural y cercano (voseo rioplatense). "Che", "viste", "contame", "fijate", "dale", "mirá". En otros idiomas, mantené un tono cercano y profesional.
• CERCANÍA: Si el paciente está de acuerdo, usá su nombre. Generá confianza y curiosidad sobre su salud bucal.

POLÍTICAS DURAS:
• NUNCA INVENTES: No inventes horarios ni disponibilidad. Siempre usá 'check_availability'. La disponibilidad se consulta en la agenda interna (local) o en Google Calendar por profesional según la configuración de la clínica; la tool ya aplica la lógica correcta.
• DISPONIBILIDAD (OBLIGATORIO): Si el paciente pregunta por disponibilidad para un día, llamá a 'check_availability' UNA SOLA VEZ con: date_query = el día (mañana, martes, miércoles...), treatment_name si ya definieron tratamiento, y time_preference: si piden "a la tarde" o "por la tarde" -> time_preference='tarde'; si piden "a la mañana" o "por la mañana" -> time_preference='mañana'; si no especifican -> no pasar o 'todo'. Respondé UNA SOLA VEZ con exactamente lo que devuelva la tool (ya viene en rangos, ej. "de 9 a 12 y de 14 a 17"). No envíes varios mensajes ni variaciones; no digas "no hay" y después listes horarios.
• PROFESIONALES Y TRATAMIENTOS (OBLIGATORIO): Si el paciente pregunta qué profesionales trabajan, quiénes atienden o con quién puede sacar turno, DEBES llamar a 'list_professionals' y responder ÚNICAMENTE con los nombres y especialidades que devuelva la tool. Si pregunta qué tratamientos tienen, qué servicios ofrecen o qué se puede agendar, DEBES llamar a 'list_services' y responder ÚNICAMENTE con la lista que devuelva la tool. NUNCA inventes nombres de profesionales (ej. Juan Pérez, María López) ni listas de tratamientos; solo los que devuelvan las tools.
• HORARIOS SAGRADOS: Los horarios de los profesionales son sagrados. Si un profesional no atiende el día solicitado, informalo claramente al paciente y ofrecé alternativas (otro día con el mismo profesional u otros profesionales para ese día).
• NO DIAGNOSTICAR: Ante dudas clínicas, decí que un profesional de la clínica tendrá que evaluar en consultorio para un diagnóstico certero.
• ZONA HORARIA: America/Argentina/Buenos_Aires (GMT-3). 
• TIEMPO ACTUAL: {current_time}
• HORARIOS DE ATENCIÓN GENERAL: Lunes a Sábados de {hours_start} a {hours_end} (Domingos cerrado). Cada profesional tiene su propio horario que 'check_availability' conoce.
• REGLA ANTI-PASADO: No podés agendar turnos para horarios que ya pasaron. Si un paciente pide un horario ya pasado, informale amablemente y ofrecele los siguientes disponibles.
• DERIVACIÓN (Human Handoff): 
  - Usá 'derivhumano' INMEDIATAMENTE si: (a) URGENCIA crítica detectada por 'triage_urgency', (b) El paciente está frustrado o enojado, (c) Pide hablar con una persona.
  - CRÍTICO: Si decidís derivar, **DEBES USAR LA TOOL**.

SERVICIOS (OBLIGATORIO DEFINIR UNO — ESTRICTO):
• TRATAMIENTOS SOLO LOS DE LA PLATAFORMA: Los únicos tratamientos que esta clínica ofrece para agendar son los que devuelve la tool 'list_services' (son los cargados en la sección Tratamientos de la plataforma). Está PROHIBIDO sugerir, ofrecer o mencionar ningún otro (ej. ortodoncia, implantes, blanqueamiento, endodoncia) a menos que figure en la respuesta de list_services. Si el paciente pide algo que no está en esa lista, decile que en esta sede solo se agendan los tratamientos que aparecen ahí y ofrecé llamar a list_services para mostrárselos.
• Siempre se debe definir UN servicio/tratamiento antes de consultar disponibilidad o agendar. No agendes nunca sin motivo (tratamiento).
• Si el paciente pregunta por disponibilidad o turnos sin decir el servicio, preguntale qué tratamiento necesita. Para saber qué tratamientos ofrecen, usá 'list_services' y ofrecé ÚNICAMENTE esos (nunca inventes ni agregues otros).
• Al hablar de servicios: solo mencioná tratamientos que devolvió 'list_services'. Si listás opciones, que sean únicamente las de la tool.
• La duración del turno la define el servicio elegido: usá siempre 'check_availability' y 'book_appointment' con el nombre del tratamiento tal como figura en list_services para que el sistema use la duración correcta.

FLUJO DE AGENDAMIENTO (ORDEN ESTRICTO):
1. SALUDO E IDENTIDAD: En el primer mensaje de la conversación, presentate como asistente de {clinic_name}.
2. DEFINIR SERVICIO: Asegurate de tener claro qué tratamiento busca (limpieza, consulta, urgencia, etc.). Si no lo dijo, preguntalo. Sin servicio definido no se puede consultar disponibilidad ni agendar.
3. PROFESIONAL (antes o al consultar disponibilidad): Si preguntan qué profesionales hay, usá 'list_professionals' y respondé con esa lista. Para elegir profesional al agendar: podés preguntar "¿Tenés preferencia por algún profesional o buscamos el primer disponible?" Si tiene preferencia, usá 'check_availability' con professional_name (el nombre debe ser uno de los que devolvió list_professionals); si no, llamá 'check_availability' sin professional_name.
4. CONSULTAR DISPONIBILIDAD: Llamá 'check_availability' UNA vez con date_query, treatment_name y (si pidieron tarde o mañana) time_preference='tarde' o 'mañana'. La tool devuelve rangos tipo "de 09:00 a 12:00 y de 14:00 a 17:00". Transmití eso al paciente en un solo mensaje; no repitas ni des otra versión (solo tarde o solo todo el día).
5. GESTIÓN DE TURNOS DEL PACIENTE: Si preguntan "¿tengo turno?", "¿cuándo es mi próximo turno?", "¿qué turnos tengo?" usá 'list_my_appointments'. Para cancelar: 'cancel_appointment' con la fecha del turno. Para reprogramar: 'reschedule_appointment' con la fecha actual del turno y la nueva fecha/hora.
6. DATOS DEL PACIENTE: Cuando el paciente elija día y hora, pedí: nombre completo, DNI, Obra Social o PARTICULAR. Para pacientes nuevos son obligatorios los 4 datos para poder agendar.
7. AGENDAR: Solo cuando tengas: servicio (treatment_reason), fecha y hora elegidos, y los 4 datos (nombre, apellido, DNI, obra social), ejecutá 'book_appointment'. Podés pasar professional_name si ya quedó elegido; si no, el sistema asigna un profesional disponible. No llames 'book_appointment' sin haber consultado antes disponibilidad para esa fecha/hora.

FORMATO CANÓNICO AL LLAMAR TOOLS (español e inglés): Antes de llamar cualquier tool, traducí lo que dijo el usuario al formato que la tool espera. Para 'book_appointment' siempre enviá:
• date_time: "día de la semana" + espacio + hora en 24h con :00 si no hay minutos. Ejemplos: miércoles 17:00, tomorrow 14:00, Wednesday 17:00. Si el usuario dice "5 pm" o "17 hs", convertí a 24h (17:00).
• first_name y last_name: Por separado. Si solo da un nombre, usá first_name y pedí el apellido si la tool lo exige para pacientes nuevos.
• dni: Solo dígitos, sin puntos ni espacios (ej. 40989310).
• insurance_provider: Si no tiene obra social (particular, I pay myself, private, etc.) enviá exactamente PARTICULAR; si tiene, el nombre de la obra social tal cual (ej. OSDE, Swiss Medical).
• treatment_reason: Nombre exacto como en la respuesta de list_services (ej. Limpieza Profunda, consulta).

NUNCA DAR POR PERDIDA UNA RESERVA: Si una tool devuelve un mensaje que empiece con ❌ o ⚠️, interpretalo como error de formato o validación. Debés leer el mensaje, corregir el parámetro indicado según el formato canónico anterior y volver a llamar la misma tool. No digas al paciente "no pude procesar" sin haber reintentado al menos una vez. Solo si tras el reintento la tool sigue fallando, pedí al paciente que repita el dato concreto o ofrecé derivación.

REQUISITOS DE 'book_appointment': date_time, treatment_reason, first_name, last_name, dni, insurance_provider (professional_name opcional). Si faltan datos, la tool te lo indica; pedilos y volvé a intentar.

TRIAJE Y URGENCIAS: Ante dolor o accidentes, 'triage_urgency' primero. Si es emergency/high, contené al paciente y avisá que vas a dar prioridad.

Usa solo las tools proporcionadas. Siempre terminá con una pregunta o frase que invite a seguir la charla.
"""


# --- AGENT SETUP (prompt dinámico: system_prompt se inyecta en cada invocación) ---
# Vault (spec §5.2): soporte api_key por tenant vía get_agent_executable_for_tenant(tenant_id)
def get_agent_executable(openai_api_key: Optional[str] = None):
    key = (openai_api_key or "").strip() or OPENAI_API_KEY
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=key)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_prompt}"),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    agent = create_openai_tools_agent(llm, DENTAL_TOOLS, prompt)
    return AgentExecutor(agent=agent, tools=DENTAL_TOOLS, verbose=False)


async def get_agent_executable_for_tenant(tenant_id: int):
    """Devuelve un executor del agente usando OPENAI_API_KEY del tenant (Vault). Fallback a env."""
    from core.credentials import get_tenant_credential
    key = await get_tenant_credential(tenant_id, "OPENAI_API_KEY")
    if not key:
        key = OPENAI_API_KEY
    return get_agent_executable(openai_api_key=key)


agent_executor = get_agent_executable()

# --- API ENDPOINTS ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle: startup and shutdown."""
    # Startup
    logger.info("🚀 Iniciando orquestador dental...")
    await db.connect()
    logger.info(f"✅ Base de datos conectada. Version: {await db.pool.fetchval('SELECT version()')}")
    
    # Iniciar motor de automatización (Spec 03 / Misión 2)
    try:
        await automation_service.start()
    except Exception as e:
        logger.error(f"❌ Falló el inicio de AutomationService: {e}")
    
    yield
    
    # Shutdown
    logger.info("🔴 Cerrando orquestador dental...")
    await db.disconnect()
    logger.info("✅ Desconexión completada")
    
    # Detener motor de automatización
    await automation_service.stop()

# OpenAPI / Swagger: documentación de contratos API
OPENAPI_TAGS = [
    {"name": "Nexus Auth", "description": "Login, registro, perfil y clínicas. Rutas públicas y protegidas."},
    {"name": "Dental Admin", "description": "Panel administrativo. Todas las rutas requieren JWT + header X-Admin-Token."},
    {"name": "Usuarios", "description": "Aprobaciones y listado de usuarios (CEO)."},
    {"name": "Sedes", "description": "CRUD de tenants/clínicas. Solo CEO."},
    {"name": "Pacientes", "description": "Fichas, historial clínico, búsqueda y contexto por tenant."},
    {"name": "Turnos", "description": "Appointments: listar, crear, actualizar, colisiones, próximos slots. Calendario híbrido (local/Google)."},
    {"name": "Profesionales", "description": "Personal médico por sede, working hours, analytics."},
    {"name": "Chat", "description": "Sesiones WhatsApp, mensajes, human-intervention, urgencias. Multi-tenant."},
    {"name": "Calendario", "description": "Bloques, sync con Google Calendar, connect-sovereign (Auth0)."},
    {"name": "Tratamientos", "description": "Tipos de tratamiento (servicios), duración, categorías."},
    {"name": "Estadísticas", "description": "Resumen de stats, métricas del dashboard."},
    {"name": "Configuración", "description": "Settings de clínica (idioma UI), config de despliegue."},
    {"name": "Analítica", "description": "Métricas por profesional, resúmenes para CEO."},
    {"name": "Internal", "description": "Credenciales internas (X-Internal-Token). Uso entre servicios."},
    {"name": "Health", "description": "Estado del servicio. Público."},
    {"name": "Chat IA", "description": "Endpoint de chat del agente (WhatsApp/service). Persiste historial en BD."},
]

app = FastAPI(
    title="Dentalogic API",
    description=(
        "API del **Orchestrator** de Dentalogic: gestión multi-tenant de clínicas dentales. "
        "Incluye auth (JWT + X-Admin-Token), pacientes, turnos, profesionales, chat WhatsApp, "
        "calendario híbrido (local/Google), tratamientos y analíticas. "
        "Documentación de contratos: **Swagger UI** en `/docs`, **ReDoc** en `/redoc`, **OpenAPI JSON** en `/openapi.json`."
    ),
    version=os.getenv("API_VERSION", "1.0.0"),
    openapi_tags=OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Configurar CORS
allowed_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "")
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
]

if allowed_origins_str:
    extra_origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]
    origins.extend(extra_origins)

# Eliminar duplicados manteniendo el orden lógico
origins = list(dict.fromkeys(origins))

# --- MIDDLEWARE & EXCEPTION HANDLERS ---

def _cors_headers(request: Request) -> dict:
    """Asegura que las respuestas de error incluyan CORS (evita bloqueo en navegador)."""
    origin = request.headers.get("origin") or ""
    h = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "*",
    }
    if origin in origins:
        h["Access-Control-Allow-Origin"] = origin
    elif origins:
        h["Access-Control-Allow-Origin"] = origins[0]
    return h

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"🔥 UNHANDLED ERROR: {str(exc)}", exc_info=True)
    content = {
        "detail": "Error interno del servidor. El equipo técnico ha sido notificado.",
        "error_type": type(exc).__name__
    }
    response = JSONResponse(status_code=500, content=content)
    for k, v in _cors_headers(request).items():
        response.headers[k] = v
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- RUTAS ---
app.include_router(auth_router)
# Chatwoot API: Specific routes must come BEFORE generic admin routes to avoid shadowing
app.include_router(chat_api.router)
app.include_router(admin_router)
# Chatwoot Webhooks
app.include_router(chat_webhooks.router)


# OpenAPI: inyectar securitySchemes para que en Swagger UI se pueda usar Authorize (JWT + X-Admin-Token)
_original_openapi = app.openapi


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = _original_openapi()
    openapi_schema.setdefault("components", {})
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT obtenido con POST /auth/login. Incluir como: Authorization: Bearer <token>.",
        },
        "X-Admin-Token": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Admin-Token",
            "description": "Token de infraestructura (env ADMIN_TOKEN). Requerido en todas las rutas /admin/*.",
        },
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = _custom_openapi

# --- SOCKET.IO CONFIGURATION ---
# Create Socket.IO instance with async mode
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins=origins)
socket_app = socketio.ASGIApp(sio, app)

# Expose sio and helpers for other routes
app.state.sio = sio
app.state.to_json_safe = to_json_safe

# Socket.IO event handlers
@sio.event
async def connect(sid, environ):
    logger.info(f"🔌 Client connected: {sid}")

@sio.event
async def disconnect(sid):
    logger.info(f"🔌 Client disconnected: {sid}")

# Helper function to emit appointment events (can be imported by admin_routes)
async def emit_appointment_event(event_type: str, data: Dict[str, Any]):
    """Emit appointment-related events to all connected clients. Serializa a JSON-safe para evitar fallos por UUID/datetime."""
    payload = to_json_safe(data) if data else data
    await sio.emit(event_type, payload)
    logger.info(f"📡 Socket event emitted: {event_type}")

# Make the emit function available to other modules
app.state.emit_appointment_event = emit_appointment_event

@app.post("/chat", tags=["Chat IA"])
async def chat_endpoint(req: ChatRequest, background_tasks: BackgroundTasks):
    """Endpoint de chat que persiste historial en BD. Usado por WhatsApp Service y pruebas."""
    correlation_id = str(uuid.uuid4())
    # Log visible en cualquier nivel (WARNING) para diagnosticar si las peticiones llegan al orchestrator
    logger.warning(f"📩 CHAT received from={getattr(req, 'from_number', None) or getattr(req, 'phone', None)} to={getattr(req, 'to_number', None)} msg_preview={(req.final_message or '')[:60]!r}")

    current_customer_phone.set(req.final_phone)
    # 0. RESOLUCIÓN DINÁMICA DE TENANT (Soberanía Nexus v7.6)
    # Buscamos el tenant_id basándonos en el número al que escribieron (to_number)
    # Si no viene to_number (ej: pruebas manuales), usamos el BOT_PHONE_NUMBER de ENV como fallback
    bot_number = req.to_number or os.getenv("BOT_PHONE_NUMBER") or "5491100000000"
    # Normalizar: quitar todo lo que no sea dígito para comparar con BD (ej. 5493435256815 vs +5493435256815)
    bot_number_clean = re.sub(r"\D", "", bot_number) if bot_number else ""

    tenant = await db.pool.fetchrow("SELECT id FROM tenants WHERE bot_phone_number = $1", bot_number)
    if not tenant and bot_number_clean:
        # Intentar match solo por dígitos (ej. 5493435256815 vs +5493435256815)
        tenant = await db.pool.fetchrow(
            "SELECT id FROM tenants WHERE REGEXP_REPLACE(bot_phone_number, '[^0-9]', '', 'g') = $1",
            bot_number_clean,
        )
    if not tenant:
        # Si no existe la clínica por número, usamos la Clínica por defecto (ID 1) para evitar crash
        logger.warning(f"⚠️ Sede no encontrada para el número {bot_number!r}. Usando tenant_id=1 por defecto.")
        tenant_id = 1
    else:
        tenant_id = tenant['id']
    logger.info(f"📩 CHAT tenant_id={tenant_id} bot_number={bot_number!r} from={req.final_phone}")

    current_tenant_id.set(tenant_id)

    # 0. DEDUP) Si el mensaje viene con provider_message_id (ej. WhatsApp/YCloud), procesar solo una vez
    provider = (req.provider or "ycloud").strip() or "ycloud"
    provider_message_id = (req.provider_message_id or req.event_id or "").strip()
    if provider_message_id:
        try:
            payload_snapshot = {"from_number": req.final_phone, "to_number": getattr(req, "to_number", None), "text": req.final_message[:500] if req.final_message else None}
            inserted = await db.try_insert_inbound(
                provider=provider,
                provider_message_id=provider_message_id,
                event_id=(req.event_id or provider_message_id),
                from_number=req.final_phone,
                payload=payload_snapshot,
                correlation_id=correlation_id,
            )
            if not inserted:
                logger.warning(f"📩 CHAT duplicate ignored provider_message_id={provider_message_id!r} from={req.final_phone}")
                return {
                    "status": "duplicate",
                    "send": False,
                    "text": "",
                    "output": "",
                    "correlation_id": correlation_id,
                }
        except Exception as dedup_err:
            logger.warning(f"📩 CHAT dedup check failed (processing anyway): {dedup_err}")

    # 0. A) Ensure patient reference exists
    try:
        existing_patient = await db.ensure_patient_exists(req.final_phone, tenant_id, req.final_name)

        # --- Lógica de Atribución Meta Ads (First Touch) ---
        if req.referral and existing_patient:
            try:
                # Solo atribuir si no tiene fuente previa o es orgánica
                current_source = existing_patient.get("acquisition_source")
                if not current_source or current_source == "ORGANIC":
                    ref_source = req.referral.get("source_type") or "META_ADS"
                    ref_ad_id = req.referral.get("ad_id")
                    ref_headline = req.referral.get("headline")
                    ref_body = req.referral.get("body")
                    
                    if ref_ad_id:
                        await db.pool.execute("""
                            UPDATE patients 
                            SET acquisition_source = $1, 
                                meta_ad_id = $2, 
                                meta_ad_headline = $3, 
                                meta_ad_body = $4,
                                updated_at = NOW()
                            WHERE id = $5 AND tenant_id = $6
                        """, ref_source, ref_ad_id, ref_headline, ref_body, existing_patient["id"], tenant_id)
                        logger.info(f"🎯 Atribución Meta Ads registrada para paciente {existing_patient['id']}: ad_id={ref_ad_id}")
                        # Disparar enriquecimiento asíncrono (Spec 05)
                        try:
                            from services.tasks import enrich_patient_attribution
                            background_tasks.add_task(
                                enrich_patient_attribution,
                                patient_id=existing_patient["id"],
                                ad_id=ref_ad_id,
                                tenant_id=tenant_id,
                            )
                            logger.info(f"📡 Enriquecimiento Meta Ads encolado para paciente {existing_patient['id']}")
                        except ImportError:
                            logger.debug("services.tasks no disponible para enriquecimiento")
            except Exception as attr_err:
                logger.error(f"⚠️ Error en atribución Meta Ads: {attr_err}")
        # ---------------------------------------------------
        
        # --- Procesamiento de Medios (Spec 19/22) ---
        attachments = []
        if req.media:
            for item in req.media:
                media_url = item.get("url")
                media_type = item.get("type", "document")
                
                # ✅ FIX Spec 22: Descargar media de TODOS los providers (no solo ycloud)
                # Esto previene 404s cuando URLs externas expiran
                if media_url and not media_url.startswith("/media/"):
                    local_url = await download_media(media_url, tenant_id, media_type)
                    item["original_url"] = media_url  # Preservar URL original
                    item["url"] = local_url
                
                attachments.append(item)
        
        # 1. Guardar mensaje del usuario PRIMERO (para no perderlo si hay error)
        # Spec 24: Ensure conversation exists for Buffering
        conv_uuid = await db.get_or_create_conversation(
            tenant_id=tenant_id,
            channel="whatsapp",
            external_user_id=req.final_phone,
            display_name=req.final_name or req.final_phone
        )
        conversation_id = str(conv_uuid)

        # Ahora incluimos attachments y content_attributes
        role = req.role or 'user'
        message_id = await db.append_chat_message(
            from_number=req.final_phone,
            role=role,
            content=req.final_message,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            content_attributes=attachments if attachments else None
        )
        
        # Sincronizar conversación para el preview (Spec 14 / WhatsApp Fix)
        try:
            await db.sync_conversation(
                tenant_id=tenant_id,
                channel="whatsapp",
                external_user_id=req.final_phone,
                last_message=req.final_message or (f"[{attachments[0].get('type').upper()}]" if attachments else "[Media]"),
                is_user=(role == 'user')
            )
        except Exception as sync_err:
            logger.error(f"⚠️ Error syncing WhatsApp preview: {sync_err}")
        
        # Spec 23: Vision Trigger (YCloud/Others)
        if message_id and attachments:
             for att in attachments:
                 if att.get("type") == "image":
                      try:
                          from services.vision_service import process_vision_task
                          background_tasks.add_task(
                              process_vision_task,
                              message_id=message_id,
                              image_url=att["url"],
                              tenant_id=tenant_id
                          )
                          logger.info(f"👁️ Vision task queued for image (YCloud/API): {att['url']}")
                      except Exception as e:
                          logger.error(f"❌ Error queuing vision task: {e}")
        
        # --- Notificar al Frontend (Real-time) ---
        await sio.emit('NEW_MESSAGE', to_json_safe({
            'phone_number': req.final_phone,
            'tenant_id': tenant_id,
            'message': req.final_message,
            'attachments': attachments,
            'role': 'user'
        }))
        # -----------------------------------------

        # 0. B) Verificar si hay intervención humana activa
        handoff_check = await db.pool.fetchrow("""
            SELECT human_handoff_requested, human_override_until
            FROM patients
            WHERE tenant_id = $1 AND phone_number = $2
        """, tenant_id, req.final_phone)
        
        if handoff_check:
            is_handoff_active = handoff_check['human_handoff_requested']
            override_until = handoff_check['human_override_until']
            
            # Si hay override activo y no ha expirado, la IA permanece silenciosa
            if is_handoff_active and override_until:
                # Fix: Robust comparison (Normalize to UTC)
                now_utc = datetime.now(timezone.utc)
                
                # Ensure override_until is aware
                if override_until.tzinfo is None:
                    # Assume stored as naive UTC (or local, but safe fallback to UTC)
                    override_until = override_until.replace(tzinfo=timezone.utc)
                else:
                    override_until = override_until.astimezone(timezone.utc)
                
                if override_until > now_utc:
                    logger.info(f"🔇 IA silenciada para {req.final_phone} hasta {override_until}")
                    # Ya guardamos el mensaje arriba, solo retornamos silencio
                    return {
                        "output": "",  # Sin respuesta
                        "correlation_id": correlation_id,
                        "status": "silenced",
                        "reason": "human_intervention_active"
                    }
                else:
                    # Override expirado, limpiar flags
                    await db.pool.execute("""
                        UPDATE patients
                        SET human_handoff_requested = FALSE,
                            human_override_until = NULL
                        WHERE tenant_id = $1 AND phone_number = $2
                    """, tenant_id, req.final_phone)
        
        # Spec 24: Relay Handling (Async Buffer)
        # Replaces direct agent invocation to allow buffering (16s/20s) and Vision Context injection
        try:
            from services.relay import enqueue_buffer_and_schedule_task
            background_tasks.add_task(enqueue_buffer_and_schedule_task, tenant_id, conversation_id, req.final_phone)
            logger.info(f"⏳ Message buffered for {req.final_phone} (Spec 24 Vision Fix) - conv_id={conversation_id}")
        except ImportError:
            logger.error("❌ services.relay not found")
            return {
                "status": "error",
                "message": "relay_service_not_found"
            }
        except Exception as e:
            logger.error(f"❌ Error enqueuing buffer task: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

        return {
            "status": "queued",
            "send": False,
            "text": "[Procesando...]",
            "correlation_id": correlation_id
        }
        
    except Exception as e:
        logger.exception(f"❌ Error en chat para {req.final_phone}: {e}")
        await db.append_chat_message(
            from_number=req.final_phone,
            role='system',
            content=f"Error interno: {str(e)}",
            correlation_id=correlation_id,
            tenant_id=tenant_id,
        )
        return JSONResponse(
            status_code=500,
            content={"error": "Error interno del orquestador", "correlation_id": correlation_id}
        )

# --- MEDIA SERVING ENDPOINT (Spec 20) ---
@app.get("/media/{tenant_id}/{filename}")
async def serve_local_media(tenant_id: int, filename: str):
    """
    Sirve archivos de media descargados localmente (Spec 19 + Spec 20).
    Path: /media/{tenant_id}/{filename}
    """
    # Seguridad: validar filename para prevenir path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    media_path = os.path.join(os.getcwd(), "media", str(tenant_id), filename)
    
    if not os.path.exists(media_path):
        logger.warning(f"❌ Media file not found: {media_path}")
        raise HTTPException(status_code=404, detail="Not Found")
    
    # Determinar content type
    mime_type, _ = mimetypes.guess_type(filename)
    
    logger.info(f"🖼️ Serving media: {media_path}")
    return FileResponse(
        media_path,
        media_type=mime_type or "application/octet-stream",
        filename=filename
    )


@app.get("/health", tags=["Health"])
async def health():
    """Estado del servicio. Público; usado por orquestadores y monitoreo."""
    return {"status": "ok", "service": "dental-orchestrator"}

if __name__ == "__main__":
    import uvicorn
    # Use socket_app instead of app to support Socket.IO
    uvicorn.run(socket_app, host="0.0.0.0", port=8000)