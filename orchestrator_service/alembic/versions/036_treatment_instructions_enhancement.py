"""036 - Treatment pre/post instructions enhancement (TEXT→JSONB structured)

Revision ID: 036
Revises: 034
Create Date: 2026-04-08

Enhances the existing `treatment_types.pre_instructions` and
`treatment_types.post_instructions` columns so the AI agent can answer
structured pre- and post-treatment queries (debilidad #2 del prompt).

Changes:
1. `pre_instructions` TEXT → JSONB. Legacy plain-text values are wrapped
   into `{"general_notes": "<original text>"}` so they remain readable
   by the backwards-compat path in get_treatment_instructions.
2. `post_instructions` already JSONB, but legacy rows stored an array
   of `{timing, content}` timed-sequence dicts. This migration wraps
   those arrays into `{"general_notes": "<serialized array>"}` so the
   column can also hold the new structured recovery-protocol dict
   shape (`care_duration_days`, `dietary_restrictions`, `alarm_symptoms`,
   etc.) going forward.
3. `followup_template` is NOT touched. `followups.py` reads it as-is.

Merge-order note: `down_revision = "034"` because this migration was
written while payment-financing (035) is still in progress on a sibling
branch. If payment-financing merges to main BEFORE this pack, rebase
the branch and update `down_revision` to `"035"` before pushing. If
this pack merges first, payment-financing will need to bump its
revision to `"037"` and set `down_revision = "036"`.

Idempotency: the ALTER step checks the current column type via
`_column_type()` so a re-run on an already-migrated DB is a no-op.
The UPDATE steps use `WHERE` predicates that match only the legacy
shape, so re-running them does nothing.

Downgrade reverses both transforms and restores TEXT column type via
`->>'general_notes'` extraction.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "036"
down_revision = "034"
branch_labels = None
depends_on = None


def _column_type(conn, table: str, column: str) -> str | None:
    """Return the PostgreSQL data_type of a column, or None if missing.

    Reused pattern from migration 012 (add_clinical_rules_engine) so this
    migration is idempotent — safe to re-run against a DB that has already
    been upgraded.
    """
    row = conn.execute(
        sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).fetchone()
    return row[0] if row else None


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: Wrap legacy TEXT pre_instructions into JSON objects. This must
    # happen BEFORE the ALTER TYPE because raw strings like "Ayunar 6 horas"
    # are not valid JSON and would fail the `::jsonb` USING cast. After this
    # UPDATE, every non-null row holds a valid JSON string of the form
    # '{"general_notes": "Ayunar 6 horas"}'.
    #
    # Skip the UPDATE if the column is already JSONB (idempotent re-run).
    current_type = _column_type(conn, "treatment_types", "pre_instructions")
    if current_type != "jsonb":
        conn.execute(
            sa.text(
                """
                UPDATE treatment_types
                SET pre_instructions = jsonb_build_object(
                    'general_notes', pre_instructions
                )::text
                WHERE pre_instructions IS NOT NULL
                """
            )
        )

        # Step 2: ALTER TYPE TEXT → JSONB. The USING cast is safe now that
        # every non-null row holds a valid JSON object string.
        op.alter_column(
            "treatment_types",
            "pre_instructions",
            type_=JSONB(),
            postgresql_using="pre_instructions::jsonb",
            existing_nullable=True,
        )

    # Step 3: Wrap legacy post_instructions arrays into dicts with
    # general_notes. Only affects rows where the JSONB value is an array
    # (the old timed-sequence shape). New dict rows and NULL rows are
    # left untouched. This is also idempotent because the WHERE predicate
    # filters out rows that are already dicts.
    conn.execute(
        sa.text(
            """
            UPDATE treatment_types
            SET post_instructions = jsonb_build_object(
                'general_notes', post_instructions::text
            )
            WHERE post_instructions IS NOT NULL
              AND jsonb_typeof(post_instructions) = 'array'
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Step 1: Unwrap post_instructions rows that were originally arrays.
    # Identify them by the presence of general_notes whose value parses
    # back to a JSON array. Leave new structured-dict rows untouched —
    # they will be lost on downgrade (acceptable: the feature doesn't
    # exist in the pre-036 schema).
    conn.execute(
        sa.text(
            """
            UPDATE treatment_types
            SET post_instructions = (post_instructions->>'general_notes')::jsonb
            WHERE post_instructions IS NOT NULL
              AND jsonb_typeof(post_instructions) = 'object'
              AND post_instructions ? 'general_notes'
              AND jsonb_typeof(
                  ((post_instructions->>'general_notes'))::jsonb
              ) = 'array'
            """
        )
    )

    # Step 2: ALTER TYPE JSONB → TEXT, extracting general_notes back to
    # raw text. Non-general_notes dict rows (e.g. new structured shape)
    # will become NULL because the extraction returns NULL. This is a
    # lossy downgrade by design — the pre-036 schema cannot hold
    # structured data.
    current_type = _column_type(conn, "treatment_types", "pre_instructions")
    if current_type == "jsonb":
        op.alter_column(
            "treatment_types",
            "pre_instructions",
            type_=sa.Text(),
            postgresql_using="pre_instructions->>'general_notes'",
            existing_nullable=True,
        )
