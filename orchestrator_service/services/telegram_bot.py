"""
telegram_bot.py — Nova Telegram Bot (runs inside orchestrator as background task).

Polling mode — no webhook needed. Directly calls execute_nova_tool()
without HTTP overhead. Starts on orchestrator boot, stops on shutdown.

Flow:
  User message → python-telegram-bot polling → verify authorized user
  → build Nova prompt → OpenAI Chat Completions + tool loop
  → execute_nova_tool() directly → response → sendMessage
"""
import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Optional, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.error import RetryAfter

logger = logging.getLogger(__name__)

# ── State ─────────────────────────────────────────────────────────────────────
_bots: Dict[int, Application] = {}  # tenant_id → Application
_polling_tasks: Dict[int, asyncio.Task] = {}  # tenant_id → polling task
_rate_limiter: Dict[int, float] = {}  # chat_id → last_message_time
RATE_LIMIT_SECONDS = 2
MAX_TOOL_ROUNDS = 10
TELEGRAM_MAX_LEN = 4096


# ── Message Chunking ──────────────────────────────────────────────────────────

def chunk_message(text: str, max_len: int = TELEGRAM_MAX_LEN) -> List[str]:
    if not text:
        return [""]
    if len(text) <= max_len:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n\n", 0, max_len)
        if split_at < max_len // 3:
            split_at = text.rfind("\n", 0, max_len)
        if split_at < max_len // 4:
            split_at = text.rfind(" ", 0, max_len)
        if split_at < 1:
            split_at = max_len
        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip("\n ")
    return chunks


# ── Auth Check ────────────────────────────────────────────────────────────────

_auth_cache: Dict[str, Dict[str, str]] = {}


async def _verify_user(tenant_id: int, chat_id: int) -> Optional[Dict[str, str]]:
    """Check if chat_id is authorized for this tenant. Uses in-memory cache."""
    cache_key = f"{tenant_id}:{chat_id}"
    if cache_key in _auth_cache:
        return _auth_cache[cache_key]

    try:
        from db import pool as db_pool
        from core.credentials import decrypt_value

        rows = await db_pool.fetch(
            "SELECT telegram_chat_id, display_name, user_role FROM telegram_authorized_users "
            "WHERE tenant_id = $1 AND is_active = true",
            tenant_id,
        )
        for row in rows:
            try:
                decrypted_id = decrypt_value(row["telegram_chat_id"])
                if str(chat_id) == decrypted_id:
                    result = {
                        "user_role": row["user_role"],
                        "display_name": row["display_name"],
                    }
                    _auth_cache[cache_key] = result
                    return result
            except Exception:
                continue
    except Exception as e:
        logger.error(f"Telegram auth check failed: {e}")

    return None


def clear_auth_cache():
    _auth_cache.clear()


# ── Nova Processing (DIRECT — no HTTP) ────────────────────────────────────────

