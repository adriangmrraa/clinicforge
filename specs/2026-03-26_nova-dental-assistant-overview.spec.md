# SPEC: Nova Dental Assistant — Arquitectura General

**Fecha**: 2026-03-26
**Proyecto**: ClinicForge
**Prioridad**: Alta
**Costo estimado**: ~$0.01/usuario/dia (GPT-4o-mini para analisis)

---

## 1. VISION

Nova es un asistente de voz inteligente integrado en ClinicForge, accesible como widget flotante en toda la plataforma. Permite al staff de la clinica (CEO, profesionales, secretarias) interactuar por voz o texto con el sistema completo: pacientes, turnos, tratamientos, facturacion, analytics y configuracion.

Nova cumple **dos propositos fundamentales**:

### 1.1 Onboarding dental

Guia a nuevas clinicas a traves de la configuracion inicial completa del sistema:
- Crear profesionales y asignar especialidades
- Configurar horarios de atencion y sedes
- Conectar WhatsApp (YCloud)
- Cargar tratamientos y tipos de consulta
- Configurar FAQs del chatbot de pacientes
- Configurar datos bancarios (CBU, alias, titular)

Nova convierte un proceso de setup complejo en una conversacion guiada paso a paso.

### 1.2 CEO multi-sede assistant

Un CEO gestiona **multiples clinicas/sedes**. Nova proporciona:
- **Vistas consolidadas**: metricas agregadas de todas las sedes en un solo lugar
- **Comparativas cross-sede**: ranking de sedes por facturacion, cancelaciones, pacientes nuevos, etc.
- **Operaciones per-sede**: ejecutar acciones en una sede especifica sin salir del contexto actual

### Casos de uso principales

| Rol | Ejemplo de uso |
|-----|---------------|
| **Profesional** | "Nova, quien es mi proximo paciente?" — mientras se lava las manos |
| **Profesional** | "Agenda un control para Maria Lopez el jueves a las 10" |
| **Profesional** | "Registra caries en pieza 36 superficie oclusal para el paciente actual" |
| **Secretaria** | "Cuantos turnos hay manana?" — sin abrir la agenda |
| **Secretaria** | "Busca al paciente con DNI 35.XXX.XXX" |
| **CEO** | "Como estuvo la semana en facturacion?" |
| **CEO** | "Cuantos pacientes nuevos tuvimos este mes?" |
| **CEO** | "Nova, quiero configurar una nueva sede" → inicia wizard de onboarding |
| **CEO** | "Como estuvieron las 3 sedes esta semana?" → reporte consolidado cross-sede |
| **CEO** | "Cual sede tuvo mas cancelaciones?" → comparativa cross-sede con ranking |
| **CEO** | "Cambiame a la sede Cordoba" → switch de contexto tenant via X-Tenant-ID |

### Diferencias con Nova (Platform AI Solutions)

| Aspecto | Platform AI (e-commerce) | ClinicForge (dental) |
|---------|--------------------------|---------------------|
| **Usuarios** | Duenos de tiendas online | Staff clinico (CEO, dentistas, secretarias) |
| **Entidades** | Productos, pedidos, canales | Pacientes, turnos, tratamientos, odontograma |
| **Tools** | CRUD productos, editar prompt, stock | CRUD pacientes, agendar turnos, registros clinicos |
| **Health checks** | Canales, productos, prompt | Turnos vacios, recordatorios, facturacion pendiente |
| **Daily analysis** | Conversaciones WhatsApp | Interacciones pacientes, cancelaciones, derivaciones |
| **Contexto** | Pagina actual del dashboard | Pagina + paciente seleccionado + turno en curso |
| **Compliance** | Terminos de servicio | Datos sensibles de salud (ley 25.326) |

---

## 2. ARQUITECTURA

```
Browser (React)                    Orchestrator (FastAPI)              OpenAI
    |                                    |                              |
    | 1. Click widget flotante           |                              |
    | 2. POST /admin/nova/session ------>|                              |
    |    {page, context}                 |                              |
    |<-- {session_id} ------------------|                              |
    |                                    |                              |
    | 3. WS /public/nova/realtime/{id} ->|                              |
    |    [audio PCM16 24kHz] ---------->|-- WS wss://api.openai.com -->|
    |                                    |     input_audio_buffer       |
    |                                    |                              |
    |<-- [audio PCM16 24kHz] -----------|<-- response.audio.delta -----|
    |<-- {transcript, tool_call} -------|<-- function_call_args.done --|
    |                                    |                              |
    |    [mic auto-muted]               |-- tool execution (SQL) ----->|
    |                                    |-- function_call_output ----->|
    |<-- [audio respuesta] -------------|<-- response.audio.delta -----|
```

