# Contexto completo del proyecto para agentes IA

**Propósito:** Este documento permite que otra IA (en otra conversación) tome contexto completo del proyecto Dentalogic: qué es, cómo está construido, cómo trabajar en él y dónde está cada cosa. Úsalo como punto de entrada único antes de tocar código.

**Para comenzar una nueva conversación con una IA de código (ej. Cursor):** Usá el **prompt listo para copiar/pegar** en [docs/PROMPT_CONTEXTO_IA_COMPLETO.md](PROMPT_CONTEXTO_IA_COMPLETO.md). Copiá el bloque de ese archivo y pegarlo como **primer mensaje** del chat nuevo; así la IA carga reglas, workflows y checklist desde el inicio.

**Última actualización:** 2026-02 (Chatwoot omnicanal: webhook, lista unificada YCloud+Chatwoot, filtro canal, Vault agente por tenant; landing demo, agenda fixes, buffer)

---

## 1. Qué es el proyecto

- **Nombre:** Dentalogic (Nexus v8.0 / Platinum Security Hardened).
- **Tipo:** Plataforma de gestión clínica dental **multi-tenant** (multi-sede), con asistente IA por WhatsApp para turnos, triaje y derivación a humano.
- **Seguridad Proactiva (v8.0)**: Middleware de headers (HSTS, CSP, XFO), AI Guardrails (Prompt Injection Detection), sanitización XSS (SafeHTML) y X-Admin-Token obligatorio.
- **Usuarios:** Clínicas (una o varias sedes), CEOs, secretarias, profesionales. Pacientes interactúan por WhatsApp con el agente.
- **Pilares:** Backend (Orchestrator FastAPI + LangChain), Frontend (React + Vite + Tailwind), WhatsApp Service (YCloud + Whisper), PostgreSQL, Redis. Opcional: integración **Chatwoot** (WhatsApp/Instagram/Facebook en la misma bandeja de Chats; webhook, filtro por canal, credenciales por tenant en tabla `credentials`).

---

## 2. Stack y repositorio

| Capa | Tecnología | Ubicación |
|------|------------|-----------|
| **Backend (orquestador)** | FastAPI, LangChain, OpenAI GPT-4o-mini, asyncpg | `orchestrator_service/` |
| **WhatsApp / audio** | FastAPI, YCloud, Whisper | `whatsapp_service/` |
| **Frontend** | React 18, TypeScript, Vite, Tailwind, FullCalendar, Socket.IO client, Recharts | `frontend_react/` |
| **Base de datos** | PostgreSQL (esquema + parches en arranque) | `orchestrator_service/db.py` + `db/init/` |
| **Caché / locks** | Redis | Env `REDIS_URL` |
| **Infra** | Docker Compose, opcional EasyPanel | `docker-compose.yml` |

**Regla de oro:** Código de negocio y API admin están en `orchestrator_service/`. El frontend solo consume esa API y el chat (POST `/chat`).

---

## 3. Estructura de carpetas clave

