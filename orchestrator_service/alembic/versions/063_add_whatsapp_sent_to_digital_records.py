"""063 - Add WhatsApp sent tracking columns to patient_digital_records

Adds two columns to track when a digital record was sent via WhatsApp:
- sent_to_whatsapp: phone number (E.164) of the recipient
- sent_via_whatsapp_at: timestamp of the delivery

These are independent of the existing sent_to_email / sent_at columns so a
record can be sent to multiple channels without overwriting history.

Revision ID: 063
Revises: 062
Create Date: 2026-06-07
"""
from alembic import op


revision = "063"
down_revision = "062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE patient_digital_records
        ADD COLUMN IF NOT EXISTS sent_to_whatsapp VARCHAR(50),
        ADD COLUMN IF NOT EXISTS sent_via_whatsapp_at TIMESTAMPTZ
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE patient_digital_records
        DROP COLUMN IF EXISTS sent_via_whatsapp_at,
        DROP COLUMN IF EXISTS sent_to_whatsapp
        """
    )
