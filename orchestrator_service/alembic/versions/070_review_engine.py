"""070 - Motor de reseñas: review_requests + review_goal_monthly + review_requested_at

Boton "Pedir resena" en el chat + objetivo mensual + seguimiento.
- review_requests: 1 fila por pedido (contar por mes + quien).
- tenants.review_goal_monthly: objetivo mensual de resenas pedidas (0 = sin objetivo).
- patients.review_requested_at: candado anti-repetir + estado del boton.

Revision ID: 070
Revises: 069
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa


revision = "070"
down_revision = "069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Text(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_review_requests_tenant_at",
        "review_requests",
        ["tenant_id", "requested_at"],
    )
    op.add_column(
        "tenants",
        sa.Column(
            "review_goal_monthly",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "patients",
        sa.Column("review_requested_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("patients", "review_requested_at")
    op.drop_column("tenants", "review_goal_monthly")
    op.drop_index("ix_review_requests_tenant_at", table_name="review_requests")
    op.drop_table("review_requests")
