# Meta Native Connection — Canales Directos de Instagram, Facebook y WhatsApp

> Origen: Requerimiento del equipo — conectar canales de mensajeria de Meta (IG DM, Messenger, WA Cloud API) directamente sin depender de Chatwoot como intermediario. Implementacion validada en Platform AI Solutions.

## 1. Contexto y Objetivos

- **Problema:** Actualmente ClinicForge recibe mensajes de Instagram y Facebook solo a traves de Chatwoot (intermediario), y WhatsApp solo via YCloud. Esto implica dependencia de servicios terceros para cada canal. Se necesita una opcion nativa de Meta que conecte directamente via Graph API, coexistiendo con los providers actuales.

- **Solucion:** Agregar un tercer provider `meta_direct` al sistema de canales. El usuario conecta sus Pages, Instagram y WhatsApp Business directamente desde una nueva pestana "Meta" en la pagina de Settings (ConfigView). Se crea un microservicio `meta_service` que maneja OAuth, webhooks y envio de mensajes. El orchestrator recibe los mensajes via un nuevo adapter (`MetaDirectAdapter`) que se integra al pipeline existente de `ChannelService`.

- **KPIs:**
  - Conectar canales Meta en <2 minutos desde el popup
  - Mensajes recibidos en IG/FB/WA aparecen en Chats en <5 segundos
  - El agente de IA responde automaticamente en el canal de origen
  - Chatwoot y YCloud siguen funcionando sin interferencia
  - Credenciales almacenadas encriptadas con Fernet (existente)

---

## 2. Esquemas de Datos

### M01 — SimpleEvent (meta_service → orchestrator)

Payload normalizado que el meta_service envia al orchestrator por cada mensaje recibido:

```typescript
interface SimpleEvent {
    provider: "meta";
    platform: "instagram" | "facebook" | "whatsapp";
    tenant_identifier: string;  // Page ID, IG ID, o display_phone_number
    event_type: "message";
    timestamp: number;
    recipient_id: string;       // ID del asset que recibio el mensaje
    sender_id: string;          // PSID del usuario
    sender_name: string | null;
    payload: {
        id: string;             // mid del mensaje
        type: "text" | "image" | "audio" | "video" | "document";
        text: string | null;
        media_url: string | null;
    };
}
```

### M02 — Credential Sync (meta_service → orchestrator)

```typescript
interface CredentialSync {
    tenant_id: number;
    provider: "meta";
    credentials: {
        user_access_token: string;
        assets: {
            pages: Array<{ id: string; name: string; access_token: string }>;
            instagram: Array<{ id: string; username: string; linked_page_id: string; access_token: string }>;
            whatsapp: Array<{ id: string; name: string; phone_numbers: Array<{id: string; display_phone_number: string}>; access_token: string }>;
        };
    };
}
```

### M03 — Frontend Assets Response (sanitizado, sin tokens)

```typescript
interface MetaConnectResponse {
    status: "success";
    connected: { facebook: boolean; instagram: boolean; whatsapp: boolean };
    assets: {
        pages: Array<{ id: string; name: string }>;            // Sin access_token
        instagram: Array<{ id: string; username: string }>;
        whatsapp: Array<{ id: string; name: string; phone_numbers: Array<{display_phone_number: string}> }>;
    };
}
```

### Persistencia — Migracion Alembic REQUERIDA

```sql
-- 1. Tabla business_assets (assets descubiertos)
CREATE TABLE IF NOT EXISTS business_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    asset_type TEXT NOT NULL,        -- 'facebook_page', 'instagram_account', 'whatsapp_waba'
    content JSONB NOT NULL,          -- { id, name, username, phone_numbers, status }
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_business_assets_tenant ON business_assets(tenant_id);
CREATE INDEX IF NOT EXISTS idx_business_assets_content_id ON business_assets((content->>'id'));

-- 2. PSIDs para identidad en patients (Meta usa PSIDs, no telefonos)
ALTER TABLE patients ADD COLUMN IF NOT EXISTS instagram_psid TEXT;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS facebook_psid TEXT;
CREATE INDEX IF NOT EXISTS idx_patients_ig_psid ON patients(tenant_id, instagram_psid);
CREATE INDEX IF NOT EXISTS idx_patients_fb_psid ON patients(tenant_id, facebook_psid);

-- 3. Columnas opcionales en chat_conversations para enriquecimiento
ALTER TABLE chat_conversations ADD COLUMN IF NOT EXISTS source_entity_id TEXT;
ALTER TABLE chat_conversations ADD COLUMN IF NOT EXISTS platform_origin TEXT;
```

