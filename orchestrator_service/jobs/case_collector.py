"""
Colector de Casos a Revisar — job diario (jobs/case_collector.py).

Detecta por SENALES DETERMINISTAS (sin IA, cero tokens) las conversaciones donde
el bot fallo o quedo trabado y las PERSISTE en la tabla cases_to_review
(idempotente por dia). NO manda mail ni notifica a nadie: los casos se revisan
INTERNAMENTE consultando la tabla (pull), en la cadencia que el equipo elija.
Asi no depende de SMTP/Telegram y la clinica NUNCA ve nada.

Senales de la fase 1:
  - agent_error : chat_conversations.last_agent_error_at  (el bot se cayo)
  - derivation  : chat_conversations.last_derivhumano_at  (el bot derivo a humano)
  - loop        : el asistente repitio el MISMO mensaje 3+ veces en 24h

REVISION: consultar cases_to_review WHERE status='pending'. Comando listo en
scratch/REVISION_CASOS.md (SSH + docker exec psql). Recomendado: cada 3 dias al
principio, luego semanal.

Programacion: corre 08:00 ART (CASE_COLLECTOR_HOUR). Con
CASE_COLLECTOR_RUN_ON_START=1 corre una vez ~30s tras arrancar (para probar).

Fase 2 (futura): sumar clasificacion con IA sobre los candidatos para casos
sutiles (frustracion, obra social mal resuelta, confusion).
"""
import os
import asyncio
import logging
from datetime import datetime, time, timedelta

logger = logging.getLogger("case_collector")

try:
    from zoneinfo import ZoneInfo

    ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
except Exception:  # pragma: no cover
    from datetime import timezone

    ARG_TZ = timezone(timedelta(hours=-3))

RUN_HOUR = int(os.getenv("CASE_COLLECTOR_HOUR", "8"))

CATEGORY_LABELS = {
    "agent_error": "El bot se cayó / no pudo responder",
    "derivation": "El bot derivó a un humano",
    "loop": "El bot repitió el mismo mensaje (loop)",
}


# ---------------------------------------------------------------------------
# Loop / scheduling
# ---------------------------------------------------------------------------


async def case_collector_loop(pool):
    """Loop diario: espera hasta la hora objetivo (ART), corre el colector, repite."""
    if os.getenv("CASE_COLLECTOR_RUN_ON_START") in ("1", "true", "True", "TRUE"):
        await asyncio.sleep(30)
        try:
            await run_case_collector_once(pool)
        except Exception as e:
            logger.error(f"case_collector_run_on_start_error: {e}")

    while True:
        try:
            secs = _seconds_until(RUN_HOUR)
            logger.info(f"case_collector: próxima corrida en {secs / 3600:.1f} h")
            await asyncio.sleep(secs)
            await run_case_collector_once(pool)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"case_collector_loop_error: {e}")
            await asyncio.sleep(3600)  # reintenta en 1h ante error inesperado


def _seconds_until(hour: int) -> float:
    now = datetime.now(ARG_TZ)
    target = datetime.combine(now.date(), time(hour, 0, 0), tzinfo=ARG_TZ)
    if now >= target:
        target = target + timedelta(days=1)
    return (target - now).total_seconds()


# ---------------------------------------------------------------------------
# Colecta
# ---------------------------------------------------------------------------


async def run_case_collector_once(pool) -> int:
    """Una pasada: detecta + persiste. Devuelve # de casos nuevos.

    NO manda nada por fuera: los casos quedan en cases_to_review para revisar
    internamente (pull). Solo loguea un conteo como heads-up.
    """
    tenants = await pool.fetch("SELECT id, clinic_name FROM tenants ORDER BY id ASC")
    total_new = 0
    for t in tenants:
        tid = t["id"]
        try:
            new_cases = await _collect_tenant(pool, tid)
        except Exception as e:
            logger.error(f"case_collector_tenant_{tid}_error: {e}")
            continue
        if new_cases:
            total_new += len(new_cases)
            por_cat = {}
            for c in new_cases:
                por_cat[c["category"]] = por_cat.get(c["category"], 0) + 1
            detalle = ", ".join(
                f"{CATEGORY_LABELS.get(k, k)}={v}" for k, v in por_cat.items()
            )
            logger.info(
                f"case_collector: tenant {tid} ({t['clinic_name']}) — "
                f"{len(new_cases)} caso(s) nuevo(s) [{detalle}]"
            )

    # Total pendiente acumulado (lo que falta revisar), como heads-up.
    try:
        pending = await pool.fetchval(
            "SELECT COUNT(*) FROM cases_to_review WHERE status = 'pending'"
        )
    except Exception:
        pending = None
    logger.info(
        "case_collector: %s caso(s) nuevo(s) hoy | %s pendiente(s) en total "
        "— revisá la tabla cases_to_review (ver scratch/REVISION_CASOS.md)"
        % (total_new, pending if pending is not None else "?")
    )
    return total_new


