"""Add social IG/FB fields to tenants.

Revision ID: 040_add_social_ig_fields
Revises: 039
Create Date: 2026-04-09

Adds 4 columns to `tenants` for the Instagram/Facebook Social Agent feature:
  - social_ig_active  BOOLEAN NOT NULL DEFAULT false — master toggle per tenant
  - social_landings   JSONB NULL             — dict of landing-page URLs keyed by CTA group
  - instagram_handle  VARCHAR(100) NULL      — "@handle" shown in preamble identity block
  - facebook_page_id  VARCHAR(100) NULL      — page name / id for FB Messenger channel

Confirmed head before writing: 039_add_tenant_support_complaints
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "040_add_social_ig_fields"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tenants",
        sa.Column(
            "social_ig_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "social_landings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("instagram_handle", sa.String(100), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("facebook_page_id", sa.String(100), nullable=True),
    )


def downgrade():
    op.drop_column("tenants", "facebook_page_id")
    op.drop_column("tenants", "instagram_handle")
    op.drop_column("tenants", "social_landings")
    op.drop_column("tenants", "social_ig_active")
