# Spec — C3: Engine Mode Toggle + Multi-Agent System

**Change ID:** `engine-mode-toggle-and-multi-agent`
**Umbrella:** `openspec/changes/dual-engine-umbrella/proposal.md`
**Hereda de:** branch `claude/multi-agent-system-plan-k2UCI`, archivo `openspec/changes/tora-to-multi-agent/{proposal,spec,tasks}.md`
**Companion:** `proposal.md` (per-change), `design.md`, `tasks.md` (próxima fase)
**Status:** Draft
**Fecha:** 2026-04-07

---

## 1. Objetivos

1. **Coexistencia de motores**: TORA-solo y multi-agente corren en el mismo proceso FastAPI sin interferir. Cada turno de conversación se resuelve en exactamente un motor, determinado por `tenants.ai_engine_mode`.
2. **Selector por tenant en Settings UI**: el CEO puede cambiar el motor desde `ConfigView.tsx` (tab general) sin acceso a la base de datos ni a infraestructura.
3. **Health check pre-switch**: antes de confirmar el cambio de motor, el frontend valida que el motor destino responde correctamente vía `GET /admin/ai-engine/health`. El selector no habilita el cambio si el motor destino está en fail.
4. **Sistema multi-agente completo**: Supervisor + 6 agentes especializados (Reception, Booking, Triage, Billing, Anamnesis, Handoff) implementados con LangGraph según la arquitectura del plan k2UCI, con las adaptaciones documentadas en este spec.
5. **Cero impacto en TORA-solo**: cuando `ai_engine_mode = 'solo'`, el flujo de `buffer_task.py` es idéntico al actual (misma instancia de `AgentExecutor`, mismas herramientas, mismo prompt). No se agrega latencia ni complejidad al camino caliente.
6. **Acceso CEO exclusivo**: el selector y el health check solo son visibles y operables para usuarios con `role === 'ceo'`, usando el gate ya existente en `ConfigView.tsx:898`.

---

## 2. Alcance

### 2.1 Lo que entra en C3

- **Helper `core/openai_compat.py`** (prerequisito obligatorio — hoy NO existe en el repo)
- **Migración Alembic 015**: nueva columna `ai_engine_mode` en tabla `tenants`
- **Migración Alembic 016**: tablas nuevas `patient_context_snapshots` y `agent_turn_log`
- **Módulo `services/engine_router.py`**: decisor de motor por tenant, caché en memoria, circuit breaker
- **Endpoint `GET /admin/ai-engine/health`**: sanity check de ambos motores con latencia medida
- **Endpoint `PATCH /admin/settings/clinic` extendido**: acepta `ai_engine_mode` con health check inline previo a la escritura
- **Frontend**: selector en `ConfigView.tsx` tab general, modal de confirmación con resultado del health check, i18n en los tres idiomas
- **Sistema multi-agente completo**: carpeta `orchestrator_service/agents/` con supervisor + 6 agentes + LangGraph `StateGraph` + prompts en Markdown
- **`services/patient_context.py`**: servicio de contexto compartido entre agentes (Profile, Episodic, Semantic, Working)
- **Tests unitarios** por agente (≥ 10 casos cada uno), unit tests de `engine_router` y `openai_compat`, integration tests de switch
- **Smoke test E2E manual** del flujo completo solo→multi→solo

### 2.2 Lo que NO entra en C3

- Cambios al código interno de TORA-solo (cubiertos en C1 y C2 del umbrella)
- Integración de Nova voice assistant al engine router (fuera del alcance del umbrella)
- Shadow mode, per-phone whitelist, override per-conversación (explícitamente descartados por el usuario)
- A/B testing automático con métricas comparativas (solo selector manual del CEO)
- Refactor o consolidación de los 14 tools de `DENTAL_TOOLS` (se reutilizan tal cual entre agentes, sin modificación)
- Eval harness con 50 conversaciones reales (movido a fase post-DoD, posterior al rollout F7)
- Migración de datos históricos de `chat_messages` a las nuevas tablas

---

## 3. Helper `openai_compat.py` (prerequisito)

### 3.1 Estado actual

**NO EXISTE en el repositorio.** Confirmado por el explore agent: el directorio `orchestrator_service/core/` no contiene `openai_compat.py`. Documentación anterior que indicaba que estaba "mergeado" era incorrecta.

Hoy `main.py:7039-7046` instancia `ChatOpenAI` directamente desde `langchain_openai`, hardcodeando parámetros compatibles con la familia `gpt-*`. Los modelos `o-series` (o1, o3, o4-mini) tienen restricciones diferentes: no aceptan `temperature`, usan `max_completion_tokens` en lugar de `max_tokens`, y no soportan `system` messages en algunas versiones.

### 3.2 Solución

Crear `orchestrator_service/core/openai_compat.py` con la siguiente API surface mínima:

```python
from langchain_openai import ChatOpenAI
from typing import Any


def get_chat_model(
    model_name: str,
    temperature: float = 0.0,
    **kwargs: Any
) -> ChatOpenAI:
    """
    Factory que devuelve una instancia de ChatOpenAI con los parámetros correctos
    para la familia del modelo indicado.

    Familias reconocidas:
    - gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo → temperatura + max_tokens
    - gpt-5, gpt-5-mini → temperatura + max_tokens (asumido compatible)
    - o1, o1-mini, o3, o3-mini, o4-mini → sin temperatura, max_completion_tokens

    Args:
        model_name: Nombre del modelo OpenAI (ej. 'gpt-4o-mini', 'o1-mini')
        temperature: Temperatura deseada. Ignorada silenciosamente para o-series.
        **kwargs: Parámetros adicionales pasados a ChatOpenAI.

    Returns:
        Instancia de ChatOpenAI configurada correctamente.
    """


async def safe_chat_completion(
    client: Any,
    model: str,
    messages: list[dict],
    **kwargs: Any
) -> dict:
    """
    Llama a la API de OpenAI con el conjunto correcto de parámetros según la familia
    del modelo. Maneja la diferencia max_tokens vs max_completion_tokens y la ausencia
    de temperature en o-series.

    Diseñado para llamadas directas (no LangChain) como el health check sanity probe.
    """
```

