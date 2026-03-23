# Integrations Logic Deep Dive

Este documento profundiza en la lógica de integración de canales de Chat (WhatsApp/YCloud, Instagram/Facebook/Chatwoot) y los servicios cognitivos asociados (Vision, Audio).

## 1. AI Vision Service (Ojos del Agente)

### Arquitectura
El servicio de visión (`orchestrator_service/services/vision_service.py`) dota al agente de capacidades multimodales.

- **Modelo**: GPT-4o.
- **Entrada**: URLs de imágenes (públicas o firmadas).
- **Salida**: Descripciones textuales ricas inyectadas en el contexto del bot.

### Flujo de Datos
1. **Recepción**:
   - **YCloud**: El endpoint `POST /chat` recibe `media` con `type: image`.
   - **Chatwoot**: El webhook recibe `attachments` con `type: image`.
2. **Persistencia**:
   - Se guarda el mensaje en `chat_messages` con `content_attributes` conteniendo la URL.
   - **Critical**: Se captura el `message_id` retornado por el INSERT.
3. **Trigger**:
   - Se encola una `Background Task` (`process_vision_task`).
   - El hilo principal retorna inmediatamente (no bloquea la respuesta HTTP).
4. **Análisis (Async)**:
   - Descarga/Accede a la imagen.
   - Envía a OpenAI con un prompt de sistema especializado ("Describe esta imagen para un asistente dental...").
5. **Enriquecimiento**:
   - Actualiza la fila en `chat_messages` agregando el campo `description` dentro de `content_attributes`.
6. **Consumo**:
   - Al siguiente turno del bot (`buffer_task.py`), se consultan las imágenes recientes (< 5 min) del usuario.
   - Se inyecta `[CONTEXTO VISUAL: <descripción>]` en el system prompt.

## 2. Audio & Transcripción (Oídos del Agente)

### Unificación de Canales
Originalmente, solo WhatsApp (YCloud) tenía transcripción. Ahora, Chatwoot (Instagram/Facebook) también la soporta.

- **WhatsApp**: La transcripción ocurre en `whatsapp_service` antes de llegar al Orchestrator.
- **Chatwoot**: La transcripción ocurre en el Orchestrator (`chat_webhooks.py`) tras recibir el webhook.

### Lógica Chatwoot Audio
1. **Detección**: Webhook recibe adjunto. Si `file_type` es `audio` o el mime-type es audio (`audio/ogg`, `audio/mpeg`, `audio/mp4`), se trata como mensaje de voz.
2. **Normalización**: Se fuerza el tipo `audio` en la metadata para que el Frontend renderice el reproductor `<audio>` en lugar de un link de descarga.
3. **Procesamiento**:
   - Se invoca `transcribe_audio_url` (Whisper API).
   - El texto transcrito se usa para el procesamiento del Agente IA.

## 3. Descarga y Proxy de Medios (Spec 22)

Para evitar problemas de CORS y expiración de URLs firmadas (S3/Facebook/WhatsApp), el sistema centraliza la gestión de medios.

### Flujo de Descarga (`download_media`)
1. **Intercepción**: Al recibir un medio en `/chat` o Webhook Chatwoot.
2. **Descarga Local**: Se descarga el archivo a `media/<tenant_id>/<uuid>.<ext>`.
3. **Reemplazo**: En la BD se guarda la URL local `/media/...` y se preserva la original en `original_url`.

### Proxy Seguro (`/admin/chat/media/proxy`)
Endpoint autenticado para servir archivos que requieren headers específicos o tokens rotativos.

## 4. Deduplicación de Mensajes (Spec 20)

Para garantizar idempotencia ante reintentos de webhooks y "ecos" de Chatwoot.

- **Tabla**: `inbound_messages`.
- **Clave Única**: `(provider, provider_message_id)`.
- **Lógica**:
  1. `try_insert_inbound` intenta insertar.
  2. Si hay conflicto (duplicado), retorna `False` -> Se ignora el mensaje.
  3. Si es nuevo, retorna `True` -> Se procesa.
