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
