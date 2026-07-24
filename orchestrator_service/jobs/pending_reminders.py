# -*- coding: utf-8 -*-
"""Aviso por Telegram de PENDIENTES VENCIDOS — pedido Carlos 2026-07-23.

Cierra el hueco más grave del módulo Pendientes: hoy los pendientes (incluidas
las derivaciones del bot y los 'bot falló') vencen en SILENCIO — el campo
reminder_sent_at existía pero ningún job lo usaba.

Este job manda al Telegram del equipo (mismo canal donde la Dra. usa Nova) UN
digest por día (a la mañana, SEND_HOUR_AR) con los pendientes ABIERTOS que ya
pasaron su vencimiento, ordenados por prioridad. Cada ítem se avisa como máximo
una vez por día (dedupe por reminder_sent_at) — sin repetir ni spamear
(pedido Carlos 2026-07-24: "una vez al día y que no se repitan").

Patrón calcado de jobs/agenda_report.py (chequeo por intervalo, fail-safe,
tenant-scoped). NO usa LLM: es una query + un mensaje de Telegram (costo ≈ 0).
"""

import logging
from datetime import datetime

from jobs.scheduler import scheduler

logger = logging.getLogger("jobs.pending_reminders")

# Pedido Carlos 2026-07-24: el aviso de vencidos va UNA VEZ AL DÍA (no cada 30 min) y sin
# repetir. Se manda un único digest a la mañana (SEND_HOUR_AR) con los pendientes vencidos
# reales; cada ítem se avisa como máximo una vez por día (dedupe por reminder_sent_at).
SEND_HOUR_AR = 9       # hora local Argentina en la que se manda el digest diario
REMINDER_EVERY_H = 20  # no re-avisar el mismo ítem antes de ~1 día (evita repetir dentro del día)
MAX_LIST = 15          # máximo de ítems listados en el mensaje (el resto se resume)
_PRIO_ICON = {"urgente": "🔴", "media": "🟡", "tranqui": "⚪"}


def _es_hora_de_avisar() -> bool:
    """True solo durante la hora local AR configurada → un único envío al día."""
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).hour == SEND_HOUR_AR
    except Exception:
        # Si falla la zona horaria, no arriesgar spam: no enviar.
        return False


async def check_overdue_pendings():
    """Chequeo por intervalo: avisa los pendientes vencidos de cada tenant con bot de
    Telegram activo, pero SOLO una vez al día (durante SEND_HOUR_AR). Fail-safe: un error
    en un tenant no frena a los otros."""
    try:
        if not _es_hora_de_avisar():
            return
        from services.telegram_bot import _bots

        active_tenants = list(_bots.keys())
        if not active_tenants:
            return
        for tenant_id in active_tenants:
            try:
                await _remind_tenant_overdue(tenant_id)
            except Exception as e:
                logger.error(f"pending reminder error tenant {tenant_id}: {e}")
    except Exception as e:
        logger.error(f"check_overdue_pendings global error: {e}")


async def _remind_tenant_overdue(tenant_id: int):
    from db import db

    # --- Pieza 3: escalada por tiempo ---
    # Un pendiente 'media' que está por vencer (o ya venció) sube a 'urgente' para que
    # salte primero en la lista y en el aviso. 'tranqui' se deja (baja prioridad a propósito).
    try:
        await db.pool.execute(
            """
            UPDATE clinic_pendings
            SET priority = 'urgente', updated_at = NOW()
            WHERE tenant_id = $1 AND status = 'abierto' AND priority = 'media'
              AND due_at IS NOT NULL AND due_at < NOW() + INTERVAL '1 hour'
            """,
            tenant_id,
        )
    except Exception as _esc_err:
        logger.warning(f"escalada por tiempo skipped tenant {tenant_id} (non-fatal): {_esc_err}")

    rows = await db.pool.fetch(
        """
        SELECT cp.id, cp.title, cp.due_at, cp.priority, cp.source,
               p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name,
               EXTRACT(EPOCH FROM (NOW() - cp.due_at)) / 3600.0 AS hours_overdue
        FROM clinic_pendings cp
        LEFT JOIN patients p ON p.id = cp.patient_id AND p.tenant_id = cp.tenant_id
        WHERE cp.tenant_id = $1
          AND cp.status = 'abierto'
          AND cp.due_at IS NOT NULL
          AND cp.due_at < NOW()
          AND (cp.reminder_sent_at IS NULL
               OR cp.reminder_sent_at < NOW() - ($2 || ' hours')::interval)
        ORDER BY CASE cp.priority WHEN 'urgente' THEN 0 WHEN 'media' THEN 1 ELSE 2 END,
                 cp.due_at ASC
        LIMIT 100
        """,
        tenant_id,
        str(REMINDER_EVERY_H),
    )
    if not rows:
        return

    lines = [
        f"⏰ <b>Pendientes vencidos ({len(rows)})</b> — hay que resolverlos",
        "",
    ]
    for r in rows[:MAX_LIST]:
        h = float(r["hours_overdue"] or 0)
        atraso = f"{int(h)}h" if h >= 1 else f"{max(1, int(h * 60))}min"
        icon = _PRIO_ICON.get(r["priority"], "🟡")
        pname = (r["patient_name"] or "").strip()
        quien = f" · {pname}" if pname else ""
        lines.append(f"{icon} {r['title']}{quien} <i>(vencido hace {atraso})</i>")
    if len(rows) > MAX_LIST:
        lines.append(f"\n… y {len(rows) - MAX_LIST} más.")
    lines.append("\n👉 Abrí <b>Pendientes</b> en el panel para resolverlos.")

    from services.telegram_notifier import send_proactive_message

    sent = await send_proactive_message(tenant_id, "\n".join(lines))

    # SOLO estampar reminder_sent_at si el aviso REALMENTE se entregó (auditoría 2026-07-24 #2:
    # si no hay destinatarios activos o falla Telegram, no marcar como avisado — se reintenta al
    # próximo ciclo en vez de silenciar el vencido por REMINDER_EVERY_H horas).
    if not sent:
        logger.warning(
            f"pending reminder tenant {tenant_id}: {len(rows)} vencidos NO entregados por Telegram "
            f"(sin destinatarios o error) — no se estampa, se reintenta en el próximo ciclo"
        )
        return

    ids = [r["id"] for r in rows]
    await db.pool.execute(
        "UPDATE clinic_pendings SET reminder_sent_at = NOW() "
        "WHERE id = ANY($1::int[]) AND tenant_id = $2",
        ids,
        tenant_id,
    )
    logger.info(f"pending reminder tenant {tenant_id}: avisados {len(rows)} vencidos")


# Corre cada 30 min, pero la función solo envía durante SEND_HOUR_AR → un digest por día.
scheduler.add_job(check_overdue_pendings, interval_seconds=1800, run_at_startup=False)
