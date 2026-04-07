"""032 - Multi-agent system tables

Revision ID: 032
Revises: 031
Create Date: 2026-04-07

Creates tables for multi-agent system:
- patient_context_snapshots: LangGraph checkpoint storage
- agent_turn_log: Audit log for agent interactions

These tables enable the multi-agent engine to maintain conversation
state across turns and provide auditing/debugging capabilities.
"""

from alembic import op
import sqlalchemy as sa


revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Patient context snapshots (LangGraph checkpointer)
    op.execute(
        """
        CREATE TABLE patient_context_snapshots (
            id BIGSERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            phone_number TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            state JSONB NOT NULL,
            active_agent TEXT,
            hop_count INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (tenant_id, phone_number, thread_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_pcs_tenant_phone ON patient_context_snapshots (tenant_id, phone_number)"
    )
    op.execute("CREATE INDEX idx_pcs_thread ON patient_context_snapshots (thread_id)")

    # Agent turn log (audit trail)
    op.execute(
        """
        CREATE TABLE agent_turn_log (
            id BIGSERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            phone_number TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            tools_called JSONB,
            handoff_to TEXT,
            duration_ms INTEGER,
            model TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_atl_tenant_phone ON agent_turn_log (tenant_id, phone_number)"
    )
    op.execute("CREATE INDEX idx_atl_turn ON agent_turn_log (turn_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_turn_log")
    op.execute("DROP TABLE IF EXISTS patient_context_snapshots")
