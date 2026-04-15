"""
054: Add linked_patient_id to chat_conversations.

Allows linking a chat contact (who may NOT be a patient) to an existing
patient record. Use case: a family member (e.g. son) pays on behalf of
a patient (e.g. mother). The son's chat gets linked to the mother's
patient record so documents and receipts flow to her file automatically.
"""

revision = "054"
down_revision = "053"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    op.add_column(
        "chat_conversations",
        sa.Column("linked_patient_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "chat_conversations",
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_chat_conv_linked_patient",
        "chat_conversations",
        ["linked_patient_id"],
        postgresql_where=sa.text("linked_patient_id IS NOT NULL"),
    )


def downgrade():
    from alembic import op

    op.drop_index("idx_chat_conv_linked_patient", table_name="chat_conversations")
    op.drop_column("chat_conversations", "linked_at")
    op.drop_column("chat_conversations", "linked_patient_id")
