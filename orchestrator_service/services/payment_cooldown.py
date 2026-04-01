"""
Redis cooldown mechanism for payment verification.

Prevents re-triggering payment verification within a configurable time window.
Key pattern: `payment_verify_cooldown:{tenant_id}:{phone_number}`

Spec: WhatsApp Agent Loop Bug Fix (v8.1)
"""

import logging
import os

logger = logging.getLogger(__name__)

# Default TTL: 10 minutes (600 seconds)
DEFAULT_COOLDOWN_SECONDS = int(os.getenv("PAYMENT_VERIFY_COOLDOWN_SECONDS", "600"))


def _get_redis():
    """Get Redis client from relay module (graceful fallback)."""
    try:
        from services.relay import get_redis

        return get_redis()
    except ImportError:
        logger.warning("Redis not available (relay module missing)")
        return None


async def check_payment_cooldown(tenant_id: int, phone_number: str) -> bool:
    """
    Check if a payment verification cooldown is active for this tenant+phone.

    Returns:
        True if cooldown active (verification should be skipped)
        False if cooldown inactive or Redis unavailable
    """
    redis_client = _get_redis()
    if not redis_client:
        logger.debug("Redis unavailable, treating cooldown as inactive")
        return False

    key = f"payment_verify_cooldown:{tenant_id}:{phone_number}"
    try:
        exists = await redis_client.exists(key)
        if exists:
            logger.info(
                f"Payment verification cooldown active for tenant {tenant_id}, phone {phone_number}"
            )
            return True
        return False
    except Exception as e:
        logger.warning(f"Redis error checking cooldown: {e}")
        return False


async def set_payment_cooldown(
    tenant_id: int, phone_number: str, ttl_seconds: int = None
) -> None:
    """
    Set a payment verification cooldown for this tenant+phone.

    Args:
        tenant_id: Tenant ID
        phone_number: Patient phone number
        ttl_seconds: Cooldown duration in seconds (defaults to env var or 600)
    """
    if ttl_seconds is None:
        ttl_seconds = DEFAULT_COOLDOWN_SECONDS

    redis_client = _get_redis()
    if not redis_client:
        logger.warning("Redis unavailable, cannot set payment cooldown")
        return

    key = f"payment_verify_cooldown:{tenant_id}:{phone_number}"
    try:
        await redis_client.setex(key, ttl_seconds, "1")
        logger.info(
            f"Payment verification cooldown set for tenant {tenant_id}, phone {phone_number} (TTL: {ttl_seconds}s)"
        )
    except Exception as e:
        logger.warning(f"Redis error setting cooldown: {e}")
        # Continue gracefully — cooldown just won't be active
