"""046 - Add external_ids JSONB column to patients table

Revision ID: 046
Revises: 045_treatment_missing_cols
Create Date: 2026-04-11

Adds external_ids column to patients table for storing external
contact IDs (Instagram, Facebook, ChatWot, etc.)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect


revision = "046"
down_revision = "045_treatment_missing_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("patients")]
    if "external_ids" not in columns:
        op.add_column(
            "patients",
            sa.Column(
                "external_ids",
                sa.JSON(),
                nullable=True,
                server_default=text("'{}'::jsonb"),
            ),
        )


def downgrade() -> None:
    op.drop_column("patients", "external_ids")
