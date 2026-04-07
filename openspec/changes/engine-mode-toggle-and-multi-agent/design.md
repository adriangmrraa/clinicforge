# Design — C3: Engine Mode Toggle + Multi-Agent System

**Change ID:** `engine-mode-toggle-and-multi-agent`
**Hereda de:** branch `claude/multi-agent-system-plan-k2UCI` (`openspec/changes/tora-to-multi-agent/`)
**Companion:** `spec.md`, `tasks.md`
**Status:** Draft
**Fecha:** 2026-04-07

---

## 1. Resumen del approach

C3 es el change más grande del umbrella dual-engine. Introduce la capacidad de correr, en paralelo y por tenant, dos motores de IA distintos: el TORA-solo actual (monolítico, LangChain AgentExecutor con `DENTAL_TOOLS`) y un nuevo sistema multi-agente basado en LangGraph (Supervisor + 6 agentes especializados). El switch entre motores se hace por tenant vía una sola columna `tenants.ai_engine_mode TEXT CHECK IN ('solo','multi')`, controlado desde la UI por el CEO.

La estrategia divide el trabajo en **7 fases deployables** (F0 prerequisitos → F7 rollout). Cada fase deja el sistema en un estado funcional y reversible. El default de la columna es `'solo'`, por lo que las fases F1-F5 son "dark launch": el código nuevo existe, se puede testear, pero nadie lo usa en producción hasta que un CEO lo active explícitamente vía el selector de la UI. El principio rector es **no big-bang merge**: cada fase corresponde a uno o dos commits atómicos, cada uno deployable por sí solo.

El approach se apoya en 3 piezas centrales: (1) un **helper `openai_compat.py`** que unifica el manejo de familias de modelos OpenAI (gpt-4o, gpt-4o-mini, gpt-5, o-series), usado solo por los agentes nuevos; (2) un **`engine_router.py`** (Strategy pattern) que decide qué motor atiende cada turno consultando `tenants.ai_engine_mode`, con caché en memoria (TTL 60s) y circuit breaker (3 fallos → fallback 5 min); y (3) un **`PatientContext`** de 4 capas (Profile, Episodic, Semantic, Working) que el sistema multi-agente usa como memoria compartida entre hops, con lock optimista en Redis.

C3 depende de que C1 (quick wins) y C2 (state lock) estén mergeados, porque `SoloEngine` internamente envuelve el TORA actual con las correcciones de C1 y C2. Si C3 se mergeara primero, la opción "solo" seguiría siendo el TORA con bugs. Orden de merge estricto: **C1 → C2 → C3**.

---

## 2. Decisiones de diseño clave

### 2.1 Por qué `ai_engine_mode TEXT` y no `multi_agent_enabled BOOL`

El plan heredado del branch `claude/multi-agent-system-plan-k2UCI` proponía dos columnas: un boolean `multi_agent_enabled` y un texto auxiliar `engine_mode`. Lo simplificamos a **una sola columna TEXT** con CHECK constraint. Razones:

1. **Menos estados inválidos**: con dos columnas puede existir `{enabled: false, mode: 'multi'}` que es contradictorio. Con una sola columna TEXT + CHECK el estado es siempre coherente.
2. **Extensibilidad**: si mañana agregamos un tercer motor (ej. `rag-only`, `hybrid`), no hay que migrar esquema, solo ampliar el CHECK.
3. **Legibilidad**: en logs, dashboards y queries ad-hoc el valor es auto-descriptivo.
4. **Menos código**: un solo getter/setter, una sola invalidación de caché.

### 2.2 `engine_router` como Strategy pattern

Usamos el Strategy pattern clásico con un `Protocol` `Engine` y dos implementaciones: `SoloEngine`, `MultiAgentEngine`. Alternativas descartadas:

- **Factory function que retorna directamente un `AgentExecutor`**: acopla `buffer_task.py` al detalle interno de cada motor (el executor LangChain no tiene la misma interfaz que un grafo LangGraph). Romperíamos la abstracción.
- **If/else inline en `buffer_task.py`**: no testeable de forma aislada, no mockeable, y cada motor nuevo agrega ramas al mismo archivo.

El trade-off es una capa extra de indirección, pero nos da testing aislado, mocking trivial, y soporte para agregar un tercer motor sin tocar el caller.

### 2.3 Caché de `ai_engine_mode` en memoria con TTL 60s

El valor se cachea **en memoria del proceso** en un dict `{tenant_id: (mode, expires_at)}`. Razones:

- **Latencia**: leer DB en cada turno añade ~5-15ms por request. Con caché, el overhead es ~10μs.
- **TTL corto (60s)**: si un CEO cambia el motor, en el peor caso espera 60s antes de que surta efecto. Para una acción manual e infrecuente es aceptable.
- **Invalidación activa**: cuando el PATCH cambia el valor, `engine_router.invalidate_cache(tenant_id)` se llama inmediatamente para el proceso local. En multi-proceso/multi-instancia, se publica un evento Redis `pubsub` en el canal `engine_router_invalidate` que cada proceso consume.

