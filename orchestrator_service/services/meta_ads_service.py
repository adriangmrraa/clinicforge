"""
Meta Ads Graph API Client.
Spec 04: Consulta la Graph API de Meta para enriquecer IDs opacos
(ad_id, campaign_id) con nombres legibles por humanos.

CLINICASV1.0 - Integración Meta Ads & Dentalogic.
"""
import os
import logging
from typing import Optional, Dict, Any

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
