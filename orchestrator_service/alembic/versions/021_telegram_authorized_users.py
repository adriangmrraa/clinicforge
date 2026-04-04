"""021 - Telegram Authorized Users

Revision ID: 021
Revises: 020
Create Date: 2026-04-03

Creates the table for Telegram bot authorization:
- telegram_authorized_users: Stores authorized Telegram chat IDs per tenant (Fernet encrypted)

## Table Schema

### telegram_authorized_users
| Column          | Type          | Constraints                             |
|-----------------|---------------|-----------------------------------------|
| id              | SERIAL        | PK                                      |
| tenant_id       | INTEGER       | FK tenants.id CASCADE, NOT NULL         |
| telegram_chat_id| TEXT          | NOT NULL (Fernet encrypted)             |
| display_name    | VARCHAR(255)  | NOT NULL                                |
| user_role       | VARCHAR(50)   | NOT NULL, DEFAULT 'ceo'                 |
| is_active       | BOOLEAN       | NOT NULL, DEFAULT true                  |
| created_at      | TIMESTAMPTZ   | NOT NULL, DEFAULT now()                 |
| updated_at      | TIMESTAMPTZ   | NOT NULL, DEFAULT now()                 |

UNIQUE: (tenant_id, telegram_chat_id)
INDEX: (tenant_id, is_active)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def _table_exists(conn, table):
    """Check if a table exists in the database."""
    try:
        result = conn.execute(
            text(
                f"SELECT 1 FROM information_schema.tables WHERE table_name = '{table}'"
            )
        )
        return result.fetchone() is not None
    except Exception:
        return False


def _index_exists(conn, index_name):
    """Check if a PostgreSQL index already exists."""
    result = conn.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": index_name},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()

    # -------------------------------------------------------------------------
    # 1. CREATE TABLE telegram_authorized_users
    # -------------------------------------------------------------------------
    if not _table_exists(conn, "telegram_authorized_users"):
        op.create_table(
            "telegram_authorized_users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("telegram_chat_id", sa.Text(), nullable=False),
            sa.Column("display_name", sa.String(255), nullable=False),
            sa.Column(
                "user_role",
                sa.String(50),
                nullable=False,
                server_default="ceo",
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
        )
        print("✅ Created telegram_authorized_users table")

        if not _index_exists(conn, "idx_telegram_auth_tenant_chatid"):
            op.create_index(
                "idx_telegram_auth_tenant_chatid",
                "telegram_authorized_users",
                ["tenant_id", "telegram_chat_id"],
                unique=True,
            )
            print("✅ Created UNIQUE index idx_telegram_auth_tenant_chatid")

        if not _index_exists(conn, "idx_telegram_auth_active"):
            op.create_index(
                "idx_telegram_auth_active",
                "telegram_authorized_users",
                ["tenant_id", "is_active"],
            )
            print("✅ Created index idx_telegram_auth_active")
    else:
        print("ℹ️  telegram_authorized_users table already exists — skipping")


def downgrade():
    conn = op.get_bind()

    if _table_exists(conn, "telegram_authorized_users"):
        if _index_exists(conn, "idx_telegram_auth_active"):
            op.drop_index("idx_telegram_auth_active", table_name="telegram_authorized_users")
        if _index_exists(conn, "idx_telegram_auth_tenant_chatid"):
            op.drop_index("idx_telegram_auth_tenant_chatid", table_name="telegram_authorized_users")
        op.drop_table("telegram_authorized_users")
        print("✅ Dropped telegram_authorized_users table")
    else:
        print("ℹ️  telegram_authorized_users table does not exist — skipping downgrade")
