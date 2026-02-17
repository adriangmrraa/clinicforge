# Auditoría de estado del proyecto – Dentalogic / Nexus

**Fecha:** 2026-02-08 (actualizado 2026-02-09)  
**Workflow:** Audit (detección de drift y estado global)  
**Alcance:** Backend, Frontend, Base de datos, Lógica, Especificaciones vs código.

> **Nota (2026-02-09):** Los archivos `.spec.md` listados en la tabla "Specs vs código" fueron consolidados; la trazabilidad y el estado de cada feature están en **[docs/SPECS_IMPLEMENTADOS_INDICE.md](SPECS_IMPLEMENTADOS_INDICE.md)**. La seguridad OWASP quedó en **docs/29_seguridad_owasp_auditoria.md**.

---

## 1. Resumen ejecutivo

| Área        | Estado global | Drift / Riesgos |
|------------|----------------|------------------|
| Backend    | ✅ Funcional   | ✅ **Corregido:** rutas `/admin/tenants` ahora usan `verify_admin_token` (antes `get_current_user` no definido). Bloque `except` suelto eliminado. |
| Frontend   | ✅ Funcional   | ✅ Vista Configuración (ConfigView) con selector de idioma (es/en/fr) e i18n en Sidebar, Layout y páginas. Sedes (ClinicsView) usa `/admin/tenants` correctamente. |
| Base de datos | ✅ Esquema unificado | ✅ Aislamiento por `tenant_id` en tablas críticas. |
| Lógica     | ✅ Coherente  | Soberanía (tenant_id, JWT) aplicada en la mayoría de endpoints. |
| Specs vs código | Parcial | Algunas specs implementadas; otras (ej. Sovereign Glass) parciales. |

---

## 2. Backend (orchestrator_service)

### 2.1 Stack y archivos críticos

- **Framework:** FastAPI  
- **DB:** asyncpg (PostgreSQL)  
- **Archivos:** `main.py` (app, chat, tools LangChain, Socket.IO, `get_agent_executable_for_tenant` Vault), `admin_routes.py` (API admin), `auth_routes.py` (login/register/me/profile), `db.py` (pool + Maintenance Robot; parches chat_conversations, credentials, chat_messages), `gcal_service.py` (Google Calendar), `analytics_service.py` (métricas profesionales), `chatwoot_client.py` (envío a API Chatwoot), `core/credentials.py` (get_tenant_credential, resolve_tenant_from_webhook_token), `routes/chat_webhooks.py` (POST /admin/chatwoot/webhook), `routes/chat_api.py` (chats/summary, messages, send, human-override, config), `services/relay.py` (buffer 10s/20s), `services/buffer_task.py` (agente por tenant, envío Chatwoot).  
- **Env opcional:** `CREDENTIALS_FERNET_KEY` (clave Fernet para cifrar tokens en `credentials`; requerida por `POST /admin/calendar/connect-sovereign`). `BASE_URL`, `REDIS_URL` para Chatwoot (ver `docs/02_environment_variables.md` §2.5). Ver `docs/02_environment_variables.md`.

### 2.2 Auth y seguridad

- **Auth:** JWT en `/auth/login`; `auth_service.decode_token` para sesión.  
- **Admin:** Doble capa: `X-Admin-Token` (header) + JWT en `Authorization`.  
- **Dependencia principal:** `verify_admin_token` en la mayoría de rutas admin (valida token + JWT + rol `ceo`|`secretary`|`professional`).  
- **Nota:** Las rutas de tenants usan `verify_admin_token` y comprueban `user_data.role == 'ceo'`; no se usa `get_current_user`.

### 2.3 Endpoints por módulo

#### Auth (`/auth`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/auth/clinics` | **Público.** Lista clínicas (id, clinic_name) para selector de registro. |
| POST | `/auth/register` | Registro usuario (status `pending`), Protocolo Omega. **Body ampliado:** `tenant_id` (obligatorio si role professional/secretary), `specialty`, `phone_number`, `registration_id`. Crea fila en `professionals` con `is_active=FALSE` para esa sede. |
| POST | `/auth/login` | Login, retorna JWT + user. |
| GET | `/auth/me` | Usuario actual (JWT). |
| GET | `/auth/profile` | Perfil extendido. |
| PATCH | `/auth/profile` | Actualizar perfil. |

