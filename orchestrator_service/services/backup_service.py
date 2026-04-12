"""
Full Platform Backup Service.

Generates a restorable ZIP snapshot of all tenant data:
- JSON per table (FK-safe order)
- Files (documents, PDFs, media)
- Manifest with checksums and schema version

Background task with Redis progress tracking.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BACKUP_VERSION = "1.0"
MAX_FILE_COLLECTION_BYTES = 5 * 1024 * 1024 * 1024  # 5GB cap

# FK-safe export order
EXPORT_TABLES = [
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
    "automation_playbooks",
    "automation_steps",
    "automation_executions",
    "automation_events",
]

# Tables excluded from backup (sensitive/ephemeral/regenerated)
EXCLUDED_TABLES = {
    "credentials",
    "google_oauth_tokens",
    "faq_embeddings",
    "agent_turn_log",
    "patient_context_snapshots",
    "users",
    "channel_configs",
    "alembic_version",
    "system_config",
    "inbound_messages",
}

# Tables that need JOIN-based tenant filtering (no tenant_id column)
JUNCTION_TABLES = {
    "treatment_type_professionals": """
        SELECT ttp.* FROM treatment_type_professionals ttp
        JOIN treatment_types tt ON ttp.treatment_type_id = tt.id
        WHERE tt.tenant_id = $1
    """,
    "automation_steps": """
        SELECT s.* FROM automation_steps s
        JOIN automation_playbooks p ON s.playbook_id = p.id
        WHERE p.tenant_id = $1
        ORDER BY s.playbook_id, s.step_order
    """,
    "automation_events": """
        SELECT ae.* FROM automation_events ae
        JOIN automation_executions ex ON ae.execution_id = ex.id
        WHERE ex.tenant_id = $1
        ORDER BY ae.created_at DESC
        LIMIT 10000
    """,
    "meta_ad_insights": """
        SELECT mai.* FROM meta_ad_insights mai
        WHERE EXISTS (
            SELECT 1 FROM patients p
            WHERE p.first_touch_campaign_id = mai.campaign_id AND p.tenant_id = $1
        )
        LIMIT 5000
    """,
    "patient_attribution_history": """
        SELECT pah.* FROM patient_attribution_history pah
        JOIN patients p ON pah.patient_id = p.id
        WHERE p.tenant_id = $1
    """,
}


def _coerce_value(val: Any) -> Any:
    """Convert DB types to JSON-serializable values with type markers for lossless restore."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, time):
        return val.isoformat()
    if isinstance(val, timedelta):
        return f"td:{val.total_seconds()}"
    if isinstance(val, Decimal):
        return f"Decimal:{val}"
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, bytes):
        import base64
        return f"b64:{base64.b64encode(val).decode()}"
    if isinstance(val, (dict, list)):
        return val  # JSONB — already serializable
    return val


def _coerce_row(row) -> Dict[str, Any]:
    """Convert an asyncpg Record to a JSON-serializable dict."""
    return {k: _coerce_value(v) for k, v in dict(row).items()}


async def _query_table(pool, table_name: str, tenant_id: int) -> List[Dict]:
    """Query all rows for a table filtered by tenant_id."""
    try:
        if table_name in JUNCTION_TABLES:
            sql = JUNCTION_TABLES[table_name]
            rows = await pool.fetch(sql, tenant_id)
        elif table_name == "tenants":
            rows = await pool.fetch("SELECT * FROM tenants WHERE id = $1", tenant_id)
        else:
            # Check if table has tenant_id column
            has_tid = await pool.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = $1 AND column_name = 'tenant_id'
                )
                """,
                table_name,
            )
            if has_tid:
                # Check if table has 'id' column for ordering
                has_id = await pool.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = $1 AND column_name = 'id'
                    )
                    """,
                    table_name,
                )
                order = " ORDER BY id" if has_id else ""
                BATCH_SIZE = 5000
                rows = []
                offset = 0
                while True:
                    batch = await pool.fetch(
                        f"SELECT * FROM {table_name} WHERE tenant_id = $1{order} LIMIT {BATCH_SIZE} OFFSET $2",
                        tenant_id,
                        offset,
                    )
                    if not batch:
                        break
                    rows.extend(batch)
                    offset += BATCH_SIZE
                    if len(batch) < BATCH_SIZE:
                        break
            else:
                logger.warning(f"[backup] Table {table_name} has no tenant_id — skipping")
                return []

        return [_coerce_row(r) for r in rows]
    except Exception as e:
        logger.warning(f"[backup] Failed to query {table_name}: {e}")
        return []


