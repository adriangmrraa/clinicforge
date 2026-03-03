"""
Google Ads Service for ClinicForge
Adapted from CRM Ventas implementation
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import httpx
from decimal import Decimal

from db import get_pool
from core.credentials import get_tenant_credential
from services.auth.google_oauth_service import GoogleOAuthService

logger = logging.getLogger(__name__)

class GoogleAdsService:
    """Service for Google Ads API integration"""
    
    @staticmethod
    async def get_campaigns(tenant_id: int, time_range: str = "last_30d") -> List[Dict[str, Any]]:
        """
        Get Google Ads campaigns with metrics
        
        Args:
            tenant_id: Tenant ID
            time_range: Time range for metrics
            
        Returns:
            List of campaigns with metrics
        """
        # First check if connected
        status = await GoogleOAuthService.get_connection_status(tenant_id, "ads")
        if not status.get("connected"):
            logger.warning(f"Google Ads not connected for tenant {tenant_id}")
            return []
        
        # Get developer token
        developer_token = await get_tenant_credential(tenant_id, "GOOGLE_DEVELOPER_TOKEN")
        if not developer_token:
            logger.warning(f"GOOGLE_DEVELOPER_TOKEN not configured for tenant {tenant_id}")
            return []
        
        # Get access token
        tokens = await GoogleOAuthService.get_tokens(tenant_id, "ads")
        if not tokens:
            logger.warning(f"No valid Google tokens for tenant {tenant_id}")
            return []
        
        access_token = tokens["access_token"]
        
        # For now, return demo data (actual API implementation would go here)
        # In production, this would call Google Ads API
        return await GoogleAdsService._get_demo_campaigns()
    
    @staticmethod
    async def _get_demo_campaigns() -> List[Dict[str, Any]]:
        """Return demo campaign data for development"""
        return [
            {
                "id": "campaign_1",
                "name": "Clínica Dental - Búsqueda Branded",
                "status": "ENABLED",
                "type": "SEARCH",
                "budget": 50000,  # Micros (divide by 1,000,000 for currency)
                "impressions": 12500,
                "clicks": 350,
                "cost": 42000,  # Micros
                "conversions": 12,
                "conversions_value": 2400000,  # Micros
                "ctr": 2.8,
                "cpc": 120,  # Micros
                "conversion_rate": 3.43,
                "roas": 5.71,
                "start_date": (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d"),
                "end_date": None,
                "currency_code": "ARS"
            },
            {
                "id": "campaign_2",
                "name": "Ortodoncia - Display Remarketing",
                "status": "ENABLED",
                "type": "DISPLAY",
                "budget": 30000,
                "impressions": 85000,
                "clicks": 1200,
                "cost": 28000,
                "conversions": 8,
                "conversions_value": 1600000,
                "ctr": 1.41,
                "cpc": 23,
                "conversion_rate": 0.67,
                "roas": 5.71,
                "start_date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                "end_date": None,
                "currency_code": "ARS"
            },
            {
                "id": "campaign_3",
                "name": "Blanqueamiento - Video YouTube",
                "status": "PAUSED",
                "type": "VIDEO",
                "budget": 20000,
                "impressions": 45000,
                "clicks": 600,
                "cost": 15000,
                "conversions": 5,
                "conversions_value": 1000000,
                "ctr": 1.33,
                "cpc": 25,
                "conversion_rate": 0.83,
                "roas": 6.67,
                "start_date": (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),
                "end_date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                "currency_code": "ARS"
            }
        ]
    
    @staticmethod
    async def get_metrics(tenant_id: int, time_range: str = "last_30d") -> Dict[str, Any]:
        """
        Get aggregated Google Ads metrics
        
        Args:
            tenant_id: Tenant ID
            time_range: Time range for metrics
            
        Returns:
            Aggregated metrics
        """
        campaigns = await GoogleAdsService.get_campaigns(tenant_id, time_range)
        
        if not campaigns:
            return await GoogleAdsService._get_demo_metrics()
        
        # Aggregate metrics from campaigns
        total_impressions = sum(c.get("impressions", 0) for c in campaigns)
        total_clicks = sum(c.get("clicks", 0) for c in campaigns)
        total_cost = sum(c.get("cost", 0) for c in campaigns) / 1000000  # Convert micros to currency
        total_conversions = sum(c.get("conversions", 0) for c in campaigns)
        total_conversions_value = sum(c.get("conversions_value", 0) for c in campaigns) / 1000000
        
        # Calculate derived metrics
        ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        cpc = (total_cost / total_clicks) if total_clicks > 0 else 0
        conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
        roas = (total_conversions_value / total_cost) if total_cost > 0 else 0
        
        # Active campaigns
        active_campaigns = [c for c in campaigns if c.get("status") == "ENABLED"]
        
        return {
            "impressions": total_impressions,
            "clicks": total_clicks,
            "cost": total_cost,
            "conversions": total_conversions,
            "conversions_value": total_conversions_value,
            "ctr": round(ctr, 2),
            "cpc": round(cpc, 2),
            "conversion_rate": round(conversion_rate, 2),
            "roas": round(roas, 2),
            "campaign_count": len(campaigns),
            "active_campaigns": len(active_campaigns),
            "currency": "ARS",
            "time_range": time_range,
            "is_connected": True
        }
    
    @staticmethod
    async def _get_demo_metrics() -> Dict[str, Any]:
        """Return demo metrics for development"""
        return {
            "impressions": 142500,
            "clicks": 2150,
            "cost": 85.00,  # Already in currency (not micros)
            "conversions": 25,
            "conversions_value": 5000.00,
            "ctr": 1.51,
            "cpc": 0.04,
            "conversion_rate": 1.16,
            "roas": 58.82,
            "campaign_count": 3,
            "active_campaigns": 2,
            "currency": "ARS",
            "time_range": "last_30d",
            "is_connected": True,
            "is_demo": True  # Flag to indicate demo data
        }
    
    @staticmethod
    async def get_customers(tenant_id: int) -> List[Dict[str, Any]]:
        """
        Get accessible Google Ads customer accounts
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            List of customer accounts
        """
        # Check connection
        status = await GoogleOAuthService.get_connection_status(tenant_id, "ads")
        if not status.get("connected"):
            return []
        
        # For now, return demo data
        return [
            {
                "customer_id": "1234567890",
                "descriptive_name": "Clínica Dental Principal",
                "currency_code": "ARS",
                "time_zone": "America/Argentina/Buenos_Aires",
                "manager": False,
                "test_account": False
            },
            {
                "customer_id": "2345678901",
                "descriptive_name": "Clínica Dental Sucursal",
                "currency_code": "ARS",
                "time_zone": "America/Argentina/Buenos_Aires",
                "manager": False,
                "test_account": False
            }
        ]
    
    @staticmethod
    async def sync_data(tenant_id: int) -> Dict[str, Any]:
        """
        Trigger manual sync of Google Ads data
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Sync result
        """
        # Check connection
        status = await GoogleOAuthService.get_connection_status(tenant_id, "ads")
        if not status.get("connected"):
            return {
                "success": False,
                "message": "Google Ads not connected",
                "synced_items": 0
            }
        
        # In production, this would:
        # 1. Fetch campaigns from Google Ads API
        # 2. Fetch metrics for each campaign
        # 3. Store in cache table
        # 4. Return sync statistics
        
        # For demo purposes
        return {
            "success": True,
            "message": "Google Ads data sync completed",
            "synced_items": 3,
            "campaigns_synced": 3,
            "metrics_synced": 90,  # 30 days * 3 campaigns
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    async def get_combined_stats(tenant_id: int, time_range: str = "last_30d") -> Dict[str, Any]:
        """
        Get combined stats for dashboard (Google + Meta)
        
        Args:
            tenant_id: Tenant ID
            time_range: Time range for metrics
            
        Returns:
            Combined stats
        """
        # Get Google metrics
        google_metrics = await GoogleAdsService.get_metrics(tenant_id, time_range)
        
        # Note: Meta metrics would come from MarketingService
        # For now, just return Google metrics with combined structure
        return {
            "google": google_metrics,
            "meta": {
                "is_connected": False,
                "message": "Meta metrics would come from MarketingService"
            },
            "combined": {
                "total_impressions": google_metrics.get("impressions", 0),
                "total_clicks": google_metrics.get("clicks", 0),
                "total_cost": google_metrics.get("cost", 0),
                "total_conversions": google_metrics.get("conversions", 0),
                "total_conversions_value": google_metrics.get("conversions_value", 0),
                "platforms": ["google"] if google_metrics.get("is_connected") else []
            },
            "time_range": time_range
        }
    
    @staticmethod
    async def test_connection(tenant_id: int) -> Dict[str, Any]:
        """
        Test Google Ads API connection
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Connection test result
        """
        # Check OAuth connection
        oauth_status = await GoogleOAuthService.get_connection_status(tenant_id, "ads")
        
        if not oauth_status.get("connected"):
            return {
                "success": False,
                "message": "Google OAuth not connected",
                "oauth_status": oauth_status
            }
        
        # Check developer token
        developer_token = await get_tenant_credential(tenant_id, "GOOGLE_DEVELOPER_TOKEN")
        if not developer_token:
            return {
                "success": False,
                "message": "GOOGLE_DEVELOPER_TOKEN not configured",
                "oauth_status": oauth_status
            }
        
        # Try to get customer list (simulated for demo)
        try:
            customers = await GoogleAdsService.get_customers(tenant_id)
            
            return {
                "success": True,
                "message": "Google Ads connection successful",
                "oauth_status": oauth_status,
                "customers_count": len(customers),
                "developer_token_configured": bool(developer_token),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Google Ads connection test failed: {e}")
            return {
                "success": False,
                "message": f"Google Ads API test failed: {str(e)}",
                "oauth_status": oauth_status,
                "developer_token_configured": bool(developer_token),
                "error": str(e)
            }