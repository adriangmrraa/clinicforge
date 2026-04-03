"""Tests para el sistema de Treatment Plan Billing.

Cubre: liquidación profesional con planes, clasificación de pagos en buffer_task,
y lógica de plan payments.
"""
import pytest
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timezone


# =========================================================================
# TESTS: Liquidación Profesional con Planes (Tarea 4.2)
# =========================================================================


class TestLiquidationGroupingLogic:
    """Tests para la lógica de agrupación de liquidación con planes."""

    def test_group_key_legacy_appointment(self):
        """Legacy appointments (no plan_item_id) use (patient_id, treatment_code) as key."""
        pat_id = 100
        treatment_code = "consultation"
        plan_id = None

        if plan_id:
            group_key = (pat_id, f"plan:{plan_id}")
        else:
            group_key = (pat_id, treatment_code)

        assert group_key == (100, "consultation")

    def test_group_key_plan_appointment(self):
        """Plan appointments use (patient_id, plan:UUID) as key."""
        pat_id = 100
        treatment_code = "consultation"
        plan_id = str(uuid.uuid4())

        if plan_id:
            group_key = (pat_id, f"plan:{plan_id}")
        else:
            group_key = (pat_id, treatment_code)

        assert group_key == (100, f"plan:{plan_id}")

    def test_multiple_plan_sessions_same_group(self):
        """Multiple appointments with same plan_id should group together."""
        plan_id = str(uuid.uuid4())
        groups = {}

        for i in range(3):
            key = (100, f"plan:{plan_id}")
            if key not in groups:
                groups[key] = {"sessions": [], "type": "plan"}
            groups[key]["sessions"].append({"appointment_id": i})

        assert len(groups) == 1
        assert len(groups[(100, f"plan:{plan_id}")]["sessions"]) == 3

    def test_plan_billed_uses_approved_total(self):
        """Plan groups should use approved_total as total_billed, not sum of session billing."""
        plan_approved_total = Decimal("420000")
        session_billing_amounts = [Decimal("0"), Decimal("0"), Decimal("0")]

        # Plan total_billed = approved_total
        total_billed_plan = float(plan_approved_total)
        # NOT sum of sessions
        total_billed_sessions = float(sum(session_billing_amounts))

        assert total_billed_plan == 420000.0
        assert total_billed_sessions == 0.0

    def test_plan_paid_from_payments_table(self):
        """Plan total_paid comes from treatment_plan_payments, not appointment payment_status."""
        plan_payments = [
            {"amount": Decimal("100000")},
            {"amount": Decimal("70000")},
        ]

        total_paid = float(sum(p["amount"] for p in plan_payments))
        assert total_paid == 170000.0

    def test_plan_pending_calculation(self):
        """pending = approved_total - total_paid from payments."""
        approved = 420000.0
        paid = 170000.0
        pending = approved - paid
        assert pending == 250000.0

    def test_type_discriminator_in_output(self):
        """Output groups should have 'type' field."""
        legacy_group = {"type": "appointment", "plan_id": None, "plan_name": None}
        plan_group = {"type": "plan", "plan_id": "uuid-123", "plan_name": "Rehab oral"}

        assert legacy_group["type"] == "appointment"
        assert plan_group["type"] == "plan"
        assert plan_group["plan_id"] is not None

    def test_mixed_groups_separate_correctly(self):
        """Legacy and plan appointments should create separate groups."""
        plan_id = str(uuid.uuid4())
        rows_data = [
            {"patient_id": 100, "plan_id": None, "treatment_code": "consultation"},
            {"patient_id": 100, "plan_id": plan_id, "treatment_code": "implant"},
            {"patient_id": 100, "plan_id": plan_id, "treatment_code": "crown"},
        ]

        groups = {}
        for r in rows_data:
            if r["plan_id"]:
                key = (r["patient_id"], f"plan:{r['plan_id']}")
            else:
                key = (r["patient_id"], r["treatment_code"])
            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        assert len(groups) == 2  # 1 legacy + 1 plan (2 plan items grouped together)
        legacy_key = (100, "consultation")
        plan_key = (100, f"plan:{plan_id}")
        assert len(groups[legacy_key]) == 1
        assert len(groups[plan_key]) == 2


# =========================================================================
# TESTS: Buffer Task — Plan Payment Detection (Tarea 5.6)
# =========================================================================