**Regla de familia**: si `model_name` empieza con `o1`, `o3`, `o4`, o `o-`, se trata como o-series.

### 3.3 Quién lo usa

- `orchestrator_service/agents/base.py` (clase base de todos los agentes del sistema multi-agente)
- `orchestrator_service/routes/ai_engine_health.py` (sanity probe del multi-agente)
- **NO se aplica a TORA-solo legacy** (`main.py:7039`): ese código queda intacto para garantizar zero impact.

### 3.4 Tests requeridos

Archivo: `tests/test_openai_compat.py`

| # | Caso | Verificación |
|---|------|-------------|
| 1 | `get_chat_model('gpt-4o-mini', temperature=0.7)` | instancia tiene `temperature=0.7` y `model_name='gpt-4o-mini'` |
| 2 | `get_chat_model('gpt-4o', temperature=0.5)` | ídem con gpt-4o |
| 3 | `get_chat_model('o1-mini', temperature=0.5)` | instancia NO tiene `temperature` en los parámetros de llamada |
| 4 | `get_chat_model('o3-mini', temperature=0.0)` | ídem, o-series ignorando temperatura |

Tests son unitarios, no llaman a la API real (mock de `ChatOpenAI.__init__`).

---

## 4. Migración Alembic 015 — `tenants.ai_engine_mode`

### 4.1 Contexto

La migración más reciente en el repo es `014_add_custom_holiday_hours.py`. Esta migración será la `015`. El plan k2UCI original numeraba esta migración como `010`, pero ese número ya está ocupado. Las migraciones deben ser `015` y `016`.

La tabla `tenants` está definida en `models.py:159-187` y actualmente **no tiene columnas `multi_agent_enabled` ni `multi_agent_mode`** (confirmado por explore agent). Se agrega una sola columna que reemplaza ambas del plan original.

### 4.2 Decisión de diseño: un campo en lugar de dos

El plan k2UCI proponía `multi_agent_enabled BOOL` + `multi_agent_mode TEXT('off'|'shadow'|'live')`. Esto se simplifica a **un único campo** `ai_engine_mode TEXT('solo'|'multi')` por las siguientes razones:

- El usuario descartó shadow mode explícitamente
- Dos campos con tres estados posibles generan combinaciones inválidas (`enabled=false, mode='live'`)
- Un campo `TEXT` con CHECK constraint es más simple, más legible y sin ambigüedad
- El nombre `ai_engine_mode` es más descriptivo que `multi_agent_enabled/mode`

### 4.3 Schema SQL

```sql
ALTER TABLE tenants
  ADD COLUMN ai_engine_mode TEXT NOT NULL DEFAULT 'solo'
    CHECK (ai_engine_mode IN ('solo', 'multi'));
```

El `DEFAULT 'solo'` garantiza que todos los tenants existentes continúan con TORA-solo sin ninguna intervención manual posterior a la migración.

### 4.4 Archivo de migración

**Ruta:** `orchestrator_service/alembic/versions/015_ai_engine_mode_column.py`

Debe incluir:
- `upgrade()`: `ALTER TABLE tenants ADD COLUMN ai_engine_mode TEXT NOT NULL DEFAULT 'solo' CHECK (ai_engine_mode IN ('solo', 'multi'))`
- `downgrade()`: `ALTER TABLE tenants DROP COLUMN ai_engine_mode`
- `down_revision`: apuntar al ID de la migración 014

### 4.5 SQLAlchemy ORM

Agregar en `models.py`, clase `Tenant` (línea ~187):

```python
ai_engine_mode: Mapped[str] = mapped_column(
    String, nullable=False, default="solo", server_default="solo"
)
```

---

## 5. Migración Alembic 016 — Tablas multi-agente

### 5.1 Propósito de cada tabla

**`patient_context_snapshots`**: persiste el `AgentState` de LangGraph entre turnos. Actúa como checkpointer de LangGraph con backend Postgres. Permite que conversaciones largas sobrevivan reinicios del servicio.

**`agent_turn_log`**: registro append-only de cada turno ejecutado por el sistema multi-agente. Útil para debugging, auditoría, y futuro eval harness.

### 5.2 Schema SQL

```sql
-- Snapshots del estado LangGraph por conversación
CREATE TABLE patient_context_snapshots (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone_number TEXT NOT NULL,
    thread_id   TEXT NOT NULL,
    state       JSONB NOT NULL,
    active_agent TEXT,
    hop_count   INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, phone_number, thread_id)
);

CREATE INDEX idx_pcs_tenant_phone
    ON patient_context_snapshots (tenant_id, phone_number);

-- Log inmutable de turnos por agente
CREATE TABLE agent_turn_log (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone_number TEXT NOT NULL,
    turn_id      TEXT NOT NULL,
    agent_name   TEXT NOT NULL,
    tools_called JSONB,
    handoff_to   TEXT,
    duration_ms  INT,
    model        TEXT,
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_atl_tenant_phone
    ON agent_turn_log (tenant_id, phone_number);

CREATE INDEX idx_atl_turn
    ON agent_turn_log (turn_id);
```

### 5.3 Campos clave

