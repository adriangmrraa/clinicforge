# Spec: Telegram Multimedia + Intelligent Buffer

## S1: Audio/Voice Handler

### Requirements
- Registrar handler para `filters.VOICE` y `filters.AUDIO` en python-telegram-bot
- Descargar archivo de audio via `update.message.voice.get_file()` → `file.download_as_bytearray()`
- Obtener metadata: `duration`, `file_size`, `mime_type` (normalmente `audio/ogg` con codec OPUS)
- Transcribir con OpenAI Whisper API: POST `https://api.openai.com/v1/audio/transcriptions` con `model=whisper-1`
- Enviar bytes crudos sin conversión de formato (Whisper acepta .ogg nativo)
- Inyectar transcripción en el input de Nova como: `[AUDIO ({duration}s): "{transcripción}"]`
- Si hay caption (texto adjunto al audio, raro pero posible): concatenar
- Mostrar typing indicator durante la transcripción
- Si la transcripción falla: responder "No pude transcribir el audio. Intentá de nuevo o escribí el mensaje."
- Límite: 20MB (Telegram Bot API standard limit)

### Scenarios
```
DADO que un usuario autorizado envía una nota de voz de 15 segundos
CUANDO el handler recibe el audio
ENTONCES descarga los bytes → transcribe con Whisper → inyecta "[AUDIO (15s): texto]"
→ procesa con Nova → responde con el resultado
Y muestra typing indicator durante todo el proceso

DADO que el audio dura 3 minutos (180s)
CUANDO Whisper tarda 5-8 segundos en transcribir
ENTONCES muestra typing indicator continuo
Y la transcripción se procesa correctamente

DADO que Whisper falla (timeout, error de API)
CUANDO no se obtiene transcripción
ENTONCES responde "No pude transcribir el audio. Intentá de nuevo o escribí el mensaje."
Y NO llama a Nova

DADO que un usuario NO autorizado envía un audio
CUANDO se verifica el chat_id
ENTONCES responde con mensaje de no autorización
Y NO descarga ni transcribe el audio
```

## S2: Image Handler

### Requirements
- Registrar handler para `filters.PHOTO` en python-telegram-bot
- Descargar la foto de mayor resolución: `update.message.photo[-1].get_file()` → `file.download_as_bytearray()`
- Convertir a base64: `base64.b64encode(bytes).decode()`
- Analizar con GPT-4o vision usando prompt dental contextualizado (mismo que `vision_service.py`)
- Clasificar con `classify_message()` de `image_classifier.py`: determinar si es comprobante de pago o documento clínico
- Inyectar en input de Nova como: `[IMAGEN: "{descripción_vision}"]\n{clasificación_context}`
- Si la imagen tiene caption: agregar `Caption: {caption_text}` al input
- Si `classify_message()` detecta comprobante de pago:
  - Verificar si algún paciente del tenant tiene pago pendiente
  - Inyectar contexto: "PROBABLE COMPROBANTE DE PAGO — usar verify_payment_receipt"
- Mostrar typing indicator durante el análisis
- Si el análisis falla: responder "No pude analizar la imagen. Intentá de nuevo."

### Scenarios
```
DADO que un usuario autorizado envía una foto de un comprobante bancario
CUANDO el handler recibe la imagen
ENTONCES descarga → base64 → GPT-4o vision → classify_message
Y detecta is_payment=true
Y inyecta "[IMAGEN: Comprobante de transferencia bancaria por $50.000 a nombre de...]"
Y agrega "PROBABLE COMPROBANTE DE PAGO"
Y Nova llama a verify_payment_receipt automáticamente

DADO que un usuario envía una foto clínica (radiografía)
CUANDO el handler clasifica la imagen
ENTONCES detecta is_medical=true
Y inyecta "[IMAGEN: Radiografía periapical de pieza 36 mostrando...]"
Y Nova procesa como contexto clínico

DADO que un usuario envía una foto con caption "comprobante de García"
CUANDO el handler procesa
ENTONCES incluye tanto la descripción visual como el caption
Y Nova tiene el contexto completo para actuar

DADO que la imagen es demasiado oscura o ilegible
CUANDO GPT-4o no puede describir
ENTONCES responde "No pude analizar la imagen. Probá con una foto más clara."
```

## S3: Document/PDF Handler

### Requirements
- Registrar handler para `filters.Document.ALL` en python-telegram-bot
- Filtrar por mime_type: solo procesar `application/pdf` y tipos de imagen
- Descargar via `update.message.document.get_file()` → `file.download_as_bytearray()`
- Validar tamaño: máximo 5MB para PDFs (Telegram permite hasta 20MB, pero vision tiene límite)
- Analizar con GPT-4o vision usando `data:application/pdf;base64,{b64}` (mismo patrón que `analyze_pdf_url`)
- Inyectar en input como: `[DOCUMENTO ({file_name}): "{descripción}"]`
- Si tiene caption: agregar al input
- Clasificar como comprobante o clínico usando `classify_message()`
- Mostrar typing indicator durante el análisis

### Scenarios
```
DADO que un usuario envía un PDF de autorización de obra social
CUANDO el handler procesa el documento
ENTONCES descarga → base64 → GPT-4o vision → descripción
Y inyecta "[DOCUMENTO (autorizacion_os.pdf): Solicitud de autorización para...]"
Y Nova puede actuar sobre el contenido

DADO que un usuario envía un PDF de 8MB
CUANDO el handler verifica el tamaño
ENTONCES responde "El archivo es muy grande (8MB). El máximo es 5MB."
Y NO procesa el documento

DADO que un usuario envía un archivo .docx (no PDF)
CUANDO el handler verifica el mime_type
ENTONCES responde "Solo puedo procesar archivos PDF e imágenes."
Y NO procesa el archivo

DADO que un usuario envía un PDF con caption "informe de García"
CUANDO el handler procesa
ENTONCES incluye descripción + caption
Y Nova tiene contexto completo
```

