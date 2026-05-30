# Spec: Nova Telegram Integration

## S1: Telegram Service (Microservicio)

### Requirements
- FastAPI microservice en port 8003
- python-telegram-bot v22+ como dependencia
- Webhook endpoint POST `/telegram/webhook/{access_token}`
- Validar `X-Telegram-Bot-Api-Secret-Token` header
- Validar `chat_id` contra lista de autorizados (query al orchestrator)
- Enviar mensaje de texto al orchestrator para procesamiento
- Recibir response y enviar al chat de Telegram
- Chunking de respuestas >4096 chars
- Formateo MarkdownV2 para responses
- Health check GET `/health`
- Startup: registrar webhook en Telegram API via `setWebhook`

### Scenarios
```
DADO que un usuario autorizado envía "cuántos turnos hay hoy" por Telegram
CUANDO el webhook recibe el mensaje
ENTONCES valida chat_id → envía al orchestrator → recibe respuesta → envía al chat
Y la respuesta incluye los datos reales de la agenda

DADO que un chat_id NO autorizado envía un mensaje
CUANDO el webhook recibe el mensaje
ENTONCES responde "No tenés autorización para usar Nova. Contactá al administrador."
Y NO procesa el mensaje ni llama al orchestrator

DADO que la respuesta de Nova tiene 8000 caracteres
CUANDO se envía al chat de Telegram
ENTONCES se divide en 2 mensajes (4096 + 3904) sin cortar palabras

DADO que el orchestrator no responde en 30 segundos
CUANDO hay timeout
ENTONCES envía "Hubo un error procesando tu consulta. Intentá de nuevo."
```

## S2: Orchestrator — Endpoint Nova Telegram

### Requirements
- Nuevo endpoint POST `/admin/nova/telegram-message`
- Recibe: `{ chat_id, text, tenant_id, user_role, user_id, display_name }`
- Usa OpenAI Chat Completions (gpt-4o-mini) con el system prompt de Nova
- Incluye NOVA_TOOLS_SCHEMA como tools del chat completion
- Ejecuta tool calls via `execute_nova_tool()`
- Soporta multi-turn tool calling (hasta 10 rounds)
- Retorna: `{ response_text, tools_called: [...] }`
- Logging de cada interacción para auditoría

### Scenarios
```
DADO que llega un mensaje "cobrale la cuota a García"
CUANDO el orchestrator procesa con OpenAI
ENTONCES ejecuta: buscar_paciente → treatment_plans → registrar_pago
Y retorna el resultado final como texto

DADO que el tool call falla
CUANDO execute_nova_tool retorna error
ENTONCES incluye el error en el contexto y deja que OpenAI genere una respuesta amigable

DADO que se necesitan 5 tool calls encadenados
CUANDO OpenAI pide tools iterativamente
ENTONCES el loop ejecuta hasta 10 rounds máximo
Y retorna el resultado consolidado
```

## S3: Base de Datos — Tabla telegram_authorized_users

### Requirements
- Migración Alembic (021_telegram_authorized_users)
- Tabla: `telegram_authorized_users`
  - `id` SERIAL PRIMARY KEY
  - `tenant_id` INTEGER FK tenants(id) ON DELETE CASCADE
  - `telegram_chat_id` BIGINT NOT NULL (encrypted con Fernet)
  - `display_name` VARCHAR(255) NOT NULL
  - `user_role` VARCHAR(50) NOT NULL DEFAULT 'ceo' (ceo/secretary/professional)
  - `is_active` BOOLEAN DEFAULT true
  - `created_at` TIMESTAMPTZ DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ DEFAULT NOW()
  - UNIQUE(tenant_id, telegram_chat_id)
- Index: `idx_telegram_auth_tenant` ON (tenant_id, is_active)

### Scenarios
```
DADO que el CEO agrega un Telegram ID desde Settings
CUANDO se guarda en la tabla
ENTONCES el chat_id se encripta con Fernet antes de almacenar

DADO que se consulta si un chat_id está autorizado
CUANDO el telegram_service hace la query
ENTONCES se desencriptan todos los chat_ids del tenant y se compara
```

## S4: Credenciales — Bot Token

### Requirements
- Constante `TELEGRAM_BOT_TOKEN` en `core/credentials.py`
- Constante `TELEGRAM_WEBHOOK_SECRET` en `core/credentials.py`
- Almacenado en tabla `credentials` (encrypted, per-tenant)
- Endpoints GET/POST `/admin/integrations/telegram/config`
- GET retorna: `{ configured: bool, webhook_url: string, bot_username: string }`
- POST recibe: `{ bot_token: string }` → encripta y guarda → registra webhook

### Scenarios
```
DADO que el CEO configura el bot token desde Settings
CUANDO guarda el token
ENTONCES se encripta con Fernet y se almacena en credentials
Y se genera un webhook_secret aleatorio
Y se llama a setWebhook de Telegram API con la URL y secret

DADO que el CEO quiere ver si Telegram está configurado
CUANDO abre la tab Telegram en Settings
ENTONCES ve: estado (conectado/desconectado), username del bot, URL del webhook
Y NO ve el token en texto plano
```

## S5: Frontend — Tab Telegram en Settings

### Requirements
- Nueva tab "Telegram" en ConfigView.tsx
- Sección 1: Configuración del Bot
  - Input para Bot Token (password type, con toggle visibility)
  - Botón "Conectar Bot" / "Desconectar"
  - Estado: conectado/desconectado con username del bot
  - URL del webhook (read-only, copiable)
- Sección 2: Usuarios Autorizados
  - Tabla con: nombre, Telegram ID (parcialmente oculto), rol, estado activo
  - Botón "+ Agregar usuario"
  - Modal: nombre, Telegram chat ID, rol (dropdown: CEO/Secretaria/Profesional)
  - Toggle activo/inactivo por usuario
  - Botón eliminar por usuario
- i18n: claves en es.json, en.json, fr.json

### Scenarios
```
DADO que el CEO abre Settings → Telegram
CUANDO no hay bot configurado
ENTONCES ve input para token + botón "Conectar Bot"
Y la sección de usuarios está deshabilitada

DADO que el CEO conecta un bot
CUANDO pega el token y da "Conectar"
ENTONCES se guarda encrypted, se registra webhook
Y aparece: "Bot @nombre_bot conectado" con badge verde
Y se habilita la sección de usuarios

DADO que el CEO agrega un usuario autorizado
CUANDO completa nombre + chat ID + rol
ENTONCES aparece en la tabla con el ID parcialmente oculto (123***789)
Y ese usuario puede empezar a usar Nova por Telegram inmediatamente
```

## S6: Docker Compose

### Requirements
- Nuevo servicio `telegram_service` en docker-compose.yml
- Image: build desde `./telegram_service`
- Port: 8003 (internal)
- Environment: `ORCHESTRATOR_URL`, `CREDENTIALS_FERNET_KEY`
- Depends on: orchestrator_service
- Resources: 256M RAM, 0.25 CPU
- Health check: GET /health cada 30s

## S7: Interacción UX en Telegram

### Requirements
- Comando `/start` → mensaje de bienvenida con instrucciones
- Comando `/help` → lista de acciones disponibles
- Comando `/status` → resumen rápido (agenda hoy + pendientes)
- Mensajes de texto libres → procesados por Nova
- Indicador "typing..." mientras procesa
- Respuestas formateadas con MarkdownV2 (bold, italic, monospace para datos)
- Inline keyboard para acciones rápidas después de cada respuesta
- Emoji contextual en respuestas (pero no excesivo)
