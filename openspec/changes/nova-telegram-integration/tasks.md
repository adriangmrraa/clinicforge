# Tasks: Nova Telegram Integration

## Phase 1: Backend Foundation (Batch 1)

- [ ] **T1.1** Migración Alembic 021 — tabla `telegram_authorized_users`
- [ ] **T1.2** Agregar constantes `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_WEBHOOK_ACCESS_TOKEN` en `core/credentials.py`
- [ ] **T1.3** Endpoints CRUD para usuarios autorizados: GET/POST/PUT/DELETE `/admin/telegram/authorized-users`
- [ ] **T1.4** Endpoint GET/POST `/admin/integrations/telegram/config` (bot token, webhook setup)
- [ ] **T1.5** Endpoint POST `/admin/nova/telegram-message` (procesamiento de mensajes con Chat Completions + tool loop)
- [ ] **T1.6** Endpoint GET `/admin/telegram/verify-user/{chat_id}` (validación rápida de chat_id autorizado)
- [ ] **T1.7** Helper `nova_tools_for_chat_completions()` — convertir schemas Realtime → Chat Completions format
- [ ] **T1.8** Agregar `page=telegram` al system prompt de Nova con reglas de modo texto

## Phase 2: Telegram Microservice (Batch 2)

- [ ] **T2.1** Crear `telegram_service/` con estructura: main.py, config.py, message_handler.py, response_formatter.py
- [ ] **T2.2** FastAPI app con webhook endpoint POST `/telegram/webhook/{access_token}`
- [ ] **T2.3** Bot lifecycle: startup registra webhook, shutdown cleanup
- [ ] **T2.4** Message handler: validar chat_id → typing indicator → call orchestrator → send response
- [ ] **T2.5** Response formatter: chunking 4096 chars + MarkdownV2 escape
- [ ] **T2.6** Comandos /start, /help, /status
- [ ] **T2.7** Dockerfile + requirements.txt (python-telegram-bot, fastapi, uvicorn, httpx)
- [ ] **T2.8** Agregar servicio a docker-compose.yml

## Phase 3: Frontend (Batch 3)

- [ ] **T3.1** Componente `TelegramConfigTab.tsx` — sección bot config (token + connect/disconnect)
- [ ] **T3.2** Sección usuarios autorizados — tabla + CRUD modal
- [ ] **T3.3** Integrar tab en ConfigView.tsx
- [ ] **T3.4** i18n: claves telegram.* en es.json, en.json, fr.json

## Phase 4: Polish & Security (Batch 4)

- [ ] **T4.1** Audit logging: registrar cada interacción Telegram en tabla de logs
- [ ] **T4.2** Rate limiting: queue de mensajes con backoff en 429
- [ ] **T4.3** Error handling: timeouts, bot desconectado, orchestrator caído
- [ ] **T4.4** Instrucciones en UI: "Cómo obtener tu Telegram Chat ID"
