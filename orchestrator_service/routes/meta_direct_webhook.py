"""
Meta Direct Webhook — POST /admin/meta-direct/webhook
Receives normalized SimpleEvents from meta_service, resolves tenant, processes via ChannelService.
"""
import logging
import os

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Header

from db import get_pool
from core.credentials import get_tenant_credential
from services.channels.service import ChannelService

logger = logging.getLogger(__name__)
router = APIRouter()


async def _fetch_sender_name(sender_id: str, recipient_id: str, platform: str, tenant_id: int) -> str:
    """Fetch sender name from Meta Graph API using the page token."""
    try:
        # Get page token for this tenant
        page_token = await get_tenant_credential(tenant_id, f"META_PAGE_TOKEN_{recipient_id}")
        if not page_token:
            page_token = await get_tenant_credential(tenant_id, "meta_page_token")
        if not page_token:
            return ""

        api_version = os.getenv("META_GRAPH_API_VERSION", "v22.0")

        async with httpx.AsyncClient(timeout=5.0) as client:
            if platform == "facebook":
                # Use conversations endpoint (direct GET /{psid} is restricted in v13+)
                url = f"https://graph.facebook.com/{api_version}/{recipient_id}/conversations"
                resp = await client.get(url, params={
                    "fields": "participants",
                    "user_id": sender_id,
                    "access_token": page_token
                })
                data = resp.json()
                if resp.status_code == 200 and "error" not in data:
                    convs = data.get("data", [])
                    if convs:
                        for p in convs[0].get("participants", {}).get("data", []):
                            if p.get("id") == sender_id:
                                return p.get("name", "")
                            elif p.get("id") != recipient_id:
                                return p.get("name", "")

                # Fallback: direct profile fetch
                url2 = f"https://graph.facebook.com/{api_version}/{sender_id}"
                resp2 = await client.get(url2, params={
                    "fields": "first_name,last_name",
                    "access_token": page_token
                })
                data2 = resp2.json()
                if resp2.status_code == 200 and "error" not in data2:
                    first = data2.get("first_name", "")
                    last = data2.get("last_name", "")
                    return f"{first} {last}".strip()

            elif platform == "instagram":
                url = f"https://graph.facebook.com/{api_version}/{sender_id}"
                resp = await client.get(url, params={
                    "fields": "name,username,profile_pic",
                    "access_token": page_token
                })
                data = resp.json()
                if resp.status_code == 200 and "error" not in data:
                    return data.get("name") or data.get("username") or ""

    except Exception as e:
        logger.warning(f"Failed to fetch sender name: {e}")
    return ""


@router.post("/admin/meta-direct/webhook")
async def receive_meta_direct_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_internal_secret: str = Header(None)
):
    """
    Receives SimpleEvents from the meta_service (The Meta Diplomat).
    Resolves tenant via business_assets, normalizes to CanonicalMessage,
    and processes through the same pipeline as Chatwoot/YCloud.
    """
    # 1. Verify inter-service secret
    expected = os.getenv("INTERNAL_API_TOKEN", "")
    alt = os.getenv("INTERNAL_SECRET_KEY", "")
    if x_internal_secret not in (expected, alt):
        raise HTTPException(403, "Unauthorized")

    payload = await request.json()
    logger.info(f"Meta Direct webhook received: platform={payload.get('platform')}, sender={payload.get('sender_id')}")

    # 2. Resolve tenant via business_assets
    pool = get_pool()
    recipient_id = payload.get("recipient_id") or payload.get("tenant_identifier")

    tenant_id = None
    if recipient_id:
        row = await pool.fetchrow(
            "SELECT tenant_id FROM business_assets WHERE content->>'id' = $1 AND is_active = true LIMIT 1",
            str(recipient_id)
        )
        if row:
            tenant_id = int(row['tenant_id'])

    # Fallback: WhatsApp — try bot_phone_number in tenants
    if not tenant_id and payload.get("platform") == "whatsapp":
        phone = str(recipient_id or "").replace("+", "")
        row = await pool.fetchrow("SELECT id FROM tenants WHERE bot_phone_number = $1", phone)
        if row:
            tenant_id = row['id']

    if not tenant_id:
        logger.warning(f"Meta Direct: No tenant found for recipient {recipient_id}")
        return {"status": "ignored", "reason": "tenant_not_found"}

    # 3. Enrich sender name if missing
    sender_name = payload.get("sender_name")
    if not sender_name or sender_name == "User":
        sender_id = payload.get("sender_id", "")
        platform = payload.get("platform", "facebook")
        resolved_name = await _fetch_sender_name(sender_id, str(recipient_id), platform, tenant_id)
        if resolved_name:
            payload["sender_name"] = resolved_name
            logger.info(f"Sender name resolved: {resolved_name} (platform={platform})")

    # 4. Handle echo messages (doctor/staff sent from Instagram/Facebook app)
    # Intercept BEFORE normalization to avoid touching the existing pipeline.
    if payload.get("is_echo") or payload.get("event_type") == "message_echo":
        from datetime import datetime, timezone, timedelta
        import json

        user_id = payload.get("sender_id", "")  # In echo, sender_id = the user who RECEIVED the message
        text = (payload.get("payload") or {}).get("text") or ""
        platform = payload.get("platform", "instagram")
        override_until = datetime.now(timezone.utc) + timedelta(hours=24)

        if user_id:
            # Activate manual mode on BOTH tables
            await pool.execute(
                "UPDATE patients SET human_handoff_requested = true, human_override_until = $1, updated_at = NOW() WHERE tenant_id = $2 AND (phone_number = $3 OR instagram_psid = $3 OR facebook_psid = $3)",
                override_until, tenant_id, user_id,
            )
            await pool.execute(
                "UPDATE chat_conversations SET human_override_until = $1, updated_at = NOW() WHERE tenant_id = $2 AND external_user_id = $3",
                override_until, tenant_id, user_id,
            )

            # Persist the message for full conversation context
            if text:
                conv_row = await pool.fetchrow(
                    "SELECT id FROM chat_conversations WHERE tenant_id = $1 AND external_user_id = $2 ORDER BY updated_at DESC LIMIT 1",
                    tenant_id, user_id,
                )
                if conv_row:
                    meta_json = json.dumps({"source": f"{platform}_app_echo", "provider": "meta_direct"})
                    await pool.execute(
                        "INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, platform_metadata) VALUES ($1, $2, 'assistant', $3, $4, $5::jsonb)",
                        tenant_id, conv_row["id"], text, user_id, meta_json,
                    )
                    # Update conversation preview
                    await pool.execute(
                        "UPDATE chat_conversations SET last_message = $1, updated_at = NOW() WHERE id = $2",
                        text[:200], conv_row["id"],
                    )

            logger.info(f"👤 {platform} echo → manual mode activated for {user_id} (tenant={tenant_id})")
            try:
                from main import sio
                await sio.emit("HUMAN_OVERRIDE_CHANGED", {"phone_number": user_id, "tenant_id": tenant_id, "enabled": True, "until": override_until.isoformat()}, room=f"tenant:{tenant_id}")
            except Exception:
                pass

        return {"status": "echo_handled", "manual_mode": True}

    # 5. Normalize via ChannelService (only for NON-echo messages)
    messages = await ChannelService.normalize_webhook("meta_direct", payload, tenant_id)

    if not messages:
        return {"status": "ignored", "reason": "no_relevant_messages"}

    # 6. Process through shared pipeline (same as Chatwoot/YCloud)
    from routes.chat_webhooks import _process_canonical_messages
    return await _process_canonical_messages(messages, tenant_id, "meta_direct", background_tasks)
