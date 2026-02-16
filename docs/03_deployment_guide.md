# Despliegue en EasyPanel / Docker - Guía Completa

Este proyecto está optimizado para EasyPanel, un orquestador de contenedores basado en Docker.

## 1. Estructura del Proyecto en EasyPanel

### 1.1 Crear un Nuevo Proyecto

```
EasyPanel Dashboard
  → New Project
  → Select Source: GitHub (o Git Repo)
  → Seleccionar este repositorio
``` 

### 1.2 Agregar Infraestructura (Add-ons)

#### PostgreSQL
```
1. Click "Add Service" → Search "PostgreSQL"
2. Configurar:
   - Version: 13+ (recomendado 13 o 15)
   - Username: postgres
   - Password: (strong password)
   - Database: nexus_db
3. Copiar conexión string: postgres://user:pass@host:5432/nexus_db
4. Asignar a POSTGRES_DSN
```

#### Redis
```
1. Click "Add Service" → Search "Redis"
2. Configurar:
   - Version: Alpine (más liviano)
   - Password: (optional pero recomendado)
3. Copiar conexión string: redis://host:6379
4. Asignar a REDIS_URL
```

## 2. Despliegue de Microservicios

### 2.1 WhatsApp Service (Puerto 8002) - PÚBLICO

```
1. Add Service → Docker
2. Nombre: whatsapp-service
3. Dockerfile: whatsapp_service/Dockerfile
4. Puerto: 8002
5. Dominio: wa.tudominio.com (HTTPS automático con Let's Encrypt)
6. Healthcheck:
   - Path: /health
   - Port: 8002
   - Interval: 30s
   - Timeout: 10s
7. Variables de Entorno:
   - YCLOUD_API_KEY=...
   - YCLOUD_WEBHOOK_SECRET=...
   - INTERNAL_API_TOKEN=...
   - ORCHESTRATOR_SERVICE_URL=http://orchestrator_service:8000
   - REDIS_URL=...
8. Deploy
```

**Importante:** El servicio acepta webhooks en `/webhook` y `/webhook/ycloud` para máxima compatibilidad con el panel de YCloud.
```
https://wa.tudominio.com/webhook
```

### 2.2 Orchestrator Service (Puerto 8000) - INTERNO

```
1. Add Service → Docker
2. Nombre: orchestrator-service
3. Dockerfile: orchestrator_service/Dockerfile
4. Puerto: 8000
5. Dominio: (OPCIONAL - puedes usar nombre de servicio internamente)
6. Healthcheck:
   - Path: /health
   - Port: 8000
   - Interval: 30s
7. Variables de Entorno:
   - OPENAI_API_KEY=...
   - POSTGRES_DSN=... (copiada de PostgreSQL add-on)
   - REDIS_URL=... (copiada de Redis add-on)
   - INTERNAL_API_TOKEN=...
   - STORE_NAME=...
   - BOT_PHONE_NUMBER=...
   - TIENDANUBE_STORE_ID=...
   - TIENDANUBE_ACCESS_TOKEN=...
   - HANDOFF_EMAIL=...
   - SMTP_HOST=...
   - SMTP_PORT=...
   - SMTP_USER=...
   - SMTP_PASS=...
   - ADMIN_TOKEN=...
   - CORS_ALLOWED_ORIGINS=...
8. Deploy
```

**Nota:** El Orchestrator ejecuta migraciones de BD automáticamente en startup (via lifespan event).

### 2.3 Frontend React (Puerto 80) - PÚBLICO

```
1. Add Service → Docker
2. Nombre: frontend-react
3. Dockerfile: frontend_react/Dockerfile
4. Puerto: 80
5. Dominio: admin.tudominio.com (HTTPS)
6. Healthcheck: (la UI es React, puede no tener endpoint /health)
7. Variables de Entorno:
   - ADMIN_TOKEN=... (copia el mismo del Orchestrator)
   - ORCHESTRATOR_URL=http://orchestrator_service:8000 (o deja en blanco para auto-detectar)
8. Deploy
```

**Auto-detección de URL:**
Si no especificas `ORCHESTRATOR_URL`, el Frontend React lo detecta automáticamente:
- `localhost` → `http://localhost:8000`
- `frontend-react.domain.com` → `orchestrator-service.domain.com`

## 3. Mapeo de Puertos y Networking

