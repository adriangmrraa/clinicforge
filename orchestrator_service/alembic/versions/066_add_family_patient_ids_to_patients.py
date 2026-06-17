"""066 - Add family_patient_ids to patients table

Adds family_patient_ids INTEGER[] nullable column with GIN index
so the Clinical Context endpoint can read linked family members
directly from the patient record (not just from chat_conversations).

Revision ID: 066
Revises: 065
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa


revision = "066"
down_revision = "065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("family_patient_ids", sa.ARRAY(sa.Integer()), nullable=True),
    )
    op.create_index(
        "ix_patients_family_patient_ids_gin",
        "patients",
        ["family_patient_ids"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_patients_family_patient_ids_gin",
        table_name="patients",
    )
    op.drop_column("patients", "family_patient_ids")
