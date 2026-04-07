# Tasks — C3: Engine Mode Toggle + Multi-Agent System

**Change ID:** `engine-mode-toggle-and-multi-agent`
**Companion:** `spec.md`, `design.md`
**Branch:** `feat/c3-engine-toggle-multi-agent`
**Depends on:** C1 (`tora-solo-quick-wins`) y C2 (`tora-solo-state-lock`) deben estar mergeados antes de comenzar C3.

---

## Convention

- Cada tarea = 1 commit, excepto donde se agrupan explícitamente.
- Conventional commits con scope: `feat(engine):`, `feat(agents):`, `feat(router):`, `feat(core):`, `feat(db):`, `feat(api):`, `feat(ui):`, `chore(c3):`, `docs:`.
- Cada fase tiene su propio go/no-go antes de pasar a la siguiente.
- TDD estricto: tests antes o junto con la implementación.

---

## F0 — Prerequisitos (Día 1)

- [ ] **T0.1** Verificar `alembic heads` confirma que la última migración es `014_add_custom_holiday_hours`.
- [ ] **T0.2** Confirmar que C1 y C2 están mergeados en `main`.
- [ ] **T0.3** Crear branch `feat/c3-engine-toggle-multi-agent` desde `main`.
- [ ] **T0.4** Crear carpetas vacías: `orchestrator_service/agents/`, `orchestrator_service/agents/prompts/`, `tests/agents/`.
- [ ] **T0.5** Commit: `chore(c3): scaffold folders for multi-agent system`

**Go/no-go F0**: C1+C2 mergeados, branch creada, carpetas vacías pusheadas.

---

## F1 — Helper openai_compat + migraciones (Día 2-3)

### openai_compat
- [ ] **T1.1** Crear `orchestrator_service/core/openai_compat.py` con `get_chat_model()` y `safe_chat_completion()` — soporte para gpt-4o, gpt-4o-mini, gpt-5, gpt-5-mini, o1-mini (manejo de `max_tokens` vs `max_completion_tokens`, temperature lock para o-series).
- [ ] **T1.2** Crear `tests/test_openai_compat.py` con 4 casos (gpt-4o, gpt-5, o1-mini, fallback).
- [ ] **T1.3** Tests verdes.
- [ ] **T1.4** Commit: `feat(core): openai_compat helper for multi-family model support`

### Migración 015
- [ ] **T1.5** Crear `orchestrator_service/alembic/versions/015_ai_engine_mode_column.py` con upgrade (`ADD COLUMN ai_engine_mode TEXT NOT NULL DEFAULT 'solo' CHECK IN ('solo','multi')`) y downgrade.
- [ ] **T1.6** Aplicar en staging: `alembic upgrade head`, verificar que la columna existe con default `'solo'` en todos los tenants.
- [ ] **T1.7** Probar downgrade en staging.
- [ ] **T1.8** Modificar `orchestrator_service/models.py` Tenant (líneas 159-187) agregando `ai_engine_mode: Mapped[str]`.
- [ ] **T1.9** Commit: `feat(db): migration 015 — tenants.ai_engine_mode column`

### Migración 016
- [ ] **T1.10** Crear `orchestrator_service/alembic/versions/016_multi_agent_tables.py` con `CREATE TABLE patient_context_snapshots` + `CREATE TABLE agent_turn_log` + índices. Downgrade drops ambas.
- [ ] **T1.11** Aplicar en staging, verificar tablas e índices con `\d` en psql.
- [ ] **T1.12** Probar downgrade en staging.
- [ ] **T1.13** Modificar `models.py` agregando ORM classes `PatientContextSnapshot` y `AgentTurnLog`.
- [ ] **T1.14** Commit: `feat(db): migration 016 — patient_context_snapshots + agent_turn_log`

**Go/no-go F1**: migraciones aplicadas y reversibles en staging, zero impact en TORA-solo.

---

## F2 — engine_router skeleton (Día 4-5)

