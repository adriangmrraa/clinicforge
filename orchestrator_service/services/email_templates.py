"""
Email templates for payment confirmation emails, keyed by language.

Language selection is based on tenant country_code via _language_from_country().
Templates contain placeholders for patient name, appointment details, payment amount, etc.
"""

import logging

logger = logging.getLogger(__name__)


def _language_from_country(country_code: str) -> str:
    """
    Map ISO 3166‑1 alpha‑2 country code to ISO 639‑1 language code.

    Defaults to Spanish ('es') for unknown or unsupported countries.
    """
    if not country_code:
        return "es"

    country_code = country_code.upper().strip()

    # Core mapping: country → primary language
    mapping = {
        # Spanish‑speaking countries
        "AR": "es",  # Argentina
        "MX": "es",  # México
        "CO": "es",  # Colombia
        "CL": "es",  # Chile
        "PE": "es",  # Perú
        "EC": "es",  # Ecuador
        "UY": "es",  # Uruguay
        "PY": "es",  # Paraguay
        "VE": "es",  # Venezuela
        "BO": "es",  # Bolivia
        "CR": "es",  # Costa Rica
        "PA": "es",  # Panamá
        "DO": "es",  # República Dominicana
        "GT": "es",  # Guatemala
        "HN": "es",  # Honduras
        "SV": "es",  # El Salvador
        "NI": "es",  # Nicaragua
        "CU": "es",  # Cuba
        "PR": "es",  # Puerto Rico
        "ES": "es",  # España
        # English‑speaking countries
        "US": "en",  # United States
        "GB": "en",  # United Kingdom
        "CA": "en",  # Canada (default English; French could be added later)
        "AU": "en",  # Australia
        "NZ": "en",  # New Zealand
        "IE": "en",  # Ireland
        # French‑speaking countries
        "FR": "fr",  # France
        "BE": "fr",  # Belgium (French community)
        "CH": "fr",  # Switzerland (French region)
        "LU": "fr",  # Luxembourg
        "MC": "fr",  # Monaco
        # Portuguese‑speaking countries
        "BR": "pt",  # Brazil
        "PT": "pt",  # Portugal
        "AO": "pt",  # Angola
        "MZ": "pt",  # Mozambique
        # Additional European languages could be added as needed
        "DE": "de",  # Germany
        "IT": "it",  # Italy
        "NL": "nl",  # Netherlands
    }

    return mapping.get(country_code, "es")  # default to Spanish


