# Umbrella Proposal — Arquitectura Dual-Engine de IA para ClinicForge

**Status:** Draft
**Owner:** Platform / AI
**Fecha:** 2026-04-07
**Tipo:** Umbrella (orquesta 3 changes hijos)

---

## 1. Resumen ejecutivo

ClinicForge opera hoy con un único motor de IA conversacional (TORA), un agente monolítico LangChain con 9 bugs verificados y sin máquina de estados. Esta propuesta define una hoja de ruta en tres cambios para pasar de ese estado a una arquitectura **dual-engine**: el motor actual endurecido (TORA-solo) y un sistema multi-agente nuevo (LangGraph + Supervisor + 6 agentes especializados), ambos conviviendo con un toggle per-tenant controlado por el CEO desde la UI. El objetivo no es migrar forzosamente, sino darle a la clínica una opción de mejora sin riesgo: primero corregir lo que hay, después agregar lo nuevo, y dejar que el operador elija cuándo hacer el salto.

---

## 2. Contexto y motivación

### 2.1 Estado actual

TORA es un agente monolítico definido en `orchestrator_service/main.py`. Características actuales:

- **~14 tools** registradas en el array `DENTAL_TOOLS` (LangChain).
- **Un único system prompt** inyectado en cada conversación, con toda la lógica de negocio embebida en texto.
- **Sin máquina de estados programática**: el flujo de reserva (buscar → confirmar → registrar) depende del LLM para recordar en qué paso está.
- **Sin validador de presentación**: fechas, precios y markers internos se pasan al LLM y se devuelven al paciente sin filtrado previo.
- **Sin isolación de motor por tenant**: todos los tenants usan el mismo código path.
- **Entry point**: `services/buffer_task.py` procesa los mensajes entrantes de WhatsApp y llama al agente.

Esta arquitectura fue adecuada para el MVP, pero la ausencia de capa de presentación y de estado programático produce una clase de bugs recurrentes que no se pueden resolver sólo con prompt engineering.

### 2.2 Los 9 bugs reproducidos