### Credentials que se crean automaticamente (en tabla `credentials` existente)

| name | category | Descripcion |
|------|----------|-------------|
| `META_USER_LONG_TOKEN` | meta | Token long-lived del usuario (~60 dias) |
| `META_PAGE_TOKEN_{page_id}` | meta | Token especifico por Facebook Page |
| `meta_page_token` | meta | Primer Page Token (fallback generico) |
| `META_IG_TOKEN_{ig_id}` | meta | Token para cuenta Instagram |
| `META_WA_TOKEN_{waba_id}` | meta | Token para WhatsApp Business Account |

---

## 3. Logica de Negocio (Invariantes)

### Coexistencia de Providers

- Un tenant puede tener Chatwoot, YCloud y Meta Direct activos simultaneamente.
- Cada `chat_conversations` tiene un campo `provider` que determina la ruta de delivery.
- Si el mismo canal (ej: Instagram) esta conectado via Chatwoot Y Meta Direct, se crean conversaciones separadas. **Recomendacion**: usar un solo provider por canal.

### Flujo de Conexion

```
Usuario (CEO) → Settings → Tab "Meta" → Click "Conectar con Meta"
    → FB.login() popup se abre
    → Usuario selecciona Pages, IG, WA en el popup de Meta
    → Meta retorna authorization code
    → Frontend envia code a POST /admin/meta/connect
    → Orchestrator proxy a meta_service POST /connect
    → meta_service: exchange code → long-lived token
    → meta_service: GET /me/accounts → descubre Pages + Instagram
    → meta_service: POST /{page_id}/subscribed_apps → suscribe webhooks
    → meta_service: GET /me/whatsapp_business_accounts → descubre WABAs
    → meta_service: POST orchestrator/admin/credentials/internal-sync
    → Credenciales encriptadas + business_assets guardados en DB
    → Frontend muestra assets conectados con iconos IG/FB/WA
```

### Flujo de Mensajes Entrantes

```
DM en Instagram/Facebook/WhatsApp
    → Meta Webhook → meta_service POST /webhook
    → Verificar firma X-Hub-Signature-256
    → Normalizar payload a SimpleEvent
    → FILTRAR is_echo (CRITICO: evita loops infinitos)
    → POST orchestrator/admin/meta-direct/webhook (background task)
    → Orchestrator: resolver tenant via business_assets
    → ChannelService.normalize_webhook("meta_direct", payload, tenant_id)
    → MetaDirectAdapter → CanonicalMessage
    → _process_canonical_messages() (misma pipeline que Chatwoot/YCloud)
    → Persistir en chat_messages + chat_conversations (provider='meta_direct')
    → Socket.IO emit NEW_MESSAGE
    → BufferManager.enqueue_message(provider="meta_direct", ...)
    → AI Agent procesa y genera respuesta
    → Delivery via Meta Graph API
```

### Flujo de Respuesta del Agente (Delivery)

```
AI Agent genera respuesta
    → Detectar provider de la conversacion
    → Si provider == "meta_direct":
        → Si channel == "instagram" o "facebook":
            → POST https://graph.facebook.com/v22.0/me/messages
              { recipient: {id: PSID}, message: {text: respuesta}, messaging_type: "RESPONSE" }
              access_token = meta_page_token del tenant
        → Si channel == "whatsapp":
            → POST https://graph.facebook.com/v22.0/{phone_number_id}/messages
              { messaging_product: "whatsapp", to: phone, type: "text", text: {body: respuesta} }
              Authorization: Bearer {WA_TOKEN}
    → Si provider == "chatwoot": flujo existente
    → Si provider == "ycloud": flujo existente
```

### Filtro de Echo (CRITICO)

Meta envia un webhook `is_echo: true` por cada mensaje que la pagina ENVIA. Sin filtrar esto, cada respuesta del agente generaria un nuevo webhook → nuevo mensaje → nuevo trigger del agente → loop infinito.

