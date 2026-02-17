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
from typing import Any, List, Optional

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
from db import get_pool

logger = logging.getLogger(__name__)
router = APIRouter()


from admin_routes import get_resolved_tenant_id

# Clave secreta para firmar URLs (usar variable de entorno en producción)
MEDIA_PROXY_SECRET = os.getenv("MEDIA_PROXY_SECRET", "dentalogic-media-proxy-secret-2026")
MEDIA_URL_TTL = 3600  # 1 hora de validez

def generate_signed_url(url: str, tenant_id: int) -> str:
    """
    Genera una URL firmada para acceso seguro al proxy de medios.
    """
    expires = int(time.time()) + MEDIA_URL_TTL
    
    # Crear firma HMAC
    message = f"{url}|{tenant_id}|{expires}"
    signature = hmac.new(
        MEDIA_PROXY_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return signature, expires

def verify_signed_url(url: str, tenant_id: int, signature: str, expires: int) -> bool:
    """
    Verifica que la URL firmada sea válida y no haya expirado.
    """
    # Verificar expiración
    if int(time.time()) > expires:
        return False
    
    # Verificar firma
    message = f"{url}|{tenant_id}|{expires}"
    expected_signature = hmac.new(
        MEDIA_PROXY_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)




@router.get("/admin/chats/summary")
async def chats_summary(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    channel: Optional[str] = Query(None),
    human_override: Optional[bool] = Query(None),
    tenant_id: int = Depends(get_resolved_tenant_id),
) -> List[dict]:
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
               c.last_user_message_at, c.status, c.human_override_until, c.meta
        FROM chat_conversations c
        WHERE {where}
        ORDER BY c.last_message_at DESC NULLS LAST
        LIMIT ${lim_off_1} OFFSET ${lim_off_2}
    """
    rows = await pool.fetch(sql, *params)
    utc_now = datetime.now(timezone.utc)
    out = []
    for r in rows:
        meta = r["meta"] or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        ho = r["human_override_until"]
        out.append({
            "id": str(r["id"]),
            "tenant_id": r["tenant_id"],
            "name": r["display_name"] or r["external_user_id"] or "",
            "avatar_url": meta.get("customer_avatar"),
            "external_user_id": r["external_user_id"],
            "channel": r["channel"],
            "provider": r["provider"],
            "last_message": r["last_message"] or "",
            "last_message_at": r["last_message_at"].isoformat() if r["last_message_at"] else None,
            "last_user_message_at": r["last_user_message_at"].isoformat() if r["last_user_message_at"] else None,
            "is_locked": ho is not None and (ho if ho.tzinfo else ho.replace(tzinfo=timezone.utc)) > utc_now,
            "status": r["status"],
            "meta": meta,
        })
    logger.info(f"📤 Devueltos {len(out)} chats unificados (limit={limit}, offset={offset})")
    return out


@router.get("/admin/chats/{conversation_id}/messages")
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
                logger.warning(f"⚠️ Skipping invalid attachment (not a dict): {type(att)} - {att}")
                continue
            
            # Sign ALL URLs to ensure they go through the proxy (fixes audio mime-type issues)
            original_url = att.get("url", "")
            if original_url:
                # Generar firma para URL (sea externa o local /media/)
                signature, expires = generate_signed_url(original_url, tenant_id)
                # Construir URL del proxy con parámetros de seguridad
                from urllib.parse import urlencode
                proxy_params = {
                    "url": original_url,
                    "tenant_id": tenant_id,
                    "signature": signature,
                    "expires": expires
                }
                proxy_url = f"/admin/chat/media/proxy?{urlencode(proxy_params)}"
                
                signed_attachments.append({
                    **att,
                    "url": proxy_url,  # URL firmada para el proxy
                    "original_url": original_url  # Preservar URL original para referencia
                })
            else:
                signed_attachments.append(att)
        
        messages.append({
            "id": str(r["id"]),
            "conversation_id": str(r["conversation_id"]) if r.get("conversation_id") else None,
            "role": r["role"],
            "content": r["content"] or "",
            "timestamp": r["created_at"].isoformat() if r["created_at"] else None,
            "attachments": signed_attachments,
            "correlation_id": r.get("correlation_id"),
        })

    # Debug: mostrar el contenido crudo de content_attributes de cada mensaje
    if messages:
        sample_attrs = [(i, r.get("content_attributes"), type(r.get("content_attributes"))) for i, r in enumerate(rows[:3])]
        logger.info(f"🔍 Muestra de content_attributes crudos (primeros 3): {sample_attrs}")
    logger.info(f"📤 Devueltos {len(messages)} mensajes para conversación {conversation_id} (attachments check: {[len(m.get('attachments', []) or []) for m in messages]})")
    return messages


@router.post("/admin/chat/send")
@router.post("/admin/whatsapp/send")
async def unified_send_message(
    body: dict,
    tenant_id: int = Depends(get_resolved_tenant_id),
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
    
    if not message:
        raise HTTPException(status_code=400, detail="message required")

    pool = get_pool()
    
    # 2. Localizar conversación
    if conv_id_raw:
        try:
            conv_id = uuid.UUID(str(conv_id_raw))
            row = await pool.fetchrow(
                "SELECT * FROM chat_conversations WHERE id = $1 AND tenant_id = $2",
                conv_id, tenant_id
            )
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid conversation_id format")
    elif phone:
        # Fallback para búsqueda por teléfono (YCloud legacy)
        row = await pool.fetchrow(
            "SELECT * FROM chat_conversations WHERE external_user_id = $1 AND tenant_id = $2 AND channel = 'whatsapp'",
            str(phone), tenant_id
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
            detail="Ventana de 24h cerrada por política de Meta. Utilice plantillas para reabrir el canal."
        )
    
    # Normalizar a UTC si es naive
    if last_user_msg.tzinfo is None:
        last_user_msg = last_user_msg.replace(tzinfo=timezone.utc)
    
    if utc_now - last_user_msg > timedelta(hours=24):
        logger.warning(f"🚫 24h Window Closed for conversation {conv_id} (Last: {last_user_msg})")
        raise HTTPException(
            status_code=403, 
            detail="Ventana de 24h cerrada por política de Meta. Utilice plantillas para reabrir el canal."
        )

    # 4. ENVÍO SEGÚN PROVEEDOR
    try:
        if provider == "chatwoot":
            account_id = row["external_account_id"]
            cw_conv_id = row["external_chatwoot_id"]
            if not account_id or not cw_conv_id:
                raise HTTPException(status_code=400, detail="Chatwoot conversation not linked")
            
            token = await get_tenant_credential(tenant_id, CHATWOOT_API_TOKEN)
            base_url = await get_tenant_credential(tenant_id, CHATWOOT_BASE_URL) or "https://app.chatwoot.com"
            if not token:
                raise HTTPException(status_code=503, detail="Chatwoot credentials not configured")
            
            from chatwoot_client import ChatwootClient
            client = ChatwootClient(base_url, token)
            await client.send_text_message(account_id, cw_conv_id, message)
            
        elif provider == "ycloud":
            api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
            if not api_key:
                raise HTTPException(status_code=503, detail="YCloud credentials not configured")
            
            from ycloud_client import YCloudClient
            # Intentar obtener el 'from' (número de la clínica) si está en meta o credentials
            from_number = await get_tenant_credential(tenant_id, "YCLOUD_WHATSAPP_NUMBER")
            
            client = YCloudClient(api_key)
            # En YCloud, external_user_id es el teléfono (phone_number)
            await client.send_text_message(to=external_user_id, text=message, from_number=from_number)
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

        # 5. PERSISTENCIA Y NOTIFICACIÓN
        from db import db
        await db.pool.execute(
            """
            INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number) 
            VALUES ($1, $2, 'human_supervisor', $3, $4)
            """,
            tenant_id, conv_id, message, external_user_id,
        )
        
        # Sincronizar metadata de conversación (sin tocar la ventana de 24h ya que es saliente)
        from db import db as db_inst
        await db_inst.sync_conversation(tenant_id, channel, external_user_id, message, is_user=False)

        return {"status": "sent", "conversation_id": str(conv_id)}

    except Exception as e:
        logger.error(f"❌ Error sending message: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@router.post("/admin/conversations/{conversation_id}/human-override")
async def human_override(
    conversation_id: uuid.UUID,
    body: dict,
    tenant_id: int = Depends(get_resolved_tenant_id),
) -> dict:
    enabled = body.get("enabled", False)
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT id FROM chat_conversations WHERE id = $1 AND tenant_id = $2",
        conversation_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if enabled:
        await pool.execute(
            "UPDATE chat_conversations SET human_override_until = NOW() + INTERVAL '24 hours' WHERE id = $1",
            conversation_id,
        )
    else:
        await pool.execute(
            "UPDATE chat_conversations SET human_override_until = NULL WHERE id = $1",
            conversation_id,
        )
    return {"status": "ok", "human_override": enabled}
@router.get("/admin/chat/media/proxy")
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
    
    is_allowed = any(domain in url for domain in allowed_domains) or url.startswith("/media/")
    if not is_allowed:  
        logger.warning(f"❌ Dominio no permitido: {url}")
        raise HTTPException(status_code=403, detail="Dominio no permitido")
    
    logger.info(f"🎞️ Proxying media (tenant {tenant_id}): {url}")
    
    import mimetypes
    
    # Determinar Content-Type
    media_content_type, _ = mimetypes.guess_type(url)
    if not media_content_type:
        # Fallback manual para tipos comunes si mimetypes falla
        if ".ogg" in url.lower() or ".opus" in url.lower():
            media_content_type = "audio/ogg"
        elif ".mp3" in url.lower():
            media_content_type = "audio/mpeg"
        else:
            media_content_type = "application/octet-stream"

    async def stream_content():
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            try:
                # Si es una URL local del servidor, leer del disco de forma segura
                if url.startswith("/media/"):
                    # Normalizar path para evitar traversal
                    path_parts = url.replace("/media/", "").split("/")
                    # Bloquear paths que contengan ".."
                    if ".." in path_parts:
                        return
                        
                    local_path = os.path.join(os.getcwd(), "media", *path_parts)
                    if os.path.exists(local_path) and os.path.isfile(local_path):
                        with open(local_path, "rb") as f:
                            while chunk := f.read(65536):
                                yield chunk
                        return
                    else:
                        logger.error(f"❌ Local media not found: {local_path}")
                        return
                
                # De lo contrario, descargar del proveedor
                async with client.stream("GET", url) as response:
                    if response.status_code != 200:
                        logger.error(f"❌ Failed to proxy media ({response.status_code}): {url}")
                        return
                    
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except Exception as e:
                logger.error(f"❌ Error streaming media: {str(e)}")

    headers = {"Content-Type": media_content_type}
    return StreamingResponse(stream_content(), headers=headers)


@router.post("/admin/chat/upload")
async def chat_upload(
    file: UploadFile = File(...),
    tenant_id: int = Query(..., description="Tenant ID target"),
):
    """
    Sube un archivo de media localmente para ser enviado en el chat (Spec 19).
    Límite de 20MB.
    """
    import mimetypes
    import os
    import uuid
    
    # 1. Enforce 20MB limit (20 * 1024 * 1024 bytes)
    MAX_SIZE = 20 * 1024 * 1024
    
    # Check if we can get size from headers (fast check)
    content_length = file.size # Starlette/FastAPI 0.100+ typical place for size
    if content_length and content_length > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large (Max 20MB)")

    # Determinar tipo
    content_type = file.content_type or ""
    file_type = "file"
    if "image" in content_type: file_type = "image"
    elif "video" in content_type: file_type = "video"
    elif "audio" in content_type: file_type = "audio"
    
    ext = mimetypes.guess_extension(content_type) or ".bin"
    filename = f"{uuid.uuid4()}{ext}"
    
    # Asegurar directorio
    media_dir = os.path.join(os.getcwd(), "media", str(tenant_id))
    os.makedirs(media_dir, exist_ok=True)
    
    local_path = os.path.join(media_dir, filename)
    
    size_so_far = 0
    with open(local_path, "wb") as f:
        # We read in chunks to avoid memory spikes and double-check size
        while chunk := await file.read(65536): # 64KB chunks
            size_so_far += len(chunk)
            if size_so_far > MAX_SIZE:
                 f.close()
                 os.remove(local_path)
                 raise HTTPException(status_code=413, detail="File too large (Max 20MB)")
            f.write(chunk)
    
    return {
        "type": file_type,
        "url": f"/media/{tenant_id}/{filename}",
        "file_name": file.filename,
        "size": size_so_far
    }
