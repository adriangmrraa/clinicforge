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

    # 4. Normalize via ChannelService
    messages = await ChannelService.normalize_webhook("meta_direct", payload, tenant_id)

    if not messages:
        return {"status": "ignored", "reason": "no_relevant_messages"}

    # 5. Process through shared pipeline (same as Chatwoot/YCloud)
    from routes.chat_webhooks import _process_canonical_messages
    return await _process_canonical_messages(messages, tenant_id, "meta_direct", background_tasks)
