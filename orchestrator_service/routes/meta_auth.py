from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
import httpx
import os
import logging
from typing import Optional
from core.auth import verify_admin_token
from core.credentials import get_tenant_credential, save_tenant_credential, META_APP_ID, META_APP_SECRET
import db

router = APIRouter(prefix="/admin/marketing/meta-auth", tags=["Meta Ads Auth"])
logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"

@router.get("/url")
async def get_meta_auth_url(
    user_data=Depends(verify_admin_token)
):
    """
    Fase 1: Generar URL de OAuth para Meta Ads.
    """
    if user_data.role != 'ceo':
        raise HTTPException(status_code=403, detail="Solo el CEO puede conectar Meta Ads.")
        
    app_id = os.getenv("META_APP_ID")
    redirect_uri = os.getenv("META_REDIRECT_URI") # Ej: https://tudominio.com/api/admin/marketing/meta-auth/callback
    
    if not app_id:
        raise HTTPException(status_code=500, detail="META_APP_ID no configurado en el servidor.")

    # Scopes necesarios para Ads, WhatsApp y Páginas
    scopes = [
        "ads_management", 
        "ads_read", 
        "business_management", 
        "pages_show_list", 
        "pages_read_engagement", 
        "whatsapp_business_management"
    ]
    
    url = (
        f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth?"
        f"client_id={app_id}&"
        f"redirect_uri={redirect_uri}&"
        f"scope={','.join(scopes)}&"
        f"response_type=code"
    )
    return {"url": url}

@router.get("/callback")
async def meta_auth_callback(
    code: str,
    tenant_id: Optional[int] = Query(None) # El tenant se puede pasar en el state si es necesario
):
    """
    Fase 2 y 3: Canje de tokens (Short -> Long -> Permanent).
    """
    app_id = os.getenv("META_APP_ID")
    app_secret = os.getenv("META_APP_SECRET")
    redirect_uri = os.getenv("META_REDIRECT_URI")

    async with httpx.AsyncClient() as client:
        # 1. Obtener Short-Lived User Token (Intercambio de Code)
        token_res = await client.get(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token",
            params={
                "client_id": app_id,
                "client_secret": app_secret,
                "redirect_uri": redirect_uri,
                "code": code
            }
        )
        if token_res.status_code != 200:
            logger.error(f"Error exchange code: {token_res.text}")
            return RedirectResponse(url="/marketing?error=auth_failed")
            
        short_token = token_res.json().get("access_token")

        # 2. Canjear por Long-Lived User Token (60 días)
        long_token_res = await client.get(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": short_token
            }
        )
        long_token = long_token_res.json().get("access_token")
        
        # 3. Guardar el token de usuario (60 días) para este tenant
        if tenant_id:
            await save_tenant_credential(tenant_id, "META_USER_LONG_TOKEN", long_token, category="meta_ads")
            
        # 4. Obtener tokens permanentes de páginas/whatsapp si aplica
        # (Lógica extendida en servicios/meta_ads_service.py)
        
    return RedirectResponse(url="/marketing?success=connected")

@router.post("/deauth")
async def meta_deauth_callback():
    """
    Callback cuando un usuario revoca el acceso desde Facebook.
    Meta enviará un POST aquí.
    """
    logger.info("Meta Ads authorization revoked by user.")
    return {"status": "success", "message": "Authorization revocation received."}

@router.post("/data-deletion")
async def meta_data_deletion_callback():
    """
    Callback para cumplimiento de borrado de datos de Meta (GDPR/Compliance).
    """
    import time
    confirmation_code = f"DEL_{int(time.time())}"
    logger.info(f"Meta Data Deletion request received. Code: {confirmation_code}")
    return {
        "url": "https://dentalforge-frontend.gvdlcu.easypanel.host/marketing",
        "confirmation_code": confirmation_code
    }
