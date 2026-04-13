"""
YCloud Full Message Sync Service.

Implements background sync of WhatsApp messages from YCloud API:
- Cursor-based pagination (100 msgs/page, max 10k)
- Rate limiting with exponential backoff
- Redis progress tracking
- Media download to filesystem
- Messages stored in whatsapp_messages table
- Also creates chat_conversations + chat_messages for UI display
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ycloud_client import YCloudClient, RateLimitError, MediaSizeError

logger = logging.getLogger(__name__)

# Config
PAGE_SIZE = 100
MAX_MESSAGES = 50000
MAX_RETRIES = 5
INITIAL_BACKOFF = 1
MAX_BACKOFF = 60
LOCK_TTL_SECONDS = 1800  # 30 min
PROGRESS_TTL_SECONDS = 35 * 60  # 35 min


# ── Phone normalization ──────────────────────────────────────────────────

def normalize_phone_e164(phone: str) -> str:
    """Basic E.164 normalization."""
    if not phone:
        return ""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        phone = "+" + phone
    return phone


# ── Redis helpers ────────────────────────────────────────────────────────

def _get_redis():
    """Get Redis client."""
    try:
        from services.relay import get_redis
        return get_redis()
    except Exception:
        return None


async def _acquire_lock(tenant_id: int) -> bool:
    r = _get_redis()
    if not r:
        return True  # No Redis = no lock = allow
    key = f"ycloud_sync_lock:{tenant_id}"
    result = await r.set(key, "1", nx=True, ex=LOCK_TTL_SECONDS)
    return bool(result)


async def _release_lock(tenant_id: int):
    r = _get_redis()
    if r:
        await r.delete(f"ycloud_sync_lock:{tenant_id}")


async def _update_progress(
    tenant_id: int,
    task_id: str,
    status: str = "processing",
    messages_fetched: int = 0,
    messages_saved: int = 0,
    media_downloaded: int = 0,
    errors: list = None,
    started_at: datetime = None,
    completed_at: datetime = None,
):
    r = _get_redis()
    if not r:
        return
    key = f"ycloud_sync:{tenant_id}:{task_id}"
    progress = {
        "task_id": task_id,
        "tenant_id": tenant_id,
        "status": status,
        "messages_fetched": messages_fetched,
        "messages_saved": messages_saved,
        "media_downloaded": media_downloaded,
        "errors": errors or [],
        "started_at": started_at.isoformat() if started_at else None,
        "completed_at": completed_at.isoformat() if completed_at else None,
    }
    await r.setex(key, PROGRESS_TTL_SECONDS, json.dumps(progress))


async def _get_progress(tenant_id: int, task_id: str) -> Optional[dict]:
    r = _get_redis()
    if not r:
        return None
    key = f"ycloud_sync:{tenant_id}:{task_id}"
    raw = await r.get(key)
    if raw:
        return json.loads(raw)
    return None


# ── Fetch with backoff ───────────────────────────────────────────────────

async def _fetch_with_backoff(client: YCloudClient, cursor: Optional[str] = None) -> dict:
    backoff = INITIAL_BACKOFF
    retries = 0
    while retries < MAX_RETRIES:
        try:
            return await client.fetch_messages(cursor=cursor, limit=PAGE_SIZE)
        except RateLimitError:
            retries += 1
            if retries >= MAX_RETRIES:
                raise
            wait_time = min(backoff, MAX_BACKOFF)
            logger.warning(f"Rate limited (attempt {retries}/{MAX_RETRIES}), waiting {wait_time}s")
            await asyncio.sleep(wait_time)
            backoff *= 2
    return {"messages": []}


# ── Media download ───────────────────────────────────────────────────────

def _get_uploads_dir() -> Path:
    uploads_dir = os.getenv("UPLOADS_DIR", os.path.join(os.getcwd(), "uploads"))
    return Path(uploads_dir)


def _get_media_path(tenant_id: int, message_id: str, extension: str) -> Path:
    media_dir = _get_uploads_dir() / str(tenant_id) / "whatsapp_media"
    media_dir.mkdir(parents=True, exist_ok=True)
    return media_dir / f"{message_id}.{extension}"


async def _download_and_save_media(
    client: YCloudClient, tenant_id: int, message: dict, message_db_id: int
) -> bool:
    media_id = message.get("mediaId") or message.get("media_id")
    if not media_id:
        return False
    try:
        media_info = await client.get_media_url(media_id)
        url = media_info.get("url")
        if not url:
            return False
        mime_type = media_info.get("mime_type", "application/octet-stream")
        ext_map = {
            "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp",
            "audio/ogg": "ogg", "audio/mpeg": "mp3", "video/mp4": "mp4",
            "application/pdf": "pdf",
        }
        extension = ext_map.get(mime_type, "bin")
        content = await client.download_media(url, timeout=30)
        media_path = _get_media_path(tenant_id, str(message_db_id), extension)
        media_path.write_bytes(content)
        logger.info(f"Downloaded media for message {message_db_id}: {media_path.name}")
        return True
    except MediaSizeError as e:
        logger.warning(f"Media too large for message {message_db_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to download media for message {message_db_id}: {e}")
        return False


# ── Parse YCloud message ─────────────────────────────────────────────────

def _parse_ycloud_message(message: dict, tenant_id: int, business_number: str = "") -> dict:
    msg_type = message.get("type", "text")

    # Determine direction:
    # YCloud field "direction" may exist, or we infer from whatsappInboundMessage
    raw_direction = message.get("direction", "")
    if raw_direction:
        direction = "inbound" if raw_direction.lower() in ("inbound", "incoming") else "outbound"
    elif message.get("whatsappInboundMessage"):
        direction = "inbound"
    elif business_number:
        # If "from" is the business number → outbound; otherwise inbound
        msg_from = normalize_phone_e164(message.get("from", ""))
        biz = normalize_phone_e164(business_number)
        direction = "outbound" if msg_from == biz else "inbound"
    else:
        direction = "outbound"  # Default if we can't tell

    content = None
    media_id = None
    media_mime_type = None
    media_filename = None

    if msg_type == "text":
        content = (message.get("text") or {}).get("body") if isinstance(message.get("text"), dict) else message.get("text")
    elif msg_type == "image":
        media_id = (message.get("image") or {}).get("id")
        media_mime_type = (message.get("image") or {}).get("mimeType")
        content = (message.get("image") or {}).get("caption")
    elif msg_type == "video":
        media_id = (message.get("video") or {}).get("id")
        media_mime_type = (message.get("video") or {}).get("mimeType")
    elif msg_type == "audio":
        media_id = (message.get("audio") or {}).get("id")
        media_mime_type = (message.get("audio") or {}).get("mimeType")
    elif msg_type == "document":
        media_id = (message.get("document") or {}).get("id")
        media_mime_type = (message.get("document") or {}).get("mimeType")
        media_filename = (message.get("document") or {}).get("filename")
    elif msg_type == "interactive":
        content = (message.get("interactive") or {}).get("button_reply", {}).get("title")
    elif msg_type == "button":
        content = (message.get("button") or {}).get("text")

    created_at = message.get("timestamp")
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            created_at = datetime.now(timezone.utc)
    elif not created_at:
        created_at = datetime.now(timezone.utc)

    from_number = normalize_phone_e164(message.get("from", ""))
    to_number = normalize_phone_e164(message.get("to", ""))

    return {
        "tenant_id": tenant_id,
        "external_id": message.get("id"),
        "wamid": message.get("wamid"),
        "from_number": from_number,
        "to_number": to_number,
        "direction": direction,
        "message_type": msg_type,
        "content": content,
        "media_id": media_id,
        "media_mime_type": media_mime_type,
        "media_filename": media_filename,
        "created_at": created_at,
        "status": "synced",
    }


# ── Main entry point ─────────────────────────────────────────────────────

async def start_sync(
    db,  # Database object (has .pool for asyncpg)
    tenant_id: int,
    password: str,
    background_tasks=None,
) -> Dict[str, Any]:
    """Start full message sync for a tenant."""

    if not await _acquire_lock(tenant_id):
        return {"task_id": None, "status": "error", "error": "Sync already running for this tenant"}

    # Get YCloud credentials from vault
    try:
        from core.credentials import get_tenant_credential, YCLOUD_API_KEY, YCLOUD_WHATSAPP_NUMBER
        ycloud_api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
        ycloud_business_number = await get_tenant_credential(tenant_id, YCLOUD_WHATSAPP_NUMBER)
    except Exception as e:
        await _release_lock(tenant_id)
        return {"task_id": None, "status": "error", "error": f"Failed to get credentials: {e}"}

    if not ycloud_api_key:
        await _release_lock(tenant_id)
        return {"task_id": None, "status": "error", "error": "YCloud API key not configured"}

    task_id = f"sync_{tenant_id}_{uuid.uuid4().hex[:8]}"
    started_at = datetime.now(timezone.utc)

    await _update_progress(tenant_id=tenant_id, task_id=task_id, status="processing", started_at=started_at)

    client = YCloudClient(api_key=ycloud_api_key, business_number=ycloud_business_number)

    if background_tasks:
        background_tasks.add_task(_run_sync, db.pool, client, tenant_id, task_id, ycloud_business_number or "")
    else:
        await _run_sync(db.pool, client, tenant_id, task_id, ycloud_business_number or "")

    return {"task_id": task_id, "status": "processing", "started_at": started_at.isoformat()}


async def _run_sync(pool, client: YCloudClient, tenant_id: int, task_id: str, business_number: str = "") -> None:
    """Run the actual sync process using asyncpg pool."""
    cursor = None
    total_fetched = 0
    total_saved = 0
    total_media = 0
    errors = []
    started_at = datetime.now(timezone.utc)

    try:
        logger.info(f"[ycloud_sync] Starting sync {task_id} for tenant {tenant_id}")

        while total_fetched < MAX_MESSAGES:
            # Check cancellation
            progress = await _get_progress(tenant_id, task_id)
            if progress and progress.get("status") == "cancelled":
                logger.info(f"[ycloud_sync] Sync {task_id} was cancelled")
                break

            # Fetch page
            try:
                result = await _fetch_with_backoff(client, cursor)
            except RateLimitError as e:
                errors.append(f"Rate limit exceeded: {e}")
                logger.error(f"[ycloud_sync] Rate limit exceeded for {task_id}")
                break
            except Exception as e:
                errors.append(f"Fetch error: {e}")
                logger.error(f"[ycloud_sync] Fetch error for {task_id}: {e}")
                break

            messages = result.get("messages") or result.get("items") or []
            if not messages:
                logger.info(f"[ycloud_sync] No more messages for {task_id} (fetched {total_fetched})")
                break

            total_fetched += len(messages)
            logger.info(f"[ycloud_sync] Fetched page: {len(messages)} messages (total: {total_fetched})")

            # Process each message
            for msg in messages:
                try:
                    msg_data = _parse_ycloud_message(msg, tenant_id, business_number)
                    if not msg_data.get("external_id"):
                        continue

                    # Upsert into whatsapp_messages
                    msg_db_id = await pool.fetchval("""
                        INSERT INTO whatsapp_messages
                        (tenant_id, external_id, wamid, from_number, to_number, direction,
                         message_type, content, media_id, media_mime_type, media_filename,
                         created_at, status)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        ON CONFLICT (external_id) DO UPDATE SET
                            content = EXCLUDED.content,
                            synced_at = NOW()
                        RETURNING id
                    """,
                        msg_data["tenant_id"], msg_data["external_id"], msg_data.get("wamid"),
                        msg_data["from_number"], msg_data["to_number"], msg_data["direction"],
                        msg_data["message_type"], msg_data.get("content"),
                        msg_data.get("media_id"), msg_data.get("media_mime_type"),
                        msg_data.get("media_filename"), msg_data["created_at"], msg_data["status"],
                    )

                    total_saved += 1

                    # Also upsert into chat_conversations + chat_messages for UI display
                    external_user_id = msg_data["from_number"] if msg_data["direction"] == "inbound" else msg_data["to_number"]
                    if external_user_id:
                        await _upsert_chat_record(pool, tenant_id, msg_data, external_user_id)

                    # Download media if present
                    if msg_data.get("media_id") and msg_db_id:
                        media_ok = await _download_and_save_media(client, tenant_id, msg, msg_db_id)
                        if media_ok:
                            total_media += 1
                            ext = (msg_data.get("media_filename", "").split(".")[-1] or "bin")
                            await pool.execute(
                                "UPDATE whatsapp_messages SET media_url = $1 WHERE id = $2",
                                f"/uploads/{tenant_id}/whatsapp_media/{msg_db_id}.{ext}", msg_db_id,
                            )

                except Exception as e:
                    error_msg = f"Failed to persist message {msg.get('id')}: {e}"
                    logger.warning(f"[ycloud_sync] {error_msg}")
                    errors.append(error_msg)

            # Update progress
            await _update_progress(
                tenant_id=tenant_id, task_id=task_id, status="processing",
                messages_fetched=total_fetched, messages_saved=total_saved,
                media_downloaded=total_media, errors=errors[-10:], started_at=started_at,
            )

            # Next page
            cursor = result.get("nextCursor") or result.get("next_cursor")
            if not cursor:
                break

            await asyncio.sleep(0.5)

        # Completed
        final_status = "completed" if not errors else "completed_with_errors"
        await _update_progress(
            tenant_id=tenant_id, task_id=task_id, status=final_status,
            messages_fetched=total_fetched, messages_saved=total_saved,
            media_downloaded=total_media, errors=errors[-20:],
            started_at=started_at, completed_at=datetime.now(timezone.utc),
        )
        logger.info(f"[ycloud_sync] Sync {task_id} completed: {total_fetched} fetched, {total_saved} saved, {total_media} media")

    except Exception as e:
        logger.error(f"[ycloud_sync] Sync {task_id} failed: {e}")
        errors.append(f"Sync failed: {e}")
        await _update_progress(
            tenant_id=tenant_id, task_id=task_id, status="error",
            messages_fetched=total_fetched, messages_saved=total_saved,
            media_downloaded=total_media, errors=errors,
            started_at=started_at, completed_at=datetime.now(timezone.utc),
        )

    finally:
        await _release_lock(tenant_id)


async def _upsert_chat_record(pool, tenant_id: int, msg_data: dict, external_user_id: str):
    """Create/update chat_conversations and insert into chat_messages for UI display."""
    try:
        # Get or create conversation
        conv_id = await pool.fetchval(
            "SELECT id FROM chat_conversations WHERE tenant_id = $1 AND channel = 'whatsapp' AND external_user_id = $2",
            tenant_id, external_user_id,
        )
        if not conv_id:
            conv_id = await pool.fetchval("""
                INSERT INTO chat_conversations (tenant_id, channel, provider, external_user_id, display_name, status)
                VALUES ($1, 'whatsapp', 'ycloud', $2, $2, 'active')
                ON CONFLICT DO NOTHING
                RETURNING id
            """, tenant_id, external_user_id)
            # If ON CONFLICT hit, fetch again
            if not conv_id:
                conv_id = await pool.fetchval(
                    "SELECT id FROM chat_conversations WHERE tenant_id = $1 AND channel = 'whatsapp' AND external_user_id = $2",
                    tenant_id, external_user_id,
                )

        if not conv_id:
            return

        # Insert message (skip if duplicate by YCloud external_id stored in platform_metadata)
        role = "user" if msg_data["direction"] == "inbound" else "assistant"
        ext_id = msg_data.get("external_id") or ""
        import json as _json
        platform_meta = _json.dumps({"provider_message_id": ext_id, "source": "ycloud_sync"})

        await pool.execute("""
            INSERT INTO chat_messages (tenant_id, conversation_id, from_number, role, content, created_at, platform_metadata)
            SELECT $1, $2, $3, $4, $5, $6, $7::jsonb
            WHERE NOT EXISTS (
                SELECT 1 FROM chat_messages
                WHERE conversation_id = $2
                  AND platform_metadata->>'provider_message_id' = $8
                  AND $8 != ''
            )
        """,
            tenant_id, conv_id, external_user_id, role,
            msg_data.get("content") or f"[{msg_data['message_type']}]",
            msg_data["created_at"],
            platform_meta,
            ext_id,
        )

        # Update conversation last message
        await pool.execute("""
            UPDATE chat_conversations SET
                last_message_at = GREATEST(last_message_at, $1),
                updated_at = NOW()
            WHERE id = $2
        """, msg_data["created_at"], conv_id)

    except Exception as e:
        logger.warning(f"[ycloud_sync] chat record upsert failed (non-fatal): {e}")


async def cancel_sync(tenant_id: int, task_id: str) -> bool:
    """Cancel a running sync by marking status in Redis."""
    progress = await _get_progress(tenant_id, task_id)
    if not progress:
        return False
    if progress.get("status") not in ("processing", "queued"):
        return False
    await _update_progress(
        tenant_id=tenant_id, task_id=task_id, status="cancelled",
        messages_fetched=progress.get("messages_fetched", 0),
        messages_saved=progress.get("messages_saved", 0),
        media_downloaded=progress.get("media_downloaded", 0),
        started_at=datetime.fromisoformat(progress["started_at"]) if progress.get("started_at") else None,
        completed_at=datetime.now(timezone.utc),
    )
    return True
