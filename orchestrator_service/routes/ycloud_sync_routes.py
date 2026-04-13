"""
YCloud Sync API routes.

CEO-only endpoints for full message sync management.
Security: verify_ceo_token + password verification for start/cancel.
"""

import logging
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
)
from pydantic import BaseModel

from core.auth import verify_ceo_token, get_resolved_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Request models ---


class SyncStartRequest(BaseModel):
    password: str


class SyncConfigUpdate(BaseModel):
    sync_enabled: Optional[bool] = None
    max_messages: Optional[int] = None


# --- Helper functions ---


async def _verify_password(user_data, password: str) -> None:
    """Verify user password for sensitive operations."""
    from db import db
    import bcrypt

    user_id = getattr(user_data, "id", None) or getattr(user_data, "user_id", None)
    if not user_id:
        raise HTTPException(401, "Usuario no identificado")

    user_row = await db.pool.fetchrow(
        "SELECT password_hash FROM users WHERE id = $1", str(user_id)
    )
    if not user_row:
        raise HTTPException(401, "Usuario no encontrado")

    if not bcrypt.checkpw(
        password.encode("utf-8"),
        user_row["password_hash"].encode("utf-8"),
    ):
        raise HTTPException(401, "Contraseña incorrecta")


def _get_redis():
    """Get Redis client."""
    from services.relay import get_redis

    r = get_redis()
    if r is None:
        raise HTTPException(503, "Redis no disponible")
    return r


# --- POST /start ---


