# Prompt para OpenCode — Remediación de Seguridad ClinicForge

> **Instrucciones**: Copiar este prompt completo y pegarlo en OpenCode. Ejecutar los 3 packs en orden. Cada pack tiene verificaciones al final — NO avanzar al siguiente pack hasta que todas pasen.

---

## PROMPT

```
Sos un ingeniero de seguridad senior. Tu tarea es remediar las vulnerabilidades identificadas en la auditoría de seguridad de ClinicForge. Leé primero el archivo docs/SECURITY_AUDIT_2026-04-11.md para contexto completo.

REGLAS ESTRICTAS:
- NO agregues features nuevas, solo corregí vulnerabilidades
- NO refactorices código que no esté directamente relacionado con la vulnerabilidad
- NO cambies la lógica de negocio existente
- Cada fix debe ser lo más pequeño y quirúrgico posible
- Verificá que no rompas tests existentes después de cada cambio
- Antes de escribir migrations, ejecutá: ls orchestrator_service/alembic/versions/ para confirmar el head real
- Usá conventional commits: fix(security): descripción corta
- NUNCA hardcodees secrets, tokens, o credenciales

---

## PACK 1 — CRITICAL (ejecutar primero, todo junto)

### Task 1.1: Eliminar credenciales hardcodeadas del frontend
Archivo: frontend_react/src/views/LoginView.tsx
Líneas: 13-14

Acción:
- Eliminar las constantes DEMO_EMAIL y DEMO_PASSWORD
- Si hay un botón "Demo" que las usa, reemplazar con lectura de import.meta.env.VITE_DEMO_EMAIL y import.meta.env.VITE_DEMO_PASSWORD
- Si las env vars no existen, ocultar el botón demo completamente
- NO agregar valores default

Verificación: rg "DEMO_PASSWORD|Wstg1793|gamarraadrian200" frontend_react/ → 0 resultados

### Task 1.2: Crear migración para columna external_ids
Archivo nuevo: orchestrator_service/alembic/versions/033_add_external_ids_column.py

IMPORTANTE: Primero ejecutá ls orchestrator_service/alembic/versions/ para confirmar el head real. Si el último archivo NO es 032, ajustá el número.

Contenido de la migración:
```python
"""Add external_ids JSONB column to patients table"""

revision = '033'
down_revision = '032'  # VERIFICAR QUE ESTE SEA EL HEAD REAL

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

def upgrade():
    op.add_column('patients', sa.Column('external_ids', sa.JSON(), nullable=True, server_default=text("'{}'::jsonb")))

def downgrade():
    op.drop_column('patients', 'external_ids')
```

También agregar al modelo ORM en orchestrator_service/models.py, en la clase Patient:
```python
external_ids = Column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
```

Verificación: rg "external_ids" orchestrator_service/models.py → match en la clase Patient

### Task 1.3: Fix confirm_slot() con SET NX atómico
Archivo: orchestrator_service/main.py
Buscar: la función confirm_slot (alrededor de línea 5358-5380)

Reemplazar el patrón:
```python
existing_lock = await r.get(lock_key)
if existing_lock:
    ...
await r.setex(lock_key, 120, phone)
```

Por:
```python
result = await r.set(lock_key, phone, ex=120, nx=True)
if not result:
    existing = await r.get(lock_key)
    if existing:
        lock_holder = existing.decode() if isinstance(existing, bytes) else str(existing)
        if lock_holder != phone:
            return "⚠️ Ese horario acaba de ser reservado por otro paciente. ¿Querés que busque otro horario disponible?"
        else:
            return f"✅ Ya tenés reservado el turno para {date_str} a las {time_str}. Continuemos con tus datos."
```

Verificación: rg "r\.get\(lock_key\)" orchestrator_service/main.py → 1 resultado (el de después del SET NX), NO el pattern original GET-then-SET

### Task 1.4: Rate limiting en WhatsApp webhook
Archivo: whatsapp_service/main.py

Paso 1 — Agregar dependencia:
Verificar si slowapi está en whatsapp_service/requirements.txt. Si no, agregar: slowapi==0.1.9

Paso 2 — Implementar rate limiting:
Al inicio del archivo, después de los imports:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def ratelimit_handler(request, exc):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
```

