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
from typing import Optional, Dict, Any

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from config import ORCHESTRATOR_URL, ADMIN_TOKEN
from response_formatter import chunk_message, format_response

logger = logging.getLogger(__name__)

# Cache authorized users per tenant to avoid constant HTTP calls
# Key: f"{tenant_id}:{chat_id}", Value: {user_role, display_name}
_auth_cache: Dict[str, Dict[str, str]] = {}
_CACHE_TTL = 300  # 5 minutes — cleared on each verify call


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

    for chunk in chunks:
        try:
            await update.message.reply_text(chunk)
        except Exception as e:
            logger.error(f"Error sending chunk to {chat_id}: {e}")
            # Try without formatting as fallback
            try:
                await update.message.reply_text(chunk[:4096])
            except Exception:
                pass


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
        f"Hola {user_info['display_name']}! Soy Nova, "
        f"la inteligencia artificial de {clinic_name}.\n\n"
        "Podés preguntarme cualquier cosa sobre la clínica:\n"
        "• Agenda y turnos\n"
        "• Pacientes y fichas médicas\n"
        "• Cobros y presupuestos\n"
        "• Odontograma\n"
        "• Informes y documentos\n"
        "• Estadísticas y analytics\n"
        "• Mensajes a pacientes\n\n"
        "Escribime lo que necesites!"
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
        "Escribí cualquier cosa y yo la resuelvo!"
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