async def _query_all_data(pool, tenant_id: int, task_id: str) -> Dict[str, List[Dict]]:
    """Query all exportable tables, updating progress as we go."""
    data = {}
    total = len(EXPORT_TABLES)
    for i, table in enumerate(EXPORT_TABLES):
        pct = int((i / total) * 40)  # 0-40% for data phase
        await _update_progress(task_id, pct, f"Exportando {table}...")
        rows = await _query_table(pool, table, tenant_id)
        if rows:
            data[table] = rows
        logger.info(f"[backup] {table}: {len(rows)} rows")
    return data


async def _collect_files(
    tenant_id: int, data: Dict[str, List[Dict]], task_id: str
) -> Dict[str, bytes]:
    """Collect local files referenced by the data. Returns {relative_path: bytes}."""
    files = {}
    total_size = 0
    uploads_dir = os.environ.get("UPLOADS_DIR", "/app/uploads")

    await _update_progress(task_id, 42, "Recolectando archivos...")

    # Tenant logo
    for ext in ("png", "jpg", "jpeg", "svg", "webp"):
        logo_path = os.path.join(uploads_dir, "tenants", str(tenant_id), f"logo.{ext}")
        if os.path.isfile(logo_path):
            try:
                content = Path(logo_path).read_bytes()
                files[f"files/logo/logo.{ext}"] = content
                total_size += len(content)
            except Exception as e:
                logger.warning(f"[backup] Logo read failed: {e}")
            break

    # Patient documents
    for doc in data.get("patient_documents", []):
        file_path = doc.get("file_path", "")
        if not file_path:
            continue

        patient_id = doc.get("patient_id", "unknown")
        filename = os.path.basename(file_path)
        zip_path = f"files/documents/{patient_id}/{filename}"

        if file_path.startswith(("http://", "https://")):
            # External URL — try to download
            try:
                import httpx
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(file_path)
                    if resp.status_code == 200:
                        files[zip_path] = resp.content
                        total_size += len(resp.content)
            except Exception as e:
                logger.warning(f"[backup] External file download failed {file_path}: {e}")
        elif os.path.isfile(file_path):
            try:
                content = Path(file_path).read_bytes()
                files[zip_path] = content
                total_size += len(content)
            except Exception as e:
                logger.warning(f"[backup] File read failed {file_path}: {e}")

        if total_size > MAX_FILE_COLLECTION_BYTES:
            logger.error(f"[backup] File collection exceeded 5GB cap at {total_size} bytes")
            break

    # Digital record PDFs
    digital_records_dir = os.path.join(uploads_dir, "digital_records", str(tenant_id))
    if os.path.isdir(digital_records_dir):
        for fname in os.listdir(digital_records_dir):
            fpath = os.path.join(digital_records_dir, fname)
            if os.path.isfile(fpath):
                try:
                    content = Path(fpath).read_bytes()
                    files[f"files/digital_records/{fname}"] = content
                    total_size += len(content)
                except Exception:
                    pass

    # Budget PDFs
    budgets_dir = os.path.join(uploads_dir, "budgets", str(tenant_id))
    if os.path.isdir(budgets_dir):
        for fname in os.listdir(budgets_dir):
            fpath = os.path.join(budgets_dir, fname)
            if os.path.isfile(fpath):
                try:
                    content = Path(fpath).read_bytes()
                    files[f"files/budgets/{fname}"] = content
                    total_size += len(content)
                except Exception:
                    pass

    await _update_progress(task_id, 68, f"Archivos recolectados: {len(files)}")
    logger.info(f"[backup] Collected {len(files)} files, {total_size / 1024 / 1024:.1f} MB")
    return files