Alternativas descartadas: Redis cache compartido (round-trip extra por turno), sin caché (lento), TTL largo (retrasa cambios).

### 2.4 Circuit breaker — 3 failures → 5 min fallback

Si `MultiAgentEngine.process_turn` lanza excepción 3 veces consecutivas para el mismo tenant dentro de una ventana de 60s, el router cambia ese tenant a `SoloEngine` automáticamente por 5 minutos. Luego de los 5 min, se resetea y se reintenta multi.

Trade-off:
- **Pro**: protege a los pacientes del 4to turno en adelante cuando el motor multi está caído.
- **Contra**: los primeros 3 pacientes que caigan en la ventana de fallo sufren la falla.

Alternativas descartadas:
- **1 failure → fallback**: sobreprotege. Un error transitorio (timeout de red) traba todo por 5 min.
- **Sin fallback**: si multi está caído, el tenant queda sin servicio.

Implementación: contador en memoria del proceso (no Redis). La simplicidad justifica la duplicación de contadores entre procesos — cada proceso se protege solo, y el TTL 5 min garantiza convergencia.

### 2.5 Health check sintético, NO heartbeat continuo

`GET /admin/ai-engine/health` corre **on-demand** cuando el frontend lo invoca (al abrir el modal de switch). NO hay cron job ni heartbeat continuo.

Justificación: el caso de uso es "CEO clickea el selector cada algunos meses". Un health check sintético on-demand es suficiente, infinitamente más simple, y no añade carga constante a la DB/API.

Alternativas descartadas:
- **Heartbeat cada N min con métricas en Prometheus**: overkill para este scope.
- **Socket.IO push con estado en tiempo real**: complejidad desproporcionada.

### 2.6 Sanity probe de cada motor

Cada motor expone un método `probe()` que verifica su salud sin tocar datos de pacientes reales:

- **`SoloEngine.probe()`**: instancia un `AgentExecutor` mínimo con prompt `"Responde exactamente la palabra: pong"` y `tools=[]`. Timeout 10s. Verifica que retorna texto no vacío.
- **`MultiAgentEngine.probe()`**: instancia el `StateGraph` con un `AgentState` sintético (`tenant_id=None`, `phone="+sanity"`, `last_message="ping"`). Verifica que el supervisor decide un agente y el grafo termina en < 15s. Tools mockeadas, sin escritura a DB.

Ambos probes corren con `tenant_id=None` porque es un check global de infraestructura, no por-tenant. Los probes nunca tocan datos reales.

### 2.7 Por qué extender PATCH `/admin/settings/clinic` y no nuevo PUT

Extendemos el endpoint existente (`admin_routes.py:3392`, modelo `ClinicSettingsUpdate`) con un campo opcional `ai_engine_mode`. Razones:

1. **Reutilización**: el frontend ya consume este endpoint para `ui_language`, `bot_phone_number`, etc. El modal de save en ConfigView ya hace PATCH.
2. **Menos surface area**: un endpoint menos que documentar, autorizar, testear.
3. **Cohesión**: ambos (settings generales + engine switch) son configuración del tenant. El CEO está en el mismo modal de configuración general.

Trade-off: el endpoint hace dos cosas, pero la cohesión semántica es alta.

### 2.8 Health check inline en el PATCH

Cuando el PATCH recibe `ai_engine_mode='multi'`, antes del UPDATE en DB corre `MultiAgentEngine.probe()`. Si falla, responde **HTTP 422** con detalle estructurado y NO hace el UPDATE. Esto previene que el switch quede en un estado donde el motor target está caído.

Trade-off: el PATCH puede tardar hasta 15s (el timeout del probe). Aceptable porque es una acción manual del CEO, no un endpoint de pacientes.

### 2.9 Frontend — modal de confirmación con resultado del health check

UX en 3 pasos:

1. CEO abre Settings → tab General → ve selector `<select>` con dos opciones.
2. CEO cambia selección → frontend llama `GET /admin/ai-engine/health` → muestra modal con estado de ambos motores (`solo: ✓ OK`, `multi: ✓ OK` o `✗ fail + detalle`).
3. Botón "Confirmar cambio" habilitado **solo si el motor target está OK**. Al confirmar, se hace PATCH.

Alternativas descartadas:
- **Switch directo sin modal**: riesgo de click accidental que rompe conversaciones activas.
- **Solo mostrar health sin confirm step**: pierde el safety net.

### 2.10 Coexistencia multi-agente + TORA-solo en el mismo proceso

Ambos motores viven en el mismo proceso Python. La instanciación es lazy:

