"""add clinical rules engine: tenant_insurance_providers, professional_derivation_rules, treatment_types instructions

Revision ID: 012
Revises: 011
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = 'q2r3s4t5u6v7'
down_revision = 'p1q2r3s4t5u6'
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    try:
        result = conn.execute(text(
            f"SELECT 1 FROM information_schema.columns "
            f"WHERE table_name = '{table}' AND column_name = '{column}'"
        ))
        return result.fetchone() is not None
    except Exception:
        return False


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

    # 1. CREATE TABLE tenant_insurance_providers
    if not _table_exists(conn, 'tenant_insurance_providers'):
        op.create_table(
            'tenant_insurance_providers',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
            sa.Column('provider_name', sa.String(100), nullable=False),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('restrictions', sa.Text(), nullable=True),
            sa.Column('external_target', sa.Text(), nullable=True),
            sa.Column('requires_copay', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('copay_notes', sa.Text(), nullable=True),
            sa.Column('ai_response_template', sa.Text(), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
            sa.CheckConstraint(
                "status IN ('accepted', 'restricted', 'external_derivation', 'rejected')",
                name='ck_tenant_insurance_providers_status'
            ),
            sa.UniqueConstraint('tenant_id', 'provider_name', name='uq_tenant_insurance_providers_tenant_name'),
        )
        op.create_index(
            'idx_tenant_insurance_providers_tenant',
            'tenant_insurance_providers',
            ['tenant_id']
        )
        op.create_index(
            'idx_tenant_insurance_providers_tenant_active',
            'tenant_insurance_providers',
            ['tenant_id', 'is_active']
        )

    # 2. CREATE TABLE professional_derivation_rules
    if not _table_exists(conn, 'professional_derivation_rules'):
        op.create_table(
            'professional_derivation_rules',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
            sa.Column('rule_name', sa.String(100), nullable=False),
            sa.Column('patient_condition', sa.String(30), nullable=False),
            sa.Column('treatment_categories', ARRAY(sa.Text()), nullable=False, server_default='{}'),
            sa.Column('target_type', sa.String(30), nullable=False),
            sa.Column('target_professional_id', sa.Integer(), sa.ForeignKey('professionals.id', ondelete='SET NULL'), nullable=True),
            sa.Column('priority_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
            sa.CheckConstraint(
                "patient_condition IN ('new_patient', 'existing_patient', 'any')",
                name='ck_professional_derivation_rules_patient_condition'
            ),
            sa.CheckConstraint(
                "target_type IN ('specific_professional', 'priority_professional', 'team')",
                name='ck_professional_derivation_rules_target_type'
            ),
        )
        op.create_index(
            'idx_professional_derivation_rules_tenant',
            'professional_derivation_rules',
            ['tenant_id']
        )
        op.create_index(
            'idx_professional_derivation_rules_tenant_active',
            'professional_derivation_rules',
            ['tenant_id', 'is_active']
        )

    # 3. ALTER TABLE treatment_types — add pre_instructions, post_instructions, followup_template
    if not _column_exists(conn, 'treatment_types', 'pre_instructions'):
        op.add_column('treatment_types', sa.Column(
            'pre_instructions', sa.Text(), nullable=True
        ))

    if not _column_exists(conn, 'treatment_types', 'post_instructions'):
        op.add_column('treatment_types', sa.Column(
            'post_instructions', JSONB(), nullable=True
        ))

    if not _column_exists(conn, 'treatment_types', 'followup_template'):
        op.add_column('treatment_types', sa.Column(
            'followup_template', JSONB(), nullable=True
        ))


def downgrade():
    # Remove columns from treatment_types
    try:
        op.drop_column('treatment_types', 'followup_template')
    except Exception:
        pass
    try:
        op.drop_column('treatment_types', 'post_instructions')
    except Exception:
        pass
    try:
        op.drop_column('treatment_types', 'pre_instructions')
    except Exception:
        pass

    # Drop professional_derivation_rules
    try:
        op.drop_index('idx_professional_derivation_rules_tenant_active', table_name='professional_derivation_rules')
    except Exception:
        pass
    try:
        op.drop_index('idx_professional_derivation_rules_tenant', table_name='professional_derivation_rules')
    except Exception:
        pass
    try:
        op.drop_table('professional_derivation_rules')
    except Exception:
        pass

    # Drop tenant_insurance_providers
    try:
        op.drop_index('idx_tenant_insurance_providers_tenant_active', table_name='tenant_insurance_providers')
    except Exception:
        pass
    try:
        op.drop_index('idx_tenant_insurance_providers_tenant', table_name='tenant_insurance_providers')
    except Exception:
        pass
    try:
        op.drop_table('tenant_insurance_providers')
    except Exception:
        pass