### Componentes

| Componente | Archivo | Descripcion |
|-----------|---------|-------------|
| **Nova Widget (frontend)** | `frontend_react/src/components/NovaWidget.tsx` | Widget flotante con chat, salud, insights + selector de sede (CEO) |
| **Nova Routes (backend)** | `orchestrator_service/routes/nova_routes.py` | Endpoints: context, health-check, session, daily-analysis |
| **Nova WS Handler (backend)** | `orchestrator_service/main.py` | WebSocket bridge a OpenAI Realtime con tools |
| **Nova Daily Analysis** | `orchestrator_service/services/nova_daily_analysis.py` | Cron cada 12h, analiza interacciones con GPT-4o-mini |
| **nginx proxy** | `frontend_react/nginx.conf` | Proxy WS `/api/public/nova/realtime-ws/` |

### Mecanismos clave

- **X-Tenant-ID header**: El CEO puede cambiar de sede enviando este header en cada request de Nova. El backend valida que el CEO tenga acceso al tenant solicitado via `get_allowed_tenant_ids()`.
- **Consolidated queries**: Para reportes cross-sede, Nova ejecuta queries contra multiples `tenant_id` en paralelo y agrega los resultados antes de responder.
- **Onboarding state machine**: El progreso del wizard de onboarding se almacena en Redis con key `nova:onboarding:{tenant_id}`. Cada paso completado se marca y persiste, permitiendo retomar el setup en cualquier momento. Estados: `pending` → `professionals` → `hours` → `whatsapp` → `treatments` → `faqs` → `bank` → `completed`.

---

## 3. MULTI-SEDE ARCHITECTURE

### Flujo de acceso CEO

1. CEO hace login → recibe JWT con `default_tenant_id` (primera clinica creada)
2. Nova carga con el contexto del tenant default
3. CEO puede cambiar de sede via comando de voz ("Cambiame a sede Cordoba") o via dropdown en el widget
4. El cambio envia `X-Tenant-ID` header en todos los requests subsiguientes de Nova
5. Backend valida acceso via `get_allowed_tenant_ids()` antes de ejecutar cualquier tool

### Reglas de aislamiento

| Rol | Acceso multi-sede | Mecanismo |
|-----|-------------------|-----------|
| **CEO** | SI — todas las sedes vinculadas a su cuenta | `get_allowed_tenant_ids()` retorna lista de tenant_ids |
| **Professional** | NO — solo su tenant_id del JWT | `tenant_id` fijo del token, sin override posible |
| **Secretary** | NO — solo su tenant_id del JWT | `tenant_id` fijo del token, sin override posible |

### Implementacion en Nova

- **Widget**: muestra un dropdown selector de clinica/sede SOLO para usuarios con rol CEO. Staff no ve el selector.
- **Tools**: todos los tools de Nova aceptan un parametro opcional `tenant_id`. Si el usuario es CEO y envia `X-Tenant-ID`, el tool usa ese tenant. Si no, usa el `tenant_id` del JWT.
- **Consolidated tools**: tools especificos para CEO que iteran sobre `get_allowed_tenant_ids()` y agregan resultados (ej: `consolidated_weekly_report`, `cross_sede_comparison`).
- **Staff (prof/secretary)**: NUNCA ven otras clinicas. El parametro `tenant_id` override es ignorado para roles no-CEO.

---

## 4. FASES DE IMPLEMENTACION

| Fase | Entregable | Costo | Spec |
|------|-----------|-------|------|
| **Fase 0** | Onboarding: wizard guiado para nuevas clinicas (state machine Redis, 7 pasos, validaciones) | $0 | `nova-dental-onboarding.spec.md` |
| **Fase 1** | Backend: routes + WS handler + 20 tools + multi-sede tools para CEO | $0 (SQL) | `nova-dental-backend.spec.md` |
| **Fase 2** | Frontend: widget flotante + voz + chat + sede selector + onboarding UI | $0 | `nova-dental-frontend.spec.md` |
| **Fase 3** | Health check clinico + score + toast + consolidated multi-sede score para CEO | $0 (SQL) | `nova-dental-health.spec.md` |
| **Fase 4** | Daily analysis + insights + sugerencias + cross-sede insights comparativos | ~$0.003/clinica/dia | `nova-dental-analysis.spec.md` |

---

## 5. SEGURIDAD Y COMPLIANCE

### Datos sensibles de salud

- **NUNCA** loguear contenido de pacientes en texto plano
- Audio NO se almacena — se procesa en streaming y se descarta
- Transcripciones se guardan solo en Redis con TTL 1h (contexto de sesion)
- OpenAI Realtime API: datos NO usados para training (segun TOS enterprise)
- Tool results con datos clinicos se envian solo al OpenAI session, no se persisten
- Health-check y daily-analysis NO incluyen datos de pacientes individuales

