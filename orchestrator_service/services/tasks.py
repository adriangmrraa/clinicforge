"""
Background Tasks para Meta Ads Enrichment.
Spec 05: Caché Redis + enriquecimiento asíncrono de datos de anuncios.

Flujo:
  1. Verificar Redis (clave `meta:ad:{ad_id}`). Si hit, usar datos cacheados.
  2. Si miss, llamar a MetaAdsClient.get_ad_details().
  3. Guardar resultado en Redis con TTL 48h.
  4. Actualizar tabla `patients` con nombres de campaña/anuncio enriquecidos.

Se ejecuta como BackgroundTask de FastAPI post-respuesta.

CLINICASV1.0 - Integración Meta Ads & Dentalogic.
"""
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = int(os.getenv("META_CACHE_TTL", str(48 * 3600)))  # 48 horas


def _get_redis():
    """Reutiliza el patrón de get_redis de relay.py."""
    try:
        from services.relay import get_redis
        return get_redis()
    except ImportError:
        logger.warning("redis no disponible para caché de Meta Ads")
        return None


async def enrich_patient_attribution(
    patient_id: int,
    ad_id: str,
    tenant_id: int,
    is_last_touch: bool = False,
) -> None:
    """
    Tarea de enriquecimiento asíncrono. Diseñada para ejecutarse como
    FastAPI BackgroundTask (no bloquea la respuesta al webhook/chat).

    Args:
        patient_id: ID del paciente en BD.
        ad_id: ID del anuncio de Meta a enriquecer.
        tenant_id: ID del tenant (soberanía multi-tenant).
        is_last_touch: Si es True, actualiza campos de last_touch; si es False, actualiza first_touch
    """
    if not ad_id:
        logger.debug("enrich_patient_attribution: ad_id vacío, omitiendo.")
        return

    cache_key = f"meta:ad:{ad_id}"
    ad_details: Optional[dict] = None

    # ---- Paso 1: Check Redis Cache ----
    r = _get_redis()
    if r:
        try:
            cached = await r.get(cache_key)
            if cached:
                ad_details = json.loads(cached)
                logger.info(f"🎯 Cache HIT para ad_id={ad_id}")
        except Exception as cache_err:
            logger.warning(f"⚠️ Error leyendo caché Redis para ad_id={ad_id}: {cache_err}")

    # ---- Paso 2: Si miss, llamar a Meta Graph API ----
    if not ad_details:
        try:
            from services.meta_ads_service import MetaAdsClient, MetaAuthError, MetaRateLimitError, MetaNotFoundError
            client = MetaAdsClient()

            if not client.access_token:
                logger.info("enrich_patient_attribution: META_ADS_TOKEN no configurado, omitiendo enriquecimiento.")
                return

            ad_details = await client.get_ad_details(ad_id)
            logger.info(f"🎯 Cache MISS para ad_id={ad_id}, datos obtenidos de Graph API")

            # ---- Paso 3: Guardar en Redis ----
            if r and ad_details:
                try:
                    await r.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(ad_details))
                    logger.debug(f"💾 Caché guardado: {cache_key} (TTL={CACHE_TTL_SECONDS}s)")
                except Exception as set_err:
                    logger.warning(f"⚠️ Error guardando caché Redis: {set_err}")

        except MetaAuthError:
            logger.error(f"🔒 Token de Meta inválido. Enriquecimiento deshabilitado para ad_id={ad_id}")
            return
        except MetaNotFoundError:
            logger.info(f"🔍 Anuncio {ad_id} no encontrado en Meta. Degradación grácil.")
            return
        except MetaRateLimitError:
            logger.warning(f"🚦 Rate limit Meta. Reintentaremos en la próxima solicitud para ad_id={ad_id}")
            return
        except Exception as api_err:
            logger.error(f"❌ Error enriqueciendo ad_id={ad_id}: {api_err}")
            return

    # ---- Paso 4: Actualizar tabla patients ----
    if not ad_details:
        return

    campaign_name = ad_details.get("campaign_name")
    ad_name = ad_details.get("ad_name")
    adset_name = ad_details.get("adset_name")

    try:
        from db import get_pool
        pool = get_pool()
        if not pool:
            logger.warning("enrich_patient_attribution: pool de BD no disponible")
            return

        # Determinar qué campos actualizar según el tipo de touch
        if is_last_touch:
            # Actualizar campos de last_touch
            await pool.execute("""
                UPDATE patients 
                SET last_touch_ad_name = COALESCE($1, last_touch_ad_name),
                    last_touch_campaign_name = COALESCE($2, last_touch_campaign_name),
                    updated_at = NOW()
                WHERE id = $3 AND tenant_id = $4
            """, ad_name, campaign_name, patient_id, tenant_id)
            
            # Registrar en historial
            await pool.execute("""
                INSERT INTO patient_attribution_history (
                    patient_id, tenant_id, attribution_type, source,
                    ad_id, ad_name, campaign_id, campaign_name, adset_name,
                    event_description
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """, 
                patient_id, tenant_id, 'last_touch', 'META_ADS',
                ad_id, ad_name, ad_details.get("campaign_id"), campaign_name, adset_name,
                f"Enriched last-touch attribution via Meta API"
            )
            
            logger.info(
                f"✅ Paciente {patient_id} last-touch enriquecido: "
                f"campaign={campaign_name}, ad_name={ad_name}"
            )
        else:
            # Actualizar campos de first_touch (compatibilidad hacia atrás)
            await pool.execute("""
                UPDATE patients 
                SET first_touch_campaign_name = COALESCE($1, first_touch_campaign_name),
                    first_touch_ad_name = COALESCE($2, first_touch_ad_name),
                    first_touch_adset_name = COALESCE($3, first_touch_adset_name),
                    updated_at = NOW()
                WHERE id = $4 AND tenant_id = $5
            """, campaign_name, ad_name, adset_name, patient_id, tenant_id)
            
            # Registrar en historial
            await pool.execute("""
                INSERT INTO patient_attribution_history (
                    patient_id, tenant_id, attribution_type, source,
                    ad_id, ad_name, campaign_id, campaign_name, adset_name,
                    event_description
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """, 
                patient_id, tenant_id, 'first_touch', 'META_ADS',
                ad_id, ad_name, ad_details.get("campaign_id"), campaign_name, adset_name,
                f"Enriched first-touch attribution via Meta API"
            )
            
            logger.info(
                f"✅ Paciente {patient_id} first-touch enriquecido: "
                f"campaign={campaign_name}, ad_name={ad_name}, adset={adset_name}"
            )

    except Exception as db_err:
        logger.error(f"❌ Error actualizando paciente {patient_id} con datos enriquecidos: {db_err}")
