"""
message_handler.py — Process incoming Telegram messages through Nova.

Flow:
1. Validate chat_id against authorized users (call orchestrator)
2. Show typing indicator
3. Send message to orchestrator's /admin/nova/telegram-message
4. Format and chunk response
5. Send back to Telegram chat
"""
import logging
import time
from typing import Optional, Dict, Any

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ORCHESTRATOR_URL, ADMIN_TOKEN
from response_formatter import chunk_message, format_response

logger = logging.getLogger(__name__)

# Cache authorized users per tenant to avoid constant HTTP calls
# Key: f"{tenant_id}:{chat_id}", Value: {user_role, display_name}
_auth_cache: Dict[str, Dict[str, str]] = {}
_CACHE_TTL = 300  # 5 minutes — cleared on each verify call

# Simple in-memory rate limiter
_last_message: Dict[int, float] = {}  # chat_id → timestamp
_RATE_LIMIT_SECONDS = 2  # Min seconds between messages per user


def _check_rate_limit(chat_id: int) -> bool:
    """Returns True if allowed, False if rate limited."""
    now = time.time()
    last = _last_message.get(chat_id, 0)
    if now - last < _RATE_LIMIT_SECONDS:
        return False
    _last_message[chat_id] = now
    return True


async def verify_user(tenant_id: int, chat_id: int) -> Optional[Dict[str, str]]:
    """
    Check if a Telegram chat_id is authorized for this tenant.
    Returns {user_role, display_name} or None.
    """
    cache_key = f"{tenant_id}:{chat_id}"
    if cache_key in _auth_cache:
        return _auth_cache[cache_key]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{ORCHESTRATOR_URL}/admin/telegram/verify-user/{tenant_id}/{chat_id}",
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("authorized"):
                    result = {
                        "user_role": data.get("user_role", "ceo"),
                        "display_name": data.get("display_name", "Usuario"),
                    }
                    _auth_cache[cache_key] = result
                    return result
    except Exception as e:
        logger.error(f"Error verifying user {chat_id}: {e}")

    return None


def clear_auth_cache():
    """Clear the auth cache (called periodically or on config change)."""
    _auth_cache.clear()


async def process_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Main message handler — processes any text message from Telegram.
    """
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    text = update.message.text
    tenant_id = context.bot_data.get("tenant_id", 1)

    # 0. Rate limiting
    if not _check_rate_limit(chat_id):
        await update.message.reply_text(
            "Esperá unos segundos antes de enviar otro mensaje."
        )
        return

    # 1. Verify authorized user
    user_info = await verify_user(tenant_id, chat_id)
    if not user_info:
        await update.message.reply_text(
            "No tenés autorización para usar Nova. "
            "Contactá al administrador de la clínica para que agregue tu Telegram ID."
        )
        return

    # 2. Show typing indicator
    await update.effective_chat.send_action("typing")

    # 3. Call orchestrator
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/admin/nova/telegram-message",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "tenant_id": tenant_id,
                    "user_role": user_info["user_role"],
                    "user_id": str(chat_id),
                    "display_name": user_info["display_name"],
                },
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )

            if resp.status_code != 200:
                logger.error(
                    f"Orchestrator returned {resp.status_code}: {resp.text[:200]}"
                )
                await update.message.reply_text(
                    "Hubo un error procesando tu consulta. Intentá de nuevo en unos segundos."
                )
                return

            result = resp.json()
            response_text = result.get("response_text", "")
            tools_called = result.get("tools_called", [])

            if tools_called:
                logger.info(
                    f"Nova Telegram: {user_info['display_name']} → {len(tools_called)} tools: {', '.join(tools_called)}"
                )

    except httpx.TimeoutException:
        logger.error(f"Orchestrator timeout for chat_id {chat_id}")
        await update.message.reply_text(
            "La consulta tardó demasiado. Intentá con algo más específico."
        )
        return
    except Exception as e:
        logger.error(f"Error calling orchestrator: {e}")
        await update.message.reply_text(
            "Hubo un error de conexión. Intentá de nuevo."
        )
        return

    # 4. Format and send response
    if not response_text:
        response_text = "Procesé tu consulta pero no obtuve una respuesta. Intentá reformular."

    formatted = format_response(response_text)
    chunks = chunk_message(formatted)

    # Quick action keyboard (shown after last chunk only)
    quick_actions = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Agenda", callback_data="__agenda"),
            InlineKeyboardButton("💰 Pendientes", callback_data="__pendientes"),
        ],
        [
            InlineKeyboardButton("📊 Resumen", callback_data="__resumen"),
            InlineKeyboardButton("❓ Ayuda", callback_data="__ayuda"),
        ],
    ])

    import asyncio
    from telegram.error import RetryAfter

    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        try:
            await update.message.reply_text(
                chunk,
                reply_markup=quick_actions if is_last else None,
            )
        except RetryAfter as e:
            # Telegram rate limit — retry once after the requested delay
            retry_after = getattr(e, "retry_after", 5)
            logger.warning(
                f"Telegram 429 for tenant={tenant_id} chat_id={chat_id}, "
                f"retrying after {retry_after}s"
            )
            await asyncio.sleep(retry_after)
            try:
                await update.message.reply_text(chunk)
            except Exception as retry_err:
                logger.error(
                    f"Retry failed for tenant={tenant_id} chat_id={chat_id}: {retry_err}"
                )
        except Exception as e:
            logger.error(
                f"Error sending chunk to tenant={tenant_id} chat_id={chat_id}: {e}"
            )
            # Fallback: resend as plain text (strips any MarkdownV2 formatting)
            try:
                plain = chunk.replace("*", "").replace("_", "").replace("`", "").replace("\\", "")
                await update.message.reply_text(plain[:4096])
            except Exception as fallback_err:
                logger.error(
                    f"Plain text fallback also failed for tenant={tenant_id} "
                    f"chat_id={chat_id}: {fallback_err}"
                )


async def handle_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handler for /start command."""
    chat_id = update.effective_chat.id
    tenant_id = context.bot_data.get("tenant_id", 1)
    clinic_name = context.bot_data.get("clinic_name", "la clínica")

    user_info = await verify_user(tenant_id, chat_id)
    if not user_info:
        await update.message.reply_text(
            "No tenés autorización para usar Nova. "
            "Contactá al administrador para que agregue tu Telegram ID."
        )
        return

    await update.message.reply_text(
        f"👋 Hola {user_info['display_name']}! Soy Nova, "
        f"la inteligencia artificial de {clinic_name}.\n\n"
        "Podés preguntarme cualquier cosa:\n"
        "📋 Agenda y turnos\n"
        "👤 Pacientes y fichas médicas\n"
        "💰 Cobros y presupuestos\n"
        "🦷 Odontograma\n"
        "📄 Informes y documentos\n"
        "📊 Estadísticas y analytics\n"
        "💬 Mensajes a pacientes\n\n"
        "Escribime lo que necesites! 🚀",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📋 Ver agenda", callback_data="__agenda"),
                InlineKeyboardButton("📊 Resumen", callback_data="__resumen"),
            ],
        ]),
    )


