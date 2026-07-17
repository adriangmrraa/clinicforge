"""077 - Candado anti-doble-envío de reseñas: UNIQUE(tenant_id, phone) en review_requests

Bug hallado 2026-07-17 (verificación adversarial): el candado anti-repetición de
pedidos de reseña era check-then-act (SELECT antes del envío, INSERT después),
sin transacción ni índice único → dos requests concurrentes (doble click / doble
pestaña) mandaban 2 mensajes e inflaban el conteo del mes. Además, un contacto
sin ficha que recibía reseña y luego se volvía paciente podía recibir un 2º pedido.

Este UNIQUE(tenant_id, phone) hace el candado atómico a nivel BD: el endpoint
reclama el cupo con INSERT ... ON CONFLICT DO NOTHING ANTES de enviar. Solo uno
gana; el resto recibe 409. Cubre ambos agujeros de una sola vez.

Política confirmada por Carlos (2026-07-17): 1 pedido de reseña por paciente
para SIEMPRE (anti-spam de por vida) — este UNIQUE lo garantiza.

Revision ID: 077
Revises: 076
"""
from alembic import op

revision = "077"
down_revision = "076"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Dedup defensivo: si ya había duplicados por el bug de la carrera, dejar la
    #    fila MÁS ANTIGUA por (tenant_id, phone) — así el índice único puede crearse.
    #    phone NULL se ignora (NULLs no chocan en UNIQUE de Postgres).
    op.execute(
        """
        DELETE FROM review_requests a
        USING review_requests b
        WHERE a.tenant_id = b.tenant_id
          AND a.phone = b.phone
          AND a.phone IS NOT NULL
          AND a.id > b.id
        """
    )
    # 2) Candado atómico.
    op.create_unique_constraint(
        "uq_review_requests_tenant_phone",
        "review_requests",
        ["tenant_id", "phone"],
    )


def downgrade():
    op.drop_constraint(
        "uq_review_requests_tenant_phone",
        "review_requests",
        type_="unique",
    )
