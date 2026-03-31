"""
Integration test for payment email trigger in verify_payment_receipt tool.
Tests that successful payment verification triggers send_payment_email with correct parameters.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator_service.main import (
    verify_payment_receipt,
    current_customer_phone,
    current_tenant_id,
)


@pytest.mark.asyncio
async def test_verify_payment_receipt_triggers_payment_email():
    """
    When verify_payment_receipt succeeds (holder_match and amount_match),
    it should call email_service.send_payment_email with patient and appointment details.
    """
    # Mock context variables
    phone = "+5491123456789"
    tenant_id = "test-tenant-id"

    # Mock tenant data (with country_code, clinic_name, address, phone)
    mock_tenant = {
        "bank_cbu": "1234567890123456789012",
        "bank_alias": "clinica.salud",
        "bank_holder_name": "Clinica Salud S.A.",
        "consultation_price": 5000.0,
        "country_code": "AR",
        "clinic_name": "Clínica Salud",
        "address": "Av. Siempre Viva 123",
        "phone": "+54112345678",
    }

    # Mock appointment data (including patient email)
    mock_appointment = {
        "id": "appointment-id",
        "status": "scheduled",
        "billing_amount": 2500.0,
        "payment_status": "pending",
        "appointment_datetime": "2026-04-15 10:00:00",
        "appointment_type": "limpieza",
        "professional_id": "prof-id",
        "payment_receipt_data": None,
        "first_name": "Juan",
        "last_name": "Pérez",
        "prof_name": "Dr. García",
        "prof_price": 5000.0,
        "appointment_name": "Limpieza Dental",
        "email": "juan.perez@example.com",  # patient email
    }

    # Mock receipt description with holder name
    receipt_description = "Transferencia a Clinica Salud S.A. por $2500"
    amount_detected = "2500"

    with (
        patch("orchestrator_service.main.db") as mock_db,
        patch("orchestrator_service.main.email_service") as mock_email_service,
        patch("orchestrator_service.main.current_customer_phone") as mock_phone_ctx,
        patch("orchestrator_service.main.current_tenant_id") as mock_tenant_ctx,
    ):
        # Setup context mocks
        mock_phone_ctx.get.return_value = phone
        mock_tenant_ctx.get.return_value = tenant_id

        # Mock database queries
        mock_db.pool.fetchrow.side_effect = [
            mock_tenant,  # tenant query
            mock_appointment,  # appointment query
        ]
        mock_db.pool.fetchval.return_value = None  # treatment price lookup
        mock_db.pool.fetchrow.return_value = None  # receipt file lookup
        mock_db.pool.execute = AsyncMock()  # appointment update

        # Mock email service
        mock_email_service.send_payment_email.return_value = True

        # Call the tool
        result = await verify_payment_receipt(
            receipt_description=receipt_description,
            amount_detected=amount_detected,
            appointment_id="appointment-id",
        )

        # Assert success response
        assert "✅ Comprobante verificado correctamente" in result

        # Assert email was called with correct parameters
        mock_email_service.send_payment_email.assert_called_once()

        call_args = mock_email_service.send_payment_email.call_args
        # Check key parameters
        assert call_args[1]["to_email"] == "juan.perez@example.com"
        assert call_args[1]["country_code"] == "AR"
        assert call_args[1]["patient_name"] == "Juan Pérez"
        assert call_args[1]["clinic_name"] == "Clínica Salud"
        assert call_args[1]["amount"] == "2500"
        # Additional assertions can be added for date/time formatting

        # Assert appointment was updated
        mock_db.pool.execute.assert_called()


@pytest.mark.asyncio
async def test_verify_payment_receipt_no_email_skips_sending():
    """
    If patient has no email, verify_payment_receipt should skip email sending.
    """
    phone = "+5491123456789"
    tenant_id = "test-tenant-id"

    mock_tenant = {
        "bank_cbu": "1234567890123456789012",
        "bank_alias": "clinica.salud",
        "bank_holder_name": "Clinica Salud S.A.",
        "consultation_price": 5000.0,
        "country_code": "AR",
        "clinic_name": "Clínica Salud",
        "address": "Av. Siempre Viva 123",
        "phone": "+54112345678",
    }

    # Appointment without email
    mock_appointment = {
        "id": "appointment-id",
        "status": "scheduled",
        "billing_amount": 2500.0,
        "payment_status": "pending",
        "appointment_datetime": "2026-04-15 10:00:00",
        "appointment_type": "limpieza",
        "professional_id": "prof-id",
        "payment_receipt_data": None,
        "first_name": "Juan",
        "last_name": "Pérez",
        "prof_name": "Dr. García",
        "prof_price": 5000.0,
        "appointment_name": "Limpieza Dental",
        "email": None,  # no email
    }

    receipt_description = "Transferencia a Clinica Salud S.A. por $2500"
    amount_detected = "2500"

    with (
        patch("orchestrator_service.main.db") as mock_db,
        patch("orchestrator_service.main.email_service") as mock_email_service,
        patch("orchestrator_service.main.current_customer_phone") as mock_phone_ctx,
        patch("orchestrator_service.main.current_tenant_id") as mock_tenant_ctx,
    ):
        mock_phone_ctx.get.return_value = phone
        mock_tenant_ctx.get.return_value = tenant_id

        mock_db.pool.fetchrow.side_effect = [mock_tenant, mock_appointment]
        mock_db.pool.fetchval.return_value = None
        mock_db.pool.fetchrow.return_value = None
        mock_db.pool.execute = AsyncMock()

        # Call the tool
        result = await verify_payment_receipt(
            receipt_description=receipt_description,
            amount_detected=amount_detected,
            appointment_id="appointment-id",
        )

        # Assert success but email not sent
        assert "✅ Comprobamento verificado correctamente" in result
        mock_email_service.send_payment_email.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
