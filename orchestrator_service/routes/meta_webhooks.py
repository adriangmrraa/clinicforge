"""
Meta Ads Webhooks for ClinicForge - Dual Attribution System
Handles both WhatsApp referral attribution and Lead Forms webhooks

Spec: Complete Meta Ads Attribution System
- WhatsApp Clicks: Referral object processing
- Lead Forms: Standard Meta webhook + custom payloads (n8n/LeadsBridge)
- Background processing for scalability
- Multi-tenant isolation with tenant_id
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Query

from core.auth import verify_admin_token, get_resolved_tenant_id
from core.rate_limiter import limiter
from db import get_pool, update_patient_attribution_from_meta_webhook
from services.meta_ads_service import MetaAdsClient

logger = logging.getLogger(__name__)
router = APIRouter()

# Webhook verification token (configured in Meta Developers)
META_WEBHOOK_VERIFY_TOKEN = os.getenv("META_WEBHOOK_VERIFY_TOKEN", "clinicforge_meta_secret_token")


@router.get("/webhooks/meta")
async def verify_meta_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token")
):
    """
    Meta Webhook Verification Endpoint.
    
    Required by Meta to verify webhook URL.
    Returns hub.challenge if verify_token matches.
    """
    if hub_mode == "subscribe" and hub_verify_token == META_WEBHOOK_VERIFY_TOKEN:
        logger.info("✅ Meta webhook verified successfully")
        return int(hub_challenge)
    
    logger.warning(f"❌ Meta webhook verification failed: mode={hub_mode}, token={hub_verify_token}")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhooks/meta")
@limiter.limit("20/minute")
async def receive_meta_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    tenant_id: Optional[int] = None
):
    """
    Receives Meta Lead Forms webhooks.
    
    Supports:
    1. Standard Meta webhook (entry-based)
    2. Custom flattened payloads (n8n/LeadsBridge)
    3. Background processing for scalability
    
    Returns immediate 200 OK, processes in background.
    """
    try:
        body = await request.json()
        logger.info(f"📥 Received Meta webhook: {json.dumps(body)[:500]}...")
        
    except Exception as e:
        logger.error(f"❌ Error parsing Meta webhook JSON: {e}")
        return {"status": "error", "message": "Invalid JSON"}
    
    # Detect payload type and process in background
    if isinstance(body, dict) and "entry" in body:
        # Standard Meta webhook format
        background_tasks.add_task(
            process_standard_meta_lead,
            body,
            tenant_id or await get_resolved_tenant_id(request)
        )
        return {"status": "processing", "type": "meta_standard"}
    
    else:
        # Custom flattened payload (n8n/LeadsBridge format)
        background_tasks.add_task(
            process_flattened_lead,
            body,
            tenant_id or await get_resolved_tenant_id(request)
        )
        return {"status": "processing", "type": "meta_custom"}


async def process_standard_meta_lead(payload: Dict[str, Any], tenant_id: int):
    """
    Processes standard Meta webhook payload.
    
    Standard format:
    {
        "entry": [{
            "changes": [{
                "value": {
                    "leadgen_id": "123",
                    "page_id": "456",
                    "ad_id": "789"
                }
            }]
        }]
    }
    """
    try:
        logger.info(f"🔍 Processing standard Meta lead for tenant {tenant_id}")
        
        # Extract leadgen_id from payload
        leadgen_id = None
        page_id = None
        ad_id = None
        
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                leadgen_id = value.get("leadgen_id")
                page_id = value.get("page_id")
                ad_id = value.get("ad_id")
                break
            if leadgen_id:
                break
        
        if not leadgen_id:
            logger.warning("⚠️ No leadgen_id found in standard Meta payload")
            return
        
        # Get Meta token for this tenant/page
        meta_token = await get_meta_token_for_page(tenant_id, page_id)
        if not meta_token:
            logger.warning(f"⚠️ No Meta token found for tenant {tenant_id}, page {page_id}")
            return
        
        # Fetch lead details from Meta Graph API
        lead_details = await fetch_lead_details_from_meta(leadgen_id, meta_token)
        if not lead_details:
            logger.warning(f"⚠️ Could not fetch lead details for leadgen_id {leadgen_id}")
            return
        
        # Create/update patient with attribution
        patient_id = await create_or_update_patient_from_lead(lead_details, tenant_id, ad_id)
        if patient_id:
            logger.info(f"✅ Patient {patient_id} created/updated from Meta lead {leadgen_id}")
            
            # Fetch ad details for attribution
            if ad_id and meta_token:
                ad_details = await fetch_ad_details_from_meta(ad_id, meta_token)
                if ad_details:
                    await update_patient_attribution_from_meta_webhook(
                        patient_id, tenant_id, ad_details
                    )
        
    except Exception as e:
        logger.error(f"❌ Error processing standard Meta lead: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def process_flattened_lead(payload: Any, tenant_id: int):
    """
    Processes custom flattened payload (n8n/LeadsBridge format).
    
    Expected format:
    [
        {
            "body": {
                "phone_number": "+5491234567890",
                "name": "John Doe",
                "email": "john@example.com",
                "meta_ad_id": "123",
                "meta_campaign_id": "456",
                "meta_adset_id": "789"
            }
        }
    ]
    """
    try:
        logger.info(f"🔍 Processing flattened lead for tenant {tenant_id}")
        
        # Handle both list and single object formats
        if isinstance(payload, list):
            leads = payload
        else:
            leads = [payload]
        
        for lead_item in leads:
            lead_data = lead_item.get("body") if isinstance(lead_item, dict) else lead_item
            
            if not isinstance(lead_data, dict):
                continue
            
            # Extract patient data
            phone_number = lead_data.get("phone_number")
            name = lead_data.get("name", "Visitante")
            email = lead_data.get("email")
            
            if not phone_number:
                logger.warning("⚠️ No phone_number in flattened lead")
                continue
            
            # Extract Meta Ads data
            meta_data = {
                "ad_id": lead_data.get("meta_ad_id"),
                "ad_name": lead_data.get("meta_ad_name"),
                "adset_id": lead_data.get("meta_adset_id"),
                "adset_name": lead_data.get("meta_adset_name"),
                "campaign_id": lead_data.get("meta_campaign_id"),
                "campaign_name": lead_data.get("meta_campaign_name"),
                "headline": lead_data.get("meta_ad_headline"),
                "body": lead_data.get("meta_ad_body")
            }
            
            # Create/update patient
            patient_id = await create_or_update_patient(
                phone_number=phone_number,
                tenant_id=tenant_id,
                first_name=extract_first_name(name),
                last_name=extract_last_name(name),
                email=email,
                meta_data=meta_data
            )
            
            if patient_id:
                logger.info(f"✅ Patient {patient_id} created/updated from flattened lead")
    
    except Exception as e:
        logger.error(f"❌ Error processing flattened lead: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def get_meta_token_for_page(tenant_id: int, page_id: Optional[str]) -> Optional[str]:
    """
    Gets Meta access token for a specific page.
    
    Args:
        tenant_id: Tenant ID
        page_id: Meta Page ID (optional)
    
    Returns:
        Optional[str]: Meta access token
    """
    try:
        pool = get_pool()
        
        query = """
            SELECT access_token FROM meta_tokens 
            WHERE tenant_id = $1 AND (page_id = $2 OR $2 IS NULL)
            ORDER BY created_at DESC LIMIT 1
        """
        
        async with pool.acquire() as conn:
            token = await conn.fetchval(query, tenant_id, page_id)
            return token
            
    except Exception as e:
        logger.error(f"❌ Error getting Meta token: {e}")
        return None


async def fetch_lead_details_from_meta(leadgen_id: str, access_token: str) -> Optional[Dict[str, Any]]:
    """
    Fetches lead details from Meta Graph API.
    
    Args:
        leadgen_id: Meta Leadgen ID
        access_token: Meta access token
    
    Returns:
        Optional[Dict]: Lead details
    """
    try:
        client = MetaAdsClient(access_token)
        
        # Note: MetaAdsClient might need extension for lead details
        # For now, we'll use a direct HTTP call
        import httpx
        
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(
                f"https://graph.facebook.com/v21.0/{leadgen_id}",
                params={"access_token": access_token}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Meta API error: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        logger.error(f"❌ Error fetching lead details: {e}")
        return None


async def fetch_ad_details_from_meta(ad_id: str, access_token: str) -> Optional[Dict[str, Any]]:
    """
    Fetches ad details from Meta Graph API.
    
    Args:
        ad_id: Meta Ad ID
        access_token: Meta access token
    
    Returns:
        Optional[Dict]: Ad details
    """
    try:
        client = MetaAdsClient(access_token)
        ad_details = await client.get_ad_details(ad_id)
        return ad_details
        
    except Exception as e:
        logger.error(f"❌ Error fetching ad details: {e}")
        return None


async def create_or_update_patient_from_lead(
    lead_details: Dict[str, Any], 
    tenant_id: int, 
    ad_id: Optional[str] = None
) -> Optional[int]:
    """
    Creates or updates a patient from Meta lead details.
    
    Args:
        lead_details: Lead details from Meta API
        tenant_id: Tenant ID
        ad_id: Meta Ad ID (optional)
    
    Returns:
        Optional[int]: Patient ID
    """
    try:
        pool = get_pool()
        
        # Extract data from lead details
        # Meta lead structure varies, adjust as needed
        field_data = lead_details.get("field_data", [])
        
        phone_number = None
        name = "Visitante"
        email = None
        
        for field in field_data:
            field_name = field.get("name", "")
            field_value = field.get("values", [""])[0]
            
            if "phone" in field_name.lower() or "tel" in field_name.lower():
                phone_number = field_value
            elif "name" in field_name.lower() or "full_name" in field_name.lower():
                name = field_value
            elif "email" in field_name.lower():
                email = field_value
        
        if not phone_number:
            logger.warning("⚠️ No phone number found in lead details")
            return None
        
        # Create or update patient
        query = """
            INSERT INTO patients (
                tenant_id, phone_number, first_name, last_name, email,
                acquisition_source, status, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, 'META_ADS', 'active', NOW(), NOW())
            ON CONFLICT (tenant_id, phone_number)
            DO UPDATE SET
                first_name = COALESCE(EXCLUDED.first_name, patients.first_name),
                last_name = COALESCE(EXCLUDED.last_name, patients.last_name),
                email = COALESCE(EXCLUDED.email, patients.email),
                acquisition_source = 'META_ADS',
                updated_at = NOW()
            RETURNING id
        """
        
        first_name = extract_first_name(name)
        last_name = extract_last_name(name)
        
        async with pool.acquire() as conn:
            patient_id = await conn.fetchval(
                query, tenant_id, phone_number, first_name, last_name, email
            )
            return patient_id
            
    except Exception as e:
        logger.error(f"❌ Error creating/updating patient from lead: {e}")
        return None


async def create_or_update_patient(
    phone_number: str,
    tenant_id: int,
    first_name: str = "Visitante",
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    meta_data: Optional[Dict[str, Any]] = None
) -> Optional[int]:
    """
    Creates or updates a patient with Meta Ads attribution.
    
    Args:
        phone_number: Patient phone number
        tenant_id: Tenant ID
        first_name: First name
        last_name: Last name (optional)
        email: Email (optional)
        meta_data: Meta Ads attribution data
    
    Returns:
        Optional[int]: Patient ID
    """
    try:
        pool = get_pool()
        
        query = """
            INSERT INTO patients (
                tenant_id, phone_number, first_name, last_name, email,
                acquisition_source, status, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, 'META_ADS', 'active', NOW(), NOW())
            ON CONFLICT (tenant_id, phone_number)
            DO UPDATE SET
                first_name = COALESCE(EXCLUDED.first_name, patients.first_name),
                last_name = COALESCE(EXCLUDED.last_name, patients.last_name),
                email = COALESCE(EXCLUDED.email, patients.email),
                acquisition_source = 'META_ADS',
                updated_at = NOW()
            RETURNING id
        """
        
        async with pool.acquire() as conn:
            patient_id = await conn.fetchval(
                query, tenant_id, phone_number, first_name, last_name, email
            )
            
            # Update attribution if meta_data provided
            if patient_id and meta_data:
                await update_patient_attribution_from_meta_webhook(
                    patient_id, tenant_id, meta_data
                )
            
            return patient_id
            
    except Exception as e:
        logger.error(f"❌ Error creating/updating patient: {e}")
        return None


def extract_first_name(full_name: str) -> str:
    """Extracts first name from full name."""
    if not full_name:
        return "Visitante"
    
    parts = full_name.strip().split()
    return parts[0] if parts else "Visitante"


def extract_last_name(full_name: str) -> Optional[str]:
    """Extracts last name from full name."""
    if not full_name:
        return None
    
    parts = full_name.strip().split()
    return " ".join(parts[1:]) if len(parts) > 1 else None


# ==================== ADMIN ENDPOINTS ====================

@router.get("/admin/config/deployment")
async def get_deployment_config(request: Request):
    """
    Returns deployment configuration including webhook URLs.
    
    Used by frontend to display webhook URLs for configuration.
    """
    try:
        # Get base URL from environment or request
        api_base = os.getenv("BASE_URL", "").rstrip("/")
        if not api_base:
            # Fallback to request base URL
            api_base = str(request.base_url).rstrip("/")
        
        config = {
            "orchestrator_url": api_base,
            "webhook_meta_url": f"{api_base}/webhooks/meta",
            "webhook_ycloud_url": f"{api_base}/admin/chatwoot/webhook",
            "meta_webhook_verify_token": META_WEBHOOK_VERIFY_TOKEN,
            "environment": os.getenv("ENVIRONMENT", "development"),
            "timestamp": datetime.now().isoformat()
        }
        
        return config
        
    except Exception as e:
        logger.error(f"❌ Error getting deployment config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/admin/marketing/attribution/stats")
async def get_attribution_stats(
    request: Request,
    range: str = "last_30d",
    tenant_id: Optional[int] = None
):
    """
    Returns Meta Ads attribution statistics.
    
    Args:
        range: Time range (last_7d, last_30d, all)
        tenant_id: Tenant ID (optional, will be resolved from token)
    """
    try:
        # Resolve tenant_id if not provided
        if tenant_id is None:
            tenant_id = await get_resolved_tenant_id(request)
        
        from db import get_patient_attribution_stats
        stats = await get_patient_attribution_stats(tenant_id, range)
        
        return {
            "success": True,
            "stats": stats,
            "time_range": range,
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting attribution stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))