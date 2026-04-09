"""041 - Add consultation fields for high-ticket treatments

Adds per-treatment consultation configuration so high-ticket treatments
(implants, surgery, whitening) can book a short evaluation first.

Columns added to treatment_types:
- is_high_ticket: marks treatment as requiring prior consultation
- consultation_duration_minutes: duration of the evaluation (default 30)
- consultation_requirements: what patient needs for the consultation
- consultation_notes: internal notes for the professional
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "041_consultation_ht"
down_revision = "040_add_social_ig_fields"
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:table AND column_name=:col)"
        ),
        {"table": table, "col": column},
    )
    return result.scalar()


def upgrade():
    conn = op.get_bind()

    if not _column_exists(conn, "treatment_types", "is_high_ticket"):
        op.add_column(
            "treatment_types",
            sa.Column(
                "is_high_ticket",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
        print("✅ Added is_high_ticket column to treatment_types")
    else:
        print("ℹ️  is_high_ticket already exists — skipping")

    if not _column_exists(conn, "treatment_types", "consultation_duration_minutes"):
        op.add_column(
            "treatment_types",
            sa.Column(
                "consultation_duration_minutes",
                sa.Integer(),
                nullable=True,
                server_default=sa.text("30"),
            ),
        )
        print("✅ Added consultation_duration_minutes column to treatment_types")
    else:
        print("ℹ️  consultation_duration_minutes already exists — skipping")

    if not _column_exists(conn, "treatment_types", "consultation_requirements"):
        op.add_column(
            "treatment_types",
            sa.Column("consultation_requirements", sa.Text(), nullable=True),
        )
        print("✅ Added consultation_requirements column to treatment_types")
    else:
        print("ℹ️  consultation_requirements already exists — skipping")

    if not _column_exists(conn, "treatment_types", "consultation_notes"):
        op.add_column(
            "treatment_types",
            sa.Column("consultation_notes", sa.Text(), nullable=True),
        )
        print("✅ Added consultation_notes column to treatment_types")
    else:
        print("ℹ️  consultation_notes already exists — skipping")


def downgrade():
    conn = op.get_bind()
    for col in [
        "consultation_notes",
        "consultation_requirements",
        "consultation_duration_minutes",
        "is_high_ticket",
    ]:
        if _column_exists(conn, "treatment_types", col):
            op.drop_column("treatment_types", col)
            print(f"✅ Dropped {col} from treatment_types")
