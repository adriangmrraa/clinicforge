"""whatsapp_messages - Full WhatsApp message sync table

Revision ID: 044_whatsapp_messages
Revises: 043_lead_recovery_v2
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "044_whatsapp_messages"
down_revision = "043_lead_recovery_v2"
branch_labels = None
depends_on = None


def upgrade():
    # Main whatsapp_messages table
    op.create_table(
        "whatsapp_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(64), nullable=True),  # YCloud message ID
        sa.Column("wamid", sa.String(64), nullable=True),  # WhatsApp message ID
        sa.Column("from_number", sa.String(32), nullable=False),
        sa.Column("to_number", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("message_type", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("media_url", sa.String(512), nullable=True),
        sa.Column("media_id", sa.String(128), nullable=True),
        sa.Column("media_mime_type", sa.String(64), nullable=True),
        sa.Column("media_filename", sa.String(256), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="synced",
        ),
        sa.Column(
            "patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=True
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_conversations.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("error_message", sa.String(512), nullable=True),
    )

    # Add constraints
    op.create_index(
        "idx_whatsapp_messages_external_id",
        "whatsapp_messages",
        ["external_id"],
        unique=True,
    )
    op.create_index("idx_whatsapp_messages_wamid", "whatsapp_messages", ["wamid"])
    op.create_index(
        "idx_whatsapp_messages_from_number", "whatsapp_messages", ["from_number"]
    )
    op.create_index(
        "idx_whatsapp_messages_tenant_created",
        "whatsapp_messages",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "idx_whatsapp_messages_direction", "whatsapp_messages", ["direction"]
    )
    op.create_index(
        "idx_whatsapp_messages_tenant_sync",
        "whatsapp_messages",
        ["tenant_id", "synced_at"],
    )

    # Direction constraint
    op.execute(
        "ALTER TABLE whatsapp_messages ADD CONSTRAINT whatsapp_messages_direction_check "
        "CHECK (direction IN ('inbound', 'outbound'))"
    )

    # Status constraint
    op.execute(
        "ALTER TABLE whatsapp_messages ADD CONSTRAINT whatsapp_messages_status_check "
        "CHECK (status IN ('pending', 'syncing', 'synced', 'failed'))"
    )


def downgrade():
    op.execute(
        "ALTER TABLE whatsapp_messages DROP CONSTRAINT whatsapp_messages_status_check"
    )
    op.execute(
        "ALTER TABLE whatsapp_messages DROP CONSTRAINT whatsapp_messages_direction_check"
    )
    op.drop_index("idx_whatsapp_messages_tenant_sync", table_name="whatsapp_messages")
    op.drop_index("idx_whatsapp_messages_direction", table_name="whatsapp_messages")
    op.drop_index(
        "idx_whatsapp_messages_tenant_created", table_name="whatsapp_messages"
    )
    op.drop_index("idx_whatsapp_messages_from_number", table_name="whatsapp_messages")
    op.drop_index("idx_whatsapp_messages_wamid", table_name="whatsapp_messages")
    op.drop_index("idx_whatsapp_messages_external_id", table_name="whatsapp_messages")
    op.drop_table("whatsapp_messages")
