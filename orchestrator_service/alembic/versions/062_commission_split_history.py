"""Add clinic_pct to professional_commissions, commission_history table, reconciliation_ignored table

Adds:
1. clinic_pct column to professional_commissions with CHECK (commission_pct + clinic_pct = 100)
2. commission_history table for point-in-time commission lookup
3. reconciliation_ignored table for persisting ignored reconciliation discrepancies

Revision ID: 062
Revises: 061
"""
from alembic import op
import sqlalchemy as sa

revision = '062'
down_revision = '061'
branch_labels = None
depends_on = None


def upgrade():
    # ============================================================
    # 1. Add clinic_pct to professional_commissions
    # ============================================================

    # Step 1: Add nullable column
    op.add_column(
        "professional_commissions",
        sa.Column("clinic_pct", sa.Numeric(5, 2), nullable=True),
    )

    # Step 2: Populate with existing data (commission_pct was the professional's %)
    op.execute(
        """
        UPDATE professional_commissions
        SET clinic_pct = 100 - commission_pct
        WHERE clinic_pct IS NULL
        """
    )

    # Step 3: Make NOT NULL
    op.alter_column(
        "professional_commissions",
        "clinic_pct",
        nullable=False,
        server_default=sa.text("0"),
    )

    # Step 4: Add CHECK constraint
    op.create_check_constraint(
        "chk_comm_sum_100",
        "professional_commissions",
        sa.text("commission_pct + clinic_pct = 100"),
    )

    # ============================================================
    # 2. Create commission_history table
    # ============================================================

    op.create_table(
        "commission_history",
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
        sa.Column("treatment_code", sa.String(100), nullable=True),
        sa.Column("old_commission_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("new_commission_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("old_clinic_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("new_clinic_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("changed_by", sa.String(255), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Indexes for commission_history
    op.create_index("idx_comm_hist_tenant", "commission_history", ["tenant_id"])
    op.create_index(
        "idx_comm_hist_prof", "commission_history", ["professional_id"]
    )
    op.create_index(
        "idx_comm_hist_effective", "commission_history", ["effective_date"]
    )
    op.create_index(
        "idx_comm_hist_lookup",
        "commission_history",
        ["tenant_id", "professional_id", sa.text("effective_date DESC")],
    )

    # Migrate existing commission data to history (initial baseline entry)
    # Idempotent: only inserts if table is empty
    op.execute(
        """
        INSERT INTO commission_history (
            tenant_id, professional_id, treatment_code,
            old_commission_pct, new_commission_pct,
            old_clinic_pct, new_clinic_pct,
            changed_by, effective_date, created_at
        )
        SELECT
            tenant_id, professional_id, treatment_code,
            NULL, commission_pct,
            NULL, clinic_pct,
            'system_migration', CURRENT_DATE, NOW()
        FROM professional_commissions
        WHERE NOT EXISTS (
            SELECT 1 FROM commission_history
        )
        """
    )

    # ============================================================
    # 3. Create reconciliation_ignored table
    # ============================================================

    op.create_table(
        "reconciliation_ignored",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("appointment_id", sa.String(36), nullable=False),
        sa.Column(
            "ignored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ignored_by", sa.String(255), nullable=True),
    )

    # Unique constraint
    op.create_unique_constraint(
        "uq_reconciliation_ignore",
        "reconciliation_ignored",
        ["tenant_id", "appointment_id"],
    )

    # Index
    op.create_index(
        "idx_reconciliation_tenant", "reconciliation_ignored", ["tenant_id"]
    )


def downgrade():
    # Drop reconciliation_ignored
    op.drop_table("reconciliation_ignored")

    # Drop commission_history
    op.drop_table("commission_history")

    # Remove CHECK constraint from professional_commissions
    op.drop_constraint("chk_comm_sum_100", "professional_commissions")

    # Drop clinic_pct column
    op.drop_column("professional_commissions", "clinic_pct")
