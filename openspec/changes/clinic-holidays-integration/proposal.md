# SDD Proposal: Clinic Holidays Integration

**Change**: `clinic-holidays-integration`
**Status**: PROPOSED
**Date**: 2026-04-07
**Author**: SDD Orchestrator

---

## 1. Intent

### Problem Statement

Holiday management in ClinicForge exists at the data layer and agent-prompt layer but is invisible in the most natural location: the clinic configuration modal.

**Current state (as investigated)**:

| Layer | Status |
|-------|--------|
| DB schema | COMPLETE — `tenant_holidays` table exists since migration 010; `custom_hours_start/end` added in 014 |
| ORM | COMPLETE — `TenantHoliday` model with all columns in `models.py:1262` |
| Backend service | COMPLETE — `holiday_service.py` hybrid engine (Python `holidays` library + DB overrides) |
| Backend endpoints | COMPLETE — Full CRUD at `/admin/holidays` (GET list, POST, PUT, DELETE, toggle) in `admin_routes.py:2768` |
| Agent context wiring | COMPLETE — `buffer_task.py:685` fetches holidays and passes to `build_system_prompt()` via `upcoming_holidays=_upcoming_holidays` |
| Agent prompt consumption | COMPLETE — `main.py:6336` formats and injects feriados section; handles `custom_hours` display |
| Frontend — AgendaView | PARTIAL — Holidays visible on calendar (`AgendaView.tsx:142`) + `HolidayDetailModal.tsx` for toggle/hours |
| Frontend — ClinicsView | MISSING — No holidays section in the clinic config modal |

**The UX gap**: The clinic owner configures everything for a clinic inside `ClinicsView` (Tab 1 modal: name, hours, bank, working hours by day, etc.). But to see or add custom holidays, they have to discover a completely separate flow through the Agenda calendar, click on a holiday dot, and interact with a modal that was designed for viewing, not bulk management. There is no way to add a new custom closure from the clinic config page — only from the calendar.

**Concrete consequence**: Clinic owners miss configuring holidays before vacations, the AI agent schedules appointments on closed days, and patients show up to a closed clinic.

### Why This Matters

- **Patient trust**: An AI that schedules on Christmas or local holidays destroys credibility.
- **Discoverability**: 100% of clinic setup happens in the ClinicsView modal. Holidays belong there.
- **Operational completeness**: The backend and agent wiring are already done. This change costs frontend effort only — no new infrastructure required.

---

## 2. Scope

### In Scope

| Area | What Changes |
|------|-------------|
| `frontend_react/src/views/ClinicsView.tsx` | Add "Feriados y Dias Especiales" collapsible section at the bottom of the Edit Clinic modal (before submit buttons), showing next 90 days of holidays with inline add/edit/delete |
| `frontend_react/src/locales/es.json` | New i18n keys for the section (namespace `clinics.holidays.*`) |
| `frontend_react/src/locales/en.json` | Same keys in English |
| `frontend_react/src/locales/fr.json` | Same keys in French |
| `tests/test_clinic_holidays_integration.py` | New test file — backend endpoint contract tests + agent prompt injection verification |
| Alembic (verification only) | Confirm migration 010+014 is complete; add migration 031 ONLY if a required field is missing after field audit |

### Out of Scope

- `AgendaView.tsx` + `HolidayDetailModal.tsx` — already working, do not modify
- `holiday_service.py` — no changes; works correctly
- `admin_routes.py` — no changes; endpoints already exist and are complete
- `models.py` — no changes; `TenantHoliday` is complete
- `buffer_task.py` — no changes; wiring is already correct
- `main.py` `build_system_prompt()` — no changes; agent prompt section is already correct
- Nova assistant — out of scope

### Field Audit (pre-implementation check)

Current `tenant_holidays` columns confirmed from migrations and ORM:
- `id`, `tenant_id`, `date`, `name`, `holiday_type`, `is_recurring`, `custom_hours_start`, `custom_hours_end`, `created_at`

The original change description requested `notes` (text nullable) and `is_closed` (bool alias for holiday_type='closure') plus `custom_hours` as JSONB. Investigation shows:

- `is_closed` is represented by `holiday_type='closure'` — no new column needed, the existing enum is semantically equivalent.
- `custom_hours` is split into `custom_hours_start` + `custom_hours_end` Time columns — already present in migration 014.
- `notes` column is NOT present in current schema. If needed by the UI, migration 031 adds it.

**Decision**: The UI will NOT expose `notes` in the initial implementation (YAGNI — no endpoint currently returns or saves it). Migration 031 is deferred unless spec explicitly requires it. The holiday section uses all existing columns.

