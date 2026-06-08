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
