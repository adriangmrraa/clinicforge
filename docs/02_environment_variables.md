# Variables de Entorno - Guía Completa

Este proyecto se configura completamente mediante variables de entorno. En despliegue de EasyPanel, carga estas variables para cada microservicio.

## 1. Variables Globales (Todos los Servicios)

| Variable | Descripción | Ejemplo | Requerida |
| :--- | :--- | :--- | :--- |
| `INTERNAL_API_TOKEN` | Token de seguridad entre microservicios | `compu-global-hyper-mega-net` | ✅ |
| `OPENAI_API_KEY` | Clave API de OpenAI (GPT-4o-mini + Whisper) | `sk-proj-xxxxx` | ✅ |
| `REDIS_URL` | URL de conexión a Redis | `redis://redis:6379` | ✅ |
| `POSTGRES_DSN` | URL de conexión a PostgreSQL | `postgres://user:pass@db:5432/database` | ✅  

## 2. Orchestrator Service (8000)

### 2.1 Identidad y Branding (Whitelabel — Fallback)

| Variable | Descripción | Ejemplo | Requerida |
| :--- | :--- | :--- | :--- |
| `BOT_PHONE_NUMBER` | Número de WhatsApp del bot (fallback si la petición no trae `to_number`) | `+5493756123456` | ❌ |
| `CLINIC_NAME` | Nombre de clínica (fallback si la sede no tiene `clinic_name` en BD) | `Clínica Dental` | ❌ |
| `CLINIC_LOCATION` | Ubicación de la clínica (usado en respuestas del agente) | `República de Francia 2899, Mercedes, BA` | ❌ |
| `STORE_WEBSITE` | URL de la clínica (usada en el prompt del agente) | `https://www.miclinica.com` | ❌ |
| `STORE_DESCRIPTION` | Especialidad clínica (usada en el prompt) | `Salud Bucal e Implantología` | ❌ |

> **Regla Multi-tenant:** La fuente de verdad son `tenants.bot_phone_number` y `tenants.clinic_name` en base de datos. Estas variables solo actúan como fallback en pruebas manuales. No es obligatorio definirlas si todas las sedes tienen sus datos en la plataforma.

### 2.2 Cifrado (Arquitectura)

El proyecto usa dos mecanismos de cifrado complementarios, ninguno requiere `ENCRYPTION_KEY`:

| Qué cifra | Algoritmo | Variable requerida | Dónde |
| :--- | :--- | :--- | :--- |
| Contraseñas de usuarios (`users.password_hash`) | **bcrypt** (passlib) | — (no requiere config) | `auth_service.py` |
| API keys y tokens (`credentials.value`) | **Fernet** (AES-128-CBC) | `CREDENTIALS_FERNET_KEY` ✅ | `core/credentials.py` |

> `ENCRYPTION_KEY` **no existe en este proyecto**. Las contraseñas se hashean con bcrypt (irreversible). Los tokens/API-keys se cifran con Fernet (reversible, para usarlos en runtime).

### 2.3 Handoff / Derivación a Humanos

| Variable | Descripción | Ejemplo | Requerida |
| :--- | :--- | :--- | :--- |
| `NOTIFICATIONS_EMAIL` | Email destino para alertas de derivación humana del agente. Si no se define, se usa un fallback de desarrollo. | `soporte@clinica.com` | ✅ (en producción) |
| `SMTP_HOST` | Host del servidor SMTP | `smtp.gmail.com` | ✅ (si handoff activo) |
| `SMTP_PORT` | Puerto del servidor SMTP | `465` | ✅ (si handoff activo) |
| `SMTP_USER` / `SMTP_USERNAME` | Usuario SMTP | `noreply@clinica.com` | ✅ (si handoff activo) |
| `SMTP_PASS` / `SMTP_PASSWORD` | Contraseña SMTP | (password de app) | ✅ (si handoff activo) |
| `SMTP_SENDER` | Dirección "From" del email enviado (puede ser distinta del usuario SMTP) | `no-reply@clinica.com` | ✅ (si handoff activo) |
| `SMTP_SECURITY` | Tipo de seguridad SMTP | `SSL` o `STARTTLS` | ✅ (si handoff activo) |

### 2.4 Seguridad y RBAC (Nexus v7.6 — Hardened)

