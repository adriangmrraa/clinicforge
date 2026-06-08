import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, date
from decimal import Decimal
from fastapi import HTTPException
import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator_service.services.liquidation_service import LiquidationService


@pytest.mark.asyncio
async def test_generate_liquidation_commission_only_for_paid():
    """
    Test that generate_liquidation sums to commission_amount and total_paid ONLY if the appointment is 'paid'.
    Unpaid appointments should still be included in total_billed but not in commission/total_paid.
    """
    service = LiquidationService()
    tenant_id = 1
    professional_id = 42
    period_start = date(2026, 6, 1)
    period_end = date(2026, 6, 3)
    generated_by = "test@clinicforge.com"

    # Fake placeholder return
    placeholder_record = {"id": 100}
    
    # Fake appointments: one paid ($100), one pending ($50), one cancelled ($200)
    fake_appointments = [
        {
            "appointment_id": 1,
            "appointment_datetime": datetime(2026, 6, 1, 10, 0),
            "appointment_status": "completed",
            "appointment_type": "ENDO",
            "payment_status": "paid",
            "billing_amount": Decimal("100.00"),
            "treatment_code": "ENDO",
            "treatment_name": "Endodoncia",
            "plan_item_id": None
        },
        {
            "appointment_id": 2,
            "appointment_datetime": datetime(2026, 6, 2, 11, 0),
            "appointment_status": "completed",
            "appointment_type": "CONSULT",
            "payment_status": "pending",
            "billing_amount": Decimal("50.00"),
            "treatment_code": "CONSULT",
            "treatment_name": "Consulta",
            "plan_item_id": None
        },
        {
            "appointment_id": 3,
            "appointment_datetime": datetime(2026, 6, 3, 12, 0),
            "appointment_status": "cancelled",
            "appointment_type": "ENDO",
            "payment_status": "paid",
            "billing_amount": Decimal("200.00"),
            "treatment_code": "ENDO",
            "treatment_name": "Endodoncia",
            "plan_item_id": None
        }
    ]

    mock_pool = MagicMock()
    mock_pool.fetchrow = AsyncMock(side_effect=[
        placeholder_record,  # First insert (placeholder)
        {
            "id": 100,
            "tenant_id": tenant_id,
            "professional_id": professional_id,
            "period_start": period_start,
            "period_end": period_end,
            "total_billed": 150.0,  # 100 + 50 (cancelled is excluded)
            "total_paid": 100.0,    # only the paid one
            "total_pending": 50.0,
            "commission_pct": 30.0,
            "commission_amount": 30.0,  # 30% of $100
            "payout_amount": 30.0,
            "status": "generated",
            "generated_by": generated_by,
            "notes": {"audit_trail": []},
            "created_at": datetime.utcnow()
        }  # Update return
    ])
    mock_pool.fetch = AsyncMock(return_value=fake_appointments)

    # Mock commission config lookup: default 30% commission
    fake_config = {
        "default_commission_pct": 30.0,
        "per_treatment": {},
        "source": "current_config"
    }
    
    with patch.object(service, "get_commission_config_at_date", AsyncMock(return_value=fake_config)):
        result = await service.generate_liquidation(
            mock_pool, tenant_id, professional_id, period_start, period_end, generated_by
        )

        assert result["id"] == 100
        assert result["total_billed"] == 150.0   # 100 + 50 (cancelled is excluded)
        assert result["total_paid"] == 100.0     # Only paid
        assert result["total_pending"] == 50.0   # Billed - paid
        assert result["commission_amount"] == 30.0 # 30% of paid $100


