"""023 - Add nova_memories table

Revision ID: 023
Revises: 022
Create Date: 2026-04-04

Creates the nova_memories table for Nova's Engram persistent memory system.
Allows Nova to remember decisions, workflows, and patient notes across sessions
(Telegram, voice, and future channels).

Columns:
  type        — semantic type (decision/feedback/patient_note/reminder/workflow/preference/discovery/general)
  topic_key   — stable key for upsert (optional, e.g. "workflow/turno-flow")
  source_channel — origin channel (telegram/voice/web/unknown)
  created_by  — user identifier (optional)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def _table_exists(conn, table):
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :table"
        ),
        {"table": table},
    )
    return result.fetchone() is not None


def _column_exists(conn, table, column):
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.fetchone() is not None


def _index_exists(conn, index_name):
    result = conn.execute(
        text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :name"
        ),
        {"name": index_name},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()

    if not _table_exists(conn, "nova_memories"):
        op.create_table(
            "nova_memories",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "type",
                sa.String(50),
                nullable=False,
                server_default="general",
            ),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("topic_key", sa.String(255), nullable=True),
            sa.Column("created_by", sa.String(100), nullable=True),
            sa.Column(
                "source_channel",
                sa.String(50),
                nullable=False,
                server_default="unknown",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()"),
            ),
        )
        op.create_index("idx_nova_memories_tenant", "nova_memories", ["tenant_id"])
        op.create_index(
            "idx_nova_memories_type", "nova_memories", ["tenant_id", "type"]
        )
        op.create_index(
            "idx_nova_memories_topic_key",
            "nova_memories",
            ["tenant_id", "topic_key"],
        )
        print("✅ Created nova_memories table with full Engram schema")
    else:
        # Table already exists — add missing columns introduced by this revision
        print("ℹ️  nova_memories already exists — checking for missing columns")

        if _column_exists(conn, "nova_memories", "category") and not _column_exists(conn, "nova_memories", "type"):
            # Rename legacy 'category' → 'type'
            op.alter_column("nova_memories", "category", new_column_name="type")
            print("✅ Renamed column category → type in nova_memories")

        if not _column_exists(conn, "nova_memories", "type"):
            op.add_column(
                "nova_memories",
                sa.Column("type", sa.String(50), nullable=False, server_default="general"),
            )
            print("✅ Added type column to nova_memories")

        if not _column_exists(conn, "nova_memories", "topic_key"):
            op.add_column(
                "nova_memories",
                sa.Column("topic_key", sa.String(255), nullable=True),
            )
            print("✅ Added topic_key column to nova_memories")

        if not _column_exists(conn, "nova_memories", "source_channel"):
            op.add_column(
                "nova_memories",
                sa.Column(
                    "source_channel",
                    sa.String(50),
                    nullable=False,
                    server_default="unknown",
                ),
            )
            print("✅ Added source_channel column to nova_memories")

        # Ensure indexes exist
        if not _index_exists(conn, "idx_nova_memories_topic_key"):
            op.create_index(
                "idx_nova_memories_topic_key",
                "nova_memories",
                ["tenant_id", "topic_key"],
            )
            print("✅ Added idx_nova_memories_topic_key index")

        if not _index_exists(conn, "idx_nova_memories_type"):
            op.create_index(
                "idx_nova_memories_type", "nova_memories", ["tenant_id", "type"]
            )
            print("✅ Added idx_nova_memories_type index")

        if not _index_exists(conn, "idx_nova_memories_tenant"):
            op.create_index(
                "idx_nova_memories_tenant", "nova_memories", ["tenant_id"]
            )
            print("✅ Added idx_nova_memories_tenant index")


def downgrade():
    conn = op.get_bind()

    if _table_exists(conn, "nova_memories"):
        op.drop_index("idx_nova_memories_topic_key", table_name="nova_memories")
        op.drop_index("idx_nova_memories_type", table_name="nova_memories")
        op.drop_index("idx_nova_memories_tenant", table_name="nova_memories")
        op.drop_table("nova_memories")
        print("✅ Dropped nova_memories table")
    else:
        print("ℹ️  nova_memories does not exist — skipping downgrade")
