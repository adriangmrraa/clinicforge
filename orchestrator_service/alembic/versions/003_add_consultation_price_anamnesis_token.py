"""Add consultation_price to tenants and anamnesis_token to patients

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-03-20

- tenants.consultation_price: configurable consultation fee shown by AI agent
- patients.anamnesis_token: unique UUID for public anamnesis form URL
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, Sequence[str]] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tenant: consultation price (configurable from UI)
    op.execute("""
    ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS consultation_price DECIMAL(12,2) DEFAULT NULL;
    """)

    # Patient: unique token for public anamnesis form
    op.execute("""
    ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS anamnesis_token UUID DEFAULT NULL;
    """)

    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_anamnesis_token
    ON patients(anamnesis_token) WHERE anamnesis_token IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_patients_anamnesis_token;")
    op.execute("ALTER TABLE patients DROP COLUMN IF EXISTS anamnesis_token;")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS consultation_price;")
