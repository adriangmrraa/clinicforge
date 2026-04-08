# SDD Proposal: Derivation Escalation Fallback

**Change**: `derivation-escalation-fallback`
**Status**: PROPOSED
**Date**: 2026-04-07
**Author**: SDD Orchestrator

---

## 1. Intent

### Problem Statement

When the AI agent matches a derivation rule and the assigned `target_professional_id` has no available slots within the search window (typically 7 days), the agent returns "no hay disponibilidad" and the conversation dies. The lead is lost even though the clinic may have other professionals who could cover that treatment.

This is a **silent lead drain**: the rule exists, it fires correctly, the primary professional is simply saturated — but no fallback mechanism is attempted before surfacing a dead-end response to the patient.

**Observed scenarios that fail today**:
1. High-value patient asks about implants → derivation rule routes to Dr. A (specialist) → Dr. A is fully booked for 10 days → agent says "no hay turnos" → patient leaves.
2. Saturday emergency → rule targets the on-call professional → that professional marked unavailable → agent says "no hay disponibilidad" instead of trying any available professional.
3. New patient flow → rule targets the head of intake → head of intake is on vacation → zero fallback → lead lost.

### Why This Matters

- **Conversion loss**: Every "no hay disponibilidad" response from a matched-rule path is a lead that could have been saved by routing to a fallback professional.
- **Implicit clinic promise broken**: The derivation rule was set up BY the clinic owner. The owner's intent is "route this type of patient to X". If X is unavailable, the owner would want "try Y next", not "tell the patient to go away".
- **Admin has no control today**: There is no mechanism in the UI or the data model to express "if primary is unavailable, try this other professional (or any professional in the team)".

---

## 2. Scope

### In Scope

| Area | Files | What Changes |
|------|-------|-------------|
| DB schema | `orchestrator_service/alembic/versions/037_derivation_escalation_fallback.py` | Add 5 new columns to `professional_derivation_rules` |
| ORM model | `orchestrator_service/models.py` | Extend `ProfessionalDerivationRule` class |
| Pydantic schemas | `orchestrator_service/admin_routes.py` | Extend `DerivationRuleCreate` / `DerivationRuleUpdate` with new fields + validation |
| CRUD endpoints | `orchestrator_service/admin_routes.py` | `POST/PUT /admin/derivation-rules` accept and persist new fields |
| `check_availability` tool | `orchestrator_service/main.py` (~line 1404) | Escalation algorithm: try fallback when primary returns 0 slots within `max_wait_days_before_escalation` |
| `book_appointment` tool | `orchestrator_service/main.py` (~line 2101) | Accept and persist escalation context so the booking targets the correct professional |
| `_format_derivation_rules()` | `orchestrator_service/main.py` (~line 6130) | Emit fallback info in the prompt block so the agent knows escalation is possible |
| Frontend modal | `frontend_react/src/views/ClinicsView.tsx` (~line 1468) | New "Escalación" sub-section in the derivation rule modal |
| i18n | `frontend_react/src/locales/es.json`, `en.json`, `fr.json` | New translation keys for escalation UI |

### Out of Scope

- **Nova** (internal AI copilot) — no changes needed; Nova uses direct DB queries
- **RAG embeddings for derivation rules** — the existing `upsert_derivation_embedding` hook does not need updating for escalation fields (behavioral, not semantic)
- **Escalation chain depth > 1** — only primary → fallback (one level). Multi-level chains are a future extension.
- **Automatic professional availability monitoring / alerts** — out of scope; this is reactive (on patient request), not proactive
- **WhatsApp service** — no changes to message routing/delivery
- **Analytics / ROI dashboard** — escalation events are not tracked in this change (future)

---

## 3. Approach

### New Fields on `professional_derivation_rules`

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `enable_escalation` | BOOLEAN | `false` | Master switch. When false, behavior is identical to today. |
| `fallback_professional_id` | INTEGER FK → professionals, nullable | NULL | Specific professional to try as fallback. Mutually exclusive intent with `fallback_team_mode`. |
| `fallback_team_mode` | BOOLEAN | `false` | If true, on escalation try ANY active professional in the same treatment categories instead of a specific one. |
| `max_wait_days_before_escalation` | INTEGER | `7` | Window (days) to check for primary availability before triggering escalation. Range: 1–30. |
| `escalation_message_template` | TEXT, nullable | NULL | Spanish template sent to patient when fallback fires. Supports `{primary}` and `{fallback}` placeholders. If NULL, system uses a built-in default. |
| `criteria_custom` | JSONB, nullable | NULL | Reserved for future criteria (urgency_level, patient_history, time_of_day). Schema documented below; stub support only in this change. |

**`criteria_custom` stub schema** (for documentation — not evaluated in this change):
```json
{
  "urgency_level": "high|medium|low",
  "patient_history": "new|existing|any",
  "time_window": {"from": "08:00", "to": "12:00"}
}
```

### Escalation Algorithm in `check_availability`

```
Given derivation rule matched for treatment X:
  1. Query primary professional slots for next max_wait_days_before_escalation days
  2. IF slots found → return normally (no escalation needed)
  3. IF no slots AND enable_escalation = false → return "no disponibilidad" (current behavior)
  4. IF no slots AND enable_escalation = true:
     a. Determine fallback target:
        - fallback_team_mode=true → query ALL active professionals for treatment categories
        - fallback_professional_id IS NOT NULL → query that specific professional
        - both NULL and fallback_team_mode=false → treat as team mode (safe default)
     b. Query fallback target slots for same window
     c. IF fallback slots found → return those slots + inject escalation_message_template into result
     d. IF fallback also empty → return "no disponibilidad" (exhausted chain)
```

