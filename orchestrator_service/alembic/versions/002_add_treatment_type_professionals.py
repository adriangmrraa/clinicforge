"""Add treatment_type_professionals junction table

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-20

Many-to-many relationship between treatment_types and professionals.
Backward compatible: if a treatment has no assigned professionals, all can perform it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, Sequence[str]] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS treatment_type_professionals (
        id              SERIAL PRIMARY KEY,
        tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        treatment_type_id INTEGER NOT NULL REFERENCES treatment_types(id) ON DELETE CASCADE,
        professional_id   INTEGER NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(tenant_id, treatment_type_id, professional_id)
    );
    CREATE INDEX IF NOT EXISTS idx_ttp_tenant ON treatment_type_professionals(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_ttp_treatment ON treatment_type_professionals(treatment_type_id);
    CREATE INDEX IF NOT EXISTS idx_ttp_professional ON treatment_type_professionals(professional_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS treatment_type_professionals;")