- [ ] **T2.1** Crear `orchestrator_service/services/engine_router.py` con:
  - `Engine` Protocol (`process_turn`, `probe`).
  - `SoloEngine` (wrappea `get_agent_executable_for_tenant` actual).
  - `MultiAgentEngine` stub (`process_turn` → `raise NotImplementedError`, `probe` → check módulo importable).
  - `TurnContext`, `TurnResult`, `ProbeResult` dataclasses.
- [ ] **T2.2** Implementar cache en memoria con TTL 60s (`dict[uuid, tuple[str, float]]`) + función `_load_mode(tenant_id)` que lee DB.
- [ ] **T2.3** Implementar circuit breaker (contador en memoria, threshold 3, window 60s, recovery 300s).
- [ ] **T2.4** Suscripción al canal Redis `engine_router_invalidate` para invalidación cross-process.
- [ ] **T2.5** Crear `tests/test_engine_router.py` con 6 casos:
  1. Dispatch solo con default.
  2. Dispatch multi cuando `tenants.ai_engine_mode='multi'` (con stub raise).
  3. Cache hit: segunda llamada dentro de 60s no toca DB.
  4. Cache miss: después de TTL, relee DB.
  5. `invalidate_cache` fuerza relectura.
  6. Pubsub recibido invalida cache.
- [ ] **T2.6** Crear `tests/test_engine_router_circuit.py` con 4 casos:
  1. 1 failure no trigger.
  2. 3 failures dentro de 60s → TRIPPED.
  3. Durante TRIPPED, rutea a solo aunque tenant=multi.
  4. Después de 300s, resetea y retoma multi.
- [ ] **T2.7** Tests verdes.
- [ ] **T2.8** Modificar `orchestrator_service/services/buffer_task.py:998` — reemplazar llamada directa a `get_agent_executable_for_tenant` por `engine_router.get_engine_for_tenant(tenant_id).process_turn(ctx)`.
- [ ] **T2.9** Smoke manual en staging: enviar mensaje de prueba, verificar que TORA-solo responde idéntico al comportamiento pre-F2.
- [ ] **T2.10** Commit: `feat(router): engine_router with SoloEngine + MultiAgentEngine stub + circuit breaker`

**Go/no-go F2**: TORA-solo sigue funcionando idéntico, router en su lugar con stub de multi.

---

## F3 — Multi-agent core (Día 6-12)

### Día 6 — PatientContext
- [ ] **T3.1** Crear `orchestrator_service/services/patient_context.py` con `PatientContext` dataclass, `load()`, `apply_delta()`, `to_agent_state()`, `release()`.
- [ ] **T3.2** Implementar 4 layers: Profile (PG read), Episodic (PG read+append), Semantic (pgvector RAG read), Working (Redis hash TTL 30m).
- [ ] **T3.3** Lock optimista Redis `patient_ctx_lock:{tenant_id}:{phone}` con TTL 30s y retry exponencial.
- [ ] **T3.4** Tenant enforcement en TODAS las queries (asserts + `WHERE tenant_id=$1`).
- [ ] **T3.5** Crear `tests/agents/test_patient_context.py` con 8 casos:
  1. Load básico.
  2. Apply delta: append episodic.
  3. Apply delta: update working.
  4. Lock acquired/released correctamente.
  5. Lock contention: segundo turno espera.
  6. Tenant isolation: tenant A no ve datos de tenant B.
  7. Working layer TTL expira.
  8. `to_agent_state` produce estructura correcta.
- [ ] **T3.6** Tests verdes.
- [ ] **T3.7** Commit: `feat(agents): PatientContext service with 4-layer memory`

### Día 7 — State + Base + Graph skeleton
- [ ] **T3.8** Crear `orchestrator_service/agents/state.py` con `AgentState` TypedDict (tenant_id, phone, turn_id, thread_id, messages, next_agent, hop_count, max_hops, context_ref, tool_outputs, done, error).
- [ ] **T3.9** Crear `orchestrator_service/agents/base.py` con `BaseAgent` abstract class (`async run(state) -> state`, `name`, `prompt_path`).
- [ ] **T3.10** Crear `orchestrator_service/agents/graph.py` con `StateGraph` skeleton (nodos vacíos, edges pendientes).
- [ ] **T3.11** Commit: `feat(agents): state, base, graph scaffolding`

