"""076: prioridad en Pendientes (urgente / media / tranqui).

Pedido Carlos 2026-07-16: las derivaciones del bot nacen URGENTES (Paula no
entra al mail — el pendiente es el canal real), los chats colgados MEDIA,
y lo manual lo elige el usuario (default media).

Revision ID: 076
Revises: 075
"""

from alembic import op
import sqlalchemy as sa

revision = "076"
down_revision = "075"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "clinic_pendings",
        sa.Column(
            "priority",
            sa.String(10),
            nullable=False,
            server_default=sa.text("'media'"),
        ),
    )
    op.create_check_constraint(
        "ck_clinic_pendings_priority",
        "clinic_pendings",
        "priority IN ('urgente','media','tranqui')",
    )


def downgrade():
    op.drop_constraint("ck_clinic_pendings_priority", "clinic_pendings", type_="check")
    op.drop_column("clinic_pendings", "priority")
