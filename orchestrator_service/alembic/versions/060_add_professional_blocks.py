"""Add professional_id and scope to tenant_holidays for per-professional blocks

Revision ID: 060
Revises: 059
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = '060'
down_revision = '059'
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

    # Add professional_id column (nullable FK → professionals)
    if not _column_exists(conn, 'tenant_holidays', 'professional_id'):
        op.add_column(
            'tenant_holidays',
            sa.Column('professional_id', sa.Integer(), nullable=True)
        )
        op.create_foreign_key(
            'fk_tenant_holidays_professional',
            'tenant_holidays', 'professionals',
            ['professional_id'], ['id'],
            ondelete='CASCADE'
        )

    # Add scope column with default 'global'
    if not _column_exists(conn, 'tenant_holidays', 'scope'):
        op.add_column(
            'tenant_holidays',
            sa.Column('scope', sa.String(20),
                      nullable=False, server_default='global')
        )

    # Drop old unique constraint and create new one that includes professional_id
    op.execute("ALTER TABLE tenant_holidays DROP CONSTRAINT IF EXISTS uq_tenant_holidays_tenant_date_type")
    
    # Create new unique constraint: null professional_ids coalesce to 0
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_holidays_tenant_date_type_prof
        ON tenant_holidays (tenant_id, date, holiday_type, COALESCE(professional_id, 0))
    """)

    # Create index for querying blocks by professional
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_tenant_holidays_professional
        ON tenant_holidays (tenant_id, professional_id, date)
        WHERE professional_id IS NOT NULL
    """)


def downgrade():
    try:
        op.drop_index('idx_tenant_holidays_professional')
    except Exception:
        pass
    try:
        op.drop_index('uq_tenant_holidays_tenant_date_type_prof')
    except Exception:
        pass
    try:
        op.drop_constraint('fk_tenant_holidays_professional', 'tenant_holidays', type_='foreignkey')
    except Exception:
        pass
    try:
        op.drop_column('tenant_holidays', 'professional_id')
    except Exception:
        pass
    try:
        op.drop_column('tenant_holidays', 'scope')
    except Exception:
        pass