- **Ventana de Procesamiento**: Redis Lock para evitar condiciones de carrera en intervalos de milisegundos.

### 4.1. Deduplicación Robusta (YCloud/Chatwoot Echo)
Para evitar que el bot se responda a sí mismo o duplique mensajes confirmados por webhook:
- **Estrategia**: Se ignora el mensaje entrante si su ID coincide con `platform_metadata->>'provider_message_id'` de un mensaje ya guardado.
- **YCloud**: El ID del mensaje se extrae de `message.id` (no del evento).
- **Chatwoot**: El ID del mensaje se extrae de `id`.

## 5. Buffering & Contexto (Spec 24/25)

El sistema implementa un **Buffer Unificado** (`relay.py`) para WhatsApp (YCloud) e Instagram/Facebook (Chatwoot) con el objetivo de agrupar mensajes en ráfaga y dar tiempo al análisis de imágenes.

### Lógica "Sliding Window" (Rebote)
- **Comportamiento**: Cada mensaje nuevo del usuario reinicia el contador de espera.
- **Debounce**: El bot no responde hasta que detecta "silencio" por X segundos.

### Tiempos de Espera (TTL)
1. **Texto/Audio**: **10 segundos**. (Para conversaciones fluidas).
2. **Imagen**: **20 segundos**. (Para dar tiempo a GPT-4o Vision).
   - **Critical**: Si llega una imagen, el buffer se extiende a 20s. Mensajes de texto posteriores **NO** reducen este tiempo (se respeta el `max(remaining_ttl, 10)`).

### Recuperación de Contexto (Amnesia Fix)
Antes de invocar al Agente, la tarea `process_buffer_task`:
1. **Fetch History**: Recupera los últimos **10 mensajes** de la BD (no solo el buffer).
2. **Deduplicación**: Elimina el último mensaje del historial si coincide con el primero del buffer (evita duplicados).
3. **Ad Context**: Inyecta información de `meta_ad_headline` si el paciente provino de un anuncio (ej. Urgencias).

## 5.5. Retry System & Exponential Backoff (Cura al Descarte)
Dado que los fallos transitorios en las APIs de los LLMs (ej. OpenAI, Groq) u otros errores de red podían romper la cadena de buffers y dejar los mensajes "huérfanos", la ejecución principal del generador de IA (`executor.ainvoke` en `buffer_task.py`) ahora opera bajó un bloque de reintentos:
- **Intento 1**: Ejecución normal.
- **Si falla**: Pausa `asyncio.sleep(2 ** attempt)` y retoma.
- **Límite**: 3 intentos. Si se supera el límite, despacha por el send path natural una frase de disculpas genérica, para asegurarse de limpiar el canal sin comprometer UX, manteniendo al paciente notificado.

## 5.6. Respuesta Sender & Burbujas Multimedia (Smart Splitter)
El sistema divide las respuestas largas del agente IA en párrafos semánticos o frases, simulando "Envío de Burbujas" reales con pausas (`typing_on` + Delay de X segundos) adaptables para YCloud y Chatwoot por igual.
Adicionalmente, se integró el **Multimedia Sender**:
1. **Extracción**: El Sender escanea la respuesta de la IA por el tag interno `[LOCAL_IMAGE:/media/X]`. Al detectarlo, limpia el texto para el paciente.
2. **Priorización**: Manda *primeramente* la imagen usando los endpoints nativos de cada proveedor (`send_attachment` en Chatwoot, `send_image` en YCloud).
3. **Flujo de Texto**: Luego de enviar la imagen exitosamente, ejecuta el split normal de texto, añadiendo los delays que correspondan, entregando una UX multimedia fluida.

## 6. Configuración de Credenciales (YCloud)
> [!IMPORTANT]
> Para que el canal de WhatsApp (YCloud) funcione, es OBLIGATORIO configurar las siguientes credenciales en la base de datos (tabla `credentials`):

