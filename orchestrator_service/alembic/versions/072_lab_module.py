"""072 — Módulo Laboratorio (F2-4 L1): labs + lab_cases

Tablero de trabajos de laboratorio con estados
(pendiente_envio → enviado → recibido → a_ajustar → colocado / cancelado),
fechas del ciclo, contador de re-trabajos y costo/pago al lab.

Revision ID: 072
Revises: 071
"""

from alembic import op
import sqlalchemy as sa

revision = "072"
down_revision = "071"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "labs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_labs_tenant_name"),
    )
    op.create_index("idx_labs_tenant", "labs", ["tenant_id"])

    op.create_table(
        "lab_cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "professional_id",
            sa.Integer(),
            sa.ForeignKey("professionals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "lab_id",
            sa.Integer(),
            sa.ForeignKey("labs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("work_type", sa.String(80), nullable=False),
        sa.Column("tooth_numbers", sa.String(120), nullable=True),
        sa.Column("shade", sa.String(40), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="pendiente_envio",
        ),
        sa.Column("sent_at", sa.Date(), nullable=True),
        sa.Column("promised_at", sa.Date(), nullable=True),
        sa.Column("received_at", sa.Date(), nullable=True),
        sa.Column("tried_at", sa.Date(), nullable=True),
        sa.Column("placed_at", sa.Date(), nullable=True),
        sa.Column(
            "rework_count", sa.Integer(), nullable=False, server_default="0"
        ),
        # Referencias sueltas a turnos (sin FK: appointments.id es UUID texto
        # y el turno puede borrarse sin romper el historial del lab)
        sa.Column("origin_appointment_id", sa.String(64), nullable=True),
        sa.Column("placement_appointment_id", sa.String(64), nullable=True),
        sa.Column("cost", sa.DECIMAL(12, 2), nullable=True),
        sa.Column(
            "lab_paid", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN ('pendiente_envio','enviado','recibido','a_ajustar',"
            "'colocado','cancelado')",
            name="ck_lab_cases_status",
        ),
    )
    op.create_index(
        "idx_lab_cases_tenant_status", "lab_cases", ["tenant_id", "status"]
    )
    op.create_index(
        "idx_lab_cases_tenant_patient", "lab_cases", ["tenant_id", "patient_id"]
    )


def downgrade():
    op.drop_index("idx_lab_cases_tenant_patient", table_name="lab_cases")
    op.drop_index("idx_lab_cases_tenant_status", table_name="lab_cases")
    op.drop_table("lab_cases")
    op.drop_index("idx_labs_tenant", table_name="labs")
    op.drop_table("labs")
