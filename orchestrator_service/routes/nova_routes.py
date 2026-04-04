"""
Nova Dental Assistant — Backend Routes (Fase 1)
Endpoints for health checks, context, sessions, daily analysis, onboarding, and suggestions.
"""

import os
import uuid
import json
import logging
from datetime import datetime, timedelta, date, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query, Depends, Request, Body, Header
from pydantic import BaseModel

from db import db
from core.auth import verify_admin_token, get_resolved_tenant_id

logger = logging.getLogger(__name__)

ARG_TZ = timezone(timedelta(hours=-3))

router = APIRouter(prefix="/admin/nova", tags=["nova"])


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class SessionRequest(BaseModel):
    page: str
    context_summary: str = ""
    patient_id: Optional[int] = None


class CompleteStepRequest(BaseModel):
    step: str
    data: Dict[str, Any] = {}


class ApplySuggestionRequest(BaseModel):
    type: str
    question: str
    answer: str


# ---------------------------------------------------------------------------
# Helper: get_allowed_tenant_ids (duplicated locally to avoid circular import)
# ---------------------------------------------------------------------------

async def _get_allowed_tenant_ids(user_data) -> List[int]:
    """Return list of tenant IDs the user can access. CEO: all tenants."""
    try:
        if user_data.role == "ceo":
            rows = await db.pool.fetch("SELECT id FROM tenants ORDER BY id ASC")
            return [int(r["id"]) for r in rows] if rows else [1]
        tid = await db.pool.fetchval(
            "SELECT tenant_id FROM professionals WHERE user_id = $1",
            uuid.UUID(user_data.user_id),
        )
        if tid is not None:
            return [int(tid)]
        first = await db.pool.fetchval("SELECT id FROM tenants ORDER BY id ASC LIMIT 1")
        return [int(first)] if first is not None else [1]
    except Exception:
        return [1]


# ---------------------------------------------------------------------------
# Helper: Redis access
# ---------------------------------------------------------------------------

def _get_redis():
    """Lazy import to avoid import‐time dependency on relay module."""
    try:
        from services.relay import get_redis
        return get_redis()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helper: get clinic name
# ---------------------------------------------------------------------------

async def _get_clinic_name(tenant_id: int) -> str:
    name = await db.pool.fetchval(
        "SELECT clinic_name FROM tenants WHERE id = $1", tenant_id
    )
    return name or f"Sede {tenant_id}"


# ---------------------------------------------------------------------------
# Helper: stats for a single tenant
# ---------------------------------------------------------------------------

async def _get_stats(tenant_id: int) -> Dict[str, Any]:
    today = date.today()

    appointments_today = await db.pool.fetchval(
        "SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND DATE(appointment_datetime) = $2",
        tenant_id, today,
    ) or 0

    appointments_confirmed = await db.pool.fetchval(
        "SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND DATE(appointment_datetime) = $2 AND status = 'confirmed'",
        tenant_id, today,
    ) or 0

    unconfirmed_today = await db.pool.fetchval(
        "SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND DATE(appointment_datetime) = $2 AND status = 'scheduled'",
        tenant_id, today,
    ) or 0

    patients_total = await db.pool.fetchval(
        "SELECT COUNT(*) FROM patients WHERE tenant_id = $1",
        tenant_id,
    ) or 0

    patients_new_month = await db.pool.fetchval(
        "SELECT COUNT(*) FROM patients WHERE tenant_id = $1 AND created_at >= NOW() - INTERVAL '30 days'",
        tenant_id,
    ) or 0

    pending_payments = await db.pool.fetchval(
        "SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND status = 'completed' AND (payment_status IS NULL OR payment_status = 'pending') AND completed_at >= NOW() - INTERVAL '30 days'",
        tenant_id,
    ) or 0

    cancellations_today = await db.pool.fetchval(
        "SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND DATE(appointment_datetime) = $2 AND status = 'cancelled'",
        tenant_id, today,
    ) or 0

    appointments_week = await db.pool.fetchval(
        "SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND DATE(appointment_datetime) >= $2",
        tenant_id, today - timedelta(days=7),
    ) or 0

    professionals = await db.pool.fetchval(
        "SELECT COUNT(*) FROM professionals WHERE tenant_id = $1 AND is_active = true",
        tenant_id,
    ) or 0

    treatment_types = await db.pool.fetchval(
        "SELECT COUNT(*) FROM treatment_types WHERE tenant_id = $1 AND is_active = true",
        tenant_id,
    ) or 0

    faq_count = await db.pool.fetchval(
        "SELECT COUNT(*) FROM clinic_faqs WHERE tenant_id = $1 AND answer IS NOT NULL AND answer != ''",
        tenant_id,
    ) or 0

    derivations_24h = await db.pool.fetchval(
        "SELECT COUNT(*) FROM chat_messages WHERE tenant_id = $1 AND role = 'tool' AND content ILIKE '%derivhumano%' AND created_at >= NOW() - INTERVAL '24 hours'",
        tenant_id,
    ) or 0

    active_conversations = await db.pool.fetchval(
        "SELECT COUNT(*) FROM chat_conversations WHERE tenant_id = $1 AND status = 'open'",
        tenant_id,
    ) or 0

    return {
        "appointments_today": int(appointments_today),
        "appointments_confirmed": int(appointments_confirmed),
        "unconfirmed_today": int(unconfirmed_today),
        "patients_total": int(patients_total),
        "patients_new_month": int(patients_new_month),
        "pending_payments": int(pending_payments),
        "cancellations_today": int(cancellations_today),
        "appointments_week": int(appointments_week),
        "professionals": int(professionals),
        "treatment_types": int(treatment_types),
        "faq_count": int(faq_count),
        "derivations_24h": int(derivations_24h),
        "active_conversations": int(active_conversations),
    }


# ---------------------------------------------------------------------------
# Helper: operational checks for a tenant (9 checks used by /context)
# ---------------------------------------------------------------------------

