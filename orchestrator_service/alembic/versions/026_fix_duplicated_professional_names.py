"""026 - Clean up duplicated professional names (Delgado Delgado Delgado bug)

Revision ID: 026
Revises: 025
Create Date: 2026-04-07

The update_professional endpoint had a bug where the frontend sent a 'name' field
containing "FirstName LastName", which got assigned entirely to the first_name column,
while last_name was left untouched. On every save, the full name was concatenated
to first_name again, producing values like:

  first_name = "Laura Delgado Delgado Delgado Delgado Delgado Delgado Delgado Delgado"
  last_name  = "Delgado"

This migration cleans up the corruption by:
1. Detecting any first_name that contains the last_name as a repeated suffix
2. Stripping the duplicates and keeping just the original first name
3. Same logic applied to professional_name columns in any other reference table is NOT
   needed because they are derived from the join, not stored separately.

After this migration, last_name remains unchanged (it was always correct).
The first_name is normalized to its original single occurrence.
"""
from alembic import op
from sqlalchemy import text

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Find professionals where first_name contains repeated copies of last_name
    rows = conn.execute(text("""
        SELECT id, first_name, last_name
        FROM professionals
        WHERE last_name IS NOT NULL
          AND last_name != ''
          AND first_name LIKE '%' || last_name || ' ' || last_name || '%'
    """)).fetchall()

    print(f"📋 Found {len(rows)} professionals with duplicated last_name in first_name")

    for row in rows:
        prof_id = row[0]
        first_name = row[1] or ""
        last_name = row[2] or ""

        # Strategy: split first_name by spaces, remove all trailing tokens that equal last_name,
        # and the cleaned result becomes the new first_name.
        tokens = first_name.split()
        # Remove trailing duplicates of last_name
        while tokens and tokens[-1] == last_name:
            tokens.pop()
        cleaned_first = " ".join(tokens).strip()

        # Edge case: if everything was last_name, preserve at least one word
        if not cleaned_first:
            cleaned_first = last_name

        if cleaned_first != first_name:
            print(f"  Fixing professional {prof_id}: '{first_name}' → '{cleaned_first}'")
            conn.execute(text("""
                UPDATE professionals
                SET first_name = :new_name, updated_at = NOW()
                WHERE id = :id
            """), {"new_name": cleaned_first, "id": prof_id})

    print("✅ Professional name cleanup complete")


def downgrade():
    # No downgrade — the corrupted state is the bug we're fixing
    pass
