# -*- coding: utf-8 -*-
"""Aviso por Telegram de TRABAJOS DE LABORATORIO vencidos — pedido Carlos 2026-07-24.

Cierra el hueco del semáforo: hoy un trabajo se pone ROJO en el tablero pero nadie
se entera si no abre la pantalla. Este job manda UN digest por día (a la mañana)
al Telegram del equipo con los trabajos que se pasaron de la fecha prometida y
los que están por vencer, para que la clínica reclame al laboratorio a tiempo.

Costo: CERO en Meta — Telegram es interno (no es un mensaje al paciente).

Patrón calcado de jobs/pending_reminders.py (un envío diario, tenant-scoped,
fail-safe, sin LLM).
"""

import logging
from datetime import datetime

from jobs.scheduler import scheduler

logger = logging.getLogger("jobs.lab_reminders")

SEND_HOUR_AR = 9      # hora local Argentina del digest diario
DUE_SOON_DAYS = 3     # "por vencer": faltan N días o menos para la fecha prometida
MAX_LIST = 12         # máximo de ítems listados por sección


def _es_hora_de_avisar() -> bool:
    """True solo durante la hora local AR configurada → un único envío al día."""
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).hour == SEND_HOUR_AR
    except Exception:
        # Si falla la zona horaria, no arriesgar spam: no enviar.
        return False


async def check_overdue_lab_cases():
    """Chequeo por intervalo: avisa los trabajos vencidos/por vencer de cada tenant
    con bot de Telegram activo, UNA vez al día. Fail-safe por tenant."""
    try:
        if not _es_hora_de_avisar():
            return
        from services.telegram_bot import _bots

        active_tenants = list(_bots.keys())
        if not active_tenants:
            return
        for tenant_id in active_tenants:
            try:
                await _remind_tenant_lab(tenant_id)
            except Exception as e:
                logger.error(f"lab reminder error tenant {tenant_id}: {e}")
    except Exception as e:
        logger.error(f"check_overdue_lab_cases global error: {e}")


async def _remind_tenant_lab(tenant_id: int):
    from db import db

    # Trabajos AFUERA (en el laboratorio o en ajuste) con fecha prometida:
    # vencidos (promised_at < hoy) o por vencer (dentro de DUE_SOON_DAYS).
    rows = await db.pool.fetch(
        """
        SELECT lc.work_type, lc.promised_at, lc.status,
               (lc.promised_at - CURRENT_DATE) AS days_left,
               p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name,
               l.name AS lab_name
        FROM lab_cases lc
        JOIN patients p ON p.id = lc.patient_id AND p.tenant_id = lc.tenant_id
        LEFT JOIN labs l ON l.id = lc.lab_id AND l.tenant_id = lc.tenant_id
        WHERE lc.tenant_id = $1
          AND lc.status IN ('enviado', 'a_ajustar')
          AND lc.promised_at IS NOT NULL
          AND lc.promised_at <= CURRENT_DATE + ($2 || ' days')::interval
        ORDER BY lc.promised_at ASC
        LIMIT 60
        """,
        tenant_id,
        str(DUE_SOON_DAYS),
    )

    # Trabajos que YA LLEGARON y todavía no se le avisó al paciente (el aviso lo
    # manda la secretaria a mano — acá solo se lo recordamos, sin mandar nada).
    sin_avisar = await db.pool.fetch(
        """
        SELECT lc.work_type,
               p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name
        FROM lab_cases lc
        JOIN patients p ON p.id = lc.patient_id AND p.tenant_id = lc.tenant_id
        WHERE lc.tenant_id = $1 AND lc.status = 'recibido'
          AND lc.patient_notified_at IS NULL
        ORDER BY lc.received_at ASC NULLS LAST
        LIMIT 20
        """,
        tenant_id,
    )

    vencidos = [r for r in rows if (r["days_left"] or 0) < 0]
    por_vencer = [r for r in rows if (r["days_left"] or 0) >= 0]
    if not vencidos and not por_vencer and not sin_avisar:
        return

    def _line(r):
        wt = r["work_type"] or "trabajo"
        quien = (r["patient_name"] or "").strip()
        lab = f" · {r['lab_name']}" if r.get("lab_name") else ""
        d = r["days_left"] or 0
        if d < 0:
            cuando = f"vencido hace {abs(int(d))}d"
        elif d == 0:
            cuando = "vence HOY"
        else:
            cuando = f"vence en {int(d)}d"
        return f"• {wt} — {quien}{lab} <i>({cuando})</i>"

    lines = ["🦷 <b>Laboratorio — resumen del día</b>", ""]
    if vencidos:
        lines.append(f"🔴 <b>VENCIDOS ({len(vencidos)})</b> — reclamar al laboratorio:")
        lines += [_line(r) for r in vencidos[:MAX_LIST]]
        if len(vencidos) > MAX_LIST:
            lines.append(f"… y {len(vencidos) - MAX_LIST} más.")
        lines.append("")
    if por_vencer:
        lines.append(f"🟡 <b>POR VENCER ({len(por_vencer)})</b>:")
        lines += [_line(r) for r in por_vencer[:MAX_LIST]]
        if len(por_vencer) > MAX_LIST:
            lines.append(f"… y {len(por_vencer) - MAX_LIST} más.")
        lines.append("")
    if sin_avisar:
        lines.append(f"📲 <b>LLEGARON y falta avisarle al paciente ({len(sin_avisar)})</b>:")
        lines += [
            f"• {(r['work_type'] or 'trabajo')} — {(r['patient_name'] or '').strip()}"
            for r in sin_avisar[:MAX_LIST]
        ]
        lines.append("")
    lines.append("👉 Abrí <b>Laboratorio</b> en el panel para gestionarlos.")

    from services.telegram_notifier import send_proactive_message

    sent = await send_proactive_message(tenant_id, "\n".join(lines), is_digest=True)
    if sent:
        logger.info(
            f"lab reminder tenant {tenant_id}: {len(vencidos)} vencidos, "
            f"{len(por_vencer)} por vencer, {len(sin_avisar)} sin avisar"
        )
    else:
        logger.warning(
            f"lab reminder tenant {tenant_id}: no se entregó por Telegram (sin destinatarios o error)"
        )


# Corre cada 30 min, pero la función solo envía durante SEND_HOUR_AR → un digest por día.
scheduler.add_job(check_overdue_lab_cases, interval_seconds=1800, run_at_startup=False)
