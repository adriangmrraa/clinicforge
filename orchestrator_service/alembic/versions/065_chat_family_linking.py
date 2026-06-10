"""065 - Add family_patient_ids to chat_conversations

Adds family_patient_ids INTEGER[] nullable column with GIN index
so a single chat can manage appointments and context for MULTIPLE patients
(primary linked_patient_id + family members), without overwriting linked_patient_id.

Revision ID: 065
Revises: 064
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa


revision = "065"
down_revision = "064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_conversations",
        sa.Column("family_patient_ids", sa.ARRAY(sa.Integer()), nullable=True),
    )
    op.create_index(
        "ix_chat_conversations_family_patient_ids_gin",
        "chat_conversations",
        ["family_patient_ids"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chat_conversations_family_patient_ids_gin",
        table_name="chat_conversations",
    )
    op.drop_column("chat_conversations", "family_patient_ids")
