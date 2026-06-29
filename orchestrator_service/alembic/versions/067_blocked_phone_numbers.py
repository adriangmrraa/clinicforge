"""067 - Lista de bloqueo: tabla blocked_phone_numbers

Numeros que Paula (agente WhatsApp) NO debe contestar, por clinica.
Cada numero lleva una etiqueta y un comportamiento:
  - SILENCIO  -> el agente no responde nada (lo toma un humano)
  - MENSAJE   -> responde un texto fijo configurable UNA vez y entra en
                 enfriamiento (cooldown_hours) antes de poder volver a responder.
Opcionalmente notifica por mail al derivation_email del tenant cuando el numero
escribe (con su propio enfriamiento via last_notified_at).

Revision ID: 067
Revises: 066
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa


revision = "067"
down_revision = "066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blocked_phone_numbers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Telefono NORMALIZADO (solo digitos, sin +, sin espacios) para matchear confiable.
        sa.Column("phone_digits", sa.String(32), nullable=False),
        # Telefono tal cual lo cargaron (para mostrar en la UI).
        sa.Column("phone_display", sa.Text(), nullable=True),
        sa.Column("label", sa.String(30), nullable=False),
        sa.Column("behavior", sa.String(20), nullable=False),
        sa.Column("message_template", sa.Text(), nullable=True),
        sa.Column(
            "notify_email",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "cooldown_hours",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("24"),
        ),
        sa.Column("last_autoreply_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "label IN ('profesional_clinica','inconveniente_ia','laboratorio','proveedor','otros','spam')",
            name="ck_blocked_phone_numbers_label",
        ),
        sa.CheckConstraint(
            "behavior IN ('SILENCIO','MENSAJE')",
            name="ck_blocked_phone_numbers_behavior",
        ),
    )
    # Un mismo numero no se carga dos veces en la misma clinica.
    op.create_index(
        "uq_blocked_phone_numbers_tenant_phone",
        "blocked_phone_numbers",
        ["tenant_id", "phone_digits"],
        unique=True,
    )
    # Lookup rapido al ingresar un mensaje.
    op.create_index(
        "ix_blocked_phone_numbers_tenant_active",
        "blocked_phone_numbers",
        ["tenant_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_blocked_phone_numbers_tenant_active",
        table_name="blocked_phone_numbers",
    )
    op.drop_index(
        "uq_blocked_phone_numbers_tenant_phone",
        table_name="blocked_phone_numbers",
    )
    op.drop_table("blocked_phone_numbers")
