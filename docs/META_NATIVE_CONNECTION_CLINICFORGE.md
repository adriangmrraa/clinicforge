# Meta Native Connection para ClinicForge — Guia de Implementacion

Documento tecnico para agregar soporte de **Meta Direct** (Facebook Messenger, Instagram DM, WhatsApp Cloud API) como un nuevo provider nativo en ClinicForge, **sin reemplazar** los providers existentes (Chatwoot y YCloud).

---

## Indice

1. [Arquitectura Actual vs Propuesta](#1-arquitectura-actual-vs-propuesta)
2. [Prerequisitos en Meta Developer Portal](#2-prerequisitos-en-meta-developer-portal)
3. [Variables de Entorno Nuevas](#3-variables-de-entorno-nuevas)
4. [Frontend: Popup de Conexion](#4-frontend-popup-de-conexion)
5. [Nuevo Microservicio: meta_service](#5-nuevo-microservicio-meta_service)
6. [Orchestrator: Nuevo Adapter + Webhook](#6-orchestrator-nuevo-adapter--webhook)
7. [Delivery: Envio de Respuestas Meta Direct](#7-delivery-envio-de-respuestas-meta-direct)
8. [Migraciones de Base de Datos](#8-migraciones-de-base-de-datos)
9. [Buffer Manager: Soporte meta_direct](#9-buffer-manager-soporte-meta_direct)
10. [Docker Compose: Nuevo Servicio](#10-docker-compose-nuevo-servicio)
11. [Checklist de Implementacion](#11-checklist-de-implementacion)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Arquitectura Actual vs Propuesta

### 1.1 Arquitectura Actual

```
YCloud (WhatsApp) ──► whatsapp_service ──► POST /chat ──► AI Agent ──► YCloud (respuesta)
Chatwoot (IG/FB/WA) ──► POST /admin/chatwoot/webhook ──► ChannelService ──► AI Agent ──► Chatwoot API (respuesta)
```

Providers actuales registrados en `ChannelService._adapters`:
- `"chatwoot"` → `ChatwootAdapter`
- `"ycloud"` → `YCloudAdapter`

### 1.2 Arquitectura Propuesta (Meta Direct como tercer provider)

```
YCloud (WhatsApp)       ──► whatsapp_service ──► POST /chat ──┐
Chatwoot (IG/FB/WA)     ──► POST /admin/chatwoot/webhook ─────┤
Meta Direct (IG/FB/WA)  ──► meta_service ──► POST /admin/meta-direct/webhook ──┤
                                                               ▼
                                                    ChannelService.normalize_webhook()
                                                               │
                                                    _process_canonical_messages()
                                                               │
                                                    BufferManager → AI Agent
                                                               │
                                                    unified_send_message()
                                                               │
                                              ┌────────────────┼────────────────┐
                                              ▼                ▼                ▼
                                          Chatwoot API    YCloud API    Meta Graph API
                                          (existente)     (existente)     (NUEVO)
```

### 1.3 Principio de Coexistencia

| Provider | WhatsApp | Instagram | Facebook | Entrada | Salida |
|----------|:--------:|:---------:|:--------:|---------|--------|
| Chatwoot | Si | Si | Si | Webhook Chatwoot | Chatwoot API |
| YCloud | Si | No | No | Webhook YCloud / whatsapp_service | YCloud API |
| **Meta Direct** | **Si*** | **Si** | **Si** | **Webhook Meta → meta_service** | **Meta Graph API** |

*WhatsApp via Meta Direct requiere WABA aprobado con Cloud API.

**Regla**: Un tenant puede tener los 3 providers activos simultaneamente. Cada conversacion tiene un `provider` fijo que determina como se envia la respuesta.

---

## 2. Prerequisitos en Meta Developer Portal

### 2.1 App de Meta

1. Crear app en https://developers.facebook.com/apps/ tipo **Business**
2. Anotar **App ID** y **App Secret**

### 2.2 Facebook Login for Business

1. Agregar producto **Facebook Login for Business**
2. Crear **Configuration** (config_id) con permisos:
   - `pages_messaging` — Messenger
   - `pages_manage_metadata` — Suscribir webhooks
   - `instagram_basic` — Info de cuenta IG
   - `instagram_manage_messages` — DMs de IG
   - `whatsapp_business_management` — Gestionar WABA
   - `whatsapp_business_messaging` — Mensajes WA Cloud API
   - `business_management` — Acceso a Business Manager
3. Response type: `code`

### 2.3 Webhooks

En cada producto (Messenger, Instagram, WhatsApp):
- **Callback URL**: `https://<tu-meta-service-publico>/webhook`
- **Verify Token**: valor de `META_VERIFY_TOKEN`
- **Campos**: `messages`, `messaging_postbacks`, `message_reads`, `message_deliveries`

### 2.4 Data Deletion Callback

- URL: `https://<tu-meta-service-publico>/privacy/data-deletion`

---

## 3. Variables de Entorno Nuevas

### 3.1 Frontend (agregar a `.env` del frontend)

```env
# Meta Native Connection
VITE_FACEBOOK_APP_ID=123456789012345
VITE_META_CONFIG_ID=987654321098765
VITE_META_EMBEDDED_SIGNUP=false
VITE_FACEBOOK_API_VERSION=v22.0
```

### 3.2 Meta Service (nuevo servicio)

```env
PORT=8000
META_APP_ID=123456789012345
META_APP_SECRET=abc123def456...
META_VERIFY_TOKEN=clinicforge_meta_verification
META_GRAPH_API_VERSION=v22.0
ORCHESTRATOR_URL=http://orchestrator_service:8000
INTERNAL_SECRET_KEY=${INTERNAL_API_TOKEN}
FRONTEND_URL=https://app.tudominio.com
```

### 3.3 Orchestrator (agregar a las existentes)

```env
# Meta Service URL (nuevo)
META_SERVICE_URL=http://meta_service:8000
```

### 3.4 Credentials que se crean automaticamente (en tabla `credentials`)

Cuando un usuario conecta Meta via popup, el sistema crea automaticamente:

| name | category | Para que |
|------|----------|---------|
| `META_USER_LONG_TOKEN` | meta | Token long-lived del usuario |
| `META_PAGE_TOKEN_{page_id}` | meta | Token especifico por Page |
| `meta_page_token` | meta | Primer Page Token (fallback generico) |
| `META_IG_TOKEN_{ig_id}` | meta | Token de cuenta IG |
| `META_WA_TOKEN_{waba_id}` | meta | Token de WABA |

---

## 4. Frontend: Popup de Conexion

### 4.1 Archivos a Crear

**`frontend_react/src/hooks/useFacebookSdk.ts`**

Hook que carga el SDK de Facebook:
```typescript
import { useState, useEffect } from 'react';

export const useFacebookSdk = () => {
    const [isReady, setIsReady] = useState(false);

    useEffect(() => {
        const appId = import.meta.env.VITE_FACEBOOK_APP_ID;
        if (!appId) return;

        if (window.FB) {
            window.FB.init({ appId, cookie: true, xfbml: true, version: 'v22.0' });
            setIsReady(true);
            return;
        }

        window.fbAsyncInit = function () {
            window.FB.init({ appId, cookie: true, xfbml: true, version: 'v22.0' });
            setIsReady(true);
        };

        const js = document.createElement('script');
        js.id = 'facebook-jssdk';
        js.src = 'https://connect.facebook.net/es_LA/sdk.js';
        document.head.appendChild(js);

        const timeout = setTimeout(() => setIsReady(true), 3000);
        return () => clearTimeout(timeout);
    }, []);

    return isReady;
};
```

**`frontend_react/src/views/MetaConnectionView.tsx`**

Pagina de conexion con el popup. Flujo:
1. Cargar SDK via `useFacebookSdk()`
2. Al click, llamar `FB.login()` con `config_id` y `response_type: 'code'`
3. Obtener `code` o `accessToken` del response
4. Enviar a backend: `POST /admin/meta/connect` con `{ code, redirect_uri }`
5. Mostrar assets descubiertos (Pages, IG, WhatsApp)

### 4.2 Flujo del Popup

```
FB.login(callback, {
    config_id: VITE_META_CONFIG_ID,
    response_type: 'code',
    override_default_response_type: true,
    // Solo si Embedded Signup esta habilitado:
    extras: { feature: 'whatsapp_embedded_signup', setup: {} }
});
```

Meta abre un popup donde el usuario selecciona que Pages, Instagram y WhatsApp quiere conectar. Al completar, retorna un `code` (authorization code).

---

## 5. Nuevo Microservicio: meta_service

### 5.1 Estructura de Archivos

```
meta_service/
├── main.py              # FastAPI app: /connect, /webhook, /subscribe, /messages/send, /whatsapp/send
├── core/
│   ├── auth.py          # OAuth exchange, asset discovery, page webhook subscription
│   ├── webhooks.py      # Normalizacion de payloads Meta → SimpleEvent
│   └── client.py        # HTTP client para comunicarse con orchestrator
├── requirements.txt     # fastapi, httpx, structlog, pydantic
└── Dockerfile
```

### 5.2 Endpoints del meta_service

| Metodo | Ruta | Proposito |
|--------|------|-----------|
| POST | `/connect` | Recibe code/token del frontend, exchange, descubre assets, sync credenciales |
| GET | `/webhook` | Verificacion challenge de Meta (hub.verify_token) |
| POST | `/webhook` | Recibe webhooks de Meta, normaliza, reenvia al orchestrator |
| POST | `/subscribe` | Suscribe assets a webhooks (page-level para FB/IG) |
| POST | `/messages/send` | Proxy para enviar mensajes via Graph API (FB/IG Messenger) |
| POST | `/whatsapp/send` | Proxy para enviar mensajes via WhatsApp Cloud API |
| POST | `/privacy/data-deletion` | Callback obligatorio de Meta |

### 5.3 Flujo de Conexion (POST /connect)

```
1. Recibir { code, tenant_id, redirect_uri }
2. Exchange code → short-lived token (sin redirect_uri para FB Login for Business)
3. Si falla, retry con redirect_uri variants
4. Upgrade a long-lived token (fb_exchange_token)
5. GET /me/accounts → Descubrir Pages + Instagram vinculado
6. Por cada Page: POST /{page_id}/subscribed_apps → Suscribir webhooks
7. GET /me/whatsapp_business_accounts → Descubrir WABAs + phone numbers
8. POST {ORCHESTRATOR_URL}/admin/credentials/internal-sync → Sync credenciales encriptadas
9. Retornar assets sanitizados (sin tokens) al frontend
```

### 5.4 Normalizacion de Webhooks (webhooks.py)

Meta envia payloads diferentes segun plataforma. Se normalizan a `SimpleEvent`:

```python
SimpleEvent = {
    "provider": "meta",
    "platform": "instagram" | "facebook" | "whatsapp",
    "tenant_identifier": "PAGE_ID",  # Para resolver tenant
    "event_type": "message",
    "sender_id": "PSID_USUARIO",
    "recipient_id": "PAGE_ID",
    "sender_name": "User",
    "payload": { "id": "mid", "type": "text", "text": "Hola", "media_url": null }
}
```

**CRITICO**: Filtrar mensajes echo (`message.is_echo: true`) para evitar loops infinitos.

### 5.5 Reenvio al Orchestrator (client.py)

```python
POST {ORCHESTRATOR_URL}/admin/meta-direct/webhook
Headers: { X-Internal-Secret: INTERNAL_SECRET_KEY }
Body: SimpleEvent
```

---

## 6. Orchestrator: Nuevo Adapter + Webhook

### 6.1 Nuevo Adapter: `MetaDirectAdapter`

**Archivo a crear**: `orchestrator_service/services/channels/meta_direct.py`

```python
from typing import List, Dict, Any
from .base import ChannelAdapter
from .types import CanonicalMessage, MediaItem, MediaType

class MetaDirectAdapter(ChannelAdapter):
    """Adapter para normalizar SimpleEvents del meta_service."""

    async def normalize_payload(self, payload: Dict[str, Any], tenant_id: int) -> List[CanonicalMessage]:
        # El payload ya es un SimpleEvent normalizado por meta_service
        if payload.get("provider") != "meta":
            return []

        platform = payload.get("platform", "facebook")
        text = payload.get("payload", {}).get("text")
        media_url = payload.get("payload", {}).get("media_url")

        if not text and not media_url:
            return []

        media = []
        if media_url:
            media.append(MediaItem(
                type=MediaType.IMAGE,  # Simplificado, mejorar segun payload.type
                url=media_url,
                file_name="attachment"
            ))

        return [CanonicalMessage(
            provider="meta_direct",
            original_channel=platform,
            external_user_id=payload.get("sender_id", ""),
            display_name=payload.get("sender_name"),
            tenant_id=tenant_id,
            content=text,
            media=media,
            is_agent=False,
            raw_payload=payload,
            sender={"id": payload.get("sender_id"), "name": payload.get("sender_name")}
        )]
```

### 6.2 Registrar Adapter en ChannelService

**Archivo a modificar**: `orchestrator_service/services/channels/service.py`

```python
from .meta_direct import MetaDirectAdapter

class ChannelService:
    _adapters = {
        "chatwoot": ChatwootAdapter(),
        "ycloud": YCloudAdapter(),
        "meta_direct": MetaDirectAdapter(),  # NUEVO
    }
```

### 6.3 Nuevo Webhook Endpoint

**Archivo a crear**: `orchestrator_service/routes/meta_direct_webhook.py`

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Header
from services.channels.service import ChannelService
from routes.chat_webhooks import _process_canonical_messages
from db import get_pool
import os, logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/admin/meta-direct/webhook")
async def receive_meta_direct_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_internal_secret: str = Header(None)
):
    """Recibe SimpleEvents del meta_service (The Meta Diplomat)."""
    # 1. Verificar secret inter-servicio
    expected = os.getenv("INTERNAL_API_TOKEN", "")
    alt = os.getenv("INTERNAL_SECRET_KEY", "")
    if x_internal_secret not in (expected, alt):
        raise HTTPException(403, "Unauthorized")

    payload = await request.json()

    # 2. Resolver tenant por asset (business_assets)
    pool = get_pool()
    recipient_id = payload.get("recipient_id") or payload.get("tenant_identifier")

    tenant_id = None
    if recipient_id:
        row = await pool.fetchrow(
            "SELECT tenant_id FROM business_assets WHERE content->>'id' = $1 AND is_active = true LIMIT 1",
            str(recipient_id)
        )
        if row:
            tenant_id = int(row['tenant_id'])

    if not tenant_id:
        # Fallback: buscar por bot_phone_number (WhatsApp)
        platform = payload.get("platform")
        if platform == "whatsapp":
            phone = payload.get("recipient_id", "").replace("+", "")
            row = await pool.fetchrow("SELECT id FROM tenants WHERE bot_phone_number = $1", phone)
            if row:
                tenant_id = row['id']

    if not tenant_id:
        logger.warning(f"Meta Direct: No tenant found for recipient {recipient_id}")
        return {"status": "ignored", "reason": "tenant_not_found"}

    # 3. Normalizar via ChannelService
    messages = await ChannelService.normalize_webhook("meta_direct", payload, tenant_id)

    if not messages:
        return {"status": "ignored", "reason": "no_relevant_messages"}

    # 4. Procesar (misma pipeline que Chatwoot/YCloud)
    return await _process_canonical_messages(messages, tenant_id, "meta_direct", background_tasks)
```

### 6.4 Registrar la Ruta

**Archivo a modificar**: `orchestrator_service/main.py` (donde se registran routers)

```python
from routes.meta_direct_webhook import router as meta_direct_router
app.include_router(meta_direct_router)
```

### 6.5 Endpoint Proxy para Conexion

**Archivo a crear o agregar a routes existentes**: endpoint `POST /admin/meta/connect`

```python
@router.post("/admin/meta/connect")
async def connect_meta_account(request: Request, tenant_id: int = Depends(get_resolved_tenant_id)):
    body = await request.json()
    meta_service_url = os.getenv("META_SERVICE_URL", "http://meta_service:8000")

    payload = {
        "tenant_id": tenant_id,
        "code": body.get("code"),
        "access_token": body.get("access_token"),
        "redirect_uri": body.get("redirect_uri")
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{meta_service_url}/connect", json=payload)
        resp.raise_for_status()
        return resp.json()
```

### 6.6 Endpoint de Sync de Credenciales

**Agregar a rutas existentes** (similar al flujo de credentials existente):

El meta_service envia credenciales via `POST /admin/credentials/internal-sync`:

```python
@router.post("/admin/credentials/internal-sync")
async def internal_credential_sync(request: Request, x_internal_secret: str = Header(None)):
    # Verificar secret
    data = await request.json()
    tenant_id = int(data["tenant_id"])
    provider = data["provider"]
    credentials = data["credentials"]

    if provider == "meta":
        assets = credentials.get("assets", {})

        # Guardar token de usuario
        if credentials.get("user_access_token"):
            await save_tenant_credential(tenant_id, "META_USER_LONG_TOKEN", credentials["user_access_token"], "meta")

        # Guardar page tokens
        for page in assets.get("pages", []):
            if page.get("access_token"):
                await save_tenant_credential(tenant_id, f"META_PAGE_TOKEN_{page['id']}", page["access_token"], "meta")
                # Guardar primer token como generico
                await save_tenant_credential(tenant_id, "meta_page_token", page["access_token"], "meta")

        # Guardar IG tokens
        for ig in assets.get("instagram", []):
            if ig.get("access_token"):
                await save_tenant_credential(tenant_id, f"META_IG_TOKEN_{ig['id']}", ig["access_token"], "meta")

        # Guardar WA tokens
        for waba in assets.get("whatsapp", []):
            if waba.get("access_token"):
                await save_tenant_credential(tenant_id, f"META_WA_TOKEN_{waba['id']}", waba["access_token"], "meta")

        # Guardar assets en business_assets
        for page in assets.get("pages", []):
            await upsert_business_asset(tenant_id, "facebook_page", page)
        for ig in assets.get("instagram", []):
            await upsert_business_asset(tenant_id, "instagram_account", ig)
        for waba in assets.get("whatsapp", []):
            await upsert_business_asset(tenant_id, "whatsapp_waba", waba)

    return {"status": "ok"}
```

---

## 7. Delivery: Envio de Respuestas Meta Direct

### 7.1 Modificar `unified_send_message` en chat_api.py

Actualmente `unified_send_message` soporta `chatwoot` y `ycloud`. Agregar `meta_direct`:

```python
# En routes/chat_api.py → unified_send_message()

elif provider == "meta_direct":
    # Obtener page token para este tenant
    page_token = await get_tenant_credential(tenant_id, "meta_page_token")
    if not page_token:
        raise HTTPException(503, "Meta page token not configured")

    if channel == "whatsapp":
        # WhatsApp Cloud API
        phone_number_id = await get_tenant_credential(tenant_id, "WHATSAPP_PHONE_NUMBER_ID")
        wa_token = await get_tenant_credential(tenant_id, f"META_WA_TOKEN_{waba_id}")  # O meta_page_token como fallback

        url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {wa_token}", "Content-Type": "application/json"}
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": external_user_id,
            "type": "text",
            "text": {"body": message}
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
    else:
        # Facebook Messenger / Instagram DM
        url = "https://graph.facebook.com/v22.0/me/messages"
        params = {"access_token": page_token}
        payload = {
            "recipient": {"id": external_user_id},
            "message": {"text": message},
            "messaging_type": "RESPONSE"
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, params=params, json=payload)
            resp.raise_for_status()
```

### 7.2 Modificar Agent Response Delivery

En el flujo de BufferManager → AI Agent → respuesta, el agente envia su respuesta.

Buscar donde el orchestrator envia la respuesta del agente al canal (tipicamente en `main.py` despues de `agent_executor.invoke()`). Agregar logica para `meta_direct`:

```python
# Despues de obtener agent_response:

if provider == "meta_direct":
    page_token = await get_tenant_credential(tenant_id, "meta_page_token")
    if page_token and channel in ("instagram", "facebook"):
        url = "https://graph.facebook.com/v22.0/me/messages"
        async with httpx.AsyncClient() as client:
            await client.post(url, params={"access_token": page_token}, json={
                "recipient": {"id": external_user_id},
                "message": {"text": agent_response},
                "messaging_type": "RESPONSE"
            })
    elif page_token and channel == "whatsapp":
        # WhatsApp Cloud API delivery...
        pass
elif provider == "chatwoot":
    # Logica existente de Chatwoot...
elif provider == "ycloud":
    # Logica existente de YCloud...
```

---

## 8. Migraciones de Base de Datos

### 8.1 Nueva Migracion Alembic

Crear archivo: `orchestrator_service/alembic/versions/005_add_meta_direct_support.py`

```python
"""Add Meta Direct support"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # 1. business_assets table (para almacenar Pages, IG accounts, WABAs descubiertos)
    op.execute("""
        CREATE TABLE IF NOT EXISTS business_assets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
            asset_type TEXT NOT NULL,
            content JSONB NOT NULL,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_business_assets_tenant
            ON business_assets(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_business_assets_content_id
            ON business_assets((content->>'id'));
    """)

    # 2. Asegurar que chat_conversations soporta meta_direct como provider
    # La columna 'provider' ya existe con valores 'ycloud' y 'chatwoot'
    # Solo necesitamos asegurar que no hay CHECK constraint que lo bloquee

    # 3. Agregar columnas opcionales para Meta Direct en conversaciones
    op.execute("""
        ALTER TABLE chat_conversations
            ADD COLUMN IF NOT EXISTS source_entity_id TEXT,
            ADD COLUMN IF NOT EXISTS platform_origin TEXT;
    """)

def downgrade():
    op.execute("DROP TABLE IF EXISTS business_assets;")
    op.execute("""
        ALTER TABLE chat_conversations
            DROP COLUMN IF EXISTS source_entity_id,
            DROP COLUMN IF EXISTS platform_origin;
    """)
```

### 8.2 Tablas Existentes que se Reutilizan

| Tabla | Como se usa para Meta Direct |
|-------|------------------------------|
| `credentials` | Almacena tokens (META_PAGE_TOKEN_*, meta_page_token, META_WA_TOKEN_*) |
| `chat_conversations` | Nuevas conversaciones con `provider='meta_direct'`, `channel='instagram'/'facebook'/'whatsapp'` |
| `chat_messages` | Mensajes entrantes/salientes, identico al flujo actual |
| `patients` | Se crea/busca paciente por `external_user_id` (PSID) — puede requerir campo adicional |
| `inbound_messages` | Deduplicacion (provider='meta_direct', provider_message_id=mid) |

### 8.3 Busqueda de Paciente por PSID

Los PSIDs de Meta no son numeros de telefono. Agregar columnas para lookup:

```sql
ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS instagram_psid TEXT,
    ADD COLUMN IF NOT EXISTS facebook_psid TEXT;

CREATE INDEX IF NOT EXISTS idx_patients_ig_psid ON patients(tenant_id, instagram_psid);
CREATE INDEX IF NOT EXISTS idx_patients_fb_psid ON patients(tenant_id, facebook_psid);
```

---

## 9. Buffer Manager: Soporte meta_direct

### 9.1 Agregar Defaults para meta_direct

**Archivo a modificar**: `orchestrator_service/services/buffer_manager.py`

```python
class BufferManager:
    GLOBAL_DEFAULTS = {
        # ... existentes ...
        "meta_direct_instagram": {
            "debounce_seconds": 8,
            "bubble_delay": 3,
            "max_message_length": 300,
            "typing_indicator": True
        },
        "meta_direct_facebook": {
            "debounce_seconds": 8,
            "bubble_delay": 3,
            "max_message_length": 300,
            "typing_indicator": True
        },
        "meta_direct_whatsapp": {
            "debounce_seconds": 11,
            "bubble_delay": 4,
            "max_message_length": 400,
            "typing_indicator": True
        }
    }
```

### 9.2 Buffer Keys para Meta Direct

Las keys de Redis siguen el patron existente:
```
buffer:meta_direct:{tenant_id}:{sender_psid}
timer:meta_direct:{tenant_id}:{sender_psid}
active_task:meta_direct:{tenant_id}:{sender_psid}
```

No requiere cambios en la logica de `BufferManager.get_buffer_key()` ya que acepta `provider` como parametro.

---

## 10. Docker Compose: Nuevo Servicio

### 10.1 Agregar meta_service al docker-compose.yml

```yaml
  meta_service:
    build: ./meta_service
    ports:
      - "8004:8000"
    environment:
      - PORT=8000
      - META_APP_ID=${META_APP_ID}
      - META_APP_SECRET=${META_APP_SECRET}
      - META_VERIFY_TOKEN=${META_VERIFY_TOKEN:-clinicforge_meta_verify}
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

### 10.2 Agregar variable al orchestrator

```yaml
  orchestrator_service:
    environment:
      # ... existentes ...
      - META_SERVICE_URL=http://meta_service:8000
```

### 10.3 Exponer meta_service en hosting

El `meta_service` necesita una URL publica con HTTPS para que Meta envie webhooks:
```
https://clinicforge-meta.tudominio.com → meta_service:8000
```

---

## 11. Checklist de Implementacion

### Fase 1: Infraestructura (sin cambios al flujo actual)

- [ ] Crear directorio `meta_service/` con `main.py`, `core/auth.py`, `core/webhooks.py`, `core/client.py`
- [ ] Crear `Dockerfile` para meta_service
- [ ] Agregar meta_service al `docker-compose.yml`
- [ ] Configurar variables de entorno (`META_APP_ID`, `META_APP_SECRET`, etc.)
- [ ] Ejecutar migracion: tabla `business_assets`, columnas en `patients`
- [ ] Configurar webhook URL en Meta Developer Portal
- [ ] Verificar que el challenge GET `/webhook` funciona

### Fase 2: Conexion (Frontend + Backend)

- [ ] Crear `useFacebookSdk.ts` hook
- [ ] Crear vista de conexion Meta en frontend
- [ ] Crear endpoint `POST /admin/meta/connect` en orchestrator (proxy a meta_service)
- [ ] Crear endpoint `POST /admin/credentials/internal-sync` en orchestrator
- [ ] Probar: conectar una Page + Instagram via popup → verificar credentials en DB

### Fase 3: Recepcion de Mensajes

- [ ] Crear `MetaDirectAdapter` en `services/channels/meta_direct.py`
- [ ] Registrar adapter en `ChannelService._adapters`
- [ ] Crear endpoint `POST /admin/meta-direct/webhook` en orchestrator
- [ ] Registrar router en `main.py`
- [ ] Verificar filtro de echo en `meta_service/core/webhooks.py`
- [ ] Probar: enviar DM en IG/FB → verificar que aparece en `chat_messages`

### Fase 4: Respuesta del Agente

- [ ] Agregar `meta_direct` defaults en `BufferManager.GLOBAL_DEFAULTS`
- [ ] Agregar logica `meta_direct` en `unified_send_message` (chat_api.py)
- [ ] Agregar logica `meta_direct` en la respuesta del agent (main.py, post agent_executor)
- [ ] Probar: enviar DM → agente responde → respuesta aparece en IG/FB

### Fase 5: UI y Polish

- [ ] Mostrar icono de canal (IG/FB/WA) en lista de conversaciones
- [ ] Agregar filtro por provider en la vista de Chats
- [ ] Probar flujo completo end-to-end con los 3 providers activos

---

## 12. Troubleshooting

### El popup no se abre
- Verificar `VITE_FACEBOOK_APP_ID` y `VITE_META_CONFIG_ID`
- Verificar que ad blockers no bloqueen `connect.facebook.net`

### El code exchange falla
- Verificar `META_APP_ID` y `META_APP_SECRET` en meta_service
- El code expira en ~10 minutos

### Webhooks no llegan
- URL debe ser HTTPS publica
- `META_VERIFY_TOKEN` debe coincidir
- Verificar suscripcion: `POST /{page_id}/subscribed_apps`

### Mensajes llegan pero el agente no responde
- Verificar que `provider='meta_direct'` esta en la conversacion
- Verificar que `BufferManager` acepta provider `meta_direct`
- Verificar logs: buscar `agent_execution` o `buffer` errors
- **Bug conocido en Platform AI Solutions**: `datetime.utcnow()` vs TIMESTAMPTZ causa TypeError silencioso en checks de 24h. Usar siempre `datetime.now(timezone.utc)` y normalizar timestamps naive antes de comparar.

### El agente responde pero no llega al usuario
- Verificar que `meta_page_token` existe en credentials para ese tenant
- Verificar que el token no ha expirado (long-lived tokens duran ~60 dias)
- Para Instagram: el Page Token de la Page vinculada debe tener permiso `instagram_manage_messages`

### Loops infinitos
- Verificar filtro de `is_echo` en `meta_service/core/webhooks.py`
- Sin este filtro, cada respuesta del bot genera un nuevo webhook

### Conflicto con Chatwoot
- Si el mismo canal (ej: Instagram) esta conectado via Chatwoot Y Meta Direct, se crearan conversaciones separadas con diferentes providers
- Recomendacion: usar solo UN provider por canal por tenant para evitar confusion
