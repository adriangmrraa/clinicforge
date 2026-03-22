# Plan Tecnico — Meta Native Connection

> Spec: `specs/2026-03-22_meta-native-connection.spec.md`
> Fases: 4 | Tareas: 24 | Archivos nuevos: 14 | Archivos modificados: 7

---

## Fase 1: Microservicio meta_service (Backend independiente)

Objetivo: Tener el meta_service funcionando con health check y webhook challenge, listo para recibir webhooks de Meta.

### T01 — Crear estructura base de meta_service
**Archivos:** `meta_service/requirements.txt`, `meta_service/Dockerfile`
**Accion:**
- Crear directorio `meta_service/` y `meta_service/core/`
- `requirements.txt`: fastapi==0.109.2, uvicorn[standard]==0.27.1, httpx==0.27.0, python-multipart==0.0.9, pydantic==2.6.1, structlog==24.1.0, python-dotenv==1.0.1
- `Dockerfile`: python:3.11-slim, pip install, CMD uvicorn main:app --host 0.0.0.0 --port 8000
**Verificacion:** `docker build -t meta_service ./meta_service`

### T02 — Crear core/auth.py (OAuth + Discovery)
**Archivo:** `meta_service/core/auth.py`
**Accion:** Copiar de Platform AI Solutions (`meta_service/core/auth.py`) y adaptar:
- Clase `MetaAuthService` con:
  - `exchange_code(code, redirect_uri)` — Exchange sin redirect_uri primero, fallback con redirect_uri
  - `get_accounts(access_token)` — Descubre Pages + IG + WABAs
  - `subscribe_page(client, page_id, page_token)` — POST /{page_id}/subscribed_apps
- Env vars: `META_APP_ID`, `META_APP_SECRET`, `META_GRAPH_API_VERSION=v22.0`
**Verificacion:** Unit test: instanciar MetaAuthService, verificar que base_url se construye correctamente

### T03 — Crear core/webhooks.py (Normalizacion + Echo Filter)
**Archivo:** `meta_service/core/webhooks.py`
**Accion:** Copiar de Platform AI Solutions. Clase `MetaWebhookService` con:
- `verify_challenge(mode, token, challenge)` — Retorna int(challenge)
- `verify_signature(request)` — HMAC-SHA256 con META_APP_SECRET
- `normalize_payload(body)` — Detecta platform (page/instagram/whatsapp_business_account)
- `_normalize_messenger(messaging, platform)` — FB/IG con **filtro is_echo**
- `_normalize_whatsapp(change)` — WA Cloud API
**CRITICO:** Incluir `if message.get("is_echo"): return None` en `_normalize_messenger`
**Verificacion:** Test manual con payload de ejemplo de cada plataforma

### T04 — Crear core/client.py (HTTP Client al Orchestrator)
**Archivo:** `meta_service/core/client.py`
**Accion:** Copiar de Platform AI Solutions. Clase `OrchestratorClient` con:
- `ingest_webhook_event(event_data)` — POST {ORCHESTRATOR_URL}/admin/meta-direct/webhook
- `sync_credentials(payload)` — POST {ORCHESTRATOR_URL}/admin/credentials/internal-sync
- Headers: `X-Internal-Secret: {INTERNAL_SECRET_KEY}`
**Verificacion:** Verificar que base_url lee de `ORCHESTRATOR_URL` env var

### T05 — Crear main.py (FastAPI completo)
**Archivo:** `meta_service/main.py`
**Accion:** Copiar de Platform AI Solutions y adaptar. Endpoints:
- `GET /health` → `{"status": "ok", "service": "meta_service"}`
- `POST /connect` → Recibe code/access_token + tenant_id, ejecuta flujo completo
- `GET /webhook` → Verificacion challenge
- `POST /webhook` → Recibe webhooks, normaliza, reenvia al orchestrator
- `POST /subscribe` → Suscribe assets a webhooks
- `POST /messages/send` → Proxy Graph API para FB/IG
- `POST /whatsapp/send` → Proxy WhatsApp Cloud API
- `POST /privacy/data-deletion` → Callback GDPR obligatorio
- `GET /privacy/deletion-status/{code}` → Status check
**Verificacion:** `curl http://localhost:8004/health` → `{"status": "ok"}`

