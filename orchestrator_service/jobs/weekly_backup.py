"""
weekly_backup.py — Automated weekly backup sent to Telegram.

Generates a full platform backup ZIP and sends it as a document
to all authorized Telegram users. Runs weekly (every 7 days).
Also runs at startup (first deploy).
"""

import logging
import os
import uuid
from datetime import datetime

from .scheduler import scheduler

logger = logging.getLogger(__name__)


async def run_weekly_backup():
    """Generate backup for all tenants and send ZIP to Telegram."""
    try:
        from db import db
        if not db.pool:
            return

        from services.telegram_bot import _bots

        # Only run for tenants with active Telegram bots
        active_tenants = list(_bots.keys())
        if not active_tenants:
            logger.info("[weekly_backup] No active Telegram bots, skipping")
            return

        # Dedup: check if we already ran this week
        try:
            from services.relay import get_redis
            r = get_redis()
            if r:
                dedup_key = "weekly_backup:last_run"
                last_run = await r.get(dedup_key)
                if last_run:
                    logger.info(f"[weekly_backup] Already ran this week ({last_run}), skipping")
                    return
                # Mark as ran for 6 days (run again after ~7 days)
                await r.setex(dedup_key, 518400, datetime.now().isoformat())
        except Exception:
            pass

        for tenant_id in active_tenants:
            try:
                await _backup_and_send(tenant_id)
            except Exception as e:
                logger.error(f"[weekly_backup] Failed for tenant {tenant_id}: {e}")

    except Exception as e:
        logger.error(f"[weekly_backup] Global error: {e}")


async def _backup_and_send(tenant_id: int):
    """Generate backup ZIP and send to Telegram for one tenant."""
    from services.backup_service import generate_backup
    from services.relay import get_redis

    task_id = str(uuid.uuid4())
    logger.info(f"[weekly_backup] Starting backup for tenant {tenant_id} (task: {task_id})")

    # Generate the backup
    await generate_backup(tenant_id, task_id)

    # Get the zip path from Redis
    r = get_redis()
    if not r:
        logger.error("[weekly_backup] Redis not available after backup generation")
        return

    key = f"backup:progress:{task_id}"
    data = await r.hgetall(key)

    if not data or data.get("status") != "done":
        logger.error(f"[weekly_backup] Backup did not complete: status={data.get('status') if data else 'no data'}")
        return

    zip_path = data.get("zip_path", "")
    if not zip_path or not os.path.isfile(zip_path):
        logger.error(f"[weekly_backup] ZIP file not found: {zip_path}")
        return

    zip_size_mb = os.path.getsize(zip_path) / 1024 / 1024

    # Get clinic name for the message
    from db import db
    clinic_name = await db.pool.fetchval(
        "SELECT clinic_name FROM tenants WHERE id = $1", tenant_id
    ) or "ClinicForge"

    # Send to all authorized Telegram users
    from services.telegram_bot import _bots
    app = _bots.get(tenant_id)
    if not app:
        logger.warning(f"[weekly_backup] No Telegram bot for tenant {tenant_id}")
        return

    from db import db as db_pool
    rows = await db_pool.fetch(
        "SELECT telegram_chat_id FROM telegram_authorized_users "
        "WHERE tenant_id = $1 AND is_active = true",
        tenant_id,
    )

    if not rows:
        logger.info(f"[weekly_backup] No authorized Telegram users for tenant {tenant_id}")
        return

    from core.credentials import decrypt_value

    date_str = datetime.now().strftime("%d/%m/%Y")
    caption = (
        f"📦 <b>Backup Semanal — {clinic_name}</b>\n\n"
        f"📅 Fecha: {date_str}\n"
        f"📊 Tamaño: {zip_size_mb:.1f} MB\n\n"
        f"Este archivo contiene una copia de seguridad completa de todos los datos de la clínica. "
        f"Guardalo en un lugar seguro."
    )

    sent_count = 0
    bot = app.bot

    for row in rows:
        try:
            chat_id = int(decrypt_value(row["telegram_chat_id"]))

            # Telegram limit: 50MB for documents via bot API
            if zip_size_mb > 50:
                # Too large for Telegram — send message with info
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"📦 <b>Backup Semanal — {clinic_name}</b>\n\n"
                        f"📅 Fecha: {date_str}\n"
                        f"📊 Tamaño: {zip_size_mb:.1f} MB\n\n"
                        f"⚠️ El archivo es demasiado grande para enviarlo por Telegram (máximo 50 MB). "
                        f"Descargalo manualmente desde la app: Configuración → Mantenimiento → Generar Backup."
                    ),
                    parse_mode="HTML",
                )
            else:
                # Send as document
                with open(zip_path, "rb") as f:
                    await bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename=f"backup_{clinic_name.replace(' ', '_')}_{datetime.now().strftime('%Y-%m-%d')}.zip",
                        caption=caption,
                        parse_mode="HTML",
                    )

            sent_count += 1
            logger.info(f"[weekly_backup] ZIP sent to chat {chat_id} for tenant {tenant_id}")

        except Exception as e:
            logger.error(f"[weekly_backup] Failed to send to chat: {e}")

    logger.info(f"[weekly_backup] Backup sent to {sent_count} users for tenant {tenant_id} ({zip_size_mb:.1f} MB)")

    # Cleanup: delete the ZIP file after sending
    try:
        os.remove(zip_path)
        await r.delete(key)
        await r.delete(f"backup:lock:{tenant_id}")
    except Exception:
        pass


# Register: every 7 days (604800s), run at startup
scheduler.add_job(run_weekly_backup, 604800, run_at_startup=True)
