# Arquitectura del Sistema - Dentalogic

Este documento describe la estructura técnica, el flujo de datos y la interacción entre los componentes de la plataforma de gestión clínica Dentalogic.

### 1. Diagrama de Bloques (Conceptual)

``` 
Usuario WhatsApp (Paciente)
        |
        | Audio/Texto/Imagen
        v
WhatsApp Service (8002)
  - YCloud Webhook
  - Deduplicación (Redis)
  - Transcripción (Whisper)
        |
        | POST /chat
        v
Orchestrator Service (8000)
  - LangChain Agent (Asistente Dental)
  - Vision Service (GPT-4o)  <-- NUEVO
  - Tools Clínicas (Agenda, Triaje)
  - Memoria Histórica (Postgres)
  - Lockout (24h)
  - Socket.IO Server (Real-time)
        |
    ____|____
   /    |    \
  v     v     v
PostgreSQL Redis OpenAI
(Historias)(Locks)(LLM/Vision)
   |
   v
Frontend React (5173)
Centro de Operaciones Dental
   |
   | WebSocket (Socket.IO)
   v
AgendaView / Odontograma
   - FullCalendar
   - Real-time updates
```

## 2. Estructura de Microservicios (Dentalogic)

### A. WhatsApp Service (Puerto 8002)

**Tecnología:** FastAPI + httpx + Redis

**Función:** Interfaz de comunicación con pacientes vía YCloud.

**Responsabilidades:**
- **Transcripción Whisper:** Convierte audios de síntomas en texto para el análisis de la IA.
- **Deduplicación:** Evita procesar el mismo mensaje de WhatsApp múltiples veces.
- **Deduplicación:** Evita procesar el mismo mensaje de WhatsApp múltiples veces.
- **Relay (Buffering):** Encola mensajes en `orchestrator_service` para agrupación inteligente (Sliding Window).
- **Relay de Audio/Imagen:** Permite que los audios e imágenes sean procesados y visualizados en el dashboard.

### B. Orchestrator Service (Puerto 8000) - **Coordinador Clínico**

**Tecnología:** FastAPI + LangChain + OpenAI + PostgreSQL

**Función:** Procesamiento de lenguaje natural, clasificación de urgencias, gestión de agenda y **Buffer Unificado**.

**NUEVO: Relay Service (Spec 24/25):**
- **Buffer Unificado:** Agrupa mensajes de WhatsApp y Chatwoot.
- **Sliding Window:** Cada mensaje reinicia el contador de espera (Debounce).
- **Dynamic TTL:**
    - Texto/Audio: **10 segundos**.
    - Imagen: **20 segundos** (protegido para análisis de visión).

**NUEVO: Vision Service (Spec 23):**
- **Capacidad:** Análisis de imágenes (Rx, fotos clínicas) usando GPT-4o.
- **Flujo:** Webhook -> Descarga -> Análisis Async -> Inyección de Contexto Visual en el Agente.

**Tools Clínicas Integradas:**
- `check_availability(date_query, [professional_name], [treatment_name], [time_preference])`: Implementa lógica **Just-in-Time (JIT)** y **cerebro híbrido** por sede.
  1. **Cerebro híbrido:** Lee `tenants.config.calendar_provider` (`local` o `google`). Si es local, solo usa tabla `appointments` y horarios de profesionales; si es google, para cada profesional con `google_calendar_id` consulta eventos GCal y los persiste en `google_calendar_blocks`.
  2. **Limpieza de Identidad:** Normaliza nombres de profesionales (elimina títulos como "Dr."/"Dra.").
  3. **Duración por tratamiento:** Si se pasa `treatment_name`, usa `default_duration_minutes` del tratamiento para calcular huecos.
  4. **Working hours:** Si el profesional no tiene horarios configurados para ese día, se considera disponible en horario clínica (evita "no hay huecos" cuando la semana está libre).
  5. **Cálculo de Huecos:** Combina `appointments` + bloqueos GCal (si aplica) y genera slots donde al menos un profesional esté libre.
- `book_appointment(...)`: 
  - **Protocolo Service-First**: La IA debe tener definido el servicio (tratamiento) antes de agendar; la duración se toma de `treatment_types.default_duration_minutes`.
  - Valida datos obligatorios para leads (DNI, Obra Social).
  - Registra turno en PG; si la sede usa Google y el profesional tiene `google_calendar_id`, crea evento en GCal.
  - Emite eventos WebSocket (`NEW_APPOINTMENT`) para actualizar UI.

