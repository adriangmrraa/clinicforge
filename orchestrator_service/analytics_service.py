import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from db import db

logger = logging.getLogger("analytics")

class AnalyticsService:
    async def get_professionals_summary(
        self, 
        start_date: datetime, 
        end_date: datetime, 
        tenant_id: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Calculates performance metrics for all professionals within the given date range.
        Using REAL data from appointments, patients, and clinical records.
        """
        try:
            # 1. Fetch basic professional info (solo profesionales dentales, no secretarias)
            professionals = await db.pool.fetch("""
                SELECT p.id, p.first_name, p.last_name, p.specialty, p.google_calendar_id 
                FROM professionals p
                INNER JOIN users u ON p.user_id = u.id AND u.role = 'professional'
                WHERE p.is_active = true AND p.tenant_id = $1
            """, tenant_id)

            results = []

            for prof in professionals:
                prof_id = prof['id']
                full_name = f"{prof['first_name']} {prof['last_name'] or ''}".strip()
                
                # 2. Aggregations from APPOINTMENTS
                # Status counts
                stats = await db.pool.fetchrow("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'completed') as completed,
                        COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
                        COUNT(*) FILTER (WHERE status = 'no_show') as no_show,
                        COUNT(DISTINCT patient_id) as unique_patients
                    FROM appointments
                    WHERE professional_id = $1
                    AND appointment_datetime BETWEEN $2 AND $3
                    AND tenant_id = $4
                """, prof_id, start_date, end_date, tenant_id)

                total_apts = stats['total'] or 0
                completed_apts = stats['completed'] or 0
                cancelled_apts = stats['cancelled'] or 0
                
                # Rates
                completion_rate = (completed_apts / total_apts) * 100 if total_apts > 0 else 0
                cancellation_rate = (cancelled_apts / total_apts) * 100 if total_apts > 0 else 0

                # 3. Revenue Estimation — multi-source: billing_amount > treatment base_price > clinical_records
                revenue_row = await db.pool.fetchrow("""
                    SELECT
                        COALESCE(SUM(
                            CASE
                                WHEN a.billing_amount IS NOT NULL AND a.billing_amount > 0 THEN a.billing_amount
                                WHEN tt.base_price IS NOT NULL AND tt.base_price > 0 THEN tt.base_price
                                ELSE 0
                            END
                        ), 0) as total_revenue,
                        COUNT(*) FILTER (WHERE a.payment_status = 'paid') as paid_count,
                        COUNT(*) FILTER (WHERE a.payment_status = 'partial') as partial_count,
                        COUNT(*) FILTER (WHERE a.billing_amount > 0) as with_billing
                    FROM appointments a
                    LEFT JOIN treatment_types tt ON a.appointment_type = tt.code AND tt.tenant_id = a.tenant_id
                    WHERE a.professional_id = $1
                    AND a.appointment_datetime BETWEEN $2 AND $3
                    AND a.tenant_id = $4
                    AND a.status IN ('completed', 'confirmed', 'scheduled')
                """, prof_id, start_date, end_date, tenant_id)
                estimated_revenue = float(revenue_row['total_revenue'] or 0)

                # 4. Retention Analysis (Patients seen in this period who had prior visits)
                # "Returning Patient": A patient who has an appointment BEFORE start_date
                returning_patients_count = await db.pool.fetchval("""
                    SELECT COUNT(DISTINCT patient_id)
                    FROM appointments a1
                    WHERE professional_id = $1
                    AND appointment_datetime BETWEEN $2 AND $3
                    AND EXISTS (
                        SELECT 1 FROM appointments a2
                        WHERE a2.patient_id = a1.patient_id
                        AND a2.appointment_datetime < $2
                    )
                """, prof_id, start_date, end_date)
                
                retention_rate = (returning_patients_count / stats['unique_patients']) * 100 if stats['unique_patients'] > 0 else 0

                no_show_count = stats['no_show'] or 0
                no_show_rate = (no_show_count / total_apts) * 100 if total_apts > 0 else 0
                avg_revenue = estimated_revenue / total_apts if total_apts > 0 else 0

                # 5. Top treatment for this professional
                top_treatment = await db.pool.fetchrow("""
                    SELECT a.appointment_type, tt.name, COUNT(*) as cnt
                    FROM appointments a
                    LEFT JOIN treatment_types tt ON a.appointment_type = tt.code AND tt.tenant_id = a.tenant_id
                    WHERE a.professional_id = $1
                    AND a.appointment_datetime BETWEEN $2 AND $3
                    AND a.tenant_id = $4
                    AND a.status IN ('completed', 'confirmed', 'scheduled')
                    GROUP BY a.appointment_type, tt.name
                    ORDER BY cnt DESC LIMIT 1
                """, prof_id, start_date, end_date, tenant_id)

                # 6. Busiest day of the week
                busiest_day = await db.pool.fetchrow("""
                    SELECT EXTRACT(DOW FROM appointment_datetime)::int as dow, COUNT(*) as cnt
                    FROM appointments
                    WHERE professional_id = $1
                    AND appointment_datetime BETWEEN $2 AND $3
                    AND tenant_id = $4
                    AND status IN ('completed', 'confirmed', 'scheduled')
                    GROUP BY dow ORDER BY cnt DESC LIMIT 1
                """, prof_id, start_date, end_date, tenant_id)
                days_es = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

                # 7. Strategic Tags
                tags = []
                if completion_rate > 90 and total_apts > 5:
                    tags.append("High Performance")
                if retention_rate > 60:
                    tags.append("Retention Master")
                if cancellation_rate > 20:
                    tags.append("Risk: Cancellations")
                if no_show_rate > 15:
                    tags.append("Risk: No-Shows")
                if estimated_revenue > 50000:
                    tags.append("Top Revenue")
                if total_apts > 0 and avg_revenue > 5000:
                    tags.append("High Ticket")

                results.append({
                    "id": prof_id,
                    "name": full_name,
                    "specialty": prof['specialty'] or "General",
                    "metrics": {
                        "total_appointments": total_apts,
                        "unique_patients": stats['unique_patients'] or 0,
                        "completion_rate": round(completion_rate, 1),
                        "cancellation_rate": round(cancellation_rate, 1),
                        "no_show_rate": round(no_show_rate, 1),
                        "revenue": estimated_revenue,
                        "avg_revenue_per_appointment": round(avg_revenue, 0),
                        "retention_rate": round(retention_rate, 1),
                        "paid_appointments": revenue_row['paid_count'] or 0,
                        "partial_payments": revenue_row['partial_count'] or 0,
                    },
                    "top_treatment": {
                        "name": (top_treatment['name'] or top_treatment['appointment_type'] or 'N/A') if top_treatment else 'N/A',
                        "count": top_treatment['cnt'] if top_treatment else 0
                    },
                    "busiest_day": days_es[busiest_day['dow']] if busiest_day else 'N/A',
                    "tags": tags
                })

            return results

        except Exception as e:
            logger.error(f"Error calculating analytics: {e}")
            return []

    async def get_professional_summary(
        self,
        professional_id: int,
        start_date: datetime,
        end_date: datetime,
        tenant_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Métricas de un solo profesional para un tenant y rango de fechas.
        Usado por el modal de datos del profesional (acordeón).
        """
        try:
            prof = await db.pool.fetchrow(
                """
                SELECT id, first_name, last_name, specialty
                FROM professionals
                WHERE id = $1 AND tenant_id = $2
                """,
                professional_id,
                tenant_id,
            )
            if not prof:
                return None
            prof_id = prof["id"]
            full_name = f"{prof['first_name']} {prof['last_name'] or ''}".strip()
            stats = await db.pool.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed,
                    COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
                    COUNT(DISTINCT patient_id) as unique_patients
                FROM appointments
                WHERE professional_id = $1
                AND appointment_datetime BETWEEN $2 AND $3
                AND tenant_id = $4
                """,
                prof_id,
                start_date,
                end_date,
                tenant_id,
            )
            total_apts = stats["total"] or 0
            completed_apts = stats["completed"] or 0
            cancelled_apts = stats["cancelled"] or 0
            completion_rate = (completed_apts / total_apts) * 100 if total_apts > 0 else 0
            cancellation_rate = (cancelled_apts / total_apts) * 100 if total_apts > 0 else 0
            unique_patients = stats["unique_patients"] or 0
            returning_patients_count = await db.pool.fetchval(
                """
                SELECT COUNT(DISTINCT patient_id)
                FROM appointments a1
                WHERE professional_id = $1
                AND appointment_datetime BETWEEN $2 AND $3
                AND EXISTS (
                    SELECT 1 FROM appointments a2
                    WHERE a2.patient_id = a1.patient_id AND a2.appointment_datetime < $2
                )
                """,
                prof_id,
                start_date,
                end_date,
            )
            retention_rate = (
                (returning_patients_count / unique_patients) * 100 if unique_patients > 0 else 0
            )
            revenue_row = await db.pool.fetchrow(
                """
                SELECT SUM(COALESCE((treatment->>'cost')::numeric, 0)) as total_revenue
                FROM clinical_records, jsonb_array_elements(treatments) as treatment
                WHERE professional_id = $1
                AND created_at BETWEEN $2 AND $3
                AND tenant_id = $4
                """,
                prof_id,
                start_date,
                end_date,
                tenant_id,
            )
            estimated_revenue = float(revenue_row["total_revenue"] or 0)
            tags = []
            if completion_rate > 90 and total_apts > 10:
                tags.append("High Performance")
            if retention_rate > 60:
                tags.append("Retention Master")
            if cancellation_rate > 20:
                tags.append("Risk: Cancellations")
            if estimated_revenue > 100000:
                tags.append("Top Revenue")
            return {
                "id": prof_id,
                "name": full_name,
                "specialty": prof["specialty"] or "General",
                "metrics": {
                    "total_appointments": total_apts,
                    "unique_patients": unique_patients,
                    "completion_rate": round(completion_rate, 1),
                    "cancellation_rate": round(cancellation_rate, 1),
                    "revenue": estimated_revenue,
                    "retention_rate": round(retention_rate, 1),
                },
                "tags": tags,
            }
        except Exception as e:
            logger.error(f"Error get_professional_summary: {e}")
            return None


analytics_service = AnalyticsService()
