"""lead_recovery_v2_fields

Revision ID: 043_lead_recovery_v2
Revises: 042_sena_guardrails
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa

revision = "043_lead_recovery_v2"
down_revision = "042_sena_guardrails"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('chat_conversations',
        sa.Column('no_followup', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('chat_conversations',
        sa.Column('recovery_touch_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('chat_conversations',
        sa.Column('last_recovery_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        'idx_chat_conv_recovery',
        'chat_conversations',
        ['tenant_id', 'last_user_message_at', 'recovery_touch_count', 'no_followup']
    )


def downgrade():
    op.drop_index('idx_chat_conv_recovery', table_name='chat_conversations')
    op.drop_column('chat_conversations', 'last_recovery_at')
    op.drop_column('chat_conversations', 'recovery_touch_count')
    op.drop_column('chat_conversations', 'no_followup')
