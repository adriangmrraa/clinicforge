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


BUFFER_TTL_SECONDS = 10


async def enqueue_buffer_and_schedule_task(tenant_id: int, conversation_id: str, external_user_id: str):
    """Encola mensaje y programa process_buffer_task con Sliding Window."""
    r = get_redis()
    if not r:
        logger.warning("redis_not_available_skipping_buffer")
        return
    buffer_key = f"buffer:{tenant_id}:{external_user_id}"
    timer_key = f"timer:{tenant_id}:{external_user_id}"
    lock_key = f"active_task:{tenant_id}:{external_user_id}"
    from db import get_pool
    import json
    pool = get_pool()
    
    # Spec 24/25: Dynamic TTL (Sliding Window)
    row = await pool.fetchrow(
        "SELECT content, content_attributes FROM chat_messages WHERE conversation_id = $1 ORDER BY created_at DESC LIMIT 1",
        conversation_id,
    )
    if not row:
        return
    content = row["content"] or ""
    
    # 1. Determine Target TTL for THIS message
    req_ttl = BUFFER_TTL_SECONDS
    try:
        attrs = row["content_attributes"]
        if attrs:
            if isinstance(attrs, str):
                attrs = json.loads(attrs)
            if isinstance(attrs, list):
                if any(str(a.get("type")).lower() == "image" for a in attrs):
                    req_ttl = 20
                    logger.info(f"⏳ Vision Buffer: Image detected, requiring {req_ttl}s")
    except Exception as e:
        logger.warning(f"Error checking attributes for TTL: {e}")

    await r.rpush(buffer_key, content)
    
    # 2. Sliding Window Calculation
    # If active timer exists, we want to extend it, but NEVER reduce it below what's currently remaining.
    current_ttl = await r.ttl(timer_key)
    if current_ttl < 0:
        current_ttl = 0
        
    final_ttl = max(current_ttl, req_ttl)
    await r.setex(timer_key, final_ttl, "1")
    
    # 3. Ensure Consumer Task is running
    if not await r.get(lock_key):
        await r.setex(lock_key, 60 + final_ttl, "1") # Lock ensures only one task runs per batch
        asyncio.create_task(_delayed_process_buffer_task(tenant_id, conversation_id, external_user_id, buffer_key, timer_key, lock_key))


async def _delayed_process_buffer_task(
    tenant_id: int, conversation_id: str, external_user_id: str,
    buffer_key: str, timer_key: str, lock_key: str,
):
    """
    Consumer Task con Debounce Loop.
    Espera hasta que el timer expire (silencio total).
    """
    r = get_redis()
    if not r:
        return
    
    try:
        # Loop Check (Debounce)
        while True:
            # Check remaining time
            rem_ttl = await r.ttl(timer_key)
            
            if rem_ttl > 0:
                # Still waiting for silence...
                # logger.debug(f"⏳ Debouncing... sleeping {rem_ttl}s")
                await asyncio.sleep(rem_ttl)
            else:
                # Timer expired (or deleted). Silence detected.
                break
        
        # Process Buffer
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
