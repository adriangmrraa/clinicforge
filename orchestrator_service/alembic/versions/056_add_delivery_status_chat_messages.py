"""
056: Add delivery_status column to chat_messages.

Adds:
- delivery_status (VARCHAR 20, NOT NULL, default 'delivered') to chat_messages
  Tracks WhatsApp delivery state: sent / delivered / read / failed
"""

revision = "056"
down_revision = "055"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    op.add_column(
        "chat_messages",
        sa.Column(
            "delivery_status",
            sa.String(20),
            nullable=False,
            server_default="delivered",
        ),
    )


def downgrade():
    from alembic import op

    op.drop_column("chat_messages", "delivery_status")
