"""add pgvector extension and faq_embeddings table

Revision ID: 009
Revises: 008
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = 'i9j0k1l2m3n4'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Try to enable pgvector — skip gracefully if not available
    has_vector = False
    try:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        has_vector = True
    except Exception:
        print("⚠️ pgvector extension not available — creating tables with BYTEA fallback. "
              "Install pgvector on PostgreSQL for vector search support.")

    # faq_embeddings
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

    # Only create vector columns and IVFFlat indexes if pgvector is available
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
            print(f"⚠️ Vector indexes not created: {e}")


def downgrade():
    op.drop_table('document_embeddings')
    op.drop_table('faq_embeddings')
    try:
        op.execute("DROP EXTENSION IF EXISTS vector")
    except Exception:
        pass
