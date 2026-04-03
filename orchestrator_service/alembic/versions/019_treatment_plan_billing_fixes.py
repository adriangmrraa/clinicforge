"""019 - Treatment plan billing fixes

Revision ID: 019
Revises: 018
Create Date: 2026-04-03

Corrective migration over 018_treatment_plan_billing:

H2  — payment_date: DATE → TIMESTAMPTZ with DEFAULT NOW()
H3  — Drop FK constraint treatment_plan_payments_appointment_id_fkey
H4  — Add 7 CHECK constraints (financial sanity + approval consistency + in_progress status)
M1  — Rename 4 indexes to consistent _id suffix
M2  — custom_description: VARCHAR(255) → TEXT
M3  — name: VARCHAR(255) → VARCHAR(200)
"""

from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "v4w5x6y7z8a9b"
branch_labels = None
depends_on = None


def upgrade():
    # -------------------------------------------------------------------------
    # H2 — payment_date: DATE → TIMESTAMPTZ, DEFAULT NOW()
    # -------------------------------------------------------------------------
    op.execute(
        "ALTER TABLE treatment_plan_payments "
        "ALTER COLUMN payment_date TYPE TIMESTAMPTZ "
        "USING payment_date::timestamptz"
    )
    op.execute(
        "ALTER TABLE treatment_plan_payments "
        "ALTER COLUMN payment_date SET DEFAULT NOW()"
    )

    # -------------------------------------------------------------------------
    # H3 — Drop FK on appointment_id (appointments UUID column, not needed)
    # -------------------------------------------------------------------------
    op.execute(
        "ALTER TABLE treatment_plan_payments "
        "DROP CONSTRAINT IF EXISTS treatment_plan_payments_appointment_id_fkey"
    )

    # -------------------------------------------------------------------------
    # H4 — CHECK constraints
    # -------------------------------------------------------------------------

    # treatment_plans: estimated_total >= 0
    op.execute(
        "ALTER TABLE treatment_plans "
        "ADD CONSTRAINT chk_tp_estimated_total "
        "CHECK (estimated_total >= 0)"
    )

    # treatment_plans: approved_total IS NULL OR >= 0
    op.execute(
        "ALTER TABLE treatment_plans "
        "ADD CONSTRAINT chk_tp_approved_total "
        "CHECK (approved_total IS NULL OR approved_total >= 0)"
    )

    # treatment_plans: approved_by and approved_at must both be NULL or both NOT NULL
    op.execute(
        "ALTER TABLE treatment_plans "
        "ADD CONSTRAINT chk_tp_approved_consistency "
        "CHECK ("
        "  (approved_by IS NULL AND approved_at IS NULL) OR "
        "  (approved_by IS NOT NULL AND approved_at IS NOT NULL)"
        ")"
    )

    # treatment_plan_items: estimated_price >= 0
    op.execute(
        "ALTER TABLE treatment_plan_items "
        "ADD CONSTRAINT chk_tpi_estimated_price "
        "CHECK (estimated_price >= 0)"
    )

    # treatment_plan_items: approved_price IS NULL OR >= 0
    op.execute(
        "ALTER TABLE treatment_plan_items "
        "ADD CONSTRAINT chk_tpi_approved_price "
        "CHECK (approved_price IS NULL OR approved_price >= 0)"
    )

    # treatment_plan_items: replace status CHECK to include 'in_progress'
    op.execute(
        "ALTER TABLE treatment_plan_items "
        "DROP CONSTRAINT IF EXISTS chk_treatment_plan_items_status"
    )
    op.execute(
        "ALTER TABLE treatment_plan_items "
        "ADD CONSTRAINT chk_treatment_plan_items_status "
        "CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled'))"
    )

    # -------------------------------------------------------------------------
    # M1 — Rename indexes to consistent _id suffix
    # -------------------------------------------------------------------------
    op.execute(
        "ALTER INDEX IF EXISTS idx_treatment_plan_items_plan "
        "RENAME TO idx_treatment_plan_items_plan_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS idx_treatment_plan_items_tenant_treatment "
        "RENAME TO idx_treatment_plan_items_tenant_code"
    )
    op.execute(
        "ALTER INDEX IF EXISTS idx_treatment_plan_payments_plan "
        "RENAME TO idx_treatment_plan_payments_plan_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS idx_appointments_plan_item "
        "RENAME TO idx_appointments_plan_item_id"
    )

    # -------------------------------------------------------------------------
    # M2 — custom_description: VARCHAR(255) → TEXT
    # -------------------------------------------------------------------------
    op.execute(
        "ALTER TABLE treatment_plan_items "
        "ALTER COLUMN custom_description TYPE TEXT"
    )

    # -------------------------------------------------------------------------
    # M3 — name: VARCHAR(255) → VARCHAR(200)
    # -------------------------------------------------------------------------
    op.execute(
        "ALTER TABLE treatment_plans "
        "ALTER COLUMN name TYPE VARCHAR(200)"
    )


