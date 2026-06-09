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
    # Fix collation version mismatch (idempotent — no-op if versions match)
    # Check if the current user is the owner of the current database or a superuser
    connection = op.get_bind()
    try:
        is_owner_or_superuser = connection.execute(
            "SELECT pg_catalog.pg_get_userbyid(d.datdba) = current_user OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_user AND rolsuper = true) "
            "FROM pg_catalog.pg_database d WHERE d.datname = current_database()"
        ).scalar()
        
        if is_owner_or_superuser:
            db_name = connection.execute("SELECT current_database()").scalar()
            op.execute(f"ALTER DATABASE {db_name} REFRESH COLLATION VERSION")
    except Exception as e:
        # If any check fails, do not block the migration
        print(f"Warning: Collation refresh skipped. Reason: {e}")

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_insurance_provider_name_trgm "
        "ON tenant_insurance_providers USING gin(provider_name gin_trgm_ops)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_insurance_provider_name_trgm")
