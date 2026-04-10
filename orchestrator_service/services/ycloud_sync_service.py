"""
YCloud Full Message Sync Service.

Implements background sync of WhatsApp messages from YCloud API:
- Cursor-based pagination (100 msgs/page, max 10k)
- Rate limiting with exponential backoff
- Redis progress tracking
- Media download to filesystem

Design: openspec/changes/ycloud-sync/design.md
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from models import WhatsAppMessage, Tenant
from ycloud_client import (
    YCloudClient,
    RateLimitError,
    MediaSizeError,
    normalize_phone_e164,
)

logger = logging.getLogger(__name__)

# Constants from design
MAX_MESSAGES = 10000
PAGE_SIZE = 100
SYNC_TIMEOUT_MINUTES = 30
LOCK_TTL_SECONDS = 30 * 60  # 30 min

# Backoff: 1s -> 2s -> 4s -> 8s -> max 60s
INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 60.0
MAX_RETRIES = 5

# Redis keys
LOCK_KEY_PREFIX = "ycloud_sync_lock"
PROGRESS_KEY_PREFIX = "ycloud_sync"


def _get_redis():
    """Get Redis client using relay pattern."""
    from services.relay import get_redis

    return get_redis()


def _get_progress_key(tenant_id: int, task_id: str) -> str:
    """Generate Redis key for sync progress."""
    return f"{PROGRESS_KEY_PREFIX}:{tenant_id}:{task_id}"


def _get_lock_key(tenant_id: int) -> str:
    """Generate Redis key for sync lock."""
    return f"{LOCK_KEY_PREFIX}:{tenant_id}"


async def _acquire_lock(tenant_id: int) -> bool:
    """Acquire lock for tenant sync. Returns True if acquired."""
    r = _get_redis()
    lock_key = _get_lock_key(tenant_id)

    # SET NX with TTL
    result = r.set(lock_key, "1", nx=True, ex=LOCK_TTL_SECONDS)
    return bool(result)


async def _release_lock(tenant_id: int) -> None:
    """Release lock for tenant sync."""
    r = _get_redis()
    lock_key = _get_lock_key(tenant_id)
    r.delete(lock_key)


async def _update_progress(
    tenant_id: int,
    task_id: str,
    status: str,
    messages_fetched: int = 0,
    messages_saved: int = 0,
    media_downloaded: int = 0,
    errors: Optional[List[str]] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> None:
    """Update sync progress in Redis."""
    r = _get_redis()
    key = _get_progress_key(tenant_id, task_id)

    progress = {
        "task_id": task_id,
        "status": status,
        "tenant_id": tenant_id,
        "messages_fetched": messages_fetched,
        "messages_saved": messages_saved,
        "media_downloaded": media_downloaded,
        "errors": errors or [],
        "started_at": started_at.isoformat() if started_at else None,
        "completed_at": completed_at.isoformat() if completed_at else None,
    }

    # TTL: timeout + 5 min buffer
    r.setex(key, (SYNC_TIMEOUT_MINUTES + 5) * 60, json.dumps(progress))


async def _get_progress(tenant_id: int, task_id: str) -> Optional[Dict[str, Any]]:
    """Get sync progress from Redis."""
    r = _get_redis()
    key = _get_progress_key(tenant_id, task_id)

    data = r.get(key)
    if data:
        return json.loads(data)
    return None


async def _fetch_with_backoff(
    client: YCloudClient,
    cursor: Optional[str] = None,
) -> dict[str, Any]:
    """
    Fetch messages with exponential backoff on rate limiting.

    Raises:
        RateLimitError: After MAX_RETRIES failures
    """
    backoff = INITIAL_BACKOFF
    retries = 0

    while retries < MAX_RETRIES:
        try:
            return await client.fetch_messages(cursor=cursor, limit=PAGE_SIZE)
        except RateLimitError as e:
            retries += 1
            if retries >= MAX_RETRIES:
                logger.error(f"Max retries ({MAX_RETRIES}) exceeded for rate limit")
                raise

            wait_time = min(backoff, MAX_BACKOFF)
            logger.warning(
                f"Rate limited (attempt {retries}/{MAX_RETRIES}), "
                f"waiting {wait_time}s before retry"
            )
            await asyncio.sleep(wait_time)
            backoff *= 2


def _get_uploads_dir() -> Path:
    """Get uploads directory path."""
    uploads_dir = os.getenv("UPLOADS_DIR", os.path.join(os.getcwd(), "uploads"))
    return Path(uploads_dir)


def _get_media_path(tenant_id: int, message_id: str, extension: str) -> Path:
    """Get media file path for a message."""
    media_dir = _get_uploads_dir() / str(tenant_id) / "whatsapp_media"
    media_dir.mkdir(parents=True, exist_ok=True)
    return media_dir / f"{message_id}.{extension}"


async def _download_and_save_media(
    client: YCloudClient,
    tenant_id: int,
    message: dict,
    message_db_id: int,
) -> bool:
    """
    Download and save media from message to filesystem.

    Returns:
        True if media was downloaded successfully, False otherwise
    """
    media_id = message.get("mediaId") or message.get("media_id")
    if not media_id:
        return False

    try:
        # Get media URL
        media_info = await client.get_media_url(media_id)
        url = media_info.get("url")
        if not url:
            logger.warning(f"No media URL for message {message_db_id}")
            return False

        # Determine file extension from mime type
        mime_type = media_info.get("mime_type", "application/octet-stream")
        ext_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "audio/ogg": "ogg",
            "audio/mpeg": "mp3",
            "video/mp4": "mp4",
            "application/pdf": "pdf",
        }
        extension = ext_map.get(mime_type, "bin")

        # Download media
        content = await client.download_media(url, timeout=30)

        # Save to filesystem
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


def _parse_ycloud_message(message: dict, tenant_id: int) -> dict:
    """
    Parse YCloud message format to DB schema.

    YCloud message format example:
    {
        "id": "ym_xxxxx",
        "wamid": "wamid.xxx",
        "from": "+54911...",
        "to": "+549...",
        "type": "text",
        "text": {"body": "Hello"},
        "image": {"id": "media_xxx", "mimeType": "image/jpeg"},
        "timestamp": "2026-04-10T10:00:00Z"
    }
    """
    msg_type = message.get("type", "text")
    direction = "inbound" if message.get("direction") == "inbound" else "outbound"

    # Extract content based on message type
    content = None
    media_id = None
    media_mime_type = None
    media_filename = None

    if msg_type == "text":
        content = message.get("text", {}).get("body")
    elif msg_type == "image":
        media_id = message.get("image", {}).get("id")
        media_mime_type = message.get("image", {}).get("mimeType")
    elif msg_type == "video":
        media_id = message.get("video", {}).get("id")
        media_mime_type = message.get("video", {}).get("mimeType")
    elif msg_type == "audio":
        media_id = message.get("audio", {}).get("id")
        media_mime_type = message.get("audio", {}).get("mimeType")
    elif msg_type == "document":
        media_id = message.get("document", {}).get("id")
        media_mime_type = message.get("document", {}).get("mimeType")
        media_filename = message.get("document", {}).get("filename")
    elif msg_type == "interactive":
        content = message.get("interactive", {}).get("button_reply", {}).get("title")

    # Parse timestamp
    created_at = message.get("timestamp")
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            created_at = datetime.utcnow()
    elif not created_at:
        created_at = datetime.utcnow()

    # Normalize phone numbers to E.164
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


async def start_sync(
    db: Session,
    tenant_id: int,
    password: str,
    background_tasks=None,
) -> Dict[str, Any]:
    """
    Start full message sync for a tenant.

    Entry point for BackgroundTasks.

    Args:
        db: Database session
        tenant_id: Tenant ID to sync
        password: YCloud API password (validated before calling)
        background_tasks: FastAPI BackgroundTasks instance

    Returns:
        dict with task_id, status
    """
    # Check if lock exists (another sync running)
    if not await _acquire_lock(tenant_id):
        return {
            "task_id": None,
            "status": "error",
            "error": "Sync already running for this tenant",
        }

    # Get tenant config for YCloud credentials
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        await _release_lock(tenant_id)
        return {"task_id": None, "status": "error", "error": "Tenant not found"}

    config = tenant.config or {}
    ycloud_api_key = config.get("ycloud_api_key")
    ycloud_business_number = config.get("ycloud_business_number")

    if not ycloud_api_key:
        await _release_lock(tenant_id)
        return {
            "task_id": None,
            "status": "error",
            "error": "YCloud API key not configured",
        }

    # Generate task ID
    task_id = f"sync_{tenant_id}_{uuid.uuid4().hex[:8]}"
    started_at = datetime.utcnow()

    # Initialize progress in Redis
    await _update_progress(
        tenant_id=tenant_id,
        task_id=task_id,
        status="processing",
        started_at=started_at,
    )

    # Create client
    client = YCloudClient(
        api_key=ycloud_api_key, business_number=ycloud_business_number
    )

    # Run sync in background
    if background_tasks:
        background_tasks.add_task(
            _run_sync,
            db=db,
            client=client,
            tenant_id=tenant_id,
            task_id=task_id,
        )
    else:
        # Run synchronously for testing
        await _run_sync(db, client, tenant_id, task_id)

    return {
        "task_id": task_id,
        "status": "processing",
        "started_at": started_at.isoformat(),
    }


async def _run_sync(
    db: Session,
    client: YCloudClient,
    tenant_id: int,
    task_id: str,
) -> None:
    """
    Run the actual sync process.

    Fetches messages page by page, persists to DB, downloads media.
    """
    cursor = None
    total_fetched = 0
    total_saved = 0
    total_media = 0
    errors = []
    started_at = datetime.utcnow()

    try:
        while total_fetched < MAX_MESSAGES:
            # Check if cancelled (by reading progress status)
            progress = await _get_progress(tenant_id, task_id)
            if progress and progress.get("status") == "cancelled":
                logger.info(f"Sync {task_id} was cancelled")
                break

            # Fetch page with backoff
            try:
                result = await _fetch_with_backoff(client, cursor)
            except RateLimitError as e:
                errors.append(f"Rate limit exceeded: {e}")
                break
            except Exception as e:
                errors.append(f"Fetch error: {e}")
                break

            messages = result.get("messages", [])
            if not messages:
                break

            total_fetched += len(messages)

            # Persist messages
            for msg in messages:
                try:
                    msg_data = _parse_ycloud_message(msg, tenant_id)

                    # Upsert: check if exists by external_id
                    existing = (
                        db.query(WhatsAppMessage)
                        .filter(
                            and_(
                                WhatsAppMessage.tenant_id == tenant_id,
                                WhatsAppMessage.external_id == msg_data["external_id"],
                            )
                        )
                        .first()
                    )

                    if existing:
                        # Update existing
                        for key, value in msg_data.items():
                            setattr(existing, key, value)
                        existing.synced_at = datetime.utcnow()
                        msg_db_id = existing.id
                    else:
                        # Insert new
                        msg_obj = WhatsAppMessage(**msg_data)
                        db.add(msg_obj)
                        db.flush()
                        msg_db_id = msg_obj.id

                    total_saved += 1

                    # Download media if present
                    if msg_data.get("media_id"):
                        media_downloaded = await _download_and_save_media(
                            client, tenant_id, msg, msg_db_id
                        )
                        if media_downloaded:
                            total_media += 1
                            # Update media_url in DB
                            if existing:
                                ext = (
                                    msg_data.get("media_filename", "").split(".")[-1]
                                    or "bin"
                                )
                                existing.media_url = f"/uploads/{tenant_id}/whatsapp_media/{msg_db_id}.{ext}"

                except Exception as e:
                    error_msg = f"Failed to persist message {msg.get('id')}: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue

            db.commit()

            # Update progress
            await _update_progress(
                tenant_id=tenant_id,
                task_id=task_id,
                status="processing",
                messages_fetched=total_fetched,
                messages_saved=total_saved,
                media_downloaded=total_media,
                errors=errors[-10:],  # Keep last 10 errors
                started_at=started_at,
            )

            # Next page
            cursor = result.get("next_cursor")
            if not cursor:
                break

            # Small delay between pages to avoid overwhelming the API
            await asyncio.sleep(0.5)

        # Sync completed
        completed_at = datetime.utcnow()
        final_status = "completed" if not errors else "completed_with_errors"

        await _update_progress(
            tenant_id=tenant_id,
            task_id=task_id,
            status=final_status,
            messages_fetched=total_fetched,
            messages_saved=total_saved,
            media_downloaded=total_media,
            errors=errors[-20:],  # Keep last 20 errors
            started_at=started_at,
            completed_at=completed_at,
        )

        logger.info(
            f"Sync {task_id} completed: {total_fetched} fetched, "
            f"{total_saved} saved, {total_media} media"
        )

    except Exception as e:
        logger.error(f"Sync {task_id} failed: {e}")
        errors.append(f"Sync failed: {e}")

        await _update_progress(
            tenant_id=tenant_id,
            task_id=task_id,
            status="error",
            messages_fetched=total_fetched,
            messages_saved=total_saved,
            media_downloaded=total_media,
            errors=errors,
            started_at=started_at,
            completed_at=datetime.utcnow(),
        )

    finally:
        await _release_lock(tenant_id)


async def cancel_sync(tenant_id: int, task_id: str) -> bool:
    """
    Cancel a running sync by marking status in Redis.

    The sync task checks progress periodically and stops when cancelled.
    """
    progress = await _get_progress(tenant_id, task_id)
    if not progress:
        return False

    if progress.get("status") not in ("processing", "queued"):
        return False

    # Mark as cancelled - the sync loop will pick this up
    await _update_progress(
        tenant_id=tenant_id,
        task_id=task_id,
        status="cancelled",
        messages_fetched=progress.get("messages_fetched", 0),
        messages_saved=progress.get("messages_saved", 0),
        media_downloaded=progress.get("media_downloaded", 0),
        started_at=datetime.fromisoformat(progress["started_at"])
        if progress.get("started_at")
        else None,
        completed_at=datetime.utcnow(),
    )

    return True
