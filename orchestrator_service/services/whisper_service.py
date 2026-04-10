import os
import httpx
import logging
from typing import Optional
from db import db
import json

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

async def transcribe_audio_url(url: str, tenant_id: int, conversation_id: str, external_user_id: str):
    """
    Downloads audio from url (or reads from local disk), transcribes it via Whisper, and updates chat_messages.
    """
    if not OPENAI_API_KEY:
        logger.warning("❌ OPENAI_API_KEY not set. Skipping transcription.")
        return

    original_url = url  # Preserve for DB lookup

    try:
        # 1. Get audio data — from local file or remote URL
        audio_data = None

        if url.startswith("/media/") or url.startswith("/uploads/"):
            # Local file — read from disk
            stripped = url
            for prefix in ("/media/", "/uploads/"):
                if stripped.startswith(prefix):
                    stripped = stripped[len(prefix):]
                    break
            # Try multiple candidate paths
            candidates = [
                os.path.join(os.getcwd(), "media", stripped),
                os.path.join(os.getcwd(), "uploads", stripped),
                os.path.join("/media", stripped),
                os.path.join("/uploads", stripped),
            ]
            for path in candidates:
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        audio_data = f.read()
                    logger.info(f"📁 Audio leído desde disco: {path} ({len(audio_data)} bytes)")
                    break
            if not audio_data:
                logger.error(f"❌ Local audio file not found. Tried: {candidates}")
                return
        else:
            # Remote URL — download
            headers = {}
            ycloud_key = os.getenv("YCLOUD_API_KEY")
            if ycloud_key and "ycloud" in url.lower():
                headers["X-API-Key"] = ycloud_key
            async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.error(f"❌ Failed to download audio from {url}: {resp.status_code}")
                    return
                audio_data = resp.content

        if not audio_data or len(audio_data) == 0:
            logger.warning(f"⚠️ Audio data is empty for {url}")
            return

        # 2. Transcribe via Whisper
        filename = url.split("?")[0].split("/")[-1] or "audio.ogg"
        if "." not in filename:
            filename += ".ogg"

        files = {"file": (filename, audio_data)}
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            whisper_resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                data={"model": "whisper-1"},
                files=files
            )

            if whisper_resp.status_code != 200:
                logger.error(f"❌ Whisper API error: {whisper_resp.text}")
                return

            transcription = whisper_resp.json().get("text", "")
            if not transcription:
                logger.warning("⚠️ Transcription resulted in empty string.")
                return

        logger.info(f"🎙️ Transcription successful: '{transcription[:80]}...'")

        # Track Whisper usage (billed per minute, ~$0.006/min; estimate tokens for dashboard)
        try:
            audio_size_kb = len(audio_data) / 1024 if audio_data else 0
            # Rough estimate: 1 min audio ≈ 500KB OGG ≈ 100 "equivalent tokens" for cost tracking
            est_tokens = max(int(audio_size_kb / 5), 10)
            from dashboard.token_tracker import track_service_usage
            from db import db as _db_ref
            await track_service_usage(_db_ref.pool, tenant_id, "whisper-1", est_tokens, 0, source="whisper_transcription", phone=external_user_id)
        except Exception:
            pass

        # 3. Update DB — find the message by conversation + audio type (most recent)
        # Try multiple search strategies since the URL in DB may differ from the original
        msg = None

        # Strategy 1: Search by original URL
        msg = await db.fetchrow("""
            SELECT id, content_attributes FROM chat_messages
            WHERE conversation_id = $1::uuid
            AND content_attributes::text LIKE $2
            ORDER BY created_at DESC LIMIT 1
        """, conversation_id, f"%{original_url}%")

        # Strategy 2: Search by local URL (if URL was rewritten to local path)
        if not msg and not url.startswith("http"):
            msg = await db.fetchrow("""
                SELECT id, content_attributes FROM chat_messages
                WHERE conversation_id = $1::uuid
                AND content_attributes::text LIKE $2
                ORDER BY created_at DESC LIMIT 1
            """, conversation_id, f"%{url}%")

        # Strategy 3: Find the most recent audio message without transcription
        if not msg:
            msg = await db.fetchrow("""
                SELECT id, content_attributes FROM chat_messages
                WHERE conversation_id = $1::uuid
                AND content_attributes::text LIKE '%audio%'
                AND content_attributes::text NOT LIKE '%transcription%'
                ORDER BY created_at DESC LIMIT 1
            """, conversation_id)

        if msg:
            attrs = msg["content_attributes"] or {}
            if isinstance(attrs, str):
                attrs = json.loads(attrs)
            if isinstance(attrs, list):
                for item in attrs:
                    if isinstance(item, dict) and item.get("type") in ("audio", "voice"):
                        item["transcription"] = transcription
            elif isinstance(attrs, dict):
                attrs["transcription"] = transcription

            await db.execute("""
                UPDATE chat_messages SET content_attributes = $1::jsonb
                WHERE id = $2
            """, json.dumps(attrs), msg["id"])
            logger.info(f"✅ DB updated with transcription for message {msg['id']}")
        else:
            logger.warning(f"⚠️ Could not find audio message in DB for Conv {conversation_id}")

    except Exception as e:
        logger.error(f"❌ Error in transcribe_audio_url: {str(e)}")
