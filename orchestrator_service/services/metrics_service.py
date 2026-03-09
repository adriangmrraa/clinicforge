"""
Metrics Service for ClinicForge
Unified metrics calculation for Meta Ads attribution (WhatsApp referrals + Leads Forms)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from db import db

logger = logging.getLogger(__name__)


class AttributionType(Enum):
    """Types of attribution for metrics calculation"""
    FIRST_TOUCH = "first_touch"
    LAST_TOUCH = "last_touch"
    CONVERSION = "conversion"


class MetricPeriod(Enum):
    """Time periods for metrics aggregation"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class MetricsService:
    """Service for unified metrics calculation"""
    
    @staticmethod
    async def get_campaign_metrics(
        tenant_id: int,
        period: MetricPeriod = MetricPeriod.MONTHLY,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        attribution_type: AttributionType = AttributionType.FIRST_TOUCH
    ) -> Dict[str, Any]:
        """
        Get unified campaign metrics combining WhatsApp referrals and Leads Forms
        
        Args:
            tenant_id: Tenant ID
            period: Aggregation period
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            attribution_type: Type of attribution to use
            
        Returns:
            Dict with campaign metrics
        """
        try:
            # Determine date range
            date_range = await MetricsService._get_date_range(period, date_from, date_to)
            
            # Get metrics from different sources
            whatsapp_metrics = await MetricsService._get_whatsapp_campaign_metrics(
                tenant_id, date_range, attribution_type
            )
            
            leads_metrics = await MetricsService._get_leads_campaign_metrics(
                tenant_id, date_range
            )
            
            # Combine and unify metrics
            unified_metrics = await MetricsService._unify_campaign_metrics(
                whatsapp_metrics, leads_metrics, attribution_type
            )
            
            # Calculate ROI and other derived metrics
            enriched_metrics = await MetricsService._enrich_metrics_with_roi(
                unified_metrics, tenant_id
            )
            
            return {
                "success": True,
                "period": period.value,
                "date_range": date_range,
                "attribution_type": attribution_type.value,
                "metrics": enriched_metrics,
                "summary": await MetricsService._calculate_summary(enriched_metrics)
            }
            
        except Exception as e:
            logger.error(f"Error getting campaign metrics: {e}")
            raise
    
    @staticmethod
    async def _get_date_range(
        period: MetricPeriod,
        date_from: Optional[str],
        date_to: Optional[str]
    ) -> Dict[str, str]:
        """Calculate date range based on period"""
        today = datetime.utcnow().date()
        
        if date_from and date_to:
            return {"from": date_from, "to": date_to}
        
        if period == MetricPeriod.DAILY:
            start_date = today
        elif period == MetricPeriod.WEEKLY:
            start_date = today - timedelta(days=7)
        elif period == MetricPeriod.MONTHLY:
            start_date = today - timedelta(days=30)
        elif period == MetricPeriod.QUARTERLY:
            start_date = today - timedelta(days=90)
        elif period == MetricPeriod.YEARLY:
            start_date = today - timedelta(days=365)
        else:
            start_date = today - timedelta(days=30)
        
        return {
            "from": start_date.isoformat(),
            "to": today.isoformat()
        }
    
    @staticmethod
    async def _get_whatsapp_campaign_metrics(
        tenant_id: int,
        date_range: Dict[str, str],
        attribution_type: AttributionType
    ) -> List[Dict[str, Any]]:
        """Get campaign metrics from WhatsApp referrals"""
        
        # Determine which fields to use based on attribution type
        if attribution_type == AttributionType.FIRST_TOUCH:
            ad_id_field = "first_touch_ad_id"
            ad_name_field = "first_touch_ad_name"
            campaign_id_field = "first_touch_campaign_id"
            campaign_name_field = "first_touch_campaign_name"
            source_field = "first_touch_source"
        else:  # LAST_TOUCH
            ad_id_field = "last_touch_ad_id"
            ad_name_field = "last_touch_ad_name"
            campaign_id_field = "last_touch_campaign_id"
            campaign_name_field = "last_touch_campaign_name"
            source_field = "last_touch_source"
        
        query = f"""
            SELECT 
                COALESCE({campaign_id_field}, 'unknown') as campaign_id,
                COALESCE({campaign_name_field}, 'Unknown Campaign') as campaign_name,
                COALESCE({ad_id_field}, 'unknown') as ad_id,
                COALESCE({ad_name_field}, 'Unknown Ad') as ad_name,
                COUNT(*) as total_patients,
                COUNT(DISTINCT id) as unique_patients,
                MIN(created_at) as first_interaction,
                MAX(created_at) as last_interaction
            FROM patients 
            WHERE tenant_id = $1
            AND created_at >= $2::timestamp
            AND created_at <= $3::timestamp
            AND {source_field} = 'META_ADS'
            GROUP BY {campaign_id_field}, {campaign_name_field}, {ad_id_field}, {ad_name_field}
            ORDER BY total_patients DESC
        """
        
        try:
            results = await db.pool.fetch(
                query, tenant_id, date_range["from"], date_range["to"]
            )
            
            metrics = []
            for row in results:
                metrics.append({
                    "source": "whatsapp",
                    "campaign_id": row["campaign_id"],
                    "campaign_name": row["campaign_name"],
                    "ad_id": row["ad_id"],
                    "ad_name": row["ad_name"],
                    "total_patients": row["total_patients"],
                    "unique_patients": row["unique_patients"],
                    "first_interaction": row["first_interaction"].isoformat() if row["first_interaction"] else None,
                    "last_interaction": row["last_interaction"].isoformat() if row["last_interaction"] else None,
                    "conversions": 0,  # WhatsApp doesn't have separate conversion tracking
                    "conversion_rate": 0
                })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting WhatsApp metrics: {e}")
            return []
    
    @staticmethod
    async def _get_leads_campaign_metrics(
        tenant_id: int,
        date_range: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Get campaign metrics from Leads Forms"""
        
        query = """
            SELECT 
                COALESCE(campaign_id, 'unknown') as campaign_id,
                COALESCE(campaign_name, 'Unknown Campaign') as campaign_name,
                COALESCE(ad_id, 'unknown') as ad_id,
                COALESCE(ad_name, 'Unknown Ad') as ad_name,
                COUNT(*) as total_leads,
                COUNT(DISTINCT id) as unique_leads,
                SUM(CASE WHEN status = 'converted' THEN 1 ELSE 0 END) as converted_leads,
                MIN(created_at) as first_lead,
                MAX(created_at) as last_lead
            FROM meta_form_leads 
            WHERE tenant_id = $1
            AND created_at >= $2::timestamp
            AND created_at <= $3::timestamp
            GROUP BY campaign_id, campaign_name, ad_id, ad_name
            ORDER BY total_leads DESC
        """
        
        try:
            results = await db.pool.fetch(
                query, tenant_id, date_range["from"], date_range["to"]
            )
            
            metrics = []
            for row in results:
                total_leads = row["total_leads"] or 0
                converted_leads = row["converted_leads"] or 0
                conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
                
                metrics.append({
                    "source": "leads_form",
                    "campaign_id": row["campaign_id"],
                    "campaign_name": row["campaign_name"],
                    "ad_id": row["ad_id"],
                    "ad_name": row["ad_name"],
                    "total_leads": total_leads,
                    "unique_leads": row["unique_leads"],
                    "converted_leads": converted_leads,
                    "conversion_rate": round(conversion_rate, 2),
                    "first_lead": row["first_lead"].isoformat() if row["first_lead"] else None,
                    "last_lead": row["last_lead"].isoformat() if row["last_lead"] else None
                })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting Leads metrics: {e}")
            return []
    
    @staticmethod
    async def _unify_campaign_metrics(
        whatsapp_metrics: List[Dict[str, Any]],
        leads_metrics: List[Dict[str, Any]],
        attribution_type: AttributionType
    ) -> List[Dict[str, Any]]:
        """Unify metrics from different sources"""
        
        # Create a dictionary keyed by campaign_id + ad_id
        unified_dict = {}
        
        # Process WhatsApp metrics
        for metric in whatsapp_metrics:
            key = f"{metric['campaign_id']}_{metric['ad_id']}"
            unified_dict[key] = {
                "campaign_id": metric["campaign_id"],
                "campaign_name": metric["campaign_name"],
                "ad_id": metric["ad_id"],
                "ad_name": metric["ad_name"],
                "whatsapp_patients": metric["total_patients"],
                "whatsapp_unique_patients": metric["unique_patients"],
                "leads_total": 0,
                "leads_converted": 0,
                "leads_conversion_rate": 0,
                "total_patients": metric["total_patients"],  # WhatsApp patients
                "total_conversions": 0,  # Will be updated with leads conversions
                "sources": ["whatsapp"]
            }
        
        # Process Leads metrics
        for metric in leads_metrics:
            key = f"{metric['campaign_id']}_{metric['ad_id']}"
            
            if key in unified_dict:
                # Update existing entry
                unified_dict[key]["leads_total"] = metric["total_leads"]
                unified_dict[key]["leads_converted"] = metric["converted_leads"]
                unified_dict[key]["leads_conversion_rate"] = metric["conversion_rate"]
                unified_dict[key]["total_conversions"] = metric["converted_leads"]
                unified_dict[key]["sources"].append("leads_form")
            else:
                # Create new entry
                unified_dict[key] = {
                    "campaign_id": metric["campaign_id"],
                    "campaign_name": metric["campaign_name"],
                    "ad_id": metric["ad_id"],
                    "ad_name": metric["ad_name"],
                    "whatsapp_patients": 0,
                    "whatsapp_unique_patients": 0,
                    "leads_total": metric["total_leads"],
                    "leads_converted": metric["converted_leads"],
                    "leads_conversion_rate": metric["conversion_rate"],
                    "total_patients": 0,  # No WhatsApp patients
                    "total_conversions": metric["converted_leads"],
                    "sources": ["leads_form"]
                }
        
        # Convert to list and calculate derived metrics
        unified_list = []
        for key, metric in unified_dict.items():
            # Calculate overall metrics
            total_patients = metric["whatsapp_patients"] + metric["leads_converted"]
            total_interactions = metric["whatsapp_patients"] + metric["leads_total"]
            
            # Calculate overall conversion rate
            if total_interactions > 0:
                overall_conversion_rate = (total_patients / total_interactions * 100)
            else:
                overall_conversion_rate = 0
            
            unified_list.append({
                **metric,
                "total_patients": total_patients,
                "total_interactions": total_interactions,
                "overall_conversion_rate": round(overall_conversion_rate, 2),
                "attribution_type": attribution_type.value
            })
        
        # Sort by total patients (descending)
        unified_list.sort(key=lambda x: x["total_patients"], reverse=True)
        
        return unified_list
    
    @staticmethod
    async def _enrich_metrics_with_roi(
        metrics: List[Dict[str, Any]],
        tenant_id: int
    ) -> List[Dict[str, Any]]:
        """Enrich metrics with ROI calculations"""
        
        # TODO: Integrate with Meta Ads API to get actual spend data
        # For now, use placeholder ROI calculations
        
        enriched_metrics = []
        for metric in metrics:
            # Placeholder ROI calculation
            # In production, this would fetch actual spend from Meta API
            estimated_spend = 100  # Placeholder
            estimated_value_per_patient = 500  # Placeholder (average patient value)
            
            total_value = metric["total_patients"] * estimated_value_per_patient
            roi = ((total_value - estimated_spend) / estimated_spend * 100) if estimated_spend > 0 else 0
            
            enriched_metrics.append({
                **metric,
                "estimated_spend": estimated_spend,
                "estimated_value_per_patient": estimated_value_per_patient,
                "total_estimated_value": total_value,
                "estimated_roi": round(roi, 2),
                "cost_per_patient": round(estimated_spend / metric["total_patients"], 2) if metric["total_patients"] > 0 else 0
            })
        
        return enriched_metrics
    
    @staticmethod
    async def _calculate_summary(metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate summary statistics"""
        
        if not metrics:
            return {
                "total_campaigns": 0,
                "total_patients": 0,
                "total_interactions": 0,
                "average_conversion_rate": 0,
                "total_estimated_value": 0,
                "total_estimated_spend": 0,
                "average_roi": 0
            }
        
        total_campaigns = len(metrics)
        total_patients = sum(m["total_patients"] for m in metrics)
        total_interactions = sum(m["total_interactions"] for m in metrics)
        total_estimated_value = sum(m["total_estimated_value"] for m in metrics)
        total_estimated_spend = sum(m["estimated_spend"] for m in metrics)
        
        # Calculate average conversion rate
        if total_interactions > 0:
            avg_conversion_rate = (total_patients / total_interactions * 100)
        else:
            avg_conversion_rate = 0
        
        # Calculate average ROI
        if total_estimated_spend > 0:
            avg_roi = ((total_estimated_value - total_estimated_spend) / total_estimated_spend * 100)
        else:
            avg_roi = 0
        
        return {
            "total_campaigns": total_campaigns,
            "total_patients": total_patients,
            "total_interactions": total_interactions,
            "average_conversion_rate": round(avg_conversion_rate, 2),
            "total_estimated_value": total_estimated_value,
            "total_estimated_spend": total_estimated_spend,
            "average_roi": round(avg_roi, 2),
            "cost_per_patient": round(total_estimated_spend / total_patients, 2) if total_patients > 0 else 0
        }
    
    @staticmethod
    async def get_detailed_attribution_report(
        tenant_id: int,
        campaign_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get detailed attribution report showing patient journey
        
        Args:
            tenant_id: Tenant ID
            campaign_id: Optional campaign ID filter
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            
        Returns:
            Detailed attribution report
        """
        
        # Build query conditions
        conditions = ["p.tenant_id = $1"]
        params = [tenant_id]
        param_count = 1
        
        if date_from:
            param_count += 1
            conditions.append(f"p.created_at >= ${param_count}::timestamp")
            params.append(date_from)
        
        if date_to:
            param_count += 1
            conditions.append(f"p.created_at <= ${param_count}::timestamp")
            params.append(date_to)
        
        if campaign_id:
            param_count += 1
            conditions.append(f"(p.first_touch_campaign_id = ${param_count} OR p.last_touch_campaign_id = ${param_count})")
            params.append(campaign_id)
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT 
                p.id as patient_id,
                p.full_name,
                p.phone_number,
                p.email,
                p.created_at as patient_created,
                
                -- First Touch Attribution
                p.first_touch_source,
                p.first_touch_ad_id,
                p.first_touch_ad_name,
                p.first_touch_campaign_id,
                p.first_touch_campaign_name,
                p.first_touch_ad_headline,
                p.first_touch_ad_body,
                
                -- Last Touch Attribution
                p.last_touch_source,
                p.last_touch_ad_id,
                p.last_touch_ad_name,
                p.last_touch_campaign_id,
                p.last_touch_campaign_name,
                p.last_touch_timestamp,
                
                -- Conversion Attribution (from leads forms)
                mfl.id as lead_id,
                mfl.ad_id as conversion_ad_id,
                mfl.ad_name as conversion_ad_name,
                mfl.campaign_id as conversion_campaign_id,
                mfl.campaign_name as conversion_campaign_name,
                mfl.status as lead_status,
                mfl.converted_at as conversion_timestamp,
                
                -- Attribution History Count
                (SELECT COUNT(*) FROM patient_attribution_history pah 
                 WHERE pah.patient_id = p.id AND pah.tenant_id = p.tenant_id) as attribution_events_count
                
            FROM patients p
            LEFT JOIN meta_form_leads mfl ON p.id = mfl.converted_to_patient_id AND p.tenant_id = mfl.tenant_id
            WHERE {where_clause}
            ORDER BY p.created_at DESC
            LIMIT 100
        """
        
        try:
            results = await db.pool.fetch(query, *params)
            
            patients = []
            for row in results:
                patient = {
                    "patient_id": row["patient_id"],
                    "full_name": row["full_name"],
                    "phone_number": row["phone_number"],
                    "email": row["email"],
                    "patient_created": row["patient_created"].isoformat() if row["patient_created"] else None,
                    
                    "first_touch": {
                        "source": row["first_touch_source"],
                        "ad_id": row["first_touch_ad_id"],
                        "ad_name": row["first_touch_ad_name"],
                        "campaign_id": row["first_touch_campaign_id"],
                        "campaign_name": row["first_touch_campaign_name"],
                        "headline": row["first_touch_ad_headline"],
                        "body": row["first_touch_ad_body"]
                    } if row["first_touch_source"] else None,
                    
                    "last_touch": {
                        "source": row["last_touch_source"],
                        "ad_id": row["last_touch_ad_id"],
                        "ad_name": row["last_touch_ad_name"],
                        "campaign_id": row["last_touch_campaign_id"],
                        "campaign_name": row["last_touch_campaign_name"],
                        "timestamp": row["last_touch_timestamp"].isoformat() if row["last_touch_timestamp"] else None
                    } if row["last_touch_source"] else None,
                    
                    "conversion": {
                        "lead_id": row["lead_id"],
                        "ad_id": row["conversion_ad_id"],
                        "ad_name": row["conversion_ad_name"],
                        "campaign_id": row["conversion_campaign_id"],
                        "campaign_name": row["conversion_campaign_name"],
                        "status": row["lead_status"],
                        "timestamp": row["conversion_timestamp"].isoformat() if row["conversion_timestamp"] else None
                    } if row["lead_id"] else None,
                    
                    "attribution_events_count": row["attribution_events_count"]
                }
                
                # Determine attribution path
                attribution_path = []
                if patient["first_touch"]:
                    attribution_path.append(f"First: {patient['first_touch']['source']}")
                if patient["last_touch"] and patient["last_touch"] != patient["first_touch"]:
                    attribution_path.append(f"Last: {patient['last_touch']['source']}")
                if patient["conversion"]:
                    attribution_path.append(f"Converted: {patient['conversion']['status']}")
                
                patient["attribution_path"] = " → ".join(attribution_path) if attribution_path else "Organic"
                patients.append(patient)
            
            # Get attribution history for the first few patients
            if patients:
                patient_ids = [p["patient_id"] for p in patients[:5]]
                history_query = """
                    SELECT * FROM patient_attribution_history 
                    WHERE patient_id = ANY($1) AND tenant_id = $2
                    ORDER BY event_timestamp DESC
                """
                history_results = await db.pool.fetch(history_query, patient_ids, tenant_id)
                
                # Group history by patient
                history_by_patient = {}
                for row in history_results:
                    patient_id = row["patient_id"]
                    if patient_id not in history_by_patient:
                        history_by_patient[patient_id] = []
                    
                    history_by_patient[patient_id].append({
                        "attribution_type": row["attribution_type"],
                        "source": row["source"],
                        "ad_name": row["ad_name"],
                        "campaign_name": row["campaign_name"],
                        "event_timestamp": row["event_timestamp"].isoformat() if row["event_timestamp"] else None,
                        "event_description": row["event_description"]
                    })
            
            return {
                "success": True,
                "total_patients": len(patients),
                "patients": patients,
                "sample_attribution_history": history_by_patient if patients else {}
            }
            
        except Exception as e:
            logger.error(f"Error getting detailed attribution report: {e}")
            raise
    
    @staticmethod
    async def get_roi_dashboard(
        tenant_id: int,
        period: MetricPeriod = MetricPeriod.MONTHLY
    ) -> Dict[str, Any]:
        """
        Get ROI dashboard with key metrics
        
        Args:
            tenant_id: Tenant ID
            period: Time period for metrics
            
        Returns:
            ROI dashboard data
        """
        
        try:
            # Get metrics for different attribution types
            first_touch_metrics = await MetricsService.get_campaign_metrics(
                tenant_id, period, attribution_type=AttributionType.FIRST_TOUCH
            )
            
            last_touch_metrics = await MetricsService.get_campaign_metrics(
                tenant_id, period, attribution_type=AttributionType.LAST_TOUCH
            )
            
            # Calculate trend data
            trend_data = await MetricsService._get_trend_data(tenant_id, period)
            
            # Get top performing campaigns
            top_campaigns = await MetricsService._get_top_campaigns(tenant_id, period)
            
            # Get attribution mix
            attribution_mix = await MetricsService._get_attribution_mix(tenant_id, period)
            
            return {
                "success": True,
                "period": period.value,
                "first_touch_metrics": first_touch_metrics.get("summary", {}),
                "last_touch_metrics": last_touch_metrics.get("summary", {}),
                "trend_data": trend_data,
                "top_campaigns": top_campaigns,
                "attribution_mix": attribution_mix,
                "comparison": {
                    "attribution_difference": {
                        "patients": last_touch_metrics.get("summary", {}).get("total_patients", 0) - 
                                   first_touch_metrics.get("summary", {}).get("total_patients", 0),
                        "conversion_rate": round(
                            last_touch_metrics.get("summary", {}).get("average_conversion_rate", 0) - 
                            first_touch_metrics.get("summary", {}).get("average_conversion_rate", 0), 2
                        )
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting ROI dashboard: {e}")
            raise
    
    @staticmethod
    async def _get_trend_data(
        tenant_id: int,
        period: MetricPeriod
    ) -> List[Dict[str, Any]]:
        """Get trend data over time"""
        
        # Determine interval based on period
        if period == MetricPeriod.DAILY:
            interval = "1 day"
            date_format = "YYYY-MM-DD"
        elif period == MetricPeriod.WEEKLY:
            interval = "1 week"
            date_format = "YYYY-WW"
        elif period == MetricPeriod.MONTHLY:
            interval = "1 month"
            date_format = "YYYY-MM"
        else:
            interval = "1 month"
            date_format = "YYYY-MM"
        
        query = f"""
            WITH date_series AS (
                SELECT generate_series(
                    NOW() - INTERVAL '90 days',
                    NOW(),
                    INTERVAL '{interval}'
                ) as date
            )
            SELECT 
                TO_CHAR(ds.date, '{date_format}') as period,
                COUNT(DISTINCT p.id) as total_patients,
                COUNT(DISTINCT CASE WHEN p.first_touch_source = 'META_ADS' THEN p.id END) as first_touch_patients,
                COUNT(DISTINCT CASE WHEN p.last_touch_source = 'META_ADS' THEN p.id END) as last_touch_patients,
                COUNT(DISTINCT mfl.id) as total_leads,
                COUNT(DISTINCT CASE WHEN mfl.status = 'converted' THEN mfl.id END) as converted_leads
            FROM date_series ds
            LEFT JOIN patients p ON DATE(p.created_at) = DATE(ds.date) AND p.tenant_id = $1
            LEFT JOIN meta_form_leads mfl ON DATE(mfl.created_at) = DATE(ds.date) AND mfl.tenant_id = $1
            GROUP BY TO_CHAR(ds.date, '{date_format}')
            ORDER BY MIN(ds.date)
        """
        
        try:
            results = await db.pool.fetch(query, tenant_id)
            
            trend_data = []
            for row in results:
                trend_data.append({
                    "period": row["period"],
                    "total_patients": row["total_patients"] or 0,
                    "first_touch_patients": row["first_touch_patients"] or 0,
                    "last_touch_patients": row["last_touch_patients"] or 0,
                    "total_leads": row["total_leads"] or 0,
                    "converted_leads": row["converted_leads"] or 0,
                    "conversion_rate": round(
                        (row["converted_leads"] / row["total_leads"] * 100) if row["total_leads"] > 0 else 0, 2
                    )
                })
            
            return trend_data
            
        except Exception as e:
            logger.error(f"Error getting trend data: {e}")
            return []
    
    @staticmethod
    async def _get_top_campaigns(
        tenant_id: int,
        period: MetricPeriod
    ) -> List[Dict[str, Any]]:
        """Get top performing campaigns"""
        
        date_range = await MetricsService._get_date_range(period, None, None)
        
        query = """
            WITH campaign_stats AS (
                -- WhatsApp patients (first touch)
                SELECT 
                    first_touch_campaign_id as campaign_id,
                    first_touch_campaign_name as campaign_name,
                    COUNT(*) as whatsapp_patients,
                    0 as leads_total,
                    0 as leads_converted
                FROM patients 
                WHERE tenant_id = $1
                AND created_at >= $2::timestamp
                AND created_at <= $3::timestamp
                AND first_touch_source = 'META_ADS'
                GROUP BY first_touch_campaign_id, first_touch_campaign_name
                
                UNION ALL
                
                -- Leads forms
                SELECT 
                    campaign_id,
                    campaign_name,
                    0 as whatsapp_patients,
                    COUNT(*) as leads_total,
                    SUM(CASE WHEN status = 'converted' THEN 1 ELSE 0 END) as leads_converted
                FROM meta_form_leads 
                WHERE tenant_id = $1
                AND created_at >= $2::timestamp
                AND created_at <= $3::timestamp
                GROUP BY campaign_id, campaign_name
            )
            SELECT 
                COALESCE(campaign_id, 'unknown') as campaign_id,
                COALESCE(campaign_name, 'Unknown Campaign') as campaign_name,
                SUM(whatsapp_patients) as total_whatsapp_patients,
                SUM(leads_total) as total_leads,
                SUM(leads_converted) as total_converted_leads,
                (SUM(whatsapp_patients) + SUM(leads_converted)) as total_patients
            FROM campaign_stats
            GROUP BY campaign_id, campaign_name
            ORDER BY total_patients DESC
            LIMIT 10
        """
        
        try:
            results = await db.pool.fetch(
                query, tenant_id, date_range["from"], date_range["to"]
            )
            
            top_campaigns = []
            for row in results:
                total_interactions = row["total_whatsapp_patients"] + row["total_leads"]
                conversion_rate = (
                    (row["total_patients"] / total_interactions * 100) 
                    if total_interactions > 0 else 0
                )
                
                top_campaigns.append({
                    "campaign_id": row["campaign_id"],
                    "campaign_name": row["campaign_name"],
                    "whatsapp_patients": row["total_whatsapp_patients"],
                    "total_leads": row["total_leads"],
                    "converted_leads": row["total_converted_leads"],
                    "total_patients": row["total_patients"],
                    "conversion_rate": round(conversion_rate, 2),
                    "sources": []
                })
            
            return top_campaigns
            
        except Exception as e:
            logger.error(f"Error getting top campaigns: {e}")
            return []
    
    @staticmethod
    async def _get_attribution_mix(
        tenant_id: int,
        period: MetricPeriod
    ) -> Dict[str, Any]:
        """Get attribution mix (first touch vs last touch vs conversion)"""
        
        date_range = await MetricsService._get_date_range(period, None, None)
        
        query = """
            SELECT 
                -- First touch attribution
                COUNT(DISTINCT CASE WHEN first_touch_source = 'META_ADS' THEN id END) as first_touch_patients,
                
                -- Last touch attribution
                COUNT(DISTINCT CASE WHEN last_touch_source = 'META_ADS' THEN id END) as last_touch_patients,
                
                -- Both first and last touch
                COUNT(DISTINCT CASE WHEN first_touch_source = 'META_ADS' AND last_touch_source = 'META_ADS' THEN id END) as both_touch_patients,
                
                -- Conversion attribution (from leads)
                COUNT(DISTINCT mfl.converted_to_patient_id) as conversion_patients,
                
                -- Total patients in period
                COUNT(DISTINCT id) as total_patients
                
            FROM patients p
            LEFT JOIN meta_form_leads mfl ON p.id = mfl.converted_to_patient_id AND p.tenant_id = mfl.tenant_id
            WHERE p.tenant_id = $1
            AND p.created_at >= $2::timestamp
            AND p.created_at <= $3::timestamp
        """
        
        try:
            result = await db.pool.fetchrow(
                query, tenant_id, date_range["from"], date_range["to"]
            )
            
            if not result:
                return {}
            
            total_patients = result["total_patients"] or 0
            
            if total_patients == 0:
                return {
                    "first_touch_percentage": 0,
                    "last_touch_percentage": 0,
                    "both_touch_percentage": 0,
                    "conversion_percentage": 0,
                    "organic_percentage": 100
                }
            
            first_touch_patients = result["first_touch_patients"] or 0
            last_touch_patients = result["last_touch_patients"] or 0
            both_touch_patients = result["both_touch_patients"] or 0
            conversion_patients = result["conversion_patients"] or 0
            
            # Calculate percentages
            first_touch_percentage = (first_touch_patients / total_patients * 100)
            last_touch_percentage = (last_touch_patients / total_patients * 100)
            both_touch_percentage = (both_touch_patients / total_patients * 100)
            conversion_percentage = (conversion_patients / total_patients * 100)
            
            # Organic = total - attributed
            attributed_patients = first_touch_patients + last_touch_patients - both_touch_patients
            organic_patients = total_patients - attributed_patients
            organic_percentage = (organic_patients / total_patients * 100)
            
            return {
                "first_touch_percentage": round(first_touch_percentage, 2),
                "last_touch_percentage": round(last_touch_percentage, 2),
                "both_touch_percentage": round(both_touch_percentage, 2),
                "conversion_percentage": round(conversion_percentage, 2),
                "organic_percentage": round(organic_percentage, 2),
                "total_patients": total_patients,
                "attributed_patients": attributed_patients,
                "organic_patients": organic_patients
            }
            
        except Exception as e:
            logger.error(f"Error getting attribution mix: {e}")
            return {}