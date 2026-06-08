"""
liquidation_service.py — Core liquidation business logic.

Handles generation, commission application, status transitions, payout creation,
and detail retrieval for professional liquidations.

All queries include WHERE tenant_id = $X for mandatory tenant isolation.
Uses raw asyncpg queries (ORM models added separately in T1.2).
"""

import logging
import os
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Valid status transitions: current_status -> allowed next statuses
_VALID_TRANSITIONS = {
    "draft": ["generated"],
    "generated": ["approved"],
    "approved": ["paid"],
    "paid": [],  # terminal state
}

# Timestamp fields to set per status
_STATUS_TIMESTAMPS = {
    "generated": "generated_at",
    "approved": "approved_at",
    "paid": "paid_at",
}


class LiquidationService:
    """Service for managing professional liquidations with commission tracking."""

    # ------------------------------------------------------------------
    # Method 1: generate_liquidation
    # ------------------------------------------------------------------
    async def generate_liquidation(
        self,
        pool,
        tenant_id: int,
        professional_id: int,
        period_start,
        period_end,
        generated_by_email: str,
    ) -> dict:
        """
        Generates a persistent liquidation snapshot for a professional in a given period.
        Idempotent: returns existing record if one already exists for the same key.
        """
        # 1. Check idempotency — use INSERT ON CONFLICT to prevent race conditions
        #    First, try to insert a "placeholder" row; if it conflicts, return existing
        placeholder = await pool.fetchrow(
            """
            INSERT INTO liquidation_records (
                tenant_id, professional_id, period_start, period_end,
                total_billed, total_paid, total_pending,
                commission_pct, commission_amount, payout_amount,
                status, generated_by, notes
            ) VALUES ($1::int, $2::int, $3::date, $4::date, 0, 0, 0, 0, 0, 0, 'generated', 'system', '{}')
            ON CONFLICT (tenant_id, professional_id, period_start, period_end)
            DO NOTHING
            RETURNING id
            """,
            tenant_id,
            professional_id,
            period_start,
            period_end,
        )

        if placeholder is None:
            # Record already exists — fetch and check if it's a valid record
            existing = await pool.fetchrow(
                """
                SELECT * FROM liquidation_records
                WHERE tenant_id = $1
                  AND professional_id = $2
                  AND period_start = $3
                  AND period_end = $4
                """,
                tenant_id,
                professional_id,
                period_start,
                period_end,
            )
            if existing:
                # Check for zombie placeholder (crash between INSERT and UPDATE)
                if float(existing["total_billed"] or 0) == 0 and existing["generated_by"] == "system":
                    logger.warning(
                        "generate_liquidation: zombie placeholder %s found for prof %s, "
                        "period %s-%s. Deleting and regenerating.",
                        existing["id"],
                        professional_id,
                        period_start,
                        period_end,
                    )
                    await pool.execute(
                        "DELETE FROM liquidation_records WHERE id = $1",
                        existing["id"],
                    )
                    # Fall through to generate fresh
                else:
                    logger.info(
                        "generate_liquidation: existing record %s for prof %s, period %s-%s",
                        existing["id"],
                        professional_id,
                        period_start,
                        period_end,
                    )
                    return dict(existing)

        placeholder_id = placeholder["id"] if placeholder else None

        # If we deleted a zombie, we need a fresh placeholder
        if placeholder_id is None:
            new_placeholder = await pool.fetchrow(
                """
                INSERT INTO liquidation_records (
                    tenant_id, professional_id, period_start, period_end,
                    total_billed, total_paid, total_pending,
                    commission_pct, commission_amount, payout_amount,
                    status, generated_by, notes
                ) VALUES ($1::int, $2::int, $3::date, $4::date, 0, 0, 0, 0, 0, 0, 'generated', 'system', '{}')
                RETURNING id
                """,
                tenant_id,
                professional_id,
                period_start,
                period_end,
            )
            placeholder_id = new_placeholder["id"] if new_placeholder else None

        # 3. Query ONLY PAID appointments in the period for this professional
        #    DLD-91: "Solo se liquidan tratamientos cobrados."
        #    Each appointment uses point-in-time commission lookup via get_commission_config_at_date
        appt_rows = await pool.fetch(
            """
            SELECT
                a.id AS appointment_id,
                a.appointment_datetime,
                a.status AS appointment_status,
                a.appointment_type,
                a.payment_status,
                COALESCE(a.billing_amount, tt.base_price, 0) AS billing_amount,
                tt.code AS treatment_code,
                tt.name AS treatment_name,
                a.plan_item_id,
                tpi.plan_id,
                tp.approved_total AS plan_approved_total,
                tp.status AS plan_status
            FROM appointments a
            LEFT JOIN treatment_types tt
                ON tt.code = a.appointment_type AND tt.tenant_id = $1
            LEFT JOIN treatment_plan_items tpi
                ON tpi.id = a.plan_item_id AND tpi.tenant_id = $1
            LEFT JOIN treatment_plans tp
                ON tp.id = tpi.plan_id AND tp.tenant_id = $1
            WHERE a.tenant_id = $1
              AND a.professional_id = $2
              AND a.appointment_datetime >= $3
              AND a.appointment_datetime < ($4::date + INTERVAL '1 day')
              AND a.status != 'deleted'
            ORDER BY a.appointment_datetime
            """,
            tenant_id,
            professional_id,
            period_start,
            period_end,
        )

        # Check if there are any appointments at all for this period
        if not appt_rows:
            if placeholder_id:
                await pool.execute(
                    "DELETE FROM liquidation_records WHERE id = $1 AND tenant_id = $2",
                    placeholder_id,
                    tenant_id,
                )
            raise HTTPException(
                status_code=400,
                detail="No se encontraron turnos registrados para este profesional en el período especificado."
            )

        # Collect plan IDs to fetch payments in bulk
        plan_ids = set()
        for row in appt_rows:
            p_id = row.get("plan_id")
            p_status = row.get("plan_status")
            if p_id and p_status in ("approved", "in_progress"):
                plan_ids.add(p_id)

        plan_paid_map = {}
        if plan_ids:
            plan_payment_rows = await pool.fetch(
                """
                SELECT plan_id, COALESCE(SUM(amount), 0) AS total_paid
                FROM treatment_plan_payments
                WHERE tenant_id = $1 AND plan_id = ANY($2::uuid[])
                GROUP BY plan_id
                """,
                tenant_id,
                list(plan_ids),
            )
            for r in plan_payment_rows:
                plan_paid_map[r["plan_id"]] = Decimal(str(r["total_paid"]))

        # 4. Calculate totals with point-in-time commission lookup
        total_billed = Decimal("0")
        total_paid = Decimal("0")
        total_commission = Decimal("0")
        treatments_without_commission = []

        for row in appt_rows:
            billing = Decimal(str(row["billing_amount"] or 0))
            treatment_code = row["treatment_code"] or ""
            appt_date = row["appointment_datetime"].date() if row["appointment_datetime"] else period_start
            appt_status = row["appointment_status"] or ""
            pstatus = row["payment_status"] or "pending"
            plan_id = row.get("plan_id")
            plan_status = row.get("plan_status")
            plan_approved_total = row.get("plan_approved_total")

            excluded = appt_status in ("cancelled", "no_show")
            billing_for_totals = Decimal("0") if excluded else billing

            # Point-in-time commission lookup for THIS appointment's date
            config_at_date = await self.get_commission_config_at_date(
                pool, tenant_id, professional_id, appt_date
            )

            # Determine commission % for this treatment on this date
            per_treatment = config_at_date.get("per_treatment", {})
            if treatment_code in per_treatment:
                appt_commission_pct = per_treatment[treatment_code]["commission_pct"]
            else:
                appt_commission_pct = config_at_date["default_commission_pct"]

            if config_at_date["source"] == "default_zero":
                if treatment_code not in treatments_without_commission:
                    treatments_without_commission.append(treatment_code)

            total_billed += billing_for_totals

            if not excluded:
                is_prop_plan = plan_id and plan_status in ("approved", "in_progress")
                if is_prop_plan:
                    plan_approved_total_dec = Decimal(str(plan_approved_total or 0))
                    total_plan_paid = plan_paid_map.get(plan_id, Decimal("0"))
                    if plan_approved_total_dec > 0:
                        ratio = total_plan_paid / plan_approved_total_dec
                        if ratio > Decimal("1.0"):
                            ratio = Decimal("1.0")
                    else:
                        ratio = Decimal("0")
                    paid_for_appt = billing_for_totals * ratio
                else:
                    paid_for_appt = billing_for_totals if pstatus == 'paid' else Decimal("0")

                appt_commission = paid_for_appt * (
                    Decimal(str(appt_commission_pct)) / Decimal("100")
                )
                total_commission += appt_commission
                total_paid += paid_for_appt

        total_pending = total_billed - total_paid
        if total_pending < 0:
            total_pending = Decimal("0")

        total_commission_pct = float(total_commission / total_billed * 100) if total_billed > 0 else 0.0

        commission_amount = total_commission
        payout_amount = commission_amount  # payout is what the professional receives

        # 6. Insert liquidation record
        audit_trail = [
            {
                "action": "generated",
                "by": generated_by_email,
                "at": datetime.utcnow().isoformat(),
                "detail": "Liquidación generada automáticamente",
            }
        ]

        # Update the placeholder row with real data
        record = await pool.fetchrow(
            """
            UPDATE liquidation_records SET
                total_billed = $5, total_paid = $6, total_pending = $7,
                commission_pct = $8, commission_amount = $9, payout_amount = $10,
                generated_by = $11, notes = $12
            WHERE id = $13 AND tenant_id = $1
            RETURNING *
            """,
            tenant_id,
            professional_id,
            period_start,
            period_end,
            float(total_billed),
            float(total_paid),
            float(total_pending),
            total_commission_pct,
            float(commission_amount),
            float(payout_amount),
            generated_by_email,
            {"audit_trail": audit_trail},
            placeholder_id,
        )

        logger.info(
            "generate_liquidation: created record %s for prof %s, "
            "billed=%s, commission=%s%%, payout=%s",
            record["id"],
            professional_id,
            total_billed,
            total_commission_pct,
            payout_amount,
        )

        return dict(record)

    # ------------------------------------------------------------------
    # Method 2: generate_bulk_liquidations
    # ------------------------------------------------------------------
    async def generate_bulk_liquidations(
        self,
        pool,
        tenant_id: int,
        period_start,
        period_end,
        generated_by_email: str,
    ) -> dict:
        """
        Generates liquidations for ALL active professionals in the period.
        Returns { generated_count, skipped_count, liquidations: [...] }.
        """
        # 1. Get list of active professionals
        professionals = await pool.fetch(
            """
            SELECT p.id, p.first_name, p.last_name
            FROM professionals p
            INNER JOIN users u ON p.user_id = u.id
            WHERE p.tenant_id = $1 AND p.is_active = true
              AND u.role IN ('professional', 'ceo')
            ORDER BY p.id
            """,
            tenant_id,
        )

        results = []
        generated_count = 0
        skipped_count = 0

        for prof in professionals:
            try:
                record = await self.generate_liquidation(
                    pool,
                    tenant_id,
                    prof["id"],
                    period_start,
                    period_end,
                    generated_by_email,
                )

                # Check if it was newly created or already existed
                created_at = record.get("created_at")
                if created_at and isinstance(created_at, datetime):
                    # If created_at is very recent (within last minute), it's new
                    now = datetime.utcnow()
                    diff = (now - created_at).total_seconds()
                    is_new = diff < 60
                else:
                    is_new = True  # assume new if we can't tell

                # More reliable check: look at audit_trail for 'generated' action
                # If the record was just created by us, it's new
                notes = record.get("notes") or {}
                audit_trail = notes.get("audit_trail", [])
                # If there's only one audit entry and it's 'generated', it's new
                is_new = (
                    len(audit_trail) == 1
                    and audit_trail[0].get("action") == "generated"
                )

                if is_new:
                    generated_count += 1
                else:
                    skipped_count += 1

                results.append(
                    {
                        "id": record["id"],
                        "professional_id": prof["id"],
                        "professional_name": f"{prof['first_name']} {prof['last_name']}".strip(),
                        "total_billed": float(record["total_billed"]),
                        "status": record["status"],
                    }
                )
            except Exception as e:
                logger.error(
                    "generate_bulk_liquidations: error for professional %s: %s",
                    prof["id"],
                    e,
                    exc_info=True,
                )
                # Continue with next professional

        return {
            "generated_count": generated_count,
            "skipped_count": skipped_count,
            "liquidations": results,
        }

    # ------------------------------------------------------------------
    # Method 3: get_liquidation_detail
    # ------------------------------------------------------------------
    async def get_liquidation_detail(
        self, pool, tenant_id: int, liquidation_id: int
    ) -> Optional[dict]:
        """
        Returns full liquidation detail including treatment groups.
        Re-queries appointments for the liquidation's period to get current data.
        """
        # 1. Fetch the liquidation record
        record = await pool.fetchrow(
            """
            SELECT lr.*,
                   p.first_name || ' ' || COALESCE(p.last_name, '') AS professional_name,
                   p.specialty
            FROM liquidation_records lr
            JOIN professionals p ON p.id = lr.professional_id AND p.tenant_id = lr.tenant_id
            WHERE lr.id = $1 AND lr.tenant_id = $2
            """,
            liquidation_id,
            tenant_id,
        )

        if not record:
            return None

        prof_id = record["professional_id"]
        period_start = record["period_start"]
        period_end = record["period_end"]

        # 2. Query appointments for the professional in the liquidation's period
        #    Same query pattern as analytics_service.get_professionals_liquidation
        appt_rows = await pool.fetch(
            """
            SELECT
                a.id AS appointment_id,
                a.appointment_datetime,
                a.status AS appointment_status,
                a.appointment_type,
                a.payment_status,
                COALESCE(a.billing_amount, tt.base_price, 0) AS billing_amount,
                a.billing_notes,
                a.notes AS appointment_notes,
                a.plan_item_id,
                pat.id AS patient_id,
                pat.first_name || ' ' || COALESCE(pat.last_name, '') AS patient_name,
                pat.phone_number AS patient_phone,
                tt.code AS treatment_code,
                tt.name AS treatment_name,
                tpi.plan_id,
                tp.name AS plan_name,
                tp.approved_total AS plan_approved_total,
                tp.status AS plan_status
            FROM appointments a
            JOIN patients pat ON pat.id = a.patient_id AND pat.tenant_id = $1
            LEFT JOIN treatment_types tt ON tt.code = a.appointment_type AND tt.tenant_id = $1
            LEFT JOIN treatment_plan_items tpi ON tpi.id = a.plan_item_id AND tpi.tenant_id = $1
            LEFT JOIN treatment_plans tp ON tp.id = tpi.plan_id AND tp.tenant_id = $1
            WHERE a.tenant_id = $1
              AND a.professional_id = $2
              AND a.appointment_datetime >= $3
              AND a.appointment_datetime < ($4::date + INTERVAL '1 day')
              AND a.status != 'deleted'
            ORDER BY pat.id, a.appointment_type, a.appointment_datetime
            """,
            tenant_id,
            prof_id,
            period_start,
            period_end,
        )

        # 3. Group by patient → treatment (same aggregation as analytics_service)
        treatment_groups_map = {}
        plan_ids_found = set()

        for row in appt_rows:
            plan_id = row["plan_id"]
            plan_status = row["plan_status"]
            if plan_id and plan_status in ("approved", "in_progress"):
                plan_ids_found.add(plan_id)

        plan_paid_map = {}
        if plan_ids_found:
            plan_payment_rows = await pool.fetch(
                """
                SELECT plan_id, COALESCE(SUM(amount), 0) AS total_paid
                FROM treatment_plan_payments
                WHERE tenant_id = $1 AND plan_id = ANY($2::uuid[])
                GROUP BY plan_id
                """,
                tenant_id,
                list(plan_ids_found),
            )
            plan_paid_map = {
                r["plan_id"]: float(r["total_paid"]) for r in plan_payment_rows
            }

        for row in appt_rows:
            pat_id = row["patient_id"]
            treatment_code = row["treatment_code"] or ""
            billing_amount = float(row["billing_amount"] or 0)
            pstatus = row["payment_status"] or "pending"
            plan_id = row["plan_id"]
            plan_status = row["plan_status"]
            plan_approved_total = float(row["plan_approved_total"] or 0)

            # Unified group key by (patient_id, treatment_code)
            group_key = (pat_id, treatment_code)

            if group_key not in treatment_groups_map:
                treatment_groups_map[group_key] = {
                    "patient_id": pat_id,
                    "patient_name": (row["patient_name"] or "").strip(),
                    "patient_phone": row["patient_phone"] or "",
                    "treatment_code": treatment_code,
                    "treatment_name": row["treatment_name"]
                    or treatment_code
                    or "Sin tratamiento",
                    "sessions": [],
                    "total_billed": 0.0,
                    "total_paid": 0.0,
                    "total_pending": 0.0,
                    "session_count": 0,
                }

            group = treatment_groups_map[group_key]
            appt_status = row["appointment_status"] or ""
            excluded = appt_status in ("cancelled", "no_show")
            billing_for_totals = 0.0 if excluded else billing_amount

            if not excluded:
                is_prop_plan = plan_id and plan_status in ("approved", "in_progress")
                if is_prop_plan:
                    total_plan_paid = plan_paid_map.get(plan_id, 0.0)
                    if plan_approved_total > 0:
                        ratio = total_plan_paid / plan_approved_total
                        if ratio > 1.0:
                            ratio = 1.0
                    else:
                        ratio = 0.0
                    paid_for_appt = billing_for_totals * ratio
                else:
                    paid_for_appt = billing_for_totals if pstatus == 'paid' else 0.0
            else:
                paid_for_appt = 0.0

            pending_for_appt = max(billing_for_totals - paid_for_appt, 0.0)

            display_payment_status = pstatus
            if not excluded and plan_id and plan_status in ("approved", "in_progress"):
                if paid_for_appt >= billing_for_totals:
                    display_payment_status = 'paid'
                elif paid_for_appt > 0:
                    display_payment_status = 'partial'
                else:
                    display_payment_status = 'pending'

            group["sessions"].append(
                {
                    "appointment_id": row["appointment_id"],
                    "date": row["appointment_datetime"].isoformat()
                    if row["appointment_datetime"]
                    else None,
                    "status": appt_status,
                    "billing_amount": billing_amount,
                    "amount": billing_amount,  # compatibility duplicate
                    "payment_status": display_payment_status,
                    "billing_notes": row["billing_notes"],
                    "description": row["billing_notes"] or display_payment_status,  # compatibility duplicate
                }
            )

            group["session_count"] += 1
            group["total_billed"] += billing_for_totals
            group["total_paid"] += paid_for_appt
            group["total_pending"] += pending_for_appt

        # Sort treatment groups by total_billed DESC
        groups_sorted = sorted(
            treatment_groups_map.values(), key=lambda g: g["total_billed"], reverse=True
        )
        treatment_groups_out = []
        for g in groups_sorted:
            g["sessions"].sort(key=lambda s: s["date"] or "")
            treatment_groups_out.append(
                {
                    "patient_id": g["patient_id"],
                    "patient_name": g["patient_name"],
                    "patient_phone": g["patient_phone"],
                    "treatment_code": g["treatment_code"],
                    "treatment_name": g["treatment_name"],
                    "type": "appointment",
                    "plan_id": None,
                    "plan_name": None,
                    "plan_status": None,
                    "approved_total": None,
                    "sessions": g["sessions"],
                    "total_billed": round(g["total_billed"], 2),
                    "total": round(g["total_billed"], 2),  # compatibility duplicate
                    "total_paid": round(g["total_paid"], 2),
                    "total_pending": round(g["total_pending"], 2),
                    "session_count": g["session_count"],
                }
            )

        # 4. Fetch payouts for this liquidation
        payouts = await pool.fetch(
            """
            SELECT id, amount, payment_method, payment_date,
                   reference_number, notes, created_at
            FROM professional_payouts
            WHERE liquidation_record_id = $1 AND tenant_id = $2
            ORDER BY payment_date DESC
            """,
            liquidation_id,
            tenant_id,
        )
        payouts_out = [
            {
                "id": p["id"],
                "amount": float(p["amount"]),
                "payment_method": p["payment_method"],
                "payment_date": p["payment_date"].isoformat()
                if p["payment_date"]
                else None,
                "reference_number": p["reference_number"],
                "notes": p["notes"],
                "created_at": p["created_at"].isoformat() if p["created_at"] else None,
            }
            for p in payouts
        ]

        # 5. Build response
        return {
            "liquidation": {
                "id": record["id"],
                "tenant_id": record["tenant_id"],
                "professional_id": record["professional_id"],
                "professional_name": record.get("professional_name"),
                "specialty": record.get("specialty"),
                "period_start": str(record["period_start"]),
                "period_end": str(record["period_end"]),
                "total_billed": float(record["total_billed"]),
                "total_paid": float(record["total_paid"]),
                "total_pending": float(record["total_pending"]),
                "commission_pct": float(record["commission_pct"]),
                "commission_amount": float(record["commission_amount"]),
                "payout_amount": float(record["payout_amount"]),
                "status": record["status"],
                "generated_at": record.get("generated_at").isoformat()
                if record.get("generated_at")
                else None,
                "approved_at": record.get("approved_at").isoformat()
                if record.get("approved_at")
                else None,
                "paid_at": record.get("paid_at").isoformat() if record.get("paid_at") else None,
                "generated_by": record["generated_by"],
                "notes": record.get("notes") or {},
                "created_at": record.get("created_at").isoformat()
                if record.get("created_at")
                else None,
            },
            "treatment_groups": treatment_groups_out,
            "payouts": payouts_out,
        }

    # ------------------------------------------------------------------
    # Method 4: list_liquidations
    # ------------------------------------------------------------------
    async def list_liquidations(
        self,
        pool,
        tenant_id: int,
        professional_id: Optional[int] = None,
        status: Optional[str] = None,
        period_start=None,
        period_end=None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """
        Returns paginated list of liquidation records with optional filters.
        """
        # Build dynamic WHERE clauses
        conditions = ["lr.tenant_id = $1"]
        params: list = [tenant_id]
        param_idx = 2

        if professional_id is not None:
            conditions.append(f"lr.professional_id = ${param_idx}")
            params.append(professional_id)
            param_idx += 1

        if status:
            conditions.append(f"lr.status = ${param_idx}")
            params.append(status)
            param_idx += 1

        if period_start:
            conditions.append(f"lr.period_start >= ${param_idx}")
            params.append(period_start)
            param_idx += 1

        if period_end:
            conditions.append(f"lr.period_end <= ${param_idx}")
            params.append(period_end)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        # Count query
        count_sql = f"""
            SELECT COUNT(*) FROM liquidation_records lr
            WHERE {where_clause}
        """
        total = await pool.fetchval(count_sql, *params)

        # Data query
        params_for_data = list(params)
        param_idx_data = len(params_for_data) + 1
        params_for_data.append(limit)
        params_for_data.append(offset)

        data_sql = f"""
            SELECT lr.*,
                   p.first_name || ' ' || COALESCE(p.last_name, '') AS professional_name
            FROM liquidation_records lr
            JOIN professionals p ON p.id = lr.professional_id AND p.tenant_id = lr.tenant_id
            WHERE {where_clause}
            ORDER BY lr.created_at DESC
            LIMIT ${param_idx_data} OFFSET ${param_idx_data + 1}
        """

        rows = await pool.fetch(data_sql, *params_for_data)

        liquidations = []
        for row in rows:
            liquidations.append(
                {
                    "id": row["id"],
                    "professional_id": row["professional_id"],
                    "professional_name": row["professional_name"],
                    "period_start": str(row["period_start"]),
                    "period_end": str(row["period_end"]),
                    "total_billed": float(row["total_billed"]),
                    "total_paid": float(row["total_paid"]),
                    "total_pending": float(row["total_pending"]),
                    "commission_pct": float(row["commission_pct"]),
                    "commission_amount": float(row["commission_amount"]),
                    "payout_amount": float(row["payout_amount"]),
                    "status": row["status"],
                    "generated_at": row["generated_at"].isoformat()
                    if row["generated_at"]
                    else None,
                    "approved_at": row["approved_at"].isoformat()
                    if row["approved_at"]
                    else None,
                    "paid_at": row["paid_at"].isoformat() if row["paid_at"] else None,
                    "generated_by": row["generated_by"],
                    "created_at": row["created_at"].isoformat()
                    if row["created_at"]
                    else None,
                }
            )

        total_pages = (total + limit - 1) // limit if total > 0 else 0

        return {
            "liquidations": liquidations,
            "total": total,
            "page": (offset // limit) + 1 if limit > 0 else 1,
            "page_size": limit,
            "total_pages": total_pages,
        }

    # ------------------------------------------------------------------
    # Method 5: update_liquidation_status
    # ------------------------------------------------------------------
    async def update_liquidation_status(
        self,
        pool,
        tenant_id: int,
        liquidation_id: int,
        new_status: str,
        user_email: str,
        notes: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Updates liquidation status with audit trail.
        Validates status transitions: draft→generated→approved→paid
        """
        # 1. Fetch liquidation record with row lock (prevents race conditions)
        record = await pool.fetchrow(
            """
            SELECT * FROM liquidation_records
            WHERE id = $1 AND tenant_id = $2
            FOR UPDATE
            """,
            liquidation_id,
            tenant_id,
        )

        if not record:
            return None

        current_status = record["status"]

        # 1.5 BLOCK: If approving, check all treatments have commission configured
        if new_status == "approved":
            missing = await self._check_treatments_without_commission(
                pool, tenant_id, liquidation_id, record
            )
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"No se puede aprobar la liquidación. "
                        f"Hay tratamientos sin comisión configurada: "
                        f"{', '.join(missing)}. "
                        f"Configurá las comisiones en /finanzas → Liquidaciones."
                    ),
                )

        # 2. Validate status transition
        allowed = _VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid status transition: {current_status} → {new_status}. "
                f"Allowed transitions: {allowed}"
            )

        # 3. Build update fields
        now = datetime.utcnow()
        updates = {"status": new_status}
        ts_field = _STATUS_TIMESTAMPS.get(new_status)
        if ts_field:
            updates[ts_field] = now

        # 4. Append audit trail entry
        existing_notes = record["notes"] or {}
        audit_trail = existing_notes.get("audit_trail", [])
        audit_entry = {
            "action": "status_change",
            "from": current_status,
            "to": new_status,
            "by": user_email,
            "at": now.isoformat(),
        }
        if notes:
            audit_entry["notes"] = notes
        audit_trail.append(audit_entry)
        existing_notes["audit_trail"] = audit_trail
        updates["notes"] = existing_notes

        # Build dynamic SET clause
        set_parts = []
        values = []
        param_idx = 1

        for key, value in updates.items():
            set_parts.append(f"{key} = ${param_idx}")
            values.append(value)
            param_idx += 1

        values.append(liquidation_id)
        values.append(tenant_id)

        update_sql = f"""
            UPDATE liquidation_records
            SET {", ".join(set_parts)}
            WHERE id = ${param_idx} AND tenant_id = ${param_idx + 1}
            RETURNING *
        """

        updated = await pool.fetchrow(update_sql, *values)

        # 5. If status='paid' and no payout exists, create auto-payout
        if new_status == "paid":
            existing_payouts = await pool.fetchval(
                """
                SELECT COUNT(*) FROM professional_payouts
                WHERE liquidation_id = $1
                """,
                liquidation_id,
            )
            if existing_payouts == 0:
                payout_amount = float(updated["payout_amount"])
                if payout_amount > 0:
                    await pool.execute(
                        """
                        INSERT INTO professional_payouts (
                            tenant_id, liquidation_id, professional_id,
                            amount, payment_method, payment_date,
                            reference_number, notes
                        ) VALUES ($1, $2, $3, $4, 'transfer', CURRENT_DATE, 'auto-paid', $5)
                        """,
                        tenant_id,
                        liquidation_id,
                        updated["professional_id"],
                        payout_amount,
                        "Pago automático al marcar como pagada",
                    )
                    # Append audit entry for auto-payout
                    audit_trail.append(
                        {
                            "action": "auto_payout_created",
                            "amount": payout_amount,
                            "by": user_email,
                            "at": datetime.utcnow().isoformat(),
                        }
                    )
                    await pool.execute(
                        """
                        UPDATE liquidation_records
                        SET notes = $1
                        WHERE id = $2 AND tenant_id = $3
                        """,
                        existing_notes,
                        liquidation_id,
                        tenant_id,
                    )

                    # Refresh the record
                    updated = await pool.fetchrow(
                        """
                        SELECT * FROM liquidation_records
                        WHERE id = $1 AND tenant_id = $2
                        """,
                        liquidation_id,
                        tenant_id,
                    )

        logger.info(
            "update_liquidation_status: %s → %s for liquidation %s by %s",
            current_status,
            new_status,
            liquidation_id,
            user_email,
        )

        # Invalidate PDF cache
        await self.invalidate_liquidation_pdf(tenant_id, liquidation_id)

        return dict(updated)

    # ------------------------------------------------------------------
    # Helper: _check_treatments_without_commission
    # ------------------------------------------------------------------
    async def _check_treatments_without_commission(
        self, pool, tenant_id: int, liquidation_id: int, record=None
    ) -> list:
        """
        Checks if any treatments in the liquidation have no commission config.
        Returns list of treatment names without commission. Empty list = all good.
        Blocks approval if not empty.
        """
        if record is None:
            record = await pool.fetchrow(
                "SELECT * FROM liquidation_records WHERE id = $1 AND tenant_id = $2",
                liquidation_id,
                tenant_id,
            )
            if not record:
                return []

        professional_id = record["professional_id"]
        period_start = record["period_start"]
        period_end = record["period_end"]

        # Get all distinct treatments in the liquidation's period
        treatment_rows = await pool.fetch(
            """
            SELECT DISTINCT tt.code, tt.name
            FROM appointments a
            LEFT JOIN treatment_types tt ON tt.code = a.appointment_type AND tt.tenant_id = $1
            WHERE a.tenant_id = $1
              AND a.professional_id = $2
              AND a.appointment_datetime::date >= $3
              AND a.appointment_datetime::date <= $4
              AND a.status != 'deleted'
              AND a.payment_status = 'paid'
              AND tt.code IS NOT NULL
            """,
            tenant_id,
            professional_id,
            period_start,
            period_end,
        )

        missing = []
        for row in treatment_rows:
            code = row["code"]
            name = row["name"] or code

            # Check EVERY appointment for this treatment — not just the first one
            # (commission config may have changed mid-period)
            appt_dates = await pool.fetch(
                """
                SELECT DISTINCT a.appointment_datetime::date AS appt_date
                FROM appointments a
                WHERE a.tenant_id = $1
                  AND a.professional_id = $2
                  AND a.appointment_type = $3
                  AND a.appointment_datetime::date >= $4
                  AND a.appointment_datetime::date <= $5
                  AND a.status != 'deleted'
                  AND a.payment_status = 'paid'
                ORDER BY a.appointment_datetime::date
                """,
                tenant_id,
                professional_id,
                code,
                period_start,
                period_end,
            )

            any_missing = False
            for date_row in appt_dates:
                config = await self.get_commission_config_at_date(
                    pool, tenant_id, professional_id, date_row["appt_date"]
                )
                if config["source"] == "default_zero":
                    any_missing = True
                    break

            if any_missing:
                missing.append(name)

        return missing

    # ------------------------------------------------------------------
    # Method 6: create_payout
    # ------------------------------------------------------------------
    async def create_payout(
        self,
        pool,
        tenant_id: int,
        liquidation_id: int,
        amount: float,
        payment_method: str,
        payment_date,
        reference_number: Optional[str],
        notes: Optional[str],
        user_email: str,
    ) -> dict:
        """
        Creates a professional payout record.
        Auto-updates liquidation status to 'paid' if total payouts >= payout_amount.
        """
        # 1. Fetch liquidation record
        record = await pool.fetchrow(
            """
            SELECT * FROM liquidation_records
            WHERE id = $1 AND tenant_id = $2
            """,
            liquidation_id,
            tenant_id,
        )

        if not record:
            raise ValueError(
                f"Liquidation {liquidation_id} not found for tenant {tenant_id}"
            )

        # Validate: liquidation not in 'draft'
        if record["status"] == "draft":
            raise ValueError("Cannot create payout for a liquidation in 'draft' status")

        # Validate: amount > 0
        if amount <= 0:
            raise ValueError("Payout amount must be greater than 0")

        # Validate: payment_method
        valid_methods = ["transfer", "cash", "check"]
        if payment_method not in valid_methods:
            raise ValueError(
                f"Invalid payment method: {payment_method}. Must be one of {valid_methods}"
            )

        # 2. Insert payout
        payout = await pool.fetchrow(
            """
            INSERT INTO professional_payouts (
                tenant_id, liquidation_id, professional_id,
                amount, payment_method, payment_date,
                reference_number, notes
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            tenant_id,
            liquidation_id,
            record["professional_id"],
            amount,
            payment_method,
            payment_date,
            reference_number,
            notes,
        )

        # 3. Recalculate total payouts
        total_payouts = await pool.fetchval(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM professional_payouts
            WHERE liquidation_id = $1
            """,
            liquidation_id,
        )
        total_payouts = float(total_payouts)
        payout_amount = float(record["payout_amount"])

        # 4. Auto-update status to 'paid' if fully covered
        #    Prevent overpayment: new payout cannot exceed remaining balance
        remaining = payout_amount - total_payouts
        if amount > remaining and remaining > 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"El monto del pago (${amount:.2f}) excede "
                    f"el saldo restante (${remaining:.2f}). "
                    f"Total a pagar: ${payout_amount:.2f}, ya pagado: ${total_payouts:.2f}."
                ),
            )

        auto_paid = False
        current_notes = record["notes"] or {}
        if total_payouts + amount >= payout_amount and record["status"] != "paid":
            now = datetime.utcnow()
            audit_trail = current_notes.get("audit_trail", [])
            audit_trail.append(
                {
                    "action": "status_change",
                    "from": record["status"],
                    "to": "paid",
                    "by": "system",
                    "at": now.isoformat(),
                    "detail": "Auto-completed: total payouts >= payout_amount",
                }
            )
            current_notes["audit_trail"] = audit_trail

            await pool.execute(
                """
                UPDATE liquidation_records
                SET status = 'paid', paid_at = $1, notes = $2
                WHERE id = $3 AND tenant_id = $4
                """,
                now,
                current_notes,
                liquidation_id,
                tenant_id,
            )
            auto_paid = True

        # 5. Append audit trail for payout creation (reuse current_notes to preserve auto-paid entry)
        audit_trail = current_notes.get("audit_trail", [])
        audit_trail.append(
            {
                "action": "payout_created",
                "amount": amount,
                "method": payment_method,
                "by": user_email,
                "at": datetime.utcnow().isoformat(),
                "reference": reference_number,
            }
        )
        current_notes["audit_trail"] = audit_trail
        await pool.execute(
            """
            UPDATE liquidation_records
            SET notes = $1
            WHERE id = $2 AND tenant_id = $3
            """,
            current_notes,
            liquidation_id,
            tenant_id,
        )

        logger.info(
            "create_payout: created payout %s for liquidation %s, amount=%s, "
            "total_payouts=%s, auto_paid=%s",
            payout["id"],
            liquidation_id,
            amount,
            total_payouts,
            auto_paid,
        )

        # Invalidate PDF cache
        await self.invalidate_liquidation_pdf(tenant_id, liquidation_id)

        return dict(payout)

    # ------------------------------------------------------------------
    # Method 7: get_commission_config
    # ------------------------------------------------------------------
    async def get_commission_config(
        self, pool, tenant_id: int, professional_id: int
    ) -> dict:
        """
        Returns commission configuration for a professional.
        Now includes clinic_pct and change history.
        """
        rows = await pool.fetch(
            """
            SELECT pc.commission_pct, pc.clinic_pct, pc.treatment_code, tt.name AS treatment_name
            FROM professional_commissions pc
            LEFT JOIN treatment_types tt ON tt.code = pc.treatment_code AND tt.tenant_id = pc.tenant_id
            WHERE pc.tenant_id = $1 AND pc.professional_id = $2
            ORDER BY pc.treatment_code NULLS FIRST
            """,
            tenant_id,
            professional_id,
        )

        if not rows:
            # Pre-populate default commission overrides from the specifications
            dynamic_rows = await pool.fetch(
                """
                SELECT code, name FROM treatment_types
                WHERE tenant_id = $1
                  AND (
                     LOWER(code) LIKE '%endo%' OR LOWER(name) LIKE '%endo%' OR
                     LOWER(code) LIKE '%orto%' OR LOWER(name) LIKE '%orto%' OR
                     LOWER(code) LIKE '%consult%' OR LOWER(name) LIKE '%consult%'
                  )
                """,
                tenant_id,
            )

            per_treatment = []
            if dynamic_rows:
                for r in dynamic_rows:
                    code_lower = (r["code"] or "").lower()
                    name_lower = (r["name"] or "").lower()

                    if "endo" in code_lower or "endo" in name_lower:
                        comm = 60.0
                        cl = 40.0
                    elif "orto" in code_lower or "orto" in name_lower:
                        comm = 50.0
                        cl = 50.0
                    elif "consult" in code_lower or "consult" in name_lower:
                        comm = 40.0
                        cl = 60.0
                    else:
                        continue

                    per_treatment.append(
                        {
                            "treatment_code": r["code"],
                            "treatment_name": r["name"] or r["code"],
                            "commission_pct": comm,
                            "clinic_pct": cl,
                        }
                    )

            if not per_treatment:
                db_types = await pool.fetch(
                    """
                    SELECT code, name FROM treatment_types
                    WHERE tenant_id = $1 AND code = ANY($2::text[])
                    """,
                    tenant_id,
                    ["root_canal", "orthodontics", "consultation"]
                )
                name_map = {r["code"]: r["name"] for r in db_types}

                per_treatment = [
                    {
                        "treatment_code": "root_canal",
                        "treatment_name": name_map.get("root_canal", "Endodoncia"),
                        "commission_pct": 60.0,
                        "clinic_pct": 40.0,
                    },
                    {
                        "treatment_code": "orthodontics",
                        "treatment_name": name_map.get("orthodontics", "Ortodoncia"),
                        "commission_pct": 50.0,
                        "clinic_pct": 50.0,
                    },
                    {
                        "treatment_code": "consultation",
                        "treatment_name": name_map.get("consultation", "Consulta General"),
                        "commission_pct": 40.0,
                        "clinic_pct": 60.0,
                    }
                ]

            default_commission_pct = 40.0
            default_clinic_pct = 60.0
        else:
            default_commission_pct = 0.0
            default_clinic_pct = 100.0
            per_treatment = []

            for row in rows:
                if row["treatment_code"] is None:
                    default_commission_pct = float(row["commission_pct"])
                    default_clinic_pct = float(row["clinic_pct"])
                else:
                    per_treatment.append(
                        {
                            "treatment_code": row["treatment_code"],
                            "treatment_name": row["treatment_name"] or row["treatment_code"],
                            "commission_pct": float(row["commission_pct"]),
                            "clinic_pct": float(row["clinic_pct"]),
                        }
                    )

        result = {
            "professional_id": professional_id,
            "default_commission_pct": default_commission_pct,
            "default_clinic_pct": default_clinic_pct,
            "per_treatment": per_treatment,
        }

        # Include change history
        result["history"] = await self.get_commission_history(
            pool, tenant_id, professional_id
        )

        # If no config at all, add warning
        if not rows:
            result["warning"] = (
                "Sin configuración de comisiones. Mostrando valores predeterminados "
                "(Endodoncia 60/40, Ortodoncia 50/50, Consulta General 40/60)."
            )
            logger.warning(
                "get_commission_config: no config for professional %s, tenant %s. "
                "Using default template.",
                professional_id,
                tenant_id,
            )

        return result

    # ------------------------------------------------------------------
    # Method 8: upsert_commission_config (with history + clinic_pct)
    # ------------------------------------------------------------------
    async def upsert_commission_config(
        self,
        pool,
        tenant_id: int,
        professional_id: int,
        default_commission_pct: float,
        default_clinic_pct: float = 0.0,
        per_treatment: list = None,
        effective_date: date = None,
        changed_by: str = None,
    ) -> dict:
        """
        Upserts commission configuration with history tracking.
        Saves previous values to commission_history BEFORE modifying.
        Validates commission_pct + clinic_pct = 100 for all entries.
        """
        if per_treatment is None:
            per_treatment = []
        if effective_date is None:
            effective_date = datetime.now().date()

        # Validate default sum = 100
        if abs((default_commission_pct + default_clinic_pct) - 100.0) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"La suma del % profesional ({default_commission_pct}) y "
                    f"% clínica ({default_clinic_pct}) debe ser 100."
                ),
            )

        # Validate each per-treatment sum
        for entry in per_treatment:
            cp = entry.get("commission_pct", 0)
            clp = entry.get("clinic_pct", 0)
            if abs((cp + clp) - 100.0) > 0.01:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Para {entry.get('treatment_code', 'unknown')}: "
                        f"la suma del % profesional ({cp}) y % clínica ({clp}) debe ser 100."
                    ),
                )

        # Helper: record commission change in history
        async def _record_history(treatment_code, old_pct, old_clinic, new_pct, new_clinic):
            await pool.execute(
                """
                INSERT INTO commission_history (
                    tenant_id, professional_id, treatment_code,
                    old_commission_pct, new_commission_pct,
                    old_clinic_pct, new_clinic_pct,
                    changed_by, effective_date
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                tenant_id,
                professional_id,
                treatment_code,
                old_pct,
                new_pct,
                old_clinic,
                new_clinic,
                changed_by,
                effective_date,
            )

        # 1. Read OLD default values before upsert
        old_default = await pool.fetchrow(
            """
            SELECT commission_pct, clinic_pct FROM professional_commissions
            WHERE tenant_id = $1 AND professional_id = $2 AND treatment_code IS NULL
            """,
            tenant_id,
            professional_id,
        )

        # 2. Upsert default commission
        existing_default = await pool.fetchrow(
            """
            SELECT id FROM professional_commissions
            WHERE tenant_id = $1 AND professional_id = $2 AND treatment_code IS NULL
            """,
            tenant_id,
            professional_id,
        )
        if existing_default:
            await pool.execute(
                """
                UPDATE professional_commissions
                SET commission_pct = $3, clinic_pct = $4, updated_at = NOW()
                WHERE tenant_id = $1 AND professional_id = $2 AND treatment_code IS NULL
                """,
                tenant_id,
                professional_id,
                default_commission_pct,
                default_clinic_pct,
            )
        else:
            await pool.execute(
                """
                INSERT INTO professional_commissions (
                    tenant_id, professional_id, commission_pct, clinic_pct, treatment_code
                ) VALUES ($1, $2, $3, $4, NULL)
                """,
                tenant_id,
                professional_id,
                default_commission_pct,
                default_clinic_pct,
            )

        # 3. Record history for default if it changed
        if old_default:
            old_pct = float(old_default["commission_pct"])
            old_clinic = float(old_default["clinic_pct"])
            if abs(old_pct - default_commission_pct) > 0.01 or abs(old_clinic - default_clinic_pct) > 0.01:
                await _record_history(
                    None, old_pct, old_clinic,
                    default_commission_pct, default_clinic_pct,
                )
        else:
            # First time creating config
            await _record_history(
                None, None, None,
                default_commission_pct, default_clinic_pct,
            )

        # 4. Upsert per-treatment overrides
        new_treatment_codes = set()
        for entry in per_treatment:
            treatment_code = entry["treatment_code"]
            commission_pct = entry["commission_pct"]
            clinic_pct = entry.get("clinic_pct", 100.0 - commission_pct)
            new_treatment_codes.add(treatment_code)

            # Read old override before upsert
            old_override = await pool.fetchrow(
                """
                SELECT commission_pct, clinic_pct FROM professional_commissions
                WHERE tenant_id = $1 AND professional_id = $2 AND treatment_code = $3
                """,
                tenant_id,
                professional_id,
                treatment_code,
            )

            existing_override = await pool.fetchrow(
                """
                SELECT id FROM professional_commissions
                WHERE tenant_id = $1 AND professional_id = $2 AND treatment_code = $3
                """,
                tenant_id,
                professional_id,
                treatment_code,
            )
            if existing_override:
                await pool.execute(
                    """
                    UPDATE professional_commissions
                    SET commission_pct = $3, clinic_pct = $4, updated_at = NOW()
                    WHERE tenant_id = $1 AND professional_id = $2 AND treatment_code = $5
                    """,
                    tenant_id,
                    professional_id,
                    commission_pct,
                    clinic_pct,
                    treatment_code,
                )
            else:
                await pool.execute(
                    """
                    INSERT INTO professional_commissions (
                        tenant_id, professional_id, commission_pct, clinic_pct, treatment_code
                    ) VALUES ($1, $2, $3, $4, $5)
                    """,
                    tenant_id,
                    professional_id,
                    commission_pct,
                    clinic_pct,
                    treatment_code,
                )

            # Record history for override
            if old_override:
                old_op = float(old_override["commission_pct"])
                old_oc = float(old_override["clinic_pct"])
                if abs(old_op - commission_pct) > 0.01 or abs(old_oc - clinic_pct) > 0.01:
                    await _record_history(
                        treatment_code, old_op, old_oc,
                        commission_pct, clinic_pct,
                    )
            else:
                await _record_history(
                    treatment_code, None, None,
                    commission_pct, clinic_pct,
                )

        # 5. Delete existing per-treatment entries NOT in the new list
        existing_rows = await pool.fetch(
            """
            SELECT treatment_code FROM professional_commissions
            WHERE tenant_id = $1 AND professional_id = $2 AND treatment_code IS NOT NULL
            """,
            tenant_id,
            professional_id,
        )
        existing_codes = {r["treatment_code"] for r in existing_rows}
        codes_to_delete = existing_codes - new_treatment_codes

        if codes_to_delete:
            # Record history for deleted overrides
            for code in codes_to_delete:
                deleted_row = await pool.fetchrow(
                    """
                    SELECT commission_pct, clinic_pct FROM professional_commissions
                    WHERE tenant_id = $1 AND professional_id = $2 AND treatment_code = $3
                    """,
                    tenant_id,
                    professional_id,
                    code,
                )
                if deleted_row:
                    await _record_history(
                        code,
                        float(deleted_row["commission_pct"]),
                        float(deleted_row["clinic_pct"]),
                        0.0, 100.0,  # deleted = defaults to 0/100
                    )

            await pool.execute(
                """
                DELETE FROM professional_commissions
                WHERE tenant_id = $1
                  AND professional_id = $2
                  AND treatment_code = ANY($3::text[])
                """,
                tenant_id,
                professional_id,
                list(codes_to_delete),
            )

        # 6. Return updated config
        return await self.get_commission_config(pool, tenant_id, professional_id)

    # ------------------------------------------------------------------
    # Method 9: get_commission_config_at_date (point-in-time lookup)
    # ------------------------------------------------------------------
    async def get_commission_config_at_date(
        self, pool, tenant_id: int, professional_id: int, target_date: date
    ) -> dict:
        """
        Returns commission config for a professional AS IT WAS on target_date.
        Uses commission_history for point-in-time lookup with fallback chain.

        Algorithm:
        1. Search commission_history for most recent entry <= target_date
        2. If no history, use current professional_commissions value
        3. If no config exists, return 0%/100% with source='default_zero'
        """
        # Step 1: Look up default commission in history
        history_default = await pool.fetchrow(
            """
            SELECT new_commission_pct, new_clinic_pct
            FROM commission_history
            WHERE tenant_id = $1
              AND professional_id = $2
              AND treatment_code IS NULL
              AND effective_date <= $3
            ORDER BY effective_date DESC
            LIMIT 1
            """,
            tenant_id,
            professional_id,
            target_date,
        )

        if history_default:
            default_pct = float(history_default["new_commission_pct"])
            default_clinic = float(history_default["new_clinic_pct"])
            source = "history"
        else:
            # Step 2: Fallback to current config
            current = await pool.fetchrow(
                """
                SELECT commission_pct, clinic_pct FROM professional_commissions
                WHERE tenant_id = $1 AND professional_id = $2 AND treatment_code IS NULL
                """,
                tenant_id,
                professional_id,
            )
            if current:
                default_pct = float(current["commission_pct"])
                default_clinic = float(current["clinic_pct"])
                source = "current_config"
            else:
                # Step 3: No config exists — fallback to default splits
                default_pct = 40.0
                default_clinic = 60.0
                source = "default_zero"

        # Step 4: Same for per-treatment overrides (point-in-time)
        history_overrides = await pool.fetch(
            """
            SELECT DISTINCT ON (treatment_code) treatment_code,
                   new_commission_pct, new_clinic_pct
            FROM commission_history
            WHERE tenant_id = $1
              AND professional_id = $2
              AND treatment_code IS NOT NULL
              AND effective_date <= $3
            ORDER BY treatment_code, effective_date DESC, id DESC
            """,
            tenant_id,
            professional_id,
            target_date,
        )

        overrides = {}
        for row in history_overrides:
            overrides[row["treatment_code"]] = {
                "commission_pct": float(row["new_commission_pct"]),
                "clinic_pct": float(row["new_clinic_pct"]),
            }

        # Also include current overrides not in history (created before history existed)
        current_overrides = await pool.fetch(
            """
            SELECT commission_pct, clinic_pct, treatment_code
            FROM professional_commissions
            WHERE tenant_id = $1
              AND professional_id = $2
              AND treatment_code IS NOT NULL
              AND treatment_code NOT IN (
                  SELECT DISTINCT treatment_code FROM commission_history
                  WHERE tenant_id = $1
                    AND professional_id = $2
                    AND treatment_code IS NOT NULL
                    AND effective_date <= $3
              )
              AND treatment_code IS NOT NULL
            """,
            tenant_id,
            professional_id,
            target_date,
        )
        for row in current_overrides:
            if row["treatment_code"] not in overrides:
                overrides[row["treatment_code"]] = {
                    "commission_pct": float(row["commission_pct"]),
                    "clinic_pct": float(row["clinic_pct"]),
                }

        # Step 5.5: If no current config exists, pre-populate default overrides dynamically
        if source == "default_zero":
            dynamic_rows = await pool.fetch(
                """
                SELECT code, name FROM treatment_types
                WHERE tenant_id = $1
                  AND (
                     LOWER(code) LIKE '%endo%' OR LOWER(name) LIKE '%endo%' OR
                     LOWER(code) LIKE '%orto%' OR LOWER(name) LIKE '%orto%' OR
                     LOWER(code) LIKE '%consult%' OR LOWER(name) LIKE '%consult%'
                  )
                """,
                tenant_id,
            )
            if dynamic_rows:
                for r in dynamic_rows:
                    code_lower = (r["code"] or "").lower()
                    name_lower = (r["name"] or "").lower()
                    if "endo" in code_lower or "endo" in name_lower:
                        comm = 60.0
                        cl = 40.0
                    elif "orto" in code_lower or "orto" in name_lower:
                        comm = 50.0
                        cl = 50.0
                    elif "consult" in code_lower or "consult" in name_lower:
                        comm = 40.0
                        cl = 60.0
                    else:
                        continue
                    overrides[r["code"]] = {
                        "commission_pct": comm,
                        "clinic_pct": cl,
                    }
            else:
                overrides["root_canal"] = {"commission_pct": 60.0, "clinic_pct": 40.0}
                overrides["orthodontics"] = {"commission_pct": 50.0, "clinic_pct": 50.0}
                overrides["consultation"] = {"commission_pct": 40.0, "clinic_pct": 60.0}

            logger.warning(
                "get_commission_config_at_date: no config for professional %s, "
                "tenant %s at %s. Using default splits (40%% default, dynamic overrides).",
                professional_id,
                tenant_id,
                target_date,
            )

        return {
            "default_commission_pct": default_pct,
            "default_clinic_pct": default_clinic,
            "per_treatment": overrides,
            "source": source,
        }

    # ------------------------------------------------------------------
    # Method 10: get_commission_history
    # ------------------------------------------------------------------
    async def get_commission_history(
        self, pool, tenant_id: int, professional_id: int
    ) -> list:
        """
        Returns full change history for a professional's commissions.
        Ordered by effective_date DESC, created_at DESC.
        """
        rows = await pool.fetch(
            """
            SELECT ch.*, p.first_name, p.last_name
            FROM commission_history ch
            JOIN professionals p ON p.id = ch.professional_id
            WHERE ch.tenant_id = $1 AND ch.professional_id = $2
            ORDER BY ch.effective_date DESC, ch.created_at DESC
            """,
            tenant_id,
            professional_id,
        )

        history = []
        for row in rows:
            entry = {
                "id": row["id"],
                "treatment_code": row["treatment_code"],
                "treatment_name": None,  # Frontend can resolve
                "old_commission_pct": float(row["old_commission_pct"]) if row["old_commission_pct"] else None,
                "new_commission_pct": float(row["new_commission_pct"]),
                "old_clinic_pct": float(row["old_clinic_pct"]) if row["old_clinic_pct"] else None,
                "new_clinic_pct": float(row["new_clinic_pct"]),
                "changed_by": row["changed_by"],
                "effective_date": row["effective_date"].isoformat() if row["effective_date"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            history.append(entry)

        return history

    # ------------------------------------------------------------------
    # Helper: _get_commission_config (internal, returns tuple)
    # Kept for backward compatibility — returns current values only
    # ------------------------------------------------------------------
    async def _get_commission_config(
        self, pool, tenant_id: int, professional_id: int
    ) -> tuple:
        rows = await pool.fetch(
            """
            SELECT commission_pct, clinic_pct, treatment_code
            FROM professional_commissions
            WHERE tenant_id = $1 AND professional_id = $2
            """,
            tenant_id,
            professional_id,
        )

        default_pct = 0.0
        default_clinic = 100.0
        overrides = {}

        for row in rows:
            if row["treatment_code"] is None:
                default_pct = float(row["commission_pct"])
                default_clinic = float(row["clinic_pct"])
            else:
                overrides[row["treatment_code"]] = {
                    "commission_pct": float(row["commission_pct"]),
                    "clinic_pct": float(row["clinic_pct"]),
                }

        if not rows:
            logger.warning(
                "_get_commission_config: no config for professional %s, tenant %s. "
                "Using 0%% default.",
                professional_id,
                tenant_id,
            )

        return default_pct, default_clinic, overrides

    # ------------------------------------------------------------------
    # Method 9: ignore_reconciliation_discrepancy
    # ------------------------------------------------------------------
    async def ignore_reconciliation_discrepancy(
        self,
        pool,
        tenant_id: int,
        appointment_id: str,
        ignored_by: str,
    ):
        """Marks a reconciliation discrepancy as ignored. Idempotent."""
        await pool.execute("""
            INSERT INTO reconciliation_ignored (tenant_id, appointment_id, ignored_by)
            VALUES ($1, $2, $3)
            ON CONFLICT (tenant_id, appointment_id) DO NOTHING
        """)

    # ------------------------------------------------------------------
    # Helper: invalidate_liquidation_pdf
    # ------------------------------------------------------------------
    async def invalidate_liquidation_pdf(
        self, tenant_id: int, liquidation_id: int
    ) -> None:
        """
        Deletes cached PDF file for a liquidation.
        Path: /app/uploads/liquidations/{tenant_id}/{liquidation_id}.pdf
        """
        pdf_path = f"/app/uploads/liquidations/{tenant_id}/{liquidation_id}.pdf"
        try:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                logger.info(
                    "invalidate_liquidation_pdf: removed cached PDF for liquidation %s",
                    liquidation_id,
                )
        except OSError as e:
            logger.warning(
                "invalidate_liquidation_pdf: failed to remove %s: %s",
                pdf_path,
                e,
            )


# Singleton instance
liquidation_service = LiquidationService()
