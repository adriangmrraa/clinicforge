"""
Webhook Chatwoot & Channels: POST /admin/chatwoot/webhook
CLINICASV1.0 - Unified Channel Normalization (Spec 28)
"""
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from core.credentials import resolve_tenant_from_webhook_token
from db import get_pool, db
from services.channels.service import ChannelService
from services.channels.types import CanonicalMessage, MediaType

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/admin/chatwoot/webhook")
async def receive_chatwoot_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    access_token: str = Query(..., alias="access_token"),
):
    """
    Endpoint unificado de Webhooks. 
    Soporta Chatwoot (nativo) y YCloud (si se configura este endpoint por error o legado).
    """
    tenant_id = await resolve_tenant_from_webhook_token(access_token)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Invalid Access Token")

    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid_json"}

    # 1. Detectar Provider (Backward Compatibility)
    provider = "chatwoot"
    # YCloud payloads have "type": "message" or "image", Chatwoot has "event"
    if payload.get("type") and payload.get("message") and not payload.get("event"):
        provider = "ycloud"
        logger.info(f"⚠️ YCloud payload received on Chatwoot endpoint. Tenant: {tenant_id}")

    # 2. Normalizar Payload
    try:
        messages = await ChannelService.normalize_webhook(provider, payload, tenant_id)
    except Exception as e:
        logger.exception(f"❌ Error normalizing webhook: {e}")
        return {"status": "error", "reason": str(e)}

    if not messages:
        return {"status": "ignored", "reason": "no_relevant_messages", "provider": provider}

    # 2. Bucle de Procesamiento Canonizado
    # Usamos la función compartida para garantizar paridad y reducir duplicación
    # FIX: Pass the detected 'provider' variable instead of hardcoded "chatwoot"
    return await _process_canonical_messages(messages, tenant_id, provider, background_tasks)


@router.post("/admin/ycloud/webhook")
async def receive_ycloud_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    access_token: str = Query(..., alias="access_token"),
):
    """
    Endpoint dedicado para YCloud.
    """
    # Reutiliza la misma lógica, forzando provider='ycloud'
    # Podríamos refactorizar el body a una función común, pero por ahora llamamos al handler
    # inyectando el provider si fuese necesario, pero el handler ya tiene detección
    # Mejor: Copiar la lógica de llamada es más limpio para evitar recursión HTTP
    
    tenant_id = await resolve_tenant_from_webhook_token(access_token)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Invalid Access Token")
        
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid_json"}
        
    # Force YCloud normalization
    try:
        messages = await ChannelService.normalize_webhook("ycloud", payload, tenant_id)
    except Exception as e:
        logger.exception(f"❌ Error normalizing YCloud webhook: {e}")
        return {"status": "error", "reason": str(e)}

    # ... repetimos lógica de DB ...
    # Para no duplicar código en este paso (Hotfix/Stabilization), voy a invocar una función shared
    # Defino la función shared abajo y actualizo ambas rutas para usarla.
    return await _process_canonical_messages(messages, tenant_id, "ycloud", background_tasks)

