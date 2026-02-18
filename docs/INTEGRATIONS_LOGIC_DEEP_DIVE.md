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

## 6. Configuración de Credenciales (YCloud)
> [!IMPORTANT]
> Para que el canal de WhatsApp (YCloud) funcione, es OBLIGATORIO configurar las siguientes credenciales en la base de datos (tabla `credentials`):

| Nombre | Descripción | Ejemplo |
| :--- | :--- | :--- |
| `YCLOUD_API_KEY` | API Key de YCloud | `gAAAA...` |
| `YCLOUD_WHATSAPP_NUMBER` | Número del remitente (Bot) | `+54911...` |
| `YCLOUD_WEBHOOK_SECRET` | Secreto para validar firma | `whsec_...` |

Sin `YCLOUD_WHATSAPP_NUMBER`, el servicio `buffer_task.py` fallará al intentar enviar respuestas.
