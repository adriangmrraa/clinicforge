"""
Webhook Chatwoot: POST /admin/chatwoot/webhook
CLINICASV1.0 - paridad con Version Estable.
"""
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from core.credentials import resolve_tenant_from_webhook_token
from db import get_pool

logger = logging.getLogger(__name__)
router = APIRouter()


def _map_chatwoot_channel_to_nexus(cw_channel: str) -> str:
    cw_lower = (cw_channel or "").lower()
    if "whatsapp" in cw_lower:
        return "whatsapp"
    if "instagram" in cw_lower:
        return "instagram"
    if "facebook" in cw_lower:
        return "facebook"
    return "chatwoot"


@router.post("/admin/chatwoot/webhook")
async def receive_chatwoot_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    access_token: str = Query(..., alias="access_token"),
):
    tenant_id = await resolve_tenant_from_webhook_token(access_token)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Invalid Access Token")

    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid_json"}

    if payload.get("event") != "message_created":
        return {"status": "ignored", "reason": "event_not_supported"}

    msg_type = payload.get("message_type", "incoming")
    is_private = payload.get("private", False)
    if is_private:
        return {"status": "ignored", "reason": "private_note"}

    data = payload.get("content") or payload.get("content_attributes", {}).get("message", "") or "[Attachment]"
    if isinstance(data, dict):
        data = str(data)

    conversation_map = payload.get("conversation", {})
    contact_map = payload.get("sender", {})
    account_map = payload.get("account", {})
    chatwoot_conv_id = conversation_map.get("id")
    chatwoot_account_id = account_map.get("id") if account_map else None
    customer_map = conversation_map.get("meta", {}).get("sender", {}) or contact_map
    chatwoot_contact_id = customer_map.get("id")

    cw_channel = conversation_map.get("channel", "")
    nexus_channel = _map_chatwoot_channel_to_nexus(cw_channel)

    identifier = customer_map.get("phone_number")
    if nexus_channel == "instagram":
        additional = customer_map.get("additional_attributes", {}) or {}
        social = additional.get("social_profiles", {}) or {}
        identifier = social.get("instagram") or customer_map.get("name") or identifier
    if nexus_channel == "facebook":
        identifier = customer_map.get("name") or contact_map.get("name") or identifier
    if not identifier:
        identifier = contact_map.get("email") or f"cw_{chatwoot_contact_id}"

    display_name = customer_map.get("name") or str(identifier)
    avatar_url = customer_map.get("thumbnail") or customer_map.get("avatar_url")
    meta_data = {
        "chatwoot_conversation_id": chatwoot_conv_id,
        "chatwoot_contact_id": chatwoot_contact_id,
        "chatwoot_account_id": chatwoot_account_id,
        "customer_name": display_name,
        "customer_avatar": avatar_url,
        "last_sender_type": msg_type,
    }

    pool = get_pool()
    conv_id: uuid.UUID | None = None

    upsert_sql = """
        INSERT INTO chat_conversations (
            id, tenant_id, channel, channel_source, external_user_id, status, provider,
            external_chatwoot_id, external_account_id, display_name, meta,
            last_message_at, last_message_preview, last_user_message_at, updated_at
        )
        VALUES ($1, $2, $3, $3, $4, 'open', 'chatwoot', $5, $6, $7, $8::jsonb, NOW(), LEFT($9, 255), CASE WHEN $10 = 'incoming' THEN NOW() ELSE NULL END, NOW())
        ON CONFLICT (tenant_id, channel, external_user_id)
        DO UPDATE SET
            external_chatwoot_id = EXCLUDED.external_chatwoot_id,
            external_account_id = EXCLUDED.external_account_id,
            meta = chat_conversations.meta || EXCLUDED.meta,
            last_message_at = NOW(),
            last_message_preview = EXCLUDED.last_message_preview,
            last_user_message_at = CASE WHEN EXCLUDED.last_user_message_at IS NOT NULL THEN EXCLUDED.last_user_message_at ELSE chat_conversations.last_user_message_at END,
            updated_at = NOW()
        RETURNING id
    """
    try:
        conv_id = await pool.fetchval(
            upsert_sql,
            uuid.uuid4(),
            tenant_id,
            nexus_channel,
            str(identifier),
            chatwoot_conv_id,
            chatwoot_account_id,
            display_name,
            json.dumps(meta_data),
            data[:255] if data else "",
            msg_type,
        )
    except Exception as e:
        logger.warning("chatwoot_upsert_failed", error=str(e), tenant_id=tenant_id)
        row = await pool.fetchrow(
            "SELECT id FROM chat_conversations WHERE tenant_id = $1 AND external_chatwoot_id = $2 LIMIT 1",
            tenant_id,
            chatwoot_conv_id,
        )
        if row:
            conv_id = row["id"]
            await pool.execute(
                "UPDATE chat_conversations SET meta = meta || $1::jsonb, last_message_at = NOW(), last_message_preview = $2, updated_at = NOW() WHERE id = $3",
                json.dumps(meta_data),
                (data[:255] if data else ""),
                conv_id,
            )
        else:
            raise HTTPException(status_code=500, detail="Conversation upsert failed")

    if not conv_id:
        raise HTTPException(status_code=500, detail="No conversation id")

    if msg_type == "outgoing":
        await pool.execute(
            "UPDATE chat_conversations SET human_override_until = NOW() + INTERVAL '24 hours' WHERE id = $1",
            conv_id,
        )

    dup = await pool.fetchval(
        """
        SELECT id FROM chat_messages
        WHERE conversation_id = $1 AND content = $2 AND created_at > NOW() - INTERVAL '2 seconds'
        LIMIT 1
        """,
        conv_id,
        data,
    )
    if dup:
        return {"status": "ignored", "reason": "duplicate"}
    logger.info(f"📥 Recibiendo webhook de Chatwoot: event={payload.get('event')}, msg_type={msg_type}")
    
    # Log de adjuntos crudos para depuración
    logger.info(f"📦 DEBUG PAYLOAD: {json.dumps(payload)[:1000]}...") # Limit length

    role = "user" if msg_type == "incoming" else "human_supervisor"
    
    # Extraction robusta de adjuntos (Chatwoot v3+ y canales variados)
    raw_attachments = payload.get("attachments")
    if not isinstance(raw_attachments, list):
        raw_attachments = payload.get("message", {}).get("attachments")
    if not isinstance(raw_attachments, list):
        raw_attachments = []
        
    content_attrs = []
    for att in raw_attachments:
        # Normalización de tipos para el frontend (image, audio, video, file)
        ftype = att.get("file_type", "file")
        if ftype == "voice": ftype = "audio"
        
        content_attrs.append({
            "type": ftype,
            "url": att.get("data_url") or att.get("source_url", ""),
            "file_name": att.get("file_name", "attachment"),
            "file_size": att.get("file_size"),
        })
    
    if content_attrs:
        logger.info(f"🖇️ Adjuntos extraídos ({len(content_attrs)}): {json.dumps(content_attrs)}")
    else:
        logger.warning(f"⚠️ No se encontraron adjuntos en el payload para el mensaje {payload.get('id')}")

    # CLINICASV1.0: chat_messages tiene from_number NOT NULL e id BIGSERIAL (no UUID)
    await pool.execute(
        """
        INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, platform_metadata, content_attributes)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)
        """,
        tenant_id,
        conv_id,
        role,
        data,
        str(identifier),
        json.dumps(payload),
        json.dumps(content_attrs),
    )

    # --- Transcripción Universal (Spec 19) ---
    if msg_type == "incoming":
        for att in content_attrs:
            if att["type"] == "audio":
                try:
                    from services.whisper_service import transcribe_audio_url
                    background_tasks.add_task(
                        transcribe_audio_url,
                        url=att["url"],
                        tenant_id=tenant_id,
                        conversation_id=str(conv_id),
                        external_user_id=str(identifier)
                    )
                    logger.info(f"🎙️ Transcription queued for Chatwoot audio: {att['url']}")
                except ImportError:
                    logger.warning("whisper_service not available for universal transcription")
                except Exception as e:
                    logger.error(f"❌ Error queuing transcription: {str(e)}")

    if msg_type == "incoming":
        override_row = await pool.fetchrow(
            "SELECT human_override_until FROM chat_conversations WHERE id = $1",
            conv_id,
        )
        from datetime import datetime, timezone
        utc_now = datetime.now(timezone.utc)
        is_locked = (
            override_row
            and override_row["human_override_until"] is not None
            and override_row["human_override_until"] > utc_now
        )
        if not is_locked:
            try:
                from services.relay import enqueue_buffer_and_schedule_task
                background_tasks.add_task(enqueue_buffer_and_schedule_task, tenant_id, str(conv_id), str(identifier))
            except ImportError:
                logger.debug("relay.enqueue_buffer_and_schedule_task not available")

    return {
        "status": "processed",
        "tenant_id": tenant_id,
        "conversation_id": str(conv_id),
    }