#### Admin – Usuarios y aprobaciones

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/admin/users/pending` | Usuarios pendientes de aprobación. |
| GET | `/admin/users` | Listado de usuarios. |
| POST | `/admin/users/{user_id}/status` | Actualizar status (ej. aprobar). **Al aprobar (active):** si el usuario es professional/secretary y no tiene fila en `professionals`, se crea una para la primera sede (working_hours por defecto). |

#### Admin – Tenants (Sedes/Clínicas)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/admin/tenants` | Listar tenants (solo CEO). |
| POST | `/admin/tenants` | Crear tenant (solo CEO). |
| PUT | `/admin/tenants/{tenant_id}` | Actualizar tenant (solo CEO). |
| DELETE | `/admin/tenants/{tenant_id}` | Eliminar tenant (solo CEO). |

*Nota: Estas rutas usan `verify_admin_token` y comprueban `user_data.role == 'ceo'`.*

#### Admin – Chat / conversaciones

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/admin/chat/tenants` | Clínicas disponibles para Chats (CEO: todas; otros: una). |
| GET | `/admin/chat/sessions` | Sesiones de chat. **Query:** `tenant_id` (obligatorio). Solo sesiones de esa clínica; override 24h por (tenant_id, phone). |
| GET | `/admin/chat/messages/{phone}` | Mensajes por teléfono. **Query:** `tenant_id` (obligatorio). |
| PUT | `/admin/chat/sessions/{phone}/read` | Marcar conversación como leída. **Query:** `tenant_id`. |
| POST | `/admin/chat/human-intervention` | Activar/desactivar intervención humana. **Body:** `phone`, `tenant_id`, `activate`, `duration`. Independiente por clínica. |
| POST | `/admin/chat/remove-silence` | Quitar silencio (human override). **Body:** `phone`, `tenant_id`. |
| POST | `/admin/chat/send` | Enviar mensaje manual a WhatsApp. **Body:** `phone`, `tenant_id`, `message`. Ventana 24h por clínica. |
| GET | `/admin/chat/urgencies` | Urgencias recientes. |

#### Admin – Chat omnicanal (Chatwoot)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/admin/integrations/chatwoot/config` | URL webhook + token por tenant (para copiar en Chatwoot). |
| GET | `/admin/chats/summary` | Lista conversaciones (channel opcional: whatsapp, instagram, facebook). |
| GET | `/admin/chats/{conversation_id}/messages` | Mensajes de una conversación. |
| POST | `/admin/whatsapp/send` | Enviar mensaje. **Body:** `conversation_id`, `message`. Enruta por provider (Chatwoot/YCloud). |
| POST | `/admin/conversations/{conversation_id}/human-override` | Activar/desactivar override 24h. **Body:** `{ "enabled": true \| false }`. |
| POST | `/admin/chatwoot/webhook?access_token=...` | **Público.** Webhook Chatwoot (evento message_created); buffer 16s, agente por tenant (Vault). |

#### Admin – Pacientes

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/admin/patients` | Listar pacientes (filtro por tenant del usuario). |
| GET | `/admin/patients/{id}` | Detalle paciente. |
| PUT | `/admin/patients/{id}` | Actualizar paciente. |
| DELETE | `/admin/patients/{id}` | Eliminar paciente. |
| GET | `/admin/patients/phone/{phone}/context` | Contexto clínico por teléfono. |
| GET | `/admin/patients/{patient_id}/insurance-status` | Estado obra social. |
| GET | `/admin/patients/search-semantic` | Búsqueda por síntomas. |
| GET | `/admin/patients/{id}/records` | Historias clínicas. |
| POST | `/admin/patients/{id}/records` | Añadir nota clínica. |

#### Admin – Turnos (appointments)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/admin/appointments` | Listar por rango de fechas (y opcional professional_id). |
| GET | `/admin/appointments/check-collisions` | Verificar colisiones. |
| POST | `/admin/appointments` | Crear turno manual. |
| PUT/PATCH | `/admin/appointments/{id}/status` | Cambiar estado. |
| PUT | `/admin/appointments/{id}` | Actualizar turno. |
| DELETE | `/admin/appointments/{id}` | Eliminar turno. |
| GET | `/admin/appointments/next-slots` | Próximos slots disponibles. |