---

## 3. Approach

### Layer 1: Frontend Section in ClinicsView Modal

Add a collapsible `<details>`-style section at the bottom of the Edit Clinic modal (between "Horarios por dia" and the submit buttons). The section:

1. Opens collapsed by default (state: `holidaysSectionOpen: false`).
2. On expand: fetches `GET /admin/holidays?days=90` for the currently editing clinic's tenant.
3. Renders a list of upcoming holidays (both national from library and custom from DB), grouped by month.
4. Each custom holiday row shows: date badge, name, type badge (cerrado / horario especial), edit and delete icons.
5. National holidays (source='library') show with a lock icon — cannot be deleted, but CAN be toggled to override_open with custom hours.
6. An inline "Agregar feriado" form at the bottom of the list: date picker (HTML `<input type="date">`), name input, type select (closure / override_open), optional custom hours inputs (visible only when override_open selected), submit button.
7. All API calls use the same `/admin/holidays` endpoints already in place.

### Layer 2: Test Coverage

TDD-strict: write tests before implementing. Tests cover:
- Backend endpoint contract (GET returns correct structure, POST creates, PUT updates, DELETE removes)
- Agent prompt injection: `build_system_prompt()` called with `upcoming_holidays` list produces the `## FERIADOS PROXIMOS` section with correct format
- Agent answer scenarios: agent has holidays in prompt and user asks about a holiday date — response includes closure or custom hours

---

## 4. Success Criteria

- [ ] The Edit Clinic modal contains a "Feriados y Dias Especiales" section (collapsible).
- [ ] Section loads holidays from `/admin/holidays?days=90` when expanded.
- [ ] Clinic owner can add a custom closure from within the modal (no navigation to Agenda required).
- [ ] Clinic owner can add an override_open with custom start/end hours from within the modal.
- [ ] Clinic owner can delete a custom holiday from within the modal.
- [ ] National holidays (source='library') are visible but not deletable; toggle to override_open is available.
- [ ] `build_system_prompt()` receives non-empty `upcoming_holidays` when holidays exist in DB (verified by test).
- [ ] Agent answers "Atienden el [holiday date]?" with the correct closure or special hours info (verified by scenario test).
- [ ] All new UI strings are present in es.json, en.json, fr.json.
- [ ] Zero migration added if schema is already complete (audit first).

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Modal gets too tall (already long with working_hours section) | MEDIUM | Section is collapsed by default; list is limited to 90 days, max 15 items visible before scroll |
| Multi-tenant isolation: fetching holidays for wrong tenant | HIGH | Always use tenant_id from JWT (already enforced by `verify_admin_token` + `user_data['tenant_id']`); never use editing modal's clinic_id as tenant override |
| National holidays not showing for new country_code | LOW | `holiday_service.py` handles this; country_code is already configurable in the modal above the section |
| Unique constraint on `(tenant_id, date, holiday_type)` causes POST 409 | LOW | Frontend validates before POST; catch 409 and show user-friendly message |
| `is_recurring` not exposed in UI | LOW | Out of scope for this change; recurring holidays are an advanced feature; simple add form covers 90% of use cases |

---

## 6. Alternatives Considered

### Alternative A: Separate "Feriados" page in sidebar

**Pros**: Unlimited space, can show full calendar, no modal size concerns.
**Cons**: Adds another navigation item; clinic owner must leave clinic config context; the feature is already partially in AgendaView — adding a third location increases fragmentation.
**Decision**: Rejected. Context proximity wins.

### Alternative B: Keep holidays only in AgendaView

**Pros**: Zero code change.
**Cons**: Does not solve the discoverability gap. The clinic owner has to know to look at the calendar to configure holiday closures. This is the current state that caused the problem.
**Decision**: Rejected.

### Alternative C: Surface holidays as a separate tab inside the ClinicsView modal

**Pros**: More space, could show a mini-calendar.
**Cons**: Adds tab navigation complexity to a modal that currently has no tabs; increases component surface area significantly.
**Decision**: Rejected for now. If holidays section proves too complex, this is the natural V2 upgrade path.

---

## 7. Implementation Order

1. Audit migration state — confirm 010+014 cover all required columns (no migration 031 needed).
2. Write tests (TDD): endpoint contract, prompt injection, agent scenarios.
3. Add i18n keys to all 3 locale files.
4. Implement ClinicsView holiday section — collapsible wrapper, list, add form.
5. Verify end-to-end: add holiday in ClinicsView → appears in AgendaView → agent prompt includes it.
