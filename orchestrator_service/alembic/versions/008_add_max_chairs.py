"""add max_chairs to tenants

Revision ID: 008
Revises: 007
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = 'h8i9j0k1l2m3'
down_revision = 'g7h8i9j0k1l2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tenants', sa.Column('max_chairs', sa.Integer(), server_default='2', nullable=True))


def downgrade():
    op.drop_column('tenants', 'max_chairs')