#### Admin – Profesionales

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/admin/professionals` | Listar profesionales. **CEO:** todos los de sus sedes (`allowed_ids`). **Secretary/Professional:** solo los de su clínica. |
| GET | `/admin/professionals/by-user/{user_id}` | Filas de `professionals` para ese usuario (para modal detalle y Editar Perfil). Devuelve id, tenant_id, first_name, last_name, email, specialty, is_active, working_hours, phone_number, registration_id. |
| POST | `/admin/professionals` | Crear profesional (o vincular usuario existente por email). **Body:** tenant_id, email, name, phone, specialty, license_number, etc. Fallbacks si faltan columnas `phone_number`, `specialty`, `updated_at` en BD. |
| PUT | `/admin/professionals/{id}` | Actualizar profesional (nombre, contacto, working_hours, etc.). Fallbacks para BD sin phone_number. |

#### Admin – Calendario / Google Calendar

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/admin/calendar/connect-sovereign` | Guardar token Auth0 cifrado (Fernet) en `credentials` (category `google_calendar`, por `tenant_id`) y poner `tenants.config.calendar_provider` en `'google'`. **Body:** `access_token`, opcional `tenant_id`. Requiere `CREDENTIALS_FERNET_KEY` en entorno. |
| GET | `/admin/calendar/blocks` | Bloques de calendario (rangos, professional_id). |
| POST | `/admin/calendar/blocks` | Crear bloque. |
| DELETE | `/admin/calendar/blocks/{block_id}` | Eliminar bloque. |
| POST | `/admin/calendar/sync` o `/admin/sync/calendar` | Disparar sincronización con GCal. |

#### Admin – Tratamientos (treatment-types)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/admin/treatment-types` | Listar tipos. |
| GET | `/admin/treatment-types/{code}` | Detalle por código. |
| POST | `/admin/treatment-types` | Crear tipo. |
| PUT | `/admin/treatment-types/{code}` | Actualizar. |
| DELETE | `/admin/treatment-types/{code}` | Eliminar. |
| GET | `/admin/treatment-types/{code}/duration` | Duración (por urgencia). |

#### Admin – Dashboard y analíticas

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/admin/stats/summary` | Resumen dashboard (range: weekly, etc.). |
| GET | `/admin/analytics/professionals/summary` | Métricas por profesional (CEO / Estrategia). |

#### Admin – Configuración

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/admin/config/deployment` | Config de despliegue. |
| GET | `/admin/settings/clinic` | Configuración de clínica (tenant resuelto). Devuelve `name`, `ui_language` (es\|en\|fr, default `en`), `hours_start`, `hours_end`, etc. |
| PATCH | `/admin/settings/clinic` | Actualizar configuración. **Body:** `{ "ui_language": "es" \| "en" \| "fr" }`. Persiste en `tenants.config.ui_language`. |

#### Interno (header X-Internal-Token)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/admin/internal/credentials/{name}` | Credencial interna (servicios). |

### 2.4 Main.py – Chat IA y tools

- **POST /chat:** Entrada de mensajes (WhatsApp o UI). Context vars: `current_customer_phone`, `current_tenant_id`. Mensajes y handoff filtrados por `tenant_id`; override 24h por (tenant_id, phone). Socket `NEW_MESSAGE` incluye `tenant_id`.
- **Cerebro Híbrido:** `check_availability` y `book_appointment` usan `get_tenant_calendar_provider(tenant_id)`: si `'google'` → GCal + BD; si `'local'` → solo BD (appointments). `cancel_appointment` y `reschedule_appointment` idem; Human Override y `derivhumano` por (tenant_id, phone).
- **Tools LangChain:** `check_availability`, `book_appointment`, `triage_urgency`, `derivhumano`, `cancel_appointment`, `reschedule_appointment`, `list_services`; todos con filtro por `tenant_id`.
- **Socket.IO:** Eventos de turnos y chat (NEW_MESSAGE, HUMAN_OVERRIDE_CHANGED, HUMAN_HANDOFF) con `tenant_id` cuando aplica.

### 2.5 Soberanía de datos (tenant_id)

- En `admin_routes`, las consultas a pacientes, turnos, profesionales, bloques de calendario, treatment_types, etc. filtran por `tenant_id` obtenido del usuario (JWT) o del contexto.  
- Rutas de tenants actuales no filtran por tenant (listan/crean/actualizan/eliminan todos los tenants); acceso restringido por rol CEO vía `get_current_user`, que está roto.

---

## 3. Frontend (frontend_react)

### 3.1 Stack

- React 18, TypeScript, Vite, Tailwind CSS, React Router, FullCalendar, Recharts, Socket.IO client, Axios.

### 3.2 Rutas (App.tsx) y vistas