### Día 8 — Supervisor
- [ ] **T3.12** Crear `orchestrator_service/agents/supervisor.py` con:
  - 4 reglas determinísticas (human_override, image+payment pending, emergency regex, max_hops).
  - LLM fallback con tool-choice forzado a `route_to(agent_name)`.
- [ ] **T3.13** Crear `orchestrator_service/agents/prompts/supervisor.md` (<500 tokens).
- [ ] **T3.14** Crear `tests/agents/test_supervisor_routing.py` con 20 casos cubriendo las 4 reglas + LLM fallback a cada uno de los 6 agentes + edge cases.
- [ ] **T3.15** Tests verdes.
- [ ] **T3.16** Commit: `feat(agents): supervisor with deterministic rules + LLM fallback`

### Día 9 — Reception + Booking
- [ ] **T3.17** Crear `agents/reception.py` + `prompts/reception.md` + `tests/agents/test_reception.py` (10 casos). Tools: `list_professionals`, `list_services`, FAQ via RAG.
- [ ] **T3.18** Tests verdes.
- [ ] **T3.19** Commit: `feat(agents): reception agent`
- [ ] **T3.20** Crear `agents/booking.py` + `prompts/booking.md` + `tests/agents/test_booking.py` (12 casos). Tools: `check_availability`, `confirm_slot`, `book_appointment`, `list_my_appointments`, `cancel_appointment`, `reschedule_appointment`.
- [ ] **T3.21** Tests verdes.
- [ ] **T3.22** Commit: `feat(agents): booking agent`

### Día 10 — Triage + Billing
- [ ] **T3.23** Crear `agents/triage.py` usando gpt-4o (más fuerte para decisiones clínicas) + `prompts/triage.md` + `tests/agents/test_triage.py` (10 casos). Tools: `triage_urgency` + lógica implante/prótesis.
- [ ] **T3.24** Tests verdes.
- [ ] **T3.25** Commit: `feat(agents): triage agent (gpt-4o)`
- [ ] **T3.26** Crear `agents/billing.py` + `prompts/billing.md` + `tests/agents/test_billing.py` (10 casos). Tools: `verify_payment_receipt`.
- [ ] **T3.27** Tests verdes.
- [ ] **T3.28** Commit: `feat(agents): billing agent`

### Día 11 — Anamnesis + Handoff
- [ ] **T3.29** Crear `agents/anamnesis.py` + `prompts/anamnesis.md` + `tests/agents/test_anamnesis.py` (8 casos). Tools: `save_patient_anamnesis`, `get_patient_anamnesis`, `save_patient_email`.
- [ ] **T3.30** Tests verdes.
- [ ] **T3.31** Commit: `feat(agents): anamnesis agent`
- [ ] **T3.32** Crear `agents/handoff.py` + `prompts/handoff.md` + `tests/agents/test_handoff.py` (6 casos). Tools: `derivhumano`.
- [ ] **T3.33** Tests verdes.
- [ ] **T3.34** Commit: `feat(agents): handoff agent`

### Día 12 — StateGraph wiring
- [ ] **T3.35** Completar `agents/graph.py`: añadir todos los nodos (supervisor + 6 agentes) y edges (supervisor → agent → supervisor o END).
- [ ] **T3.36** Configurar checkpointer PG contra tabla `patient_context_snapshots`.
- [ ] **T3.37** Constantes: `max_hops=5`, `timeout=45s`.
- [ ] **T3.38** Test integration: `tests/agents/test_graph_integration.py` — armar un `AgentState` fake, correr el grafo, verificar que termina en handoff o done sin exceder hops.
- [ ] **T3.39** Tests verdes.
- [ ] **T3.40** Agregar `langgraph>=0.2.0,<0.3.0` a `requirements.txt`.
- [ ] **T3.41** Commit: `feat(agents): LangGraph StateGraph wiring with PG checkpointer`

