"""add custom_hours_start and custom_hours_end to tenant_holidays

Revision ID: 014
Revises: 013
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = 'a1b2c3d4e5f7'
down_revision = 'r3s4t5u6v7w8'
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    try:
        result = conn.execute(text(
            "SELECT 1 FROM information_schema.columns "
            f"WHERE table_name = '{table}' AND column_name = '{column}'"
        ))
        return result.fetchone() is not None
    except Exception:
        return False


def upgrade():
    conn = op.get_bind()

    if not _column_exists(conn, 'tenant_holidays', 'custom_hours_start'):
        op.add_column(
            'tenant_holidays',
            sa.Column('custom_hours_start', sa.Time(), nullable=True)
        )

    if not _column_exists(conn, 'tenant_holidays', 'custom_hours_end'):
        op.add_column(
            'tenant_holidays',
            sa.Column('custom_hours_end', sa.Time(), nullable=True)
        )


def downgrade():
    try:
        op.drop_column('tenant_holidays', 'custom_hours_end')
    except Exception:
        pass
    try:
        op.drop_column('tenant_holidays', 'custom_hours_start')
    except Exception:
        pass
