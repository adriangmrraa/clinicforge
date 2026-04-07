"""027 - Add UNIQUE constraint on appointments to prevent double-booking

Revision ID: 027
Revises: 026
Create Date: 2026-04-07

Adds a partial UNIQUE index on (professional_id, appointment_datetime) for active
appointments (status IN scheduled/confirmed). This prevents double-booking at the
DATABASE level — even if there's a race condition between check_availability and
book_appointment, PostgreSQL will reject the second INSERT with a uniqueness
violation that we can catch and handle.

Why partial index:
- Cancelled/no_show/completed appointments shouldn't block new bookings at the same time
- Using a WHERE clause restricts the constraint to active states only

This is the LAST line of defense against double-booking. Application code should
still use soft-locks + transactions, but if all of those fail, the DB protects us.
"""
from alembic import op
from sqlalchemy import text

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # First clean up any existing duplicates that would prevent the index creation
    # (defensive: in production there shouldn't be any, but just in case)
    duplicates = conn.execute(text("""
        SELECT professional_id, appointment_datetime, COUNT(*) as cnt
        FROM appointments
        WHERE status IN ('scheduled', 'confirmed')
          AND professional_id IS NOT NULL
        GROUP BY professional_id, appointment_datetime
        HAVING COUNT(*) > 1
    """)).fetchall()

    if duplicates:
        print(f"⚠️  Found {len(duplicates)} duplicate appointment slots — keeping oldest, marking newer as 'cancelled'")
        for dup in duplicates:
            prof_id = dup[0]
            apt_dt = dup[1]
            cnt = dup[2]
            print(f"  professional_id={prof_id} datetime={apt_dt} count={cnt}")
            # Keep the oldest (lowest id), cancel the rest
            conn.execute(text("""
                UPDATE appointments
                SET status = 'cancelled',
                    cancellation_reason = 'Auto-cancelled by migration 027 (duplicate slot)',
                    updated_at = NOW()
                WHERE id IN (
                    SELECT id FROM appointments
                    WHERE professional_id = :prof_id
                      AND appointment_datetime = :apt_dt
                      AND status IN ('scheduled', 'confirmed')
                    ORDER BY created_at ASC
                    OFFSET 1
                )
            """), {"prof_id": prof_id, "apt_dt": apt_dt})

    # Create the partial unique index
    conn.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_appointments_no_double_booking
        ON appointments (professional_id, appointment_datetime)
        WHERE status IN ('scheduled', 'confirmed') AND professional_id IS NOT NULL
    """))
    print("✅ Created partial UNIQUE index idx_appointments_no_double_booking")


def downgrade():
    conn = op.get_bind()
    conn.execute(text("DROP INDEX IF EXISTS idx_appointments_no_double_booking"))