**Go/no-go F3**: todos los tests de agentes verdes, grafo wiring completo, `MultiAgentEngine` aún no conectado.

---

## F4 — Health check endpoint (Día 13)

- [ ] **T4.1** Crear `orchestrator_service/routes/ai_engine_health.py` con endpoint `GET /admin/ai-engine/health` (requiere JWT CEO).
- [ ] **T4.2** Implementar `_probe_solo(timeout=10)`: instancia `AgentExecutor` con prompt minimal `"Responde pong"` y tools vacías.
- [ ] **T4.3** Implementar `_probe_multi(timeout=15)`: instancia `StateGraph` con `AgentState` sintético y tools mockeadas (no DB).
- [ ] **T4.4** Probes en paralelo con `asyncio.gather(..., return_exceptions=True)`.
- [ ] **T4.5** Crear `tests/test_ai_engine_health.py` con 4 casos:
  1. Ambos OK.
  2. solo OK, multi fail.
  3. Ambos fail.
  4. Timeout de uno.
- [ ] **T4.6** Tests verdes.
- [ ] **T4.7** Registrar el router en `orchestrator_service/main.py`.
- [ ] **T4.8** Commit: `feat(router): /admin/ai-engine/health endpoint with parallel sanity probes`

**Go/no-go F4**: endpoint disponible, retorna estado de ambos motores correctamente.

---

## F5 — Frontend selector + PATCH extension (Día 14)

### F5a — Backend PATCH extension
- [ ] **T5.1** Modificar `orchestrator_service/admin_routes.py:3392` `ClinicSettingsUpdate` agregando `ai_engine_mode: Optional[Literal['solo','multi']] = None`.
- [ ] **T5.2** En el handler, si `ai_engine_mode` presente, correr `_probe_solo` o `_probe_multi` según target ANTES del UPDATE.
- [ ] **T5.3** Si probe falla → `raise HTTPException(422, detail=...)`.
- [ ] **T5.4** Si probe OK → `UPDATE tenants SET ai_engine_mode=? WHERE id=?` + `engine_router.invalidate_cache(tenant_id)` + publish a canal Redis `engine_router_invalidate`.
- [ ] **T5.5** Crear `tests/test_settings_clinic_engine.py` con 6 casos:
  1. PATCH a solo sin cambios: no-op.
  2. PATCH a multi con probe OK: update aplicado.
  3. PATCH a multi con probe fail: 422, no update.
  4. PATCH a valor inválido: 422 validation.
  5. Non-CEO: 403.
  6. Multi-tenant isolation: PATCH de tenant A no afecta tenant B.
- [ ] **T5.6** Tests verdes.
- [ ] **T5.7** Commit: `feat(api): PATCH /admin/settings/clinic accepts ai_engine_mode with inline probe`

### F5b — Frontend selector
- [ ] **T5.8** Modificar `frontend_react/src/views/ConfigView.tsx` tab General — añadir `<select>` para `ai_engine_mode` dentro del bloque existente `{user?.role === 'ceo' && (...)}` (línea 898).
- [ ] **T5.9** Handler `onChange`: llama a `GET /admin/ai-engine/health`, abre modal con resultado.
- [ ] **T5.10** Modal muestra estado de ambos motores (✓/✗ + latencia + error), botón "Confirmar" disabled si target fail.
- [ ] **T5.11** Al confirmar: `PATCH /admin/settings/clinic` con `{ ai_engine_mode: target }`, toast de éxito/error, reload settings.
- [ ] **T5.12** Añadir claves i18n en `locales/es.json`, `locales/en.json`, `locales/fr.json` (namespace `config.aiEngine`).
- [ ] **T5.13** Smoke manual: abrir Settings como CEO, ver selector, ejecutar health check, confirmar switch (dado que MultiAgentEngine.probe aún debería funcionar porque el grafo existe; `process_turn` stub no afecta el probe).
- [ ] **T5.14** Commit: `feat(ui): ai_engine_mode selector in ConfigView with health check modal`

**Go/no-go F5**: selector funcional para CEO, gate por rol correcto, health check responde.

---

## F6 — Activación e integración (Día 15-16)

