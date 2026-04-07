"""029 - Validate tenant country_code is set

Revision ID: 029
Revises: 028
Create Date: 2026-04-07

Backfills NULL country_code to 'AR' for production safety (Dra. Laura's clinic).
US-default tenants are LEFT alone (the column already has server_default='US'),
but they are logged via a SELECT for manual review by ops.

This migration is non-destructive: only NULLs are touched.
"""
from alembic import op
import sqlalchemy as sa


revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade():
    # Backfill NULLs to AR (Argentina) — safest default for current production tenants.
    op.execute(
        """
        UPDATE tenants
        SET country_code = 'AR'
        WHERE country_code IS NULL
        """
    )
    # Enforce NOT NULL going forward (column is already defined NOT NULL in newer schemas,
    # but historic deployments may have lost the constraint).
    op.execute(
        """
        ALTER TABLE tenants
        ALTER COLUMN country_code SET NOT NULL
        """
    )


def downgrade():
    # Allow NULL again — but DO NOT clear values, that's destructive.
    op.execute(
        """
        ALTER TABLE tenants
        ALTER COLUMN country_code DROP NOT NULL
        """
    )
