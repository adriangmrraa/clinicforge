"""
057: Add patient_source column to patients.

Adds:
- patient_source (VARCHAR 20, NOT NULL, default 'regular') to patients
  Values: 'regular' | 'art' | 'minor' | 'third_party'
  Used to identify patients derived from ART (Aseguradora de Riesgos del Trabajo)
  or other special intake flows.
"""

revision = "057"
down_revision = "056"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    op.add_column(
        "patients",
        sa.Column(
            "patient_source",
            sa.String(20),
            nullable=False,
            server_default="regular",
        ),
    )
    op.create_index(
        "idx_patients_source",
        "patients",
        ["patient_source"],
        postgresql_where=sa.text("patient_source != 'regular'"),
    )


def downgrade():
    from alembic import op

    op.drop_index("idx_patients_source", table_name="patients")
    op.drop_column("patients", "patient_source")
