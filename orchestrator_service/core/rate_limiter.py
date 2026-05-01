"""
Unified rate limiter — proxy-aware IP detection + Redis storage.

All routers import `limiter` from here. The FastAPI app in main.py must
assign it to `app.state.limiter` for slowapi to pick it up automatically.
"""
import os

from slowapi import Limiter
from starlette.requests import Request


def _get_real_client_ip(request: Request) -> str:
    """
    Resolve the real client IP behind Cloudflare / nginx / EasyPanel proxies.

    Priority:
    1. CF-Connecting-IP  — set by Cloudflare, always the true end-user IP
    2. X-Forwarded-For   — first entry (closest to the client)
    3. request.client.host — direct TCP peer (fallback for local dev)
    """
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()

    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()

    return request.client.host if request.client else "unknown"


limiter = Limiter(
    key_func=_get_real_client_ip,
    storage_uri=os.getenv("REDIS_URL", "memory://"),
)
