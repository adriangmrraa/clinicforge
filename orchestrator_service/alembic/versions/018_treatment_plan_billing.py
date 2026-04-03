"""treatment_plan_billing: Create treatment_plans, treatment_plan_items, treatment_plan_payments tables

Revision ID: 018
Revises: 017
Create Date: 2026-04-03

Creates the core tables for the Treatment Plan Billing System:
- treatment_plans: Master records for patient treatment plans
- treatment_plan_items: Individual treatment line items within a plan
- treatment_plan_payments: Payment records against a plan
- appointments.plan_item_id: FK to link appointments to plan items

## Table Schemas

### treatment_plans
| Column            | Type          | Constraints                              |
|-------------------|---------------|------------------------------------------|
| id                | UUID          | PK                                       |
| tenant_id         | INTEGER       | FK tenants.id CASCADE, NOT NULL          |
| patient_id        | INTEGER       | FK patients.id CASCADE, NOT NULL          |
| professional_id   | INTEGER       | FK professionals.id SET NULL             |
| name              | VARCHAR(255)  | NOT NULL                                 |
| status            | VARCHAR(20)   | NOT NULL, CHECK IN (draft|approved|in_progress|completed|cancelled) |
| estimated_total   | NUMERIC(12,2) | DEFAULT 0                                 |
| approved_total    | NUMERIC(12,2) | NULL                                      |
| approved_by       | VARCHAR(100)  | NULL                                      |
| approved_at       | TIMESTAMP     | NULL                                      |
| notes             | TEXT          | NULL                                      |
| created_at        | TIMESTAMP     | NOT NULL, DEFAULT now()                   |
| updated_at        | TIMESTAMP     | NOT NULL, DEFAULT now()                   |

### treatment_plan_items
| Column              | Type          | Constraints                              |
|---------------------|---------------|------------------------------------------|
| id                  | UUID          | PK                                       |
| plan_id             | UUID          | FK treatment_plans.id CASCADE, NOT NULL  |
| tenant_id           | INTEGER       | FK tenants.id CASCADE, NOT NULL           |
| treatment_type_code | VARCHAR(50)   | NULL                                      |
| custom_description  | VARCHAR(255)  | NULL                                      |
| estimated_price     | NUMERIC(12,2) | NOT NULL, DEFAULT 0                      |
| approved_price      | NUMERIC(12,2) | NULL                                      |
| status              | VARCHAR(20)   | NOT NULL, CHECK IN (pending|completed|cancelled) |
| sort_order          | INTEGER       | NOT NULL, DEFAULT 0                      |
| created_at          | TIMESTAMP     | NOT NULL, DEFAULT now()                   |
| updated_at          | TIMESTAMP     | NOT NULL, DEFAULT now()                   |

### treatment_plan_payments
| Column            | Type          | Constraints                              |
|-------------------|---------------|------------------------------------------|
| id                | UUID          | PK                                       |
| plan_id           | UUID          | FK treatment_plans.id CASCADE, NOT NULL  |
| tenant_id         | INTEGER       | FK tenants.id CASCADE, NOT NULL          |
| amount            | NUMERIC(12,2) | NOT NULL, CHECK > 0                      |
| payment_method    | VARCHAR(20)   | NOT NULL, CHECK IN (cash|transfer|card|insurance) |
| payment_date      | DATE          | NOT NULL, DEFAULT CURRENT_DATE           |
| recorded_by       | VARCHAR(100)  | NULL                                      |
| appointment_id    | UUID          | FK appointments.id SET NULL              |
| receipt_data      | JSONB         | NULL                                      |
| notes             | TEXT          | NULL                                      |
| created_at        | TIMESTAMP     | NOT NULL, DEFAULT now()                   |

### appointments (add column)
| Column      | Type   | Constraints                        |
|-------------|--------|------------------------------------|
| plan_item_id| UUID   | FK treatment_plan_items.id SET NULL|
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID, JSONB, NUMERIC


revision = "v4w5x6y7z8a9b"
down_revision = "v4w5x6y7z8a9"
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
    # 1. CREATE TABLE treatment_plans
    # -------------------------------------------------------------------------
    if not _table_exists(conn, "treatment_plans"):
        op.create_table(
            "treatment_plans",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "patient_id",
                sa.Integer(),
                sa.ForeignKey("patients.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "professional_id",
                sa.Integer(),
                sa.ForeignKey("professionals.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default="draft",
            ),
            sa.Column(
                "estimated_total",
                NUMERIC(12, 2),
                nullable=False,
                server_default="0",
            ),
            sa.Column("approved_total", NUMERIC(12, 2), nullable=True),
            sa.Column("approved_by", sa.String(100), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
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
        print("✅ Created treatment_plans table")

        # CHECK constraint for plan status
        op.execute(
            """
            ALTER TABLE treatment_plans
            ADD CONSTRAINT chk_treatment_plans_status
            CHECK (status IN ('draft', 'approved', 'in_progress', 'completed', 'cancelled'))
            """
        )
        print("✅ Added CHECK constraint chk_treatment_plans_status")

        # Indexes with tenant_id filter
        op.create_index(
            "idx_treatment_plans_tenant_patient",
            "treatment_plans",
            ["tenant_id", "patient_id"],
        )
        op.create_index(
            "idx_treatment_plans_tenant_status",
            "treatment_plans",
            ["tenant_id", "status"],
        )
        op.create_index(
            "idx_treatment_plans_tenant_professional",
            "treatment_plans",
            ["tenant_id", "professional_id"],
        )
        print("✅ Created indexes on treatment_plans")
    else:
        print("ℹ️  treatment_plans table already exists — skipping")

    # -------------------------------------------------------------------------
    # 2. CREATE TABLE treatment_plan_items
    # -------------------------------------------------------------------------
    if not _table_exists(conn, "treatment_plan_items"):
        op.create_table(
            "treatment_plan_items",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "plan_id",
                UUID(as_uuid=True),
                sa.ForeignKey("treatment_plans.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("treatment_type_code", sa.String(50), nullable=True),
            sa.Column("custom_description", sa.String(255), nullable=True),
            sa.Column(
                "estimated_price",
                NUMERIC(12, 2),
                nullable=False,
                server_default="0",
            ),
            sa.Column("approved_price", NUMERIC(12, 2), nullable=True),
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default="pending",
            ),
            sa.Column(
                "sort_order",
                sa.Integer(),
                nullable=False,
                server_default="0",
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
        print("✅ Created treatment_plan_items table")

        # CHECK constraint for item status
        op.execute(
            """
            ALTER TABLE treatment_plan_items
            ADD CONSTRAINT chk_treatment_plan_items_status
            CHECK (status IN ('pending', 'completed', 'cancelled'))
            """
        )
        print("✅ Added CHECK constraint chk_treatment_plan_items_status")

        # Indexes with tenant_id filter
        op.create_index(
            "idx_treatment_plan_items_plan",
            "treatment_plan_items",
            ["plan_id"],
        )
        op.create_index(
            "idx_treatment_plan_items_tenant_plan",
            "treatment_plan_items",
            ["tenant_id", "plan_id"],
        )
        op.create_index(
            "idx_treatment_plan_items_tenant_treatment",
            "treatment_plan_items",
            ["tenant_id", "treatment_type_code"],
        )
        print("✅ Created indexes on treatment_plan_items")
    else:
        print("ℹ️  treatment_plan_items table already exists — skipping")

    # -------------------------------------------------------------------------
    # 3. CREATE TABLE treatment_plan_payments
    # -------------------------------------------------------------------------
    if not _table_exists(conn, "treatment_plan_payments"):
        op.create_table(
            "treatment_plan_payments",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "plan_id",
                UUID(as_uuid=True),
                sa.ForeignKey("treatment_plans.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "amount",
                NUMERIC(12, 2),
                nullable=False,
            ),
            sa.Column(
                "payment_method",
                sa.String(20),
                nullable=False,
            ),
            sa.Column(
                "payment_date",
                sa.Date,
                nullable=False,
                server_default=sa.func.current_date(),
            ),
            sa.Column("recorded_by", sa.String(100), nullable=True),
            sa.Column(
                "appointment_id",
                UUID(as_uuid=True),
                sa.ForeignKey("appointments.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("receipt_data", JSONB, nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        print("✅ Created treatment_plan_payments table")

        # CHECK constraint for payment_method
        op.execute(
            """
            ALTER TABLE treatment_plan_payments
            ADD CONSTRAINT chk_treatment_plan_payments_method
            CHECK (payment_method IN ('cash', 'transfer', 'card', 'insurance'))
            """
        )
        print("✅ Added CHECK constraint chk_treatment_plan_payments_method")

        # CHECK constraint for amount > 0
        op.execute(
            """
            ALTER TABLE treatment_plan_payments
            ADD CONSTRAINT chk_treatment_plan_payments_amount
            CHECK (amount > 0)
            """
        )
        print("✅ Added CHECK constraint chk_treatment_plan_payments_amount")

        # Indexes with tenant_id filter
        op.create_index(
            "idx_treatment_plan_payments_plan",
            "treatment_plan_payments",
            ["plan_id"],
        )
        op.create_index(
            "idx_treatment_plan_payments_tenant_plan",
            "treatment_plan_payments",
            ["tenant_id", "plan_id"],
        )
        op.create_index(
            "idx_treatment_plan_payments_tenant_date",
            "treatment_plan_payments",
            ["tenant_id", "payment_date"],
        )
        op.create_index(
            "idx_treatment_plan_payments_appointment",
            "treatment_plan_payments",
            ["appointment_id"],
        )
        print("✅ Created indexes on treatment_plan_payments")

        # ADD COLUMN accounting_transaction_id
        op.execute(
            """
            ALTER TABLE treatment_plan_payments
            ADD COLUMN accounting_transaction_id UUID
            REFERENCES accounting_transactions(id) ON DELETE SET NULL
            """
        )
        print("✅ Added accounting_transaction_id column to treatment_plan_payments")
    else:
        print("ℹ️  treatment_plan_payments table already exists — skipping")

    # Check and add accounting_transaction_id column if missing
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'treatment_plan_payments' AND column_name = 'accounting_transaction_id'"
        )
    )
    if result.fetchone() is None:
        op.execute(
            """
            ALTER TABLE treatment_plan_payments
            ADD COLUMN accounting_transaction_id UUID
            REFERENCES accounting_transactions(id) ON DELETE SET NULL
            """
        )
        print("✅ Added accounting_transaction_id column to treatment_plan_payments")

    # -------------------------------------------------------------------------
    # 4. ADD COLUMN plan_item_id TO appointments
    # -------------------------------------------------------------------------
    # Check if column exists by inspecting the table
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'appointments' AND column_name = 'plan_item_id'"
        )
    )
    if result.fetchone() is None:
        op.add_column(
            "appointments",
            sa.Column(
                "plan_item_id",
                UUID(as_uuid=True),
                sa.ForeignKey("treatment_plan_items.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        print("✅ Added plan_item_id column to appointments")

        # Create partial index for appointments with plan_item_id
        op.execute(
            """
            CREATE INDEX idx_appointments_plan_item
            ON appointments (plan_item_id)
            WHERE plan_item_id IS NOT NULL
            """
        )
        print("✅ Created partial index idx_appointments_plan_item")
    else:
        print("ℹ️  plan_item_id column already exists in appointments — skipping")


def downgrade():
    conn = op.get_bind()

    # Drop index on appointments
    try:
        op.execute("DROP INDEX IF EXISTS idx_appointments_plan_item")
        print("✅ Dropped partial index idx_appointments_plan_item")
    except Exception:
        pass

    # Drop column from appointments
    try:
        op.drop_column("appointments", "plan_item_id")
        print("✅ Dropped plan_item_id column from appointments")
    except Exception:
        pass

    # Drop indexes and table treatment_plan_payments
    try:
        op.drop_index(
            "idx_treatment_plan_payments_appointment",
            table_name="treatment_plan_payments",
        )
    except Exception:
        pass
    try:
        op.drop_index(
            "idx_treatment_plan_payments_tenant_date",
            table_name="treatment_plan_payments",
        )
    except Exception:
        pass
    try:
        op.drop_index(
            "idx_treatment_plan_payments_tenant_plan",
            table_name="treatment_plan_payments",
        )
    except Exception:
        pass
    try:
        op.drop_index(
            "idx_treatment_plan_payments_plan",
            table_name="treatment_plan_payments",
        )
    except Exception:
        pass
    try:
        op.execute("DROP TABLE IF EXISTS treatment_plan_payments CASCADE")
        print("✅ Dropped treatment_plan_payments table")
    except Exception:
        pass

    # Drop indexes and table treatment_plan_items
    try:
        op.drop_index(
            "idx_treatment_plan_items_tenant_treatment",
            table_name="treatment_plan_items",
        )
    except Exception:
        pass
    try:
        op.drop_index(
            "idx_treatment_plan_items_tenant_plan",
            table_name="treatment_plan_items",
        )
    except Exception:
        pass
    try:
        op.drop_index(
            "idx_treatment_plan_items_plan",
            table_name="treatment_plan_items",
        )
    except Exception:
        pass
    try:
        op.execute("DROP TABLE IF EXISTS treatment_plan_items CASCADE")
        print("✅ Dropped treatment_plan_items table")
    except Exception:
        pass

    # Drop indexes and table treatment_plans
    try:
        op.drop_index(
            "idx_treatment_plans_tenant_professional",
            table_name="treatment_plans",
        )
    except Exception:
        pass
    try:
        op.drop_index(
            "idx_treatment_plans_tenant_status",
            table_name="treatment_plans",
        )
    except Exception:
        pass
    try:
        op.drop_index(
            "idx_treatment_plans_tenant_patient",
            table_name="treatment_plans",
        )
    except Exception:
        pass
    try:
        op.execute("DROP TABLE IF EXISTS treatment_plans CASCADE")
        print("✅ Dropped treatment_plans table")
    except Exception:
        pass
