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
    state: Optional[str] = Query(None),
    user_data=Depends(verify_admin_token)
):
    """
    Fase 1: Generar URL de OAuth para Meta Ads.
    """
    if user_data["role"] != 'ceo':
        raise HTTPException(status_code=403, detail="Solo el CEO puede conectar Meta Ads.")
        
    app_id = os.getenv("META_APP_ID")
    redirect_uri = os.getenv("META_REDIRECT_URI")
    
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
    
    if state:
        url += f"&state={state}"
        
    return {"url": url}

@router.get("/callback")
async def meta_auth_callback(
    code: str,
    state: Optional[str] = Query(None) # Usamos state para el tenant_id si se pasa desde el frontend
):
    """
    Fase 2 y 3: Canje de tokens (Short -> Long -> Permanent).
    """
    app_id = os.getenv("META_APP_ID")
    app_secret = os.getenv("META_APP_SECRET")
    redirect_uri = os.getenv("META_REDIRECT_URI")
    
    # Extraer tenant_id del state (formato: "tenant_X")
    tenant_id = None
    if state and state.startswith("tenant_"):
        try:
            tenant_id = int(state.replace("tenant_", ""))
        except:
            pass

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
            return RedirectResponse(url="https://dentalforge-frontend.gvdlcu.easypanel.host/marketing?error=auth_failed")
            
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
        
        if long_token_res.status_code != 200:
            logger.error(f"Error exchange long token: {long_token_res.text}")
            return RedirectResponse(url="https://dentalforge-frontend.gvdlcu.easypanel.host/marketing?error=token_exchange_failed")

        long_token = long_token_res.json().get("access_token")
        
        # 3. Guardar el token de usuario (60 días) para este tenant
        if tenant_id:
            await save_tenant_credential(tenant_id, "META_USER_LONG_TOKEN", long_token, category="meta_ads")
            logger.info(f"✅ Meta LongToken saved for tenant {tenant_id}")
            
        # 4. Redirigir al frontend con éxito
    return RedirectResponse(url="https://dentalforge-frontend.gvdlcu.easypanel.host/marketing?success=connected")

@router.api_route("/deauth", methods=["GET", "POST"])
async def meta_deauth_callback():
    """
    Callback cuando un usuario revoca el acceso desde Facebook.
    Aceptamos GET y POST para evitar errores de validación de Meta.
    """
    logger.info("Meta Ads authorization revoked request received.")
    return {"status": "success", "message": "Authorization revocation endpoint reachable."}

@router.api_route("/data-deletion", methods=["GET", "POST"])
async def meta_data_deletion_callback():
    """
    Callback para cumplimiento de borrado de datos de Meta (GDPR/Compliance).
    Aceptamos GET y POST para satisfacer el validador de Meta.
    """
    import time
    confirmation_code = f"DEL_{int(time.time())}"
    logger.info(f"Meta Data Deletion request received. Code: {confirmation_code}")
    return {
        "url": "https://dentalforge-frontend.gvdlcu.easypanel.host/privacy",
        "confirmation_code": confirmation_code
    }