**Implementacion en meta_service/core/webhooks.py:**
```python
message = messaging.get("message", {})
if message.get("is_echo"):
    return None  # Ignorar mensajes enviados por nosotros
```

### Politica 24h de Meta

Meta solo permite responder dentro de las 24 horas desde el ultimo mensaje del usuario. La logica existente de `last_user_message_at` y `human_override_until` aplica identica para Meta Direct.

**ATENCION al bug de timezone:** Siempre usar `datetime.now(timezone.utc)` para comparaciones. Nunca `datetime.utcnow()` que retorna naive datetime y causa TypeError con columnas TIMESTAMPTZ.

### Soberania Multi-Tenant

- Resolucion de tenant por `business_assets WHERE content->>'id' = recipient_id`
- Credenciales aisladas por `tenant_id` (misma tabla `credentials` existente)
- Buffer keys incluyen tenant_id: `buffer:meta_direct:{tenant_id}:{sender_psid}`

---

## 4. Stack y Restricciones

### Backend — Nuevo microservicio `meta_service/`

| Archivo | Proposito |
|---------|-----------|
| `meta_service/main.py` | FastAPI: /connect, /webhook (GET+POST), /subscribe, /messages/send, /whatsapp/send, /privacy/data-deletion |
| `meta_service/core/auth.py` | OAuth exchange (code→token→long-lived), asset discovery, page webhook subscription |
| `meta_service/core/webhooks.py` | Normalizacion de payloads (Messenger, IG Direct, WA Cloud API) + filtro echo |
| `meta_service/core/client.py` | HTTP client para orchestrator (sync credentials, ingest webhook) |
| `meta_service/requirements.txt` | fastapi, uvicorn, httpx, structlog, pydantic, python-dotenv |
| `meta_service/Dockerfile` | python:3.11, pip install, uvicorn |

### Backend — Orchestrator (archivos nuevos)

| Archivo | Proposito |
|---------|-----------|
| `orchestrator_service/services/channels/meta_direct.py` | `MetaDirectAdapter(ChannelAdapter)` — normaliza SimpleEvent a CanonicalMessage |
| `orchestrator_service/routes/meta_direct_webhook.py` | `POST /admin/meta-direct/webhook` — recibe de meta_service, resuelve tenant, llama pipeline |
| `orchestrator_service/routes/meta_connect.py` | `POST /admin/meta/connect` — proxy al meta_service para conexion |
| `orchestrator_service/routes/meta_credentials_sync.py` | `POST /admin/credentials/internal-sync` — recibe y almacena credenciales de meta_service |
| `orchestrator_service/alembic/versions/005_add_meta_direct_support.py` | Migracion: business_assets, PSIDs en patients |

### Backend — Orchestrator (archivos a modificar)

| Archivo | Cambio |
|---------|--------|
| `services/channels/service.py` | Agregar `"meta_direct": MetaDirectAdapter()` a `_adapters` |
| `services/buffer_manager.py` | Agregar defaults para `meta_direct_*` en `GLOBAL_DEFAULTS` |
| `routes/chat_api.py` → `unified_send_message` | Agregar `elif provider == "meta_direct":` para delivery via Graph API |
| `main.py` | Registrar nuevos routers. Agregar delivery `meta_direct` en respuesta del agente |
| `main.py` | Incluir `from routes.meta_direct_webhook import router as meta_direct_router` |

### Frontend (archivos a modificar)

| Archivo | Cambio |
|---------|--------|
| `frontend_react/src/views/ConfigView.tsx` | Agregar tab "Meta" con `activeTab === 'meta'` |
| `frontend_react/src/hooks/useFacebookSdk.ts` | **NUEVO** — Hook para cargar SDK de Facebook |
| `frontend_react/.env` / `.env.example` | Agregar `VITE_FACEBOOK_APP_ID`, `VITE_META_CONFIG_ID` |

### Frontend (archivos nuevos opcionales)

| Archivo | Proposito |
|---------|-----------|
| `frontend_react/src/components/integrations/MetaConnectionTab.tsx` | Componente lazy-loaded para la tab Meta en ConfigView |

### Docker

| Archivo | Cambio |
|---------|--------|
| `docker-compose.yml` | Agregar servicio `meta_service` |

### Variables de Entorno Nuevas

