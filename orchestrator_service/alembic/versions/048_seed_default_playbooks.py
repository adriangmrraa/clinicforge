"""
048: Seed default playbooks for all tenants.

Migrates existing automation_rules to automation_playbooks with steps,
and creates 9 pre-built playbooks (inactive by default, CEO activates from UI).
"""

revision = "048"
down_revision = "047"


def upgrade():
    import json
    from alembic import op
    import sqlalchemy as sa

    conn = op.get_bind()

    # Get all tenants
    tenants = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()

    for (tenant_id,) in tenants:
        # ── Migrate existing automation_rules → playbooks ──

        # 1. Recordatorio 24h
        existing_reminder = conn.execute(sa.text(
            "SELECT id, is_active, free_text_message, message_type, ycloud_template_name, "
            "ycloud_template_vars, send_hour_min, send_hour_max "
            "FROM automation_rules WHERE tenant_id = :tid AND trigger_type = 'appointment_reminder' "
            "ORDER BY is_system DESC LIMIT 1"
        ), {"tid": tenant_id}).fetchone()

        # Indices: 0=id, 1=is_active, 2=free_text_message, 3=message_type,
        #          4=ycloud_template_name, 5=ycloud_template_vars, 6=send_hour_min, 7=send_hour_max
        pb_reminder = conn.execute(sa.text("""
            INSERT INTO automation_playbooks
            (tenant_id, name, description, icon, category, trigger_type, trigger_config,
             conditions, is_active, is_system, max_messages_per_day, schedule_hour_min, schedule_hour_max)
            VALUES (:tid, 'Escudo Anti-Ausencias',
                    'Le recuerda al paciente su turno 24hs antes y le da opciones para confirmar o reprogramar',
                    '🛡️', 'retention', 'appointment_reminder',
                    '{"hours_before": 24}', '{}',
                    :active, true, 2,
                    :hmin, :hmax)
            RETURNING id
        """), {
            "tid": tenant_id,
            "active": existing_reminder[1] if existing_reminder else False,
            "hmin": int(existing_reminder[6]) if existing_reminder and existing_reminder[6] is not None else 9,
            "hmax": int(existing_reminder[7]) if existing_reminder and existing_reminder[7] is not None else 20,
        }).fetchone()

        if pb_reminder:
            pb_id = pb_reminder[0]
            # Step 0: Send reminder (HSM or text based on existing config)
            if existing_reminder and existing_reminder[3] == 'hsm' and existing_reminder[4]:
                conn.execute(sa.text("""
                    INSERT INTO automation_steps
                    (playbook_id, step_order, step_label, action_type, delay_minutes,
                     template_name, template_lang, template_vars)
                    VALUES (:pid, 0, 'Recordatorio con botones', 'send_template', 0,
                            :tname, 'es', :tvars)
                """), {
                    "pid": pb_id,
                    "tname": existing_reminder[4],
                    "tvars": json.dumps(existing_reminder[5] or {}),
                })
            else:
                msg = (existing_reminder[2] if existing_reminder and existing_reminder[2]
                       else "Hola {{nombre_paciente}}, te recordamos tu turno de mañana a las {{hora_turno}}. ¿Nos confirmás tu asistencia?")
                conn.execute(sa.text("""
                    INSERT INTO automation_steps
                    (playbook_id, step_order, step_label, action_type, delay_minutes, message_text)
                    VALUES (:pid, 0, 'Recordatorio', 'send_text', 0, :msg)
                """), {"pid": pb_id, "msg": msg})

            # Step 1: Wait response 2h
            conn.execute(sa.text("""
                INSERT INTO automation_steps
                (playbook_id, step_order, step_label, action_type, delay_minutes,
                 wait_timeout_minutes, on_no_response, response_rules)
                VALUES (:pid, 1, 'Esperar confirmación', 'wait_response', 0, 120, 'continue',
                        :rules)
            """), {
                "pid": pb_id,
                "rules": json.dumps([
                    {"name": "confirmado", "keywords": ["confirmo", "confirmar", "sí", "si", "dale", "ok", "voy"], "action": "continue"},
                    {"name": "cancelar", "keywords": ["no puedo", "cancelar", "cancelo", "no voy"], "action": "abort"},
                    {"name": "reprogramar", "keywords": ["reprogramar", "cambiar", "otro día", "otro dia", "otro horario"], "action": "pass_to_ai"},
                ]),
            })

        # 2. Feedback Pacientes → Protocolo Post-Atención
        existing_feedback = conn.execute(sa.text(
            "SELECT id, is_active, free_text_message, send_hour_min, send_hour_max "
            "FROM automation_rules WHERE tenant_id = :tid AND trigger_type = 'post_appointment_completed' "
            "ORDER BY is_system DESC LIMIT 1"
        ), {"tid": tenant_id}).fetchone()

        pb_feedback = conn.execute(sa.text("""
            INSERT INTO automation_playbooks
            (tenant_id, name, description, icon, category, trigger_type, trigger_config,
             conditions, is_active, is_system, max_messages_per_day, schedule_hour_min, schedule_hour_max)
            VALUES (:tid, 'Seguimiento Post-Atención',
                    'Después del turno, le pregunta al paciente cómo se siente y envía instrucciones de cuidado',
                    '🩺', 'clinical', 'appointment_completed',
                    '{}', '{}',
                    :active, true, 2,
                    :hmin, :hmax)
            RETURNING id
        """), {
            "tid": tenant_id,
            "active": existing_feedback[1] if existing_feedback else False,
            "hmin": existing_feedback[3] if existing_feedback else 9,
            "hmax": existing_feedback[4] if existing_feedback else 20,
        }).fetchone()

        if pb_feedback:
            pb_id = pb_feedback[0]
            msg = (existing_feedback[2] if existing_feedback and existing_feedback[2]
                   else "Hola {{nombre_paciente}}, ¿cómo te sentís después de la atención de hoy? ¿Tuviste alguna molestia o va todo bien?")
            conn.execute(sa.text("""
                INSERT INTO automation_steps
                (playbook_id, step_order, step_label, action_type, delay_minutes, message_text)
                VALUES (:pid, 0, 'Check-in post atención', 'send_text', 180, :msg)
            """), {"pid": pb_id, "msg": msg})

            conn.execute(sa.text("""
                INSERT INTO automation_steps
                (playbook_id, step_order, step_label, action_type, delay_minutes,
                 wait_timeout_minutes, on_no_response, response_rules)
                VALUES (:pid, 1, 'Esperar respuesta', 'wait_response', 0, 1440, 'continue',
                        :rules)
            """), {
                "pid": pb_id,
                "rules": json.dumps([
                    {"name": "urgencia", "keywords": ["dolor", "duele", "sangra", "sangrado", "fiebre", "hinchado", "hinchazón", "inflamado"], "action": "notify_and_pause"},
                    {"name": "positivo", "keywords": ["bien", "perfecto", "genial", "todo ok", "sin problemas", "tranquilo", "bárbaro"], "action": "continue"},
                ]),
            })

        # 3. Recuperación de Leads
        existing_leads = conn.execute(sa.text(
            "SELECT id, is_active, condition_json, send_hour_min, send_hour_max "
            "FROM automation_rules WHERE tenant_id = :tid AND trigger_type = 'lead_meta_no_booking' "
            "ORDER BY is_system DESC LIMIT 1"
        ), {"tid": tenant_id}).fetchone()

        pb_leads = conn.execute(sa.text("""
            INSERT INTO automation_playbooks
            (tenant_id, name, description, icon, category, trigger_type, trigger_config,
             conditions, is_active, is_system, max_messages_per_day, schedule_hour_min, schedule_hour_max)
            VALUES (:tid, 'Recuperador de Leads',
                    'Si un lead escribió pero no agendó en 2 horas, le envía un seguimiento personalizado',
                    '🎯', 'revenue', 'lead_no_booking',
                    '{"hours_without_booking": 2}', '{}',
                    :active, true, 2,
                    :hmin, :hmax)
            RETURNING id
        """), {
            "tid": tenant_id,
            "active": existing_leads[1] if existing_leads else False,
            "hmin": existing_leads[3] if existing_leads else 9,
            "hmax": existing_leads[4] if existing_leads else 20,
        }).fetchone()

        if pb_leads:
            pb_id = pb_leads[0]
            conn.execute(sa.text("""
                INSERT INTO automation_steps
                (playbook_id, step_order, step_label, action_type, delay_minutes, message_text)
                VALUES (:pid, 0, 'Primer seguimiento', 'send_text', 120,
                        'Hola {{nombre_paciente}}, te escribimos porque notamos que estabas interesado/a en agendar un turno. ¿Querés que te ayudemos a coordinar? 😊')
            """), {"pid": pb_id})

            conn.execute(sa.text("""
                INSERT INTO automation_steps
                (playbook_id, step_order, step_label, action_type, delay_minutes,
                 wait_timeout_minutes, on_no_response)
                VALUES (:pid, 1, 'Esperar respuesta', 'wait_response', 0, 480, 'continue')
            """), {"pid": pb_id})

            conn.execute(sa.text("""
                INSERT INTO automation_steps
                (playbook_id, step_order, step_label, action_type, delay_minutes, message_text)
                VALUES (:pid, 2, 'Segundo contacto', 'send_text', 480,
                        'Hola de nuevo 😊 Solo quería asegurarme de que no se te pasó. Si necesitás un turno, estoy para ayudarte. ¡Que tengas un gran día!')
            """), {"pid": pb_id})

        # ── Seed additional pre-built playbooks (inactive) ──

        # 4. Motor de Reseñas Google
        pb_id = conn.execute(sa.text("""
            INSERT INTO automation_playbooks
            (tenant_id, name, description, icon, category, trigger_type, trigger_config,
             conditions, is_active, is_system, max_messages_per_day)
            VALUES (:tid, 'Motor de Reseñas Google',
                    'Después de completar un tratamiento de alto valor, le pide al paciente que deje una reseña en Google',
                    '⭐', 'reputation', 'appointment_completed',
                    '{"days_after": 7}',
                    '{"treatments": ["implante_*", "cirugia_*", "estetica_*", "endolifting", "rehabilitacion_*"]}',
                    false, true, 1)
            RETURNING id
        """), {"tid": tenant_id}).fetchone()[0]

        conn.execute(sa.text("""
            INSERT INTO automation_steps
            (playbook_id, step_order, step_label, action_type, delay_minutes, message_text)
            VALUES (:pid, 0, 'Pedir reseña', 'send_text', 10080,
                    'Hola {{nombre_paciente}} 😊 ¿Cómo estás? Quería agradecerte por la confianza que depositaste en la Dra. para tu {{tratamiento}}. Tu experiencia puede ayudar a otros pacientes que están en una situación similar. Si te sentís cómodo/a, te agradecería mucho una reseña 🤍')
        """), {"pid": pb_id})

        # 5. Recuperador de No-Shows
        pb_id = conn.execute(sa.text("""
            INSERT INTO automation_playbooks
            (tenant_id, name, description, icon, category, trigger_type, trigger_config,
             conditions, is_active, is_system, max_messages_per_day)
            VALUES (:tid, 'Recuperador de No-Shows',
                    'Si el paciente no vino al turno, le escribe para saber si está bien y ofrece reprogramar',
                    '❌', 'recovery', 'no_show',
                    '{}', '{}',
                    false, true, 2)
            RETURNING id
        """), {"tid": tenant_id}).fetchone()[0]

        conn.execute(sa.text("""
            INSERT INTO automation_steps
            (playbook_id, step_order, step_label, action_type, delay_minutes, message_text)
            VALUES (:pid, 0, 'Contacto inmediato', 'send_text', 30,
                    'Hola {{nombre_paciente}}, notamos que no pudiste asistir a tu turno de hoy. Esperamos que esté todo bien 😊 Si querés, podemos reprogramar para otro día que te quede mejor.')
        """), {"pid": pb_id})

        conn.execute(sa.text("""
            INSERT INTO automation_steps
            (playbook_id, step_order, step_label, action_type, delay_minutes,
             wait_timeout_minutes, on_no_response)
            VALUES (:pid, 1, 'Esperar respuesta', 'wait_response', 0, 1440, 'continue')
        """), {"pid": pb_id})

        conn.execute(sa.text("""
            INSERT INTO automation_steps
            (playbook_id, step_order, step_label, action_type, delay_minutes, message_text,
             on_no_response)
            VALUES (:pid, 2, 'Último intento', 'send_text', 1440,
                    'Hola {{nombre_paciente}}, te escribimos por última vez para ver si querés reagendar tu turno. Estamos para ayudarte cuando lo necesites 😊',
                    'abort')
        """), {"pid": pb_id})

        # 6. Protocolo Post-Quirúrgico
        pb_id = conn.execute(sa.text("""
            INSERT INTO automation_playbooks
            (tenant_id, name, description, icon, category, trigger_type, trigger_config,
             conditions, is_active, is_system, max_messages_per_day)
            VALUES (:tid, 'Protocolo Post-Quirúrgico',
                    'Después de una cirugía o implante, envía instrucciones de cuidado y hace seguimiento del dolor',
                    '🔪', 'clinical', 'appointment_completed',
                    '{}',
                    '{"treatments": ["cirugia_*", "implante_*", "injerto_regeneracion_osea"]}',
                    false, true, 2)
            RETURNING id
        """), {"tid": tenant_id}).fetchone()[0]

        conn.execute(sa.text("""
            INSERT INTO automation_steps
            (playbook_id, step_order, step_label, action_type, delay_minutes, instruction_source)
            VALUES (:pid, 0, 'Enviar instrucciones post-op', 'send_instructions', 180, 'from_treatment')
        """), {"pid": pb_id})

        conn.execute(sa.text("""
            INSERT INTO automation_steps
            (playbook_id, step_order, step_label, action_type, delay_minutes, message_text)
            VALUES (:pid, 1, 'Check-in 24h', 'send_text', 1440,
                    'Hola {{nombre_paciente}}, ¿cómo te sentís después de la intervención? ¿Tuviste alguna molestia o va todo bien? 😊')
        """), {"pid": pb_id})

        conn.execute(sa.text("""
            INSERT INTO automation_steps
            (playbook_id, step_order, step_label, action_type, delay_minutes,
             wait_timeout_minutes, on_no_response, response_rules)
            VALUES (:pid, 2, 'Esperar respuesta', 'wait_response', 0, 1440, 'notify_team',
                    :rules)
        """), {
            "pid": pb_id,
            "rules": json.dumps([
                {"name": "urgencia", "keywords": ["dolor", "duele", "sangra", "sangrado", "fiebre", "hinchado", "hinchazón", "pus", "inflamado", "infeccion", "infectado"], "action": "notify_and_pause"},
                {"name": "positivo", "keywords": ["bien", "perfecto", "genial", "todo ok", "sin problemas", "bárbaro", "mejorando"], "action": "continue"},
            ]),
        })

        # 7. Reactivador de Pacientes
        pb_id = conn.execute(sa.text("""
            INSERT INTO automation_playbooks
            (tenant_id, name, description, icon, category, trigger_type, trigger_config,
             conditions, is_active, is_system, max_messages_per_day)
            VALUES (:tid, 'Reactivador de Pacientes',
                    'Contacta pacientes que no vienen hace más de 90 días para invitarlos a un control',
                    '💤', 'retention', 'patient_inactive',
                    '{"inactive_days": 90}', '{}',
                    false, true, 1)
            RETURNING id
        """), {"tid": tenant_id}).fetchone()[0]

        conn.execute(sa.text("""
            INSERT INTO automation_steps
            (playbook_id, step_order, step_label, action_type, delay_minutes, message_text)
            VALUES (:pid, 0, 'Mensaje de reactivación', 'send_text', 0,
                    'Hola {{nombre_paciente}} 😊 ¡Hace tiempo que no nos vemos! Te escribimos porque recomendamos hacer un control periódico para cuidar tu salud bucal. Si querés, te ayudamos a coordinar un turno.')
        """), {"pid": pb_id})

        conn.execute(sa.text("""
            INSERT INTO automation_steps
            (playbook_id, step_order, step_label, action_type, delay_minutes,
             wait_timeout_minutes, on_no_response)
            VALUES (:pid, 1, 'Esperar respuesta', 'wait_response', 0, 2880, 'continue')
        """), {"pid": pb_id})

        conn.execute(sa.text("""
            INSERT INTO automation_steps
            (playbook_id, step_order, step_label, action_type, delay_minutes, message_text,
             on_no_response)
            VALUES (:pid, 2, 'Segundo contacto', 'send_text', 43200,
                    'Hola {{nombre_paciente}}, solo queríamos recordarte que estamos disponibles para cuando necesites un control. ¡Tu sonrisa nos importa! 🦷',
                    'abort')
        """), {"pid": pb_id})

        # 8. Cobrador de Seña
        pb_id = conn.execute(sa.text("""
            INSERT INTO automation_playbooks
            (tenant_id, name, description, icon, category, trigger_type, trigger_config,
             conditions, is_active, is_system, max_messages_per_day)
            VALUES (:tid, 'Recordatorio de Pago',
                    'Antes del turno, le recuerda al paciente si tiene un saldo pendiente de seña',
                    '💰', 'revenue', 'appointment_created',
                    '{"hours_before_appointment": 24}',
                    '{"payment_status": "pending"}',
                    false, true, 1)
            RETURNING id
        """), {"tid": tenant_id}).fetchone()[0]

        conn.execute(sa.text("""
            INSERT INTO automation_steps
            (playbook_id, step_order, step_label, action_type, delay_minutes, message_text)
            VALUES (:pid, 0, 'Recordatorio de seña', 'send_text', 0,
                    'Hola {{nombre_paciente}} 😊 Te recordamos que tenés un saldo pendiente de {{saldo_pendiente}} para tu turno del {{dia_semana}} {{fecha_turno}} a las {{hora_turno}}. Podés transferir al CBU/alias de la clínica y enviarnos el comprobante por acá.')
        """), {"pid": pb_id})

        # 9. Segundo Aviso (linked to reminder)
        pb_id = conn.execute(sa.text("""
            INSERT INTO automation_playbooks
            (tenant_id, name, description, icon, category, trigger_type, trigger_config,
             conditions, is_active, is_system, max_messages_per_day)
            VALUES (:tid, 'Segundo Aviso de Turno',
                    'Si el paciente no confirmó el recordatorio en 2 horas, envía un segundo aviso más directo',
                    '⏰', 'retention', 'appointment_reminder',
                    '{"hours_before": 4}', '{}',
                    false, true, 2)
            RETURNING id
        """), {"tid": tenant_id}).fetchone()[0]

        conn.execute(sa.text("""
            INSERT INTO automation_steps
            (playbook_id, step_order, step_label, action_type, delay_minutes, message_text)
            VALUES (:pid, 0, 'Segundo aviso', 'send_text', 0,
                    'Hola {{nombre_paciente}}, seguimos a la espera de tu confirmación para el turno de mañana. De no recibir respuesta en la próxima hora, lamentablemente deberemos liberar el espacio para otro paciente. ¡Gracias!')
        """), {"pid": pb_id})


def downgrade():
    from alembic import op
    import sqlalchemy as sa

    conn = op.get_bind()
    # Delete all system playbooks (user-created ones remain)
    conn.execute(sa.text("DELETE FROM automation_playbooks WHERE is_system = true"))
