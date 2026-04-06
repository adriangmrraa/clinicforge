"""024 - Add assigned_professional_id to patients

Revision ID: 024
Revises: 023
Create Date: 2026-04-06

Adds assigned_professional_id column to patients table for persistent
patient-professional assignment. Allows bulk assignment of patients to
their habitual professional, so the AI agent auto-routes them.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers
revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Add assigned_professional_id column (nullable, FK to professionals)
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'patients' AND column_name = 'assigned_professional_id'
        )
    """))
    if not result.scalar():
        op.add_column(
            "patients",
            sa.Column(
                "assigned_professional_id",
                sa.Integer(),
                sa.ForeignKey("professionals.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    # Partial index for efficient lookups (only assigned patients)
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_patients_assigned_professional
        ON patients (tenant_id, assigned_professional_id)
        WHERE assigned_professional_id IS NOT NULL
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("DROP INDEX IF EXISTS idx_patients_assigned_professional"))
    op.drop_column("patients", "assigned_professional_id")
