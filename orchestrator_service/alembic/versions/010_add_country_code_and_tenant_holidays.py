"""add country_code to tenants and tenant_holidays table

Revision ID: 010
Revises: 009
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = 'j0k1l2m3n4o5'
down_revision = 'i9j0k1l2m3n4'
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    try:
        result = conn.execute(text(
            f"SELECT 1 FROM information_schema.columns "
            f"WHERE table_name = '{table}' AND column_name = '{column}'"
        ))
        return result.fetchone() is not None
    except Exception:
        return False


def _table_exists(conn, table_name):
    try:
        result = conn.execute(text(
            f"SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}'"
        ))
        return result.fetchone() is not None
    except Exception:
        return False


def upgrade():
    conn = op.get_bind()

    # 1. Add country_code to tenants
    if not _column_exists(conn, 'tenants', 'country_code'):
        op.add_column('tenants', sa.Column(
            'country_code', sa.String(2), nullable=False, server_default='US'
        ))

    # 2. Create tenant_holidays table
    if not _table_exists(conn, 'tenant_holidays'):
        op.create_table(
            'tenant_holidays',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('name', sa.Text(), nullable=False),
            sa.Column('holiday_type', sa.String(20), nullable=False),
            sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint('tenant_id', 'date', 'holiday_type', name='uq_tenant_holidays_tenant_date_type'),
            sa.CheckConstraint("holiday_type IN ('closure', 'override_open')", name='ck_tenant_holidays_type'),
        )
        op.create_index('idx_tenant_holidays_tenant_date', 'tenant_holidays', ['tenant_id', 'date'])
        op.create_index('idx_tenant_holidays_recurring', 'tenant_holidays', ['tenant_id', 'is_recurring'],
                        postgresql_where=sa.text('is_recurring = true'))


def downgrade():
    try:
        op.drop_table('tenant_holidays')
    except Exception:
        pass
    try:
        op.drop_column('tenants', 'country_code')
    except Exception:
        pass
