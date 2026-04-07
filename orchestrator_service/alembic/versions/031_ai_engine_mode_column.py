"""031 - Add ai_engine_mode column to tenants

Revision ID: 031
Revises: 030
Create Date: 2026-04-07

Adds ai_engine_mode column to tenants table for dual-engine system.
Default 'solo' ensures backward compatibility — all existing tenants
continue using TORA-solo without any migration needed.

Values:
- 'solo': TORA monolithic (default, backward compatible)
- 'multi': Multi-agent LangGraph system
"""

from alembic import op
import sqlalchemy as sa


revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE tenants 
        ADD COLUMN ai_engine_mode TEXT NOT NULL DEFAULT 'solo'
        CHECK (ai_engine_mode IN ('solo', 'multi'))
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE tenants DROP COLUMN ai_engine_mode")