- **`SoloEngine`**: se carga al startup porque siempre puede ser usado (default).
- **`MultiAgentEngine`**: se carga en el primer request que lo necesita (lazy import + singleton). Esto evita penalizar el startup time si ningún tenant usa multi.

La memoria del proceso aloja ambas referencias tras el primer uso. No hay aislamiento por subprocess ni threads dedicados — el GIL + async es suficiente para el throughput esperado.

### 2.11 Compatibilidad con C1 y C2

C3 depende de C1 y C2 mergeados. `SoloEngine` envuelve la función actual `get_agent_executable_for_tenant` que, tras C1+C2, ya tiene los quick wins y el state lock aplicados. Si C3 se mergeara primero, "solo" sería el TORA buggy y perdería el sentido del dual-engine como **safe path**.

Plan de merge: **C1 → C2 → C3**, en ese orden, sin solapamiento.

### 2.12 Helper `openai_compat.py` — solo para multi-agent

El helper se usa exclusivamente por el supervisor y los 6 agentes nuevos. **NO se aplica al code path de TORA-solo**. Razón: TORA ya funciona con `ChatOpenAI` directo; tocarlo introduce riesgo sin beneficio (C3 es "mantener solo estable, sumar multi al lado"). Si en el futuro queremos migrar TORA al helper, es un follow-up separado post-C3.

### 2.13 Migration numbering

Las migraciones propuestas son **015** y **016**. La última migración existente es `014_add_custom_holiday_hours.py`. Riesgo: entre el momento de planning (ahora) y el apply, alguien puede añadir una 015 en otra branch.

Mitigación: antes de aplicar, correr `alembic heads` y, si hay conflicto, renumerar ambas a 0XX+1 manteniendo el orden interno de C3.

### 2.14 Supervisor routing — determinístico primero, LLM segundo

Heredado del plan k2UCI. El supervisor aplica **4 reglas determinísticas** antes de consultar al LLM:

1. `patients.human_override_until > now()` → ruta a `HandoffAgent` (silencio 24h).
2. Mensaje con attachment tipo imagen Y `appointments.payment_status='pending'` → `BillingAgent` (probable comprobante).
3. Regex de emergencia (`/sangrado|trauma|hinchazón|flemón|dolor insoportable/i`) → `TriageAgent`.
4. `state.hop_count >= max_hops (5)` → `HandoffAgent` (prevenir loops).

Si ninguna regla matchea, invoca al LLM supervisor con **tool-choice forzado** a una única tool `route_to(agent_name)`, que retorna el nombre del agente destino.

### 2.15 PatientContext — 4 layers de memoria

Heredado del plan k2UCI:

| Layer | Storage | Modo | TTL |
|-------|---------|------|-----|
| **Profile** | PostgreSQL `patients` | read-only por turno | — |
| **Episodic** | PostgreSQL `chat_messages` + `agent_turn_log` | read + append | — |
| **Semantic** | pgvector (`faq_embeddings`, `document_embeddings`) | read-only RAG | — |
| **Working** | Redis hash `patient_ctx_working:{tenant}:{phone}` | read + write | 30 min |

El **Working layer** guarda el estado del `StateGraph` entre turnos del mismo paciente (ej. slot pre-confirmado, datos parciales de reserva). El lock optimista Redis (`patient_ctx_lock:{tenant}:{phone}`, TTL 30s) previene que dos turnos concurrentes del mismo paciente corrompan el estado.

---

## 3. Diagramas

### 3.1 Arquitectura completa con `engine_router`

```
┌────────────────────────────────────────────────────────────────┐
│                  WhatsApp / Web / Chatwoot                      │
└──────────────────────────────┬─────────────────────────────────┘
                               ▼
                   ┌───────────────────────┐
                   │  buffer_task.py:998   │
                   │  process_buffer_task  │
                   └───────────┬───────────┘
                               │
                               ▼
                   ┌───────────────────────┐
                   │    engine_router      │
                   │ get_engine_for_tenant │
                   │  + cache (TTL 60s)    │
                   │  + circuit breaker    │
                   └─────┬───────────┬─────┘
                         │           │
                  solo   │           │   multi
                         ▼           ▼
              ┌──────────────┐  ┌───────────────────┐
              │  SoloEngine  │  │  MultiAgentEngine │
              │              │  │                   │
              │ AgentExecutor│  │   LangGraph       │
              │ DENTAL_TOOLS │  │   StateGraph      │
              │   (TORA)     │  │  + checkpointer   │
              └──────┬───────┘  └────────┬──────────┘
                     │                   │
                     │                   ▼
                     │       ┌─────────────────────┐
                     │       │  Supervisor + 6     │
                     │       │  Specialized Agents │
                     │       │ (Reception,Booking, │
                     │       │  Triage,Billing,    │
                     │       │  Anamnesis,Handoff) │
                     │       └────────┬────────────┘
                     │                │
                     │                ▼
                     │       ┌─────────────────────┐
                     │       │   PatientContext    │
                     │       │  Profile/Episodic/  │
                     │       │  Semantic/Working   │
                     │       └─────────┬───────────┘
                     │                 │
                     ▼                 ▼
              ┌──────────────────────────────┐
              │  PostgreSQL + Redis +        │
              │  pgvector                    │
              └──────────────────────────────┘
```

