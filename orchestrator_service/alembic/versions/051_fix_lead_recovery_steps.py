"""
051: Fix Recuperador de Leads playbook steps.

Migration 049 incorrectly forced HSM on step 0 of lead_no_booking playbooks,
but lead_no_booking is REACTIVE (patient messaged first), so the 24h window
is open and send_ai_message is valid for step 0.

Also fixes step 2 timing: 720 min (12h) instead of 480 min (8h) for the
second follow-up, giving more time between contacts.
"""

revision = "051"
down_revision = "050"


def upgrade():
    import sqlalchemy as sa
    from alembic import op

    conn = op.get_bind()

    # Get all tenants
    tenants = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()

    for (tenant_id,) in tenants:
        # Find the "Recuperador de Leads" playbook (lead_no_booking trigger)
        pb = conn.execute(sa.text("""
            SELECT id FROM automation_playbooks
            WHERE tenant_id = :tid AND trigger_type = 'lead_no_booking'
            AND is_system = true
            LIMIT 1
        """), {"tid": tenant_id}).fetchone()

        if not pb:
            continue

        pb_id = pb[0]

        # Step 0: Revert from send_template back to send_ai_message
        # The AI will check conversation history, decide if follow-up is needed,
        # and generate a personalized message (or skip if not appropriate).
        conn.execute(sa.text("""
            UPDATE automation_steps SET
                action_type = 'send_ai_message',
                template_name = NULL,
                template_lang = NULL,
                template_vars = NULL,
                message_text = 'Revisá la conversación anterior con este paciente. Si mostró interés en un tratamiento o turno pero no agendó, enviá un seguimiento breve, cálido y personalizado basado en lo que habló. Si ya agendó o no corresponde seguimiento, respondé NO_ENVIAR.',
                step_label = 'Seguimiento IA'
            WHERE playbook_id = :pid AND step_order = 0
        """), {"pid": pb_id})

        # Step 2: Set delay to 720 min (12h from step 1 completion)
        # and ensure it's send_text (within 24h window)
        conn.execute(sa.text("""
            UPDATE automation_steps SET
                action_type = 'send_text',
                delay_minutes = 720,
                step_label = 'Segundo contacto'
            WHERE playbook_id = :pid AND step_order = 2
        """), {"pid": pb_id})


def downgrade():
    import sqlalchemy as sa
    from alembic import op

    conn = op.get_bind()
    tenants = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()

    for (tenant_id,) in tenants:
        pb = conn.execute(sa.text("""
            SELECT id FROM automation_playbooks
            WHERE tenant_id = :tid AND trigger_type = 'lead_no_booking'
            AND is_system = true LIMIT 1
        """), {"tid": tenant_id}).fetchone()

        if not pb:
            continue

        conn.execute(sa.text("""
            UPDATE automation_steps SET
                action_type = 'send_template',
                message_text = NULL,
                step_label = 'Primer seguimiento'
            WHERE playbook_id = :pid AND step_order = 0
        """), {"pid": pb[0]})

        conn.execute(sa.text("""
            UPDATE automation_steps SET
                delay_minutes = 480
            WHERE playbook_id = :pid AND step_order = 2
        """), {"pid": pb[0]})
