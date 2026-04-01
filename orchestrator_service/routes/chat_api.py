"""
API de chats para la UI: summary, messages, send, human-override, config Chatwoot.
CLINICASV1.0 - paridad con Version Estable. Filtro por tenant_id vía get_resolved_tenant_id.
"""

import json
import logging
import os
import uuid
import hmac
import hashlib
import time
import traceback
from datetime import datetime, timedelta
from typing import Any, List, Optional, Dict

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Request, File, UploadFile
from fastapi.responses import StreamingResponse
import httpx

from core.credentials import (
    CHATWOOT_BASE_URL,
    CHATWOOT_API_TOKEN,
    WEBHOOK_ACCESS_TOKEN,
    YCLOUD_API_KEY,
    get_tenant_credential,
)
from core.security_utils import generate_signed_url, verify_signed_url
from core.auth import verify_ceo_token, verify_staff_token
from db import get_pool

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Chat"])


class ChatSummaryResponse(BaseModel):
    id: str
    tenant_id: int
    name: str
    avatar_url: Optional[str] = None
    external_user_id: str
    channel: str
    provider: str
    last_message: str
    last_message_at: Optional[str] = None
    last_user_message_at: Optional[str] = None
    is_locked: bool
    status: str
    last_derivhumano_at: Optional[str] = None
    meta: Dict[str, Any]
    unread_count: int


from admin_routes import get_resolved_tenant_id


