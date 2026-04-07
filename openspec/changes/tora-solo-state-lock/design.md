# Design — C2: TORA-Solo State Lock + Date Validator

**Change ID:** `tora-solo-state-lock`
**Companion:** `spec.md`, `tasks.md`
**Status:** Draft
**Fecha:** 2026-04-07

---

## 1. Resumen del approach

Este change ataca tres bugs (#1 fecha invertida, #4 pérdida de estado, #5 list_my_appointments vacío) aplicando dos patrones complementarios: un **validador de presentación post-LLM** que corre en `services/buffer_task.py` entre el `executor.ainvoke()` y el `response_sender.send_sequence()`, y una **máquina de estados conversacional en Redis** keyed por `(tenant_id, phone_normalized)` con TTL de 30 minutos. No hay cambios de schema en PostgreSQL: toda la capa de estado vive en Redis con fallback seguro a IDLE si el cache no responde.

El orden de aplicación es por riesgo creciente. Primero Bug #5 (refactor cosmético de phone normalization, 1 día), después Bug #1 (módulo aislado de validación de fechas, 2 días), finalmente Bug #4 (máquina de estados con hooks en 6 tools + doble guard input/output en buffer_task.py, 3-4 días). El Bug #4 se subdivide en cinco fases secuenciales — módulo standalone, hooks write-only, input-side guard, output-side guard, tests e2e — para poder revertir cualquier fase sin tocar las anteriores.

El principio guía es **reversibilidad total**: el change no crea columnas nuevas, no toca migraciones Alembic, y todo comportamiento nuevo puede desactivarse por feature flag (`ENABLE_DATE_VALIDATOR`, `ENABLE_STATE_MACHINE`) o por `redis-cli FLUSHDB` si hiciera falta. Un revert de los commits de la rama deja a TORA exactamente en su estado actual. Esta propiedad es crítica porque C2 es arquitectónicamente el change de mayor riesgo del umbrella fuera de C3.

El alcance está bound a TORA-solo: Nova voice (WebSocket independiente) y los jobs proactivos (`jobs/`) no tocan `buffer_task.py` y por lo tanto quedan fuera del change.

---

## 2. Decisiones de diseño clave

### 2.1 Bug #1 — Validador de presentación, NO fix de parser

**Decisión:** Insertar un validador en `services/buffer_task.py` que corre DESPUÉS de `executor.ainvoke()` y ANTES de `response_sender.send_sequence()`. El validador extrae las fechas canónicas de `intermediate_steps` (los outputs de las tools), busca patrones de fecha en el texto del LLM (`DD/MM`, `DD/MM/YYYY`, `weekday DD/MM`) y, si encuentra una fecha del LLM que NO matchea ninguna canónica pero matchea un swap (DD↔MM), reemplaza con la canónica.

**Alternativas descartadas:**
- **A. Fix en `parse_date()`:** ya es correcto (`dayfirst=True`). El bug NO está en el parser — el LLM reformatea la fecha en su texto de respuesta de forma independiente al parser. Inaccionable.
- **B. Hardening puro del system prompt:** insuficiente. Los LLMs siguen reformateando dates en la salida aunque el prompt indique lo contrario. Útil como defensa en profundidad, no como fix principal.
- **C. Estructurar la respuesta del LLM como JSON y renderizar nosotros:** rompe la naturaleza conversacional, requiere refactor masivo del system prompt y del response_sender, y reduce la calidad del texto.
- **D. Validador post-LLM (elegida):** aislada, reversible, se puede desactivar con un feature flag, no toca el system prompt salvo opcionalmente.

**Trade-offs:**

| Aspecto | Validador post-LLM | Parse JSON estructurado | Hardening del prompt |
|---------|---|---|---|
| Risk | Bajo | Alto | Cero |
| Effectiveness | Alto | Total | Bajo |
| Effort | Bajo | Alto | Cero |
| Reversible | Sí (un boolean) | No | N/A |

### 2.2 Bug #4 — State machine en Redis, NO en Postgres

**Decisión:** El estado conversacional vive en Redis con TTL 30 min, NO en una columna de `patients` ni en `chat_conversations`.

**Alternativas descartadas:**
- **A. Columna `conversation_state` en `patients`:** requiere migración Alembic, persiste indefinidamente (basura), conflicto con pacientes que tienen múltiples canales activos.
- **B. Tabla nueva `conversation_states`:** igual, requiere migración + cleanup job + tests adicionales.
- **C. Campo en `chat_conversations`:** la conversación tiene id pero el state machine es per-`(tenant, phone)`, no per-conversation. Distintas `chat_conversations` pueden pertenecer al mismo flujo de booking.
- **D. Redis con TTL (elegida):** zero schema changes, auto-cleanup, fácil reset, fácil debug (`redis-cli`), coherente con el patrón `slot_lock:` ya existente.

**Por qué TTL = 30 min:** una conversación de booking típica termina en menos de 10 minutos. 30 minutos cubre interrupciones razonables del paciente (miró otro chat, salió a buscar el DNI). Después de 30 min sin actividad asumimos que el paciente abandonó y volvemos a IDLE, lo que permite iniciar un flujo nuevo sin interferencia.

**Por qué keyed por `(tenant_id, phone_normalized)` y no por `conversation_id`:** los pacientes pueden iniciar una nueva conversación (nuevo `chat_conversation_id`) sin que la anterior cierre formalmente. El estado debe seguir al teléfono del paciente, no al record de conversación técnica.

### 2.3 Input-side guard vs Output-side guard

La máquina de estados se enforza con **doble defensa**:

- **Input-side guard (preventivo, cheap):** antes de invocar al LLM, `buffer_task.py` lee el estado actual. Si `state == OFFERED_SLOTS` y el mensaje del paciente matchea un intent de selección (regex + keywords), inyecta un bloque `[STATE_HINT: El paciente ya vio slots. Si elige uno, llamá confirm_slot/book_appointment — NO re-llames check_availability.]` en el system prompt. Costo: cero requests extra.
- **Output-side guard (correctivo, more expensive):** después del `ainvoke`, inspecciona `intermediate_steps`. Si el estado previo era `OFFERED_SLOTS`, el LLM llamó a `check_availability` otra vez, y el mensaje del usuario NO matcheaba re-search intent, entonces el LLM ignoró el hint. Se dispara UN retry con un nudge más fuerte (p. ej. `[STATE_ENFORCEMENT: Re-llamar check_availability está prohibido en este turno. Usá confirm_slot.]`). Costo: un segundo `ainvoke` (latencia adicional).

La razón para tener ambos: el input-side es el camino feliz y cubre 90% de los casos sin costo. El output-side es la red de seguridad para cuando el LLM ignora el hint (empíricamente pasa con mensajes ambiguos como "dale"). Un solo guard no alcanza porque cada uno cubre una clase distinta de falla.

### 2.4 Intent detection — regex vs LLM

**Decisión:** Regex + lista de keywords. NO usar un LLM para clasificar intent (sería un LLM call extra por turno, doblando el costo y la latencia).

**Patterns de selection intent (activa el guard):**
- Numéricos: `^[1-3]$`, `el (primero|segundo|tercero)`, `el (uno|dos|tres)`
- Demostrativos: `^(ese|esa|este|esta)\b`, `agendam[eí]`, `dale`, `confirma`, `quiero ese`, `ok dale`, `va`, `perfecto`
- Específicos: `el del \d{1,2}/\d{1,2}`, `el del \d{1,2} de \w+`, `el \d{1,2} a las`

**Patterns de re-search intent (desactiva el guard, permite nueva búsqueda):**
- `otra fecha`, `otro día`, `más opciones`, `mostrame más`, `no me sirve`, `no hay otro`, `más tarde`, `más temprano`, `siguiente semana`

Los falsos positivos del selection regex no son críticos porque el hint es una **sugerencia**, no una orden — el LLM puede ignorarlo si el mensaje real no encaja con el state. Los falsos negativos (no detectar selección) son los que activan el output-side guard como red de seguridad.

### 2.5 Output-side guard — retry limit = 1

**Decisión:** Si el output-side guard detecta que el LLM ignoró el hint de estado, hace **UN solo retry** con un nudge más fuerte. NO bucle. Si el segundo intento también ignora el estado, se deja pasar con degradación graceful y se loggea el caso con nivel WARNING para revisión manual.

**Justificación:** 2+ retries producirían latencia inaceptable (3+ invocaciones de LLM en un solo turn del paciente). Un retry está en el límite de lo tolerable para un chat que el usuario espera en ~5 segundos. Además, si el LLM ignora DOS veces el mismo hint, probablemente hay una razón contextual legítima que el regex no captó.

### 2.6 Bug #5 — Refactor mínimo de phone normalization

**Decisión:** Extraer la lógica de normalización a `normalize_phone_digits()` (función ya existente en `main.py:269`), llamarla desde `list_my_appointments` ANTES del SQL, pasar el resultado como query parameter. Eliminar el `REGEXP_REPLACE` del SQL.

**Por qué unificar es mejor que arreglar el regex SQL:** single source of truth, testeable en Python puro, evita divergencias futuras entre el path de write (donde se normaliza en Python) y el path de read (donde se normaliza en SQL). Además, `list_my_appointments` es el único consumidor problemático identificado; el refactor es local y sin riesgo de propagación.

### 2.7 Coexistencia con `slot_lock:` Redis existente

El namespace nuevo `convstate:{tenant_id}:{phone}` NO reemplaza al `slot_lock:{slot_key}` existente (que es per-slot, TTL 120s, creado por `confirm_slot`). Ambos coexisten con responsabilidades distintas:

```
slot_lock:abc123          → "reservá físicamente este slot para este teléfono por 120s"
convstate:1:5491122334455 → "en qué paso del flujo está este paciente (30 min)"
```

El `slot_lock` protege contra doble-booking de un slot a través de múltiples usuarios/conversaciones. El `convstate` protege contra el LLM olvidándose de qué paso del flujo está haciendo dentro de UNA conversación. Son ortogonales.

---

## 3. Diagramas

### 3.1 State machine completo

```
        ┌─────┐
        │IDLE │◄──────────────────────┐
        └──┬──┘                       │
           │ check_availability       │ cancel/reschedule
           │ tool runs                │ o TTL 30min expira
           ▼                          │
   ┌──────────────┐                   │
   │OFFERED_SLOTS │◄────┐             │
   └──────┬───────┘     │ user pide   │
          │             │ más opciones│
          │ confirm_slot│ (re-search  │
          ▼             │  intent)    │
   ┌──────────────┐     │             │
   │ SLOT_LOCKED  │─────┘             │
   └──────┬───────┘                   │
          │ book_appointment success  │
          ├──────────────┐            │
          ▼              ▼            │
    ┌─────────┐  ┌──────────────────┐ │
    │ BOOKED  │──│ PAYMENT_PENDING  │ │
    └────┬────┘  └────────┬─────────┘ │
         │                │           │
         │        verify_payment      │
         │        success             │
         │                ▼           │
         │        ┌──────────────────┐│
         │        │ PAYMENT_VERIFIED ││
         │        └────────┬─────────┘│
         │                 │          │
         └─────────────────┴──────────┘
```

### 3.2 Flujo de un turno con state machine

```
Inbound message → buffer_task.process_buffer_task()
    │
    ▼
Read convstate from Redis (get_state)
    │
    ▼
Match user intent against current state
    │ if state == OFFERED_SLOTS and _detect_selection_intent(msg):
    │     inject [STATE_HINT: ...] into system prompt
    ▼
build_system_prompt(hint=optional)
    │
    ▼
executor.ainvoke()
    │
    ▼
Inspect intermediate_steps:
    │ if state was OFFERED_SLOTS
    │ and LLM called check_availability
    │ and NOT _detect_research_intent(msg):
    │     → retry 1x with stronger nudge (bounded)
    ▼
date_validator.validate_and_correct(response_text, intermediate_steps)
    │
    ▼
Update convstate based on which tools ran this turn
    │ check_availability → OFFERED_SLOTS
    │ confirm_slot        → SLOT_LOCKED
    │ book_appointment    → BOOKED | PAYMENT_PENDING
    │ verify_payment      → PAYMENT_VERIFIED
    │ cancel/reschedule   → IDLE
    ▼
response_sender.send_sequence()
    │
    ▼
Patient
```

### 3.3 Date validator pseudo-flow

```
Input: response_text (LLM output), intermediate_steps (tool outputs)
    │
    ▼
canonical_dates = extract_canonical_dates(intermediate_steps)
    │   (list of (date_obj, display_str, source_tool) tuples)
    │
    ▼
text_dates = regex_find_dates_in_text(response_text)
    │   (list of (match_span, match_str, parsed_date_attempt))
    │
    ▼
for text_date in text_dates:
    ├── if text_date matches any canonical → OK, leave it
    ├── elif swap(text_date) matches a canonical
    │       → REPLACE match_span in text with canonical.display
    │       → log correction at WARNING
    └── else → no canonical match → log WARNING, leave it
            (do NOT blindly replace)
    │
    ▼
return (corrected_text, list[Correction])
```

---

## 4. Cambios por archivo

### 4.1 NEW `orchestrator_service/services/conversation_state.py`

Módulo nuevo que encapsula la máquina de estados.

**Responsabilidad:** get/set/transition/reset del estado conversacional en Redis.

**Funciones públicas:**
- `get_state(tenant_id, phone) -> dict`
- `set_state(tenant_id, phone, state, **fields) -> None`
- `transition(tenant_id, phone, expected_from, to, **fields) -> bool`
- `reset(tenant_id, phone) -> None`

**Constants:**
- `VALID_STATES = ['IDLE', 'OFFERED_SLOTS', 'SLOT_LOCKED', 'BOOKED', 'PAYMENT_PENDING', 'PAYMENT_VERIFIED']`
- `CONVSTATE_TTL = 1800`  (30 minutos)
- `REDIS_KEY_PREFIX = 'convstate'`

**Dependencias:** Redis async client del módulo existente. No importa nada de `main.py` (evitamos ciclos).

**Fallback safe:** si Redis levanta excepción en cualquier operación, `get_state` retorna `{state: 'IDLE', ...}` por defecto (comportamiento idéntico al actual sin state machine). `set_state` loggea warning y retorna sin raise.

### 4.2 NEW `orchestrator_service/services/date_validator.py`

Módulo nuevo del validador de presentación de fechas.

**Responsabilidad:** detectar swaps DD↔MM en el texto del LLM y corregir contra fechas canónicas de las tools.

**Funciones públicas:**
- `extract_canonical_dates(intermediate_steps: list) -> list[CanonicalDate]`
- `validate_and_correct(text: str, canonical_dates: list[CanonicalDate]) -> tuple[str, list[dict]]`

**Helpers privados:**
- `_regex_find_dates_in_text(text) -> list[TextDate]`
- `_match_with_swap(text_date, canonicals) -> Optional[CanonicalDate]`

**Dataclass interno:**
```python
@dataclass
class CanonicalDate:
    date_obj: date
    display: str       # como vino de la tool, ej "12/05" o "Lunes 12/05"
    source_tool: str   # "check_availability" | "book_appointment" | ...
```

**Logger:** todas las correcciones se loguean a stdout nivel WARNING con formato estructurado `{correction, original, replaced_with, tool_source}` para permitir análisis posterior.

### 4.3 `orchestrator_service/services/buffer_task.py` (MOD)

Modificaciones en el flujo de procesamiento:

- **Pre-ainvoke (~line 998):** leer `convstate` vía `get_state`. Si state == `OFFERED_SLOTS` y `_detect_selection_intent(user_msg)` → inyectar bloque `[STATE_HINT: ...]` al construir el system prompt.
- **Helpers nuevos:** `_detect_selection_intent(msg)` y `_detect_research_intent(msg)` — regex compiladas a nivel módulo, retornan bool.
- **Post-ainvoke:** llamar `date_validator.validate_and_correct(response_text, intermediate_steps)` antes del `response_sender.send_sequence()`.
- **Output-side guard:** después del ainvoke, si state previo == `OFFERED_SLOTS` Y `check_availability` aparece en `intermediate_steps` Y NOT `_detect_research_intent(user_msg)` → hacer UN retry con nudge reforzado. Constant `MAX_STATE_RETRIES = 1`.
- **Post-send:** actualizar `convstate` en base a qué tools se ejecutaron este turno, vía `set_state` (write-path único).
- **Eliminación del recovery loop muerto (`1529-1588`)** queda fuera de este change (pertenece a C1).

### 4.4 `orchestrator_service/main.py` (MOD)

Cambios mínimos, limitados a hooks puntuales dentro de las tools:

- **Hook en `check_availability` (~line 1291):** al final del happy path, llamar `conversation_state.set_state(tenant_id, phone, 'OFFERED_SLOTS', last_offered_slots=[...])`.
- **Hook en `confirm_slot` (~line 4504):** al final del happy path, `set_state('SLOT_LOCKED', last_locked_slot={...})`.
- **Hook en `book_appointment` (~line 2101):** al final del happy path, `set_state('BOOKED')` o `set_state('PAYMENT_PENDING')` según si la cita requiere seña.
- **Hook en `verify_payment_receipt`:** al final del happy path, `set_state('PAYMENT_VERIFIED')`.
- **Hook en `cancel_appointment` y `reschedule_appointment`:** al final, `reset(tenant_id, phone)` (vuelta a IDLE).
- **Refactor `list_my_appointments` (~line 3360-3433):** usar `normalize_phone_digits()` en Python antes del SQL. Eliminar `REGEXP_REPLACE`. Añadir `logger.info(f"list_my_appointments input={raw} normalized={norm} results={n}")`.
- **Hardening opcional del system prompt (~line 6713-6840):** agregar instrucción "Al mencionar una fecha, copiala exactamente como apareció en el último resultado de check_availability". Marcado como opcional porque puede revertirse si produce regresión estilística.

---

## 5. Estructuras de datos nuevas

### 5.1 Redis keys

| Key | Type | TTL | Set by | Read by |
|-----|------|-----|--------|---------|
| `convstate:{tenant_id}:{phone}` | string (JSON) | 1800s | `conversation_state.set_state`, hooks en 6 tools | `conversation_state.get_state`, `buffer_task` pre-ainvoke |

### 5.2 Schema del JSON value de convstate

```json
{
  "state": "OFFERED_SLOTS",
  "last_offered_slots": [
    {
      "date": "2026-05-12",
      "time": "10:00",
      "treatment": "blanqueamiento",
      "professional_id": 1
    }
  ],
  "last_locked_slot": null,
  "updated_at": "2026-04-07T13:45:00-03:00"
}
```

Campos opcionales (null cuando no aplican): `last_offered_slots`, `last_locked_slot`, `last_booked_appointment_id`.

### 5.3 CanonicalDate dataclass (interno del validator)

```python
@dataclass
class CanonicalDate:
    date_obj: date
    display: str        # ej: "12/05" o "Lunes 12/05"
    source_tool: str    # ej: "check_availability"
```

### 5.4 Sin DB migrations

Se confirma explícitamente: **C2 no incluye migraciones Alembic**. La cadena de migraciones (001 → 009) no se toca. Toda la nueva superficie de estado vive en Redis.

---

## 6. Contratos de funciones nuevas

### 6.1 `conversation_state` module

```python
async def get_state(tenant_id: int, phone: str) -> dict:
    """Returns {state, last_offered_slots, last_locked_slot, updated_at}.
    Returns {state: 'IDLE', ...} if not found OR if Redis fails.
    Fallback seguro: cualquier excepción de Redis → IDLE."""

async def set_state(tenant_id: int, phone: str, state: str, **fields) -> None:
    """Writes the new state with TTL=1800s. Validates state name against VALID_STATES.
    Logs warning if Redis fails but does not raise."""

async def transition(tenant_id: int, phone: str,
                     expected_from: str, to: str, **fields) -> bool:
    """Atomic check-and-set. Returns False if current state != expected_from.
    Usado para verificar transiciones válidas cuando importa evitar carreras."""

async def reset(tenant_id: int, phone: str) -> None:
    """Sets state back to IDLE. Idempotente."""

VALID_STATES = [
    'IDLE',
    'OFFERED_SLOTS',
    'SLOT_LOCKED',
    'BOOKED',
    'PAYMENT_PENDING',
    'PAYMENT_VERIFIED',
]
```

### 6.2 `date_validator` module

```python
async def extract_canonical_dates(intermediate_steps: list) -> list[CanonicalDate]:
    """Parsea los outputs de las tools en intermediate_steps buscando fechas
    canónicas. Soporta check_availability, book_appointment, list_my_appointments,
    reschedule_appointment. Retorna lista (posiblemente vacía)."""

async def validate_and_correct(
    text: str,
    canonical_dates: list[CanonicalDate],
) -> tuple[str, list[dict]]:
    """Returns (corrected_text, applied_corrections).
    applied_corrections es lista de dicts {original, replaced_with, reason}
    para logging y métricas."""
```

### 6.3 `buffer_task` helpers nuevos

```python
_SELECTION_INTENT_RE: re.Pattern    # compilada a nivel módulo
_RESEARCH_INTENT_RE: re.Pattern

def _detect_selection_intent(msg: str) -> bool: ...
def _detect_research_intent(msg: str) -> bool: ...
```

---

## 7. Casos de test

| Bug | Test type | File | Cantidad |
|-----|-----------|------|----------|
| #1 | unit | `tests/test_date_validator.py` | 10 |
| #1 | integration | `tests/test_buffer_task_date_validator.py` | 3 |
| #4 | unit | `tests/test_conversation_state.py` | 8 |
| #4 | unit | `tests/test_buffer_task_state_guard.py` | 12 |
| #4 | integration | `tests/test_state_machine_e2e.py` | 5 |
| #5 | unit | `tests/test_phone_normalization.py` | 5 |
| #5 | integration | `tests/test_book_then_list.py` | 2 |

Total: 45 casos.

---

## 8. Orden de implementación recomendado

Por riesgo creciente y dependencias:

1. **Día 1 — Bug #5 phone normalization.** Warm-up de menor riesgo. Un refactor local en `list_my_appointments` + 5 tests unit + 2 integration. Si algo sale mal, el revert es un cherry-pick trivial.
2. **Día 2-3 — Bug #1 date validator.** Módulo aislado sin side effects. 10 tests unit cubriendo casos edge (swap claro, swap ambiguo, fecha fuera de canónicas, múltiples fechas en un solo texto). 3 tests integration hitteando buffer_task con mocks.
3. **Día 4 — Bug #4 fase A: state machine module standalone.** `conversation_state.py` con 8 tests unit (get, set, transition happy, transition conflict, reset, Redis fail get, Redis fail set, fallback IDLE). No conectado aún a nada.
4. **Día 5 — Bug #4 fase B: hooks write-only en 6 tools.** Agregar llamadas a `set_state` al final de cada tool del flujo. Sin enforcing aún — solo escribe. Verificar que TORA sigue funcionando 100% igual que antes (smoke test con booking feliz).
5. **Día 6 — Bug #4 fase C: input-side guard.** Activar lectura de state + inyección de STATE_HINT. Primer punto donde el comportamiento observable cambia. Smoke manual con "Agéndame el del 12 de mayo".
6. **Día 7 — Bug #4 fase D: output-side guard con bounded retry.** Segunda capa defensiva. Cuidado con el timeout.
7. **Día 8 — Integration tests e2e + optional prompt hardening + smoke completo.**

---

## 9. Modo "observación" para Bug #4 (recomendado)

Antes de activar el **enforcing** de los guards (fases C y D), se recomienda correr al menos 48h en modo "write-only" (fase B sola). En ese modo las tools ya escriben state pero ningún guard bloquea nada. Durante ese periodo se instrumenta logging adicional:

```
logger.info(f"[STATE_OBSERVE] tenant={t} phone={p} prev_state={s} "
            f"intent_selection={sel} intent_research={res} "
            f"tools_called={tools}")
```

El análisis de estos logs permite:
- Validar que el regex de selection intent tiene pocas falsas alarmas en datos reales.
- Medir cuántos turns realmente serían interceptados por el output-side guard.
- Ajustar la lista de keywords antes del enforcement.

Este paso reduce dramáticamente el riesgo de producción porque convierte el guard en un cambio empírico en lugar de teórico.

---

## 10. Riesgos de implementación

| # | Riesgo | Probabilidad | Mitigación |
|---|--------|-------------|-----------|
| R1 | Date validator corrige una fecha que el LLM puso a propósito (caso raro) | Baja | Solo corrige si hay exact swap match contra canónica. Si no hay swap exacto, loggea y deja pasar. |
| R2 | Intent detection regex tiene falso positivo y bloquea consulta válida | Media | El hint es sugerencia, no orden — el LLM puede ignorarlo. Fase de observación previa valida el regex. |
| R3 | Output-side guard genera latencia perceptible (segundo ainvoke) | Media | Limit 1 retry, timeout corto en el segundo ainvoke, logging del tiempo total del turn. |
| R4 | Redis caído → state machine falla | Baja | Fallback safe a IDLE = comportamiento idéntico al actual sin state machine. |
| R5 | Hooks en tools aplicados parcialmente (algunos sí, otros no) → estado inconsistente | Media | Tests integration por cada tool + test e2e que ejercita el flujo completo. |
| R6 | Phone normalization unificada rompe lookup en patients existentes | Baja | El refactor solo afecta `list_my_appointments` (read path). No toca writes ni el lookup de patients. |
| R7 | System prompt hardening (cita la fecha tal cual) confunde al LLM en otros contextos | Baja | Opcional, se puede revertir aisladamente si causa regresión estilística. |

---

## 11. Open questions para el apply phase

1. ¿El validador de fechas debe correr SIEMPRE o solo cuando `state` ∈ {`OFFERED_SLOTS`, `SLOT_LOCKED`, `BOOKED`}? Default recomendado: siempre (cheap, no hace daño).
2. ¿Aplicamos el system prompt hardening en este change o lo dejamos como follow-up? Default recomendado: opcional dentro de C2, no bloquea el merge.
3. ¿El TTL de 30 min se puede hacer configurable per-tenant o queda hardcoded? Default recomendado: hardcoded en C2, promover a config si surge demanda.
4. ¿Logueamos las correcciones del date validator en una tabla `agent_corrections_log` o solo a stdout? Default recomendado: stdout en C2, tabla queda para un follow-up si hay métricas útiles.
5. ¿El regex de intent se mantiene en código o se mueve a config (más fácil de editar)? Default recomendado: en código en C2, promover a config si el equipo itera frecuente sobre él.