| Servicio | Puerto Interno | Exposición Pública | URL |
| :--- | :--- | :--- | :--- |
| whatsapp_service | 8002 | ✅ SÍ | `https://wa.tudominio.com` |
| orchestrator_service | 8000 | ❌ NO (interno) | `http://orchestrator_service:8000` (red interna) |
| frontend_react | 80 | ✅ SÍ | `https://admin.tudominio.com` |
| postgres | 5432 | ❌ NO (solo desde servicios) | `postgres://...@postgres:5432` |
| redis | 6379 | ❌ NO (solo desde servicios) | `redis://redis:6379` |

## 4. Pasos Críticos Post-Deploy

### 4.1 Migraciones de Base de Datos

El `orchestrator_service` ejecuta migraciones automáticamente en startup:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Conecta a DB
    await db.connect()
    
    # Ejecuta schema (dentalogic_schema.sql)
    # El sistema usa un Smart Splitter para ejecutar cada sentencia individualmente
    # garantizando compatibilidad con funciones PL/pgSQL complejas.
    await sync_environment()
```

**Si la BD es nueva:**
- Se crean tablas desde `dentalogic_schema.sql` (ejecutar manualmente)
- Se crea un "default tenant" usando las variables de entorno

**Si ya existe:**
- Las migraciones son idempotentes (CREATE TABLE IF NOT EXISTS)
- No sobreescriben datos existentes (por defecto)

**Para resetear BD (en desarrollo):**
```bash
# Conectar a PostgreSQL (via EasyPanel console)
psql -U postgres -d nexus_db

# Dropear y recrear
DROP TABLE IF EXISTS chat_messages CASCADE;
DROP TABLE IF EXISTS chat_conversations CASCADE;
-- Luego reiniciar orchestrator_service
-- Las migraciones se ejecutan automáticamente
```

### 4.2 Configuración de Webhooks (YCloud)

1. Ve a panel de YCloud
2. Busca "Webhook Settings" o "API Configuration"
3. Configura:
   - **URL:** `https://wa.tudominio.com/webhook/ycloud`
   - **Secret:** El valor de `YCLOUD_WEBHOOK_SECRET` (debe coincidir)
   - **Events:** Message, MessageStatus, etc.
4. Prueba webhook (ping test desde panel de YCloud)

### 4.3 Verificar Conectividad

```bash
# Desde la consola de EasyPanel:

# ¿Orchestrator arrancó?
curl http://orchestrator_service:8000/health

# ¿WhatsApp Service arrancó?
curl http://whatsapp_service:8002/health

# ¿PostgreSQL accesible?
psql -U postgres -h postgres -d nexus_db -c "SELECT 1"

# ¿Redis accesible?
redis-cli -h redis ping
```

### 4.4 Validar Migraciones de BD

```bash
psql -U postgres -h postgres -d nexus_db

# Ver tablas creadas
\dt

# Ver tenants
SELECT * FROM tenants;

# Ver tabla de conversaciones (debe estar vacía inicialmente)
### 4.5 Configuración de Google Calendar (Service Account)

Para que el sistema sincronice eventos, es **CRÍTICO** compartir cada calendario con la Service Account:

1.  **Obtener Email de Service Account**:
    - Desde Google Cloud Console > IAM & Admin > Service Accounts.
    - Copiar el email (ej: `dental-bot@project-id.iam.gserviceaccount.com`).
2.  **Compartir Calendario**:
    - Ir a Google Calendar (dueño del calendario).
    - Configuración > "Integrar el calendario" o "Compartir con personas específicas".
    - Agregar el email de la Service Account.
    - Permisos: **"Hacer cambios en eventos"** (Make changes to events).
3.  **Obtener Calendar ID**:
    - Copiar el "ID de calendario" (normalmente el email del dueño o un string largo `...group.calendar.google.com`).
    - Asignar este ID al profesional correspondiente en el panel admin (`/admin/professionals`).

## 5. Variables de Entorno en EasyPanel

### Método 1: Panel UI
```
Service → Settings → Environment Variables
  → Add
  → Key: OPENAI_API_KEY
  → Value: sk-proj-xxxxx
  → Save
  → Deploy