async def _process_with_nova(
    text: str, tenant_id: int, user_role: str, user_id: str, display_name: str
) -> tuple:
    """Process a message through Nova. Returns (response_text, tools_called)."""
    from services.nova_tools import execute_nova_tool, nova_tools_for_chat_completions

    try:
        import openai
        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Build system prompt
        try:
            from db import pool as db_pool
            clinic_row = await db_pool.fetchrow(
                "SELECT clinic_name FROM tenants WHERE id = $1", tenant_id
            )
            clinic_name = clinic_row["clinic_name"] if clinic_row else "Clínica"
        except Exception:
            clinic_name = "Clínica"

        system_prompt = f"""Sos Nova, la inteligencia artificial operativa de "{clinic_name}". Comunicación por Telegram.
Rol: {user_role}. Tenant: {tenant_id}. Usuario: {display_name}.

REGLAS TELEGRAM:
- Respuestas CONCISAS (máximo 3000 chars). Datos concretos, no explicaciones largas.
- Formateá con texto plano legible: bullets •, separadores ---, mayúsculas para títulos.
- 1-2 emojis máximo por respuesta.
- Ejecutar tools PRIMERO, hablar después. NUNCA "voy a buscar" — HACELO.
- Encadenar 3-5 tools es NORMAL. Sin confirmación intermedia.
- "Hola" = resumen_semana automáticamente.
- NUNCA digas "no puedo". Tenés acceso a TODO via tools.
"""

        # Convert tool schemas
        cc_tools = nova_tools_for_chat_completions()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

        tools_called = []

        # Agentic tool loop
        for _round in range(MAX_TOOL_ROUNDS):
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=cc_tools,
                tool_choice="auto",
                temperature=0.3,
            )

            choice = response.choices[0]

            # No tool calls — we have the final answer
            if not choice.message.tool_calls:
                return (choice.message.content or "", tools_called)

            # Process tool calls
            messages.append(choice.message)
            for tc in choice.message.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                logger.info(f"🤖 Telegram Nova tool: {tool_name}({list(tool_args.keys())})")
                tool_result = await execute_nova_tool(
                    name=tool_name,
                    args=tool_args,
                    tenant_id=tenant_id,
                    user_role=user_role,
                    user_id=user_id,
                )
                tools_called.append(tool_name)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(tool_result),
                })

        # Max rounds reached — get final answer
        final = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        return (final.choices[0].message.content or "", tools_called)

    except Exception as e:
        logger.error(f"Nova Telegram processing error: {e}", exc_info=True)
        return (f"Error procesando tu consulta: {str(e)[:200]}", [])


# ── Handlers ──────────────────────────────────────────────────────────────────

QUICK_ACTIONS = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📋 Agenda", callback_data="__agenda"),
        InlineKeyboardButton("💰 Pendientes", callback_data="__pendientes"),
    ],
    [
        InlineKeyboardButton("📊 Resumen", callback_data="__resumen"),
        InlineKeyboardButton("❓ Ayuda", callback_data="__ayuda"),
    ],
])

QUICK_ACTION_MAP = {
    "__agenda": "Qué turnos hay hoy",
    "__pendientes": "Qué turnos están sin cobrar y quién debe plata",
    "__resumen": "Dame el resumen de la semana",
}


async def _handle_text(update: Update, context) -> None:
    """Handle any text message."""
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    text = update.message.text
    tenant_id = context.bot_data.get("tenant_id", 1)

    # Rate limit
    now = time.time()
    if now - _rate_limiter.get(chat_id, 0) < RATE_LIMIT_SECONDS:
        await update.message.reply_text("⏳ Esperá unos segundos...")
        return
    _rate_limiter[chat_id] = now

    # Auth check
    user_info = await _verify_user(tenant_id, chat_id)
    if not user_info:
        await update.message.reply_text(
            "🔒 No tenés autorización para usar Nova.\n"
            "Pedile al administrador que agregue tu Telegram ID en Configuración → Telegram."
        )
        return

    # Typing indicator
    await update.effective_chat.send_action("typing")

    # Process with Nova
    response_text, tools_called = await _process_with_nova(
        text=text,
        tenant_id=tenant_id,
        user_role=user_info["user_role"],
        user_id=str(chat_id),
        display_name=user_info["display_name"],
    )

    if tools_called:
        logger.info(f"Telegram Nova: {user_info['display_name']} → {len(tools_called)} tools: {', '.join(tools_called)}")

    # Audit log
    try:
        from db import pool as db_pool
        await db_pool.execute(
            """INSERT INTO automation_logs (tenant_id, log_type, details, created_at)
               VALUES ($1, 'nova_telegram', $2::jsonb, NOW())""",
            tenant_id,
            json.dumps({
                "chat_id": chat_id,
                "display_name": user_info["display_name"],
                "message": text[:500],
                "response": (response_text or "")[:500],
                "tools_called": tools_called,
            }),
        )
    except Exception:
        pass

    # Send chunked response
    if not response_text:
        response_text = "Procesé tu consulta pero no obtuve respuesta. Intentá reformular."

    chunks = chunk_message(response_text)
    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        try:
            await update.message.reply_text(
                chunk,
                reply_markup=QUICK_ACTIONS if is_last else None,
            )
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await update.message.reply_text(chunk)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            try:
                await update.message.reply_text(chunk[:4096])
            except Exception:
                pass