def _compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def _build_zip(
    tenant_id: int,
    task_id: str,
    data: Dict[str, List[Dict]],
    files: Dict[str, bytes],
    clinic_name: str,
) -> str:
    """Build the backup ZIP file. Returns the temp file path."""
    await _update_progress(task_id, 72, "Construyendo archivo ZIP...")

    zip_path = os.path.join(tempfile.gettempdir(), f"backup_{tenant_id}_{task_id}.zip")
    date_str = datetime.now().strftime("%Y-%m-%d")
    prefix = f"backup_{re.sub(r'[^a-zA-Z0-9_-]', '_', clinic_name)}_{date_str}"

    checksums = {}
    table_counts = {}

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Data files
        for table_name, rows in data.items():
            json_bytes = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
            checksums[f"data/{table_name}.json"] = _compute_checksum(json_bytes)
            table_counts[table_name] = len(rows)
            zf.writestr(f"{prefix}/data/{table_name}.json", json_bytes)

        await _update_progress(task_id, 80, "Agregando archivos al ZIP...")

        # Binary files
        for fpath, content in files.items():
            zf.writestr(f"{prefix}/{fpath}", content)

        # Get alembic head
        alembic_head = "unknown"
        try:
            from db import db
            row = await db.pool.fetchval("SELECT version_num FROM alembic_version LIMIT 1")
            if row:
                alembic_head = row
        except Exception:
            pass

        await _update_progress(task_id, 88, "Generando manifiesto...")

        # Manifest
        manifest = {
            "version": BACKUP_VERSION,
            "alembic_head": alembic_head,
            "tenant_id": tenant_id,
            "clinic_name": clinic_name,
            "created_at": datetime.now().isoformat(),
            "table_counts": table_counts,
            "total_tables": len(data),
            "total_files": len(files),
            "checksums": checksums,
        }
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        zf.writestr(f"{prefix}/manifest.json", manifest_bytes)

        # Human-readable info
        info_lines = [
            f"ClinicForge Backup — {clinic_name}",
            f"Fecha: {date_str}",
            f"Tenant ID: {tenant_id}",
            f"Schema: {alembic_head}",
            f"Tablas: {len(data)}",
            f"Registros totales: {sum(table_counts.values())}",
            f"Archivos: {len(files)}",
            "",
            "Este archivo puede ser restaurado en una nueva instancia de ClinicForge",
            "usando la opción 'Restaurar Backup' en Configuración > Mantenimiento.",
        ]
        zf.writestr(f"{prefix}/BACKUP_INFO.txt", "\n".join(info_lines))

    # Set restrictive permissions
    try:
        os.chmod(zip_path, 0o600)
    except Exception:
        pass

    # Verify ZIP integrity
    with zipfile.ZipFile(zip_path, "r") as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError(f"ZIP integrity check failed on: {bad}")

    await _update_progress(task_id, 95, "Verificando integridad...")
    return zip_path


async def _update_progress(task_id: str, pct: int, message: str) -> None:
    """Update backup task progress in Redis."""
    try:
        from services.relay import get_redis
        r = get_redis()
        if r is None:
            return
        key = f"backup:progress:{task_id}"
        await r.hset(key, mapping={
            "pct": str(pct),
            "message": message,
            "status": "done" if pct >= 100 else "generating",
            "updated_at": datetime.now().isoformat(),
        })
        await r.expire(key, 3600)
    except Exception as e:
        logger.warning(f"[backup] Progress update failed: {e}")


async def generate_backup(tenant_id: int, task_id: str) -> None:
    """Main background task entry point for generating a backup."""
    try:
        from db import db

        await _update_progress(task_id, 0, "Iniciando backup...")

        # Get clinic name
        clinic_name = "ClinicForge"
        try:
            row = await db.pool.fetchval(
                "SELECT clinic_name FROM tenants WHERE id = $1", tenant_id
            )
            if row:
                clinic_name = row
        except Exception:
            pass

        # Phase 1: Query all data (0-40%)
        data = await _query_all_data(db.pool, tenant_id, task_id)

        # Phase 2: Collect files (40-70%)
        files = await _collect_files(tenant_id, data, task_id)

        # Phase 3: Build ZIP (70-95%)
        zip_path = await _build_zip(tenant_id, task_id, data, files, clinic_name)

        # Phase 4: Finalize (95-100%)
        zip_size = os.path.getsize(zip_path)
        logger.info(
            f"[backup] Backup complete: {zip_path} ({zip_size / 1024 / 1024:.1f} MB)"
        )

        # Store completion with zip_path
        try:
            from services.relay import get_redis
            r = get_redis()
            if r:
                key = f"backup:progress:{task_id}"
                await r.hset(key, mapping={
                    "pct": "100",
                    "message": "Backup listo para descargar",
                    "status": "done",
                    "zip_path": zip_path,
                    "zip_size": str(zip_size),
                    "updated_at": datetime.now().isoformat(),
                })
                await r.expire(key, 3600)
        except Exception:
            pass

        # Release lock
        try:
            from services.relay import get_redis
            r = get_redis()
            if r:
                await r.delete(f"backup:lock:{tenant_id}")
        except Exception:
            pass

    except Exception as e:
        logger.exception(f"[backup] Backup generation failed: {e}")
        try:
            from services.relay import get_redis
            r = get_redis()
            if r:
                key = f"backup:progress:{task_id}"
                await r.hset(key, mapping={
                    "pct": "0",
                    "message": f"Error: {str(e)[:200]}",
                    "status": "error",
                    "updated_at": datetime.now().isoformat(),
                })
                await r.expire(key, 3600)
                await r.delete(f"backup:lock:{tenant_id}")
        except Exception:
            pass
