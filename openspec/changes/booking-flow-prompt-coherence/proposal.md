# Proposal: Booking Flow Prompt Coherence

## Intent

Fix 4 real-world booking failures found in a WhatsApp conversation with patient Wilma. The system prompt has contradictory rules, missing semantic definitions, and disjointed selection logic that cause the LLM to hallucinate turnos, re-query availability after patient confirmation, corrupt booking context, and trigger false anti-loop escalation.

## Scope

### In Scope
- **Change 1 (CRITICAL)**: Insert hierarchy gate — when patient picks an already-shown option, override all specific_time/min_time/preference rules and go directly to PASO 4b (book).
- **Change 2 (FIX)**: Define PRÓXIMOS/ANTERIORES semantics for `list_my_appointments` output so LLM never calls past appointments "próximo turno".
- **Change 3 (QUALITY)**: Merge two duplicate selection rule blocks into one coherent section with `slot_index` as primary resolution method.
- **Change 4 (QUALITY)**: Add instruction for professional_name continuity across check_availability → book_appointment calls.

### Out of Scope
- No Python logic changes (tools, routes, models).
- No database or schema changes.
- No tool implementation changes.
- No content removal from prompt — only restructure, add, or clarify.

## Capabilities

> No spec-level behavior changes. These are internal prompt coherence fixes — the exposed tools and API contracts remain identical.

### New Capabilities
None

### Modified Capabilities
None

## Approach

Four isolated edits to `orchestrator_service/main.py` system prompt, applied in dependency order:

1. **Priority Gate insertion** (line 10692-10693): Insert a hard hierarchy rule that declares shown-option matching as the #1 priority, overriding all time-specific rules below.
2. **list_my_appointments semantics** (after line 10953): Add semantic definition for PRÓXIMOS vs ANTERIORES with a hard rule against using "próximo turno" for past entries.
3. **Merge duplicate selection rules** (lines 10668-10717): Combine "REGLA INQUEBRANTABLE DE SELECCIÓN" and "REGLA DE SELECCIÓN DE TURNO" into a single coherent block.
4. **Professional name continuity** (near PASO 4b/4c area): Add instruction to preserve and reuse `professional_name` from `check_availability` results.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` | Modified | System prompt sections only (lines 10668-10717, after 10953, around PASO 4c) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Priority gate wording still ambiguous for LLM | Med | Use exact match examples and explicit "ALL rules below are OVERRIDDEN" language |
| Merge of two rules loses edge case | Low | Preserve all original content; reorder only, never remove |
| Professional name instruction adds token overhead | Low | Single line of text, negligible cost |
| Regression in other booking flows | Low | Changes only add/clarify — all existing behaviors preserved |

## Rollback Plan

Revert each Change independently via `git revert` on the commit. The changes are text-only edits to a single file — revert the diff for lines 10668-10717 and insertions at lines 10954 and near PASO 4c.

## Dependencies

None. All changes are self-contained within `orchestrator_service/main.py`.

## Success Criteria

- [ ] Patient selecting an already-shown option (by number, day+hour, or hour) goes directly to booking — no re-query of `check_availability`.
- [ ] `list_my_appointments` with only ANTERIORES entries never produces "próximo turno" in bot response.
- [ ] Single unified selection rule block replaces two duplicate sections without losing any rules.
- [ ] `professional_name` from `check_availability` output is consistently reused in `book_appointment` calls.
- [ ] All existing prompt content preserved (no removals).