**Gestión de Datos:**
- **Memoria Persistente:** Vincula cada chat con el `patient_id`.
- **Sincronización Real-Time (Omnipresente v3):** 
  - Server Socket.IO (namespace `/`) emite eventos: `NEW_APPOINTMENT`, `APPOINTMENT_UPDATED`, `APPOINTMENT_DELETED`.
  - **Frontend Listeners Optimizados (2026-02-08)**:
    - Ambos eventos `NEW_APPOINTMENT` y `APPOINTMENT_UPDATED` ahora ejecutan `calendarApi.refetchEvents()` 
    - Este método re-carga todos los eventos desde las sources configuradas (DB + Google Calendar blocks)
    - Garantiza sincronización total y consistencia en todas las sesiones activas
    - Elimina riesgo de duplicados o estados desincronizados del método manual anterior (`addEvent()`, `setProp()`)
  - **Auto-Sync Silencioso**: 
    - La sincronización con Google Calendar ocurre automáticamente al cargar `AgendaView`
    - No requiere intervención manual del usuario (botón "Sync" removido en v3 hito 2026-02-08)
    - Delay de 800ms post-sync garantiza que los writes en DB se completen antes del fetch
- **Urgencia y Triaje (Clinical Triage v1):**
  - Los pacientes ahora poseen un `urgency_level` (`low`, `medium`, `high`, `emergency`).
  - La UI de la agenda resalta automáticamente los turnos con urgencia `high` o superior mediante bordes y efectos pulsantes.
- **UUID Serialization Fix (Backend):**
  - Endpoints de actualización de estado (`PUT /admin/appointments/{id}/status`) ahora convierten UUID a string antes de JSON response
  - Eliminado error `TypeError: Object of type UUID is not JSON serializable`
- **Multi-Tenancy:** Soporte para múltiples consultorios/clínicas; datos aislados por `tenant_id`. La configuración por sede (idioma de UI, proveedor de calendario) se guarda en `tenants.config` y se expone vía GET/PATCH `/admin/settings/clinic` (`ui_language`: es|en|fr).
- **Sovereign Analytics Engine (v1 2026-02-08):**
  - **Propósito**: Consolidar métricas operativas y financieras en un dashboard centralizado.
  - **Lógica de Ingresos**: Basada estrictamente en asistencia confirmada (`attended` o `completed`).
  - **Eficiencia de IA**: Las "Conversaciones IA" se calculan como hilos únicos por paciente (`COUNT(DISTINCT from_number)`), no por volumen de mensajes individuales.
  - **Filtrado Dinámico**: Soporte nativo para rangos `weekly` (7 días) y `monthly` (30 días).
  - **Triage Monitoring**: Integración directa con el flujo de detección de urgencias IA.

### D. Sistema de Layout y Scroll (SaaS-style)

**Tecnología:** Flexbox + `min-h-0` + Overflow Isolation

**Arquitectura de Visualización:**
- **Layout Global Rígido:** El contenedor principal (`Layout.tsx`) utiliza `h-screen` y `overflow-hidden` para eliminar el scroll de la página completa, siguiendo el estándar **Sovereign Glass**.
- **Aislamiento de Scroll:** Cada vista maestra gestiona su propio desplazamiento interno mediante `flex-1 min-h-0 overflow-auto`.
- **ProfessionalsView (Vista Maestra):** Implementa un sistema de **Overflow Isolation** donde el grid fluye de forma independiente.
- **Mobile-First Evolution (Hito Agenda 2.0):**
    - **`MobileAgenda`**: Nueva capa de visualización vertical optimizada para pantallas pequeñas, activada automáticamente vía `@media` queries o JS detection.
    - **`DateStrip`**: Navegador de fechas horizontal táctil que permite cambiar el foco del calendario sin recargar la página.
- **Odontograma y Pantallas de Alta Densidad:** Utilizan el patrón de **Sub-Scrolling**, permitiendo que herramientas complejas mantengan sus controles visibles mientras los diagramas scrollean.
- **ChatsView Rígido:** Implementa una jerarquía flex con `min-h-0` que fuerza el scroll únicamente en el área de mensajes.

### E. Chat omnicanal (Chatwoot/YCloud Unificado)

**Objetivo:** Recibir y responder conversaciones de WhatsApp, Instagram y Facebook vía **Chatwoot** en la misma bandeja de Chats que YCloud (por teléfono).

**Nuevas Capacidades (Spec 23):**
- **Transcripción de Audio**: Chatwoot ahora transcribe notas de voz igual que YCloud.
- **AI Vision**: Ambos canales soportan envío de imágenes, analizadas por GPT-4o e inyectadas en el contexto del agente.

