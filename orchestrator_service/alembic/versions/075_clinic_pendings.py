"""075: modulo Pendientes con vencimiento (clinic_pendings).

Tareas/notas de la clinica con fecha limite, para que no se olviden chats
cuando interviene la secretaria (pedido Carlos 2026-07-16). El bot tambien
crea pendientes automaticos al derivar (derivhumano -> "seguir la derivacion",
vence en 24h) — cierra el hueco "la IA promete 'lo pase al equipo' y nadie sigue".

Nota de diseno: "vencido" NO es un estado almacenado — se deriva de
(status='abierto' AND due_at < NOW()) para no depender de un job que marque.

Revision ID: 075
Revises: 074
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "075"
down_revision = "074"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "clinic_pendings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        # Vencimiento (opcional): un pendiente sin fecha es una nota "cuando se pueda".
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(12),
            nullable=False,
            server_default=sa.text("'abierto'"),
        ),
        # Vinculos opcionales al chat/paciente que lo origino (para saltar directo).
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("assigned_to", sa.String(120), nullable=True),
        # 'staff' (panel) | 'bot' (auto-pendiente de derivhumano) | 'sistema'
        sa.Column(
            "created_by",
            sa.String(40),
            nullable=False,
            server_default=sa.text("'staff'"),
        ),
        # Origen puntual: 'manual' | 'chat' | 'derivhumano' | ...
        sa.Column("source", sa.String(40), nullable=True),
        # Dedupe del aviso Telegram al vencer (P2): se estampa al enviarlo.
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('abierto','hecho','cancelado')",
            name="ck_clinic_pendings_status",
        ),
    )
    op.create_index(
        "ix_clinic_pendings_tenant_status_due",
        "clinic_pendings",
        ["tenant_id", "status", "due_at"],
    )


def downgrade():
    op.drop_index("ix_clinic_pendings_tenant_status_due", table_name="clinic_pendings")
    op.drop_table("clinic_pendings")