@pytest.mark.asyncio
async def test_update_liquidation_status_blocks_approved_if_missing_commission():
    """
    Test that update_liquidation_status raises HTTPException(400) if new_status is 'approved'
    and there are treatments without commission configured (default_zero source).
    """
    service = LiquidationService()
    tenant_id = 1
    liquidation_id = 100
    user_email = "test@clinicforge.com"

    fake_liquidation = {
        "id": liquidation_id,
        "tenant_id": tenant_id,
        "professional_id": 42,
        "period_start": date(2026, 6, 1),
        "period_end": date(2026, 6, 30),
        "status": "generated",
        "notes": {"audit_trail": []}
    }

    mock_pool = MagicMock()
    mock_pool.fetchrow = AsyncMock(return_value=fake_liquidation)

    # Mock _check_treatments_without_commission to return missing treatments
    with patch.object(
        service, "_check_treatments_without_commission", AsyncMock(return_value=["Endodoncia"])
    ):
        with pytest.raises(HTTPException) as exc_info:
            await service.update_liquidation_status(
                mock_pool, tenant_id, liquidation_id, "approved", user_email
            )
        
        assert exc_info.value.status_code == 400
        assert "Hay tratamientos sin comisión configurada: Endodoncia" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_commission_config_returns_defaults_when_empty():
    """
    Test that get_commission_config returns default commission splits (Endodoncia, Ortodoncia, Consulta General)
    when no configuration row is found in the database.
    """
    service = LiquidationService()
    tenant_id = 1
    professional_id = 42

    mock_pool = MagicMock()
    # No rows returned for professional commissions
    mock_pool.fetch = AsyncMock(side_effect=[
        [],  # Fetch rows in get_commission_config
        [
            {"code": "root_canal", "name": "Endodoncia"},
            {"code": "orthodontics", "name": "Ortodoncia"},
            {"code": "consultation", "name": "Consulta General"},
        ],  # Fetch rows in get_commission_config for defaults
        []   # Fetch rows in get_commission_history
    ])

    config = await service.get_commission_config(mock_pool, tenant_id, professional_id)

    assert config["default_commission_pct"] == 40.0
    assert config["default_clinic_pct"] == 60.0
    assert len(config["per_treatment"]) == 3
    assert config["per_treatment"][0]["treatment_code"] == "root_canal"
    assert config["per_treatment"][0]["commission_pct"] == 60.0
    assert config["per_treatment"][0]["clinic_pct"] == 40.0


@pytest.mark.asyncio
async def test_generate_liquidation_raises_http_exception_if_no_appointments():
    """
    Test that generate_liquidation raises HTTPException with 400 status code
    and cleans up placeholder when there are no appointments in the period.
    """
    service = LiquidationService()
    tenant_id = 1
    professional_id = 42
    period_start = date(2026, 6, 1)
    period_end = date(2026, 6, 30)
    generated_by = "test@clinicforge.com"

    mock_pool = MagicMock()
    # Return placeholder on first insert, then return empty array for appointments
    mock_pool.fetchrow = AsyncMock(return_value={"id": 100})
    mock_pool.fetch = AsyncMock(return_value=[])  # Empty appt_rows
    mock_pool.execute = AsyncMock()  # For DELETE query

    with pytest.raises(HTTPException) as exc_info:
        await service.generate_liquidation(
            mock_pool, tenant_id, professional_id, period_start, period_end, generated_by
        )

    assert exc_info.value.status_code == 400
    assert "No se encontraron turnos registrados" in exc_info.value.detail
    # Check that DELETE placeholder was executed
    mock_pool.execute.assert_called_once()
    args, _ = mock_pool.execute.call_args
    assert "DELETE FROM liquidation_records" in args[0]


@pytest.mark.asyncio
async def test_generate_liquidation_proportional_plan_payment():
    """
    Test that generate_liquidation calculates proportional payment for treatment plan appointments.
    """
    service = LiquidationService()
    tenant_id = 1
    professional_id = 42
    period_start = date(2026, 6, 1)
    period_end = date(2026, 6, 3)
    generated_by = "test@clinicforge.com"

    placeholder_record = {"id": 100}

    # Fake appointments:
    # 1. Normal appointment: paid, billing $100 -> paid $100
    # 2. Plan appointment: billing $200. Plan approved total: $500. Plan paid total: $250.
    #    Proportional ratio = 250 / 500 = 0.5. Proportional paid = 200 * 0.5 = 100.
    fake_appointments = [
        {
            "appointment_id": 1,
            "appointment_datetime": datetime(2026, 6, 1, 10, 0),
            "appointment_status": "completed",
            "appointment_type": "ENDO",
            "payment_status": "paid",
            "billing_amount": Decimal("100.00"),
            "treatment_code": "ENDO",
            "treatment_name": "Endodoncia",
            "plan_item_id": None,
            "plan_id": None,
            "plan_status": None,
            "plan_approved_total": None
        },
        {
            "appointment_id": 2,
            "appointment_datetime": datetime(2026, 6, 2, 11, 0),
            "appointment_status": "completed",
            "appointment_type": "CONSULT",
            "payment_status": "pending",
            "billing_amount": Decimal("200.00"),
            "treatment_code": "CONSULT",
            "treatment_name": "Consulta",
            "plan_item_id": 10,
            "plan_id": 5,
            "plan_status": "approved",
            "plan_approved_total": Decimal("500.00")
        }
    ]

    mock_pool = MagicMock()
    # Mock pool.fetch for:
    # 1. appointments query
    # 2. treatment_plan_payments query (returns plan_id=5, total_paid=250.0)
    mock_pool.fetch = AsyncMock(side_effect=[
        fake_appointments,
        [{"plan_id": 5, "total_paid": Decimal("250.00")}]
    ])

    mock_pool.fetchrow = AsyncMock(side_effect=[
        placeholder_record,  # First insert
        {
            "id": 100,
            "tenant_id": tenant_id,
            "professional_id": professional_id,
            "period_start": period_start,
            "period_end": period_end,
            "total_billed": 300.0,   # 100 + 200
            "total_paid": 200.0,     # 100 (normal paid) + 100 (proportional plan)
            "total_pending": 100.0,  # 300 - 200
            "commission_pct": 30.0,
            "commission_amount": 60.0,  # 30% of paid $200
            "payout_amount": 60.0,
            "status": "generated",
            "generated_by": generated_by,
            "notes": {"audit_trail": []},
            "created_at": datetime.utcnow()
        }  # Update return
    ])

    # Default 30% commission
    fake_config = {
        "default_commission_pct": 30.0,
        "per_treatment": [],
        "source": "current_config"
    }

    with patch.object(service, "get_commission_config_at_date", AsyncMock(return_value=fake_config)):
        result = await service.generate_liquidation(
            mock_pool, tenant_id, professional_id, period_start, period_end, generated_by
        )

        assert result["id"] == 100
        assert result["total_billed"] == 300.0
        assert result["total_paid"] == 200.0
        assert result["total_pending"] == 100.0
        assert result["commission_amount"] == 60.0


