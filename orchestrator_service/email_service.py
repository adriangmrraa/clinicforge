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

    def send_handoff_email(self, to_email: str, patient_name: str, phone: str, reason: str, chat_history_preview: str = ""):
        """
        Envía un correo de notificación de derivación humana.
        """
        if not self.smtp_host or not self.smtp_user:
            logger.warning("⚠️ SMTP not configured. Skipping email.")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🔔 Derivación Humana: {patient_name} ({phone})"
            msg["From"] = self.smtp_sender
            msg["To"] = to_email

            # Create WhatsApp Link
            wa_link = f"https://wa.me/{phone.replace('+', '')}"

            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="background-color: #f8f9fa; padding: 20px; text-align: center;">
                    <h2 style="color: #0d6efd;">Nueva Derivación de IA</h2>
                </div>
                <div style="padding: 20px;">
                    <p>Hola,</p>
                    <p>El agente de IA ha derivado un chat que requiere atención humana.</p>
                    
                    <div style="background-color: #e9ecef; padding: 15px; border-radius: 5px; margin: 15px 0;">
                        <p><strong>Paciente:</strong> {patient_name}</p>
                        <p><strong>Teléfono:</strong> {phone}</p>
                        <p><strong>Motivo:</strong> {reason}</p>
                    </div>

                    <p><strong>Última interacción:</strong></p>
                    <blockquote style="border-left: 3px solid #ccc; padding-left: 10px; color: #666;">
                        {chat_history_preview}
                    </blockquote>

                    <br/>
                    <a href="{wa_link}" style="background-color: #25D366; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Abrir Chat en WhatsApp
                    </a>
                    
                    <p style="margin-top: 20px; font-size: 12px; color: #999;">
                        Este es un mensaje automático del sistema {self.clinic_name}.
                    </p>
                </div>
            </body>
            </html>
            """

            msg.attach(MIMEText(html_content, "html"))

            if self.smtp_port == 465:
                # SSL connection (Implicit SSL)
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            else:
                # TLS connection (STARTTLS)
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()

            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_sender, to_email, msg.as_string())
            server.quit()
            
            logger.info(f"📧 Email de derivación enviado a {to_email}")
            return True

        except Exception as e:
            logger.error(f"❌ Error sending email: {e}")
            return False

email_service = EmailService()
