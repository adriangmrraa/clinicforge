"""020 - Financial Command Center

Revision ID: 020
Revises: 019
Create Date: 2026-04-03

Creates the core tables for the Financial Command Center:
- professional_commissions: Commission rate configuration per professional (default + per-treatment overrides)
- liquidation_records: Persistent liquidation snapshots with status tracking and audit trail
- professional_payouts: Payment tracking to professionals against liquidations

## Table Schemas

### professional_commissions
| Column           | Type           | Constraints                              |
|------------------|----------------|------------------------------------------|
| id               | SERIAL         | PK                                       |
| tenant_id        | INTEGER        | FK tenants.id CASCADE, NOT NULL          |
| professional_id  | INTEGER        | FK professionals.id CASCADE, NOT NULL    |
| commission_pct   | NUMERIC(5,2)   | NOT NULL, DEFAULT 0                      |
| treatment_code   | VARCHAR(100)   | NULL (NULL = default for all treatments) |
| created_at       | TIMESTAMPTZ    | NOT NULL, DEFAULT now()                  |
| updated_at       | TIMESTAMPTZ    | NOT NULL, DEFAULT now()                  |

UNIQUE: (tenant_id, professional_id, COALESCE(treatment_code, '__default__'))

### liquidation_records
| Column            | Type           | Constraints                              |
|-------------------|----------------|------------------------------------------|
| id                | SERIAL         | PK                                       |
| tenant_id         | INTEGER        | FK tenants.id CASCADE, NOT NULL          |
| professional_id   | INTEGER        | FK professionals.id CASCADE, NOT NULL    |
| period_start      | DATE           | NOT NULL                                 |
| period_end        | DATE           | NOT NULL                                 |
| total_billed      | NUMERIC(12,2)  | NOT NULL, DEFAULT 0                      |
| total_paid        | NUMERIC(12,2)  | NOT NULL, DEFAULT 0                      |
| total_pending     | NUMERIC(12,2)  | NOT NULL, DEFAULT 0                      |
| commission_pct    | NUMERIC(5,2)   | NOT NULL, DEFAULT 0                      |
| commission_amount | NUMERIC(12,2)  | NOT NULL, DEFAULT 0                      |
| payout_amount     | NUMERIC(12,2)  | NOT NULL, DEFAULT 0                      |
| status            | VARCHAR(20)    | NOT NULL, DEFAULT 'draft'                |
| generated_at      | TIMESTAMPTZ    | NOT NULL, DEFAULT now()                  |
| approved_at       | TIMESTAMPTZ    | NULL                                     |
| paid_at           | TIMESTAMPTZ    | NULL                                     |
| generated_by      | VARCHAR(255)   | NULL                                     |
| notes             | JSONB          | NULL                                     |
| created_at        | TIMESTAMPTZ    | NOT NULL, DEFAULT now()                  |
| updated_at        | TIMESTAMPTZ    | NOT NULL, DEFAULT now()                  |

CHECK: status IN ('draft', 'generated', 'approved', 'paid')
UNIQUE: (tenant_id, professional_id, period_start, period_end)

### professional_payouts
| Column             | Type           | Constraints                              |
|--------------------|----------------|------------------------------------------|
| id                 | SERIAL         | PK                                       |
| tenant_id          | INTEGER        | FK tenants.id CASCADE, NOT NULL          |
| liquidation_id     | INTEGER        | FK liquidation_records.id CASCADE, NOT NULL |
| professional_id    | INTEGER        | FK professionals.id CASCADE, NOT NULL    |
| amount             | NUMERIC(12,2)  | NOT NULL                                 |
| payment_method     | VARCHAR(50)    | NOT NULL                                 |
| payment_date       | DATE           | NOT NULL                                 |
| reference_number   | VARCHAR(100)   | NULL                                     |
| notes              | TEXT           | NULL                                     |
| created_at         | TIMESTAMPTZ    | NOT NULL, DEFAULT now()                  |

CHECK: payment_method IN ('transfer', 'cash', 'check')
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "020"
down_revision = "019"
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


def _constraint_exists(conn, constraint_name):
    """Check if a CHECK constraint exists."""
    result = conn.execute(
        text("SELECT 1 FROM pg_constraint WHERE conname = :name"),
        {"name": constraint_name},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()

    # -------------------------------------------------------------------------
    # 1. CREATE TABLE professional_commissions
    # -------------------------------------------------------------------------
    if not _table_exists(conn, "professional_commissions"):
        op.create_table(
            "professional_commissions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "professional_id",
                sa.Integer(),
                sa.ForeignKey("professionals.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "commission_pct",
                sa.Numeric(5, 2),
                nullable=False,
                server_default="0",
            ),
            sa.Column("treatment_code", sa.String(100), nullable=True),
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
        print("✅ Created professional_commissions table")

        # UNIQUE constraint: (tenant_id, professional_id, COALESCE(treatment_code, '__default__'))
        op.execute(
            """
            ALTER TABLE professional_commissions
            ADD CONSTRAINT uq_prof_comm
            UNIQUE (tenant_id, professional_id, COALESCE(treatment_code, '__default__'))
            """
        )
        print("✅ Added UNIQUE constraint uq_prof_comm")

        # Indexes with tenant_id filter
        op.create_index(
            "idx_prof_comm_tenant_professional",
            "professional_commissions",
            ["tenant_id", "professional_id"],
        )
        op.create_index(
            "idx_prof_comm_tenant",
            "professional_commissions",
            ["tenant_id"],
        )
        print("✅ Created indexes on professional_commissions")
    else:
        print("ℹ️  professional_commissions table already exists — skipping")

    # -------------------------------------------------------------------------
    # 2. CREATE TABLE liquidation_records
    # -------------------------------------------------------------------------
    if not _table_exists(conn, "liquidation_records"):
        op.create_table(
            "liquidation_records",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "professional_id",
                sa.Integer(),
                sa.ForeignKey("professionals.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column(
                "total_billed",
                sa.Numeric(12, 2),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "total_paid",
                sa.Numeric(12, 2),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "total_pending",
                sa.Numeric(12, 2),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "commission_pct",
                sa.Numeric(5, 2),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "commission_amount",
                sa.Numeric(12, 2),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "payout_amount",
                sa.Numeric(12, 2),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default="draft",
            ),
            sa.Column(
                "generated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("generated_by", sa.String(255), nullable=True),
            sa.Column("notes", sa.dialects.postgresql.JSONB, nullable=True),
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
        print("✅ Created liquidation_records table")

        # CHECK constraint for status
        op.execute(
            """
            ALTER TABLE liquidation_records
            ADD CONSTRAINT chk_liquidation_status
            CHECK (status IN ('draft', 'generated', 'approved', 'paid'))
            """
        )
        print("✅ Added CHECK constraint chk_liquidation_status")

        # UNIQUE constraint for idempotency
        op.execute(
            """
            ALTER TABLE liquidation_records
            ADD CONSTRAINT uq_liquidation_period
            UNIQUE (tenant_id, professional_id, period_start, period_end)
            """
        )
        print("✅ Added UNIQUE constraint uq_liquidation_period")

        # Indexes with tenant_id filter
        op.create_index(
            "idx_liquidation_tenant_status",
            "liquidation_records",
            ["tenant_id", "status"],
        )
        op.create_index(
            "idx_liquidation_tenant_professional_period",
            "liquidation_records",
            ["tenant_id", "professional_id", "period_start", "period_end"],
        )
        op.create_index(
            "idx_liquidation_tenant_period",
            "liquidation_records",
            ["tenant_id", "period_start", "period_end"],
        )
        print("✅ Created indexes on liquidation_records")
    else:
        print("ℹ️  liquidation_records table already exists — skipping")

    # -------------------------------------------------------------------------
    # 3. CREATE TABLE professional_payouts
    # -------------------------------------------------------------------------
    if not _table_exists(conn, "professional_payouts"):
        op.create_table(
            "professional_payouts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "liquidation_record_id",
                sa.Integer(),
                sa.ForeignKey("liquidation_records.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "professional_id",
                sa.Integer(),
                sa.ForeignKey("professionals.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "amount",
                sa.Numeric(12, 2),
                nullable=False,
            ),
            sa.Column(
                "payment_method",
                sa.String(50),
                nullable=False,
            ),
            sa.Column("payment_date", sa.Date(), nullable=False),
            sa.Column("reference_number", sa.String(100), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        print("✅ Created professional_payouts table")

        # CHECK constraint for payment_method
        op.execute(
            """
            ALTER TABLE professional_payouts
            ADD CONSTRAINT chk_payout_method
            CHECK (payment_method IN ('transfer', 'cash', 'check'))
            """
        )
        print("✅ Added CHECK constraint chk_payout_method")

        # Indexes with tenant_id filter
        op.create_index(
            "idx_payout_tenant_liquidation",
            "professional_payouts",
            ["tenant_id", "liquidation_record_id"],
        )
        op.create_index(
            "idx_payout_tenant_professional",
            "professional_payouts",
            ["tenant_id", "professional_id"],
        )
        op.create_index(
            "idx_payout_tenant_payment_date",
            "professional_payouts",
            ["tenant_id", "payment_date"],
        )
        print("✅ Created indexes on professional_payouts")
    else:
        print("ℹ️  professional_payouts table already exists — skipping")


def downgrade():
    conn = op.get_bind()

    # -------------------------------------------------------------------------
    # Drop professional_payouts (depends on liquidation_records)
    # -------------------------------------------------------------------------
    try:
        op.drop_index(
            "idx_payout_tenant_payment_date", table_name="professional_payouts"
        )
    except Exception:
        pass
    try:
        op.drop_index(
            "idx_payout_tenant_professional", table_name="professional_payouts"
        )
    except Exception:
        pass
    try:
        op.drop_index(
            "idx_payout_tenant_liquidation", table_name="professional_payouts"
        )
    except Exception:
        pass
    try:
        op.execute("DROP TABLE IF EXISTS professional_payouts CASCADE")
        print("✅ Dropped professional_payouts table")
    except Exception:
        pass

    # -------------------------------------------------------------------------
    # Drop liquidation_records
    # -------------------------------------------------------------------------
    try:
        op.drop_index("idx_liquidation_tenant_period", table_name="liquidation_records")
    except Exception:
        pass
    try:
        op.drop_index(
            "idx_liquidation_tenant_professional_period",
            table_name="liquidation_records",
        )
    except Exception:
        pass
    try:
        op.drop_index("idx_liquidation_tenant_status", table_name="liquidation_records")
    except Exception:
        pass
    try:
        op.execute("DROP TABLE IF EXISTS liquidation_records CASCADE")
        print("✅ Dropped liquidation_records table")
    except Exception:
        pass

    # -------------------------------------------------------------------------
    # Drop professional_commissions
    # -------------------------------------------------------------------------
    try:
        op.drop_index("idx_prof_comm_tenant", table_name="professional_commissions")
    except Exception:
        pass
    try:
        op.drop_index(
            "idx_prof_comm_tenant_professional", table_name="professional_commissions"
        )
    except Exception:
        pass
    try:
        op.execute("DROP TABLE IF EXISTS professional_commissions CASCADE")
        print("✅ Dropped professional_commissions table")
    except Exception:
        pass