### 3.2 Flujo del switch desde la UI

```
CEO en ConfigView.tsx tab General
      │
      ▼
selecciona "Multi-Agente" en el dropdown
      │
      ▼
frontend → GET /admin/ai-engine/health
      │
      ▼
backend ejecuta sanity probes en paralelo (asyncio.gather):
      ├─ _probe_solo()   (timeout 10s)
      └─ _probe_multi()  (timeout 15s)
      │
      ▼
backend retorna { solo: {ok,latency_ms}, multi: {ok,latency_ms,detail} }
      │
      ▼
frontend muestra modal:
      ┌──────────────────────────────────┐
      │  Estado de motores               │
      │  TORA-solo:    ✓ OK (450 ms)     │
      │  Multi-Agente: ✓ OK (1.2 s)      │
      │                                  │
      │  [Cancelar]  [Confirmar cambio]  │
      └──────────────────────────────────┘
      │
      ▼
CEO confirma
      │
      ▼
frontend → PATCH /admin/settings/clinic { ai_engine_mode: 'multi' }
      │
      ▼
backend re-ejecuta probe del target (defensive)
      │
      ▼
backend UPDATE tenants SET ai_engine_mode='multi' WHERE id=?
      │
      ▼
backend engine_router.invalidate_cache(tenant_id)
      │         + publish evento Redis 'engine_router_invalidate'
      ▼
backend → 200 OK
      │
      ▼
frontend toast "Motor cambiado correctamente"
      │
      ▼
PRÓXIMO mensaje del paciente → engine_router lee 'multi' → MultiAgentEngine
```

### 3.3 Circuit breaker state machine

```
         ┌─────────┐
         │ HEALTHY │
         └────┬────┘
              │ MultiAgentEngine.process_turn raises
              ▼
        ┌──────────┐
        │ FAILURES │  count = 1
        │  COUNT   │  window_start = now
        └────┬─────┘
             │ another error within 60s
             │ count++
             ▼
         count >= 3?
             │
        ┌────┴────┐
        │ no      │ yes
        ▼         ▼
    stay in    ┌──────────┐
    FAILURES   │ TRIPPED  │  start 5min timer
               └────┬─────┘  route ALL to SoloEngine
                    │
                    │ during 5min: force solo even if tenant=multi
                    │
                    ▼
               5min elapsed
                    │
                    ▼
               ┌─────────┐
               │ HEALTHY │  reset count, retry multi next turn
               └─────────┘
```

### 3.4 Multi-agent supervisor routing flow

```
     ┌──────────────────────────┐
     │  incoming patient turn   │
     └────────────┬─────────────┘
                  ▼
     ┌──────────────────────────┐
     │  load PatientContext     │
     │  (acquire Redis lock)    │
     └────────────┬─────────────┘
                  ▼
     ┌──────────────────────────┐
     │  Supervisor.route()       │
     │                           │
     │  rule 1: human_override? ─┼────► HandoffAgent
     │  rule 2: img+pending?    ─┼────► BillingAgent
     │  rule 3: emergency regex?─┼────► TriageAgent
     │  rule 4: max_hops?       ─┼────► HandoffAgent
     │                           │
     │  fallback: LLM tool-call  │
     │  route_to(agent_name)     │
     └────────────┬──────────────┘
                  ▼
          ┌───────────────┐
          │ Specialized   │
          │    Agent      │
          │  (one of 6)   │
          └───────┬───────┘
                  │ executes tools, may set next_agent
                  ▼
          done or hand off?
                  │
        ┌─────────┴──────────┐
        │ done               │ hand off
        ▼                    ▼
  save PatientContext   back to Supervisor
  emit response         (hop_count++)
  release lock
```

---

## 4. Cambios por archivo

