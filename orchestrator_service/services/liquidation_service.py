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
        # 1. Check idempotency
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
            logger.info(
                "generate_liquidation: existing record %s for prof %s, period %s-%s",
                existing["id"],
                professional_id,
                period_start,
                period_end,
            )
            return dict(existing)

        # 2. Get professional commissions
        commission_pct, per_treatment_map = await self._get_commission_config(
            pool, tenant_id, professional_id
        )

        # 3. Query appointments in the period for this professional
        #    Reusing the query pattern from analytics_service.get_professionals_liquidation
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
                tt.name AS treatment_name
            FROM appointments a
            LEFT JOIN treatment_types tt
                ON tt.code = a.appointment_type AND tt.tenant_id = $1
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

        # 4. Query plan payments for appointments linked to treatment plans
        plan_ids = set()
        for row in appt_rows:
            if row.get("plan_item_id"):
                # We need to resolve the plan_id from plan_item
                pass

        # Fetch plan_ids from appointments that have plan_item_id
        plan_item_ids = [
            r["appointment_id"] for r in appt_rows if r.get("plan_item_id")
        ]
        if plan_item_ids:
            plan_rows = await pool.fetch(
                """
                SELECT DISTINCT tpi.plan_id
                FROM appointments a
                JOIN treatment_plan_items tpi ON tpi.id = a.plan_item_id AND tpi.tenant_id = $1
                WHERE a.id = ANY($2) AND a.tenant_id = $1
                """,
                tenant_id,
                plan_item_ids,
            )
            plan_ids = {str(r["plan_id"]) for r in plan_rows}

        # Query plan payments
        plan_paid_map = {}
        if plan_ids:
            plan_payment_rows = await pool.fetch(
                """
                SELECT plan_id, COALESCE(SUM(amount), 0) AS total_paid
                FROM treatment_plan_payments
                WHERE tenant_id = $1 AND plan_id = ANY($2)
                GROUP BY plan_id
                """,
                tenant_id,
                list(plan_ids),
            )
            plan_paid_map = {
                str(r["plan_id"]): float(r["total_paid"]) for r in plan_payment_rows
            }

        # 5. Calculate totals
        total_billed = Decimal("0")
        total_paid = Decimal("0")
        total_commission = Decimal("0")

        for row in appt_rows:
            appt_status = row["appointment_status"] or ""
            excluded = appt_status in ("cancelled", "no_show")
            if excluded:
                continue

            billing = Decimal(str(row["billing_amount"] or 0))
            treatment_code = row["treatment_code"] or ""
            pstatus = row["payment_status"] or "pending"

            # Determine commission for this appointment
            if treatment_code in per_treatment_map:
                appt_commission_pct = per_treatment_map[treatment_code]
            else:
                appt_commission_pct = commission_pct

            appt_commission = billing * (
                Decimal(str(appt_commission_pct)) / Decimal("100")
            )
            total_commission += appt_commission
            total_billed += billing

            if pstatus == "paid":
                total_paid += billing

        # Add plan payments to total_paid
        for plan_id, paid_amount in plan_paid_map.items():
            total_paid += Decimal(str(paid_amount))

        total_pending = total_billed - total_paid
        if total_pending < 0:
            total_pending = Decimal("0")

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

        record = await pool.fetchrow(
            """
            INSERT INTO liquidation_records (
                tenant_id, professional_id, period_start, period_end,
                total_billed, total_paid, total_pending,
                commission_pct, commission_amount, payout_amount,
                status, generated_by, notes
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'generated', $11, $12)
            RETURNING *
            """,
            tenant_id,
            professional_id,
            period_start,
            period_end,
            float(total_billed),
            float(total_paid),
            float(total_pending),
            float(commission_pct),
            float(commission_amount),
            float(payout_amount),
            generated_by_email,
            {"audit_trail": audit_trail},
        )

        logger.info(
            "generate_liquidation: created record %s for prof %s, "
            "billed=%s, commission=%s%%, payout=%s",
            record["id"],
            professional_id,
            total_billed,
            commission_pct,
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
            SELECT id, first_name, last_name
            FROM professionals
            WHERE tenant_id = $1 AND is_active = true
            ORDER BY id
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
            pat_id = row["patient_id"]
            treatment_code = row["treatment_code"] or ""
            billing_amount = float(row["billing_amount"] or 0)
            pstatus = row["payment_status"] or "pending"
            plan_id = row["plan_id"]

            # Group key
            if plan_id:
                group_key = (pat_id, f"plan:{plan_id}")
                plan_ids_found.add(plan_id)
            else:
                group_key = (pat_id, treatment_code)

            if group_key not in treatment_groups_map:
                if plan_id:
                    treatment_groups_map[group_key] = {
                        "patient_id": pat_id,
                        "patient_name": (row["patient_name"] or "").strip(),
                        "patient_phone": row["patient_phone"] or "",
                        "treatment_code": treatment_code,
                        "treatment_name": row["plan_name"] or "Plan sin nombre",
                        "type": "plan",
                        "plan_id": str(plan_id),
                        "plan_name": row["plan_name"],
                        "plan_status": row["plan_status"],
                        "approved_total": float(row["plan_approved_total"] or 0),
                        "sessions": [],
                        "total_billed": float(row["plan_approved_total"] or 0),
                        "total_paid": 0.0,
                        "total_pending": 0.0,
                        "session_count": 0,
                    }
                else:
                    treatment_groups_map[group_key] = {
                        "patient_id": pat_id,
                        "patient_name": (row["patient_name"] or "").strip(),
                        "patient_phone": row["patient_phone"] or "",
                        "treatment_code": treatment_code,
                        "treatment_name": row["treatment_name"]
                        or treatment_code
                        or "Sin tratamiento",
                        "type": "appointment",
                        "plan_id": None,
                        "plan_name": None,
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

            group["sessions"].append(
                {
                    "appointment_id": row["appointment_id"],
                    "date": row["appointment_datetime"].isoformat()
                    if row["appointment_datetime"]
                    else None,
                    "status": appt_status,
                    "billing_amount": billing_amount,
                    "payment_status": pstatus,
                    "billing_notes": row["billing_notes"],
                }
            )

            group["session_count"] += 1
            if group.get("type") != "plan":
                group["total_billed"] += billing_for_totals
                if not excluded:
                    if pstatus == "paid":
                        group["total_paid"] += billing_for_totals
                    else:
                        group["total_pending"] += billing_for_totals

        # Fetch plan payments
        if plan_ids_found:
            plan_payment_rows = await pool.fetch(
                """
                SELECT plan_id, COALESCE(SUM(amount), 0) AS total_paid
                FROM treatment_plan_payments
                WHERE tenant_id = $1 AND plan_id = ANY($2)
                GROUP BY plan_id
                """,
                tenant_id,
                list(plan_ids_found),
            )
            plan_paid_map = {
                str(r["plan_id"]): float(r["total_paid"]) for r in plan_payment_rows
            }

            for group in treatment_groups_map.values():
                if group.get("type") != "plan":
                    continue
                paid = plan_paid_map.get(group["plan_id"], 0.0)
                group["total_paid"] = paid
                group["total_pending"] = max(group["total_billed"] - paid, 0.0)

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
                    "type": g.get("type", "appointment"),
                    "plan_id": g.get("plan_id"),
                    "plan_name": g.get("plan_name"),
                    "plan_status": g.get("plan_status"),
                    "approved_total": g.get("approved_total"),
                    "sessions": g["sessions"],
                    "total_billed": round(g["total_billed"], 2),
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
            WHERE liquidation_id = $1 AND tenant_id = $2
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
                "professional_name": record["professional_name"],
                "specialty": record["specialty"],
                "period_start": str(record["period_start"]),
                "period_end": str(record["period_end"]),
                "total_billed": float(record["total_billed"]),
                "total_paid": float(record["total_paid"]),
                "total_pending": float(record["total_pending"]),
                "commission_pct": float(record["commission_pct"]),
                "commission_amount": float(record["commission_amount"]),
                "payout_amount": float(record["payout_amount"]),
                "status": record["status"],
                "generated_at": record["generated_at"].isoformat()
                if record["generated_at"]
                else None,
                "approved_at": record["approved_at"].isoformat()
                if record["approved_at"]
                else None,
                "paid_at": record["paid_at"].isoformat() if record["paid_at"] else None,
                "generated_by": record["generated_by"],
                "notes": record["notes"] or {},
                "created_at": record["created_at"].isoformat()
                if record["created_at"]
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
            return None

        current_status = record["status"]

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
        auto_paid = False
        if total_payouts >= payout_amount and record["status"] != "paid":
            now = datetime.utcnow()
            existing_notes = record["notes"] or {}
            audit_trail = existing_notes.get("audit_trail", [])
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
            existing_notes["audit_trail"] = audit_trail

            await pool.execute(
                """
                UPDATE liquidation_records
                SET status = 'paid', paid_at = $1, notes = $2
                WHERE id = $3 AND tenant_id = $4
                """,
                now,
                existing_notes,
                liquidation_id,
                tenant_id,
            )
            auto_paid = True

        # 5. Append audit trail for payout creation
        existing_notes = record["notes"] or {}
        audit_trail = existing_notes.get("audit_trail", [])
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
        existing_notes["audit_trail"] = audit_trail
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
        """
        rows = await pool.fetch(
            """
            SELECT commission_pct, treatment_code
            FROM professional_commissions
            WHERE tenant_id = $1 AND professional_id = $2
            ORDER BY treatment_code NULLS FIRST
            """,
            tenant_id,
            professional_id,
        )

        default_commission_pct = 0.0
        per_treatment = []

        for row in rows:
            if row["treatment_code"] is None:
                default_commission_pct = float(row["commission_pct"])
            else:
                per_treatment.append(
                    {
                        "treatment_code": row["treatment_code"],
                        "commission_pct": float(row["commission_pct"]),
                    }
                )

        result = {
            "professional_id": professional_id,
            "default_commission_pct": default_commission_pct,
            "per_treatment": per_treatment,
        }

        # If no config at all, add warning
        if not rows:
            result["warning"] = (
                "Sin configuración de comisiones. Se aplica 0% "
                "(profesional recibe 100%)."
            )
            logger.warning(
                "get_commission_config: no config for professional %s, tenant %s. "
                "Using 0%% default.",
                professional_id,
                tenant_id,
            )

        return result

    # ------------------------------------------------------------------
    # Method 8: upsert_commission_config
    # ------------------------------------------------------------------
    async def upsert_commission_config(
        self,
        pool,
        tenant_id: int,
        professional_id: int,
        default_commission_pct: float,
        per_treatment: list,
    ) -> dict:
        """
        Upserts commission configuration for a professional.
        """
        # 1. Upsert default commission (treatment_code IS NULL)
        await pool.execute(
            """
            INSERT INTO professional_commissions (
                tenant_id, professional_id, commission_pct, treatment_code
            ) VALUES ($1, $2, $3, NULL)
            ON CONFLICT (tenant_id, professional_id, treatment_code)
            DO UPDATE SET commission_pct = $3, updated_at = NOW()
            """,
            tenant_id,
            professional_id,
            default_commission_pct,
        )

        # 2. Upsert per-treatment overrides
        new_treatment_codes = set()
        for entry in per_treatment:
            treatment_code = entry["treatment_code"]
            commission_pct = entry["commission_pct"]
            new_treatment_codes.add(treatment_code)

            await pool.execute(
                """
                INSERT INTO professional_commissions (
                    tenant_id, professional_id, commission_pct, treatment_code
                ) VALUES ($1, $2, $3, $4)
                ON CONFLICT (tenant_id, professional_id, treatment_code)
                DO UPDATE SET commission_pct = $3, updated_at = NOW()
                """,
                tenant_id,
                professional_id,
                commission_pct,
                treatment_code,
            )

        # 3. Delete existing per-treatment entries NOT in the new list
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
            await pool.execute(
                """
                DELETE FROM professional_commissions
                WHERE tenant_id = $1
                  AND professional_id = $2
                  AND treatment_code = ANY($3)
                """,
                tenant_id,
                professional_id,
                list(codes_to_delete),
            )

        # 4. Return updated config
        return await self.get_commission_config(pool, tenant_id, professional_id)

    # ------------------------------------------------------------------
    # Helper: _get_commission_config (internal, returns tuple)
    # ------------------------------------------------------------------
    async def _get_commission_config(
        self, pool, tenant_id: int, professional_id: int
    ) -> tuple:
        """
        Internal helper: returns (default_commission_pct, {treatment_code: pct}).
        Used by generate_liquidation for commission lookup.
        """
        rows = await pool.fetch(
            """
            SELECT commission_pct, treatment_code
            FROM professional_commissions
            WHERE tenant_id = $1 AND professional_id = $2
            """,
            tenant_id,
            professional_id,
        )

        default_pct = 0.0
        overrides = {}

        for row in rows:
            if row["treatment_code"] is None:
                default_pct = float(row["commission_pct"])
            else:
                overrides[row["treatment_code"]] = float(row["commission_pct"])

        if not rows:
            logger.warning(
                "_get_commission_config: no config for professional %s, tenant %s. "
                "Using 0%% default.",
                professional_id,
                tenant_id,
            )

        return default_pct, overrides

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
