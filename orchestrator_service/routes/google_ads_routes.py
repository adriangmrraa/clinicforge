"""
Google Ads API Routes for ClinicForge
Adapted from CRM Ventas implementation
"""
from fastapi import APIRouter, Depends, HTTPException, Query
import logging
from typing import Optional

from core.auth import get_ceo_user_and_tenant
from services.marketing.google_ads_service import GoogleAdsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/marketing/google", tags=["Google Ads"])

@router.get("/campaigns")
async def get_google_campaigns(
    time_range: str = Query("last_30d", description="Time range for metrics"),
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get Google Ads campaigns with metrics
    """
    user, tenant_id = auth_data
    
    try:
        campaigns = await GoogleAdsService.get_campaigns(tenant_id, time_range)
        
        return {
            "success": True,
            "campaigns": campaigns,
            "count": len(campaigns),
            "time_range": time_range,
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        logger.error(f"Failed to get Google campaigns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics")
async def get_google_metrics(
    time_range: str = Query("last_30d", description="Time range for metrics"),
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get aggregated Google Ads metrics
    """
    user, tenant_id = auth_data
    
    try:
        metrics = await GoogleAdsService.get_metrics(tenant_id, time_range)
        
        return {
            "success": True,
            "metrics": metrics,
            "time_range": time_range,
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        logger.error(f"Failed to get Google metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/customers")
async def get_google_customers(
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get accessible Google Ads customer accounts
    """
    user, tenant_id = auth_data
    
    try:
        customers = await GoogleAdsService.get_customers(tenant_id)
        
        return {
            "success": True,
            "customers": customers,
            "count": len(customers),
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        logger.error(f"Failed to get Google customers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync")
async def sync_google_data(
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Trigger manual sync of Google Ads data
    """
    user, tenant_id = auth_data
    
    try:
        sync_result = await GoogleAdsService.sync_data(tenant_id)
        
        return {
            "success": True,
            "sync_result": sync_result,
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        logger.error(f"Failed to sync Google data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_google_stats(
    time_range: str = Query("last_30d", description="Time range for stats"),
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get comprehensive Google Ads stats (campaigns + metrics)
    """
    user, tenant_id = auth_data
    
    try:
        campaigns = await GoogleAdsService.get_campaigns(tenant_id, time_range)
        metrics = await GoogleAdsService.get_metrics(tenant_id, time_range)
        
        return {
            "success": True,
            "campaigns": campaigns,
            "metrics": metrics,
            "count": len(campaigns),
            "time_range": time_range,
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        logger.error(f"Failed to get Google stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/connection-status")
async def get_google_connection_status(
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get Google Ads connection status
    """
    user, tenant_id = auth_data
    
    try:
        # Test connection
        test_result = await GoogleAdsService.test_connection(tenant_id)
        
        return {
            "success": True,
            "connection_status": test_result,
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        logger.error(f"Failed to get Google connection status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/combined-stats")
async def get_combined_stats(
    time_range: str = Query("last_30d", description="Time range for stats"),
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get combined stats for dashboard (Google + Meta)
    """
    user, tenant_id = auth_data
    
    try:
        combined_stats = await GoogleAdsService.get_combined_stats(tenant_id, time_range)
        
        return {
            "success": True,
            "stats": combined_stats,
            "time_range": time_range,
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        logger.error(f"Failed to get combined stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/config")
async def debug_google_config(
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Debug endpoint to check Google configuration
    """
    user, tenant_id = auth_data
    
    try:
        import os
        from core.credentials import get_tenant_credential
        
        config = {
            "tenant_id": tenant_id,
            "google_client_id": bool(await get_tenant_credential(tenant_id, "GOOGLE_CLIENT_ID")),
            "google_client_secret": bool(await get_tenant_credential(tenant_id, "GOOGLE_CLIENT_SECRET")),
            "google_developer_token": bool(await get_tenant_credential(tenant_id, "GOOGLE_DEVELOPER_TOKEN")),
            "google_redirect_uri": await get_tenant_credential(tenant_id, "GOOGLE_REDIRECT_URI"),
            "google_login_redirect_uri": await get_tenant_credential(tenant_id, "GOOGLE_LOGIN_REDIRECT_URI"),
            "env_google_client_id": bool(os.getenv("GOOGLE_CLIENT_ID")),
            "env_google_client_secret": bool(os.getenv("GOOGLE_CLIENT_SECRET")),
            "env_google_developer_token": bool(os.getenv("GOOGLE_DEVELOPER_TOKEN")),
            "env_google_redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
            "env_google_login_redirect_uri": os.getenv("GOOGLE_LOGIN_REDIRECT_URI"),
            "frontend_url": os.getenv("FRONTEND_URL"),
            "platform_url": os.getenv("PLATFORM_URL")
        }
        
        return {
            "success": True,
            "config": config,
            "timestamp": "2024-03-03T10:00:00Z"
        }
        
    except Exception as e:
        logger.error(f"Google config debug failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))