| Campo | Tipo | Propósito |
|-------|------|-----------|
| `thread_id` | TEXT | ID único de conversación. Formato: `{tenant_id}:{phone_number}:{fecha_inicio}` |
| `state` | JSONB | Serialización completa de `AgentState` (mensajes, contexto del paciente, intent) |
| `active_agent` | TEXT | Último agente activo antes del snapshot. Permite retomar desde el agente correcto |
| `hop_count` | INT | Cantidad de handoffs en el turno actual. Límite máximo: 5 (protección contra loops) |
| `tools_called` | JSONB | Array de `{tool_name, args_summary, success}` para auditoría |
| `handoff_to` | TEXT | Si este turno terminó con un handoff, nombre del agente destino |

### 5.4 Archivo de migración

**Ruta:** `orchestrator_service/alembic/versions/016_multi_agent_tables.py`

Debe incluir:
- `upgrade()`: ambos CREATE TABLE + índices
- `downgrade()`: DROP TABLE en orden inverso (agent_turn_log primero, luego patient_context_snapshots)
- `down_revision`: apuntar al ID de la migración 015

### 5.5 SQLAlchemy ORM

Agregar en `models.py` dos clases nuevas `PatientContextSnapshot` y `AgentTurnLog` con los campos correspondientes y `__tablename__` correcto.

---

## 6. Módulo `services/engine_router.py`

### 6.1 Responsabilidad

`engine_router` es la capa de decisión que reemplaza la llamada directa a `get_agent_executable_for_tenant()` en `buffer_task.py:998`. Su responsabilidad es exclusivamente: dado un `tenant_id`, retornar el motor correcto para procesar el turno. No contiene lógica de negocio conversacional.

El módulo es multi-tenant desde el diseño: toda decisión está keyed por `tenant_id`. No existe ningún estado global entre tenants.

### 6.2 API pública

```python
from typing import Protocol, Any
from dataclasses import dataclass


@dataclass
class TurnContext:
    tenant_id: str          # UUID del tenant
    phone_number: str       # Número del paciente
    message: str            # Mensaje del turno actual
    thread_id: str          # ID de conversación
    extra: dict[str, Any]   # Contexto adicional (buffer, historial, etc.)


@dataclass
class TurnResult:
    output: str             # Respuesta generada
    agent_used: str         # 'solo' o nombre del agente multi
    duration_ms: int


class Engine(Protocol):
    async def process_turn(self, ctx: TurnContext) -> TurnResult: ...


async def get_engine_for_tenant(tenant_id: str) -> Engine:
    """
    Retorna el motor correcto para el tenant indicado.
    Lee tenants.ai_engine_mode desde caché en memoria (TTL 60s) o DB en miss.
    Nunca retorna None — si el modo es desconocido, usa SoloEngine como fallback seguro.
    Thread-safe: usa asyncio.Lock por tenant_id para evitar doble-query en arranque.
    """
```

### 6.3 Implementaciones de Engine

**`SoloEngine`**:
- Wrapper sobre `get_agent_executable_for_tenant(tenant_id)` + `executor.ainvoke(input, config)` exactamente como hoy en `buffer_task.py:998-1020`.
- No modifica nada del flujo TORA-solo existente.
- `agent_used = 'solo'`

**`MultiAgentEngine`**:
- Wrapper sobre el `StateGraph` compilado del supervisor (`agents/graph.py`).
- Carga o crea el snapshot en `patient_context_snapshots` al inicio del turno.
- Persiste el snapshot actualizado al final.
- Registra en `agent_turn_log` con `turn_id = uuid4()`.
- `agent_used = nombre del último agente activo`

### 6.4 Inserción en `buffer_task.py`

**Antes** (`buffer_task.py:998`):
```python
executor = await get_agent_executable_for_tenant(tenant_id)
result = await executor.ainvoke(
    {"input": user_message, "chat_history": history},
    config={"configurable": {"session_id": session_id}}
)
response_text = result.get("output", "")
```

**Después**:
```python
from services.engine_router import get_engine_for_tenant, TurnContext

engine = await get_engine_for_tenant(tenant_id)
ctx = TurnContext(
    tenant_id=tenant_id,
    phone_number=phone_number,
    message=user_message,
    thread_id=session_id,
    extra={"chat_history": history, "buffer_data": buffer_data}
)
turn_result = await engine.process_turn(ctx)
response_text = turn_result.output
```

La lógica posterior a `response_text` (envío de respuesta, actualización de `chat_messages`, etc.) no cambia.

### 6.5 Caché de `ai_engine_mode`

- Estructura: `dict[str, tuple[str, float]]` donde el valor es `(modo, timestamp_expiry)`
- TTL: 60 segundos
- En miss (key no existe o expiró): query async a `tenants.ai_engine_mode WHERE id = $1`
- Invalidación activa: el handler de `PATCH /admin/settings/clinic` llama a `engine_router.invalidate_cache(tenant_id)` después de una escritura exitosa
- Thread-safety: `asyncio.Lock` por `tenant_id` para evitar thundering herd en el primer request

### 6.6 Circuit breaker

Objetivo: proteger a los pacientes de un multi-agente degradado. Si el motor multi-agente falla repetidamente para un tenant, cae automáticamente a TORA-solo.

Reglas:
- Contador de fallas consecutivas por `tenant_id` en memoria
- **Umbral de apertura**: 3 fallas consecutivas en `MultiAgentEngine.process_turn` (excepción o timeout)
- **Duración del estado abierto**: 5 minutos
- **En estado abierto**: `get_engine_for_tenant` retorna `SoloEngine` aunque `ai_engine_mode = 'multi'`
- **Reset**: después de 5 minutos, el siguiente request intenta `MultiAgentEngine` nuevamente (estado half-open). Si tiene éxito, el contador se resetea.
- **Log**: cada apertura del circuit breaker genera un log `ERROR` con `tenant_id`, timestamp, y la excepción que causó la tercera falla
- **No alerta automática** (fuera de scope — el log es suficiente para la primera versión)

