# Design: Nova Telegram Integration

## Architecture

```
Telegram Cloud → webhook HTTPS → telegram_service (FastAPI :8003)
                                        ↓
                                  Validate chat_id
                                  (GET /admin/telegram/verify-user)
                                        ↓
                                  POST /admin/nova/telegram-message
                                        ↓
                                  Orchestrator (FastAPI :8000)
                                        ↓
                                  OpenAI Chat Completions
                                  + execute_nova_tool() loop
                                        ↓
                                  Response text
                                        ↓
                                  telegram_service
                                        ↓
                                  bot.sendMessage (chunked)
                                        ↓
                                  Telegram Cloud → User
```

## Component Design

### 1. telegram_service/ (Nuevo microservicio)

```
telegram_service/
├── main.py              # FastAPI app + webhook endpoint + bot lifecycle
├── config.py            # Environment config (ORCHESTRATOR_URL, etc)
├── message_handler.py   # Process incoming messages, call orchestrator
├── response_formatter.py # MarkdownV2 formatting + chunking
├── requirements.txt     # python-telegram-bot, fastapi, uvicorn, httpx
└── Dockerfile
```

**main.py — Core flow:**
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import httpx

# Bot init (per-tenant, lazy loaded)
bots: Dict[str, Application] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load configured tenants on startup
    await load_tenant_bots()
    yield
    # Cleanup
    for bot in bots.values():
        await bot.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/telegram/webhook/{access_token}")
async def webhook(access_token: str, request: Request):
    # 1. Resolve tenant from access_token
    tenant_id = await resolve_tenant(access_token)
    if not tenant_id:
        return Response(status_code=403)

    # 2. Validate secret token header
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not validate_secret(tenant_id, secret):
        return Response(status_code=403)

    # 3. Parse update
    bot_app = bots.get(str(tenant_id))
    update = Update.de_json(await request.json(), bot_app.bot)

    # 4. Process through handlers
    await bot_app.process_update(update)
    return Response(status_code=200)
```

**message_handler.py — Orchestrator call:**
```python
async def handle_message(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    text = update.message.text
    tenant_id = context.bot_data["tenant_id"]

    # 1. Verify authorized user
    user_info = await verify_user(tenant_id, chat_id)
    if not user_info:
        await update.message.reply_text("No tenés autorización para usar Nova.")
        return

    # 2. Show typing indicator
    await update.effective_chat.send_action("typing")

    # 3. Call orchestrator
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{ORCHESTRATOR_URL}/admin/nova/telegram-message",
            json={
                "chat_id": chat_id,
                "text": text,
                "tenant_id": tenant_id,
                "user_role": user_info["user_role"],
                "user_id": str(chat_id),
                "display_name": user_info["display_name"],
            },
            headers={"X-Admin-Token": ADMIN_TOKEN}
        )

    # 4. Format and send response
    result = response.json()
    chunks = chunk_message(result["response_text"], max_len=4096)
    for chunk in chunks:
        await update.message.reply_text(
            chunk,
            parse_mode="MarkdownV2"
        )
```

### 2. Orchestrator — Nova Telegram Endpoint

**Nuevo endpoint en admin_routes.py:**

```python
@router.post("/nova/telegram-message")
async def nova_telegram_message(request: Request, ...):
    body = await request.json()

    # 1. Build Nova system prompt (same as WebSocket handler)
    system_prompt = build_nova_system_prompt(
        tenant_id=body["tenant_id"],
        user_role=body["user_role"],
        page="telegram",  # New page context
    )

    # 2. Call OpenAI Chat Completions with tools
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": body["text"]},
    ]

    # 3. Tool calling loop (max 10 rounds)
    tools_called = []
    for _ in range(10):
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=nova_tools_for_chat_completions(),
            tool_choice="auto",
        )

        choice = response.choices[0]
        if choice.finish_reason == "stop":
            break

        if choice.finish_reason == "tool_calls":
            for tool_call in choice.message.tool_calls:
                result = await execute_nova_tool(
                    tool_call.function.name,
                    json.loads(tool_call.function.arguments),
                    body["tenant_id"],
                    body["user_role"],
                    body.get("user_id", ""),
                )
                tools_called.append(tool_call.function.name)
                messages.append(choice.message)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

    return {
        "response_text": choice.message.content,
        "tools_called": tools_called,
    }
```

**Conversión de tool schemas:**
Los NOVA_TOOLS_SCHEMA usan formato Realtime (`{"type": "function", "name": ...}`).
Chat Completions necesita formato wrapped (`{"type": "function", "function": {"name": ...}}`).
Crear helper `nova_tools_for_chat_completions()` que convierte.

### 3. Alembic Migration 021

```sql
CREATE TABLE telegram_authorized_users (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    telegram_chat_id TEXT NOT NULL,  -- Fernet encrypted
    display_name VARCHAR(255) NOT NULL,
    user_role VARCHAR(50) NOT NULL DEFAULT 'ceo',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_telegram_auth_tenant_chatid
    ON telegram_authorized_users (tenant_id, telegram_chat_id);
CREATE INDEX idx_telegram_auth_active
    ON telegram_authorized_users (tenant_id, is_active);
```

### 4. Credentials Constants

```python
# core/credentials.py
TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
TELEGRAM_WEBHOOK_SECRET = "TELEGRAM_WEBHOOK_SECRET"
TELEGRAM_WEBHOOK_ACCESS_TOKEN = "TELEGRAM_WEBHOOK_ACCESS_TOKEN"
```

### 5. Response Formatter

```python
def chunk_message(text: str, max_len: int = 4096) -> List[str]:
    """Split long messages without breaking words or markdown."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Find last newline or space before limit
        split_at = text.rfind('\n', 0, max_len)
        if split_at == -1:
            split_at = text.rfind(' ', 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    return chunks

def escape_markdown_v2(text: str) -> str:
    """Escape special chars for Telegram MarkdownV2."""
    special = '_*[]()~`>#+-=|{}.!'
    for char in special:
        text = text.replace(char, f'\\{char}')
    return text
```

### 6. Frontend — TelegramConfigTab Component

```
TelegramConfigTab.tsx
├── Bot Configuration Section
│   ├── Token input (password) + Connect/Disconnect button
│   ├── Status badge (connected/disconnected)
│   ├── Bot username display
│   └── Webhook URL (read-only + copy button)
├── Authorized Users Section
│   ├── Table: name | chat_id (masked) | role | active toggle | delete
│   ├── "+ Agregar usuario" button → modal
│   └── Modal: name + chat_id + role dropdown
└── Instructions Section
    └── How to get your Telegram chat ID (link to @userinfobot)
```

## Security Design

1. **Bot token** → Fernet encrypted in `credentials` table
2. **Webhook secret** → Random 64-char hex, stored encrypted, validated on every request
3. **Access token in URL** → Random UUID per tenant, used for tenant routing
4. **Chat ID whitelist** → Only authorized IDs can interact, checked before processing
5. **Role-based** → Each authorized user has a role (ceo/secretary/professional)
6. **Audit log** → Every Telegram interaction logged with chat_id, command, response

## Nova page=telegram Mode

Agregar al system prompt de Nova:

```
page=telegram → MODO TELEGRAM:
  Contexto: comunicación por texto (no voz). Respuestas concisas.
  Formatear con markdown: **bold** para títulos, `monospace` para datos, listas con •
  Máximo ~3000 chars por respuesta (dejar margen para el split).
  NO usar emojis excesivos. 1-2 por respuesta máximo.
  Priorizar datos concretos sobre explicaciones largas.
  "Hola" / primer mensaje → resumen_semana automáticamente (como en dashboard).
```
