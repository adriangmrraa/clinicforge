"""042 - Seña guardrails: expiration + unpaid limits

Adds columns for appointment seña (deposit) protection:
- tenants.sena_expiration_hours: auto-cancel unpaid after X hours (default 24)
- tenants.max_unpaid_appointments: max pending seña per patient (default 1, 0=disabled)
- appointments.sena_expires_at: timestamp when unpaid appointment auto-cancels
- appointments.sena_amount: seña amount stamped at booking time
"""

from alembic import op
import sqlalchemy as sa


revision = "042_sena_guardrails"
down_revision = "041_consultation_ht"
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

    # Tenant config
    if not _column_exists(conn, "tenants", "sena_expiration_hours"):
        op.add_column(
            "tenants",
            sa.Column("sena_expiration_hours", sa.Integer(), nullable=True, server_default=sa.text("24")),
        )
        print("✅ Added sena_expiration_hours to tenants (default 24)")

    if not _column_exists(conn, "tenants", "max_unpaid_appointments"):
        op.add_column(
            "tenants",
            sa.Column("max_unpaid_appointments", sa.Integer(), nullable=True, server_default=sa.text("1")),
        )
        print("✅ Added max_unpaid_appointments to tenants (default 1)")

    # Appointment expiration
    if not _column_exists(conn, "appointments", "sena_expires_at"):
        op.add_column(
            "appointments",
            sa.Column("sena_expires_at", sa.DateTime(timezone=True), nullable=True),
        )
        # Partial index for the expiration job (only pending appointments)
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_appointments_sena_expiry "
            "ON appointments (sena_expires_at) "
            "WHERE sena_expires_at IS NOT NULL AND payment_status = 'pending' AND status IN ('scheduled', 'confirmed')"
        )
        print("✅ Added sena_expires_at to appointments + partial index")

    if not _column_exists(conn, "appointments", "sena_amount"):
        op.add_column(
            "appointments",
            sa.Column("sena_amount", sa.Numeric(12, 2), nullable=True),
        )
        print("✅ Added sena_amount to appointments")


def downgrade():
    conn = op.get_bind()
    for table, col in [
        ("appointments", "sena_amount"),
        ("appointments", "sena_expires_at"),
        ("tenants", "max_unpaid_appointments"),
        ("tenants", "sena_expiration_hours"),
    ]:
        if _column_exists(conn, table, col):
            if col == "sena_expires_at":
                op.execute("DROP INDEX IF EXISTS idx_appointments_sena_expiry")
            op.drop_column(table, col)
            print(f"✅ Dropped {col} from {table}")
