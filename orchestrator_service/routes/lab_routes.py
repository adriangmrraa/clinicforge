"""
Módulo Laboratorio (F2-4 L1) — labs + lab_cases.

Tablero de trabajos de laboratorio: estados
pendiente_envio → enviado → recibido → a_ajustar → colocado (/cancelado),
con sellado automático de fechas por transición y contador de re-trabajos.

Referencias de diseño: Dentalink (estados + pago por solicitud),
Open Dental (vínculo con turnos), Crownbeam (semáforo por vencimiento).
Ver scratch/PLAN_LABORATORIO.md.

Sovereignty Protocol: TODA query filtra por tenant_id.
"""

import asyncio
import logging
from datetime import date
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

import db
from core.auth import verify_admin_token, get_resolved_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_STATUSES = (
    "pendiente_envio",
    "enviado",
    "recibido",
    "a_ajustar",
    "colocado",
    "cancelado",
)

# Campos de fecha que se sellan solos al entrar a cada estado (si vienen vacíos)
STATUS_DATE_STAMP = {
    "enviado": "sent_at",
    "recibido": "received_at",
    "a_ajustar": "tried_at",
    "colocado": "placed_at",
}


def _parse_date(value):
    """'YYYY-MM-DD' → date; None/'' → None. Lanza 400 si el formato es inválido."""
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Fecha inválida: {value!r} (usar YYYY-MM-DD)"
        )


# ---------------------------------------------------------------------------
# ABM de laboratorios
# ---------------------------------------------------------------------------