```
orchestrator_service/
  main.py              # App FastAPI, POST /chat, LangChain agent, tools, Socket.IO; get_agent_executable_for_tenant (Vault)
  admin_routes.py      # Todas las rutas /admin/* (pacientes, turnos, chat YCloud, tenants, settings, analytics, etc.)
  auth_routes.py       # /auth/login, /auth/register, /auth/me, /auth/clinics, /auth/profile
  db.py                # Pool PostgreSQL + Maintenance Robot (parches: chat_conversations, credentials, chat_messages)
  gcal_service.py      # Google Calendar (disponibilidad, eventos, bloques)
  analytics_service.py # Métricas por profesional (CEO)
  chatwoot_client.py   # Cliente HTTP para enviar mensajes a la API Chatwoot
  core/credentials.py  # get_tenant_credential, resolve_tenant_from_webhook_token (Vault por tenant)
  routes/chat_webhooks.py  # POST /admin/chatwoot/webhook (evento message_created)
  routes/chat_api.py   # GET /admin/chats/summary, /admin/chats/{id}/messages, POST /admin/whatsapp/send, human-override, config
  services/relay.py    # Buffer inteligente (10s texto/audio, 20s imagen); enqueue_buffer_and_schedule_task
  services/buffer_task.py  # process_buffer_task: invoca agente por tenant, envía respuesta por Chatwoot
  core/security_middleware.py # Nexus Security Middleware (HSTS, CSP, XFO)
  core/prompt_security.py    # AI Guardrails: detect_prompt_injection, sanitize_input
  core/log_sanitizer.py      # Redacción de PII y tokens en logs

frontend_react/src/
  App.tsx              # Rutas; LanguageProvider y AuthProvider envuelven todo
  context/
    AuthContext.tsx    # Sesión, rol, usuario
    LanguageContext.tsx # language, setLanguage, t(key); locales es/en/fr
  api/axios.ts         # Cliente HTTP; inyecta Authorization, X-Admin-Token
  views/              # Una vista por pantalla (LoginView, AgendaView, ChatsView, etc.)
  components/         # Layout, Sidebar, AppointmentForm, MobileAgenda, AnalyticsFilters, etc.
    common/SafeHTML.tsx # Componente de renderizado seguro (XSS Prevention)
  locales/
    es.json, en.json, fr.json  # Traducciones; todas las vistas usan t('clave')
```

---

## 4. Reglas obligatorias (resumen de AGENTS.md)

- **Backend – Soberanía:** Todas las consultas (SELECT/INSERT/UPDATE/DELETE) deben filtrar por `tenant_id`. El aislamiento por sede es inviolable.
- **Backend – Auth:** Rutas admin usan `verify_admin_token` (valida JWT + X-Admin-Token + rol). No usar `get_current_user` solo en rutas que requieran rol CEO.
- **Backend – Security Hardening (v8.0)**: Todo input del usuario al LLM debe pasar por `detect_prompt_injection`. No deshabilitar el middleware de headers.
- **Frontend – XSS Prevention**: Prohibido usar `dangerouslySetInnerHTML`. Usar `<SafeHTML html={...} />` para contenido dinámico.
- **Frontend – Rutas:** Rutas con hijos deben usar `path="/*"`. `/profesionales` redirige a `/aprobaciones`; la gestión de profesionales es desde Personal Activo (UserApprovalView).
- **Frontend – Scroll:** Aislamiento de scroll: contenedor global `h-screen overflow-hidden`; vistas con `flex-1 min-h-0 overflow-y-auto` para no romper layout.
- **Frontend – i18n:** Cualquier texto visible debe usar `useTranslation()` y `t('namespace.key')`. Añadir claves en `es.json`, `en.json` y `fr.json`.
- **Base de datos:** No ejecutar SQL manual contra producción. Cambios de esquema: añadir parches idempotentes en `db.py` (bloques `DO $$ ... END $$`) y, si aplica, actualizar `db/init/dentalogic_schema.sql` para instalaciones nuevas.

---

## 5. Cómo ejecutar el proyecto

- **Todo el stack:** `docker-compose up --build` (Orchestrator en 8000, WhatsApp en 8002, frontend en 5173, Postgres, Redis).
- **Solo frontend (dev):** `cd frontend_react && npm install && npm run dev` (asume API en `VITE_API_URL` o `http://localhost:8000`).
- **Variables mínimas:** Ver `docs/02_environment_variables.md`. Imprescindibles: `POSTGRES_DSN`, `REDIS_URL`, `OPENAI_API_KEY`, `JWT_SECRET_KEY`, `ADMIN_TOKEN` (y para WhatsApp: `YCLOUD_*`). Opcional: `CREDENTIALS_FERNET_KEY` para connect-sovereign (Google Calendar).

---

## 6. Backend – Resumen de API