async def handle_help(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handler for /help command."""
    chat_id = update.effective_chat.id
    tenant_id = context.bot_data.get("tenant_id", 1)

    user_info = await verify_user(tenant_id, chat_id)
    if not user_info:
        await update.message.reply_text("No tenés autorización.")
        return

    await update.message.reply_text(
        "Ejemplos de lo que puedo hacer:\n\n"
        "AGENDA:\n"
        "• \"Qué turnos hay hoy\"\n"
        "• \"Agendá turno para García\"\n"
        "• \"Cancelá el de las 15\"\n"
        "• \"Quién viene ahora\"\n\n"
        "PACIENTES:\n"
        "• \"Buscá a Martínez\"\n"
        "• \"Resumen completo de García\"\n"
        "• \"Cargale alergia a penicilina\"\n\n"
        "COBROS:\n"
        "• \"Cobrale a García\"\n"
        "• \"Quién debe plata\"\n"
        "• \"Facturación del día\"\n\n"
        "PRESUPUESTOS:\n"
        "• \"Creá presupuesto para López\"\n"
        "• \"Mandá el presupuesto por email\"\n\n"
        "INFORMES:\n"
        "• \"Resumen de la semana\"\n"
        "• \"Rendimiento de Laura\"\n"
        "• \"Generá informe de García\"\n\n"
        "ODONTOGRAMA:\n"
        "• \"Caries en la 16 y 18\"\n"
        "• \"Mostrame el odontograma\"\n\n"
        "Escribí cualquier cosa y yo la resuelvo!\n\n"
        "Para configurar usuarios y ver instrucciones de setup, "
        "ingresá a ClinicForge → Configuración → Telegram."
    )


async def handle_status(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handler for /status command — quick clinic summary."""
    chat_id = update.effective_chat.id
    tenant_id = context.bot_data.get("tenant_id", 1)

    user_info = await verify_user(tenant_id, chat_id)
    if not user_info:
        await update.message.reply_text("No tenés autorización.")
        return

    # Send typing while processing
    await update.effective_chat.send_action("typing")

    # Call orchestrator with a status request
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/admin/nova/telegram-message",
                json={
                    "chat_id": chat_id,
                    "text": "Dame un resumen rápido: agenda de hoy, facturación pendiente y presupuestos activos",
                    "tenant_id": tenant_id,
                    "user_role": user_info["user_role"],
                    "user_id": str(chat_id),
                    "display_name": user_info["display_name"],
                },
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )

            if resp.status_code == 200:
                result = resp.json()
                chunks = chunk_message(result.get("response_text", "Sin datos"))
                for chunk in chunks:
                    await update.message.reply_text(chunk)
            else:
                await update.message.reply_text("Error obteniendo el resumen.")
    except Exception as e:
        logger.error(f"Error in /status: {e}")
        await update.message.reply_text("Error de conexión. Intentá de nuevo.")


# Inline keyboard callback queries
_QUICK_ACTIONS = {
    "__agenda": "Qué turnos hay hoy",
    "__pendientes": "Qué turnos están sin cobrar y quién debe plata",
    "__resumen": "Dame el resumen de la semana",
    "__ayuda": "/help",
}


async def handle_callback_query(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle inline keyboard button presses."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()  # Acknowledge the button press

    action = _QUICK_ACTIONS.get(query.data)
    if not action:
        return

    if action == "/help":
        # Reuse help handler
        await handle_help(update, context)
        return

    # Simulate a text message with the mapped query
    chat_id = update.effective_chat.id
    tenant_id = context.bot_data.get("tenant_id", 1)

    user_info = await verify_user(tenant_id, chat_id)
    if not user_info:
        await query.message.reply_text("No tenés autorización.")
        return

    await update.effective_chat.send_action("typing")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/admin/nova/telegram-message",
                json={
                    "chat_id": chat_id,
                    "text": action,
                    "tenant_id": tenant_id,
                    "user_role": user_info["user_role"],
                    "user_id": str(chat_id),
                    "display_name": user_info["display_name"],
                },
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )
            if resp.status_code == 200:
                result = resp.json()
                chunks = chunk_message(result.get("response_text", "Sin datos"))
                for chunk in chunks:
                    await query.message.reply_text(chunk)
            else:
                await query.message.reply_text("❌ Error procesando la consulta.")
    except Exception as e:
        logger.error(f"Callback query error: {e}")
        await query.message.reply_text("❌ Error de conexión.")