# Payment confirmation email templates
PAYMENT_EMAIL_TEMPLATES = {
    "es": {
        "subject": "✅ Confirmación de pago – {clinic_name}",
        "html": """
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Confirmación de pago</title>
        </head>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; line-height: 1.6;">
            <div style="background: linear-gradient(135deg, #10b981, #059669); padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 24px;">✅ Pago confirmado</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0; font-size: 15px;">{clinic_name}</p>
            </div>

            <div style="padding: 25px; background: #fff; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px; margin-bottom: 20px;">
                    ¡Hola <strong>{patient_name}</strong>!<br>
                    Tu pago ha sido confirmado correctamente. Acá tenés los detalles:
                </p>

                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                    <h2 style="color: #065f46; margin-top: 0; border-bottom: 2px solid #10b981; padding-bottom: 8px;">📋 Detalles del pago</h2>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold; width: 40%;">Paciente:</td>
                            <td style="padding: 10px 0;">{patient_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Fecha del turno:</td>
                            <td style="padding: 10px 0;">{appointment_date} a las {appointment_time}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Tratamiento:</td>
                            <td style="padding: 10px 0;">{treatment}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Monto pagado:</td>
                            <td style="padding: 10px 0; font-size: 18px; color: #065f46; font-weight: bold;">{amount}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Método de pago:</td>
                            <td style="padding: 10px 0;">{payment_method}</td>
                        </tr>
                    </table>
                </div>

                <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 18px; margin-bottom: 25px;">
                    <h3 style="color: #1e40af; margin-top: 0;">🏥 Datos de la clínica</h3>
                    <p style="margin: 8px 0;">
                        <strong>{clinic_name}</strong><br>
                        {clinic_address}<br>
                        Teléfono: {clinic_phone}
                    </p>
                </div>

                <div style="text-align: center; margin-top: 25px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                    <p style="color: #6b7280; font-size: 14px; margin: 0;">
                        Este es un comprobante automático de pago.<br>
                        Si tenés alguna duda, podés responder a este email o contactar a la clínica.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """,
    },
    "en": {
        "subject": "✅ Payment confirmation – {clinic_name}",
        "html": """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Payment Confirmation</title>
        </head>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; line-height: 1.6;">
            <div style="background: linear-gradient(135deg, #10b981, #059669); padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 24px;">✅ Payment confirmed</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0; font-size: 15px;">{clinic_name}</p>
            </div>

            <div style="padding: 25px; background: #fff; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px; margin-bottom: 20px;">
                    Hello <strong>{patient_name}</strong>!<br>
                    Your payment has been successfully confirmed. Here are the details:
                </p>

                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                    <h2 style="color: #065f46; margin-top: 0; border-bottom: 2px solid #10b981; padding-bottom: 8px;">📋 Payment Details</h2>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold; width: 40%;">Patient:</td>
                            <td style="padding: 10px 0;">{patient_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Appointment date:</td>
                            <td style="padding: 10px 0;">{appointment_date} at {appointment_time}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Treatment:</td>
                            <td style="padding: 10px 0;">{treatment}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Amount paid:</td>
                            <td style="padding: 10px 0; font-size: 18px; color: #065f46; font-weight: bold;">{amount}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Payment method:</td>
                            <td style="padding: 10px 0;">{payment_method}</td>
                        </tr>
                    </table>
                </div>

                <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 18px; margin-bottom: 25px;">
                    <h3 style="color: #1e40af; margin-top: 0;">🏥 Clinic Information</h3>
                    <p style="margin: 8px 0;">
                        <strong>{clinic_name}</strong><br>
                        {clinic_address}<br>
                        Phone: {clinic_phone}
                    </p>
                </div>

                <div style="text-align: center; margin-top: 25px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                    <p style="color: #6b7280; font-size: 14px; margin: 0;">
                        This is an automatic payment receipt.<br>
                        If you have any questions, you can reply to this email or contact the clinic.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """,
    },
    "fr": {
        "subject": "✅ Confirmation de paiement – {clinic_name}",
        "html": """
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Confirmation de paiement</title>
        </head>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; line-height: 1.6;">
            <div style="background: linear-gradient(135deg, #10b981, #059669); padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 24px;">✅ Paiement confirmé</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0; font-size: 15px;">{clinic_name}</p>
            </div>

            <div style="padding: 25px; background: #fff; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px; margin-bottom: 20px;">
                    Bonjour <strong>{patient_name}</strong> !<br>
                    Votre paiement a été confirmé avec succès. Voici les détails :
                </p>

                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                    <h2 style="color: #065f46; margin-top: 0; border-bottom: 2px solid #10b981; padding-bottom: 8px;">📋 Détails du paiement</h2>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold; width: 40%;">Patient :</td>
                            <td style="padding: 10px 0;">{patient_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Date du rendez‑vous :</td>
                            <td style="padding: 10px 0;">{appointment_date} à {appointment_time}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Traitement :</td>
                            <td style="padding: 10px 0;">{treatment}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Montant payé :</td>
                            <td style="padding: 10px 0; font-size: 18px; color: #065f46; font-weight: bold;">{amount}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Méthode de paiement :</td>
                            <td style="padding: 10px 0;">{payment_method}</td>
                        </tr>
                    </table>
                </div>

                <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 18px; margin-bottom: 25px;">
                    <h3 style="color: #1e40af; margin-top: 0;">🏥 Informations de la clinique</h3>
                    <p style="margin: 8px 0;">
                        <strong>{clinic_name}</strong><br>
                        {clinic_address}<br>
                        Téléphone : {clinic_phone}
                    </p>
                </div>

                <div style="text-align: center; margin-top: 25px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                    <p style="color: #6b7280; font-size: 14px; margin: 0;">
                        Ceci est un reçu de paiement automatique.<br>
                        Si vous avez des questions, vous pouvez répondre à cet e‑mail ou contacter la clinique.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """,
    },
    "pt": {
        "subject": "✅ Confirmação de pagamento – {clinic_name}",
        "html": """
        <!DOCTYPE html>
        <html lang="pt">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Confirmação de Pagamento</title>
        </head>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; line-height: 1.6;">
            <div style="background: linear-gradient(135deg, #10b981, #059669); padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 24px;">✅ Pagamento confirmado</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0; font-size: 15px;">{clinic_name}</p>
            </div>

            <div style="padding: 25px; background: #fff; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px; margin-bottom: 20px;">
                    Olá <strong>{patient_name}</strong>!<br>
                    Seu pagamento foi confirmado com sucesso. Aqui estão os detalhes:
                </p>

                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                    <h2 style="color: #065f46; margin-top: 0; border-bottom: 2px solid #10b981; padding-bottom: 8px;">📋 Detalhes do pagamento</h2>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold; width: 40%;">Paciente:</td>
                            <td style="padding: 10px 0;">{patient_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Data da consulta:</td>
                            <td style="padding: 10px 0;">{appointment_date} às {appointment_time}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Tratamento:</td>
                            <td style="padding: 10px 0;">{treatment}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Valor pago:</td>
                            <td style="padding: 10px 0; font-size: 18px; color: #065f46; font-weight: bold;">{amount}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Método de pagamento:</td>
                            <td style="padding: 10px 0;">{payment_method}</td>
                        </tr>
                    </table>
                </div>

                <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 18px; margin-bottom: 25px;">
                    <h3 style="color: #1e40af; margin-top: 0;">🏥 Informações da clínica</h3>
                    <p style="margin: 8px 0;">
                        <strong>{clinic_name}</strong><br>
                        {clinic_address}<br>
                        Telefone: {clinic_phone}
                    </p>
                </div>

                <div style="text-align: center; margin-top: 25px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                    <p style="color: #6b7280; font-size: 14px; margin: 0;">
                        Este é um comprovante automático de pagamento.<br>
                        Se tiver alguma dúvida, pode responder a este e‑mail ou entrar em contato com a clínica.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """,
    },
}


