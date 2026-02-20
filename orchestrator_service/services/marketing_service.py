import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from db import db

logger = logging.getLogger(__name__)

class MarketingService:
    @staticmethod
    async def get_roi_stats(tenant_id: int, time_range: str = "last_30d") -> Dict[str, Any]:
        """
        Calcula el ROI real cruzando datos de atribución con transacciones contables.
        """
        from core.credentials import get_tenant_credential
        token = await get_tenant_credential(tenant_id, "META_USER_LONG_TOKEN")
        is_connected = bool(token)
        
        logger.info(f"🔍 ROI Debug: Tenant={tenant_id}, TokenFound={is_connected}, Range={time_range}")
        
        # Mapeo de time_range a intervalos de Postgres
        interval_map = {
            "last_30d": "30 days",
            "last_90d": "90 days",
            "this_year": "1 year",
            "lifetime": "100 years"
        }
        interval = interval_map.get(time_range, "30 days")

        try:
            # 1. Obtener leads atribuidos a Meta Ads en el periodo
            meta_leads = await db.pool.fetchval(f"""
                SELECT COUNT(*) FROM patients 
                WHERE tenant_id = $1 AND acquisition_source = 'META_ADS'
                AND created_at >= NOW() - INTERVAL '{interval}'
            """, tenant_id) or 0

            # 2. Obtener pacientes convertidos en el periodo
            converted_patients = await db.pool.fetchval(f"""
                SELECT COUNT(DISTINCT p.id) 
                FROM patients p
                JOIN appointments a ON p.id = a.patient_id
                WHERE p.tenant_id = $1 AND p.acquisition_source = 'META_ADS'
                AND a.status IN ('confirmed', 'completed')
                AND a.appointment_datetime >= NOW() - INTERVAL '{interval}'
            """, tenant_id) or 0

            # 3. Calcular Ingresos Reales en el periodo
            total_revenue = await db.pool.fetchval(f"""
                SELECT SUM(amount) 
                FROM accounting_transactions t
                JOIN patients p ON t.patient_id = p.id
                WHERE p.tenant_id = $1 AND p.acquisition_source = 'META_ADS'
                AND t.status = 'completed'
                AND t.created_at >= NOW() - INTERVAL '{interval}'
            """, tenant_id) or 0

            # 4. Inversión (Spend) - Sincronizada con Meta si hay conexión
            from services.meta_ads_service import MetaAdsClient
            ad_account_id = await get_tenant_credential(tenant_id, "META_AD_ACCOUNT_ID")
            
            total_spend = 0.0
            currency = "ARS"
            
            if is_connected and ad_account_id:
                try:
                    meta_client = MetaAdsClient(token)
                    meta_preset_map = {
                        "last_30d": "last_30d",
                        "last_90d": "last_90d",
                        "this_year": "this_year",
                        "lifetime": "maximum"
                    }
                    meta_preset = meta_preset_map.get(time_range, "last_30d")
                    insights = await meta_client.get_ads_insights(ad_account_id, date_preset=meta_preset)
                    total_spend = sum(float(item.get('spend', 0)) for item in insights)
                    if insights:
                        currency = insights[0].get('account_currency', 'ARS')
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo sincronizar spend real de Meta: {e}")
            
            cpa = total_spend / meta_leads if meta_leads > 0 else 0

            return {
                "total_spend": total_spend,
                "total_revenue": float(total_revenue or 0),
                "leads": meta_leads,
                "patients_converted": converted_patients,
                "cpa": cpa,
                "is_connected": is_connected,
                "ad_account_id": ad_account_id,
                "currency": currency,
                "time_range": time_range
            }
        except Exception as e:
            logger.error(f"❌ Error calculating ROI stats for tenant {tenant_id}: {e}")
            return {
                "total_spend": 0, "total_revenue": 0, "leads": 0, "patients_converted": 0,
                "cpa": 0, "is_connected": is_connected, "error": str(e)
            }

    @staticmethod
    async def get_token_status(tenant_id: int) -> Dict[str, Any]:
        """Verifica la salud del token de Meta y devuelve días para expirar."""
        from core.credentials import get_tenant_credential
        expires_at_str = await get_tenant_credential(tenant_id, "META_TOKEN_EXPIRES_AT")
        token = await get_tenant_credential(tenant_id, "META_USER_LONG_TOKEN")
        
        if not token:
            return {"needs_reconnect": True, "days_left": None}
            
        if not expires_at_str:
            # Si no tenemos fecha (legacy or failed save), asumimos que falta poco si el token es viejo
            # Por ahora, devolvemos un estado neutral pero seguro
            return {"needs_reconnect": False, "days_left": None}
            
        try:
            from datetime import datetime
            expires_at = datetime.fromisoformat(expires_at_str)
            now = datetime.now()
            
            delta = expires_at - now
            days_left = delta.days
            
            return {
                "needs_reconnect": days_left <= 0,
                "days_left": max(0, days_left),
                "expires_at": expires_at_str
            }
        except Exception as e:
            logger.error(f"Error parsing token expiration: {e}")
            return {"needs_reconnect": True, "days_left": 0}

    @staticmethod
    async def get_campaign_stats(tenant_id: int, time_range: str = "last_30d") -> List[Dict[str, Any]]:
        """
        Retorna el rendimiento por campaña/anuncio, sincronizando con Meta si hay conexión.
        """
        try:
            from core.credentials import get_tenant_credential
            from services.meta_ads_service import MetaAdsClient
            
            token = await get_tenant_credential(tenant_id, "META_USER_LONG_TOKEN")
            ad_account_id = await get_tenant_credential(tenant_id, "META_AD_ACCOUNT_ID")
            
            logger.info(f"🔍 Campaigns Debug: Tenant={tenant_id}, TokenFound={bool(token)}, AdAccount={ad_account_id}, Range={time_range}")
            
            interval_map = {
                "last_30d": "30 days",
                "last_90d": "90 days",
                "this_year": "1 year",
                "lifetime": "100 years"
            }
            interval = interval_map.get(time_range, "30 days")

            # 1. Obtener datos de Meta (Insights)
            meta_ads = []
            if token and ad_account_id:
                try:
                    meta_client = MetaAdsClient(token)
                    meta_preset_map = {
                        "last_30d": "last_30d",
                        "last_90d": "last_90d",
                        "this_year": "this_year",
                        "lifetime": "maximum"
                    }
                    meta_preset = meta_preset_map.get(time_range, "last_30d")
                    meta_ads = await meta_client.get_ads_insights(ad_account_id, date_preset=meta_preset)
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo obtener ads de Meta: {e}")

            # 2. Obtener atribución local (Leads y Citas por ad_id) filtrado por periodo
            local_stats = await db.pool.fetch(f"""
                SELECT meta_ad_id,
                       COUNT(id) as leads,
                       COUNT(id) FILTER (WHERE EXISTS (
                           SELECT 1 FROM appointments a 
                           WHERE a.patient_id = patients.id AND a.status IN ('confirmed', 'completed')
                           AND a.appointment_datetime >= NOW() - INTERVAL '{interval}'
                       )) as appointments,
                       (SELECT SUM(t.amount) 
                        FROM accounting_transactions t 
                        JOIN patients p2 ON t.patient_id = p2.id 
                        WHERE p2.meta_ad_id = patients.meta_ad_id AND t.status = 'completed'
                        AND t.created_at >= NOW() - INTERVAL '{interval}'
                       ) as revenue
                FROM patients
                WHERE tenant_id = $1 AND acquisition_source = 'META_ADS' AND meta_ad_id IS NOT NULL
                AND created_at >= NOW() - INTERVAL '{interval}'
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
                        "status": "active"
                    })
            
            # 4. Incluir ads con atribución local pero sin spend en Meta para este periodo
            meta_ad_ids = {ad.get('ad_id') for ad in meta_ads}
            for ad_id, local in attribution_map.items():
                if ad_id not in meta_ad_ids:
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

            # Diagnostic logs
            logger.info(f"📊 Marketing Sync: Tenant={tenant_id}, Range={time_range}, MetaAdsCount={len(meta_ads)}, LocalAttributionCount={len(local_stats)}")

            return results
        except Exception as e:
            logger.error(f"❌ Error fetching campaign stats for tenant {tenant_id}: {e}")
            return []
