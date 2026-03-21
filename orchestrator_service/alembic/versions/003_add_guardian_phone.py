"""Add guardian_phone to patients for minor-parent linkage

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-03-21

Allows linking minor patients to their parent/guardian phone number.
Minors use phone format: parent_phone-M1, parent_phone-M2, etc.
guardian_phone stores the real parent phone for communication.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, Sequence[str]] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE patients ADD COLUMN IF NOT EXISTS guardian_phone VARCHAR(20) DEFAULT NULL;
    CREATE INDEX IF NOT EXISTS idx_patients_guardian ON patients(guardian_phone) WHERE guardian_phone IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("""
    DROP INDEX IF EXISTS idx_patients_guardian;
    ALTER TABLE patients DROP COLUMN IF EXISTS guardian_phone;
    """)