@router.get(
    "/admin/chats/summary",
    summary="Obtener resumen de conversaciones omnicanal",
    response_model=List[ChatSummaryResponse],
)
async def chats_summary(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    channel: Optional[str] = Query(None),
    human_override: Optional[bool] = Query(None),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    from datetime import datetime, timezone

    pool = get_pool()
    conditions = ["c.tenant_id = $1"]
    params: List[Any] = [tenant_id]
    if channel:
        conditions.append("c.channel = $2")
        params.append(channel)
    if human_override is True:
        conditions.append("c.human_override_until > NOW()")
    where = " AND ".join(conditions)
    params.extend([limit, offset])
    lim_off_1 = len(params) - 1
    lim_off_2 = len(params)
    sql = f"""
        SELECT c.id, c.tenant_id, c.channel, c.provider, c.external_user_id, c.display_name,
               c.last_message_preview AS last_message, c.last_message_at AS last_message_at,
               c.last_user_message_at, c.status, c.human_override_until, c.last_derivhumano_at, c.meta, c.last_read_at
        FROM chat_conversations c
        WHERE {where}
        ORDER BY c.last_message_at DESC NULLS LAST
        LIMIT ${lim_off_1} OFFSET ${lim_off_2}
    """
    rows = await pool.fetch(sql, *params)
    utc_now = datetime.now(timezone.utc)
    out = []
    from urllib.parse import urlencode

    for r in rows:
        conv_id = r["id"]
        # Conteo de no leídos (Spec 14 isolation)
        unread_sql = """
            SELECT COUNT(*) FROM chat_messages
            WHERE conversation_id = $1
            AND role = 'user'
            AND tenant_id = $2
            AND created_at > GREATEST(
                COALESCE(
                    (SELECT created_at FROM chat_messages
                     WHERE conversation_id = $1 AND role = 'assistant' AND tenant_id = $2
                     ORDER BY created_at DESC LIMIT 1),
                    '1970-01-01'::timestamptz
                ),
                COALESCE($3, '1970-01-01'::timestamptz)
            )
        """
        unread = await pool.fetchval(
            unread_sql, conv_id, tenant_id, r.get("last_read_at")
        )
        meta = r["meta"] or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        ho = r["human_override_until"]

        avatar_url = meta.get("customer_avatar")
        # ✅ Proxy avatar if it looks like a remote Meta/External URL or local /media/
        is_external = avatar_url and (
            avatar_url.startswith("http") or avatar_url.startswith("https")
        )
        is_local_media = avatar_url and avatar_url.startswith("/media/")

        if (
            is_external or is_local_media
        ) and "/admin/chat/media/proxy" not in avatar_url:
            signature, expires = generate_signed_url(avatar_url, tenant_id)
            proxy_params = {
                "url": avatar_url,
                "tenant_id": tenant_id,
                "signature": signature,
                "expires": expires,
            }
            avatar_url = f"/admin/chat/media/proxy?{urlencode(proxy_params)}"

        out.append(
            {
                "id": str(r["id"]),
                "tenant_id": r["tenant_id"],
                "name": r["display_name"] or r["external_user_id"] or "",
                "avatar_url": avatar_url,
                "external_user_id": r["external_user_id"],
                "channel": r["channel"],
                "provider": r["provider"],
                "last_message": r["last_message"] or "",
                "last_message_at": r["last_message_at"].isoformat()
                if r["last_message_at"]
                else None,
                "last_user_message_at": r["last_user_message_at"].isoformat()
                if r["last_user_message_at"]
                else None,
                "is_locked": ho is not None
                and (ho if ho.tzinfo else ho.replace(tzinfo=timezone.utc)) > utc_now,
                "status": r["status"],
                "last_derivhumano_at": r["last_derivhumano_at"].isoformat()
                if r["last_derivhumano_at"]
                else None,
                "meta": meta,
                "unread_count": unread or 0,
            }
        )
    logger.info(
        f"📤 Devueltos {len(out)} chats unificados (limit={limit}, offset={offset})"
    )
    return out


@router.put(
    "/admin/chats/{conversation_id}/read", summary="Marcar una conversación como leída"
)
async def mark_conversation_read(
    conversation_id: str,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Marca una conversación omnicanal como leída."""
    pool = get_pool()
    await pool.execute(
        """
        UPDATE chat_conversations 
        SET last_read_at = NOW(), updated_at = NOW()
        WHERE id = $1 AND tenant_id = $2
    """,
        uuid.UUID(conversation_id),
        tenant_id,
    )
    return {"status": "ok", "conversation_id": conversation_id}


@router.get(
    "/admin/chats/{conversation_id}/messages",
    summary="Listar mensajes de una conversación",
)
async def chat_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tenant_id: int = Depends(get_resolved_tenant_id),
) -> List[dict]:
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT id FROM chat_conversations WHERE id = $1 AND tenant_id = $2",
        conversation_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = await pool.fetch(
        """
        SELECT id, conversation_id, role, content, created_at, correlation_id, content_attributes
        FROM chat_messages
        WHERE conversation_id = $1 AND tenant_id = $2
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        conversation_id,
        tenant_id,
        limit,
        offset,
    )
    messages = []
    for r in rows:
        # Parse content_attributes if it's a JSON string
        attachments = []
        raw_attrs = r.get("content_attributes")
        if raw_attrs:
            if isinstance(raw_attrs, str):
                try:
                    attachments = json.loads(raw_attrs)
                    # Handle double-encoded JSON (e.g. '"[]"') which returns a string after first load
                    if isinstance(attachments, str):
                        try:
                            attachments = json.loads(attachments)
                        except (json.JSONDecodeError, TypeError):
                            # If second parse fails, treat as empty or leave as is (likely not valid structure)
                            pass
                except (json.JSONDecodeError, TypeError):
                    attachments = []
            elif isinstance(raw_attrs, list):
                attachments = raw_attrs
        # Generar URLs firmadas para cada attachment
        signed_attachments = []
        for att in attachments:
            # ✅ FIX: Validar que att sea dict, no string
            if not isinstance(att, dict):
                logger.warning(
                    f"⚠️ Skipping invalid attachment (not a dict): {type(att)} - {att}"
                )
                continue

            # Sign ALL URLs to ensure they go through the proxy (fixes audio mime-type issues)
            original_url = att.get("url", "")
            if original_url:
                # ✅ FIX: Si es local /media/ o /uploads/, limpiar de parámetros antes de re-firmar para el proxy (Spec 19)
                clean_url = original_url
                if original_url.startswith("/media/") or original_url.startswith(
                    "/uploads/"
                ):
                    clean_url = original_url.split("?")[0]
                    logger.debug(
                        f"🧹 Limpiando URL local: {original_url} -> {clean_url}"
                    )

                # Generar firma para URL (sea externa o local)
                signature, expires = generate_signed_url(clean_url, tenant_id)
                logger.info(
                    f"🔐 Firmando attachment: original={original_url[:80]}..., clean={clean_url[:80]}..., tenant={tenant_id}, expires={expires}"
                )

                # Construir URL del proxy con parámetros de seguridad
                from urllib.parse import urlencode

                proxy_params = {
                    "url": clean_url,
                    "tenant_id": tenant_id,
                    "signature": signature,
                    "expires": expires,
                }
                proxy_url = f"/admin/chat/media/proxy?{urlencode(proxy_params)}"
                logger.debug(f"🔗 Proxy URL generada: {proxy_url[:100]}...")

                signed_attachments.append(
                    {
                        **att,
                        "url": proxy_url,  # URL firmada para el proxy
                        "original_url": original_url,  # Preservar URL original para referencia
                    }
                )
            else:
                logger.warning(f"⚠️ Attachment sin URL: {att}")
                signed_attachments.append(att)

        messages.append(
            {
                "id": str(r["id"]),
                "conversation_id": str(r["conversation_id"])
                if r.get("conversation_id")
                else None,
                "role": r["role"],
                "content": r["content"] or "",
                "timestamp": r["created_at"].isoformat() if r["created_at"] else None,
                "attachments": signed_attachments,
                "correlation_id": r.get("correlation_id"),
            }
        )

    # Debug: mostrar el contenido crudo de content_attributes de cada mensaje
    if messages:
        sample_attrs = [
            (i, r.get("content_attributes"), type(r.get("content_attributes")))
            for i, r in enumerate(rows[:3])
        ]
        logger.info(
            f"🔍 Muestra de content_attributes crudos (primeros 3): {sample_attrs}"
        )
    logger.info(
        f"📤 Devueltos {len(messages)} mensajes para conversación {conversation_id} (attachments check: {[len(m.get('attachments', []) or []) for m in messages]})"
    )
    return messages


@router.post(
    "/admin/chat/send", summary="Enviar mensaje manual desde el chat (Omnicanal)"
)
@router.post("/admin/whatsapp/send", summary="Enviar mensaje de WhatsApp (Alias)")
async def unified_send_message(
    body: dict,
    tenant_id: int = Depends(get_resolved_tenant_id),
    user_data=Depends(verify_staff_token),
) -> dict:
    """
    Endpoint unificado (Spec 18) para enviar mensajes a WhatsApp, Instagram y Facebook.
    Valida la ventana de 24h de Meta.
    """
    from datetime import datetime, timezone, timedelta

    # 1. Extraer identificadores
    conv_id_raw = body.get("conversation_id") or body.get("id")
    # Soporte para el formato antiguo de la UI que enviaba 'phone' para YCloud
    phone = body.get("phone")
    message = (body.get("message", "") or "").strip()
    attachments = body.get("attachments", [])

    if not message and not attachments:
        raise HTTPException(status_code=400, detail="message or attachments required")

    pool = get_pool()

    # 2. Localizar conversación
    if conv_id_raw:
        try:
            conv_id = uuid.UUID(str(conv_id_raw))
            row = await pool.fetchrow(
                "SELECT * FROM chat_conversations WHERE id = $1 AND tenant_id = $2",
                conv_id,
                tenant_id,
            )
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400, detail="Invalid conversation_id format"
            )
    elif phone:
        # Fallback para búsqueda por teléfono (YCloud legacy)
        row = await pool.fetchrow(
            "SELECT * FROM chat_conversations WHERE external_user_id = $1 AND tenant_id = $2 AND channel = 'whatsapp'",
            str(phone),
            tenant_id,
        )
    else:
        raise HTTPException(status_code=400, detail="conversation_id or phone required")

    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv_id = row["id"]
    provider = (row["provider"] or "ycloud").lower()
    channel = row["channel"]
    external_user_id = row["external_user_id"]

    # 3. VALIDACIÓN VENTANA 24h (Spec 18)
    last_user_msg = row["last_user_message_at"]
    utc_now = datetime.now(timezone.utc)

    if not last_user_msg:
        # Si nunca hubo mensaje del usuario, la ventana está cerrada
        raise HTTPException(
            status_code=403,
            detail="Ventana de 24h cerrada por política de Meta. Utilice plantillas para reabrir el canal.",
        )

    # Normalizar a UTC si es naive
    if last_user_msg.tzinfo is None:
        last_user_msg = last_user_msg.replace(tzinfo=timezone.utc)

    if utc_now - last_user_msg > timedelta(hours=24):
        logger.warning(
            f"🚫 24h Window Closed for conversation {conv_id} (Last: {last_user_msg})"
        )
        raise HTTPException(
            status_code=403,
            detail="Ventana de 24h cerrada por política de Meta. Utilice plantillas para reabrir el canal.",
        )

    # 4. ENVÍO SEGÚN PROVEEDOR
    try:
        if provider == "chatwoot":
            account_id = row["external_account_id"]
            cw_conv_id = row["external_chatwoot_id"]
            if not account_id or not cw_conv_id:
                raise HTTPException(
                    status_code=400, detail="Chatwoot conversation not linked"
                )

            token = await get_tenant_credential(tenant_id, CHATWOOT_API_TOKEN)
            base_url = (
                await get_tenant_credential(tenant_id, CHATWOOT_BASE_URL)
                or "https://app.chatwoot.com"
            )
            if not token:
                raise HTTPException(
                    status_code=503, detail="Chatwoot credentials not configured"
                )

            from chatwoot_client import ChatwootClient

            client = ChatwootClient(base_url, token)

            # Send text if present
            if message:
                await client.send_text_message(account_id, cw_conv_id, message)

            # Send attachments
            import os

            for att in attachments:
                # att is expected to be { type: 'image', url: '/media/...' }
                # Resolve local path from URL
                url = att.get("url", "")
                if url.startswith("/media/"):
                    # url format: /media/{tenant_id}/{filename}
                    # local path: os.getcwd()/media/{tenant_id}/{filename}
                    rel_path = url.lstrip("/")
                    # Security check: ensure no directory traversal
                    parts = rel_path.split("/")
                    if ".." in parts:
                        logger.warning(f"⚠️ Skip unsafe attachment path: {url}")
                        continue

                    file_path = os.path.join(os.getcwd(), *parts)
                    if os.path.exists(file_path):
                        await client.send_attachment(account_id, cw_conv_id, file_path)
                    else:
                        logger.warning(f"⚠️ Attachment file not found: {file_path}")

        elif provider == "ycloud":
            api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
            if not api_key:
                raise HTTPException(
                    status_code=503, detail="YCloud credentials not configured"
                )

            from ycloud_client import YCloudClient

            # Use bot_phone_number from tenants (same as response_sender)
            from_number = await pool.fetchval(
                "SELECT bot_phone_number FROM tenants WHERE id = $1", tenant_id
            )
            if not from_number:
                from_number = await get_tenant_credential(
                    tenant_id, "YCLOUD_WHATSAPP_NUMBER"
                )

            client = YCloudClient(api_key)
            # En YCloud, external_user_id es el teléfono (phone_number)
            await client.send_text_message(
                to=external_user_id, text=message, from_number=from_number
            )

        elif provider == "meta_direct":
            page_token = await get_tenant_credential(tenant_id, "meta_page_token")
            if not page_token:
                raise HTTPException(
                    status_code=503,
                    detail="Meta page token not configured. Connect Meta first in Settings.",
                )

            import httpx as _httpx

            async with _httpx.AsyncClient(timeout=10.0) as meta_client:
                if channel == "whatsapp":
                    # WhatsApp Cloud API delivery
                    # Find phone_number_id from business_assets
                    wa_asset = await pool.fetchrow(
                        "SELECT content FROM business_assets WHERE tenant_id = $1 AND asset_type = 'whatsapp_waba' AND is_active = true LIMIT 1",
                        tenant_id,
                    )
                    phone_number_id = None
                    if wa_asset:
                        wa_content = (
                            wa_asset["content"]
                            if isinstance(wa_asset["content"], dict)
                            else json.loads(wa_asset["content"])
                        )
                        phones = wa_content.get("phone_numbers", [])
                        if phones:
                            phone_number_id = phones[0].get("id")

                    wa_token = (
                        await get_tenant_credential(
                            tenant_id, f"META_WA_TOKEN_{wa_content.get('id')}"
                        )
                        if wa_asset
                        else page_token
                    )

                    if not phone_number_id:
                        raise HTTPException(
                            status_code=503,
                            detail="WhatsApp phone number ID not found in business assets",
                        )

                    resp = await meta_client.post(
                        f"https://graph.facebook.com/v22.0/{phone_number_id}/messages",
                        headers={
                            "Authorization": f"Bearer {wa_token}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "messaging_product": "whatsapp",
                            "recipient_type": "individual",
                            "to": external_user_id,
                            "type": "text",
                            "text": {"body": message},
                        },
                    )
                    resp.raise_for_status()
                else:
                    # Facebook Messenger / Instagram DM
                    resp = await meta_client.post(
                        "https://graph.facebook.com/v22.0/me/messages",
                        params={"access_token": page_token},
                        json={
                            "recipient": {"id": external_user_id},
                            "message": {"text": message},
                            "messaging_type": "RESPONSE",
                        },
                    )
                    resp.raise_for_status()

            logger.info(
                f"Meta Direct message sent: channel={channel}, to={external_user_id}"
            )

        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

        # 5. PERSISTENCIA Y NOTIFICACIÓN
        from db import db

        await db.pool.execute(
            """
            INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, content_attributes) 
            VALUES ($1, $2, 'human_supervisor', $3, $4, $5::jsonb)
            """,
            tenant_id,
            conv_id,
            message,
            external_user_id,
            json.dumps(attachments) if attachments else None,
        )

        # Sincronizar metadata de conversación (sin tocar la ventana de 24h ya que es saliente)
        from db import db as db_inst

        await db_inst.sync_conversation(
            tenant_id, channel, external_user_id, message, is_user=False
        )

        return {"status": "sent", "conversation_id": str(conv_id)}

    except Exception as e:
        logger.error(f"❌ Error sending message: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@router.post(
    "/admin/conversations/{conversation_id}/human-override",
    summary="Activar/Desactivar intervención humana (Pausa IA)",
)
async def human_override(
    conversation_id: uuid.UUID,
    body: dict,
    tenant_id: int = Depends(get_resolved_tenant_id),
    user_data=Depends(verify_staff_token),
) -> dict:
    enabled = body.get("enabled", False)
    logger.info(
        f"🔄 HUMAN_OVERRIDE Request: conv={conversation_id}, enabled={enabled}, tenant={tenant_id}"
    )
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT id, channel, external_user_id FROM chat_conversations WHERE id = $1 AND tenant_id = $2",
        conversation_id,
        tenant_id,
    )
    if not row:
        logger.error(
            f"❌ Conversation not found: {conversation_id} (tenant={tenant_id})"
        )
        raise HTTPException(status_code=404, detail="Conversation not found")

    logger.info(
        f"✅ Found conversation: {row['id']}, channel={row['channel']}, ext_id={row['external_user_id']}"
    )

    try:
        if enabled:
            await pool.execute(
                "UPDATE chat_conversations SET human_override_until = NOW() + INTERVAL '24 hours' WHERE id = $1",
                conversation_id,
            )
            # Spec 24: Sync with patients table if it's a WhatsApp/Phone-based conversation
            if row["channel"] == "whatsapp":
                await pool.execute(
                    "UPDATE patients SET human_handoff_requested = TRUE, human_override_until = NOW() + INTERVAL '24 hours' WHERE tenant_id = $1 AND phone_number = $2",
                    tenant_id,
                    row["external_user_id"],
                )
        else:
            await pool.execute(
                "UPDATE chat_conversations SET human_override_until = NULL WHERE id = $1",
                conversation_id,
            )
            # Spec 24: Sync with patients table
            if row["channel"] == "whatsapp":
                await pool.execute(
                    "UPDATE patients SET human_handoff_requested = FALSE, human_override_until = NULL WHERE tenant_id = $1 AND phone_number = $2",
                    tenant_id,
                    row["external_user_id"],
                )

        # Spec 34: Real-time update
        from main import sio

        payload = {
            "phone_number": row["external_user_id"],
            "conversation_id": str(conversation_id),  # UUID to string
            "enabled": enabled,
            "until": (datetime.now() + timedelta(hours=24)).isoformat()
            if enabled
            else None,
            "tenant_id": tenant_id,
        }
        logger.info(f"📡 Emitting HUMAN_OVERRIDE_CHANGED: {payload}")
        await sio.emit("HUMAN_OVERRIDE_CHANGED", payload)

        return {"status": "ok", "human_override": enabled}

    except Exception as e:
        error_details = f"human_override ERROR: {str(e)}\n{traceback.format_exc()}"
        logger.error(f"❌ {error_details}")
        # Retornamos 500 pero con el detalle del error para que el frontend lo muestre en el popup
        raise HTTPException(status_code=500, detail=error_details)


