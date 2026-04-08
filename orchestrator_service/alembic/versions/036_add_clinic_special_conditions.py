"""add clinic special conditions to tenants

Revision ID: 036
Revises: 035
Create Date: 2026-04-08

Adds 8 columns to `tenants` to let clinics configure embarazo/pediatría/
alto riesgo policies + anamnesis-gate. Consumido por
`_format_special_conditions()` en main.py e inyectado en el system prompt.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {c["name"] for c in inspector.get_columns("tenants")}

    if "accepts_pregnant_patients" not in existing:
        op.add_column(
            "tenants",
            sa.Column(
                "accepts_pregnant_patients",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )

    if "pregnancy_restricted_treatments" not in existing:
        op.add_column(
            "tenants",
            sa.Column(
                "pregnancy_restricted_treatments",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )

    if "pregnancy_notes" not in existing:
        op.add_column(
            "tenants",
            sa.Column("pregnancy_notes", sa.Text(), nullable=True),
        )

    if "accepts_pediatric" not in existing:
        op.add_column(
            "tenants",
            sa.Column(
                "accepts_pediatric",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )

    if "min_pediatric_age_years" not in existing:
        op.add_column(
            "tenants",
            sa.Column("min_pediatric_age_years", sa.Integer(), nullable=True),
        )

    if "pediatric_notes" not in existing:
        op.add_column(
            "tenants",
            sa.Column("pediatric_notes", sa.Text(), nullable=True),
        )

    if "high_risk_protocols" not in existing:
        op.add_column(
            "tenants",
            sa.Column(
                "high_risk_protocols",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    if "requires_anamnesis_before_booking" not in existing:
        op.add_column(
            "tenants",
            sa.Column(
                "requires_anamnesis_before_booking",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    for col in [
        "requires_anamnesis_before_booking",
        "high_risk_protocols",
        "pediatric_notes",
        "min_pediatric_age_years",
        "accepts_pediatric",
        "pregnancy_notes",
        "pregnancy_restricted_treatments",
        "accepts_pregnant_patients",
    ]:
        try:
            op.drop_column("tenants", col)
        except Exception:
            pass
