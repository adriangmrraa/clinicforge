# -*- coding: utf-8 -*-
"""Reporte diario de agenda del DÍA SIGUIENTE por Telegram — pedido Carlos 2026-07-23.

A la tarde (default 14:00, configurable por tenant vía system_config
AGENDA_REPORT_HOUR), manda al Telegram del equipo (telegram_authorized_users,
mismo canal donde la Dra. usa Nova):

  1) Un resumen en texto: total de turnos de MAÑANA, cuántos confirmados ✅ y
     cuántos sin confirmar ⚠️, con la lista hora — paciente — tratamiento.
  2) El PDF de la agenda del día siguiente (vista diaria imprimible, el mismo
     generador del botón Imprimir) para que el equipo se organice.

Se manda junto con la franja del aviso de no-confirmados. Patrón calcado de
jobs/nova_morning.py (chequeo horario + dedup por día en Redis, fail-safe).
"""

import logging
from datetime import datetime, timedelta

from jobs.scheduler import scheduler

logger = logging.getLogger("jobs.agenda_report")

DEFAULT_HOUR = 14  # 14:00 hora local del tenant


async def send_agenda_tomorrow_report():
    """Hourly check — sends the next-day agenda report to tenants whose
    configured hour matches the current local hour. One send per day."""
    try:
        from services.telegram_bot import _bots

        active_tenants = list(_bots.keys())
        if not active_tenants:
            return
        for tenant_id in active_tenants:
            try:
                await _maybe_send_tenant_report(tenant_id)
            except Exception as e:
                logger.error(f"Agenda report error tenant {tenant_id}: {e}")
    except Exception as e:
        logger.error(f"send_agenda_tomorrow_report global error: {e}")


async def _maybe_send_tenant_report(tenant_id: int):
    from db import db

    # --- hora configurada + timezone del tenant (mismo esquema que nova_morning) ---
    configured_hour = DEFAULT_HOUR
    try:
        row = await db.fetchrow(
            "SELECT value FROM system_config WHERE key = 'AGENDA_REPORT_HOUR' AND tenant_id = $1",
            tenant_id,
        )
        if row and row.get("value"):
            configured_hour = int(row["value"])
    except Exception:
        pass

    tenant_tz_str = "America/Argentina/Buenos_Aires"
    try:
        tz_row = await db.fetchrow(
            "SELECT COALESCE(config->>'timezone', 'America/Argentina/Buenos_Aires') AS tz "
            "FROM tenants WHERE id = $1",
            tenant_id,
        )
        if tz_row and tz_row.get("tz"):
            tenant_tz_str = tz_row["tz"]
    except Exception:
        pass

    try:
        from zoneinfo import ZoneInfo

        tenant_tz = ZoneInfo(tenant_tz_str)
    except Exception:
        from zoneinfo import ZoneInfo

        tenant_tz = ZoneInfo("America/Argentina/Buenos_Aires")

    now_local = datetime.now(tenant_tz)
    if now_local.hour != configured_hour:
        return

    # --- dedup: una vez por día por tenant ---
    try:
        from services.telegram_bot import _get_redis

        redis = _get_redis()
        if redis:
            key = f"agenda_report_sent:{tenant_id}:{now_local.strftime('%Y-%m-%d')}"
            already = await redis.get(key)
            if already:
                return
            await redis.set(key, "1", ex=60 * 60 * 30)  # 30h
    except Exception:
        pass  # sin Redis: se manda igual (peor caso: doble envío tras restart)

    tomorrow = (now_local + timedelta(days=1)).strftime("%Y-%m-%d")

    # --- datos del día siguiente (mismo gather de la vista diaria) ---
    from services.agenda_export_service import gather_day_data, generate_agenda_pdf

    data = await gather_day_data(db.pool, tenant_id, tomorrow)

    if data["total"] == 0:
        # Nada agendado mañana: aviso corto, sin PDF.
        from services.telegram_notifier import send_proactive_message

        await send_proactive_message(
            tenant_id,
            f"🗓️ <b>Agenda de mañana ({data['fecha_titulo']})</b>\n\nNo hay turnos agendados 🎉",
        )
        logger.info(f"Agenda report tenant {tenant_id}: sin turnos mañana")
        return

    # --- resumen en texto (hora — paciente — tratamiento, estado) ---
    lines = [
        f"🗓️ <b>Agenda de mañana — {data['fecha_titulo']}</b>",
        "",
        f"📋 <b>{data['total']} turno{'s' if data['total'] != 1 else ''}</b>"
        f" · ✅ {data['confirmados']} confirmado{'s' if data['confirmados'] != 1 else ''}"
        f" · ⚠️ {data['sin_confirmar']} sin confirmar",
        "",
    ]
    for t in data["turnos"]:
        icon = "✅" if t["estado"] == "Confirmado" else ("⚠️" if t["estado"] == "Sin confirmar" else "▪️")
        lines.append(f"{icon} <b>{t['hora']}</b> — {t['paciente']} · {t['tratamiento']}")
    if data["sin_confirmar"] > 0:
        lines.append("")
        lines.append("<i>⚠️ = todavía no confirmó. El detalle completo va en el PDF adjunto.</i>")

    from services.telegram_notifier import send_proactive_document, send_proactive_message

    await send_proactive_message(tenant_id, "\n".join(lines))

    # --- PDF adjunto (vista diaria, mismo generador del botón Imprimir) ---
    try:
        pdf_path = await generate_agenda_pdf(
            db.pool, tenant_id, tomorrow, tomorrow, view_type="day"
        )
        await send_proactive_document(
            tenant_id,
            pdf_path,
            caption=f"📎 Agenda del {data['fecha_titulo']} para imprimir",
            filename=f"Agenda_{tomorrow}.pdf",
        )
    except Exception as pdf_err:
        # El resumen de texto ya salió — el PDF es best-effort.
        logger.warning(f"Agenda report tenant {tenant_id}: PDF falló (non-fatal): {pdf_err}")

    logger.info(
        f"Agenda report sent tenant {tenant_id}: {data['total']} turnos "
        f"({data['confirmados']} conf / {data['sin_confirmar']} sin conf)"
    )


# Chequeo horario: la función decide por tenant si es su hora configurada.
scheduler.add_job(send_agenda_tomorrow_report, interval_seconds=3600, run_at_startup=False)
