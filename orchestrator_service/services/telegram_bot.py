"""
telegram_bot.py — Nova Telegram Bot (runs inside orchestrator as background task).

Polling mode — no webhook needed. Directly calls execute_nova_tool()
without HTTP overhead. Starts on orchestrator boot, stops on shutdown.

Flow:
  User message → python-telegram-bot polling → verify authorized user
  → build Nova prompt → OpenAI Chat Completions + tool loop
  → execute_nova_tool() directly → response → sendMessage

Media support:
  Voice/Audio → Whisper transcription → buffer
  Photo       → GPT-4o vision + classification → buffer
  Document    → GPT-4o vision (PDF/image) → buffer

Buffer:
  Sliding-window Redis buffer (12s text / 20s media) accumulates messages
  and processes them together when silence is detected.
"""
import asyncio
import base64
import io
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
HISTORY_TTL = 1800       # 30 min conversation memory
MAX_HISTORY_MESSAGES = 40  # keep last 40 messages (20 exchanges)

# ── Buffer constants ──────────────────────────────────────────────────────────
BUFFER_TTL_TEXT = 12    # seconds — text messages
BUFFER_TTL_MEDIA = 20   # seconds — audio/photo/document
MIN_REMAINING_TTL = 4   # extend timer if less than this remains

# ── Vision Prompts ────────────────────────────────────────────────────────────
VISION_PROMPT = (
    "Describe esta imagen en el contexto de una clínica dental.\n"
    "Si es un comprobante de pago/transferencia bancaria: extraé monto, titular, CBU/alias, fecha.\n"
    "Si es un documento clínico (radiografía, foto intraoral): describí hallazgos clínicos.\n"
    "Si es otro tipo de imagen: describí brevemente.\n"
    "Respondé en español, máximo 3 oraciones."
)

PDF_ANALYSIS_PROMPT = (
    "Analizá este documento PDF en el contexto de una clínica dental.\n"
    "Extraé la información más relevante: tipo de documento, datos del paciente si los hay,\n"
    "montos, diagnósticos, tratamientos mencionados.\n"
    "Respondé en español, máximo 5 oraciones."
)


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
        from db import db as db_pool
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

async def _get_conversation_history(tenant_id: int, chat_id: int) -> list:
    """Load conversation history from Redis."""
    try:
        redis = _get_redis()
        key = f"tg_history:{tenant_id}:{chat_id}"
        data = redis.get(key)
        if data:
            history = json.loads(data if isinstance(data, str) else data.decode())
            return history[-MAX_HISTORY_MESSAGES:]
        return []
    except Exception as e:
        logger.warning(f"Failed to load Telegram history: {e}")
        return []


async def _save_conversation_history(
    tenant_id: int, chat_id: int, history: list
) -> None:
    """Save conversation history to Redis with TTL."""
    try:
        redis = _get_redis()
        key = f"tg_history:{tenant_id}:{chat_id}"
        # Only keep user/assistant messages (no tool calls — they bloat history)
        trimmed = [
            m for m in history
            if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
        ][-MAX_HISTORY_MESSAGES:]
        redis.setex(key, HISTORY_TTL, json.dumps(trimmed))
    except Exception as e:
        logger.warning(f"Failed to save Telegram history: {e}")


