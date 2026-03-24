import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

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
            channel = pi.get('_channel', 'whatsapp')

            # Build contact links based on channel
            phone_digits = phone.replace('+', '').replace(' ', '').replace('-', '')
            wa_link = f"https://wa.me/{phone_digits}"
            ig_psid = pi.get('instagram_psid', '')
            fb_psid = pi.get('facebook_psid', '')

            contact_buttons = []
            # WhatsApp is always available if we have a phone
            if phone_digits and not phone_digits.startswith('ig_') and not phone_digits.startswith('fb_'):
                contact_buttons.append(
                    f'<a href="{wa_link}" style="display:inline-block; background-color:#25D366; color:white; '
                    f'padding:12px 24px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:14px; margin:4px;">'
                    f'📱 WhatsApp</a>'
                )
            # Instagram
            if ig_psid or channel == 'instagram':
                ig_url = f"https://www.instagram.com/direct/t/{ig_psid}" if ig_psid else "https://www.instagram.com/direct/inbox/"
                contact_buttons.append(
                    f'<a href="{ig_url}" style="display:inline-block; background:linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888); '
                    f'color:white; padding:12px 24px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:14px; margin:4px;">'
                    f'📷 Instagram DM</a>'
                )
            # Facebook
            if fb_psid or channel == 'facebook':
                fb_url = f"https://www.facebook.com/messages/t/{fb_psid}" if fb_psid else "https://www.facebook.com/messages/"
                contact_buttons.append(
                    f'<a href="{fb_url}" style="display:inline-block; background-color:#1877F2; color:white; '
                    f'padding:12px 24px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:14px; margin:4px;">'
                    f'💬 Facebook Messenger</a>'
                )

            if not contact_buttons:
                contact_buttons.append(
                    f'<a href="{wa_link}" style="display:inline-block; background-color:#25D366; color:white; '
                    f'padding:12px 24px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:14px; margin:4px;">'
                    f'📱 Contactar por WhatsApp</a>'
                )

            contact_buttons_html = "\n".join(contact_buttons)
            channel_label = {'whatsapp': 'WhatsApp', 'instagram': 'Instagram', 'facebook': 'Facebook Messenger'}.get(channel, channel.title())

            # --- Build patient info section ---
            patient_section = f"""
            <table style="width:100%; border-collapse:collapse; margin:10px 0;">
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold; width:140px;">Nombre</td><td style="padding:6px 12px; background:#f8f9ff;">{patient_name}</td></tr>
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Teléfono</td><td style="padding:6px 12px; background:#f8f9ff;">{phone}</td></tr>
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">DNI</td><td style="padding:6px 12px; background:#f8f9ff;">{pi.get('dni', 'No registrado')}</td></tr>
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Email</td><td style="padding:6px 12px; background:#f8f9ff;">{pi.get('email', 'No registrado')}</td></tr>
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Ciudad</td><td style="padding:6px 12px; background:#f8f9ff;">{pi.get('city', 'No registrada')}</td></tr>
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Nivel urgencia</td><td style="padding:6px 12px; background:#f8f9ff;">{pi.get('urgency_level', 'normal')}</td></tr>
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Fuente</td><td style="padding:6px 12px; background:#f8f9ff;">{pi.get('first_touch_source', 'No registrada')}</td></tr>
                <tr><td style="padding:6px 12px; background:#f0f4ff; font-weight:bold;">Canal</td><td style="padding:6px 12px; background:#f8f9ff;">{channel_label}</td></tr>
            </table>
            """

            # --- Build anamnesis section ---
            anamnesis_section = ""
            if anamnesis_data:
                rows = ""
                field_labels = {
                    'base_diseases': 'Enfermedades base',
                    'habitual_medication': 'Medicación habitual',
                    'allergies': 'Alergias',
                    'previous_surgeries': 'Cirugías previas',
                    'is_smoker': 'Fumador',
                    'is_pregnant': 'Embarazada',
                    'has_pacemaker': 'Marcapasos',
                    'blood_pressure_issues': 'Presión arterial',
                    'diabetes': 'Diabetes',
                    'heart_condition': 'Condición cardíaca',
                    'bleeding_disorder': 'Trastorno hemorrágico',
                    'dental_anxiety_level': 'Nivel de ansiedad dental',
                    'last_dental_visit': 'Última visita dental',
                    'main_concern': 'Motivo de consulta principal',
                    'additional_notes': 'Notas adicionales',
                }
                for key, label in field_labels.items():
                    val = anamnesis_data.get(key)
                    if val and str(val).strip() and str(val).strip().lower() not in ('none', 'null', 'no', 'false'):
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
                    <tr><td style="padding:5px 10px; background:#eff6ff; font-weight:bold; width:140px;">Fecha/Hora</td><td style="padding:5px 10px; background:#f8faff;">{next_appointment.get('datetime', '—')}</td></tr>
                    <tr><td style="padding:5px 10px; background:#eff6ff; font-weight:bold;">Tratamiento</td><td style="padding:5px 10px; background:#f8faff;">{next_appointment.get('type', '—')}</td></tr>
                    <tr><td style="padding:5px 10px; background:#eff6ff; font-weight:bold;">Profesional</td><td style="padding:5px 10px; background:#f8faff;">{next_appointment.get('professional', '—')}</td></tr>
                    <tr><td style="padding:5px 10px; background:#eff6ff; font-weight:bold;">Estado</td><td style="padding:5px 10px; background:#f8faff;">{next_appointment.get('status', '—')}</td></tr>
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

            logger.info(f"📧 Email de derivación enviado a {len(to_emails)} destinatarios: {', '.join(to_emails)}")
            return True

        except Exception as e:
            logger.error(f"❌ Error sending handoff email: {e}")
            return False

email_service = EmailService()
