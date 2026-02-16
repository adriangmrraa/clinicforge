"""
API de chats para la UI: summary, messages, send, human-override, config Chatwoot.
CLINICASV1.0 - paridad con Version Estable. Filtro por tenant_id vía get_resolved_tenant_id.
"""
import json
import logging
import os
import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

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

@router.get("/admin/integrations/chatwoot/config")
async def get_chatwoot_webhook_config(
    request: Request,
    tenant_id: int = Depends(get_resolved_tenant_id),
) -> dict:
    try:
        pool = get_pool()
        secure_token = await get_tenant_credential(tenant_id, WEBHOOK_ACCESS_TOKEN)
        if not secure_token:
            secure_token = uuid.uuid4().hex + uuid.uuid4().hex
            await pool.execute(
                "INSERT INTO credentials (tenant_id, name, value, updated_at) VALUES ($1, $2, $3, NOW()) "
                "ON CONFLICT (tenant_id, name) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()",
                tenant_id,
                WEBHOOK_ACCESS_TOKEN,
                secure_token,
            )
            logger.info(f"✅ chatwoot_webhook_token_generated tenant_id={tenant_id}")
        # Detección dinámica de URL base (Nexus Sovereign Protocol)
        # 1. Intentar desde env 
        # 2. Si no, usar request.base_url (detecta protocolo y dominio/puerto actual)
        api_base = os.getenv("BASE_URL", "").rstrip("/")
        if not api_base:
            # Reconstrucción manual para mayor precisión con Proxies
            scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
            host = request.headers.get("x-forwarded-host", request.url.netloc)
            api_base = f"{scheme}://{host}"
            
        webhook_path = "/admin/chatwoot/webhook"
        full_url = f"{api_base}{webhook_path}?access_token={secure_token}"
            
        return {
            "webhook_path": webhook_path,
            "access_token": secure_token,
            "tenant_id": tenant_id,
            "api_base": api_base,
            "full_webhook_url": full_url,
        }
    except Exception as e:
        logger.exception(f"🔥 Error en get_chatwoot_webhook_config para tenant={tenant_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
               c.status, c.human_override_until, c.meta
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
            "attachments": (r["content_attributes"] or []) if isinstance(r.get("content_attributes"), list) else (r.get("content_attributes") or {}),
            "correlation_id": r.get("correlation_id"),
        }
        for r in rows
    ]


@router.post("/admin/whatsapp/send")
async def send_message(
    body: dict,
    tenant_id: int = Depends(get_resolved_tenant_id),
) -> dict:
    conv_id_raw = body.get("conversation_id") if isinstance(body, dict) else getattr(body, "conversation_id", None)
    message = (body.get("message", "") if isinstance(body, dict) else getattr(body, "message", "")) or ""
    message = message.strip()
    if not conv_id_raw or not message:
        raise HTTPException(status_code=400, detail="conversation_id and message required")
    try:
        conv_id = uuid.UUID(str(conv_id_raw))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid conversation_id format")
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT id, provider, external_user_id, external_chatwoot_id, external_account_id FROM chat_conversations WHERE id = $1 AND tenant_id = $2",
        conv_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")
    provider = (row["provider"] or "ycloud").lower()
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
        logger.warning("ycloud_send_not_implemented_placeholder", conv_id=conv_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    # CLINICASV1.0: chat_messages tiene from_number NOT NULL e id BIGSERIAL
    await pool.execute(
        "INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number) VALUES ($1, $2, 'human_supervisor', $3, $4)",
        tenant_id, conv_id, message, row["external_user_id"] or "chatwoot",
    )
    return {"status": "sent"}


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
