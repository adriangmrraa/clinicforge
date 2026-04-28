"""Add partial unique index to prevent clinical record duplication.

Revision ID: 059
Revises: 058
"""
from alembic import op

revision = '059'
down_revision = '058'


def upgrade():
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_clinical_records_dedup
        ON clinical_records (
            tenant_id,
            patient_id,
            diagnosis,
            DATE(record_date AT TIME ZONE 'UTC')
        )
        WHERE diagnosis IS NOT NULL
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_clinical_records_dedup")
