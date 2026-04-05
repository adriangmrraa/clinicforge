"""
smart_alerts.py — Periodic smart alerts sent to Telegram.

Evaluates alert conditions every 4 hours for all tenants with active
Telegram bots and sends notifications for:
  - Unconfirmed appointments for tomorrow
  - No-shows detected today
  - Recurring no-show patients (3+ in 60 days)
  - Appointments starting in ≤1h still unconfirmed
  - High-value overdue treatment plan debt (weekly)

Redis keys follow the pattern:
  alert_sent:{tenant_id}:{alert_type}:{discriminator}
with a TTL that matches the desired maximum frequency per alert type.
"""

import logging
from datetime import datetime, date, timedelta

from .scheduler import scheduler

logger = logging.getLogger(__name__)


# ── Redis helpers ──────────────────────────────────────────────────────────────

async def _alert_already_sent(tenant_id: int, alert_key: str) -> bool:
    """Return True if this alert was already sent within its TTL window."""
    try:
        from services.telegram_bot import _get_redis

        redis = _get_redis()
        if not redis:
            return False
        key = f"alert_sent:{tenant_id}:{alert_key}"
        exists = await redis.exists(key)
        return bool(exists)
    except Exception:
        return False


async def _mark_alert_sent(tenant_id: int, alert_key: str, ttl: int = 86400):
    """Mark alert as sent with TTL (default 24h)."""
    try:
        from services.telegram_bot import _get_redis

        redis = _get_redis()
        if redis:
            key = f"alert_sent:{tenant_id}:{alert_key}"
            await redis.setex(key, ttl, "1")
    except Exception:
        pass


# ── Main entry point ───────────────────────────────────────────────────────────

async def evaluate_smart_alerts():
    """
    Check all alert conditions for every tenant with an active Telegram bot.
    Runs every 4 hours. Each individual alert function handles its own dedup.
    """
    try:
        from services.telegram_bot import _bots

        active_tenants = list(_bots.keys())
        if not active_tenants:
            return

        for tenant_id in active_tenants:
            try:
                await _check_unconfirmed_tomorrow(tenant_id)
                await _check_no_shows_today(tenant_id)
                await _check_recurring_no_show_patients(tenant_id)
                await _check_imminent_unconfirmed(tenant_id)
                await _check_overdue_payments(tenant_id)
            except Exception as e:
                logger.error(f"Smart alert error tenant {tenant_id}: {e}")

    except Exception as e:
        logger.error(f"evaluate_smart_alerts global error: {e}")


# ── Individual alert checks ────────────────────────────────────────────────────

async def _check_unconfirmed_tomorrow(tenant_id: int):
    """
    Alert if there are unconfirmed appointments for tomorrow.
    Fires once per day at most (24h TTL). Ideally fires during the evening
    run of the 4h job.
    """
    from db import db
    from services.telegram_notifier import send_proactive_message

    tomorrow = date.today() + timedelta(days=1)
    alert_key = f"unconfirmed_{tomorrow.isoformat()}"

    if await _alert_already_sent(tenant_id, alert_key):
        return

    count = await db.fetchval(
        """SELECT COUNT(*) FROM appointments
           WHERE tenant_id = $1 AND DATE(appointment_datetime) = $2
           AND status = 'scheduled'""",
        tenant_id, tomorrow,
    )

    if count and count > 0:
        await send_proactive_message(
            tenant_id,
            f"⚠️ <b>Turnos sin confirmar para mañana</b>\n\n"
            f"▸ <b>{count}</b> turno{'s' if count != 1 else ''} en estado pendiente para "
            f"{tomorrow.strftime('%d/%m')}\n\n"
            f"<i>¿Querés que los confirme todos?</i>",
        )
        await _mark_alert_sent(tenant_id, alert_key, ttl=86400)
        logger.info(f"Alert unconfirmed_tomorrow sent: tenant={tenant_id}, count={count}")


