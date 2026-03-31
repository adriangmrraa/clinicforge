"""add priority to treatment_types and is_priority_professional to professionals

Revision ID: 011
Revises: 010
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = 'p1q2r3s4t5u6'
down_revision = 'j0k1l2m3n4o5'
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


def upgrade():
    conn = op.get_bind()

    # 1. Add priority to treatment_types
    if not _column_exists(conn, 'treatment_types', 'priority'):
        op.add_column('treatment_types', sa.Column(
            'priority', sa.String(20), nullable=False, server_default='medium'
        ))
        op.create_check_constraint(
            'ck_treatment_types_priority',
            'treatment_types',
            "priority IN ('high', 'medium-high', 'medium', 'low')"
        )

    # 2. Add is_priority_professional to professionals
    if not _column_exists(conn, 'professionals', 'is_priority_professional'):
        op.add_column('professionals', sa.Column(
            'is_priority_professional', sa.Boolean(), nullable=False, server_default='false'
        ))


def downgrade():
    try:
        op.drop_constraint('ck_treatment_types_priority', 'treatment_types', type_='check')
    except Exception:
        pass
    try:
        op.drop_column('treatment_types', 'priority')
    except Exception:
        pass
    try:
        op.drop_column('professionals', 'is_priority_professional')
    except Exception:
        pass
