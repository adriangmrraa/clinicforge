"""Add missing columns to treatment_types: ai_response_template, patient_display_name

These columns existed in models.py but were never created via migration.
ai_response_template: doctor's curated response when patient asks about a treatment
patient_display_name: patient-facing name (different from internal name)

Revision ID: 045_treatment_missing_cols
Revises: 044_whatsapp_messages
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa

revision = "045_treatment_missing_cols"
down_revision = "044_whatsapp_messages"
branch_labels = None
depends_on = None


def upgrade():
    # ai_response_template: text the AI uses when patient asks about this treatment
    op.add_column(
        "treatment_types",
        sa.Column("ai_response_template", sa.Text(), nullable=True),
    )
    # patient_display_name: patient-facing name (e.g. "Evaluación de Implantes" vs "Implante Dental")
    op.add_column(
        "treatment_types",
        sa.Column("patient_display_name", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("treatment_types", "patient_display_name")
    op.drop_column("treatment_types", "ai_response_template")
