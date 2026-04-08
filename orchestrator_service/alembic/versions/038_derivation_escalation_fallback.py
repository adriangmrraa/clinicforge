"""038 - Derivation escalation fallback

Revision ID: 038
Revises: 037
Create Date: 2026-04-08

Adds 6 columns to `professional_derivation_rules` so a derivation rule
can escalate to a secondary professional (or to the whole team) when
the primary has no slots within a configurable wait window.

New columns:
- enable_escalation BOOLEAN NOT NULL DEFAULT false — master toggle
- fallback_professional_id INTEGER NULL FK professionals(id) ON DELETE SET NULL
- fallback_team_mode BOOLEAN NOT NULL DEFAULT false — if true, fallback
  runs with no professional filter (all active professionals)
- max_wait_days_before_escalation INTEGER NOT NULL DEFAULT 7 — window
  used to check the primary before escalating
- escalation_message_template TEXT NULL — optional Spanish template
  shown to the patient when escalation triggers. Supports {primary}
  and {fallback} placeholders resolved at prompt/tool time.
- criteria_custom JSONB NULL — reserved for future filters (urgency
  level, patient history). Documented but no runtime consumer yet.

Idempotency: each column is added only if missing via information_schema.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def _existing_columns(conn) -> set[str]:
    rows = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'professional_derivation_rules'"
        )
    ).fetchall()
    return {r[0] for r in rows}


def upgrade() -> None:
    conn = op.get_bind()
    existing = _existing_columns(conn)

    if "enable_escalation" not in existing:
        op.add_column(
            "professional_derivation_rules",
            sa.Column(
                "enable_escalation",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if "fallback_professional_id" not in existing:
        op.add_column(
            "professional_derivation_rules",
            sa.Column("fallback_professional_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_derivation_fallback_professional",
            "professional_derivation_rules",
            "professionals",
            ["fallback_professional_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "fallback_team_mode" not in existing:
        op.add_column(
            "professional_derivation_rules",
            sa.Column(
                "fallback_team_mode",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if "max_wait_days_before_escalation" not in existing:
        op.add_column(
            "professional_derivation_rules",
            sa.Column(
                "max_wait_days_before_escalation",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("7"),
            ),
        )
    if "escalation_message_template" not in existing:
        op.add_column(
            "professional_derivation_rules",
            sa.Column("escalation_message_template", sa.Text(), nullable=True),
        )
    if "criteria_custom" not in existing:
        op.add_column(
            "professional_derivation_rules",
            sa.Column("criteria_custom", postgresql.JSONB(), nullable=True),
        )


def downgrade() -> None:
    try:
        op.drop_constraint(
            "fk_derivation_fallback_professional",
            "professional_derivation_rules",
            type_="foreignkey",
        )
    except Exception:
        pass
    op.drop_column("professional_derivation_rules", "criteria_custom")
    op.drop_column("professional_derivation_rules", "escalation_message_template")
    op.drop_column("professional_derivation_rules", "max_wait_days_before_escalation")
    op.drop_column("professional_derivation_rules", "fallback_team_mode")
    op.drop_column("professional_derivation_rules", "fallback_professional_id")
    op.drop_column("professional_derivation_rules", "enable_escalation")
