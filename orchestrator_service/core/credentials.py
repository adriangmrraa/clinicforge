"""
Vault: credenciales por tenant. Para Chatwoot y agente IA.
CLINICASV1.0 - paridad con Version Estable.
"""
import logging
from typing import Optional

from db import get_pool

logger = logging.getLogger(__name__)

CHATWOOT_API_TOKEN = "CHATWOOT_API_TOKEN"
CHATWOOT_ACCOUNT_ID = "CHATWOOT_ACCOUNT_ID"
CHATWOOT_BASE_URL = "CHATWOOT_BASE_URL"
WEBHOOK_ACCESS_TOKEN = "WEBHOOK_ACCESS_TOKEN"
YCLOUD_API_KEY = "YCLOUD_API_KEY"
YCLOUD_WEBHOOK_SECRET = "YCLOUD_WEBHOOK_SECRET"


async def get_tenant_credential(tenant_id: int, name: str) -> Optional[str]:
    """Obtiene el valor de una credencial del tenant desde la tabla credentials."""
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT value FROM credentials WHERE tenant_id = $1 AND name = $2 LIMIT 1",
        tenant_id,
        name,
    )
    if not row or not row["value"]:
        return None
    return str(row["value"]).strip()


async def get_tenant_credential_int(tenant_id: int, name: str) -> Optional[int]:
    """Conveniencia para credenciales numéricas (ej. CHATWOOT_ACCOUNT_ID)."""
    v = await get_tenant_credential(tenant_id, name)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None


async def resolve_tenant_from_webhook_token(access_token: str) -> Optional[int]:
    """Resuelve tenant_id desde WEBHOOK_ACCESS_TOKEN (para webhook Chatwoot)."""
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT tenant_id FROM credentials WHERE name = $1 AND value = $2 LIMIT 1",
        WEBHOOK_ACCESS_TOKEN,
        access_token.strip(),
    )
    return int(row["tenant_id"]) if row else None
