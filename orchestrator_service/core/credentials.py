"""
Vault: credenciales por tenant. Para Chatwoot y agente IA.
CLINICASV1.0 - paridad con Version Estable.
"""
import logging
import os
from typing import Optional, Any
from cryptography.fernet import Fernet

# Configuración Global de Seguridad
CREDENTIALS_FERNET_KEY = os.getenv("CREDENTIALS_FERNET_KEY")

logger = logging.getLogger(__name__)

def encrypt_value(value: str) -> str:
    """Encripta un valor usando Fernet si la clave está configurada."""
    if not CREDENTIALS_FERNET_KEY:
        return value
    try:
        f = Fernet(CREDENTIALS_FERNET_KEY.encode("utf-8") if isinstance(CREDENTIALS_FERNET_KEY, str) else CREDENTIALS_FERNET_KEY)
        return f.encrypt(value.encode("utf-8")).decode("ascii")
    except Exception as e:
        logger.error(f"Error encrypting value: {e}")
        return value

def decrypt_value(cipher: str) -> str:
    """Desencripta un valor usando Fernet si la clave está configurada."""
    if not CREDENTIALS_FERNET_KEY or not cipher:
        return cipher
    try:
        f = Fernet(CREDENTIALS_FERNET_KEY.encode("utf-8") if isinstance(CREDENTIALS_FERNET_KEY, str) else CREDENTIALS_FERNET_KEY)
        return f.decrypt(cipher.strip().encode("ascii")).decode("utf-8")
    except Exception:
        # Si falla, asumir que está en texto plano (migración gradual)
        return cipher

from db import get_pool

CHATWOOT_API_TOKEN = "CHATWOOT_API_TOKEN"
CHATWOOT_ACCOUNT_ID = "CHATWOOT_ACCOUNT_ID"
CHATWOOT_BASE_URL = "CHATWOOT_BASE_URL"
WEBHOOK_ACCESS_TOKEN = "WEBHOOK_ACCESS_TOKEN"
YCLOUD_API_KEY = "YCLOUD_API_KEY"
YCLOUD_WEBHOOK_SECRET = "YCLOUD_WEBHOOK_SECRET"
YCLOUD_WHATSAPP_NUMBER = "YCLOUD_WHATSAPP_NUMBER"

META_USER_LONG_TOKEN = "META_USER_LONG_TOKEN"
META_APP_ID = "META_APP_ID"
META_APP_SECRET = "META_APP_SECRET"


async def get_tenant_credential(tenant_id: int, name: str) -> Optional[str]:
    """Obtiene el valor de una credencial del tenant desde la tabla credentials."""
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT value FROM credentials WHERE tenant_id = $1 AND name = $2 LIMIT 1",
        tenant_id,
        name,
    )
    if not row or not row["value"]:
        # Fallback a variable de entorno global (Nexus Resilience Protocol)
        import os
        env_val = os.getenv(name)
        return env_val.strip() if env_val else None
    
    # Intentar decriptar si es un valor encriptado (Fernet)
    return decrypt_value(str(row["value"]))


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


async def save_tenant_credential(tenant_id: int, name: str, value: str, category: str = "general") -> bool:
    """Guarda o actualiza una credencial para un tenant."""
    pool = get_pool()
    final_value = encrypt_value(value)
            
    try:
        await pool.execute("""
            INSERT INTO credentials (tenant_id, name, value, category, updated_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (tenant_id, name) 
            DO UPDATE SET value = $3, category = $4, updated_at = NOW()
        """, tenant_id, name, final_value, category)
        return True
    except Exception as e:
        logger.error(f"Error saving credential {name} for tenant {tenant_id}: {e}")
        return False