async def _get_operational_checks(tenant_id: int, stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    today = date.today()

    # 1. Turnos sin confirmar hoy
    if stats["unconfirmed_today"] > 0:
        checks.append({
            "type": "alert",
            "icon": "calendar",
            "message": f"{stats['unconfirmed_today']} turnos sin confirmar para hoy",
            "action": "confirmar_turnos",
            "weight": 10,
        })

    # 2. Huecos en agenda (manana) — simplified: check if tomorrow has very few appointments
    tomorrow = today + timedelta(days=1)
    tomorrow_appts = await db.pool.fetchval(
        "SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND DATE(appointment_datetime) = $2 AND status IN ('scheduled', 'confirmed')",
        tenant_id, tomorrow,
    ) or 0
    # Check professionals working_hours to detect large gaps
    profs = await db.pool.fetch(
        "SELECT id, working_hours FROM professionals WHERE tenant_id = $1 AND is_active = true AND working_hours IS NOT NULL AND working_hours != '{}'",
        tenant_id,
    )
    if profs and int(tomorrow_appts) == 0:
        checks.append({
            "type": "suggestion",
            "icon": "clock",
            "message": "La agenda de manana esta vacia",
            "action": "ver_agenda",
            "weight": 5,
        })
    elif profs:
        # Estimate available hours vs booked
        tomorrow_minutes = await db.pool.fetchval(
            "SELECT COALESCE(SUM(duration_minutes), 0) FROM appointments WHERE tenant_id = $1 AND DATE(appointment_datetime) = $2 AND status IN ('scheduled', 'confirmed')",
            tenant_id, tomorrow,
        ) or 0
        total_prof_hours = len(profs) * 8  # rough estimate
        booked_hours = int(tomorrow_minutes) / 60
        gap_hours = total_prof_hours - booked_hours
        if gap_hours >= 3:
            checks.append({
                "type": "suggestion",
                "icon": "clock",
                "message": f"Hay aproximadamente {int(gap_hours)}h libres en la agenda de manana",
                "action": "ver_agenda",
                "weight": 5,
            })

    # 3. Recordatorios no enviados (turnos de manana)
    reminders_pending = await db.pool.fetchval(
        "SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND DATE(appointment_datetime) = $2 AND reminder_sent = false AND status IN ('scheduled', 'confirmed')",
        tenant_id, tomorrow,
    ) or 0
    if int(reminders_pending) > 0:
        checks.append({
            "type": "alert",
            "icon": "bell",
            "message": f"{int(reminders_pending)} recordatorios pendientes para turnos de manana",
            "action": "enviar_recordatorios",
            "weight": 8,
        })

    # 4. Facturacion pendiente
    if stats["pending_payments"] > 0:
        checks.append({
            "type": "warning",
            "icon": "credit-card",
            "message": f"{stats['pending_payments']} turnos completados sin cobrar",
            "action": "facturacion_pendiente",
            "weight": 7,
        })

    # 5. Cancelaciones del dia
    if stats["cancellations_today"] > 0:
        checks.append({
            "type": "info",
            "icon": "calendar",
            "message": f"{stats['cancellations_today']} turnos cancelados hoy",
            "action": "ver_agenda",
            "weight": 3,
        })

    # 6. Pacientes nuevos sin anamnesis
    patients_no_anamnesis = await db.pool.fetchval(
        "SELECT COUNT(*) FROM patients WHERE tenant_id = $1 AND (medical_history IS NULL OR medical_history = '{}') AND created_at >= NOW() - INTERVAL '7 days'",
        tenant_id,
    ) or 0
    if int(patients_no_anamnesis) > 0:
        checks.append({
            "type": "suggestion",
            "icon": "user-plus",
            "message": f"{int(patients_no_anamnesis)} pacientes nuevos sin ficha medica completa",
            "action": "ver_pacientes",
            "weight": 4,
        })

    # 7. FAQ insuficientes
    if stats["faq_count"] < 3:
        checks.append({
            "type": "suggestion",
            "icon": "help-circle",
            "message": f"Solo tenes {stats['faq_count']} FAQ. Agrega mas para que el agente responda mejor",
            "action": "agregar_faqs",
            "weight": 5,
        })

    # 8. Derivaciones a humano (ultimas 24h)
    if stats["derivations_24h"] > 3:
        checks.append({
            "type": "alert",
            "icon": "message-circle",
            "message": f"El agente derivo {stats['derivations_24h']} veces en 24h. Puede faltar informacion en las FAQ",
            "action": "agregar_faqs",
            "weight": 6,
        })

    # 9. Pacientes sin control hace 6+ meses
    patients_no_control = await db.pool.fetchval(
        """SELECT COUNT(*) FROM patients p
           WHERE p.tenant_id = $1 AND p.status = 'active'
           AND (p.last_visit IS NULL OR p.last_visit < NOW() - INTERVAL '6 months')
           AND EXISTS (SELECT 1 FROM appointments WHERE patient_id = p.id)""",
        tenant_id,
    ) or 0
    if int(patients_no_control) > 5:
        checks.append({
            "type": "suggestion",
            "icon": "users",
            "message": f"{int(patients_no_control)} pacientes activos sin control hace mas de 6 meses",
            "action": "ver_pacientes",
            "weight": 4,
        })

    # Sort by weight descending
    checks.sort(key=lambda c: c["weight"], reverse=True)
    return checks


# ---------------------------------------------------------------------------
# Helper: health score calculation (0-100)
# ---------------------------------------------------------------------------

async def _calculate_health_score(tenant_id: int, stats: Dict[str, Any]) -> int:
    score = 0

    # --- Configuration (50 pts max) ---
    # Has active professionals (10)
    if stats["professionals"] > 0:
        score += 10

    # Professionals have schedules (10)
    profs_with_hours = await db.pool.fetchval(
        "SELECT COUNT(*) FROM professionals WHERE tenant_id = $1 AND is_active = true AND working_hours IS NOT NULL AND working_hours != '{}'",
        tenant_id,
    ) or 0
    if int(profs_with_hours) > 0 and int(profs_with_hours) >= stats["professionals"]:
        score += 10

    # Has treatment types (10)
    if stats["treatment_types"] > 0:
        score += 10

    # WhatsApp connected (10)
    whatsapp = await db.pool.fetchval(
        "SELECT COUNT(*) FROM credentials WHERE tenant_id = $1 AND category = 'ycloud'",
        tenant_id,
    ) or 0
    if int(whatsapp) > 0:
        score += 10

    # Google Calendar connected (5)
    try:
        gcal = await db.pool.fetchval(
            "SELECT COUNT(*) FROM google_oauth_tokens WHERE tenant_id = $1",
            tenant_id,
        ) or 0
    except Exception:
        gcal = 0
    if int(gcal) > 0:
        score += 5

    # FAQ >= 3 (5)
    if stats["faq_count"] >= 3:
        score += 5

    # --- Operational (50 pts max) ---
    # Appointments this week > 0 (10)
    if stats["appointments_week"] > 0:
        score += 10

    # No unconfirmed today (10)
    if stats["unconfirmed_today"] == 0:
        score += 10

    # No pending payments (10)
    if stats["pending_payments"] == 0:
        score += 10

    # Reminders sent >= 80% for tomorrow (10)
    tomorrow = date.today() + timedelta(days=1)
    tomorrow_total = await db.pool.fetchval(
        "SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND DATE(appointment_datetime) = $2 AND status IN ('scheduled', 'confirmed')",
        tenant_id, tomorrow,
    ) or 0
    tomorrow_reminded = await db.pool.fetchval(
        "SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND DATE(appointment_datetime) = $2 AND reminder_sent = true AND status IN ('scheduled', 'confirmed')",
        tenant_id, tomorrow,
    ) or 0
    if int(tomorrow_total) == 0 or (int(tomorrow_total) > 0 and int(tomorrow_reminded) / int(tomorrow_total) >= 0.8):
        score += 10

    # Derivations <= 3 in 24h (10)
    if stats["derivations_24h"] <= 3:
        score += 10

    return score


# ---------------------------------------------------------------------------
# Helper: full health check for a single tenant
# ---------------------------------------------------------------------------

async def _get_health_check_single(tenant_id: int) -> Dict[str, Any]:
    stats = await _get_stats(tenant_id)
    score = await _calculate_health_score(tenant_id, stats)
    checks = await _get_operational_checks(tenant_id, stats)

    # Add configuration-level checks
    config_checks: List[Dict[str, Any]] = []

    # Professionals without schedules
    profs_no_hours = await db.pool.fetchval(
        "SELECT COUNT(*) FROM professionals WHERE tenant_id = $1 AND is_active = true AND (working_hours IS NULL OR working_hours = '{}')",
        tenant_id,
    ) or 0
    if int(profs_no_hours) > 0:
        config_checks.append({
            "type": "warning",
            "icon": "settings",
            "message": f"{int(profs_no_hours)} profesionales sin horarios configurados",
            "action": "configurar_horarios",
            "weight": 8,
        })

    # Google Calendar
    gcal = await db.pool.fetchval(
        "SELECT COUNT(*) FROM google_oauth_tokens WHERE tenant_id = $1", tenant_id,
    ) or 0
    if int(gcal) == 0:
        config_checks.append({
            "type": "warning",
            "icon": "link",
            "message": "Google Calendar no conectado",
            "action": "conectar_gcal",
            "weight": 6,
        })

    # WhatsApp
    whatsapp = await db.pool.fetchval(
        "SELECT COUNT(*) FROM credentials WHERE tenant_id = $1 AND category = 'ycloud'", tenant_id,
    ) or 0
    if int(whatsapp) == 0:
        config_checks.append({
            "type": "warning",
            "icon": "message-circle",
            "message": "Canal WhatsApp no conectado",
            "action": "conectar_whatsapp",
            "weight": 8,
        })

    # Treatment types
    if stats["treatment_types"] == 0:
        config_checks.append({
            "type": "warning",
            "icon": "clipboard",
            "message": "Sin tipos de tratamiento configurados",
            "action": "configurar_tratamientos",
            "weight": 7,
        })

    # Onboarding check (Check 14)
    onboarding = await _get_onboarding_status(tenant_id)
    if not onboarding["is_complete"]:
        missing_names = [s["label"] for s in onboarding["steps"] if not s["completed"]]
        config_checks.append({
            "type": "warning",
            "icon": "settings",
            "message": f"Configuracion {onboarding['completed_steps']}/8 completa. Faltan: {', '.join(missing_names[:3])}",
            "action": "onboarding",
            "weight": 9,
        })

    all_checks = checks + config_checks
    all_checks.sort(key=lambda c: c["weight"], reverse=True)

    # Completed items
    completed: List[Dict[str, str]] = []
    if stats["professionals"] > 0:
        completed.append({"label": f"{stats['professionals']} profesionales activos"})
    profs_with_hours = await db.pool.fetchval(
        "SELECT COUNT(*) FROM professionals WHERE tenant_id = $1 AND is_active = true AND working_hours IS NOT NULL AND working_hours != '{}'",
        tenant_id,
    ) or 0
    if int(profs_with_hours) > 0:
        completed.append({"label": "Horarios configurados"})
    if stats["treatment_types"] > 0:
        completed.append({"label": f"{stats['treatment_types']} tipos de tratamiento"})
    if stats["patients_total"] > 0:
        completed.append({"label": f"{stats['patients_total']} pacientes registrados"})
    if int(whatsapp) > 0:
        completed.append({"label": "WhatsApp conectado"})
    if int(gcal) > 0:
        completed.append({"label": "Google Calendar conectado"})
    if stats["faq_count"] >= 3:
        completed.append({"label": f"{stats['faq_count']} FAQ configuradas"})
    if stats["appointments_week"] > 0:
        completed.append({"label": f"Turnos esta semana ({stats['appointments_week']})"})

    top_priority = all_checks[0]["message"] if all_checks else None

    # Build pending array from checks for frontend consumption
    pending = [
        {"label": c["message"], "action": c.get("action"), "weight": c.get("weight", 0)}
        for c in all_checks
    ]

    # Score label
    if score >= 80:
        score_label = "Excelente"
    elif score >= 50:
        score_label = "Bien"
    else:
        score_label = "Necesita atencion"

    return {
        "score": score,
        "score_label": score_label,
        "checks": all_checks,
        "completed": completed,
        "pending": pending,
        "top_priority": top_priority,
        "stats": {
            "professionals": stats["professionals"],
            "treatment_types": stats["treatment_types"],
            "total_patients": stats["patients_total"],
            "appointments_today": stats["appointments_today"],
            "appointments_week": stats["appointments_week"],
            "unconfirmed_today": stats["unconfirmed_today"],
            "pending_payments": stats["pending_payments"],
            "cancellations_today": stats["cancellations_today"],
            "derivations_24h": stats["derivations_24h"],
            "faq_count": stats["faq_count"],
        },
    }


# ---------------------------------------------------------------------------
# Helper: greeting builder
# ---------------------------------------------------------------------------

def _build_greeting(
    page: str,
    checks: List[Dict[str, Any]],
    score: int,
    stats: Dict[str, Any],
    onboarding_completed: int = 8,
) -> str:
    # Check onboarding first
    if onboarding_completed < 8:
        missing = 8 - onboarding_completed
        return f"Tu sede tiene {missing} pasos de configuracion pendientes. Queres que te ayude a completarlos?"

    # Score-based prefix
    if score < 50:
        alert_checks = [c for c in checks if c["type"] in ("alert", "warning")]
        if alert_checks:
            return f"La clinica necesita atencion. Lo mas urgente: {alert_checks[0]['message']}"

    if score <= 80:
        suggestions = [c for c in checks if c["type"] == "suggestion"]
        if suggestions:
            return f"Va bien! Pero podes mejorar: {suggestions[0]['message']}"

    # Page-specific
    if page == "agenda":
        n = stats.get("appointments_today", 0)
        unconf = stats.get("unconfirmed_today", 0)
        if n > 0:
            msg = f"Hoy tenes {n} turnos."
            if unconf > 0:
                msg += f" {unconf} sin confirmar."
            return msg
        return "No hay turnos para hoy."

    if page == "pacientes":
        return f"Tenes {stats.get('patients_total', 0)} pacientes. Busco alguno?"

    if page == "chats":
        active = stats.get("active_conversations", 0)
        if active > 0:
            return f"{active} conversaciones activas. Alguna para revisar?"
        return "Sin conversaciones activas. Todo tranquilo."

    if page == "dashboard":
        if score > 80:
            return "Todo en orden. En que te ayudo?"
        return "Hola! Soy Nova. En que te ayudo?"

    if page == "tratamientos":
        return f"Tenes {stats.get('treatment_types', 0)} tipos de tratamiento configurados."

    if page == "configuracion":
        return "Aca podes ajustar integraciones y configuracion de la clinica."

    if page == "analytics":
        return "Queres que te haga un resumen de la semana?"

    return "Hola! Soy Nova. En que te ayudo?"


# ---------------------------------------------------------------------------
# Helper: onboarding status for a single tenant
# ---------------------------------------------------------------------------

ONBOARDING_STEP_ORDER = [
    "professionals",
    "working_hours",
    "treatment_types",
    "whatsapp",
    "google_calendar",
    "faqs",
    "bank_details",
    "consultation_price",
]

ONBOARDING_LABELS = {
    "professionals": "Profesionales",
    "working_hours": "Horarios",
    "treatment_types": "Tipos de tratamiento",
    "whatsapp": "WhatsApp",
    "google_calendar": "Google Calendar",
    "faqs": "FAQs",
    "bank_details": "Datos bancarios",
    "consultation_price": "Precio de consulta",
}


async def _get_onboarding_status(tenant_id: int) -> Dict[str, Any]:
    has_professionals = (await db.pool.fetchval(
        "SELECT COUNT(*) FROM professionals WHERE tenant_id = $1 AND is_active = true", tenant_id,
    ) or 0) > 0

    has_working_hours = (await db.pool.fetchval(
        "SELECT COUNT(*) FROM professionals WHERE tenant_id = $1 AND is_active = true AND working_hours IS NOT NULL AND working_hours != '{}'",
        tenant_id,
    ) or 0) > 0

    has_treatment_types = (await db.pool.fetchval(
        "SELECT COUNT(*) FROM treatment_types WHERE tenant_id = $1 AND is_active = true", tenant_id,
    ) or 0) > 0

    has_whatsapp = (await db.pool.fetchval(
        "SELECT COUNT(*) FROM credentials WHERE tenant_id = $1 AND category = 'ycloud'", tenant_id,
    ) or 0) > 0

    try:
        has_google_calendar = (await db.pool.fetchval(
            "SELECT COUNT(*) FROM google_oauth_tokens WHERE tenant_id = $1", tenant_id,
        ) or 0) > 0
    except Exception:
        has_google_calendar = False

    has_faqs = (await db.pool.fetchval(
        "SELECT COUNT(*) FROM clinic_faqs WHERE tenant_id = $1 AND answer IS NOT NULL AND answer != ''",
        tenant_id,
    ) or 0) >= 3

    tenant = await db.pool.fetchrow(
        "SELECT bank_cbu, bank_alias, consultation_price FROM tenants WHERE id = $1", tenant_id,
    )
    has_bank_details = bool(tenant and (tenant["bank_cbu"] or tenant["bank_alias"]))
    has_consultation_price = bool(tenant and tenant["consultation_price"] is not None)

    step_values = {
        "professionals": has_professionals,
        "working_hours": has_working_hours,
        "treatment_types": has_treatment_types,
        "whatsapp": has_whatsapp,
        "google_calendar": has_google_calendar,
        "faqs": has_faqs,
        "bank_details": has_bank_details,
        "consultation_price": has_consultation_price,
    }

    completed_steps = sum(1 for v in step_values.values() if v)
    total_steps = len(ONBOARDING_STEP_ORDER)

    # Find next incomplete step
    next_step = None
    for s in ONBOARDING_STEP_ORDER:
        if not step_values[s]:
            next_step = s
            break

    steps = [
        {"key": s, "label": ONBOARDING_LABELS[s], "completed": step_values[s]}
        for s in ONBOARDING_STEP_ORDER
    ]

    return {
        "has_professionals": has_professionals,
        "has_working_hours": has_working_hours,
        "has_treatment_types": has_treatment_types,
        "has_whatsapp": has_whatsapp,
        "has_google_calendar": has_google_calendar,
        "has_faqs": has_faqs,
        "has_bank_details": has_bank_details,
        "has_consultation_price": has_consultation_price,
        "completed_steps": completed_steps,
        "total_steps": total_steps,
        "next_step": next_step,
        "is_complete": completed_steps == total_steps,
        "steps": steps,
    }


# ===================================================================
# 1. GET /admin/nova/context
# ===================================================================

@router.get("/context")
async def get_nova_context(
    request: Request,
    page: str = Query("dashboard"),
    patient_id: Optional[int] = Query(None),
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Return contextual data for Nova on the current page.
    CEO without X-Tenant-ID: consolidated across all sedes.
    CEO with X-Tenant-ID or staff: single tenant context.
    """
    try:
        is_ceo = user_data.role == "ceo"
        header_tid = request.headers.get("X-Tenant-ID")
        # If CEO and no specific tenant requested, return consolidated
        wants_consolidated = is_ceo and not header_tid

        if wants_consolidated:
            allowed = await _get_allowed_tenant_ids(user_data)
            sedes = []
            agg_stats: Dict[str, int] = {
                "appointments_today": 0,
                "appointments_confirmed": 0,
                "unconfirmed_today": 0,
                "patients_total": 0,
                "patients_new_month": 0,
                "pending_payments": 0,
                "cancellations_today": 0,
                "appointments_week": 0,
                "professionals": 0,
                "treatment_types": 0,
                "faq_count": 0,
                "derivations_24h": 0,
                "active_conversations": 0,
            }
            all_checks: List[Dict[str, Any]] = []
            total_score = 0

            for tid in allowed:
                s = await _get_stats(tid)
                sc = await _calculate_health_score(tid, s)
                chk = await _get_operational_checks(tid, s)
                cname = await _get_clinic_name(tid)

                top_alert = chk[0]["message"] if chk else None
                sedes.append({
                    "tenant_id": tid,
                    "clinic_name": cname,
                    "score": sc,
                    "top_alert": top_alert,
                })
                total_score += sc
                for c in chk:
                    c["sede"] = cname
                    all_checks.append(c)
                for k in agg_stats:
                    agg_stats[k] += s.get(k, 0)

            consolidated_score = total_score // len(allowed) if allowed else 0
            all_checks.sort(key=lambda c: c["weight"], reverse=True)

            # Greeting for consolidated
            greeting = _build_greeting(page, all_checks, consolidated_score, agg_stats, 8)

            # Daily summary from Redis
            daily_summary = None
            r = _get_redis()
            if r:
                try:
                    raw = await r.get("nova_daily:consolidated")
                    if raw:
                        daily_summary = json.loads(raw)
                except Exception:
                    pass

            return {
                "page": page,
                "checks": all_checks[:15],
                "score": consolidated_score,
                "stats": agg_stats,
                "sedes": sedes,
                "daily_summary": daily_summary,
                "greeting": greeting,
            }

        # Single tenant context
        stats = await _get_stats(tenant_id)
        score = await _calculate_health_score(tenant_id, stats)
        checks = await _get_operational_checks(tenant_id, stats)
        onboarding = await _get_onboarding_status(tenant_id)
        greeting = _build_greeting(page, checks, score, stats, onboarding["completed_steps"])

        # Daily summary from Redis
        daily_summary = None
        r = _get_redis()
        if r:
            try:
                raw = await r.get(f"nova_daily:{tenant_id}")
                if raw:
                    daily_summary = json.loads(raw)
            except Exception:
                pass

        # Sedes array for CEO even on single-tenant view
        sedes = None
        if is_ceo:
            allowed = await _get_allowed_tenant_ids(user_data)
            sedes = []
            for tid in allowed:
                cname = await _get_clinic_name(tid)
                s2 = await _get_stats(tid)
                sc2 = await _calculate_health_score(tid, s2)
                chk2 = await _get_operational_checks(tid, s2)
                top_alert = chk2[0]["message"] if chk2 else None
                sedes.append({
                    "tenant_id": tid,
                    "clinic_name": cname,
                    "score": sc2,
                    "top_alert": top_alert,
                })

        return {
            "page": page,
            "checks": checks,
            "score": score,
            "stats": stats,
            "sedes": sedes,
            "daily_summary": daily_summary,
            "greeting": greeting,
        }

    except Exception as e:
        logger.error(f"nova_context_error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error obteniendo contexto de Nova: {str(e)}")


# ===================================================================
# 2. GET /admin/nova/health-check
# ===================================================================

@router.get("/health-check")
async def get_nova_health_check(
    request: Request,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Full health check with weighted score 0-100.
    CEO: includes consolidated_score + per_sede array.
    """
    try:
        is_ceo = user_data.role == "ceo"
        result = await _get_health_check_single(tenant_id)

        if is_ceo:
            allowed = await _get_allowed_tenant_ids(user_data)
            per_sede = []
            total_score = 0
            all_checks: List[Dict[str, Any]] = []

            for tid in allowed:
                sede_health = await _get_health_check_single(tid)
                cname = await _get_clinic_name(tid)
                per_sede.append({
                    "tenant_id": tid,
                    "clinic_name": cname,
                    "score": sede_health["score"],
                    "checks": sede_health["checks"],
                    "stats": sede_health["stats"],
                })
                total_score += sede_health["score"]
                for chk in sede_health["checks"]:
                    chk_copy = dict(chk)
                    chk_copy["sede"] = cname
                    all_checks.append(chk_copy)

            consolidated_score = total_score // len(allowed) if allowed else 0
            all_checks.sort(key=lambda c: c["weight"], reverse=True)

            result["consolidated_score"] = consolidated_score
            result["per_sede"] = per_sede
            result["global_checks"] = all_checks[:10]
            result["global_stats"] = {
                "total_sedes": len(allowed),
                "sedes_ok": len([s for s in per_sede if s["score"] >= 80]),
                "sedes_warning": len([s for s in per_sede if 50 <= s["score"] < 80]),
                "sedes_critical": len([s for s in per_sede if s["score"] < 50]),
                "appointments_today": sum(s["stats"]["appointments_today"] for s in per_sede),
                "patients_total": sum(s["stats"]["patients_total"] for s in per_sede),
                "pending_payments": sum(s["stats"]["pending_payments"] for s in per_sede),
                "cancellations_today": sum(s["stats"]["cancellations_today"] for s in per_sede),
            }

        return result

    except Exception as e:
        logger.error(f"nova_health_check_error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error en health check: {str(e)}")


# ===================================================================
# 3. POST /admin/nova/session
# ===================================================================

@router.post("/session")
async def create_nova_session(
    body: SessionRequest,
    request: Request,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Create an OpenAI Realtime session for the Nova voice widget.
    Rate limited: max 1 concurrent session per user.
    """
    try:
        r = _get_redis()
        if not r:
            raise HTTPException(status_code=503, detail="Redis no disponible")

        user_id = user_data.user_id

        # Rate limiting: 1 concurrent session per user
        rate_key = f"nova_session:user:{user_id}"
        existing = await r.get(rate_key)
        if existing:
            raise HTTPException(
                status_code=429,
                detail="Ya tenes una sesion activa. Espera a que termine antes de iniciar otra.",
            )

        # Resolve clinic info
        clinic_name = await _get_clinic_name(tenant_id)

        # Build patient context if patient_id provided
        patient_context = "Ningun paciente seleccionado."
        if body.patient_id:
            patient = await db.pool.fetchrow(
                "SELECT id, first_name, last_name, phone_number, dni, insurance_provider, insurance_id FROM patients WHERE id = $1 AND tenant_id = $2",
                body.patient_id, tenant_id,
            )
            if patient:
                patient_context = (
                    f"Paciente: {patient['first_name']} {patient['last_name']} "
                    f"(ID: {patient['id']}, Tel: {patient['phone_number'] or 'N/A'}, "
                    f"DNI: {patient['dni'] or 'N/A'}, "
                    f"Obra social: {patient['insurance_provider'] or 'N/A'} "
                    f"#{patient['insurance_id'] or 'N/A'})"
                )

        # Build sedes context for CEO
        sedes_context = ""
        if user_data.role == "ceo":
            allowed = await _get_allowed_tenant_ids(user_data)
            sede_names = []
            for tid in allowed:
                cname = await _get_clinic_name(tid)
                sede_names.append(f"- {cname} (ID: {tid})")
            sedes_context = f"\n\nSEDES QUE GESTIONA EL CEO:\n" + "\n".join(sede_names)

        # System prompt
        system_prompt = f"""IDIOMA OBLIGATORIO: Espanol argentino. Voseo (vos, sos, tenes). NUNCA cambies de idioma.

Sos Nova, la asistente inteligente de ClinicForge para la clinica "{clinic_name}".
Estas en la pagina: {body.page}. Rol del usuario: {user_data.role}.

PERSONALIDAD:
- Sos proactiva, directa y profesional
- Hablas con confianza pero con calidez
- Usas terminologia dental cuando corresponde
- Sos concisa: maximo 3 oraciones por respuesta
- Cada respuesta termina con una sugerencia o accion concreta

CONTEXTO ACTUAL:
{body.context_summary}

PACIENTE SELECCIONADO:
{patient_context}

PERMISOS DEL ROL:
- CEO: acceso total
- Professional: sus pacientes, sus turnos, registros clinicos
- Secretary: pacientes, turnos, NO registros clinicos detallados

REGLAS:
- Si el usuario pide algo fuera de su rol, deci "No tenes permiso para eso"
- NUNCA inventes datos de pacientes — siempre usa las tools
- Si no encontras un paciente, deci "No encontre a ese paciente"
- Fechas: usa formato argentino (dd/mm/yyyy)
- Horarios: formato 24h (14:00, no 2pm){sedes_context}"""

        session_id = str(uuid.uuid4())

        # Store config in Redis (TTL 360s)
        session_config = {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "user_role": user_data.role,
            "user_email": user_data.email,
            "page": body.page,
            "patient_id": body.patient_id,
            "system_prompt": system_prompt,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await r.setex(
            f"nova_session:{session_id}",
            360,
            json.dumps(session_config, ensure_ascii=False),
        )

        # Mark user as having an active session (TTL 360s)
        await r.setex(rate_key, 360, session_id)

        logger.info(f"nova_session_created: session={session_id} user={user_data.email} page={body.page} tenant={tenant_id}")

        return {"session_id": session_id, "page": body.page}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"nova_session_error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creando sesion: {str(e)}")


# ===================================================================
# 4. GET /admin/nova/daily-analysis
# ===================================================================

@router.get("/daily-analysis")
async def get_nova_daily_analysis(
    consolidated: bool = Query(False),
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Read daily analysis from Redis (generated by cron).
    ?consolidated=true for CEO cross-sede view.
    """
    try:
        r = _get_redis()
        if not r:
            return {"available": False, "analysis": None}

        if consolidated and user_data.role == "ceo":
            raw = await r.get("nova_daily:consolidated")
            if raw:
                analysis = json.loads(raw)
                # Also fetch per-sede stats
                allowed = await _get_allowed_tenant_ids(user_data)
                per_sede_stats = []
                for tid in allowed:
                    sede_raw = await r.get(f"nova_daily:{tid}")
                    if sede_raw:
                        sede_data = json.loads(sede_raw)
                        cname = await _get_clinic_name(tid)
                        per_sede_stats.append({
                            "sede": cname,
                            "tenant_id": tid,
                            **(sede_data.get("operational_stats", {})),
                        })
                return {
                    "available": True,
                    "consolidated": True,
                    "analysis": analysis,
                    "per_sede_stats": per_sede_stats,
                }
            return {"available": False, "consolidated": True, "analysis": None}

        # Per-tenant
        raw = await r.get(f"nova_daily:{tenant_id}")
        if raw:
            analysis = json.loads(raw)
            return {"available": True, "analysis": analysis}

        return {"available": False, "analysis": None}

    except Exception as e:
        logger.error(f"nova_daily_analysis_error: {e}", exc_info=True)
        return {"available": False, "analysis": None}


# ===================================================================
# 5. GET /admin/nova/onboarding-status
# ===================================================================

@router.get("/onboarding-status")
async def get_nova_onboarding_status(
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Returns onboarding progress for the current tenant."""
    try:
        return await _get_onboarding_status(tenant_id)
    except Exception as e:
        logger.error(f"nova_onboarding_status_error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error obteniendo estado de onboarding: {str(e)}")


# ===================================================================
# 6. POST /admin/nova/onboarding/complete-step
# ===================================================================

@router.post("/onboarding/complete-step")
async def complete_onboarding_step(
    body: CompleteStepRequest,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Validate and save configuration for a specific onboarding step.
    Returns updated onboarding status.
    """
    step = body.step
    data = body.data

    if step not in ONBOARDING_STEP_ORDER:
        raise HTTPException(status_code=400, detail=f"Paso no valido: {step}. Validos: {', '.join(ONBOARDING_STEP_ORDER)}")

    try:
        if step == "professionals":
            # Data expected: {first_name, last_name, specialty} or just acknowledgment
            if data.get("first_name") and data.get("last_name"):
                # Check if already exists
                existing = await db.pool.fetchval(
                    "SELECT COUNT(*) FROM professionals WHERE tenant_id = $1 AND is_active = true",
                    tenant_id,
                )
                if int(existing or 0) == 0:
                    # Create a basic professional entry (minimal — full creation via admin UI)
                    await db.pool.execute(
                        """INSERT INTO professionals (tenant_id, first_name, last_name, specialty, is_active, created_at)
                           VALUES ($1, $2, $3, $4, true, NOW())""",
                        tenant_id,
                        data["first_name"],
                        data["last_name"],
                        data.get("specialty", "general"),
                    )

        elif step == "working_hours":
            # Data expected: {professional_id, working_hours: {}}
            prof_id = data.get("professional_id")
            wh = data.get("working_hours")
            if prof_id and wh:
                await db.pool.execute(
                    "UPDATE professionals SET working_hours = $1 WHERE id = $2 AND tenant_id = $3",
                    json.dumps(wh),
                    int(prof_id),
                    tenant_id,
                )

        elif step == "treatment_types":
            # Data expected: {treatments: [{code, name, duration}]}
            treatments = data.get("treatments", [])
            for t in treatments:
                if t.get("code") and t.get("name"):
                    await db.pool.execute(
                        """INSERT INTO treatment_types (tenant_id, code, name, default_duration_minutes, is_active, is_available_for_booking, requires_multiple_sessions, created_at)
                           VALUES ($1, $2, $3, $4, true, true, false, NOW())
                           ON CONFLICT (tenant_id, code) DO NOTHING""",
                        tenant_id,
                        t["code"],
                        t["name"],
                        int(t.get("duration", 30)),
                    )

        elif step == "whatsapp":
            # This typically requires YCloud API key — just validate presence
            if data.get("api_key"):
                from core.credentials import encrypt_value
                encrypted = encrypt_value(data["api_key"])
                await db.pool.execute(
                    """INSERT INTO credentials (tenant_id, name, category, value, scope, created_at)
                       VALUES ($1, 'ycloud_api_key', 'ycloud', $2, 'tenant', NOW())
                       ON CONFLICT (tenant_id, name) DO UPDATE SET value = $2, updated_at = NOW()""",
                    tenant_id,
                    encrypted,
                )

        elif step == "google_calendar":
            # Google Calendar is typically connected via OAuth — this step is informational
            pass

        elif step == "faqs":
            # Data expected: {faqs: [{question, answer}]}
            faqs = data.get("faqs", [])
            for faq in faqs:
                if faq.get("question") and faq.get("answer"):
                    await db.pool.execute(
                        """INSERT INTO clinic_faqs (tenant_id, question, answer, created_at)
                           VALUES ($1, $2, $3, NOW())""",
                        tenant_id,
                        faq["question"],
                        faq["answer"],
                    )

        elif step == "bank_details":
            # Data expected: {bank_cbu?, bank_alias?, bank_holder_name?}
            updates = []
            params = [tenant_id]
            idx = 2
            for field in ["bank_cbu", "bank_alias", "bank_holder_name"]:
                if data.get(field):
                    updates.append(f"{field} = ${idx}")
                    params.append(data[field])
                    idx += 1
            if updates:
                await db.pool.execute(
                    f"UPDATE tenants SET {', '.join(updates)} WHERE id = $1",
                    *params,
                )

        elif step == "consultation_price":
            # Data expected: {price: number}
            price = data.get("price")
            if price is not None:
                await db.pool.execute(
                    "UPDATE tenants SET consultation_price = $1 WHERE id = $2",
                    float(price),
                    tenant_id,
                )

        # Return updated status
        return await _get_onboarding_status(tenant_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"nova_onboarding_complete_step_error: step={step} error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error completando paso '{step}': {str(e)}")


# ===================================================================
# 7. POST /admin/nova/apply-suggestion
# ===================================================================

@router.post("/apply-suggestion")
async def apply_suggestion(
    body: ApplySuggestionRequest,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Apply a suggestion from the daily analysis.
    Supports type='faq' (UPSERT FAQ).
    """
    try:
        if body.type == "faq":
            # Search for existing FAQ with similar question
            existing = await db.pool.fetchrow(
                "SELECT id FROM clinic_faqs WHERE tenant_id = $1 AND question ILIKE $2",
                tenant_id,
                f"%{body.question[:50]}%",
            )
            if existing:
                await db.pool.execute(
                    "UPDATE clinic_faqs SET answer = $1, updated_at = NOW() WHERE id = $2",
                    body.answer,
                    existing["id"],
                )
                logger.info(f"nova_apply_suggestion: FAQ updated id={existing['id']} tenant={tenant_id} by {user_data.email}")
                return {"status": "ok", "action": "faq_updated", "faq_id": existing["id"]}
            else:
                new_id = await db.pool.fetchval(
                    "INSERT INTO clinic_faqs (tenant_id, question, answer, created_at) VALUES ($1, $2, $3, NOW()) RETURNING id",
                    tenant_id,
                    body.question,
                    body.answer,
                )
                logger.info(f"nova_apply_suggestion: FAQ created id={new_id} tenant={tenant_id} by {user_data.email}")
                return {"status": "ok", "action": "faq_created", "faq_id": new_id}

        elif body.type == "prompt_rule":
            # Placeholder for future prompt rule additions
            logger.info(f"nova_apply_suggestion: prompt_rule requested by {user_data.email} tenant={tenant_id}")
            return {"status": "ok", "action": "rule_noted"}

        raise HTTPException(status_code=400, detail=f"Tipo de sugerencia no soportado: {body.type}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"nova_apply_suggestion_error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error aplicando sugerencia: {str(e)}")


# ===================================================================
# 8. POST /admin/nova/telegram-message
# ===================================================================

class TelegramMessageRequest(BaseModel):
    tenant_id: int
    text: str
    chat_id: Optional[int] = None
    display_name: str = ""
    user_role: str = "ceo"
    user_id: str = ""


@router.post("/telegram-message")
async def nova_telegram_message(
    body: TelegramMessageRequest,
    user_data=Depends(verify_admin_token),
):
    """
    Process a Telegram text message through Nova using OpenAI Chat Completions.
    Returns the assistant's response text and a list of tool names called.
    """
    import json as json_mod
    import openai
    from services.nova_tools import execute_nova_tool, nova_tools_for_chat_completions

    tenant_id = body.tenant_id
    user_role = body.user_role
    user_id = body.user_id

    # 1. Build Nova system prompt (re-use the inline prompt pattern from main.py)
    clinic_name = "la clinica"
    try:
        cn = await db.pool.fetchval(
            "SELECT clinic_name FROM tenants WHERE id = $1", tenant_id
        )
        if cn:
            clinic_name = cn
    except Exception:
        pass

    system_prompt = f"""IDIOMA: Espanol argentino con voseo. NUNCA cambies de idioma.

Sos Nova, la inteligencia artificial operativa de "{clinic_name}". No sos un asistente — sos el sistema nervioso central de la clínica.
Página: telegram. Rol: {user_role}. Tenant: {tenant_id}.

PRINCIPIO JARVIS (AGRESIVO — esto es tu ADN):
1. TE PIDEN → EJECUTÁS. No "voy a buscar", no "déjame verificar" — HACELO y respondé con el resultado.
2. NO TE PIDEN PERO VES LA OPORTUNIDAD → SUGERÍ LA ACCIÓN.
3. FALTA UN DATO → INFERILO del contexto. Solo si es IMPOSIBLE inferir → preguntá UNA vez.
4. DESPUÉS DE EJECUTAR → NO pares. Ofrecé el SIGUIENTE paso lógico.
5. NUNCA digas "no puedo", "no tengo acceso", "necesito que me des". TENÉS ACCESO A TODO. BUSCALO.

page=telegram → MODO TELEGRAM:
  Contexto: texto puro (no voz). Respuestas CONCISAS.
  Formatear: **bold** para títulos/datos importantes, listas con •, números con formato $X.XXX
  Máximo ~3000 chars por respuesta (Telegram limita a 4096).
  NO emojis excesivos (1-2 máximo por respuesta).
  Priorizar datos concretos sobre explicaciones largas.
  "Hola" / primer mensaje → resumen_semana automáticamente.
  ACCIONES PRIORITARIAS: todas — mismo poder que en cualquier otra página.

RAZONAMIENTO POR ROL:
- CEO (user_role=ceo): Acceso total. Priorizá datos financieros, analytics, comparativas.
- Professional (user_role=professional): Su agenda, sus pacientes. Priorizá datos clínicos.
- Secretary (user_role=secretary): Agenda, pacientes, cobros. NO analytics CEO.
"""

    # 2. Convert tool schemas to Chat Completions format
    cc_tools = nova_tools_for_chat_completions()

    # 3. OpenAI Chat Completions agentic loop (max 10 rounds)
    client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": body.text},
    ]
    tools_called: List[str] = []
    response_text = ""

    for _round in range(10):
        try:
            completion = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=cc_tools,
                tool_choice="auto",
            )
        except Exception as api_err:
            logger.error(f"nova_telegram_openai_error: {api_err}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"Error de OpenAI: {str(api_err)}")

        msg = completion.choices[0].message

        # No tool calls → final text response
        if not msg.tool_calls:
            response_text = msg.content or ""
            break

        # Append assistant message with tool calls
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        # 4. Execute tool calls
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            tools_called.append(tool_name)
            try:
                args = json_mod.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}

            try:
                tool_result = await execute_nova_tool(
                    name=tool_name,
                    args=args,
                    tenant_id=tenant_id,
                    user_role=user_role,
                    user_id=user_id,
                )
            except Exception as tool_err:
                logger.error(f"nova_telegram_tool_error [{tool_name}]: {tool_err}", exc_info=True)
                tool_result = f"Error ejecutando {tool_name}: {str(tool_err)}"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(tool_result),
                }
            )

    logger.info(
        f"nova_telegram: tenant={tenant_id} role={user_role} "
        f"tools={tools_called} resp_len={len(response_text)}"
    )

    # Audit log — non-fatal
    try:
        await db.pool.execute(
            """INSERT INTO automation_logs
               (tenant_id, log_type, details, created_at)
               VALUES ($1, 'nova_telegram', $2::jsonb, NOW())""",
            tenant_id,
            json_mod.dumps({
                "chat_id": body.chat_id,
                "display_name": body.display_name,
                "user_role": body.user_role,
                "message": body.text[:500],
                "response": response_text[:500] if response_text else "",
                "tools_called": tools_called,
            })
        )
    except Exception:
        pass  # Non-fatal

    return {"response_text": response_text, "tools_called": tools_called}


# ===================================================================
# 9. GET /admin/telegram/verify-user/{tenant_id}/{chat_id}
# ===================================================================

_tg_verify_router = APIRouter(prefix="/admin/telegram", tags=["telegram"])


@_tg_verify_router.get("/verify-user/{tenant_id}/{chat_id}")
async def telegram_verify_user(
    tenant_id: int,
    chat_id: str,
    x_admin_token: str = Header(None),
):
    """
    Verify whether a Telegram chat_id is authorized for a given tenant.
    Called by telegram_service internally — uses X-Admin-Token only (no JWT needed).
    Returns { authorized, user_role, display_name }.
    """
    from core.auth import ADMIN_TOKEN
    from core.credentials import decrypt_value

    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token de infraestructura inválido.")

    rows = await db.pool.fetch(
        """
        SELECT telegram_chat_id, user_role, display_name
        FROM telegram_authorized_users
        WHERE tenant_id = $1 AND is_active = true
        """,
        tenant_id,
    )

    for row in rows:
        try:
            decrypted = decrypt_value(row["telegram_chat_id"])
        except Exception:
            decrypted = row["telegram_chat_id"]

        if str(decrypted).strip() == str(chat_id).strip():
            return {
                "authorized": True,
                "user_role": row["user_role"],
                "display_name": row["display_name"],
            }

    return {"authorized": False, "user_role": None, "display_name": None}