### T06 — Agregar meta_service a docker-compose.yml
**Archivo:** `docker-compose.yml`
**Accion:** Agregar servicio:
```yaml
meta_service:
    build: ./meta_service
    ports:
      - "8004:8000"
    environment:
      - PORT=8000
      - META_APP_ID=${META_APP_ID}
      - META_APP_SECRET=${META_APP_SECRET}
      - META_VERIFY_TOKEN=${META_VERIFY_TOKEN}
      - META_GRAPH_API_VERSION=v22.0
      - ORCHESTRATOR_URL=http://orchestrator_service:8000
      - INTERNAL_SECRET_KEY=${INTERNAL_API_TOKEN}
      - FRONTEND_URL=${FRONTEND_URL}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      - orchestrator_service
```
Agregar a orchestrator_service environment: `META_SERVICE_URL=http://meta_service:8000`
**Verificacion:** `docker compose up meta_service` → health check pasa

---

## Fase 2: Orchestrator — Ingestion Pipeline

Objetivo: El orchestrator puede recibir SimpleEvents del meta_service, resolver tenant, normalizar a CanonicalMessage y persistir en DB.

### T07 — Migracion Alembic (business_assets + PSIDs)
**Archivo:** `orchestrator_service/alembic/versions/005_add_meta_direct_support.py`
**Accion:** Crear migracion con:
- CREATE TABLE `business_assets` (id UUID, tenant_id FK, asset_type, content JSONB, is_active, timestamps)
- Indices: tenant_id, content->>'id'
- ALTER TABLE patients: ADD instagram_psid TEXT, facebook_psid TEXT + indices
- ALTER TABLE chat_conversations: ADD source_entity_id TEXT, platform_origin TEXT
**Verificacion:** `alembic upgrade head` sin errores. `\dt business_assets` en psql.

### T08 — Crear MetaDirectAdapter
**Archivo:** `orchestrator_service/services/channels/meta_direct.py`
**Accion:** Clase `MetaDirectAdapter(ChannelAdapter)`:
- `normalize_payload(payload, tenant_id)` → Convierte SimpleEvent a CanonicalMessage
- Mapea: provider="meta_direct", original_channel=payload.platform
- Extrae text, media_url, sender info
- Retorna `List[CanonicalMessage]`
**Verificacion:** Test unitario con payload mock de Instagram/Facebook/WhatsApp

### T09 — Registrar adapter en ChannelService
**Archivo:** `orchestrator_service/services/channels/service.py`
**Accion:** Agregar import y registro:
```python
from .meta_direct import MetaDirectAdapter

class ChannelService:
    _adapters = {
        "chatwoot": ChatwootAdapter(),
        "ycloud": YCloudAdapter(),
        "meta_direct": MetaDirectAdapter(),
    }
```
**Verificacion:** `ChannelService._adapters.get("meta_direct")` no es None

### T10 — Crear endpoint POST /admin/credentials/internal-sync
**Archivo:** `orchestrator_service/routes/meta_credentials_sync.py`
**Accion:** Endpoint que recibe CredentialSync del meta_service:
- Verificar X-Internal-Secret header
- Si provider=="meta": guardar tokens encriptados (META_USER_LONG_TOKEN, META_PAGE_TOKEN_{id}, meta_page_token, META_IG_TOKEN_{id}, META_WA_TOKEN_{id})
- Guardar business_assets (upsert por tenant_id + asset_type + content->>'id')
- Usar `save_tenant_credential()` del vault existente
**Verificacion:** POST con payload mock → verificar rows en credentials y business_assets

### T11 — Crear endpoint POST /admin/meta-direct/webhook
**Archivo:** `orchestrator_service/routes/meta_direct_webhook.py`
**Accion:**
- Verificar X-Internal-Secret header
- Resolver tenant via `business_assets WHERE content->>'id' = recipient_id`
- Fallback WhatsApp: buscar por bot_phone_number en tenants
- Llamar `ChannelService.normalize_webhook("meta_direct", payload, tenant_id)`
- Llamar `_process_canonical_messages()` (importar de chat_webhooks.py)
**Verificacion:** POST con SimpleEvent mock → mensaje aparece en chat_messages

### T12 — Registrar nuevos routers en main.py
**Archivo:** `orchestrator_service/main.py`
**Accion:** Agregar imports y registros:
```python
from routes.meta_direct_webhook import router as meta_direct_router
from routes.meta_credentials_sync import router as meta_cred_sync_router
app.include_router(meta_direct_router)
app.include_router(meta_cred_sync_router)
```
**Verificacion:** `GET /docs` muestra los nuevos endpoints

### T13 — Agregar meta_direct defaults en BufferManager
**Archivo:** `orchestrator_service/services/buffer_manager.py`
**Accion:** Agregar a `GLOBAL_DEFAULTS`:
```python
"meta_direct": {
    "debounce_seconds": 8,
    "bubble_delay": 3,
    "max_message_length": 300,
    "typing_indicator": True
}
```
**Verificacion:** `BufferManager.GLOBAL_DEFAULTS.get("meta_direct")` retorna dict