Agregar decorador a los endpoints:
```python
@app.post("/webhook")
@limiter.limit("500/minute")
async def ycloud_webhook(request: Request):
    ...

@app.post("/send")
@limiter.limit("100/minute")
async def send_message(...):
    ...
```

Verificación: rg "limiter.limit" whatsapp_service/main.py → al menos 2 resultados

### Task 1.5: SSRF protection en media downloads
Archivo: whatsapp_service/main.py

Agregar función de validación de URLs ANTES de transcribe_audio y cualquier descarga de media:
```python
from urllib.parse import urlparse

ALLOWED_MEDIA_DOMAINS = frozenset({
    'media.ycloud.com', 'cdn.ycloud.com', 'ycloud.com',
    'mms.ycloud.com', 'storage.googleapis.com'
})

def is_safe_media_url(url: str) -> bool:
    """Validate media URL is from trusted CDN — SSRF prevention"""
    try:
        parsed = urlparse(url)
        if parsed.scheme != 'https':
            return False
        hostname = parsed.hostname or ''
        return any(hostname == d or hostname.endswith('.' + d) for d in ALLOWED_MEDIA_DOMAINS)
    except Exception:
        return False
```

Usar en transcribe_audio():
```python
async def transcribe_audio(audio_url: str, correlation_id: str) -> Optional[str]:
    if not is_safe_media_url(audio_url):
        logger.error("unsafe_media_url_blocked", url=audio_url[:80], correlation_id=correlation_id)
        return None
    # ... rest of existing code
```

Buscar TODAS las otras descargas de media en el archivo y agregar la misma validación.

Verificación: rg "is_safe_media_url" whatsapp_service/main.py → al menos 2 usos

### Task 1.6: Validación de teléfonos en WhatsApp
Archivo: whatsapp_service/main.py

Agregar función de validación:
```python
import re

PHONE_REGEX = re.compile(r'^[1-9]\d{6,14}$')

def validate_phone_number(phone: str) -> bool:
    """Validate WhatsApp phone number format (E.164 without +)"""
    if not phone or not isinstance(phone, str):
        return False
    return bool(PHONE_REGEX.match(phone.strip()))
```

Usar en el webhook handler, después de extraer from_n/to_n:
```python
from_n = msg.get("from")
to_n = msg.get("to")
if not validate_phone_number(from_n):
    logger.warning("invalid_phone_rejected", phone=from_n[:20] if from_n else "null", correlation_id=correlation_id)
    return {"status": "rejected", "reason": "invalid phone format"}
```

Verificación: rg "validate_phone_number" whatsapp_service/main.py → al menos 2 usos

### Task 1.7: Rate limiting en BFF
Archivo: bff_service/src/index.ts y bff_service/package.json

Paso 1 — Verificar si express-rate-limit está en package.json. Si no:
```json
"express-rate-limit": "^7.1.0"
```

Paso 2 — Agregar al inicio de index.ts:
```typescript
import rateLimit from 'express-rate-limit';

const globalLimiter = rateLimit({
    windowMs: 60 * 1000,
    max: 200,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: 'Too many requests' }
});

const authLimiter = rateLimit({
    windowMs: 60 * 1000,
    max: 10,
    message: { error: 'Too many auth requests' }
});

app.use(globalLimiter);
app.use('/auth', authLimiter);
```

Verificación: rg "rateLimit|rate-limit" bff_service/src/index.ts → al menos 2 resultados

---

### VERIFICACIÓN PACK 1 COMPLETA
Ejecutar estos comandos. TODOS deben pasar antes de continuar:
```bash
# 1. Sin credenciales hardcodeadas
rg "DEMO_PASSWORD|Wstg1793|gamarraadrian200" frontend_react/
# Esperado: 0 resultados

# 2. external_ids en modelo
rg "external_ids" orchestrator_service/models.py
# Esperado: al menos 1 match en clase Patient

# 3. SET NX atómico (no más GET+SETEX pattern)
rg "existing_lock = await r\.get" orchestrator_service/main.py
# Esperado: 0 resultados del pattern viejo

# 4. Rate limiting en WhatsApp
rg "limiter.limit" whatsapp_service/main.py
# Esperado: al menos 2

# 5. SSRF protection
rg "is_safe_media_url" whatsapp_service/main.py
# Esperado: al menos 2

# 6. Phone validation
rg "validate_phone_number" whatsapp_service/main.py
# Esperado: al menos 2

# 7. Rate limiting en BFF
rg "rateLimit" bff_service/src/index.ts
# Esperado: al menos 1
```

