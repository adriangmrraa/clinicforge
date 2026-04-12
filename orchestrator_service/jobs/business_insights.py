"""
business_insights.py — Strategic Business Intelligence Alerts via Telegram.

Runs every 12 hours. Analyzes campaign performance, attribution data,
lead conversion, and patient segments. Sends ACTIONABLE insights to CEO
via Telegram — not questions, but conclusions with recommended actions
and clear reasoning.

Format: WHAT happened → WHY it matters → DO this (concrete action)
"""

import logging
import json
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

from .scheduler import scheduler

logger = logging.getLogger(__name__)


async def evaluate_business_insights():
    """
    Run all business intelligence checks for tenants with Telegram bots.
    Every 12 hours.
    """
    try:
        from services.telegram_bot import _bots

        active_tenants = list(_bots.keys())
        if not active_tenants:
            return

        for tenant_id in active_tenants:
            try:
                await _insight_campaign_roi(tenant_id)
                await _insight_lead_conversion_funnel(tenant_id)
                await _insight_high_value_leads_stalled(tenant_id)
                await _insight_top_performing_campaign(tenant_id)
                await _insight_attribution_channel_shift(tenant_id)
                await _insight_reactivation_opportunity(tenant_id)
                await _insight_no_show_pattern(tenant_id)
            except Exception as e:
                logger.error(f"Business insight error tenant {tenant_id}: {e}")

    except Exception as e:
        logger.error(f"evaluate_business_insights global error: {e}")


# ── Redis dedup (reuse smart_alerts pattern) ─────────────────────────────

async def _already_sent(tenant_id: int, key: str) -> bool:
    try:
        from services.telegram_bot import _get_redis
        redis = _get_redis()
        if not redis:
            return False
        return bool(await redis.exists(f"biz_insight:{tenant_id}:{key}"))
    except Exception:
        return False


async def _mark_sent(tenant_id: int, key: str, ttl: int = 43200):
    """Mark insight as sent with TTL (default 12h)."""
    try:
        from services.telegram_bot import _get_redis
        redis = _get_redis()
        if redis:
            await redis.setex(f"biz_insight:{tenant_id}:{key}", ttl, "1")
    except Exception:
        pass


def _fmt_money(amount) -> str:
    """Format number as money."""
    if amount is None:
        return "$0"
    try:
        return f"${int(float(amount)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "$0"


def _fmt_pct(value) -> str:
    """Format as percentage."""
    try:
        return f"{float(value):.1f}%"
    except (ValueError, TypeError):
        return "0%"


# ── 1. Campaign ROI Alert ────────────────────────────────────────────────

async def _insight_campaign_roi(tenant_id: int):
    """Detect campaigns with negative ROI (spending but not converting)."""
    from db import db

    key = f"campaign_roi_{date.today().isoformat()}"
    if await _already_sent(tenant_id, key):
        return

    # Get campaigns with spend in last 7 days
    campaigns = await db.pool.fetch("""
        SELECT
            p.first_touch_campaign_id as campaign_id,
            p.first_touch_campaign_name as campaign_name,
            COUNT(DISTINCT p.id) as total_leads,
            COUNT(DISTINCT CASE WHEN a.id IS NOT NULL THEN p.id END) as converted,
            COUNT(DISTINCT CASE WHEN a.status = 'completed' THEN p.id END) as completed
        FROM patients p
        LEFT JOIN appointments a ON a.patient_id = p.id AND a.tenant_id = p.tenant_id
            AND a.status IN ('scheduled', 'confirmed', 'completed')
        WHERE p.tenant_id = $1
            AND p.first_touch_campaign_id IS NOT NULL
            AND p.created_at > NOW() - INTERVAL '30 days'
        GROUP BY p.first_touch_campaign_id, p.first_touch_campaign_name
        HAVING COUNT(DISTINCT p.id) >= 3
        ORDER BY COUNT(DISTINCT p.id) DESC
    """, tenant_id)

    if not campaigns:
        return

    from services.telegram_notifier import send_proactive_message

    low_converters = []
    for c in campaigns:
        total = c["total_leads"]
        converted = c["converted"]
        rate = (converted / total * 100) if total > 0 else 0
        if rate < 10 and total >= 5:
            low_converters.append({
                "name": c["campaign_name"] or c["campaign_id"],
                "leads": total,
                "converted": converted,
                "rate": rate,
            })

    if low_converters:
        lines = ["📊 <b>Alerta de rendimiento de campañas</b>\n"]
        for lc in low_converters[:3]:
            lines.append(
                f"▸ <b>{lc['name']}</b>: {lc['leads']} leads → {lc['converted']} agendaron "
                f"({_fmt_pct(lc['rate'])} conversión)\n"
            )
        lines.append(
            "\n<b>💡 Acción recomendada:</b> Revisá el copy y la segmentación de "
            f"{'estas campañas' if len(low_converters) > 1 else 'esta campaña'}. "
            "Un ratio menor al 10% indica que el público que llega no coincide con el "
            "servicio ofrecido, o que el mensaje inicial del bot no está conectando con "
            "la expectativa que generó el anuncio.\n\n"
            "Podés ajustar las respuestas del bot para estos tratamientos desde "
            "<b>Tratamientos → Respuesta del Agente IA</b>, o modificar la audiencia "
            "directamente en Meta Ads Manager."
        )
        await send_proactive_message(tenant_id, "\n".join(lines))
        await _mark_sent(tenant_id, key, ttl=86400)


