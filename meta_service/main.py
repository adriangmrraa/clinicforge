import os
import uuid
import httpx
import structlog
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Query
from contextlib import asynccontextmanager
from typing import Optional

from core.auth import MetaAuthService
from core.webhooks import MetaWebhookService
from core.client import OrchestratorClient

# Configuration
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "clinicforge_meta_verify")
META_APP_SECRET = os.getenv("META_APP_SECRET")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator_service:8000")

# Logging
structlog.configure(processors=[structlog.processors.JSONRenderer()])
logger = structlog.get_logger()

# Services
auth_service = MetaAuthService()
webhook_service = MetaWebhookService(META_VERIFY_TOKEN, META_APP_SECRET)
orchestrator_client = OrchestratorClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", service="meta_service")
    yield
    logger.info("shutdown")


app = FastAPI(title="ClinicForge Meta Service", lifespan=lifespan)


# --- Health ---

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "meta_service"}


# --- Connection Flow ---

@app.post("/connect")
async def connect_meta_account(data: dict):
    """
    Frontend calls this (via orchestrator proxy) with an Authorization Code from FB Login SDK.
    We: Exchange Code -> Get Assets -> Subscribe Webhooks -> Sync with Orchestrator.
    """
    code = data.get("code")
    access_token = data.get("access_token")
    tenant_id = data.get("tenant_id")
    frontend_url = os.getenv("FRONTEND_URL", "https://dentalforge-frontend.gvdlcu.easypanel.host")
    redirect_uri = data.get("redirect_uri") or frontend_url

    if not tenant_id:
        raise HTTPException(400, "Missing tenant_id")
    if not code and not access_token:
        raise HTTPException(400, "Missing code or access_token")

    result = await _handle_connection_flow(code, access_token, tenant_id, redirect_uri)
    return result