- **Auth:** `POST /auth/login`, `POST /auth/register` (con `tenant_id`, specialty, phone_number, registration_id para professional/secretary), `GET /auth/clinics`, `GET /auth/me`, `GET/PATCH /auth/profile`.
- **Admin – Configuración:** `GET /admin/settings/clinic` (devuelve `ui_language` es|en|fr), `PATCH /admin/settings/clinic` (body `{ "ui_language": "es"|"en"|"fr" }` → `tenants.config.ui_language`).
- **Admin – Pacientes, turnos, profesionales, chat, tenants, tratamientos, analíticas, calendario:** Ver `docs/AUDIT_ESTADO_PROYECTO.md` sección 2 (tablas de endpoints) o `docs/API_REFERENCE.md`.
- **Chat IA:** `POST /chat` (mensaje entrante; contexto `current_customer_phone`, `current_tenant_id`; tools con filtro por tenant).
- **Chat omnicanal (Chatwoot):** `GET /admin/integrations/chatwoot/config`, `GET /admin/chats/summary` (query `channel`: whatsapp|instagram|facebook), `GET /admin/chats/{id}/messages`, `POST /admin/whatsapp/send`, `POST /admin/conversations/{id}/human-override`; webhook público `POST /admin/chatwoot/webhook?access_token=...`. Credenciales por tenant en tabla `credentials`; agente usa `get_agent_executable_for_tenant(tenant_id)` (Vault OPENAI_API_KEY). Ver `docs/API_REFERENCE.md` (sección Chat omnicanal) y `docs/AUDIT_CHATWOOT_2025-02-13.md`.

**Tools del agente (nombres exactos):** `check_availability`, `book_appointment`, `triage_urgency`, `derivhumano`, `cancel_appointment`, `reschedule_appointment`, `list_services`. Todos reciben/respetan `tenant_id`.

**Flujo del agente (datos que necesita):** Saludo mencionando la clínica → definir **siempre un servicio** (máx. 3 si se listan) → usar duración del servicio para disponibilidad y agendar → **consultar disponibilidad** (local o Google según sede) y **elegir profesional** (preguntar preferencia o "cualquiera disponible") → con servicio, profesional (opcional), día/hora y datos del paciente, ejecutar `book_appointment`. Detalle en `README.md` (sección "Flujo del agente de IA") y `docs/04_agent_logic_and_persona.md` (sección 3.1).

---

## 7. Frontend – Rutas y vistas

**Rutas públicas (sin ProtectedRoute):** `/login`, `/demo`.

| Ruta | Vista | Notas |
|------|--------|--------|
| `/login` | LoginView | Registro con sede, especialidad, teléfono, matrícula para pro/secretary. Con `?demo=1`: prellenado y botón "Entrar a la demo" (login automático). |
| `/demo` | LandingView | Landing pública: Probar app (→ /login?demo=1), Probar Agente IA (WhatsApp), Iniciar sesión (→ /login). Móvil-first, conversión. |
| `/` | DashboardView | KPIs, urgencias, gráficos |
| `/agenda` | AgendaView | FullCalendar, Socket.IO, leyenda origen (IA/Manual/GCal) traducida |
| `/pacientes`, `/pacientes/:id` | PatientsView, PatientDetail | Listado y ficha clínica |
| `/chats` | ChatsView | Por tenant_id; lista unificada YCloud + Chatwoot; filtro canal (Todos, WhatsApp, Instagram, Facebook); human override, envío manual; polling 10s lista, 3s mensajes Chatwoot |
| `/profesionales` | Redirect | → `/aprobaciones` |
| `/analytics/professionals` | ProfessionalAnalyticsView | Solo CEO; filtros y tabla con t() |
| `/tratamientos` | TreatmentsView | CRUD treatment-types |
| `/perfil` | ProfileView | Perfil usuario |
| `/aprobaciones` | UserApprovalView | Pendientes + Personal Activo; modal detalle, Vincular a sede, Editar Perfil |
| `/sedes` | ClinicsView | CRUD tenants (solo CEO) |
| `/configuracion` | ConfigView | Selector idioma (es/en/fr); GET/PATCH settings/clinic; sección Chatwoot (URL webhook + token para copiar en Chatwoot) |

