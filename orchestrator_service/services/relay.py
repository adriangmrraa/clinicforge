"""
Relay y Atomic Buffer (16s) para Chatwoot.
CLINICASV1.0 - paridad con Version Estable.
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as redis
    _redis: Optional[redis.Redis] = None

    def get_redis():
        global _redis
        if _redis is None:
            import os
            url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            _redis = redis.from_url(url, decode_responses=True)
        return _redis
except ImportError:
    def get_redis():
        return None


BUFFER_TTL_SECONDS = 16


async def enqueue_buffer_and_schedule_task(tenant_id: int, conversation_id: str, external_user_id: str):
    """Encola mensaje y programa process_buffer_task tras BUFFER_TTL_SECONDS."""
    r = get_redis()
    if not r:
        logger.warning("redis_not_available_skipping_buffer")
        return
    buffer_key = f"buffer:{tenant_id}:{external_user_id}"
    timer_key = f"timer:{tenant_id}:{external_user_id}"
    lock_key = f"active_task:{tenant_id}:{external_user_id}"
    from db import get_pool
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT content FROM chat_messages WHERE conversation_id = $1 ORDER BY created_at DESC LIMIT 1",
        conversation_id,
    )
    if not row:
        return
    content = row["content"] or ""
    await r.rpush(buffer_key, content)
    await r.setex(timer_key, BUFFER_TTL_SECONDS, "1")
    if not await r.get(lock_key):
        await r.setex(lock_key, 60, "1")
        asyncio.create_task(_delayed_process_buffer_task(tenant_id, conversation_id, external_user_id, buffer_key, timer_key, lock_key))


async def _delayed_process_buffer_task(
    tenant_id: int, conversation_id: str, external_user_id: str,
    buffer_key: str, timer_key: str, lock_key: str,
):
    await asyncio.sleep(BUFFER_TTL_SECONDS)
    r = get_redis()
    if not r:
        return
    try:
        messages = await r.lrange(buffer_key, 0, -1)
        await r.delete(buffer_key)
        if not messages:
            return
        try:
            from services.buffer_task import process_buffer_task
            await process_buffer_task(tenant_id, conversation_id, external_user_id, messages)
        except ImportError:
            logger.warning("buffer_task.process_buffer_task not implemented")
    finally:
        if r:
            await r.delete(lock_key)