| Variable | Donde | Obligatoria | Descripcion |
|----------|-------|:-----------:|-------------|
| `META_APP_ID` | meta_service | SI | App ID de Meta Developer |
| `META_APP_SECRET` | meta_service | SI | App Secret |
| `META_VERIFY_TOKEN` | meta_service | SI | Token de verificacion para webhooks |
| `META_SERVICE_URL` | orchestrator | SI | URL interna del meta_service (`http://meta_service:8000`) |
| `VITE_FACEBOOK_APP_ID` | frontend | SI | App ID para SDK de Facebook |
| `VITE_META_CONFIG_ID` | frontend | SI | Config ID de Facebook Login for Business |
| `VITE_META_EMBEDDED_SIGNUP` | frontend | NO | `true` solo si eres Tech Provider aprobado |

### Infraestructura EasyPanel

| Servicio | URL Publica | Puerto |
|----------|------------|--------|
| `dentalforge-metaservice` | `https://dentalforge-metaservice.gvdlcu.easypanel.host` | 8000 |

**Webhook URL para Meta Developer Portal:** `https://dentalforge-metaservice.gvdlcu.easypanel.host/webhook`
(Usar esta misma URL en Messenger Webhooks, Instagram Webhooks y WhatsApp Webhooks de la app de Meta Developer)

---

## 5. Criterios de Aceptacion (Gherkin)

### Escenario 1: Conexion via popup

```gherkin
Dado que el CEO esta en Settings → Tab "Meta"
Y tiene una Facebook Page con Instagram Business vinculado
Cuando hace click en "Conectar con Meta"
Y completa el popup de Facebook Login seleccionando su Page e Instagram
Entonces el sistema muestra los assets descubiertos (FB check, IG check, WA check o no detectado)
Y las credenciales se almacenan encriptadas en la tabla credentials
Y los assets se almacenan en la tabla business_assets
Y el boton cambia a estado "Conectado" con icono verde
```

### Escenario 2: Recepcion de DM de Instagram

```gherkin
Dado que un tenant tiene Instagram conectado via Meta Direct
Cuando un paciente envia un DM en Instagram
Entonces el mensaje aparece en la pagina de Chats en <5 segundos
Y se crea una conversacion con provider='meta_direct' y channel='instagram'
Y se emite evento Socket.IO NEW_MESSAGE
Y el agente de IA se activa via BufferManager
```

### Escenario 3: Respuesta del agente

```gherkin
Dado que un mensaje de Instagram llego via Meta Direct
Y el agente de IA genero una respuesta
Cuando el sistema envia la respuesta
Entonces usa POST /me/messages de Graph API con el page_token del tenant
Y el paciente recibe la respuesta en Instagram DM
Y la respuesta se persiste en chat_messages con role='assistant'
```

### Escenario 4: Coexistencia con Chatwoot

```gherkin
Dado que un tenant tiene Instagram conectado via Chatwoot
Y tambien tiene Facebook conectado via Meta Direct
Cuando llega un mensaje por Instagram via Chatwoot
Entonces se procesa por la pipeline de Chatwoot (sin cambios)
Y cuando llega un mensaje por Facebook via Meta Direct
Entonces se procesa por la pipeline de Meta Direct
Y ambas conversaciones coexisten en la pagina de Chats
```

### Escenario 5: Filtro de echo

```gherkin
Dado que el agente envio una respuesta por Graph API
Cuando Meta envia el webhook de echo (is_echo=true)
Entonces el meta_service lo descarta
Y NO se crea un nuevo mensaje en el sistema
Y NO se vuelve a activar el agente de IA
```

### Escenario 6: Envio manual por humano

```gherkin
Dado que un supervisor esta en la pagina de Chats
Y selecciona una conversacion con provider='meta_direct' y channel='facebook'
Cuando escribe un mensaje y hace click en Enviar
Entonces unified_send_message detecta provider='meta_direct'
Y envia el mensaje via Graph API POST /me/messages
Y el paciente lo recibe en Messenger
```

---

## 6. Archivos Afectados

### NUEVOS

