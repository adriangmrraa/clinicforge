import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from db import db

logger = logging.getLogger("analytics")


class AnalyticsService:
    async def get_professionals_summary(
        self, start_date: datetime, end_date: datetime, tenant_id: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Calculates performance metrics for all professionals within the given date range.
        Using REAL data from appointments, patients, and clinical records.
        """
        try:
            # 1. Fetch basic professional info (solo profesionales dentales, no secretarias)
            professionals = await db.pool.fetch(
                """
                SELECT p.id, p.first_name, p.last_name, p.specialty, p.google_calendar_id 
                FROM professionals p
                LEFT JOIN users u ON p.user_id = u.id AND u.role IN ('professional', 'ceo')
                WHERE p.is_active = true AND p.tenant_id = $1
            """,
                tenant_id,
            )

            results = []

            for prof in professionals:
                prof_id = prof["id"]
                full_name = f"{prof['first_name']} {prof['last_name'] or ''}".strip()

                # 2. Aggregations from APPOINTMENTS
                # Status counts
                stats = await db.pool.fetchrow(
                    """
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
                """,
                    prof_id,
                    start_date,
                    end_date,
                    tenant_id,
                )

                total_apts = stats["total"] or 0
                completed_apts = stats["completed"] or 0
                cancelled_apts = stats["cancelled"] or 0

                # Rates
                completion_rate = (
                    (completed_apts / total_apts) * 100 if total_apts > 0 else 0
                )
                cancellation_rate = (
                    (cancelled_apts / total_apts) * 100 if total_apts > 0 else 0
                )

                # 3. Revenue Estimation — multi-source: billing_amount > treatment base_price > clinical_records
                revenue_row = await db.pool.fetchrow(
                    """
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
                """,
                    prof_id,
                    start_date,
                    end_date,
                    tenant_id,
                )
                estimated_revenue = float(revenue_row["total_revenue"] or 0)

                # 4. Retention Analysis (Patients seen in this period who had prior visits)
                # "Returning Patient": A patient who has an appointment BEFORE start_date
                returning_patients_count = await db.pool.fetchval(
                    """
                    SELECT COUNT(DISTINCT patient_id)
                    FROM appointments a1
                    WHERE professional_id = $1
                    AND appointment_datetime BETWEEN $2 AND $3
                    AND EXISTS (
                        SELECT 1 FROM appointments a2
                        WHERE a2.patient_id = a1.patient_id
                        AND a2.appointment_datetime < $2
                    )
                """,
                    prof_id,
                    start_date,
                    end_date,
                )

                retention_rate = (
                    (returning_patients_count / stats["unique_patients"]) * 100
                    if stats["unique_patients"] > 0
                    else 0
                )

                no_show_count = stats["no_show"] or 0
                no_show_rate = (
                    (no_show_count / total_apts) * 100 if total_apts > 0 else 0
                )
                avg_revenue = estimated_revenue / total_apts if total_apts > 0 else 0

                # 5. Top treatment for this professional
                top_treatment = await db.pool.fetchrow(
                    """
                    SELECT a.appointment_type, tt.name, COUNT(*) as cnt
                    FROM appointments a
                    LEFT JOIN treatment_types tt ON a.appointment_type = tt.code AND tt.tenant_id = a.tenant_id
                    WHERE a.professional_id = $1
                    AND a.appointment_datetime BETWEEN $2 AND $3
                    AND a.tenant_id = $4
                    AND a.status IN ('completed', 'confirmed', 'scheduled')
                    GROUP BY a.appointment_type, tt.name
                    ORDER BY cnt DESC LIMIT 1
                """,
                    prof_id,
                    start_date,
                    end_date,
                    tenant_id,
                )

                # 6. Busiest day of the week
                busiest_day = await db.pool.fetchrow(
                    """
                    SELECT EXTRACT(DOW FROM appointment_datetime)::int as dow, COUNT(*) as cnt
                    FROM appointments
                    WHERE professional_id = $1
                    AND appointment_datetime BETWEEN $2 AND $3
                    AND tenant_id = $4
                    AND status IN ('completed', 'confirmed', 'scheduled')
                    GROUP BY dow ORDER BY cnt DESC LIMIT 1
                """,
                    prof_id,
                    start_date,
                    end_date,
                    tenant_id,
                )
                days_es = [
                    "Domingo",
                    "Lunes",
                    "Martes",
                    "Miércoles",
                    "Jueves",
                    "Viernes",
                    "Sábado",
                ]

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

                results.append(
                    {
                        "id": prof_id,
                        "name": full_name,
                        "specialty": prof["specialty"] or "General",
                        "metrics": {
                            "total_appointments": total_apts,
                            "unique_patients": stats["unique_patients"] or 0,
                            "completion_rate": round(completion_rate, 1),
                            "cancellation_rate": round(cancellation_rate, 1),
                            "no_show_rate": round(no_show_rate, 1),
                            "revenue": estimated_revenue,
                            "avg_revenue_per_appointment": round(avg_revenue, 0),
                            "retention_rate": round(retention_rate, 1),
                            "paid_appointments": revenue_row["paid_count"] or 0,
                            "partial_payments": revenue_row["partial_count"] or 0,
                        },
                        "top_treatment": {
                            "name": (
                                top_treatment["name"]
                                or top_treatment["appointment_type"]
                                or "N/A"
                            )
                            if top_treatment
                            else "N/A",
                            "count": top_treatment["cnt"] if top_treatment else 0,
                        },
                        "busiest_day": days_es[busiest_day["dow"]]
                        if busiest_day
                        else "N/A",
                        "tags": tags,
                    }
                )

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
            completion_rate = (
                (completed_apts / total_apts) * 100 if total_apts > 0 else 0
            )
            cancellation_rate = (
                (cancelled_apts / total_apts) * 100 if total_apts > 0 else 0
            )
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
                (returning_patients_count / unique_patients) * 100
                if unique_patients > 0
                else 0
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

    async def get_professionals_liquidation(
        self,
        pool,
        tenant_id: int,
        start_date,
        end_date,
        professional_id=None,
        payment_status=None,
    ) -> dict:
        """
        Liquidación detallada por profesional: appointments con trazabilidad completa.
        Agrupa por profesional → (paciente, tratamiento) → sesiones individuales.
        """
        try:
            # Build dynamic query with optional filters
            param_counter = 3  # $1=tenant_id, $2=start_date, $3=end_date
            extra_conditions = ""
            extra_params: list = []

            if professional_id is not None:
                param_counter += 1
                extra_conditions += f" AND a.professional_id = ${param_counter}"
                extra_params.append(professional_id)

            if payment_status and payment_status != "all":
                param_counter += 1
                extra_conditions += f" AND a.payment_status = ${param_counter}"
                extra_params.append(payment_status)

            query = f"""
                SELECT
                    a.id AS appointment_id,
                    a.appointment_datetime,
                    a.status AS appointment_status,
                    a.appointment_type,
                    a.payment_status,
                    COALESCE(a.billing_amount, tt.base_price, 0) AS billing_amount,
                    a.billing_notes,
                    a.notes AS appointment_notes,
                    p.id AS professional_id,
                    p.first_name || ' ' || COALESCE(p.last_name, '') AS professional_name,
                    p.specialty,
                    pat.id AS patient_id,
                    pat.first_name || ' ' || COALESCE(pat.last_name, '') AS patient_name,
                    pat.phone_number AS patient_phone,
                    tt.code AS treatment_code,
                    tt.name AS treatment_name,
                    cr.clinical_notes,
                    cr.diagnosis,
                    a.plan_item_id,
                    tpi.plan_id,
                    tp.name AS plan_name,
                    tp.approved_total AS plan_approved_total,
                    tp.status AS plan_status
                FROM appointments a
                JOIN professionals p ON p.id = a.professional_id AND p.tenant_id = $1
                JOIN patients pat ON pat.id = a.patient_id AND pat.tenant_id = $1
                LEFT JOIN treatment_types tt ON tt.code = a.appointment_type AND tt.tenant_id = $1
                LEFT JOIN treatment_plan_items tpi ON tpi.id = a.plan_item_id AND tpi.tenant_id = $1
                LEFT JOIN treatment_plans tp ON tp.id = tpi.plan_id AND tp.tenant_id = $1
                LEFT JOIN LATERAL (
                    SELECT cr2.clinical_notes, cr2.diagnosis
                    FROM clinical_records cr2
                    WHERE cr2.patient_id = a.patient_id
                      AND cr2.professional_id = a.professional_id
                      AND cr2.record_date = a.appointment_datetime::date
                      AND cr2.tenant_id = $1
                    ORDER BY cr2.created_at DESC
                    LIMIT 1
                ) cr ON true
                WHERE a.tenant_id = $1
                    AND a.appointment_datetime >= $2
                    AND a.appointment_datetime < ($3::date + INTERVAL '1 day')
                    AND a.status != 'deleted'
                    {extra_conditions}
                ORDER BY p.id, pat.id, a.appointment_type,
                  CASE
                    WHEN a.payment_status = 'paid' THEN 0
                    WHEN a.payment_status = 'partial' THEN 1
                    WHEN a.billing_amount > 0 THEN 2
                    ELSE 3
                  END,
                  a.appointment_datetime
            """

            rows = await db.pool.fetch(
                query, tenant_id, start_date, end_date, *extra_params
            )

            # --- Aggregation in Python ---
            # professionals_map: { prof_id: { meta, summary, treatment_groups_map } }
            # treatment_groups_map: { group_key: { meta, sessions, totals } }
            # group_key = (patient_id, f"plan:{plan_id}") for plan appointments
            #           = (patient_id, treatment_code)    for legacy appointments
            professionals_map: dict = {}
            all_patient_ids: set = set()
            plan_ids_found: set = set()

            for row in rows:
                prof_id = row["professional_id"]
                pat_id = row["patient_id"]
                treatment_code = row["treatment_code"] or ""
                billing_amount = float(row["billing_amount"] or 0)
                pstatus = row["payment_status"] or "pending"
                plan_id = row["plan_id"]

                # Initialise professional entry
                if prof_id not in professionals_map:
                    professionals_map[prof_id] = {
                        "id": prof_id,
                        "name": (row["professional_name"] or "").strip(),
                        "specialty": row["specialty"] or "General",
                        "summary": {
                            "billed": 0.0,
                            "paid": 0.0,
                            "pending": 0.0,
                            "appointments": 0,
                            "patients": set(),
                        },
                        "treatment_groups_map": {},
                    }

                prof_entry = professionals_map[prof_id]
                tg_map = prof_entry["treatment_groups_map"]

                # Group by plan_id when linked to a plan, otherwise by (patient_id, treatment_code)
                if plan_id:
                    group_key = (pat_id, f"plan:{plan_id}")
                    plan_ids_found.add(plan_id)
                else:
                    group_key = (pat_id, treatment_code)

                # Initialise treatment group
                if group_key not in tg_map:
                    if plan_id:
                        tg_map[group_key] = {
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
                            # total_billed will be overwritten after plan_payments query
                            "total_billed": float(row["plan_approved_total"] or 0),
                            "total_paid": 0.0,
                            "total_pending": 0.0,
                            "session_count": 0,
                        }
                    else:
                        tg_map[group_key] = {
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

                group = tg_map[group_key]

                # Merge clinical notes
                notes_parts = []
                if row["appointment_notes"]:
                    notes_parts.append(row["appointment_notes"])
                if row["clinical_notes"]:
                    notes_parts.append(row["clinical_notes"])
                merged_notes = " | ".join(notes_parts) if notes_parts else None

                appt_status = row["appointment_status"] or ""
                # Cancelled/no_show appointments are shown in the row but excluded from revenue totals
                excluded_from_totals = appt_status in ("cancelled", "no_show")
                billing_for_totals = 0.0 if excluded_from_totals else billing_amount

                group["sessions"].append(
                    {
                        "appointment_id": row["appointment_id"],
                        "date": row["appointment_datetime"].isoformat()
                        if row["appointment_datetime"]
                        else None,
                        "status": appt_status,
                        "billing_amount": billing_amount,  # original, always shown
                        "payment_status": pstatus,
                        "billing_notes": row["billing_notes"],
                        "clinical_notes": merged_notes,
                    }
                )

                # Accumulate group totals (cancelled/no_show count 0)
                # For plan groups: billed/paid/pending come from plan-level payment query below
                # For appointment groups: accumulate per-session billing as before
                group["session_count"] += 1
                if group.get("type") != "plan":
                    group["total_billed"] += billing_for_totals
                    if not excluded_from_totals:
                        if pstatus == "paid":
                            group["total_paid"] += billing_for_totals
                        else:
                            group["total_pending"] += billing_for_totals

                # Accumulate professional summary
                # For plan groups we defer the amount contribution until after plan_payments query
                summary = prof_entry["summary"]
                if group.get("type") != "plan":
                    summary["billed"] += billing_for_totals
                    if not excluded_from_totals:
                        if pstatus == "paid":
                            summary["paid"] += billing_for_totals
                        else:
                            summary["pending"] += billing_for_totals
                summary["appointments"] += 1
                summary["patients"].add(pat_id)

                all_patient_ids.add(pat_id)

            # --- Fetch plan payments and resolve plan group totals ---
            if plan_ids_found:
                plan_payment_rows = await db.pool.fetch(
                    """
                    SELECT plan_id, COALESCE(SUM(amount), 0) AS total_paid
                    FROM treatment_plan_payments
                    WHERE tenant_id = $1 AND plan_id = ANY($2)
                    GROUP BY plan_id
                    """,
                    tenant_id,
                    list(plan_ids_found),
                )
                plan_paid_map: dict = {
                    str(r["plan_id"]): float(r["total_paid"]) for r in plan_payment_rows
                }

                # Update plan groups with correct paid/pending and add to professional summary
                for prof_entry in professionals_map.values():
                    summary = prof_entry["summary"]
                    for group in prof_entry["treatment_groups_map"].values():
                        if group.get("type") != "plan":
                            continue
                        paid = plan_paid_map.get(group["plan_id"], 0.0)
                        group["total_paid"] = paid
                        group["total_pending"] = max(group["total_billed"] - paid, 0.0)
                        # Now contribute plan amounts to professional summary
                        summary["billed"] += group["total_billed"]
                        summary["paid"] += group["total_paid"]
                        summary["pending"] += group["total_pending"]

            # --- Build final response structure ---
            total_billed = 0.0
            total_paid = 0.0
            total_pending = 0.0
            total_appointments = 0
            total_patients: set = set()

            professionals_list = []
            for prof_entry in professionals_map.values():
                summary = prof_entry["summary"]
                # Convert patients set → count
                patient_count = len(summary["patients"])
                summary_out = {
                    "billed": round(summary["billed"], 2),
                    "paid": round(summary["paid"], 2),
                    "pending": round(summary["pending"], 2),
                    "appointments": summary["appointments"],
                    "patients": patient_count,
                }

                # Sort treatment groups by billed DESC, sessions by date ASC
                groups_sorted = sorted(
                    prof_entry["treatment_groups_map"].values(),
                    key=lambda g: g["total_billed"],
                    reverse=True,
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

                professionals_list.append(
                    {
                        "id": prof_entry["id"],
                        "name": prof_entry["name"],
                        "specialty": prof_entry["specialty"],
                        "summary": summary_out,
                        "treatment_groups": treatment_groups_out,
                    }
                )

                # Global totals
                total_billed += summary["billed"]
                total_paid += summary["paid"]
                total_pending += summary["pending"]
                total_appointments += summary["appointments"]
                total_patients.update(prof_entry["summary"]["patients"])

            # Sort professionals by billed DESC
            professionals_list.sort(key=lambda x: x["summary"]["billed"], reverse=True)

            return {
                "period": {"start": str(start_date), "end": str(end_date)},
                "totals": {
                    "billed": round(total_billed, 2),
                    "paid": round(total_paid, 2),
                    "pending": round(total_pending, 2),
                    "appointments": total_appointments,
                    "patients": len(total_patients),
                },
                "professionals": professionals_list,
            }

        except Exception as e:
            logger.error(f"Error get_professionals_liquidation: {e}", exc_info=True)
            raise


analytics_service = AnalyticsService()