# ── 2. Lead Conversion Funnel ───────────────────────────────────────────

async def _insight_lead_conversion_funnel(tenant_id: int):
    """Weekly funnel analysis: leads → conversations → appointments → completed."""
    from db import db

    key = f"funnel_{date.today().isocalendar()[1]}"  # Weekly by week number
    if await _already_sent(tenant_id, key):
        return

    # Only run on Mondays (weekly report)
    if date.today().weekday() != 0:
        return

    stats = await db.pool.fetchrow("""
        SELECT
            (SELECT COUNT(*) FROM patients WHERE tenant_id = $1
                AND created_at > NOW() - INTERVAL '7 days') as new_leads,
            (SELECT COUNT(DISTINCT patient_id) FROM appointments
                WHERE tenant_id = $1 AND created_at > NOW() - INTERVAL '7 days'
                AND status IN ('scheduled', 'confirmed', 'completed')) as booked,
            (SELECT COUNT(DISTINCT patient_id) FROM appointments
                WHERE tenant_id = $1 AND created_at > NOW() - INTERVAL '7 days'
                AND status = 'completed') as completed,
            (SELECT COUNT(*) FROM appointments
                WHERE tenant_id = $1 AND created_at > NOW() - INTERVAL '7 days'
                AND status IN ('no-show', 'no_show')) as no_shows,
            (SELECT COALESCE(SUM(billing_amount), 0) FROM appointments
                WHERE tenant_id = $1 AND created_at > NOW() - INTERVAL '7 days'
                AND status = 'completed' AND billing_amount > 0) as revenue
    """, tenant_id)

    if not stats or stats["new_leads"] == 0:
        return

    leads = stats["new_leads"]
    booked = stats["booked"]
    completed = stats["completed"]
    no_shows = stats["no_shows"]
    revenue = stats["revenue"] or 0
    book_rate = (booked / leads * 100) if leads > 0 else 0
    complete_rate = (completed / booked * 100) if booked > 0 else 0

    from services.telegram_notifier import send_proactive_message

    lines = [
        "📈 <b>Resumen semanal del funnel de conversión</b>\n",
        f"▸ Nuevos leads: <b>{leads}</b>",
        f"▸ Agendaron turno: <b>{booked}</b> ({_fmt_pct(book_rate)} del total)",
        f"▸ Completaron tratamiento: <b>{completed}</b> ({_fmt_pct(complete_rate)} de agendados)",
        f"▸ No-shows: <b>{no_shows}</b>",
        f"▸ Facturación: <b>{_fmt_money(revenue)}</b>\n",
    ]

    # Actionable insight based on data
    if book_rate < 30:
        lines.append(
            "<b>💡 Acción recomendada:</b> Solo el " + _fmt_pct(book_rate) + " de los leads "
            "agenda turno. Revisá el flujo de conversación del bot — puede estar perdiendo "
            "leads por respuestas demasiado genéricas. Configurá respuestas específicas por "
            "tratamiento en <b>Tratamientos → Respuesta del Agente IA</b> para conectar mejor "
            "con lo que el paciente vio en el anuncio."
        )
    elif no_shows > 2:
        lines.append(
            f"<b>💡 Acción recomendada:</b> Hubo {no_shows} no-shows esta semana. "
            "Activá el playbook <b>Escudo Anti-Ausencias</b> en Automatizaciones si no lo "
            "tenés activo — el recordatorio con botones de confirmación reduce los no-shows "
            "en un 60-80%."
        )
    elif complete_rate > 70:
        lines.append(
            "<b>💡 Insight positivo:</b> El " + _fmt_pct(complete_rate) + " de los pacientes "
            "que agendaron completaron su tratamiento. El funnel está sano. Considerá "
            "escalar el presupuesto en las campañas activas de Meta Ads para capitalizar "
            "este buen momento."
        )
    else:
        lines.append(
            "<b>💡 Acción recomendada:</b> El flujo general está dentro de lo normal. "
            "Enfocate en reducir la brecha entre agendados y completados — activá el "
            "playbook <b>Recordatorio de turno</b> y <b>Protocolo Post-Consulta</b> "
            "para mejorar la retención."
        )

    await send_proactive_message(tenant_id, "\n".join(lines))
    await _mark_sent(tenant_id, key, ttl=604800)  # 7 days


