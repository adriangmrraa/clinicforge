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
            total_spend = 1500.0  # Placeholder: USD/ARS 1500
            
            # 5. Verificar conexión real y cuenta seleccionada
            from core.credentials import get_tenant_credential
            token = await get_tenant_credential(tenant_id, "META_USER_LONG_TOKEN")
            ad_account_id = await get_tenant_credential(tenant_id, "META_AD_ACCOUNT_ID")
            
            cpa = total_spend / meta_leads if meta_leads > 0 else 0

            return {
                "total_spend": total_spend,
                "total_revenue": float(total_revenue),
                "leads": meta_leads,
                "patients_converted": converted_patients,
                "cpa": cpa,
                "is_connected": bool(token),
                "ad_account_id": ad_account_id,
                "currency": "ARS" # Default
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
        Retorna el rendimiento por campaña/anuncio.
        """
        # Mocking campaign data until Meta API sync is implemented in Mission 3
        # Pero calculamos la parte de 'appointments' y 'roi' real de la base de datos
        
        # 1. Obtener datos de atribución reales por campaña
        ad_attribution = await db.pool.fetch("""
            SELECT meta_ad_id, meta_ad_headline, 
                   COUNT(id) as leads,
                   COUNT(id) FILTER (WHERE EXISTS (SELECT 1 FROM appointments a WHERE a.patient_id = patients.id AND a.status IN ('confirmed', 'completed'))) as appointments
            FROM patients
            WHERE tenant_id = $1 AND acquisition_source = 'META_ADS' AND meta_ad_id IS NOT NULL
            GROUP BY meta_ad_id, meta_ad_headline
        """, tenant_id)

        campaigns = []
        for row in ad_attribution:
            # Mock spend per ad for demo purposes
            mock_spend = 120.50
            rev = await db.pool.fetchval("""
                SELECT SUM(amount) FROM accounting_transactions t
                JOIN patients p ON t.patient_id = p.id
                WHERE p.meta_ad_id = $1 AND t.status = 'completed'
            """, row['meta_ad_id']) or 0
            
            roi = (float(rev) - mock_spend) / mock_spend if mock_spend > 0 else 0

            campaigns.append({
                "ad_id": row['meta_ad_id'],
                "ad_name": row['meta_ad_headline'] or "Anuncio de Meta",
                "campaign_name": "Campaña de Implantología",
                "spend": mock_spend,
                "leads": row['leads'],
                "appointments": row['appointments'],
                "roi": roi
            })
        
        if not campaigns:
            # Fallback mock for UI demonstration if no real data exists yet
            campaigns = [
                {
                    "ad_id": "meta_123",
                    "ad_name": "Consulta Estética Gratis",
                    "campaign_name": "Captación Invierno",
                    "spend": 450.0,
                    "leads": 24,
                    "appointments": 8,
                    "roi": 1.5
                },
                {
                    "ad_id": "meta_456",
                    "ad_name": "Video Ortodoncia Invisible",
                    "campaign_name": "Ortodoncia Youth",
                    "spend": 320.0,
                    "leads": 15,
                    "appointments": 4,
                    "roi": 0.8
                }
            ]

        return campaigns