```

### Método 2: Archivo .env
Si el servicio soporta, subir `.env` a la raíz del Dockerfile:
```dockerfile
FROM python:3.11
COPY .env /app/.env
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
```

### Método 3: Secrets (Recomendado para producción)
EasyPanel puede almacenar secretos encriptados:
```
Project → Secrets
  → Add Secret
  → SMTP_PASS=xxxxx (se almacena encriptado)
  → Los servicios acceden vía variable de entorno
```

## 6. Healthchecks y Readiness Probes

### Orchestrator
```
GET /health
Respuesta: 200 {"status": "ok"}

GET /ready
Respuesta: 200 {"status": "ok"} (si DB conectada)
```

### WhatsApp Service
```
GET /health
Respuesta: 200 {"status": "ok"}
```

### Platform UI
```
GET / (página HTML)
Respuesta: 200 (HTML del dashboard)
```

## 7. Logs y Debugging

### Ver logs en tiempo real (EasyPanel)
```
Service → Logs
  → Ver output del contenedor
```

### Buscar errores específicos
```
Logs → Search
  → "error"
  → "migration_failed"
  → "request_failed"
```

### Acceder al contenedor
```
Service → Console (SSH)
  → Ejecutar comandos
  → Ej: curl http://localhost:8000/health
```

## 8. Troubleshooting

### Error: 500 en /chat

**Causa:** Variable de entorno faltante o error de conexión

**Solución:**
```
1. Ver logs de orchestrator_service
2. Buscar "error" o "CRITICAL"
3. Comunes:
   - OPENAI_API_KEY no configurada
   - POSTGRES_DSN no válida
   - TIENDANUBE_ACCESS_TOKEN expirado
```

### Error: Bot no responde

**Causa:** ORCHESTRATOR_SERVICE_URL incorrecto

**Solución:**
```
1. Verificar en whatsapp_service que:
   ORCHESTRATOR_SERVICE_URL=http://orchestrator_service:8000
   (Si usas dominio, debe ser resuelto internamente)
2. Hacer curl desde WhatsApp Service:
   curl http://orchestrator_service:8000/health
3. Si falla:
   - Revisar nombre del servicio en EasyPanel
   - Revisar que servicios estén en la misma red Docker
```

### Error: Bot responde doble

**Causa:** Deduplicación en Redis no funciona

**Solución:**
```
1. Verificar REDIS_URL:
   redis://redis:6379 (debe ser resuelto internamente)
2. Validar que Redis esté corriendo:
   redis-cli -h redis ping
3. Si Redis está en otro host:
   REDIS_URL=redis://redis.host.com:6379
```

### Error: SMTP/Mail no se envía

**Causa:** Credenciales SMTP inválidas

**Solución:**
```
1. Verificar SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
2. Para Gmail:
   - SMTP_HOST=smtp.gmail.com
   - SMTP_PORT=465
   - SMTP_PASS=(contraseña de aplicación, no contraseña normal)
3. Revisar logs en system_events table:
   SELECT * FROM system_events WHERE event_type='smtp_failed';
```

## 9. Performance y Escalabilidad

### Recomendaciones de recursos (EasyPanel)

```
Orchestrator Service:
  - CPU: 2 vCPUs (mínimo 1)
  - RAM: 1GB (mínimo 512MB)
  - Restart policy: Always

WhatsApp Service:
  - CPU: 1 vCPU
  - RAM: 512MB

Platform UI:
  - CPU: 1 vCPU
  - RAM: 256MB

PostgreSQL:
  - CPU: 2 vCPUs
  - RAM: 2GB
  - Storage: 20GB (ajustar según uso)

Redis:
  - CPU: 1 vCPU
  - RAM: 512MB
```

### Auto-scaling (si EasyPanel lo soporta)

```
Orchestrator Service:
  - Min replicas: 1
  - Max replicas: 3
  - CPU trigger: 70%
  - RAM trigger: 80%
```

## 10. Despliegue Alternativo: Docker Compose (Desarrollo)

Para desarrollo local:

```bash
# Clonar repo
git clone https://github.com/tu-repo/nexus.git
cd nexus

# Configurar .env
cp .env.example .env
# Editar .env con valores locales

# Levantar servicios
docker-compose up --build

# Acceso:
# - Orchestrator: http://localhost:8000
# - WhatsApp Service: http://localhost:8002
# - Frontend React: http://localhost:5173
```

**docker-compose.yml incluye:**
- orchestrator_service
- whatsapp_service
- frontend_react
- postgres
- redis

---

*Guía de Despliegue Nexus v3 © 2025*