async def _check_no_shows_today(tenant_id: int):
    """
    Alert when no-shows are detected for today.
    Fires at most once per day (24h TTL).
    """
    from db import db
    from services.telegram_notifier import send_proactive_message

    today = date.today()
    alert_key = f"noshows_{today.isoformat()}"

    if await _alert_already_sent(tenant_id, alert_key):
        return

    no_shows = await db.fetch(
        """SELECT p.first_name, p.last_name, a.appointment_datetime
           FROM appointments a
           JOIN patients p ON a.patient_id = p.id
           WHERE a.tenant_id = $1 AND DATE(a.appointment_datetime) = $2
           AND a.status = 'no-show'
           ORDER BY a.appointment_datetime""",
        tenant_id, today,
    )

    if no_shows:
        lines = [f"🔴 <b>{len(no_shows)} inasistencia{'s' if len(no_shows) != 1 else ''} hoy</b>", ""]
        for ns in no_shows[:5]:
            name = f"{ns['first_name']} {ns.get('last_name', '') or ''}".strip()
            apt_time = (
                ns["appointment_datetime"].strftime("%H:%M")
                if ns["appointment_datetime"] else "?"
            )
            lines.append(f"▸ {name} — turno de las {apt_time}")
        if len(no_shows) > 5:
            lines.append(f"▸ … y {len(no_shows) - 5} más")
        lines.extend(["", "<i>¿Los contacto para reagendar?</i>"])
        await send_proactive_message(tenant_id, "\n".join(lines))
        await _mark_alert_sent(tenant_id, alert_key, ttl=86400)
        logger.info(f"Alert no_shows sent: tenant={tenant_id}, count={len(no_shows)}")


async def _check_recurring_no_show_patients(tenant_id: int):
    """
    Alert when a patient accumulates 3+ no-shows in the last 60 days.
    Fires once per patient (permanent dedup — no TTL expiry until manually cleared).
    """
    from db import db
    from services.telegram_notifier import send_proactive_message

    cutoff = date.today() - timedelta(days=60)

    recurring = await db.fetch(
        """SELECT p.id as patient_id, p.first_name, p.last_name, COUNT(*) as ns_count
           FROM appointments a
           JOIN patients p ON a.patient_id = p.id
           WHERE a.tenant_id = $1 AND a.status = 'no-show'
           AND DATE(a.appointment_datetime) >= $2
           GROUP BY p.id, p.first_name, p.last_name
           HAVING COUNT(*) >= 3
           ORDER BY ns_count DESC""",
        tenant_id, cutoff,
    )

    for patient in recurring:
        patient_id = patient["patient_id"]
        alert_key = f"recurring_noshow_patient_{patient_id}"

        if await _alert_already_sent(tenant_id, alert_key):
            continue

        name = f"{patient['first_name']} {patient.get('last_name', '') or ''}".strip()
        count = patient["ns_count"]

        await send_proactive_message(
            tenant_id,
            f"🔴 <b>Paciente con inasistencias reiteradas</b>\n\n"
            f"▸ <b>{name}</b> tuvo <b>{count} inasistencias</b> en los últimos 60 días\n\n"
            f"<i>¿Lo contactamos para ver qué pasó?</i>",
        )
        # No TTL — once alerted for this pattern, don't repeat until next cycle
        # (TTL 30 days allows re-alert if pattern continues a month later)
        await _mark_alert_sent(tenant_id, alert_key, ttl=30 * 86400)
        logger.info(f"Alert recurring_noshow sent: tenant={tenant_id}, patient_id={patient_id}, count={count}")


