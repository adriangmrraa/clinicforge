import os
import smtplib
import html as _html
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import logging

# Payment email templates
from services.email_templates import (
    render_payment_email_from_country,
    _language_from_country,
)

logger = logging.getLogger("email_service")


class EmailService:
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_pass = os.getenv("SMTP_PASS", "")
        self.smtp_sender = os.getenv("SMTP_SENDER", "")
        self.clinic_name = os.getenv("CLINIC_NAME", "Sistema de Gestión")

    def send_handoff_email(
        self,
        to_emails: list,
        patient_name: str,
        phone: str,
        reason: str,
        chat_history_html: str = "",
        patient_info: dict = None,
        anamnesis_data: dict = None,
        next_appointment: dict = None,
        suggestions: str = "",
    ):
        """
        Envía email de derivación completo a múltiples destinatarios.
        Incluye: resumen, conversación literal, ficha clínica, anamnesis, sugerencias.
        """
        if not self.smtp_host or not self.smtp_user:
            logger.warning("⚠️ SMTP not configured. Skipping email.")
            return False

        if not to_emails:
            logger.warning("⚠️ No destination emails for handoff.")
            return False

        # Ensure list
        if isinstance(to_emails, str):
            to_emails = [to_emails]

        # Filter empty
        to_emails = [e.strip() for e in to_emails if e and e.strip()]
        if not to_emails:
            return False

        try:
            pi = patient_info or {}
            channel = pi.get("_channel", "whatsapp")

            # Build contact links based on channel
            phone_digits = phone.replace("+", "").replace(" ", "").replace("-", "")
            wa_link = f"https://wa.me/{phone_digits}"
            ig_psid = pi.get("instagram_psid", "")
            fb_psid = pi.get("facebook_psid", "")

            contact_buttons = []
            # WhatsApp is always available if we have a phone
            if (
                phone_digits
                and not phone_digits.startswith("ig_")
                and not phone_digits.startswith("fb_")
            ):
                contact_buttons.append(
                    f'<a href="{wa_link}" style="display:inline-block; background-color:#25D366; color:white; '
                    f'padding:12px 24px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:14px; margin:4px;">'
                    f"📱 WhatsApp</a>"
                )
            # Instagram
            if ig_psid or channel == "instagram":
                ig_url = (
                    f"https://www.instagram.com/direct/t/{ig_psid}"
                    if ig_psid
                    else "https://www.instagram.com/direct/inbox/"
                )
                contact_buttons.append(
                    f'<a href="{ig_url}" style="display:inline-block; background:linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888); '
                    f'color:white; padding:12px 24px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:14px; margin:4px;">'
                    f"📷 Instagram DM</a>"
                )
            # Facebook
            if fb_psid or channel == "facebook":
                fb_url = (
                    f"https://www.facebook.com/messages/t/{fb_psid}"
                    if fb_psid
                    else "https://www.facebook.com/messages/"
                )
                contact_buttons.append(
                    f'<a href="{fb_url}" style="display:inline-block; background-color:#1877F2; color:white; '
                    f'padding:12px 24px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:14px; margin:4px;">'
                    f"💬 Facebook Messenger</a>"
                )

            if not contact_buttons:
                contact_buttons.append(
                    f'<a href="{wa_link}" style="display:inline-block; background-color:#25D366; color:white; '
                    f'padding:12px 24px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:14px; margin:4px;">'
                    f"📱 Contactar por WhatsApp</a>"
                )

            contact_buttons_html = "\n".join(contact_buttons)
            channel_label = {
                "whatsapp": "WhatsApp",
                "instagram": "Instagram",
                "facebook": "Facebook Messenger",
            }.get(channel, channel.title())

            # --- Build patient info section ---
            patient_section = f"""
            <table style="width:100%; border-collapse:collapse; margin:10px 0;">
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold; width:140px;">Nombre</td><td style="padding:6px 12px; background:#f8f9ff;">{patient_name}</td></tr>
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Teléfono</td><td style="padding:6px 12px; background:#f8f9ff;">{phone}</td></tr>
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">DNI</td><td style="padding:6px 12px; background:#f8f9ff;">{pi.get("dni", "No registrado")}</td></tr>
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Email</td><td style="padding:6px 12px; background:#f8f9ff;">{pi.get("email", "No registrado")}</td></tr>
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Ciudad</td><td style="padding:6px 12px; background:#f8f9ff;">{pi.get("city", "No registrada")}</td></tr>
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Nivel urgencia</td><td style="padding:6px 12px; background:#f8f9ff;">{pi.get("urgency_level", "normal")}</td></tr>
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Fuente</td><td style="padding:6px 12px; background:#f8f9ff;">{pi.get("first_touch_source", "No registrada")}</td></tr>
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Canal</td><td style="padding:6px 12px; background:#f8f9ff;">{channel_label}</td></tr>
            </table>
            """

            # --- Build anamnesis section ---
            anamnesis_section = ""
            if anamnesis_data:
                rows = ""
                field_labels = {
                    "base_diseases": "Enfermedades base",
                    "habitual_medication": "Medicación habitual",
                    "allergies": "Alergias",
                    "previous_surgeries": "Cirugías previas",
                    "is_smoker": "Fumador",
                    "is_pregnant": "Embarazada",
                    "has_pacemaker": "Marcapasos",
                    "blood_pressure_issues": "Presión arterial",
                    "diabetes": "Diabetes",
                    "heart_condition": "Condición cardíaca",
                    "bleeding_disorder": "Trastorno hemorrágico",
                    "dental_anxiety_level": "Nivel de ansiedad dental",
                    "last_dental_visit": "Última visita dental",
                    "main_concern": "Motivo de consulta principal",
                    "additional_notes": "Notas adicionales",
                }
                for key, label in field_labels.items():
                    val = anamnesis_data.get(key)
                    if (
                        val
                        and str(val).strip()
                        and str(val).strip().lower()
                        not in ("none", "null", "no", "false")
                    ):
                        rows += f'<tr><td style="padding:5px 10px; background:#f0fff4; font-weight:bold; width:180px; font-size:13px;">{label}</td><td style="padding:5px 10px; background:#f8fff8; font-size:13px;">{val}</td></tr>'
                if rows:
                    anamnesis_section = f"""
                    <h3 style="color:#059669; margin-top:20px; border-bottom:2px solid #059669; padding-bottom:5px;">📋 Ficha Médica / Anamnesis</h3>
                    <table style="width:100%; border-collapse:collapse; margin:10px 0;">{rows}</table>
                    """
                else:
                    anamnesis_section = '<p style="color:#999; font-style:italic;">El paciente no tiene anamnesis completada.</p>'
            else:
                anamnesis_section = '<p style="color:#999; font-style:italic;">El paciente no tiene anamnesis completada.</p>'

            # --- Build appointment section ---
            appointment_section = ""
            if next_appointment:
                appointment_section = f"""
                <h3 style="color:#2563eb; margin-top:20px; border-bottom:2px solid #2563eb; padding-bottom:5px;">📅 Próximo Turno</h3>
                <table style="width:100%; border-collapse:collapse; margin:10px 0;">
                    <tr><td style="padding:5px 10px; background:#eff6ff; font-weight:bold; width:140px;">Fecha/Hora</td><td style="padding:5px 10px; background:#f8faff;">{next_appointment.get("datetime", "—")}</td></tr>
                    <tr><td style="padding:5px 10px; background:#eff6ff; font-weight:bold;">Tratamiento</td><td style="padding:5px 10px; background:#f8faff;">{next_appointment.get("type", "—")}</td></tr>
                    <tr><td style="padding:5px 10px; background:#eff6ff; font-weight:bold;">Profesional</td><td style="padding:5px 10px; background:#f8faff;">{next_appointment.get("professional", "—")}</td></tr>
                    <tr><td style="padding:5px 10px; background:#eff6ff; font-weight:bold;">Estado</td><td style="padding:5px 10px; background:#f8faff;">{next_appointment.get("status", "—")}</td></tr>
                </table>
                """

            # --- Suggestions section ---
            suggestions_section = ""
            if suggestions:
                suggestions_section = f"""
                <h3 style="color:#d97706; margin-top:20px; border-bottom:2px solid #d97706; padding-bottom:5px;">💡 Sugerencias del Sistema</h3>
                <div style="background:#fffbeb; border-left:4px solid #d97706; padding:12px 15px; margin:10px 0; border-radius:0 8px 8px 0;">
                    {suggestions}
                </div>
                """

            # --- Full email ---
            html_content = f"""
            <html>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 700px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #1e40af, #3b82f6); padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 22px;">🔔 Derivación Humana</h1>
                    <p style="color: rgba(255,255,255,0.85); margin: 5px 0 0; font-size: 14px;">{self.clinic_name}</p>
                </div>

                <div style="padding: 25px; background: #fff; border: 1px solid #e5e7eb; border-top: none;">

                    <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
                        <h3 style="color: #dc2626; margin: 0 0 8px;">⚠️ Motivo de la derivación</h3>
                        <p style="margin: 0; font-size: 15px; color: #991b1b;">{reason}</p>
                    </div>

                    <h3 style="color:#1e40af; border-bottom:2px solid #1e40af; padding-bottom:5px;">👤 Datos del Paciente</h3>
                    {patient_section}

                    {anamnesis_section}

                    {appointment_section}

                    <h3 style="color:#7c3aed; margin-top:20px; border-bottom:2px solid #7c3aed; padding-bottom:5px;">💬 Conversación (últimos mensajes)</h3>
                    <div style="background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 8px; padding: 15px; margin: 10px 0; max-height: 400px; overflow-y: auto;">
                        {chat_history_html}
                    </div>

                    {suggestions_section}

                    <h3 style="color:#0369a1; margin-top:20px; border-bottom:2px solid #0369a1; padding-bottom:5px;">🔗 Contactar al paciente</h3>
                    <div style="text-align: center; margin-top: 15px; padding: 15px; background: #f8fafc; border-radius: 8px;">
                        {contact_buttons_html}
                    </div>

                    <p style="margin-top: 25px; font-size: 11px; color: #999; text-align: center; border-top: 1px solid #eee; padding-top: 15px;">
                        Este email fue enviado automáticamente por el sistema de IA de {self.clinic_name}.<br>
                        Todos los profesionales activos de la clínica reciben esta notificación.
                    </p>
                </div>
            </body>
            </html>
            """

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🔔 Derivación: {patient_name} — {reason[:60]}"
            msg["From"] = self.smtp_sender
            msg["To"] = ", ".join(to_emails)
            msg.attach(MIMEText(html_content, "html"))

            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()

            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_sender, to_emails, msg.as_string())
            server.quit()

            logger.info(
                f"📧 Email de derivación enviado a {len(to_emails)} destinatarios: {', '.join(to_emails)}"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Error sending handoff email: {e}")
            return False

    def send_payment_email(
        self,
        to_email: str,
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
    ) -> bool:
        """
        Envía email de confirmación de pago al paciente.
        Usa plantillas traducidas según country_code (es, en, fr, pt).
        """
        # 1. Validar configuración SMTP
        if not self.smtp_host or not self.smtp_user:
            logger.warning("⚠️ SMTP no configurado. Saltando envío de email de pago.")
            return False

        # 2. Validar email destino
        if not to_email or not to_email.strip():
            logger.warning("⚠️ Email destino vacío. Saltando envío de email de pago.")
            return False

        # Normalizar email a lista (para compatibilidad con sendmail)
        to_emails = [to_email.strip()]

        # 3. Renderizar plantilla
        try:
            rendered = render_payment_email_from_country(
                country_code=country_code,
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
        except Exception as e:
            logger.error(f"❌ Error renderizando plantilla de pago: {e}")
            return False

        subject = rendered["subject"]
        html_content = rendered["html"]

        # 4. Enviar via SMTP
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.smtp_sender
            msg["To"] = ", ".join(to_emails)
            msg.attach(MIMEText(html_content, "html"))

            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()

            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_sender, to_emails, msg.as_string())
            server.quit()

            logger.info(f"📧 Email de confirmación de pago enviado a {to_email}")
            return True

        except Exception as e:
            logger.error(f"❌ Error enviando email de pago: {e}")
            return False

    def send_professional_booking_notification(
        self,
        to_email: str,
        professional_name: str,
        patient_name: str,
        patient_phone: str,
        clinic_name: str,
        appointment_date: str,
        appointment_time: str,
        treatment: str,
        notes: str = "",
    ) -> bool:
        """
        Notifica al profesional que se le agendó un nuevo turno desde el agente IA.
        Best-effort: nunca debe romper el flujo de booking si falla.
        """
        if not self.smtp_host or not self.smtp_user:
            logger.warning("⚠️ SMTP no configurado. Saltando notificación al profesional.")
            return False
        if not to_email or not to_email.strip():
            return False

        to_emails = [to_email.strip()]

        # HTML-escape all interpolated values to prevent injection from patient input
        e_patient_name = _html.escape(patient_name or "")
        e_patient_phone = _html.escape(patient_phone or "—")
        e_professional_name = _html.escape(professional_name or "")
        e_clinic_name = _html.escape(clinic_name or "")
        e_treatment = _html.escape(treatment or "")
        e_appointment_date = _html.escape(appointment_date or "")
        e_appointment_time = _html.escape(appointment_time or "")
        e_notes = _html.escape(notes or "")

        subject = f"🗓️ Nuevo turno agendado — {patient_name} ({appointment_date} {appointment_time})"

        notes_block = ""
        if e_notes:
            notes_block = f"<p style='margin:8px 0;color:#475569;'><strong>Notas:</strong> {e_notes}</p>"

        html_content = f"""
        <html>
          <body style="font-family: -apple-system, Segoe UI, sans-serif; background:#f8fafc; padding:24px;">
            <div style="max-width:560px; margin:0 auto; background:#ffffff; border-radius:12px; padding:32px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
              <h2 style="margin:0 0 16px 0; color:#0f172a;">Nuevo turno agendado</h2>
              <p style="margin:0 0 16px 0; color:#475569;">Hola {e_professional_name}, se agendó un nuevo turno para vos desde el asistente IA.</p>
              <table style="width:100%; border-collapse:collapse; margin:16px 0;">
                <tr><td style="padding:8px 0; color:#64748b;">Paciente:</td><td style="padding:8px 0; color:#0f172a;"><strong>{e_patient_name}</strong></td></tr>
                <tr><td style="padding:8px 0; color:#64748b;">Teléfono:</td><td style="padding:8px 0; color:#0f172a;">{e_patient_phone}</td></tr>
                <tr><td style="padding:8px 0; color:#64748b;">Tratamiento:</td><td style="padding:8px 0; color:#0f172a;">{e_treatment}</td></tr>
                <tr><td style="padding:8px 0; color:#64748b;">Fecha:</td><td style="padding:8px 0; color:#0f172a;"><strong>{e_appointment_date}</strong></td></tr>
                <tr><td style="padding:8px 0; color:#64748b;">Hora:</td><td style="padding:8px 0; color:#0f172a;"><strong>{e_appointment_time}</strong></td></tr>
              </table>
              {notes_block}
              <p style="margin:16px 0 0 0; font-size:13px; color:#94a3b8;">— {e_clinic_name}</p>
            </div>
          </body>
        </html>
        """

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.smtp_sender
            msg["To"] = ", ".join(to_emails)
            msg.attach(MIMEText(html_content, "html"))

            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()

            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_sender, to_emails, msg.as_string())
            server.quit()

            logger.info(f"📧 Notificación de booking enviada al profesional {to_email}")
            return True
        except Exception as e:
            logger.error(f"❌ Error enviando notificación al profesional: {e}")
            return False

    def send_payment_verification_failed_email(
        self,
        to_email: str,
        clinic_name: str,
        patient_name: str,
        patient_phone: str,
        appointment_date: str,
        treatment: str,
        failure_reason: str,
        amount_detected: str = "",
        amount_expected: str = "",
    ) -> bool:
        """
        Notifica a la clínica que la verificación automática de un comprobante falló.
        Solo va al derivation_email del tenant (no a profesionales).
        """
        if not self.smtp_host or not self.smtp_user:
            logger.warning("SMTP not configured. Skipping payment failure email.")
            return False
        if not to_email or not to_email.strip():
            return False

        to_emails = [to_email.strip()]
        phone_digits = patient_phone.replace("+", "").replace(" ", "").replace("-", "")
        wa_link = f"https://wa.me/{phone_digits}"

        html_content = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; background: #0d1117; color: #e6edf3; padding: 24px; border-radius: 12px;">
            <div style="background: linear-gradient(135deg, #b91c1c, #dc2626); padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 24px;">
                <h1 style="color: white; margin: 0; font-size: 20px;">⚠️ Verificación de Pago Fallida</h1>
                <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0; font-size: 14px;">{clinic_name}</p>
            </div>

            <div style="background: rgba(255,255,255,0.05); padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                <h3 style="color: #f87171; margin: 0 0 12px;">Motivo del fallo</h3>
                <p style="color: #e6edf3; margin: 0;">{failure_reason}</p>
            </div>

            <div style="background: rgba(255,255,255,0.05); padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                <h3 style="color: #60a5fa; margin: 0 0 12px;">Datos del paciente</h3>
                <table style="width: 100%; color: #e6edf3;">
                    <tr><td style="padding: 4px 8px; color: #9ca3af;">Paciente</td><td style="padding: 4px 8px;">{patient_name}</td></tr>
                    <tr><td style="padding: 4px 8px; color: #9ca3af;">Teléfono</td><td style="padding: 4px 8px;">{patient_phone}</td></tr>
                    <tr><td style="padding: 4px 8px; color: #9ca3af;">Turno</td><td style="padding: 4px 8px;">{appointment_date} — {treatment}</td></tr>
                    <tr><td style="padding: 4px 8px; color: #9ca3af;">Monto detectado</td><td style="padding: 4px 8px;">{amount_detected or "No detectado"}</td></tr>
                    <tr><td style="padding: 4px 8px; color: #9ca3af;">Monto esperado</td><td style="padding: 4px 8px;">{amount_expected or "No calculado"}</td></tr>
                </table>
            </div>

            <div style="text-align: center; margin-top: 20px;">
                <a href="{wa_link}" style="background: #25D366; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold;">
                    💬 Contactar al paciente
                </a>
            </div>

            <p style="color: #6b7280; font-size: 12px; text-align: center; margin-top: 24px;">
                El paciente envió un comprobante que no pudo ser verificado automáticamente.
                Revisalo manualmente y actualizá el estado del turno desde el panel.
            </p>
        </div>
        """

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"⚠️ Pago no verificado: {patient_name} — {treatment}"
            msg["From"] = self.smtp_sender
            msg["To"] = ", ".join(to_emails)
            msg.attach(MIMEText(html_content, "html"))

            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()

            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_sender, to_emails, msg.as_string())
            server.quit()

            logger.info(
                f"📧 Payment verification failed email sent to {to_email} for {patient_name}"
            )
            return True

        except Exception as e:
            logger.error(f"Error sending payment verification failed email: {e}")
            return False

    def send_digital_record_email(
        self,
        to_email: str,
        pdf_path: str,
        patient_name: str,
        document_title: str,
    ) -> bool:
        """Send a digital record as PDF attachment via email.

        Uses MIMEMultipart("mixed") to support both HTML body and PDF attachment.
        """
        if not self.smtp_host or not self.smtp_user:
            logger.warning("⚠️ SMTP not configured. Skipping digital record email.")
            return False

        if not to_email or not to_email.strip():
            logger.warning("⚠️ No destination email for digital record.")
            return False

        to_emails = [to_email.strip()]

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #333; border-bottom: 2px solid #333; padding-bottom: 10px;">
                {self.clinic_name}
            </h2>
            <p style="color: #555; font-size: 14px; line-height: 1.6;">
                Se adjunta el documento: <strong>{document_title}</strong>
            </p>
            <p style="color: #555; font-size: 14px; line-height: 1.6;">
                Paciente: <strong>{patient_name}</strong>
            </p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="color: #999; font-size: 11px;">
                Este documento fue generado por {self.clinic_name}.
                Si recibió este email por error, por favor ignórelo.
            </p>
        </div>
        """

        try:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = f"Ficha Digital — {patient_name}"
            msg["From"] = self.smtp_sender
            msg["To"] = ", ".join(to_emails)

            msg.attach(MIMEText(html_content, "html"))

            with open(pdf_path, "rb") as f:
                pdf_part = MIMEApplication(f.read(), _subtype="pdf")
            pdf_part.add_header(
                "Content-Disposition",
                "attachment",
                filename=f"{document_title}.pdf",
            )
            msg.attach(pdf_part)

            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15)
                server.starttls()

            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_sender, to_emails, msg.as_string())
            server.quit()

            logger.info(f"📧 Ficha digital enviada a {to_email} para {patient_name}")
            return True

        except Exception as e:
            logger.error(f"❌ Error sending digital record email: {e}")
            raise RuntimeError(f"Error SMTP al enviar email: {e}") from e

    def send_budget_email(
        self,
        to_email: str,
        pdf_path: str,
        patient_name: str,
        clinic_name: str,
    ) -> bool:
        """Envía presupuesto de tratamiento por email con PDF adjunto."""
        if not self.smtp_host or not self.smtp_user:
            logger.warning("⚠️ SMTP not configured. Skipping budget email.")
            return False

        if not to_email or not to_email.strip():
            logger.warning("⚠️ No destination email for budget.")
            return False

        to_emails = [to_email.strip()]

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #333; border-bottom: 2px solid #333; padding-bottom: 10px;">
                {clinic_name}
            </h2>
            <p style="color: #555; font-size: 14px; line-height: 1.6;">
                Estimado/a <strong>{patient_name}</strong>,
            </p>
            <p style="color: #555; font-size: 14px; line-height: 1.6;">
                Adjuntamos el presupuesto detallado de su plan de tratamiento en <strong>{clinic_name}</strong>.
            </p>
            <p style="color: #555; font-size: 14px; line-height: 1.6;">
                Por favor revise el documento adjunto. Si tiene alguna consulta, no dude en contactarnos.
            </p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="color: #999; font-size: 11px;">
                Este email fue enviado automáticamente desde {clinic_name}.
                Si recibió este email por error, por favor ignórelo.
            </p>
        </div>
        """

        safe_name = patient_name.replace(" ", "_")
        attachment_filename = f"Presupuesto_{safe_name}.pdf"

        try:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = f"Presupuesto de tratamiento — {clinic_name}"
            msg["From"] = self.smtp_sender
            msg["To"] = ", ".join(to_emails)

            msg.attach(MIMEText(html_content, "html"))

            with open(pdf_path, "rb") as f:
                pdf_part = MIMEApplication(f.read(), _subtype="pdf")
            pdf_part.add_header(
                "Content-Disposition",
                "attachment",
                filename=attachment_filename,
            )
            msg.attach(pdf_part)

            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15)
                server.starttls()

            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_sender, to_emails, msg.as_string())
            server.quit()

            logger.info(f"📧 Presupuesto enviado a {to_email} para {patient_name}")
            return True

        except Exception as e:
            logger.error(f"❌ Error sending budget email: {e}")
            raise RuntimeError(f"Error SMTP al enviar presupuesto: {e}") from e

    def send_liquidation_email(
        self,
        to_email: str,
        pdf_path: str,
        professional_name: str,
        clinic_name: str,
        period_label: str,
        payout_amount: float,
        html_body: str = None,
    ) -> bool:
        """Envía liquidación por email con PDF adjunto."""
        if not self.smtp_host or not self.smtp_user:
            logger.warning("⚠️ SMTP not configured. Skipping liquidation email.")
            return False

        if not to_email or not to_email.strip():
            logger.warning("⚠️ No destination email for liquidation.")
            return False

        to_emails = [to_email.strip()]

        if html_body is None:
            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #1a365d; border-bottom: 2px solid #1a365d; padding-bottom: 10px;">
                    {clinic_name}
                </h2>
                <p style="color: #555; font-size: 14px; line-height: 1.6;">
                    Hola <strong>{professional_name}</strong>,
                </p>
                <p style="color: #555; font-size: 14px; line-height: 1.6;">
                    Te adjuntamos tu liquidación correspondiente al período <strong>{period_label}</strong>.
                </p>
                <p style="color: #555; font-size: 14px; line-height: 1.6;">
                    <strong>Monto a liquidar: ${payout_amount:,.0f}</strong>
                </p>
                <p style="color: #555; font-size: 14px; line-height: 1.6;">
                    Si tenés alguna consulta, no dudes en comunicarte con la administración de {clinic_name}.
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #999; font-size: 11px;">
                    Saludos,<br>Equipo de {clinic_name}
                </p>
            </div>
            """

        safe_name = professional_name.replace(" ", "_")
        attachment_filename = (
            f"Liquidacion_{safe_name}_{period_label.replace(' ', '_')}.pdf"
        )

        try:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = f"Liquidación {period_label} — {clinic_name}"
            msg["From"] = self.smtp_sender
            msg["To"] = ", ".join(to_emails)

            msg.attach(MIMEText(html_body, "html"))

            with open(pdf_path, "rb") as f:
                pdf_part = MIMEApplication(f.read(), _subtype="pdf")
            pdf_part.add_header(
                "Content-Disposition",
                "attachment",
                filename=attachment_filename,
            )
            msg.attach(pdf_part)

            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15)
                server.starttls()

            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_sender, to_emails, msg.as_string())
            server.quit()

            logger.info(
                f"📧 Liquidación enviada a {to_email} para {professional_name} ({period_label})"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Error sending liquidation email: {e}")
            raise RuntimeError(f"Error SMTP al enviar liquidación: {e}") from e

    def send_welcome_email(
        self,
        to_email: str,
        user_name: str,
        role: str,
        clinic_name: str,
        platform_url: str,
        logo_url: str = "",
        is_pending: bool = False,
    ) -> bool:
        """Send a dark-themed welcome email to a new clinic user.

        Args:
            to_email: Destination email address.
            user_name: Display name of the new user.
            role: "professional" or "secretary".
            clinic_name: Name of the clinic/tenant.
            platform_url: URL for the CTA button.
            logo_url: Optional clinic logo URL for the header.
            is_pending: If True, show "pending approval" instead of "active".

        Returns:
            True on success.

        Raises:
            RuntimeError: On SMTP failure (same contract as send_digital_record_email).
        """
        # Guard: skip placeholder / empty emails and unconfigured SMTP
        if not to_email or not to_email.strip():
            logger.warning("send_welcome_email: empty email, skipping.")
            return False

        if to_email.strip().endswith("@dentalogic.local"):
            logger.info("send_welcome_email: placeholder email, skipping.")
            return False

        if not self.smtp_host or not self.smtp_user:
            logger.warning("SMTP not configured. Skipping welcome email.")
            return False

        # Role-specific content
        role_lower = (role or "").lower()
        if role_lower == "professional":
            role_label = "Profesional"
            guide_items = [
                ("Tu agenda personal", "Consulta y administra tus turnos del dia"),
                ("Gestion de pacientes", "Accede a fichas clinicas e historial"),
                ("Registros clinicos y odontograma", "Documentacion digital completa"),
                (
                    "Nova — asistente de voz IA",
                    "Tu copiloto inteligente dentro de la plataforma",
                ),
            ]
        else:
            role_label = "Secretaria"
            guide_items = [
                (
                    "Agenda completa",
                    "Vista global de turnos de todos los profesionales",
                ),
                ("Registro de pacientes", "Alta, edicion y busqueda de pacientes"),
                ("Conversaciones y mensajeria", "Historial de chats con pacientes"),
                (
                    "Gestion de turnos",
                    "Crear, confirmar, cancelar y reprogramar turnos",
                ),
            ]

        subject = f"Bienvenido/a a {clinic_name} — {role_label}"

        # Status section
        if is_pending:
            status_bg = "#f59e0b"
            status_text = "Tu cuenta esta pendiente de aprobacion"
            status_detail = "El administrador de la clinica revisara tu solicitud. Recibiras una notificacion cuando tu cuenta este activa."
        else:
            status_bg = "#22c55e"
            status_text = "Tu cuenta ya esta activa"
            status_detail = "Ya podes ingresar a la plataforma con tus credenciales."

        # Logo HTML
        logo_html = ""
        if logo_url:
            logo_html = (
                f'<img src="{logo_url}" alt="{clinic_name}" '
                f'style="max-height:48px;margin-bottom:12px;border-radius:8px;" /><br/>'
            )

        # Build guide list HTML
        guide_html = ""
        for title, desc in guide_items:
            guide_html += (
                f"<tr>"
                f'<td style="padding:10px 14px;border-bottom:1px solid #21262d;">'
                f'<strong style="color:#e6edf3;font-size:14px;">{title}</strong><br/>'
                f'<span style="color:#8b949e;font-size:12px;">{desc}</span>'
                f"</td>"
                f"</tr>"
            )

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background-color:#0d1117;font-family:'Segoe UI',Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#0d1117;">
<tr><td align="center" style="padding:32px 16px;">

<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

  <!-- HEADER -->
  <tr>
    <td style="background-color:#161b22;border-radius:12px 12px 0 0;padding:28px 24px;text-align:center;border-bottom:2px solid #3b82f6;">
      {logo_html}
      <h1 style="margin:0;font-size:20px;color:#e6edf3;font-weight:600;">{clinic_name}</h1>
    </td>
  </tr>

  <!-- WELCOME -->
  <tr>
    <td style="background-color:#161b22;padding:28px 24px;">
      <h2 style="margin:0 0 8px;font-size:22px;color:#ffffff;">Bienvenido/a a {clinic_name}, {user_name}!</h2>
      <p style="margin:0;font-size:14px;color:#8b949e;">Te damos la bienvenida al equipo como <strong style="color:#3b82f6;">{role_label}</strong>.</p>
    </td>
  </tr>

  <!-- STATUS BADGE -->
  <tr>
    <td style="background-color:#161b22;padding:0 24px 20px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="background-color:#0d1117;border-radius:8px;padding:16px 20px;border-left:4px solid {status_bg};">
            <strong style="color:{status_bg};font-size:15px;">{status_text}</strong><br/>
            <span style="color:#8b949e;font-size:13px;">{status_detail}</span>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ROLE GUIDE -->
  <tr>
    <td style="background-color:#161b22;padding:0 24px 20px;">
      <h3 style="margin:0 0 12px;font-size:15px;color:#e6edf3;">Lo que podes hacer en la plataforma:</h3>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#0d1117;border-radius:8px;overflow:hidden;">
        {guide_html}
      </table>
    </td>
  </tr>

  <!-- CTA BUTTON -->
  <tr>
    <td style="background-color:#161b22;padding:8px 24px 28px;text-align:center;">
      <a href="{platform_url}" style="display:inline-block;background-color:#3b82f6;color:#ffffff;padding:14px 32px;text-decoration:none;border-radius:8px;font-weight:600;font-size:15px;">
        Ingresar a la plataforma
      </a>
    </td>
  </tr>

  <!-- FOOTER -->
  <tr>
    <td style="background-color:#0d1117;border-radius:0 0 12px 12px;padding:20px 24px;text-align:center;border-top:1px solid #21262d;">
      <p style="margin:0;font-size:11px;color:#484f58;">
        Este email fue enviado automaticamente por {clinic_name}.<br/>
        Si recibiste este mensaje por error, simplemente ignoralo.
      </p>
    </td>
  </tr>

</table>

</td></tr>
</table>
</body>
</html>"""

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.smtp_sender
            msg["To"] = to_email.strip()

            msg.attach(MIMEText(html_content, "html", "utf-8"))

            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15)
                server.starttls()

            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_sender, [to_email.strip()], msg.as_string())
            server.quit()

            logger.info(f"Welcome email sent to {to_email} ({role_label})")
            return True

        except Exception as e:
            logger.error(f"Error sending welcome email to {to_email}: {e}")
            raise RuntimeError(f"Error SMTP al enviar welcome email: {e}") from e


email_service = EmailService()


async def send_welcome_email(
    tenant_id: int,
    user_id: str,
    user_role: str,
    db_pool,
) -> bool:
    """
    Envía email de bienvenida a nuevos usuarios (professional/secretary/ceo).
    Solo se envía si el usuario está activo (is_active=TRUE para profesionales).

    Args:
        tenant_id: ID de la clínica/sede
        user_id: UUID del usuario
        user_role: Rol del usuario (professional, secretary, ceo)
        db_pool: Pool de conexión a la base de datos

    Returns:
        bool: True si el email se envió exitosamente, False en caso contrario
    """
    email_svc = EmailService()

    # Validar configuración SMTP
    if not email_svc.smtp_host or not email_svc.smtp_user:
        logger.warning("⚠️ SMTP no configurado. Saltando email de bienvenida.")
        return False

    try:
        # 1. Obtener datos del usuario
        user_row = await db_pool.fetchrow(
            "SELECT email, first_name, last_name FROM users WHERE id = $1", user_id
        )
        if not user_row:
            logger.warning(
                f"⚠️ Usuario {user_id} no encontrado para email de bienvenida."
            )
            return False

        user_email = user_row["email"]
        user_first_name = user_row["first_name"] or "Usuario"
        user_last_name = user_row["last_name"] or ""
        user_full_name = (
            f"{user_first_name} {user_last_name}".strip() or user_first_name
        )

        # 2. Obtener datos de la clínica
        tenant_row = await db_pool.fetchrow(
            "SELECT clinic_name, address, phone, derivation_email FROM tenants WHERE id = $1",
            tenant_id,
        )
        if not tenant_row:
            logger.warning(
                f"⚠️ Tenant {tenant_id} no encontrado para email de bienvenida."
            )
            return False

        clinic_name = tenant_row["clinic_name"] or "Nuestra Clínica"
        clinic_address = tenant_row["address"] or ""
        clinic_phone = tenant_row["phone"] or ""
        support_email = tenant_row["derivation_email"] or user_email

        # 3. Obtener datos adicionales según rol
        specialty = ""
        registration_id = ""
        phone_number = ""

        if user_role == "professional":
            prof_row = await db_pool.fetchrow(
                "SELECT specialty, registration_id, phone_number FROM professionals WHERE user_id = $1",
                user_id,
            )
            if prof_row:
                specialty = prof_row["specialty"] or ""
                registration_id = prof_row["registration_id"] or ""
                phone_number = prof_row["phone_number"] or ""

        # 4. Generar contenido según rol
        login_url = os.getenv("FRONTEND_URL", "https://app.clinicforge.com")

        if user_role == "professional":
            subject = f"👨‍⚕️ Bienvenido a {clinic_name} - Tu cuenta está activa"

            html_content = f"""
            <html>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 700px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #059669, #10b981); padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 22px;">👨‍⚕️ Bienvenido a {clinic_name}</h1>
                    <p style="color: rgba(255,255,255,0.85); margin: 5px 0 0; font-size: 14px;">Tu cuenta de profesional está activa</p>
                </div>

                <div style="padding: 25px; background: #fff; border: 1px solid #e5e7eb; border-top: none;">
                    <p style="font-size: 15px; line-height: 1.6;">Hola <strong>{user_full_name}</strong>,</p>
                    
                    <p style="font-size: 15px; line-height: 1.6;">¡Te damos la bienvenida a nuestro equipo! Tu cuenta de profesional ha sido creada y está activa.</p>
                    
                    <h3 style="color:#059669; border-bottom:2px solid #059669; padding-bottom:5px; margin-top:20px;">📋 Tus Credenciales</h3>
                    <table style="width:100%; border-collapse:collapse; margin:10px 0;">
                        <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold; width:140px;">Email</td><td style="padding:6px 12px; background:#f8f9ff;">{user_email}</td></tr>
                        <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Especialidad</td><td style="padding:6px 12px; background:#f8f9ff;">{specialty or "No especificada"}</td></tr>
                        <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Matrícula</td><td style="padding:6px 12px; background:#f8f9ff;">{registration_id or "No especificada"}</td></tr>
                        <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Teléfono</td><td style="padding:6px 12px; background:#f8f9ff;">{phone_number or "No especificado"}</td></tr>
                    </table>

                    <h3 style="color:#059669; border-bottom:2px solid #059669; padding-bottom:5px; margin-top:20px;">🏥 Datos de la Clínica</h3>
                    <table style="width:100%; border-collapse:collapse; margin:10px 0;">
                        <tr><td style="padding:6px 12px; background:#f0fff4; font-weight:bold; width:140px;">Clínica</td><td style="padding:6px 12px; background:#f8fff8;">{clinic_name}</td></tr>
                        <tr><td style="padding:6px 12px; background:#f0fff4; font-weight:bold;">Dirección</td><td style="padding:6px 12px; background:#f8fff8;">{clinic_address or "No disponible"}</td></tr>
                        <tr><td style="padding:6px 12px; background:#f0fff4; font-weight:bold;">Teléfono</td><td style="padding:6px 12px; background:#f8fff8;">{clinic_phone or "No disponible"}</td></tr>
                    </table>

                    <h3 style="color:#2563eb; border-bottom:2px solid #2563eb; padding-bottom:5px; margin-top:20px;">🔗 Acceso al Sistema</h3>
                    <div style="text-align: center; margin: 20px 0;">
                        <a href="{login_url}" style="display:inline-block; background-color:#2563eb; color:white; padding:14px 28px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:16px;">
                            🚀 Ingresar al Sistema
                        </a>
                    </div>
                    <p style="font-size: 13px; color: #666; text-align: center;">
                        Desde el panel podrás gestionar tu agenda, ver pacientes, y acceder a todas las herramientas de atención.
                    </p>

                    <h3 style="color:#7c3aed; border-bottom:2px solid #7c3aed; padding-bottom:5px; margin-top:20px;">💡 Funcionalidades Disponibles</h3>
                    <ul style="font-size: 14px; line-height: 1.8; color: #444;">
                        <li>📅 <strong>Gestión de Turnos:</strong> Consultá y administrá tu agenda diaria</li>
                        <li>👥 <strong>Fichas de Pacientes:</strong> Accedé al historial clínico y documentación</li>
                        <li>💬 <strong>Chat con Pacientes:</strong> Comunicación directa a través del sistema</li>
                        <li>📊 <strong>Reportes:</strong> Estadísticas de atención y rendimiento</li>
                        <li>🔗 <strong>Google Calendar:</strong> Sincronización de turnos (si está configurado)</li>
                    </ul>

                    <h3 style="color:#dc2626; border-bottom:2px solid #dc2626; padding-bottom:5px; margin-top:20px;">❓ Soporte</h3>
                    <p style="font-size: 14px; line-height: 1.6;">
                        Si tenés alguna pregunta o necesitás ayuda, no dudes en contactarnos:<br>
                        📧 <strong>Email:</strong> {support_email}
                    </p>

                    <p style="margin-top: 25px; font-size: 11px; color: #999; text-align: center; border-top: 1px solid #eee; padding-top: 15px;">
                        Este email fue enviado automáticamente por {clinic_name}.<br>
                        Te recomendamos guardar este mensaje para futuras referencias.
                    </p>
                </div>
            </body>
            </html>
            """

        elif user_role == "secretary":
            subject = f"📋 Bienvenido a {clinic_name} - Tu cuenta está activa"

            html_content = f"""
            <html>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 700px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #7c3aed, #a78bfa); padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 22px;">📋 Bienvenido a {clinic_name}</h1>
                    <p style="color: rgba(255,255,255,0.85); margin: 5px 0 0; font-size: 14px;">Tu cuenta de secretaría está activa</p>
                </div>

                <div style="padding: 25px; background: #fff; border: 1px solid #e5e7eb; border-top: none;">
                    <p style="font-size: 15px; line-height: 1.6;">Hola <strong>{user_full_name}</strong>,</p>
                    
                    <p style="font-size: 15px; line-height: 1.6;">¡Te damos la bienvenida a nuestro equipo de atención! Tu cuenta de secretaría ha sido creada y está activa.</p>
                    
                    <h3 style="color:#7c3aed; border-bottom:2px solid #7c3aed; padding-bottom:5px; margin-top:20px;">📋 Tus Credenciales</h3>
                    <table style="width:100%; border-collapse:collapse; margin:10px 0;">
                        <tr><td style="padding:6px 12px; background:#f5f3ff; font-weight:bold; width:140px;">Email</td><td style="padding:6px 12px; background:#fafaff;">{user_email}</td></tr>
                        <tr><td style="padding:6px 12px; background:#f5f3ff; font-weight:bold;">Teléfono</td><td style="padding:6px 12px; background:#fafaff;">{phone_number or "No especificado"}</td></tr>
                    </table>

                    <h3 style="color:#7c3aed; border-bottom:2px solid #7c3aed; padding-bottom:5px; margin-top:20px;">🏥 Datos de la Clínica</h3>
                    <table style="width:100%; border-collapse:collapse; margin:10px 0;">
                        <tr><td style="padding:6px 12px; background:#f5f3ff; font-weight:bold; width:140px;">Clínica</td><td style="padding:6px 12px; background:#fafaff;">{clinic_name}</td></tr>
                        <tr><td style="padding:6px 12px; background:#f5f3ff; font-weight:bold;">Dirección</td><td style="padding:6px 12px; background:#fafaff;">{clinic_address or "No disponible"}</td></tr>
                        <tr><td style="padding:6px 12px; background:#f5f3ff; font-weight:bold;">Teléfono</td><td style="padding:6px 12px; background:#fafaff;">{clinic_phone or "No disponible"}</td></tr>
                    </table>

                    <h3 style="color:#2563eb; border-bottom:2px solid #2563eb; padding-bottom:5px; margin-top:20px;">🔗 Acceso al Sistema</h3>
                    <div style="text-align: center; margin: 20px 0;">
                        <a href="{login_url}" style="display:inline-block; background-color:#2563eb; color:white; padding:14px 28px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:16px;">
                            🚀 Ingresar al Sistema
                        </a>
                    </div>

                    <h3 style="color:#059669; border-bottom:2px solid #059669; padding-bottom:5px; margin-top:20px;">💡 Funcionalidades Disponibles</h3>
                    <ul style="font-size: 14px; line-height: 1.8; color: #444;">
                        <li>📅 <strong>Gestión de Agenda:</strong> Crear, modificar y cancelar turnos</li>
                        <li>✅ <strong>Confirmación de Turnos:</strong> Confirmar o rechazar solicitudes de turno</li>
                        <li>👥 <strong>Registro de Pacientes:</strong> Alta y gestión de fichas de pacientes</li>
                        <li>💬 <strong>Historial de Conversaciones:</strong> Ver el historial de chat con pacientes</li>
                        <li>💳 <strong>Pagos:</strong> Registro de pagos y comprobantes</li>
                    </ul>

                    <h3 style="color:#dc2626; border-bottom:2px solid #dc2626; padding-bottom:5px; margin-top:20px;">❓ Soporte</h3>
                    <p style="font-size: 14px; line-height: 1.6;">
                        Si tenés alguna pregunta o necesitás ayuda:<br>
                        📧 <strong>Email:</strong> {support_email}
                    </p>

                    <p style="margin-top: 25px; font-size: 11px; color: #999; text-align: center; border-top: 1px solid #eee; padding-top: 15px;">
                        Este email fue enviado automáticamente por {clinic_name}.
                    </p>
                </div>
            </body>
            </html>
            """

        elif user_role == "ceo":
            subject = f"⚙️ Bienvenido a {clinic_name} - Acceso como Administrador"

            html_content = f"""
            <html>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 700px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #f59e0b, #d97706); padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 22px;">⚙️ Bienvenido a {clinic_name}</h1>
                    <p style="color: rgba(255,255,255,0.85); margin: 5px 0 0; font-size: 14px;">Tu acceso como Administrador está activo</p>
                </div>

                <div style="padding: 25px; background: #fff; border: 1px solid #e5e7eb; border-top: none;">
                    <p style="font-size: 15px; line-height: 1.6;">Hola <strong>{user_full_name}</strong>,</p>
                    
                    <p style="font-size: 15px; line-height: 1.6;">¡Felicitaciones! Tu cuenta de Administrador ha sido creada. Ahora podés gestionar completamente {clinic_name}.</p>
                    
                    <h3 style="color:#f59e0b; border-bottom:2px solid #f59e0b; padding-bottom:5px; margin-top:20px;">📋 Tus Credenciales</h3>
                    <table style="width:100%; border-collapse:collapse; margin:10px 0;">
                        <tr><td style="padding:6px 12px; background:#fffbeb; font-weight:bold; width:140px;">Email</td><td style="padding:6px 12px; background:#fffef0;">{user_email}</td></tr>
                        <tr><td style="padding:6px 12px; background:#fffbeb; font-weight:bold;">Clínica</td><td style="padding:6px 12px; background:#fffef0;">{clinic_name}</td></tr>
                        <tr><td style="padding:6px 12px; background:#fffbeb; font-weight:bold;">Dirección</td><td style="padding:6px 12px; background:#fffef0;">{clinic_address or "No disponible"}</td></tr>
                        <tr><td style="padding:6px 12px; background:#fffbeb; font-weight:bold;">Teléfono</td><td style="padding:6px 12px; background:#fffef0;">{clinic_phone or "No disponible"}</td></tr>
                    </table>

                    <h3 style="color:#2563eb; border-bottom:2px solid #2563eb; padding-bottom:5px; margin-top:20px;">🔗 Acceso al Sistema</h3>
                    <div style="text-align: center; margin: 20px 0;">
                        <a href="{login_url}" style="display:inline-block; background-color:#f59e0b; color:white; padding:14px 28px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:16px;">
                            🚀 Ingresar al Panel
                        </a>
                    </div>

                    <h3 style="color:#059669; border-bottom:2px solid #059669; padding-bottom:5px; margin-top:20px;">📊 Dashboard y Métricas</h3>
                    <ul style="font-size: 14px; line-height: 1.8; color: #444;">
                        <li>📈 <strong>Ingresos y Estadísticas:</strong> Seguimiento de ingresos y performance</li>
                        <li>👥 <strong>Gestión de Relaciones:</strong> Pacientes y profesionales</li>
                        <li>📑 <strong>Reportes Detallados:</strong> Informes completos de la clínica</li>
                    </ul>

                    <h3 style="color:#7c3aed; border-bottom:2px solid #7c3aed; padding-bottom:5px; margin-top:20px;">⚙️ Configuraciones Disponibles</h3>
                    <ul style="font-size: 14px; line-height: 1.8; color: #444;">
                        <li>🏥 <strong>Configurar Clínica:</strong> Datos, logo, horarios, servicios</li>
                        <li>👤 <strong>Gestionar Usuarios:</strong> Agregar profesionales, secretarias, permisos</li>
                        <li>📅 <strong>Ajustar Agenda:</strong> Horarios de atención, duraciones</li>
                        <li>📆 <strong>Google Calendar:</strong> Integrar y sincronizar turnos</li>
                    </ul>

                    <h3 style="color:#dc2626; border-bottom:2px solid #dc2626; padding-bottom:5px; margin-top:20px;">❓ Soporte</h3>
                    <p style="font-size: 14px; line-height: 1.6;">
                        Si tenés alguna pregunta o necesitás ayuda:<br>
                        📧 <strong>Email:</strong> {support_email}
                    </p>

                    <p style="margin-top: 25px; font-size: 11px; color: #999; text-align: center; border-top: 1px solid #eee; padding-top: 15px;">
                        Este email fue enviado automáticamente por {clinic_name}.<br>
                        Guardá este mensaje para futuras referencias.
                    </p>
                </div>
            </body>
            </html>
            """
        else:
            # Rol desconocido - no enviar
            logger.warning(f"⚠️ Rol desconocido para email de bienvenida: {user_role}")
            return False

        # 5. Enviar email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = email_svc.smtp_sender
        msg["To"] = user_email
        msg.attach(MIMEText(html_content, "html"))

        if email_svc.smtp_port == 465:
            server = smtplib.SMTP_SSL(email_svc.smtp_host, email_svc.smtp_port)
        else:
            server = smtplib.SMTP(email_svc.smtp_host, email_svc.smtp_port)
            server.starttls()

        server.login(email_svc.smtp_user, email_svc.smtp_pass)
        server.sendmail(email_svc.smtp_sender, [user_email], msg.as_string())
        server.quit()

        logger.info(f"📧 Email de bienvenida enviado a {user_email} (rol: {user_role})")
        return True

    except Exception as e:
        logger.error(f"❌ Error enviando email de bienvenida: {e}")
        return False


async def send_plan_payment_confirmation_email(
    tenant_id: int,
    patient_id: int,
    payment_id: str,
    db_pool,
) -> dict:
    """
    Envía email de confirmación de pago de plan de tratamiento al paciente.

    Args:
        tenant_id: ID de la clínica/sede
        patient_id: ID del paciente
        payment_id: UUID del pago en treatment_plan_payments
        db_pool: Pool de conexión a la base de datos

    Returns:
        dict: {"success": bool, "summary": str}
    """
    email_svc = EmailService()

    # Validar configuración SMTP
    if not email_svc.smtp_host or not email_svc.smtp_user:
        logger.warning(
            "⚠️ SMTP no configurado. Saltando email de confirmación de pago de plan."
        )
        return {"success": False, "summary": "SMTP no configurado"}

    try:
        # 1. Obtener datos del pago
        payment_row = await db_pool.fetchrow(
            """
            SELECT 
                pp.id, pp.amount, pp.payment_method, pp.payment_date, pp.plan_id,
                tp.name as plan_name, tp.approved_total, tp.patient_id,
                p.first_name, p.last_name, p.email, p.phone_number,
                t.clinic_name, t.address, t.phone, t.country_code
            FROM treatment_plan_payments pp
            JOIN treatment_plans tp ON pp.plan_id = tp.id
            JOIN patients p ON tp.patient_id = p.id
            JOIN tenants t ON pp.tenant_id = t.id
            WHERE pp.id = $1 AND pp.tenant_id = $2
            """,
            payment_id,
            tenant_id,
        )

        if not payment_row:
            logger.warning(
                f"⚠️ Pago {payment_id} no encontrado para email de confirmación."
            )
            return {"success": False, "summary": "Pago no encontrado"}

        # 2. Validar que el pago pertenece al paciente indicado
        if payment_row["patient_id"] != patient_id:
            logger.warning(
                f"⚠️ Pago {payment_id} no pertenece al paciente {patient_id}."
            )
            return {"success": False, "summary": "Pago no pertenece al paciente"}

        # 3. Validar email del paciente
        patient_email = payment_row["email"]
        if not patient_email or not patient_email.strip():
            logger.info(
                f"⚠️ Paciente {patient_id} no tiene email. No se envía email de confirmación."
            )
            return {"success": False, "summary": "Paciente sin email"}

        patient_name = (
            f"{payment_row['first_name']} {payment_row['last_name']}".strip()
            or payment_row["first_name"]
        )
        plan_name = payment_row["plan_name"]
        amount = float(payment_row["amount"])
        payment_method = payment_row["payment_method"]
        payment_date = payment_row["payment_date"]
        clinic_name = payment_row["clinic_name"] or "Nuestra Clínica"
        clinic_address = payment_row["address"] or ""
        clinic_phone = payment_row["phone"] or ""
        country_code = payment_row["country_code"] or "AR"

        # 4. Calcular totales del plan
        paid_total = await db_pool.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM treatment_plan_payments WHERE plan_id = $1 AND tenant_id = $2",
            payment_row["plan_id"],
            tenant_id,
        )

        approved_total = (
            float(payment_row["approved_total"]) if payment_row["approved_total"] else 0
        )
        pending_total = max(0, approved_total - paid_total)

        # Calcular porcentaje
        paid_percentage = (
            int((paid_total / approved_total) * 100) if approved_total > 0 else 0
        )

        # 5. Determinar idioma del template
        lang = _language_from_country(country_code)

        # 6. Renderizar template según idioma
        if lang == "es":
            subject = f"✅ Pago registrado - {plan_name} - {clinic_name}"
            html_content = _render_plan_payment_template_es(
                patient_name=patient_name,
                clinic_name=clinic_name,
                plan_name=plan_name,
                amount=amount,
                payment_method=_format_payment_method(payment_method),
                payment_date=payment_date.strftime("%d/%m/%Y") if payment_date else "",
                approved_total=approved_total,
                paid_total=paid_total,
                pending_total=pending_total,
                paid_percentage=paid_percentage,
                clinic_address=clinic_address,
                clinic_phone=clinic_phone,
            )
        elif lang == "en":
            subject = f"✅ Payment recorded - {plan_name} - {clinic_name}"
            html_content = _render_plan_payment_template_en(
                patient_name=patient_name,
                clinic_name=clinic_name,
                plan_name=plan_name,
                amount=amount,
                payment_method=_format_payment_method(payment_method),
                payment_date=payment_date.strftime("%d/%m/%Y") if payment_date else "",
                approved_total=approved_total,
                paid_total=paid_total,
                pending_total=pending_total,
                paid_percentage=paid_percentage,
                clinic_address=clinic_address,
                clinic_phone=clinic_phone,
            )
        else:  # fr o default
            subject = f"✅ Paiement enregistré - {plan_name} - {clinic_name}"
            html_content = _render_plan_payment_template_fr(
                patient_name=patient_name,
                clinic_name=clinic_name,
                plan_name=plan_name,
                amount=amount,
                payment_method=_format_payment_method(payment_method),
                payment_date=payment_date.strftime("%d/%m/%Y") if payment_date else "",
                approved_total=approved_total,
                paid_total=paid_total,
                pending_total=pending_total,
                paid_percentage=paid_percentage,
                clinic_address=clinic_address,
                clinic_phone=clinic_phone,
            )

        # 7. Enviar email
        to_emails = [patient_email.strip()]
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = email_svc.smtp_sender
        msg["To"] = ", ".join(to_emails)
        msg.attach(MIMEText(html_content, "html"))

        if email_svc.smtp_port == 465:
            server = smtplib.SMTP_SSL(email_svc.smtp_host, email_svc.smtp_port)
        else:
            server = smtplib.SMTP(email_svc.smtp_host, email_svc.smtp_port)
            server.starttls()

        server.login(email_svc.smtp_user, email_svc.smtp_pass)
        server.sendmail(email_svc.smtp_sender, to_emails, msg.as_string())
        server.quit()

        summary = f"Email de confirmación enviado a {patient_email} para plan '{plan_name}'. Pagado: ${paid_total:.2f} / ${approved_total:.2f} ({paid_percentage}%)"
        logger.info(f"📧 {summary}")
        return {"success": True, "summary": summary}

    except Exception as e:
        logger.error(f"❌ Error enviando email de confirmación de pago de plan: {e}")
        return {"success": False, "summary": f"Error: {str(e)}"}


def _format_payment_method(method: str) -> str:
    """Formatea el método de pago para mostrar en el email."""
    mapping = {
        "cash": "Efectivo",
        "transfer": "Transferencia",
        "card": "Tarjeta",
        "insurance": "Seguro",
    }
    return mapping.get(method, method.capitalize())


def _render_plan_payment_template_es(
    patient_name: str,
    clinic_name: str,
    plan_name: str,
    amount: float,
    payment_method: str,
    payment_date: str,
    approved_total: float,
    paid_total: float,
    pending_total: float,
    paid_percentage: int,
    clinic_address: str,
    clinic_phone: str,
) -> str:
    """Renderiza el template de confirmación de pago de plan en español."""
    status_text = (
        "¡Pago completado!" if pending_total == 0 else "Pago parcial registrado"
    )

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Confirmación de pago</title>
    </head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; line-height: 1.6;">
        <div style="background: linear-gradient(135deg, #10b981, #059669); padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">✅ {status_text}</h1>
            <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0; font-size: 15px;">{clinic_name}</p>
        </div>

        <div style="padding: 25px; background: #fff; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
            <p style="font-size: 16px; margin-bottom: 20px;">
                Hola <strong>{patient_name}</strong>,<br>
                Tu pago ha sido registrado correctamente. Aquí tienes los detalles:
            </p>

            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                <h2 style="color: #065f46; margin-top: 0; border-bottom: 2px solid #10b981; padding-bottom: 8px;">📋 Detalles del Pago</h2>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold; width: 40%;">Plan de Tratamiento:</td>
                        <td style="padding: 10px 0;">{plan_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold;">Monto pagado:</td>
                        <td style="padding: 10px 0; font-size: 18px; color: #065f46; font-weight: bold;">${amount:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold;">Método de pago:</td>
                        <td style="padding: 10px 0;">{payment_method}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold;">Fecha:</td>
                        <td style="padding: 10px 0;">{payment_date}</td>
                    </tr>
                </table>
            </div>

            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                <h3 style="color: #1e40af; margin-top: 0; margin-bottom: 15px;">📊 Progreso del Plan</h3>
                
                <!-- Progress Bar -->
                <div style="background: #e2e8f0; border-radius: 10px; height: 20px; width: 100%; overflow: hidden; margin-bottom: 10px;">
                    <div style="background: linear-gradient(90deg, #10b981, #34d399); border-radius: 10px; height: 100%; width: {paid_percentage}%; transition: width 0.3s ease;"></div>
                </div>
                <p style="text-align: center; font-weight: bold; color: #065f46; margin: 0 0 15px 0;">
                    {paid_percentage}% pagado
                </p>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #64748b;">Total aprobado:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold;">${approved_total:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #10b981;">Total pagado:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; color: #10b981;">${paid_total:,.2f}</td>
                    </tr>
                    <tr style="border-top: 2px solid #e2e8f0;">
                        <td style="padding: 8px 0; color: #f59e0b; font-weight: bold;">Pendiente:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; color: #f59e0b;">${pending_total:,.2f}</td>
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
                    Si tienes alguna duda, puedes responder a este email o contactar a la clínica.
                </p>
            </div>
        </div>
    </body>
    </html>
    """


def _render_plan_payment_template_en(
    patient_name: str,
    clinic_name: str,
    plan_name: str,
    amount: float,
    payment_method: str,
    payment_date: str,
    approved_total: float,
    paid_total: float,
    pending_total: float,
    paid_percentage: int,
    clinic_address: str,
    clinic_phone: str,
) -> str:
    """Renderiza el template de confirmación de pago de plan en inglés."""
    status_text = (
        "Payment completed!" if pending_total == 0 else "Partial payment recorded"
    )

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payment Confirmation</title>
    </head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; line-height: 1.6;">
        <div style="background: linear-gradient(135deg, #10b981, #059669); padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">✅ {status_text}</h1>
            <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0; font-size: 15px;">{clinic_name}</p>
        </div>

        <div style="padding: 25px; background: #fff; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
            <p style="font-size: 16px; margin-bottom: 20px;">
                Hello <strong>{patient_name}</strong>,<br>
                Your payment has been successfully recorded. Here are the details:
            </p>

            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                <h2 style="color: #065f46; margin-top: 0; border-bottom: 2px solid #10b981; padding-bottom: 8px;">📋 Payment Details</h2>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold; width: 40%;">Treatment Plan:</td>
                        <td style="padding: 10px 0;">{plan_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold;">Amount paid:</td>
                        <td style="padding: 10px 0; font-size: 18px; color: #065f46; font-weight: bold;">${amount:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold;">Payment method:</td>
                        <td style="padding: 10px 0;">{payment_method}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold;">Date:</td>
                        <td style="padding: 10px 0;">{payment_date}</td>
                    </tr>
                </table>
            </div>

            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                <h3 style="color: #1e40af; margin-top: 0; margin-bottom: 15px;">📊 Plan Progress</h3>
                
                <!-- Progress Bar -->
                <div style="background: #e2e8f0; border-radius: 10px; height: 20px; width: 100%; overflow: hidden; margin-bottom: 10px;">
                    <div style="background: linear-gradient(90deg, #10b981, #34d399); border-radius: 10px; height: 100%; width: {paid_percentage}%; transition: width 0.3s ease;"></div>
                </div>
                <p style="text-align: center; font-weight: bold; color: #065f46; margin: 0 0 15px 0;">
                    {paid_percentage}% paid
                </p>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #64748b;">Total approved:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold;">${approved_total:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #10b981;">Total paid:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; color: #10b981;">${paid_total:,.2f}</td>
                    </tr>
                    <tr style="border-top: 2px solid #e2e8f0;">
                        <td style="padding: 8px 0; color: #f59e0b; font-weight: bold;">Pending:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; color: #f59e0b;">${pending_total:,.2f}</td>
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
    """


def _render_plan_payment_template_fr(
    patient_name: str,
    clinic_name: str,
    plan_name: str,
    amount: float,
    payment_method: str,
    payment_date: str,
    approved_total: float,
    paid_total: float,
    pending_total: float,
    paid_percentage: int,
    clinic_address: str,
    clinic_phone: str,
) -> str:
    """Renderiza el template de confirmación de pago de plan en francés."""
    status_text = (
        "Paiement terminé!" if pending_total == 0 else "Paiement partiel enregistré"
    )

    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Confirmation de paiement</title>
    </head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; line-height: 1.6;">
        <div style="background: linear-gradient(135deg, #10b981, #059669); padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">✅ {status_text}</h1>
            <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0; font-size: 15px;">{clinic_name}</p>
        </div>

        <div style="padding: 25px; background: #fff; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
            <p style="font-size: 16px; margin-bottom: 20px;">
                Bonjour <strong>{patient_name}</strong>,<br>
                Votre paiement a été enregistré avec succès. Voici les détails:
            </p>

            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                <h2 style="color: #065f46; margin-top: 0; border-bottom: 2px solid #10b981; padding-bottom: 8px;">📋 Détails du Paiement</h2>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold; width: 40%;">Plan de traitement:</td>
                        <td style="padding: 10px 0;">{plan_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold;">Montant payé:</td>
                        <td style="padding: 10px 0; font-size: 18px; color: #065f46; font-weight: bold;">{amount:,.2f}€</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold;">Méthode de paiement:</td>
                        <td style="padding: 10px 0;">{payment_method}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold;">Date:</td>
                        <td style="padding: 10px 0;">{payment_date}</td>
                    </tr>
                </table>
            </div>

            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                <h3 style="color: #1e40af; margin-top: 0; margin-bottom: 15px;">📊 Progression du Plan</h3>
                
                <!-- Progress Bar -->
                <div style="background: #e2e8f0; border-radius: 10px; height: 20px; width: 100%; overflow: hidden; margin-bottom: 10px;">
                    <div style="background: linear-gradient(90deg, #10b981, #34d399); border-radius: 10px; height: 100%; width: {paid_percentage}%; transition: width 0.3s ease;"></div>
                </div>
                <p style="text-align: center; font-weight: bold; color: #065f46; margin: 0 0 15px 0;">
                    {paid_percentage}% payé
                </p>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #64748b;">Total approuvé:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold;">{approved_total:,.2f}€</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #10b981;">Total payé:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; color: #10b981;">{paid_total:,.2f}€</td>
                    </tr>
                    <tr style="border-top: 2px solid #e2e8f0;">
                        <td style="padding: 8px 0; color: #f59e0b; font-weight: bold;">En attente:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; color: #f59e0b;">{pending_total:,.2f}€</td>
                    </tr>
                </table>
            </div>

            <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 18px; margin-bottom: 25px;">
                <h3 style="color: #1e40af; margin-top: 0;">🏥 Informations de la clinique</h3>
                <p style="margin: 8px 0;">
                    <strong>{clinic_name}</strong><br>
                    {clinic_address}<br>
                    Téléphone: {clinic_phone}
                </p>
            </div>

            <div style="text-align: center; margin-top: 25px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 14px; margin: 0;">
                    Ceci est un reçu de paiement automatique.<br>
                    Si vous avez des questions, vous pouvez répondre à cet email ou contacter la clinique.
                </p>
            </div>
        </div>
    </body>
    </html>
    """


async def send_backup_verification_code(
    to_email: str,
    code: str,
    clinic_name: str,
) -> bool:
    """
    Send a 6-digit verification code for backup download authorization.

    Returns True if sent successfully, False otherwise.
    """
    email_svc = EmailService()

    if not email_svc.smtp_host or not email_svc.smtp_user:
        logger.warning("[backup] SMTP not configured — cannot send verification code")
        return False

    subject = f"ClinicForge — Código de verificación para Backup"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background: #0d1117; color: #e6edf3; padding: 20px;">
        <div style="max-width: 500px; margin: 0 auto; background: #161b22; border-radius: 12px; padding: 30px; border: 1px solid rgba(255,255,255,0.1);">
            <h2 style="color: #ffffff; margin-top: 0;">Código de verificación</h2>
            <p>Se solicitó un backup completo de <strong>{_html.escape(clinic_name)}</strong>.</p>
            <p>Tu código de verificación es:</p>
            <div style="background: #0d1117; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #58a6ff; font-family: monospace;">{code}</span>
            </div>
            <p style="color: #8b949e; font-size: 13px;">Este código expira en <strong>10 minutos</strong>.</p>
            <p style="color: #8b949e; font-size: 13px;">Si no solicitaste este backup, ignorá este email y verificá la seguridad de tu cuenta.</p>
            <hr style="border: none; border-top: 1px solid rgba(255,255,255,0.1); margin: 20px 0;">
            <p style="color: #484f58; font-size: 11px;">ClinicForge — Backup & Restore System</p>
        </div>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = email_svc.smtp_sender or email_svc.smtp_user
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        if email_svc.smtp_port == 465:
            with smtplib.SMTP_SSL(email_svc.smtp_host, email_svc.smtp_port) as server:
                server.login(email_svc.smtp_user, email_svc.smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(email_svc.smtp_host, email_svc.smtp_port) as server:
                server.starttls()
                server.login(email_svc.smtp_user, email_svc.smtp_pass)
                server.send_message(msg)

        logger.info(f"[backup] Verification code sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"[backup] Failed to send verification code: {e}")
        return False
