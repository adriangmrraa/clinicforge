"""add pgvector extension and faq_embeddings table

Revision ID: 009
Revises: 008
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect

revision = 'i9j0k1l2m3n4'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None


def _has_pgvector(conn):
    """Check if pgvector extension is available without breaking the transaction."""
    try:
        result = conn.execute(text(
            "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"
        ))
        return result.fetchone() is not None
    except Exception:
        return False


def _table_exists(conn, table_name):
    try:
        result = conn.execute(text(
            f"SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}'"
        ))
        return result.fetchone() is not None
    except Exception:
        return False


def upgrade():
    conn = op.get_bind()

    # Check if pgvector is available BEFORE trying to install it
    has_vector = _has_pgvector(conn)

    if has_vector:
        try:
            op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        except Exception as e:
            print(f"⚠️ Could not create vector extension: {e}")
            has_vector = False
    else:
        print("⚠️ pgvector not available on this PostgreSQL. Tables created with BYTEA fallback.")

    # faq_embeddings
    if not _table_exists(conn, 'faq_embeddings'):
        op.create_table(
            'faq_embeddings',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('faq_id', sa.Integer(), sa.ForeignKey('clinic_faqs.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('embedding', sa.LargeBinary(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index('idx_faq_embeddings_tenant', 'faq_embeddings', ['tenant_id'])

    # document_embeddings
    if not _table_exists(conn, 'document_embeddings'):
        op.create_table(
            'document_embeddings',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('source_type', sa.String(50), nullable=False),
            sa.Column('source_id', sa.Integer(), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('embedding', sa.LargeBinary(), nullable=False),
            sa.Column('metadata', sa.JSON(), server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint('source_type', 'source_id', name='uq_doc_embeddings_source'),
        )
        op.create_index('idx_doc_embeddings_tenant', 'document_embeddings', ['tenant_id'])

    # Vector columns + indexes only if pgvector available
    if has_vector:
        try:
            op.execute("ALTER TABLE faq_embeddings ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)")
            op.create_index(
                'idx_faq_embeddings_vector', 'faq_embeddings', ['embedding'],
                postgresql_using='ivfflat',
                postgresql_with={'lists': 100},
                postgresql_ops={'embedding': 'vector_cosine_ops'}
            )
            op.execute("ALTER TABLE document_embeddings ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)")
            op.create_index(
                'idx_doc_embeddings_vector', 'document_embeddings', ['embedding'],
                postgresql_using='ivfflat',
                postgresql_with={'lists': 100},
                postgresql_ops={'embedding': 'vector_cosine_ops'}
            )
        except Exception as e:
            print(f"⚠️ Vector indexes skipped: {e}")


def downgrade():
    try:
        op.drop_table('document_embeddings')
    except Exception:
        pass
    try:
        op.drop_table('faq_embeddings')
    except Exception:
        pass
    try:
        op.execute("DROP EXTENSION IF EXISTS vector")
    except Exception:
        pass
