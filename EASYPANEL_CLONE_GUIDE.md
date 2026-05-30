# Guia de Clonacion — ClinicForge en EasyPanel (Entorno Staging/Test)

Esta guia explica como crear un proyecto NUEVO en EasyPanel (dentro del mismo servidor donde corre produccion) para tener un entorno de staging/testing aislado.

---

## Arquitectura de Servicios

```
Frontend (React)  -->  BFF (Express :3000)  -->  Orchestrator (FastAPI :8000)
                                                       |
                                 +---------------------+---------------------+
                                 |                     |                     |
                           WhatsApp Service      Meta Service        Telegram Service
                              (:8002)              (:8000)              (:8003)
                                 |                     |
                                 +----------+----------+
                                            |
                                    PostgreSQL + Redis
```

---

## Paso 1 — Crear Proyecto en EasyPanel

1. En el dashboard de EasyPanel, click **"New Project"**
2. Nombre sugerido: `clinicforge-staging` o `clinicforge-test`
3. Este proyecto es 100% independiente del de produccion — tiene sus propias bases de datos, servicios y variables

---

## Paso 2 — Crear Servicios

Crear los siguientes servicios en este orden (respetar dependencias):

### 2.1 Infraestructura (crear primero)

#### `postgres`
- **Tipo**: Database → PostgreSQL 13
- **Volumes**: Habilitar persistencia (EasyPanel lo hace automatico)
- **Variables de entorno**:

| Variable | Valor | Notas |
|----------|-------|-------|
| `POSTGRES_USER` | `clinicforge_staging` | Diferente al de prod |
| `POSTGRES_PASSWORD` | `<generar-password-seguro>` | Min 32 chars |
| `POSTGRES_DB` | `clinicforge_staging` | Diferente al de prod |

- **Recursos**: 512MB RAM min, 1GB max
- **Nota**: Despues de crear, habilitar pgvector:
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  ```

#### `redis`
- **Tipo**: Database → Redis (Alpine)
- **Command override**: `redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru`
- **Recursos**: 128MB RAM min, 256MB max

---

### 2.2 Backend Principal

#### `orchestrator_service`
- **Tipo**: App → GitHub / Docker
- **Source**: Repo `adriangmrraa/clinicforge`, branch `main` (o `staging`)
- **Dockerfile path**: `orchestrator_service/Dockerfile`
- **Port**: 8000 (interno, NO exponer publicamente)
- **Health check**: `http://localhost:8000/health/ready`
- **Volumes**:
  - `/app/uploads` → persistente (logos, archivos de tenants)
  - `/app/media` → persistente (imagenes de WhatsApp)
- **Recursos**: 1GB RAM min, 3GB max, 2 CPUs
- **Variables de entorno**:

| Variable | Valor | Requerida | Notas |
|----------|-------|-----------|-------|
| `POSTGRES_DSN` | `postgresql://clinicforge_staging:<password>@postgres:5432/clinicforge_staging` | Si | Apuntar al postgres del proyecto staging |
| `REDIS_URL` | `redis://redis:6379` | Si | Redis interno del proyecto |
| `OPENAI_API_KEY` | `sk-...` | Si | Puede ser la misma key que prod o una diferente |
| `ADMIN_TOKEN` | `<generar-token-32-chars>` | Si | DIFERENTE al de prod |
| `JWT_SECRET_KEY` | `<generar-secret-32-chars>` | Si | DIFERENTE al de prod |
| `INTERNAL_API_TOKEN` | `<generar-token-32-chars>` | Si | Para comunicacion entre servicios |
| `CREDENTIALS_FERNET_KEY` | `<generar-fernet-key>` | Si | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `MEDIA_PROXY_SECRET` | `<generar-secret-32-chars>` | Si | Para URLs firmadas de media |
| `CORS_ALLOWED_ORIGINS` | `https://clinicforge-staging-frontend.<host>.easypanel.host` | Si | URL del frontend staging |
| `FRONTEND_URL` | `https://clinicforge-staging-frontend.<host>.easypanel.host` | Si | Para links de anamnesis, emails, etc. |
| `WHATSAPP_SERVICE_URL` | `http://whatsapp_service:8002` | Si | Servicio interno |
| `META_SERVICE_URL` | `http://meta_service:8000` | No | Solo si se configura Meta |
| `CLINIC_NAME` | `ClinicForge Staging` | No | Default: "Consultorio Dental" |
| `SENTRY_DSN` | `<dsn-staging>` | No | Opcional, para monitoreo |
| `SENTRY_ENVIRONMENT` | `staging` | No | Diferenciarlo de prod |
| `DEEPSEEK_API_KEY` | `<key>` | No | Solo si se usa DeepSeek como modelo alternativo |
| `LOG_LEVEL` | `DEBUG` | No | Recomendado para staging |
| `SMTP_HOST` | `smtp.gmail.com` | No | Para envio de emails |
| `SMTP_PORT` | `587` | No | TLS |
| `SMTP_USER` | `<email>` | No | Cuenta de envio |
| `SMTP_PASS` | `<app-password>` | No | App password de Gmail |
| `SMTP_SENDER` | `<email>` | No | Remitente visible |
| `NOTIFICATIONS_EMAIL` | `<email>` | No | Email para notificaciones internas |
| `DB_POOL_MIN` | `5` | No | Default: 10 (staging necesita menos) |
| `DB_POOL_MAX` | `20` | No | Default: 40 |