**Key invariant**: Rule evaluation ORDER remains deterministic (`priority_order ASC, id ASC`). The escalation algorithm only runs AFTER a rule has already matched — it does not change which rule wins.

### `_format_derivation_rules()` Prompt Changes

Current output (example):
```
REGLA 1 — Implantes:
  Aplica a: any / Categorías: implantes,cirugia
  Acción: agendar con Dr. Juan Pérez (ID: 3)
```

New output when `enable_escalation = true`:
```
REGLA 1 — Implantes:
  Aplica a: any / Categorías: implantes,cirugia
  Acción primaria: agendar con Dr. Juan Pérez (ID: 3)
  Escalación: si Dr. Pérez no tiene turnos en 7 días → intentar con equipo disponible
  Mensaje de escalación: "Hoy Dr. Pérez no tiene disponibilidad en los próximos días, pero podemos coordinar con {fallback} que también atiende este tipo de casos."
```

This tells the agent that escalation is automatic — it does not need to ask the patient for permission; the tool handles it transparently.

### Frontend Modal Addition

Add a collapsible "Escalación" section at the bottom of the derivation rule modal, visible only when the user enables the toggle. Contains:
- Toggle: "Activar escalación automática" (`enable_escalation`)
- (Conditional on toggle ON) Integer input: "Días de espera antes de escalar (1–30)" (`max_wait_days_before_escalation`)
- (Conditional on toggle ON) Radio: "Escalar a profesional específico" / "Escalar al equipo disponible" (`fallback_team_mode`)
- (Conditional on specific professional selected) Dropdown: "Profesional de fallback" (`fallback_professional_id`) — same list as primary professional dropdown
- (Conditional on toggle ON) Textarea: "Mensaje de escalación (opcional)" (`escalation_message_template`) — placeholder shows default Spanish template

---

## 4. Success Criteria

- [ ] Agent NEVER responds "no hay disponibilidad" when a matched-rule professional is saturated AND `enable_escalation = true` AND a fallback slot exists
- [ ] Existing rules with `enable_escalation = false` (the default) have zero behavior change — no regression
- [ ] `_format_derivation_rules()` emits fallback info in the prompt only when `enable_escalation = true`
- [ ] Frontend modal shows escalation fields only when toggle is ON (no UI clutter for simple rules)
- [ ] `criteria_custom` field is persisted and returned by CRUD but not evaluated by tools in this change
- [ ] Alembic migration `037` upgrades and downgrades cleanly against a live DB with existing derivation rules
- [ ] All 4 Gherkin acceptance scenarios pass (see spec.md)

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Cascading complexity: multiple rules, all with escalation, firing at once | MEDIUM | Only the FIRST matching rule runs the escalation algorithm. Rule evaluation is deterministic. |
| `fallback_professional_id` references a professional from a different tenant | HIGH | `_validate_derivation_rule()` MUST assert `fallback_professional_id` belongs to the same tenant. Identical check already exists for `target_professional_id`. |
| `fallback_team_mode = true` returns too many professionals, causing slow queries | LOW | The query for team mode reuses the same index path as the base case (no derivation filter). Already optimized. |
| Prompt length increase from fallback info | LOW | The fallback line adds ~2 lines per rule with escalation enabled. Most clinics have 1–5 rules. |
| Agent ignores the escalation info in the prompt and still surfaces "no disponibilidad" | MEDIUM | The tool handles escalation transparently — the agent does not need to reason about it. The tool RETURNS slots already resolved to the fallback professional. The agent just uses what the tool returns. |
| `criteria_custom` JSONB creates future migration confusion | LOW | Document the stub clearly. The column is nullable and ignored in all tool evaluation code. |

---

## 6. Alternatives Considered

### Alt A: Manual reassignment by clinic staff
Admin is alerted when primary professional is saturated; they manually reassign inbound leads.

**Tradeoffs**: Low implementation cost. High operational cost (requires human monitoring). Leads lost during off-hours. **Rejected** because the problem is precisely off-hours and the goal is zero-human-intervention.

### Alt B: Priority queue — patient books primary and is waitlisted for another
Patient is offered a date in the distant future with the primary, but also given a nearby slot with the fallback as an alternative.

**Tradeoffs**: More transparent to the patient. Requires complex UX reasoning from the agent. **Rejected** for this change; can be layered on top later.

### Alt C (chosen): Transparent escalation in the tool
The `check_availability` tool handles escalation internally. The patient-facing message uses `escalation_message_template` to explain the routing naturally ("hoy la Dra. no tiene turnos, pero podemos coordinar con otro profesional del equipo").

**Tradeoffs**: Requires DB schema change and prompt update. Agent behavior stays simple (tool returns a slot, agent offers it). **Chosen** because it keeps agent reasoning simple and the logic deterministic.

### Alt D: Fallback to "team" only (no specific professional)
Skip the `fallback_professional_id` field entirely — just toggle to team mode.

**Tradeoffs**: Simpler schema. Loses control for clinics that want "primary = specialist, fallback = specific generalist". **Rejected** because some clinics have a known secondary specialist for complex cases.
