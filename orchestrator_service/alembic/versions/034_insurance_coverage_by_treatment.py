"""034 - Insurance coverage by treatment (structured JSONB)

Revision ID: 034
Revises: 033
Create Date: 2026-04-08

Replaces the flat `restrictions TEXT` column on `tenant_insurance_providers`
with a structured `coverage_by_treatment JSONB` column keyed by treatment
code. Each entry carries copay %, pre-authorization requirements, waiting
period, annual cap, and notes. Also adds 3 top-level columns: `is_prepaid`,
`employee_discount_percent`, `default_copay_percent`.

Closes the gap where the AI agent could only answer "do you accept OSDE?"
but not "what's my copay for an implant?" or "do I need pre-authorization?".

Backwards compat: legacy `restrictions` JSON arrays are migrated to
`coverage_by_treatment` dicts with `covered=true` defaults. Rows with
NULL or unparseable `restrictions` get `coverage_by_treatment = {}`.
The downgrade reverses this by extracting `covered=true` codes back to
a JSON array string and restoring the `restrictions` column.

The conversion logic is exposed as two pure functions
(`_migrate_restrictions_to_coverage`, `_migrate_coverage_to_restrictions`)
so it can be unit-tested without a live DB.
"""

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


# -----------------------------------------------------------------------------
# Pure functions (exported for unit testing — no DB I/O)
# -----------------------------------------------------------------------------

def _default_coverage_entry() -> dict:
    """Default values for a covered treatment entry."""
    return {
        "covered": True,
        "copay_percent": 0.0,
        "requires_pre_authorization": False,
        "pre_auth_leadtime_days": 0,
        "waiting_period_days": 0,
        "max_annual_coverage": None,
        "notes": "",
    }


def _migrate_restrictions_to_coverage(restrictions_val) -> dict:
    """
    Convert a legacy `restrictions` value (JSON array string or None) into
    a `coverage_by_treatment` dict.

    - None, empty string, or unparseable input → `{}`
    - Valid JSON array of strings → dict with each code as a covered entry
    - Non-list JSON or mixed content → `{}`
    """
    if not restrictions_val:
        return {}
    try:
        codes = json.loads(restrictions_val) if isinstance(restrictions_val, str) else restrictions_val
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(codes, list):
        return {}
    coverage = {}
    for code in codes:
        if isinstance(code, str) and code.strip():
            coverage[code.strip()] = _default_coverage_entry()
    return coverage


def _migrate_coverage_to_restrictions(coverage_val) -> str | None:
    """
    Reverse of `_migrate_restrictions_to_coverage`. Extract only the
    `covered=true` treatment codes and return them as a JSON array string.
    Returns None if there are no covered codes (preserves NULL in DB).
    """
    if not coverage_val:
        return None
    coverage = coverage_val
    if isinstance(coverage, str):
        try:
            coverage = json.loads(coverage)
        except (json.JSONDecodeError, TypeError):
            return None
    if not isinstance(coverage, dict):
        return None
    codes = [
        k for k, v in coverage.items()
        if isinstance(v, dict) and v.get("covered", False)
    ]
    return json.dumps(codes) if codes else None


# -----------------------------------------------------------------------------
# Alembic upgrade / downgrade
# -----------------------------------------------------------------------------

def upgrade() -> None:
    # 1. Add new columns (additive first — safe if re-run)
    op.add_column(
        "tenant_insurance_providers",
        sa.Column(
            "coverage_by_treatment",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "tenant_insurance_providers",
        sa.Column(
            "is_prepaid",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "tenant_insurance_providers",
        sa.Column(
            "employee_discount_percent",
            sa.Numeric(5, 2),
            nullable=True,
        ),
    )
    op.add_column(
        "tenant_insurance_providers",
        sa.Column(
            "default_copay_percent",
            sa.Numeric(5, 2),
            nullable=True,
        ),
    )

    # 2. Data migration: convert existing restrictions arrays into coverage dicts
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, restrictions FROM tenant_insurance_providers")
    ).fetchall()
    for row in rows:
        # Alembic may return Row or dict depending on SQLAlchemy version
        row_id = row[0] if hasattr(row, "__getitem__") else row.id
        restrictions_val = row[1] if hasattr(row, "__getitem__") else row.restrictions
        coverage = _migrate_restrictions_to_coverage(restrictions_val)
        conn.execute(
            sa.text(
                "UPDATE tenant_insurance_providers "
                "SET coverage_by_treatment = CAST(:cov AS jsonb) WHERE id = :id"
            ),
            {"cov": json.dumps(coverage), "id": row_id},
        )

    # 3. Drop the legacy restrictions column
    op.drop_column("tenant_insurance_providers", "restrictions")


def downgrade() -> None:
    # 1. Restore the legacy restrictions column as nullable TEXT
    op.add_column(
        "tenant_insurance_providers",
        sa.Column("restrictions", sa.Text, nullable=True),
    )

    # 2. Reverse data migration: extract covered=true codes back to JSON array
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, coverage_by_treatment FROM tenant_insurance_providers")
    ).fetchall()
    for row in rows:
        row_id = row[0] if hasattr(row, "__getitem__") else row.id
        coverage_val = row[1] if hasattr(row, "__getitem__") else row.coverage_by_treatment
        restrictions_val = _migrate_coverage_to_restrictions(coverage_val)
        conn.execute(
            sa.text(
                "UPDATE tenant_insurance_providers "
                "SET restrictions = :r WHERE id = :id"
            ),
            {"r": restrictions_val, "id": row_id},
        )

    # 3. Drop new columns
    op.drop_column("tenant_insurance_providers", "coverage_by_treatment")
    op.drop_column("tenant_insurance_providers", "is_prepaid")
    op.drop_column("tenant_insurance_providers", "employee_discount_percent")
    op.drop_column("tenant_insurance_providers", "default_copay_percent")
