"""
Backup & Restore routes.

CEO-only endpoints for full platform backup generation and restore.
Security: verify_ceo_token (JWT + X-Admin-Token + role='ceo') + password + email verification code.
"""

import logging
import os
import secrets
import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Header,
    UploadFile,
)
from pydantic import BaseModel

from core.auth import verify_ceo_token, get_resolved_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Request models ---


class GenerateRequest(BaseModel):
    password: str
    code: str = ""  # Optional — not needed for direct flow


class DirectGenerateRequest(BaseModel):
    password: str


# --- POST /request-code ---


@router.post("/request-code")
async def request_verification_code(
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Send a 6-digit verification code to the CEO's email for backup authorization."""
    try:
        from services.relay import get_redis

        r = get_redis()
        if r is None:
            raise HTTPException(503, "Redis no disponible")

        # Rate limit: 60s cooldown
        code_key = f"backup:verify_code:{tenant_id}"
        existing_ttl = await r.ttl(code_key)
        if existing_ttl and existing_ttl > 540:  # Less than 60s elapsed
            raise HTTPException(
                429, "Ya se envió un código. Esperá 60 segundos para solicitar otro."
            )

        # Generate 6-digit code
        code = str(secrets.randbelow(900000) + 100000)

        # Get CEO email
        ceo_email = getattr(user_data, "email", None)
        if not ceo_email:
            raise HTTPException(400, "No se encontró email del CEO")

        # Get clinic name
        from db import db

        clinic_name = (
            await db.pool.fetchval(
                "SELECT clinic_name FROM tenants WHERE id = $1", tenant_id
            )
            or "ClinicForge"
        )

        # Send email first (atomic: only store if send succeeds)
        from email_service import send_backup_verification_code

        sent = await send_backup_verification_code(ceo_email, code, clinic_name)
        if not sent:
            raise HTTPException(
                502, "No se pudo enviar el email. Verificá la configuración SMTP."
            )

        # Store code + attempts counter in Redis
        await r.setex(code_key, 600, code)
        attempts_key = f"backup:verify_attempts:{tenant_id}"
        await r.setex(attempts_key, 600, "0")

        # Mask email for frontend
        parts = ceo_email.split("@")
        masked = f"{parts[0][:3]}***@{parts[1]}" if len(parts) == 2 else "***"

        return {"message": "Código enviado", "email_hint": masked, "expires_in": 600}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[backup] request-code failed: {e}")
        raise HTTPException(500, "Error al enviar el código de verificación")


# --- POST /generate ---


@router.post("/generate", status_code=202)
async def generate_backup(
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Verify password + code, start backup generation as background task."""
    try:
        from services.relay import get_redis

        r = get_redis()
        if r is None:
            raise HTTPException(503, "Redis no disponible")

        # Check concurrent lock
        lock_key = f"backup:lock:{tenant_id}"
        if await r.exists(lock_key):
            raise HTTPException(
                409, "Ya hay un backup en curso. Esperá a que finalice."
            )

        # Verify password
        from db import db

        user_id = getattr(user_data, "id", None) or getattr(user_data, "user_id", None)
        user_row = await db.pool.fetchrow(
            "SELECT password_hash FROM users WHERE id = $1", str(user_id)
        )
        if not user_row:
            raise HTTPException(401, "Usuario no encontrado")

        import bcrypt

        if not bcrypt.checkpw(
            body.password.encode("utf-8"),
            user_row["password_hash"].encode("utf-8"),
        ):
            raise HTTPException(401, "Contraseña incorrecta")

        # Verify code
        code_key = f"backup:verify_code:{tenant_id}"
        attempts_key = f"backup:verify_attempts:{tenant_id}"

        # Check max attempts
        attempts = int(await r.get(attempts_key) or "0")
        if attempts >= 3:
            await r.delete(code_key, attempts_key)
            raise HTTPException(
                429, "Máximo de intentos alcanzado. Solicitá un nuevo código."
            )

        stored_code = await r.get(code_key)
        if not stored_code:
            raise HTTPException(
                400, "El código expiró o no existe. Solicitá uno nuevo."
            )

        if not secrets.compare_digest(body.code, stored_code):
            await r.incr(attempts_key)
            remaining = 3 - (attempts + 1)
            raise HTTPException(
                400, f"Código incorrecto. Intentos restantes: {remaining}"
            )

        # Code valid — delete both keys
        await r.delete(code_key, attempts_key)

        # Set lock
        await r.setex(lock_key, 3600, "1")

        # Create task
        task_id = str(uuid.uuid4())
        progress_key = f"backup:progress:{task_id}"
        await r.hset(
            progress_key,
            mapping={
                "pct": "0",
                "message": "Backup en cola...",
                "status": "queued",
                "tenant_id": str(tenant_id),
            },
        )
        await r.expire(progress_key, 3600)

        # Launch background task
        from services.backup_service import generate_backup as _do_backup

        background_tasks.add_task(_do_backup, tenant_id, task_id)

        logger.info(f"[backup] Backup task {task_id} queued for tenant {tenant_id}")
        return {"task_id": task_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[backup] generate failed: {e}")
        raise HTTPException(500, "Error al iniciar el backup")


# --- POST /generate-direct (simplified: password only, no email code) ---


@router.post("/generate-direct", status_code=202)
async def generate_backup_direct(
    body: DirectGenerateRequest,
    background_tasks: BackgroundTasks,
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Simplified backup: verify CEO password only, then start generation. No email code needed."""
    try:
        from services.relay import get_redis

        r = get_redis()
        if r is None:
            raise HTTPException(503, "Redis no disponible")

        # Check concurrent lock
        lock_key = f"backup:lock:{tenant_id}"
        if await r.exists(lock_key):
            raise HTTPException(
                409, "Ya hay un backup en curso. Esperá a que finalice."
            )

        # Verify password
        from db import db
        import bcrypt

        user_id = getattr(user_data, "id", None) or getattr(user_data, "user_id", None)
        user_row = await db.pool.fetchrow(
            "SELECT password_hash FROM users WHERE id = $1", str(user_id)
        )
        if not user_row:
            raise HTTPException(401, "Usuario no encontrado")

        if not bcrypt.checkpw(
            body.password.encode("utf-8"),
            user_row["password_hash"].encode("utf-8"),
        ):
            raise HTTPException(401, "Contraseña incorrecta")

        # Set lock
        await r.setex(lock_key, 3600, "1")

        # Create task
        task_id = str(uuid.uuid4())
        progress_key = f"backup:progress:{task_id}"
        await r.hset(
            progress_key,
            mapping={
                "pct": "0",
                "message": "Backup en cola...",
                "status": "queued",
                "tenant_id": str(tenant_id),
            },
        )
        await r.expire(progress_key, 3600)

        # Launch background task
        from services.backup_service import generate_backup as _do_backup

        background_tasks.add_task(_do_backup, tenant_id, task_id)

        logger.info(f"[backup] Direct backup task {task_id} queued for tenant {tenant_id}")
        return {"task_id": task_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[backup] generate-direct failed: {e}")
        raise HTTPException(500, "Error al iniciar el backup")


# --- GET /status/{task_id} ---


@router.get("/status/{task_id}")
async def get_backup_status(
    task_id: str,
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Poll backup task progress."""
    try:
        from services.relay import get_redis

        r = get_redis()
        if r is None:
            raise HTTPException(503, "Redis no disponible")

        key = f"backup:progress:{task_id}"
        data = await r.hgetall(key)

        if not data:
            raise HTTPException(404, "Tarea de backup no encontrada")

        # Verify tenant ownership
        if data.get("tenant_id") and str(data["tenant_id"]) != str(tenant_id):
            raise HTTPException(404, "Tarea de backup no encontrada")

        return {
            "task_id": task_id,
            "progress_pct": int(data.get("pct", 0)),
            "message": data.get("message", ""),
            "status": data.get("status", "unknown"),
            "download_ready": data.get("status") == "done",
            "error": data.get("error"),
            "zip_size": int(data.get("zip_size", 0)) if data.get("zip_size") else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[backup] status check failed: {e}")
        raise HTTPException(500, "Error al consultar el estado del backup")


# --- GET /download/{task_id} ---


@router.get("/download/{task_id}")
async def download_backup(
    task_id: str,
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Stream the generated backup ZIP for download."""
    try:
        from services.relay import get_redis

        r = get_redis()
        if r is None:
            raise HTTPException(503, "Redis no disponible")

        key = f"backup:progress:{task_id}"
        data = await r.hgetall(key)

        if not data:
            raise HTTPException(404, "Tarea de backup no encontrada o expirada")

        if data.get("tenant_id") and str(data["tenant_id"]) != str(tenant_id):
            raise HTTPException(404, "Tarea de backup no encontrada")

        if data.get("status") != "done":
            raise HTTPException(425, "El backup aún no está listo")

        zip_path = data.get("zip_path", "")

        # Path traversal guard: must be in temp directory and contain tenant_id
        import tempfile as _tmpmod
        if not zip_path or not zip_path.startswith(_tmpmod.gettempdir()) or f"backup_{tenant_id}_" not in zip_path:
            raise HTTPException(500, "Ruta de archivo inválida")

        if not os.path.isfile(zip_path):
            await r.delete(key)
            raise HTTPException(
                500, "Archivo de backup no encontrado. Generá uno nuevo."
            )

        from fastapi.responses import FileResponse
        import re

        # Get clinic name for filename
        from db import db

        clinic_name = (
            await db.pool.fetchval(
                "SELECT clinic_name FROM tenants WHERE id = $1", tenant_id
            )
            or "ClinicForge"
        )
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", clinic_name)
        from datetime import datetime

        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"backup_{safe_name}_{date_str}.zip"

        # Cleanup after download (Redis key — file stays for potential re-download within TTL)
        # File will be cleaned up by the 1-hour TTL expiry or manual cleanup

        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename=filename,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[backup] download failed: {e}")
        raise HTTPException(500, "Error al descargar el backup")


# --- POST /restore ---


@router.post("/restore")
async def restore_backup(
    file: UploadFile = File(...),
    target_tenant_id: Optional[int] = None,
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Upload a backup ZIP and restore it to the current (or target) tenant.
    Security: CEO-only via verify_ceo_token (JWT + X-Admin-Token + role='ceo')."""
    import tempfile

    # Size check (5GB max)
    max_size = 5 * 1024 * 1024 * 1024
    if file.size and file.size > max_size:
        raise HTTPException(413, "El archivo excede el límite de 5GB")

    # Stream upload to temp file (avoid loading entire file into memory)
    tmp_path = os.path.join(tempfile.gettempdir(), f"restore_{uuid.uuid4()}.zip")
    try:
        total_written = 0
        with open(tmp_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                total_written += len(chunk)
                if total_written > max_size:
                    raise HTTPException(413, "El archivo excede el límite de 5GB")
                f.write(chunk)

        # Validate it's a real ZIP
        import zipfile

        if not zipfile.is_zipfile(tmp_path):
            raise HTTPException(422, "El archivo no es un ZIP válido")

        # Run restore
        from services.restore_service import restore_from_zip

        target = target_tenant_id or tenant_id
        summary = await restore_from_zip(tmp_path, tenant_id, db.pool, target)

        logger.info(f"[backup] Restore completed for tenant {target}: {summary}")
        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[backup] restore failed: {e}")
        raise HTTPException(500, f"Error durante la restauración: {str(e)[:200]}")
    finally:
        # Cleanup temp file
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
