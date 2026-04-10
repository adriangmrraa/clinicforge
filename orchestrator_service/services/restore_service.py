"""
Full Platform Restore Service.

Restores a tenant from a backup ZIP snapshot:
- Validates manifest (version, schema, checksums)
- Inserts data in FK-safe order (idempotent: ON CONFLICT DO NOTHING)
- Restores files to UPLOADS_DIR
- Supports tenant ID remapping for cross-deployment restore
"""

import hashlib
import json
import logging
import os
import re
import zipfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BACKUP_VERSION = "1.0"

# FK-safe insertion order (same as export)
INSERT_ORDER = [
    "tenants",
    "professionals",
    "treatment_types",
    "treatment_type_professionals",
    "patients",
    "clinical_records",
    "clinical_record_summaries",
    "appointments",
    "appointment_audit_log",
    "chat_conversations",
    "chat_messages",
    "treatment_plans",
    "treatment_plan_items",
    "treatment_plan_payments",
    "clinic_faqs",
    "automation_rules",
    "automation_logs",
    "tenant_holidays",
    "meta_form_leads",
    "meta_ad_insights",
    "nova_memories",
    "patient_memories",
    "patient_documents",
    "accounting_transactions",
    "daily_cash_flow",
    "liquidation_records",
    "professional_payouts",
    "tenant_insurance_providers",
    "treatment_images",
    "google_calendar_blocks",
    "professional_derivation_rules",
    "professional_commissions",
    "lead_status_history",
    "lead_notes",
    "patient_attribution_history",
]

# Columns that need type coercion reversal on restore
DECIMAL_COLUMNS = {
    "base_price",
    "consultation_price",
    "billing_amount",
    "amount",
    "estimated_total",
    "approved_total",
    "financed_total",
    "commission_pct",
    "copay_percent",
    "cost_micros",
    "total_revenue",
    "total_expenses",
    "total_paid",
    "sena_amount",
    "sena_paid",
}


def _decoerce_value(val: Any, col_name: str = "") -> Any:
    """Reverse type coercion markers back to Python types for asyncpg."""
    if val is None:
        return None
    if isinstance(val, str):
        if val.startswith("Decimal:"):
            return Decimal(val[8:])
        if val.startswith("b64:"):
            import base64

            return base64.b64decode(val[4:])
        if val.startswith("td:"):
            from datetime import timedelta

            return timedelta(seconds=float(val[3:]))
        # Auto-detect datetime ISO strings
        if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:", val):
            try:
                return datetime.fromisoformat(val)
            except ValueError:
                pass
        # Auto-detect date strings
        if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
            try:
                from datetime import date

                return date.fromisoformat(val)
            except ValueError:
                pass
        # Known decimal columns without marker (backward compat)
        if col_name in DECIMAL_COLUMNS:
            try:
                return Decimal(val)
            except Exception:
                pass
    return val


def validate_manifest(manifest: Dict) -> Tuple[bool, str]:
    """
    Validate backup manifest.

    Returns (is_valid, error_message).
    """
    if not manifest:
        return False, "Manifest vacío o no encontrado"

    version = manifest.get("version")
    if version != BACKUP_VERSION:
        return (
            False,
            f"Versión de backup no soportada: {version} (esperada: {BACKUP_VERSION})",
        )

    required_keys = ["alembic_head", "tenant_id", "created_at", "table_counts"]
    for key in required_keys:
        if key not in manifest:
            return False, f"Manifest incompleto: falta '{key}'"

    return True, ""


async def check_schema_compatibility(pool, manifest: Dict) -> Tuple[bool, str]:
    """Check if the target DB schema is compatible with the backup."""
    backup_head = manifest.get("alembic_head", "")
    try:
        db_head = await pool.fetchval("SELECT version_num FROM alembic_version LIMIT 1")
        if not db_head:
            return False, "No se encontró versión de schema en la base de datos destino"
        # Simple string comparison — backup head should not be newer than DB
        # In practice, both are like "043_lead_recovery_v2_fields"
        # We just warn if they differ, don't block
        if backup_head != db_head:
            logger.warning(
                f"[restore] Schema mismatch: backup={backup_head}, db={db_head}. Proceeding anyway."
            )
        return True, ""
    except Exception as e:
        return False, f"Error verificando schema: {e}"