@router.get(
    "/admin/chat/media/proxy",
    summary="Proxy seguro para previsualización de multimedia",
)
async def media_proxy(
    url: str = Query(..., description="Original media URL"),
    tenant_id: int = Query(..., description="Tenant ID"),
    signature: str = Query(..., description="HMAC signature"),
    expires: int = Query(..., description="Expiration timestamp"),
):
    """
    Proxy seguro para medios con URLs firmadas (Spec 19).

    Seguridad:
    - HMAC signature para autenticidad
    - Timestamp de expiración (1 hora TTL)
    - Whitelist de dominios permitidos
    - Compatible con <img> tags (autenticación via query params)
    """

    # 1. Verificar firma y expiración
    if not verify_signed_url(url, tenant_id, signature, expires):
        logger.warning(f"❌ Firma inválida o expirada para URL: {url}")
        raise HTTPException(status_code=403, detail="URL inválida o expirada")

    # 2. Validar dominio permitido (defensa en profundidad)
    allowed_domains = [
        "lookaside.fbsbx.com",  # Instagram/Facebook CDN
        "scontent",  # Facebook content
        "cdn.ycloud.com",  # YCloud
        "storage.googleapis.com",  # Google Cloud Storage
    ]

    is_allowed = (
        any(domain in url for domain in allowed_domains)
        or url.startswith("/media/")
        or url.startswith("/uploads/")
    )
    if not is_allowed:
        logger.warning(f"❌ Dominio no permitido: {url}")
        raise HTTPException(status_code=403, detail="Dominio no permitido")

    logger.info(f"🎞️ Proxying media (tenant {tenant_id}): {url}")

    import mimetypes

    # Determinar Content-Type
    media_content_type, _ = mimetypes.guess_type(url)

    # Fallback manual para tipos comunes si mimetypes falla (especialmente .ogg/.opus de WhatsApp)
    if not media_content_type:
        low_url = url.lower()
        if ".ogg" in low_url or ".opus" in low_url:
            media_content_type = "audio/ogg"
        elif ".mp3" in low_url:
            media_content_type = "audio/mpeg"
        elif ".m4a" in low_url:
            media_content_type = "audio/mp4"
        else:
            media_content_type = "application/octet-stream"

    # --- Spec 33: Mejorar serving de archivos locales ---
    # Si es una URL local del servidor, usar FileResponse (soporta Range headers nativamente)
    if url.startswith("/media/") or url.startswith("/uploads/"):
        # Normalizar path para evitar traversal
        stripped = url
        for prefix in ("/media/", "/uploads/"):
            if stripped.startswith(prefix):
                stripped = stripped[len(prefix) :]
                break
        path_parts = stripped.split("/")
        if ".." in path_parts:
            raise HTTPException(status_code=400, detail="Invalid path")

        # Try multiple candidate paths
        candidates = [
            os.path.join(os.getcwd(), "media", *path_parts),
            os.path.join(os.getcwd(), "uploads", *path_parts),
            os.path.join("/media", *path_parts),
            os.path.join("/uploads", *path_parts),
        ]
        local_path = None
        for c in candidates:
            if os.path.exists(c) and os.path.isfile(c):
                local_path = c
                break

        if local_path:
            from fastapi.responses import FileResponse

            logger.info(
                f"📁 Serving local media via FileResponse: {local_path} (Range Support)"
            )
            return FileResponse(
                local_path,
                media_type=media_content_type,
                filename=os.path.basename(local_path),
            )
        else:
            logger.error(f"❌ Local media not found. Tried: {candidates}")
            raise HTTPException(status_code=404, detail="File not found")

    # De lo contrario (URLs externas), mantener StreamingResponse
    async def stream_content():
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            try:
                async with client.stream("GET", url) as response:
                    if response.status_code != 200:
                        logger.error(
                            f"❌ Failed to proxy media ({response.status_code}): {url}"
                        )
                        return

                    async for chunk in response.aiter_bytes():
                        yield chunk
            except Exception as e:
                logger.error(f"❌ Error streaming media: {str(e)}")

    headers = {"Content-Type": media_content_type}
    return StreamingResponse(stream_content(), headers=headers)


