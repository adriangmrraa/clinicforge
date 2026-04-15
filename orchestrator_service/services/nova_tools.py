async def _enviar_email_chat(args: Dict, tenant_id: int, user_role: str) -> str:
    """
    Envía un email con el resumen de una conversación de chat.
    - Si no se provee email, envía a todos los profesionales, CEOs y secretaries.
    - Si se provee email, envía solo a ese destinatario.
    """
    phone_number = args.get("phone_number")
    destinatario = args.get("destinatario")
    asunto = args.get("asunto", "Resumen de conversación")

    if not phone_number:
        return "Necesito el número de teléfono del paciente para generar el resumen."

    try:
        from email_service import EmailService

        email_svc = EmailService()

        # Obtener datos del paciente/conversación
        patient_row = await db.pool.fetchrow(
            """SELECT id, first_name, last_name, phone_number, email, insurance_provider
               FROM patients WHERE phone_number = $1 AND tenant_id = $2""",
            phone_number,
            tenant_id,
        )

        if not patient_row:
            return f"No encontré ningún paciente con el teléfono {phone_number}."

        patient_name = (
            f"{patient_row['first_name']} {patient_row['last_name'] or ''}".strip()
        )

        # Obtener últimos mensajes del chat
        messages_rows = await db.pool.fetch(
            """SELECT content, direction, created_at FROM chat_messages
               WHERE external_user_id = $1 AND tenant_id = $2
               ORDER BY created_at DESC LIMIT 20""",
            phone_number,
            tenant_id,
        )

        chat_history_html = ""
        for msg in reversed(messages_rows):
            direction = "Paciente" if msg["direction"] == "inbound" else "Clínica"
            chat_history_html += (
                f"<p><strong>{direction}:</strong> {msg['content']}</p>"
            )

        # Obtener próximo turno
        next_apt = await db.pool.fetchrow(
            """SELECT a.appointment_datetime, a.appointment_type, p.first_name as prof_name
               FROM appointments a
               JOIN professionals p ON a.professional_id = p.id
               WHERE a.patient_id = $1 AND a.status NOT IN ('cancelled', 'completed')
                 AND a.appointment_datetime > NOW()
               ORDER BY a.appointment_datetime ASC LIMIT 1""",
            patient_row["id"],
        )

        next_appointment_str = ""
        if next_apt:
            from services.email_templates import _format_datetime

            next_appointment_str = f"{_format_datetime(next_apt['appointment_datetime'])} - {next_apt['appointment_type']} con {next_apt['prof_name']}"

        # Si no hay destinatario específico, obtener todos los emails del staff
        if not destinatario:
            # Obtener emails de todos los profesionales, CEOs y secretaries activos
            staff_emails = await db.pool.fetch(
                """SELECT DISTINCT u.email FROM users u
                   JOIN professionals prof ON prof.user_id = u.id
                   WHERE prof.tenant_id = $1 AND prof.is_active = true AND u.status = 'active' AND u.email IS NOT NULL
                   UNION
                   SELECT u.email FROM users u
                   WHERE u.role = 'ceo' AND u.status = 'active' AND u.email IS NOT NULL""",
                tenant_id,
            )
            destinatarios = [row["email"] for row in staff_emails if row.get("email")]
            if not destinatarios:
                return (
                    "No hay profesionales o CEOs con email configurado en esta clínica."
                )
        else:
            destinatarios = [destinatario]

        # Construir contenido del email
        contenido = f"""
        <h2>Resumen de conversación</h2>
        <p><strong>Paciente:</strong> {patient_name}</p>
        <p><strong>Teléfono:</strong> {phone_number}</p>
        <p><strong>Obra Social:</strong> {patient_row.get("insurance_provider", "Particular") or "No especificada"}</p>
        {"<p><strong>Próximo turno:</strong> " + next_appointment_str + "</p>" if next_appointment_str else ""}
        <h3>Últimos mensajes:</h3>
        {chat_history_html}
        """

        # Enviar email
        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            import smtplib

            if not email_svc.smtp_host or not email_svc.smtp_user:
                return "El sistema de email no está configurado. Contactá al administrador."

            msg = MIMEMultipart("alternative")
            msg["Subject"] = asunto
            msg["From"] = email_svc.smtp_sender
            msg["To"] = ", ".join(destinatarios)

            part = MIMEText(contenido, "html")
            msg.attach(part)

            if email_svc.smtp_port == 465:
                server = smtplib.SMTP_SSL(email_svc.smtp_host, email_svc.smtp_port)
            else:
                server = smtplib.SMTP(email_svc.smtp_host, email_svc.smtp_port)
                server.starttls()

            server.login(email_svc.smtp_user, email_svc.smtp_pass)
            server.sendmail(email_svc.smtp_sender, destinatarios, msg.as_string())
            server.quit()

            destinatarios_str = (
                ", ".join(destinatarios) if len(destinatarios) > 1 else destinatarios[0]
            )
            return f"✅ Email enviado correctamente a: {destinatarios_str}"

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return f"Error al enviar el email: {str(e)}"

    except Exception as e:
        logger.error(f"_enviar_email_chat error: {e}", exc_info=True)
        return f"Error al generar el email: {str(e)}"