def verify_checksums(
    zip_ref: zipfile.ZipFile, manifest: Dict, prefix: str
) -> List[str]:
    """Verify SHA-256 checksums of data files. Returns list of mismatches."""
    checksums = manifest.get("checksums", {})
    mismatches = []
    for rel_path, expected_hash in checksums.items():
        full_path = f"{prefix}/{rel_path}"
        try:
            content = zip_ref.read(full_path)
            actual_hash = hashlib.sha256(content).hexdigest()
            if actual_hash != expected_hash:
                mismatches.append(rel_path)
        except KeyError:
            mismatches.append(f"{rel_path} (not found)")
    return mismatches


def _remap_tenant_id(rows: List[Dict], source_tid: int, target_tid: int) -> List[Dict]:
    """Replace tenant_id in all rows for cross-tenant restore."""
    if source_tid == target_tid:
        return rows
    remapped = []
    for row in rows:
        row_copy = dict(row)
        if "tenant_id" in row_copy:
            row_copy["tenant_id"] = target_tid
        # For tenants table, remap the 'id' itself
        if "id" in row_copy and row_copy.get("tenant_id") is None:
            # This might be the tenants table where id IS the tenant_id
            pass
        remapped.append(row_copy)
    return remapped


async def _insert_table(
    pool, table_name: str, rows: List[Dict], target_tenant_id: int
) -> Tuple[int, int, List[str]]:
    """
    Insert rows into a table with ON CONFLICT DO NOTHING.

    Returns (inserted_count, skipped_count, warnings).
    """
    if not rows:
        return 0, 0, []

    inserted = 0
    skipped = 0
    warnings = []

    for row in rows:
        try:
            # Decoerce all values
            clean_row = {k: _decoerce_value(v, k) for k, v in row.items()}

            columns = list(clean_row.keys())
            values = list(clean_row.values())
            placeholders = [f"${i + 1}" for i in range(len(columns))]
            col_str = ", ".join(columns)
            val_str = ", ".join(placeholders)

            # Determine conflict target
            if table_name == "treatment_type_professionals":
                conflict = "ON CONFLICT (treatment_type_id, professional_id) DO NOTHING"
            elif "id" in columns:
                conflict = "ON CONFLICT (id) DO NOTHING"
            else:
                conflict = "ON CONFLICT DO NOTHING"

            sql = f"INSERT INTO {table_name} ({col_str}) VALUES ({val_str}) {conflict}"

            result = await pool.execute(sql, *values)
            if "INSERT 0 1" in result:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            skipped += 1
            warnings.append(f"{table_name} row {row.get('id', '?')}: {str(e)[:100]}")
            logger.warning(f"[restore] Insert failed {table_name}: {e}")

    return inserted, skipped, warnings


async def _restore_files(
    zip_ref: zipfile.ZipFile,
    prefix: str,
    target_tenant_id: int,
    source_tenant_id: int,
) -> int:
    """Extract files from ZIP to UPLOADS_DIR. Returns file count."""
    uploads_dir = os.environ.get("UPLOADS_DIR", "/app/uploads")
    file_count = 0

    for entry in zip_ref.namelist():
        if not entry.startswith(f"{prefix}/files/"):
            continue
        if entry.endswith("/"):
            continue  # Skip directories

        # Relative path within files/
        rel_path = entry[len(f"{prefix}/files/") :]

        # Sanitize path (prevent traversal)
        rel_path = rel_path.replace("\\", "/")
        rel_path = re.sub(r"\.\./", "", rel_path)
        rel_path = rel_path.lstrip("/")
        if not rel_path:
            continue

        # Remap source tenant_id in path to target
        if str(source_tenant_id) in rel_path:
            rel_path = rel_path.replace(str(source_tenant_id), str(target_tenant_id), 1)

        target_path = os.path.join(uploads_dir, rel_path)

        # Create parent dirs
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        # Don't overwrite existing files
        if os.path.exists(target_path):
            continue

        try:
            content = zip_ref.read(entry)
            with open(target_path, "wb") as f:
                f.write(content)
            file_count += 1
        except Exception as e:
            logger.warning(f"[restore] File extraction failed {entry}: {e}")

    return file_count


