import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta
import sys
import os
import uuid

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator_service.main import (
    confirm_appointment as _confirm_appointment_tool,
    ARG_TZ
)

# Call underlying coroutine directly in tests
confirm_appointment = _confirm_appointment_tool.coroutine


@pytest.mark.asyncio
async def test_confirm_by_appointment_id_success():
    """
    If appointment_id is provided, confirm it, update status, and return success string.
    """
    phone = "+5491123456789"
    tenant_id = 1
    apt_id = "550e8400-e29b-41d4-a716-446655440000"
    
    # Future appointment (e.g. 5 days from now)
    future_time_utc = datetime.now(timezone.utc) + timedelta(days=5)
    future_time_utc = future_time_utc.replace(hour=15, minute=15, second=0, microsecond=0)
    
    mock_appointment = {
        "id": uuid.UUID(apt_id),
        "appointment_datetime": future_time_utc,
        "status": "scheduled",
        "patient_id": 42,
        "patient_first_name": "Juan",
        "patient_last_name": "Perez",
        "patient_phone": phone,
        "professional_name": "Dra. Laura Delgado",
        "treatment_name": "Consulta"
    }

    with (
        patch("orchestrator_service.main.db") as mock_db,
        patch("orchestrator_service.main.current_customer_phone") as mock_phone_ctx,
        patch("orchestrator_service.main.current_tenant_id") as mock_tenant_ctx,
        patch("orchestrator_service.main.get_active_tz") as mock_tz_ctx,
    ):
        mock_phone_ctx.get.return_value = phone
        mock_tenant_ctx.get.return_value = tenant_id
        mock_tz_ctx.return_value = ARG_TZ # UTC-3
        
        mock_db.pool.fetchrow = AsyncMock(return_value=mock_appointment)
        mock_db.pool.execute = AsyncMock(return_value=None)

        result = await confirm_appointment(appointment_id=apt_id)

        # Assert status is success and contains expected details
        assert "SUCCESS" in result
        assert "confirmado" in result
        assert "Dra. Laura Delgado" in result
        assert "Consulta" in result
        assert "WARNING" not in result
        
        # Verify db update called with tenant_id filter and correct ID
        mock_db.pool.execute.assert_called_once_with(
            "UPDATE appointments SET status = 'confirmed', updated_at = NOW() WHERE id = $1 AND tenant_id = $2",
            uuid.UUID(apt_id), tenant_id
        )


@pytest.mark.asyncio
async def test_confirm_by_appointment_id_not_found():
    """
    If appointment_id is not found, return an error.
    """
    phone = "+5491123456789"
    tenant_id = 1
    apt_id = "550e8400-e29b-41d4-a716-446655440001"

    with (
        patch("orchestrator_service.main.db") as mock_db,
        patch("orchestrator_service.main.current_customer_phone") as mock_phone_ctx,
        patch("orchestrator_service.main.current_tenant_id") as mock_tenant_ctx,
    ):
        mock_phone_ctx.get.return_value = phone
        mock_tenant_ctx.get.return_value = tenant_id
        
        mock_db.pool.fetchrow = AsyncMock(return_value=None)

        result = await confirm_appointment(appointment_id=apt_id)

        assert "ERROR" in result
        assert "No se encontró ningún turno" in result


@pytest.mark.asyncio
async def test_confirm_by_phone_closest_with_warning():
    """
    If appointment_id not provided, find by phone, filter by target_date,
    select closest to approximate_time, confirm it, and return warning about discrepancy.
    """
    phone = "+5491123456789"
    tenant_id = 1
    
    # Let's say target date is 2026-06-05
    target_dt_local = datetime(2026, 6, 5, 15, 15, 0, tzinfo=ARG_TZ) # 15:15
    other_dt_local = datetime(2026, 6, 5, 10, 0, 0, tzinfo=ARG_TZ)   # 10:00
    
    # Conver to UTC for database mocks
    target_dt_utc = target_dt_local.astimezone(timezone.utc)
    other_dt_utc = other_dt_local.astimezone(timezone.utc)
    
    mock_patient = {
        "id": 42,
        "first_name": "Juan",
        "last_name": "Perez"
    }
    
    mock_appointments = [
        {
            "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
            "appointment_datetime": other_dt_utc,
            "status": "scheduled",
            "patient_id": 42,
            "patient_first_name": "Juan",
            "patient_last_name": "Perez",
            "patient_phone": phone,
            "professional_name": "Dra. Laura Delgado",
            "treatment_name": "Consulta"
        },
        {
            "id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
            "appointment_datetime": target_dt_utc,
            "status": "scheduled",
            "patient_id": 42,
            "patient_first_name": "Juan",
            "patient_last_name": "Perez",
            "patient_phone": phone,
            "professional_name": "Dra. Laura Delgado",
            "treatment_name": "Consulta"
        }
    ]

    with (
        patch("orchestrator_service.main.db") as mock_db,
        patch("orchestrator_service.main.current_customer_phone") as mock_phone_ctx,
        patch("orchestrator_service.main.current_tenant_id") as mock_tenant_ctx,
        patch("orchestrator_service.main.get_active_tz") as mock_tz_ctx,
    ):
        mock_phone_ctx.get.return_value = phone
        mock_tenant_ctx.get.return_value = tenant_id
        mock_tz_ctx.return_value = ARG_TZ
        
        # 1. Fetch patient, 2. Fetch appointments
        mock_db.pool.fetchrow = AsyncMock(return_value=mock_patient)
        mock_db.pool.fetch = AsyncMock(return_value=mock_appointments)
        mock_db.pool.execute = AsyncMock(return_value=None)

        result = await confirm_appointment(
            approximate_time="a las 3", # 15:00
            target_date="05/06/2026"
        )

        assert "SUCCESS" in result
        assert "confirmado" in result
        assert "WARNING" in result
        assert "El paciente mencionó las 15:00 hs, pero el turno está agendado a las 15:15 hs" in result
        
        # Assert database updated the 15:15 appointment (id "22222222...")
        mock_db.pool.execute.assert_called_once_with(
            "UPDATE appointments SET status = 'confirmed', updated_at = NOW() WHERE id = $1 AND tenant_id = $2",
            uuid.UUID("22222222-2222-2222-2222-222222222222"), tenant_id
        )