---

## Fase 3: Conexion Frontend + Delivery

Objetivo: El CEO puede conectar canales desde Settings, y el agente puede enviar respuestas por Meta Direct.

### T14 — Crear endpoint POST /admin/meta/connect (proxy)
**Archivo:** `orchestrator_service/routes/meta_connect.py`
**Accion:**
- Endpoint `POST /admin/meta/connect` con Depends(verify_staff_token)
- Recibe { code, access_token, redirect_uri, tenant_id }
- Resolucion de tenant: usar tenant_id del body (si CEO multi-sede) o del token del usuario
- Proxy a `META_SERVICE_URL/connect` con httpx
- Retornar response sanitizada (assets sin tokens)
**Verificacion:** POST con code mock → retorna assets structure

### T15 — Crear endpoint DELETE /admin/meta/disconnect
**Archivo:** `orchestrator_service/routes/meta_connect.py` (mismo archivo)
**Accion:**
- Endpoint `DELETE /admin/meta/disconnect` con Depends(verify_staff_token)
- Obtener page tokens de business_assets antes de borrar
- Desuscribir webhooks en Meta: DELETE /{page_id}/subscribed_apps
- Eliminar en orden: chat_messages → chat_conversations → business_assets → credentials (category='meta')
- Limpiar PSIDs en patients
**Verificacion:** DELETE → verificar que todas las tablas quedaron limpias para ese tenant

### T16 — Agregar meta_direct a unified_send_message
**Archivo:** `orchestrator_service/routes/chat_api.py`
**Accion:** En funcion `unified_send_message`, agregar `elif provider == "meta_direct":`:
- Obtener `meta_page_token` via `get_tenant_credential(tenant_id, "meta_page_token")`
- Si channel es instagram/facebook: POST `https://graph.facebook.com/v22.0/me/messages`
- Si channel es whatsapp: POST `https://graph.facebook.com/v22.0/{phone_number_id}/messages`
**Verificacion:** Test manual: enviar mensaje desde UI a conversacion meta_direct

### T17 — Agregar delivery meta_direct en respuesta del agente
**Archivo:** `orchestrator_service/main.py`
**Accion:** En la seccion donde el agente envia su respuesta (post agent_executor), agregar logica para provider `meta_direct`:
- Buscar provider de la conversacion
- Si `meta_direct`: enviar via Graph API (misma logica que T16)
- Si `chatwoot` o `ycloud`: flujo existente sin cambios
**Verificacion:** DM en IG → agente responde → respuesta llega al usuario en IG

### T18 — Crear hook useFacebookSdk.ts
**Archivo:** `frontend_react/src/hooks/useFacebookSdk.ts`
**Accion:** Copiar de Platform AI Solutions y adaptar:
- Lee `VITE_FACEBOOK_APP_ID` y `VITE_FACEBOOK_API_VERSION`
- Carga script de `connect.facebook.net/es_LA/sdk.js`
- Llama `FB.init()` con appId
- Retorna `isReady: boolean`
- Timeout fallback de 3s
**Verificacion:** Importar en componente de test, verificar que `isReady` pasa a true

