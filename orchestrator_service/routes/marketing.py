from fastapi import APIRouter, Depends, Header, HTTPException
from typing import Optional
from services.marketing_service import MarketingService
from core.auth import get_current_user_and_tenant

router = APIRouter(prefix="/admin/marketing", tags=["Marketing Analytics"])

@router.get("/stats/roi")
async def get_marketing_roi(
    auth_data: tuple = Depends(get_current_user_and_tenant)
):
    """
    Retorna métricas consolidadas de ROI Real.
    """
    user, tenant_id = auth_data
    if user["role"] != "ceo":
        raise HTTPException(status_code=403, detail="Only CEOs can access marketing ROI stats")
        
    stats = await MarketingService.get_roi_stats(tenant_id)
    return stats

@router.get("/stats")
async def get_marketing_stats(
    auth_data: tuple = Depends(get_current_user_and_tenant)
):
    """
    Retorna el listado de campañas y sus métricas de conversión.
    """
    user, tenant_id = auth_data
    if user["role"] != "ceo":
        raise HTTPException(status_code=403, detail="Only CEOs can access marketing stats")
        
    campaigns = await MarketingService.get_campaign_stats(tenant_id)
    return {"campaigns": campaigns}
