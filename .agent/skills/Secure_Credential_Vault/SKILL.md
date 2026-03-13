---
name: Secure Credential Vault
description: Patrón de seguridad para gestión de secretos multi-tenant con encriptación Fernet (AES-256).
---

# Secure Credential Vault (SCV) Protocol

Este protocolo define cómo almacenar, recuperar y utilizar credenciales sensibles (tokens de API, claves secretas) en un entorno multi-tenant, garantizando el aislamiento y la seguridad en reposo.

## Principios Fundamentales
1. **Encriptación en Reposo**: NUNCA guardar secretos en texto plano. Usar Fernet (AES-256).
2. **Aislamiento por Tenant**: Cada credencial pertenece estrictamente a un `tenant_id` (salvo que sea Global/CEO).
3. **Decriptación On-The-Fly**: Las credenciales solo se desencriptan en memoria al momento de usarse.
4. **Sanitización en UI**: La API nunca devuelve el valor real al frontend, solo máscaras (`••••AT12`).
5. **Fallback Jerárquico**: `DB (Tenant) > ENV (Global) > Error`.

## Estructura de Base de Datos
La tabla `credentials` es la bóveda:
```sql
CREATE TABLE credentials (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id), -- NULL para globales
    category TEXT NOT NULL, -- ej: 'chatwoot', 'openai', 'google_calendar'
    name TEXT NOT NULL, -- ej: 'api_token', 'access_token'
    value TEXT NOT NULL, -- CIFRADO con Fernet
    scope TEXT DEFAULT 'tenant', -- 'global' | 'tenant'
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Implementación de Referencia (Python/FastAPI)

### 1. Encriptación/Decriptación (Utils)
```python
from cryptography.fernet import Fernet
import os

# Clave maestra en variable de entorno (Base64 URL-safe)
FERNET_KEY = os.getenv("CREDENTIALS_FERNET_KEY")

def encrypt(plain: str) -> str:
    f = Fernet(FERNET_KEY.encode())
    return f.encrypt(plain.encode()).decode()

def decrypt(cipher: str) -> str:
    f = Fernet(FERNET_KEY.encode())
    return f.decrypt(cipher.encode()).decode()
```

### 2. Recuperación Segura (Service Layer)
```python
async def get_tenant_credential(tenant_id: int, name: str) -> Optional[str]:
    # 1. Buscar en DB
    row = await db.fetchrow(
        "SELECT value FROM credentials WHERE tenant_id = $1 AND name = $2", 
        tenant_id, name
    )
    
    if row:
        # 2. Desencriptar
        try:
             return decrypt(row['value'])
        except:
             return None # Fallo integridad
             
    # 3. Fallback ENV (Solo si es permitido por política)
    return os.getenv(name)
```

### 3. API de Gestión (Admin Panel)

*   **GET /admin/credentials**: Devuelve lista. `value` siempre enmascarado.
*   **POST /admin/credentials**: Recibe `value` en plano, lo encripta INMEDIATAMENTE y guarda el cifrado.
*   **DELETE /admin/credentials/{id}**: Eliminación dura.

## Casos de Uso Comunes

### Chatwoot Integration
*   **Bot**: Usa `get_tenant_credential(tid, 'CHATWOOT_API_TOKEN')` para responder.
*   **Webhook**: Valida `WEBHOOK_ACCESS_TOKEN` contra el vault para autenticar payloads.

```python
async def resolve_tenant_from_webhook_token(token: str) -> Optional[int]:
    # Busca tenant_id donde (name='WEBHOOK_ACCESS_TOKEN' AND value=token)
    # Nota: Los tokens de webhook a veces se guardan en plano si son generados por el sistema y no sensibles de lectura,
    # pero idealmente deberían estar cifrados y el sistema debería probar desencriptar o usar un hash.
    # En la implementación actual v1.0, se asume búsqueda directa por valor (si no está cifrado) o
    # descifrado iterativo (costoso) si estuviera cifrado.
    # Recomendación: Usar un HASH (SHA256) del token para búsquedas rápidas si el token es secreto.
    pass
```

### Google Calendar
*   Tokens de OAuth2 (Access/Refresh) se guardan cifrados.
*   Al refrescar el token, se actualiza el registro cifrado en DB.