---

### 2.3 BFF (API Proxy)

#### `bff_service`
- **Tipo**: App → GitHub / Docker
- **Dockerfile path**: `bff_service/Dockerfile`
- **Port**: 3000 (exponer publicamente con HTTPS)
- **Health check**: `http://localhost:3000/health`
- **Dominio**: Asignar subdominio (ej: `clinicforge-staging-bff.<host>.easypanel.host`)
- **Recursos**: 64MB RAM min, 256MB max
- **Variables de entorno**:

| Variable | Valor | Requerida | Notas |
|----------|-------|-----------|-------|
| `PORT` | `3000` | Si | |
| `ORCHESTRATOR_URL` | `http://orchestrator_service:8000` | Si | Nombre del servicio interno |
| `ADMIN_TOKEN` | `<mismo-token-que-orchestrator>` | Si | DEBE coincidir |
| `ALLOWED_ORIGINS` | `https://clinicforge-staging-frontend.<host>.easypanel.host` | Si | URL del frontend |

---

### 2.4 Frontend

#### `frontend_react`
- **Tipo**: App → GitHub / Docker
- **Dockerfile path**: `frontend_react/Dockerfile`
- **Port**: 80 (exponer publicamente con HTTPS)
- **Dominio**: Asignar subdominio (ej: `clinicforge-staging-frontend.<host>.easypanel.host`)
- **Recursos**: 32MB RAM min, 128MB max
- **Variables de entorno (build-time)**:

| Variable | Valor | Requerida | Notas |
|----------|-------|-----------|-------|
| `VITE_API_URL` | `https://clinicforge-staging-bff.<host>.easypanel.host` | Si | URL PUBLICA del BFF (con HTTPS) |

> **IMPORTANTE**: `VITE_API_URL` es una variable de BUILD, no de runtime. Cada vez que cambies esta URL necesitas rebuild del frontend.

---

### 2.5 Servicios de Mensajeria (Opcionales para staging)

#### `whatsapp_service`
- **Tipo**: App → GitHub / Docker
- **Dockerfile path**: `whatsapp_service/Dockerfile`
- **Port**: 8002 (interno)
- **Health check**: `http://localhost:8002/health`
- **Recursos**: 128MB RAM min, 512MB max
- **Variables de entorno**:

| Variable | Valor | Requerida | Notas |
|----------|-------|-----------|-------|
| `YCLOUD_API_KEY` | `<key>` | Si | USAR KEY DE TEST de YCloud, NO produccion |
| `YCLOUD_WEBHOOK_SECRET` | `<secret>` | Si | Webhook de YCloud |
| `OPENAI_API_KEY` | `sk-...` | Si | Para transcripcion de audio (Whisper) |
| `INTERNAL_API_TOKEN` | `<mismo-que-orchestrator>` | Si | DEBE coincidir |
| `ORCHESTRATOR_SERVICE_URL` | `http://orchestrator_service:8000` | Si | |
| `REDIS_URL` | `redis://redis:6379` | Si | |

#### `meta_service`
- **Tipo**: App → GitHub / Docker
- **Dockerfile path**: `meta_service/Dockerfile`
- **Port**: 8000 (interno)
- **Health check**: `http://localhost:8000/health`
- **Recursos**: 128MB RAM min, 512MB max
- **Variables de entorno**:

| Variable | Valor | Requerida | Notas |
|----------|-------|-----------|-------|
| `PORT` | `8000` | Si | |
| `META_APP_ID` | `<app-id>` | Si | ID de la app de Meta |
| `META_APP_SECRET` | `<secret>` | Si | Secret de la app de Meta |
| `META_VERIFY_TOKEN` | `<verify-token>` | Si | Token de verificacion de webhook |
| `META_GRAPH_API_VERSION` | `v22.0` | No | Default: v22.0 |
| `ORCHESTRATOR_URL` | `http://orchestrator_service:8000` | Si | |
| `INTERNAL_SECRET_KEY` | `<mismo-INTERNAL_API_TOKEN>` | Si | DEBE coincidir con INTERNAL_API_TOKEN del orchestrator |
| `FRONTEND_URL` | `https://clinicforge-staging-frontend.<host>.easypanel.host` | Si | Para redirects OAuth |

