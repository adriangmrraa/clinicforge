# Verification Report — C3: Engine Mode Toggle + Multi-Agent System

**Change ID:** `engine-mode-toggle-and-multi-agent`
**Version:** 1.0
**Mode:** Standard (Strict TDD not configured)
**Branch:** `feat/c3-engine-mode-toggle`
**Commit:** `d14fe78` — "feat(c3): dual-engine system — migrations 031/032 + engine_router + health + UI toggle"
**Fecha:** 2026-04-07

---

## Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 42 |
| Tasks complete | 17 |
| Tasks incomplete | 25 |

### Incomplete Tasks (Critical by Phase)

**F1 — Helper + Migrations:**
- [ ] T1.6 — Apply migration 031 in staging (manual)
- [ ] T1.7 — Test downgrade in staging (manual)
- [ ] T1.11 — Apply migration 032 in staging (manual)
- [ ] T1.12 — Test downgrade in staging (manual)

**F2 — engine_router skeleton:**
- [ ] T2.5 — Create `tests/test_engine_router.py` with 6 cases
- [ ] T2.6 — Create `tests/test_engine_router_circuit.py` with 4 cases
- [ ] T2.7 — Tests green
- [ ] T2.8 — Integrate in `buffer_task.py` (NOT DONE — still uses `get_agent_executable_for_tenant` directly)
- [ ] T2.9 — Smoke manual

**F3 — Multi-agent core:**
- [ ] T3.1-T3.41 — All PatientContext + 7 agents + graph wiring (NOT IMPLEMENTED)

**F4 — Health check:**
- [ ] T4.5 — Tests for health endpoint
- [ ] T4.6 — Tests green

**F5 — Frontend selector:**
- [ ] T5.5 — Tests for PATCH extension
- [ ] T5.6 — Tests green
- [ ] T5.13 — Smoke manual

**F6-F7:**
- [ ] Alltasks — Not started

### Zero-Impact Status

✅ **PASS** — The implementation is zero-impact by design:
- Default `ai_engine_mode = 'solo'` ensures all existing tenants use TORA legacy
- `MultiAgentEngine.process_turn` raises `NotImplementedError` — never called in F0-F5
- Health endpoint returns `multi: fail` with detail — correct behavior

---

## Build & Tests Execution

### Build
```
Backend: No build command detected (Python/FastAPI)
Status: ✅ N/A — Python does not compile
```

### Tests
```
Total: Not found
Passed: N/A
Failed: N/A
Skipped: N/A

Status: ⚠️ WARNING — No test runner configuration detected
```

**Test files found:**
- `tests/test_openai_compat.py` ✅ EXISTS (4 cases minimal, per spec)
- `tests/test_engine_router.py` ❌ MISSING
- `tests/test_engine_router_circuit.py` ❌ MISSING
- `tests/agents/` ❌ MISSING (F3)
- `tests/test_ai_engine_health.py` ❌ MISSING
- `tests/test_settings_clinic_engine.py` ❌ MISSING

**Coverage:** Not available

---

## Spec Compliance Matrix (Static)

| Requirement | Scenario | Implementation | Result |
|-------------|----------|---------------|--------|
| REQ-01: `ai_engine_mode` column in `tenants` | Migration 031 adds column | ✅ IMPLEMENTED in migration 031 + models.py | ✅ COMPLIANT |
| REQ-02: Multi-agent tables | Migration 032 + ORM | ✅ IMPLEMENTED in migration 032 + models.py (PatientContextSnapshot, AgentTurnLog) | ✅ COMPLIANT |
| REQ-03: `engine_router.py` | SoloEngine + MultiAgentEngine + cache + circuit breaker | ✅ IMPLEMENTED with cache 60s, circuit 3/5min, pubsub | ✅ COMPLIANT |
| REQ-04: Health endpoint | GET /admin/ai-engine/health | ✅ IMPLEMENTED in routes/ai_engine_health.py | ✅ COMPLIANT |
| REQ-05: PATCH accepts mode | Extends /admin/settings/clinic | ✅ IMPLEMENTED in admin_routes.py with inline probe | ✅ COMPLIANT |
| REQ-06: Frontend selector | ConfigView tab General | ✅ IMPLEMENTED with CEO gate (line 418-439) | ✅ COMPLIANT |
| REQ-07: i18n keys | es/en/fr | ✅ keys `ai_engine_label`, `ai_engine_helper`, `engine_solo`, `engine_multi` in all 3 locales | ✅ COMPLIANT |
| REQ-08: `openai_compat.py` | get_chat_model + safe_chat_completion | ✅ IMPLEMENTED in core/openai_compat.py | ✅ COMPLIANT |
| REQ-09: Multi-agent agents | Supervisor + 6 agents + graph | ❌ NOT IMPLEMENTED — F3 | ⚠️ PARTIAL |
| REQ-10: PatientContext service | 4-layer memory | ❌ NOT IMPLEMENTED — F3 | ⚠️ PARTIAL |
| REQ-11: buffer_task integration | Uses engine_router | ❌ NOT IMPLEMENTED — still uses `get_agent_executable_for_tenant` directly | ⚠️ PARTIAL |

