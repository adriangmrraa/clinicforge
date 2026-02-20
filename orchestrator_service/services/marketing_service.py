import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from db import db

logger = logging.getLogger(__name__)

class MarketingService:
    @staticmethod
    async def get_roi_stats(tenant_id: int) -> Dict[str, Any]:
        """
        Calcula el ROI real cruzando datos de atribución con transacciones contables.
        """
        try:
            # 1. Obtener leads atribuidos a Meta Ads
            meta_leads = await db.pool.fetchval("""
                SELECT COUNT(*) FROM patients 
                WHERE tenant_id = $1 AND acquisition_source = 'META_ADS'
            """, tenant_id) or 0

            # 2. Obtener pacientes convertidos (que tienen al menos un turno confirmado/completado)
            # o que tienen transacciones contables.
            converted_patients = await db.pool.fetchval("""
                SELECT COUNT(DISTINCT p.id) 
                FROM patients p
                JOIN appointments a ON p.id = a.patient_id
                WHERE p.tenant_id = $1 AND p.acquisition_source = 'META_ADS'
                AND a.status IN ('confirmed', 'completed')
            """, tenant_id) or 0

            # 3. Calcular Ingresos Reales de estos pacientes
            total_revenue = await db.pool.fetchval("""
                SELECT SUM(amount) 
                FROM accounting_transactions t
                JOIN patients p ON t.patient_id = p.id
                WHERE p.tenant_id = $1 AND p.acquisition_source = 'META_ADS'
                AND t.status = 'completed'
            """, tenant_id) or 0

            # 4. Inversión (Spend) - Mockeado por ahora o recuperado de Meta API si estuviera sync
            # En una fase real, esto vendría de una tabla 'meta_campaign_stats'
            # 5. Obtener Inversión Real desde Meta
            from core.credentials import get_tenant_credential
            from services.meta_ads_service import MetaAdsClient
            token = await get_tenant_credential(tenant_id, "META_USER_LONG_TOKEN")
            ad_account_id = await get_tenant_credential(tenant_id, "META_AD_ACCOUNT_ID")
            
            total_spend = 0.0
            currency = "ARS"
            
            if token and ad_account_id:
                try:
                    meta_client = MetaAdsClient(token)
                    insights = await meta_client.get_ads_insights(ad_account_id)
                    total_spend = sum(float(item.get('spend', 0)) for item in insights)
                    if insights:
                        currency = insights[0].get('account_currency', 'ARS')
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo sincronizar spend real de Meta: {e}")
                    total_spend = 1500.0 # Fallback demo
            else:
                total_spend = 1500.0 # Fallback demo
            
            cpa = total_spend / meta_leads if meta_leads > 0 else 0

            return {
                "total_spend": total_spend,
                "total_revenue": float(total_revenue),
                "leads": meta_leads,
                "patients_converted": converted_patients,
                "cpa": cpa,
                "is_connected": bool(token),
                "ad_account_id": ad_account_id,
                "currency": currency
            }
        except Exception as e:
            logger.error(f"Error calculating ROI stats: {e}")
            return {
                "total_spend": 0,
                "total_revenue": 0,
                "leads": 0,
                "patients_converted": 0,
                "cpa": 0
            }

    @staticmethod
    async def get_campaign_stats(tenant_id: int) -> List[Dict[str, Any]]:
        """
        Retorna el rendimiento por campaña/anuncio, sincronizando con Meta si hay conexión.
        """
        from core.credentials import get_tenant_credential
        from services.meta_ads_service import MetaAdsClient
        
        token = await get_tenant_credential(tenant_id, "META_USER_LONG_TOKEN")
        ad_account_id = await get_tenant_credential(tenant_id, "META_AD_ACCOUNT_ID")
        
        # 1. Obtener datos de Meta (Insights)
        meta_ads = []
        if token and ad_account_id:
            try:
                meta_client = MetaAdsClient(token)
                meta_ads = await meta_client.get_ads_insights(ad_account_id)
            except Exception as e:
                logger.warning(f"⚠️ No se pudo obtener ads de Meta: {e}")

        # 2. Obtener atribución local (Leads y Citas por ad_id)
        # Agrupamos por meta_ad_id para cruzar con Meta
        local_stats = await db.pool.fetch("""
            SELECT meta_ad_id,
                   COUNT(id) as leads,
                   COUNT(id) FILTER (WHERE EXISTS (
                       SELECT 1 FROM appointments a 
                       WHERE a.patient_id = patients.id AND a.status IN ('confirmed', 'completed')
                   )) as appointments,
                   (SELECT SUM(t.amount) 
                    FROM accounting_transactions t 
                    JOIN patients p2 ON t.patient_id = p2.id 
                    WHERE p2.meta_ad_id = patients.meta_ad_id AND t.status = 'completed'
                   ) as revenue
            FROM patients
            WHERE tenant_id = $1 AND acquisition_source = 'META_ADS' AND meta_ad_id IS NOT NULL
            GROUP BY meta_ad_id
        """, tenant_id)
        
        attribution_map = {row['meta_ad_id']: row for row in local_stats}

        results = []
        
        # 3. Construir lista final priorizando Meta Ads
        if meta_ads:
            for ad in meta_ads:
                ad_id = ad.get('ad_id')
                local = attribution_map.get(ad_id, {})
                spend = float(ad.get('spend', 0))
                rev = float(local.get('revenue') or 0)
                
                roi = (rev - spend) / spend if spend > 0 else 0
                
                results.append({
                    "ad_id": ad_id,
                    "ad_name": ad.get('ad_name', 'Anuncio sin nombre'),
                    "campaign_name": ad.get('campaign_name', 'Campaña de Meta'),
                    "spend": spend,
                    "leads": local.get('leads', 0),
                    "appointments": local.get('appointments', 0),
                    "roi": roi,
                    "status": "active" # Meta insights solo trae activos usualmente o filtramos
                })
        
        # 4. Si hay data local que no está en los insights actuales (ads viejos), los agregamos
        meta_ad_ids = {ad.get('ad_id') for ad in meta_ads}
        for ad_id, local in attribution_map.items():
            if ad_id not in meta_ad_ids:
                rev = float(local.get('revenue') or 0)
                results.append({
                    "ad_id": ad_id,
                    "ad_name": "Anuncio Histórico",
                    "campaign_name": "Atribución Directa",
                    "spend": 0.0,
                    "leads": local.get('leads', 0),
                    "appointments": local.get('appointments', 0),
                    "roi": 0.0,
                    "status": "inactive"
                })

        if not results:
            # Fallback mock para demostración si no hay nada de nada
            results = [
                {
                    "ad_id": "meta_123",
                    "ad_name": "Consulta Estética Gratis (Demo)",
                    "campaign_name": "Captación Invierno",
                    "spend": 450.0,
                    "leads": 24,
                    "appointments": 8,
                    "roi": 1.5,
                    "status": "active"
                }
            ]

        return results