async def _handle_start(update: Update, context) -> None:
    chat_id = update.effective_chat.id
    tenant_id = context.bot_data.get("tenant_id", 1)
    clinic_name = context.bot_data.get("clinic_name", "la clínica")

    user_info = await _verify_user(tenant_id, chat_id)
    if not user_info:
        await update.message.reply_text("🔒 No tenés autorización. Contactá al administrador.")
        return

    await update.message.reply_text(
        f"👋 Hola {user_info['display_name']}! Soy Nova, la IA de {clinic_name}.\n\n"
        "Podés preguntarme cualquier cosa:\n"
        "📋 Agenda y turnos\n"
        "👤 Pacientes y fichas\n"
        "💰 Cobros y presupuestos\n"
        "🦷 Odontograma\n"
        "📄 Informes y documentos\n"
        "📊 Estadísticas\n\n"
        "Escribime lo que necesites! 🚀",
        reply_markup=QUICK_ACTIONS,
    )


async def _handle_help(update: Update, context) -> None:
    chat_id = update.effective_chat.id
    tenant_id = context.bot_data.get("tenant_id", 1)

    user_info = await _verify_user(tenant_id, chat_id)
    if not user_info:
        await update.message.reply_text("🔒 No tenés autorización.")
        return

    await update.message.reply_text(
        "📖 Ejemplos de lo que puedo hacer:\n\n"
        "AGENDA:\n"
        "• \"Qué turnos hay hoy\"\n"
        "• \"Agendá turno para García\"\n"
        "• \"Cancelá el de las 15\"\n\n"
        "COBROS:\n"
        "• \"Cobrale a García\"\n"
        "• \"Quién debe plata\"\n"
        "• \"Cobrale la cuota\"\n\n"
        "PACIENTES:\n"
        "• \"Buscá a Martínez\"\n"
        "• \"Resumen completo de García\"\n\n"
        "ODONTOGRAMA:\n"
        "• \"Caries en la 16 y 18\"\n"
        "• \"Mostrame el odontograma\"\n\n"
        "INFORMES:\n"
        "• \"Resumen de la semana\"\n"
        "• \"Generá informe de García\"\n\n"
        "Escribí cualquier cosa y yo la resuelvo! 💪",
    )


async def _handle_callback(update: Update, context) -> None:
    """Handle inline keyboard button presses."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    if query.data == "__ayuda":
        # Fake an update with /help
        await _handle_help(update, context)
        return

    action_text = QUICK_ACTION_MAP.get(query.data)
    if not action_text:
        return

    chat_id = update.effective_chat.id
    tenant_id = context.bot_data.get("tenant_id", 1)

    user_info = await _verify_user(tenant_id, chat_id)
    if not user_info:
        await query.message.reply_text("🔒 No tenés autorización.")
        return

    await update.effective_chat.send_action("typing")

    response_text, tools_called = await _process_with_nova(
        text=action_text,
        tenant_id=tenant_id,
        user_role=user_info["user_role"],
        user_id=str(chat_id),
        display_name=user_info["display_name"],
    )

    chunks = chunk_message(response_text or "Sin datos")
    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        try:
            await query.message.reply_text(
                chunk,
                reply_markup=QUICK_ACTIONS if is_last else None,
            )
        except Exception as e:
            logger.error(f"Callback send error: {e}")


# ── Bot Lifecycle ─────────────────────────────────────────────────────────────

async def _start_bot_polling(tenant_id: int, bot_token: str, clinic_name: str):
    """Start polling for a single tenant's bot."""
    try:
        app = Application.builder().token(bot_token).build()

        # Register handlers
        app.add_handler(CommandHandler("start", _handle_start))
        app.add_handler(CommandHandler("help", _handle_help))
        app.add_handler(CommandHandler("ayuda", _handle_help))
        app.add_handler(CommandHandler("status", lambda u, c: _handle_text(
            type('FakeUpdate', (), {'message': type('Msg', (), {'text': 'Dame resumen rápido: agenda hoy + pendientes + presupuestos', 'reply_text': u.message.reply_text})(), 'effective_chat': u.effective_chat})(),
            c
        )))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text))
        app.add_handler(CallbackQueryHandler(_handle_callback))

        # Store tenant context
        app.bot_data["tenant_id"] = tenant_id
        app.bot_data["clinic_name"] = clinic_name

        _bots[tenant_id] = app

        # Delete any existing webhook (switch to polling)
        try:
            await app.bot.delete_webhook(drop_pending_updates=False)
        except Exception:
            pass

        logger.info(f"🤖 Telegram bot starting polling for tenant {tenant_id} ({clinic_name})")

        # Start polling
        await app.initialize()
        await app.start()
        await app.updater.start_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=False,
        )

        # Keep alive until cancelled
        while True:
            await asyncio.sleep(60)

    except asyncio.CancelledError:
        logger.info(f"🤖 Telegram bot stopping for tenant {tenant_id}")
        if tenant_id in _bots:
            try:
                await _bots[tenant_id].updater.stop()
                await _bots[tenant_id].stop()
                await _bots[tenant_id].shutdown()
            except Exception:
                pass
            del _bots[tenant_id]
    except Exception as e:
        logger.error(f"Telegram bot error for tenant {tenant_id}: {e}", exc_info=True)


