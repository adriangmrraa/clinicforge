"""
financial_dashboard_service.py — Aggregated financial metrics for the global dashboard.

Provides:
  - get_financial_summary()       — revenue, payouts, profit, pending
  - get_revenue_by_professional() — breakdown per professional
  - get_revenue_by_treatment()    — breakdown per treatment type
  - get_daily_cash_flow()         — daily revenue + payouts for charting
  - get_mom_growth()              — month-over-month growth percentage
  - get_pending_collections()     — outstanding balances to collect
  - get_top_treatments()          — top N treatments by revenue

All queries are filtered by tenant_id (soberanía de datos).
Uses asyncpg pool passed as first argument.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_float(value: Any) -> float:
    """Safely convert a DB value (Decimal, int, float, None) to float."""
    if value is None:
        return 0.0
    return float(value)


def _shift_period(
    period_start: datetime, period_end: datetime
) -> tuple[datetime, datetime]:
    """
    Calculate the previous period of the same duration.
    E.g. if current is Mar 1 – Mar 31 (31 days), previous is Feb 1 – Feb 28 (28 days).
    prev_end = period_start - 1 day (non-overlapping)
    prev_start = prev_end - duration + 1 day
    """
    duration = period_end - period_start
    prev_end = period_start - timedelta(days=1)
    prev_start = prev_end - duration + timedelta(days=1)
    return prev_start, prev_end


# ---------------------------------------------------------------------------
# FinancialDashboardService
# ---------------------------------------------------------------------------


class FinancialDashboardService:
    """Service for aggregated financial dashboard metrics."""

    # ------------------------------------------------------------------
    # 1. Financial Summary
    # ------------------------------------------------------------------

    async def get_financial_summary(
        self,
        pool,
        tenant_id: int,
        period_start: datetime,
        period_end: datetime,
    ) -> Dict[str, Any]:
        """
        Returns the main financial summary for a period.

        Returns dict with:
          - total_revenue: sum of patient payments (appointments + treatment plans)
          - total_payouts: sum of professional payouts
          - net_profit: total_revenue - total_payouts
          - total_billed: billing_amount for completed appointments
          - total_pending: pending amounts (billed but not paid)
          - liquidations_generated: count of liquidation_records in period
          - liquidations_pending: count with status in ('draft', 'generated')
          - liquidations_paid: count with status = 'paid'
        """
        try:
            # Revenue from completed/paid appointments
            appt_revenue = await pool.fetchval(
                """
                SELECT COALESCE(SUM(billing_amount), 0)
                FROM appointments
                WHERE tenant_id = $1
                  AND appointment_datetime >= $2
                  AND appointment_datetime < ($3::date + INTERVAL '1 day')
                  AND payment_status = 'paid'
                  AND status NOT IN ('cancelled', 'deleted')
                """,
                tenant_id,
                period_start,
                period_end,
            )

            # Revenue from treatment plan payments
            plan_revenue = await pool.fetchval(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM treatment_plan_payments
                WHERE tenant_id = $1
                  AND payment_date >= $2
                  AND payment_date < ($3::date + INTERVAL '1 day')
                """,
                tenant_id,
                period_start,
                period_end,
            )

            # Professional payouts
            total_payouts = await pool.fetchval(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM professional_payouts
                WHERE tenant_id = $1
                  AND payment_date >= $2
                  AND payment_date < ($3::date + INTERVAL '1 day')
                """,
                tenant_id,
                period_start,
                period_end,
            )

            # Total billed (all completed appointments regardless of payment)
            total_billed = await pool.fetchval(
                """
                SELECT COALESCE(SUM(billing_amount), 0)
                FROM appointments
                WHERE tenant_id = $1
                  AND appointment_datetime >= $2
                  AND appointment_datetime < ($3::date + INTERVAL '1 day')
                  AND status IN ('completed', 'attended')
                """,
                tenant_id,
                period_start,
                period_end,
            )

            # Total pending (billed but not fully paid)
            total_pending = await pool.fetchval(
                """
                SELECT COALESCE(SUM(billing_amount), 0)
                FROM appointments
                WHERE tenant_id = $1
                  AND appointment_datetime >= $2
                  AND appointment_datetime < ($3::date + INTERVAL '1 day')
                  AND payment_status IN ('pending', 'partial')
                  AND status NOT IN ('cancelled', 'deleted')
                  AND billing_amount > 0
                """,
                tenant_id,
                period_start,
                period_end,
            )

            # Liquidation counts
            liquidations_row = await pool.fetchrow(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status IN ('draft', 'generated')) AS pending,
                    COUNT(*) FILTER (WHERE status = 'paid') AS paid
                FROM liquidation_records
                WHERE tenant_id = $1
                  AND period_start >= $2
                  AND period_end < ($3::date + INTERVAL '1 day')
                """,
                tenant_id,
                period_start,
                period_end,
            )

            revenue = _to_float(appt_revenue) + _to_float(plan_revenue)
            payouts = _to_float(total_payouts)

            return {
                "total_revenue": round(revenue, 2),
                "total_payouts": round(payouts, 2),
                "net_profit": round(revenue - payouts, 2),
                "total_billed": round(_to_float(total_billed), 2),
                "total_pending": round(_to_float(total_pending), 2),
                "liquidations_generated": liquidations_row["total"]
                if liquidations_row
                else 0,
                "liquidations_pending": liquidations_row["pending"]
                if liquidations_row
                else 0,
                "liquidations_paid": liquidations_row["paid"]
                if liquidations_row
                else 0,
                "period_start": period_start.strftime("%Y-%m-%d")
                if isinstance(period_start, datetime)
                else str(period_start),
                "period_end": period_end.strftime("%Y-%m-%d")
                if isinstance(period_end, datetime)
                else str(period_end),
            }

        except Exception as e:
            logger.error(f"Error in get_financial_summary: {e}", exc_info=True)
            return {
                "total_revenue": 0.0,
                "total_payouts": 0.0,
                "net_profit": 0.0,
                "total_billed": 0.0,
                "total_pending": 0.0,
                "liquidations_generated": 0,
                "liquidations_pending": 0,
                "liquidations_paid": 0,
                "period_start": str(period_start),
                "period_end": str(period_end),
            }

    # ------------------------------------------------------------------
    # 2. Revenue by Professional
    # ------------------------------------------------------------------

    async def get_revenue_by_professional(
        self,
        pool,
        tenant_id: int,
        period_start: datetime,
        period_end: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Returns revenue breakdown by professional.

        Returns array of:
          { professional_id, professional_name, specialty,
            total_billed, total_paid, total_pending,
            appointment_count, liquidation_count }
        """
        try:
            rows = await pool.fetch(
                """
                SELECT
                    p.id AS professional_id,
                    p.first_name || ' ' || COALESCE(p.last_name, '') AS professional_name,
                    p.specialty,
                    COALESCE(SUM(a.billing_amount), 0) AS total_billed,
                    COALESCE(SUM(a.billing_amount) FILTER (WHERE a.payment_status = 'paid'), 0) AS total_paid,
                    COALESCE(SUM(a.billing_amount) FILTER (WHERE a.payment_status IN ('pending', 'partial')), 0) AS total_pending,
                    COUNT(a.id) AS appointment_count
                FROM professionals p
                LEFT JOIN appointments a ON a.professional_id = p.id
                    AND a.tenant_id = $1
                    AND a.appointment_datetime >= $2
                    AND a.appointment_datetime < ($3::date + INTERVAL '1 day')
                    AND a.status NOT IN ('cancelled', 'deleted')
                WHERE p.tenant_id = $1
                GROUP BY p.id, p.first_name, p.last_name, p.specialty
                ORDER BY total_billed DESC
                """,
                tenant_id,
                period_start,
                period_end,
            )

            # Count liquidations per professional in the period
            liq_rows = await pool.fetch(
                """
                SELECT professional_id, COUNT(*) AS liquidation_count
                FROM liquidation_records
                WHERE tenant_id = $1
                  AND period_start >= $2
                  AND period_end < ($3::date + INTERVAL '1 day')
                GROUP BY professional_id
                """,
                tenant_id,
                period_start,
                period_end,
            )
            liq_map = {r["professional_id"]: r["liquidation_count"] for r in liq_rows}

            result = []
            for row in rows:
                prof_id = row["professional_id"]
                result.append(
                    {
                        "professional_id": prof_id,
                        "professional_name": (row["professional_name"] or "").strip(),
                        "specialty": row["specialty"] or "General",
                        "total_billed": round(_to_float(row["total_billed"]), 2),
                        "total_paid": round(_to_float(row["total_paid"]), 2),
                        "total_pending": round(_to_float(row["total_pending"]), 2),
                        "appointment_count": row["appointment_count"] or 0,
                        "liquidation_count": liq_map.get(prof_id, 0),
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Error in get_revenue_by_professional: {e}", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # 3. Revenue by Treatment
    # ------------------------------------------------------------------

    async def get_revenue_by_treatment(
        self,
        pool,
        tenant_id: int,
        period_start: datetime,
        period_end: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Returns revenue breakdown by treatment type.

        Returns array of:
          { treatment_code, treatment_name, total_billed, total_paid,
            appointment_count, percentage }
        """
        try:
            rows = await pool.fetch(
                """
                SELECT
                    COALESCE(tt.code, a.appointment_type, 'unknown') AS treatment_code,
                    COALESCE(tt.name, a.appointment_type, 'Sin tratamiento') AS treatment_name,
                    COALESCE(SUM(a.billing_amount), 0) AS total_billed,
                    COALESCE(SUM(a.billing_amount) FILTER (WHERE a.payment_status = 'paid'), 0) AS total_paid,
                    COUNT(a.id) AS appointment_count
                FROM appointments a
                LEFT JOIN treatment_types tt ON tt.code = a.appointment_type AND tt.tenant_id = a.tenant_id
                WHERE a.tenant_id = $1
                  AND a.appointment_datetime >= $2
                  AND a.appointment_datetime < ($3::date + INTERVAL '1 day')
                  AND a.status NOT IN ('cancelled', 'deleted')
                GROUP BY tt.code, tt.name, a.appointment_type
                ORDER BY total_billed DESC
                LIMIT 10
                """,
                tenant_id,
                period_start,
                period_end,
            )

            total_all = sum(_to_float(r["total_billed"]) for r in rows)

            result = []
            for row in rows:
                billed = _to_float(row["total_billed"])
                percentage = (
                    round((billed / total_all * 100), 1) if total_all > 0 else 0.0
                )
                result.append(
                    {
                        "treatment_code": row["treatment_code"],
                        "treatment_name": row["treatment_name"],
                        "total_billed": round(billed, 2),
                        "total_paid": round(_to_float(row["total_paid"]), 2),
                        "appointment_count": row["appointment_count"] or 0,
                        "percentage": percentage,
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Error in get_revenue_by_treatment: {e}", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # 4. Daily Cash Flow
    # ------------------------------------------------------------------

    async def get_daily_cash_flow(
        self,
        pool,
        tenant_id: int,
        period_start: datetime,
        period_end: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Returns daily cash flow data for charting.

        Returns array of:
          { date, cash_received, card_received, total, payouts }

        Uses generate_series to include all days in the range (even days with 0 revenue).
        """
        try:
            rows = await pool.fetch(
                """
                WITH date_series AS (
                    SELECT generate_series(
                        $2::date,
                        $3::date,
                        INTERVAL '1 day'
                    )::date AS d
                ),
                daily_revenue AS (
                    SELECT
                        DATE(a.appointment_datetime) AS d,
                        COALESCE(SUM(a.billing_amount) FILTER (
                            WHERE a.payment_method = 'cash' AND a.payment_status = 'paid'
                        ), 0) AS cash_received,
                        COALESCE(SUM(a.billing_amount) FILTER (
                            WHERE a.payment_method IN ('card', 'credit_card', 'debit_card')
                            AND a.payment_status = 'paid'
                        ), 0) AS card_received,
                        COALESCE(SUM(a.billing_amount) FILTER (
                            WHERE a.payment_status = 'paid'
                        ), 0) AS total
                    FROM appointments a
                    WHERE a.tenant_id = $1
                      AND a.appointment_datetime >= $2
                      AND a.appointment_datetime < ($3::date + INTERVAL '1 day')
                      AND a.status NOT IN ('cancelled', 'deleted')
                    GROUP BY DATE(a.appointment_datetime)
                ),
                daily_payouts AS (
                    SELECT
                        payment_date AS d,
                        COALESCE(SUM(amount), 0) AS payouts
                    FROM professional_payouts
                    WHERE tenant_id = $1
                      AND payment_date >= $2
                      AND payment_date < ($3::date + INTERVAL '1 day')
                    GROUP BY payment_date
                )
                SELECT
                    ds.d AS date,
                    COALESCE(dr.cash_received, 0) AS cash_received,
                    COALESCE(dr.card_received, 0) AS card_received,
                    COALESCE(dr.total, 0) AS total,
                    COALESCE(dp.payouts, 0) AS payouts
                FROM date_series ds
                LEFT JOIN daily_revenue dr ON dr.d = ds.d
                LEFT JOIN daily_payouts dp ON dp.d = ds.d
                ORDER BY ds.d ASC
                """,
                tenant_id,
                period_start,
                period_end,
            )

            return [
                {
                    "date": row["date"].isoformat()
                    if hasattr(row["date"], "isoformat")
                    else str(row["date"]),
                    "cash_received": round(_to_float(row["cash_received"]), 2),
                    "card_received": round(_to_float(row["card_received"]), 2),
                    "total": round(_to_float(row["total"]), 2),
                    "payouts": round(_to_float(row["payouts"]), 2),
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Error in get_daily_cash_flow: {e}", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # 5. Month-over-Month Growth
    # ------------------------------------------------------------------

    async def get_mom_growth(
        self,
        pool,
        tenant_id: int,
        period_start: datetime,
        period_end: datetime,
    ) -> Dict[str, Any]:
        """
        Returns month-over-month growth percentage.

        Logic:
          1. Calculate total revenue for the current period
          2. Calculate the same duration for the previous period (shift dates back)
          3. growth_pct = ((current - previous) / previous) * 100
          4. If previous is 0, return null or 0

        Returns:
          { current_revenue, previous_revenue, growth_pct,
            current_payouts, previous_payouts, payout_growth_pct }
        """
        try:
            # Current period revenue
            current_appt = await pool.fetchval(
                """
                SELECT COALESCE(SUM(billing_amount), 0)
                FROM appointments
                WHERE tenant_id = $1
                  AND appointment_datetime >= $2
                  AND appointment_datetime < ($3::date + INTERVAL '1 day')
                  AND payment_status = 'paid'
                  AND status NOT IN ('cancelled', 'deleted')
                """,
                tenant_id,
                period_start,
                period_end,
            )
            current_plan = await pool.fetchval(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM treatment_plan_payments
                WHERE tenant_id = $1
                  AND payment_date >= $2
                  AND payment_date < ($3::date + INTERVAL '1 day')
                """,
                tenant_id,
                period_start,
                period_end,
            )
            current_payouts = await pool.fetchval(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM professional_payouts
                WHERE tenant_id = $1
                  AND payment_date >= $2
                  AND payment_date < ($3::date + INTERVAL '1 day')
                """,
                tenant_id,
                period_start,
                period_end,
            )

            # Previous period (same duration, shifted back)
            prev_start, prev_end = _shift_period(period_start, period_end)

            prev_appt = await pool.fetchval(
                """
                SELECT COALESCE(SUM(billing_amount), 0)
                FROM appointments
                WHERE tenant_id = $1
                  AND appointment_datetime >= $2
                  AND appointment_datetime < ($3::date + INTERVAL '1 day')
                  AND payment_status = 'paid'
                  AND status NOT IN ('cancelled', 'deleted')
                """,
                tenant_id,
                prev_start,
                prev_end,
            )
            prev_plan = await pool.fetchval(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM treatment_plan_payments
                WHERE tenant_id = $1
                  AND payment_date >= $2
                  AND payment_date < ($3::date + INTERVAL '1 day')
                """,
                tenant_id,
                prev_start,
                prev_end,
            )
            prev_payouts = await pool.fetchval(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM professional_payouts
                WHERE tenant_id = $1
                  AND payment_date >= $2
                  AND payment_date < ($3::date + INTERVAL '1 day')
                """,
                tenant_id,
                prev_start,
                prev_end,
            )

            current_revenue = _to_float(current_appt) + _to_float(current_plan)
            previous_revenue = _to_float(prev_appt) + _to_float(prev_plan)
            current_payouts_val = _to_float(current_payouts)
            previous_payouts_val = _to_float(prev_payouts)

            # Growth calculations
            if previous_revenue > 0:
                growth_pct = round(
                    ((current_revenue - previous_revenue) / previous_revenue) * 100, 1
                )
            else:
                growth_pct = None  # Can't calculate growth from zero

            if previous_payouts_val > 0:
                payout_growth_pct = round(
                    (
                        (current_payouts_val - previous_payouts_val)
                        / previous_payouts_val
                    )
                    * 100,
                    1,
                )
            else:
                payout_growth_pct = None

            return {
                "current_revenue": round(current_revenue, 2),
                "previous_revenue": round(previous_revenue, 2),
                "growth_pct": growth_pct,
                "current_payouts": round(current_payouts_val, 2),
                "previous_payouts": round(previous_payouts_val, 2),
                "payout_growth_pct": payout_growth_pct,
            }

        except Exception as e:
            logger.error(f"Error in get_mom_growth: {e}", exc_info=True)
            return {
                "current_revenue": 0.0,
                "previous_revenue": 0.0,
                "growth_pct": None,
                "current_payouts": 0.0,
                "previous_payouts": 0.0,
                "payout_growth_pct": None,
            }

    # ------------------------------------------------------------------
    # 6. Pending Collections
    # ------------------------------------------------------------------

    async def get_pending_collections(
        self,
        pool,
        tenant_id: int,
        period_start: datetime,
        period_end: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Returns list of outstanding balances that need collection.

        Returns array of:
          { patient_id, patient_name, patient_phone, appointment_id,
            treatment_name, amount_pending, days_overdue, professional_name }
        """
        try:
            rows = await pool.fetch(
                """
                SELECT
                    pat.id AS patient_id,
                    pat.first_name || ' ' || COALESCE(pat.last_name, '') AS patient_name,
                    pat.phone_number AS patient_phone,
                    a.id AS appointment_id,
                    COALESCE(tt.name, a.appointment_type, 'Sin tratamiento') AS treatment_name,
                    a.billing_amount AS amount_pending,
                    EXTRACT(DAY FROM NOW() - a.appointment_datetime)::int AS days_overdue,
                    p.first_name || ' ' || COALESCE(p.last_name, '') AS professional_name
                FROM appointments a
                JOIN patients pat ON pat.id = a.patient_id AND pat.tenant_id = $1
                JOIN professionals p ON p.id = a.professional_id AND p.tenant_id = $1
                LEFT JOIN treatment_types tt ON tt.code = a.appointment_type AND tt.tenant_id = $1
                WHERE a.tenant_id = $1
                  AND a.appointment_datetime >= $2
                  AND a.appointment_datetime < ($3::date + INTERVAL '1 day')
                  AND a.payment_status IN ('pending', 'partial')
                  AND a.billing_amount > 0
                  AND a.status NOT IN ('cancelled', 'deleted')
                ORDER BY days_overdue DESC
                LIMIT 20
                """,
                tenant_id,
                period_start,
                period_end,
            )

            return [
                {
                    "patient_id": row["patient_id"],
                    "patient_name": (row["patient_name"] or "").strip(),
                    "patient_phone": row["patient_phone"] or "",
                    "appointment_id": row["appointment_id"],
                    "treatment_name": row["treatment_name"],
                    "amount_pending": round(_to_float(row["amount_pending"]), 2),
                    "days_overdue": row["days_overdue"] or 0,
                    "professional_name": (row["professional_name"] or "").strip(),
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Error in get_pending_collections: {e}", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # 7. Top Treatments
    # ------------------------------------------------------------------

    async def get_top_treatments(
        self,
        pool,
        tenant_id: int,
        period_start: datetime,
        period_end: datetime,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Returns top treatments by revenue.

        Returns array of:
          { treatment_code, treatment_name, total_revenue, count, avg_price }
        """
        try:
            rows = await pool.fetch(
                """
                SELECT
                    COALESCE(tt.code, a.appointment_type, 'unknown') AS treatment_code,
                    COALESCE(tt.name, a.appointment_type, 'Sin tratamiento') AS treatment_name,
                    COALESCE(SUM(a.billing_amount), 0) AS total_revenue,
                    COUNT(a.id) AS count,
                    CASE
                        WHEN COUNT(a.id) > 0 THEN AVG(a.billing_amount)
                        ELSE 0
                    END AS avg_price
                FROM appointments a
                LEFT JOIN treatment_types tt ON tt.code = a.appointment_type AND tt.tenant_id = a.tenant_id
                WHERE a.tenant_id = $1
                  AND a.appointment_datetime >= $2
                  AND a.appointment_datetime < ($3::date + INTERVAL '1 day')
                  AND a.status NOT IN ('cancelled', 'deleted')
                GROUP BY tt.code, tt.name, a.appointment_type
                ORDER BY total_revenue DESC
                LIMIT $4
                """,
                tenant_id,
                period_start,
                period_end,
                limit,
            )

            return [
                {
                    "treatment_code": row["treatment_code"],
                    "treatment_name": row["treatment_name"],
                    "total_revenue": round(_to_float(row["total_revenue"]), 2),
                    "count": row["count"] or 0,
                    "avg_price": round(_to_float(row["avg_price"]), 2),
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Error in get_top_treatments: {e}", exc_info=True)
            return []


# Singleton instance
financial_dashboard_service = FinancialDashboardService()