| Ruta | Vista | Roles | Descripción breve |
|------|--------|-------|-------------------|
| `/login` | LoginView | Público | Login (email/password) → JWT + ADMIN_TOKEN en localStorage. **Registro:** Nombre, Apellido, Rol; si rol professional/secretary: **Sede/Clínica** (selector GET `/auth/clinics`), Especialidad (dropdown), Teléfono, Matrícula. POST `/auth/register` con tenant_id y datos de profesional; crea fila en `professionals` pendiente de aprobación. |
| `/` | DashboardView | ceo, professional, secretary | KPIs (conversaciones IA, turnos, urgencias, ingresos), gráfico de crecimiento, lista de urgencias. |
| `/agenda` | AgendaView | ceo, professional, secretary | Calendario (FullCalendar + resource-timegrid), bloques GCal, crear/editar/cancelar turnos, Socket.IO para refresco. Vista móvil con MobileAgenda. |
| `/pacientes` | PatientsView | ceo, professional, secretary | Listado de pacientes. |
| `/pacientes/:id` | PatientDetail | ceo, professional, secretary | Detalle paciente, historial, notas. |
| `/chats` | ChatsView | ceo, professional, secretary | Lista unificada YCloud + Chatwoot; filtro canal (Todos, WhatsApp, Instagram, Facebook); mensajes, envío manual, human override; polling 10s lista, 3s mensajes Chatwoot. |
| `/profesionales` | (redirige) | — | Redirige a `/aprobaciones`. La gestión de profesionales se hace desde **Personal Activo** (modal detalle + Vincular a sede / Editar Perfil). |
| `/analytics/professionals` | ProfessionalAnalyticsView | ceo | Analytics por profesional (métricas, filtros fechas, tags). |
| `/tratamientos` | TreatmentsView | ceo, secretary | CRUD tipos de tratamiento. |
| `/perfil` | ProfileView | Todos los roles | Perfil del usuario. |
| `/aprobaciones` | UserApprovalView | ceo | Aprobación de usuarios pendientes. **Personal Activo:** clic en tarjeta → modal detalle; botón **Vincular a sede** (sede, teléfono, especialidad dropdown, matrícula); botón **tuerca** → modal **Editar Perfil** (Datos Principales, Contacto & Estado, Disponibilidad). Profesionales listados vía GET `/admin/professionals` (CEO: todas sus sedes). |
| `/sedes` | ClinicsView | ceo | CRUD de tenants (sedes/clínicas). Llama a `/admin/tenants` → afectado por bug `get_current_user`. |
| `/configuracion` | ConfigView | ceo | Selector idioma (es/en/fr); sección Chatwoot (URL webhook + token): “Configuración – Próximamente…”. |

### 3.3 Componentes principales

- **Layout:** Sidebar colapsable, menú móvil, notificaciones Socket (handoff), área de contenido con hijos.  
- **Sidebar:** Items filtrados por rol; enlaces a todas las rutas anteriores.  
- **AgendaView:** FullCalendar, AppointmentForm, MobileAgenda, AppointmentCard; colores por origen (AI, manual, GCal).  
- **DashboardView:** KPICard, gráfico (recharts), UrgencyBadge; datos de `/admin/stats/summary` y `/admin/chat/urgencies`.  
- **ProfessionalAnalyticsView:** Filtros (fechas, profesionales), KPICard, BarChart, tabla de métricas; `/admin/analytics/professionals/summary`.  
- **ClinicsView:** Lista tenants, modal crear/editar, delete; `/admin/tenants` (GET/POST/PUT/DELETE).

### 3.4 API (axios.ts)

- Base URL: `VITE_API_URL` o `http://localhost:8000`.  
- Headers: `X-Admin-Token` (localStorage ADMIN_TOKEN), `Authorization: Bearer <JWT_TOKEN>`, `X-Tenant-ID` (localStorage/sessionStorage o default).  
- Retry con backoff en 5xx/timeout; 401 → limpieza y redirección a `/login`.

### 3.5 Estado por página (resumen)