| Nombre | Descripción | Ejemplo |
| :--- | :--- | :--- |
| `YCLOUD_API_KEY` | API Key de YCloud | `gAAAA...` |
| `YCLOUD_WHATSAPP_NUMBER` | Número del remitente (Bot) | `+54911...` |
| `YCLOUD_WEBHOOK_SECRET` | Secreto para validar firma | `whsec_...` |

> [!NOTE]
> **YCloud API v2 Upgrade (Marzo 2026):**
> 1. **Inbound Webhooks**: El sistema ahora rastrea los webhooks usando la validación de YCloud API v2 (`type == "whatsapp.inbound_message.received"`), leyendo nombres de perfil desde `customerProfile.name` y extrayendo metadatos nativos desde la llave `whatsappInboundMessage`.  
> 2. **Outbound Sender**: Las respuestas de texto y multimedia se transmiten directamente al endpoint V2 sincronizado (`https://api.ycloud.com/v2/whatsapp/messages/sendDirectly`).  
> 3. **Número del Remitente**: Aunque `YCLOUD_WHATSAPP_NUMBER` puede existir en credentials como fallback heredado de la v1, el Orquestador V2 siempre prefiere leer dinámicamente el `bot_phone_number` seteado en la interfaz de usuario en la tabla `tenants` para soportar infraestructuras Multi-Sede (Multi-Tenancy) limpias.

## 7. Meta Ads ROI Engine (Mission 3)

El sistema de marketing integra datos de Meta Ads con la facturación real de la clínica para calcular el ROI real generado por los anuncios.

### Arquitectura de Conexión
1. **OAuth Flow**: El usuario conecta su cuenta de Facebook. El token se guarda en `credentials` (tenant-scoped).
2. **Discovery**: El sistema explora las Ad Accounts disponibles (Owned y Client accounts).
3. **Persistence**: El `ad_account_id` seleccionado se guarda en la configuración del tenant.

### Algoritmo de Cálculo de ROI
- **Gasto (Spend)**: Se obtiene vía Meta Insights API con `date_preset=maximum` (lifetime) o rangos específicos.
- **Ingresos (Revenue)**: Se suman los tratamientos completados (`billing`) de pacientes cuya `source` sea "Meta Ads" o provengan de un `ad_id` rastreado.
- **ROI**: `((Revenue - Spend) / Spend) * 100`.

## 8. Meta Native Connection (Sesion 2026-03-22)

### Arquitectura

Tercer provider de mensajeria (`meta_direct`) que conecta Facebook Messenger e Instagram DM directamente via Meta Graph API, sin depender de Chatwoot como intermediario. Coexiste con YCloud y Chatwoot.

```
YCloud (WhatsApp)       → whatsapp_service → POST /chat
Chatwoot (IG/FB/WA)     → POST /admin/chatwoot/webhook
Meta Direct (IG/FB/WA)  → meta_service → POST /admin/meta-direct/webhook
                                ↓
                    ChannelService.normalize_webhook()
                                ↓
                    _process_canonical_messages() (pipeline compartido)
                                ↓
                    BufferManager → AI Agent → ResponseSender
```

### Microservicio: meta_service

Servicio independiente (`meta_service/`) desplegado en EasyPanel como `dentalforge-metaservice`.

**Endpoints:**
- `POST /connect` — Recibe code/token del popup de FB Login, exchange a long-lived token, descubre assets, sync credenciales al orchestrator
- `GET /webhook` — Verificacion challenge de Meta
- `POST /webhook` — Recibe webhooks de Meta, normaliza a SimpleEvent, reenvia al orchestrator
- `POST /messages/send` — Proxy para enviar mensajes via Graph API (FB/IG)
- `POST /whatsapp/send` — Proxy para WhatsApp Cloud API
- `POST /privacy/data-deletion` — Callback GDPR obligatorio

**Filtro de Echo**: `webhooks.py` filtra `message.is_echo: true` para evitar loops infinitos.

### Orchestrator: MetaDirectAdapter

Archivo: `services/channels/meta_direct.py`

Registrado en `ChannelService._adapters["meta_direct"]`. Convierte `SimpleEvent` a `CanonicalMessage` para pasar por el mismo pipeline que YCloud y Chatwoot.

