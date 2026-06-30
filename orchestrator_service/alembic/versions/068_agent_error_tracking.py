"""068 - Agent error tracking: bandera de fallo del bot en chat_conversations

Blindaje "esto no puede pasar": cuando el motor del agente (TORA/SoloEngine) cae
con un error y el paciente quedaria en silencio, marcamos la conversacion con:
  - last_agent_error_at : timestamp del ultimo fallo (NULL = sin fallo / recuperado)
  - agent_error_reason  : motivo corto del fallo (para diagnostico)

Esto alimenta la marca ROJA "el bot fallo, requiere atencion humana" en el panel
de Chats y sirve de rate-limit para el email de alerta a la clinica.

Revision ID: 068
Revises: 067
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa


revision = "068"
down_revision = "067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_conversations",
        sa.Column("last_agent_error_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "chat_conversations",
        sa.Column("agent_error_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_conversations", "agent_error_reason")
    op.drop_column("chat_conversations", "last_agent_error_at")