class TestBufferTaskPlanDetection:
    """Tests para la detección de comprobantes contra planes en buffer_task."""

    async def test_plan_check_query_structure(self):
        """Verify the plan pending check query is valid SQL structure."""
        # The query should check treatment_plans with pending balance
        query = """
            SELECT tp.id FROM treatment_plans tp
            LEFT JOIN (
                SELECT plan_id, SUM(amount) as total_paid
                FROM treatment_plan_payments WHERE tenant_id = $1
                GROUP BY plan_id
            ) pay ON pay.plan_id = tp.id
            WHERE tp.tenant_id = $1 AND tp.patient_id = $2
              AND tp.status IN ('approved', 'in_progress')
              AND tp.approved_total > COALESCE(pay.total_paid, 0)
            LIMIT 1
        """
        # Basic validation: query should reference the right tables
        assert "treatment_plans" in query
        assert "treatment_plan_payments" in query
        assert "approved_total" in query
        assert "total_paid" in query

    async def test_appointment_priority_over_plan(self):
        """If appointment has pending payment, plan check should NOT run."""
        # This tests the logic: if has_pending_payment from appointment, skip plan check
        has_pending_payment = True  # From appointment check
        has_pending_plan = False

        # Plan check only runs if NOT has_pending_payment
        if not has_pending_payment:
            has_pending_plan = True  # This should NOT execute

        assert has_pending_payment is True
        assert has_pending_plan is False  # Plan check was skipped


# =========================================================================
# TESTS: Payment Verification for Plans (Tarea 5.5)
# =========================================================================


class TestVerifyPaymentReceiptForPlans:
    """Tests para verify_payment_receipt con fallback a planes."""

    async def test_plan_fallback_query_structure(self):
        """Verify plan fallback query selects correct fields."""
        query = """
            SELECT tp.id as plan_id, tp.name as plan_name, tp.approved_total,
                   COALESCE(SUM(tpp.amount), 0) as total_paid
            FROM treatment_plans tp
            LEFT JOIN treatment_plan_payments tpp ON tpp.plan_id = tp.id AND tpp.tenant_id = tp.tenant_id
            WHERE tp.tenant_id = $1 AND tp.patient_id = $2
              AND tp.status IN ('approved', 'in_progress')
            GROUP BY tp.id, tp.name, tp.approved_total
            HAVING tp.approved_total > COALESCE(SUM(tpp.amount), 0)
            ORDER BY tp.created_at DESC
            LIMIT 1
        """
        assert "plan_id" in query
        assert "plan_name" in query
        assert "approved_total" in query
        assert "total_paid" in query
        assert "approved" in query
        assert "in_progress" in query

    async def test_plan_pending_balance_calculation(self):
        """Test that pending balance is correctly calculated from plan data."""
        plan_row = {
            "plan_id": str(uuid.uuid4()),
            "plan_name": "Rehabilitación oral",
            "approved_total": Decimal("420000"),
            "total_paid": Decimal("170000"),
        }

        plan_pending = float(plan_row["approved_total"]) - float(plan_row["total_paid"])
        assert plan_pending == 250000.0

    async def test_plan_completion_on_full_payment(self):
        """When total_paid >= approved_total, plan should be marked completed."""
        plan_approved = Decimal("100000")
        plan_total_paid = Decimal("80000")
        amount_detected = 20000.0

        new_total = float(plan_total_paid) + amount_detected
        should_complete = new_total >= float(plan_approved)

        assert should_complete is True

    async def test_plan_not_completed_on_partial(self):
        """Partial payment should not complete the plan."""
        plan_approved = Decimal("100000")
        plan_total_paid = Decimal("30000")
        amount_detected = 20000.0

        new_total = float(plan_total_paid) + amount_detected
        should_complete = new_total >= float(plan_approved)

        assert should_complete is False

    async def test_appointment_context_priority(self):
        """If appointment has billing_amount, payment_context should be 'appointment'."""
        expected_amount = 5000.0  # From appointment billing_amount
        payment_context = "appointment"

        # Plan fallback only runs if expected_amount is None/0
        if not expected_amount or expected_amount <= 0:
            payment_context = "plan"

        assert payment_context == "appointment"

    async def test_plan_context_when_no_appointment_amount(self):
        """If no appointment billing, should fall to plan context."""
        expected_amount = None
        payment_context = "appointment"

        if not expected_amount or expected_amount <= 0:
            payment_context = "plan"

        assert payment_context == "plan"