async def _process_with_nova(
    text: str, tenant_id: int, user_role: str, user_id: str, display_name: str,
    chat_id: int = 0,
) -> tuple:
    """Process a message through Nova with conversation history. Returns (response_text, tools_called)."""
    from services.nova_tools import execute_nova_tool, nova_tools_for_chat_completions

    try:
        import openai
        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Build system prompt — SAME as Nova Realtime, page=telegram
        try:
            from db import db as db_pool
            clinic_row = await db_pool.fetchrow(
                "SELECT clinic_name FROM tenants WHERE id = $1", tenant_id
            )
            clinic_name = clinic_row["clinic_name"] if clinic_row else "Clínica"
        except Exception:
            clinic_name = "Clínica"

        from main import build_nova_system_prompt
        system_prompt = build_nova_system_prompt(clinic_name, "telegram", user_role, tenant_id)

        # Convert tool schemas
        cc_tools = nova_tools_for_chat_completions()

        # Load conversation history
        history = await _get_conversation_history(tenant_id, chat_id) if chat_id else []

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": text})

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
                response_text = choice.message.content or ""
                # Save user + assistant to history
                history.append({"role": "user", "content": text})
                history.append({"role": "assistant", "content": response_text})
                await _save_conversation_history(tenant_id, chat_id, history)
                return (response_text, tools_called)

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
        response_text = final.choices[0].message.content or ""
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": response_text})
        await _save_conversation_history(tenant_id, chat_id, history)
        return (response_text, tools_called)

    except Exception as e:
        logger.error(f"Nova Telegram processing error: {e}", exc_info=True)
        return (f"Error procesando tu consulta: {str(e)[:200]}", [])


# ── Media Processing Helpers ──────────────────────────────────────────────────