async def start_telegram_bots():
    """Load and start all configured Telegram bots. Called from orchestrator lifespan."""
    try:
        from db import pool as db_pool
        from core.credentials import get_tenant_credential, TELEGRAM_BOT_TOKEN

        tenants = await db_pool.fetch("SELECT id, clinic_name FROM tenants")

        for tenant in tenants:
            tenant_id = tenant["id"]
            try:
                token = await get_tenant_credential(tenant_id, TELEGRAM_BOT_TOKEN)
                if token:
                    task = asyncio.create_task(
                        _start_bot_polling(tenant_id, token, tenant["clinic_name"])
                    )
                    _polling_tasks[tenant_id] = task
                    logger.info(f"🤖 Telegram bot queued for tenant {tenant_id}")
            except Exception as e:
                logger.warning(f"Telegram bot load failed for tenant {tenant_id}: {e}")

        if _polling_tasks:
            logger.info(f"🤖 {len(_polling_tasks)} Telegram bot(s) starting...")
        else:
            logger.info("🤖 No Telegram bots configured")

    except Exception as e:
        logger.error(f"Failed to start Telegram bots: {e}")


async def stop_telegram_bots():
    """Stop all running Telegram bots. Called from orchestrator shutdown."""
    for tenant_id, task in _polling_tasks.items():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    _polling_tasks.clear()
    _bots.clear()
    logger.info("🤖 All Telegram bots stopped")


async def reload_telegram_bot(tenant_id: int):
    """Reload a specific tenant's bot (called when config changes)."""
    # Stop existing
    if tenant_id in _polling_tasks:
        _polling_tasks[tenant_id].cancel()
        try:
            await _polling_tasks[tenant_id]
        except (asyncio.CancelledError, Exception):
            pass
        del _polling_tasks[tenant_id]

    clear_auth_cache()

    # Restart if configured
    try:
        from db import pool as db_pool
        from core.credentials import get_tenant_credential, TELEGRAM_BOT_TOKEN

        token = await get_tenant_credential(tenant_id, TELEGRAM_BOT_TOKEN)
        if token:
            tenant = await db_pool.fetchrow(
                "SELECT clinic_name FROM tenants WHERE id = $1", tenant_id
            )
            clinic_name = tenant["clinic_name"] if tenant else "Clínica"
            task = asyncio.create_task(
                _start_bot_polling(tenant_id, token, clinic_name)
            )
            _polling_tasks[tenant_id] = task
            logger.info(f"🤖 Telegram bot reloaded for tenant {tenant_id}")
        else:
            logger.info(f"🤖 Telegram bot removed for tenant {tenant_id} (no token)")
    except Exception as e:
        logger.error(f"Failed to reload Telegram bot for tenant {tenant_id}: {e}")
