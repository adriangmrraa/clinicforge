"""Job de cierre de mes del Motor de Reseñas.

Corre 1 vez al día a las 9:00 hora Argentina; si HOY es el día 1 del mes, manda
a Telegram el resumen del mes que ACABA DE CERRAR: reseñas PEDIDAS vs el objetivo
mensual, por cada tenant que tenga objetivo (>0).

Diseño (decisión Carlos 2026-07-17): se envía la mañana del día 1 (no la noche
del último día) por dos razones:
  1) Llega "a primera hora con los mensajes que se mandan" (lo que pidió Carlos).
  2) El mes anterior ya está 100% cerrado en hora argentina, así que el conteo
     incluye TODAS las reseñas del mes — antes disparaba 20:00 UTC = 17:00 AR del
     último día y se comía las de la tarde/noche.

La ventana [inicio_mes_anterior, inicio_mes_actual) se calcula en Python con TZ
Argentina y se pasa como parámetros al COUNT — NO se depende de NOW()/date_trunc
del servidor (que corre en UTC por omisión).

Best-effort: si el bot de Telegram no corre o algo falla, no rompe nada.
"""
import logging
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:  # py<3.9 fallback
    from backports.zoneinfo import ZoneInfo

from .scheduler import schedule_daily_at

logger = logging.getLogger(__name__)

AR_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


@schedule_daily_at(hour=9, minute=0, tz=AR_TZ)
async def send_reviews_month_closing():
    """Resumen de reseñas del mes cerrado a Telegram, la mañana del día 1."""
    now_ar = datetime.now(AR_TZ)
    # Actuar solo el día 1 (resumen del mes anterior, ya cerrado).
    if now_ar.day != 1:
        return

    # Ventana del mes que cerró, en hora Argentina (tz-aware → asyncpg compara bien
    # contra requested_at que es timestamptz, sin importar la TZ de la sesión).
    this_month_start = now_ar.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (this_month_start - timedelta(days=1)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    mes_nombre = _MESES[prev_month_start.month - 1]

    logger.info(
        f"📊 Motor de Reseñas: cierre de {mes_nombre} "
        f"[{prev_month_start.isoformat()} → {this_month_start.isoformat()})"
    )
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
                    "WHERE tenant_id = $1 AND requested_at >= $2 AND requested_at < $3",
                    tid,
                    prev_month_start,
                    this_month_start,
                )
                or 0
            )
            ok = "✅" if count >= goal else "❌"
            cn = _html.escape((t["clinic_name"] or "la clínica"))
            msg = (
                f"📊 <b>Cierre de {mes_nombre.capitalize()} — Reseñas</b>\n\n"
                f"Se pidieron <b>{count}</b> reseñas (objetivo {goal}) {ok}\n\n"
                f"¡Gracias por el laburo, equipo de {cn}! Arrancamos el mes nuevo 💪"
            )
            try:
                await send_proactive_message(tid, msg)
            except Exception as e:
                logger.warning(f"reviews closing notify failed tenant={tid}: {e}")
    except Exception as e:
        logger.error(f"send_reviews_month_closing error: {e}")
