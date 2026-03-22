"""
Meta Direct Webhook — POST /admin/meta-direct/webhook
Receives normalized SimpleEvents from meta_service, resolves tenant, processes via ChannelService.
"""
import logging
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Header

from db import get_pool
from services.channels.service import ChannelService

logger = logging.getLogger(__name__)
router = APIRouter()


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

    # 3. Normalize via ChannelService
    messages = await ChannelService.normalize_webhook("meta_direct", payload, tenant_id)

    if not messages:
        return {"status": "ignored", "reason": "no_relevant_messages"}

    # 4. Process through shared pipeline (same as Chatwoot/YCloud)
    from routes.chat_webhooks import _process_canonical_messages
    return await _process_canonical_messages(messages, tenant_id, "meta_direct", background_tasks)