| Archivo | Tipo | Descripcion |
|---------|------|-------------|
| `meta_service/main.py` | CREATE | Microservicio FastAPI completo |
| `meta_service/core/auth.py` | CREATE | OAuth, discovery, subscription |
| `meta_service/core/webhooks.py` | CREATE | Normalizacion + filtro echo |
| `meta_service/core/client.py` | CREATE | HTTP client al orchestrator |
| `meta_service/requirements.txt` | CREATE | Dependencias |
| `meta_service/Dockerfile` | CREATE | Container build |
| `orchestrator_service/services/channels/meta_direct.py` | CREATE | MetaDirectAdapter |
| `orchestrator_service/routes/meta_direct_webhook.py` | CREATE | Webhook endpoint |
| `orchestrator_service/routes/meta_connect.py` | CREATE | Proxy /admin/meta/connect + DELETE /admin/meta/disconnect |
| `orchestrator_service/routes/meta_credentials_sync.py` | CREATE | Sync de credenciales |
| `orchestrator_service/routes/meta_disconnect.py` | CREATE | Limpieza total al desconectar (credentials, assets, conversaciones, mensajes, PSIDs) |
| `orchestrator_service/alembic/versions/005_add_meta_direct_support.py` | CREATE | Migracion DB |
| `frontend_react/src/hooks/useFacebookSdk.ts` | CREATE | Hook SDK Facebook |
| `frontend_react/src/components/integrations/MetaConnectionTab.tsx` | CREATE | Tab Meta en Settings |

### MODIFICADOS

| Archivo | Tipo | Cambio |
|---------|------|--------|
| `orchestrator_service/services/channels/service.py` | MODIFY | Agregar MetaDirectAdapter a _adapters |
| `orchestrator_service/services/buffer_manager.py` | MODIFY | Agregar meta_direct defaults |
| `orchestrator_service/routes/chat_api.py` | MODIFY | Agregar meta_direct a unified_send_message |
| `orchestrator_service/main.py` | MODIFY | Registrar routers, agregar delivery meta_direct post-agente |
| `frontend_react/src/views/ConfigView.tsx` | MODIFY | Agregar tab "Meta" |
| `docker-compose.yml` | MODIFY | Agregar servicio meta_service |
| `frontend_react/.env.example` | MODIFY | Agregar VITE_FACEBOOK_APP_ID, VITE_META_CONFIG_ID |

---

## 7. Casos Borde y Riesgos

| Riesgo | Mitigacion |
|--------|------------|
| Loop infinito por falta de filtro echo | Implementar filtro `is_echo` en webhooks.py ANTES de cualquier procesamiento |
| TypeError por timezone naive vs aware en check 24h | Usar `datetime.now(timezone.utc)` siempre. Normalizar naive datetimes con `.replace(tzinfo=timezone.utc)` |
| Token expirado (long-lived dura ~60 dias) | Mostrar warning en UI cuando faltan <7 dias. Log de error si Graph API retorna 401 |
| Page Token de pagina equivocada | Almacenar token especifico `META_PAGE_TOKEN_{page_id}` ademas del generico. En delivery, buscar token por source_entity_id primero |
| DNS entre servicios en Docker (underscore vs dash) | Usar nombre del servicio tal cual esta en docker-compose.yml. Implementar fallback si falla |
| Paciente sin telefono (IG/FB usan PSIDs) | El agente PIDE el telefono obligatoriamente antes de agendar. PSID se usa como referencia secundaria para vincular (ver C1) |
| Doble conexion (mismo canal en Chatwoot Y Meta Direct) | Documentar en UI: "Si ya usas este canal via Chatwoot, desactivalo antes de conectar aqui". No bloquear tecnicamente |
| Webhook URL no publica / sin HTTPS | Servicio `dentalforge-metaservice` en EasyPanel con dominio publico HTTPS (ver C3) |
| WA YCloud vs WA Meta Direct | No hay conflicto: son numeros diferentes (WA Business App vs Cloud API). Ambos coexisten (ver C5) |
| Multi-sede: canales asignados al tenant equivocado | Selector de sede/tenant en la UI ANTES de conectar. CEO elige a que clinica van los canales (ver C5) |
| Desconexion parcial deja datos huerfanos | DELETE /admin/meta/disconnect ejecuta limpieza total: credentials + assets + conversaciones + mensajes + PSIDs (ver C4) |

---

## 8. Checkpoints de Soberania

