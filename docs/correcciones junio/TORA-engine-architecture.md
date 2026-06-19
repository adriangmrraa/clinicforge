# TORA Engine Architecture: Single-Agent vs Multi-Agent en ClinicForge

> **Versión:** v8.3 — Parity Complete
> **Propósito:** Documentación técnica viva para desarrolladores que mantienen o extienden el sistema de agentes IA de ClinicForge.

---

## Tabla de Contenidos

1. [Arquitectura General del Sistema](#1-arquitectura-general-del-sistema)
2. [Solo-Agent (TORA Legacy)](#2-solo-agent-tora-legacy)
3. [Multi-Agent (LangGraph)](#3-multi-agent-langgraph)
4. [Comparativa Detallada: Solo vs Multi](#4-comparativa-detallada-solo-vs-multi)
5. [Historia de los Cambios](#5-historia-de-los-cambios)
6. [SDD Workflow Usado](#6-sdd-workflow-usado)
7. [Referencia Rápida para el Desarrollador](#7-referencia-rápida-para-el-desarrollador)

---

## 1. Arquitectura General del Sistema

### 1.1 ¿Qué es TORA?

**TORA** (el nombre del bot, configurable por clínica via `tenants.bot_name`) es el sistema de agente conversacional de ClinicForge. Es un asistente virtual odontológico multi-tenant que:

- Atiende pacientes por **WhatsApp** (Chatwoot / YCloud), **Instagram**, **Facebook** y **Telegram**
- Agrupa turnos, responde preguntas frecuentes, hace triaje de urgencias, gestiona pagos y cobros
- Opera 100% en español rioplatense con voseo
- Está desplegado como un monolito FastAPI + LangChain + PostgreSQL

```
┌──────────────────────────────────────────────────────────────────┐
│                        USUARIOS                                  │
│   WhatsApp ─── Chatwoot/YCloud ──┐                               │
│   Instagram ──────────────────────┤                               │
│   Facebook ───────────────────────┤    ┌──────────────────────┐  │
│   Telegram ───────────────────────┼───►│   BFF Service        │  │
│   Web App ────────────────────────┘    │   (Express, :3000)   │  │
│                                        └──────────┬───────────┘  │
│                                                   │              │
│                                        ┌──────────▼───────────┐  │
│                                        │   Orchestrator        │  │
│                                        │   Service             │  │
│                                        │   (FastAPI, :8000)    │  │
│                                        │                      │  │
│                                        │   ┌──────────────┐   │  │
│                                        │   │  Agent Engine │   │  │
│                                        │   │ (Solo/Multi)  │   │  │
│                                        │   └──────┬───────┘   │  │
│                                        │          │           │  │
│                                        │   ┌──────▼───────┐   │  │
│                                        │   │  Tools        │   │  │
│                                        │   │ (30+)        │   │  │
│                                        │   └──────────────┘   │  │
│                                        └──────────────────────┘  │
│                                                   │              │
│                                        ┌──────────▼───────────┐  │
│                                        │   PostgreSQL          │  │
│                                        │   + Redis             │  │
│                                        └──────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 Canales de Atención

| Canal | Middleware | ID del Paciente |
|-------|-----------|-----------------|
| WhatsApp | Chatwoot o YCloud | `phone_number` (normalizado a dígitos) |
| Instagram | Chatwoot | `instagram_psid` o `external_ids->>'instagram'` |
| Facebook | Chatwoot | `facebook_psid` o `external_ids->>'facebook'` |
| Telegram | Bot API directo | `phone_number` |
| Web App | Axios (frontend React) | JWT + `X-Admin-Token` |

### 1.3 BFF Service

El **Backend for Frontend** (`bff_service/`) es un proxy Express en el puerto 3000 que:

- Media entre el frontend React y el Orchestrator FastAPI
- Maneja CORS, rate limiting (express-rate-limit) y timeouts de 60s
- Forwardea rutas al puerto 8000 del Orchestrator
- Sirve como punto único de entrada para el frontend

```typescript
// bff_service/src/index.ts (conceptual)
app.use('/api', proxy({ target: 'http://orchestrator:8000', timeout: 60000 }));
```

### 1.4 Orchestrator Service

El **Orchestrator** (`orchestrator_service/`) es el cerebro del sistema:

- **FastAPI** con 30+ endpoints agrupados en `admin_routes.py`, `auth_routes.py`, `public_routes.py`
- **LangChain** para el agente conversacional (tanto solo como multi-agent)
- **PostgreSQL** con 30+ tablas SQLAlchemy (`models.py`), migraciones Alembic
- **Redis** para caché, working state, cola de mensajes y pubsub
- **WebSocket / Socket.IO** para sincronización en tiempo real de la agenda
- **Multi-tenancy estricto**: toda query filtra por `tenant_id`

---

## 2. Solo-Agent (TORA Legacy)

### 2.1 ¿Qué es?

El **solo-agent** es la implementación original y actualmente activa en producción (`ai_engine_mode="solo"`). Es un único agente LangChain que hace TODO: desde el saludo inicial hasta el agendamiento de turnos, triaje de urgencias y gestión de pagos.

### 2.2 Flujo Completo

```
WhatsApp ──► process_buffer_task() ──► SoloEngine ──► get_agent_executable_for_tenant()
                │                                               │
                ├─ Resuelve paciente (phone + DNI + nombre)     │
                ├─ Carga datos del tenant (FAQs, horarios, OS) │
                ├─ Construye patient_context (19+ campos)       │
                └─ Llama a build_system_prompt() ◄──────────────┘
                                                    │
                                                    ▼
                                             build_system_prompt()
                                             (1575 líneas)
                                                    │
                                                    ▼
                                           OpenAI LLM + Tools
                                                    │
                                                    ▼
                                             response_sender()
                                             → WhatsApp
```

**Punto de entrada:** `services/buffer_task.py:process_buffer_task()`

```python
# buffer_task.py — flujo reducido
async def process_buffer_task(tenant_id, conversation_id, ...):
    # 1. Resuelve paciente por phone, DNI, nombre (3 intentos)
    # 2. Carga tenant_row (50+ columnas de tenants)
    # 3. Carga FAQs, OS, treatment_types, derivation_rules
    # 4. Construye patient_context (19 campos de identity + turns)
    # 5. Ejecuta get_agent_executable_for_tenant(tenant_id)
    # 6. Invoca executor.ainvoke({input, chat_history, system_prompt})
    # 7. Post-procesa errores ([BOOK_ERROR:...], false system errors)
    # 8. Envía respuesta por Chatwoot / YCloud
```

### 2.3 Cómo se Construye el Prompt (build_system_prompt)

La función `build_system_prompt()` en `main.py` (línea ~10520, ~1575 líneas) construye UN SOLO string que contiene TODO:

```
build_system_prompt(
    clinic_name, current_time, response_language,
    hours_start, hours_end,
    ad_context,           # Contexto de Meta Ads (para campañas)
    patient_context,      # 19 campos de identidad + turnos
    clinic_address,       # Dirección + Maps URL
    clinic_working_hours, # Horarios por día (JSONB multi-sede)
    faqs,                 # FAQS del tenant (con RAG opcional)
    patient_status,       # new_lead / patient_no_appointment / patient_with_appointment
    consultation_price,   # Valor de consulta
    sede_info,            # Sede resuelta para hoy
    anamnesis_url,        # Link a ficha médica
    bank_cbu, alias, holder,   # Datos bancarios
    upcoming_holidays,     # Próximos feriados
    insurance_providers,   # Obras sociales
    derivation_rules,      # Reglas de derivación a profesionales
    specialty_pitch,       # Template de posicionamiento
    professional_name,     # Nombre del profesional lead
    bot_name="TORA",       # Nombre del bot
    intent_tags,           # Tags de intención (implant, media, payment)
    treatment_types,       # Tipos de tratamiento activos
    payment_methods,       # Métodos de pago
    financing_*,           # Financiación
    special_conditions_block,  # Condiciones especiales (embarazo, pediatría)
    support_policy_block,  # Política de atención y quejas
    channel="whatsapp",    # Canal (controla anti-markdown)
)
```

El prompt resultante incluye:

| Sección | Líneas Aprox | Contenido |
|---------|-------------|-----------|
| Identidad del profesional | ~50 | Nombre, rol, especialidad |
| Instrucciones de idioma | ~10 | Español rioplatense, voseo |
| Contexto de anuncio (Ads) | ~30 | Si viene de campaña Meta |
| **Contexto del paciente** | ~200 | 19 campos de identidad + reglas de uso |
| Anti-markdown | ~50 | Reglas de formato para WhatsApp |
| Horarios | ~30 | Working hours + multi-sede |
| FAQs | ~200 | Preguntas frecuentes del tenant |
| Precio de consulta | ~50 | Formato de presentación obligatorio |
| Feriados | ~80 | Próximos feriados + bloqueos |
| Obras sociales | ~150 | Proveedores activos + coberturas |
| Reglas de derivación | ~80 | Derivación a profesionales específicos |
| Condiciones especiales | ~80 | Embarazo, pediatría, alto riesgo |
| Formas de pago | ~80 | Métodos, cuotas, descuentos |
| Datos bancarios | ~30 | CBU, alias, titular |
| Política de atención | ~60 | Quejas y escalación |
| **Reglas de comportamiento** | ~400 | ~100 secciones inline de reglas |
| Tools definitions | ~200 | Definiciones inline de tools |

### 2.4 Routing (No Existe)

En el solo-agent NO hay routing. Un único agente recibe TODO el prompt y decide qué hacer. No hay separación de concerns — el mismo agente saluda, agenda turnos, hace triaje, cobra y gestiona quejas.

### 2.5 Fortalezas

- ✅ **Battle-tested en producción**: miles de conversaciones reales
- ✅ **Contexto denso**: el agente ve TODO de una vez — decisiones más informadas
- ✅ **Ejemplos inline (few-shot)**: ~200 líneas de ejemplos de comportamiento
- ✅ **Maduro**: cientos de bugs corregidos, edge cases cubiertos
- ✅ **Simple de operar**: un solo deployment, una sola cosa que monitorear

### 2.6 Debilidades

- ❌ **Monolítico**: tocar una regla implica re-leer 1575 líneas de prompt
- ❌ **Costoso**: cada turno envía todo el contexto (incluyendo secciones irrelevantes)
- ❌ **Un solo agente para todo**: no hay especialización — el "agente de booking" tiene que saber de triaje y viceversa
- ❌ **Difícil de mantener**: agregar una funcionalidad nueva requiere entender el prompt COMPLETO
- ❌ **Sin aislamiento**: un bug en una regla de pricing puede afectar el booking

---

## 3. Multi-Agent (LangGraph)

### 3.1 ¿Qué es?

El **multi-agent** es la nueva arquitectura (actualmente en `ai_engine_mode="solo"` — NUNCA ejecutado en producción). Reemplaza el monolito por un **supervisor que rutea a especialistas dedicados**, cada uno con su propio subset de tools y prompt.

### 3.2 Flujo Completo

```
WhatsApp ──► process_buffer_task() ──► MultiAgentEngine ──► graph.run_turn()
                │                                               │
                ├─ Resuelve paciente (igual que solo)            │
                ├─ Carga datos del tenant                        │
                ├─ Construye patient_context                     │
                └─ Crea TurnContext ──────────────────────────────┘
                                                                 │
                                                                 ▼
                                                          graph.run_turn()
                                                                 │
                    ┌────────────────────────────────────────────┐│
                    │  1. Load patient_context (asyncio.gather)   ││
                    │  2. Build tenant_context blocks (parallel) ││
                    │  3. Resolve tenant model config            ││
                    │  4. Build AgentState                       ││
                    │  5. Supervisor.route(state)                ││
                    │  6. AGENTS[agent].run(state)               ││
                    │  7. _log_turn()                            ││
                    └────────────────────────────────────────────┘│
                                                                 │
                                                                 ▼
                          ┌─────────────────┐
                          │   Supervisor     │
                          │  (deterministic  │
                          │   + LLM fallback)│
                          └────────┬────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
             ┌──────────┐  ┌──────────┐  ┌──────────┐
             │Reception  │  │ Booking  │  │ Triage   │
             │Agent      │  │ Agent    │  │ Agent    │
             ├──────────┤  ├──────────┤  ├──────────┤
             │Saludo,   │  │Turnos,   │  │Urgencias,│
             │Preguntas │  │Cancel,   │  │Derivación│
             │generales │  │Reprogram │  │humana    │
             └──────────┘  └──────────┘  └──────────┘
                    │              │              │
                    ▼              ▼              ▼
             ┌──────────┐  ┌──────────┐  ┌──────────┐
             │ Billing  │  │Anamnesis │  │ Handoff  │
             │ Agent    │  │ Agent    │  │ Agent    │
             ├──────────┤  ├──────────┤  ├──────────┤
             │Pagos, OS│  │Ficha     │  │Quejas,   │
             │Cuotas   │  │médica    │  │Escalación│
             └──────────┘  └──────────┘  └──────────┘
```

**Punto de entrada:** `agents/graph.py:run_turn()`

```python
# graph.py — flujo reducido
async def run_turn(ctx: TurnContext) -> TurnResult:
    # 1. Load patient profile (paralelo: 8 queries asíncronas)
    profile, chat_history = await _load_patient_context(...)

    # 2. Resolve tenant model (system_config.OPENAI_MODEL)
    model_config = await resolve_tenant_model(ctx.tenant_id)

    # 3. Build tenant context blocks (paralelo: 7 fetches)
    tenant_context = await build_tenant_context_blocks(pool, tenant_id, ...)

    # 4. Build AgentState con todo
    state = AgentState(tenant_id, phone, profile, model_config, tenant_context, ...)

    # 5. Supervisor routea al especialista
    next_agent = await _supervisor.route(state)  # "booking" | "triage" | etc.

    # 6. Ejecuta el especialista
    agent = AGENTS[next_agent]
    state = await agent.run(state)

    # 7. Log + return
    await _log_turn(state, next_agent, duration_ms, model_used)
    return TurnResult(output=state["agent_output"], agent_used=next_agent, ...)
```

### 3.3 Los 6 Agentes Especialistas

#### SupervisorAgent (`agents/supervisor.py`)

El **router** — decide qué especialista maneja cada mensaje. Usa **reglas determinísticas** primero (regex patterns) y **LLM fallback** cuando las reglas no alcanzan.

```python
# Jerarquía de routing (orden estricto):
# 1. human_override activo → handoff
# 2. SLOT_LOCKED state → booking
# 3. DNI / documento detectado → booking
# 4. EMERGENCY_PATTERNS → triage
# 5. BILLING_PATTERNS → billing
# 6. ANAMNESIS_PATTERNS → anamnesis
# 7. HANDOFF_PATTERNS → handoff
# 8. BOOKING_PATTERNS → booking
# 9. GREETING_PATTERNS → reception
# 10. Fallback → LLM (lee prompts/supervisor.md)
```

#### ReceptionAgent — "La primera voz"

- **Rol:** Saludo diferenciado, preguntas generales, detección de intención
- **Tools:** `list_professionals`, `list_services`
- **Prompt:** ~80 líneas (rol + reglas + tono)
- **NO hace:** booking, triaje, billing, anamnesis

#### BookingAgent — "Gestión de turnos"

- **Rol:** TODO el ciclo de turnos: disponibilidad, confirmación, booking, cancelación, reprogramación
- **Tools:** `check_availability`, `confirm_slot`, `book_appointment`, `create_patient`, `list_my_appointments`, `cancel_appointment`, `reschedule_appointment`, `check_insurance_coverage`, `list_services`, `confirm_appointment`
- **Prompt:** ~260 líneas (máquina de estados formal PASO 1-10)
- **Máquina de estados:** OFRECER → CONFIRMAR → BOOKEAR

#### TriageAgent — "Seguridad del paciente"

- **Rol:** Evaluar urgencia de síntomas, detectar emergencias, aplicar política clínica
- **Tools:** `triage_urgency`, `derivhumano`
- **Prompt:** ~80 líneas
- **NO hace:** diagnosticar, recetar, agendar

#### BillingAgent — "Cobros y cobertura"

- **Rol:** Precios, obras sociales, cuotas, financiación, verificación de comprobantes
- **Tools:** `verify_payment_receipt`
- **Prompt:** ~100 líneas
- **NO hace:** booking, triaje clínico

#### AnamnesisAgent — "Historia clínica"

- **Rol:** Recolectar ficha médica: alergias, medicación, condiciones preexistentes
- **Tools:** `get_patient_anamnesis`, `save_patient_anamnesis`, `save_patient_email`
- **Prompt:** ~70 líneas
- **NO hace:** interpretar datos médicos, diagnosticar

#### HandoffAgent — "Escalación humana"

- **Rol:** Último eslabón antes de humano. Protocolo graduado de quejas (Nivel 1-2-3)
- **Tools:** `derivhumano`
- **Prompt:** ~100 líneas
- **NUNCA:** inventa compensaciones, negocia fuera de la política

### 3.4 Cómo se Ensambla el Prompt de Cada Especialista

La función `_with_tenant_blocks()` en `specialists.py` arma el prompt final:

```
┌────────────────────────────────────────────────────────────────┐
│  SOCIAL PREAMBLE (si IG/FB)                                    │
│  "Sos el equipo de {clinic} en Instagram..."                   │
├────────────────────────────────────────────────────────────────┤
│  CONTEXTO DEL PACIENTE (19 campos)                             │
│  _inject_patient_context(state)                                │
│  • Nombre, DNI, Email, Teléfono                                │
│  • Próximo turno, Último turno                                 │
│  • Profesional asignado                                        │
│  • Plan de tratamiento activo                                  │
│  • Familiares a cargo                                          │
│  • Hijos/menores vinculados                                    │
│  • Memorias del paciente (RAG)                                 │
├────────────────────────────────────────────────────────────────┤
│  SHARED PREAMBLE (~250 líneas, 25 secciones)                   │
│  _build_shared_preamble(state)                                 │
│  • PROHIBICIONES (16 reglas)                                   │
│  • REGLA CERO — Avanzar sin pedir permiso                      │
│  • F1-F10 Flujos emocionales                                   │
│  • Post-booking, No-elección, Re-intento, Fallback             │
│  • Anti-markdown, Anti-hallucination, Anti-loop                │
│  • Pacientes existentes, Multi-tratamiento                     │
│  • Derivación empática, Reactivación tras override             │
├────────────────────────────────────────────────────────────────┤
│  SPECIALIST BASE PROMPT                                        │
│  (cada agente tiene el suyo: 70-260 líneas)                    │
├────────────────────────────────────────────────────────────────┤
│  TENANT BLOCKS (whitelisted por especialista)                  │
│  select_blocks_for_specialist(state, "booking")                │
│  • Cada especialista ve SOLO los bloques que necesita          │
│  • Reception: clinic_basics + faqs + holidays                  │
│  • Booking: clinic_basics + insurance + holidays + derivation  │
│  • Triage: clinic_basics + special_conditions                  │
│  • Billing: clinic_basics + insurance + payment + bank         │
│  • Anamnesis: clinic_basics + special_conditions               │
│  • Handoff: clinic_basics + support_policy                     │
├────────────────────────────────────────────────────────────────┤
│  OPERATIONAL RULES (temporales/estratégicas desde DB)          │
└────────────────────────────────────────────────────────────────┘
```

### 3.5 El Toggle `ai_engine_mode`

Está en `services/engine_router.py`:

```python
# Cada tenant tiene un campo ai_engine_mode en la tabla 'tenants':
#   'solo'  → usa SoloEngine (TORA legacy — PRODUCCIÓN)
#   'multi' → usa MultiAgentEngine (nuevo — NUNCA en producción)

# Cache con TTL de 60s
# Circuit breaker: 3 fallos en 60s → fallback a solo por 5 min
# Redis pubsub para invalidación cross-process

engine_router = EngineRouter()  # Singleton

async def get_engine_for_tenant(tenant_id: int) -> Engine:
    mode = await engine_router._get_mode(tenant_id)  # cache + DB
    if mode == "multi":
        return MultiAgentEngine()
    return SoloEngine()
```

El switch se hace desde la UI de admin (PATCH `/admin/settings/clinic` → cambia `ai_engine_mode` en la DB).

### 3.6 Patient Context (Compartido)

`services/patient_context.py` — usado por AMBOS motores:

```python
class PatientProfile:
    name: str | None              # Nombre del paciente
    dni: str | None               # DNI
    email: str | None             # Email
    is_new_lead: bool             # ¿Es nuevo?
    phone_number: str | None      # CE1 — Teléfono (si no es SIN-TEL)
    assigned_professional: dict   # CE2 — {id, name}
    next_appointment: dict        # CE3 — {treatment, professional, date_time}
    last_appointment: dict        # CE4 — {treatment, professional, date_time, days_since}
    treatment_plan: dict          # CE5 — {id, name, approved_total, paid, pending}
    family_members: list[dict]    # CE6 — Familiares
    children_dependents: list[dict] # CE7 — Hijos/menores
    visit_count: int              # CE8 — Cantidad de visitas
    anamnesis_status: dict        # CE9 — {completed, url}
    birth_date: str | None        # CE11 — Fecha de nacimiento
    patient_memories: str | None  # RAG — Memorias semánticas
    medical_history: dict         # Historia clínica (alergias, condiciones)
```

Se carga con `asyncio.gather()` — 8 queries independientes en paralelo.

### 3.7 Tenant Context Blocks

`agents/tenant_context.py` — construye los bloques configurables por clínica UNA VEZ por turno:

```
ALL_BLOCK_KEYS = (
    "clinic_basics",           # Identidad del bot + clínica
    "bot_name_raw",            # Nombre del bot para interpolación
    "insurance_section",       # Obras sociales activas
    "payment_section",         # Formas de pago + financiación
    "special_conditions_block", # Condiciones especiales (embarazo, pediatría)
    "support_policy_block",     # Política de atención y quejas
    "derivation_rules_section", # Reglas de derivación a profesionales
    "holidays_section",        # Próximos feriados
    "faqs_section",            # FAQs con RAG semántico
    "bank_info",               # Datos bancarios
    "sede_info",               # Sede del día (dict)
    "sede_info_text",          # Sede del día (string)
)
```

### 3.8 Engram / Patient Memory

`services/patient_memory.py` — sistema de memoria persistente con RAG semántico:

- Almacena memorias en tabla `patient_memories` (PostgreSQL)
- Extrae memorias de CADA turno de conversación usando GPT-4o-mini
- Compacción periódica: mergea memorias viejas para mantener el prompt liviano
- Búsqueda semántica: recupera las memorias más relevantes para el contexto actual
- Multi-canal: funciona con WhatsApp (phone), Instagram (PSID), Facebook (PSID)

---

## 4. Comparativa Detallada: Solo vs Multi

| Aspecto | Solo-Agent (TORA Legacy) | Multi-Agent (LangGraph) |
|---------|--------------------------|------------------------|
| **Estructura del prompt** | 1 monolito de ~1575 líneas | Shared preamble (250) + contexto paciente (80-120) + specialist prompt (70-260) + tenant blocks |
| **Routing** | Inexistente — un agente hace TODO | Supervisor determinístico (regex) + LLM fallback → 6 especialistas |
| **Tools por agente** | 30+ tools definidas inline | Cada especialista tiene SOLO las tools que necesita (3-10 cada uno) |
| **Contexto de paciente** | 19 campos inline en el prompt | 19 campos desde PatientProfile (misma fuente, mismo formato) |
| **Reglas de comportamiento** | ~100 secciones inline, mezcladas | 25 secciones en shared preamble + reglas específicas en cada specialist |
| **Ejemplos inline (few-shot)** | ~200 líneas | Ninguno (depende del prompt + fine-tuning del modelo) |
| **Tenant blocks** | Todos juntos, sin filtro | Filtrados por especialista (solo ve lo que necesita) |
| **Mantenibilidad** | ❌ Tocar una regla = leer 1575 líneas | ✅ Cada agente es un archivo independiente |
| **Costo por turno** | Más alto (envía todo el contexto siempre) | Más bajo (solo envía los bloques relevantes al especialista) |
| **Aislamiento de fallos** | ❌ Un bug en pricing afecta booking | ✅ Cada agente es independiente |
| **Escalabilidad** | ❌ Un agente para todo | ✅ Nuevos especialistas se agregan sin tocar los existentes |
| **Estado en producción** | ✅ **Activo** (ai_engine_mode="solo") | ⏸ Modo "solo" — **nunca ejecutado en producción** |
| **Cobertura de tests** | ~160 tests de paridad (validan que multi comporte igual que solo) | ~160 tests + asserts de string |

### 4.1 Diferencias Clave en la Arquitectura de Prompts

**Solo-agent:**
```python
# Un solo prompt con TODO mezclado
prompt = f"""
ROL: Sos TORA, asistente de {clinic_name}
REGLAS: ... (400 líneas)
CONTEXTO PACIENTE: ... (200 líneas)
TOOLS: ...
FAQS: ...
HORARIOS: ...
OBRAS SOCIALES: ...
...
"""
```

**Multi-agent:**
```python
# Cada especialista recibe SOLO lo que necesita
# 1. Shared preamble (todos ven lo mismo)
preamble = _build_shared_preamble(state)  # 250 líneas, 25 secciones

# 2. Contexto del paciente
patient_ctx = _inject_patient_context(state)  # 19 campos formateados

# 3. Base prompt del especialista
base = BookingAgent._get_prompt()  # 260 líneas específicas de booking

# 4. Tenant blocks filtrados
blocks = select_blocks_for_specialist(state, "booking")
# → solo clinic_basics + insurance + holidays + derivation + sede

# 5. Ensamblado final
prompt = f"{preamble}\n\n{patient_ctx}\n\n---\n\n{base}\n\n{blocks}"
```

### 4.2 Schema de Datos Comparativo

| Componente | Solo | Multi | Dónde se define |
|------------|------|-------|-----------------|
| Patient Context | En buffer_task (~400 líneas de SQL + formato) | PatientContext.load() con asyncio.gather | `services/patient_context.py` |
| Tenant Context | En buffer_task (queries secuenciales + formateo inline) | build_tenant_context_blocks() parallel | `agents/tenant_context.py` |
| System Prompt | build_system_prompt() (~1575 líneas) | _with_tenant_blocks() (~80 líneas de lógica de ensamblado) | `main.py` vs `agents/specialists.py` |
| Engine Dispatch | Llamada directa a get_agent_executable() | EngineRouter con cache + circuit breaker | `services/engine_router.py` |
| Tools Binding | En el AgentExecutor principal | Cada especialista llama _get_tools() propio | `agents/specialists.py` |
| Audit Log | No hay (solo chat_messages) | agent_turn_log con tools_called + model + duration | `agents/graph.py:_log_turn()` |

---

## 5. Historia de los Cambios

### Phase 1 — Bug Fixes + F2 Protocol Port
- Fix de `NameError` en producción
- Port del protocolo F2 (urgencia/dolor) del prompt legacy al multi-agent
- Corrección de reglas de derivación empática

### Phase 2 — `multi-agent-solo-parity` (5 Critical Gaps)
- **5 gaps críticos cerrados:** PROHIBICIONES, F2 M1-M3, REGLA CERO, Post-Booking, RE-INTENTO/FALLBACK
- **+300 líneas de shared preamble**
- Se unificaron las 16 reglas de PROHIBICIÓN entre ambos motores
- Se agregaron los flujos emocionales F1-F10 completos

### Phase 3 — `multi-agent-parity-v2` (10 Gaps Finales)
- **10 gaps cerrados:** GAP-1 a GAP-10
- **+92 líneas de preamble**
- **127 tests** de paridad (asserts de string, sin mocks, sin LLM)
- Cobertura completa de: No-elección, Fallback inteligente, Sin disponibilidad cercana, Regla post-booking, Seguimiento post-atención

### Phase 4 — `context-engineering-parity` (11 Campos de Contexto)
- **11 campos de contexto de paciente portados** del solo al multi:
  - CE1: Teléfono (phone_number)
  - CE2: Profesional asignado
  - CE3: Próximo turno (con nombres resueltos)
  - CE4: Último turno (con days_since + estado)
  - CE5: Plan de tratamiento activo (con pagos)
  - CE6: Familiares y memorias RAG
  - CE7: Hijos/menores vinculados
  - CE8: Visit count
  - CE9: Estado de anamnesis
  - CE10: Lead context formateado
  - CE11: Fecha de nacimiento
- **+155 líneas en PatientContext**, **+87 en el formatter**, **+150 tests**
- **160 tests total** de paridad

### Estado Actual
- **Solo-agent:** Producción estable (ai_engine_mode="solo")
- **Multi-agent:** Parity completa con solo-agent. Bloqueado en modo "solo". Listo para prueba en producción cuando se haga el switch.
- **Engine Router:** Operativo con cache, circuit breaker y fallback automático

---

## 6. SDD Workflow Usado

Todo el desarrollo del multi-agent se gestionó con **Spec-Driven Development (SDD)**:

```
proposal → spec → design → tasks → apply → verify → archive
```

### Ciclo SDD por cada phase:

1. **Proposal:** Definición de alcance, objetivos, riesgos
2. **Spec:** Especificación detallada con requisitos funcionales y no funcionales
3. **Design:** Arquitectura técnica, diagramas, decisiones
4. **Tasks:** Descomposición en tareas atómicas (con review workload forecast)
5. **Apply:** Implementación por sub-agentes (sdd-apply)
6. **Verify:** Tests de aserción de strings (160 tests) — sin mocks, sin LLM
7. **Archive:** Cierre y persistencia en artifact store

### Artifact Store

- **Backend:** Engram (memoria persistente)
- **NO se usan archivos openspec** — todos los artefactos están en Engram
- Los topic keys siguen el formato `sdd/{change-name}/{artifact}`

### Test Strategy

Los tests de paridad (`test_agent_parity.py`, ~160 tests) son **asserción de strings pura**:

```python
def test_whatsapp_includes_anti_markdown(self):
    preamble = _build_shared_preamble({"channel": "whatsapp"})
    self.assertIn("ANTI-MARKDOWN", preamble)
    self.assertIn("Prohibido: **negritas**", preamble)

def test_includes_all_f_flows(self):
    preamble = _build_shared_preamble({"channel": "whatsapp"})
    for f_num in range(1, 11):
        self.assertIn(f"F{f_num}", preamble)

def test_new_lead_shows_correct_status(self):
    state = make_state(is_new_lead=True)
    ctx = _inject_patient_context(state)
    self.assertIn("Nuevo paciente", ctx)
```

No hay mocks. No hay LLM. Son tests rápidos (<1s) que verifican que el prompt generado contenga las reglas correctas.

---

## 7. Referencia Rápida para el Desarrollador

### 7.1 Archivos Clave

| Archivo | Rol | Líneas |
|---------|-----|--------|
| `main.py` | Build system prompt + tools definition + FastAPI routes | ~14,000 |
| `services/buffer_task.py` | Entry point del agente (resuelve paciente, carga datos, invoca engine) | ~1,400 |
| `services/patient_context.py` | Carga de datos del paciente (compartido ambos motores) | ~491 |
| `services/patient_memory.py` | Sistema de memoria persistente con RAG | ~532 |
| `services/lead_context.py` | Contexto acumulado de leads en Redis | ~170 |
| `services/engine_router.py` | Router dual-engine con cache + circuit breaker | ~512 |
| `services/conversation_state.py` | State machine para slots (SLOT_LOCKED, etc.) | ~50 |
| `agents/graph.py` | Entry point del multi-agent (run_turn) | ~396 |
| `agents/specialists.py` | 6 especialistas + shared preamble + prompt assembly | ~1,476 |
| `agents/supervisor.py` | Router determinístico + LLM fallback | ~149 |
| `agents/tenant_context.py` | Bloques de contexto configurables por clínica | ~486 |
| `agents/state.py` | Tipos del AgentState | ~30 |
| `agents/model_resolver.py` | Resolución del modelo por tenant | ~100 |
| `tests/test_agent_parity.py` | ~160 tests de paridad solo vs multi | ~1,776 |

### 7.2 Para Hacer el Switch a Multi-Agent

```python
# 1. En la DB: cambiar el modo del tenant
UPDATE tenants SET ai_engine_mode = 'multi' WHERE id = <tenant_id>;

# 2. El EngineRouter invalida el cache automáticamente
#    (o forzar con PATCH /admin/settings/clinic desde la UI)

# 3. Verificar logs:
#    - "Engine mode for tenant X: multi"
#    - Circuit breaker status en caso de fallos
#    - agent_turn_log para ver qué especialistas se activan

# 4. Rollback instantáneo:
UPDATE tenants SET ai_engine_mode = 'solo' WHERE id = <tenant_id>;
#    El circuit breaker también hace fallback automático tras 3 fallos
```

### 7.3 Para Agregar un Nuevo Especialista

```python
# 1. Crear la clase en agents/specialists.py
class NewAgent(BaseAgent):
    name = "new_role"

    def _get_tools(self):
        from main import some_tool
        return [some_tool]

    async def run(self, state: AgentState) -> AgentState:
        prompt = """# ROL — NUEVO ESPECIALISTA
        ...
        """
        prompt = _with_tenant_blocks(prompt, state, "new_role")
        executor = _build_executor(tools, cfg, prompt)
        result = await executor.ainvoke({...})
        state["agent_output"] = result["output"]
        state["active_agent"] = "END"
        return state

# 2. Registrar en AGENTS
AGENTS["new_role"] = NewAgent()

# 3. Agregar ruta en el Supervisor
NEW_PATTERNS = [r"keyword", r"pattern"]
# En supervisor.py, agregar Rule N antes del fallback

# 4. Agregar tenant blocks whitelist (si aplica)
SPECIALIST_BLOCKS["new_role"] = ["clinic_basics", ...]

# 5. Escribir tests de paridad en test_agent_parity.py
```

### 7.4 Para Debuggear

```bash
# Ver qué engine usa un tenant
SELECT id, clinic_name, ai_engine_mode FROM tenants;

# Ver logs de turns multi-agent
SELECT * FROM agent_turn_log ORDER BY id DESC LIMIT 20;

# Ver estado del circuit breaker (en memoria, no en DB)
# Buscar en logs: "Circuit breaker TRIPPED for tenant X"

# Ver si el multi-agent está en fallback por cache
# Buscar en logs: "Engine mode for tenant X: solo" (cuando debería ser multi)

# Ver patient_context cargado (debug)
# LOG_LEVEL=DEBUG en services/patient_context
```

---

> **Nota final:** Ambos motores están en paridad funcional completa. El multi-agent tiene 160 tests que verifican que produce prompts equivalentes al solo-agent para cada escenario. El switch a multi-agent es cuestión de cambiar `ai_engine_mode` y monitorear — el engine router garantiza fallback automático si algo falla.