| Página | Estado | Backend usado | Notas |
|--------|--------|----------------|-------|
| Login | ✅ | /auth/login | Guarda JWT + ADMIN_TOKEN. |
| Dashboard | ✅ | /admin/stats/summary, /admin/chat/urgencies | KPIs y urgencias. |
| Agenda | ✅ | /admin/appointments, /admin/calendar/blocks, /admin/professionals, next-slots, create/update/delete appointment, calendar/sync | Socket.IO para actualizaciones. |
| Pacientes | ✅ | /admin/patients | Listado y filtros. |
| Detalle paciente | ✅ | /admin/patients/{id}, /admin/patients/{id}/records | Notas clínicas. |
| Chats | ✅ | /admin/chat/tenants, /admin/chat/sessions?tenant_id=, messages, send, human-intervention, remove-silence, PUT sessions/read | Selector de Clínica (CEO varias); sesiones y override por tenant_id. |
| Profesionales | ✅ | /admin/professionals, /admin/professionals/by-user/:id | Gestión desde Aprobaciones (modal Vincular a sede / Editar Perfil). Ruta `/profesionales` redirige a `/aprobaciones`. |
| Analytics profesionales | ✅ | /admin/analytics/professionals/summary | Solo CEO. |
| Tratamientos | ✅ | /admin/treatment-types | CRUD por código. |
| Perfil | ✅ | /auth/profile, PATCH /auth/profile | Edición perfil. |
| Aprobaciones | ✅ | /admin/users/pending, /admin/users/{id}/status, /admin/professionals, /admin/professionals/by-user/:id, PUT /admin/professionals/:id | Solo CEO. Personal Activo + modal detalle, Vincular a sede, tuerca → Editar Perfil (3 columnas, max-w-6xl). |
| Sedes (Clinics) | ✅ | /admin/tenants | Corregido: backend usa `verify_admin_token`. |
| Configuración | ✅ | GET/PATCH /admin/settings/clinic | ConfigView: selector idioma (es/en/fr), sección Chatwoot (webhook URL + token), i18n aplicado. |

---

## 4. Base de datos

### 4.1 Esquema (dentalogic_schema.sql)

- **Mensajes y chat:** `inbound_messages`, `chat_messages` (desde parche 15: `chat_messages.tenant_id` para conversaciones por clínica).  
- **Tenant y config:** `tenants`, `credentials`, `system_events`.  
- **RBAC:** `users` (id UUID, email, role: ceo|professional|secretary, status: pending|active|suspended, professional_id).  
- **Profesionales:** `professionals` (tenant_id, user_id, first_name, last_name, email, is_active, google_calendar_id, **phone_number**, **specialty**, **registration_id**, **updated_at**, working_hours, etc.). Columnas añadidas por parches 12d (phone_number), 12e (specialty) si no existen.  
- **Pacientes:** `patients` (tenant_id, phone_number, dni, first_name, last_name, human_handoff_requested, human_override_until, etc.).  
- **Historias clínicas:** `clinical_records` (tenant_id, patient_id, professional_id, odontogram, treatment_plan, etc.).  
- **Turnos:** `appointments` (tenant_id, patient_id, professional_id, appointment_datetime, duration_minutes, google_calendar_event_id, status, urgency_level, source, etc.).  
- **Contabilidad:** `accounting_transactions`, `daily_cash_flow`.  
- **Calendario:** `google_calendar_blocks`, `calendar_sync_log`.  
- **Tratamientos:** `treatment_types` (tenant_id, code, name, default_duration_minutes, etc.).  
- **Función:** `get_treatment_duration(p_treatment_code, p_tenant_id, p_urgency_level)`.

### 4.2 Mantenimiento (db.py)

- **Maintenance Robot:** Al arrancar, comprueba existencia del esquema; si no existe aplica `dentalogic_schema.sql`.  
- **Evolution pipeline:** Parches idempotentes (user_id en professionals, Protocolo Omega Prime, DNI/last_name nullable, **parches 12–15:** `tenant_id` + índice en `professionals`, `appointments`, `treatment_types`, `chat_messages`; en `appointments` columnas `source` y `google_calendar_event_id`). **Parches 12d/12e:** añaden `phone_number` y `specialty` a `professionals` si no existen. `get_chat_history` acepta `tenant_id` opcional para historial por clínica.  
- Conexión vía `POSTGRES_DSN` (asyncpg).

### 4.3 Aislamiento multi-tenant

- Tablas con `tenant_id`: tenants, credentials, professionals, patients, clinical_records, appointments, accounting_transactions, daily_cash_flow, google_calendar_blocks, calendar_sync_log, treatment_types.  
- Consultas en admin_routes (pacientes, turnos, profesionales, bloques, treatment_types) usan `tenant_id` del usuario autenticado.  
- `users` no tiene `tenant_id`; la relación con tenant se hace vía `professionals.tenant_id` o lógica de negocio (por defecto tenant 1).

