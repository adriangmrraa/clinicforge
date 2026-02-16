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
    Downloads audio from url, transcribes it via Whisper, and updates chat_messages.
    """
    if not OPENAI_API_KEY:
        logger.warning("❌ OPENAI_API_KEY not set. Skipping transcription.")
        return

    try:
        # 1. Download audio
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.error(f"❌ Failed to download audio from {url}: {resp.status_code}")
                return
            audio_data = resp.content

        # 2. Transcribe via Whisper
        # Note: Whisper requires a file-like object with a filename (for format detection)
        # We'll use a multipart form request
        filename = url.split("?")[0].split("/")[-1] or "audio.mp4"
        if "." not in filename: filename += ".mp4"

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

        # 3. Update DB
        # We search for the message that contains this attachment URL in its content_attributes
        # Or better: search for the latest incoming audio message for this conversation
        # Since we have the URL, we can be precise.
        
        # chat_messages: content_attributes is JSONB (array of objects for Chatwoot, usually object/array for internal)
        # In Chatwoot/YCloud, it might be inside a list.
        
        # Update logic: If transcription found, merge it into content_attributes
        logger.info(f"🎙️ Transcription successful: '{transcription[:50]}...'")
        
        # We update the message where the URL matches in content_attributes
        # Since content_attributes can be complex, we use jsonb_set or simple filter if we can find the ID
        
        # Let's find the message ID first
        msg = await db.fetchrow("""
            SELECT id, content_attributes FROM chat_messages 
            WHERE conversation_id = $1::uuid 
            AND content_attributes::text LIKE $2
            ORDER BY created_at DESC LIMIT 1
        """, conversation_id, f"%{url}%")

        if msg:
            attrs = msg["content_attributes"] or {}
            # Si es Chatwoot, suele ser una lista de adjuntos
            if isinstance(attrs, list):
                for item in attrs:
                    if item.get("url") == url or item.get("data_url") == url:
                        item["transcription"] = transcription
            # Si es objeto directo
            elif isinstance(attrs, dict):
                attrs["transcription"] = transcription
            
            await db.execute("""
                UPDATE chat_messages SET content_attributes = $1::jsonb
                WHERE id = $2
            """, json.dumps(attrs), msg["id"])
            logger.info(f"✅ DB updated with transcription for message {msg['id']}")
        else:
            logger.warning(f"⚠️ Could not find message in DB for URL {url} / Conv {conversation_id}")

    except Exception as e:
        logger.error(f"❌ Error in transcribe_audio_url: {str(e)}")