- [x] Todas las queries incluyen `WHERE tenant_id = $X`
- [x] Credenciales encriptadas con Fernet (reutiliza vault existente)
- [x] business_assets aislados por tenant_id con FK CASCADE
- [x] Buffer keys incluyen tenant_id
- [x] No se exponen tokens al frontend (assets sanitizados)
- [x] Verificacion de secret inter-servicio (X-Internal-Secret header)
- [x] Migracion via Alembic (no SQL inline)

---

## 9. Diseno de UI — Tab "Meta" en Settings

### Ubicacion

`ConfigView.tsx` → Nueva tab despues de "Leads Forms":

```
[General] [YCloud (WhatsApp)] [Chatwoot (Meta)] [Otras] [Mantenimiento] [Leads Forms] [Meta]
```

Color del tab: `blue-600` (consistente con brand de Meta/Facebook).

### Estado: No Conectado

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│          [Icono Facebook azul grande, 48px]                 │
│                                                             │
│           Conectar canales de Meta                          │
│    Conecta tus paginas de Facebook, Instagram y             │
│    WhatsApp Business directamente para recibir              │
│    mensajes y que tu agente de IA responda.                 │
│                                                             │
│  Asignar canales a:                                         │
│  ┌─────────────────────────────────┐                        │
│  │ ▼  Clinica Dental Centro       │  ← Selector de sede    │
│  └─────────────────────────────────┘    (solo si multi-sede)│
│                                                             │
│         ┌─────────────────────────────┐                     │
│         │  f  Conectar con Meta       │  ← Boton azul      │
│         └─────────────────────────────┘    #1877F2          │
│                                                             │
│  ┌─────────────────────────────────────────┐                │
│  │ ℹ  Que sucede al conectar?              │                │
│  │                                         │                │
│  │ 1. Se abre un popup de Meta             │                │
│  │ 2. Seleccionas tus paginas y cuentas    │                │
│  │ 3. Se suscriben automaticamente a       │                │
│  │    webhooks para recibir mensajes       │                │
│  │ 4. Tu agente de IA responde en esos     │                │
│  │    canales (pedira telefono para agendar)│                │
│  └─────────────────────────────────────────┘                │
│                                                             │
│  ⚠ Requisitos: Facebook Page con rol de Admin,             │
│    Instagram Business Account vinculado a la Page.          │
└─────────────────────────────────────────────────────────────┘
```

### Estado: Conectado

```
┌─────────────────────────────────────────────────────────────┐
│  ✅ Meta conectado                                          │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │    f     │  │   📷    │  │   💬    │                  │
│  │ Facebook │  │Instagram │  │WhatsApp  │                  │
│  │    ✓     │  │    ✓     │  │  ⚠ N/D  │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
│                                                             │
│  Assets detectados:                                         │
│  • Mi Clinica Dental (Facebook Page)                        │
│  • @miclinica_dental (Instagram Business)                   │
│                                                             │
│  ┌────────────────────┐  ┌───────────────────┐              │
│  │  Reconectar        │  │  Desconectar      │              │
│  └────────────────────┘  └───────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### Nota sobre Marketing Hub

El boton de Meta en Marketing Hub (`MarketingHubView.tsx`) es para **Meta Ads** (scopes: `ads_management, ads_read`). La nueva tab en Settings es para **Meta Messaging** (scopes: `pages_messaging, instagram_manage_messages`). Son flujos OAuth diferentes con scopes diferentes y NO se interfieren.

---

## 10. Orden de Implementacion

### Fase 1: Infraestructura (no afecta produccion)
1. Crear `meta_service/` completo (copiar de Platform AI Solutions, adaptar URLs)
2. Migracion Alembic (business_assets, PSIDs)
3. Agregar meta_service a docker-compose.yml
4. Configurar variables de entorno
5. Configurar webhook URL en Meta Developer Portal

### Fase 2: Conexion (Frontend + Backend)
6. Crear `useFacebookSdk.ts`
7. Crear `MetaConnectionTab.tsx`
8. Agregar tab "Meta" a `ConfigView.tsx`
9. Crear `meta_connect.py` + `meta_credentials_sync.py` en orchestrator
10. Probar: popup → assets → credentials en DB

### Fase 3: Recepcion de Mensajes
11. Crear `MetaDirectAdapter`
12. Registrar en `ChannelService._adapters`
13. Crear `meta_direct_webhook.py`
14. Agregar meta_direct defaults en BufferManager
15. Probar: DM en IG → aparece en Chats