---

## 5. Lógica de negocio (resumen)

- **Auth:** Registro → pending; para professional/secretary se pide **sede (tenant_id)** y datos de profesional (especialidad, teléfono, matrícula); se crea fila en `professionals` con is_active=FALSE. CEO aprueba en Aprobaciones (POST users/:id/status → active); si no hay fila en professionals se crea para la primera sede. Login solo si status active.  
- **Tenant:** Usuario tiene contexto de tenant (por profesional o por defecto); backend filtra por ese tenant en datos clínicos y operativos.  
- **Agenda:** Turnos en DB + bloques en GCal; sincronización bidireccional; creación/edición desde UI con chequeo de colisiones y next-slots.  
- **IA/WhatsApp:** Mensajes entrantes → LangChain agent con tools (disponibilidad, reserva, triaje, derivhumano); human override 24h; mensajes guardados en chat_messages.  
- **Analytics CEO:** Agregación por profesional (turnos, ingresos, tasas) en rango de fechas; endpoint `/admin/analytics/professionals/summary`.  

---

## 6. Specs vs código (drift)

**Trazabilidad actual:** Ver **[SPECS_IMPLEMENTADOS_INDICE.md](SPECS_IMPLEMENTADOS_INDICE.md)** (consolidación 2026-02-09; los .spec.md fueron retirados).

| Spec | Documentación actual | Estado | Drift / Notas |
|------|----------------------|--------|----------------|
| Sovereign Glass (Agenda 2.0) | SPECS_IMPLEMENTADOS_INDICE, AGENTS.md | Parcial | Scroll isolation y glassmorphism aplicados en parte; revisar que todo contenedor flex-1 tenga min-h-0 y que no haya scroll global. |
| CEO Professionals Analytics | README, API_REFERENCE (analytics) | Implementado | ProfessionalAnalyticsView + `/admin/analytics/professionals/summary`. |
| Agenda Inteligente 2.0 | README, 01_architecture | Implementado | Agenda con recursos, bloques GCal, Socket.IO. |
| Google Calendar sync fix | 01_architecture, 08_troubleshooting | En uso | gcal_service y sync en admin. |
| Mobile scroll fix | AGENTS.md (Scroll Isolation) | Parcial | MobileAgenda y patrones de scroll; auditar todas las vistas móviles. |
| Mobile agenda range fix | 01_architecture | Parcial | Rango de fechas en agenda móvil. |
| Treatments optimization | README, API_REFERENCE | Implementado | treatment_types CRUD y duración por urgencia. |
| Professionals CEO control / Personal Activo | README, AGENTS.md | Implementado | Personal Activo como fuente de verdad; modal detalle, Vincular a sede, tuerca → Editar Perfil; GET by-user; CEO ve profesionales de todas sus sedes. |
| Registro con sede y datos profesional | README, API_REFERENCE (auth) | Implementado | GET /auth/clinics, POST /auth/register con tenant_id y datos pro; formulario registro con selector sede y especialidad. |
| Modal datos profesional (acordeón) | UserApprovalView, README | Implementado | Modal detalle grande con acordeón; GET /admin/professionals/:id/analytics; optimizado móvil (bottom sheet). |
| Idioma plataforma y agente | README (Idiomas), AGENTS.md | Implementado | Selector idioma en Configuración (es/en/fr); i18n; agente agnóstico y detección idioma del mensaje; idioma por defecto inglés. |
| Dashboard Analytics Sovereign | Dashboard_Analytics_Sovereign/docs/plans/ | Módulo aparte | Vistas CEO/Secretary; no integrado en frontend_react principal. |

---

## 7. Acciones correctivas recomendadas

1. ~~**Crítico – Rutas tenants:**~~ **HECHO.** Las rutas `/admin/tenants` usan ya `verify_admin_token` y comprueban rol CEO; se eliminó el bloque `except` suelto que seguía a `delete_tenant`.  
2. ~~**Configuración:**~~ **HECHO.** ConfigView en `/configuracion` con selector de idioma (es/en/fr), GET/PATCH `/admin/settings/clinic`, e i18n (Sidebar, Layout, ConfigView). “pendiente”.  
3. **Sovereign Glass / Scroll:** Revisar Layout y AgendaView (y vistas con listas largas) para cumplir 100% con Scroll Isolation (h-screen, overflow-hidden, flex-1 min-h-0 overflow-y-auto).  
4. **Dashboard Analytics Sovereign:** Decidir si el módulo en `Dashboard_Analytics_Sovereign` debe integrarse en la SPA principal (rutas y menú) o permanecer como servicio/vista separado, y documentarlo.  
5. ~~**Auditoría de sintaxis en admin_routes**~~ **HECHO.** Se eliminó el bloque `except` suelto que estaba después de `delete_tenant`.

