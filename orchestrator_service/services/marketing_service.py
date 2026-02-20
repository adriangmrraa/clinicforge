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
            "yearly": "1 year",
            "lifetime": "100 years",
            "all": "100 years"
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
                        "lifetime": "maximum",
                        "all": "maximum"
                    }
                    meta_preset = meta_preset_map.get(time_range, "last_30d")
                    
                    # Usar level="account" para asegurar que obtenemos el gasto total histórico
                    # incluso si los anuncios individuales han sido borrados o archivados.
                    insights = await meta_client.get_ads_insights(ad_account_id, date_preset=meta_preset, level="account")
                    
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
                "yearly": "1 year",
                "lifetime": "100 years",
                "all": "100 years"
            }
            interval = interval_map.get(time_range, "30 days")

            # 1. Obtener datos de Meta (Campaign-First Strategy)
            meta_campaigns = []
            account_total_spend = 0.0
            if token and ad_account_id:
                try:
                    meta_client = MetaAdsClient(token)
                    meta_preset_map = {
                        "last_30d": "last_30d",
                        "last_90d": "last_90d",
                        "this_year": "this_year",
                        "lifetime": "maximum",
                        "all": "maximum"
                    }
                    meta_preset = meta_preset_map.get(time_range, "last_30d")
                    
                    # 1.1 Obtener total cuenta para reconciliación (ROI Real)
                    acc_ins = await meta_client.get_ads_insights(ad_account_id, date_preset=meta_preset, level="account")
                    if acc_ins:
                         account_total_spend = float(acc_ins[0].get('spend', 0))

                    # 1.2 Obtener campañas con insights embebidos
                    meta_campaigns = await meta_client.get_campaigns_with_insights(ad_account_id, date_preset=meta_preset)
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
            reported_spend = 0.0
            
            # 3. Construir lista final priorizando Meta Campaigns (Insights embebidos)
            if meta_campaigns:
                for camp in meta_campaigns:
                    # Meta devuelve 'insights' como un objeto con 'data' (lista de 1 elemento usualmente)
                    insights_data = camp.get('insights', {}).get('data', [])
                    ins = insights_data[0] if insights_data else {}
                    
                    camp_id = camp.get('id')
                    spend = float(ins.get('spend', 0))
                    reported_spend += spend
                    
                    # Ver atribución (Usamos Campaign ID como fallback de Ad ID en la UI)
                    local = attribution_map.get(camp_id, {})
                    rev = float(local.get('revenue') or 0)
                    roi = (rev - spend) / spend if spend > 0 else 0
                    
                    results.append({
                        "ad_id": camp_id,
                        "ad_name": camp.get('name', 'Campaña sin nombre'),
                        "campaign_name": "Agrupado por Campaña",
                        "spend": spend,
                        "leads": local.get('leads', 0),
                        "appointments": local.get('appointments', 0),
                        "roi": roi,
                        "status": camp.get('effective_status', 'active').lower()
                    })
            
            # 4. Reconciliación (Gasto Histórico/Otros)
            # Si el gasto de la cuenta es mayor que el de las campañas reportadas (típico en cuentas con muchos borrados)
            diff = account_total_spend - reported_spend
            if diff > 1.0: # Margen de 1 unidad monetaria
                results.append({
                    "ad_id": "historical_other",
                    "ad_name": "Gasto Histórico / Otros",
                    "campaign_name": "Acumulado sin desglose",
                    "spend": diff,
                    "leads": 0,
                    "appointments": 0,
                    "roi": 0.0,
                    "status": "archived"
                })

            # 5. Incluir atribución local huérfana (Ad IDs no encontrados en las campañas actuales)
            meta_ids = {c.get('id') for c in meta_campaigns}
            for ad_id, local in attribution_map.items():
                if ad_id not in meta_ids and ad_id != "historical_other":
                    results.append({
                        "ad_id": ad_id,
                        "ad_name": "Anuncio con Atribución",
                        "campaign_name": "Atribución Directa",
                        "spend": 0.0,
                        "leads": local.get('leads', 0),
                        "appointments": local.get('appointments', 0),
                        "roi": 0.0,
                        "status": "inactive"
                    })

            # Diagnostic logs
            logger.info(f"[Marketing Sync] Tenant={tenant_id}, Range={time_range}, MetaCampaignsCount={len(meta_campaigns)}, LocalAttributionCount={len(local_stats)}")

            return results
        except Exception as e:
            logger.error(f"❌ Error fetching campaign stats for tenant {tenant_id}: {e}")
            return []