@pytest.mark.asyncio
async def test_get_liquidation_detail_proportional_and_unified_grouping():
    """
    Test that get_liquidation_detail groups by (patient_id, treatment_code) and
    calculates proportional session payments correctly.
    """
    service = LiquidationService()
    tenant_id = 1
    liquidation_id = 100

    # 1. Mock the liquidation record
    fake_record = {
        "id": liquidation_id,
        "tenant_id": tenant_id,
        "professional_id": 42,
        "period_start": date(2026, 6, 1),
        "period_end": date(2026, 6, 30),
        "total_billed": 300.0,
        "total_paid": 200.0,
        "total_pending": 100.0,
        "commission_pct": 30.0,
        "commission_amount": 60.0,
        "payout_amount": 60.0,
        "status": "generated",
        "generated_by": "admin@clinicforge.com",
        "notes": {"audit_trail": []},
        "professional_name": "Dr. John Doe",
        "specialty": "Dentist"
    }

    # 2. Mock the appointments (same patient, same treatment code, but one is plan, one is not)
    fake_appointments = [
        {
            "appointment_id": 1,
            "appointment_datetime": datetime(2026, 6, 1, 10, 0),
            "appointment_status": "completed",
            "appointment_type": "ENDO",
            "payment_status": "paid",
            "billing_amount": Decimal("100.00"),
            "billing_notes": "First session",
            "appointment_notes": "Some notes",
            "notes": "Some notes",
            "plan_item_id": None,
            "patient_id": 10,
            "patient_name": "Alice Smith",
            "patient_phone": "123456",
            "treatment_code": "ENDO",
            "treatment_name": "Endodoncia",
            "plan_id": None,
            "plan_name": None,
            "plan_approved_total": None,
            "plan_status": None
        },
        {
            "appointment_id": 2,
            "appointment_datetime": datetime(2026, 6, 2, 11, 0),
            "appointment_status": "completed",
            "appointment_type": "ENDO",
            "payment_status": "pending",
            "billing_amount": Decimal("200.00"),
            "billing_notes": "Second session",
            "appointment_notes": "Plan session",
            "notes": "Plan session",
            "plan_item_id": 20,
            "patient_id": 10,
            "patient_name": "Alice Smith",
            "patient_phone": "123456",
            "treatment_code": "ENDO",
            "treatment_name": "Endodoncia",
            "plan_id": 5,
            "plan_name": "Tratamiento de Conducto",
            "plan_approved_total": Decimal("500.00"),
            "plan_status": "approved"
        }
    ]

    # 3. Mock the plan payment (for plan_id=5, total_paid=250.0 -> ratio 0.5)
    fake_plan_payments = [
        {"plan_id": 5, "total_paid": Decimal("250.00")}
    ]

    mock_pool = MagicMock()
    mock_pool.fetchrow = AsyncMock(return_value=fake_record)
    mock_pool.fetch = AsyncMock(side_effect=[
        fake_appointments,
        fake_plan_payments,
        []  # Empty payouts list
    ])

    result = await service.get_liquidation_detail(mock_pool, tenant_id, liquidation_id)

    assert result is not None
    assert result["liquidation"]["professional_name"] == "Dr. John Doe"
    assert result["liquidation"]["id"] == liquidation_id

    groups = result["treatment_groups"]
    # Verify we only have 1 unified group for (patient_id=10, treatment_code="ENDO")
    assert len(groups) == 1
    group = groups[0]
    assert group["patient_id"] == 10
    assert group["treatment_code"] == "ENDO"
    assert group["total_billed"] == 300.0   # 100 + 200
    assert group["total_paid"] == 200.0     # 100 (non-plan paid) + 100 (plan proportional: 200 * 0.5)
    assert group["total_pending"] == 100.0  # 300 - 200
    assert len(group["sessions"]) == 2


