"""
Tests for email_service.py — send_payment_email functionality.

Covers:
- SMTP configuration check (skip if not configured)
- Template selection based on tenant country_code
- Email sending with correct subject and HTML
- Handling missing patient email (should skip gracefully)
- Error handling (SMTP failures)
"""

import pytest
from unittest.mock import MagicMock, patch, call
import os
import email
from email import policy


def get_decoded_html_from_raw_email(raw_email: str) -> str:
    """Parse raw email string and return decoded HTML body."""
    msg = email.message_from_string(raw_email, policy=policy.default)
    html_part = None
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            html_part = part
            break
    if html_part:
        payload = html_part.get_payload(decode=True)
        return payload.decode("utf-8")
    return ""


# ─── send_payment_email tests ───


def test_send_payment_email_smtp_not_configured():
    """If SMTP_HOST or SMTP_USER missing, should skip and return False."""
    with patch.dict(os.environ, {"SMTP_HOST": "", "SMTP_USER": ""}):
        from orchestrator_service.email_service import EmailService

        service = EmailService()
        assert service.smtp_host == ""
        assert service.smtp_user == ""

        result = service.send_payment_email(
            to_email="patient@example.com",
            country_code="AR",
            patient_name="Juan Pérez",
            clinic_name="Clínica Salud",
            appointment_date="15/04/2026",
            appointment_time="10:30",
            treatment="Limpieza dental",
            amount="$25.000",
            payment_method="Transferencia bancaria",
            clinic_address="Av. Siempreviva 123",
            clinic_phone="+54 11 1234-5678",
        )
        assert result is False


@patch("smtplib.SMTP_SSL")
@patch("smtplib.SMTP")
def test_send_payment_email_success_argentina_spanish(mock_smtp, mock_smtp_ssl):
    """Successful email sending for Argentina (Spanish template)."""
    # Configure environment
    with patch.dict(
        os.environ,
        {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "user@example.com",
            "SMTP_PASS": "password",
            "SMTP_SENDER": "sender@example.com",
            "CLINIC_NAME": "Test Clinic",
        },
    ):
        from orchestrator_service.email_service import EmailService

        service = EmailService()

        # Mock SMTP connection (non‑SSL)
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        mock_smtp_ssl.return_value = mock_server

        result = service.send_payment_email(
            to_email="patient@example.com",
            country_code="AR",
            patient_name="Juan Pérez",
            clinic_name="Clínica Salud",
            appointment_date="15/04/2026",
            appointment_time="10:30",
            treatment="Limpieza dental",
            amount="$25.000",
            payment_method="Transferencia bancaria",
            clinic_address="Av. Siempreviva 123",
            clinic_phone="+54 11 1234-5678",
        )

        # Verify SMTP was called correctly
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "password")
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()

        # Verify email content (subject and body)
        sendmail_args = mock_server.sendmail.call_args
        assert sendmail_args[0][0] == "sender@example.com"
        assert sendmail_args[0][1] == ["patient@example.com"]
        email_body = sendmail_args[0][2]
        decoded_html = get_decoded_html_from_raw_email(email_body)
        assert "Confirmación de pago" in decoded_html
        assert "Juan Pérez" in decoded_html
        assert "Limpieza dental" in decoded_html
        assert "$25.000" in decoded_html

        assert result is True


@patch("smtplib.SMTP_SSL")
@patch("smtplib.SMTP")
def test_send_payment_email_success_united_states_english(mock_smtp, mock_smtp_ssl):
    """Successful email sending for US (English template)."""
    with patch.dict(
        os.environ,
        {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "user@example.com",
            "SMTP_PASS": "password",
            "SMTP_SENDER": "sender@example.com",
        },
    ):
        from orchestrator_service.email_service import EmailService

        service = EmailService()

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        result = service.send_payment_email(
            to_email="patient@example.com",
            country_code="US",
            patient_name="John Doe",
            clinic_name="Health Clinic",
            appointment_date="04/15/2026",
            appointment_time="10:30 AM",
            treatment="Dental Cleaning",
            amount="$500",
            payment_method="Bank Transfer",
            clinic_address="123 Main St",
            clinic_phone="+1 555-1234",
        )

        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "password")
        mock_server.sendmail.assert_called_once()

        # Verify English subject and content
        sendmail_args = mock_server.sendmail.call_args
        email_body = sendmail_args[0][2]
        decoded_html = get_decoded_html_from_raw_email(email_body)
        assert "Payment Confirmation" in decoded_html
        assert "John Doe" in decoded_html
        assert "Dental Cleaning" in decoded_html
        assert "$500" in decoded_html

        assert result is True