---

## PACK 2 — HIGH (ejecutar después de Pack 1)

### Task 2.1: Desactivar debug endpoints en producción
Archivo: orchestrator_service/admin_routes.py
Buscar: los endpoints /debug/auth-test, /debug/health, /debug/env-safe (alrededor de líneas 304-377)

Agregar guard al inicio de cada función:
```python
import os
ENABLE_DEBUG = os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() == "true"

# En cada endpoint /debug/*:
if not ENABLE_DEBUG:
    raise HTTPException(status_code=404, detail="Not found")
```

Además, en /debug/auth-test, ELIMINAR cualquier línea que retorne preview del token o comparación de tokens. Solo retornar:
```python
return {"status": "authenticated", "timestamp": datetime.utcnow().isoformat()}
```

### Task 2.2: Sanitizar errores del BFF
Archivo: bff_service/src/index.ts
Buscar: el bloque catch del proxy handler (alrededor de líneas 179-189)

Reemplazar:
```typescript
res.status(502).json({
    error: 'Orchestrator unavailable',
    details: error.message,
    target: url
});
```

Por:
```typescript
console.error(`[Proxy Error] ${req.method} ${req.path}: ${error.message}`);
res.status(502).json({ error: 'Service temporarily unavailable' });
```

### Task 2.3: Rate limiting en /login
Archivo: orchestrator_service/auth_routes.py
Buscar: el endpoint POST /login

Agregar decorador (verificar que limiter ya está importado — register lo usa):
```python
@router.post("/login")
@limiter.limit("5/minute")
async def login_user(request: Request, payload: UserLogin):
```

### Task 2.4: Mover INTERNAL_API_TOKEN de query param a header
Archivo: whatsapp_service/main.py
Buscar: líneas que construyen URL con access_token= como query param

Reemplazar:
```python
url = f"{ORCHESTRATOR_URL}/admin/ycloud/webhook?access_token={INTERNAL_API_TOKEN}"
```

Por:
```python
url = f"{ORCHESTRATOR_URL}/admin/ycloud/webhook"
# Y en la llamada httpx, agregar header:
headers = {**headers, "X-Internal-Token": INTERNAL_API_TOKEN}
```

Verificar en el orchestrator que el endpoint acepta X-Internal-Token header además de access_token query param.

### Task 2.5: Eliminar JWT dev-secret fallback
Archivo: orchestrator_service/my_routes.py (alrededor de líneas 57-58)

Reemplazar:
```python
secrets_to_try = [
    os.getenv("JWT_SECRET", "dev-secret"),
    os.getenv("SECRET_KEY", "dev-secret"),
]
```

Por:
```python
jwt_secret = os.getenv("JWT_SECRET_KEY") or os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY")
if not jwt_secret:
    logger.error("CRITICAL: No JWT secret configured. Set JWT_SECRET_KEY env var.")
    raise HTTPException(status_code=500, detail="Server configuration error")
secrets_to_try = [jwt_secret]
```

### Task 2.6: Reducir DOMPurify whitelist
Archivo: frontend_react/src/components/DigitalRecordsTab.tsx (líneas 329, 402)

En TODOS los lugares donde se usa DOMPurify.sanitize() con ADD_TAGS, ELIMINAR 'style' de la lista:
```typescript
// ANTES:
ADD_TAGS: ['style', 'table', 'thead', ...]
// DESPUÉS:
ADD_TAGS: ['table', 'thead', ...]
```

### Task 2.7: Agregar noopener,noreferrer a window.open()
Archivos: Buscar con rg "window\.open\(" frontend_react/src/
En CADA resultado, cambiar:
```typescript
// ANTES:
window.open(url, '_blank')
// DESPUÉS:
window.open(url, '_blank', 'noopener,noreferrer')
```

