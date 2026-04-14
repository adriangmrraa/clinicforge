"""
053: Create clinic_operational_rules table for temporary/strategic rules
that modify AI agent behavior dynamically (scheduling restrictions,
operational conditions, etc.)
"""

revision = "053"
down_revision = "052"


def upgrade():
    from alembic import op
    import sqlalchemy as sa
    from sqlalchemy.dialects.postgresql import JSONB

    op.create_table(
        "clinic_operational_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_name", sa.String(150), nullable=False),
        sa.Column("rule_type", sa.String(30), nullable=False),  # 'temporary', 'strategic', 'scheduling'
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("prompt_injection", sa.Text, nullable=False),  # The actual text injected into AI prompt
        sa.Column("applies_to", sa.ARRAY(sa.String), nullable=False, server_default="{}"),  # ['tora','nova','multi','social'] or ['all']
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),  # NULL = immediate
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),  # NULL = permanent
        sa.Column("priority_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_operational_rules_tenant", "clinic_operational_rules", ["tenant_id"])
    op.create_index("idx_operational_rules_tenant_active", "clinic_operational_rules", ["tenant_id", "is_active"])


def downgrade():
    from alembic import op
    op.drop_table("clinic_operational_rules")
