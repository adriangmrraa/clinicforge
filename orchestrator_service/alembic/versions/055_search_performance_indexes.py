"""
055: Add pg_trgm extension and GIN trigram indexes for search performance.

Adds:
- pg_trgm extension for trigram-based fuzzy text search
- GIN trigram indexes on patients.first_name and patients.last_name
  (enables fast ILIKE/similarity queries without full table scans)
- B-tree index on whatsapp_messages(patient_id)
  (missing FK index — fixes slow lookups by patient)
- B-tree index on agent_turn_log(tenant_id, created_at DESC)
  (speeds up per-tenant turn history queries)

Note: CONCURRENTLY is NOT used inside transactions. Alembic migrations
run inside a transaction by default, so we use regular CREATE INDEX.
For a live large table, run the CONCURRENTLY variants manually outside
the migration and skip this migration.
"""

revision = "055"
down_revision = "054"


def upgrade():
    from alembic import op

    # Enable pg_trgm extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # GIN trigram indexes for fast patient name search (ILIKE, similarity)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_patients_first_name_trgm "
        "ON patients USING gin(first_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_patients_last_name_trgm "
        "ON patients USING gin(last_name gin_trgm_ops)"
    )

    # B-tree index on whatsapp_messages(patient_id) — missing FK index
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_patient_id "
        "ON whatsapp_messages(patient_id)"
    )

    # Composite index on agent_turn_log for per-tenant time-ordered queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_turn_log_tenant_created "
        "ON agent_turn_log(tenant_id, created_at DESC)"
    )


def downgrade():
    from alembic import op

    op.execute("DROP INDEX IF EXISTS idx_agent_turn_log_tenant_created")
    op.execute("DROP INDEX IF EXISTS idx_whatsapp_messages_patient_id")
    op.execute("DROP INDEX IF EXISTS idx_patients_last_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_patients_first_name_trgm")
    # Note: we intentionally do NOT drop the pg_trgm extension on downgrade
    # because other migrations or user code may depend on it.