- [ ] **T6.1** Reemplazar el stub de `MultiAgentEngine.process_turn` en `engine_router.py` con la implementación real (llama a `agents.graph.run_turn(ctx)`).
- [ ] **T6.2** Conectar el checkpointer del grafo con `patient_context_snapshots`.
- [ ] **T6.3** Conectar el log de hops con `agent_turn_log` (insert por cada hop con tenant_id, turn_id, hop_index, agent_name, latency_ms, tool_calls, error).
- [ ] **T6.4** Test integration `tests/test_dual_engine_parallel.py`: dos tenants, uno `solo` y otro `multi`, ambos atendidos correctamente en paralelo sin cross-contamination.
- [ ] **T6.5** Tests verdes.
- [ ] **T6.6** Commit: `feat(engine): activate MultiAgentEngine with full graph + checkpointer + audit log`
- [ ] **T6.7** Smoke manual en staging: crear un tenant interno de testing (NO Dra. Laura), setearlo a `multi` vía UI, mandar mensajes desde un test phone cubriendo los 6 agentes (FAQ, reserva, emergencia, pago, anamnesis, handoff).
- [ ] **T6.8** Verificar `agent_turn_log` muestra hops correctos con latencias razonables.
- [ ] **T6.9** Dejar el tenant interno en `multi` por 7 días con monitoreo activo (logs, tokens, errores).

**Go/no-go F6**: 7 días de tenant interno en `multi` sin incidentes críticos.

---

## F7 — Rollout y documentación (Día 17+)

- [ ] **T7.1** Si F6 estable por 1 semana, presentar a la Dra. Laura el sistema dual-engine + obtener consentimiento explícito.
- [ ] **T7.2** Si consiente, el CEO activa `multi` para el tenant de Dra. Laura vía el selector en ConfigView.
- [ ] **T7.3** Monitorear 1 semana adicional con alertas automáticas en `agent_turn_log` (errores, latencia p95, tokens por turno).
- [ ] **T7.4** Si surgen problemas: toggle inverso vía UI (multi → solo) en segundos.
- [ ] **T7.5** Actualizar `CLAUDE.md` con sección "Dual-Engine Architecture" (solo, multi, router, health check, toggle, PatientContext, agents).
- [ ] **T7.6** Commit: `docs: update CLAUDE.md with dual-engine architecture`
- [ ] **T7.7** Mover C1, C2, C3 a `openspec/changes/archive/`.
- [ ] **T7.8** Crear PR final del umbrella dual-engine y mergear.

**Go/no-go F7**: Dra. Laura con la opción visible (con o sin uso), umbrella cerrado.

---

## Definition of Done

- [ ] Migraciones 015 y 016 aplicadas en producción sin incidentes.
- [ ] `core/openai_compat.py` con 4 tests verdes.
- [ ] `services/engine_router.py` con `SoloEngine`, `MultiAgentEngine`, cache, circuit breaker, invalidación pubsub. 10 tests verdes.
- [ ] `services/patient_context.py` con 4 layers, tenant isolation, lock optimista. 8 tests verdes.
- [ ] 7 componentes de agentes (supervisor + 6 especializados) implementados, cada uno con >=6 tests unit verdes. Total ~86 tests.
- [ ] `agents/graph.py` LangGraph wiring completo con checkpointer PG funcional.
- [ ] `GET /admin/ai-engine/health` responde y diferencia correctamente entre engines. 4 tests verdes.
- [ ] `PATCH /admin/settings/clinic` acepta `ai_engine_mode` con health check inline. 6 tests verdes.
- [ ] Selector funcional en `ConfigView.tsx` para CEO, bloqueado para non-CEO.
- [ ] Smoke E2E manual: switch `solo → multi → solo` funciona sin incidentes.
- [ ] `CLAUDE.md` actualizado con sección dual-engine.
- [ ] Tenant interno en `multi` sin incidentes por >= 7 días.
- [ ] Dra. Laura tiene la opción visible (sin obligación de usarla).
- [ ] C1, C2, C3 archivados. Umbrella cerrado.