@pytest.mark.asyncio
async def test_get_professionals_liquidation_proportional_and_unified_grouping():
    """
    Test that get_professionals_liquidation in AnalyticsService correctly groups by
    (patient_id, treatment_code) and calculates proportional payments.
    """
    from orchestrator_service.analytics_service import AnalyticsService
    service = AnalyticsService()
    tenant_id = 1
    start_date = date(2026, 6, 1)
    end_date = date(2026, 6, 30)

    # Fake query results for appointments
    fake_appointments = [
        {
            "appointment_id": 1,
            "appointment_datetime": datetime(2026, 6, 1, 10, 0),
            "appointment_status": "completed",
            "appointment_type": "ENDO",
            "payment_status": "paid",
            "billing_amount": Decimal("100.00"),
            "billing_notes": "First session",
            "appointment_notes": "Some notes",
            "notes": "Some notes",
            "plan_item_id": None,
            "professional_id": 42,
            "professional_name": "Dr. John Doe",
            "specialty": "Dentist",
            "patient_id": 10,
            "patient_name": "Alice Smith",
            "patient_phone": "123456",
            "treatment_code": "ENDO",
            "treatment_name": "Endodoncia",
            "clinical_notes": "Clinical note 1",
            "diagnosis": "Diagnostico 1",
            "plan_id": None,
            "plan_name": None,
            "plan_approved_total": None,
            "plan_status": None
        },
        {
            "appointment_id": 2,
            "appointment_datetime": datetime(2026, 6, 2, 11, 0),
            "appointment_status": "completed",
            "appointment_type": "ENDO",
            "payment_status": "pending",
            "billing_amount": Decimal("200.00"),
            "billing_notes": "Second session",
            "appointment_notes": "Plan session",
            "notes": "Plan session",
            "plan_item_id": 20,
            "professional_id": 42,
            "professional_name": "Dr. John Doe",
            "specialty": "Dentist",
            "patient_id": 10,
            "patient_name": "Alice Smith",
            "patient_phone": "123456",
            "treatment_code": "ENDO",
            "treatment_name": "Endodoncia",
            "clinical_notes": None,
            "diagnosis": None,
            "plan_id": 5,
            "plan_name": "Tratamiento de Conducto",
            "plan_approved_total": Decimal("500.00"),
            "plan_status": "approved"
        }
    ]

    # Fake plan payments
    fake_plan_payments = [
        {"plan_id": 5, "total_paid": Decimal("250.00")}
    ]

    with patch("orchestrator_service.analytics_service.db.pool") as mock_pool:
        mock_pool.fetch = AsyncMock(side_effect=[
            fake_appointments,
            fake_plan_payments
        ])

        result = await service.get_professionals_liquidation(
            mock_pool, tenant_id, start_date, end_date, professional_id=42
        )

        assert result is not None
        assert "professionals" in result
        profs = result["professionals"]
        assert len(profs) == 1
        prof = profs[0]
        assert prof["name"] == "Dr. John Doe"
        assert prof["summary"]["billed"] == 300.0
        assert prof["summary"]["paid"] == 200.0
        assert prof["summary"]["pending"] == 100.0

        groups = prof["treatment_groups"]
        assert len(groups) == 1
        group = groups[0]
        assert group["patient_id"] == 10
        assert group["treatment_code"] == "ENDO"
        assert group["total_billed"] == 300.0
        assert group["total_paid"] == 200.0
        assert group["total_pending"] == 100.0
        assert len(group["sessions"]) == 2

