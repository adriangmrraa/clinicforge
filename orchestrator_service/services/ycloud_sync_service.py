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

    # Determine direction using multiple signals:
    # 1. YCloud "bizType" field: "user_initiated" = inbound, "business_initiated" = outbound
    # 2. YCloud "direction" field (may not exist)
    # 3. Compare from/to against business number
    # 4. "whatsappInboundMessage" nested object
    raw_direction = message.get("direction", "")
    msg_from = normalize_phone_e164(message.get("from", ""))
    msg_to = normalize_phone_e164(message.get("to", ""))
    biz = normalize_phone_e164(business_number) if business_number else ""

    if raw_direction:
        direction = "inbound" if raw_direction.lower() in ("inbound", "incoming") else "outbound"
    elif message.get("whatsappInboundMessage"):
        direction = "inbound"
    elif biz:
        # Business number = the bot. If "from" is the bot → outbound. If "to" is bot → inbound.
        if msg_from == biz:
            direction = "outbound"
        elif msg_to == biz:
            direction = "inbound"
        else:
            # Neither matches — try without +
            biz_bare = biz.lstrip("+")
            if msg_from.lstrip("+") == biz_bare:
                direction = "outbound"
            elif msg_to.lstrip("+") == biz_bare:
                direction = "inbound"
            else:
                direction = "outbound"
    else:
        direction = "outbound"

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

    created_at = message.get("createTime") or message.get("sendTime") or message.get("timestamp")
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
    seen_ids: set = set()  # Track message IDs to detect pagination loops
    started_at = datetime.now(timezone.utc)

    try:
        logger.info(f"[ycloud_sync] Starting sync {task_id} for tenant {tenant_id}, configured biz={business_number}")

        # Auto-detect business number from first page if not matching
        # YCloud's "to" field for outbound messages = business number
        # We find the most common number across from+to — that's the bot
        try:
            probe = await client.fetch_messages(limit=100)
            probe_msgs = probe.get("messages") or probe.get("items") or []
            if probe_msgs:
                from collections import Counter
                all_numbers = []
                for m in probe_msgs:
                    all_numbers.append(normalize_phone_e164(m.get("to", "")))
                    all_numbers.append(normalize_phone_e164(m.get("from", "")))
                # The business number is the one that appears in EVERY message (either as from or to)
                counter = Counter(all_numbers)
                most_common = counter.most_common(1)[0][0] if counter else ""
                if most_common and most_common != normalize_phone_e164(business_number):
                    logger.info(f"[ycloud_sync] Auto-detected business number: {most_common} (configured was: {business_number})")
                    business_number = most_common
        except Exception as e:
            logger.warning(f"[ycloud_sync] Business number auto-detect failed (non-fatal): {e}")

        # Cache for WhatsApp profile names (phone → name)
        # Avoids calling get_contact_profile for the same number multiple times
        contact_names_cache: dict[str, str] = {}

        async def _get_wa_name(phone: str) -> str:
            """Get WhatsApp profile name, cached."""
            if phone in contact_names_cache:
                return contact_names_cache[phone]
            # First check DB patients
            patient_row = await pool.fetchrow(
                "SELECT first_name, last_name FROM patients WHERE tenant_id = $1 AND phone_number = $2 LIMIT 1",
                tenant_id, phone,
            )
            if patient_row:
                name = f"{patient_row['first_name'] or ''} {patient_row['last_name'] or ''}".strip()
                if name:
                    contact_names_cache[phone] = name
                    return name
            # Then try YCloud contact API
            try:
                wa_name = await client.get_contact_profile(phone.lstrip("+"))
                if wa_name:
                    logger.info(f"[ycloud_sync] Got WA name for {phone}: {wa_name}")
                    contact_names_cache[phone] = wa_name
                    return wa_name
                else:
                    # Log first failure to diagnose
                    if len(contact_names_cache) < 3:
                        logger.info(f"[ycloud_sync] No WA name from API for {phone}")
            except Exception as e:
                if len(contact_names_cache) < 3:
                    logger.warning(f"[ycloud_sync] WA name API failed for {phone}: {e}")
            contact_names_cache[phone] = ""
            return ""

        # Iterate by week ranges to get ALL messages (YCloud limits ~100 per query without date filter)
        from datetime import timedelta as _td
        sync_start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)  # Start from Jan 2024
        sync_end_date = datetime.now(timezone.utc) + _td(days=1)  # Tomorrow
        week_start = sync_start_date
        week_number = 0
        total_weeks = int((sync_end_date - sync_start_date).days / 7) + 1

        while week_start < sync_end_date:
            week_end = min(week_start + _td(days=7), sync_end_date)
            week_number += 1

            # Check cancellation
            progress = await _get_progress(tenant_id, task_id)
            if progress and progress.get("status") == "cancelled":
                logger.info(f"[ycloud_sync] Sync {task_id} was cancelled")
                break

            # Fetch all pages for this week
            cursor = None
            week_new = 0
            page_in_week = 0

            while True:
                try:
                    result = await client.fetch_messages(
                        cursor=cursor, limit=100,
                        from_date=week_start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                        to_date=week_end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    )
                except RateLimitError as e:
                    errors.append(f"Rate limit week {week_number}: {e}")
                    logger.warning(f"[ycloud_sync] Rate limit on week {week_number}, waiting 60s")
                    await asyncio.sleep(60)
                    continue
                except Exception as e:
                    errors.append(f"Fetch error week {week_number}: {e}")
                    logger.error(f"[ycloud_sync] Fetch error week {week_number}: {e}")
                    break

                messages = result.get("messages") or result.get("items") or []
                if not messages:
                    break

                # Detect duplicates within this week's pages
                page_ids = {m.get("id") for m in messages if m.get("id")}
                overlap = page_ids & seen_ids
                if overlap and len(overlap) > len(page_ids) * 0.8:
                    break  # All duplicates, move to next week
                seen_ids |= page_ids

                total_fetched += len(messages)
                week_new += len(page_ids)
                page_in_week += 1

                # Process each message in this page
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
                    # external_user_id = the PATIENT phone (not the business number)
                    # Determine patient phone = whichever is NOT the business
                    from_num = msg_data["from_number"]
                    to_num = msg_data["to_number"]

                    if msg_data["direction"] == "inbound":
                        external_user_id = from_num  # Patient sent the message
                    else:
                        external_user_id = to_num  # Bot sent to patient

                    if external_user_id:
                        wa_name = await _get_wa_name(external_user_id)
                        await _upsert_chat_record(pool, tenant_id, msg_data, external_user_id, wa_name)

                    # Download media if present
                    if msg_data.get("media_id") and msg_db_id:
                        media_ok = await _download_and_save_media(client, tenant_id, msg, msg_db_id)
                        if media_ok:
                            total_media += 1
                            orig_filename = msg_data.get("media_filename") or ""
                            ext = orig_filename.split(".")[-1] if "." in orig_filename else "bin"
                            media_rel_path = f"/uploads/{tenant_id}/whatsapp_media/{msg_db_id}.{ext}"

                            # Update whatsapp_messages with media URL
                            await pool.execute(
                                "UPDATE whatsapp_messages SET media_url = $1 WHERE id = $2",
                                media_rel_path, msg_db_id,
                            )

                            # Update chat_messages content_attributes with downloaded URL
                            import json as _json3
                            ext_id_for_media = msg_data.get("external_id") or ""
                            if ext_id_for_media:
                                await pool.execute("""
                                    UPDATE chat_messages SET content_attributes = $1::jsonb
                                    WHERE platform_metadata->>'provider_message_id' = $2
                                """,
                                    _json3.dumps([{
                                        "type": msg_data.get("message_type", "document"),
                                        "url": media_rel_path,
                                        "file_name": orig_filename or f"media_{msg_db_id}.{ext}",
                                        "mime_type": msg_data.get("media_mime_type") or "application/octet-stream",
                                    }]),
                                    ext_id_for_media,
                                )

                            # Register in patient_documents if patient exists (for Archivos tab)
                            patient_phone = external_user_id if msg_data["direction"] == "inbound" else msg_data["to_number"]
                            patient_id = await pool.fetchval(
                                "SELECT id FROM patients WHERE tenant_id = $1 AND phone_number = $2 LIMIT 1",
                                tenant_id, patient_phone,
                            )
                            if patient_id:
                                import json as _json2
                                media_abs = _get_media_path(tenant_id, str(msg_db_id), ext)
                                file_size = media_abs.stat().st_size if media_abs.exists() else 0
                                doc_type = "clinical" if ext == "pdf" else "image" if ext in ("jpg", "png", "webp") else "audio" if ext in ("ogg", "mp3") else "other"
                                # Dedup: don't insert if same file already registered
                                existing_doc = await pool.fetchval(
                                    "SELECT id FROM patient_documents WHERE tenant_id = $1 AND file_path = $2",
                                    tenant_id, str(media_abs),
                                )
                                if not existing_doc:
                                    await pool.execute("""
                                        INSERT INTO patient_documents
                                        (tenant_id, patient_id, file_name, file_path, file_size, mime_type,
                                         document_type, source, source_details)
                                        VALUES ($1, $2, $3, $4, $5, $6, $7, 'ycloud_sync', $8)
                                    """,
                                        tenant_id, patient_id,
                                        orig_filename or f"media_{msg_db_id}.{ext}",
                                        str(media_abs),
                                        file_size,
                                        msg_data.get("media_mime_type") or "application/octet-stream",
                                        doc_type,
                                        _json2.dumps({"ycloud_msg_id": msg_data.get("external_id"), "direction": msg_data["direction"]}),
                                    )

                except Exception as e:
                    error_msg = f"Failed to persist message {msg.get('id')}: {e}"
                    logger.warning(f"[ycloud_sync] {error_msg}")
                    errors.append(error_msg)

                # Update progress after each page
                await _update_progress(
                    tenant_id=tenant_id, task_id=task_id, status="processing",
                    messages_fetched=total_fetched, messages_saved=total_saved,
                    media_downloaded=total_media, errors=errors[-10:], started_at=started_at,
                )

                # Next page within this week
                next_cursor = result.get("nextCursor") or result.get("next_cursor")
                # Also calculate offset-based cursor
                current_offset = result.get("offset", 0)
                page_length = result.get("length", len(messages))
                if next_cursor:
                    cursor = next_cursor
                elif page_length >= 100 and len(messages) >= 100:
                    cursor = str(current_offset + len(messages))
                else:
                    break  # Last page for this week

                await asyncio.sleep(0.3)

            # End of week — log and advance
            if week_new > 0:
                logger.info(
                    f"[ycloud_sync] Week {week_number}/{total_weeks} "
                    f"({week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}): "
                    f"{week_new} new messages, {page_in_week} pages"
                )

            week_start = week_end
            await asyncio.sleep(0.2)

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


