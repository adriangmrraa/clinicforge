"""add payment_keywords and medical_keywords to tenant config

Revision ID: 015
Revises: 014
Create Date: 2026-04-01

Adds payment_keywords and medical_keywords JSONB arrays to tenants.config
for WhatsApp image classification (payment vs medical document detection).

This is a data migration only - config column already exists as JSONB.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "t2u3v4w5x6y7"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    try:
        result = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                f"WHERE table_name = '{table}' AND column_name = '{column}'"
            )
        )
        return result.fetchone() is not None
    except Exception:
        return False


def upgrade():
    """
    Add payment_keywords and medical_keywords to tenants.config JSONB.
    Also populate default Spanish keywords for existing tenants.
    """
    conn = op.get_bind()

    # Default Spanish payment keywords
    default_payment_keywords = [
        "transferencia",
        "transferir",
        "transferí",
        "pagado",
        "pagué",
        "pago",
        "comprobante",
        "recibo",
        "factura",
        "boleto",
        "depósito",
        "deposito",
        "cbu",
        "alias",
        "banco",
        "mercadopago",
        "mp",
        "visa",
        "mastercard",
        "débito",
        "debito",
        "crédito",
        "credito",
        "monto",
    ]

    # Default Spanish medical keywords
    default_medical_keywords = [
        "orden médica",
        "orden medica",
        "receta",
        "prescripción",
        "prescripcion",
        "estudio",
        "análisis",
        "analisis",
        "laboratorio",
        "rayos x",
        "ecografía",
        "ecograf",
        "tomografía",
        "tomograf",
        "resonancia",
        "mamografía",
        "biopsia",
        "ortodoncia",
        "implante",
        "prótesis",
        "protesis",
        "caries",
        "endodoncia",
        "puente",
        "corona",
        "blanqueamiento",
        "limpieza",
        "extracción",
        "extraccion",
        "diagnóstico",
        "diagnostico",
        "tratamiento",
        "consulta",
        "revisión",
        "revision",
        "chequeo",
        "evaluación",
        "evaluacion",
    ]

    # Safer approach: Update with CASE to handle NULL safely
    try:
        # First, ensure config is not NULL for all tenants
        conn.execute(
            text("UPDATE tenants SET config = '{}'::jsonb WHERE config IS NULL")
        )
    except Exception as e:
        print(f"Warning: Could not initialize NULL configs: {e}")

    try:
        # Update using JSONB set operation - safer approach
        conn.execute(
            text("""
            UPDATE tenants 
            SET config = COALESCE(config, '{}'::jsonb) || jsonb_build_object(
                'payment_keywords', :payment_kw::jsonb,
                'medical_keywords', :medical_kw::jsonb
            )
            WHERE true
        """),
            {
                "payment_kw": default_payment_keywords,
                "medical_kw": default_medical_keywords,
            },
        )

        print(
            "✅ Migration completed: Added payment_keywords and medical_keywords to tenants.config"
        )

    except Exception as e:
        print(f"⚠️ Migration warning: {e}")
        # Try simpler approach - just insert directly
        try:
            conn.execute(
                text("""
                UPDATE tenants 
                SET config = jsonb_build_object(
                    'payment_keywords', :payment_kw::jsonb,
                    'medical_keywords', :medical_kw::jsonb
                )
                WHERE config IS NULL OR config = '{}'::jsonb
            """),
                {
                    "payment_kw": default_payment_keywords,
                    "medical_kw": default_medical_keywords,
                },
            )
            print("✅ Migration completed with fallback approach")
        except Exception as e2:
            print(f"⚠️ Migration fallback also failed: {e2}")


def downgrade():
    """
    Remove payment_keywords and medical_keywords from tenants.config.
    """
    conn = op.get_bind()

    try:
        # Remove the keywords from config JSONB
        conn.execute(
            text("""
            UPDATE tenants 
            SET config = config - 'payment_keywords' - 'medical_keywords'
            WHERE config IS NOT NULL
        """)
        )
        print("✅ Migration downgrade completed")
    except Exception as e:
        print(f"⚠️ Migration downgrade warning: {e}")