@patch("smtplib.SMTP_SSL")
@patch("smtplib.SMTP")
def test_send_payment_email_success_france_french(mock_smtp, mock_smtp_ssl):
    """Successful email sending for France (French template)."""
    with patch.dict(
        os.environ,
        {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "user@example.com",
            "SMTP_PASS": "password",
            "SMTP_SENDER": "sender@example.com",
        },
    ):
        from orchestrator_service.email_service import EmailService

        service = EmailService()

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        result = service.send_payment_email(
            to_email="patient@example.com",
            country_code="FR",
            patient_name="Jean Dupont",
            clinic_name="Clinique Santé",
            appointment_date="15/04/2026",
            appointment_time="10:30",
            treatment="Nettoyage dentaire",
            amount="€200",
            payment_method="Virement bancaire",
            clinic_address="123 Rue de la Paix",
            clinic_phone="+33 1 23 45 67 89",
        )

        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "password")
        mock_server.sendmail.assert_called_once()

        # Verify French subject and content
        sendmail_args = mock_server.sendmail.call_args
        email_body = sendmail_args[0][2]
        decoded_html = get_decoded_html_from_raw_email(email_body)
        assert "Confirmation de paiement" in decoded_html
        assert "Jean Dupont" in decoded_html
        assert "Nettoyage dentaire" in decoded_html
        assert "€200" in decoded_html

        assert result is True


@patch("smtplib.SMTP_SSL")
@patch("smtplib.SMTP")
def test_send_payment_email_success_brazil_portuguese(mock_smtp, mock_smtp_ssl):
    """Successful email sending for Brazil (Portuguese template)."""
    with patch.dict(
        os.environ,
        {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "user@example.com",
            "SMTP_PASS": "password",
            "SMTP_SENDER": "sender@example.com",
        },
    ):
        from orchestrator_service.email_service import EmailService

        service = EmailService()

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        result = service.send_payment_email(
            to_email="patient@example.com",
            country_code="BR",
            patient_name="João Silva",
            clinic_name="Clínica Saúde",
            appointment_date="15/04/2026",
            appointment_time="10:30",
            treatment="Limpeza dental",
            amount="R$ 500",
            payment_method="Transferência bancária",
            clinic_address="Av. Paulista 123",
            clinic_phone="+55 11 98765-4321",
        )

        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "password")
        mock_server.sendmail.assert_called_once()

        # Verify Portuguese subject and content
        sendmail_args = mock_server.sendmail.call_args
        email_body = sendmail_args[0][2]
        decoded_html = get_decoded_html_from_raw_email(email_body)
        assert "Confirmação de Pagamento" in decoded_html
        assert "João Silva" in decoded_html
        assert "Limpeza dental" in decoded_html
        assert "R$ 500" in decoded_html

        assert result is True


@patch("smtplib.SMTP_SSL")
@patch("smtplib.SMTP")
def test_send_payment_email_missing_optional_clinic_details(mock_smtp, mock_smtp_ssl):
    """Missing clinic_address and clinic_phone should be replaced with '—'."""
    with patch.dict(
        os.environ,
        {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "user@example.com",
            "SMTP_PASS": "password",
            "SMTP_SENDER": "sender@example.com",
        },
    ):
        from orchestrator_service.email_service import EmailService

        service = EmailService()

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        mock_smtp_ssl.return_value = mock_server

        result = service.send_payment_email(
            to_email="patient@example.com",
            country_code="AR",
            patient_name="Test",
            clinic_name="Test Clinic",
            appointment_date="01/01/2026",
            appointment_time="00:00",
            treatment="Test",
            amount="$0",
            payment_method="Test",
            # No clinic_address or clinic_phone
        )

        # Verify SMTP was called
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "password")
        mock_server.sendmail.assert_called_once()

        # Verify email content contains placeholder for missing address/phone
        sendmail_args = mock_server.sendmail.call_args
        email_body = sendmail_args[0][2]
        decoded_html = get_decoded_html_from_raw_email(email_body)
        assert "—" in decoded_html  # placeholder for missing address/phone


@patch("smtplib.SMTP")
def test_send_payment_email_smtp_failure(mock_smtp):
    """SMTP exception should be caught and return False."""
    with patch.dict(
        os.environ,
        {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "user@example.com",
            "SMTP_PASS": "password",
            "SMTP_SENDER": "sender@example.com",
        },
    ):
        from orchestrator_service.email_service import EmailService

        service = EmailService()

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        mock_server.login.side_effect = Exception("SMTP authentication failed")

        result = service.send_payment_email(
            to_email="patient@example.com",
            country_code="AR",
            patient_name="Juan Pérez",
            clinic_name="Clínica Salud",
            appointment_date="15/04/2026",
            appointment_time="10:30",
            treatment="Limpieza dental",
            amount="$25.000",
            payment_method="Transferencia bancaria",
        )

        assert result is False


def test_send_payment_email_empty_to_email():
    """Empty to_email should skip and return False."""
    with patch.dict(
        os.environ,
        {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "user@example.com",
            "SMTP_PASS": "password",
            "SMTP_SENDER": "sender@example.com",
        },
    ):
        from orchestrator_service.email_service import EmailService

        service = EmailService()

        # No SMTP calls should happen
        with patch.object(service, "smtp_host", new="smtp.example.com"):
            with patch.object(service, "smtp_user", new="user@example.com"):
                # Mock SMTP to ensure it's not called
                with patch("smtplib.SMTP") as mock_smtp_class:
                    result = service.send_payment_email(
                        to_email="",
                        country_code="AR",
                        patient_name="Juan Pérez",
                        clinic_name="Clínica Salud",
                        appointment_date="15/04/2026",
                        appointment_time="10:30",
                        treatment="Limpieza dental",
                        amount="$25.000",
                        payment_method="Transferencia bancaria",
                    )

                    # SMTP should not be called
                    assert not mock_smtp_class.called
                    assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
