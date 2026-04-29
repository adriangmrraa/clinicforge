"""Add partial unique index to prevent clinical record duplication.

Revision ID: 059
Revises: 058
"""
from alembic import op

revision = '059'
down_revision = '058'


def upgrade():
    # Step 1: Remove existing duplicates, keeping the newest record (highest id)
    op.execute("""
        DELETE FROM clinical_records
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM clinical_records
            WHERE diagnosis IS NOT NULL
            GROUP BY tenant_id, patient_id, diagnosis, CAST(record_date AS date)
        )
        AND diagnosis IS NOT NULL
    """)
    # Step 2: Create unique index to prevent future duplicates
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_clinical_records_dedup
        ON clinical_records (
            tenant_id,
            patient_id,
            diagnosis,
            CAST(record_date AS date)
        )
        WHERE diagnosis IS NOT NULL
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_clinical_records_dedup")