### Task 2.8: Sanitizar headers antes de loguear
Archivo: whatsapp_service/main.py (línea 267)

Reemplazar:
```python
logger.info("webhook_hit", headers=str(request.headers))
```

Por:
```python
def _sanitize_headers_for_log(headers) -> dict:
    sensitive = {'authorization', 'x-api-key', 'x-internal-token', 'ycloud-signature', 'x-admin-token'}
    return {k: ('***' if k.lower() in sensitive else v) for k, v in headers.items()}

logger.info("webhook_hit", headers=_sanitize_headers_for_log(request.headers))
```

### Task 2.9: Eliminar default de META_VERIFY_TOKEN
Archivo: docker-compose.yml (línea 114)

Reemplazar:
```yaml
- META_VERIFY_TOKEN=${META_VERIFY_TOKEN:-clinicforge_meta_verify}
```

Por:
```yaml
- META_VERIFY_TOKEN=${META_VERIFY_TOKEN}
```

### Task 2.10: Agregar logo_url al modelo Tenant
Archivo: orchestrator_service/models.py, clase Tenant

Buscar la clase Tenant y agregar (junto a los otros campos de config):
```python
logo_url = Column(Text, nullable=True)
```

### Task 2.11: Audit logging en /internal/credentials
Archivo: orchestrator_service/admin_routes.py (líneas 1769-1796)

Agregar logging ANTES de retornar:
```python
import hashlib

@router.get("/internal/credentials/{name}", tags=["Internal"])
async def get_internal_credential(name: str, x_internal_token: str = Header(None)):
    ALLOWED = {"YCLOUD_API_KEY", "YCLOUD_WEBHOOK_SECRET", "OPENAI_API_KEY"}

    if x_internal_token != INTERNAL_API_TOKEN:
        logger.warning(f"CREDENTIALS_ACCESS_DENIED: name={name}")
        raise HTTPException(status_code=401, detail="Unauthorized")

    if name not in ALLOWED:
        raise HTTPException(status_code=404, detail="Not found")

    val = os.getenv(name)
    val_hash = hashlib.sha256(val.encode()).hexdigest()[:8] if val else "null"
    logger.warning(f"CREDENTIALS_ACCESSED: name={name} hash={val_hash}")

    return {"name": name, "value": val}
```

### Task 2.12: Patrones básicos de prompt injection en español
Archivo: orchestrator_service/core/prompt_security.py

Agregar patrones en español al array existente de regex:
```python
INJECTION_PATTERNS_ES = [
    r"ignor[aá]\s+(las\s+)?instrucciones\s+(anteriores|previas)",
    r"olvi(d[aá]|date)\s+(de\s+)?(las\s+)?instrucciones",
    r"sos\s+un\s+asistente\s+(sin|que\s+no)",
    r"modo\s+(desarrollador|admin|debug)",
    r"prompt\s+(del\s+)?sistema",
    r"configur(aci[oó]n|ar)\s+(del\s+)?(sistema|bot|agente)",
    r"mostr[aá](me)?\s+(el|tu|la)\s+(prompt|configuraci[oó]n|instrucciones)",
    r"(act[uú]a|comport[aá]te)\s+como\s+(si\s+fueras|otro)",
    r"(jailbreak|bypass|escape)\s+(del\s+)?(sistema|filtro|restricci[oó]n)",
    r"no\s+ten[eé]s\s+(restricciones|l[ií]mites|reglas)",
]
```

Integrar con el detector existente — asegurarse de que se evalúan JUNTO con los patrones en inglés.

---

