"""
Google OAuth Service for ClinicForge
Adapted from CRM Ventas implementation
"""
import os
import json
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import httpx
from urllib.parse import urlencode, quote_plus

from db import get_pool
from core.credentials import get_tenant_credential, save_tenant_credential

logger = logging.getLogger(__name__)

class GoogleOAuthService:
    """Service for Google OAuth 2.0 authentication"""
    
    @staticmethod
    async def get_authorization_url(tenant_id: int, platform: str = "ads") -> str:
        """
        Generate Google OAuth 2.0 authorization URL
        
        Args:
            tenant_id: Tenant ID
            platform: 'ads' for Google Ads, 'login' for Google Login
            
        Returns:
            Authorization URL
        """
        client_id = await get_tenant_credential(tenant_id, "GOOGLE_CLIENT_ID")
        if not client_id:
            raise ValueError("GOOGLE_CLIENT_ID not configured for this tenant")
        
        # Get redirect URI based on platform
        if platform == "ads":
            redirect_uri = await get_tenant_credential(tenant_id, "GOOGLE_REDIRECT_URI")
            if not redirect_uri:
                # Fallback to environment variable
                redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        else:  # login
            redirect_uri = await get_tenant_credential(tenant_id, "GOOGLE_LOGIN_REDIRECT_URI")
            if not redirect_uri:
                # Fallback to environment variable
                redirect_uri = os.getenv("GOOGLE_LOGIN_REDIRECT_URI")
        
        if not redirect_uri:
            raise ValueError(f"GOOGLE_{platform.upper()}_REDIRECT_URI not configured")
        
        # Scopes based on platform
        if platform == "ads":
            scopes = [
                "https://www.googleapis.com/auth/adwords",
                "https://www.googleapis.com/auth/userinfo.email",
                "openid"
            ]
        else:  # login
            scopes = [
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
                "openid"
            ]
        
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",  # Get refresh token
            "prompt": "consent",  # Always prompt for consent to get refresh token
            "state": f"tenant_{tenant_id}_{platform}"  # Include tenant and platform in state
        }
        
        url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        logger.info(f"Generated Google OAuth URL for tenant {tenant_id}, platform {platform}")
        return url
    
    @staticmethod
    async def exchange_code_for_tokens(
        tenant_id: int, 
        code: str, 
        platform: str = "ads"
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens
        
        Args:
            tenant_id: Tenant ID
            code: Authorization code from Google
            platform: 'ads' or 'login'
            
        Returns:
            Token information
        """
        client_id = await get_tenant_credential(tenant_id, "GOOGLE_CLIENT_ID")
        client_secret = await get_tenant_credential(tenant_id, "GOOGLE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            raise ValueError("Google OAuth credentials not configured for this tenant")
        
        # Get redirect URI based on platform
        if platform == "ads":
            redirect_uri = await get_tenant_credential(tenant_id, "GOOGLE_REDIRECT_URI")
            if not redirect_uri:
                redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        else:  # login
            redirect_uri = await get_tenant_credential(tenant_id, "GOOGLE_LOGIN_REDIRECT_URI")
            if not redirect_uri:
                redirect_uri = os.getenv("GOOGLE_LOGIN_REDIRECT_URI")
        
        if not redirect_uri:
            raise ValueError(f"GOOGLE_{platform.upper()}_REDIRECT_URI not configured")
        
        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=data)
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Google token exchange failed: {error_detail}")
                raise ValueError(f"Google OAuth token exchange failed: {error_detail}")
            
            token_data = response.json()
        
        # Get user info to get email
        user_info = await GoogleOAuthService._get_user_info(token_data["access_token"])
        
        # Calculate expiration time
        expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
        
        # Save tokens to database
        await GoogleOAuthService._save_tokens(
            tenant_id=tenant_id,
            platform=platform,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=expires_at,
            scopes=token_data.get("scope", "").split(" "),
            email=user_info.get("email")
        )
        
        logger.info(f"Google OAuth tokens saved for tenant {tenant_id}, platform {platform}, email: {user_info.get('email')}")
        
        return {
            "success": True,
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
            "token_type": token_data.get("token_type"),
            "scope": token_data.get("scope"),
            "email": user_info.get("email"),
            "platform": platform
        }
    
    @staticmethod
    async def _get_user_info(access_token: str) -> Dict[str, Any]:
        """Get user info from Google using access token"""
        userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(userinfo_url, headers=headers)
            
            if response.status_code != 200:
                logger.warning(f"Failed to get user info: {response.text}")
                return {}
            
            return response.json()
    
    @staticmethod
    async def _save_tokens(
        tenant_id: int,
        platform: str,
        access_token: str,
        refresh_token: Optional[str],
        expires_at: datetime,
        scopes: list,
        email: Optional[str] = None
    ) -> bool:
        """Save OAuth tokens to database"""
        pool = get_pool()
        
        try:
            await pool.execute("""
                INSERT INTO google_oauth_tokens 
                (tenant_id, platform, access_token, refresh_token, expires_at, scopes, email, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                ON CONFLICT (tenant_id, platform) 
                DO UPDATE SET 
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    expires_at = EXCLUDED.expires_at,
                    scopes = EXCLUDED.scopes,
                    email = EXCLUDED.email,
                    updated_at = NOW()
            """, tenant_id, platform, access_token, refresh_token, expires_at, scopes, email)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save Google tokens for tenant {tenant_id}: {e}")
            return False
    
    @staticmethod
    async def get_tokens(tenant_id: int, platform: str = "ads") -> Optional[Dict[str, Any]]:
        """Get OAuth tokens from database"""
        pool = get_pool()
        
        try:
            row = await pool.fetchrow("""
                SELECT access_token, refresh_token, expires_at, scopes, email
                FROM google_oauth_tokens
                WHERE tenant_id = $1 AND platform = $2
            """, tenant_id, platform)
            
            if not row:
                return None
            
            # Check if token is expired or about to expire (within 5 minutes)
            expires_at = row["expires_at"]
            if expires_at and expires_at < datetime.utcnow() + timedelta(minutes=5):
                # Token expired or about to expire, try to refresh
                if row["refresh_token"]:
                    logger.info(f"Google token expired for tenant {tenant_id}, attempting refresh...")
                    refreshed = await GoogleOAuthService.refresh_tokens(tenant_id, platform)
                    if refreshed:
                        # Get the refreshed tokens
                        row = await pool.fetchrow("""
                            SELECT access_token, refresh_token, expires_at, scopes, email
                            FROM google_oauth_tokens
                            WHERE tenant_id = $1 AND platform = $2
                        """, tenant_id, platform)
                    else:
                        logger.warning(f"Failed to refresh Google token for tenant {tenant_id}")
                        return None
            
            return {
                "access_token": row["access_token"],
                "refresh_token": row["refresh_token"],
                "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
                "scopes": row["scopes"],
                "email": row["email"],
                "is_valid": True
            }
            
        except Exception as e:
            logger.error(f"Failed to get Google tokens for tenant {tenant_id}: {e}")
            return None
    
    @staticmethod
    async def refresh_tokens(tenant_id: int, platform: str = "ads") -> bool:
        """Refresh expired access token using refresh token"""
        pool = get_pool()
        
        try:
            # Get current tokens
            row = await pool.fetchrow("""
                SELECT refresh_token
                FROM google_oauth_tokens
                WHERE tenant_id = $1 AND platform = $2
            """, tenant_id, platform)
            
            if not row or not row["refresh_token"]:
                logger.error(f"No refresh token available for tenant {tenant_id}")
                return False
            
            refresh_token = row["refresh_token"]
            client_id = await get_tenant_credential(tenant_id, "GOOGLE_CLIENT_ID")
            client_secret = await get_tenant_credential(tenant_id, "GOOGLE_CLIENT_SECRET")
            
            if not client_id or not client_secret:
                logger.error(f"Google OAuth credentials not configured for tenant {tenant_id}")
                return False
            
            # Refresh token
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data)
                
                if response.status_code != 200:
                    logger.error(f"Google token refresh failed: {response.text}")
                    return False
                
                token_data = response.json()
            
            # Calculate new expiration time
            expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
            
            # Update tokens in database
            await pool.execute("""
                UPDATE google_oauth_tokens
                SET access_token = $1,
                    expires_at = $2,
                    updated_at = NOW()
                WHERE tenant_id = $3 AND platform = $4
            """, token_data["access_token"], expires_at, tenant_id, platform)
            
            logger.info(f"Google tokens refreshed for tenant {tenant_id}, platform {platform}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh Google tokens for tenant {tenant_id}: {e}")
            return False
    
    @staticmethod
    async def disconnect(tenant_id: int, platform: str = "ads") -> bool:
        """Disconnect Google OAuth (remove tokens)"""
        pool = get_pool()
        
        try:
            await pool.execute("""
                DELETE FROM google_oauth_tokens
                WHERE tenant_id = $1 AND platform = $2
            """, tenant_id, platform)
            
            logger.info(f"Google OAuth disconnected for tenant {tenant_id}, platform {platform}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disconnect Google OAuth for tenant {tenant_id}: {e}")
            return False
    
    @staticmethod
    async def get_connection_status(tenant_id: int, platform: str = "ads") -> Dict[str, Any]:
        """Get Google OAuth connection status"""
        tokens = await GoogleOAuthService.get_tokens(tenant_id, platform)
        
        if not tokens:
            return {
                "connected": False,
                "platform": platform,
                "message": "Not connected to Google"
            }
        
        # Check if token is still valid
        expires_at = datetime.fromisoformat(tokens["expires_at"].replace("Z", "+00:00")) if tokens["expires_at"] else None
        is_valid = expires_at and expires_at > datetime.utcnow()
        
        return {
            "connected": True,
            "platform": platform,
            "email": tokens["email"],
            "expires_at": tokens["expires_at"],
            "is_valid": is_valid,
            "scopes": tokens["scopes"]
        }