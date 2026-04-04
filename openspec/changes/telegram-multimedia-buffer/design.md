# Design: Telegram Multimedia + Intelligent Buffer

## Architecture

```
Telegram User
  ├── Texto → buffer → _process_with_nova(text)
  ├── Audio → download bytes → Whisper API → buffer → _process_with_nova("[AUDIO: transcripción]")
  ├── Foto  → download bytes → GPT-4o vision → classify → buffer → _process_with_nova("[IMAGEN: desc]")
  └── PDF   → download bytes → GPT-4o vision → buffer → _process_with_nova("[DOCUMENTO: desc]")
                                                  ↓
                                          Redis Buffer
                                    (12s texto / 20s media)
                                          ↓ (silencio)
                                    Drain all messages
                                          ↓
                                  _process_with_nova(combined_input)
                                          ↓
                                  execute_nova_tool() × N
                                          ↓
                                  Chunked response → Telegram
```

## Implementation in telegram_bot.py

### New handlers to register
```python
app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, _handle_voice))
app.add_handler(MessageHandler(filters.PHOTO, _handle_photo))
app.add_handler(MessageHandler(filters.Document.ALL, _handle_document))
```

### Media Processing Helpers

```python
async def _transcribe_audio(audio_bytes: bytes, filename: str) -> str:
    """Direct call to OpenAI Whisper API with raw bytes."""
    client = openai.AsyncOpenAI()
    # Use in-memory BytesIO — no disk write needed
    import io
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename
    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
    )
    return transcript.text

async def _analyze_image_bytes(image_bytes: bytes, mime_type: str, caption: str) -> dict:
    """Analyze image with GPT-4o vision. Returns {description, is_payment, is_medical}."""
    b64 = base64.b64encode(image_bytes).decode()
    client = openai.AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": VISION_PROMPT + (f"\nCaption: {caption}" if caption else "")},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
            ],
        }],
        max_tokens=500,
    )
    description = response.choices[0].message.content
    # Classify
    from services.image_classifier import classify_message
    classification = classify_message(caption or "", None, description)
    return {
        "description": description,
        "is_payment": classification.get("is_payment", False),
        "is_medical": classification.get("is_medical", False),
    }

async def _analyze_pdf_bytes(pdf_bytes: bytes, filename: str) -> str:
    """Analyze PDF with GPT-4o vision."""
    b64 = base64.b64encode(pdf_bytes).decode()
    client = openai.AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": PDF_ANALYSIS_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:application/pdf;base64,{b64}"}},
            ],
        }],
        max_tokens=500,
    )
    return response.choices[0].message.content
```

### Handler Pattern

```python
async def _handle_voice(update, context):
    # 1. Auth check
    # 2. Download: file = await update.message.voice.get_file()
    #    audio_bytes = await file.download_as_bytearray()
    # 3. Typing indicator
    # 4. Transcribe: text = await _transcribe_audio(bytes(audio_bytes), "voice.ogg")
    # 5. Enrich: enriched = f'[AUDIO ({update.message.voice.duration}s): "{text}"]'
    # 6. Buffer or process: _enqueue_to_buffer(tenant_id, chat_id, enriched, is_media=True)

async def _handle_photo(update, context):
    # 1. Auth check
    # 2. Download largest: photo = update.message.photo[-1]
    #    file = await photo.get_file()
    #    img_bytes = await file.download_as_bytearray()
    # 3. Typing indicator
    # 4. Analyze: result = await _analyze_image_bytes(bytes(img_bytes), "image/jpeg", caption)
    # 5. Enrich: enriched = f'[IMAGEN: "{result["description"]}"]'
    #    If result["is_payment"]: enriched += "\nPROBABLE COMPROBANTE DE PAGO"
    # 6. Buffer or process

async def _handle_document(update, context):
    # 1. Auth check
    # 2. Validate mime_type (only pdf, images)
    # 3. Validate size (< 5MB for pdf)
    # 4. Download and analyze
    # 5. Enrich and buffer
```

### Buffer System (Redis)

