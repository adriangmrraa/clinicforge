"""
Greeting state management via Redis.

Tracks whether a patient has already been greeted in the current session
to avoid repeating the institutional greeting on every message.

Redis key: greet:{tenant_id}:{phone_number}
TTL: 604800 seconds (7 days) — FIX #7 caso Stella: con 4h, un paciente conocido que
volvía al día siguiente recibía de nuevo el pitch institucional de "lead nuevo"
ignorando su pregunta. Con 7 días no se re-presenta dentro de la semana.
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
        await r.setex(key, 604800, "1")  # TTL 7 días (FIX #7: antes 4h → paciente conocido re-saludado al otro día)
    except Exception:
        pass  # Silent failure — next message will just greet again
