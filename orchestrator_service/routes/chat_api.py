"""
API de chats para la UI: summary, messages, send, human-override, config Chatwoot.
CLINICASV1.0 - paridad con Version Estable. Filtro por tenant_id vía get_resolved_tenant_id.
"""
import json
import logging
import os
import uuid
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
    return [
        {
            "id": str(r["id"]),
            "conversation_id": str(r["conversation_id"]) if r.get("conversation_id") else None,
            "role": r["role"],
            "content": r["content"] or "",
            "timestamp": r["created_at"].isoformat() if r["created_at"] else None,
            "attachments": r["content_attributes"] if isinstance(r.get("content_attributes"), list) else [],
            "correlation_id": r.get("correlation_id"),
        }
        for r in rows
    ]


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
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Proxy seguro para medios (Spec 19). 
    Evita problemas de CORS y oculta URLs privadas de proveedores.
    """
    logger.info(f"🎞️ Proxying media request for tenant {tenant_id}: {url}")
    
    # Validar que la URL sea de un dominio conocido (opcional pero recomendado por seguridad)
    # Por ahora permitimos todas las URLs ya que el acceso está protegido por get_resolved_tenant_id
    
    async def stream_content():
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            try:
                # Si es una URL local del servidor (almacenamiento persistente), leer del disco
                if url.startswith("/media/"):
                    # Asumimos que /media en la URL mapea a una carpeta local
                    # En una implementación real con Docker, esto sería un volumen
                    local_path = os.path.join(os.getcwd(), "media", url.replace("/media/", ""))
                    if os.path.exists(local_path):
                        with open(local_path, "rb") as f:
                            while chunk := f.read(8192):
                                yield chunk
                        return
                
                # De lo contrario, descargar del proveedor
                async with client.stream("GET", url) as response:
                    if response.status_code != 200:
                        logger.error(f"❌ Failed to proxy media: {response.status_code}")
                        return
                    
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except Exception as e:
                logger.error(f"❌ Error streaming media: {str(e)}")

    return StreamingResponse(stream_content())


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
