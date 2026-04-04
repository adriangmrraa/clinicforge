# Tasks: Telegram Multimedia + Intelligent Buffer

## Phase 1: Media Processing Helpers (Batch 1)

- [ ] **T1.1** Helper `_transcribe_audio(audio_bytes, filename)` — llamada directa a OpenAI Whisper API con BytesIO, retorna texto
- [ ] **T1.2** Helper `_analyze_image_bytes(image_bytes, mime_type, caption)` — GPT-4o vision base64 + classify_message(), retorna {description, is_payment, is_medical}
- [ ] **T1.3** Helper `_analyze_pdf_bytes(pdf_bytes, filename)` — GPT-4o vision base64 para PDFs, retorna descripción
- [ ] **T1.4** Helper `_typing_loop(chat, cancel_event)` — typing indicator cada 4s hasta cancelar
- [ ] **T1.5** Constantes `VISION_PROMPT`, `PDF_ANALYSIS_PROMPT` — prompts contextualizados para clínica dental

## Phase 2: Message Handlers (Batch 2)

- [ ] **T2.1** `_handle_voice(update, context)` — auth → download bytes → transcribe → enrich con `[AUDIO (Ns): "texto"]` → buffer/process
- [ ] **T2.2** `_handle_photo(update, context)` — auth → download largest → analyze → classify → enrich con `[IMAGEN: "desc"]` + comprobante context → buffer/process
- [ ] **T2.3** `_handle_document(update, context)` — auth → validate mime/size → download → analyze → enrich con `[DOCUMENTO (name): "desc"]` → buffer/process
- [ ] **T2.4** Registrar los 3 handlers en `_start_bot_polling()`: filters.VOICE|AUDIO, filters.PHOTO, filters.Document.ALL

## Phase 3: Intelligent Buffer (Batch 3)

- [ ] **T3.1** `_enqueue_to_buffer(tenant_id, chat_id, content, is_media, update, context)` — Redis RPUSH + sliding TTL timer + spawn consumer
- [ ] **T3.2** `_telegram_buffer_consumer(tenant_id, chat_id, update, context)` — debounce loop → drain → process combined → send response
- [ ] **T3.3** Modificar `_handle_text()` para usar buffer en vez de procesamiento directo
- [ ] **T3.4** Modificar `_handle_voice/photo/document` para que la parte de media processing sea síncrona (pre-buffer) y el procesamiento con Nova sea via buffer

## Phase 4: Payment Detection + Polish (Batch 4)

- [ ] **T4.1** Detección de comprobante: si `is_payment=true` → buscar paciente con pago pendiente → inyectar "PROBABLE COMPROBANTE DE PAGO — usar verify_payment_receipt"
- [ ] **T4.2** Caption support: fotos/docs con caption concatenan caption al enriched text
- [ ] **T4.3** Error handling robusto: fallback a procesamiento directo si Redis falla, retry en Whisper timeout, size validation
- [ ] **T4.4** Logging: cada interacción multimedia logueada en automation_logs con tipo de media y resultado
