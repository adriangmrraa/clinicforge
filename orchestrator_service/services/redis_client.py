import os
import redis.asyncio as redis

_redis_client = None


def get_redis():
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        _redis_client = redis.from_url(redis_url, decode_responses=True)
    return _redis_client
