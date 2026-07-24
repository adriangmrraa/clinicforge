"""Módulo Pendientes con vencimiento (migración 075) — rutas /admin/pendings.

Tareas/notas de la clínica con fecha límite, para que no se olviden chats cuando
interviene la secretaria (pedido Carlos 2026-07-16). El bot también crea pendientes
automáticos al derivar (derivhumano → "seguir la derivación", vence en 24h).

Sovereignty Protocol: TODA query filtra por tenant_id, y toda referencia que venga
del request (patient_id, conversation_id) se valida contra el tenant (ADR D6).

'vencido' NO es un estado almacenado: se deriva de (status='abierto' AND due_at < NOW()).
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.auth import verify_admin_token, get_resolved_tenant_id
from db import db

logger = logging.getLogger("orchestrator")

router = APIRouter()

VALID_STATUSES = ("abierto", "hecho", "cancelado")
VALID_PRIORITIES = ("urgente", "media", "tranqui")
VALID_BUCKETS = ("vencidas", "hoy", "proximas", "sin_fecha", "todas")

# Señales de que el paciente SÍ está esperando algo (pregunta/pedido): si el último
# mensaje tiene alguna de estas, NUNCA es un cierre por más que también diga "gracias".
_WAITING_SIGNALS = re.compile(
    r"\?|\b(turno|cancel|reprogram|precio|presupuesto|cu[aá]nto|cu[aá]ndo|puedo|quiero|"
    r"necesito|quer[ií]a|d[oó]nde|c[oó]mo|llam|whats|manda|env[ií]|pas[aá]|pasame|confirm|"
    r"reserv|saca|agenda|duda|consulta|horario|direcci|ubicaci|disponib|seña|abonar|pagar|"
    r"transfer|foto|comprobante|estudio|radiograf)\b",
    re.IGNORECASE,
)
# Palabras de cierre/cortesía. Si el mensaje (corto) es SOLO esto → conversación cerrada.
_CLOSER_WORDS = re.compile(
    r"\b(gracias|graci|ok+|oka?y|dale|perfecto|genial|buen[ií]simo|listo|barbaro|bárbaro|joya|"
    r"correcto|entendido|igualmente|saludos|abrazo|excelente|de nada|nada|copado|"
    r"buen[ií]sima|de acuerdo|va|vale|👍|👌|🙏|😊|🙌|👏|❤|💕|😀|🤗)\b",
    re.IGNORECASE,
)
_GREETING_ONLY = re.compile(
    r"^(hola|buen d[ií]a|buenas|buenas tardes|buenas noches|buen dia|hey|holis)\W*$",
    re.IGNORECASE,
)


def _is_courtesy_closer(text: Optional[str]) -> bool:
    """True si el último mensaje del paciente es solo un cierre/cortesía (gracias, 👍,
    'todo ok', un saludo suelto) → la conversación está cerrada, NO esperando respuesta.
    Conservador: ante la duda (pregunta, pedido, mensaje largo) devuelve False (lo deja)."""
    t = (text or "").strip().lower()
    if not t:
        return False  # sin preview no podemos saber → lo dejamos
    if _WAITING_SIGNALS.search(t):
        return False  # tiene pregunta/pedido → sigue esperando
    # sacar emojis y signos para ver el "core" de palabras
    core = re.sub(r"[^\w\sáéíóúñü]", "", t, flags=re.UNICODE).strip()
    if not core:
        return True  # solo emojis (👍, 🙏) → cierre
    if _GREETING_ONLY.match(t) and len(core.split()) <= 3:
        return True  # saludo suelto ("buen día")
    # cierre puro y corto (hasta ~7 palabras) que matchea cortesía
    if len(core.split()) <= 7 and _CLOSER_WORDS.search(t):
        return True
    return False


async def _validate_refs(tenant_id: int, patient_id, conversation_id):
    """ADR D6: patient_id y conversation_id, si vienen, deben ser del tenant."""
    if patient_id:
        # Validar el tipo antes de la query (auditoría 2026-07-24 #6: un valor malformado
        # reventaba con 500 en vez de un 400 claro).
        try:
            _pid = int(patient_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="patient_id inválido")
        ok = await db.pool.fetchval(
            "SELECT 1 FROM patients WHERE id = $1 AND tenant_id = $2",
            _pid, tenant_id,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")
    if conversation_id:
        import uuid as _uuid
        try:
            _cid = _uuid.UUID(str(conversation_id))
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(status_code=400, detail="conversation_id inválido")
        ok = await db.pool.fetchval(
            "SELECT 1 FROM chat_conversations WHERE id = $1 AND tenant_id = $2",
            _cid, tenant_id,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")


def _parse_due(value) -> Optional[datetime]:
    """ISO 'YYYY-MM-DDTHH:MM' (o date suelta) → datetime tz-aware; None/'' → None."""
    if value in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            # El panel manda hora local de la clínica (AR, UTC-3).
            from zoneinfo import ZoneInfo

            dt = dt.replace(tzinfo=ZoneInfo("America/Argentina/Buenos_Aires"))
        return dt
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Fecha inválida: {value}")


@router.get(
    "/pendings", dependencies=[Depends(verify_admin_token)], tags=["Pendientes"]
)
async def list_pendings(
    bucket: str = "todas",
    include_closed: bool = False,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    if bucket not in VALID_BUCKETS:
        raise HTTPException(status_code=400, detail="bucket inválido")
    conditions = ["cp.tenant_id = $1"]
    params: list = [tenant_id]
    if not include_closed:
        conditions.append("cp.status = 'abierto'")
    if bucket == "vencidas":
        conditions.append("cp.due_at IS NOT NULL AND cp.due_at < NOW()")
    elif bucket == "hoy":
        conditions.append(
            "cp.due_at IS NOT NULL AND (cp.due_at AT TIME ZONE 'America/Argentina/Buenos_Aires')::date = "
            "(NOW() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date"
        )
    elif bucket == "proximas":
        conditions.append(
            "cp.due_at IS NOT NULL AND (cp.due_at AT TIME ZONE 'America/Argentina/Buenos_Aires')::date > "
            "(NOW() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date"
        )
    elif bucket == "sin_fecha":
        conditions.append("cp.due_at IS NULL")
    rows = await db.pool.fetch(
        f"""
        SELECT cp.id, cp.title, cp.note, cp.due_at, cp.status, cp.priority, cp.assigned_to,
               cp.created_by, cp.source, cp.done_at, cp.created_at,
               cp.patient_id, cp.conversation_id,
               (cp.status = 'abierto' AND cp.due_at IS NOT NULL AND cp.due_at < NOW()) AS is_overdue,
               p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name,
               cc.external_user_id AS chat_phone
        FROM clinic_pendings cp
        LEFT JOIN patients p ON p.id = cp.patient_id AND p.tenant_id = cp.tenant_id
        LEFT JOIN chat_conversations cc ON cc.id = cp.conversation_id AND cc.tenant_id = cp.tenant_id
        WHERE {" AND ".join(conditions)}
        ORDER BY CASE cp.priority WHEN 'urgente' THEN 0 WHEN 'media' THEN 1 ELSE 2 END, cp.due_at ASC NULLS LAST, cp.created_at DESC
        LIMIT 300
        """,
        *params,
    )
    return [dict(r) for r in rows]


@router.get(
    "/pendings/unanswered-chats",
    dependencies=[Depends(verify_admin_token)],
    tags=["Pendientes"],
)
async def unanswered_chats(
    hours: int = 2,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Chats ESPERANDO RESPUESTA de la clínica (caso Pau 2026-07-16): la secretaria
    intervino (IA muda por override humano), el paciente respondió y nadie siguió.

    Detección EN VIVO (sin job ni datos nuevos): override humano vigente + el último
    mensaje es del PACIENTE + pasaron >N horas (default 2) sin respuesta.
    """
    hours = max(1, min(int(hours or 2), 72))
    rows = await db.pool.fetch(
        """
        SELECT cc.id AS conversation_id, cc.external_user_id AS chat_phone,
               cc.display_name, cc.last_message_at, cc.last_message_preview,
               p.id AS patient_id,
               p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name,
               EXTRACT(EPOCH FROM (NOW() - cc.last_message_at))/3600.0 AS hours_waiting
        FROM chat_conversations cc
        LEFT JOIN patients p ON p.id = cc.linked_patient_id AND p.tenant_id = cc.tenant_id
        WHERE cc.tenant_id = $1
          AND cc.human_override_until IS NOT NULL AND cc.human_override_until > NOW()
          AND cc.last_user_message_at IS NOT NULL
          AND cc.last_user_message_at >= cc.last_message_at - INTERVAL '5 seconds'
          AND cc.last_user_message_at < NOW() - ($2 || ' hours')::interval
          -- Excluir números BLOQUEADOS (la clínica decidió no responderles → no son
          -- "esperando respuesta"). Cubre a la Dra./staff, que van en la lista de bloqueo.
          AND NOT EXISTS (
              SELECT 1 FROM blocked_phone_numbers b
              WHERE b.tenant_id = cc.tenant_id AND b.is_active = true
                AND RIGHT(REGEXP_REPLACE(COALESCE(b.phone_digits, ''), '[^0-9]', '', 'g'), 10)
                    = RIGHT(REGEXP_REPLACE(COALESCE(cc.external_user_id, ''), '[^0-9]', '', 'g'), 10)
          )
        ORDER BY cc.last_user_message_at ASC
        LIMIT 50
        """,
        tenant_id,
        str(hours),
    )
    result = [dict(r) for r in rows]

    # Excluir también los números autorizados para TAREAS (tenants.config->'staff_task_phones'):
    # sus "Tarea:" son comandos de la Dra./staff, no consultas de paciente esperando respuesta.
    # (Caso Carlos 2026-07-24: su "Tarea:" desde el teléfono quedaba fijado acá sin poder sacarlo.)
    try:
        import json as _json
        import re as _re

        cfg = await db.pool.fetchval(
            "SELECT config->'staff_task_phones' FROM tenants WHERE id = $1", tenant_id
        )
        phones = (cfg if isinstance(cfg, list) else _json.loads(cfg)) if cfg else []
        staff10 = {_re.sub(r"\D", "", str(p))[-10:] for p in phones if p}
        if staff10:
            result = [
                r for r in result
                if _re.sub(r"\D", "", str(r.get("chat_phone") or ""))[-10:] not in staff10
            ]
    except Exception:
        pass

    # Filtro de CORTESÍA: sacar los cierres (gracias / 👍 / "todo ok" / saludo suelto). No son
    # casos esperando respuesta sino conversaciones ya terminadas (pedido Carlos 2026-07-24:
    # "hay falsos casos fijados, son casos cerrados"). Los reales (pregunta, pedido, "?") quedan.
    result = [r for r in result if not _is_courtesy_closer(r.get("last_message_preview"))]
    return result