async def _process_canonical_messages(messages, tenant_id, provider, background_tasks):
    pool = get_pool()
    saved_ids = []
    
    if not messages:
        return {"status": "ignored", "reason": "no_content"}

    for msg in messages:
        try:
            # Spec 34: Intentar extraer IDs si vienen en el crudo (para Chatwoot)
            cw_acc_id = None
            cw_conv_id = None
            if msg.raw_payload:
                cw_acc_id = msg.raw_payload.get("account", {}).get("id")
                cw_conv_id = msg.raw_payload.get("conversation", {}).get("id")

            # Fix Chat Name Persistence: Only update name/avatar if not an agent (Spec 34)
            # If msg.is_agent is True, we pass None so DB keeps existing value (COALESCE)
            # or inserts NULL (favors external_user_id) instead of "Adrian Gamarra"
            safe_display_name = msg.display_name if not msg.is_agent else None
            safe_avatar_url = (msg.sender.get("avatar") if msg.sender else None) if not msg.is_agent else None

            conv_id = await db.get_or_create_conversation(
                tenant_id=tenant_id,
                channel=msg.original_channel,
                external_user_id=msg.external_user_id,
                display_name=safe_display_name,
                external_chatwoot_id=cw_conv_id,
                external_account_id=cw_acc_id,
                avatar_url=safe_avatar_url,
                provider=provider
            )
            
            # Deduplicación robusta (Spec 34)
            # 1. Contenido idéntico reciente (5s)
            # 2. ID de proveedor coincidente (evitar eco de mensajes salientes de la IA)
            # Deduplicación robusta (Spec 34)
            # 1. Contenido idéntico reciente (5s)
            # 2. ID de proveedor coincidente (evitar eco de mensajes salientes de la IA)
            
            ext_id_candidate = None
            if provider == "ycloud":
                # YCloud: message ID is nested in 'message.id', NOT 'id' (which is event ID)
                ext_id_candidate = msg.raw_payload.get("message", {}).get("id")
            else:
                # Chatwoot/Default: ID is top-level 'id'
                ext_id_candidate = msg.raw_payload.get("id")
            
            external_id_check = str(ext_id_candidate) if ext_id_candidate else "NO_MATCH"
            
            dup = await pool.fetchval(
                """
                SELECT id FROM chat_messages
                WHERE conversation_id = $1 
                  AND (
                    (content = $2 AND created_at > NOW() - INTERVAL '5 seconds')
                    OR 
                    (platform_metadata->>'provider_message_id' = $3)
                  )
                LIMIT 1
                """,
                conv_id,
                msg.content,
                external_id_check
            )
            if dup:
                logger.info(f"♻️ Skipping duplicate message in conv {conv_id}")
                continue

            content_attrs = []
            for m_item in msg.media:
                content_attrs.append({
                    "type": m_item.type.value,
                    "url": m_item.url,
                    "file_name": m_item.file_name,
                    "file_size": m_item.meta.get("file_size"),
                    "mime_type": m_item.mime_type,
                    "transcription": m_item.transcription
                })

            role = "assistant" if msg.is_agent else "user"
            platform_meta = msg.raw_payload
            platform_meta["provider"] = provider
            
            msg_id = await pool.fetchval(
                """
                INSERT INTO chat_messages (
                    tenant_id, conversation_id, role, content, from_number, 
                    platform_metadata, content_attributes, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, NOW())
                RETURNING id
                """,
                tenant_id,
                conv_id,
                role,
                msg.content or (f"[{msg.media[0].type.value.upper()}]" if msg.media else "[Media]"),
                msg.external_user_id,
                json.dumps(platform_meta),
                json.dumps(content_attrs)
            )
            saved_ids.append(msg_id)
            logger.info(f"✅ Message saved: {msg_id} (Conv: {conv_id})")

            # Sincronizar conversación para el preview (Spec 14 / Bug Fix)
            try:
                # ✅ Fase 2: Robust fallback for previews
                content_preview = msg.content or (f"[{msg.media[0].type.value.upper()}]" if msg.media else "[Media]")
                
                await db.sync_conversation(
                    tenant_id=tenant_id,
                    channel=msg.original_channel,
                    external_user_id=msg.external_user_id,
                    last_message=content_preview,
                    is_user=(not msg.is_agent)
                )
            except Exception as sync_err:
                logger.error(f"⚠️ Error syncing conversation summary: {sync_err}")

            if msg.is_agent:
                await pool.execute(
                    "UPDATE chat_conversations SET human_override_until = NOW() + INTERVAL '24 hours' WHERE id = $1",
                    conv_id,
                )
                continue

            # Tasks
            for m_item in msg.media:
                if m_item.type == MediaType.AUDIO:
                     try:
                        from services.whisper_service import transcribe_audio_url
                        background_tasks.add_task(transcribe_audio_url, url=m_item.url, tenant_id=tenant_id, conversation_id=str(conv_id), external_user_id=msg.external_user_id)
                     except: logger.warning("whisper_service not available")
                elif m_item.type == MediaType.IMAGE:
                    try:
                        from services.vision_service import process_vision_task
                        background_tasks.add_task(process_vision_task, message_id=msg_id, image_url=m_item.url, tenant_id=tenant_id)
                    except: logger.warning("vision_service not available")

            # --- Spec 14: Socket.IO Notification (Real-time) ---
            try:
                from main import app
                sio = getattr(app.state, "sio", None)
                to_json_safe = getattr(app.state, "to_json_safe", lambda x: x)
                if sio:
                    await sio.emit('NEW_MESSAGE', to_json_safe({
                        'phone_number': msg.external_user_id,
                        'tenant_id': tenant_id,
                        'message': msg.content or (f"[{msg.media[0].type.value.upper()}]" if msg.media else ""),
                        'attachments': content_attrs,
                        'role': role,
                        'channel': msg.original_channel
                    }))
                    logger.info(f"📡 Socket NEW_MESSAGE emitted for {msg.external_user_id} via {provider}")
            except Exception as sio_err:
                logger.error(f"⚠️ Error emitting SocketIO event: {sio_err}")

            # --- Spec 24: Buffer / Agent Trigger (Only if not locked) ---
            override_row = await pool.fetchrow(
                "SELECT human_override_until FROM chat_conversations WHERE id = $1",
                conv_id,
            )
            from datetime import datetime, timezone
            utc_now = datetime.now(timezone.utc)
            is_locked = (
                override_row
                and override_row["human_override_until"] is not None
                and (override_row["human_override_until"] if override_row["human_override_until"].tzinfo else override_row["human_override_until"].replace(tzinfo=timezone.utc)) > utc_now
            )

            if not is_locked:
                try:
                    from services.relay import enqueue_buffer_and_schedule_task
                    background_tasks.add_task(enqueue_buffer_and_schedule_task, tenant_id, str(conv_id), msg.external_user_id)
                    logger.info(f"⏳ Relay task queued for {msg.external_user_id}")
                except ImportError:
                    logger.debug("relay not available")
            else:
                logger.info(f"🔇 AI silenced by human override for {msg.external_user_id}")

        except Exception as e:
            logger.error(f"Error processing msg: {e}")
            
    return {"status": "processed", "count": len(saved_ids)}
