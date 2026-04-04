"""022 - Add patient_display_name to treatment_types

Revision ID: 022
Revises: 021
Create Date: 2026-04-04

Adds patient_display_name column to treatment_types:
- Allows the AI agent to reference a treatment by a patient-friendly name
  (e.g. "Limpieza dental" instead of the internal code "PROFILAXIS_ADULTO")
- Nullable TEXT — falls back to `name` when NULL
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    """Check if a column exists in the given table."""
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()

    if not _column_exists(conn, "treatment_types", "patient_display_name"):
        op.add_column(
            "treatment_types",
            sa.Column("patient_display_name", sa.Text(), nullable=True),
        )
        print("✅ Added patient_display_name column to treatment_types")
    else:
        print("ℹ️  patient_display_name already exists in treatment_types — skipping")


def downgrade():
    conn = op.get_bind()

    if _column_exists(conn, "treatment_types", "patient_display_name"):
        op.drop_column("treatment_types", "patient_display_name")
        print("✅ Dropped patient_display_name from treatment_types")
    else:
        print("ℹ️  patient_display_name does not exist in treatment_types — skipping downgrade")