| Variable | Descripción | Ejemplo | Requerida |
| :--- | :--- | :--- | :--- |
| `ADMIN_TOKEN` | Token maestro de protección | `admin-secret-token` | ✅ |
| `JWT_SECRET_KEY` | Clave secreta para firmar tokens JWT | `mue-la-se-cre-t-a` | ✅ |
| `JWT_ALGORITHM` | Algoritmo de firma para JWT | `HS256` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración del token de sesión | `43200` (30 días) | `30` |
| `PLATFORM_URL` | URL del frontend (para links de activación) | `https://ui.clinic.com` | `http://localhost:3000` |
| `CORS_ALLOWED_ORIGINS` | Origins CORS permitidos (comma-separated) | `http://localhost:3000,https://domain.com` | `*` |
| `CREDENTIALS_FERNET_KEY` | Clave Fernet (base64) para cifrar API-keys y tokens en la tabla `credentials`. Diferente de `ENCRYPTION_KEY`. | Salida de `Fernet.generate_key().decode()` | ✅ (si se usa connect-sovereign o gestión de credenciales) |
| `CSP_EXTRA_DOMAINS` | Dominios adicionales para Content-Security-Policy connect-src (comma-separated) | `*.trusted.com,api.other.net` | ❌ |
| `LOG_LEVEL` | Nivel de logging (activa sanitización de PII en INFO/DEBUG) | `INFO` | `INFO` |
| `MEDIA_PROXY_SECRET` | Secreto HMAC para firmar URLs de medios (`/admin/chat/media/proxy`). Si no se define, se genera un valor aleatorio por sesión (las URLs firmadas se invalidan al reiniciar). | `$(openssl rand -hex 32)` | ✅ (en producción) |
| `API_VERSION` | Versión visible en el Swagger UI y en `/openapi.json` | `1.0.0` | ❌ (default `1.0.0`) |
| `ENVIRONMENT` | Entorno de ejecución (`development`, `staging`, `production`). Visible en `/admin/config/deployment`. | `production` | ❌ |
| `CLINIC_HOURS_START` | Hora de apertura de la clínica (fallback global). Usado en el prompt del agente y en cálculo de slots. | `08:00` | ❌ |
| `CLINIC_HOURS_END` | Hora de cierre de la clínica (fallback global). | `19:00` | ❌ |
| `WHATSAPP_SERVICE_PORT` | Puerto interno del WhatsApp Service (para mostrar en `/admin/config/deployment`). | `8002` | ❌ (default `8002`) |

### 2.5 Meta Ads (Integración Facebook / Instagram)

Requeridas solo si se activa la integración con Meta Ads desde el módulo de Marketing.

| Variable | Descripción | Ejemplo | Requerida |
| :--- | :--- | :--- | :--- |
| `META_APP_ID` | App ID de la aplicación Facebook (OAuth flow para conectar cuentas de anuncios) | `123456789012345` | ✅ (si Meta Ads activo) |
| `META_APP_SECRET` | App Secret de la aplicación Facebook | `abcdef1234567890abcdef1234567890` | ✅ (si Meta Ads activo) |
| `META_REDIRECT_URI` | URI de redirección OAuth autorizada en el panel de Meta Developers | `https://api.clinica.com/auth/meta/callback` | ✅ (si Meta Ads activo) |
| `META_ADS_TOKEN` | Token de acceso de larga duración a la API de Meta Ads (fallback global; los tokens por tenant se guardan en `credentials`) | `EAABwzLixnjYBAO...` | ❌ (preferir vault de credentials) |
| `META_AD_ACCOUNT_ID` | ID de la cuenta publicitaria de Meta (fallback global; preferir vault de credentials) | `act_123456789` | ❌ (preferir vault de credentials) |
| `META_GRAPH_API_VERSION` | Versión de la API de Meta Graph a utilizar | `v21.0` | ❌ (default `v21.0`) |
| `META_API_TIMEOUT` | Timeout en segundos para llamadas a la API de Meta | `5.0` | ❌ (default `5.0`) |

> **Nota:** Los tokens de Meta Ads por tenant (cuando cada clínica tiene su propia cuenta publicitaria) se almacenan cifrados en la tabla `credentials` con `category = 'meta_ads'`. Las variables `META_ADS_TOKEN` y `META_AD_ACCOUNT_ID` solo actúan como fallback global para instalaciones de un solo tenant.

### 2.6 Google Calendar

| Variable | Descripción | Ejemplo | Requerida |
| :--- | :--- | :--- | :--- |
| `GOOGLE_CREDENTIALS` | JSON completo de credenciales OAuth de Google (Service Account o OAuth 2.0) para integración con Google Calendar | Contenido del JSON descargado de Google Cloud Console | ❌ (solo si `calendar_provider: google`) |
| `GOOGLE_CALENDAR_CREDENTIALS_JSON` | Alternativa a `GOOGLE_CREDENTIALS` — ruta o contenido JSON del archivo de credenciales OAuth. Usado por `google_calendar_service.py`. | `/app/google-credentials.json` o JSON inline | ❌ (solo si `calendar_provider: google`) |
| `GOOGLE_CALENDAR_TOKEN_JSON` | Token de acceso OAuth persistido tras el primer flujo de autorización. Contiene `access_token` y `refresh_token`. | JSON inline (generado automáticamente en primer login) | ❌ (auto-generado en primer uso) |

> **Nota Google Calendar:** Si la clínica usa `calendar_provider: local` (por defecto), estas variables no son necesarias. Solo se requieren al activar `calendar_provider: google` para una sede desde el panel de Sedes.

