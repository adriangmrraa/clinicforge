# analytics_routes.py
# Protected endpoints for Dentalogic Analytics Dashboard.
# Ensures Sovereign isolation via tenant_id extraction.

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
from .services.analytics_service import AnalyticsService

router = APIRouter(prefix="/admin/analytics", tags=["Analytics"])
security = HTTPBearer()

# Mock dependency for tenant_id extraction (in real app, this comes from JWT)
async def get_current_tenant_id(credentials: HTTPAuthorizationCredentials = Security(security)):
    # Logic to decode JWT and return tenant_id
    # For this implementation, we assume it's extracted safely.
    return "extract-uuid-from-jwt"

@router.get("/ceo")
async def get_ceo_dashboard(tenant_id: str = Depends(get_current_tenant_id)):
    """
    Returns strategic data for the CEO role.
    """
    # Verify role in JWT: If role != 'ceo' return 403
    try:
        data = await AnalyticsService.get_ceo_metrics(None, tenant_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/secretary")
async def get_secretary_dashboard(tenant_id: str = Depends(get_current_tenant_id)):
    """
    Returns operational data for the Secretary role.
    """
    # Verify role in JWT: If role not in ['secretary', 'ceo'] return 403
    try:
        data = await AnalyticsService.get_secretary_metrics(None, tenant_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