El circuit breaker es transparente para `buffer_task.py`: siempre llama a `get_engine_for_tenant()` y recibe un `Engine` válido.

### 6.7 Archivos afectados

| Acción | Archivo |
|--------|---------|
| Nuevo | `orchestrator_service/services/engine_router.py` |
| Modificado (mínimo) | `orchestrator_service/services/buffer_task.py` (~línea 998) |

### 6.8 Tests requeridos

Archivo: `tests/test_engine_router.py`

| # | Caso | Verificación |
|---|------|-------------|
| 1 | tenant con `ai_engine_mode = 'solo'` | retorna `SoloEngine` |
| 2 | tenant con `ai_engine_mode = 'multi'` | retorna `MultiAgentEngine` |
| 3 | cache hit (segunda llamada en < 60s) | no ejecuta query a DB |
| 4 | cache miss (TTL expirado) | ejecuta query a DB y repopula caché |
| 5 | `invalidate_cache(tenant_id)` + siguiente llamada | ejecuta query a DB |
| 6 | circuit breaker: 2 fallas → retorna `MultiAgentEngine` todavía | contador < umbral |
| 7 | circuit breaker: 3 fallas → retorna `SoloEngine` aunque modo = multi | circuito abierto |
| 8 | circuit breaker: 5 min después → retorna `MultiAgentEngine` (half-open) | reset del circuito |
| 9 | dos tenants simultáneos: uno solo, uno multi | cada uno resuelve independiente |
| 10 | modo desconocido en DB (dato corrupto) | fallback a `SoloEngine`, log WARNING |

---

## 7. Endpoint `GET /admin/ai-engine/health`

### 7.1 Propósito

Permite al frontend verificar que ambos motores están operativos antes de que el CEO confirme un cambio. También útil como healthcheck de monitoreo externo.

### 7.2 Contrato de la respuesta

```
GET /admin/ai-engine/health
Authorization: Bearer {jwt}
X-Admin-Token: {token}

HTTP 200 OK
Content-Type: application/json

{
  "solo": {
    "status": "ok" | "fail",
    "latency_ms": 234,
    "detail": "Agent responded with 'pong' as expected"
  },
  "multi": {
    "status": "ok" | "fail",
    "latency_ms": 1890,
    "detail": "Supervisor routed to ReceptionAgent in 1 hop"
  }
}
```

- Siempre retorna HTTP 200. El estado de cada motor está en `status`.
- `latency_ms` es el tiempo real de la probe, no una estimación.
- `detail` es un string en español, legible por el CEO en el modal.
- Si un motor todavía no está implementado (fase F2), `multi.status = 'fail'` con `detail = 'Motor multi-agente no implementado todavía'`. Esto es comportamiento esperado y correcto en F2.

### 7.3 Probe del motor TORA-solo

1. Instanciar `AgentExecutor` vía `get_agent_executable()` (`main.py:7030`) — sin tenant específico
2. Llamar `executor.ainvoke({"input": "responde exactamente: pong", "chat_history": []})` con timeout de 10 segundos
3. Verificar que el output contiene "pong" (case-insensitive)
4. Si timeout o excepción: `status = 'fail'`, `detail` incluye el tipo de error

**Importante**: la probe de TORA-solo usa las credenciales de OpenAI del servidor, NO toca la DB de tenants, NO ejecuta tools de escritura.

### 7.4 Probe del motor multi-agente

1. Instanciar el `StateGraph` compilado desde `agents/graph.py`
2. Invocar con un `AgentState` mínimo: `{messages: [HumanMessage("necesito turno para mañana")], tenant_id: "__healthcheck__", phone_number: "+0000000000"}`
3. Verificar que el supervisor retorna un agente destino (cualquier agente válido) en < 15 segundos
4. **Los tools NO se ejecutan en la probe**: el `AgentState` de healthcheck usa un flag `is_healthcheck=True` que los nodos verifican antes de ejecutar tools reales
5. Si timeout o excepción: `status = 'fail'`

### 7.5 Autenticación

El endpoint requiere `Depends(verify_admin_token)` como todos los endpoints `/admin/*`. No requiere rol CEO para el GET (el selector en el frontend ya lo restringe, y el healthcheck puede ser útil para DevOps).

### 7.6 Archivos afectados

| Acción | Archivo |
|--------|---------|
| Nuevo | `orchestrator_service/routes/ai_engine_health.py` |
| Modificado (registro de router) | `orchestrator_service/main.py` (incluir el nuevo router) |

---

## 8. Endpoint PATCH para cambiar el modo

### 8.1 Opción A — Extender `PATCH /admin/settings/clinic`

Agregar `ai_engine_mode: Optional[str]` al modelo `ClinicSettingsUpdate` en `admin_routes.py:3392`. El handler (~línea 3396) ya escribe en `tenants`; agregar el campo nuevo a la cláusula UPDATE.

**Validación inline antes de la escritura**:
1. Si `ai_engine_mode` está presente en el request body, verificar que el valor es `'solo'` o `'multi'` (422 si no)
2. Si cambia de `'solo'` a `'multi'`, ejecutar internamente la probe del motor multi (como el healthcheck)
3. Si la probe falla, retornar HTTP 422 con body `{"detail": "Motor multi-agente no disponible: {detalle del fallo}"}`
4. Si la probe pasa (o si el cambio es a `'solo'`, que siempre se permite), aplicar el UPDATE
5. Llamar `engine_router.invalidate_cache(tenant_id)` para que el próximo turno use el modo nuevo inmediatamente

**No se ejecuta la probe si el cambio es a `'solo'`**: TORA-solo siempre está disponible.

### 8.2 Opción B — Nuevo `PUT /admin/tenants/{id}/ai-engine`