**Generar clave Fernet:** Con Python en el PATH:
- Windows: `py -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Linux/macOS: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

Guardar la salida en `CREDENTIALS_FERNET_KEY`.

### 2.7 Chatwoot (omnicanal, opcional)

| Variable | Descripción | Ejemplo | Requerida |
| :--- | :--- | :--- | :--- |
| `BASE_URL` | URL pública del Orchestrator (para devolver `api_base` en GET /admin/integrations/chatwoot/config; el frontend construye la URL del webhook para copiar en Chatwoot) | `https://api.clinica.com` | ❌ (si no se usa Chatwoot) |
| `REDIS_URL` | Usado por el buffer dinámico (10s/20s) de Chatwoot; si no hay Redis, el webhook no encola y el agente no se dispara para mensajes entrantes Chatwoot | `redis://redis:6379/0` | ❌ (opcional para Chatwoot) |

Las credenciales por tenant (WEBHOOK_ACCESS_TOKEN, CHATWOOT_API_TOKEN, CHATWOOT_BASE_URL, OPENAI_API_KEY, etc.) se guardan en la tabla `credentials`; no son variables de entorno globales. Ver `API_REFERENCE.md` (sección Chat omnicanal) y Configuración en el panel (sección Chatwoot).

## 3. WhatsApp Service (8002)

| Variable | Descripción | Ejemplo | Requerida |
| :--- | :--- | :--- | :--- |
| `YCLOUD_API_KEY` | API Key de YCloud | `api_key_xxxxx` | ✅ |
| `YCLOUD_WEBHOOK_SECRET` | Secreto para validar webhooks de YCloud | `webhook_secret_xxxxx` | ✅ |
| `ORCHESTRATOR_SERVICE_URL` | URL del Orchestrator (interna) | `http://orchestrator_service:8000` | ✅ |
| `INTERNAL_API_TOKEN` | Token para comunicarse con Orchestrator | (mismo que global) | ✅ |

## 4. Platform UI (80)

| Variable | Descripción | Ejemplo | Requerida |
| :--- | :--- | :--- | :--- |
| `VITE_ADMIN_TOKEN` | Token de administrador (inyectado en build) | `admin-secret-token` | ✅ |
| `VITE_API_BASE_URL` | URL base para la API del orquestador | `https://api.clinica.com` | ❌ (auto-detecta en prod) |
| `VITE_DEMO_WHATSAPP` | Número de WhatsApp para el botón de demo en `/demo` (sin `+`, sin espacios) | `5493756123456` | ❌ (tiene fallback) |

## 5. Ejemplo de .env (Desarrollo Local)

```bash
# --- Globales ---
INTERNAL_API_TOKEN=super-secret-dev-token
OPENAI_API_KEY=sk-proj-xxxxx
REDIS_URL=redis://redis:6379
POSTGRES_DSN=postgres://postgres:password@localhost:5432/nexus_db

# --- Auth & Platform ---
JWT_SECRET_KEY=mi-llave-maestra-dental
PLATFORM_URL=http://localhost:3000
ACCESS_TOKEN_EXPIRE_MINUTES=43200
ADMIN_TOKEN=admin-dev-token-CAMBIAR-EN-PRODUCCION

# --- Cifrado Fernet (para tabla credentials — API keys y tokens) ---
# Generar con: py -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
CREDENTIALS_FERNET_KEY=<fernet-key-generada>

# --- Seguridad de Medios ---
# Generar con: python -c "import secrets; print(secrets.token_hex(32))"
MEDIA_PROXY_SECRET=<hex-aleatorio-32-bytes>

# --- Orchestrator (Identidad / Whitelabel) ---
CLINIC_NAME=Clínica Demo
BOT_PHONE_NUMBER=+5493756123456
CLINIC_LOCATION=Buenos Aires, Argentina
CLINIC_HOURS_START=08:00
CLINIC_HOURS_END=19:00
CORS_ALLOWED_ORIGINS=http://localhost:3000
ENVIRONMENT=development
API_VERSION=1.0.0

# --- Handoff / Notificaciones Email ---
NOTIFICATIONS_EMAIL=admin@miclinica.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@miclinica.com
SMTP_PASS=password-de-app
SMTP_SENDER=no-reply@miclinica.com

# --- Meta Ads (solo si se usa integración) ---
META_APP_ID=<facebook-app-id>
META_APP_SECRET=<facebook-app-secret>
META_REDIRECT_URI=http://localhost:8000/auth/meta/callback
META_GRAPH_API_VERSION=v21.0
META_API_TIMEOUT=5.0

# --- WhatsApp (YCloud) ---
YCLOUD_API_KEY=yc_api_xxxxx
YCLOUD_WEBHOOK_SECRET=yc_webhook_xxxxx
ORCHESTRATOR_SERVICE_URL=http://orchestrator_service:8000

# --- Frontend (Build Time) ---
VITE_ADMIN_TOKEN=admin-dev-token
VITE_API_BASE_URL=http://localhost:8000
VITE_DEMO_WHATSAPP=5493435256815
```

---

*Guía de Variables © 2026*
泛