@router.post("/admin/chat/upload", summary="Subir archivo multimedia para el chat")
async def chat_upload(
    file: UploadFile = File(...),
    tenant_id: int = Query(..., description="Tenant ID target"),
    user_data=Depends(verify_staff_token),
    resolved_tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Sube un archivo de media localmente para ser enviado en el chat (Spec 19).
    Límite de 20MB.
    """
    # Usar el tenant resuelto para evitar escalada de privilegios
    target_tenant_id = resolved_tenant_id
    import mimetypes
    import os
    import uuid

    # 1. Enforce 20MB limit (20 * 1024 * 1024 bytes)
    MAX_SIZE = 20 * 1024 * 1024

    # Check if we can get size from headers (fast check)
    content_length = file.size  # Starlette/FastAPI 0.100+ typical place for size
    if content_length and content_length > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large (Max 20MB)")

    # Determinar tipo
    content_type = file.content_type or ""
    file_type = "file"
    if "image" in content_type:
        file_type = "image"
    elif "video" in content_type:
        file_type = "video"
    elif "audio" in content_type:
        file_type = "audio"

    ext = mimetypes.guess_extension(content_type) or ".bin"
    filename = f"{uuid.uuid4()}{ext}"

    # Asegurar directorio
    media_dir = os.path.join(os.getcwd(), "media", str(tenant_id))
    os.makedirs(media_dir, exist_ok=True)

    local_path = os.path.join(media_dir, filename)

    size_so_far = 0
    with open(local_path, "wb") as f:
        # We read in chunks to avoid memory spikes and double-check size
        while chunk := await file.read(65536):  # 64KB chunks
            size_so_far += len(chunk)
            if size_so_far > MAX_SIZE:
                f.close()
                os.remove(local_path)
                raise HTTPException(status_code=413, detail="File too large (Max 20MB)")
            f.write(chunk)

    relative_url = f"/media/{tenant_id}/{filename}"
    signature, expires = generate_signed_url(relative_url, tenant_id)

    return {
        "type": file_type,
        "url": f"{relative_url}?signature={signature}&expires={expires}",
        "file_name": file.filename,
        "size": size_so_far,
    }
