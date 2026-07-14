"""074 — Motor de dinero L1: subtipo de pago en accounting_transactions

payment_kind clasifica cada evento de cobro SIN tocar transaction_type
(que sigue siendo 'payment' para no romper los 3 filtros ya existentes en
admin_routes que buscan transaction_type='payment').

Valores esperados:
  'sena'     → seña del turno (parte de la consulta)
  'coseguro' → monto de coseguro cargado por la secretaria
  'resto'    → saldo restante cobrado en mostrador
  'ajuste'   → corrección manual
  'pago'     → cobro genérico (default cuando no se especifica)
  NULL       → filas viejas (legacy, previas a esta migración)

Esto convierte accounting_transactions en el libro único de eventos de pago:
"cobrado" = Σ eventos, y billing_amount nunca se pisa por un cobro.

Revision ID: 074
Revises: 073
"""

from alembic import op
import sqlalchemy as sa

revision = "074"
down_revision = "073"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "accounting_transactions",
        sa.Column("payment_kind", sa.String(20), nullable=True),
    )
    # Índice parcial para consultas por subtipo de cobro (seña/coseguro/resto)
    op.create_index(
        "idx_accounting_payment_kind",
        "accounting_transactions",
        ["tenant_id", "payment_kind"],
        unique=False,
    )


def downgrade():
    op.drop_index("idx_accounting_payment_kind", table_name="accounting_transactions")
    op.drop_column("accounting_transactions", "payment_kind")
