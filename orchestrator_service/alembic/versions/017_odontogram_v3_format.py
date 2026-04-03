"""odontogram_data column: document v3.0 format and add GIN index for future queries

Revision ID: 017
Revises: 016
Create Date: 2026-04-02

## Odontogram Data v3.0 Format

This migration is NON-DESTRUCTIVE. It does not modify the JSONB column or any existing data.
The v3.0 format is applied on-read via normalize_to_v3() in shared/odontogram_utils.py.

### v3.0 Schema (stored in clinical_records.odontogram_data)

    {
      "version": "3.0",
      "active_dentition": "permanente",   // "permanente" | "decidua"
      "permanente": {
        "<FDI>": {                         // e.g. "11", "21", ..., "48"  (32 teeth)
          "surfaces": {
            "oclusal":    {"state": "<state_id>", "condition": "<condition>", "color": null},
            "vestibular": {"state": "<state_id>", "condition": "<condition>", "color": null},
            "lingual":    {"state": "<state_id>", "condition": "<condition>", "color": null},
            "mesial":     {"state": "<state_id>", "condition": "<condition>", "color": null},
            "distal":     {"state": "<state_id>", "condition": "<condition>", "color": null}
          }
        }
      },
      "decidua": {
        "<FDI>": {                         // e.g. "51", "52", ..., "85"  (20 teeth)
          "surfaces": { ... }              // same structure as permanente
        }
      }
    }

### Field semantics

- state     : string ID from the 42-state catalog (e.g. "sano", "caries", "corona_metal")
              Empty string "" means healthy/unset (same as "sano").
- condition : "bueno" | "malo" | "indefinido" | null
- color     : HEX string override (e.g. "#E74C3C") or null (uses catalog default_color)

### Backward compatibility

v1 and v2 odontogram data stored in DB are auto-upgraded to v3.0 on every read via
normalize_to_v3(). Writes always persist v3.0. No manual data migration required.

### v2 → v3 state mapping (handled by normalize_to_v3)

    v2 state id             → v3 state id
    --------------------------------
    healthy / sano          → sano
    caries                  → caries
    filled / obturado       → obturacion_resina
    extracted / extraido    → ausente
    crown / corona          → corona_metal
    implant / implante      → implante
    bridge / puente         → puente_fijo
    fracture / fractura     → fractura
    root_canal / endodoncia → endodoncia
    mobility / movilidad    → movilidad
"""

from alembic import op
from sqlalchemy import text


revision = "v4w5x6y7z8a9"
down_revision = "u3v4w5x6y7z8"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_clinical_records_odontogram_gin"
TABLE_NAME = "clinical_records"
COLUMN_NAME = "odontogram_data"


def _index_exists(conn, index_name):
    """Check whether a PostgreSQL index already exists."""
    result = conn.execute(
        text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :name"
        ),
        {"name": index_name},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()

    if not _index_exists(conn, INDEX_NAME):
        op.execute(
            f"CREATE INDEX {INDEX_NAME} ON {TABLE_NAME} USING GIN ({COLUMN_NAME})"
        )
        print(f"✅ Created GIN index {INDEX_NAME} on {TABLE_NAME}.{COLUMN_NAME}")
    else:
        print(f"ℹ️  GIN index {INDEX_NAME} already exists — skipping")


def downgrade():
    conn = op.get_bind()

    if _index_exists(conn, INDEX_NAME):
        op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
        print(f"✅ Dropped GIN index {INDEX_NAME}")
    else:
        print(f"ℹ️  GIN index {INDEX_NAME} not found — nothing to drop")
