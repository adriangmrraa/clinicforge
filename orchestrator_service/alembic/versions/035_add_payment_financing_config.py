"""035 - Add payment & financing configuration

Revision ID: 035
Revises: 034
Create Date: 2026-04-08

Adds 8 columns to the `tenants` table for payment methods, financing options,
and cash discount configuration. This enables the AI agent to answer the 5 most
common payment queries without escalating to human.

Note (2026-04-08 fix): originally written with down_revision="033" because
both 034 (insurance-coverage) and 035 were developed in parallel branches.
Both were merged to main with the same down_revision, creating a fork in
the Alembic chain → "Multiple head revisions" error on `alembic upgrade head`.
Linearized to chain after 034 (the two migrations touch different tables —
tenant_insurance_providers vs tenants — so order is irrelevant functionally).

Columns added:
- payment_methods (JSONB): array of payment method tokens
- financing_available (BOOLEAN): whether financing/installments are offered
- max_installments (INTEGER): 1-24, max number of installments
- installments_interest_free (BOOLEAN): whether interest-free installments are available
- financing_provider (TEXT): financing provider name
- financing_notes (TEXT): free-text qualifier for financing terms
- cash_discount_percent (DECIMAL): discount for cash payments (0-100)
- accepts_crypto (BOOLEAN): whether cryptocurrency is accepted
"""

from alembic import op
import sqlalchemy as sa


revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Payment methods as JSONB array
    op.add_column(
        "tenants",
        sa.Column("payment_methods", sa.JSONB, nullable=True),
    )

    # Financing options
    op.add_column(
        "tenants",
        sa.Column(
            "financing_available",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
        ),
    )

    op.add_column(
        "tenants",
        sa.Column("max_installments", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_tenants_max_installments_range",
        "tenants",
        "max_installments IS NULL OR (max_installments >= 1 AND max_installments <= 24)",
    )

    op.add_column(
        "tenants",
        sa.Column(
            "installments_interest_free",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("true"),
        ),
    )

    op.add_column(
        "tenants",
        sa.Column("financing_provider", sa.Text(), nullable=True),
    )

    op.add_column(
        "tenants",
        sa.Column("financing_notes", sa.Text(), nullable=True),
    )

    # Cash discount
    op.add_column(
        "tenants",
        sa.Column(
            "cash_discount_percent",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_tenants_cash_discount_range",
        "tenants",
        "cash_discount_percent IS NULL OR (cash_discount_percent >= 0 AND cash_discount_percent <= 100)",
    )

    # Crypto
    op.add_column(
        "tenants",
        sa.Column(
            "accepts_crypto",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "accepts_crypto")
    op.drop_constraint("ck_tenants_cash_discount_range", "tenants")
    op.drop_column("tenants", "cash_discount_percent")
    op.drop_column("tenants", "financing_notes")
    op.drop_column("tenants", "financing_provider")
    op.drop_constraint("ck_tenants_max_installments_range", "tenants")
    op.drop_column("tenants", "max_installments")
    op.drop_column("tenants", "installments_interest_free")
    op.drop_column("tenants", "financing_available")
    op.drop_column("tenants", "payment_methods")
