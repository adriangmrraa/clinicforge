"""073 — Laboratorio L2: sellos de aviso al paciente y reclamo al lab

patient_notified_at: cuándo se le avisó por WhatsApp que llegó el trabajo.
lab_chased_at: cuándo se le reclamó por email al laboratorio un vencido.

Revision ID: 073
Revises: 072
"""

from alembic import op
import sqlalchemy as sa

revision = "073"
down_revision = "072"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "lab_cases",
        sa.Column("patient_notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "lab_cases",
        sa.Column("lab_chased_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("lab_cases", "lab_chased_at")
    op.drop_column("lab_cases", "patient_notified_at")