async def restore_from_zip(
    zip_path: str,
    tenant_id: int,
    pool,
    target_tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Main restore entry point.

    Args:
        zip_path: Path to the uploaded ZIP file
        tenant_id: Source tenant_id from the backup
        pool: asyncpg pool
        target_tenant_id: If provided, remap all data to this tenant

    Returns summary dict with counts and warnings.
    """
    target_tid = target_tenant_id or tenant_id
    summary = {
        "tables_restored": {},
        "rows_inserted": 0,
        "rows_skipped": 0,
        "files_restored": 0,
        "warnings": [],
    }

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Find the prefix (first directory in ZIP)
            names = zf.namelist()
            if not names:
                return {**summary, "warnings": ["ZIP vacío"]}

            prefix = names[0].split("/")[0]

            # Read and validate manifest
            manifest_path = f"{prefix}/manifest.json"
            try:
                manifest_bytes = zf.read(manifest_path)
                manifest = json.loads(manifest_bytes)
            except (KeyError, json.JSONDecodeError) as e:
                return {**summary, "warnings": [f"Manifest inválido: {e}"]}

            is_valid, error = validate_manifest(manifest)
            if not is_valid:
                return {**summary, "warnings": [error]}

            # Schema compatibility check
            is_compat, schema_warn = await check_schema_compatibility(pool, manifest)
            if schema_warn:
                summary["warnings"].append(schema_warn)

            # Verify checksums
            mismatches = verify_checksums(zf, manifest, prefix)
            if mismatches:
                summary["warnings"].append(
                    f"Checksums no coinciden: {', '.join(mismatches[:5])}"
                )

            source_tid = manifest.get("tenant_id", tenant_id)

            # Insert tables in FK-safe order
            for table_name in INSERT_ORDER:
                data_path = f"{prefix}/data/{table_name}.json"
                try:
                    raw = zf.read(data_path)
                    rows = json.loads(raw)
                except (KeyError, json.JSONDecodeError):
                    continue  # Table not in backup — skip

                if not rows:
                    continue

                # Remap tenant_id if needed
                if target_tid != source_tid:
                    if table_name == "tenants":
                        # Special: remap the tenant record itself
                        for row in rows:
                            row["id"] = target_tid
                    else:
                        rows = _remap_tenant_id(rows, source_tid, target_tid)

                inserted, skipped, warnings = await _insert_table(
                    pool, table_name, rows, target_tid
                )
                summary["tables_restored"][table_name] = inserted
                summary["rows_inserted"] += inserted
                summary["rows_skipped"] += skipped
                summary["warnings"].extend(warnings)

                logger.info(
                    f"[restore] {table_name}: {inserted} inserted, {skipped} skipped"
                )

            # Restore files
            file_count = await _restore_files(zf, prefix, target_tid, source_tid)
            summary["files_restored"] = file_count

    except zipfile.BadZipFile:
        summary["warnings"].append("Archivo ZIP corrupto o inválido")
    except Exception as e:
        logger.exception(f"[restore] Restore failed: {e}")
        summary["warnings"].append(f"Error durante la restauración: {str(e)[:200]}")

    logger.info(
        f"[restore] Complete: {summary['tables_restored']} tables, "
        f"{summary['rows_inserted']} inserted, {summary['rows_skipped']} skipped, "
        f"{summary['files_restored']} files"
    )
    return summary
