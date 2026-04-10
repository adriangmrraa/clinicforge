"""
nova_morning.py — Daily morning summary sent to Telegram at configured hour.

Sends agenda overview, pending payments, and highlights to all
authorized Telegram users per tenant.

The job runs every hour but each tenant controls its own trigger hour
via system_config key NOVA_MORNING_HOUR (default: 7).
Redis dedup key `nova_morning:{tenant_id}:{date}` with 23h TTL prevents
double-sends when the job fires multiple times in the same hour.
"""

import asyncio
import logging
from datetime import datetime, date

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from .scheduler import scheduler

logger = logging.getLogger(__name__)


async def send_morning_summary():
    """
    Hourly check — sends daily morning summary to tenants whose configured
    hour matches the current hour. One send per tenant per calendar day.
    """
    try:
        from services.telegram_bot import _bots

        active_tenants = list(_bots.keys())
        if not active_tenants:
            return

        for tenant_id in active_tenants:
            try:
                await _maybe_send_tenant_summary(tenant_id)
            except Exception as e:
                logger.error(f"Morning summary error tenant {tenant_id}: {e}")

    except Exception as e:
        logger.error(f"send_morning_summary global error: {e}")


async def _maybe_send_tenant_summary(tenant_id: int):
    """
    Check if it is time for this tenant's morning summary.
    Uses Redis dedup (key per tenant per date) to avoid double sends.
    """
    from db import db

    # --- Read tenant timezone + configured hour ---
    tenant_tz_str = "America/Argentina/Buenos_Aires"  # safe default
    configured_hour = 7
    try:
        row = await db.fetchrow(
            "SELECT value FROM system_config WHERE key = 'NOVA_MORNING_HOUR' AND tenant_id = $1",
            tenant_id,
        )
        if row and row.get("value"):
            configured_hour = int(row["value"])
    except Exception:
        pass

    try:
        tz_row = await db.fetchrow(
            "SELECT timezone FROM tenants WHERE id = $1", tenant_id,
        )
        if tz_row and tz_row.get("timezone"):
            tenant_tz_str = tz_row["timezone"]
    except Exception:
        pass

    # Compare current hour in the TENANT's timezone, not server UTC
    try:
        tenant_tz = ZoneInfo(tenant_tz_str)
    except Exception:
        tenant_tz = ZoneInfo("America/Argentina/Buenos_Aires")

    now = datetime.now(tenant_tz)

    if now.hour != configured_hour:
        return  # Not this tenant's time yet

    # --- Redis dedup: one send per day (use tenant's local date) ---
    today_str = now.date().isoformat()
    dedup_key = f"nova_morning:{tenant_id}:{today_str}"

    try:
        from services.telegram_bot import _get_redis

        redis = _get_redis()
        if redis:
            already_sent = await redis.exists(dedup_key)
            if already_sent:
                return
    except Exception:
        pass  # If Redis is unavailable, allow send (better duplicate than skip)

    await _send_tenant_summary(tenant_id)

    # Mark as sent — TTL 23h so it resets cleanly before next day's window
    try:
        from services.telegram_bot import _get_redis

        redis = _get_redis()
        if redis:
            await redis.setex(dedup_key, 23 * 3600, "1")
    except Exception:
        pass


