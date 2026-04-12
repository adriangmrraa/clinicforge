"""
047: Automation Playbooks Engine V2

New tables:
- automation_playbooks: Playbook definitions (multi-step sequences)
- automation_steps: Ordered steps within playbooks
- automation_executions: Per-patient execution state tracking
- automation_events: Granular event log for analytics

Additions:
- patients.last_automation_message_at: Global cooldown tracking
- treatment_types.post_treatment_hsm_template: YCloud template per treatment
"""

revision = "047"
down_revision = "046"


def upgrade():
    from alembic import op
    import sqlalchemy as sa
    from sqlalchemy.dialects.postgresql import JSONB

    # --- automation_playbooks ---
    op.create_table(
        "automation_playbooks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        # Identity
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("icon", sa.Text, server_default="📋"),
        sa.Column("category", sa.Text, nullable=False, server_default="custom"),
        # Trigger
        sa.Column("trigger_type", sa.Text, nullable=False),
        sa.Column("trigger_config", JSONB, nullable=False, server_default="{}"),
        # Conditions
        sa.Column("conditions", JSONB, nullable=False, server_default="{}"),
        # Execution control
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("max_messages_per_day", sa.Integer, nullable=False, server_default="2"),
        sa.Column("frequency_cap_hours", sa.Integer, server_default="24"),
        sa.Column("schedule_hour_min", sa.Integer, nullable=False, server_default="9"),
        sa.Column("schedule_hour_max", sa.Integer, nullable=False, server_default="20"),
        # Abort conditions
        sa.Column("abort_on_booking", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("abort_on_human", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("abort_on_optout", sa.Boolean, nullable=False, server_default="true"),
        # Stats cache
        sa.Column("stats_cache", JSONB, server_default="{}"),
        # Meta
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_playbooks_tenant_active", "automation_playbooks", ["tenant_id", "is_active"])
    op.create_index("idx_playbooks_trigger", "automation_playbooks", ["trigger_type"])

    # --- automation_steps ---
    op.create_table(
        "automation_steps",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("playbook_id", sa.Integer, sa.ForeignKey("automation_playbooks.id", ondelete="CASCADE"), nullable=False),
        # Ordering
        sa.Column("step_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("step_label", sa.Text),
        # Action
        sa.Column("action_type", sa.Text, nullable=False),
        # Timing
        sa.Column("delay_minutes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("schedule_hour_min", sa.Integer),
        sa.Column("schedule_hour_max", sa.Integer),
        # Content: send_template
        sa.Column("template_name", sa.Text),
        sa.Column("template_lang", sa.Text, server_default="es"),
        sa.Column("template_vars", JSONB, server_default="{}"),
        # Content: send_text
        sa.Column("message_text", sa.Text),
        # Content: send_instructions
        sa.Column("instruction_source", sa.Text, server_default="from_treatment"),
        sa.Column("custom_instructions", sa.Text),
        # Content: notify_team
        sa.Column("notify_channel", sa.Text, server_default="telegram"),
        sa.Column("notify_message", sa.Text),
        # Content: update_status
        sa.Column("update_field", sa.Text),
        sa.Column("update_value", sa.Text),
        # Response handling
        sa.Column("wait_timeout_minutes", sa.Integer, server_default="120"),
        sa.Column("response_rules", JSONB, server_default="[]"),
        sa.Column("on_no_response", sa.Text, server_default="continue"),
        sa.Column("on_unclassified", sa.Text, server_default="pass_to_ai"),
        # Branching
        sa.Column("on_response_next_step", sa.Integer),
        sa.Column("on_no_response_next_step", sa.Integer),
        # Meta
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_steps_playbook", "automation_steps", ["playbook_id", "step_order"])

    # --- automation_executions ---
    op.create_table(
        "automation_executions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("playbook_id", sa.Integer, sa.ForeignKey("automation_playbooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        # Target
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id", ondelete="SET NULL")),
        sa.Column("phone_number", sa.Text, nullable=False),
        sa.Column("appointment_id", sa.Text),  # UUID stored as text for FK flexibility
        # State
        sa.Column("current_step_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.Text, nullable=False, server_default="running"),
        sa.Column("pause_reason", sa.Text),
        # Timing
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("next_step_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        # Tracking
        sa.Column("messages_sent", sa.Integer, nullable=False, server_default="0"),
        sa.Column("messages_sent_today", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
        sa.Column("last_response_at", sa.DateTime(timezone=True)),
        # Context
        sa.Column("context", JSONB, server_default="{}"),
        # Meta
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_executions_pending", "automation_executions",
        ["next_step_at"],
        postgresql_where=sa.text("status IN ('running', 'waiting_response')"),
    )
    op.create_index("idx_executions_patient", "automation_executions", ["tenant_id", "phone_number", "status"])
    op.create_index("idx_executions_playbook", "automation_executions", ["playbook_id", "status"])

    # --- automation_events ---
    op.create_table(
        "automation_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("execution_id", sa.Integer, sa.ForeignKey("automation_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.Integer, sa.ForeignKey("automation_steps.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("event_data", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_events_execution", "automation_events", ["execution_id", "created_at"])
    op.create_index("idx_events_type", "automation_events", ["event_type"])

    # --- patients: add cooldown column ---
    op.add_column("patients", sa.Column("last_automation_message_at", sa.DateTime(timezone=True)))

    # --- treatment_types: add post-treatment HSM template ---
    op.add_column("treatment_types", sa.Column("post_treatment_hsm_template", sa.Text))


def downgrade():
    from alembic import op

    op.drop_column("treatment_types", "post_treatment_hsm_template")
    op.drop_column("patients", "last_automation_message_at")
    op.drop_table("automation_events")
    op.drop_table("automation_executions")
    op.drop_table("automation_steps")
    op.drop_table("automation_playbooks")
