"""028 - Appointment audit log table

Revision ID: 028
Revises: 027
Create Date: 2026-04-07

Creates appointment_audit_log table for tracking ALL mutations to appointments
(create / cancel / reschedule / status_changed / payment_updated) with the actor,
source channel, before/after values, and reason. Best-effort logging — never blocks
the underlying mutation.
"""
from alembic import op
import sqlalchemy as sa


revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS appointment_audit_log (
            id BIGSERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            appointment_id UUID NULL REFERENCES appointments(id) ON DELETE SET NULL,
            action VARCHAR(32) NOT NULL,
            actor_type VARCHAR(16) NOT NULL,
            actor_id VARCHAR(128) NULL,
            before_values JSONB NULL,
            after_values JSONB NULL,
            source_channel VARCHAR(32) NULL,
            reason TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_appointment_audit_action CHECK (
                action IN ('created','rescheduled','cancelled','status_changed','payment_updated')
            ),
            CONSTRAINT chk_appointment_audit_actor_type CHECK (
                actor_type IN ('ai_agent','staff_user','patient_self','system')
            ),
            CONSTRAINT chk_appointment_audit_source_channel CHECK (
                source_channel IS NULL OR source_channel IN
                ('whatsapp','instagram','facebook','web_admin','nova_voice','api','system')
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_appointment_audit_tenant_apt_time
        ON appointment_audit_log (tenant_id, appointment_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_appointment_audit_tenant_time
        ON appointment_audit_log (tenant_id, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_appointment_audit_tenant_time")
    op.execute("DROP INDEX IF EXISTS idx_appointment_audit_tenant_apt_time")
    op.execute("DROP TABLE IF EXISTS appointment_audit_log")
