"""Add missing columns to treatment_types: ai_response_template, patient_display_name

These columns existed in models.py but were never created via migration.
ai_response_template: doctor's curated response when patient asks about a treatment
patient_display_name: patient-facing name (may already exist from a prior manual migration)

Revision ID: 045_treatment_missing_cols
Revises: 044_whatsapp_messages
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "045_treatment_missing_cols"
down_revision = "044_whatsapp_messages"
branch_labels = None
depends_on = None


def _column_exists(table, column):
    """Check if a column already exists in the table."""
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [c["name"] for c in insp.get_columns(table)]
    return column in columns


def upgrade():
    if not _column_exists("treatment_types", "ai_response_template"):
        op.add_column(
            "treatment_types",
            sa.Column("ai_response_template", sa.Text(), nullable=True),
        )

    if not _column_exists("treatment_types", "patient_display_name"):
        op.add_column(
            "treatment_types",
            sa.Column("patient_display_name", sa.Text(), nullable=True),
        )


def downgrade():
    if _column_exists("treatment_types", "patient_display_name"):
        op.drop_column("treatment_types", "patient_display_name")
    if _column_exists("treatment_types", "ai_response_template"):
        op.drop_column("treatment_types", "ai_response_template")
