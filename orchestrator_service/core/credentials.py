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
YCLOUD_WHATSAPP_NUMBER = "YCLOUD_WHATSAPP_NUMBER"

# Meta Ads
META_APP_ID = "META_APP_ID"
META_APP_SECRET = "META_APP_SECRET"
META_USER_LONG_TOKEN = "META_USER_LONG_TOKEN"


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
    val = str(row["value"]).strip()
    # Detectar si parece fernet (opcional, por ahora intentamos desencriptar si falla usamos el valor raw)
    # Pero admin_routes._decrypt_credential no es accesible aquí fácilmente sin ciclo de importación.
    # Movemos la lógica de criptografía a un util o la duplicamos aquí mínimamente.
    
    # MEJORA: Importar funcion de desencriptado de un modulo común si existiera, 
    # pero como está en admin_routes (mala practica), lo mejor es mover las funciones crypto a 
    # core/security.py o similar. Por ahora, para no romper, implementamos desencriptado inline 
    # o movemos _get_fernet aquí.
    
    try:
        from cryptography.fernet import Fernet
        import os
        key = os.getenv("CREDENTIALS_FERNET_KEY")
        if key:
            f = Fernet(key.encode("utf-8") if isinstance(key, str) else key)
            try:
                # Intentar decriptar
                return f.decrypt(val.encode("ascii")).decode("utf-8")
            except:
                # Si falla, asumir que estaba en texto plano (migración gradual)
                return val
    except Exception as e:
        logger.warning(f"Error decrypting credential {name}: {e}")
    
    return val


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
    # Encriptar si hay una key configurada
    from cryptography.fernet import Fernet
    import os
    final_value = value
    key = os.getenv("CREDENTIALS_FERNET_KEY")
    if key:
        try:
            f = Fernet(key.encode("utf-8") if isinstance(key, str) else key)
            final_value = f.encrypt(value.encode("utf-8")).decode("ascii")
        except Exception as e:
            logger.error(f"Error encrypting credential {name}: {e}")
            
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