Endpoint dedicado según lo propuesto en k2UCI tasks.md T4.4. Más explícito, ruta separada, más fácil de auditar en logs.

### 8.3 Decisión recomendada

**Opción A**. Reutiliza el endpoint que ya consume `ConfigView.tsx` en la sección de settings. Reduce cambios en el frontend (mismo `fetch` call). La validación inline está especificada con suficiente detalle para que sea implementable sin ambigüedad. Si en el futuro se necesita un endpoint dedicado (ej. para automation), se puede agregar sin romper nada.

### 8.4 Archivos afectados

| Acción | Archivo | Líneas aproximadas |
|--------|---------|-------------------|
| Modificado | `orchestrator_service/admin_routes.py` | ~3392-3450 (modelo `ClinicSettingsUpdate` y handler) |
| Modificado | `orchestrator_service/models.py` | clase `Tenant` (~línea 187) |

---

## 9. Frontend — Selector en `ConfigView.tsx`

### 9.1 Ubicación

Tab `general` de `ConfigView.tsx`, después del selector de idioma (`ui_language`). El bloque completo del selector de motor debe estar envuelto en `{user?.role === 'ceo' && (...)}`, usando el gate ya existente en la línea 898 del archivo.

### 9.2 Estructura del componente

```tsx
{user?.role === 'ceo' && (
  <div className="border border-white/[0.06] rounded-xl p-4 space-y-3">
    <label className="text-white/70 text-sm font-medium">
      {t('settings.ai_engine_label')}
    </label>
    <select
      value={settings.ai_engine_mode ?? 'solo'}
      onChange={(e) => handleEngineChange(e.target.value)}
      className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2"
      disabled={isCheckingHealth}
    >
      <option value="solo">{t('settings.engine_solo')}</option>
      <option value="multi">{t('settings.engine_multi')}</option>
    </select>
    <p className="text-white/40 text-xs">
      {t('settings.ai_engine_helper')}
    </p>
  </div>
)}
```

### 9.3 Flujo de cambio paso a paso

1. CEO selecciona el motor target en el `<select>`
2. Se abre un modal de confirmación (no se aplica el cambio todavía)
3. El modal muestra un spinner mientras llama a `GET /admin/ai-engine/health` (timeout 20s en el frontend)
4. El modal se actualiza con el resultado:
   - "TORA-solo: ✓ OK (234ms)" en verde
   - "Multi-Agente: ✓ OK (1890ms)" en verde
   - O el engine en fail con el detalle del error en rojo
5. Si el motor **destino** está OK: el botón "Confirmar cambio" está habilitado
6. Si el motor destino está en `fail`: el botón está deshabilitado con tooltip "Motor no disponible"
7. Al confirmar: `PATCH /admin/settings/clinic` con `{ai_engine_mode: 'multi'}` (o `'solo'`)
8. Toast de éxito: "Motor cambiado a Multi-Agente" / "Motor cambiado a TORA-solo"
9. Reload del estado local de settings (no full page reload)
10. Si el PATCH retorna 422 (probe falló en el servidor): mostrar el detalle del error en un toast de error

**Estado del selector**: mientras el modal está abierto, el `<select>` está deshabilitado para evitar cambios dobles.

### 9.4 Claves i18n nuevas

Agregar en `es.json`, `en.json`, `fr.json`:

| Clave | es | en | fr |
|-------|----|----|-----|
| `settings.ai_engine_label` | Motor de IA conversacional | Conversational AI Engine | Moteur d'IA conversationnel |
| `settings.engine_solo` | Solo (TORA legacy) | Solo (TORA legacy) | Solo (TORA legacy) |
| `settings.engine_multi` | Multi-Agente (LangGraph) | Multi-Agent (LangGraph) | Multi-Agent (LangGraph) |
| `settings.ai_engine_helper` | El cambio afecta todas las conversaciones nuevas. Las conversaciones en curso terminan en el motor actual. | Change affects all new conversations. Ongoing ones finish on the current engine. | Le changement affecte toutes les nouvelles conversations. Les conversations en cours se terminent sur le moteur actuel. |
| `settings.engine_health_checking` | Verificando disponibilidad de motores... | Checking engine availability... | Vérification de la disponibilité des moteurs... |
| `settings.engine_confirm_title` | Confirmar cambio de motor | Confirm engine change | Confirmer le changement de moteur |
| `settings.engine_change_success` | Motor cambiado exitosamente | Engine changed successfully | Moteur changé avec succès |
| `settings.engine_target_unavailable` | Motor destino no disponible | Target engine unavailable | Moteur cible indisponible |

### 9.5 Archivos afectados

| Acción | Archivo |
|--------|---------|
| Modificado | `frontend_react/src/views/ConfigView.tsx` |
| Modificado | `frontend_react/src/locales/es.json` |
| Modificado | `frontend_react/src/locales/en.json` |
| Modificado | `frontend_react/src/locales/fr.json` |

### 9.6 Criterios de aceptación frontend

- [ ] El selector solo es visible para usuarios con `role === 'ceo'`
- [ ] El health check se ejecuta antes de habilitar el botón Confirmar (no al cargar la página)
- [ ] El botón Confirmar está deshabilitado si el motor destino tiene `status = 'fail'`
- [ ] El cambio a `'solo'` siempre tiene el botón Confirmar habilitado (TORA-solo es estable)
- [ ] El texto helper muestra la advertencia de impacto en conversaciones en curso
- [ ] El selector refleja el valor actual guardado en DB al cargar la página

---

## 10. Sistema multi-agente

### 10.1 Lo que se hereda del plan k2UCI sin cambios

Los siguientes elementos se implementan exactamente como está especificado en `openspec/changes/tora-to-multi-agent/spec.md` (branch `claude/multi-agent-system-plan-k2UCI`):