### VERIFICACIÓN PACK 2 COMPLETA
```bash
# 1. Debug endpoints gated
rg "ENABLE_DEBUG" orchestrator_service/admin_routes.py
# Esperado: al menos 1

# 2. BFF no expone URLs
rg "target.*url|details.*error" bff_service/src/index.ts
# Esperado: 0 en el bloque de error response

# 3. Login rate limited
rg "limiter.limit" orchestrator_service/auth_routes.py
# Esperado: al menos 2 (register + login)

# 4. No query param token
rg "access_token=.*INTERNAL" whatsapp_service/main.py
# Esperado: 0

# 5. No dev-secret
rg "dev-secret" orchestrator_service/
# Esperado: 0

# 6. No style en DOMPurify
rg "'style'" frontend_react/src/components/DigitalRecordsTab.tsx
# Esperado: 0 en ADD_TAGS

# 7. window.open seguro
rg "window\.open\(.*'_blank'\)" frontend_react/src/ --pcre2
# Verificar que TODOS incluyen noopener

# 8. Headers sanitizados
rg "sanitize_headers" whatsapp_service/main.py
# Esperado: al menos 1

# 9. No default META token
rg "clinicforge_meta_verify" docker-compose.yml
# Esperado: 0

# 10. logo_url en modelo
rg "logo_url" orchestrator_service/models.py
# Esperado: al menos 1

# 11. Credential audit log
rg "CREDENTIALS_ACCESSED" orchestrator_service/admin_routes.py
# Esperado: al menos 1

# 12. Injection patterns español
rg "INJECTION_PATTERNS_ES" orchestrator_service/core/prompt_security.py
# Esperado: al menos 1
```

---

## PACK 3 — MEDIUM (ejecutar después de Pack 2)

### Task 3.1: Transacción en creación de appointments
Archivo: orchestrator_service/admin_routes.py (alrededor de líneas 6446-6530)

Wrappear el collision check + INSERT en una transacción:
```python
async with db.pool.acquire() as conn:
    async with conn.transaction():
        # Collision check DENTRO de la transacción
        collision_response = await check_appointment_collision(conn, ...)
        if collision_response["has_collisions"]:
            raise HTTPException(status_code=409, detail="Conflicto de horario")
        # INSERT DENTRO de la misma transacción
        await conn.execute("INSERT INTO appointments ...", ...)
```

### Task 3.2: Validar CEO tenant access
Archivo: orchestrator_service/core/auth.py (líneas 126-146)

Después de la línea donde el CEO lee X-Tenant-ID del header, agregar validación:
```python
if user_data.role == 'ceo':
    if header_tid and header_tid.isdigit():
        requested_tid = int(header_tid)
        has_access = await db.pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM tenants WHERE id = $1)", requested_tid
        )
        if not has_access:
            logger.warning(f"CEO_TENANT_ACCESS_DENIED: user={user_data.email} tenant={requested_tid}")
            raise HTTPException(status_code=403, detail="Tenant access denied")
        return requested_tid
```

### Task 3.3: Security headers middleware
Archivo: orchestrator_service/main.py

Agregar middleware DESPUÉS de CORS:
```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
```

### Task 3.4: Validación de file uploads en frontend
Archivo: frontend_react/src/api/chats.ts (líneas 50-62)

Antes de `formData.append('file', file)`:
```typescript
const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25MB
const ALLOWED_TYPES = [
    'image/jpeg', 'image/png', 'image/webp', 'image/gif',
    'audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/webm',
    'video/mp4', 'video/webm',
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
];

if (file.size > MAX_FILE_SIZE) {
    throw new Error('El archivo excede el tamaño máximo de 25MB');
}
if (!ALLOWED_TYPES.includes(file.type)) {
    throw new Error(`Tipo de archivo no permitido: ${file.type}`);
}
```

### Task 3.5: Paginar backup queries
Archivo: orchestrator_service/services/backup_service.py (líneas 154-157)

Reemplazar el SELECT * sin LIMIT con query paginada:
```python
async def _query_table(pool, table_name: str, tenant_id: int, order: str = "") -> list:
    BATCH_SIZE = 5000
    offset = 0
    all_rows = []
    while True:
        rows = await pool.fetch(
            f"SELECT * FROM {table_name} WHERE tenant_id = $1{order} LIMIT $2 OFFSET $3",
            tenant_id, BATCH_SIZE, offset
        )
        if not rows:
            break
        all_rows.extend(rows)
        offset += BATCH_SIZE
        if len(rows) < BATCH_SIZE:
            break
    return all_rows
```

### Task 3.6: Fix JSONB server_defaults
Archivo: orchestrator_service/models.py