## S4: Intelligent Message Buffer

### Requirements
- Implementar buffer de mensajes por chat_id usando Redis (mismo patrón que `relay.py`)
- **Ventana de silencio**: 12 segundos para texto, 20 segundos para media (audio/imagen/doc)
- **Sliding window**: Si llega un nuevo mensaje antes de que expire el timer, se extiende
- **Minimum remaining TTL**: Si quedan < 4 segundos, extender a 4s mínimo
- **Acumulación**: Todos los mensajes (texto + media procesada) se acumulan en una lista Redis
- **Procesamiento**: Cuando el timer expira (silencio completo), drenar la lista y procesar TODO junto
- **Lock**: Un solo consumer task por chat_id activo a la vez (evitar duplicados)
- **Buffer key format**: `tg_buffer:{tenant_id}:{chat_id}`
- **Timer key format**: `tg_timer:{tenant_id}:{chat_id}`
- **Lock key format**: `tg_lock:{tenant_id}:{chat_id}`

### Flow detallado
```
1. Llega mensaje (texto, audio, imagen, doc)
2. Si es media → procesar (Whisper/Vision) → obtener texto enriquecido
3. Agregar texto enriquecido a Redis list: RPUSH tg_buffer:{t}:{c}
4. Calcular TTL: 12s (texto) o 20s (media)
5. Refresh timer: SETEX tg_timer:{t}:{c} TTL "1"
6. Si no hay consumer activo (lock key no existe):
   a. SET tg_lock:{t}:{c} "1"
   b. Spawn async task: _telegram_buffer_consumer(tenant_id, chat_id, update)
7. Consumer loop:
   a. Sleep 2s
   b. Check TTL de tg_timer → si > 0, seguir esperando
   c. Si TTL = 0 (silencio completo):
      - LRANGE tg_buffer:{t}:{c} 0 -1 → drain all
      - DELETE tg_buffer:{t}:{c}
      - Concatenar todos los mensajes en un solo input
      - Llamar _process_with_nova(input_combinado, ...)
      - Enviar respuesta al chat
   d. DELETE tg_lock:{t}:{c}
```

### Scenarios
```
DADO que un usuario envía 3 mensajes rápidos: "Hola", "buscame a García", "y cobrále"
CUANDO llegan con 2 segundos entre cada uno
ENTONCES el buffer acumula los 3 mensajes
Y el timer se extiende con cada mensaje
Y cuando pasan 12s de silencio → procesa "Hola\nbuscame a García\ny cobrále" como un solo input
Y Nova responde una sola vez con la acción completa

DADO que un usuario envía texto + foto rápido
CUANDO llegan texto (12s) y foto (20s)
ENTONCES el timer usa 20s (media tiene prioridad)
Y el buffer contiene: "texto del usuario\n[IMAGEN: descripción]"
Y se procesa junto cuando hay silencio

DADO que un usuario envía un solo mensaje
CUANDO no llegan más mensajes en 12 segundos
ENTONCES el buffer procesa ese único mensaje normalmente
Y la experiencia es transparente (parece respuesta directa)

DADO que Redis no está disponible
CUANDO el buffer falla al escribir
ENTONCES fallback: procesar el mensaje inmediatamente (sin buffer)
Y logear warning
```

## S5: Media Processing Integration

### Requirements
- Reutilizar servicios existentes del orchestrator:
  - `services/whisper_service.py` → patrón de llamada a Whisper API (adaptar para bytes directos)
  - `services/vision_service.py` → `analyze_image_url()` patrón (adaptar para bytes base64)
  - `services/image_classifier.py` → `classify_message()` directamente
- Para audio: llamada directa a OpenAI Whisper API (no pasar por whisper_service que espera URL)
- Para imágenes: llamada directa a GPT-4o con base64 inline (no pasar por vision_service que espera URL)
- Para PDFs: llamada directa a GPT-4o con base64 inline
- Los prompts de vision deben ser los mismos que usa el sistema WhatsApp (contexto dental)
- Toda la lógica de descarga y procesamiento va en funciones helper dentro de `telegram_bot.py`

### Helpers a crear
```python
async def _transcribe_audio(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Transcribe audio bytes with OpenAI Whisper. Returns text."""

async def _analyze_image(image_bytes: bytes, caption: str = "") -> dict:
    """Analyze image with GPT-4o vision. Returns {description, is_payment, is_medical}."""

async def _analyze_document(doc_bytes: bytes, filename: str, mime_type: str) -> dict:
    """Analyze PDF/document with GPT-4o vision. Returns {description}."""
```

## S6: Typing Indicator Management

### Requirements
- Enviar `typing` action al inicio de CADA procesamiento (auth check pasado)
- Para procesos largos (Whisper + Nova, Vision + Nova): renovar typing cada 5 segundos
- Implementar como background task que envía `send_action("typing")` en loop cada 5s
- Cancelar el typing task cuando se envía la respuesta final

### Scenarios
```
DADO que un audio de 2 minutos tarda 10 segundos en transcribir + 5 en procesar con Nova
CUANDO el usuario está esperando respuesta
ENTONCES ve "escribiendo..." continuamente durante los 15 segundos
Y NO ve pausas en el indicador de typing
```