def downgrade():
    # Reverse in reverse order of upgrade

    # M3 — name: VARCHAR(200) → VARCHAR(255)
    op.execute(
        "ALTER TABLE treatment_plans "
        "ALTER COLUMN name TYPE VARCHAR(255)"
    )

    # M2 — custom_description: TEXT → VARCHAR(255)
    op.execute(
        "ALTER TABLE treatment_plan_items "
        "ALTER COLUMN custom_description TYPE VARCHAR(255)"
    )

    # M1 — Rename indexes back to original names
    op.execute(
        "ALTER INDEX IF EXISTS idx_appointments_plan_item_id "
        "RENAME TO idx_appointments_plan_item"
    )
    op.execute(
        "ALTER INDEX IF EXISTS idx_treatment_plan_payments_plan_id "
        "RENAME TO idx_treatment_plan_payments_plan"
    )
    op.execute(
        "ALTER INDEX IF EXISTS idx_treatment_plan_items_tenant_code "
        "RENAME TO idx_treatment_plan_items_tenant_treatment"
    )
    op.execute(
        "ALTER INDEX IF EXISTS idx_treatment_plan_items_plan_id "
        "RENAME TO idx_treatment_plan_items_plan"
    )

    # H4 — Drop CHECK constraints (reverse order)
    op.execute(
        "ALTER TABLE treatment_plan_items "
        "DROP CONSTRAINT IF EXISTS chk_treatment_plan_items_status"
    )
    # Restore original status CHECK (without 'in_progress')
    op.execute(
        "ALTER TABLE treatment_plan_items "
        "ADD CONSTRAINT chk_treatment_plan_items_status "
        "CHECK (status IN ('pending', 'completed', 'cancelled'))"
    )

    op.execute(
        "ALTER TABLE treatment_plan_items "
        "DROP CONSTRAINT IF EXISTS chk_tpi_approved_price"
    )
    op.execute(
        "ALTER TABLE treatment_plan_items "
        "DROP CONSTRAINT IF EXISTS chk_tpi_estimated_price"
    )
    op.execute(
        "ALTER TABLE treatment_plans "
        "DROP CONSTRAINT IF EXISTS chk_tp_approved_consistency"
    )
    op.execute(
        "ALTER TABLE treatment_plans "
        "DROP CONSTRAINT IF EXISTS chk_tp_approved_total"
    )
    op.execute(
        "ALTER TABLE treatment_plans "
        "DROP CONSTRAINT IF EXISTS chk_tp_estimated_total"
    )

    # H3 — Re-add FK on appointment_id
    op.execute(
        "ALTER TABLE treatment_plan_payments "
        "ADD CONSTRAINT treatment_plan_payments_appointment_id_fkey "
        "FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL"
    )

    # H2 — payment_date: TIMESTAMPTZ → DATE, DEFAULT CURRENT_DATE
    op.execute(
        "ALTER TABLE treatment_plan_payments "
        "ALTER COLUMN payment_date DROP DEFAULT"
    )
    op.execute(
        "ALTER TABLE treatment_plan_payments "
        "ALTER COLUMN payment_date TYPE DATE "
        "USING payment_date::date"
    )
    op.execute(
        "ALTER TABLE treatment_plan_payments "
        "ALTER COLUMN payment_date SET DEFAULT CURRENT_DATE"
    )
