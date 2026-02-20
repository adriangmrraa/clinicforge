# API Reference - Dentalogic

Referencia de los endpoints del **Orchestrator** (FastAPI). Base URL típica: `http://localhost:8000` en desarrollo o la URL del servicio en producción.

## Documentación interactiva (OpenAPI / Swagger)

En la misma base del Orchestrator están disponibles:

| URL | Descripción |
|-----|-------------|
| **[/docs](http://localhost:8000/docs)** | **Swagger UI**: contrato completo, agrupado por tags (Auth, Pacientes, Turnos, Chat, etc.). Permite probar endpoints desde el navegador; en *Authorize* se pueden configurar **Bearer** (JWT) y **X-Admin-Token**. |
| **[/redoc](http://localhost:8000/redoc)** | **ReDoc**: documentación en formato lectura. |
| **[/openapi.json](http://localhost:8000/openapi.json)** | Esquema OpenAPI 3.x en JSON para importar en Postman, Insomnia o herramientas de generación de clientes. |

Sustituye `localhost:8000` por la URL del Orchestrator en tu entorno (ej. en producción: `https://dentalogic-orchestrator.ugwrjq.easypanel.host`).

---

## Índice

1. [Autenticación y headers](#autenticación-y-headers)
2. [Auth (login, registro, perfil)](#auth-público-y-registro)
3. [Configuración de clínica](#configuración-de-clínica-idioma-ui)
4. [Usuarios y aprobaciones](#usuarios-y-aprobaciones)
5. [Sedes (Tenants)](#sedes-tenants)
6. [Pacientes](#pacientes)
7. [Turnos (Appointments)](#turnos-appointments)
8. [Chat (multi-tenant)](#chat-multi-tenant)
9. [Chat omnicanal (Chatwoot)](#chat-omnicanal-chatwoot)
10. [Profesionales](#profesionales)
11. [Calendario y bloques](#calendario-y-bloques)
12. [Tratamientos](#tratamientos-services)
13. [Estadísticas y analíticas](#analítica-y-estadísticas)
14. [Marketing Hub (Meta Ads)](#marketing-hub-meta-ads)
15. [Automatizaciones y Handoffs](#automatizaciones-y-handoffs)
16. [Otros (health, chat IA)](#otros)

---

## Autenticación y headers

Todas las rutas bajo **`/admin/*`** exigen:

| Header | Obligatorio | Descripción |
|--------|-------------|-------------|
| **`Authorization`** | Sí | `Bearer <JWT>`. El JWT se obtiene con `POST /auth/login`. |
| **`X-Admin-Token`** | Sí (si está configurado en servidor) | Token estático de infraestructura. El frontend lo inyecta desde `VITE_ADMIN_TOKEN`. Sin este header, el backend responde **401** aunque el JWT sea válido. |

Rutas **públicas** (sin estos headers): `GET /auth/clinics`, `POST /auth/register`, `POST /auth/login`, `GET /health`.

---

## Auth (público y registro)

### Listar clínicas (público)
`GET /auth/clinics`

**Sin autenticación.** Devuelve el listado de clínicas para el selector de registro.

**Response:**
```json
[
  { "id": 1, "clinic_name": "Clínica Centro" },
  { "id": 2, "clinic_name": "Sede Norte" }
]
```

### Registro
`POST /auth/register`

Crea usuario con `status = 'pending'`. Para roles `professional` y `secretary` es **obligatorio** enviar `tenant_id`; se crea una fila en `professionals` con `is_active = FALSE` y los datos indicados.

**Payload (campos ampliados):**
- `email`, `password`, `role` (`professional` | `secretary` | `ceo`)
- `first_name`, `last_name`
- **`tenant_id`** (obligatorio si role es professional o secretary)
- `specialty` (opcional; recomendado para professional)
- `phone_number` (opcional)
- `registration_id` / matrícula (opcional)

El backend aplica fallbacks si la tabla `professionals` no tiene columnas `phone_number`, `specialty` o `updated_at` (parches 12d/12e en db.py).

### Login
`POST /auth/login`

**Payload:** `email`, `password` (form/x-www-form-urlencoded o JSON).

**Response (200):**
```json
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@clinica.com",
    "role": "ceo",
    "tenant_id": 1,
    "allowed_tenant_ids": [1, 2]
  }
}
```
El frontend guarda `access_token` y lo envía en `Authorization: Bearer <JWT>` junto con `X-Admin-Token` en rutas `/admin/*`.

### Usuario actual
`GET /auth/me`

Requiere `Authorization: Bearer <JWT>`. Devuelve el usuario autenticado (id, email, role, tenant_id, allowed_tenant_ids).

### Perfil
`GET /auth/profile` — Datos de perfil del usuario (incl. profesional si aplica).  
`PATCH /auth/profile` — Actualizar perfil (campos permitidos según rol).

---

## Configuración de clínica (idioma UI)

### Obtener configuración
`GET /admin/settings/clinic`

Devuelve la configuración de la clínica del tenant resuelto del usuario (nombre, horarios, **idioma de la UI**). Requiere autenticación admin.

**Response:**
- `name`: nombre de la clínica (`tenants.clinic_name`)
- `ui_language`: `"es"` | `"en"` | `"fr"` (por defecto `"en"`). Persistido en `tenants.config.ui_language`.
- `hours_start`, `hours_end`, `time_zone`, etc.

### Actualizar idioma de la plataforma
`PATCH /admin/settings/clinic`

Actualiza la configuración de la clínica. Solo se envían los campos a modificar.

### Configuración de despliegue
`GET /admin/config/deployment`

Devuelve datos de configuración del despliegue (feature flags, URLs, etc.) para el frontend. Requiere autenticación admin.

**Payload:**
```json
{ "ui_language": "en" }
```
Valores permitidos: `"es"`, `"en"`, `"fr"`. Se persiste en `tenants.config.ui_language` del tenant resuelto.

---

## Usuarios y aprobaciones

Todas las rutas requieren autenticación admin. Solo **CEO** puede aprobar/rechazar usuarios.

### Usuarios pendientes
`GET /admin/users/pending`

Lista usuarios con `status = 'pending'` (registrados pero no aprobados). Útil para la vista de Aprobaciones.

### Listar usuarios
`GET /admin/users`

Lista usuarios del sistema. Filtrado por tenant según rol (CEO ve todos los suyos; secretaria/profesional solo su tenant).

### Cambiar estado de usuario
`POST /admin/users/{user_id}/status`

Aprueba o rechaza un usuario pendiente.

**Payload:** `{ "status": "approved" }` o `{ "status": "rejected" }`.

---

## Sedes (Tenants)

Solo **CEO** puede gestionar sedes. Requieren autenticación admin.

### Listar sedes
`GET /admin/tenants`

Devuelve todas las clínicas/sedes del CEO.

### Crear sede
`POST /admin/tenants`

**Payload:** Incluye `clinic_name`, `config` (JSON, ej. `calendar_provider`, `ui_language`), etc.

### Actualizar sede
`PUT /admin/tenants/{tenant_id}`

Actualiza nombre y/o configuración de la sede.

### Eliminar sede
`DELETE /admin/tenants/{tenant_id}`

Elimina la sede (restricciones de integridad según esquema).

---

## Tratamientos (Services)

### Listar Tratamientos
`GET /admin/treatment-types`

Retorna todos los tipos de tratamiento configurados para el tenant. Aislado por `tenant_id`.

**Response:** Lista de objetos con `code`, `name`, `description`, `default_duration_minutes`, `category`, `is_active`, etc.

### Obtener por código
`GET /admin/treatment-types/{code}`

Devuelve un tipo de tratamiento por su `code`.

### Duración por código
`GET /admin/treatment-types/{code}/duration`

Devuelve la duración en minutos del tratamiento (para agendar). Response: `{ "duration_minutes": 30 }`.

### Crear Tratamiento
`POST /admin/treatment-types`

Registra un nuevo servicio clínico.

**Payload:**
```json
{
  "code": "blanqueamiento",
  "name": "Blanqueamiento Dental",
  "description": "Tratamiento estético con láser",
  "default_duration_minutes": 45,
  "min_duration_minutes": 30,
  "max_duration_minutes": 60,
  "complexity_level": "medium",
  "category": "estetica",
  "requires_multiple_sessions": false,
  "session_gap_days": 0
}
```

### Actualizar Tratamiento
`PUT /admin/treatment-types/{code}`

Modifica las propiedades de un tratamiento existente.

**Payload:** (Mismo que POST, todos los campos opcionales)

### Eliminar Tratamiento
`DELETE /admin/treatment-types/{code}`

- Si no tiene citas asociadas: **Eliminación física**.
- Si tiene citas asociadas: **Soft Delete** (`is_active = false`).

## Profesionales

### Listar Profesionales
`GET /admin/professionals`

- **CEO:** devuelve profesionales de **todas** las sedes permitidas (`allowed_ids`).
- **Secretary/Professional:** solo los de su clínica.

**Response:** Lista de profesionales con `id`, `tenant_id`, `name`, `specialty`, `is_active`, `working_hours`, etc. (incluye `phone_number`, `registration_id` cuando existen en BD).

### Profesionales por usuario
`GET /admin/professionals/by-user/{user_id}`

Devuelve las filas de `professionals` asociadas a ese `user_id`. Usado por el modal de detalle y Editar Perfil en Aprobaciones (Personal Activo). Incluye `phone_number`, `registration_id`, `working_hours`, `tenant_id`, etc.

### Crear/Actualizar Profesional
`POST /admin/professionals` | `PUT /admin/professionals/{id}`

Crea o actualiza profesional (tenant_id, nombre, contacto, especialidad, matrícula, working_hours). El backend aplica fallbacks si faltan columnas `phone_number`, `specialty`, `updated_at` en la tabla `professionals`.

### Analíticas por profesional
`GET /admin/professionals/{id}/analytics`

Devuelve métricas del profesional (turnos, ingresos, etc.) para el dashboard. Requiere autenticación admin; filtrado por tenant.

### Bóveda de Credenciales (Internal)
`GET /admin/internal/credentials/{name}`

Obtiene credenciales internas. Requiere header **`X-Internal-Token`** (no JWT). Uso interno entre servicios.

---

## Calendario y bloques

### Connect Sovereign (Auth0 / Google Calendar)
`POST /admin/calendar/connect-sovereign`

Guarda el token de Auth0 cifrado (Fernet) en la tabla `credentials` (category `google_calendar`, por `tenant_id`) y actualiza `tenants.config.calendar_provider` a `'google'` para esa clínica. Requiere `CREDENTIALS_FERNET_KEY` en el entorno.

**Payload:**
```json
{
  "access_token": "<token Auth0>",
  "tenant_id": 1
}
```
- `tenant_id` opcional; si no se envía se usa la clínica resuelta del usuario (CEO puede indicar clínica).

**Response:** `{ "status": "connected", "tenant_id": 1, "calendar_provider": "google" }`

### Bloques de calendario
`GET /admin/calendar/blocks` — Lista bloques (no disponibilidad) del tenant. Params: `professional_id`, fechas si aplica.  
`POST /admin/calendar/blocks` — Crea bloque. Body: `google_event_id`, `title`, `description`, `start_datetime`, `end_datetime`, `all_day`, `professional_id`.  
`DELETE /admin/calendar/blocks/{block_id}` — Elimina un bloque.

### Sincronización (JIT)
`POST /admin/calendar/sync` o `POST /admin/sync/calendar`

Fuerza el mirroring entre Google Calendar y la BD local (bloqueos externos → `google_calendar_blocks`). Suele invocarse al cargar la Agenda.

---

## Chat (multi-tenant)

Las rutas de chat filtran por `tenant_id`; Human Override y ventana 24h son independientes por clínica.

- `GET /admin/chat/tenants` — Clínicas disponibles para Chats (CEO: todas; otros: una). Response: `[{ "id", "clinic_name" }]`.
### Enviar mensaje (Unificado)
`POST /admin/chat/send` (Alias: `POST /admin/whatsapp/send`)

**Payload:**
```json
{
  "conversation_id": "<UUID>",
  "message": "Texto del mensaje"
}
```
Opcionalmente soporta `phone` y `tenant_id` para compatibilidad legacy.

**Lógica:**
1. Valida la **Ventana de 24h de Meta** usando `last_user_message_at`. Si pasaron >24h, retorna **403 Forbidden**.
2. Enruta el mensaje según el `provider` de la conversación:
   - **YCloud**: Envío directo de WhatsApp API (requiere `YCLOUD_WHATSAPP_NUMBER` en credentials).
   - **Chatwoot**: Envío a través de la API de Chatwoot (Instagram, Facebook, WhatsApp).
3. Persiste en `chat_messages` con `platform_metadata` (incluyendo `provider_message_id` para deduplicación).

---

## Chat (multi-tenant - Legacy/YCloud focus)

Las rutas de chat filtran por `tenant_id`; Human Override y ventana 24h son independientes por clínica.

- `GET /admin/chat/tenants` — Clínicas disponibles para Chats.
- `GET /admin/chat/sessions?tenant_id=<id>` — Sesiones YCloud.
- `GET /admin/chat/messages/{phone}?tenant_id=<id>` — Historial.
- `PUT /admin/chat/sessions/{phone}/read?tenant_id=<id>` — Marcar como leído.
- `POST /admin/chat/human-intervention` — Override temporal.
- `POST /admin/chat/send` — (Ver sección anterior: Endpoint Unificado).

---

## Chat omnicanal (Chatwoot)

Integración con **Chatwoot** para recibir y responder conversaciones de WhatsApp, Instagram y Facebook desde la misma bandeja de Chats. Coexiste con el chat YCloud (por teléfono); el tenant se resuelve por JWT/admin en la API y por token en el webhook.

**Auth:** Todas las rutas bajo `/admin/...` exigen JWT + X-Admin-Token (igual que el resto del panel). El webhook es **público** y se valida con `access_token` en query.

### Configuración Chatwoot (Settings)
`GET /admin/integrations/chatwoot/config`

Devuelve la URL del webhook y el token para copiar/pegar en Chatwoot (Configuración → Inbox → Webhooks). El token se genera y persiste por tenant en la tabla `credentials` (nombre `WEBHOOK_ACCESS_TOKEN`).

**Response:**
```json
{
  "webhook_path": "/admin/chatwoot/webhook",
  "access_token": "<token por tenant>",
  "tenant_id": 1,
  "api_base": "https://tu-dominio.com"
}
```
`api_base` viene de la variable de entorno `BASE_URL` (sin barra final).

### Lista de conversaciones (summary)
`GET /admin/chats/summary`

**Query params:** `limit` (default 20), `offset` (default 0), `channel` (opcional: `whatsapp`, `instagram`, `facebook`), `human_override` (opcional: `true` para solo con override activo).

Devuelve conversaciones del tenant resuelto del usuario (Chatwoot y/o YCloud según tablas). Cada ítem incluye `id` (UUID), `name`, `channel`, `provider`, `last_message`, `last_message_at`, **`last_user_message_at`** (para cálculo de ventana 24h), `is_locked` (human override activo), `status`, `external_user_id`, `avatar_url`, `meta`.

### Mensajes de una conversación
`GET /admin/chats/{conversation_id}/messages`

**Query params:** `limit` (default 30), `offset` (default 0).

Lista mensajes de esa conversación (orden `created_at` DESC). Response: array de `{ id, conversation_id, role, content, timestamp, attachments, correlation_id }`.

> [!IMPORTANT]
> A partir de la Spec 18, este endpoint está deprecado en favor de `POST /admin/chat/send` (el cual actúa como alias), pero mantiene la misma lógica de enrutamiento y validación.

### Human override (24h)
`POST /admin/conversations/{conversation_id}/human-override`

**Body:** `{ "enabled": true | false }`.

Activa o desactiva el override humano por 24 horas para esa conversación. Actualiza `chat_conversations.human_override_until`. Response: `{ "status": "ok", "human_override": true | false }`.

### Webhook Chatwoot (público)
`POST /admin/chatwoot/webhook?access_token=<token>`

**Sin JWT.** El token debe coincidir con `WEBHOOK_ACCESS_TOKEN` del tenant en `credentials`. Solo evento `message_created`: upsert en `chat_conversations`, INSERT en `chat_messages`, buffer 16s (Redis) y proceso del agente si es mensaje entrante; si es saliente (eco), activa human override 24h. Response: `{ "status": "processed" | "ignored", "reason": "...", "conversation_id": "..." }`.

---

## Pacientes

Todas las rutas de pacientes están aisladas por `tenant_id`.

### Listar pacientes
`GET /admin/patients`

**Query params:** `limit`, `offset`, `search` (texto libre). Devuelve lista paginada de pacientes del tenant.

### Alta de Paciente
`POST /admin/patients`

Crea una ficha médica administrativamente. Incluye triaje inicial. Aislado por `tenant_id`.

**Payload (PatientCreate):**
```json
{
  "first_name": "Juan",
  "last_name": "Pérez",
  "phone_number": "+5491112345678",
  "email": "juan@mail.com",
  "dni": "12345678",
  "insurance": "OSDE"
}
```
Campos requeridos: `first_name`, `phone_number`. Opcionales: `last_name`, `email`, `dni`, `insurance`.

### Obtener paciente por ID
`GET /admin/patients/{id}`

Devuelve la ficha del paciente (datos personales, contacto, obra social, etc.).

### Actualizar paciente
`PUT /admin/patients/{id}`

Actualiza datos del paciente. Body: mismos campos que creación (parcial o completo según implementación).

### Eliminar paciente
`DELETE /admin/patients/{id}`

Elimina el paciente del tenant (o soft-delete según esquema).

### Historial clínico (records)
`GET /admin/patients/{id}/records` — Lista notas/registros clínicos del paciente.  
`POST /admin/patients/{id}/records` — Crea una nota clínica. Body: `content`, opcionalmente `odontogram_data`.

### Búsqueda semántica
`GET /admin/patients/search-semantic?q=<texto>`

Búsqueda por texto sobre pacientes del tenant (nombre, teléfono, email, etc.).

### Estado de obra social
`GET /admin/patients/{patient_id}/insurance-status`

Devuelve información de cobertura/obra social del paciente.

### Contexto Clínico del Paciente
`GET /admin/patients/phone/{phone}/context`

Retorna información consolidada para la vista de chat (Última cita, próxima cita, plan de tratamiento). Aislado por `tenant_id`.

**Resolución de identidad**:
- Si `{phone}` es un número (empieza con `+` o es dígito), busca por `phone_number`.
- Si `{phone}` es texto (ej: `adriangmrraa`), busca por **External IDs** (`instagram`, `facebook`, `chatwoot`) en el campo JSONB.

**Response:**
```json
{
  "patient": { 
    "id": 1, 
    "first_name": "Juan", 
    "external_ids": {"instagram": "user_id"},
    ... 
  },
  "last_appointment": { ... },
  "upcoming_appointment": { ... },
  "treatment_plan": "...",
  "is_guest": false
}
```

---

## Turnos (Appointments)

Todas las rutas de turnos están aisladas por `tenant_id`. La disponibilidad y reserva usan **calendario híbrido**: si `tenants.config.calendar_provider == 'google'` se usa Google Calendar; si `'local'`, solo BD local (`appointments` + bloques).

### Listar turnos
`GET /admin/appointments`

**Query params:** `start_date`, `end_date` (ISO), `professional_id` (opcional). Devuelve turnos del tenant en el rango.

### Verificar colisiones
`GET /admin/appointments/check-collisions`

Comprueba solapamientos antes de crear/editar. Params: `professional_id`, `start`, `end`, opcional `exclude_appointment_id`.

### Crear turno
`POST /admin/appointments`

**Payload (AppointmentCreate):**
```json
{
  "patient_id": 1,
  "patient_phone": null,
  "professional_id": 2,
  "appointment_datetime": "2026-02-15T10:00:00",
  "appointment_type": "checkup",
  "notes": "Primera visita",
  "check_collisions": true
}
```
`patient_id` o `patient_phone` (para paciente rápido); `professional_id` y `appointment_datetime` obligatorios. `check_collisions` por defecto `true`.

### Actualizar turno
`PUT /admin/appointments/{id}`

Actualiza fecha, profesional, tipo, notas, etc. Respeta calendario (Google o local) según tenant.

### Cambiar estado
`PATCH /admin/appointments/{id}/status` o `PUT /admin/appointments/{id}/status`

Body: `{ "status": "confirmed" }` (o `cancelled`, `completed`, etc., según modelo).

### Eliminar turno
`DELETE /admin/appointments/{id}`

Borra el turno; si hay evento en Google Calendar, se sincroniza la cancelación.

### Próximos slots
`GET /admin/appointments/next-slots`

**Query params:** `professional_id`, `date` (opcional), `limit`. Devuelve los siguientes huecos disponibles para agendar (según calendario híbrido).

---

## Analítica y Estadísticas

### Resumen de Estadísticas
`GET /admin/stats/summary`

Retorna métricas clave del sistema (IA, Ingresos, Urgencias).

**Query Params:**
- `range`: Período de tiempo (`weekly` para 7 días, `monthly` para 30 días). Default: `weekly`.

**Response:**
```json
{
  "ia_conversations": 150,
  "ia_appointments": 12,
  "active_urgencies": 3,
  "total_revenue": 45000.0,
  "growth_data": [
    { "date": "2026-02-01", "ia_referrals": 5, "completed_appointments": 3 }
  ]
}
```

### Resumen de profesionales (analytics)
`GET /admin/analytics/professionals/summary`

Métricas por profesional para el dashboard CEO (citas, ingresos, etc.). **Query params:** `start_date`, `end_date` (opcional; por defecto mes actual).

### Urgencias Recientes
`GET /admin/chat/urgencies`

Lista los últimos casos de urgencia detectados por el sistema de triaje IA.

**Response:**
```json
[
  {
    "id": "123",
    "patient_name": "Juan Perez",
    "phone": "+54911...",
    "urgency_level": "CRITICAL",
    "reason": "Dolor agudo...",
    "timestamp": "2026-02-08T10:30:00"
  }
]
```

---

### Proxy de Medios (Spec 22)
`GET /admin/chat/media/proxy`

Sirve archivos de medios (imágenes/audio) de forma segura, resolviendo URLs firmadas o locales sin exponerlas directamente.

**Query Params:**
- `url`: URL absoluta del recurso (S3, YCloud, o path local `/media/...`).
- `tenant_id`: ID del tenant para validación de acceso.

**Response:** Stream de bytes del archivo con el Content-Type correcto.

---

## Otros

### Health
`GET /health`

**Público.** Respuesta: `{ "status": "ok", "service": "dental-orchestrator" }`. Usado por orquestadores y monitoreo.

### Chat (IA / WhatsApp / Vision)
`POST /chat`

Endpoint usado por el **WhatsApp Service** (y pruebas) para enviar mensajes al agente LangChain. Ahora con soporte MULTIMODAL (Spec 23) y BUFFER UNIFICADO (Spec 24/25).

**Payload:**
```json
{
  "final_phone": "+54911...",
  "final_message": "Hola, me duele...",
  "media": [
    { "type": "image", "url": "https://..." },
    { "type": "audio", "url": "https://..." }
  ]
}
```
**Comportamiento (Async Queue):**
- **Buffer 10s (Texto/Audio):** Agrupa mensajes en ráfaga (Sliding Window).
- **Buffer 20s (Imagen):** Extiende la espera si detecta una imagen para dar tiempo al análisis de Visión.
- **Respuesta Inmediata:** `{ "status": "queued", "send": false, "text": "[Procesando...]" }`. El agente responde asincrónicamente via YCloud/Chatwoot.

- **Vision**: Si viene `media` de tipo `image`, se dispara análisis GPT-4o.
- **Persistencia**: Historial en BD + Inyección de contexto visual.

---

## Parámetros globales (paginación y filtros)

En rutas de listado administrativas suelen soportarse:
- **`limit`**: Cantidad de registros (default típico: 50).
- **`offset`**: Desplazamiento para paginación.
- **`search`**: Filtro por texto libre cuando aplique.

---

## Códigos de error habituales

| Código | Significado |
|--------|-------------|
| **401** | No autenticado o token inválido. En `/admin/*` suele indicar JWT faltante/inválido o **falta de header `X-Admin-Token`**. |
| **403** | Sin permiso para el recurso (ej. tenant no permitido para el usuario). |
| **404** | Recurso no encontrado (paciente, turno, sede, etc.). |
| **422** | Error de validación (body o query params incorrectos). |
| **500** | Error interno del servidor. |