async def _check_imminent_unconfirmed(tenant_id: int):
    """
    Alert for appointments starting within the next hour that are still unconfirmed.
    Fires once per appointment (dedup key includes appointment datetime).
    """
    from db import db
    from services.telegram_notifier import send_proactive_message

    now = datetime.now()
    window_end = now + timedelta(hours=1)

    imminent = await db.fetch(
        """SELECT a.id, a.appointment_datetime, p.first_name, p.last_name
           FROM appointments a
           JOIN patients p ON a.patient_id = p.id
           WHERE a.tenant_id = $1 AND a.status = 'scheduled'
           AND a.appointment_datetime >= $2
           AND a.appointment_datetime <= $3
           ORDER BY a.appointment_datetime""",
        tenant_id, now, window_end,
    )

    for apt in imminent:
        apt_id = apt["id"]
        alert_key = f"imminent_unconfirmed_{apt_id}"

        if await _alert_already_sent(tenant_id, alert_key):
            continue

        name = f"{apt['first_name']} {apt.get('last_name', '') or ''}".strip()
        apt_time = (
            apt["appointment_datetime"].strftime("%H:%M")
            if apt["appointment_datetime"] else "?"
        )

        await send_proactive_message(
            tenant_id,
            f"⚠️ <b>Turno próximo sin confirmar</b>\n\n"
            f"▸ <b>{name}</b> — {apt_time} (en menos de 1 hora)\n\n"
            f"<i>¿Lo confirmo o le envío un recordatorio?</i>",
        )
        # TTL 2h — longer than the 1h window to avoid duplication
        await _mark_alert_sent(tenant_id, alert_key, ttl=7200)
        logger.info(f"Alert imminent_unconfirmed sent: tenant={tenant_id}, apt_id={apt_id}")


async def _check_overdue_payments(tenant_id: int):
    """
    Weekly alert about patients with overdue treatment plan debt.
    Fires once per calendar week (TTL = 7 days).
    """
    from db import db
    from services.telegram_notifier import send_proactive_message

    iso_week = date.today().isocalendar()[1]
    iso_year = date.today().isocalendar()[0]
    alert_key = f"overdue_weekly_{iso_year}_{iso_week}"

    if await _alert_already_sent(tenant_id, alert_key):
        return

    try:
        overdue = await db.fetch(
            """SELECT tp.id, tp.name, p.first_name, p.last_name,
                      tp.approved_total,
                      COALESCE(
                          (SELECT SUM(amount) FROM treatment_plan_payments WHERE plan_id = tp.id),
                          0
                      ) as paid
               FROM treatment_plans tp
               JOIN patients p ON tp.patient_id = p.id
               WHERE tp.tenant_id = $1 AND tp.status IN ('approved', 'in_progress')
               AND tp.updated_at < NOW() - INTERVAL '30 days'
               ORDER BY tp.approved_total DESC
               LIMIT 10""",
            tenant_id,
        )
    except Exception:
        # treatment_plans or treatment_plan_payments tables may not exist
        return

    if not overdue:
        return

    # Only list patients with actual pending balance
    debt_lines = []
    for o in overdue:
        total = float(o["approved_total"] or 0)
        paid = float(o["paid"] or 0)
        debe = total - paid
        if debe > 0:
            name = f"{o['first_name']} {o.get('last_name', '') or ''}".strip()
            debt_lines.append(f"▸ {name} — debe <b>${debe:,.0f}</b> de ${total:,.0f}")

    if not debt_lines:
        return

    lines = [f"💰 <b>Presupuestos con deuda (+30 días)</b>", ""]
    lines.extend(debt_lines[:8])
    if len(debt_lines) > 8:
        lines.append(f"▸ … y {len(debt_lines) - 8} más")
    lines.extend(["", "<i>¿Les mando recordatorio de pago?</i>"])

    await send_proactive_message(tenant_id, "\n".join(lines))
    await _mark_alert_sent(tenant_id, alert_key, ttl=7 * 86400)
    logger.info(f"Alert overdue_weekly sent: tenant={tenant_id}, debts={len(debt_lines)}")


# Register job: runs every 4 hours
scheduler.add_job(evaluate_smart_alerts, interval_seconds=14400, run_at_startup=False)