### Fase 4: Delivery (Respuesta del Agente)
16. Agregar `meta_direct` a `unified_send_message`
17. Agregar delivery `meta_direct` en post-agente (main.py)
18. Probar: DM → agente responde → respuesta en IG/FB

---

## 11. Clarificaciones (Ronda de Blindaje)

### C1. Pacientes de IG/FB sin telefono — El agente DEBE pedir telefono

**Resolucion:** Cuando un paciente escribe por Instagram o Facebook (donde solo tenemos PSID, no telefono), el agente de IA **obligatoriamente** le pide el numero de telefono antes de poder registrarlo como paciente y agendar un turno.

**Impacto en system prompt:**
Agregar regla al system prompt del agente:
```
REGLA CANAL: Si el paciente escribe por Instagram o Facebook (no WhatsApp),
ANTES de agendar un turno debes pedirle su numero de telefono.
Sin telefono no puedes registrarlo como paciente.
Ejemplo: "Para poder agendarte, necesito tu numero de telefono. Me lo compartes?"
```

**Impacto en tools:**
- `book_appointment` sigue usando `phone_number` como identificador primario. No se modifica.
- `list_my_appointments` sigue buscando por telefono. Si el paciente no dio su telefono, el agente le dice que lo necesita.
- Los campos `instagram_psid` y `facebook_psid` en la tabla `patients` se usan como referencia secundaria para vincular al paciente una vez que da su telefono, evitando duplicados futuros.

**Flujo:**
```
1. Paciente escribe por IG → se crea conversacion con PSID
2. Agente responde, en algun punto pide telefono
3. Paciente da telefono → agente puede agendar (book_appointment con phone)
4. Se actualiza patients: phone_number + instagram_psid (vinculacion)
5. Futuras conversaciones por IG se vinculan al paciente existente via PSID
```

### C2. Tools del agente — Pedir telefono antes de agendar

**Resolucion:** El agente debe pedir el telefono antes de poder agendar. Las tools NO se adaptan para buscar por PSID — el telefono sigue siendo el identificador primario para todas las operaciones de paciente.

**Impacto:** Solo cambio en system prompt (agregar regla de canal). Las tools permanecen iguales.

### C3. Infraestructura — Servicio meta_service separado en EasyPanel

**Resolucion:** Se crea un servicio nuevo en EasyPanel llamado `dentalforge-metaservice`, expuesto con URL publica HTTPS.

**Datos de infraestructura:**
- URL publica del webhook: `https://dentalforge-metaservice.gvdlcu.easypanel.host/webhook`
- Puerto interno: `8000` (igual que en Platform AI Solutions)
- Servicio independiente del orchestrator (mismo patron que Platform AI Solutions)
- En Meta Developer Portal (Webhooks config de Messenger, Instagram y WhatsApp), usar esta URL como Callback URL

**Docker Compose:**
```yaml
meta_service:
    build: ./meta_service
    ports:
      - "8004:8000"   # 8004 externo, 8000 interno
    environment:
      - PORT=8000
      - META_APP_ID=${META_APP_ID}
      - META_APP_SECRET=${META_APP_SECRET}
      - META_VERIFY_TOKEN=${META_VERIFY_TOKEN}
      - META_GRAPH_API_VERSION=v22.0
      - ORCHESTRATOR_URL=http://orchestrator_service:8000
      - INTERNAL_SECRET_KEY=${INTERNAL_API_TOKEN}
      - FRONTEND_URL=${FRONTEND_URL}
```

**EasyPanel:** Crear servicio `dentalforge-metaservice` apuntando al build de `./meta_service`, puerto 8000, con dominio publico habilitado.

### C4. Desconexion — Limpieza total

**Resolucion:** Al hacer click en "Desconectar", se ejecuta una limpieza completa:

1. **Eliminar credenciales** de la tabla `credentials` donde `category = 'meta'` y `tenant_id = X`
2. **Eliminar business_assets** donde `tenant_id = X`
3. **Eliminar conversaciones** de `chat_conversations` donde `provider = 'meta_direct'` y `tenant_id = X`
4. **Eliminar mensajes** de `chat_messages` vinculados a esas conversaciones
5. **Llamar a Meta API** para desuscribir webhooks: `DELETE /{page_id}/subscribed_apps`
6. **Limpiar PSIDs** en `patients`: setear `instagram_psid = NULL`, `facebook_psid = NULL` donde `tenant_id = X`

