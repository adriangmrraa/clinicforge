"""Add billing fields to appointments, bank details and derivation email to tenants

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-03-24

Adds:
- tenants: bank_cbu, bank_alias, bank_holder_name, derivation_email
- appointments: billing_amount, billing_installments, billing_notes, payment_status, payment_receipt_data
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f6g7h8i9j0k1'
down_revision: Union[str, Sequence[str]] = 'e5f6g7h8i9j0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tenant bank & derivation fields
    op.execute("""
    ALTER TABLE tenants
        ADD COLUMN IF NOT EXISTS bank_cbu TEXT,
        ADD COLUMN IF NOT EXISTS bank_alias TEXT,
        ADD COLUMN IF NOT EXISTS bank_holder_name TEXT,
        ADD COLUMN IF NOT EXISTS derivation_email TEXT;
    """)

    # Appointment billing fields
    op.execute("""
    ALTER TABLE appointments
        ADD COLUMN IF NOT EXISTS billing_amount DECIMAL(12, 2),
        ADD COLUMN IF NOT EXISTS billing_installments INTEGER,
        ADD COLUMN IF NOT EXISTS billing_notes TEXT,
        ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) DEFAULT 'pending',
        ADD COLUMN IF NOT EXISTS payment_receipt_data JSONB;
    """)

    # Professional consultation price (per-professional override)
    op.execute("""
    ALTER TABLE professionals
        ADD COLUMN IF NOT EXISTS consultation_price DECIMAL(12, 2);
    """)

    # Index for payment status queries
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_appointments_payment_status
        ON appointments (payment_status);
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE professionals DROP COLUMN IF EXISTS consultation_price;")
    op.execute("DROP INDEX IF EXISTS idx_appointments_payment_status;")
    op.execute("""
    ALTER TABLE appointments
        DROP COLUMN IF EXISTS billing_amount,
        DROP COLUMN IF EXISTS billing_installments,
        DROP COLUMN IF EXISTS billing_notes,
        DROP COLUMN IF EXISTS payment_status,
        DROP COLUMN IF EXISTS payment_receipt_data;
    """)
    op.execute("""
    ALTER TABLE tenants
        DROP COLUMN IF EXISTS bank_cbu,
        DROP COLUMN IF EXISTS bank_alias,
        DROP COLUMN IF EXISTS bank_holder_name,
        DROP COLUMN IF EXISTS derivation_email;
    """)