### T19 — Crear MetaConnectionTab.tsx
**Archivo:** `frontend_react/src/components/integrations/MetaConnectionTab.tsx`
**Accion:** Componente con:
- Estado: idle / loading / connected / error
- Si multi-sede (>1 tenant): selector de sede/tenant
- Boton "Conectar con Meta" (bg-[#1877F2]) que llama `FB.login()` con config_id
- Callback: envia code/token a `POST /admin/meta/connect` con tenant_id seleccionado
- Estado conectado: grid de 3 cards (FB/IG/WA) con check/warning
- Lista de assets detectados
- Botones "Reconectar" y "Desconectar" (llama DELETE /admin/meta/disconnect)
- Estado desconectado: confirmacion antes de borrar todo
- Info box: "Que sucede al conectar?"
- Warning: "Requisitos: Facebook Page con rol de Admin..."
**Verificacion:** Renderiza sin errores, boton visible, popup se abre

### T20 — Agregar tab "Meta" a ConfigView.tsx
**Archivo:** `frontend_react/src/views/ConfigView.tsx`
**Accion:**
- Agregar `'meta'` al tipo de activeTab
- Agregar boton tab con icono Facebook, color blue-600, texto "Meta"
- Import lazy: `const MetaConnectionTab = lazy(() => import('../components/integrations/MetaConnectionTab'))`
- Renderizar: `{activeTab === 'meta' && user?.role === 'ceo' && <Suspense><MetaConnectionTab /></Suspense>}`
**Verificacion:** Navegar a Settings → tab "Meta" visible → click muestra el componente

### T21 — Agregar variables de entorno al frontend
**Archivo:** `frontend_react/.env.example`
**Accion:** Agregar:
```env
VITE_FACEBOOK_APP_ID=
VITE_META_CONFIG_ID=
VITE_META_EMBEDDED_SIGNUP=false
VITE_FACEBOOK_API_VERSION=v22.0
```
**Verificacion:** Build del frontend sin errores con variables seteadas

---

## Fase 4: System Prompt + Testing E2E

Objetivo: El agente pide telefono en IG/FB, y todo el flujo funciona end-to-end.

### T22 — Agregar regla de canal al system prompt
**Archivo:** `orchestrator_service/main.py` (seccion de system prompt builder) o `agent/prompt_builder.py`
**Accion:** Inyectar regla condicional cuando `channel` es `instagram` o `facebook`:
```
REGLA CANAL: El paciente escribe por {channel}. En este canal NO tenemos su numero de telefono.
ANTES de poder agendar un turno, registrar datos o buscar turnos, DEBES pedirle su numero de telefono.
Sin telefono no puedes usar ninguna herramienta de gestion de pacientes.
Ejemplo: "Para poder ayudarte con turnos, necesito tu numero de telefono con codigo de area. Me lo compartes?"
```
**Verificacion:** Probar via wizard/test: simular mensaje de IG → agente pide telefono

### T23 — Registrar router meta_connect en main.py
**Archivo:** `orchestrator_service/main.py`
**Accion:** Agregar:
```python
from routes.meta_connect import router as meta_connect_router
app.include_router(meta_connect_router)
```
**Verificacion:** GET /docs muestra /admin/meta/connect y /admin/meta/disconnect

### T24 — Testing E2E completo
**Accion:** Flujo completo en staging:
1. Settings → Tab Meta → Seleccionar sede → Click "Conectar con Meta"
2. Popup Meta → Seleccionar Page + Instagram → Cerrar popup
3. Verificar: estado "Conectado" con assets
4. Verificar DB: credentials (META_PAGE_TOKEN_*, meta_page_token), business_assets
5. Enviar DM en Instagram → Verificar en pagina de Chats (<5s)
6. Verificar que agente responde y pide telefono
7. Dar telefono → agente puede agendar turno
8. Verificar respuesta llega en Instagram DM
9. Enviar mensaje manual desde UI → llega al usuario
10. Click "Desconectar" → confirmar → verificar limpieza total
11. Verificar que Chatwoot y YCloud siguen funcionando sin cambios
**Verificacion:** Los 11 pasos pasan sin errores

---

## Plan de Base de Datos

### Migracion 005: Meta Direct Support

| Operacion | Tabla | Detalle |
|-----------|-------|---------|
| CREATE TABLE | `business_assets` | id UUID PK, tenant_id FK CASCADE, asset_type TEXT, content JSONB, is_active BOOL, timestamps |
| CREATE INDEX | `business_assets` | (tenant_id), (content->>'id') |
| ADD COLUMN | `patients` | instagram_psid TEXT, facebook_psid TEXT |
| CREATE INDEX | `patients` | (tenant_id, instagram_psid), (tenant_id, facebook_psid) |
| ADD COLUMN | `chat_conversations` | source_entity_id TEXT, platform_origin TEXT |

### Tablas existentes reutilizadas (sin cambios de schema)

| Tabla | Uso con Meta Direct |
|-------|---------------------|
| `credentials` | Nuevos rows con category='meta' (tokens encriptados) |
| `chat_conversations` | Nuevos rows con provider='meta_direct' |
| `chat_messages` | Mensajes entrantes/salientes identico al flujo actual |
| `tenants` | Resolucion por bot_phone_number (WA) o via business_assets (IG/FB) |

---

## Dependencias entre Tareas

```
T01 → T02,T03,T04 → T05 → T06    (Fase 1: meta_service standalone)
                              ↓
T07 → T08 → T09               (Fase 2: DB + Adapter)
       ↓
T10,T11 → T12 → T13           (Fase 2: Orchestrator endpoints)
                    ↓
T14,T15 → T16,T17             (Fase 3: Connect/Disconnect + Delivery)
T18 → T19 → T20 → T21         (Fase 3: Frontend)
                         ↓
T22 → T23 → T24               (Fase 4: Prompt + E2E)
```

Tareas paralelizables:
- T02, T03, T04 (los 3 core modules son independientes)
- T10, T11 (endpoints independientes)
- T14/T15 y T18 (backend y frontend en paralelo)
- T16 y T17 (delivery manual y delivery agente)
