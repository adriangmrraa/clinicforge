# SDD Tasks: Context Engineering Parity

> **Change**: `context-engineering-parity`
> **Artifact**: `sdd/context-engineering-parity/tasks`
> **Based on**: Proposal (#2947) → Spec (#2948) → Design (#2949)

---

## Review Workload Forecast

| Metric | Value |
|--------|-------|
| **Estimated total delta** | ~366 lines (260 additions + 106 modifications) |
| **Files touched** | 4 (patient_context.py, graph.py, specialists.py, test_agent_parity.py) |
| **Delivery strategy** | **Single PR** (under 400 lines, single coherent concern). Chained PR is not warranted — all changes are tightly coupled to the same 3-layer pipeline and tests. |
| **Risk profile** | LOW-MEDIUM. All tables exist, no migrations, no schema changes. Main risks: (1) parallel query latency, (2) ContextVar import coupling for family IDs, (3) RAG call timeout. |
| **Recommended reviewer focus** | (A) tenant_id scoping on every new query, (B) `asyncio.gather()` error isolation, (C) formatter marker labels matching solo-agent. |

---

## Dependency Graph

```
Task 1.1 (Dataclass)
    │
    ├─── Task 1.2 (CE1 Phone) ─── depends on: patient row already fetched → LOW
    ├─── Task 1.3 (CE2 Assigned Prof) ─── depends on: patient row has assigned_professional_id
    ├─── Task 1.4 (CE3 Next Appt) ─── depends on: patient ID known
    ├─── Task 1.5 (CE4 Last Appt) ─── depends on: patient ID known. Shares JOIN pattern w/ CE3
    ├─── Task 1.6 (CE5 Treatment Plan) ─── depends on: patient ID known
    └─── Task 1.7 (CE6 Family) ─── depends on: family_patient_ids from ContextVar (passed as param)
         │
         ▼
    Task 1.8 (Phase 1 Tests)
         │
         ├─── Task 2.1 (CE7 Children) ─── depends on: patient phone known
         ├─── Task 2.2 (CE8 Visit Count) ─── depends on: patient ID known
         └─── Task 2.3 (CE9 Anamnesis) ─── depends on: patient row medical_history + anamnesis_token
              │
              ▼
         Task 2.4 (Phase 2 Tests)
              │
              ├─── Task 3.1 (CE10 Lead Context) ─── independent (pure formatting change)
              └─── Task 3.2 (CE11 Birth Date) ─── depends on: patient row has birth_date
                   │
                   ▼
              Task 3.3 (Phase 3 Tests)
                   │
                   ▼
              Task V.1 (Full Regression)
```

### Implementation Order

```
T1.1 → T1.2 → T1.3 → T1.4+T1.5 (parallel) → T1.6 → T1.7 → T1.8
                                                          ↓
                                          T2.1 → T2.2 → T2.3 → T2.4
                                                                    ↓
                                                          T3.1 → T3.2 → T3.3
                                                                              ↓
                                                                          T V.1
```

Within each task, ALWAYS implement in layer order: `patient_context.py` (data) → `graph.py` (state mapping) → `specialists.py` (formatting). Tests last.

---

## Phase 1 — CRITICAL (6 fields)

### Task 1.1 — Expand PatientProfile Dataclass

**Description**: Add 11 new `Optional`/`list` fields to the `PatientProfile` dataclass (lines 23-33). All default to `None` or `field(default_factory=list)`. No logic, no queries — pure data shape.

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `services/patient_context.py` | Add fields to `@dataclass PatientProfile` | +12 |

**Delta**: +12 lines (additive, no modifications)

**New fields**:
```python
assigned_professional: Optional[dict] = None
next_appointment: Optional[dict] = None
last_appointment: Optional[dict] = None
treatment_plan: Optional[dict] = None
family_members: list[dict] = field(default_factory=list)
patient_memories: Optional[str] = None
children_dependents: list[dict] = field(default_factory=list)
visit_count: Optional[int] = None
anamnesis_status: Optional[dict] = None
phone_number: Optional[str] = None
birth_date: Optional[str] = None
```

**Dependencies**: None (can be done first)

**Risk**: LOW — pure data definition, no runtime impact

---

### Task 1.2 — CE1: Phone Number

**Description**: Extract `phone_number` from the patient row. Only set on `profile.phone_number` if the value is non-empty and does NOT start with `"SIN-TEL"`. Format as `• Teléfono registrado: {phone}`.

**Implementation**:
1. `patient_context.py`: Add `phone_number` to the existing `SELECT` on line 68
2. `patient_context.py`: After line 92, extract phone with SIN-TEL check
3. `graph.py`: Add `"phone_number": p.phone_number` to profile_dict
4. `specialists.py`: In formatter, add phone line after identity block (before "Estado:")

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `services/patient_context.py` | Add to SELECT + extraction | +3 |
| `agents/graph.py` | Add to profile_dict | +1 |
| `agents/specialists.py` | Add formatter line | +3 |

**Delta**: ~7 lines

**Dependencies**: Task 1.1

**Risk**: LOW — trivial extraction from existing row data

**Solo-agent reference**: `buffer_task.py` lines 1136-1139 — identical logic

---

### Task 1.3 — CE2: Assigned Professional

**Description**: After patient row is fetched, query `professionals` by `assigned_professional_id`. Must only match active professionals (`is_active = true`). Format with full priority rules text matching solo-agent.

**Implementation**:
1. `patient_context.py`: Add `assigned_professional_id` to the patient SELECT on line 68
2. `patient_context.py`: Add query helper `_load_assigned_professional(pool, tenant_id, row_dict, profile)` — fetchrow by id + tenant_id + is_active
3. `graph.py`: Add `"assigned_professional": p.assigned_professional` mapping
4. `specialists.py`: Add formatter block in the "Estado:" section area — includes full priority rules text about habitual provider, pain priority, offering availability first

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `services/patient_context.py` | Add to SELECT + query helper | +13 |
| `agents/graph.py` | Add mapping | +1 |
| `agents/specialists.py` | Formatter block with priority text | +8 |

**Delta**: ~22 lines

**Dependencies**: Task 1.1

**Risk**: LOW — single fetchrow, indexed by ID+tenant_id

**Solo-agent reference**: `buffer_task.py` lines 1150-1169 — exact priority rules text to replicate

**Edge cases**:
- `assigned_professional_id` is NULL → skip
- professional not found or `is_active = false` → skip (non-fatal)
- professional deleted → skip (non-fatal)

---

### Task 1.4 — CE3: Next Appointment with Resolved Names

**Description**: Query the nearest future appointment (`appointment_datetime >= NOW()`, status IN `scheduled,confirmed`) with LEFT JOINs to `treatment_types` and `professionals` to resolve names. Format with Spanish day name, date, time, and time-until computation.

**Implementation**:
1. `patient_context.py`: Add query helper `_load_appointments(pool, tenant_id, patient_id, profile)` — fetchrow for next appointment with JOINs
2. `patient_context.py`: Compute time-until rules matching solo-agent (<30min, <1h, <24h, <48h, else absolute)
3. `graph.py`: Add `"next_appointment": p.next_appointment` mapping
4. `specialists.py`: Add formatter block — two lines (`PRÓXIMO TURNO:` + `FECHA EXACTA DEL TURNO:`)

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `services/patient_context.py` | Query helper + time-until | +15 |
| `agents/graph.py` | Add mapping | +1 |
| `agents/specialists.py` | Formatter block (2 lines) | +8 |

**Delta**: ~24 lines

**Dependencies**: Task 1.1

**Risk**: LOW — single fetchrow with standard JOINs

**Solo-agent reference**: `buffer_task.py` lines 1180-1234 — exact date formatting, day name resolution, time-until logic

**Edge cases**:
- No future appointments → skip (fails silently)
- Treatment type not found in `treatment_types` → fallback to `"Consulta"`
- `professional_id` is NULL or professional not found → render without name

---

### Task 1.5 — CE4: Last Appointment + Post-Treatment Follow-Up

**Description**: Query the most recent past appointment (`appointment_datetime < NOW()`). Compute `days_since`. If `days_since <= 7`, also emit a `SEGUIMIENTO POST-TRATAMIENTO` marker line.

**Implementation**:
1. `patient_context.py`: In the same `_load_appointments()` helper from Task 1.4, add a second fetchrow for the last appointment with same JOINs
2. `patient_context.py`: Compute `days_since = (datetime.now(timezone.utc) - ldt).days`
3. `graph.py`: Add `"last_appointment": p.last_appointment` mapping
4. `specialists.py`: Add formatter for `ÚLTIMO TURNO:` line + conditional `SEGUIMIENTO POST-TRATAMIENTO:` line

**Optimization**: This query shares the same JOIN pattern and function as CE3 (Task 1.4). Implement both in the same `_load_appointments()` coroutine to avoid code duplication.

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `services/patient_context.py` | Add to `_load_appointments()` helper | +15 |
| `agents/graph.py` | Add mapping | +1 |
| `agents/specialists.py` | Formatter + conditional seguimiento | +8 |

**Delta**: ~24 lines

**Dependencies**: Task 1.4 (same helper function — should be implemented together or CE4 after CE3)

**Risk**: LOW — same pattern as CE3

**Solo-agent reference**: `buffer_task.py` lines 1236-1281 — exact days-since and seguimiento logic

**Edge cases**:
- No past appointments → skip
- `days_since` exactly 7 → MUST include seguimiento (≤7 condition)

---

### Task 1.6 — CE5: Treatment Plan / Budget

**Description**: Query active treatment plans (`status IN draft,approved,in_progress`) with LEFT JOIN to payments. Compute financials: approved = COALESCE(approved_total, estimated_total, 0), paid = SUM(payments), pending = approved - paid. Parse installments/discount/conditions from `notes` JSON.

**Implementation**:
1. `patient_context.py`: Add query helper `_load_treatment_plan(pool, tenant_id, patient_id, profile)` — fetchrow with SUM join, GROUP BY, ORDER BY created_at DESC LIMIT 1
2. `patient_context.py`: Parse notes JSON for `installments`, `discount_pct`, `discount_amount`, `payment_conditions`
3. `graph.py`: Add `"treatment_plan": p.treatment_plan` mapping
4. `specialists.py`: Add multiline formatter block with `PRESUPUESTO ACTIVO:` header and indented fields

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `services/patient_context.py` | Query helper + JSON parsing | +25 |
| `agents/graph.py` | Add mapping | +1 |
| `agents/specialists.py` | Formatter block (~10 lines) | +15 |

**Delta**: ~41 lines

**Dependencies**: Task 1.1

**Risk**: MEDIUM — most complex query (SUM JOIN + JSON parsing). `notes` field may have inconsistent structure across tenants.

**Solo-agent reference**: `buffer_task.py` lines 1422-1498 — exact financial computation, formatting with `.replace(",", ".")` for Spanish locale

**Edge cases**:
- No payments → paid = 0, pending = approved
- `installments` = 1 → skip cuotas line
- No discount → skip discount lines
- `notes` is NULL or malformed JSON → safe defaults
- No active plans → skip

---

### Task 1.7 — CE6: Family Members

**Description**: When `family_patient_ids` (passed as parameter from ContextVar) is non-empty, load each family member's data: name, phone, next appointment, last appointment, visit count, latest clinical record (diagnosis + treatment_plan). Format as structured block with rules.

**Implementation**:
1. `patient_context.py`: Update `PatientContext.load()` signature to accept `family_patient_ids: Optional[List[int]] = None`
2. `patient_context.py`: Add query helper `_load_family_members(pool, tenant_id, family_patient_ids, profile)` — fetchrow per member + per-member sub-queries for appointments, visits, clinical records
3. `graph.py`: Update `_load_patient_context()` to accept and pass through `family_patient_ids`
4. `graph.py`: Add `"family_members": p.family_members` mapping
5. `graph.py`: Update `run_turn()` call at line 100 to extract `family_patient_ids` from `ctx.extra` and pass it
6. `specialists.py`: Add formatter block with per-member sections + rules footer

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `services/patient_context.py` | Param plumbing + query helper | +30 |
| `agents/graph.py` | Signature + param + mapping + pass-through | +5 |
| `agents/specialists.py` | Formatter + rules block | +20 |

**Delta**: ~55 lines (largest single task)

**Dependencies**: Task 1.1, understanding of `current_family_patient_ids` ContextVar in `main.py` line 248

**Risk**: MEDIUM — (1) ContextVar import from `main` may cause circular import — must lazy-import; (2) per-family-member sub-queries could be expensive for large families (N+1 pattern); (3) `ctx.extra` may not always have `family_patient_ids`.

**Mitigation**: Use lazy import for ContextVar. Family query is loop-based (N+1 is acceptable because family size is typically 1-3). Wrap entire block in try/except with silent skip.

**Solo-agent reference**: `buffer_task.py` lines 1513-1618 — exact structure for family member data collection and rules text

**Edge cases**:
- `family_patient_ids` is None or empty → skip
- Family member not found → skip silently
- Import of ContextVar fails (circular import) → skip block, log debug
- No clinical record → skip diagnosis/treatment_plan lines

---

### Task 1.8 — Phase 1 Tests

**Description**: Add test methods to `TestInjectPatientContext` class for CE1-CE6. Each test sets the corresponding field(s) in `_make_state()` and asserts the expected marker label appears in the formatted output.

**Implementation**:
1. Update `_make_state()` to include new profile keys with defaults (None/[])
2. Add test methods:
   - `test_phone_shown_when_real()` — phone_number set, verify marker
   - `test_phone_hidden_when_sintel()` — phone starting with "SIN-TEL", verify NO marker
   - `test_assigned_professional_shown()` — assigned_professional with name, verify marker + name + priority text
   - `test_no_assigned_professional_omitted()` — assigned_professional is None, verify NO marker
   - `test_next_appointment_shown()` — next_appointment with treatment_name + professional_name, verify both lines
   - `test_no_next_appointment_omitted()` — next_appointment None, verify NO marker
   - `test_last_appointment_and_seguimiento()` — last_appointment with days_since=3, verify last + seguimiento lines
   - `test_last_appointment_no_seguimiento()` — last_appointment with days_since=14, verify last WITHOUT seguimiento
   - `test_treatment_plan_budget_shown()` — treatment_plan with all fields, verify full block
   - `test_no_treatment_plan_omitted()` — treatment_plan None, verify NO budget block
   - `test_family_members_shown()` — family_members with one member, verify member entry + rules
   - `test_no_family_members_omitted()` — family_members empty, verify NO family block

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `tests/test_agent_parity.py` | New test methods + _make_state update | +72 |

**Delta**: ~72 lines

**Dependencies**: Tasks 1.1-1.7

**Risk**: LOW — pure unit tests, no DB, no mocks needed

---

## Phase 2 — HIGH (3 fields)

### Task 2.1 — CE7: Children/Minor Dependents

**Description**: Query patients whose `guardian_phone` matches the current patient's known phone numbers (normalized, non-digits stripped). For each matched minor, resolve name, DNI, phone, anamnesis URL (generate UUID token if missing), and next appointment.

**Implementation**:
1. `patient_context.py`: Add query helper `_load_children(pool, tenant_id, phone_number, row_dict, profile)` — normalize both chat phone and DB phone, use `ANY()` with regex for matching
2. `patient_context.py`: For each matched minor, check/generate `anamnesis_token` via UPDATE, fetch next appointment
3. `graph.py`: Add `"children_dependents": p.children_dependents` mapping
4. `specialists.py`: Add formatter block with per-child indented details

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `services/patient_context.py` | Query helper + token generation | +22 |
| `agents/graph.py` | Add mapping | +1 |
| `agents/specialists.py` | Formatter block | +12 |

**Delta**: ~35 lines

**Dependencies**: Task 1.1 (dataclass has `children_dependents` field)

**Risk**: MEDIUM — (1) `REGEXP_REPLACE` for phone matching may differ between PostgreSQL versions; (2) Anamnesis token generation requires background UPDATE (fire-and-forget or await); (3) Token generation on read is a side effect — could cause concurrent write issues.

**Solo-agent reference**: `buffer_task.py` lines 1370-1420 — exact phone normalization and child matching logic

**Edge cases**:
- No children found → skip
- Guardian phone is NULL or empty → skip
- Child has no anamnesis_token → generate UUID + UPDATE
- Child has no future appointment → omit next-appointment sub-line

---

### Task 2.2 — CE8: Visit Count / Recurrence

**Description**: `COUNT(*)` from `appointments` for this patient. Format: count > 1 → `Paciente recurrente ({N})`, count = 1 → `Primera visita`, count = 0 → no line.

**Implementation**:
1. `patient_context.py`: Add to `_load_appointments()` helper (cheap COUNT, same table already joined)
2. `graph.py`: Add `"visit_count": p.visit_count` mapping
3. `specialists.py`: Add conditional formatter with 3-way branch

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `services/patient_context.py` | Add COUNT to appointments helper | +8 |
| `agents/graph.py` | Add mapping | +1 |
| `agents/specialists.py` | Conditional formatter (3 branches) | +6 |

**Delta**: ~15 lines

**Dependencies**: Task 1.4 (same `_load_appointments()` helper)

**Risk**: LOW — single aggregate on indexed columns

**Solo-agent reference**: `buffer_task.py` lines 1283-1298

**Edge cases**:
- COUNT = 0 → no line emitted (silent)
- NULL → treated as None, no line

---

### Task 2.3 — CE9: Anamnesis Status

**Description**: Check `patient.medical_history` JSONB for `anamnesis_completed_at`. If truthy → injection line saying completed. Check/generate `anamnesis_token` for URL computation. Format: `• ANAMNESIS: Ya completó...` or `• ANAMNESIS: Pendiente. Link: {url}`.

**Implementation**:
1. `patient_context.py`: Add helper `_load_anamnesis(tenant_id, row_dict, profile)` — purely from existing row data, no extra DB query
2. `patient_context.py`: Parse medical_history JSONB, check anamnesis_completed_at, check/generate anamnesis_token, build URL
3. `graph.py`: Add `"anamnesis_status": p.anamnesis_status` mapping
4. `specialists.py`: Add conditional formatter (completed → completion message, not completed → url)

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `services/patient_context.py` | Anamnesis helper (no DB call) | +10 |
| `agents/graph.py` | Add mapping | +1 |
| `agents/specialists.py` | Conditional formatter | +4 |

**Delta**: ~15 lines

**Dependencies**: Task 1.1 (dataclass has `anamnesis_status`)

**Risk**: LOW — no DB query, purely from existing row data. Token generation side effect is same pattern as CE7.

**Solo-agent reference**: `buffer_task.py` lines 1336-1368

**Edge cases**:
- `medical_history` is NULL or empty JSONB → anamnesis not completed
- `anamnesis_token` missing → generate UUID, persist via UPDATE
- `FRONTEND_URL` env var not set → fallback to localhost

---

### Task 2.4 — Phase 2 Tests

**Description**: Add test methods for CE7-CE9.

**Test methods**:
- `test_children_dependents_shown()` — children_dependents with one child, verify name + DNI + anamnesis link
- `test_no_children_omitted()` — children_dependents empty, verify NO block
- `test_visit_count_recurrent()` — visit_count=5, verify "recurrente" marker
- `test_visit_count_first_time()` — visit_count=1, verify "Primera visita" marker
- `test_visit_count_zero_omitted()` — visit_count=None, verify NO line
- `test_anamnesis_completed_shown()` — anamnesis_status completed=true, verify completion message
- `test_anamnesis_pending_shown()` — anamnesis_status completed=false, verify URL shown

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `tests/test_agent_parity.py` | New test methods | +50 |

**Delta**: ~50 lines

**Dependencies**: Tasks 2.1-2.3

**Risk**: LOW — pure unit tests

---

## Phase 3 — MEDIUM (2 fields)

### Task 3.1 — CE10: Lead Context Formatted

**Description**: Replace the current raw dict dump in the formatter with `lead_ctx.format_for_prompt(state["lead_context"])`. This produces the structured `[CONTEXTO DE LEAD]` block with labeled fields.

**Implementation**:
1. `specialists.py`: At lines 277-281, replace `prompt_data = lc.get("accumulated_data") or lc.get("formatted_for_prompt")` + `f"Datos de lead: {prompt_data}"` with call to `format_for_prompt(state["lead_context"])`
2. `specialists.py`: Need to import `format_for_prompt` from `services.lead_context` (lazy, inside function to avoid circular)

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `agents/specialists.py` | Replace raw dump with `format_for_prompt()` | +6 |

**Delta**: ~6 lines (modify existing lines, not wholly additive)

**Dependencies**: `lead_context.py` already has `format_for_prompt()` function (lines 150-170)

**Risk**: LOW — pure formatting change, no DB impact

**Edge cases**:
- `state["lead_context"]` is None or {} → `format_for_prompt` returns empty string → no lead block
- Unrecognized fields in lead_context dict → silently ignored (the formatter only emits fields in `_FIELD_LABELS`)

---

### Task 3.2 — CE11: Birth Date

**Description**: Extract `birth_date` from patient row if non-null. Format: `• Fecha de nacimiento: {birth_date}`.

**Implementation**:
1. `patient_context.py`: After patient row extracted, check `row_dict.get("birth_date")` and set `profile.birth_date`
2. `graph.py`: Add `"birth_date": p.birth_date` mapping
3. `specialists.py`: Add formatter line

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `services/patient_context.py` | Extract from patient row | +3 |
| `agents/graph.py` | Add mapping | +1 |
| `agents/specialists.py` | Formatter line | +2 |

**Delta**: ~6 lines

**Dependencies**: Task 1.1

**Risk**: LOW — trivial extraction

**Solo-agent reference**: `buffer_task.py` lines 1147-1148

**Edge cases**:
- `birth_date` is NULL → no line emitted

---

### Task 3.3 — Phase 3 Tests

**Description**: Add test methods for CE10-CE11.

**Test methods**:
- `test_lead_context_formatted_shown()` — lead_context with name + channel, verify structured CONTEXTO DE LEAD block with labels
- `test_lead_context_empty_omitted()` — lead_context is None, verify NO lead block
- `test_birth_date_shown()` — birth_date set, verify marker
- `test_no_birth_date_omitted()` — birth_date is None, verify NO marker

**Files affected**:
| File | Change | Lines |
|------|--------|-------|
| `tests/test_agent_parity.py` | New test methods | +32 |

**Delta**: ~32 lines

**Dependencies**: Tasks 3.1-3.2

**Risk**: LOW — pure unit tests

---

## Verify

### Task V.1 — Full Regression

**Description**: Run the complete parity test suite to verify no regressions.

**Command**: `python -m pytest orchestrator_service/tests/test_agent_parity.py -v`

**Expected results**:
- `TestSharedPreamble` (5 tests) — PASS (no changes to shared preamble logic)
- `TestInjectPatientContext` (6 existing + 23 new = 29 tests) — PASS
- `TestVariableInterpolation` + others — PASS (no changes to interpolation logic)

**Files affected**: None (test execution only)

**Delta**: 0 lines

**Dependencies**: All tasks completed

**Risk**: LOW — automated execution

---

## Summary

| Phase | Tasks | Patient Context | Graph | Specialists | Tests | Total |
|-------|-------|----------------|-------|-------------|-------|-------|
| **1 — CRITICAL** | 1.1-1.8 | +101 | +10 | +63 | +72 | **+246** |
| **2 — HIGH** | 2.1-2.4 | +40 | +3 | +22 | +50 | **+115** |
| **3 — MEDIUM** | 3.1-3.3 | +3 | +1 | +8 | +32 | **+44** |
| **Verify** | V.1 | — | — | — | — | **0** |
| **Total** | **13** | **+144** | **+14** | **+93** | **+154** | **~+405** |

**Note**: The estimate is +405 lines vs the design's ~278 — variance comes from:
1. Test detail (72 + 50 + 32 = 154 test lines vs design's 21) — the design counted test *methods* not test *lines*
2. Family members query helper is complex (55 lines vs design's 30)
3. Treatment plan JSON parsing adds overhead (41 lines vs design's 25)

**Risk distribution**: 8 LOW, 3 MEDIUM (CE5 treatment_plan, CE6 family_members, CE7 children_dependents), 0 HIGH.

---

## Key Design Decisions to Enforce During Implementation

1. **Parallel query execution**: ALL independent field queries MUST run via `asyncio.gather(return_exceptions=True)`. Serial execution is rejected — adds latency per field.

2. **Tenant isolation**: EVERY new SQL query MUST include `WHERE tenant_id = $1`. This is non-negotiable (legal/sovereignty requirement).

3. **Fail-safe pattern**: EVERY query helper MUST be wrapped in try/except. Failure of one field must NOT prevent others from loading.

4. **No schema changes**: All columns and tables already exist. No Alembic migrations needed. If a column doesn't exist in a tenant's DB, the query returns NULL → field is skipped.

5. **Family member ContextVar**: Import `current_family_patient_ids` from `main` using lazy import (inside the function, not at module level) to avoid circular imports.

6. **Formatter marker consistency**: Each new field's marker label MUST exactly match the solo-agent format — agents may have learned patterns from the solo-agent context block.

7. **Patient Memories**: The `patient_memories` field (included in dataclass per design) is loaded via `format_memories_for_prompt()` with `query=""` (all top-25). Wrapped in explicit 2s-guarded try/except. If it fails, profile.patient_memories stays None → no memories block in context.
