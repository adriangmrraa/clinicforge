"""Add GIN trigram index on tenant_insurance_providers.provider_name

Enables fast trigram similarity matching (% operator) for fuzzy
health insurance name lookups. Supports DLD-87: "ISSN" should
match "Instituto de Seguridad Social del Neuquén".

Revision ID: 061
Revises: 060
"""
from alembic import op

revision = '061'
down_revision = '060'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_insurance_provider_name_trgm "
        "ON tenant_insurance_providers USING gin(provider_name gin_trgm_ops)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_insurance_provider_name_trgm")