# ── 3. High-Value Leads Stalled ──────────────────────────────────────────

async def _insight_high_value_leads_stalled(tenant_id: int):
    """Detect leads from high-ticket campaigns that haven't booked in 48h+."""
    from db import db

    key = f"stalled_leads_{date.today().isoformat()}"
    if await _already_sent(tenant_id, key):
        return

    # Find leads from campaigns with "implante", "cirugia", "rehabilitacion" in name
    stalled = await db.pool.fetch("""
        SELECT p.first_name, p.phone_number,
               p.first_touch_campaign_name as campaign,
               p.first_touch_ad_name as ad_name,
               p.created_at
        FROM patients p
        WHERE p.tenant_id = $1
            AND p.created_at > NOW() - INTERVAL '7 days'
            AND p.created_at < NOW() - INTERVAL '48 hours'
            AND p.first_touch_campaign_name IS NOT NULL
            AND (
                LOWER(p.first_touch_campaign_name) LIKE '%implante%'
                OR LOWER(p.first_touch_campaign_name) LIKE '%cirug%'
                OR LOWER(p.first_touch_campaign_name) LIKE '%rehabilita%'
                OR LOWER(p.first_touch_campaign_name) LIKE '%protesis%'
                OR LOWER(p.first_touch_campaign_name) LIKE '%endolifting%'
            )
            AND NOT EXISTS (
                SELECT 1 FROM appointments a
                WHERE a.patient_id = p.id AND a.tenant_id = $1
            )
        ORDER BY p.created_at DESC
        LIMIT 10
    """, tenant_id)

    if not stalled:
        return

    from services.telegram_notifier import send_proactive_message

    lines = [
        f"🎯 <b>{len(stalled)} leads de alto valor sin agendar (48h+)</b>\n",
    ]
    for s in stalled[:5]:
        days_ago = (datetime.now(timezone.utc) - s["created_at"].replace(tzinfo=timezone.utc)).days
        lines.append(
            f"▸ <b>{s['first_name'] or 'Sin nombre'}</b> — {s['phone_number']}\n"
            f"  Campaña: {s['campaign'] or '?'} (hace {days_ago} días)"
        )

    lines.append(
        f"\n<b>💡 Acción recomendada:</b> Estos {len(stalled)} leads llegaron por campañas "
        "de tratamientos de alto valor pero no agendaron. "
        "Activá el playbook <b>Recuperador de Presupuestos</b> en Automatizaciones — "
        "les enviará un seguimiento personalizado mencionando el tratamiento por el que "
        "consultaron. Los leads high-ticket necesitan más contacto para decidir, "
        "pero el bot genérico no les da ese empujón."
    )

    await send_proactive_message(tenant_id, "\n".join(lines))
    await _mark_sent(tenant_id, key, ttl=86400)


# ── 4. Top Performing Campaign ───────────────────────────────────────────

