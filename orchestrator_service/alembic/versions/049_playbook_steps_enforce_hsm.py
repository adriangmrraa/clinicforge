"""
049: Update playbook steps to use HSM templates where 24h window requires it.

Steps that initiate contact (outbound triggers) or fire after 24h
must use send_template instead of send_text per WhatsApp policy.
Template name left NULL for CEO to configure from the UI dropdown.
Known templates pre-filled where possible.
"""

revision = "049"
down_revision = "048"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    conn = op.get_bind()

    # Get all tenants
    tenants = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()

    for (tenant_id,) in tenants:

        # 1. Escudo Anti-Ausencias → step 0 must be HSM (Recordatorio de Asistencia)
        conn.execute(sa.text("""
            UPDATE automation_steps SET
                action_type = 'send_template',
                step_label = 'Recordatorio con botones (plantilla HSM)',
                message_text = NULL
            WHERE playbook_id = (
                SELECT id FROM automation_playbooks
                WHERE tenant_id = :tid AND name = 'Escudo Anti-Ausencias' AND is_system = true
                LIMIT 1
            ) AND step_order = 0 AND action_type = 'send_text'
        """), {"tid": tenant_id})

        # 2. Motor de Reseñas Google → step 0 at 7 days, must be HSM
        conn.execute(sa.text("""
            UPDATE automation_steps SET
                action_type = 'send_template',
                step_label = 'Pedir reseña (plantilla HSM)',
                message_text = NULL
            WHERE playbook_id = (
                SELECT id FROM automation_playbooks
                WHERE tenant_id = :tid AND name = 'Motor de Reseñas Google' AND is_system = true
                LIMIT 1
            ) AND step_order = 0 AND action_type = 'send_text'
        """), {"tid": tenant_id})

        # 3. Recuperador de No-Shows → step 0 outbound, must be HSM
        conn.execute(sa.text("""
            UPDATE automation_steps SET
                action_type = 'send_template',
                step_label = 'Contacto inicial (plantilla HSM)',
                message_text = NULL
            WHERE playbook_id = (
                SELECT id FROM automation_playbooks
                WHERE tenant_id = :tid AND name = 'Recuperador de No-Shows' AND is_system = true
                LIMIT 1
            ) AND step_order = 0 AND action_type = 'send_text'
        """), {"tid": tenant_id})

        # 3b. Recuperador de No-Shows → step 2 at +24h, must be HSM too
        conn.execute(sa.text("""
            UPDATE automation_steps SET
                action_type = 'send_template',
                step_label = 'Último intento (plantilla HSM)',
                message_text = NULL
            WHERE playbook_id = (
                SELECT id FROM automation_playbooks
                WHERE tenant_id = :tid AND name = 'Recuperador de No-Shows' AND is_system = true
                LIMIT 1
            ) AND step_order = 2 AND action_type = 'send_text'
        """), {"tid": tenant_id})

        # 4. Reactivador de Pacientes → step 0 outbound 90 days, must be HSM
        conn.execute(sa.text("""
            UPDATE automation_steps SET
                action_type = 'send_template',
                step_label = 'Mensaje de reactivación (plantilla HSM)',
                message_text = NULL
            WHERE playbook_id = (
                SELECT id FROM automation_playbooks
                WHERE tenant_id = :tid AND name = 'Reactivador de Pacientes' AND is_system = true
                LIMIT 1
            ) AND step_order = 0 AND action_type = 'send_text'
        """), {"tid": tenant_id})

        # 4b. Reactivador → step 2 at 30 days later, must be HSM
        conn.execute(sa.text("""
            UPDATE automation_steps SET
                action_type = 'send_template',
                step_label = 'Segundo contacto (plantilla HSM)',
                message_text = NULL
            WHERE playbook_id = (
                SELECT id FROM automation_playbooks
                WHERE tenant_id = :tid AND name = 'Reactivador de Pacientes' AND is_system = true
                LIMIT 1
            ) AND step_order = 2 AND action_type = 'send_text'
        """), {"tid": tenant_id})

        # 5. Recordatorio de Pago → step 0 outbound, must be HSM
        conn.execute(sa.text("""
            UPDATE automation_steps SET
                action_type = 'send_template',
                step_label = 'Recordatorio de seña (plantilla HSM)',
                message_text = NULL
            WHERE playbook_id = (
                SELECT id FROM automation_playbooks
                WHERE tenant_id = :tid AND name = 'Recordatorio de Pago' AND is_system = true
                LIMIT 1
            ) AND step_order = 0 AND action_type = 'send_text'
        """), {"tid": tenant_id})

        # 6. Segundo Aviso → step 0 outbound, must be HSM
        conn.execute(sa.text("""
            UPDATE automation_steps SET
                action_type = 'send_template',
                step_label = 'Segundo aviso (plantilla HSM)',
                message_text = NULL
            WHERE playbook_id = (
                SELECT id FROM automation_playbooks
                WHERE tenant_id = :tid AND name = 'Segundo Aviso de Turno' AND is_system = true
                LIMIT 1
            ) AND step_order = 0 AND action_type = 'send_text'
        """), {"tid": tenant_id})


def downgrade():
    # Not reversible cleanly — the original message_text was lost
    pass
