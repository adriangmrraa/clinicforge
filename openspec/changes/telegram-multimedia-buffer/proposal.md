# Proposal: Telegram Multimedia + Intelligent Buffer

## Intent
Llevar la experiencia de Nova en Telegram al mismo nivel que el agente de WhatsApp: soporte de audio (transcripción con Whisper), imágenes (análisis con GPT-4o vision + clasificación comprobante/clínico), documentos PDF, y buffer inteligente de mensajes para acumular ráfagas antes de procesar.

## Scope

### In Scope
1. **Handler de audio/voz** — Recibir notas de voz de Telegram, descargar bytes, transcribir con OpenAI Whisper API, inyectar transcripción en el input de Nova
2. **Handler de imágenes** — Recibir fotos, descargar, analizar con GPT-4o vision, clasificar (comprobante de pago vs documento clínico), inyectar contexto visual en Nova
3. **Handler de documentos** — Recibir PDFs y archivos, descargar, analizar con vision, inyectar contexto en Nova
4. **Buffer inteligente** — Acumular mensajes rápidos (texto + media) en ventana de tiempo antes de procesarlos juntos, usando Redis (mismo patrón que WhatsApp relay.py)
5. **Detección automática de comprobantes** — Si el usuario autorizado envía imagen y hay paciente con pago pendiente, activar flujo de verificación de comprobante
6. **Caption support** — Las fotos/docs con caption se procesan juntos (caption + media)

### Out of Scope
- Envío de archivos/fotos DESDE Nova al chat (solo recepción)
- Stickers, GIFs, ubicación, contactos
- Video (por ahora)
- Grupos de Telegram (solo chats privados)

## Approach
Reutilizar los servicios existentes del orchestrator:
- `services/whisper_service.py` → patrón de transcripción (POST directo a OpenAI, sin conversión de formato)
- `services/vision_service.py` → `analyze_image_url()` y `analyze_pdf_url()` adaptados para bytes directos
- `services/image_classifier.py` → `classify_message()` para detectar comprobantes vs documentos clínicos
- `services/relay.py` → patrón de buffer Redis (sliding window debounce)

Todo se implementa dentro de `orchestrator_service/services/telegram_bot.py` — no requiere nuevo servicio ni nuevas dependencias.

## Key Decisions
- **Whisper directo** — Enviar bytes OGG/OPUS crudos a la API de Whisper (acepta .ogg nativo, no necesita conversión ffmpeg)
- **Vision inline** — Para imágenes de Telegram, usar base64 inline en GPT-4o (no guardar en disco)
- **Buffer Redis** — Mismo patrón que WhatsApp: Redis list + sliding TTL timer (12s texto, 20s media)
- **Caption como contexto** — Si una foto/doc viene con caption, se concatena: `[IMAGEN: descripción_vision]\nCaption del usuario: {caption_text}`
- **Clasificación automática** — Imágenes pasan por `classify_message()` para detectar comprobantes de pago
- **Límite de archivo** — 20MB (límite de Telegram Bot API standard) para audio, 5MB para PDFs en vision

## Risks
| Risk | Mitigation |
|------|------------|
| Latencia Whisper (2-5s) | Typing indicator mientras transcribe |
| Latencia Vision (3-8s) | Typing indicator + buffer acumula media para procesar junto |
| Audio largo > 20MB | Telegram lo limita a 20MB, Whisper acepta hasta 25MB — sin problema |
| PDF > 5MB | Responder "El archivo es muy grande, máximo 5MB" |
| Buffer se pierde si Redis se reinicia | Timer es solo debounce, mensajes están en la DB para recovery |
| Múltiples fotos rápidas | Buffer las acumula y las procesa como batch |
