"""
Greeting state management via Redis.

Tracks whether a patient has already been greeted in the current session
to avoid repeating the institutional greeting on every message.

Redis key: greet:{tenant_id}:{phone_number}
TTL: 14400 seconds (4 hours)
Fallback: if Redis is unavailable, has_greeted returns False (conservative — greet again)
"""


async def has_greeted(tenant_id: int, phone_number: str) -> bool:
    """Check if greeting was already sent for this tenant+phone session."""
    try:
        from services.relay import get_redis

        r = get_redis()
        if r is None:
            return False
        key = f"greet:{tenant_id}:{phone_number}"
        val = await r.get(key)
        return val is not None
    except Exception:
        return False  # Conservative fallback: assume not greeted


async def mark_greeted(tenant_id: int, phone_number: str) -> None:
    """Mark that greeting was sent. Silent failure if Redis unavailable."""
    try:
        from services.relay import get_redis

        r = get_redis()
        if r is None:
            return
        key = f"greet:{tenant_id}:{phone_number}"
        await r.setex(key, 14400, "1")  # TTL 4 hours
    except Exception:
        pass  # Silent failure — next message will just greet again