@router.get(
    "/pendings/summary",
    dependencies=[Depends(verify_admin_token)],
    tags=["Pendientes"],
)
async def pendings_summary(tenant_id: int = Depends(get_resolved_tenant_id)):
    """Contadores para el badge del sidebar: vencidas / para hoy / abiertas."""
    row = await db.pool.fetchrow(
        """
        SELECT
          COUNT(*) FILTER (WHERE due_at IS NOT NULL AND due_at < NOW()) AS vencidas,
          COUNT(*) FILTER (
            WHERE due_at IS NOT NULL
              AND (due_at AT TIME ZONE 'America/Argentina/Buenos_Aires')::date =
                  (NOW() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
              AND due_at >= NOW()
          ) AS hoy,
          COUNT(*) AS abiertas
        FROM clinic_pendings
        WHERE tenant_id = $1 AND status = 'abierto'
        """,
        tenant_id,
    )
    return dict(row)


@router.post(
    "/pendings", dependencies=[Depends(verify_admin_token)], tags=["Pendientes"]
)
async def create_pending(
    data: Dict[str, Any],
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    title = (data.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title es obligatorio")
    patient_id = data.get("patient_id") or None
    conversation_id = data.get("conversation_id") or None
    await _validate_refs(tenant_id, patient_id, conversation_id)
    # Botón 📌 del chat (pedido Carlos: crear el pendiente SIN cargar nada a mano):
    # el front manda solo chat_phone y acá resolvemos paciente + conversación por
    # teléfono, SIEMPRE tenant-scoped (los resueltos son del tenant por la query misma).
    chat_phone = (data.get("chat_phone") or "").strip() or None
    if chat_phone:
        if not patient_id:
            patient_id = await db.pool.fetchval(
                "SELECT id FROM patients WHERE tenant_id = $1 AND "
                "regexp_replace(COALESCE(phone_number,''),'[^0-9]','','g') = regexp_replace($2,'[^0-9]','','g') LIMIT 1",
                tenant_id, chat_phone,
            )
        if not conversation_id:
            conversation_id = await db.pool.fetchval(
                "SELECT id FROM chat_conversations WHERE tenant_id = $1 AND "
                "regexp_replace(COALESCE(external_user_id,''),'[^0-9]','','g') = regexp_replace($2,'[^0-9]','','g') "
                "ORDER BY updated_at DESC LIMIT 1",
                tenant_id, chat_phone,
            )
    # Dedupe de pendientes ligados a un chat/paciente (pedido Carlos 2026-07-24: "deben
    # aparecer una vez"): si ya hay uno ABIERTO igual creado hace poco, devolver ese en vez
    # de duplicar. Cubre doble-clic y reintentos por timeout (caso 3× "Seguir chat con Lucas").
    if patient_id or conversation_id:
        _dup = await db.pool.fetchval(
            """
            SELECT id FROM clinic_pendings
            WHERE tenant_id = $1 AND status = 'abierto' AND lower(title) = lower($2)
              AND created_at > NOW() - INTERVAL '6 hours'
              AND ( ($3::int IS NOT NULL AND patient_id = $3::int)
                 OR ($4::uuid IS NOT NULL AND conversation_id = $4::uuid) )
            ORDER BY created_at DESC LIMIT 1
            """,
            tenant_id, title[:200],
            int(patient_id) if patient_id else None,
            conversation_id,
        )
        if _dup:
            logger.info("pendiente DEDUP: ya existe #%s '%s' tenant=%s → no duplico", _dup, title[:50], tenant_id)
            return {"id": _dup, "deduped": True}

    row = await db.pool.fetchrow(
        """
        INSERT INTO clinic_pendings
            (tenant_id, title, note, due_at, patient_id, conversation_id,
             assigned_to, created_by, source, priority)
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'staff', $8, $9)
        RETURNING id
        """,
        tenant_id,
        title[:200],
        (data.get("note") or "").strip() or None,
        _parse_due(data.get("due_at")),
        int(patient_id) if patient_id else None,
        conversation_id,
        (data.get("assigned_to") or "").strip()[:120] or None,
        (data.get("source") or "manual").strip()[:40],
        data.get("priority") if data.get("priority") in VALID_PRIORITIES else "media",
    )
    logger.info("pendiente creado: id=%s tenant=%s '%s'", row["id"], tenant_id, title[:50])
    return {"id": row["id"]}


@router.patch(
    "/pendings/{pending_id}",
    dependencies=[Depends(verify_admin_token)],
    tags=["Pendientes"],
)
async def update_pending(
    pending_id: int,
    data: Dict[str, Any],
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    current = await db.pool.fetchrow(
        "SELECT status FROM clinic_pendings WHERE id = $1 AND tenant_id = $2",
        pending_id,
        tenant_id,
    )
    if not current:
        raise HTTPException(status_code=404, detail="Pendiente no encontrado")

    sets, params = [], []

    def _set(col, value):
        params.append(value)
        sets.append(f"{col} = ${len(params)}")

    new_status = data.get("status")
    if new_status is not None and new_status != current["status"]:
        if new_status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Estado inválido")
        _set("status", new_status)
        _set("done_at", datetime.now(timezone.utc) if new_status == "hecho" else None)
    if "title" in data:
        t = (str(data.get("title") or "")).strip()
        if not t:
            raise HTTPException(status_code=400, detail="title no puede quedar vacío")
        _set("title", t[:200])
    if "note" in data:
        _set("note", (str(data.get("note") or "")).strip() or None)
    if "due_at" in data:
        _set("due_at", _parse_due(data.get("due_at")))
    if "priority" in data:
        if data.get("priority") not in VALID_PRIORITIES:
            raise HTTPException(status_code=400, detail="Prioridad inválida")
        _set("priority", data.get("priority"))
    if "assigned_to" in data:
        _set("assigned_to", (str(data.get("assigned_to") or "")).strip()[:120] or None)

    if not sets:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    sets.append("updated_at = NOW()")

    params.extend([pending_id, tenant_id])
    row = await db.pool.fetchrow(
        f"""
        UPDATE clinic_pendings SET {", ".join(sets)}
        WHERE id = ${len(params) - 1} AND tenant_id = ${len(params)}
        RETURNING id, status
        """,
        *params,
    )
    return dict(row)