Todas las vistas anteriores usan `useTranslation()` y `t()` para respetar el selector de idioma.

---

## 8. Base de datos (PostgreSQL)

- **Esquema base:** `db/init/dentalogic_schema.sql` (tenants, users, professionals, patients, appointments, clinical_records, chat_messages, treatment_types, credentials, etc.).
- **Evolución:** `orchestrator_service/db.py` – Maintenance Robot aplica parches en cada arranque (tenant_id en tablas, columnas source, google_calendar_event_id, phone_number, specialty en professionals; tablas `chat_conversations`, `credentials`; extensión `chat_messages` con conversation_id, content_attributes, platform_metadata para Chatwoot). Siempre idempotente (`DO $$ ... IF NOT EXISTS ... END $$`).
- **Multi-tenant:** Tablas con `tenant_id`: tenants, professionals, patients, appointments, clinical_records, treatment_types, chat_messages, google_calendar_blocks, etc. Toda consulta debe filtrar por `tenant_id` del usuario/sesión.
- **Config por sede:** `tenants.config` (JSONB): `ui_language`, `calendar_provider` ('local' | 'google'), etc.

---

## 9. i18n (idiomas en la plataforma)

- **Idiomas:** Español (es), Inglés (en), Francés (fr). Idioma por defecto: **inglés**.
- **Dónde se elige:** Configuración (`/configuracion`) – solo CEO. Se persiste en `tenants.config.ui_language` vía PATCH `/admin/settings/clinic`.
- **Frontend:** `LanguageProvider` envuelve la app. Al cargar con sesión se obtiene idioma de GET `/admin/settings/clinic`; también se usa `localStorage` (`ui_language`). Componentes usan `useTranslation()` y `t('namespace.key')`. Archivos: `frontend_react/src/locales/es.json`, `en.json`, `fr.json`.
- **Añadir un texto traducido:** 1) Añadir clave en los tres JSON (ej. `"my_section.my_key": "Texto"`). 2) En el componente: `const { t } = useTranslation();` y usar `t('my_section.my_key')`.
- **Agente WhatsApp:** Responde en el idioma del mensaje del paciente (detección es/en/fr en backend); no depende del idioma de la UI.

---

## 10. Documentación – Índice rápido

**Índice maestro completo (28 docs en `docs/`):** [docs/00_INDICE_DOCUMENTACION.md](00_INDICE_DOCUMENTACION.md). Resumen a continuación.