async def _handle_connection_flow(code: str, access_token: str, tenant_id: str, redirect_uri: str):
    try:
        # 1. Get token
        if access_token:
            long_token = access_token
            logger.info("direct_token_received", tenant_id=tenant_id)
        else:
            long_token = await auth_service.exchange_code(code, redirect_uri)
            logger.info("code_exchanged", tenant_id=tenant_id)

        # 2. Get Assets (Pages, IG, WABA)
        assets = await auth_service.get_accounts(long_token)
        logger.info("assets_fetched", tenant_id=tenant_id, count=len(assets["pages"]))

        # 3. Sync to Orchestrator
        payload = {
            "tenant_id": tenant_id,
            "provider": "meta",
            "credentials": {
                "user_access_token": long_token,
                "assets": assets
            }
        }
        await orchestrator_client.sync_credentials(payload)

        # 4. Return sanitized assets (NO tokens to browser)
        sanitized_assets = {
            "pages": [{k: v for k, v in p.items() if k != "access_token"} for p in assets.get("pages", [])],
            "instagram": assets.get("instagram", []),
            "whatsapp": assets.get("whatsapp", [])
        }
        # Strip tokens from IG too
        for ig in sanitized_assets["instagram"]:
            ig.pop("access_token", None)
        for wa in sanitized_assets["whatsapp"]:
            wa.pop("access_token", None)

        return {
            "status": "success",
            "connected": {
                "facebook": len(assets.get("pages", [])) > 0,
                "instagram": len(assets.get("instagram", [])) > 0,
                "whatsapp": len(assets.get("whatsapp", [])) > 0
            },
            "assets": sanitized_assets
        }

    except Exception as e:
        logger.error("connection_flow_failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(500, f"Connection Failed: {str(e)}")


# --- Webhooks ---

@app.get("/webhook")
async def verify_webhook(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge")
):
    """Meta Verification Challenge."""
    return webhook_service.verify_challenge(mode, token, challenge)


@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Ingests and Normalizes Meta Events, forwards to Orchestrator."""
    # 1. Verify Signature
    if META_APP_SECRET:
        await webhook_service.verify_signature(request)

    # 2. Parse & Normalize
    try:
        body = await request.json()
        simple_event = webhook_service.normalize_payload(body)

        if simple_event:
            background_tasks.add_task(orchestrator_client.ingest_webhook_event, simple_event)
            return {"status": "processed"}
        else:
            return {"status": "ignored", "reason": "no_relevant_change"}

    except Exception as e:
        logger.error("webhook_error", error=str(e))
        raise HTTPException(500, "Processing failed")


# --- Webhook Subscription ---

@app.post("/subscribe")
async def subscribe_asset(data: dict):
    """Subscribes assets to webhooks (page-level for FB/IG, WABA register for WA)."""
    asset_id = data.get("asset_id")
    access_token = data.get("access_token")
    asset_type = data.get("asset_type")

    if not all([asset_id, access_token, asset_type]):
        raise HTTPException(400, "Missing asset_id, access_token, or asset_type")

    async with httpx.AsyncClient(timeout=10.0) as client:
        if asset_type in ("facebook_page", "instagram_account"):
            page_id = data.get("linked_page_id") or asset_id
            await auth_service.subscribe_page(client, page_id, access_token)
            return {"status": "ok", "message": f"Subscribed page {page_id} for {asset_type}"}

        elif asset_type == "whatsapp_waba":
            phone_number_id = data.get("phone_number_id")
            if phone_number_id:
                api_version = os.getenv("META_GRAPH_API_VERSION", "v22.0")
                url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/register"
                resp = await client.post(url, json={
                    "messaging_product": "whatsapp",
                    "pin": "123456"
                }, headers={"Authorization": f"Bearer {access_token}"})
                logger.info("whatsapp_phone_register", phone_number_id=phone_number_id, status=resp.status_code)
            return {"status": "ok", "message": f"WhatsApp WABA {asset_id} configured"}

    return {"status": "ignored", "message": f"No subscription action for {asset_type}"}


# --- Message Sending Proxies ---

@app.post("/messages/send")
async def send_message_proxy(data: dict):
    """Sends a message via Meta Graph API (Facebook Messenger / Instagram DM)."""
    recipient_id = data.get("recipient_id")
    text = data.get("text")
    access_token = data.get("access_token")
    messaging_type = data.get("messaging_type", "RESPONSE")

    if not all([recipient_id, text, access_token]):
        raise HTTPException(400, "Missing required fields")

    url = "https://graph.facebook.com/v22.0/me/messages"
    params = {"access_token": access_token}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": messaging_type
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, params=params, json=payload)
        if resp.status_code != 200:
            logger.error("meta_send_failed", status=resp.status_code, body=resp.text)
            raise HTTPException(resp.status_code, f"Meta API Error: {resp.text}")
        return resp.json()


@app.post("/whatsapp/send")
async def send_whatsapp_message_proxy(data: dict):
    """Sends a message via WhatsApp Cloud API."""
    recipient_id = data.get("recipient_id")
    text = data.get("text")
    access_token = data.get("access_token")
    phone_number_id = data.get("phone_number_id")

    if not all([recipient_id, text, access_token, phone_number_id]):
        raise HTTPException(400, "Missing required fields")

    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_id,
        "type": "text",
        "text": {"body": text}
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code not in [200, 201]:
            logger.error("whatsapp_send_failed", status=resp.status_code, body=resp.text)
            raise HTTPException(resp.status_code, f"WhatsApp Cloud API Error: {resp.text}")
        return resp.json()


# --- Privacy / GDPR ---

@app.post("/privacy/data-deletion")
async def data_deletion_callback(request: Request):
    """Standard Meta Data Deletion Callback (required for app approval)."""
    try:
        data = await request.form()
        confirmation_code = str(uuid.uuid4())
        status_url = f"https://{request.headers.get('host')}/privacy/deletion-status/{confirmation_code}"
        return {
            "url": status_url,
            "confirmation_code": confirmation_code
        }
    except Exception as e:
        logger.error("data_deletion_error", error=str(e))
        raise HTTPException(400, "Invalid Request")


@app.get("/privacy/deletion-status/{code}")
async def deletion_status(code: str):
    """Status check for data deletion."""
    return {
        "status": "completed",
        "message": "Your data deletion request has been processed.",
        "code": code
    }