- **Arquitectura supervisor + 6 agentes**: Reception, Booking, Triage, Billing, Anamnesis, Handoff
- **Estructura de carpeta `orchestrator_service/agents/`** con los archivos `base.py`, `supervisor.py`, y un archivo por agente
- **Distribución de tools**: cada agente tiene acceso solo al subconjunto de `DENTAL_TOOLS` relevante a su dominio
- **`PatientContext` layers**: Profile (PG), Episodic (PG), Semantic (pgvector), Working (Redis 30min TTL)
- **Formato de prompts**: archivos Markdown en `agents/prompts/` con secciones Role, Tools, Handoff rules, Examples
- **Handoff protocol**: agente origen llama `handoff(target_agent, reason, context_delta)` y detiene su ejecución
- **Max hops**: 5 por turno antes de forzar una respuesta de cierre y handoff a Handoff agent
- **Timeout de turno**: 45 segundos totales por turno (suma de todos los hops)

### 10.2 Cambios respecto al plan k2UCI

| Aspecto | Plan k2UCI original | C3 (este spec) | Razón |
|---------|---------------------|----------------|-------|
| Columna en `tenants` | `multi_agent_enabled BOOL` + `multi_agent_mode TEXT('off'\|'shadow'\|'live')` | `ai_engine_mode TEXT('solo'\|'multi')` | Simplificación: shadow descartado, dos campos → uno |
| Modos de operación | off, shadow, live | solo, multi | Shadow mode explícitamente descartado |
| Número de migración (columna) | 010 | 015 | Migraciones 010-014 ya existen en main |
| Número de migración (tablas) | (misma) | 016 | Separación de responsabilidades |
| Health check endpoint | No especificado | `GET /admin/ai-engine/health` (§7) | Prerequisito para el selector CEO |
| Frontend selector | No especificado | spec completo en §9 | Parte del scope C3 |
| Circuit breaker | No especificado | `engine_router` (§6.6) | Protección producción |
| `openai_compat.py` | Asumido existente | Debe crearse (§3) | Confirmado que NO existe |
| Agente de comparación shadow | IncludedAgent | Eliminado | Shadow mode descartado |

### 10.3 Implementación de los 6 agentes

La especificación detallada de rol, tools y prompts de cada agente está en el plan k2UCI. Se referencia aquí para no duplicar:

**Reception** (`agents/reception.py`): punto de entrada. Identifica el intent del paciente, recopila datos básicos, decide a qué agente especializado derivar. Tools: `search_patient`, `get_patient_basic_info`.

**Booking** (`agents/booking.py`): gestión completa de turnos. Tools: `check_availability`, `confirm_slot`, `book_appointment`, `list_my_appointments`, `cancel_appointment`, `reschedule_appointment`, `list_professionals`, `list_services`.

**Triage** (`agents/triage.py`): análisis de urgencia clínica. Tools: `triage_urgency`, `list_services`.

**Billing** (`agents/billing.py`): verificación de pagos y consultas de precio. Tools: `verify_payment_receipt`, `get_tenant_billing_config`.

**Anamnesis** (`agents/anamnesis.py`): recolección de historia clínica. Tools: `save_patient_anamnesis`, `get_patient_anamnesis`, `save_patient_email`.

**Handoff** (`agents/handoff.py`): derivación a humano. Tools: `derivhumano`.

Cada agente extiende `agents/base.py` e implementa `async def run(self, state: AgentState) -> AgentState`.

### 10.4 `PatientContext` service

**Archivo:** `orchestrator_service/services/patient_context.py`

El servicio expone:

```python
async def load_context(tenant_id: str, phone_number: str, thread_id: str) -> PatientContext
async def save_context(ctx: PatientContext) -> None
async def apply_delta(ctx: PatientContext, delta: dict) -> PatientContext
```

**Tenant isolation**: TODA operación lleva `tenant_id` como filtro obligatorio. No existe ninguna operación cross-tenant. El servicio lanza `ValueError` si `tenant_id` está vacío o es None.

**Working context en Redis**: key `pctx:{tenant_id}:{phone_number}`, TTL 30 minutos. Se usa para la memoria de trabajo del turno actual.

**Semantic context en pgvector**: usa la tabla `faq_embeddings` existente + la tabla `patient_memories` (si existe) para RAG por paciente.

La especificación detallada de cada capa (Profile, Episodic, Semantic, Working) está en el plan k2UCI.

### 10.5 LangGraph wiring

**Archivo:** `orchestrator_service/agents/graph.py`

```python
from langgraph.graph import StateGraph
from agents.state import AgentState

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("reception", reception_node)
    graph.add_node("booking", booking_node)
    graph.add_node("triage", triage_node)
    graph.add_node("billing", billing_node)
    graph.add_node("anamnesis", anamnesis_node)
    graph.add_node("handoff", handoff_node)
    graph.set_entry_point("supervisor")
    # Edges condicionales desde supervisor hacia cada agente
    # Edges de retorno desde cada agente hacia supervisor (para re-routing)
    # Edge de fin desde supervisor cuando decision = "respond"
    return graph.compile(checkpointer=PostgresCheckpointer())
```

**`AgentState`** (en `agents/state.py`): TypedDict con `messages`, `tenant_id`, `phone_number`, `thread_id`, `patient_context`, `active_agent`, `hop_count`, `is_healthcheck`.

**`PostgresCheckpointer`**: implementación de `BaseCheckpointSaver` de LangGraph que lee/escribe en `patient_context_snapshots`. Reemplaza el checkpointer in-memory del plan k2UCI.

**Decisión del supervisor**: basada en el último `HumanMessage` y el `PatientContext`. El supervisor usa un LLM call con un prompt de clasificación, NO reglas heurísticas. Esto lo hace más robusto a variaciones de lenguaje.

### 10.6 Archivos nuevos del sistema multi-agente