**Resolucion de nombre**: `routes/meta_direct_webhook.py` busca el nombre real del sender via Graph API Conversations endpoint antes de normalizar.

### Endpoints del Orchestrator (Meta)

| Metodo | Ruta | Proposito |
|--------|------|-----------|
| POST | `/admin/meta/connect` | Proxy al meta_service para conexion via popup |
| DELETE | `/admin/meta/disconnect` | Limpieza total: credentials + assets + conversaciones + mensajes + PSIDs |
| GET | `/admin/meta/status` | Verifica si Meta esta conectado para el tenant |
| POST | `/admin/meta-direct/webhook` | Recibe SimpleEvents del meta_service |
| POST | `/admin/credentials/internal-sync` | Almacena tokens encriptados del meta_service |

### Credenciales (tabla `credentials`)

| name | category | Descripcion |
|------|----------|-------------|
| `META_USER_LONG_TOKEN` | meta | Token long-lived (~60 dias) |
| `META_PAGE_TOKEN_{page_id}` | meta | Token por Facebook Page |
| `meta_page_token` | meta | Primer Page Token (fallback) |
| `META_IG_TOKEN_{ig_id}` | meta | Token por cuenta Instagram |
| `META_WA_TOKEN_{waba_id}` | meta | Token por WABA |

### Frontend: Tab Meta en Settings

`ConfigView.tsx` tiene una nueva tab "Meta" (lazy-loaded `MetaConnectionTab.tsx`) con:
- Popup de Facebook Login for Business (`useFacebookSdk.ts`)
- Estados: idle → connecting → connected (con assets) → disconnect
- Selector de sede/tenant para multi-clinica

### Delivery

`ResponseSender` en `response_sender.py` tiene case `meta_direct`:
- Instagram/Facebook: `POST /me/messages` con page_token
- WhatsApp Cloud API: `POST /{phone_number_id}/messages` con WA token

### Migracion DB (Alembic 005)

- Tabla `business_assets` (Pages, IG accounts, WABAs descubiertos)
- Columnas `instagram_psid`, `facebook_psid` en `patients`
- Columnas `source_entity_id`, `platform_origin` en `chat_conversations`

### Limitaciones Actuales

- **Instagram via Meta Direct**: requiere `instagram_manage_messages` en Advanced Access (App Review de Meta). Mientras tanto, Instagram funciona via Chatwoot.
- **WhatsApp via Meta Direct**: requiere status de Tech Provider. Se sigue usando YCloud.

---

## 9. Fixes Chatwoot (Sesion 2026-03-22)

### Bugs Corregidos

1. **`sender` None en webhooks**: Chatwoot envia eventos de sistema sin `sender`. El adapter ahora retorna `[]` en vez de crashear con `AttributeError`.

2. **`services/redis_client.py` faltante**: El modulo no existia, causando `ImportError` al encolar buffer. Creado con `get_redis()` singleton.

3. **ChatwootAdapter retornaba `[]` siempre**: El adapter encolaba el buffer internamente con el Chatwoot conversation ID (int) en vez del UUID de la DB, causando `'int' has no attribute bytes'`. Fix: el adapter ahora retorna `[CanonicalMessage]` y deja que `_process_canonical_messages` maneje todo.

4. **Variable `row` sobreescrita por loop**: `for row in context_rows` en `buffer_task.py` sobreescribia la variable `row` original (con datos de la conversacion: provider, chatwoot IDs). Fix: renombrada a `ctx_row`.

5. **Token tracking `os` shadowing**: `import os` local dentro de un bloque condicional shadowed el `import os` global, causando `UnboundLocalError` cuando el bloque no se ejecutaba.

6. **Logger kwargs crash**: `logger.warning("msg", conv_id=x)` usaba kwargs que el logger standard de Python no acepta. Fix: usar f-string.

### Mejoras de Paridad Chatwoot ↔ YCloud

1. **Typing indicator**: `ChatwootClient.send_action()` agregado para mostrar "escribiendo..." en conversaciones de Chatwoot.

