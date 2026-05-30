# Proposal: Nova Telegram Integration

## Intent
Permitir al CEO y equipo autorizado interactuar con Nova (64+ tools) via Telegram bot, con la misma capacidad que tiene por voz/web. IDs de Telegram autorizados gestionados desde una nueva sección en Settings, credenciales encriptadas con Fernet.

## Scope

### In Scope
1. **Nuevo microservicio `telegram_service/`** — FastAPI + python-telegram-bot, webhook mode
2. **Integración con Nova tools** — llamadas directas a `execute_nova_tool()` via HTTP al orchestrator
3. **Gestión de IDs autorizados** — tabla `telegram_authorized_users` con roles y encriptación
4. **UI de configuración** — nueva tab "Telegram" en ConfigView con: bot token, webhook URL, IDs autorizados
5. **Endpoints de configuración** — CRUD para bot token y usuarios autorizados
6. **Migración Alembic** — tabla `telegram_authorized_users`
7. **Docker Compose** — nuevo servicio `telegram_service`
8. **Seguridad** — Fernet encryption para bot token, secret_token en webhook, whitelist de chat_ids
9. **Chunking de respuestas** — split en mensajes de 4096 chars con MarkdownV2

### Out of Scope
- Envío de archivos/fotos desde Telegram a Nova
- Telegram groups (solo chats privados 1-on-1)
- Telegram inline mode
- Telegram payments API
- Bot commands menu (futuro)

## Approach
Microservicio separado siguiendo el patrón de `whatsapp_service/`:
1. Telegram webhook → `telegram_service` (FastAPI port 8003)
2. `telegram_service` valida chat_id contra IDs autorizados (query al orchestrator)
3. Mensaje de texto → POST al orchestrator `/admin/nova/telegram-message`
4. Orchestrator procesa con OpenAI (chat completions, no realtime) → tool calls → `execute_nova_tool()`
5. Response → `telegram_service` → `sendMessage` al chat de Telegram
6. Respuestas largas se splitean en chunks de 4096 chars

## Key Decisions
- **Un bot por tenant** (mismo patrón que YCloud/WhatsApp)
- **OpenAI Chat Completions** (no Realtime) para procesar texto — más económico y adecuado para text-only
- **Webhook mode** (no polling) — más eficiente, compatible con EasyPanel/Docker
- **Tabla dedicada** para IDs autorizados (no JSON en credentials) — permite CRUD individual y roles por usuario
- **MarkdownV2** para formateo de respuestas en Telegram

## Risks
| Risk | Mitigation |
|------|------------|
| Rate limits Telegram (1 msg/seg) | Queue + retry con backoff |
| Respuestas >4096 chars | Chunking inteligente (no cortar mid-word) |
| Bot token expuesto | Fernet encryption + secret_token en webhook |
| Latencia OpenAI + tools | Mensaje "Procesando..." mientras ejecuta |
| Multi-tenant routing | Webhook URL con access_token único por tenant |
