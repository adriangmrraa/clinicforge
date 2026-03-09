"""
Google OAuth Routes for ClinicForge
Adapted from CRM Ventas implementation
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
import logging
from typing import Optional

from core.auth import get_ceo_user_and_tenant
from services.auth.google_oauth_service import GoogleOAuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/auth/google", tags=["Google OAuth"])

@router.get("/ads/url")
async def get_google_ads_auth_url(
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get Google OAuth authorization URL for Google Ads
    """
    user, tenant_id = auth_data
    
    try:
        auth_url = await GoogleOAuthService.get_authorization_url(tenant_id, platform="ads")
        
        return {
            "success": True,
            "url": auth_url,
            "tenant_id": tenant_id,
            "platform": "ads"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate Google OAuth URL: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/ads/callback")
async def google_ads_callback(
    request: Request,
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None)
):
    """
    Google OAuth callback handler for Google Ads
    """
    if error:
        logger.error(f"Google OAuth error: {error}")
        # Redirect to frontend with error
        frontend_url = request.app.state.config.get("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(f"{frontend_url}/marketing?error=google_auth_failed&error_detail={error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")
    
    try:
        # Parse tenant_id from state (format: tenant_{tenant_id}_ads)
        if not state.startswith("tenant_"):
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        parts = state.split("_")
        if len(parts) < 3:
            raise HTTPException(status_code=400, detail="Invalid state format")
        
        tenant_id = int(parts[1])
        platform = parts[2] if len(parts) > 2 else "ads"
        
        # Exchange code for tokens
        token_result = await GoogleOAuthService.exchange_code_for_tokens(
            tenant_id=tenant_id,
            code=code,
            platform=platform
        )
        
        logger.info(f"Google OAuth successful for tenant {tenant_id}, platform {platform}")
        
        # Redirect to frontend with success
        frontend_url = request.app.state.config.get("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(f"{frontend_url}/marketing?success=google_connected&platform={platform}")
        
    except ValueError as e:
        logger.error(f"Google OAuth token exchange failed: {e}")
        frontend_url = request.app.state.config.get("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(f"{frontend_url}/marketing?error=google_token_exchange_failed")
    
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        frontend_url = request.app.state.config.get("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(f"{frontend_url}/marketing?error=google_auth_error")

@router.get("/login/url")
async def get_google_login_auth_url(
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get Google OAuth authorization URL for Google Login
    """
    user, tenant_id = auth_data
    
    try:
        auth_url = await GoogleOAuthService.get_authorization_url(tenant_id, platform="login")
        
        return {
            "success": True,
            "url": auth_url,
            "tenant_id": tenant_id,
            "platform": "login"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate Google Login OAuth URL: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/login/callback")
async def google_login_callback(
    request: Request,
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None)
):
    """
    Google OAuth callback handler for Google Login
    """
    if error:
        logger.error(f"Google Login OAuth error: {error}")
        # Redirect to login page with error
        frontend_url = request.app.state.config.get("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(f"{frontend_url}/login?error=google_auth_failed")
    
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")
    
    try:
        # Parse tenant_id from state (format: tenant_{tenant_id}_login)
        if not state.startswith("tenant_"):
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        parts = state.split("_")
        if len(parts) < 3:
            raise HTTPException(status_code=400, detail="Invalid state format")
        
        tenant_id = int(parts[1])
        platform = parts[2] if len(parts) > 2 else "login"
        
        # Exchange code for tokens
        token_result = await GoogleOAuthService.exchange_code_for_tokens(
            tenant_id=tenant_id,
            code=code,
            platform=platform
        )
        
        logger.info(f"Google Login successful for tenant {tenant_id}, email: {token_result.get('email')}")
        
        # TODO: Create or update user account based on Google profile
        # For now, just redirect to dashboard
        
        frontend_url = request.app.state.config.get("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(f"{frontend_url}/dashboard?google_login_success=true")
        
    except ValueError as e:
        logger.error(f"Google Login token exchange failed: {e}")
        frontend_url = request.app.state.config.get("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(f"{frontend_url}/login?error=google_token_exchange_failed")
    
    except Exception as e:
        logger.error(f"Google Login callback error: {e}")
        frontend_url = request.app.state.config.get("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(f"{frontend_url}/login?error=google_auth_error")

@router.post("/ads/disconnect")
async def disconnect_google_ads(
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Disconnect Google Ads OAuth
    """
    user, tenant_id = auth_data
    
    try:
        success = await GoogleOAuthService.disconnect(tenant_id, platform="ads")
        
        if success:
            return {
                "success": True,
                "message": "Google Ads disconnected successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to disconnect Google Ads")
        
    except Exception as e:
        logger.error(f"Failed to disconnect Google Ads: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/ads/refresh")
async def refresh_google_ads_token(
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Manually refresh Google Ads access token
    """
    user, tenant_id = auth_data
    
    try:
        success = await GoogleOAuthService.refresh_tokens(tenant_id, platform="ads")
        
        if success:
            return {
                "success": True,
                "message": "Google Ads token refreshed successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to refresh token")
        
    except Exception as e:
        logger.error(f"Failed to refresh Google Ads token: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/ads/test-connection")
async def test_google_ads_connection(
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Test Google Ads API connection
    """
    user, tenant_id = auth_data
    
    try:
        # Get connection status
        status = await GoogleOAuthService.get_connection_status(tenant_id, "ads")
        
        return {
            "success": True,
            "status": status,
            "tenant_id": tenant_id,
            "timestamp": "2024-03-03T10:00:00Z"  # Placeholder
        }
        
    except Exception as e:
        logger.error(f"Google Ads connection test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ads/debug/token")
async def debug_google_token(
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Debug endpoint to check Google OAuth token status
    """
    user, tenant_id = auth_data
    
    try:
        tokens = await GoogleOAuthService.get_tokens(tenant_id, "ads")
        
        if not tokens:
            return {
                "connected": False,
                "message": "No Google OAuth tokens found"
            }
        
        # Mask sensitive data
        safe_tokens = {
            "has_access_token": bool(tokens.get("access_token")),
            "has_refresh_token": bool(tokens.get("refresh_token")),
            "expires_at": tokens.get("expires_at"),
            "email": tokens.get("email"),
            "scopes": tokens.get("scopes"),
            "is_valid": tokens.get("is_valid", False)
        }
        
        return {
            "connected": True,
            "tokens": safe_tokens,
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        logger.error(f"Google token debug failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))