"""
058: Add treatment_plan_installments table and link to payments.

Adds:
- treatment_plan_installments table: cuota tracking per treatment plan
  Each installment has installment_number, amount, due_date, status (pending/paid),
  paid_at, and a FK to the payment that settled it.
- treatment_plan_payments.installment_id: reverse FK to the installment paid by this payment.
"""

revision = "058"
down_revision = "057"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    op.create_table(
        "treatment_plan_installments",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "plan_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column("installment_number", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "payment_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["treatment_plans.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["treatment_plan_payments.id"],
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("installment_number > 0", name="ck_installment_number_positive"),
        sa.CheckConstraint("amount > 0", name="ck_installment_amount_positive"),
        sa.CheckConstraint(
            "status IN ('pending', 'paid')", name="ck_installment_status"
        ),
        sa.UniqueConstraint("plan_id", "installment_number", name="uq_installment_plan_number"),
    )

    op.create_index(
        "idx_installments_tenant_plan",
        "treatment_plan_installments",
        ["tenant_id", "plan_id"],
    )
    op.create_index(
        "idx_installments_status",
        "treatment_plan_installments",
        ["tenant_id", "status"],
    )

    # Add installment_id to treatment_plan_payments (reverse link)
    op.add_column(
        "treatment_plan_payments",
        sa.Column(
            "installment_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_payments_installment_id",
        "treatment_plan_payments",
        "treatment_plan_installments",
        ["installment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    from alembic import op

    op.drop_constraint(
        "fk_payments_installment_id", "treatment_plan_payments", type_="foreignkey"
    )
    op.drop_column("treatment_plan_payments", "installment_id")

    op.drop_index("idx_installments_status", table_name="treatment_plan_installments")
    op.drop_index("idx_installments_tenant_plan", table_name="treatment_plan_installments")
    op.drop_table("treatment_plan_installments")