---

## 8. Conclusión

El proyecto está **operativo** en backend (excepto tenants), frontend (excepto Sedes y Configuración), base de datos y lógica de negocio. La soberanía de datos (tenant_id y JWT) está aplicada en la gran mayoría de los endpoints.  

**Drift crítico corregido:** las rutas de tenants usan `verify_admin_token` y la vista Sedes (ClinicsView) funciona. **Actualizaciones recientes (2026-02-08):** Cerebro Híbrido, Chats por clínica, connect-sovereign; Personal Activo (modal detalle, acordeón con datos reales, GET `/admin/professionals/:id/analytics`); modales (detalle y Editar Perfil) optimizados móvil (bottom sheet, touch targets); **idioma:** ConfigView con selector es/en/fr, GET/PATCH `/admin/settings/clinic` (`ui_language` en `tenants.config`), LanguageContext + locales (es/en/fr), Sidebar/Layout/ConfigView con `t()` para efecto inmediato; agente agnóstico (nombre clínica inyectado, detección idioma del mensaje); idioma por defecto inglés. Pendiente: Scroll Isolation en todas las vistas, módulo Analytics Sovereign.

---

## 9. Actualizaciones post-audit (flujo Personal Activo y registro)

*Documentación ampliada sin eliminar contenido previo (Non-Destructive Fusion).*

### 9.1 Backend

- **Auth:** `GET /auth/clinics` (público) devuelve id y clinic_name para el selector de registro. `POST /auth/register` acepta `tenant_id` (obligatorio para professional/secretary), `specialty`, `phone_number`, `registration_id`; crea usuario y, si aplica, fila en `professionals` con `is_active=false`; fallbacks si faltan columnas en BD.
- **Profesionales:** `GET /admin/professionals` para CEO devuelve profesionales de **todas** las sedes permitidas (`allowed_ids`). `GET /admin/professionals/by-user/:user_id` devuelve las filas de `professionals` del usuario (para modal detalle y Editar Perfil), incluyendo `phone_number` y `registration_id`. En create/update se usan fallbacks cuando no existen columnas `phone_number`, `specialty`, `updated_at`, `working_hours`.
- **Aprobación:** Al aprobar usuario (POST `/admin/users/:id/status` con `active`), si es professional/secretary y no tiene fila en `professionals`, se crea una para el primer tenant.
- **Base de datos (db.py):** Parches 12d (columna `phone_number` en `professionals`) y 12e (columna `specialty`) aplicados en arranque si no existen.

### 9.2 Frontend

- **Login/Registro (LoginView):** Formulario de registro con Nombre, Apellido, Rol; si rol es professional o secretary: selector **Sede/Clínica** (GET `/auth/clinics`), **Especialidad** (dropdown), Teléfono, Matrícula.
- **Aprobaciones (UserApprovalView):** Clic en tarjeta de Personal Activo abre **modal de detalle**. Botón azul **“Vincular a sede”** con formulario (sede, teléfono, especialidad dropdown, matrícula). Botón **tuerca** (icono engranaje) a la izquierda de “Suspender Acceso” abre el **modal Editar Perfil** (o formulario Vincular si no tiene sede); modal grande (max-w-6xl, max-h-92vh), tres columnas (Datos Principales con Sede en solo lectura, Contacto & Estado, Disponibilidad con días y slots).
- **Navegación:** Eliminado ítem “Profesionales” del menú; ruta `/profesionales` redirige a `/aprobaciones`. La gestión de profesionales se realiza desde Personal Activo (modal detalle + Vincular a sede / Editar Perfil).
- **ProfessionalsView:** Si se accede por ruta directa, al editar se muestra **Sede/Clínica** en solo lectura; al crear, selector de clínica.

### 9.3 Especificaciones (trazabilidad)

Las especificaciones listadas se consolidaron en **docs/SPECS_IMPLEMENTADOS_INDICE.md** (2026-02-09). Contenido equivalente:

