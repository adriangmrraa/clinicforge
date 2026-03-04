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
        
        # Mapeo de time_range a intervalos compatibles con asyncpg (timedelta)
        interval_map = {
            "last_30d": timedelta(days=30),
            "last_90d": timedelta(days=90),
            "this_year": timedelta(days=365),
            "yearly": timedelta(days=365),
            "lifetime": timedelta(days=36500), # 100 years
            "all": timedelta(days=36500)
        }
        interval = interval_map.get(time_range, timedelta(days=30))

        try:
            # 1. Obtener leads atribuidos a Meta Ads en el periodo
            meta_leads = await db.pool.fetchval("""
                SELECT COUNT(*) FROM patients 
                WHERE tenant_id = $1 AND acquisition_source = 'META_ADS'
                AND created_at >= NOW() - $2::interval
            """, tenant_id, interval) or 0

            # 2. Obtener pacientes convertidos en el periodo
            converted_patients = await db.pool.fetchval("""
                SELECT COUNT(DISTINCT p.id) 
                FROM patients p
                JOIN appointments a ON p.id = a.patient_id
                WHERE p.tenant_id = $1 AND p.acquisition_source = 'META_ADS'
                AND a.status IN ('confirmed', 'completed')
                AND a.appointment_datetime >= NOW() - $2::interval
            """, tenant_id, interval) or 0

            # 3. Calcular Ingresos Reales en el periodo
            total_revenue = await db.pool.fetchval("""
                SELECT SUM(amount) 
                FROM accounting_transactions t
                JOIN patients p ON t.patient_id = p.id
                WHERE p.tenant_id = $1 AND p.acquisition_source = 'META_ADS'
                AND t.status = 'completed'
                AND t.created_at >= NOW() - $2::interval
            """, tenant_id, interval) or 0

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
    async def get_campaign_stats(tenant_id: int, time_range: str = "last_30d") -> Dict[str, Any]:
        """
        Retorna el rendimiento por campaña/anuncio, sincronizando con Meta si hay conexión.
        """
        try:
            from core.credentials import get_tenant_credential
            from services.meta_ads_service import MetaAdsClient
            
            token = await get_tenant_credential(tenant_id, "META_USER_LONG_TOKEN")
            ad_account_id = await get_tenant_credential(tenant_id, "META_AD_ACCOUNT_ID")
            
            logger.info(f"🔍 Campaigns Debug: Tenant={tenant_id}, TokenFound={bool(token)}, AdAccount={ad_account_id}, Range={time_range}")
            
            # Mapeo de time_range a intervalos compatibles con asyncpg (timedelta)
            interval_map = {
                "last_30d": timedelta(days=30),
                "last_90d": timedelta(days=90),
                "this_year": timedelta(days=365),
                "yearly": timedelta(days=365),
                "lifetime": timedelta(days=36500), # 100 years
                "all": timedelta(days=36500)
            }
            interval = interval_map.get(time_range, timedelta(days=30))

            # 1. Obtener datos de Meta (Campaign-First + Ads Strategy)
            meta_campaigns = []
            meta_ads_raw = []
            account_total_spend = 0.0
            if token and ad_account_id:
                try:
                    meta_client = MetaAdsClient(token)
                    meta_preset = {
                        "last_30d": "last_30d",
                        "last_90d": "last_90d",
                        "this_year": "this_year",
                        "lifetime": "maximum",
                        "all": "maximum"
                    }.get(time_range, "last_30d")
                    
                    # 1.1 Obtener total cuenta para reconciliación (ROI Real)
                    acc_ins = await meta_client.get_ads_insights(ad_account_id, date_preset=meta_preset, level="account")
                    if acc_ins:
                         account_total_spend = float(acc_ins[0].get('spend', 0))

                    # 1. Recuperar Datos desde Meta (Campañas y Maestro de Anuncios)
                    # Estrategia: Pedimos listado a nivel de insights por campaña y anuncio, 
                    # esto coincide directamente con cómo se consulta el Total de la Cuenta.
                    meta_campaigns = await meta_client.get_ads_insights(
                        ad_account_id, 
                        date_preset=meta_preset, 
                        level="campaign"
                    )
                    
                    meta_ads_raw = await meta_client.get_ads_insights(
                        ad_account_id, 
                        date_preset=meta_preset, 
                        level="ad"
                    )

                except Exception as e:
                    logger.warning(f"⚠️ No se pudo obtener ads de Meta: {e}")

            # 2. Obtener atribución local (Leads y Citas) a nivel Anuncio
            local_ad_stats = await db.pool.fetch("""
                SELECT meta_ad_id,
                       COUNT(id) as leads,
                       COUNT(id) FILTER (WHERE EXISTS (
                           SELECT 1 FROM appointments a 
                           WHERE a.patient_id = patients.id AND a.status IN ('confirmed', 'completed')
                           AND a.appointment_datetime >= NOW() - $2::interval
                       )) as appointments,
                       (SELECT SUM(t.amount) 
                        FROM accounting_transactions t 
                        JOIN patients p2 ON t.patient_id = p2.id 
                        WHERE p2.meta_ad_id = patients.meta_ad_id AND t.status = 'completed'
                        AND t.created_at >= NOW() - $2::interval
                       ) as revenue
                FROM patients
                WHERE tenant_id = $1 AND acquisition_source = 'META_ADS' AND meta_ad_id IS NOT NULL
                AND created_at >= NOW() - $2::interval
                GROUP BY meta_ad_id
            """, tenant_id, interval)
            
            ad_attribution_map = {row['meta_ad_id']: row for row in local_ad_stats}

            # 2.1 Obtener atribución local (Leads y Citas) a nivel Campaña
            local_campaign_stats = await db.pool.fetch("""
                SELECT meta_campaign_id,
                       COUNT(id) as leads,
                       COUNT(id) FILTER (WHERE EXISTS (
                           SELECT 1 FROM appointments a 
                           WHERE a.patient_id = patients.id AND a.status IN ('confirmed', 'completed')
                           AND a.appointment_datetime >= NOW() - $2::interval
                       )) as appointments,
                       (SELECT SUM(t.amount) 
                        FROM accounting_transactions t 
                        JOIN patients p2 ON t.patient_id = p2.id 
                        WHERE p2.meta_campaign_id = patients.meta_campaign_id AND t.status = 'completed'
                        AND t.created_at >= NOW() - $2::interval
                       ) as revenue
                FROM patients
                WHERE tenant_id = $1 AND acquisition_source = 'META_ADS' AND meta_campaign_id IS NOT NULL
                AND created_at >= NOW() - $2::interval
                GROUP BY meta_campaign_id
            """, tenant_id, interval)
            
            campaign_attribution_map = {row['meta_campaign_id']: row for row in local_campaign_stats}

            campaign_results = []
            creative_results = []
            reported_camp_spend = 0.0
            reported_ad_spend = 0.0
            
            # 3. Procesar Campañas
            if meta_campaigns:
                for camp in meta_campaigns:
                    camp_id = camp.get('campaign_id')
                    if not camp_id: continue
                    spend = float(camp.get('spend', 0))
                    reported_camp_spend += spend
                    
                    local = campaign_attribution_map.get(camp_id, {})
                    rev = float(local.get('revenue') or 0)
                    roi = (rev - spend) / spend if spend > 0 else 0
                    
                    campaign_results.append({
                        "ad_id": camp_id,
                        "ad_name": camp.get('campaign_name', 'Campaña sin nombre'),
                        "campaign_name": "Agrupado por Campaña",
                        "spend": spend,
                        "leads": local.get('leads', 0),
                        "appointments": local.get('appointments', 0),
                        "patients_converted": local.get('appointments', 0),
                        "roi": roi,
                        "status": camp.get('campaign.effective_status', 'active').lower()
                    })
            
            # 4. Procesar Creativos (Anuncios)
            if meta_ads_raw:
                for ad in meta_ads_raw:
                    ad_id = ad.get('ad_id')
                    if not ad_id: continue
                    spend = float(ad.get('spend', 0))
                    reported_ad_spend += spend
                    
                    local = ad_attribution_map.get(ad_id, {})
                    rev = float(local.get('revenue') or 0)
                    roi = (rev - spend) / spend if spend > 0 else 0
                    
                    creative_results.append({
                        "ad_id": ad_id,
                        "ad_name": ad.get('ad_name', 'Anuncio sin nombre'),
                        "campaign_name": ad.get('campaign_name', '—'),
                        "spend": spend,
                        "leads": local.get('leads', 0),
                        "appointments": local.get('appointments', 0),
                        "patients_converted": local.get('appointments', 0),
                        "roi": roi,
                        "status": ad.get('ad.effective_status', 'active').replace('_', ' ').lower()
                    })

            # 5. Reconciliación (Gasto Histórico/Otros)
            diff_camp = account_total_spend - reported_camp_spend
            if diff_camp > 1.0:
                campaign_results.append({
                    "ad_id": "historical_other",
                    "ad_name": "Gasto Histórico / Otros",
                    "campaign_name": "Acumulado sin desglose",
                    "spend": diff_camp,
                    "leads": 0, "appointments": 0, "roi": 0.0, "status": "archived"
                })

            diff_ad = account_total_spend - reported_ad_spend
            if diff_ad > 1.0:
                creative_results.append({
                    "ad_id": "historical_other",
                    "ad_name": "Gasto Histórico / Otros",
                    "campaign_name": "Acumulado sin desglose",
                    "spend": diff_ad,
                    "leads": 0, "appointments": 0, "roi": 0.0, "status": "archived"
                })

            # 6. Incluir atribución local huérfana
            meta_camp_ids = {c.get('id') for c in meta_campaigns}
            meta_ad_ids = {a.get('id') for a in meta_ads_raw}
            
            for camp_id, local in campaign_attribution_map.items():
                if camp_id != "historical_other" and camp_id not in meta_camp_ids:
                    campaign_results.append({
                        "ad_id": camp_id,
                        "ad_name": "Campaña con Atribución",
                        "campaign_name": "Atribución Directa",
                        "spend": 0.0,
                        "leads": local.get('leads', 0), 
                        "appointments": local.get('appointments', 0),
                        "patients_converted": local.get('appointments', 0),
                        "roi": 0.0, "status": "inactive"
                    })

            for ad_id, local in ad_attribution_map.items():
                if ad_id != "historical_other" and ad_id not in meta_ad_ids:
                    creative_results.append({
                        "ad_id": ad_id,
                        "ad_name": "Anuncio Histórico",
                        "campaign_name": "Atribución Directa",
                        "spend": 0.0,
                        "leads": local.get('leads', 0), 
                        "appointments": local.get('appointments', 0),
                        "patients_converted": local.get('appointments', 0),
                        "roi": 0.0, "status": "inactive"
                    })

            logger.info(f"[Marketing Sync] Tenant={tenant_id}, Range={time_range}, Campaigns={len(campaign_results)}, Creatives={len(creative_results)}")

            return {
                "campaigns": campaign_results,
                "creatives": creative_results,
                "account_total_spend": account_total_spend
            }
        except Exception as e:
            logger.error(f"❌ Error fetching marketing detail for tenant {tenant_id}: {e}")
            return {"campaigns": [], "creatives": [], "account_total_spend": 0}

    @staticmethod
    async def get_combined_marketing_stats(tenant_id: int, time_range: str = "last_30d") -> Dict[str, Any]:
        """
        Get combined marketing stats from all platforms (Meta + Google)
        
        Args:
            tenant_id: Tenant ID
            time_range: Time range for metrics
            
        Returns:
            Combined marketing stats
        """
        try:
            # Get Meta stats
            meta_stats = await MarketingService.get_roi_stats(tenant_id, time_range)
            
            # Get Google stats if available
            google_stats = {}
            try:
                from services.marketing.google_ads_service import GoogleAdsService
                google_stats = await GoogleAdsService.get_metrics(tenant_id, time_range)
            except ImportError:
                logger.warning("Google Ads service not available")
            except Exception as e:
                logger.warning(f"Failed to get Google stats: {e}")
            
            # Calculate combined metrics
            total_spend = meta_stats.get("total_spend", 0) + google_stats.get("cost", 0)
            total_revenue = meta_stats.get("total_revenue", 0) + google_stats.get("conversions_value", 0)
            total_leads = meta_stats.get("leads", 0) + google_stats.get("conversions", 0)
            
            # Calculate combined ROI
            combined_roi = (total_revenue / total_spend * 100) if total_spend > 0 else 0
            
            return {
                "meta": {
                    "is_connected": meta_stats.get("is_connected", False),
                    "spend": meta_stats.get("total_spend", 0),
                    "revenue": meta_stats.get("total_revenue", 0),
                    "leads": meta_stats.get("leads", 0),
                    "patients_converted": meta_stats.get("patients_converted", 0),
                    "cpa": meta_stats.get("cpa", 0),
                    "currency": meta_stats.get("currency", "ARS")
                },
                "google": {
                    "is_connected": google_stats.get("is_connected", False),
                    "spend": google_stats.get("cost", 0),
                    "revenue": google_stats.get("conversions_value", 0),
                    "leads": google_stats.get("conversions", 0),
                    "impressions": google_stats.get("impressions", 0),
                    "clicks": google_stats.get("clicks", 0),
                    "ctr": google_stats.get("ctr", 0),
                    "currency": google_stats.get("currency", "ARS"),
                    "is_demo": google_stats.get("is_demo", False)
                },
                "combined": {
                    "total_spend": total_spend,
                    "total_revenue": total_revenue,
                    "total_leads": total_leads,
                    "roi_percentage": round(combined_roi, 2),
                    "platforms": []
                },
                "time_range": time_range
            }
            
        except Exception as e:
            logger.error(f"Failed to get combined marketing stats: {e}")
            return {
                "meta": {"is_connected": False},
                "google": {"is_connected": False},
                "combined": {"platforms": []},
                "time_range": time_range
            }

    @staticmethod
    async def get_multi_platform_campaigns(tenant_id: int, time_range: str = "last_30d") -> Dict[str, Any]:
        """
        Get campaigns from all platforms (Meta + Google)
        
        Args:
            tenant_id: Tenant ID
            time_range: Time range for metrics
            
        Returns:
            Campaigns from all platforms
        """
        try:
            # Get Meta campaigns
            meta_campaigns = await MarketingService.get_campaign_stats(tenant_id, time_range)
            
            # Get Google campaigns if available
            google_campaigns = []
            try:
                from services.marketing.google_ads_service import GoogleAdsService
                google_campaigns = await GoogleAdsService.get_campaigns(tenant_id, time_range)
            except ImportError:
                logger.warning("Google Ads service not available")
            except Exception as e:
                logger.warning(f"Failed to get Google campaigns: {e}")
            
            # Format campaigns consistently
            formatted_meta_campaigns = []
            if "campaigns" in meta_campaigns:
                for campaign in meta_campaigns["campaigns"]:
                    formatted_meta_campaigns.append({
                        "id": campaign.get("ad_id", ""),
                        "name": campaign.get("campaign_name", ""),
                        "platform": "meta",
                        "status": campaign.get("status", ""),
                        "spend": campaign.get("spend", 0),
                        "leads": campaign.get("leads", 0),
                        "appointments": campaign.get("appointments", 0),
                        "roi": campaign.get("roi", 0),
                        "impressions": campaign.get("impressions", 0),
                        "clicks": campaign.get("clicks", 0),
                        "ctr": campaign.get("ctr", 0)
                    })
            
            formatted_google_campaigns = []
            for campaign in google_campaigns:
                formatted_google_campaigns.append({
                    "id": campaign.get("id", ""),
                    "name": campaign.get("name", ""),
                    "platform": "google",
                    "status": campaign.get("status", ""),
                    "spend": campaign.get("cost", 0) / 1000000 if campaign.get("cost") else 0,  # Convert micros
                    "leads": campaign.get("conversions", 0),
                    "appointments": 0,  # Google doesn't have appointments metric
                    "roi": campaign.get("roas", 0),
                    "impressions": campaign.get("impressions", 0),
                    "clicks": campaign.get("clicks", 0),
                    "ctr": campaign.get("ctr", 0),
                    "conversion_rate": campaign.get("conversion_rate", 0),
                    "cpc": campaign.get("cpc", 0)
                })
            
            # Combine all campaigns
            all_campaigns = formatted_meta_campaigns + formatted_google_campaigns
            
            return {
                "campaigns": all_campaigns,
                "meta_count": len(formatted_meta_campaigns),
                "google_count": len(formatted_google_campaigns),
                "total_count": len(all_campaigns),
                "time_range": time_range
            }
            
        except Exception as e:
            logger.error(f"Failed to get multi-platform campaigns: {e}")
            return {
                "campaigns": [],
                "meta_count": 0,
                "google_count": 0,
                "total_count": 0,
                "time_range": time_range
            }
