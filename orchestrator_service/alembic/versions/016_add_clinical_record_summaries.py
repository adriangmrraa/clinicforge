"""add clinical_record_summaries table for storing attachment summaries

Revision ID: 016
Revises: 015
Create Date: 2026-04-02

Stores AI-generated summaries of clinical record attachments (images, PDFs) sent via WhatsApp.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB


revision = "u3v4w5x6y7z8"
down_revision = "t2u3v4w5x6y7"
branch_labels = None
depends_on = None


def _table_exists(conn, table):
    """Check if a table exists in the database."""
    try:
        result = conn.execute(
            text(
                f"SELECT 1 FROM information_schema.tables WHERE table_name = '{table}'"
            )
        )
        return result.fetchone() is not None
    except Exception:
        return False


def upgrade():
    conn = op.get_bind()

    if not _table_exists(conn, "clinical_record_summaries"):
        op.create_table(
            "clinical_record_summaries",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "patient_id",
                sa.Integer(),
                sa.ForeignKey("patients.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("conversation_id", sa.String(100), nullable=True),
            sa.Column("summary_text", sa.Text(), nullable=False),
            sa.Column(
                "attachments_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "attachments_types", JSONB(), nullable=False, server_default="[]"
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "tenant_id",
                "patient_id",
                "conversation_id",
                name="uq_summaries_tenant_patient_conversation",
            ),
        )
        op.create_index(
            "idx_summaries_tenant_patient",
            "clinical_record_summaries",
            ["tenant_id", "patient_id"],
        )
        print("✅ Created clinical_record_summaries table with indexes")


def downgrade():
    try:
        op.drop_index(
            "idx_summaries_tenant_patient", table_name="clinical_record_summaries"
        )
    except Exception:
        pass
    try:
        op.drop_table("clinical_record_summaries")
    except Exception:
        pass
    print("✅ Dropped clinical_record_summaries table")
