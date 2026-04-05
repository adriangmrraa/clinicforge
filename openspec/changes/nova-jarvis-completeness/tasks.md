# Tasks: Nova Jarvis Completeness

## Phase 1: Infrastructure (Batch 1)

- [ ] **T1.1** Add `send_proactive_message(tenant_id, html_text)` to `telegram_notifier.py` — uses `_bots[tenant_id].bot.send_message()` for each authorized user, parse_mode=HTML, fire-and-forget
- [ ] **T1.2** OpenAI client singleton in `telegram_bot.py` — module-level `_openai_client`, lazy init, replace all `openai.AsyncOpenAI()` instantiations
- [ ] **T1.3** Add `nova_tools_for_page(page)` in `nova_tools.py` — filters NOVA_TOOLS_SCHEMA by page relevance, removes navigation tools for Telegram

## Phase 2: Token Tracking (Batch 2)

- [ ] **T2.1** Track Telegram Nova tokens — add `track_service_usage()` after each `client.chat.completions.create()` in `telegram_bot.py` (3 call sites in tool loop)
- [ ] **T2.2** Track Whisper/Vision tokens — add tracking after `_transcribe_audio`, `_analyze_image_bytes`, `_analyze_pdf_bytes` in `telegram_bot.py`
- [ ] **T2.3** Track Digital Records tokens — add tracking after `generate_narrative()` in `digital_records_service.py`
- [ ] **T2.4** Update `get_service_breakdown()` in `token_tracker.py` — add telegram_nova, telegram_whisper, telegram_vision, digital_records categories

## Phase 3: Patient Memory Tools (Batch 3)

- [ ] **T3.1** Add `ver_memorias_paciente` tool schema + implementation — patient_id → phone → get_memories() → formatted list
- [ ] **T3.2** Add `agregar_memoria_paciente` tool schema + implementation — patient_id → phone → add_manual_memory()
- [ ] **T3.3** Wire both in execute_nova_tool dispatcher
- [ ] **T3.4** Hook `extract_and_store_memories()` in `_process_and_respond` of telegram_bot.py — fire-and-forget after each conversation
- [ ] **T3.5** Add patient memory instructions to `nova_prompt.py` — "cuando notés algo importante → agregar_memoria_paciente"

## Phase 4: Proactive Jobs (Batch 4)

- [ ] **T4.1** Create `jobs/nova_morning.py` — daily summary job, queries agenda + cobros + insights, formats HTML, sends via `send_proactive_message()`
- [ ] **T4.2** Create `jobs/smart_alerts.py` — periodic alert evaluator (turnos sin confirmar, morosidad, no-shows), Redis dedup, sends via `send_proactive_message()`
- [ ] **T4.3** Register both jobs in `main.py` startup — morning at 7:30 AM, alerts every 4h
- [ ] **T4.4** Add configurable hour per tenant — `system_config` key `NOVA_MORNING_HOUR`, default 7:30

## Phase 5: Page Context + Speed (Batch 5)

- [ ] **T5.1** Frontend: send `context_summary` + `appointment_id` in `NovaWidget.tsx` POST /admin/nova/session
- [ ] **T5.2** Backend: extend `SessionRequest` in `nova_routes.py` — add `appointment_id`, fetch appointment data, inject into prompt
- [ ] **T5.3** Backend: inject patient_memories into Realtime session prompt when patient_id is known
- [ ] **T5.4** System prompt cache — `functools.lru_cache` or dict with 5min TTL on `build_nova_system_prompt()`
