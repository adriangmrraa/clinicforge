"""
Meta Ads Graph API Client.
Spec 04: Consulta la Graph API de Meta para enriquecer IDs opacos
(ad_id, campaign_id) con nombres legibles por humanos.

CLINICASV1.0 - Integración Meta Ads & Dentalogic.
"""
import os
import logging
import json
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v21.0")
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
REQUEST_TIMEOUT = float(os.getenv("META_API_TIMEOUT", "5.0"))


class MetaAuthError(Exception):
    """Token de Meta inválido o expirado (HTTP 401)."""
    pass


class MetaRateLimitError(Exception):
    """Rate limit alcanzado en la Graph API (HTTP 429)."""
    pass


class MetaNotFoundError(Exception):
    """Recurso no encontrado o sin permisos (HTTP 404)."""
    pass


class MetaAdsClient:
    """
    Cliente asíncrono para la Graph API de Meta.
    Diseñado para ser stateless; se instancia por llamada o como singleton.
    """

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = (access_token or "").strip() or os.getenv("META_ADS_TOKEN", "")
        if not self.access_token:
            logger.warning("⚠️ META_ADS_TOKEN no configurado. El enriquecimiento de anuncios estará deshabilitado.")

    async def get_ad_details(self, ad_id: str) -> Dict[str, Any]:
        """
        Obtiene detalles de un anuncio desde la Graph API.

        Args:
            ad_id: ID del anuncio de Meta (ej. '123456789').

        Returns:
            Dict con claves: ad_id, ad_name, campaign_name, adset_name.

        Raises:
            MetaAuthError: Token inválido/expirado.
            MetaRateLimitError: Rate limit alcanzado.
            MetaNotFoundError: Anuncio no encontrado.
        """
        if not self.access_token:
            raise MetaAuthError("META_ADS_TOKEN no configurado.")

        if not ad_id or not str(ad_id).strip():
            raise ValueError("ad_id no puede estar vacío.")

        url = f"{GRAPH_API_BASE}/{ad_id}"
        params = {
            "fields": "name,campaign{name},adset{name}",
            "access_token": self.access_token,
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url, params=params)

            if response.status_code == 401:
                logger.error("🔒 Meta Graph API: Token inválido o expirado (401).")
                raise MetaAuthError("Token de Meta inválido o expirado.")

            if response.status_code == 429:
                logger.warning("🚦 Meta Graph API: Rate limit alcanzado (429).")
                raise MetaRateLimitError("Rate limit alcanzado en Meta Graph API.")

            if response.status_code == 404:
                logger.info(f"🔍 Meta Graph API: Anuncio {ad_id} no encontrado (404).")
                raise MetaNotFoundError(f"Anuncio {ad_id} no encontrado.")

            if response.status_code != 200:
                # Error genérico de la API
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                error_msg = error_data.get("error", {}).get("message", response.text[:200])
                logger.error(f"❌ Meta Graph API error ({response.status_code}): {error_msg}")
                raise Exception(f"Meta Graph API error {response.status_code}: {error_msg}")

            data = response.json()

            # Parsear respuesta según esquema esperado
            result = {
                "ad_id": ad_id,
                "ad_name": data.get("name"),
                "campaign_name": None,
                "adset_name": None,
            }

            campaign = data.get("campaign")
            if isinstance(campaign, dict):
                result["campaign_name"] = campaign.get("name")

            adset = data.get("adset")
            if isinstance(adset, dict):
                result["adset_name"] = adset.get("name")

            logger.info(f"✅ Meta Ads enriquecido: ad_id={ad_id}, ad_name={result['ad_name']}, campaign={result['campaign_name']}")
            return result

        except (MetaAuthError, MetaRateLimitError, MetaNotFoundError):
            raise  # Re-raise excepciones tipadas
        except httpx.TimeoutException:
            logger.error(f"⏰ Meta Graph API timeout ({REQUEST_TIMEOUT}s) para ad_id={ad_id}")
            raise
        except Exception as e:
            logger.error(f"❌ Error inesperado consultando Meta Graph API: {e}")
            raise

    async def get_ads_insights(self, ad_account_id: str, date_preset: str = "maximum", level: str = "ad", filtering: Optional[list] = None) -> list:
        """
        Obtiene métricas de rendimiento (gasto, leads, etc.) a nivel de anuncio (default)
        o cuenta/campaña si se especifica 'level'.
        """
        if not self.access_token:
            raise MetaAuthError("META_ADS_TOKEN no configurado.")
        
        if not ad_account_id:
            raise ValueError("ad_account_id es requerido para consultar insights.")

        # Asegurar prefijo 'act_' si no viene
        account_id = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
        
        if level == "account":
            fields = "spend,impressions,clicks,account_currency,account_id,account_name"
            # Nivel cuenta no soporta status filtering
        elif level == "campaign":
            fields = "campaign_id,campaign_name,spend,impressions,clicks,account_currency,effective_status"
            # Incluir campañas borradas/archivadas/pausadas
            if filtering is None:
                 filtering = [{'field': 'campaign.effective_status', 'operator': 'IN', 'value': [
                     'ACTIVE', 'PAUSED', 'DELETED', 'ARCHIVED', 'IN_PROCESS', 'WITH_ISSUES', 
                     'CAMPAIGN_PAUSED', 'ADSET_PAUSED'
                 ]}]
        else:
            fields = "ad_id,ad_name,campaign_id,campaign_name,spend,impressions,clicks,account_currency,effective_status"
            if filtering is None:
                filtering = [{'field': 'ad.effective_status', 'operator': 'IN', 'value': [
                    'ACTIVE', 'PAUSED', 'DELETED', 'ARCHIVED', 'IN_PROCESS', 'WITH_ISSUES', 
                    'CAMPAIGN_PAUSED', 'ADSET_PAUSED'
                ]}]

        url = f"{GRAPH_API_BASE}/{account_id}/insights"
        params = {
            "fields": fields,
            "date_preset": date_preset,
            "level": level,
            "access_token": self.access_token,
            "limit": 1000 # Aumentar límite para traer todo el historial
        }
        
        if filtering:
            params["filtering"] = json.dumps(filtering)
            
        logger.info(f"🔍 Meta Request: {url} | Level={level} | Preset={date_preset} | Filter={params.get('filtering')}")

        try:
            all_insights = []
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT * 2) as client:
                current_url = url
                while current_url:
                    response = await client.get(current_url, params=params if current_url == url else None)
                    
                    if response.status_code != 200:
                        error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"error": {"message": response.text}}
                        error_msg = error_data.get("error", {}).get("message", "Unknown error")
                        error_code = error_data.get("error", {}).get("code", "N/A")
                        error_subcode = error_data.get("error", {}).get("error_subcode", "N/A")
                        
                        logger.error(f"❌ Meta API Error fetching insights for {account_id}: Code={error_code}, Subcode={error_subcode}, Msg='{error_msg}'")
                        return []

                    data = response.json()
                    all_insights.extend(data.get("data", []))
                    
                    # Pagination
                    paging = data.get("paging", {})
                    current_url = paging.get("next")
                    
                return all_insights
        except Exception as e:
            logger.error(f"❌ Error obteniendo insights de Meta para {account_id}: {e}")
            return []

    async def get_portfolios(self) -> list:
        """
        Lista los Business Managers (Portafolios) a los que el usuario tiene acceso.
        """
        url = f"{GRAPH_API_BASE}/me/businesses"
        params = {
            "fields": "name,id",
            "access_token": self.access_token,
        }
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json().get("data", [])
        except Exception as e:
            logger.error(f"❌ Error obteniendo portafolios de Meta: {e}")
            return []

    async def get_ad_accounts(self, portfolio_id: Optional[str] = None) -> list:
        """
        Lista las cuentas de anuncios. Si se provee portfolio_id, intenta obtener 
        tanto client_ad_accounts como owned_ad_accounts.
        """
        params = {
            "fields": "name,id,currency",
            "access_token": self.access_token,
        }
        all_accounts = []
        
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                if portfolio_id:
                    # 1. Intentar client_ad_accounts
                    url_client = f"{GRAPH_API_BASE}/{portfolio_id}/client_ad_accounts"
                    resp_client = await client.get(url_client, params=params)
                    if resp_client.status_code == 200:
                        all_accounts.extend(resp_client.json().get("data", []))
                    
                    # 2. Intentar owned_ad_accounts
                    url_owned = f"{GRAPH_API_BASE}/{portfolio_id}/owned_ad_accounts"
                    resp_owned = await client.get(url_owned, params=params)
                    if resp_owned.status_code == 200:
                        owned_data = resp_owned.json().get("data", [])
                        # Evitar duplicados por ID
                        existing_ids = {acc['id'] for acc in all_accounts}
                        all_accounts.extend([acc for acc in owned_data if acc['id'] not in existing_ids])
                else:
                    # Listado general de cuentas del usuario
                    url = f"{GRAPH_API_BASE}/me/adaccounts"
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    all_accounts = response.json().get("data", [])

            logger.info(f"📊 Meta Ads: Se encontraron {len(all_accounts)} cuentas para portfolio {portfolio_id or 'ME'}")
            return all_accounts
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo cuentas de anuncios de Meta: {e}")
            return []
    async def get_campaigns_with_insights(self, ad_account_id: str, date_preset: str = "maximum", filtering: list = None) -> list:
        """
        Estrategia 'Campaign-First': Lista campañas y expande el campo 'insights' para obtener 
        métricas incluso de las borradas/archivadas que el endpoint de /insights omite.
        """
        if not self.access_token:
            raise MetaAuthError("META_ADS_TOKEN no configurado.")
        
        account_id = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
        
        if filtering is None:
            filtering = [{'field': 'effective_status', 'operator': 'IN', 'value': [
                'ACTIVE', 'PAUSED', 'DELETED', 'ARCHIVED', 'IN_PROCESS', 'WITH_ISSUES', 
                'CAMPAIGN_PAUSED', 'ADSET_PAUSED'
            ]}]

        url = f"{GRAPH_API_BASE}/{account_id}/campaigns"
        
        # IMPORTANTE: Pedimos 'insights' como expansión de campo
        # Esto permite que campañas borradas/archivadas "arrastren" sus datos de gasto
        expand_insights = f"insights.date_preset({date_preset}){{spend,impressions,clicks,account_currency,account_id}}"
        
        params = {
            "fields": f"id,name,effective_status,{expand_insights}",
            "filtering": json.dumps(filtering),
            "access_token": self.access_token,
            "limit": 100
        }

        logger.info(f"🚀 Campaign-First Request: {url} | Preset={date_preset}")

        try:
            all_campaigns = []
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT * 2) as client:
                current_url = url
                while current_url:
                    response = await client.get(current_url, params=params if current_url == url else None)
                    response.raise_for_status()
                    
                    data = response.json()
                    all_campaigns.extend(data.get("data", []))
                    
                    paging = data.get("paging", {})
                    current_url = paging.get("next")
            
            return all_campaigns
        except Exception as e:
            logger.error(f"❌ Error en Campaign-First retrieval para {account_id}: {e}")
            return []

    async def get_ads_with_insights(self, ad_account_id: str, date_preset: str = "maximum", filtering: Optional[list] = None, include_insights: bool = True) -> list:
        """
        Versión a nivel de Anuncio (Creativo): Lista anuncios y opcionalmente expande 'insights'.
        Incluye el nombre de la campaña padre para facilitar el desglose en UI.
        """
        if not self.access_token:
            raise MetaAuthError("META_ADS_TOKEN no configurado.")
        
        account_id = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
        
        if filtering is None:
            filtering = [{'field': 'effective_status', 'operator': 'IN', 'value': [
                'ACTIVE', 'PAUSED', 'DELETED', 'ARCHIVED', 'IN_PROCESS', 'WITH_ISSUES', 
                'CAMPAIGN_PAUSED', 'ADSET_PAUSED'
            ]}]

        url = f"{GRAPH_API_BASE}/{account_id}/ads"
        
        fields = "id,name,effective_status,campaign{id,name}"
        if include_insights:
            expand_insights = f"insights.date_preset({date_preset}){{spend,impressions,clicks,account_currency,account_id}}"
            fields += f",{expand_insights}"
        
        params = {
            "fields": fields,
            "filtering": json.dumps(filtering),
            "access_token": self.access_token,
            "limit": 100
        }

        logger.info(f"🎨 Ads Fetch: {url} | Insights={include_insights} | Preset={date_preset}")

        try:
            all_ads = []
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT * 2) as client:
                current_url = url
                while current_url:
                    response = await client.get(current_url, params=params if current_url == url else None)
                    response.raise_for_status()
                    
                    data = response.json()
                    all_ads.extend(data.get("data", []))
                    
                    paging = data.get("paging", {})
                    current_url = paging.get("next")
            
            return all_ads
        except Exception as e:
            logger.error(f"❌ Error en Ads retrieval para {account_id}: {e}")
            return []
