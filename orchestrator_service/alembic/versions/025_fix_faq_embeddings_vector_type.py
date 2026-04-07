"""025 - Fix faq_embeddings.embedding column type (bytea → vector)

Revision ID: 025
Revises: 024
Create Date: 2026-04-07

Migration 009 created the embedding column as LargeBinary (bytea) and then tried
to ALTER it to vector(1536) inside a try/except that silently swallowed errors.
For tenants where the ALTER failed (e.g. pgvector installed AFTER the initial
migration ran), the column stayed as bytea forever, breaking RAG with errors like:

  - "operator does not exist: bytea <=> vector"
  - "cannot cast type bytea to vector"
  - "operator does not exist: bytea <=> unknown"

This migration:
1. Detects if pgvector is available
2. Detects if faq_embeddings.embedding (and document_embeddings.embedding) are bytea
3. If yes: TRUNCATEs the existing embeddings (not recoverable from bytea anyway)
   and ALTERs the column to vector(1536)
4. Creates the ivfflat index for fast similarity search

After this migration, FAQ embeddings will be regenerated automatically by the
startup sync (sync_all_tenants_faq_embeddings) or on-demand by upsert hooks.
"""
from alembic import op
from sqlalchemy import text

# revision identifiers
revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def _has_pgvector(conn) -> bool:
    try:
        result = conn.execute(text(
            "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
        ))
        return result.fetchone() is not None
    except Exception:
        return False


def _column_type(conn, table: str, column: str) -> str:
    try:
        result = conn.execute(text("""
            SELECT data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = :table AND column_name = :column
        """), {"table": table, "column": column})
        row = result.fetchone()
        if not row:
            return ""
        # udt_name is more specific (e.g. 'vector' for pgvector, 'bytea' for bytea)
        return (row[1] or row[0] or "").lower()
    except Exception:
        return ""


def _index_exists(conn, index_name: str) -> bool:
    try:
        result = conn.execute(text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :name"
        ), {"name": index_name})
        return result.fetchone() is not None
    except Exception:
        return False


def upgrade():
    conn = op.get_bind()

    if not _has_pgvector(conn):
        print("⚠️ pgvector extension not available — skipping migration 025")
        return

    # ─────────────────────────────────────────────────
    # FAQ embeddings
    # ─────────────────────────────────────────────────
    faq_col_type = _column_type(conn, "faq_embeddings", "embedding")
    print(f"📋 faq_embeddings.embedding current type: {faq_col_type}")

    if faq_col_type == "bytea":
        print("🔧 Migrating faq_embeddings.embedding from bytea to vector(1536)")
        # Drop old index if exists
        try:
            op.execute("DROP INDEX IF EXISTS idx_faq_embeddings_vector")
        except Exception as e:
            print(f"  drop index warning: {e}")

        # Truncate (data not recoverable from bytea — will be re-embedded by sync)
        op.execute("TRUNCATE TABLE faq_embeddings")
        print("  truncated faq_embeddings (will be re-embedded on next startup sync)")

        # Alter column type
        op.execute("ALTER TABLE faq_embeddings ALTER COLUMN embedding TYPE vector(1536) USING NULL")
        print("  ✅ faq_embeddings.embedding is now vector(1536)")
    elif faq_col_type == "vector":
        print("✅ faq_embeddings.embedding already vector — no migration needed")
    else:
        print(f"⚠️ faq_embeddings.embedding has unexpected type '{faq_col_type}' — skipping")

    # Create ivfflat index if missing
    if not _index_exists(conn, "idx_faq_embeddings_vector"):
        try:
            op.execute("""
                CREATE INDEX idx_faq_embeddings_vector ON faq_embeddings
                USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
            """)
            print("  ✅ created idx_faq_embeddings_vector (ivfflat cosine)")
        except Exception as e:
            print(f"  ⚠️ ivfflat index creation skipped: {e}")

    # ─────────────────────────────────────────────────
    # Document embeddings (same fix)
    # ─────────────────────────────────────────────────
    doc_col_type = _column_type(conn, "document_embeddings", "embedding")
    print(f"📋 document_embeddings.embedding current type: {doc_col_type}")

    if doc_col_type == "bytea":
        print("🔧 Migrating document_embeddings.embedding from bytea to vector(1536)")
        try:
            op.execute("DROP INDEX IF EXISTS idx_doc_embeddings_vector")
        except Exception as e:
            print(f"  drop index warning: {e}")

        op.execute("TRUNCATE TABLE document_embeddings")
        print("  truncated document_embeddings")

        op.execute("ALTER TABLE document_embeddings ALTER COLUMN embedding TYPE vector(1536) USING NULL")
        print("  ✅ document_embeddings.embedding is now vector(1536)")
    elif doc_col_type == "vector":
        print("✅ document_embeddings.embedding already vector — no migration needed")

    if not _index_exists(conn, "idx_doc_embeddings_vector"):
        try:
            op.execute("""
                CREATE INDEX idx_doc_embeddings_vector ON document_embeddings
                USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
            """)
            print("  ✅ created idx_doc_embeddings_vector (ivfflat cosine)")
        except Exception as e:
            print(f"  ⚠️ ivfflat index creation skipped: {e}")


def downgrade():
    # No downgrade — bytea is the broken state we're fixing
    pass
