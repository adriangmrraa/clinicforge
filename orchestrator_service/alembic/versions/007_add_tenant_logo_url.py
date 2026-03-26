"""add logo_url to tenants

Revision ID: 007
Revises: 006
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tenants', sa.Column('logo_url', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('tenants', 'logo_url')