- **Professionals CEO control / Personal Activo:** Visión CEO, Personal Activo como fuente de verdad, modal detalle, Vincular a sede, tuerca → Editar Perfil. Ver README, AGENTS.md.
- **Registro con sede y datos profesional:** Registro con sede obligatoria y datos de profesional (especialidad, teléfono, matrícula). Ver README, API_REFERENCE (POST /auth/register).
- **Modal datos profesional (acordeón):** Modal detalle con acordeón (Sus pacientes, Uso plataforma, Mensajes) y datos reales vía `/admin/professionals/:id/analytics`; layout grande y scroll aislado; optimizado móvil. Ver UserApprovalView.
- **Idioma plataforma y agente:** Selector en Configuración (es/en/fr), `tenants.config.ui_language`, LanguageContext, locales, agente agnóstico y detección idioma del mensaje. Ver README (Idiomas), AGENTS.md.

### 9.4 Modales y móvil

- **Modal detalle del profesional:** Tamaño grande (max-w-6xl, 92dvh), scroll interno; en móvil se muestra como bottom sheet (items-end, rounded-t-3xl). Acordeón con tres secciones que cargan datos reales (métricas por profesional, conversaciones por sede).
- **Modal Editar Perfil:** Misma estrategia móvil (bottom sheet); botones y controles con min-h 44px y touch-manipulation.

### 9.5 Idioma (i18n y agente)

- **Backend:** `GET /admin/settings/clinic` devuelve `ui_language` (default `en`). `PATCH /admin/settings/clinic` con `{ "ui_language": "es"|"en"|"fr" }` actualiza `tenants.config.ui_language`.
- **Frontend:** `LanguageProvider` envuelve la app; carga idioma desde API al iniciar (si hay sesión) y desde `localStorage`. `useTranslation()` expone `t(key)`, `language`, `setLanguage`. Al cambiar idioma en ConfigView se llama `setLanguage(value)` primero (efecto inmediato en toda la UI) y luego PATCH para persistir.
- **Traducciones:** `frontend_react/src/locales/es.json`, `en.json`, `fr.json` con claves nav, common, config, login, layout, etc. Sidebar, Layout y ConfigView usan `t()`; el resto de vistas pueden ir migrando a claves.
- **Agente:** Prompt construido con `build_system_prompt(clinic_name, ...)`; `clinic_name` desde `tenants.clinic_name`. `detect_message_language(text)` devuelve es/en/fr y se inyecta la instrucción de responder en ese idioma.

### 9.6 Cobertura i18n completa (selector de idioma estricto)

**Objetivo:** Todo texto visible en la plataforma (incluidas notificaciones en tiempo real y diálogos) debe respetar el idioma elegido en Configuración (es/en/fr).

- **Notificaciones WebSocket (ChatsView):**
  - **HUMAN_HANDOFF:** Toast "Derivación Humana" / "Human handoff" / "Dérivation humaine" con mensaje traducido (`chats.toast_handoff_title`, `chats.toast_handoff_message_prefix` + teléfono y motivo).
  - **NEW_APPOINTMENT:** Toast "Nuevo Turno" / "New appointment" / "Nouveau rendez-vous" con mensaje traducido (`chats.toast_new_appointment_title`, `chats.toast_new_appointment_message_prefix` + teléfono).
  - Los listeners del socket usan `t()` en el closure; el efecto incluye `t` en dependencias para que al cambiar idioma los próximos toasts usen el idioma actual.
- **Notificación global (Layout):** El banner de derivación humana usa `t('layout.notification_handoff')` y `t('layout.notification_reason')`; el cuerpo muestra teléfono y motivo (motivo puede venir del backend en el idioma del agente).
- **Alertas y confirmaciones:** Todas las vistas que usan `alert()` o `confirm()` utilizan claves de `alerts.*` en es/en/fr.json: UserApprovalView, PatientsView, TreatmentsView, ClinicsView, AppointmentForm, PatientDetail, ProfessionalsView. Credentials, Tools, Stores, Setup (vistas de administración avanzada) pueden migrarse igual si se exponen en la misma SPA.
- **Páginas con t():** Login, Dashboard, Agenda, Pacientes, Chats, Personal (Aprobaciones), Sedes, Tratamientos, Perfil, Configuración; componentes Sidebar, Layout, AppointmentForm. Ningún texto de interfaz debe quedar fuera del selector.

---

*Documento generado por workflow Audit – Dentalogic / Antigravity. Última actualización doc: 2026-02-08. Secciones 9–9.6 ampliadas por workflow Update Docs (Non-Destructive Fusion).*