Buscar TODOS los Column(JSONB) que usan `default=list()` o `default=dict()` o `default=[]` o `default={}` y reemplazar con server_default:
```python
# ANTES:
pregnancy_restricted_treatments = Column(JSONB, default=list())
# DESPUÉS:
pregnancy_restricted_treatments = Column(JSONB, nullable=True, server_default=text("'[]'::jsonb"))

# ANTES:
high_risk_protocols = Column(JSONB, default=dict())
# DESPUÉS:
high_risk_protocols = Column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
```

IMPORTANTE: Importar text si no está importado:
```python
from sqlalchemy import text
```

### Task 3.7: Multipart size limit en BFF
Archivo: bff_service/src/index.ts (líneas 66-81)

En el middleware de multipart parsing, agregar size check:
```typescript
const MAX_MULTIPART_SIZE = 100 * 1024 * 1024; // 100MB
let totalSize = 0;

req.on('data', (chunk: Buffer) => {
    totalSize += chunk.length;
    if (totalSize > MAX_MULTIPART_SIZE) {
        res.status(413).json({ error: 'Payload too large' });
        req.destroy();
        return;
    }
    chunks.push(chunk);
});
```

### Task 3.8: Sanitizar error messages
Archivo: orchestrator_service/admin_routes.py

Buscar TODOS los patrones `raise HTTPException(status_code=500, detail=f"...{str(e)}...")` y reemplazar con:
```python
import uuid as uuid_mod
error_id = uuid_mod.uuid4().hex[:8]
logger.error(f"[{error_id}] Operation failed: {str(e)}", exc_info=True)
raise HTTPException(status_code=500, detail=f"Error interno (ref: {error_id})")
```

Hacer esto para TODOS los endpoints que exponen str(e) en el detail.

---

### VERIFICACIÓN PACK 3 COMPLETA
```bash
# 1. Transactions en appointments
rg "conn\.transaction" orchestrator_service/admin_routes.py
# Esperado: al menos 1

# 2. CEO tenant validation
rg "CEO_TENANT_ACCESS_DENIED|Tenant access denied" orchestrator_service/core/auth.py
# Esperado: al menos 1

# 3. Security headers
rg "X-Frame-Options|X-Content-Type-Options" orchestrator_service/main.py
# Esperado: al menos 2

# 4. File upload validation
rg "MAX_FILE_SIZE|ALLOWED_TYPES" frontend_react/src/api/chats.ts
# Esperado: al menos 1

# 5. Backup pagination
rg "BATCH_SIZE|OFFSET" orchestrator_service/services/backup_service.py
# Esperado: al menos 1

# 6. JSONB server_defaults
rg "default=list\(\)|default=dict\(\)|default=\[\]|default=\{\}" orchestrator_service/models.py
# Esperado: 0

# 7. Multipart limit
rg "MAX_MULTIPART_SIZE|413" bff_service/src/index.ts
# Esperado: al menos 1

# 8. No str(e) en HTTPException 500s
rg 'detail=f".*str\(e\)' orchestrator_service/admin_routes.py
# Esperado: 0 (o near-zero)
```

---

## RESUMEN DE ARCHIVOS TOCADOS

| Pack | Archivos Modificados |
|------|---------------------|
| Pack 1 | LoginView.tsx, models.py, main.py (confirm_slot), whatsapp_service/main.py, bff_service/index.ts, bff_service/package.json, whatsapp_service/requirements.txt, NEW: 033_add_external_ids_column.py |
| Pack 2 | admin_routes.py, bff_service/index.ts, auth_routes.py, whatsapp_service/main.py, my_routes.py, DigitalRecordsTab.tsx, docker-compose.yml, models.py, prompt_security.py, + todos los archivos con window.open() |
| Pack 3 | admin_routes.py, core/auth.py, main.py (middleware), chats.ts, backup_service.py, models.py, bff_service/index.ts |

## COMMITS SUGERIDOS (uno por pack)
```bash
# Pack 1
git add -A && git commit -m "fix(security): remediate 7 CRITICAL vulnerabilities — credentials, SSRF, rate limiting, schema"

# Pack 2
git add -A && git commit -m "fix(security): remediate 12 HIGH vulnerabilities — debug endpoints, error sanitization, XSS hardening"

# Pack 3
git add -A && git commit -m "fix(security): remediate 8 MEDIUM vulnerabilities — transactions, headers, validation, pagination"
```
```
