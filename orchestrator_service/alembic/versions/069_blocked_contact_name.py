"""069 - Lista de bloqueo: nombre/identidad del contacto

Agrega blocked_phone_numbers.contact_name para identificar a QUIEN pertenece el
numero (ej: "Laboratorio Central", "Dra. Maria Gomez"), porque solo con el numero
la lista no se entiende. La descripcion libre ya existe en la columna `note`.

Revision ID: 069
Revises: 068
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa


revision = "069"
down_revision = "068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "blocked_phone_numbers",
        sa.Column("contact_name", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("blocked_phone_numbers", "contact_name")
