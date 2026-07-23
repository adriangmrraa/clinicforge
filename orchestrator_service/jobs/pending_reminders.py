# -*- coding: utf-8 -*-
"""Aviso por Telegram de PENDIENTES VENCIDOS — pedido Carlos 2026-07-23.

Cierra el hueco más grave del módulo Pendientes: hoy los pendientes (incluidas
las derivaciones del bot y los 'bot falló') vencen en SILENCIO — el campo
reminder_sent_at existía pero ningún job lo usaba.

Este job chequea cada 30 min y manda al Telegram del equipo (mismo canal donde
la Dra. usa Nova) un digest de los pendientes ABIERTOS que ya pasaron su
vencimiento, ordenados por prioridad. Re-avisa cada REMINDER_EVERY_H horas
mientras sigan abiertos (para que "no se pierda el cliente"), estampando
reminder_sent_at para no spamear.

Patrón calcado de jobs/agenda_report.py (chequeo por intervalo, fail-safe,
tenant-scoped). NO usa LLM: es una query + un mensaje de Telegram (costo ≈ 0).
"""

import logging

from jobs.scheduler import scheduler

logger = logging.getLogger("jobs.pending_reminders")

REMINDER_EVERY_H = 3   # re-avisar cada 3h mientras el pendiente siga abierto y vencido
MAX_LIST = 15          # máximo de ítems listados en el mensaje (el resto se resume)
_PRIO_ICON = {"urgente": "🔴", "media": "🟡", "tranqui": "⚪"}


async def check_overdue_pendings():
    """Chequeo por intervalo: avisa los pendientes vencidos de cada tenant con
    bot de Telegram activo. Fail-safe: un error en un tenant no frena a los otros."""
    try:
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

    await send_proactive_message(tenant_id, "\n".join(lines))

    # Estampar el aviso para no repetir hasta dentro de REMINDER_EVERY_H (todos los
    # de la corrida, incluidos los resumidos como "y N más").
    ids = [r["id"] for r in rows]
    await db.pool.execute(
        "UPDATE clinic_pendings SET reminder_sent_at = NOW() "
        "WHERE id = ANY($1::int[]) AND tenant_id = $2",
        ids,
        tenant_id,
    )
    logger.info(f"pending reminder tenant {tenant_id}: avisados {len(rows)} vencidos")


# Chequeo cada 30 min: la función decide por tenant qué avisar.
scheduler.add_job(check_overdue_pendings, interval_seconds=1800, run_at_startup=False)