```
orchestrator_service/
├── agents/
│   ├── __init__.py
│   ├── base.py            — clase base BaseAgent
│   ├── state.py           — AgentState TypedDict
│   ├── graph.py           — build_graph(), PostgresCheckpointer
│   ├── supervisor.py      — SupervisorAgent: routing y re-routing
│   ├── reception.py       — ReceptionAgent
│   ├── booking.py         — BookingAgent
│   ├── triage.py          — TriageAgent
│   ├── billing.py         — BillingAgent
│   ├── anamnesis.py       — AnamnesisAgent
│   ├── handoff.py         — HandoffAgent
│   └── prompts/
│       ├── supervisor.md
│       ├── reception.md
│       ├── booking.md
│       ├── triage.md
│       ├── billing.md
│       ├── anamnesis.md
│       └── handoff.md
├── services/
│   ├── engine_router.py   — NUEVO
│   └── patient_context.py — NUEVO
├── core/
│   └── openai_compat.py   — NUEVO (prerequisito)
├── routes/
│   └── ai_engine_health.py — NUEVO
└── alembic/versions/
    ├── 015_ai_engine_mode_column.py — NUEVO
    └── 016_multi_agent_tables.py   — NUEVO
```

---

## 11. Plan de tests global

### 11.1 Tests unitarios

| Módulo | Archivo de tests | Tests mínimos |
|--------|-----------------|---------------|
| `openai_compat` | `tests/test_openai_compat.py` | 4 (§3.4) |
| `engine_router` | `tests/test_engine_router.py` | 10 (§6.8) |
| `supervisor` | `tests/agents/test_supervisor.py` | 20 (heredado plan k2UCI) |
| `reception` | `tests/agents/test_reception.py` | 10 |
| `booking` | `tests/agents/test_booking.py` | 10 |
| `triage` | `tests/agents/test_triage.py` | 10 |
| `billing` | `tests/agents/test_billing.py` | 10 |
| `anamnesis` | `tests/agents/test_anamnesis.py` | 10 |
| `handoff` | `tests/agents/test_handoff.py` | 10 |
| `patient_context` | `tests/test_patient_context.py` | 8 |

**Tests de `patient_context` requeridos**:
- Carga con tenant_id correcto → retorna contexto del paciente
- Carga con tenant_id incorrecto → retorna contexto vacío (NO cross-tenant leak)
- `save_context` con tenant_id vacío → lanza `ValueError`
- Working context expira en Redis después de TTL
- `apply_delta` actualiza solo los campos del delta, no sobreescribe el resto
- Dos tenants con el mismo phone_number → contextos independientes (isolation)
- Serialización/deserialización de AgentState en JSONB roundtrip
- Lock optimista en `save_context` (no race condition en turnos paralelos del mismo paciente)

### 11.2 Tests de integración

| # | Caso | Verificación |
|---|------|-------------|
| I1 | Switch `solo→multi` vía endpoint + siguiente turno | `agent_turn_log` tiene registro, `buffer_task` usó `MultiAgentEngine` |
| I2 | Switch `multi→solo` + siguiente turno | `buffer_task` usó `SoloEngine`, no se accede a `patient_context_snapshots` |
| I3 | Health check con multi-agente no inicializado | `multi.status = 'fail'` con detalle legible |
| I4 | Health check con ambos motores OK | ambos `status = 'ok'` y `latency_ms > 0` |
| I5 | Dos tenants simultáneos (uno solo, uno multi) | cada turno resuelto por motor correcto |
| I6 | Circuit breaker: 3 fallas → caída a solo → 5 min → recovery | comportamiento según §6.6 |

### 11.3 Smoke test E2E manual

**Prerequisito**: staging con migraciones 015 y 016 aplicadas, sistema multi-agente implementado.

Secuencia:
1. CEO entra a Settings → tab General → ve selector de motor en modo "Solo (TORA legacy)"
2. CEO selecciona "Multi-Agente (LangGraph)" → modal de confirmación aparece con spinner
3. Modal muestra resultado del health check: ambos motores OK (o fail si multi aún no implementado)
4. CEO confirma → toast "Motor cambiado exitosamente"
5. Conversación de prueba vía WhatsApp: pedir turno para mañana → respuesta del agente Booking
6. CEO vuelve a Settings → selecciona "Solo (TORA legacy)" → confirma
7. Conversación de prueba: misma solicitud → respuesta de TORA-solo
8. Verificar `agent_turn_log`: solo tiene registros del paso 5 (modo multi), no del paso 7

---

## 12. Plan de rollout

| Fase | Descripción | Acción | Criterio para avanzar |
|------|-------------|--------|-----------------------|
| F0 | Migraciones | Aplicar 015 y 016 en staging | `alembic upgrade head` sin errores; tabla `patient_context_snapshots` y columna `ai_engine_mode` existen |
| F1 | Prerequisito | Implementar `core/openai_compat.py` + tests | 4 tests pasan |
| F2 | Wiring básico | Implementar `engine_router.py` + health endpoint + frontend selector; multi-agente NO implementado aún | Selector visible para CEO, health check retorna `solo: ok, multi: fail` correctamente |
| F3 | Sistema multi-agente | Implementar `patient_context.py` + supervisor + 6 agentes + grafo LangGraph | Tests unitarios de todos los agentes pasan; `MultiAgentEngine.process_turn` resuelve un turno de prueba |
| F4 | Health check completo | Health check del motor multi retorna `ok` | Endpoint retorna `multi: ok` con latencia medida |
| F5 | Smoke test | Smoke test manual §11.3 completo | CEO puede hacer switch solo↔multi y tener conversaciones en ambos modos |
| F6 | Piloto interno | Habilitar modo multi para 1 tenant interno (el tenant del equipo de desarrollo, NO el de la Dra. Laura) | 1 semana sin circuit breaker activado, sin errores en `agent_turn_log` |
| F7 | Documentación | Actualizar `CLAUDE.md` con la nueva arquitectura dual-engine | PR mergeado |

