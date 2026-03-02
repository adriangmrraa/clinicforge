"""
Metrics API for ClinicForge
Unified metrics endpoints for Meta Ads attribution (WhatsApp referrals + Leads Forms)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth import get_ceo_infra_only as get_ceo_user_and_tenant
from services.metrics_service import MetricsService, AttributionType, MetricPeriod

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/metrics", tags=["Metrics"])


@router.get("/campaigns")
async def get_campaign_metrics(
    period: Optional[str] = Query("monthly", description="Time period: daily, weekly, monthly, quarterly, yearly"),
    attribution_type: Optional[str] = Query("first_touch", description="Attribution type: first_touch, last_touch"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get unified campaign metrics combining WhatsApp referrals and Leads Forms.
    
    Returns metrics for Meta Ads campaigns with attribution from both sources.
    """
    user, tenant_id = auth_data
    
    try:
        # Parse period
        try:
            period_enum = MetricPeriod(period.lower())
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid period. Must be one of: {', '.join([p.value for p in MetricPeriod])}"
            )
        
        # Parse attribution type
        try:
            attribution_enum = AttributionType(attribution_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid attribution type. Must be one of: {', '.join([a.value for a in AttributionType])}"
            )
        
        metrics = await MetricsService.get_campaign_metrics(
            tenant_id=tenant_id,
            period=period_enum,
            date_from=date_from,
            date_to=date_to,
            attribution_type=attribution_enum
        )
        
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign metrics: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving campaign metrics")


@router.get("/attribution/report")
async def get_attribution_report(
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get detailed attribution report showing patient journey.
    
    Shows first touch, last touch, and conversion attribution for each patient.
    """
    user, tenant_id = auth_data
    
    try:
        report = await MetricsService.get_detailed_attribution_report(
            tenant_id=tenant_id,
            campaign_id=campaign_id,
            date_from=date_from,
            date_to=date_to
        )
        
        return report
        
    except Exception as e:
        logger.error(f"Error getting attribution report: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving attribution report")


@router.get("/roi/dashboard")
async def get_roi_dashboard(
    period: Optional[str] = Query("monthly", description="Time period: daily, weekly, monthly, quarterly, yearly"),
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get ROI dashboard with key metrics.
    
    Includes first touch vs last touch comparison, trend data, and top campaigns.
    """
    user, tenant_id = auth_data
    
    try:
        # Parse period
        try:
            period_enum = MetricPeriod(period.lower())
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid period. Must be one of: {', '.join([p.value for p in MetricPeriod])}"
            )
        
        dashboard = await MetricsService.get_roi_dashboard(
            tenant_id=tenant_id,
            period=period_enum
        )
        
        return dashboard
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ROI dashboard: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving ROI dashboard")


@router.get("/attribution/mix")
async def get_attribution_mix(
    period: Optional[str] = Query("monthly", description="Time period: daily, weekly, monthly, quarterly, yearly"),
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get attribution mix (first touch vs last touch vs conversion vs organic).
    
    Shows how patients are attributed across different attribution models.
    """
    user, tenant_id = auth_data
    
    try:
        # Parse period
        try:
            period_enum = MetricPeriod(period.lower())
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid period. Must be one of: {', '.join([p.value for p in MetricPeriod])}"
            )
        
        attribution_mix = await MetricsService._get_attribution_mix(
            tenant_id=tenant_id,
            period=period_enum
        )
        
        return {
            "success": True,
            "period": period,
            "attribution_mix": attribution_mix
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting attribution mix: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving attribution mix")


@router.get("/trend")
async def get_trend_data(
    period: Optional[str] = Query("monthly", description="Time period: daily, weekly, monthly, quarterly, yearly"),
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get trend data over time.
    
    Shows patient and lead trends over the selected period.
    """
    user, tenant_id = auth_data
    
    try:
        # Parse period
        try:
            period_enum = MetricPeriod(period.lower())
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid period. Must be one of: {', '.join([p.value for p in MetricPeriod])}"
            )
        
        trend_data = await MetricsService._get_trend_data(
            tenant_id=tenant_id,
            period=period_enum
        )
        
        return {
            "success": True,
            "period": period,
            "trend_data": trend_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trend data: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving trend data")


@router.get("/top/campaigns")
async def get_top_campaigns(
    period: Optional[str] = Query("monthly", description="Time period: daily, weekly, monthly, quarterly, yearly"),
    limit: int = Query(10, ge=1, le=50, description="Number of top campaigns to return"),
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get top performing campaigns.
    
    Returns campaigns sorted by total patients generated.
    """
    user, tenant_id = auth_data
    
    try:
        # Parse period
        try:
            period_enum = MetricPeriod(period.lower())
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid period. Must be one of: {', '.join([p.value for p in MetricPeriod])}"
            )
        
        top_campaigns = await MetricsService._get_top_campaigns(
            tenant_id=tenant_id,
            period=period_enum
        )
        
        # Apply limit
        if limit < len(top_campaigns):
            top_campaigns = top_campaigns[:limit]
        
        return {
            "success": True,
            "period": period,
            "limit": limit,
            "top_campaigns": top_campaigns
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting top campaigns: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving top campaigns")


@router.get("/comparison/first-vs-last")
async def compare_first_vs_last_touch(
    period: Optional[str] = Query("monthly", description="Time period: daily, weekly, monthly, quarterly, yearly"),
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Compare first touch vs last touch attribution.
    
    Shows differences in metrics between attribution models.
    """
    user, tenant_id = auth_data
    
    try:
        # Parse period
        try:
            period_enum = MetricPeriod(period.lower())
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid period. Must be one of: {', '.join([p.value for p in MetricPeriod])}"
            )
        
        # Get metrics for both attribution types
        first_touch_metrics = await MetricsService.get_campaign_metrics(
            tenant_id=tenant_id,
            period=period_enum,
            attribution_type=AttributionType.FIRST_TOUCH
        )
        
        last_touch_metrics = await MetricsService.get_campaign_metrics(
            tenant_id=tenant_id,
            period=period_enum,
            attribution_type=AttributionType.LAST_TOUCH
        )
        
        comparison = {
            "first_touch": first_touch_metrics.get("summary", {}),
            "last_touch": last_touch_metrics.get("summary", {}),
            "difference": {
                "patients": last_touch_metrics.get("summary", {}).get("total_patients", 0) - 
                           first_touch_metrics.get("summary", {}).get("total_patients", 0),
                "conversion_rate": round(
                    last_touch_metrics.get("summary", {}).get("average_conversion_rate", 0) - 
                    first_touch_metrics.get("summary", {}).get("average_conversion_rate", 0), 2
                ),
                "roi": round(
                    last_touch_metrics.get("summary", {}).get("average_roi", 0) - 
                    first_touch_metrics.get("summary", {}).get("average_roi", 0), 2
                )
            }
        }
        
        return {
            "success": True,
            "period": period,
            "comparison": comparison
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing attribution models: {e}")
        raise HTTPException(status_code=500, detail="Error comparing attribution models")