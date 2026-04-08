"""039 — Add support/complaints/review config to tenants

Revision ID: 039
Revises: 038
Create Date: 2026-04-08

7 new nullable columns on `tenants` for the support/complaints/review
configuration block. Surfaces existing infrastructure (derivhumano tool,
followup job) to be tenant-configurable so the agent has clinic-specific
escalation paths and review platforms.

Backward compat: all 7 columns nullable (the boolean flag is non-nullable
with server_default false). Existing tenants experience zero behavior
change until they configure these fields from the Clinics UI.

Idempotent via information_schema check.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def _existing_columns(conn) -> set[str]:
    rows = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'tenants'"
        )
    ).fetchall()
    return {r[0] for r in rows}


def upgrade() -> None:
    conn = op.get_bind()
    existing = _existing_columns(conn)

    if "complaint_escalation_email" not in existing:
        op.add_column(
            "tenants",
            sa.Column("complaint_escalation_email", sa.Text(), nullable=True),
        )
    if "complaint_escalation_phone" not in existing:
        op.add_column(
            "tenants",
            sa.Column("complaint_escalation_phone", sa.Text(), nullable=True),
        )
    if "expected_wait_time_minutes" not in existing:
        op.add_column(
            "tenants",
            sa.Column("expected_wait_time_minutes", sa.Integer(), nullable=True),
        )
    if "revision_policy" not in existing:
        op.add_column(
            "tenants",
            sa.Column("revision_policy", sa.Text(), nullable=True),
        )
    if "review_platforms" not in existing:
        op.add_column(
            "tenants",
            sa.Column("review_platforms", JSONB(), nullable=True),
        )
    if "complaint_handling_protocol" not in existing:
        op.add_column(
            "tenants",
            sa.Column("complaint_handling_protocol", JSONB(), nullable=True),
        )
    if "auto_send_review_link_after_followup" not in existing:
        op.add_column(
            "tenants",
            sa.Column(
                "auto_send_review_link_after_followup",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    op.drop_column("tenants", "auto_send_review_link_after_followup")
    op.drop_column("tenants", "complaint_handling_protocol")
    op.drop_column("tenants", "review_platforms")
    op.drop_column("tenants", "revision_policy")
    op.drop_column("tenants", "expected_wait_time_minutes")
    op.drop_column("tenants", "complaint_escalation_phone")
    op.drop_column("tenants", "complaint_escalation_email")