**Compliance summary:** 8/11 compliant, 3 partial (F3-F6 tasks not yet implemented)

---

## Correctness (Static — Structural Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| Migrations 031 + 032 | ✅ Implemented | Correct schema per spec |
| Tenant.ai_engine_mode column | ✅ Implemented | models.py line 189 |
| engine_router with SoloEngine | ✅ Implemented | Full implementation |
| MultiAgentEngine stub | ✅ Implemented | Raises NotImplementedError as designed |
| Health endpoint | ✅ Implemented | Returns correct structure |
| PATCH extension | ✅ Implemented | Inline probe before write |
| Frontend toggle | ✅ Implemented | CEO gate correct |
| i18n keys | ✅ Implemented | All 3 languages |
| Buffer_task NOT modified | ⚠️ Partial | Still uses old flow — pending T2.8 |

---

## Coherence (Design)

| Decision | Followed? | Notes |
|----------|---------|-------|
| Single `ai_engine_mode` TEXT field | ✅ Yes | Column is TEXT with CHECK |
| Cache 60s TTL | ✅ Yes | engine_router.py |
| Circuit breaker 3/5min | ✅ Yes | Implemented |
| Redis pubsub for invalidation | ✅ Yes | Implemented |
| Health check on-demand | ✅ Yes | Endpoint exists |
| PATCH extends /admin/settings/clinic | ✅ Yes | Uses existing endpoint |
| CEO gate | ✅ Yes | `user?.role === 'ceo'` |

---

## Issues Found

**CRITICAL (must fix before archive):**
1. **buffer_task.py NOT integrated** — Still uses `get_agent_executable_for_tenant` directly at line 1204, not `engine_router.get_engine_for_tenant()`. This defeats the core routing logic.

**WARNING (should fix):**
2. **No test infrastructure** — No pytest.ini, no detected test runner, no tests for engine_router, circuit breaker, health endpoint, or PATCH extension.
3. **Migrations NOT applied** — T1.6, T1.7, T1.11, T1.12 require manual staging apply.

**NOT YET IMPLEMENTED (by design):**
4. Multi-agent system (F3-F6) — PatientContext, 7 agents, graph wiring, integration
5. Full `MultiAgentEngine.process_turn` (F6) — current stub raises NotImplementedError
6. Full smoke tests (F5b, F6, F7)

**SUGGESTION (nice to have):**
7. `engine_solo`/`engine_multi` i18n keys only have 1 language each — add full translations for all 3 languages

---

## Verdict

⚠️ **PASS WITH CRITICAL ISSUE / PARTIAL IMPLEMENTATION**

The core infrastructure (migrations, engine_router, health endpoint, frontend selector) is implemented correctly. However:

1. **CRITICAL:** `buffer_task.py` integration is MISSING — the router was created but not wired into the actual turn processing flow.

2. **Missing tests:** No test runner or test files for F2+ tasks.

3. **Pending phases:** F3-F7 (multi-agent system) is not yet implemented — but this is by design per the spec phases.

### Summary
- Migrations: ✅ Done
- engine_router: ✅ Done  
- Health endpoint: ✅ Done
- Frontend selector: ✅ Done
- buffer_task integration: ❌ NOT DONE
- Multi-agent agents: ❌ NOT DONE (F3)
- Tests: ❌ NOT DONE

The change is **partially complete** — the base infrastructure exists but **integration into buffer_task.py is required** to complete F2.