| Documento | Contenido |
|-----------|-----------|
| **AGENTS.md** (raíz) | Reglas de oro, soberanía, tools, Maintenance Robot, i18n. **Leer antes de modificar.** |
| **README.md** | Visión general, para quién es, funcionalidades, multi-sede, idiomas, guía rápida, enlaces a docs. |
| **docs/00_INDICE_DOCUMENTACION.md** | Índice de todos los documentos de `docs/` con descripción por archivo. |
| **docs/01_architecture.md** | Diagrama, microservicios, base de datos, seguridad, flujo urgencia, calendario híbrido. |
| **docs/02_environment_variables.md** | Variables de entorno por servicio. |
| **docs/03_deployment_guide.md** | Despliegue (EasyPanel, etc.). |
| **docs/04_agent_logic_and_persona.md** | Persona del agente, reglas de conversación, flujo de datos (servicio, profesional, disponibilidad, agendar). |
| **docs/05_developer_notes.md** | Cómo añadir tools, paginación, debugging, Maintenance Robot, i18n, agenda móvil, analytics. |
| **docs/06_ai_prompt_template.md** | Plantilla de prompt para el agente IA. |
| **docs/07_workflow_guide.md** | Ciclo de tareas, Git, documentación, troubleshooting, comunicación entre servicios. |
| **docs/08_troubleshooting_history.md** | Histórico de problemas y soluciones; calendario e IA "no ve disponibilidad". |
| **docs/09_fase1_dental_datos_especificacion.md** | Fase 1 evolución de datos: especificación técnica, tablas, estado de implementación. |
| **docs/11_gap_analysis_nexus_to_dental.md** | Análisis de gaps: implementación vs requerimientos finales. |
| **docs/12_resumen_funcional_no_tecnico.md** | Resumen funcional en lenguaje no técnico. |
| **docs/13_lead_patient_workflow.md** | Flujo lead → paciente: conversión de contactos a pacientes activos. |
| **docs/29_seguridad_owasp_auditoria.md** | Auditoría OWASP Top 10:2025; JWT, X-Admin-Token, credenciales. |
| **docs/30_audit_api_contrato_2026-02-09.md** | Auditoría contrato API: OpenAPI vs endpoints reales. |
| **docs/31_audit_documentacion_2026-02-09.md** | Auditoría documentación: alineación SaaS, referencias a specs. |
| **docs/API_REFERENCE.md** | Referencia completa de la API administrativa; Swagger/ReDoc. |
| **docs/audit_26_calendario_hibrido_2026-02-10.md** | Auditoría spec 26 (match código vs spec). |
| **docs/AUDIT_ESTADO_COMPLETO_POR_PAGINA.md** | Auditoría estado completo por página del frontend. |
| **docs/AUDIT_ESTADO_PROYECTO.md** | Estado detallado: endpoints por módulo, rutas frontend, specs vs código. |
| **docs/cambios_recientes_2026-02-10.md** | Resumen de cambios recientes (spec 26, disponibilidad, landing, docs). |
| **docs/Instrucciones para IA.md** | Instrucciones para una IA que trabaje en el proyecto. |
| **docs/MATRIZ_DECISION_SKILLS.md** | Matriz de decisión para elegir skills según tipo de tarea. |
| **docs/mision_maestra_agenda.md** | Misión maestra de la agenda: objetivos y criterios. |
| **docs/PROMPT_CONTEXTO_IA_COMPLETO.md** | Prompt listo para copiar/pegar: reglas, workflows, skills, checklist. |
| **docs/PROTOCOLO_AUTONOMIA_SDD.md** | Protocolo autonomía SDD v2.0; criterios de detención. |
| **docs/riesgos_entendimiento_agente_agendar.md** | Riesgos de entendimiento del agente al agendar; mitigaciones. |
| **docs/SPECS_IMPLEMENTADOS_INDICE.md** | Índice de especificaciones implementadas; consolidación de specs. |

---

## 11. Tareas frecuentes (cómo trabajar)

- **Añadir una tool al agente:** Definir función en `main.py` con `@tool`, añadirla a la lista `tools` del agente. Respetar siempre `tenant_id` en la lógica.
- **Añadir un endpoint admin:** En `admin_routes.py`, usar `verify_admin_token`, obtener `tenant_id` del usuario cuando aplique, filtrar consultas por `tenant_id`.
- **Añadir una vista o ruta en el frontend:** Crear vista en `frontend_react/src/views/`, añadir ruta en `App.tsx` (y en Sidebar si debe aparecer en menú). Usar `useTranslation()` y `t()` para todos los textos.
- **Añadir traducciones:** Añadir claves en `es.json`, `en.json`, `fr.json`; en el componente usar `t('namespace.key')`.
- **Cambiar el esquema de BD:** Añadir parche idempotente en `orchestrator_service/db.py`; opcionalmente actualizar `db/init/dentalogic_schema.sql` para nuevas instalaciones. No ejecutar SQL directo en producción sin flujo controlado.

---

*Documento pensado para que un agente de IA en otra conversación pueda tomar contexto completo del proyecto Dentalogic y trabajar de forma coherente con las reglas y la estructura existente.*
