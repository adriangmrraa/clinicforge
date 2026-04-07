# Tasks — Tora → Multi-Agent Migration

**Change ID:** `tora-to-multi-agent`
**Branch:** `claude/multi-agent-system-plan-k2UCI`

---

## Sprint 1 — Foundations

- [ ] T1.1 Añadir `langgraph>=0.2.0` a `orchestrator_service/requirements.txt`.
- [ ] T1.2 Crear migración Alembic `010_multi_agent_store.py` con `patient_context_snapshots`, `agent_turn_log`, columnas `tenants.multi_agent_enabled`, `tenants.multi_agent_mode`.
- [ ] T1.3 Actualizar `models.py` con los nuevos ORM classes.
- [ ] T1.4 Implementar `services/patient_context.py` (`PatientContext.load`, `apply_delta`, `to_agent_state`) con tenant enforcement y Redis lock.
- [ ] T1.5 Tests `tests/agents/test_patient_context.py` (carga, delta, aislamiento multi-tenant, lock).

## Sprint 2 — Graph & Supervisor

- [ ] T2.1 Crear `agents/state.py` con `AgentState` TypedDict.
- [ ] T2.2 Crear `agents/base.py` con `BaseAgent` abstract.
- [ ] T2.3 Implementar `agents/supervisor.py` con reglas determinísticas §7 y LLM fallback.
- [ ] T2.4 Prompts en `agents/prompts/supervisor.md` (<500 tokens).
- [ ] T2.5 Wiring LangGraph en `agents/graph.py` (StateGraph + checkpointer PG).
- [ ] T2.6 Tests `tests/agents/test_supervisor_routing.py` (20 casos).

## Sprint 3 — Specialized Agents

- [ ] T3.1 `agents/reception.py` + prompt + tests.
- [ ] T3.2 `agents/booking.py` + prompt + tests (usando tools existentes `check_availability`, `book_appointment`, etc.).
- [ ] T3.3 `agents/triage.py` + prompt + tests (con `triage_urgency` + lógica implante/prótesis).
- [ ] T3.4 `agents/billing.py` + prompt + tests (con `verify_payment_receipt`).
- [ ] T3.5 `agents/anamnesis.py` + prompt + tests.
- [ ] T3.6 `agents/handoff.py` + prompt + tests (con `derivhumano`).

## Sprint 4 — Integration & Feature Flag

- [ ] T4.1 `services/agent_router.py` con `process_turn` (off/shadow/live).
- [ ] T4.2 Integrar el router en `buffer_task.py` como reemplazo opcional del call directo a Tora.
- [ ] T4.3 Dry-run mode para tools de escritura en shadow.
- [ ] T4.4 Endpoints admin: `PUT /admin/tenants/{id}/multi-agent` para alternar `enabled`/`mode`.
- [ ] T4.5 Frontend: toggle en `ConfigView.tsx` (solo superadmin).

## Sprint 5 — Observability & Eval

- [ ] T5.1 Métricas Prometheus (`agent_turn_duration_ms`, `agent_hops_per_turn`, `agent_handoffs_total`).
- [ ] T5.2 Endpoint `GET /admin/metrics/multi-agent` con resumen diario.
- [ ] T5.3 Eval harness `tests/agents/eval/` con 50 conversaciones anotadas.
- [ ] T5.4 Fuzz test multi-tenant.
- [ ] T5.5 Documentar runbook de rollback en `docs/multi_agent_runbook.md`.

## Sprint 6 — Rollout

- [ ] T6.1 Activar `shadow` en 1 tenant interno. Monitorear 1 semana.
- [ ] T6.2 Análisis de divergencias shadow vs Tora; ajustes.
- [ ] T6.3 Canary `live` en 1 tenant real con consentimiento.
- [ ] T6.4 Rollout progresivo 10% → 50% → 100%.
- [ ] T6.5 Actualizar `CLAUDE.md` con la nueva arquitectura.
- [ ] T6.6 Deprecar code-path Tora (mantener como fallback hasta fase 3).

---

## Definition of Done

- Todos los tests pasan (`pytest tests/agents/`).
- Eval set ≥ 92% accuracy.
- Shadow mode ≥ 7 días sin alertas.
- Runbook de rollback validado en staging.
- `CLAUDE.md` actualizado.
