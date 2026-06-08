"""064 - Add instruction_type column to automation_steps

Adds instruction_type VARCHAR(20) with DEFAULT 'post' to distinguish
pre-treatment ("pre") from post-treatment ("post") automation steps.
Existing rows get NULL which the executor handles via OR "post" fallback.

Revision ID: 064
Revises: 063
Create Date: 2026-06-08
"""
from alembic import op


revision = "064"
down_revision = "063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE automation_steps
        ADD COLUMN IF NOT EXISTS instruction_type VARCHAR(20) DEFAULT 'post'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE automation_steps
        DROP COLUMN IF EXISTS instruction_type
        """
    )