@router.post("/sync/start")
async def start_ycloud_sync(
    body: SyncStartRequest,
    background_tasks: BackgroundTasks,
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Start full WhatsApp message sync for the tenant.

    Requires CEO authentication + password verification.
    """
    try:
        # Verify password
        await _verify_password(user_data, body.password)

        # Check tenant has YCloud configured
        from db import db

        tenant_row = await db.pool.fetchrow(
            "SELECT config FROM tenants WHERE id = $1", tenant_id
        )
        if not tenant_row:
            raise HTTPException(404, "Tenant no encontrado")

        config = tenant_row["config"] or {}
        if isinstance(config, str):
            import json as _json
            try:
                config = _json.loads(config)
            except Exception:
                config = {}

        # Check API key from credentials vault (same as get_config)
        from core.credentials import get_tenant_credential, YCLOUD_API_KEY
        ycloud_api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)

        if not ycloud_api_key:
            raise HTTPException(
                400, "YCloud API key no configurada. Configurá primero en Settings → YCloud."
            )

        # Start sync via service
        from services import ycloud_sync_service

        result = await ycloud_sync_service.start_sync(
            db=db,
            tenant_id=tenant_id,
            password=body.password,
            background_tasks=background_tasks,
        )

        if result.get("error"):
            raise HTTPException(400, result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ycloud_sync] start failed: {e}")
        raise HTTPException(500, f"Error al iniciar sincronización: {str(e)}")


# --- GET /status/{task_id} ---


@router.get("/sync/active")
async def get_active_sync(
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Check if there's an active sync running for this tenant. Returns progress or null."""
    try:
        from services.relay import get_redis
        r = get_redis()
        if not r:
            return {"active": False}

        # Check lock first
        lock_key = f"ycloud_sync_lock:{tenant_id}"
        has_lock = await r.exists(lock_key)
        if not has_lock:
            return {"active": False}

        # Scan for active progress keys
        import json as _json
        cursor_val = 0
        while True:
            cursor_val, keys = await r.scan(cursor_val, match=f"ycloud_sync:{tenant_id}:*", count=20)
            for key in keys:
                raw = await r.get(key)
                if raw:
                    progress = _json.loads(raw)
                    if progress.get("status") in ("processing", "queued"):
                        return {"active": True, **progress}
            if cursor_val == 0:
                break

        return {"active": False}

    except Exception as e:
        logger.warning(f"[ycloud_sync] active check failed: {e}")
        return {"active": False}


@router.get("/sync/status/{task_id}")
async def get_sync_status(
    task_id: str,
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Get sync task progress from Redis.
    """
    try:
        from services import ycloud_sync_service

        progress = await ycloud_sync_service._get_progress(tenant_id, task_id)

        if not progress:
            raise HTTPException(404, "Tarea no encontrada")

        # Verify it belongs to this tenant
        if progress.get("tenant_id") != tenant_id:
            raise HTTPException(403, "No autorizado para esta tarea")

        return progress

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ycloud_sync] get_status failed: {e}")
        raise HTTPException(500, f"Error al obtener estado: {str(e)}")


# --- POST /cancel/{task_id} ---


@router.post("/sync/cancel/{task_id}")
async def cancel_ycloud_sync(
    task_id: str,
    body: SyncStartRequest,  # Reuse for password
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Cancel a running sync task.

    Requires CEO authentication + password.
    """
    try:
        # Verify password
        await _verify_password(user_data, body.password)

        # Cancel via service
        from services import ycloud_sync_service

        cancelled = await ycloud_sync_service.cancel_sync(tenant_id, task_id)

        if not cancelled:
            raise HTTPException(
                400, "No se puede cancelar. La tarea puede haber terminado."
            )

        return {"message": "Sincronización cancelada", "task_id": task_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ycloud_sync] cancel failed: {e}")
        raise HTTPException(500, f"Error al cancelar: {str(e)}")


# --- GET /config/{tenant_id} ---


@router.get("/sync/config/{tenant_id}")
async def get_sync_config(
    tenant_id: int,
    user_data=Depends(verify_ceo_token),
    _: int = Depends(get_resolved_tenant_id),
):
    """
    Get sync settings for a tenant.

    Only CEO can view.
    """
    try:
        from db import db

        tenant_row = await db.pool.fetchrow(
            "SELECT config FROM tenants WHERE id = $1", tenant_id
        )
        if not tenant_row:
            raise HTTPException(404, "Tenant no encontrado")

        config = tenant_row["config"] or {}
        if isinstance(config, str):
            import json
            try:
                config = json.loads(config)
            except Exception:
                config = {}

        # Check API key from credentials vault (not tenants.config)
        api_key_configured = False
        try:
            from core.credentials import get_tenant_credential, YCLOUD_API_KEY
            api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
            api_key_configured = bool(api_key)
        except Exception:
            pass

        return {
            "tenant_id": tenant_id,
            "sync_enabled": config.get("ycloud_sync_enabled", True),
            "max_messages": config.get("ycloud_max_messages", 10000),
            "ycloud_api_key_configured": api_key_configured,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ycloud_sync] get_config failed: {e}")
        raise HTTPException(500, f"Error al obtener configuración: {str(e)}")


# --- PATCH /config/{tenant_id} ---


@router.patch("/sync/config/{tenant_id}")
async def update_sync_config(
    tenant_id: int,
    body: SyncConfigUpdate,
    user_data=Depends(verify_ceo_token),
    _: int = Depends(get_resolved_tenant_id),
):
    """
    Update sync settings for a tenant.

    Only CEO can modify.
    """
    try:
        from db import db

        # Get current config
        tenant_row = await db.pool.fetchrow(
            "SELECT config FROM tenants WHERE id = $1", tenant_id
        )
        if not tenant_row:
            raise HTTPException(404, "Tenant no encontrado")

        config = dict(tenant_row["config"] or {})

        # Update fields
        if body.sync_enabled is not None:
            config["ycloud_sync_enabled"] = body.sync_enabled
        if body.max_messages is not None:
            if body.max_messages < 100 or body.max_messages > 50000:
                raise HTTPException(400, "max_messages debe estar entre 100 y 50000")
            config["ycloud_max_messages"] = body.max_messages

        # Save
        await db.pool.execute(
            "UPDATE tenants SET config = $1 WHERE id = $2",
            config,
            tenant_id,
        )

        return {
            "tenant_id": tenant_id,
            "sync_enabled": config.get("ycloud_sync_enabled", True),
            "max_messages": config.get("ycloud_max_messages", 10000),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ycloud_sync] update_config failed: {e}")
        raise HTTPException(500, f"Error al actualizar configuración: {str(e)}")


# --- POST /sync/purge/{tenant_id} (delete all synced data) ---


@router.post("/sync/purge/{tenant_id}")
async def purge_synced_data(
    tenant_id: int,
    user_data=Depends(verify_ceo_token),
    _: int = Depends(get_resolved_tenant_id),
):
    """
    Delete ALL chat conversations and messages for a tenant.
    Use after a bad sync to clean up and start fresh.
    CEO only. Destructive operation.
    """
    try:
        from db import db

        logger.info(f"[ycloud_sync] PURGE started for tenant {tenant_id} by user {getattr(user_data, 'user_id', '?')}")

        # Count before deleting (for response)
        msg_count = await db.pool.fetchval(
            "SELECT COUNT(*) FROM chat_messages WHERE tenant_id = $1", tenant_id
        )
        conv_count = await db.pool.fetchval(
            "SELECT COUNT(*) FROM chat_conversations WHERE tenant_id = $1", tenant_id
        )

        logger.info(f"[ycloud_sync] PURGE: found {conv_count} conversations, {msg_count} messages for tenant {tenant_id}")

        # Delete messages first (FK dependency)
        deleted_msgs = await db.pool.execute(
            "DELETE FROM chat_messages WHERE tenant_id = $1", tenant_id
        )
        logger.info(f"[ycloud_sync] PURGE: deleted messages result: {deleted_msgs}")

        # Delete conversations
        deleted_convs = await db.pool.execute(
            "DELETE FROM chat_conversations WHERE tenant_id = $1", tenant_id
        )
        logger.info(f"[ycloud_sync] PURGE: deleted conversations result: {deleted_convs}")

        # Delete inbound_messages dedup records
        try:
            await db.pool.execute(
                "DELETE FROM inbound_messages WHERE tenant_id = $1", tenant_id
            )
            logger.info(f"[ycloud_sync] PURGE: cleared inbound_messages dedup for tenant {tenant_id}")
        except Exception as e:
            logger.warning(f"[ycloud_sync] PURGE: inbound_messages cleanup skipped: {e}")

        logger.info(
            f"[ycloud_sync] PURGE complete for tenant {tenant_id}: "
            f"{conv_count} conversations, {msg_count} messages deleted"
        )

        return {
            "status": "purged",
            "tenant_id": tenant_id,
            "conversations_deleted": conv_count,
            "messages_deleted": msg_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ycloud_sync] PURGE failed for tenant {tenant_id}: {e}")
        raise HTTPException(500, f"Error al eliminar datos: {str(e)}")


# --- GET /sync/tasks (S6) ---


@router.get("/sync/tasks")
async def list_sync_tasks(
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    List all sync tasks for the tenant (S6).

    Returns current running task + recent history.
    """
    try:
        r = _get_redis()

        # Get current running task
        current_key = f"ycloud_sync:{tenant_id}:current"
        current_task = r.get(current_key)
        current = None
        if current_task:
            task_data = r.hgetall(f"ycloud_sync:{tenant_id}:{current_task}")
            if task_data:
                current = {
                    "task_id": current_task,
                    "status": task_data.get(b"status", b"unknown").decode(),
                    "started_at": task_data.get(b"started_at", b"").decode(),
                }

        # Get recent tasks from history (last 10)
        history = []
        history_key = f"ycloud_sync:{tenant_id}:history"
        task_ids = r.lrange(history_key, 0, 9)

        for task_id in task_ids:
            task_data = r.hgetall(f"ycloud_sync:{tenant_id}:{task_id.decode()}")
            if task_data:
                history.append(
                    {
                        "task_id": task_id.decode(),
                        "status": task_data.get(b"status", b"unknown").decode(),
                        "started_at": task_data.get(b"started_at", b"").decode(),
                        "completed_at": task_data.get(b"completed_at", b"").decode(),
                        "messages_fetched": int(task_data.get(b"messages_fetched", 0)),
                        "messages_saved": int(task_data.get(b"messages_saved", 0)),
                        "media_downloaded": int(task_data.get(b"media_downloaded", 0)),
                    }
                )

        return {
            "current": current,
            "history": history,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ycloud_sync] list_tasks failed: {e}")
        raise HTTPException(500, f"Error al listar tareas: {str(e)}")


# --- GET /sync/history (S7) ---


@router.get("/sync/history")
async def get_sync_history(
    page: int = 1,
    limit: int = 20,
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Get sync history with pagination (S7).

    Query params: page (default 1), limit (default 20, max 100)
    """
    try:
        if limit > 100:
            limit = 100
        if limit < 1:
            limit = 1
        if page < 1:
            page = 1

        r = _get_redis()

        # Get total count
        history_key = f"ycloud_sync:{tenant_id}:history"
        total = r.llen(history_key)

        # Calculate offset
        offset = (page - 1) * limit

        # Get page items
        task_ids = r.lrange(history_key, offset, offset + limit - 1)

        tasks = []
        for task_id in task_ids:
            task_data = r.hgetall(f"ycloud_sync:{tenant_id}:{task_id.decode()}")
            if task_data:
                tasks.append(
                    {
                        "task_id": task_id.decode(),
                        "status": task_data.get(b"status", b"unknown").decode(),
                        "started_at": task_data.get(b"started_at", b"").decode(),
                        "completed_at": task_data.get(b"completed_at", b"").decode(),
                        "messages_fetched": int(task_data.get(b"messages_fetched", 0)),
                        "messages_saved": int(task_data.get(b"messages_saved", 0)),
                        "media_downloaded": int(task_data.get(b"media_downloaded", 0)),
                        "errors": task_data.get(b"errors", b"").decode().split("|||")
                        if task_data.get(b"errors")
                        else [],
                    }
                )

        return {
            "page": page,
            "limit": limit,
            "total": total,
            "tasks": tasks,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ycloud_sync] get_history failed: {e}")
        raise HTTPException(500, f"Error al obtener historial: {str(e)}")


# --- GET /whatsapp-messages (S8) ---


@router.get("/whatsapp-messages")
async def get_whatsapp_messages(
    phone: Optional[str] = None,
    direction: Optional[str] = None,
    message_type: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """
    Query synced WhatsApp messages (S8).

    Query params:
    - phone: filter by phone number
    - direction: 'inbound' or 'outbound'
    - message_type: 'text', 'image', 'audio', 'video', 'document'
    - since: ISO datetime filter (created_at >=)
    - until: ISO datetime filter (created_at <=)
    - page: page number (default 1)
    - limit: items per page (default 50, max 100)
    """
    try:
        if limit > 100:
            limit = 100
        if limit < 1:
            limit = 1
        if page < 1:
            page = 1

        from db import db

        # Build query
        conditions = ["tenant_id = $1"]
        params = [tenant_id]
        param_idx = 2

        if phone:
            conditions.append(
                f"(from_number ILIKE ${param_idx} OR to_number ILIKE ${param_idx})"
            )
            params.append(f"%{phone}%")
            param_idx += 1

        if direction:
            conditions.append(f"direction = ${param_idx}")
            params.append(direction)
            param_idx += 1

        if message_type:
            conditions.append(f"message_type = ${param_idx}")
            params.append(message_type)
            param_idx += 1

        if since:
            conditions.append(f"created_at >= ${param_idx}::timestamptz")
            params.append(since)
            param_idx += 1

        if until:
            conditions.append(f"created_at <= ${param_idx}::timestamptz")
            params.append(until)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        # Get total count
        count_query = (
            f"SELECT COUNT(*) as total FROM whatsapp_messages WHERE {where_clause}"
        )
        total_row = await db.pool.fetchrow(count_query, *params)
        total = total_row["total"] if total_row else 0

        # Get paginated results
        offset = (page - 1) * limit
        query = f"""
            SELECT id, external_id, wamid, from_number, to_number, direction, 
                   message_type, content, media_url, status, patient_id, 
                   created_at, synced_at
            FROM whatsapp_messages
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        rows = await db.pool.fetch(query, *params)

        messages = []
        for row in rows:
            messages.append(
                {
                    "id": row["id"],
                    "external_id": row["external_id"],
                    "wamid": row["wamid"],
                    "from_number": row["from_number"],
                    "to_number": row["to_number"],
                    "direction": row["direction"],
                    "message_type": row["message_type"],
                    "content": row["content"],
                    "media_url": row["media_url"],
                    "status": row["status"],
                    "patient_id": row["patient_id"],
                    "created_at": row["created_at"].isoformat()
                    if row["created_at"]
                    else None,
                    "synced_at": row["synced_at"].isoformat()
                    if row["synced_at"]
                    else None,
                }
            )

        return {
            "page": page,
            "limit": limit,
            "total": total,
            "messages": messages,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ycloud_sync] get_whatsapp_messages failed: {e}")
        raise HTTPException(500, f"Error al obtener mensajes: {str(e)}")
