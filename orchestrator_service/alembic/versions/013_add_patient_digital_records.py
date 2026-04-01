"""add patient_digital_records table for AI-generated clinical documents

Revision ID: 013
Revises: 012
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = 'r3s4t5u6v7w8'
down_revision = 'q2r3s4t5u6v7'
branch_labels = None
depends_on = None


def _table_exists(conn, table):
    try:
        result = conn.execute(text(
            f"SELECT 1 FROM information_schema.tables "
            f"WHERE table_name = '{table}'"
        ))
        return result.fetchone() is not None
    except Exception:
        return False


def upgrade():
    conn = op.get_bind()

    if not _table_exists(conn, 'patient_digital_records'):
        op.create_table(
            'patient_digital_records',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
            sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('professional_id', sa.Integer(), sa.ForeignKey('professionals.id', ondelete='SET NULL'), nullable=True),
            sa.Column('template_type', sa.String(50), nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('html_content', sa.Text(), nullable=False, server_default=''),
            sa.Column('pdf_path', sa.String(500), nullable=True),
            sa.Column('pdf_generated_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('source_data', JSONB(), nullable=False, server_default='{}'),
            sa.Column('generation_metadata', JSONB(), nullable=True, server_default='{}'),
            sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
            sa.Column('sent_to_email', sa.String(255), nullable=True),
            sa.Column('sent_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "status IN ('draft', 'final', 'sent')",
                name='ck_patient_digital_records_status'
            ),
            sa.CheckConstraint(
                "template_type IN ('clinical_report', 'post_surgery', 'odontogram_art', 'authorization_request')",
                name='ck_patient_digital_records_template_type'
            ),
        )
        op.create_index(
            'idx_pdr_tenant_patient',
            'patient_digital_records',
            ['tenant_id', 'patient_id']
        )
        op.create_index(
            'idx_pdr_tenant',
            'patient_digital_records',
            ['tenant_id']
        )
        op.create_index(
            'idx_pdr_status',
            'patient_digital_records',
            ['tenant_id', 'status']
        )


def downgrade():
    try:
        op.drop_index('idx_pdr_status', table_name='patient_digital_records')
    except Exception:
        pass
    try:
        op.drop_index('idx_pdr_tenant', table_name='patient_digital_records')
    except Exception:
        pass
    try:
        op.drop_index('idx_pdr_tenant_patient', table_name='patient_digital_records')
    except Exception:
        pass
    try:
        op.drop_table('patient_digital_records')
    except Exception:
        pass