async def _send_tenant_summary(tenant_id: int):
    """Build and send the morning summary message for one tenant."""
    from db import db
    from services.telegram_notifier import send_proactive_message

    today = date.today()
    today_str = today.strftime("%d/%m/%Y")
    day_names = {
        0: "Lunes", 1: "Martes", 2: "Miércoles",
        3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo",
    }
    day_name = day_names.get(today.weekday(), "")

    # --- 1. Today's appointments ---
    appointments = await db.fetch(
        """SELECT a.appointment_datetime, a.appointment_type, a.status,
                  p.first_name, p.last_name, pr.first_name as prof_first
           FROM appointments a
           LEFT JOIN patients p ON a.patient_id = p.id
           LEFT JOIN professionals pr ON a.professional_id = pr.id
           WHERE a.tenant_id = $1 AND DATE(a.appointment_datetime) = $2
           ORDER BY a.appointment_datetime ASC""",
        tenant_id, today,
    )

    total = len(appointments)
    unconfirmed = sum(1 for a in appointments if a["status"] == "scheduled")
    confirmed = sum(1 for a in appointments if a["status"] == "confirmed")

    # --- 2. Pending payments ---
    pending_payments = await db.fetchrow(
        """SELECT COUNT(*) as count, COALESCE(SUM(billing_amount), 0) as total
           FROM appointments
           WHERE tenant_id = $1 AND status = 'completed'
           AND payment_status = 'pending' AND billing_amount > 0""",
        tenant_id,
    )

    # --- 3. Nova daily analysis insights (from Redis cache) ---
    daily_insight = None
    try:
        from services.telegram_bot import _get_redis

        redis = _get_redis()
        if redis:
            import json

            raw = await redis.get(f"nova_daily:{tenant_id}")
            if raw:
                analysis = json.loads(raw)
                resumen = analysis.get("resumen") or analysis.get("summary")
                if resumen:
                    daily_insight = resumen
    except Exception:
        pass

    # --- 4. Overdue treatment plans ---
    overdue_plans = 0
    try:
        overdue_plans = await db.fetchval(
            """SELECT COUNT(*) FROM treatment_plans
               WHERE tenant_id = $1 AND status IN ('approved', 'in_progress')
               AND updated_at < NOW() - INTERVAL '30 days'""",
            tenant_id,
        ) or 0
    except Exception:
        pass  # treatment_plans table may not exist in all deployments

    # --- 5. Build HTML message ---
    lines = [
        f"☀️ <b>Buenos días! {day_name} {today_str}</b>",
        "",
    ]

    if total == 0:
        lines.append("📅 <b>No hay turnos programados para hoy.</b> Día libre! 🎉")
    else:
        lines.append(f"📅 <b>Agenda — {total} turno{'s' if total != 1 else ''}</b>")
        if confirmed:
            lines.append(f"▸ {confirmed} confirmado{'s' if confirmed != 1 else ''} ✅")
        if unconfirmed:
            lines.append(f"▸ {unconfirmed} sin confirmar ⚠️")

        if appointments:
            first = appointments[0]
            first_time = (
                first["appointment_datetime"].strftime("%H:%M")
                if first["appointment_datetime"] else "?"
            )
            first_name = f"{first.get('first_name', '?')} {first.get('last_name', '') or ''}".strip()
            lines.append(f"▸ Primer turno: <b>{first_time}</b> — {first_name}")

            if len(appointments) > 1:
                last = appointments[-1]
                last_time = (
                    last["appointment_datetime"].strftime("%H:%M")
                    if last["appointment_datetime"] else "?"
                )
                last_name = f"{last.get('first_name', '?')} {last.get('last_name', '') or ''}".strip()
                lines.append(f"▸ Último turno: <b>{last_time}</b> — {last_name}")

    lines.append("")

    # Pending payments section
    pay_count = int(pending_payments["count"]) if pending_payments else 0
    pay_total = float(pending_payments["total"]) if pending_payments else 0.0
    if pay_count > 0 or overdue_plans > 0:
        lines.append("💰 <b>Cobros pendientes</b>")
        if pay_count > 0:
            lines.append(f"▸ {pay_count} turno{'s' if pay_count != 1 else ''} sin cobrar (${pay_total:,.0f})")
        if overdue_plans > 0:
            lines.append(f"▸ {overdue_plans} presupuesto{'s' if overdue_plans != 1 else ''} sin movimiento (+30 días)")
        lines.append("")

    # Highlights from Nova daily analysis
    if daily_insight:
        lines.append("🦷 <b>Highlights</b>")
        # Truncate to keep message manageable
        insight_text = str(daily_insight)[:300]
        lines.append(f"▸ {insight_text}")
        lines.append("")

    lines.append("<i>¿Necesitás que confirme los turnos o te prepare algo?</i>")

    html_text = "\n".join(lines)
    await send_proactive_message(tenant_id, html_text)
    logger.info(f"Morning summary sent to tenant {tenant_id} ({total} turnos, {pay_count} cobros pendientes)")


# Register job: runs every hour, the function itself checks the configured hour per tenant
scheduler.add_job(send_morning_summary, interval_seconds=3600, run_at_startup=False)
