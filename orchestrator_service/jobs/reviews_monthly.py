"""Job de cierre de mes del Motor de Reseñas.

Corre 1 vez al día; si HOY es el último día del mes, manda a Telegram el resumen
de reseñas PEDIDAS vs el objetivo mensual, por cada tenant que tenga objetivo (>0).
Best-effort: si el bot de Telegram no corre o algo falla, no rompe nada.
"""
import logging
from datetime import date, timedelta

from .scheduler import schedule_daily_at

logger = logging.getLogger(__name__)


@schedule_daily_at(hour=20, minute=0)
async def send_reviews_month_closing():
    """Resumen de reseñas del mes a Telegram, solo el último día del mes."""
    today = date.today()
    # Si mañana es día 1, hoy es el último día del mes.
    if (today + timedelta(days=1)).day != 1:
        return

    logger.info("📊 Motor de Reseñas: cierre de mes")
    try:
        import html as _html
        from db import db
        from services.telegram_notifier import send_proactive_message

        rows = await db.pool.fetch(
            "SELECT id, clinic_name, COALESCE(review_goal_monthly, 0) AS goal "
            "FROM tenants WHERE COALESCE(review_goal_monthly, 0) > 0"
        )
        for t in rows:
            tid = t["id"]
            goal = int(t["goal"] or 0)
            count = (
                await db.pool.fetchval(
                    "SELECT COUNT(*) FROM review_requests "
                    "WHERE tenant_id = $1 AND requested_at >= date_trunc('month', NOW())",
                    tid,
                )
                or 0
            )
            ok = "✅" if count >= goal else "❌"
            cn = _html.escape((t["clinic_name"] or "la clínica"))
            msg = (
                "📊 <b>Cierre de mes — Reseñas</b>\n\n"
                f"Se pidieron <b>{count}</b> reseñas este mes (objetivo {goal}) {ok}\n\n"
                f"¡Gracias por el laburo, equipo de {cn}! Seguimos el mes que viene 💪"
            )
            try:
                await send_proactive_message(tid, msg)
            except Exception as e:
                logger.warning(f"reviews closing notify failed tenant={tid}: {e}")
    except Exception as e:
        logger.error(f"send_reviews_month_closing error: {e}")
