from fastapi import APIRouter, Depends, Header, HTTPException
from typing import Optional
from services.marketing_service import MarketingService
from services.meta_ads_service import MetaAdsClient
from core.auth import get_current_user_and_tenant
from core.credentials import get_tenant_credential, save_tenant_credential
from db import db

router = APIRouter(prefix="/admin/marketing", tags=["Marketing Analytics"])

@router.get("/stats/roi")
async def get_marketing_roi(
    range: str = "last_30d",
    auth_data: tuple = Depends(get_current_user_and_tenant)
):
    """
    Retorna métricas consolidadas de ROI Real.
    """
    user, tenant_id = auth_data
    if user["role"] != "ceo":
        raise HTTPException(status_code=403, detail="Only CEOs can access marketing ROI stats")
        
    stats = await MarketingService.get_roi_stats(tenant_id, time_range=range)
    return stats

@router.get("/stats")
async def get_marketing_stats(
    range: str = "last_30d",
    auth_data: tuple = Depends(get_current_user_and_tenant)
):
    """
    Retorna el listado de campañas y sus métricas de conversión.
    """
    user, tenant_id = auth_data
    if user["role"] != "ceo":
        raise HTTPException(status_code=403, detail="Only CEOs can access marketing stats")
        
    roi_info = await MarketingService.get_roi_stats(tenant_id, time_range=range)
    campaigns = await MarketingService.get_campaign_stats(tenant_id, time_range=range)
    
    response_data = {
        "roi": roi_info,
        "campaigns": campaigns,
        "is_connected": roi_info.get("is_connected", False),
        "currency": roi_info.get("currency", "ARS")
    }
    
    import logging
    logging.getLogger(__name__).info(f"📊 Sending Metadata Stats to Frontend: Connected={response_data['is_connected']}")
    
    return response_data

@router.get("/token-status")
async def get_token_status(auth_data: tuple = Depends(get_current_user_and_tenant)):
    _, tenant_id = auth_data
    status = await MarketingService.get_token_status(tenant_id)
    return status

@router.get("/clinics")
async def get_clinics(
    auth_data: tuple = Depends(get_current_user_and_tenant)
):
    """
    Lista las clínicas disponibles para el CEO.
    En una arquitectura SaaS real, esto vendría de una relación user_tenants.
    """
    user, _ = auth_data
    if user["role"] != "ceo":
        raise HTTPException(status_code=403, detail="Solo el CEO puede gestionar clínicas.")
    
    # Por ahora listamos todos los tenants (multi-tenant simple)
    clinics = await db.pool.fetch("SELECT id, clinic_name as name FROM tenants ORDER BY id")
    
    results = []
    for c in clinics:
        # Verificar si ya tiene cuenta conectada
        ad_acc = await get_tenant_credential(c['id'], "META_AD_ACCOUNT_ID")
        results.append({
            "id": c['id'],
            "name": c['name'],
            "is_connected": bool(ad_acc)
        })
    return {"clinics": results}

@router.get("/meta-portfolios")
async def get_meta_portfolios(
    auth_data: tuple = Depends(get_current_user_and_tenant)
):
    """
    Lista portafolios (BMs) del token conectado.
    """
    _, tenant_id = auth_data
    token = await get_tenant_credential(tenant_id, "META_USER_LONG_TOKEN")
    if not token:
        raise HTTPException(status_code=401, detail="Meta no está conectado en esta clínica.")
    
    client = MetaAdsClient(access_token=token)
    portfolios = await client.get_portfolios()
    return {"portfolios": portfolios}

@router.get("/meta-accounts")
async def get_meta_accounts(
    portfolio_id: Optional[str] = None,
    auth_data: tuple = Depends(get_current_user_and_tenant)
):
    """
    Lista cuentas de anuncios por portafolio.
    """
    _, tenant_id = auth_data
    token = await get_tenant_credential(tenant_id, "META_USER_LONG_TOKEN")
    if not token:
        raise HTTPException(status_code=401, detail="Meta no está conectado en esta clínica.")
    
    client = MetaAdsClient(access_token=token)
    accounts = await client.get_ad_accounts(portfolio_id=portfolio_id)
    return {"accounts": accounts}

@router.post("/connect")
async def connect_meta_account(
    data: dict,
    auth_data: tuple = Depends(get_current_user_and_tenant)
):
    """
    Vincula una cuenta de anuncios a una clínica.
    """
    _, current_tenant_id = auth_data
    target_tenant_id = data.get("tenant_id")
    ad_account_id = data.get("ad_account_id")
    ad_account_name = data.get("ad_account_name")
    
    if not target_tenant_id or not ad_account_id:
        raise HTTPException(status_code=400, detail="Faltan datos de conexión.")

    # 1. Obtener el token del tenant actual (el que inició el OAuth)
    token = await get_tenant_credential(current_tenant_id, "META_USER_LONG_TOKEN")
    
    # 2. Guardar en el tenant destino
    await save_tenant_credential(target_tenant_id, "META_USER_LONG_TOKEN", token, category="meta_ads")
    await save_tenant_credential(target_tenant_id, "META_AD_ACCOUNT_ID", ad_account_id, category="meta_ads")
    await save_tenant_credential(target_tenant_id, "META_AD_ACCOUNT_NAME", ad_account_name, category="meta_ads")
    
    return {"status": "success", "message": f"Cuenta {ad_account_name} vinculada a clínica {target_tenant_id}"}
@router.get("/debug/stats")
async def debug_marketing_stats(
    range: str = "last_30d",
    secret: Optional[str] = None
):
    """
    Endpoint de diagnóstico ultra-permisivo para mantenimiento.
    """
    from core.auth import ADMIN_TOKEN
    import os
    
    env_admin_token = os.getenv("ADMIN_TOKEN")
    
    debug_info = {
        "server_status": "online",
        "env_admin_token_set": bool(env_admin_token),
        "received_secret": secret,
        "matches": (secret == env_admin_token or secret == "admin-secret-token") if secret else False
    }

    from core.credentials import CREDENTIALS_FERNET_KEY, get_tenant_credential
    
    debug_info["fernet_key_configured"] = bool(CREDENTIALS_FERNET_KEY)
    
    try:
        tenant_id = 1
        raw_token = await get_tenant_credential(tenant_id, "META_USER_LONG_TOKEN")
        
        debug_info["token_found"] = bool(raw_token)
        
        if raw_token:
            debug_info["is_encrypted"] = str(raw_token).startswith("gAAAA")
            debug_info["token_preview"] = f"{str(raw_token)[:15]}..."
            
            from services.meta_ads_service import MetaAdsClient
            client = MetaAdsClient(str(raw_token))
            
            # Listar cuentas
            try:
                accounts = await client.get_ad_accounts()
                debug_info["accessible_accounts"] = [
                    {"id": a.get("id"), "name": a.get("name")} for a in accounts
                ]
            except Exception as e_acc:
                debug_info["accounts_error"] = str(e_acc)

            ad_account_id = await get_tenant_credential(tenant_id, "META_AD_ACCOUNT_ID")
            debug_info["configured_ad_account_id"] = ad_account_id
            
            if ad_account_id:
                try:
                    insights = await client.get_ads_insights(ad_account_id, date_preset="maximum")
                    debug_info["lifetime_insights"] = {
                        "count": len(insights),
                        "spend": sum(float(i.get("spend", 0)) for i in insights)
                    }
                except Exception as api_e:
                    debug_info["meta_status"] = "API_ERROR"
                    debug_info["api_error"] = str(api_e)
    except Exception as e:
        debug_info["general_error"] = str(e)
            
    return debug_info



