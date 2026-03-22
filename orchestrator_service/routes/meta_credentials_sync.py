"""
Meta Credentials Sync — POST /admin/credentials/internal-sync
Receives encrypted credentials from meta_service and stores them in the vault.
"""
import json
import logging
import os

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any

from db import get_pool
from core.credentials import save_tenant_credential

logger = logging.getLogger(__name__)
router = APIRouter()


class MetaSyncRequest(BaseModel):
    tenant_id: str
    provider: str
    credentials: Dict[str, Any]


@router.post("/admin/credentials/internal-sync")
async def internal_credential_sync(
    data: MetaSyncRequest,
    x_internal_secret: str = Header(None)
):
    """
    Called by meta_service to sync raw credentials/assets after popup connection.
    """
    expected = os.getenv("INTERNAL_API_TOKEN", "")
    alt = os.getenv("INTERNAL_SECRET_KEY", "")
    if x_internal_secret not in (expected, alt):
        raise HTTPException(401, "Unauthorized Internal Call")

    try:
        tenant_id = int(data.tenant_id)
        creds = data.credentials
        pool = get_pool()

        if data.provider == "meta":
            # 1. Store long-lived user token
            user_token = creds.get("user_access_token")
            if user_token:
                await save_tenant_credential(tenant_id, "META_USER_LONG_TOKEN", user_token, "meta")

            assets = creds.get("assets", {})

            # 2. Store page tokens
            first_page_token_stored = False
            for page in assets.get("pages", []):
                if page.get("access_token"):
                    await save_tenant_credential(
                        tenant_id, f"META_PAGE_TOKEN_{page['id']}", page["access_token"], "meta"
                    )
                    if not first_page_token_stored:
                        await save_tenant_credential(
                            tenant_id, "meta_page_token", page["access_token"], "meta"
                        )
                        first_page_token_stored = True

            # 3. Store IG tokens (use linked page token)
            for ig in assets.get("instagram", []):
                if ig.get("access_token"):
                    await save_tenant_credential(
                        tenant_id, f"META_IG_TOKEN_{ig['id']}", ig["access_token"], "meta"
                    )

            # 4. Store WhatsApp tokens
            for waba in assets.get("whatsapp", []):
                if waba.get("access_token"):
                    await save_tenant_credential(
                        tenant_id, f"META_WA_TOKEN_{waba['id']}", waba["access_token"], "meta"
                    )

            # 5. Store business_assets (upsert)
            async def store_asset_batch(asset_list, asset_type):
                for item in asset_list:
                    safe_item = {k: v for k, v in item.items() if k != "access_token"}
                    safe_item["status"] = "active"
                    external_id = str(item["id"])

                    existing = await pool.fetchrow(
                        "SELECT id FROM business_assets WHERE tenant_id = $1 AND asset_type = $2 AND content->>'id' = $3",
                        tenant_id, asset_type, external_id
                    )

                    if existing:
                        await pool.execute(
                            "UPDATE business_assets SET content = $1, is_active = true, updated_at = NOW() WHERE id = $2",
                            json.dumps(safe_item), existing["id"]
                        )
                    else:
                        await pool.execute(
                            "INSERT INTO business_assets (tenant_id, asset_type, content, is_active, created_at) VALUES ($1, $2, $3, true, NOW())",
                            tenant_id, asset_type, json.dumps(safe_item)
                        )

            await store_asset_batch(assets.get("pages", []), "facebook_page")
            await store_asset_batch(assets.get("instagram", []), "instagram_account")
            await store_asset_batch(assets.get("whatsapp", []), "whatsapp_waba")

            logger.info(f"Meta credentials synced for tenant {tenant_id}: "
                        f"pages={len(assets.get('pages', []))}, "
                        f"ig={len(assets.get('instagram', []))}, "
                        f"wa={len(assets.get('whatsapp', []))}")

        return {"status": "ok", "tenant_id": tenant_id}

    except Exception as e:
        logger.error(f"internal_credential_sync_failed: {e}")
        raise HTTPException(500, str(e))