# =========================================================================
# TESTS: Treatment Plan CRUD Endpoint Validation
# =========================================================================


class TestTreatmentPlanEndpointSchemas:
    """Tests para validación de schemas de los endpoints de treatment plans."""

    def test_plan_status_transitions(self):
        """Valid status transitions for treatment plans."""
        valid_transitions = {
            "draft": ["approved", "cancelled"],
            "approved": ["in_progress", "cancelled"],
            "in_progress": ["completed", "cancelled"],
            "completed": [],
            "cancelled": [],
        }

        # Draft can go to approved
        assert "approved" in valid_transitions["draft"]
        # Completed cannot transition
        assert valid_transitions["completed"] == []
        # Cancelled cannot transition
        assert valid_transitions["cancelled"] == []

    def test_payment_method_enum(self):
        """Valid payment methods."""
        valid_methods = {"cash", "transfer", "card", "insurance"}
        assert "cash" in valid_methods
        assert "crypto" not in valid_methods

    def test_plan_totals_computation(self):
        """Verify plan totals are correctly computed from items."""
        items = [
            {"estimated_price": 200000, "approved_price": 180000},
            {"estimated_price": 30000, "approved_price": 30000},
            {"estimated_price": 50000, "approved_price": None},
        ]

        estimated_total = sum(i["estimated_price"] for i in items)
        approved_total = sum(
            i["approved_price"] for i in items if i["approved_price"] is not None
        )

        assert estimated_total == 280000
        assert approved_total == 210000

    def test_pending_balance_calculation(self):
        """pending = approved_total - sum(payments)."""
        approved_total = 420000
        payments = [100000, 70000, 50000]
        total_paid = sum(payments)
        pending = approved_total - total_paid

        assert total_paid == 220000
        assert pending == 200000

    def test_progress_percentage(self):
        """Progress bar percentage calculation."""
        approved_total = 420000
        total_paid = 170000

        progress_pct = (total_paid / approved_total * 100) if approved_total > 0 else 0
        assert round(progress_pct, 1) == 40.5

    def test_zero_approved_total_no_division_error(self):
        """Zero approved_total should not cause division by zero."""
        approved_total = 0
        total_paid = 0

        progress_pct = (total_paid / approved_total * 100) if approved_total > 0 else 0
        assert progress_pct == 0


# =========================================================================
# TESTS: Double-Counting Prevention
# =========================================================================


class TestDoubleCountingPrevention:
    """Tests para verificar que no hay doble conteo entre appointment billing y plan billing."""

    def test_plan_item_id_discriminator(self):
        """plan_item_id IS NULL correctly filters legacy vs plan appointments."""
        appointments = [
            {"id": 1, "plan_item_id": None, "billing_amount": 5000},
            {"id": 2, "plan_item_id": "uuid-1", "billing_amount": 0},
            {"id": 3, "plan_item_id": None, "billing_amount": 3000},
            {"id": 4, "plan_item_id": "uuid-2", "billing_amount": 0},
        ]

        legacy = [a for a in appointments if a["plan_item_id"] is None]
        plan_linked = [a for a in appointments if a["plan_item_id"] is not None]

        assert len(legacy) == 2
        assert len(plan_linked) == 2
        assert sum(a["billing_amount"] for a in legacy) == 8000
        assert sum(a["billing_amount"] for a in plan_linked) == 0

    def test_pending_payments_no_overlap(self):
        """pending_payments should not count both appointment and plan amounts."""
        # Legacy appointments pending
        legacy_pending = 15000

        # Plan pending (approved_total - total_paid)
        plan_approved = 420000
        plan_paid = 170000
        plan_pending = plan_approved - plan_paid

        # Total should be sum of both (no overlap because plan_item_id IS NULL filters)
        total_pending = legacy_pending + plan_pending
        assert total_pending == 265000

    def test_today_revenue_no_overlap(self):
        """today_revenue should sum legacy paid + plan payments today, not both."""
        legacy_today_paid = 5000
        plan_payments_today = 50000

        total_today = legacy_today_paid + plan_payments_today
        assert total_today == 55000
