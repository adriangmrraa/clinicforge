"""071 - Colector de casos: tabla cases_to_review

Recopila automaticamente las conversaciones donde el bot (Paula) fallo o quedo
trabado, para revisarlas y mejorar el prompt. NO se muestra en el panel de la
clinica (el cliente no lo ve): un job diario detecta los casos por SENALES
DETERMINISTAS y manda un resumen por mail al equipo (dueno del producto).

Senales de la fase 1 (sin IA, cero tokens):
  - agent_error : la conversacion quedo marcada con last_agent_error_at (el bot se cayo)
  - derivation  : el bot derivo a humano (last_derivhumano_at)
  - loop        : el asistente repitio el MISMO mensaje 3+ veces en la conversacion

Idempotencia: un caso por (tenant, conversacion, categoria, dia de deteccion).

Revision ID: 071
Revises: 070
Create Date: 2026-07-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "071"
down_revision = "070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cases_to_review",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # La conversacion problematica. SET NULL: si se borra la conversacion,
        # conservamos el caso para el historial de revision.
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("phone_number", sa.Text(), nullable=True),
        sa.Column("patient_name", sa.Text(), nullable=True),
        # Categoria del problema. Texto controlado por el codigo (sin CHECK para no
        # necesitar una migracion cuando la fase 2 con IA agregue categorias nuevas).
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column(
            "severity",
            sa.String(10),
            nullable=False,
            server_default=sa.text("'medium'"),
        ),
        sa.Column(
            "status",
            sa.String(15),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        # Dia de deteccion: bucket de idempotencia (recurrencia en otro dia = caso nuevo).
        sa.Column(
            "incident_date",
            sa.Date(),
            nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "severity IN ('high','medium','low')",
            name="ck_cases_to_review_severity",
        ),
        sa.CheckConstraint(
            "status IN ('pending','reviewed','dismissed')",
            name="ck_cases_to_review_status",
        ),
    )
    # Idempotencia: no re-cargar el mismo caso el mismo dia (a prueba de reinicios del job).
    op.create_index(
        "uq_cases_to_review_dedup",
        "cases_to_review",
        ["tenant_id", "conversation_id", "category", "incident_date"],
        unique=True,
    )
    # Lookup por estado (casos pendientes de revisar por clinica).
    op.create_index(
        "ix_cases_to_review_tenant_status",
        "cases_to_review",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cases_to_review_tenant_status",
        table_name="cases_to_review",
    )
    op.drop_index(
        "uq_cases_to_review_dedup",
        table_name="cases_to_review",
    )
    op.drop_table("cases_to_review")