async def _collect_tenant(pool, tenant_id):
    """Detecta señales para un tenant, persiste con idempotencia y devuelve los NUEVOS."""
    candidates = []

    async with pool.acquire() as conn:
        # 1) agent_error — la conversación quedó marcada por un fallo del bot
        rows = await conn.fetch(
            """SELECT id, external_user_id, display_name, agent_error_reason
               FROM chat_conversations
               WHERE tenant_id = $1
                 AND last_agent_error_at >= NOW() - INTERVAL '24 hours'""",
            tenant_id,
        )
        for r in rows:
            candidates.append(
                {
                    "conversation_id": r["id"],
                    "phone": r["external_user_id"],
                    "name": r["display_name"],
                    "category": "agent_error",
                    "reason": (
                        r["agent_error_reason"]
                        or "El asistente tuvo un error técnico y no pudo responder."
                    )[:500],
                    "severity": "high",
                }
            )

        # 2) derivation — el bot derivó a un humano
        rows = await conn.fetch(
            """SELECT id, external_user_id, display_name
               FROM chat_conversations
               WHERE tenant_id = $1
                 AND last_derivhumano_at >= NOW() - INTERVAL '24 hours'""",
            tenant_id,
        )
        for r in rows:
            candidates.append(
                {
                    "conversation_id": r["id"],
                    "phone": r["external_user_id"],
                    "name": r["display_name"],
                    "category": "derivation",
                    "reason": "El bot derivó la conversación a un humano.",
                    "severity": "medium",
                }
            )

        # 3) loop — el asistente repitió el MISMO mensaje 3+ veces en 24h
        rows = await conn.fetch(
            """SELECT cm.conversation_id, cc.external_user_id, cc.display_name,
                      COUNT(*) AS n
               FROM chat_messages cm
               JOIN chat_conversations cc ON cc.id = cm.conversation_id
               WHERE cm.tenant_id = $1 AND cm.role = 'assistant'
                 AND cm.created_at >= NOW() - INTERVAL '24 hours'
                 AND cm.conversation_id IS NOT NULL
                 AND cm.content IS NOT NULL AND length(trim(cm.content)) > 0
               GROUP BY cm.conversation_id, cc.external_user_id, cc.display_name, cm.content
               HAVING COUNT(*) >= 3
               ORDER BY COUNT(*) DESC""",
            tenant_id,
        )
        for r in rows:
            candidates.append(
                {
                    "conversation_id": r["conversation_id"],
                    "phone": r["external_user_id"],
                    "name": r["display_name"],
                    "category": "loop",
                    "reason": f"El asistente repitió el mismo mensaje {r['n']} veces.",
                    "severity": "medium",
                }
            )

        # Persistir (idempotente por día) y quedarse con los realmente NUEVOS
        inserted = []
        for c in candidates:
            row = await conn.fetchrow(
                """INSERT INTO cases_to_review
                     (tenant_id, conversation_id, phone_number, patient_name,
                      category, reason, severity)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   ON CONFLICT (tenant_id, conversation_id, category, incident_date)
                   DO NOTHING
                   RETURNING id""",
                tenant_id,
                c["conversation_id"],
                c["phone"],
                c["name"],
                c["category"],
                c["reason"],
                c["severity"],
            )
            if not row:
                continue  # ya existía un caso igual hoy (idempotencia)
            c["id"] = row["id"]
            snippet = await _fetch_snippet(conn, tenant_id, c["conversation_id"])
            if snippet:
                await conn.execute(
                    "UPDATE cases_to_review SET snippet = $1 WHERE id = $2",
                    snippet,
                    c["id"],
                )
            inserted.append(c)

    return inserted


async def _fetch_snippet(conn, tenant_id, conversation_id, limit: int = 6) -> str:
    """Últimos N mensajes de la conversación, compactos, para dejar en la ficha del caso."""
    if conversation_id is None:
        return ""
    rows = await conn.fetch(
        """SELECT role, content FROM chat_messages
           WHERE conversation_id = $1 AND tenant_id = $2
           ORDER BY created_at DESC LIMIT $3""",
        conversation_id,
        tenant_id,
        limit,
    )
    label = {
        "user": "PACIENTE",
        "assistant": "PAULA",
        "tool": "TOOL",
        "system": "SISTEMA",
    }
    lines = []
    for r in reversed(rows):
        who = label.get(r["role"], (r["role"] or "?").upper())
        content = (r["content"] or "").strip().replace("\n", " ")
        if len(content) > 200:
            content = content[:200] + "…"
        lines.append(f"{who}: {content}")
    return "\n".join(lines)