```python
BUFFER_TTL_TEXT = 12   # seconds
BUFFER_TTL_MEDIA = 20  # seconds
MIN_REMAINING_TTL = 4  # seconds

async def _enqueue_to_buffer(tenant_id, chat_id, content, is_media, update):
    """Add message to Redis buffer and schedule consumer if not running."""
    redis = get_redis()
    buffer_key = f"tg_buffer:{tenant_id}:{chat_id}"
    timer_key = f"tg_timer:{tenant_id}:{chat_id}"
    lock_key = f"tg_lock:{tenant_id}:{chat_id}"

    ttl = BUFFER_TTL_MEDIA if is_media else BUFFER_TTL_TEXT
    redis.rpush(buffer_key, content)

    current_ttl = redis.ttl(timer_key)
    if current_ttl < MIN_REMAINING_TTL:
        redis.setex(timer_key, ttl, "1")
    elif current_ttl < ttl:
        redis.setex(timer_key, ttl, "1")

    if not redis.exists(lock_key):
        redis.setex(lock_key, 60, "1")  # 60s max lock
        asyncio.create_task(_telegram_buffer_consumer(tenant_id, chat_id, update, context))

async def _telegram_buffer_consumer(tenant_id, chat_id, update, context):
    """Wait for silence, then drain buffer and process."""
    redis = get_redis()
    timer_key = f"tg_timer:{tenant_id}:{chat_id}"
    buffer_key = f"tg_buffer:{tenant_id}:{chat_id}"
    lock_key = f"tg_lock:{tenant_id}:{chat_id}"

    try:
        # Debounce: wait until timer expires
        while True:
            ttl = redis.ttl(timer_key)
            if ttl <= 0:
                break
            await asyncio.sleep(min(ttl, 2))

        # Drain buffer
        messages = redis.lrange(buffer_key, 0, -1)
        redis.delete(buffer_key)

        if not messages:
            return

        combined = "\n".join(m.decode() if isinstance(m, bytes) else m for m in messages)

        # Process with Nova
        user_info = await _verify_user(tenant_id, chat_id)
        if not user_info:
            return

        response_text, tools_called = await _process_with_nova(
            text=combined,
            tenant_id=tenant_id,
            user_role=user_info["user_role"],
            user_id=str(chat_id),
            display_name=user_info["display_name"],
        )

        # Send response
        chunks = chunk_message(response_text or "Sin respuesta")
        for i, chunk in enumerate(chunks):
            is_last = (i == len(chunks) - 1)
            await update.effective_chat.send_message(
                chunk,
                reply_markup=QUICK_ACTIONS if is_last else None,
            )
    finally:
        redis.delete(lock_key)
```

### Typing Indicator Loop

```python
async def _typing_loop(chat, cancel_event: asyncio.Event):
    """Send typing action every 4s until cancelled."""
    while not cancel_event.is_set():
        try:
            await chat.send_action("typing")
        except Exception:
            break
        try:
            await asyncio.wait_for(cancel_event.wait(), timeout=4)
            break
        except asyncio.TimeoutError:
            continue
```

## Vision Prompts

```python
VISION_PROMPT = """Describe esta imagen en el contexto de una clínica dental.
Si es un comprobante de pago/transferencia bancaria: extraé monto, titular, CBU/alias, fecha.
Si es un documento clínico (radiografía, foto intraoral): describí hallazgos clínicos.
Si es otro tipo de imagen: describí brevemente.
Respondé en español, máximo 3 oraciones."""

PDF_ANALYSIS_PROMPT = """Analizá este documento PDF en el contexto de una clínica dental.
Extraé la información más relevante: tipo de documento, datos del paciente si los hay,
montos, diagnósticos, tratamientos mencionados.
Respondé en español, máximo 5 oraciones."""
```

## File Structure

No se crean archivos nuevos. Todo va en `orchestrator_service/services/telegram_bot.py`:

```
telegram_bot.py (existing)
├── [NEW] _transcribe_audio()           # Whisper helper
├── [NEW] _analyze_image_bytes()        # Vision helper
├── [NEW] _analyze_pdf_bytes()          # PDF analysis helper
├── [NEW] _handle_voice()               # Voice message handler
├── [NEW] _handle_photo()               # Photo handler
├── [NEW] _handle_document()            # Document handler
├── [NEW] _enqueue_to_buffer()          # Redis buffer enqueue
├── [NEW] _telegram_buffer_consumer()   # Redis buffer drain + process
├── [NEW] _typing_loop()                # Continuous typing indicator
├── [MODIFIED] _handle_text()           # Now uses buffer instead of direct process
├── [MODIFIED] _start_bot_polling()     # Register new handlers
└── (existing functions unchanged)
```

## Dependencies
- `python-telegram-bot>=22.0` — already in requirements.txt
- `openai>=1.0.0` — already in requirements.txt
- `redis` — already in requirements.txt
- No new dependencies needed
