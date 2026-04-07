"""030 - Defensive UNIQUE index on chat_messages provider_message_id

Revision ID: 030
Revises: 029
Create Date: 2026-04-07

Belt-and-suspenders fix for the Chatwoot double-reply bug. Even after the
HTTP-level idempotency (try_insert_inbound) and the BufferManager lock-first
fixes, this partial UNIQUE index guarantees that no two rows in chat_messages
can ever share the same (conversation_id, provider_message_id) — at the
database layer.

The index is PARTIAL: only enforced when platform_metadata->>'provider_message_id'
is not null and not empty. This allows legacy rows (and rows from providers
that don't expose a stable id) to coexist without conflict.

A pre-flight cleanup step removes any pre-existing duplicates so the index
creation cannot fail.
"""
from alembic import op
import sqlalchemy as sa


revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade():
    # Pre-flight: drop any duplicate rows that would violate the new unique index.
    # Keep the earliest row per (conversation_id, provider_message_id).
    op.execute(
        """
        DELETE FROM chat_messages a
        USING chat_messages b
        WHERE a.conversation_id = b.conversation_id
          AND a.platform_metadata->>'provider_message_id' = b.platform_metadata->>'provider_message_id'
          AND a.platform_metadata->>'provider_message_id' IS NOT NULL
          AND a.platform_metadata->>'provider_message_id' <> ''
          AND a.id > b.id
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_chat_messages_conv_provider_msg_id
        ON chat_messages (conversation_id, (platform_metadata->>'provider_message_id'))
        WHERE platform_metadata->>'provider_message_id' IS NOT NULL
          AND platform_metadata->>'provider_message_id' <> ''
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uniq_chat_messages_conv_provider_msg_id")