async def _upsert_chat_record(pool, tenant_id: int, msg_data: dict, external_user_id: str, wa_name: str = ""):
    """Create/update chat_conversations and insert into chat_messages for UI display."""
    try:
        import json as _json

        # 1. Best name: patient DB name > WhatsApp profile name > phone number
        display_name = wa_name or external_user_id

        # 2. Find existing conversation (by phone, any provider — reuse existing)
        conv_id = await pool.fetchval(
            "SELECT id FROM chat_conversations WHERE tenant_id = $1 AND external_user_id = $2 ORDER BY updated_at DESC LIMIT 1",
            tenant_id, external_user_id,
        )

        if not conv_id:
            # Create new conversation
            conv_id = await pool.fetchval("""
                INSERT INTO chat_conversations (tenant_id, channel, provider, external_user_id, display_name, status)
                VALUES ($1, 'whatsapp', 'ycloud', $2, $3, 'active')
                ON CONFLICT DO NOTHING
                RETURNING id
            """, tenant_id, external_user_id, display_name)
            if not conv_id:
                conv_id = await pool.fetchval(
                    "SELECT id FROM chat_conversations WHERE tenant_id = $1 AND external_user_id = $2 ORDER BY updated_at DESC LIMIT 1",
                    tenant_id, external_user_id,
                )
        else:
            # Update display_name if we have a name
            if display_name and display_name != external_user_id:
                await pool.execute(
                    "UPDATE chat_conversations SET display_name = COALESCE(NULLIF($1, ''), display_name) WHERE id = $2 AND (display_name IS NULL OR display_name = external_user_id)",
                    display_name, conv_id,
                )

        if not conv_id:
            return

        # 3. Insert message (dedup by YCloud external_id)
        role = "user" if msg_data["direction"] == "inbound" else "assistant"
        ext_id = msg_data.get("external_id") or ""
        platform_meta = _json.dumps({"provider_message_id": ext_id, "source": "ycloud_sync"})

        # from_number: for inbound = patient, for outbound = business
        from_num = external_user_id if msg_data["direction"] == "inbound" else msg_data.get("from_number", "")

        # Build content_attributes for media (so it shows in chat UI)
        content_attrs = []
        if msg_data.get("media_id"):
            media_type = msg_data.get("message_type", "document")
            content_attrs.append({
                "type": media_type,
                "url": None,  # Will be updated after download
                "file_name": msg_data.get("media_filename") or f"media.{media_type}",
                "mime_type": msg_data.get("media_mime_type") or "application/octet-stream",
                "ycloud_media_id": msg_data.get("media_id"),
            })
        content_attrs_json = _json.dumps(content_attrs)

        await pool.execute("""
            INSERT INTO chat_messages (tenant_id, conversation_id, from_number, role, content, created_at, platform_metadata, content_attributes)
            SELECT $1, $2, $3, $4, $5, $6, $7::jsonb, $9::jsonb
            WHERE NOT EXISTS (
                SELECT 1 FROM chat_messages
                WHERE conversation_id = $2
                  AND platform_metadata->>'provider_message_id' = $8
                  AND $8 != ''
            )
        """,
            tenant_id, conv_id, from_num, role,
            msg_data.get("content") or f"[{msg_data['message_type']}]",
            msg_data["created_at"],
            platform_meta,
            ext_id,
            content_attrs_json,
        )

        # 4. Update conversation timestamps + last message preview + display_name
        msg_preview = (msg_data.get("content") or f"[{msg_data.get('message_type', 'message')}]")[:100]
        await pool.execute("""
            UPDATE chat_conversations SET
                last_message_at = GREATEST(last_message_at, $1),
                last_message_preview = CASE WHEN $1 >= COALESCE(last_message_at, '1970-01-01'::timestamptz) THEN $3 ELSE last_message_preview END,
                display_name = COALESCE(NULLIF($4, ''), display_name),
                updated_at = NOW()
            WHERE id = $2
        """, msg_data["created_at"], conv_id, msg_preview, display_name)

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