async def _transcribe_audio(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Transcribe audio bytes using OpenAI Whisper API. Returns transcribed text."""
    import openai
    client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename

    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
    )
    return transcript.text


async def _analyze_image_bytes(
    image_bytes: bytes, mime_type: str = "image/jpeg", caption: str = ""
) -> dict:
    """
    Analyze image bytes with GPT-4o vision.
    Returns {description, is_payment, is_medical}.
    """
    import openai
    client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    b64 = base64.b64encode(image_bytes).decode()
    prompt_text = VISION_PROMPT
    if caption:
        prompt_text += f"\nCaption del usuario: {caption}"

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
            ],
        }],
        max_tokens=500,
    )
    description = response.choices[0].message.content or ""

    # Classify using existing classifier
    is_payment = False
    is_medical = False
    try:
        from services.image_classifier import classify_message
        classification = await classify_message(caption or "", None, description)
        is_payment = classification.get("is_payment", False)
        is_medical = classification.get("is_medical", False)
    except Exception as e:
        logger.warning(f"Image classification failed: {e}")

    return {
        "description": description,
        "is_payment": is_payment,
        "is_medical": is_medical,
    }


async def _analyze_pdf_bytes(pdf_bytes: bytes, filename: str = "document.pdf") -> str:
    """
    Analyze PDF bytes with GPT-4o vision using base64 inline encoding.
    Returns a textual description of the document.
    """
    import openai
    client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    b64 = base64.b64encode(pdf_bytes).decode()

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": PDF_ANALYSIS_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:application/pdf;base64,{b64}"}},
            ],
        }],
        max_tokens=500,
    )
    return response.choices[0].message.content or ""


async def _typing_loop(chat, cancel_event: asyncio.Event) -> None:
    """Send typing action every 4 seconds until cancel_event is set."""
    while not cancel_event.is_set():
        try:
            await chat.send_action("typing")
        except Exception:
            break
        try:
            await asyncio.wait_for(cancel_event.wait(), timeout=4)
            break
        except asyncio.TimeoutError:
            continue


# ── Redis Buffer ──────────────────────────────────────────────────────────────

def _get_redis():
    """Get Redis client via relay module. Returns None if unavailable."""
    try:
        from services.relay import get_redis
        return get_redis()
    except Exception:
        return None


async def _enqueue_to_buffer(
    tenant_id: int,
    chat_id: int,
    content: str,
    is_media: bool,
    update: Update,
    context,
) -> None:
    """
    Push content to Redis buffer with sliding TTL timer.
    Spawns a consumer task if one is not already running.
    Falls back to direct processing if Redis is unavailable.
    """
    r = _get_redis()
    if r is None:
        logger.warning("Telegram buffer: Redis unavailable, processing directly")
        await _process_and_respond(content, tenant_id, chat_id, update, context)
        return

    buffer_key = f"tg_buffer:{tenant_id}:{chat_id}"
    timer_key = f"tg_timer:{tenant_id}:{chat_id}"
    lock_key = f"tg_lock:{tenant_id}:{chat_id}"

    ttl = BUFFER_TTL_MEDIA if is_media else BUFFER_TTL_TEXT

    try:
        await r.rpush(buffer_key, content)

        current_ttl = await r.ttl(timer_key)
        if current_ttl < MIN_REMAINING_TTL or current_ttl < ttl:
            await r.setex(timer_key, ttl, "1")

        lock_set = await r.set(lock_key, "1", ex=60, nx=True)
        if lock_set:
            asyncio.create_task(
                _telegram_buffer_consumer(tenant_id, chat_id, update, context)
            )
    except Exception as e:
        logger.error(f"Telegram buffer enqueue failed: {e}")
        # Fallback: process directly
        await _process_and_respond(content, tenant_id, chat_id, update, context)


async def _telegram_buffer_consumer(
    tenant_id: int,
    chat_id: int,
    update: Update,
    context,
) -> None:
    """
    Wait for silence (timer expiry), drain the buffer, process combined input,
    and send the response. Holds a lock to prevent duplicate consumers.
    """
    r = _get_redis()
    if r is None:
        return

    timer_key = f"tg_timer:{tenant_id}:{chat_id}"
    buffer_key = f"tg_buffer:{tenant_id}:{chat_id}"
    lock_key = f"tg_lock:{tenant_id}:{chat_id}"

    try:
        # Debounce: wait until timer expires (silence window)
        while True:
            ttl = await r.ttl(timer_key)
            if ttl <= 0:
                break
            await asyncio.sleep(min(ttl, 2))

        # Drain buffer
        messages = await r.lrange(buffer_key, 0, -1)
        await r.delete(buffer_key)

        if not messages:
            return

        combined = "\n".join(
            m.decode() if isinstance(m, bytes) else m for m in messages
        )

        await _process_and_respond(combined, tenant_id, chat_id, update, context)

    except Exception as e:
        logger.error(f"Telegram buffer consumer error: {e}", exc_info=True)
    finally:
        try:
            await r.delete(lock_key)
        except Exception:
            pass


async def _process_and_respond(
    text: str,
    tenant_id: int,
    chat_id: int,
    update: Update,
    context,
) -> None:
    """
    Process text through Nova and send the response to the chat.
    Shared by both buffer consumer and direct fallback paths.
    """
    user_info = await _verify_user(tenant_id, chat_id)
    if not user_info:
        return

    # Typing indicator during processing
    cancel_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _typing_loop(update.effective_chat, cancel_typing)
    )

    try:
        response_text, tools_called = await _process_with_nova(
            text=text,
            tenant_id=tenant_id,
            user_role=user_info["user_role"],
            user_id=str(chat_id),
            display_name=user_info["display_name"],
            chat_id=chat_id,
        )
    finally:
        cancel_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except (asyncio.CancelledError, Exception):
            pass

    if tools_called:
        logger.info(
            f"Telegram Nova: {user_info['display_name']} → "
            f"{len(tools_called)} tools: {', '.join(tools_called)}"
        )

    # Audit log
    try:
        from db import db as db_pool
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

    if not response_text:
        response_text = "Procesé tu consulta pero no obtuve respuesta. Intentá reformular."

    chunks = chunk_message(response_text)
    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        try:
            await update.effective_chat.send_message(
                chunk,
                reply_markup=QUICK_ACTIONS if is_last else None,
            )
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await update.effective_chat.send_message(chunk)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            try:
                await update.effective_chat.send_message(chunk[:4096])
            except Exception:
                pass


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
    """Handle any text message — auth, rate-limit, then buffer."""
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

    await _enqueue_to_buffer(
        tenant_id=tenant_id,
        chat_id=chat_id,
        content=text,
        is_media=False,
        update=update,
        context=context,
    )


async def _handle_voice(update: Update, context) -> None:
    """Handle voice notes and audio files: transcribe → buffer."""
    if not update.message:
        return

    chat_id = update.effective_chat.id
    tenant_id = context.bot_data.get("tenant_id", 1)

    # Auth check
    user_info = await _verify_user(tenant_id, chat_id)
    if not user_info:
        await update.message.reply_text(
            "🔒 No tenés autorización para usar Nova."
        )
        return

    # Determine source: voice note or audio file
    voice = update.message.voice
    audio = update.message.audio
    source = voice or audio
    if not source:
        return

    duration = getattr(source, "duration", 0) or 0
    filename = "voice.ogg"
    if audio and audio.file_name:
        filename = audio.file_name

    # Typing indicator during transcription
    cancel_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _typing_loop(update.effective_chat, cancel_typing)
    )

    try:
        tg_file = await source.get_file()
        audio_bytearray = await tg_file.download_as_bytearray()
        audio_bytes = bytes(audio_bytearray)

        transcribed = await _transcribe_audio(audio_bytes, filename)
    except Exception as e:
        logger.error(f"Telegram voice transcription failed: {e}", exc_info=True)
        cancel_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except (asyncio.CancelledError, Exception):
            pass
        await update.message.reply_text(
            "No pude transcribir el audio. Intentá de nuevo o escribí el mensaje."
        )
        return
    finally:
        cancel_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except (asyncio.CancelledError, Exception):
            pass

    enriched = f'[AUDIO ({duration}s): "{transcribed}"]'

    # Log multimedia interaction
    try:
        from db import db as db_pool
        await db_pool.execute(
            """INSERT INTO automation_logs (tenant_id, log_type, details, created_at)
               VALUES ($1, 'nova_telegram_media', $2::jsonb, NOW())""",
            tenant_id,
            json.dumps({
                "chat_id": chat_id,
                "display_name": user_info["display_name"],
                "media_type": "voice",
                "duration_s": duration,
                "transcription": transcribed[:300],
            }),
        )
    except Exception:
        pass

    await _enqueue_to_buffer(
        tenant_id=tenant_id,
        chat_id=chat_id,
        content=enriched,
        is_media=True,
        update=update,
        context=context,
    )


async def _handle_photo(update: Update, context) -> None:
    """Handle photos: vision analysis → classify → buffer."""
    if not update.message or not update.message.photo:
        return

    chat_id = update.effective_chat.id
    tenant_id = context.bot_data.get("tenant_id", 1)

    # Auth check
    user_info = await _verify_user(tenant_id, chat_id)
    if not user_info:
        await update.message.reply_text(
            "🔒 No tenés autorización para usar Nova."
        )
        return

    caption = update.message.caption or ""

    # Typing indicator during vision analysis
    cancel_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _typing_loop(update.effective_chat, cancel_typing)
    )

    try:
        # Download the largest available photo
        largest_photo = update.message.photo[-1]
        tg_file = await largest_photo.get_file()
        img_bytearray = await tg_file.download_as_bytearray()
        img_bytes = bytes(img_bytearray)

        result = await _analyze_image_bytes(img_bytes, "image/jpeg", caption)
    except Exception as e:
        logger.error(f"Telegram photo analysis failed: {e}", exc_info=True)
        cancel_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except (asyncio.CancelledError, Exception):
            pass
        await update.message.reply_text(
            "No pude analizar la imagen. Intentá de nuevo."
        )
        return
    finally:
        cancel_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except (asyncio.CancelledError, Exception):
            pass

    description = result.get("description", "")
    is_payment = result.get("is_payment", False)
    is_medical = result.get("is_medical", False)

    # Build enriched content
    enriched = f'[IMAGEN: "{description}"]'
    if caption:
        enriched += f'\nCaption: {caption}'
    if is_payment:
        enriched += "\nPROBABLE COMPROBANTE DE PAGO — usar verify_payment_receipt"

    # Log multimedia interaction
    try:
        from db import db as db_pool
        await db_pool.execute(
            """INSERT INTO automation_logs (tenant_id, log_type, details, created_at)
               VALUES ($1, 'nova_telegram_media', $2::jsonb, NOW())""",
            tenant_id,
            json.dumps({
                "chat_id": chat_id,
                "display_name": user_info["display_name"],
                "media_type": "photo",
                "is_payment": is_payment,
                "is_medical": is_medical,
                "description": description[:300],
            }),
        )
    except Exception:
        pass

    await _enqueue_to_buffer(
        tenant_id=tenant_id,
        chat_id=chat_id,
        content=enriched,
        is_media=True,
        update=update,
        context=context,
    )


async def _handle_document(update: Update, context) -> None:
    """Handle documents: validate → download → analyze → buffer (PDF/image only)."""
    if not update.message or not update.message.document:
        return

    chat_id = update.effective_chat.id
    tenant_id = context.bot_data.get("tenant_id", 1)

    # Auth check
    user_info = await _verify_user(tenant_id, chat_id)
    if not user_info:
        await update.message.reply_text(
            "🔒 No tenés autorización para usar Nova."
        )
        return

    doc = update.message.document
    mime_type = doc.mime_type or ""
    file_name = doc.file_name or "document"
    file_size = doc.file_size or 0
    caption = update.message.caption or ""

    # Validate mime type
    allowed_mime_prefixes = ("application/pdf", "image/")
    if not any(mime_type.startswith(p) for p in allowed_mime_prefixes):
        await update.message.reply_text(
            "Solo puedo procesar archivos PDF e imágenes."
        )
        return

    # Validate size: 5MB max for PDFs
    max_size = 5 * 1024 * 1024  # 5MB
    if file_size > max_size:
        size_mb = file_size / (1024 * 1024)
        await update.message.reply_text(
            f"El archivo es muy grande ({size_mb:.1f}MB). El máximo es 5MB."
        )
        return

    # Typing indicator during analysis
    cancel_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _typing_loop(update.effective_chat, cancel_typing)
    )

    try:
        tg_file = await doc.get_file()
        doc_bytearray = await tg_file.download_as_bytearray()
        doc_bytes = bytes(doc_bytearray)

        if mime_type.startswith("image/"):
            result = await _analyze_image_bytes(doc_bytes, mime_type, caption)
            description = result.get("description", "")
            is_payment = result.get("is_payment", False)
            enriched = f'[DOCUMENTO ({file_name}): "{description}"]'
            if caption:
                enriched += f'\nCaption: {caption}'
            if is_payment:
                enriched += "\nPROBABLE COMPROBANTE DE PAGO — usar verify_payment_receipt"
        else:
            # PDF
            description = await _analyze_pdf_bytes(doc_bytes, file_name)
            enriched = f'[DOCUMENTO ({file_name}): "{description}"]'
            if caption:
                enriched += f'\nCaption: {caption}'
            # Classify PDF description for payment detection
            try:
                from services.image_classifier import classify_message
                classification = await classify_message(caption or "", None, description)
                if classification.get("is_payment", False):
                    enriched += "\nPROBABLE COMPROBANTE DE PAGO — usar verify_payment_receipt"
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Telegram document analysis failed: {e}", exc_info=True)
        cancel_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except (asyncio.CancelledError, Exception):
            pass
        await update.message.reply_text(
            "No pude analizar el documento. Intentá de nuevo."
        )
        return
    finally:
        cancel_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except (asyncio.CancelledError, Exception):
            pass

    # Log multimedia interaction
    try:
        from db import db as db_pool
        await db_pool.execute(
            """INSERT INTO automation_logs (tenant_id, log_type, details, created_at)
               VALUES ($1, 'nova_telegram_media', $2::jsonb, NOW())""",
            tenant_id,
            json.dumps({
                "chat_id": chat_id,
                "display_name": user_info["display_name"],
                "media_type": "document",
                "file_name": file_name,
                "mime_type": mime_type,
                "description": description[:300],
            }),
        )
    except Exception:
        pass

    await _enqueue_to_buffer(
        tenant_id=tenant_id,
        chat_id=chat_id,
        content=enriched,
        is_media=True,
        update=update,
        context=context,
    )


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
        chat_id=chat_id,
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

        # Register media handlers BEFORE the text handler so they take priority
        app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, _handle_voice))
        app.add_handler(MessageHandler(filters.PHOTO, _handle_photo))
        app.add_handler(MessageHandler(filters.Document.ALL, _handle_document))

        # Text and command handlers
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
        from db import db as db_pool
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
        from db import db as db_pool
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