### Control de acceso

- Nova respeta los roles existentes de ClinicForge:
  - **CEO**: acceso total (analytics, configuracion, multi-sede)
  - **Professional**: solo sus pacientes, sus turnos, registros clinicos
  - **Secretary**: pacientes, turnos, sin acceso a registros clinicos detallados
- Cada tool valida `current_user.role` antes de ejecutar
- Tenant isolation: todas las queries filtran por `tenant_id`

### Acceso cross-tenant (CEO)

- **CEO cross-tenant access**: validado via `get_allowed_tenant_ids()` — retorna la lista de tenants a los que el CEO tiene acceso
- **Actualmente** el CEO ve TODOS los tenants (no hay filtro de ownership) — Nova respeta este patron existente
- **Professional/Secretary**: estrictamente bloqueados a su `tenant_id` del JWT. El override via `X-Tenant-ID` es rechazado para estos roles
- **Datos de onboarding**: no involucran datos de pacientes, solo configuracion de la clinica (profesionales, horarios, tratamientos, datos bancarios)

### Rate limiting

- Max 1 sesion de voz simultanea por usuario
- Max 5 minutos por sesion (renovable)
- Max 50 tool calls por sesion

---

## 6. DEPENDENCIAS

### Existentes en ClinicForge (no requieren cambios)

- PostgreSQL + SQLAlchemy (patients, appointments, clinical_records, etc.)
- Redis (buffer system, cache)
- FastAPI + WebSocket support
- Socket.IO (para notificaciones real-time)
- JWT + X-Admin-Token auth
- LangChain agent (tools existentes: check_availability, book_appointment, etc.)

### Nuevas dependencias

| Dependencia | Uso | Ya en el proyecto? |
|-------------|-----|-------------------|
| `websockets` (Python) | Bridge a OpenAI Realtime | Agregar |
| OpenAI Realtime API | Voz bidireccional | Requiere API key (ya existe OPENAI_API_KEY) |
| `lucide-react` icons adicionales | Widget UI | Ya instalado |

### Variables de entorno nuevas

```env
# Ya existente
OPENAI_API_KEY=sk-...

# Nueva (opcional, para override)
NOVA_VOICE=coral          # Voz de Nova (coral, alloy, echo, fable, onyx, shimmer)
NOVA_MAX_SESSION_SECONDS=300  # Max duracion sesion voz
NOVA_DAILY_ANALYSIS_ENABLED=true  # Habilitar cron de analisis
```

---

## 7. ESTIMACION

| Fase | Archivos nuevos | Archivos modificados | Complejidad |
|------|----------------|---------------------|-------------|
| Fase 0 (Onboarding) | `nova_onboarding.py`, `OnboardingWizard.tsx` | `nova_routes.py`, `NovaWidget.tsx` | Media |
| Fase 1 (Backend) | `nova_routes.py`, `nova_ws_handler.py` | `main.py` (registrar rutas + WS) | Media-Alta |
| Fase 2 (Frontend) | `NovaWidget.tsx`, `SedeSelector.tsx` | `Layout.tsx`, `nginx.conf` | Media |
| Fase 3 (Health) | — (inline en nova_routes) | — | Media |
| Fase 4 (Analysis) | `nova_daily_analysis.py` | `main.py` (registrar cron) | Baja |

---

## 8. VERIFICACION FINAL

1. Widget flotante visible en todas las paginas (excepto login/anamnesis publica)
2. Click → se abre panel con 3 tabs (Chat, Salud, Insights)
3. Hablar por mic → Nova responde por voz + texto
4. "Quien es mi proximo paciente?" → Nova consulta DB y responde
5. "Agenda turno para Maria Lopez manana a las 10" → turno creado
6. Tab Salud → score + checks priorizados
7. Tab Insights → resumen diario con sugerencias
8. Toast al entrar si hay alertas criticas
9. Roles respetados (profesional no ve facturacion global)
10. Audio sin eco, sin superposicion, sin corte prematuro
11. CEO: dropdown de sede visible, cambio de sede funciona via voz y click
12. CEO: "Como estuvieron las 3 sedes?" → reporte consolidado con datos de cada sede
13. CEO: "Cual sede tuvo mas cancelaciones?" → ranking comparativo
14. Onboarding: nueva clinica → wizard guiado paso a paso hasta completar setup
15. Onboarding: retomar wizard incompleto → continua desde el ultimo paso completado
16. Staff (prof/secretaria): NO ve selector de sede ni datos de otras clinicas
