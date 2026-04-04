"""
telegram_service — Nova Telegram Bot Microservice.

Receives Telegram webhook messages, validates authorized users,
forwards to orchestrator for Nova processing, returns responses.

Architecture mirrors whatsapp_service:
  Telegram Cloud → webhook → this service → orchestrator → response → Telegram
"""
import logging
import json
from contextlib import asynccontextmanager
from typing import Dict

import httpx
from fastapi import FastAPI, Request, Response
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import ORCHESTRATOR_URL, ADMIN_TOKEN, TELEGRAM_SERVICE_PORT
from message_handler import (
    process_message,
    handle_start,
    handle_help,
    handle_status,
    clear_auth_cache,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("telegram_service")

# ── Per-tenant bot instances ──────────────────────────────────────────────────
# Key: access_token → {tenant_id, bot_app, bot_token, webhook_secret}
_bots: Dict[str, dict] = {}
# Key: tenant_id → access_token (reverse lookup)
_tenant_tokens: Dict[int, str] = {}


async def _load_tenant_bots():
    """
    Load all configured Telegram bots on startup.
    Queries orchestrator for tenants with Telegram configured.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Get all tenants
            resp = await client.get(
                f"{ORCHESTRATOR_URL}/admin/tenants",
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )
            if resp.status_code != 200:
                logger.warning("Could not load tenants for Telegram bots")
                return

            tenants = resp.json()
            for tenant in tenants:
                tenant_id = tenant.get("id")
                if not tenant_id:
                    continue

                # Check if Telegram is configured for this tenant
                try:
                    config_resp = await client.get(
                        f"{ORCHESTRATOR_URL}/admin/telegram/config",
                        headers={
                            "X-Admin-Token": ADMIN_TOKEN,
                            "X-Tenant-Id": str(tenant_id),
                        },
                    )
                    if config_resp.status_code == 200:
                        config = config_resp.json()
                        if config.get("configured") and config.get("_bot_token"):
                            await _init_bot(
                                tenant_id=tenant_id,
                                bot_token=config["_bot_token"],
                                access_token=config.get("_access_token", ""),
                                webhook_secret=config.get("_webhook_secret", ""),
                                clinic_name=tenant.get("clinic_name", "Clínica"),
                            )
                except Exception as e:
                    logger.warning(
                        f"Could not load Telegram config for tenant {tenant_id}: {e}"
                    )

    except Exception as e:
        logger.error(f"Error loading tenant bots: {e}")


async def _init_bot(
    tenant_id: int,
    bot_token: str,
    access_token: str,
    webhook_secret: str,
    clinic_name: str = "Clínica",
):
    """Initialize a Telegram bot Application for a tenant."""
    try:
        app = Application.builder().token(bot_token).updater(None).build()

        # Register handlers
        app.add_handler(CommandHandler("start", handle_start))
        app.add_handler(CommandHandler("help", handle_help))
        app.add_handler(CommandHandler("ayuda", handle_help))
        app.add_handler(CommandHandler("status", handle_status))
        app.add_handler(CommandHandler("estado", handle_status))
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_message)
        )

        # Store tenant context in bot_data
        app.bot_data["tenant_id"] = tenant_id
        app.bot_data["clinic_name"] = clinic_name

        # Initialize the application
        await app.initialize()
        await app.start()

        _bots[access_token] = {
            "tenant_id": tenant_id,
            "bot_app": app,
            "bot_token": bot_token,
            "webhook_secret": webhook_secret,
        }
        _tenant_tokens[tenant_id] = access_token

        logger.info(
            f"Telegram bot initialized for tenant {tenant_id} "
            f"({clinic_name}) — token {access_token[:8]}..."
        )

    except Exception as e:
        logger.error(f"Error initializing bot for tenant {tenant_id}: {e}")


# ── FastAPI app ──────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load bots. Shutdown: stop bots."""
    logger.info("Telegram service starting — loading tenant bots...")
    await _load_tenant_bots()
    logger.info(f"Loaded {len(_bots)} Telegram bot(s)")
    yield
    # Shutdown
    for token, bot_info in _bots.items():
        try:
            await bot_info["bot_app"].stop()
            await bot_info["bot_app"].shutdown()
        except Exception as e:
            logger.warning(f"Error stopping bot {token[:8]}...: {e}")
    logger.info("Telegram service stopped")


app = FastAPI(
    title="ClinicForge Telegram Service",
    description="Nova AI Telegram Bot — webhook receiver",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "telegram",
        "bots_loaded": len(_bots),
    }


@app.post("/telegram/webhook/{access_token}")
async def telegram_webhook(access_token: str, request: Request):
    """
    Receive Telegram webhook updates.

    Each tenant has a unique access_token in their webhook URL
    for routing: /telegram/webhook/{access_token}
    """
    # 1. Resolve tenant from access_token
    bot_info = _bots.get(access_token)
    if not bot_info:
        # Maybe bot was configured after startup — try lazy load
        logger.warning(
            f"Unknown access_token {access_token[:8]}... — rejecting"
        )
        return Response(status_code=404)

    # 2. Validate secret token header
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected_secret = bot_info.get("webhook_secret", "")
    if expected_secret and secret_header != expected_secret:
        logger.warning(
            f"Invalid secret token for tenant {bot_info['tenant_id']}"
        )
        return Response(status_code=403)

    # 3. Parse update and process
    try:
        raw = await request.json()
        bot_app: Application = bot_info["bot_app"]
        update = Update.de_json(raw, bot_app.bot)
        await bot_app.process_update(update)
    except Exception as e:
        logger.error(f"Error processing Telegram update: {e}", exc_info=True)

    # Always return 200 to Telegram (avoid retries)
    return Response(status_code=200)


@app.post("/telegram/reload/{tenant_id}")
async def reload_bot(tenant_id: int, request: Request):
    """
    Reload a bot for a specific tenant.
    Called by orchestrator when Telegram config changes.
    """
    # Verify admin token
    admin_token = request.headers.get("X-Admin-Token", "")
    if admin_token != ADMIN_TOKEN:
        return Response(status_code=403)

    # Stop existing bot if running
    old_token = _tenant_tokens.get(tenant_id)
    if old_token and old_token in _bots:
        try:
            await _bots[old_token]["bot_app"].stop()
            await _bots[old_token]["bot_app"].shutdown()
        except Exception:
            pass
        del _bots[old_token]
        del _tenant_tokens[tenant_id]

    # Clear auth cache for this tenant
    clear_auth_cache()

    # Re-fetch config and init
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            config_resp = await client.get(
                f"{ORCHESTRATOR_URL}/admin/telegram/config",
                headers={
                    "X-Admin-Token": ADMIN_TOKEN,
                    "X-Tenant-Id": str(tenant_id),
                },
            )
            if config_resp.status_code == 200:
                config = config_resp.json()
                if config.get("configured") and config.get("_bot_token"):
                    await _init_bot(
                        tenant_id=tenant_id,
                        bot_token=config["_bot_token"],
                        access_token=config.get("_access_token", ""),
                        webhook_secret=config.get("_webhook_secret", ""),
                    )
                    return {"status": "reloaded", "tenant_id": tenant_id}

        return {"status": "not_configured", "tenant_id": tenant_id}

    except Exception as e:
        logger.error(f"Error reloading bot for tenant {tenant_id}: {e}")
        return {"status": "error", "detail": str(e)}


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=TELEGRAM_SERVICE_PORT)
