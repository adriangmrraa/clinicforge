"""
052: Add 'human_supervisor' to chat_messages role check constraint.

The send endpoint persists manual messages with role='human_supervisor'
but the CHECK constraint only allows 'user', 'assistant', 'system', 'tool'.
"""

revision = "052"
down_revision = "051"


def upgrade():
    from alembic import op

    # Drop old constraint and add new one with human_supervisor
    op.execute("""
        ALTER TABLE chat_messages DROP CONSTRAINT IF EXISTS chat_messages_role_check;
    """)
    op.execute("""
        ALTER TABLE chat_messages ADD CONSTRAINT chat_messages_role_check
        CHECK (role IN ('user', 'assistant', 'system', 'tool', 'human_supervisor'));
    """)


def downgrade():
    from alembic import op

    op.execute("""
        ALTER TABLE chat_messages DROP CONSTRAINT IF EXISTS chat_messages_role_check;
    """)
    op.execute("""
        ALTER TABLE chat_messages ADD CONSTRAINT chat_messages_role_check
        CHECK (role IN ('user', 'assistant', 'system', 'tool'));
    """)
