"""
Meta Connect & Disconnect — POST /admin/meta/connect, DELETE /admin/meta/disconnect
Proxy to meta_service for connection, full cleanup for disconnection.
"""
import json
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from core.credentials import get_tenant_credential
from db import get_pool
from routes.chat_api import get_resolved_tenant_id, verify_staff_token

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/admin/meta/connect")
async def connect_meta_account(
    request: Request,
    tenant_id: int = Depends(get_resolved_tenant_id),
    user_data=Depends(verify_staff_token)
):
    """
    Proxy to meta_service POST /connect.
    Frontend sends code/access_token from FB.login() popup.
    """
    body = await request.json()
    code = body.get("code")
    access_token = body.get("access_token")
    redirect_uri = body.get("redirect_uri")

    # Allow CEO to specify tenant_id for multi-sede assignment
    requested_tenant = body.get("tenant_id")
    if requested_tenant and user_data.get("role") == "ceo":
        try:
            tenant_id = int(requested_tenant)
        except (ValueError, TypeError):
            raise HTTPException(400, "Invalid tenant_id")

    if not code and not access_token:
        raise HTTPException(400, "Missing code or access_token")

    meta_service_url = os.getenv("META_SERVICE_URL", "http://meta_service:8000")

    payload = {
        "tenant_id": tenant_id,
        "redirect_uri": redirect_uri
    }
    if code:
        payload["code"] = code
    if access_token:
        payload["access_token"] = access_token

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{meta_service_url}/connect", json=payload)
            if resp.status_code != 200:
                logger.error(f"meta_service_connect_failed: {resp.status_code} - {resp.text}")
                raise HTTPException(resp.status_code, "Meta Service Connection Failed")
            return resp.json()
    except httpx.ConnectError as e:
        logger.error(f"meta_service_unreachable: {e}")
        raise HTTPException(503, "Meta Service is not reachable. Check META_SERVICE_URL.")


@router.delete("/admin/meta/disconnect")
async def disconnect_meta(
    tenant_id: int = Depends(get_resolved_tenant_id),
    user_data=Depends(verify_staff_token)
):
    """
    Full cleanup: unsubscribe webhooks, delete credentials, assets, conversations, messages, PSIDs.
    """
    pool = get_pool()

    # 1. Get page tokens before deleting (needed for unsubscribe)
    pages = await pool.fetch(
        "SELECT content->>'id' as page_id FROM business_assets WHERE tenant_id = $1 AND asset_type = 'facebook_page'",
        tenant_id
    )

    # 2. Unsubscribe webhooks in Meta
    for page in pages:
        try:
            token = await get_tenant_credential(tenant_id, f"META_PAGE_TOKEN_{page['page_id']}")
            if token:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.delete(
                        f"https://graph.facebook.com/v22.0/{page['page_id']}/subscribed_apps",
                        params={"access_token": token}
                    )
                    logger.info(f"Unsubscribed webhooks for page {page['page_id']}")
        except Exception as e:
            logger.warning(f"Failed to unsubscribe page {page['page_id']}: {e}")

    # 3. Delete messages from meta_direct conversations
    await pool.execute("""
        DELETE FROM chat_messages WHERE conversation_id IN (
            SELECT id FROM chat_conversations WHERE tenant_id = $1 AND provider = 'meta_direct'
        )
    """, tenant_id)

    # 4. Delete meta_direct conversations
    deleted_convs = await pool.execute(
        "DELETE FROM chat_conversations WHERE tenant_id = $1 AND provider = 'meta_direct'",
        tenant_id
    )

    # 5. Delete business_assets
    await pool.execute("DELETE FROM business_assets WHERE tenant_id = $1", tenant_id)

    # 6. Delete meta credentials
    await pool.execute(
        "DELETE FROM credentials WHERE tenant_id = $1 AND category = 'meta'",
        tenant_id
    )

    # 7. Clean PSIDs in patients
    await pool.execute(
        "UPDATE patients SET instagram_psid = NULL, facebook_psid = NULL WHERE tenant_id = $1",
        tenant_id
    )

    logger.info(f"Meta Direct disconnected for tenant {tenant_id}: cleaned all data")
    return {"status": "disconnected", "tenant_id": tenant_id}


@router.get("/admin/meta/status")
async def meta_connection_status(
    tenant_id: int = Depends(get_resolved_tenant_id),
    user_data=Depends(verify_staff_token)
):
    """Check if Meta is connected for this tenant (has business_assets)."""
    pool = get_pool()
    assets = await pool.fetch(
        "SELECT asset_type, content FROM business_assets WHERE tenant_id = $1 AND is_active = true",
        tenant_id
    )

    if not assets:
        return {"connected": False, "assets": {"pages": [], "instagram": [], "whatsapp": []}}

    result = {"pages": [], "instagram": [], "whatsapp": []}
    for a in assets:
        content = json.loads(a["content"]) if isinstance(a["content"], str) else a["content"]
        if a["asset_type"] == "facebook_page":
            result["pages"].append({"id": content.get("id"), "name": content.get("name")})
        elif a["asset_type"] == "instagram_account":
            result["instagram"].append({"id": content.get("id"), "username": content.get("username")})
        elif a["asset_type"] == "whatsapp_waba":
            result["whatsapp"].append({"id": content.get("id"), "name": content.get("name"), "phone_numbers": content.get("phone_numbers", [])})

    return {
        "connected": True,
        "assets": result
    }
