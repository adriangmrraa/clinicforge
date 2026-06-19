# Proposal: Multi-Agent → Solo Parity

## Intent

Make `MultiAgentEngine` behaviorally identical to `SoloEngine` (TORA). All rules from solo's ~1575-line `build_system_prompt()` must exist in the 6-specialist graph. Current gaps: literal `{bot_name}` text in prompts, missing emotional flows F1–F10, absent patient context injection, incomplete booking rules.

## Scope

**In**: (1) 3 critical bugs (interpolation, `AsyncSessionLocal`, probe arg); (2) patient context injection; (3) F1–F10 flows; (4) post-booking 5-block sequence; (5) booking flow parity (Zero Rule, Slot Resolution, No-Elección, Multi-topic Gate); (6) per-specialist gap closure; (7) parity test suite.

**Out**: Solo agent refactoring, new features, supervisor changes, new specialists.

## Capabilities

- **New**: `multi-agent-parity` — multi-agent matches solo across all domains
- **Modified**: `system-prompt` — solo spec accounts for delta rules shared with multi

## Approach

**Phase 1 — Bugs**: Replace raw `"""` with f-strings interpolating `tenant_context.clinic_basics` + `patient_profile.name`. Migrate `PatientContext.load()` → `db.pool`. Fix `SoloEngine.probe()` to pass `system_prompt` arg.

**Phase 2 — Context**: Add `_inject_patient_context()` in `specialists.py` formatting `patient_profile` + `lead_context` into a specialist-accessible block. Wire through `_with_tenant_blocks()`.

**Phase 3 — Prompts**: Reception gets anti-hallucination rules + emotional preamble. BookingAgent gets ~500 lines (Zero Rule, Slot Resolution, No-Elección, Multi-topic Gate, post-booking blocks, confirm flow, anti-loop). Triage gets tool descriptions + protocol details. Billing gets `consultation_price` + bank data + insurance rules. Anamnesis gets email flow + already-collected detection. Handoff gets complaint policy details + escalation.

**Phase 4 — Tests**: Parameterized parity scenarios covering greeting, booking, triage, billing, F1–F10, post-booking. Assert output structure, tool usage, anti-patterns.

## Affected Areas

| Area | Impact | Change |
|------|--------|--------|
| `agents/specialists.py` | Heavy | All 6 prompts expanded |
| `agents/graph.py` | Med | Context injection wiring |
| `services/patient_context.py` | Med | asyncpg migration |
| `services/engine_router.py` | Low | Probe fix |
| `agents/tenant_context.py` | Low | Add billing blocks |
| `tests/` | New | Parity suite |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Routing regressions | Med | Circuit breaker fallback to solo |
| Prompt > context window | Low | Token measurement + chunk per specialist |
| F1–F10 inflates Reception | Med | Shared module, inject on trigger only |

## Rollback

Toggle `ai_engine_mode=solo` per tenant. Circuit breaker trips after 3 failures. Git revert.

## Dependencies

`openspec/specs/system-prompt/spec.md` (delta reference). Existing circuit breaker in `engine_router.py`.

## Success Criteria

- [ ] 3 critical bugs confirmed fixed
- [ ] BookingAgent passes 10 parity scenarios vs SoloEngine
- [ ] F1–F10 produce equivalent responses in both engines
- [ ] Post-booking blocks fire in correct order
- [ ] `patient_profile` fields accessible in all specialist prompts
- [ ] PatientContext uses `db.pool` (no `AsyncSessionLocal`)
- [ ] SoloEngine.probe() returns `ok: true`