def render_payment_email(
    language: str,
    patient_name: str,
    clinic_name: str,
    appointment_date: str,
    appointment_time: str,
    treatment: str,
    amount: str,
    payment_method: str,
    clinic_address: str = "",
    clinic_phone: str = "",
) -> dict:
    """
    Render a payment confirmation email for the given language.

    Returns dict with "subject" and "html" keys.
    Falls back to Spanish if language not found.
    """
    # Normalize language code
    lang = language.lower().strip() if language else "es"

    # Fallback to Spanish if language not available
    template = PAYMENT_EMAIL_TEMPLATES.get(lang, PAYMENT_EMAIL_TEMPLATES["es"])

    # Prepare context (escape any HTML special chars? Not needed for simple strings in HTML)
    context = {
        "patient_name": patient_name,
        "clinic_name": clinic_name,
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "treatment": treatment,
        "amount": amount,
        "payment_method": payment_method,
        "clinic_address": clinic_address if clinic_address else "—",
        "clinic_phone": clinic_phone if clinic_phone else "—",
    }

    # Render subject and HTML
    subject = template["subject"].format(**context)
    html = template["html"].format(**context)

    return {"subject": subject, "html": html}


# Convenience function that combines country → language → template
def render_payment_email_from_country(
    country_code: str,
    patient_name: str,
    clinic_name: str,
    appointment_date: str,
    appointment_time: str,
    treatment: str,
    amount: str,
    payment_method: str,
    clinic_address: str = "",
    clinic_phone: str = "",
) -> dict:
    """
    Render payment email based on country code.
    """
    language = _language_from_country(country_code)
    return render_payment_email(
        language=language,
        patient_name=patient_name,
        clinic_name=clinic_name,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        treatment=treatment,
        amount=amount,
        payment_method=payment_method,
        clinic_address=clinic_address,
        clinic_phone=clinic_phone,
    )


# ============================================================
# Welcome Email Templates (professional, secretary, CEO)
# ============================================================