async def _insight_top_performing_campaign(tenant_id: int):
    """Highlight the best-performing campaign to encourage scaling."""
    from db import db

    key = f"top_campaign_{date.today().isocalendar()[1]}"
    if await _already_sent(tenant_id, key):
        return

    if date.today().weekday() != 0:
        return  # Weekly, Mondays only

    top = await db.pool.fetchrow("""
        SELECT
            p.first_touch_campaign_name as campaign_name,
            COUNT(DISTINCT p.id) as leads,
            COUNT(DISTINCT CASE WHEN a.id IS NOT NULL THEN p.id END) as booked,
            COUNT(DISTINCT CASE WHEN a.status = 'completed' THEN p.id END) as completed,
            COALESCE(SUM(a.billing_amount) FILTER (WHERE a.status = 'completed'), 0) as revenue
        FROM patients p
        LEFT JOIN appointments a ON a.patient_id = p.id AND a.tenant_id = p.tenant_id
        WHERE p.tenant_id = $1
            AND p.first_touch_campaign_id IS NOT NULL
            AND p.created_at > NOW() - INTERVAL '30 days'
        GROUP BY p.first_touch_campaign_name
        HAVING COUNT(DISTINCT p.id) >= 3
        ORDER BY COUNT(DISTINCT CASE WHEN a.id IS NOT NULL THEN p.id END) DESC
        LIMIT 1
    """, tenant_id)

    if not top or not top["campaign_name"]:
        return

    conversion = (top["booked"] / top["leads"] * 100) if top["leads"] > 0 else 0

    if conversion < 20:
        return  # Only report genuinely good campaigns

    from services.telegram_notifier import send_proactive_message

    lines = [
        "🏆 <b>Campaña destacada del mes</b>\n",
        f"▸ <b>{top['campaign_name']}</b>",
        f"▸ Leads: {top['leads']} → Agendaron: {top['booked']} ({_fmt_pct(conversion)})",
        f"▸ Completaron: {top['completed']}",
        f"▸ Facturación asociada: <b>{_fmt_money(top['revenue'])}</b>\n",
        f"<b>💡 Acción recomendada:</b> Esta campaña convierte al {_fmt_pct(conversion)}. "
        "Considerá aumentar su presupuesto diario un 20-30% en Meta Ads Manager para "
        "capitalizar su buen rendimiento. No modifiques el copy ni la audiencia — "
        "si funciona, escalá sin tocar."
    ]

    await send_proactive_message(tenant_id, "\n".join(lines))
    await _mark_sent(tenant_id, key, ttl=604800)


# ── 5. Attribution Channel Shift ─────────────────────────────────────────