#### `telegram_service`
- **Tipo**: App → GitHub / Docker
- **Dockerfile path**: `telegram_service/Dockerfile`
- **Port**: 8003 (interno)
- **Health check**: `http://localhost:8003/health`
- **Recursos**: 64MB RAM min, 256MB max
- **Variables de entorno**:

| Variable | Valor | Requerida | Notas |
|----------|-------|-----------|-------|
| `ORCHESTRATOR_URL` | `http://orchestrator_service:8000` | Si | |
| `ADMIN_TOKEN` | `<mismo-que-orchestrator>` | Si | DEBE coincidir |
| `TELEGRAM_SERVICE_PORT` | `8003` | Si | |
| `FRONTEND_URL` | `https://clinicforge-staging-frontend.<host>.easypanel.host` | No | |
| `TELEGRAM_WEBHOOK_BASE_URL` | `https://<url-publica-telegram-service>` | No | Solo si se expone para webhooks |

---

## Paso 3 — Orden de Deploy

```
1. postgres          (esperar healthy)
2. redis             (esperar healthy)
3. orchestrator      (esperar healthy — corre migraciones automaticamente via start.sh)
4. bff_service       (esperar healthy)
5. frontend_react    (build + deploy)
6. whatsapp_service  (opcional)
7. meta_service      (opcional)
8. telegram_service  (opcional)
```

---

## Paso 4 — Post-Deploy

### 4.1 Verificar migraciones
El orchestrator corre `alembic upgrade head` automaticamente al iniciar (`start.sh`). Verificar en los logs que no hubo errores.

### 4.2 Crear usuario CEO inicial
Desde el frontend, registrar el primer usuario. Luego en la DB promoverlo a CEO:

```sql
UPDATE users SET role = 'ceo', status = 'active' WHERE email = '<tu-email>';
```

### 4.3 Crear tenant
Desde la UI como CEO, crear la clinica (tenant). Esto configura el `tenant_id` para todo el sistema.

### 4.4 Verificar pgvector
```sql
SELECT extname FROM pg_extension WHERE extname = 'vector';
```
Si no existe, crearlo:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 4.5 Health checks
Verificar que todos los servicios responden:
- Orchestrator: `GET /health/ready`
- BFF: `GET /health`
- WhatsApp: `GET /health`
- Meta: `GET /health`
- Telegram: `GET /health`

---

## Reglas de Seguridad para Staging

| Regla | Detalle |
|-------|---------|
| Tokens DIFERENTES | `ADMIN_TOKEN`, `JWT_SECRET_KEY`, `CREDENTIALS_FERNET_KEY` deben ser DIFERENTES a produccion |
| DB aislada | PostgreSQL propio, nunca compartir con prod |
| Redis aislado | Redis propio dentro del proyecto staging |
| YCloud test key | NUNCA usar la API key de produccion de YCloud en staging |
| Datos de prueba | No copiar datos de pacientes reales de produccion |
| CORS estricto | `ALLOWED_ORIGINS` y `CORS_ALLOWED_ORIGINS` solo deben apuntar al frontend de staging |

---

## Generacion de Secrets

```bash
# ADMIN_TOKEN / JWT_SECRET_KEY / INTERNAL_API_TOKEN / MEDIA_PROXY_SECRET
openssl rand -hex 32

# CREDENTIALS_FERNET_KEY (formato especifico de Fernet)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Tokens que DEBEN coincidir entre servicios

| Token | Servicios que lo comparten |
|-------|---------------------------|
| `ADMIN_TOKEN` | orchestrator = bff = telegram |
| `INTERNAL_API_TOKEN` | orchestrator = whatsapp = meta (`INTERNAL_SECRET_KEY`) |
| `REDIS_URL` | orchestrator = whatsapp (mismo Redis) |
| `POSTGRES_DSN` | Solo orchestrator (unico servicio que accede a la DB) |

---

## Diferencias Staging vs Produccion

| Aspecto | Produccion | Staging |
|---------|-----------|---------|
| Proyecto EasyPanel | `clinicforge` (o nombre actual) | `clinicforge-staging` |
| Base de datos | `clinicforge_prod` | `clinicforge_staging` |
| Todos los secrets | Valores de produccion | Valores NUEVOS generados |
| `SENTRY_ENVIRONMENT` | `production` | `staging` |
| `LOG_LEVEL` | `INFO` | `DEBUG` |
| `DB_POOL_MIN/MAX` | `10/40` | `5/20` |
| YCloud API Key | Key de produccion | Key de TEST |
| Dominio | `app.clinicforge.com` | `clinicforge-staging-*.<host>.easypanel.host` |
| Recursos RAM | 3GB orchestrator | 1GB orchestrator (suficiente para test) |
