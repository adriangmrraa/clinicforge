"""add_semaphore_to_insurance_providers

Revision ID: 2ea6dcca70ad
Revises: 064
Create Date: 2026-06-08 18:43:25.935023

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ea6dcca70ad'
down_revision: Union[str, Sequence[str], None] = '064'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tenant_insurance_providers', sa.Column('scheduling_mode', sa.String(20), server_default='immediate', nullable=False))
    op.add_column('tenant_insurance_providers', sa.Column('scheduling_delay_days', sa.Integer(), server_default='0', nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tenant_insurance_providers', 'scheduling_delay_days')
    op.drop_column('tenant_insurance_providers', 'scheduling_mode')