async def _insight_attribution_channel_shift(tenant_id: int):
    """Detect if organic leads are growing or declining vs paid."""
    from db import db

    key = f"channel_shift_{date.today().isocalendar()[1]}"
    if await _already_sent(tenant_id, key):
        return

    if date.today().weekday() != 0:
        return

    stats = await db.pool.fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE acquisition_source = 'ORGANIC' OR acquisition_source IS NULL) as organic,
            COUNT(*) FILTER (WHERE acquisition_source != 'ORGANIC' AND acquisition_source IS NOT NULL) as paid
        FROM patients
        WHERE tenant_id = $1 AND created_at > NOW() - INTERVAL '30 days'
    """, tenant_id)

    if not stats or (stats["organic"] + stats["paid"]) < 5:
        return

    total = stats["organic"] + stats["paid"]
    organic_pct = stats["organic"] / total * 100
    paid_pct = stats["paid"] / total * 100

    from services.telegram_notifier import send_proactive_message

    lines = [
        "📡 <b>Distribución de canales de adquisición (30 días)</b>\n",
        f"▸ Orgánico (Google, referidos, directo): <b>{stats['organic']}</b> ({_fmt_pct(organic_pct)})",
        f"▸ Pago (Meta Ads, Google Ads): <b>{stats['paid']}</b> ({_fmt_pct(paid_pct)})\n",
    ]

    if organic_pct > 60:
        lines.append(
            "<b>💡 Insight:</b> Más del 60% de tus pacientes llegan de forma orgánica. "
            "Esto es bueno para la rentabilidad, pero indica que podrías escalar más "
            "con campañas pagas sin saturar tu audiencia. Considerá invertir más en "
            "Meta Ads en tratamientos high-ticket (implantes, rehabilitación) donde "
            "el ROI es más alto."
        )
    elif paid_pct > 70:
        lines.append(
            "<b>💡 Insight:</b> El 70%+ de tus pacientes viene de campañas pagas. "
            "Tu clínica depende mucho de la publicidad. Para reducir este riesgo, "
            "activá el playbook <b>Motor de Reseñas Google</b> — más reseñas positivas "
            "atraen pacientes orgánicos y reducen tu costo de adquisición a largo plazo."
        )
    else:
        lines.append(
            "<b>💡 Insight:</b> Tenés un balance saludable entre orgánico y pago. "
            "Mantené las campañas activas y reforzá el flujo orgánico con reseñas "
            "y contenido en redes."
        )

    await send_proactive_message(tenant_id, "\n".join(lines))
    await _mark_sent(tenant_id, key, ttl=604800)


# ── 6. Reactivation Opportunity ──────────────────────────────────────────

async def _insight_reactivation_opportunity(tenant_id: int):
    """Count patients inactive 90+ days that could be reactivated."""
    from db import db

    key = f"reactivation_{date.today().isocalendar()[1]}"
    if await _already_sent(tenant_id, key):
        return

    if date.today().weekday() != 0:
        return

    count = await db.pool.fetchval("""
        SELECT COUNT(DISTINCT p.id)
        FROM patients p
        WHERE p.tenant_id = $1
            AND p.phone_number IS NOT NULL
            AND p.no_followup = false
            AND NOT EXISTS (
                SELECT 1 FROM appointments a
                WHERE a.patient_id = p.id AND a.tenant_id = $1
                    AND a.appointment_datetime > NOW() - INTERVAL '90 days'
            )
            AND EXISTS (
                SELECT 1 FROM appointments a
                WHERE a.patient_id = p.id AND a.tenant_id = $1
                    AND a.status = 'completed'
            )
    """, tenant_id)

    if not count or count < 5:
        return

    from services.telegram_notifier import send_proactive_message

    lines = [
        f"💤 <b>{count} pacientes inactivos hace +90 días</b>\n",
        "Estos pacientes ya se atendieron en la clínica pero no volvieron en 3 meses.\n",
        f"<b>💡 Acción recomendada:</b> Activá el playbook <b>Reactivador de Pacientes</b> "
        "en Automatizaciones. Les enviará un mensaje recordándoles que es hora de un "
        "control, con un tono cercano y sin presión. En promedio, el 15-20% de los "
        f"pacientes reactivados agenda un nuevo turno. Eso son potencialmente "
        f"<b>{int(count * 0.17)}</b> turnos recuperados."
    ]

    await send_proactive_message(tenant_id, "\n".join(lines))
    await _mark_sent(tenant_id, key, ttl=604800)


# ── 7. No-Show Pattern Detection ────────────────────────────────────────

async def _insight_no_show_pattern(tenant_id: int):
    """Detect if no-show rate is above threshold and suggest action."""
    from db import db

    key = f"noshow_pattern_{date.today().isocalendar()[1]}"
    if await _already_sent(tenant_id, key):
        return

    if date.today().weekday() != 0:
        return

    stats = await db.pool.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status IN ('no-show', 'no_show')) as no_shows,
            COUNT(*) FILTER (WHERE status = 'completed') as completed
        FROM appointments
        WHERE tenant_id = $1 AND appointment_datetime > NOW() - INTERVAL '14 days'
    """, tenant_id)

    if not stats or stats["total"] < 10:
        return

    no_show_rate = (stats["no_shows"] / stats["total"] * 100) if stats["total"] > 0 else 0

    if no_show_rate < 15:
        return  # Only alert if concerning

    from services.telegram_notifier import send_proactive_message

    lines = [
        f"⚠️ <b>Tasa de no-shows elevada: {_fmt_pct(no_show_rate)}</b>\n",
        f"▸ Últimos 14 días: {stats['total']} turnos, {stats['no_shows']} no-shows\n",
        "<b>💡 Acción recomendada:</b> Una tasa de no-show por encima del 15% "
        "impacta directamente en la facturación. Dos medidas concretas:\n\n"
        "1. Activá el playbook <b>Escudo Anti-Ausencias</b> (recordatorio 24h antes con "
        "botones de confirmar/reprogramar)\n"
        "2. Activá el playbook <b>Segundo Aviso</b> (si no confirman en 2h, "
        "un segundo recordatorio más directo)\n\n"
        "Con ambos activos, la tasa de no-show baja típicamente al 5-8%."
    ]

    await send_proactive_message(tenant_id, "\n".join(lines))
    await _mark_sent(tenant_id, key, ttl=604800)


# Register with scheduler — every 12 hours
scheduler.add_job(evaluate_business_insights, 43200, run_at_startup=False)
