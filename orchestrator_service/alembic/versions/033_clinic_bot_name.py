"""033 - Editable bot name per clinic

Revision ID: 033
Revises: 032
Create Date: 2026-04-08

Adds a nullable `bot_name` column to the `tenants` table so each clinic
can override the default bot display name ("TORA"). Currently the bot
name is hardcoded in buffer_task.py which breaks multi-tenancy — every
clinic is forced to use the same name.

NULL means "use the 'TORA' fallback" — zero behavior change for
existing tenants until a CEO sets a custom name from the Clinics UI.
"""

from alembic import op
import sqlalchemy as sa


revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("bot_name", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "bot_name")