**Endpoint nuevo:** `DELETE /admin/meta/disconnect`

```python
@router.delete("/admin/meta/disconnect")
async def disconnect_meta(tenant_id: int = Depends(get_resolved_tenant_id)):
    pool = get_pool()

    # 1. Obtener page tokens antes de borrar (para desuscribir)
    pages = await pool.fetch(
        "SELECT content->>'id' as page_id FROM business_assets WHERE tenant_id = $1 AND asset_type = 'facebook_page'",
        tenant_id
    )

    # 2. Desuscribir webhooks en Meta
    for page in pages:
        page_token = await get_tenant_credential(tenant_id, f"META_PAGE_TOKEN_{page['page_id']}")
        if page_token:
            async with httpx.AsyncClient() as client:
                await client.delete(
                    f"https://graph.facebook.com/v22.0/{page['page_id']}/subscribed_apps",
                    params={"access_token": page_token}
                )

    # 3. Eliminar mensajes de conversaciones meta_direct
    await pool.execute("""
        DELETE FROM chat_messages WHERE conversation_id IN (
            SELECT id FROM chat_conversations WHERE tenant_id = $1 AND provider = 'meta_direct'
        )
    """, tenant_id)

    # 4. Eliminar conversaciones meta_direct
    await pool.execute(
        "DELETE FROM chat_conversations WHERE tenant_id = $1 AND provider = 'meta_direct'", tenant_id
    )

    # 5. Eliminar business_assets
    await pool.execute("DELETE FROM business_assets WHERE tenant_id = $1", tenant_id)

    # 6. Eliminar credenciales meta
    await pool.execute(
        "DELETE FROM credentials WHERE tenant_id = $1 AND category = 'meta'", tenant_id
    )

    # 7. Limpiar PSIDs en patients
    await pool.execute(
        "UPDATE patients SET instagram_psid = NULL, facebook_psid = NULL WHERE tenant_id = $1",
        tenant_id
    )

    return {"status": "disconnected"}
```

### C5. WhatsApp Meta Direct vs YCloud — No hay conflicto, selector de tenant

**Resolucion:** No hay conflicto posible entre WhatsApp YCloud y WhatsApp Meta Direct porque:
- YCloud usa numeros de WhatsApp Business App (no Cloud API)
- Meta Connect Native usa numeros de WhatsApp Cloud API
- Meta NO permite seleccionar numeros de WA Business App en el popup
- Son numeros completamente diferentes

**Comportamiento permitido:**
- Tenant puede tener 1 numero por YCloud + 1 numero diferente por Meta Direct
- Ambos coexisten sin interferencia (numeros distintos, providers distintos)

**Selector de tenant/sede en la UI:**
Al conectar via popup, la UI debe permitir al usuario CEO elegir **a que clinica/sede/tenant** asignar los canales conectados. Esto es especialmente importante en arquitectura multi-sede.

**Impacto en UI (MetaConnectionTab):**
Antes del boton "Conectar con Meta", mostrar un selector de sede:

```
┌─────────────────────────────────────────────────────────────┐
│  Asignar canales a:                                         │
│  ┌─────────────────────────────────┐                        │
│  │ ▼  Clinica Dental Centro       │  ← Select de tenants   │
│  │    Clinica Dental Norte         │                        │
│  │    Clinica Dental Sur           │                        │
│  └─────────────────────────────────┘                        │
│                                                             │
│         ┌─────────────────────────────┐                     │
│         │  f  Conectar con Meta       │                     │
│         └─────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

Si el usuario es CEO de una sola sede, el selector no aparece (se usa su tenant_id automaticamente).

**Impacto en backend:**
El `POST /admin/meta/connect` ya recibe `tenant_id`. El frontend debe enviar el tenant_id seleccionado en el selector (no siempre el del usuario logueado, sino el de la sede elegida).

```typescript
const connectWithBackend = async (credential: string, type: 'code' | 'token') => {
    await api.post('/admin/meta/connect', {
        ...(type === 'code' ? { code: credential } : { access_token: credential }),
        redirect_uri: window.location.href.split('?')[0],
        tenant_id: selectedTenantId  // Del selector de sede
    });
};
```