**Nota sobre F6**: el primer tenant en modo multi NO debe ser un tenant de producción con pacientes reales. Usar un tenant de staging o el tenant del propio equipo de desarrollo. La Dra. Laura pasa a modo multi solo después de F6 exitoso y decisión explícita.

---

## 13. Riesgos

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|--------|-------------|---------|------------|
| R1 | LangGraph introduce latencia extra > 2s por turno en modo multi | Media | Alto | Benchmark durante F3. Si latencia > 2s, perfilar y optimizar antes de F4. El circuit breaker protege en prod. |
| R2 | `patient_context_snapshots` crece sin control (no hay TTL ni limpieza) | Alta | Medio | Agregar job de limpieza de snapshots con `updated_at < now() - interval '7 days'` como parte de F3 |
| R3 | El supervisor elige el agente equivocado en casos ambiguos | Media | Medio | 20 tests de routing del supervisor cubren los casos principales. Monitorear `agent_turn_log.handoff_to` en F6 para detectar patrones de error |
| R4 | `openai_compat.py` rompe el comportamiento de TORA-solo legacy al ser usado inadvertidamente | Baja | Alto | La regla es explícita: `openai_compat` solo lo usan los agentes nuevos. TORA-solo (`main.py:7039`) no lo importa. Code review obligatorio en el PR |
| R5 | Migración 015 falla en prod si `tenants` tiene triggers o constraints no documentadas | Baja | Alto | Ejecutar `\d tenants` en prod antes del deploy. La migración es un solo ALTER TABLE con DEFAULT, que es no-bloqueante en Postgres 13 |
| R6 | El health check probe de TORA-solo consume tokens de OpenAI en cada vez que el CEO abre el modal | Media | Bajo | El probe usa `gpt-4o-mini` con un mensaje de 5 tokens. Costo estimado < $0.001 por check. Aceptable. Si preocupa, agregar un rate limit de 1 health check por minuto por tenant |
| R7 | Redis no disponible hace que `patient_context.py` falle para el working context | Media | Medio | Degradación graciosa: si Redis falla, working context se carga desde `patient_context_snapshots` en Postgres con penalidad de latencia. Log WARNING pero no excepción |
| R8 | Dos instancias del servicio (restart en EasyPanel) procesan el mismo turno simultáneamente en modo multi | Baja | Alto | `UNIQUE(tenant_id, phone_number, thread_id)` en `patient_context_snapshots` evita snapshots duplicados. El lock optimista en `save_context` detecta race conditions |

---

## 14. Definition of Done

- [ ] Migraciones 015 (`ai_engine_mode` column) y 016 (`patient_context_snapshots`, `agent_turn_log`) aplicadas en staging y en producción
- [ ] `orchestrator_service/core/openai_compat.py` creado con `get_chat_model()` y `safe_chat_completion()`, con 4 tests pasando
- [ ] `orchestrator_service/services/engine_router.py` con `SoloEngine`, `MultiAgentEngine`, caché 60s, y circuit breaker (3 fallas → 5 min fallback), con 10 tests pasando
- [ ] `GET /admin/ai-engine/health` responde con status y latencia de ambos motores
- [ ] `PATCH /admin/settings/clinic` acepta `ai_engine_mode: 'solo' | 'multi'` con health check inline antes de escritura; retorna 422 si el motor destino está en fail
- [ ] Selector en `ConfigView.tsx` visible solo para CEO, con modal de confirmación que muestra resultado del health check y deshabilita el botón si el motor destino está en fail
- [ ] Claves i18n agregadas en `es.json`, `en.json`, `fr.json`
- [ ] Sistema multi-agente implementado: supervisor + 6 agentes (Reception, Booking, Triage, Billing, Anamnesis, Handoff) en `orchestrator_service/agents/`
- [ ] `orchestrator_service/services/patient_context.py` con tenant isolation verificada (8 tests pasando)
- [ ] LangGraph `StateGraph` compilado con `PostgresCheckpointer` escribiendo en `patient_context_snapshots`
- [ ] Tests unitarios: ≥ 10 tests por agente + 20 tests del supervisor, todos pasando
- [ ] Smoke test manual §11.3 completado: switch solo→multi→solo con conversaciones de prueba en ambos modos
- [ ] `CLAUDE.md` actualizado con sección de arquitectura dual-engine

---

## 15. Out of scope

Los siguientes ítems están explícitamente excluidos de C3 y no deben implementarse en este cambio:

- **Migración de Nova voice assistant** al engine router: Nova usa WebSocket directo a OpenAI Realtime API, no pasa por `buffer_task.py`
- **A/B testing automático**: no hay comparación automática de métricas entre motores. El cambio es 100% manual por el CEO
- **Shadow mode**: descartado explícitamente. No se implementa `ai_engine_mode = 'shadow'`
- **Per-phone whitelist**: descartado. El modo es por tenant, no por número de teléfono individual
- **Override per-conversación**: descartado. Una conversación no puede cambiar de motor a mitad
- **Refactor de DENTAL_TOOLS**: los 14 tools de `main.py` se reutilizan sin modificación en los agentes. Su refactor o consolidación es un cambio separado
- **Eval harness con 50 conversaciones reales**: movido a fase posterior al DoD, después del rollout F7
- **Métricas comparativas de calidad**: no hay dashboard de comparación TORA-solo vs multi-agente en C3
- **Cambios al flujo de WhatsApp service**: el servicio de WhatsApp en puerto 8002 no requiere modificación; toda la lógica de routing está en `buffer_task.py`