### 4.1 NEW `orchestrator_service/core/openai_compat.py`
Helper que unifica el manejo de familias de modelos OpenAI. Expone:
- `get_chat_model(model_name, temperature=None, max_tokens=None)` → retorna un `ChatOpenAI` con parámetros ajustados por familia (o-series ignora temperature, gpt-5 usa `max_completion_tokens` en lugar de `max_tokens`).
- `safe_chat_completion(messages, model, **kwargs)` → wrapper directo sobre el SDK oficial con fallback y retries.
- Usado exclusivamente por agents/* y supervisor. TORA-solo no se toca.

### 4.2 NEW `orchestrator_service/services/engine_router.py`
Strategy pattern. Contiene:
- `class Engine(Protocol)` con `async process_turn(ctx) -> TurnResult` y `async probe() -> ProbeResult`.
- `class SoloEngine(Engine)`: wrappea el actual `get_agent_executable_for_tenant`.
- `class MultiAgentEngine(Engine)`: (F2 stub, F6 real) invoca `agents.graph.run_turn(ctx)`.
- `_cache: dict[uuid.UUID, tuple[str, float]]` con TTL 60s.
- `_circuit: dict[uuid.UUID, CircuitState]` con threshold 3 y recovery 300s.
- `async get_engine_for_tenant(tenant_id) -> Engine`.
- `invalidate_cache(tenant_id)` + suscripción al canal Redis `engine_router_invalidate`.

### 4.3 NEW `orchestrator_service/services/patient_context.py`
Servicio único con:
- `class PatientContext` (dataclass).
- `async load(tenant_id, phone) -> PatientContext` con lock optimista Redis.
- `async apply_delta(delta: dict) -> None` (append episodic, update working).
- `to_agent_state() -> AgentState`.
- 4 layers: Profile (PG), Episodic (PG), Semantic (pgvector RAG), Working (Redis hash TTL 30m).
- Tenant enforcement en TODAS las queries (`WHERE tenant_id=$1`).

### 4.4 NEW `orchestrator_service/agents/`
Carpeta con:
- `__init__.py`
- `state.py` — `AgentState` TypedDict (tenant_id, phone, messages, next_agent, hop_count, context_ref, ...)
- `base.py` — `BaseAgent` abstract class con `async run(state) -> state`
- `graph.py` — `StateGraph` wiring (Supervisor → 6 agentes → END o back to Supervisor)
- `supervisor.py` — reglas determinísticas + LLM fallback con tool-choice forzado
- `reception.py` — FAQ, información, listado de servicios
- `booking.py` — reservar, cancelar, reprogramar
- `triage.py` — urgencia, síntomas, derivación clínica (usa gpt-4o, más fuerte)
- `billing.py` — verificación de comprobantes, señas
- `anamnesis.py` — captura de historia clínica
- `handoff.py` — derivación a humano
- `prompts/` — un `.md` por agente, cada uno <500 tokens

### 4.5 NEW `orchestrator_service/routes/ai_engine_health.py`
Endpoint `GET /admin/ai-engine/health` (requiere JWT CEO). Ejecuta:
```python
solo_res, multi_res = await asyncio.gather(
    _probe_solo(timeout=10),
    _probe_multi(timeout=15),
    return_exceptions=True,
)
```
Retorna `{solo: {ok, latency_ms, error?}, multi: {ok, latency_ms, error?}}`.

### 4.6 NEW `orchestrator_service/alembic/versions/015_ai_engine_mode_column.py`
```sql
-- upgrade
ALTER TABLE tenants
  ADD COLUMN ai_engine_mode TEXT NOT NULL DEFAULT 'solo'
  CHECK (ai_engine_mode IN ('solo','multi'));

-- downgrade
ALTER TABLE tenants DROP COLUMN ai_engine_mode;
```

### 4.7 NEW `orchestrator_service/alembic/versions/016_multi_agent_tables.py`
```sql
-- upgrade
CREATE TABLE patient_context_snapshots (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  phone_number  TEXT NOT NULL,
  thread_id     TEXT NOT NULL,
  state_json    JSONB NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pcs_tenant_phone ON patient_context_snapshots(tenant_id, phone_number);
CREATE INDEX idx_pcs_thread ON patient_context_snapshots(thread_id);

CREATE TABLE agent_turn_log (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  phone_number  TEXT NOT NULL,
  turn_id       UUID NOT NULL,
  hop_index     INT NOT NULL,
  agent_name    TEXT NOT NULL,
  input_digest  TEXT,
  output_digest TEXT,
  tool_calls    JSONB,
  latency_ms    INT,
  error         TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_atl_tenant_turn ON agent_turn_log(tenant_id, turn_id);
CREATE INDEX idx_atl_created ON agent_turn_log(created_at DESC);

-- downgrade: DROP ambas tablas
```

### 4.8 `orchestrator_service/services/buffer_task.py:998`
Cambio mínimo:
```python
# antes
executor = await get_agent_executable_for_tenant(tenant_id)
result = await executor.ainvoke(...)

# después
from services.engine_router import engine_router
engine = await engine_router.get_engine_for_tenant(tenant_id)
result = await engine.process_turn(ctx)
```

### 4.9 `orchestrator_service/admin_routes.py:3392`
Extender `ClinicSettingsUpdate`:
```python
class ClinicSettingsUpdate(BaseModel):
    # ... campos existentes ...
    ai_engine_mode: Optional[Literal['solo','multi']] = None
```
En el handler: si `ai_engine_mode` presente, correr `_probe_solo` o `_probe_multi` según target. Si falla → `raise HTTPException(422, ...)`. Si OK → UPDATE + `engine_router.invalidate_cache(tenant_id)`.

### 4.10 `orchestrator_service/models.py:159-187`
Agregar al ORM `Tenant`:
```python
ai_engine_mode: Mapped[str] = mapped_column(String, nullable=False, default='solo')
```
Agregar clases nuevas `PatientContextSnapshot` y `AgentTurnLog`.

### 4.11 `frontend_react/src/views/ConfigView.tsx`
Dentro del bloque existente `{user?.role === 'ceo' && (...)}` (línea 898), añadir sección "Motor de IA" con:
- `<select>` con opciones `solo` / `multi`
- Handler `onChange` que llama a `fetchHealth()` y abre modal
- Modal con resultado del health check y botón "Confirmar"
- Al confirmar → PATCH `/admin/settings/clinic` con `ai_engine_mode`

### 4.12 `frontend_react/src/locales/{es,en,fr}.json`
Claves nuevas (namespace `config.aiEngine`):
- `label`, `optionSolo`, `optionMulti`
- `modal.title`, `modal.statusSolo`, `modal.statusMulti`, `modal.confirm`, `modal.cancel`
- `toast.success`, `toast.error`
- `health.ok`, `health.fail`, `health.loading`

### 4.13 `orchestrator_service/requirements.txt`
Añadir:
```
langgraph>=0.2.0,<0.3.0
```

---

## 5. Estructuras de datos

### 5.1 DB schema — migraciones 015 y 016

Ver §4.6 y §4.7. Referencias cruzadas con `spec.md` §4 y §5.

### 5.2 Redis keys nuevas

| Key | Type | TTL | Set by | Read by |
|-----|------|-----|--------|---------|
| `engine_router_cache:{tenant_id}` | string | 60s | engine_router al primer read | engine_router en cada turno |
| `engine_router_circuit:{tenant_id}` | hash | 300s | engine_router al fallar multi | engine_router antes de dispatch |
| `patient_ctx_lock:{tenant_id}:{phone}` | string (nx) | 30s | PatientContext.load | PatientContext.apply_delta |
| `patient_ctx_working:{tenant_id}:{phone}` | hash | 1800s | working layer write | working layer read |
| `engine_router_invalidate` (pubsub) | channel | — | PATCH handler | engine_router subscriber |

### 5.3 `AgentState` TypedDict (heredado del plan k2UCI)

```python
class AgentState(TypedDict):
    tenant_id: uuid.UUID
    phone_number: str
    turn_id: uuid.UUID
    thread_id: str
    messages: list[BaseMessage]         # LangChain message history
    last_user_message: str
    next_agent: Optional[str]            # set by supervisor
    hop_count: int
    max_hops: int                        # default 5
    context_ref: str                     # key to PatientContext in Redis
    tool_outputs: dict                   # per-turn scratch
    done: bool
    error: Optional[str]
```

---

## 6. Contratos de funciones

### 6.1 `engine_router` API

```python
async def get_engine_for_tenant(tenant_id: uuid.UUID) -> Engine: ...
def invalidate_cache(tenant_id: uuid.UUID) -> None: ...
async def _load_mode(tenant_id: uuid.UUID) -> Literal['solo','multi']: ...
def _record_failure(tenant_id: uuid.UUID) -> bool: ...  # returns True if tripped
def _is_tripped(tenant_id: uuid.UUID) -> bool: ...
```

### 6.2 `Engine` Protocol

```python
class Engine(Protocol):
    name: str  # 'solo' | 'multi'
    async def process_turn(self, ctx: TurnContext) -> TurnResult: ...
    async def probe(self) -> ProbeResult: ...

@dataclass
class TurnContext:
    tenant_id: uuid.UUID
    phone_number: str
    user_message: str
    attachments: list[dict]
    metadata: dict

@dataclass
class TurnResult:
    reply: str
    actions: list[dict]
    tokens_used: int
    latency_ms: int
    meta: dict

@dataclass
class ProbeResult:
    ok: bool
    latency_ms: int
    error: Optional[str] = None
```

### 6.3 `SoloEngine` y `MultiAgentEngine`

- **`SoloEngine.process_turn`**: llama internamente al `AgentExecutor` actual vía `get_agent_executable_for_tenant(tenant_id)` y retorna `TurnResult`.
- **`MultiAgentEngine.process_turn`**: (F2 stub) `raise NotImplementedError`. (F6) llama a `agents.graph.run_turn(ctx)`, carga/guarda `PatientContext`, persiste snapshot en `patient_context_snapshots`, loguea hops en `agent_turn_log`.

### 6.4 `PatientContext` API

```python
async def load(tenant_id: uuid.UUID, phone: str) -> PatientContext: ...
async def apply_delta(self, delta: dict) -> None: ...
def to_agent_state(self, turn_id: uuid.UUID) -> AgentState: ...
async def release(self) -> None: ...  # libera lock Redis
```

### 6.5 Health endpoint contract

Ver `spec.md` §7.1. Brief:
```
GET /admin/ai-engine/health
Auth: JWT CEO
200:
{
  "solo":  { "ok": true,  "latency_ms": 450 },
  "multi": { "ok": false, "latency_ms": 15000, "error": "graph timeout" }
}
```

### 6.6 PATCH endpoint extension

```
PATCH /admin/settings/clinic
Body (parcial):
{ "ai_engine_mode": "multi" }

200 OK → UPDATE aplicado, cache invalidado
422 UNPROCESSABLE → probe del target falló, UPDATE NO aplicado
  body: { "detail": "multi engine probe failed: <reason>" }
```

---

## 7. Casos de test (resumen)

| Componente | Tipo | File | Cantidad |
|-----------|------|------|----------|
| openai_compat | unit | `tests/test_openai_compat.py` | 4 |
| engine_router (dispatch + cache) | unit | `tests/test_engine_router.py` | 6 |
| engine_router (circuit breaker) | unit | `tests/test_engine_router_circuit.py` | 4 |
| patient_context | unit | `tests/agents/test_patient_context.py` | 8 |
| supervisor routing | unit | `tests/agents/test_supervisor_routing.py` | 20 |
| reception agent | unit | `tests/agents/test_reception.py` | 10 |
| booking agent | unit | `tests/agents/test_booking.py` | 12 |
| triage agent | unit | `tests/agents/test_triage.py` | 10 |
| billing agent | unit | `tests/agents/test_billing.py` | 10 |
| anamnesis agent | unit | `tests/agents/test_anamnesis.py` | 8 |
| handoff agent | unit | `tests/agents/test_handoff.py` | 6 |
| health endpoint | integration | `tests/test_ai_engine_health.py` | 4 |
| PATCH extended | integration | `tests/test_settings_clinic_engine.py` | 6 |
| migrations 015/016 | manual | alembic upgrade/downgrade | — |
| switch flow E2E | smoke | manual | — |

**Total**: ~108 unit + 10 integration + 2 manuales.

---

## 8. Plan de implementación por fases

Cada fase deja el sistema deployable, reversible, y con un go/no-go explícito.

### F0 — Prerequisitos (Día 1)
- Verificar `alembic heads` → la última migración es 014.
- Crear branch `feat/c3-engine-toggle-multi-agent` desde `main` (con C1 y C2 ya mergeados).
- Crear carpetas vacías: `orchestrator_service/agents/`, `orchestrator_service/agents/prompts/`, `tests/agents/`.

**Go/no-go**: C1 y C2 mergeados en main.

### F1 — Helper openai_compat + migraciones (Día 2-3)
- Crear `core/openai_compat.py` + tests.
- Crear migraciones 015 y 016 con upgrade/downgrade.
- Aplicar en staging, verificar columna y tablas, probar downgrade.
- Actualizar `models.py` con la columna y las dos clases ORM nuevas.

**Deployable**: sí. Zero impact en pacientes (default `'solo'`).

### F2 — engine_router skeleton (Día 4-5)
- Crear `services/engine_router.py` con Protocol + `SoloEngine` (wrappea flow actual) + `MultiAgentEngine` stub (`NotImplementedError`).
- Cache TTL 60s + circuit breaker + pubsub Redis.
- Tests unit (dispatch, cache, circuit).
- Modificar `buffer_task.py:998` para usar el router.
- Smoke manual: TORA sigue idéntico.

**Deployable**: sí. Zero impact: default `'solo'` + `MultiAgentEngine` nunca se invoca.

### F3 — Multi-agent core (Día 6-12)
- **Día 6**: `PatientContext` + tests (tenant isolation).
- **Día 7**: `agents/state.py`, `agents/base.py`, `agents/graph.py` (skeleton).
- **Día 8**: `agents/supervisor.py` + prompt + 20 tests de routing.
- **Día 9**: Reception + Booking agents + prompts + tests.
- **Día 10**: Triage (gpt-4o) + Billing + prompts + tests.
- **Día 11**: Anamnesis + Handoff + prompts + tests.
- **Día 12**: `StateGraph` wiring completo + checkpointer PG (`patient_context_snapshots`) + test integration.

**Deployable**: sí. Código existe pero `MultiAgentEngine` sigue stub → zero impact.

### F4 — Health check endpoint (Día 13)
- Crear `routes/ai_engine_health.py` con `_probe_solo` (10s) + `_probe_multi` (15s) en paralelo.
- Tests integration (ambos OK, uno fail, ambos fail, timeout).
- Registrar router en `main.py`.

**Deployable**: sí. Endpoint disponible, frontend aún no lo consume.

### F5 — Frontend selector + PATCH extension (Día 14)
- **F5a (frontend)**: Modificar `ConfigView.tsx` tab General — selector + modal + flow.
- **F5b (backend, paralelo)**: Extender `ClinicSettingsUpdate` con `ai_engine_mode`, probe inline, invalidate cache. Tests integration.
- Añadir claves i18n en es/en/fr.
- Smoke manual: CEO abre Settings, ve selector, health check responde, PATCH funciona (con `MultiAgentEngine` stub el PATCH a multi va a fallar en el probe → comportamiento esperado, confirma que el gate funciona).

**Deployable**: sí. Selector visible pero multi aún no activable.

### F6 — Activación e integración (Día 15-16)
- Reemplazar el stub de `MultiAgentEngine.process_turn` con la implementación real.
- Conectar checkpointer con `patient_context_snapshots`.
- Conectar log con `agent_turn_log`.
- Tests integration: dos tenants en paralelo, uno solo y otro multi.
- Smoke manual en staging: crear tenant interno (NO Dra. Laura), setearlo a multi vía SQL, mandar mensajes desde test phone, verificar supervisor + agent routing + `agent_turn_log`.
- Dejar tenant interno en multi por 7 días con monitoreo.

**Deployable**: sí con monitoreo estricto.

### F7 — Rollout y CLAUDE.md (Día 17+)
- Si F6 estable por 1 semana, presentar a Dra. Laura + obtener consentimiento.
- Si consiente, activar multi para su tenant vía UI.
- Monitorear 1 semana adicional.
- Actualizar `CLAUDE.md` con sección "Dual-Engine Architecture".
- Mover C1/C2/C3 a `openspec/changes/archive/`.
- PR final del umbrella.

---

## 9. Riesgos de implementación

| # | Riesgo | Probabilidad | Severidad | Mitigación |
|---|--------|--------------|-----------|-----------|
| R1 | Migraciones 015/016 fallan en prod | Baja | Alta | Staging primero, downgrade probado, default `'solo'` garantiza no breaking |
| R2 | Cache `engine_router` inconsistente entre procesos | Media | Media | Pubsub Redis `engine_router_invalidate`, TTL corto 60s como fallback |
| R3 | Circuit breaker false positive (3 errores transitorios) | Media | Baja | Reset manual vía endpoint admin (follow-up), o ajustar threshold a 5 |
| R4 | LangGraph version conflict con deps actuales | Media | Alta | Pin exacto `langgraph>=0.2.0,<0.3.0`, test en venv aislado antes de merge |
| R5 | `PatientContext` lock → deadlock por mensajes concurrentes | Baja | Alta | Lock TTL 30s, retry con backoff exponencial |
| R6 | Health check > 15s → timeout en el frontend | Media | Media | Probes en paralelo, timeout per-probe estricto, frontend muestra "degradado" |
| R7 | Toggle accidental rompe conversaciones activas | Baja | Alta | Modal obligatorio, mensaje de impacto, posible disable en horarios de atención |
| R8 | Supervisor LLM ignora tool-choice → handoff infinito | Baja | Alta | `max_hops=5`, timeout 45s, fallback forzado a HandoffAgent |
| R9 | Migration numbering colisiona con otra branch | Baja | Media | `alembic heads` justo antes del apply, renumerar si es necesario |
| R10 | `MultiAgentEngine` consume muchos más tokens que solo | Alta | Media | Tracking de tokens en `agent_turn_log`, alertas si excede threshold, rollback rápido vía toggle |

---

## 10. Open questions para el apply phase

1. ¿La migración 016 debe correr en el mismo deploy que 015 o en deploys separados? (Recomendación: mismo deploy, ambas son aditivas.)
2. ¿La invalidación de caché del engine_router se publica vía Redis pubsub a todos los procesos, o cada proceso convive con su TTL de 60s? (Recomendación: pubsub + TTL como fallback.)
3. ¿El sanity probe del multi engine crea un `PatientContext` fake en memoria o tiene un "tenant sanity" pre-seeded en DB?
4. ¿Los agentes del grafo ven los `DENTAL_TOOLS` originales sin modificar, o creamos wrappers que inyectan `PatientContext`?
5. ¿La instanciación del `MultiAgentEngine` es lazy (primer request) o eager (al startup)? (Recomendación: lazy.)
6. ¿`agent_turn_log` se llena por cada hop individual o por turno completo con JSON de los hops anidados? (Recomendación: por hop, mejor para debugging.)
7. ¿Hay un endpoint admin para resetear el circuit breaker manualmente sin esperar el TTL de 5 min? (Follow-up.)
8. ¿El frontend muestra el motor activo en el header (badge) o solo en Settings? (Recomendación: badge discreto para CEO.)