2. **Patient lookup ampliado**: Query de `patient_documents` ahora busca por `instagram_psid` y `facebook_psid` ademas de `phone_number`.

3. **Subtitulo de contacto en UI**: IDs numericos cortos (1-5 digitos) de Chatwoot se reemplazan por el nombre del canal ("Instagram", "Facebook") en la lista de chats.

4. **Vision context con espera**: El buffer task ahora espera hasta 15s para que el vision service termine de analizar imagenes antes de invocar al agente. Re-fetcha historial despues de la espera.

5. **Media sin paciente**: Si no existe ficha de paciente, el agente NO dice "lo guarde en tu ficha". En su lugar, usa el contexto visual para responder sobre la imagen.

### 7.1. Estrategia "Master Ad List" (Mission 6)
Para resolver la limitación de la Meta Graph API que oculta anuncios con gasto 0 al solicitar `insights` expandidos, el sistema implementa un protocolo de dos pasos:

1. **Fetch Maestro**: Se listan todos los anuncios filtrando por `effective_status` (incluyendo `CAMPAIGN_PAUSED`, `ADSET_PAUSED`, `WITH_ISSUES`).
2. **Enriquecimiento**: Se obtienen los `insights` por separado y se reconcilian en memoria.
3. **Visibilidad Total**: Esto garantiza que el 100% de los anuncios creados sean visibles en el Marketing Hub, permitiendo al CEO ver incluso campañas pausadas o sin rendimiento.

## 8. AI Guardrails & Prompt Security (Spec 27)

Para proteger al Agente de ataques de inyección y garantizar la integridad de los datos clínicos, se ha implementado una capa de defensa híbrida.

### 8.1. Blacklist Layer (`core/prompt_security.py`)
Antes de que el mensaje llegue al Agente LangChain, se escanea en busca de patrones maliciosos:
- **Injection Detection**: Bloquea frases como "ignore previous instructions", "system prompt", "dan mode", etc.
- **Respuesta de Bloqueo**: Si se detecta un ataque, el sistema retorna un estado `security_blocked` inmediato sin consumir tokens de LLM.

### 8.2. Sanitización de Entrada
Se aplica una limpieza estricta para eliminar secuencias de control, caracteres invisibles y etiquetas que puedan confundir al parseador de herramientas (JSON/Python).

### 8.3. Validación Técnica de Herramientas (Gatekeepers)
Las herramientas de agendamiento (`book_appointment`) actúan como filtros finales:
- **DNI**: Debe contener números. Si es inválido, retorna `DNI_MALFORMED`.
- **Nombres**: Deben tener longitud mínima. Si es inválido, retorna `NAME_TOO_SHORT`.
- **Feedback Cooperativo**: Estos errores técnicos se pasan al Agente IA para que este pueda explicarle amablemente al paciente qué corregir.

## 9. Motor de Automatización ("Maintenance Robot")

> [!WARNING]
> **DEPRECATED (Marzo 2026)**: El motor monolítico original en `orchestrator_service/services/automation_service.py` ha sido completamente retirado.
> Ver [`SISTEMA_JOBS_PROGRAMADOS.md`](SISTEMA_JOBS_PROGRAMADOS.md) para la nueva arquitectura y cronograma de tareas.

### Nueva Arquitectura Modular (`jobs/`)
El sistema ahora opera con módulos independientes acoplados al ciclo de vida de FastAPI (Lifespan):
- **`jobs/reminders.py`**: Dispara un recordatorio de HSM 24 horas previas al turno agendado.
- **`jobs/lead_recovery.py`**: Sistema inteligente que lee el historial del chat de un Lead (meta Ads), evalúa los servicios conversados, revisa la disponibilidad de forma dinámica en JIT y envía un último mensaje pro-activo para agendar.
- **`jobs/followups.py`**: Seguimiento clínico post-atención (cirugías).

### Ejecución
Se basa en un Scheduler Asíncrono Central que inicializa todas las rutinas registradas al encender la app y procesa cada rutina iterativamente sin bloquear los request-handling concurrentes.