WELCOME_EMAIL_TEMPLATES = {
    "professional": {
        "subject": "Bienvenido a {clinic_name} - Tu acceso al sistema",
        "html": """
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Bienvenido</title>
        </head>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; line-height: 1.6;">
            <div style="background: linear-gradient(135deg, #3b82f6, #1d4ed8); padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 24px;">🏥 Bienvenido a {clinic_name}</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0; font-size: 15px;">Tu acceso al sistema</p>
            </div>

            <div style="padding: 25px; background: #fff; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px; margin-bottom: 20px;">
                    Hola <strong>{user_first_name}</strong>!<br>
                    ¡Bienvenido a nuestro equipo! Estos son tus datos de acceso:
                </p>

                <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                    <h2 style="color: #1e40af; margin-top: 0; border-bottom: 2px solid #3b82f6; padding-bottom: 8px;">📋 Credenciales</h2>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold; width: 40%;">Usuario:</td>
                            <td style="padding: 10px 0;">{user_email}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Link de acceso:</td>
                            <td style="padding: 10px 0;">
                                <a href="{login_url}" style="color: #3b82f6; text-decoration: none; font-weight: bold;">{login_url}</a>
                            </td>
                        </tr>
                    </table>
                </div>

                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 18px; margin-bottom: 25px;">
                    <h3 style="color: #065f46; margin-top: 0;">🏥 Datos de la clínica</h3>
                    <p style="margin: 8px 0;">
                        <strong>{clinic_name}</strong><br>
                        {clinic_address}<br>
                        Teléfono: {clinic_phone}
                    </p>
                </div>

                <div style="background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 8px; padding: 18px; margin-bottom: 25px;">
                    <h3 style="color: #7c3aed; margin-top: 0;">📅 Sistema de Agenda</h3>
                    <p style="margin: 8px 0;">
                        Podés ver tu agenda, gestionar tus turnos y consultar tus pacientes desde el panel.
                    </p>
                </div>

                <div style="text-align: center; margin-top: 25px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                    <p style="color: #6b7280; font-size: 14px; margin: 0;">
                        Si tenés dudas, escribinos a {support_email}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """,
    },
    "secretary": {
        "subject": "Bienvenida a {clinic_name} - Tu acceso como Secretaría",
        "html": """
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Bienvenida</title>
        </head>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; line-height: 1.6;">
            <div style="background: linear-gradient(135deg, #8b5cf6, #6d28d9); padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 24px;">👋 Bienvenida a {clinic_name}</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0; font-size: 15px;">Tu acceso como Secretaría</p>
            </div>

            <div style="padding: 25px; background: #fff; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px; margin-bottom: 20px;">
                    Hola <strong>{user_first_name}</strong>!<br>
                    ¡Estamos felices de tenerte en el equipo! Estos son tus datos de acceso:
                </p>

                <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                    <h2 style="color: #1e40af; margin-top: 0; border-bottom: 2px solid #8b5cf6; padding-bottom: 8px;">📋 Credenciales</h2>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold; width: 40%;">Usuario:</td>
                            <td style="padding: 10px 0;">{user_email}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Link de acceso:</td>
                            <td style="padding: 10px 0;">
                                <a href="{login_url}" style="color: #8b5cf6; text-decoration: none; font-weight: bold;">{login_url}</a>
                            </td>
                        </tr>
                    </table>
                </div>

                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 18px; margin-bottom: 25px;">
                    <h3 style="color: #065f46; margin-top: 0;">🏥 Datos de la clínica</h3>
                    <p style="margin: 8px 0;">
                        <strong>{clinic_name}</strong><br>
                        {clinic_address}<br>
                        Teléfono: {clinic_phone}
                    </p>
                </div>

                <div style="background: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 18px; margin-bottom: 25px;">
                    <h3 style="color: #92400e; margin-top: 0;">📋 Funcionalidades disponibles</h3>
                    <ul style="margin: 8px 0; padding-left: 20px; color: #451a03;">
                        <li>Gestión de turnos y agenda</li>
                        <li>Registro de pacientes</li>
                        <li>Confirmación de turnos</li>
                        <li>Historial de conversaciones</li>
                    </ul>
                </div>

                <div style="text-align: center; margin-top: 25px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                    <p style="color: #6b7280; font-size: 14px; margin: 0;">
                        Si tenés dudas, escribinos a {support_email}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """,
    },
    "ceo": {
        "subject": "Bienvenido a {clinic_name} - Acceso como Administrador",
        "html": """
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Bienvenido Administrador</title>
        </head>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; line-height: 1.6;">
            <div style="background: linear-gradient(135deg, #f59e0b, #d97706); padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 24px;">⚙️ Bienvenido a {clinic_name}</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0; font-size: 15px;">Acceso como Administrador</p>
            </div>

            <div style="padding: 25px; background: #fff; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px; margin-bottom: 20px;">
                    Hola <strong>{user_first_name}</strong>!<br>
                    ¡Bienvenido como administrador! Tenés acceso completo al sistema. Estos son tus datos de acceso:
                </p>

                <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                    <h2 style="color: #1e40af; margin-top: 0; border-bottom: 2px solid #f59e0b; padding-bottom: 8px;">📋 Credenciales</h2>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold; width: 40%;">Usuario:</td>
                            <td style="padding: 10px 0;">{user_email}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold;">Link de acceso:</td>
                            <td style="padding: 10px 0;">
                                <a href="{login_url}" style="color: #f59e0b; text-decoration: none; font-weight: bold;">{login_url}</a>
                            </td>
                        </tr>
                    </table>
                </div>

                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 18px; margin-bottom: 25px;">
                    <h3 style="color: #065f46; margin-top: 0;">🏥 Datos de la clínica</h3>
                    <p style="margin: 8px 0;">
                        <strong>{clinic_name}</strong><br>
                        {clinic_address}<br>
                        Teléfono: {clinic_phone}
                    </p>
                </div>

                <div style="background: #f0f9ff; border: 1px solid #7dd3fc; border-radius: 8px; padding: 18px; margin-bottom: 25px;">
                    <h3 style="color: #0369a1; margin-top: 0;">📊 Dashboard y Métricas</h3>
                    <ul style="margin: 8px 0; padding-left: 20px; color: #0c4a6e;">
                        <li>Ver ingresos y estadísticas</li>
                        <li>Gestión de relaciones</li>
                        <li>Reportes detallados</li>
                    </ul>
                </div>

                <div style="background: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 18px; margin-bottom: 25px;">
                    <h3 style="color: #92400e; margin-top: 0;">⚙️ Configuraciones disponibles</h3>
                    <ul style="margin: 8px 0; padding-left: 20px; color: #451a03;">
                        <li>Configurar clínica</li>
                        <li>Gestionar usuarios y permisos</li>
                        <li>Ajustar agenda y horarios</li>
                        <li>Integrar calendario Google</li>
                    </ul>
                </div>

                <div style="text-align: center; margin-top: 25px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                    <p style="color: #6b7280; font-size: 14px; margin: 0;">
                        Si tenés dudas, escribinos a {support_email}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """,
    },
}


def render_welcome_email(
    role: str,
    user_first_name: str,
    user_email: str,
    clinic_name: str,
    clinic_address: str = "",
    clinic_phone: str = "",
    login_url: str = "",
    support_email: str = "",
) -> dict:
    """
    Render a welcome email for the given role.

    Roles: "professional", "secretary", "ceo"

    Returns dict with "subject" and "html" keys.
    Falls back to professional template if role not found.
    """
    # Normalize role
    role_key = role.lower().strip() if role else "professional"

    # Fallback to professional if role not available
    template = WELCOME_EMAIL_TEMPLATES.get(
        role_key, WELCOME_EMAIL_TEMPLATES["professional"]
    )

    # Prepare context
    context = {
        "user_first_name": user_first_name,
        "user_email": user_email,
        "clinic_name": clinic_name,
        "clinic_address": clinic_address if clinic_address else "—",
        "clinic_phone": clinic_phone if clinic_phone else "—",
        "login_url": login_url if login_url else "—",
        "support_email": support_email if support_email else "—",
    }

    # Render subject and HTML
    subject = template["subject"].format(**context)
    html = template["html"].format(**context)

    return {"subject": subject, "html": html}