**Componentes:**
- **Webhook:** `POST /admin/chatwoot/webhook?access_token=...` (público). Valida tenant por token en tabla `credentials`; evento `message_created`: upsert en `chat_conversations`, INSERT en `chat_messages`, buffer atómico 16s (Redis) y disparo del agente por tenant (Vault: `get_agent_executable_for_tenant(tenant_id)` con OPENAI_API_KEY por tenant).
- **API UI:** `GET /admin/chats/summary` (filtro `channel`: whatsapp|instagram|facebook), `GET /admin/chats/{id}/messages`, `POST /admin/whatsapp/send`, `POST /admin/conversations/{id}/human-override`, `GET /admin/integrations/chatwoot/config` (URL webhook + token para Configuración).
- **Frontend:** ChatsView con lista unificada (sesiones YCloud + conversaciones Chatwoot), filtro por canal (Todos, WhatsApp, Instagram, Facebook), envío y human override; ConfigView con sección Chatwoot (URL + botón Copiar). Polling lista 10s, mensajes Chatwoot 3s.
- **Tablas:** `chat_conversations` (tenant_id, channel, provider, external_user_id, human_override_until, etc.), `credentials` (tenant_id, name, value), extensión de `chat_messages` (conversation_id, content_attributes, platform_metadata). Ver `docs/API_REFERENCE.md` (Chat omnicanal) y `docs/AUDIT_CHATWOOT_2025-02-13.md`.
- **Proxy de Medios (Spec 22)**: `/admin/chat/media/proxy` para servir adjuntos de forma segura sin exponer URLs de S3/Facebook expirables.

## 6. Paginación y Carga Incremental

Para optimizar el rendimiento en conversaciones extensas, Dentalogic utiliza un sistema de carga bajo demanda:
- **Backend (Admin API)**: Soporta parámetros `limit` y `offset` para consultas SQL (`LIMIT $2 OFFSET $3`).
- **Frontend (ChatsView)**:
    - Carga inicial: Últimos 50 mensajes.
    - Botón "Cargar más": Recupera bloques anteriores y los concatena al estado, manteniendo la posición visual.
    - Estado `hasMoreMessages`: Controla la disponibilidad de historial en el servidor.

### C. Frontend React (Puerto 5173 dev / 80 prod) - **Centro de Operaciones**

**Tecnología:** React 18 + TypeScript + Vite + Tailwind CSS + FullCalendar + Socket.IO client + Recharts

**Carpeta:** `frontend_react/`

**Rutas principales (App.tsx):** Rutas **públicas** (sin Layout ni ProtectedRoute): `/login` (LoginView), `/demo` (LandingView – landing de conversión con Probar app / Probar Agente IA / Iniciar sesión; única página accesible sin login junto con login). Rutas **protegidas** (dentro de Layout + ProtectedRoute): `/` (DashboardView), `/agenda` (AgendaView), `/pacientes` y `/pacientes/:id` (PatientsView, PatientDetail), `/chats` (ChatsView), `/analytics/professionals` (ProfessionalAnalyticsView, solo CEO), `/tratamientos` (TreatmentsView), `/perfil` (ProfileView), `/aprobaciones` (UserApprovalView – Personal Activo, modal detalle, Vincular a sede, Editar Perfil), `/sedes` (ClinicsView, solo CEO), `/configuracion` (ConfigView – selector de idioma). La ruta `/profesionales` redirige a `/aprobaciones`. El flujo de login demo: `/login?demo=1` prellena credenciales y muestra botón "Entrar a la demo" que ejecuta login y redirige al dashboard.

**Idiomas (i18n):** El selector de idioma (Español / English / Français) está en **Configuración** (solo CEO). Se persiste en `tenants.config.ui_language` vía GET/PATCH `/admin/settings/clinic`. `LanguageProvider` envuelve toda la app; todas las vistas y componentes compartidos usan `useTranslation()` y `t('clave')` con archivos `src/locales/es.json`, `en.json`, `fr.json`. El cambio de idioma aplica de inmediato a toda la plataforma.