| # | Severidad | Descripción | Archivo : línea aproximada |
|---|-----------|-------------|---------------------------|
| 1 | 🔴 Crítico | Fecha invertida en texto de confirmación (ej: "12/05" → el LLM escribe "Sábado 05/12") | `main.py` — capa de respuesta del LLM, sin validador de presentación |
| 2 | 🔴 Crítico | Marker `[INTERNAL_PRICE:7000000]` se filtra al paciente sin ser strippeado | `main.py:2047` — emit del tool sin post-procesamiento |
| 3 | 🔴 Crítico | Precio mal escalado ($7.000.000 para blanqueamiento) — bug de datos, sin validación de rango | `main.py` — tool `list_services`, sin capping de sanity check |
| 4 | 🔴 Crítico | Pérdida de estado tras confirmación explícita: LLM re-corre `check_availability` en lugar de llamar `confirm_slot` | `main.py` — ausencia total de state machine programática |
| 5 | 🟠 Medio | `list_my_appointments` retorna vacío tras una reserva exitosa (síntoma del bug #4) | `main.py` — tool `list_my_appointments`, linked al estado corrupto |
| 6 | 🟠 Medio | `_get_slots_for_extra_day()` no llama a `is_holiday()` → feriados aparecen como disponibles en búsqueda por rango | `main.py:892` — función `_get_slots_for_extra_day` |
| 7 | 🟠 Medio | `time_preference` ('tarde'/'mañana') no se propaga al generador de slots de día extra | `main.py` — `_get_slots_for_extra_day`, parámetro ignorado |
| 8 | 🟡 Menor | Saludo institucional completo se repite en cada cambio de tema (sin flag `greeted_at`) | `main.py` — system prompt sin mecanismo de sesión de saludo |
| 9 | 🟡 Menor | Loop de recuperación muerto en `buffer_task.py:1529-1588` genera doble tool-call | `buffer_task.py:1529-1588` — dead-end recovery loop |

### 2.3 Causa raíz común

Los 9 bugs se agrupan en dos clases arquitectónicas distintas:

**Clase A — Ausencia de máquina de estados (bugs #1, #4, #5, #7):**
El agente delega al LLM la responsabilidad de recordar en qué paso del flujo de reserva se encuentra. Sin un estado programático, el LLM puede retroceder, saltear pasos, o reinterpretar la fecha que ya fue acordada. Estos bugs no se resuelven con prompt engineering: el LLM siempre tiene libertad de diverger. La solución es un state lock externo (Redis) que fuerce el próximo tool call según el estado actual.

**Clase B — Higiene mecánica (bugs #2, #3, #6, #8, #9):**
Son errores localizados: un marker no stripeado, un rango de precio sin validar, una función que ignora feriados, un saludo sin flag, un loop de recovery mal implementado. No requieren cambios de arquitectura, sólo correcciones puntuales con cobertura de tests.

Esta distinción es la base para la separación en dos changes de hardening (C1 y C2) antes de introducir el nuevo motor (C3).

---

## 3. Propuesta estratégica

### 3.1 Dos motores, un toggle

La arquitectura propuesta sostiene dos motores de IA conversacional de forma simultánea:

- **TORA-solo (hardened):** el agente monolítico LangChain actual, con los 9 bugs corregidos en C1 y C2. Es el motor por defecto para todos los tenants existentes. Opera sobre el mismo código de `main.py` mejorado.
- **Multi-Agent:** sistema nuevo basado en LangGraph con un Supervisor y 6 agentes especializados, `PatientContext` compartido, y estado programático nativo. Se activa por tenant cuando el CEO lo habilita explícitamente.

Un nuevo módulo `services/engine_router.py` actúa como dispatcher: lee `tenants.ai_engine_mode` desde la base de datos y enruta cada conversación al motor correspondiente. Un health check verificado (`GET /admin/ai-engine/health`) debe pasar antes de que el frontend permita el cambio de motor.

El toggle es un selector simple en la pestaña general de `ConfigView.tsx`, visible únicamente para usuarios con `role === 'ceo'` (gate ya presente en `ConfigView.tsx:898`).

### 3.2 Diagrama de alto nivel

```
WhatsApp / Chatwoot
        │
        ▼
buffer_task.py (services/)
        │
        ▼
engine_router.py  ──── lee tenants.ai_engine_mode
        │
   ┌────┴────┐
   │         │
   ▼         ▼
TORA-solo  Multi-Agent
(main.py)  (LangGraph Supervisor
            + 6 agents)
   │         │
   └────┬────┘
        │
        ▼
   DENTAL_TOOLS
   (tools existentes, sin cambio)
        │
        ▼
   PostgreSQL + Redis
        │
        ▼
   Respuesta → paciente
```

El router es el **único nuevo elemento de infraestructura** entre `buffer_task.py` y los motores. Ambos motores comparten el mismo conjunto de tools ya existentes. Nova voice (OpenAI Realtime API) queda fuera del router y sigue su path independiente.

### 3.3 Por qué dos motores y no migrar directo

Tres razones:

1. **Red de seguridad operativa:** una migración directa al multi-agente en producción sin un motor probado como fallback es inaceptable para una clínica con pacientes activos. Tener TORA-solo endurecido como default garantiza continuidad si el motor nuevo presenta regresiones.

2. **Reducción de riesgo por etapas:** el multi-agente es un sistema nuevo que requiere calibración de cada sub-agente, pruebas de integración y ajuste del Supervisor. Ese trabajo toma semanas. Obligar a todos los tenants a esperarlo antes de corregir los 9 bugs actuales es innecesario.

3. **Control del operador:** la decisión de cuándo adoptar el motor nuevo pertenece al CEO de cada clínica, no al equipo técnico. El toggle per-tenant refleja esa soberanía. También abre la puerta a un A/B futuro si se quiere comparar métricas de satisfacción entre motores.

### 3.4 Por qué tres changes y no uno

Cada change tiene un perfil de riesgo diferente y debe poder shiipearse y hacerse rollback de forma independiente:

- **C1 (mecánico, bajo riesgo):** cambios localizados a funciones específicas y al filtrado de output. Sin impacto en el flujo general. Puede shiipearse en una semana y hacerse rollback con un revert simple.
- **C2 (arquitectónico, riesgo medio):** introduce state lock en Redis y un validador de presentación. Toca `buffer_task.py` y el system prompt. Requiere tests de escenarios de flujo de reserva antes de ir a producción.
- **C3 (sistema nuevo, riesgo alto):** agrega una capa de infraestructura (`engine_router`), una migración de schema, una UI nueva y un sistema multi-agente completo. Si este change se rompe, los tenants que no lo activaron no se ven afectados porque el default es `solo`.

Shiippear los tres juntos elimina esa independencia y convierte cualquier bug en C3 en un bloqueante para las correcciones de C1 y C2.

---

## 4. Los tres changes hijos

### 4.1 C1 — `tora-solo-quick-wins`

- **Folder:** `openspec/changes/tora-solo-quick-wins/`
- **Scope:** bugs #2, #3, #6, #7, #8, #9
- **Outcome:** TORA monolítico ya no filtra markers internos al paciente, no muestra precios con escala incorrecta, no ofrece feriados como disponibles en búsquedas por rango, respeta el filtro de turno (mañana/tarde) en el generador de día extra, no repite el saludo institucional completo en cada cambio de tema, y no ejecuta doble tool-call por el loop de recovery muerto.
- **No incluye:** máquina de estados, validador de fechas en presentación, nueva arquitectura, motor multi-agente, toggle UI.
- **Riesgo:** bajo. Los cambios son localizados a funciones individuales y al post-procesamiento del output del LLM. Cada fix tiene su propio unit test.
- **Semana objetivo:** 1

### 4.2 C2 — `tora-solo-state-lock`

- **Folder:** `openspec/changes/tora-solo-state-lock/`
- **Scope:** bugs #1, #4, #5
- **Outcome:** TORA tiene un state lock por conversación almacenado en Redis. Después de que `check_availability` devuelve slots, el lock registra el estado `AWAITING_CONFIRMATION`. En ese estado, el próximo turn del LLM está restringido a llamar `confirm_slot` o `book_appointment`. Si el paciente expresa explícitamente que quiere ver más opciones ("mostrá más", "otra fecha", "cambiar"), el lock se libera y se permite nueva búsqueda. Un validador de presentación inspecciona el texto final del LLM antes de enviarlo al paciente y detecta swaps DD/MM ↔ MM/DD corrigiéndolos contra la fecha registrada en el state.
- **No incluye:** motor multi-agente, toggle UI, engine_router.
- **Riesgo:** medio. Toca `buffer_task.py` (lógica de despacho) y el system prompt (instrucciones de uso del lock). Requiere tests de al menos 10 escenarios de flujo de reserva (éxito, abandono, re-búsqueda explícita, turno doble).
- **Semana objetivo:** 2

### 4.3 C3 — `engine-mode-toggle-and-multi-agent`

- **Folder:** `openspec/changes/engine-mode-toggle-and-multi-agent/`
- **Scope:**
  - Nuevo módulo `services/engine_router.py` — dispatcher per-tenant basado en `tenants.ai_engine_mode`
  - Migración Alembic 015 — agrega columna `tenants.ai_engine_mode TEXT NOT NULL DEFAULT 'solo'`
  - Endpoint `PUT /admin/tenants/{id}/ai-engine` o extensión de `PATCH /admin/settings/clinic` — actualiza `ai_engine_mode`
  - Endpoint `GET /admin/ai-engine/health` — retorna `{solo: 'ok'|'fail', multi: 'ok'|'fail', detail: {...}}`
  - Selector en `ConfigView.tsx` pestaña general, gate `role === 'ceo'`, con confirmación modal que muestra el resultado del health check antes de aplicar
  - Helper `services/openai_compat.py` — wrapper de `ChatOpenAI` con retry, selección de modelo per-agent, y compatibilidad con gpt-5/o-series (prerequisito para multi-agente)
  - Implementación del sistema multi-agente: Supervisor + 6 agentes especializados en LangGraph, `PatientContext` compartido
  - Migración Alembic 016 — tablas `patient_context_snapshots` y `agent_turn_log`
- **Hereda de:** branch `claude/multi-agent-system-plan-k2UCI` — los archivos `proposal.md`, `spec.md` y `tasks.md` ya redactados en `openspec/changes/tora-to-multi-agent/` son el punto de partida para los sub-documentos de este change.
- **Riesgo:** alto. Sistema nuevo que involucra arquitectura de agentes, nuevas tablas, nueva UI y un módulo de routing crítico. **Mitigación principal:** el modo `solo` es el default; el motor multi-agente sólo se activa cuando el CEO lo elige explícitamente y el health check confirma que está operativo. Si N requests consecutivos fallan en modo `multi`, el circuit breaker revierte automáticamente a `solo` y notifica por Socket.IO al frontend.
- **Semana objetivo:** 3+

---

## 5. Decisiones de arquitectura

### 5.1 Hook point del router

El punto de inserción del router es **`services/buffer_task.py`**, en la línea donde hoy se obtiene el ejecutable del agente para el tenant (función `get_agent_executable_for_tenant` o equivalente). El router se inserta en ese punto exacto y retorna el ejecutable del motor correspondiente (`tora_solo_executor` o `multi_agent_executor`) según `tenants.ai_engine_mode`. El resto de `buffer_task.py` no cambia.

### 5.2 Nivel del toggle

**Per-tenant** via columna `tenants.ai_engine_mode` (TEXT, `DEFAULT 'solo'`, `NOT NULL`). Esta fue la opción confirmada. No se implementa:
- Toggle global (rompe soberanía por tenant)
- Override per-conversación (complejidad sin valor operativo inmediato)
- Shadow mode (agrega latencia y costo sin feedback claro)
- Per-phone override para testing (el CEO puede crear un tenant de prueba separado)

### 5.3 Health check

`GET /admin/ai-engine/health` — requiere JWT + X-Admin-Token. Retorna:

```
{
  "solo":  "ok" | "fail",
  "multi": "ok" | "fail",
  "detail": {
    "solo_latency_ms": number | null,
    "multi_latency_ms": number | null,
    "error": string | null
  }
}
```

El frontend consulta este endpoint **antes** de aplicar el cambio de motor. Si el motor target retorna `"fail"`, el botón de confirmación en el modal queda deshabilitado con un mensaje de error visible. No se permite el switch en ese estado.

### 5.4 Helper `openai_compat`

El módulo `services/openai_compat.py` **no existe hoy en el repositorio** (verificado en el explore). Debe crearse como parte de C3. Es un prerequisito para el sistema multi-agente porque los 6 sub-agentes necesitan selección de modelo per-agent y manejo de retry uniforme. **TORA-solo no lo usa** — sigue instanciando `ChatOpenAI` directamente como hasta ahora. Esto garantiza que la creación del helper no introduce regresiones en el motor existente.

### 5.5 Compatibilidad con Nova

Nova voice (OpenAI Realtime API, `NovaWidget.tsx` + handler en `main.py` ~línea 4713) opera sobre WebSocket y no pasa por `buffer_task.py`. Por lo tanto, **queda completamente fuera del scope del engine_router**. Nova sigue funcionando exactamente igual para todos los tenants independientemente del valor de `ai_engine_mode`. No se requiere ningún cambio en `nova_tools.py` ni en `nova_routes.py`.

---

## 6. Beneficios esperados

| Métrica | Hoy | Tras C1+C2 | Tras C3 |
|---------|-----|-----------|---------|
| Bugs cosméticos visibles al paciente | 6 activos | 0 | 0 |
| Bugs estructurales (estado/fecha) | 3 activos | 0 | 0 |
| Motores disponibles | 1 (TORA monolítico) | 1 (TORA hardened) | 2 (TORA hardened + Multi-Agent) |
| Switching per-tenant | imposible | imposible | UI selector + health check |
| State machine programática | ninguna | Redis lock (TORA-solo) | nativa en LangGraph (multi) |
| Cobertura de tests sobre el flujo de reserva | ~0 | unit tests por bug + 10 escenarios de flujo | unit tests + agent harness LangGraph |
| Control del CEO sobre el motor | ninguno | ninguno | selector en ConfigView gated por rol |

---

## 7. Riesgos y mitigaciones

| Riesgo | Probabilidad | Mitigación |
|--------|-------------|-----------|
| C1 introduce regresión visible al paciente en el output del LLM | Baja | Smoke test por cada bug con conversación de prueba antes de deploy. Revert por commit individual. |
| C2 state lock bloquea casos válidos (paciente quiere ver más opciones después de que se mostraron slots) | Media | El lock acepta intents explícitos de re-búsqueda ("mostrá más", "otra fecha", "quiero cambiar"). Tests de 10 escenarios de uso, incluyendo casos de abandono y re-inicio. |
| C2 validador de presentación produce falso positivo en fechas con formato legítimo | Baja | El validador sólo actúa si detecta un swap confirmado contra la fecha almacenada en el state. Si no hay fecha en el state, no modifica nada. |
| C3 motor multi-agente no responde o responde mal en producción para un tenant que lo activó | Alta (sistema nuevo) | Health check pre-switch. Circuit breaker que revierte a `solo` si N requests consecutivos fallan. Default mode = `solo` para todos los tenants existentes y nuevos. |
| Migraciones 015 y 016 chocan con migraciones de otra branch activa | Media | Verificar `alembic heads` antes de mergear cada change. La cadena actual llega a 009; las migraciones de C3 deben continuar la secuencia correctamente. |
| `openai_compat` mal implementado introduce regresión en TORA-solo | Baja | El helper sólo es usado por los agentes del sistema multi-agente. TORA-solo instancia `ChatOpenAI` directamente, sin pasar por el helper. Tests de integración del helper antes de conectarlo a los sub-agentes. |
| Tenant en modo `multi` experimenta latencia mayor por orquestación de sub-agentes | Media | Documentado como trade-off conocido. El health check incluye latency_ms para que el CEO pueda comparar antes de activar. |

---

## 8. Out of scope (no en este umbrella)

Los siguientes elementos fueron evaluados y descartados explícitamente:

- **Migración de Nova voice al engine_router** — Nova opera por WebSocket independiente; moverla al router agrega complejidad sin beneficio.
- **Agentes proactivos** (lead recovery, reminders, followups) — corren en `jobs/` y no participan del flujo conversacional que gestiona el router.
- **Refactor de los 14 tools de TORA** — los tools existentes se reutilizan sin modificación en ambos motores.
- **A/B testing automático entre motores** — sólo selector manual del CEO. Un A/B automatizado requiere métricas de satisfacción que no están instrumentadas hoy.
- **Override per-conversación** — descartado por el usuario. Agrega complejidad operativa sin valor inmediato.
- **Shadow mode (ejecutar ambos motores en paralelo para comparar)** — descartado. Duplica el costo de tokens y añade latencia sin un mecanismo de comparación definido.
- **Vista side-by-side comparativa de respuestas** — descartado en esta iteración.
- **Soporte multi-idioma nuevo** — las traducciones existentes en `locales/` se mantienen sin cambio.

---

## 9. Definition of Done del umbrella

- [ ] Los 3 changes hijos tienen su propio `proposal.md`, `spec.md`, `design.md` y `tasks.md` en sus respectivos folders bajo `openspec/changes/`
- [ ] C1 aplicado, verificado y archivado — los 6 bugs mecánicos ya no son reproducibles
- [ ] C2 aplicado, verificado y archivado — los 3 bugs de estado/fecha ya no son reproducibles
- [ ] Los 9 bugs documentados en §2.2 no son reproducibles en una conversación de prueba completa (búsqueda → slots → confirmación → booking)
- [ ] C3 aplicado, verificado y archivado:
  - `engine_router.py` existe y rutea correctamente según `tenants.ai_engine_mode`
  - Migraciones 015 y 016 aplicadas en producción sin conflicto
  - Endpoint de health check responde y bloquea switches cuando el motor target falla
  - Selector en `ConfigView.tsx` visible únicamente para CEO, con confirmación modal + health check
  - Sistema multi-agente (Supervisor + 6 agentes) operativo para tenants que lo activen
- [ ] `CLAUDE.md` del proyecto actualizado con la nueva arquitectura dual-engine (sección Architecture y AI Agent Tools)
- [ ] Tests de regresión cubren los 9 bugs y los 10 escenarios de flujo de reserva de C2

---

## 10. Referencias

- **Bug map detallado con file:line:** ver `openspec/changes/tora-solo-quick-wins/spec.md` §2 y `openspec/changes/tora-solo-state-lock/spec.md` §2 (se crean como parte de los changes hijos)
- **Plan multi-agente original:** branch `claude/multi-agent-system-plan-k2UCI`, archivos en `openspec/changes/tora-to-multi-agent/` — `proposal.md`, `spec.md`, `tasks.md`
- **Sovereignty Protocol (tenant isolation):** `CLAUDE.md` §Critical Rules §1
- **Gate de rol CEO en UI:** `frontend_react/src/views/ConfigView.tsx:898` — `user?.role === 'ceo'`
- **Entry point de buffer processing:** `orchestrator_service/services/buffer_task.py:1529-1588` (recovery loop) y línea de despacho al agente
- **Nova voice handler:** `orchestrator_service/main.py` ~línea 4713
- **Nova tools:** `orchestrator_service/services/nova_tools.py`
- **Cadena de migraciones activa:** `orchestrator_service/alembic/` — baseline 001 → 009 pgvector_faq_embeddings (C3 continúa con 015 y 016)