@router.get("/labs", dependencies=[Depends(verify_admin_token)], tags=["Laboratorio"])
async def list_labs(
    include_inactive: bool = Query(False),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    rows = await db.pool.fetch(
        f"""
        SELECT id, name, email, phone, notes, is_active
        FROM labs
        WHERE tenant_id = $1 {"" if include_inactive else "AND is_active = true"}
        ORDER BY name
        """,
        tenant_id,
    )
    return {"labs": [dict(r) for r in rows]}


@router.post("/labs", dependencies=[Depends(verify_admin_token)], tags=["Laboratorio"])
async def create_lab(
    data: Dict[str, Any],
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")
    existing = await db.pool.fetchval(
        "SELECT id FROM labs WHERE tenant_id = $1 AND LOWER(name) = LOWER($2)",
        tenant_id,
        name,
    )
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe un laboratorio con ese nombre")
    row = await db.pool.fetchrow(
        """
        INSERT INTO labs (tenant_id, name, email, phone, notes)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, name, email, phone, notes, is_active
        """,
        tenant_id,
        name,
        (data.get("email") or "").strip() or None,
        (data.get("phone") or "").strip() or None,
        (data.get("notes") or "").strip() or None,
    )
    return dict(row)


@router.patch(
    "/labs/{lab_id}", dependencies=[Depends(verify_admin_token)], tags=["Laboratorio"]
)
async def update_lab(
    lab_id: int,
    data: Dict[str, Any],
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    allowed = ("name", "email", "phone", "notes", "is_active")
    sets, params = [], []
    for key in allowed:
        if key in data:
            params.append(data.get(key))
            sets.append(f"{key} = ${len(params)}")
    if not sets:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    params.extend([lab_id, tenant_id])
    row = await db.pool.fetchrow(
        f"""
        UPDATE labs SET {", ".join(sets)}
        WHERE id = ${len(params) - 1} AND tenant_id = ${len(params)}
        RETURNING id, name, email, phone, notes, is_active
        """,
        *params,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Laboratorio no encontrado")
    return dict(row)


# ---------------------------------------------------------------------------
# Trabajos de laboratorio
# ---------------------------------------------------------------------------


@router.get(
    "/lab-cases", dependencies=[Depends(verify_admin_token)], tags=["Laboratorio"]
)
async def list_lab_cases(
    status: str = Query(None),
    lab_id: int = Query(None),
    professional_id: int = Query(None),
    patient_id: int = Query(None),
    overdue: bool = Query(False),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    conditions = ["lc.tenant_id = $1"]
    params: list = [tenant_id]
    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Estado inválido")
        params.append(status)
        conditions.append(f"lc.status = ${len(params)}")
    if lab_id:
        params.append(lab_id)
        conditions.append(f"lc.lab_id = ${len(params)}")
    if professional_id:
        params.append(professional_id)
        conditions.append(f"lc.professional_id = ${len(params)}")
    if patient_id:
        params.append(patient_id)
        conditions.append(f"lc.patient_id = ${len(params)}")
    if overdue:
        conditions.append(
            "lc.status IN ('enviado', 'a_ajustar') AND lc.promised_at < CURRENT_DATE"
        )

    rows = await db.pool.fetch(
        f"""
        SELECT
            lc.*,
            p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name,
            p.phone_number AS patient_phone,
            prof.first_name || ' ' || COALESCE(prof.last_name, '') AS professional_name,
            l.name AS lab_name,
            (lc.status IN ('enviado', 'a_ajustar')
             AND lc.promised_at IS NOT NULL
             AND lc.promised_at < CURRENT_DATE) AS is_overdue
        FROM lab_cases lc
        JOIN patients p ON p.id = lc.patient_id AND p.tenant_id = lc.tenant_id
        LEFT JOIN professionals prof
            ON prof.id = lc.professional_id AND prof.tenant_id = lc.tenant_id
        LEFT JOIN labs l ON l.id = lc.lab_id AND l.tenant_id = lc.tenant_id
        WHERE {" AND ".join(conditions)}
        ORDER BY
            (lc.status = 'colocado' OR lc.status = 'cancelado') ASC,
            lc.promised_at ASC NULLS LAST,
            lc.created_at DESC
        LIMIT 500
        """,
        *params,
    )
    out = []
    for r in rows:
        d = dict(r)
        for k in ("sent_at", "promised_at", "received_at", "tried_at", "placed_at"):
            if d.get(k) is not None:
                d[k] = str(d[k])
        if d.get("cost") is not None:
            d["cost"] = float(d["cost"])
        for k in ("created_at", "updated_at"):
            if d.get(k) is not None:
                d[k] = d[k].isoformat()
        out.append(d)
    overdue_count = sum(1 for d in out if d.get("is_overdue"))
    return {"cases": out, "overdue_count": overdue_count}


@router.post(
    "/lab-cases", dependencies=[Depends(verify_admin_token)], tags=["Laboratorio"]
)
async def create_lab_case(
    data: Dict[str, Any],
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    try:
        patient_id = int(data.get("patient_id") or 0)
    except (TypeError, ValueError):
        patient_id = 0
    work_type = (data.get("work_type") or "").strip()
    if not patient_id or not work_type:
        raise HTTPException(
            status_code=400, detail="patient_id y work_type son obligatorios"
        )
    # Sovereignty: el paciente debe ser del tenant
    owner_ok = await db.pool.fetchval(
        "SELECT 1 FROM patients WHERE id = $1 AND tenant_id = $2",
        patient_id,
        tenant_id,
    )
    if not owner_ok:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    status = data.get("status") or "pendiente_envio"
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Estado inválido")
    sent_at = _parse_date(data.get("sent_at"))
    if status == "enviado" and sent_at is None:
        sent_at = date.today()

    row = await db.pool.fetchrow(
        """
        INSERT INTO lab_cases (
            tenant_id, patient_id, professional_id, lab_id, work_type,
            tooth_numbers, shade, status, sent_at, promised_at,
            origin_appointment_id, cost, notes
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        RETURNING id
        """,
        tenant_id,
        patient_id,
        data.get("professional_id") or None,
        data.get("lab_id") or None,
        work_type[:80],
        (data.get("tooth_numbers") or "").strip()[:120] or None,
        (data.get("shade") or "").strip()[:40] or None,
        status,
        sent_at,
        _parse_date(data.get("promised_at")),
        (str(data.get("origin_appointment_id") or "").strip()[:64]) or None,
        float(data["cost"]) if data.get("cost") not in (None, "") else None,
        (data.get("notes") or "").strip() or None,
    )
    logger.info("lab_case creado: id=%s tenant=%s paciente=%s", row["id"], tenant_id, patient_id)
    return {"id": row["id"]}


@router.patch(
    "/lab-cases/{case_id}",
    dependencies=[Depends(verify_admin_token)],
    tags=["Laboratorio"],
)
async def update_lab_case(
    case_id: int,
    data: Dict[str, Any],
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    current = await db.pool.fetchrow(
        "SELECT status, rework_count FROM lab_cases WHERE id = $1 AND tenant_id = $2",
        case_id,
        tenant_id,
    )
    if not current:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    sets, params = [], []

    def _set(col, value):
        params.append(value)
        sets.append(f"{col} = ${len(params)}")

    new_status = data.get("status")
    if new_status is not None and new_status != current["status"]:
        if new_status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Estado inválido")
        _set("status", new_status)
        # Sellado automático de la fecha del estado (si el caller no la manda)
        stamp_col = STATUS_DATE_STAMP.get(new_status)
        if stamp_col and data.get(stamp_col) in (None, ""):
            _set(stamp_col, date.today())
        if new_status == "a_ajustar":
            _set("rework_count", (current["rework_count"] or 0) + 1)

    for col in ("work_type", "tooth_numbers", "shade", "notes",
                "origin_appointment_id", "placement_appointment_id"):
        if col in data:
            val = (str(data.get(col) or "").strip()) or None
            _set(col, val)
    for col in ("lab_id", "professional_id"):
        if col in data:
            _set(col, data.get(col) or None)
    for col in ("sent_at", "promised_at", "received_at", "tried_at", "placed_at"):
        if col in data and data.get(col) not in (None, ""):
            _set(col, _parse_date(data.get(col)))
    if "cost" in data:
        _set("cost", float(data["cost"]) if data.get("cost") not in (None, "") else None)
    if "lab_paid" in data:
        _set("lab_paid", bool(data.get("lab_paid")))

    if not sets:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    sets.append("updated_at = NOW()")

    params.extend([case_id, tenant_id])
    row = await db.pool.fetchrow(
        f"""
        UPDATE lab_cases SET {", ".join(sets)}
        WHERE id = ${len(params) - 1} AND tenant_id = ${len(params)}
        RETURNING id, status, rework_count
        """,
        *params,
    )
    return dict(row)


# ---------------------------------------------------------------------------
# L2 — Acciones manuales (regla Carlos: nada automático sin control)
# ---------------------------------------------------------------------------


@router.post(
    "/lab-cases/{case_id}/notify-patient",
    dependencies=[Depends(verify_admin_token)],
    tags=["Laboratorio"],
)
async def notify_patient_case(
    case_id: int,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    L2: botón "Avisar al paciente" — WhatsApp de que llegó su trabajo.
    Espeja el patrón del feedback post-consulta: ResponseSender si hay
    conversación (queda en el chat), fallback YCloud directo.
    """
    row = await db.pool.fetchrow(
        """
        SELECT lc.id, lc.work_type,
               p.first_name, p.phone_number, p.guardian_phone
        FROM lab_cases lc
        JOIN patients p ON p.id = lc.patient_id AND p.tenant_id = lc.tenant_id
        WHERE lc.id = $1 AND lc.tenant_id = $2
        """,
        case_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    phone = (row["phone_number"] or "").strip()
    # Menores -M{N}: el WhatsApp real es el del padre/madre
    if "-M" in phone and (row["guardian_phone"] or "").strip():
        phone = row["guardian_phone"].strip()
    if not phone or phone.startswith("SIN-TEL"):
        raise HTTPException(
            status_code=400, detail="El paciente no tiene teléfono válido"
        )

    first_name = (row["first_name"] or "").strip() or "paciente"
    work = (row["work_type"] or "trabajo").lower()
    message = (
        f"¡Hola {first_name}! 😊 Te avisamos que ya llegó tu {work} del "
        "laboratorio. Escribinos por acá así coordinamos el turno de colocación."
    )

    sent_ok = False
    try:
        conv = await db.pool.fetchrow(
            "SELECT id, provider, channel, external_account_id, external_chatwoot_id "
            "FROM chat_conversations WHERE tenant_id = $1 AND external_user_id = $2 "
            "ORDER BY updated_at DESC LIMIT 1",
            tenant_id,
            phone,
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
            sent_ok = True
        else:
            from core.credentials import (
                get_tenant_credential,
                YCLOUD_API_KEY,
                YCLOUD_WHATSAPP_NUMBER,
            )
            from ycloud_client import YCloudClient

            api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
            biz_num = await get_tenant_credential(tenant_id, YCLOUD_WHATSAPP_NUMBER)
            if api_key:
                yc = YCloudClient(api_key=api_key, business_number=biz_num)
                await yc.send_text_message(to=phone, text=message)
                sent_ok = True
    except Exception as exc:
        logger.error("notify-patient lab_case %s: %s", case_id, exc, exc_info=True)

    if not sent_ok:
        raise HTTPException(
            status_code=502,
            detail="No se pudo enviar el WhatsApp (sin conversación ni YCloud configurado)",
        )
    await db.pool.execute(
        "UPDATE lab_cases SET patient_notified_at = NOW(), updated_at = NOW() "
        "WHERE id = $1 AND tenant_id = $2",
        case_id,
        tenant_id,
    )
    logger.info("L2 aviso-paciente enviado: lab_case=%s tenant=%s", case_id, tenant_id)
    return {"sent": True}


@router.post(
    "/lab-cases/{case_id}/chase-lab",
    dependencies=[Depends(verify_admin_token)],
    tags=["Laboratorio"],
)
async def chase_lab_case(
    case_id: int,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """L2: botón "Reclamar al lab" — email pidiendo estado de un trabajo vencido."""
    row = await db.pool.fetchrow(
        """
        SELECT lc.work_type, lc.tooth_numbers, lc.sent_at, lc.promised_at,
               p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name,
               l.name AS lab_name, l.email AS lab_email,
               t.clinic_name
        FROM lab_cases lc
        JOIN patients p ON p.id = lc.patient_id AND p.tenant_id = lc.tenant_id
        LEFT JOIN labs l ON l.id = lc.lab_id AND l.tenant_id = lc.tenant_id
        JOIN tenants t ON t.id = lc.tenant_id
        WHERE lc.id = $1 AND lc.tenant_id = $2
        """,
        case_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    lab_email = (row["lab_email"] or "").strip()
    if not lab_email:
        raise HTTPException(
            status_code=400,
            detail="El laboratorio no tiene email cargado (Laboratorios → editar)",
        )

    clinic = row["clinic_name"] or "la clínica"
    piezas = f" — piezas {row['tooth_numbers']}" if row["tooth_numbers"] else ""
    subject = f"Consulta de estado — {row['work_type']} ({clinic})"
    html = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222">
      <p>Hola {row['lab_name'] or ''},</p>
      <p>Les escribimos de <b>{clinic}</b> por el siguiente trabajo:</p>
      <ul>
        <li><b>Trabajo:</b> {row['work_type']}{piezas}</li>
        <li><b>Paciente:</b> {row['patient_name']}</li>
        <li><b>Enviado:</b> {row['sent_at'] or '—'}</li>
        <li><b>Fecha prometida:</b> {row['promised_at'] or '—'}</li>
      </ul>
      <p>¿Nos confirman el estado y la fecha estimada de entrega?</p>
      <p>¡Gracias!<br>{clinic}</p>
    </div>
    """

    from email_service import EmailService

    sent = await asyncio.to_thread(EmailService().send_html, [lab_email], subject, html)
    if not sent:
        raise HTTPException(
            status_code=502,
            detail="No se pudo enviar el email (SMTP no configurado o falló)",
        )
    await db.pool.execute(
        "UPDATE lab_cases SET lab_chased_at = NOW(), updated_at = NOW() "
        "WHERE id = $1 AND tenant_id = $2",
        case_id,
        tenant_id,
    )
    logger.info("L2 reclamo-lab enviado: lab_case=%s a=%s", case_id, lab_email)
    return {"sent": True}