**Vistas Principales:**
- **Landing (LandingView):** Página pública en `/demo` para campañas y leads: hero, beneficios, credenciales de prueba (colapsables), CTA "Probar app" (→ `/login?demo=1`), "Probar Agente IA" (WhatsApp con mensaje predefinido), "Iniciar sesión con mi cuenta" (→ `/login`). Diseño móvil-first y orientado a conversión; estética alineada con la plataforma (medical, glass, botones).
- **Agenda Inteligente:** Calendario interactivo con sincronización de Google Calendar; leyenda de origen (IA, Manual, GCal) y tooltips traducidos. **Filtro por profesional** en vistas semanal y mensual (CEO y secretaria pueden elegir profesional); **profesionales solo ven su propio calendario** (una columna en vista día, sin selector de profesional). Actualización en tiempo real vía Socket.IO.
- **Perfil 360° del Paciente:** Acceso a historias clínicas, antecedentes y notas de evolución.
- **Monitor de Triaje:** Alertas inmediatas cuando la IA detecta una urgencia grave.
- **Modales IA-Aware:** Los modales de edición (especialmente en Personal Activo / Profesionales) están sincronizados con la lógica de la IA, permitiendo configurar `working_hours` que el agente respeta estrictamente durante la reserva de turnos.

## 3. Base de Datos (PostgreSQL)

**Configuración por sede:** La tabla `tenants` incluye un campo JSONB `config` donde se guardan, entre otros: `ui_language` (es|en|fr) para el idioma de la plataforma, y `calendar_provider` ('local' | 'google') para el tipo de calendario de esa sede. El backend expone `ui_language` en GET/PATCH `/admin/settings/clinic`.

### Tablas Principales (Esquema Dental)

| Tabla | Función |
| :--- | :--- |
| **professionals** | Datos de los odontólogos y sus especialidades. |
| **patients** | Registro demográfico y antecedentes médicos (JSONB). |
| **clinical_records** | Evoluciones clínicas, diagnósticos y odontogramas. |
| **appointments** | Gestión de turnos, estados y sincronización GCalendar. |
| **accounting_transactions** | Liquidaciones y cobros de prestaciones. |
| **users** | Credenciales, roles y estado de aprobación. |
| **tenants** | Sedes/clínicas; `config` (JSONB) con `ui_language`, `calendar_provider`, etc. |
| **chat_messages** | Mensajes de chat por conversación; incluye `tenant_id` para aislamiento por sede; para Chatwoot: `conversation_id`, `content_attributes`, `platform_metadata`. |
| **chat_conversations** | Conversaciones omnicanal (Chatwoot/YCloud): tenant_id, channel, provider, external_user_id, human_override_until, etc. |
| **credentials** | Credenciales por tenant (Vault): OPENAI_API_KEY, WEBHOOK_ACCESS_TOKEN, CHATWOOT_*, YCLOUD_*, etc. |

### 3.2 Maintenance Robot (Self-Healing)
El sistema utiliza un **Robot de Mantenimiento** integrado en `orchestrator_service/db.py` que garantiza la integridad del esquema en cada arranque:
- **Foundation**: Si no existe la tabla `tenants`, aplica el esquema base completo.
- **Evolution Pipeline**: Una lista de parches (`patches`) en Python que ejecutan bloques `DO $$` para agregar columnas o tablas nuevas de forma idempotente y segura.
- **Resiliencia**: El motor SQL ignora comentarios y respeta bloques de código complejos, evitando errores de sintaxis comunes en despliegues automatizados.

## 4. Seguridad e Identidad (Auth Layer)

Dentalogic implementa una arquitectura de **Seguridad de Triple Capa**:

1.  **Capa de Identidad (JWT)**: Gestión de sesiones de usuario con tokens firmados (HS256). Define el rol (`ceo`, `professional`, `secretary`) y el `tenant_id`.
2.  **Capa de Infraestructura (X-Admin-Token)**: Las rutas administrativas críticas requieren un token estático (`INTERNAL_SECRET_KEY`) para prevenir accesos no autorizados incluso si la sesión del usuario es válida.
3.  **Capa de Gatekeeper (Aprobación)**: Todo registro nuevo entra en estado `pending`. Solo un usuario con rol `ceo` puede activar cuentas desde el panel de control.

## 5. Flujo de una Urgencia

---

## 5. Flujo de una Urgencia

1. **Paciente** envía audio: "Me duele mucho la muela, está hinchado".
2. **WhatsApp Service** transcribe vía Whisper.
3. **Orchestrator** recibe texto y ejecuta `triage_urgency()`.
4. **IA** clasifica como `high` (Urgencia) y sugiere turnos próximos.
5. **Platform UI** muestra una notificación visual roja al administrativo.
6. **Agente** responde: "Entiendo que es un dolor fuerte. Tengo un hueco hoy a las 16hs, ¿te sirve?".

---

*Documentación Dentalogic © 2026*
泛
