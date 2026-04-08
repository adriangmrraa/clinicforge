# Tasks: Clinic Holidays Integration

**Change**: `clinic-holidays-integration`
**Status**: READY
**Date**: 2026-04-07
**TDD**: Strict — test tasks come BEFORE implementation tasks within each phase.
**Total tasks**: 22

---

## Dependency Graph

```
1.1 (schema audit) → 1.2 (migration 031 — conditional, skip if not needed)
1.1 → 2.1 (i18n keys) → 2.2 (TypeScript types)
2.1 + 2.2 → 3.1 (endpoint contract tests) → 3.2 (prompt injection tests) → 3.3 (buffer_task wiring tests)
3.1 → 4.1 (holidays section skeleton) → 4.2 (fetch + list render) → 4.3 (add form) → 4.4 (delete flow) → 4.5 (inline edit) → 4.6 (modal reset)
3.2 + 3.3 → 5.1 (verify prompt injection passes) → 5.2 (verify agent answer scenarios)
All → 6.1 (end-to-end smoke test)
```

---

## Phase 1: Schema Audit

- [ ] **1.1** Audit `tenant_holidays` schema state
  - Files: `orchestrator_service/alembic/versions/010_add_country_code_and_tenant_holidays.py`, `014_add_custom_holiday_hours.py`, `orchestrator_service/models.py`
  - Depends on: none
  - Acceptance:
    - Read migrations 010 and 014 and the `TenantHoliday` ORM class.
    - Confirm the following columns exist: `id`, `tenant_id`, `date`, `name`, `holiday_type`, `is_recurring`, `custom_hours_start`, `custom_hours_end`, `created_at`.
    - Document result as a comment in the test file header (`tests/test_clinic_holidays_integration.py`): `# Schema audit result: all columns present, migration 031 not required.`
    - If any column is missing, create task 1.2 immediately.

- [ ] **1.2** (CONDITIONAL) Create Alembic migration 031 for missing columns
  - Files: `orchestrator_service/alembic/versions/031_clinic_holidays_missing_fields.py`
  - Depends on: 1.1 (only if columns are missing)
  - Acceptance:
    - `revision = '031'`, `down_revision = '030'`
    - Only adds missing columns; does not re-add existing ones (use `_column_exists()` guard).
    - `upgrade()` and `downgrade()` both present.
    - File follows naming convention consistent with existing migrations.
    - **Skip this task entirely if schema audit (1.1) confirms all columns are present.**

---

## Phase 2: Types and i18n (prerequisites for all frontend work)

- [ ] **2.1** Add i18n keys to all 3 locale files
  - Files: `frontend_react/src/locales/es.json`, `en.json`, `fr.json`
  - Depends on: none
  - Acceptance:
    - Adds `clinics.holidays` namespace object (NOT top-level `holidays` — that already exists).
    - Contains all 19 keys from REQ-6 of spec.md.
    - Keys added after the last existing key in the `clinics` section.
    - No existing keys removed or modified.
    - Valid JSON after edit (no trailing commas, no missing commas).
    - All 3 files updated.

- [ ] **2.2** Add TypeScript interfaces for holiday data
  - Files: `frontend_react/src/views/ClinicsView.tsx` (near top of file, with other local interfaces)
  - Depends on: none
  - Acceptance:
    - `HolidayItem` interface with fields: `id?: number`, `date: string`, `name: string`, `holiday_type: 'closure' | 'override_open'`, `source: 'library' | 'custom'`, `is_recurring?: boolean`, `custom_hours?: {start: string; end: string} | null`, `custom_hours_start?: string | null`, `custom_hours_end?: string | null`.
    - `NewHolidayForm` interface with fields: `date: string`, `name: string`, `holiday_type: 'closure' | 'override_open'`, `custom_hours_start: string`, `custom_hours_end: string`, `is_recurring: boolean`.
    - Added before the `ClinicsView` component function, alongside other local type definitions.

---

## Phase 3: Tests (TDD — write before Phase 4 and 5 implementation)

- [ ] **3.1** Write endpoint contract tests
  - Files: `tests/test_clinic_holidays_integration.py` (new file)
  - Depends on: 1.1
  - Acceptance:
    - Class `TestHolidayEndpointContract` with:
      - `test_get_holidays_requires_auth`: GET `/admin/holidays` without auth header returns 401 or 403.
      - `test_get_holidays_returns_correct_structure`: GET `/admin/holidays?days=90` returns JSON with `upcoming` (list) and `custom` (list) keys.
      - `test_post_holiday_creates_closure`: POST `/admin/holidays` with valid closure data creates a record and returns `id`.
      - `test_post_holiday_creates_override_open`: POST with `holiday_type='override_open'` and valid `custom_hours_start`/`end` creates record.
      - `test_post_holiday_409_on_duplicate`: POST same `(date, holiday_type)` twice returns 409 with detail message `"Ya existe un feriado con ese tipo para esa fecha"`.
      - `test_put_holiday_updates_name`: PUT `/admin/holidays/{id}` with `{"name": "Nuevo nombre"}` updates the record.
      - `test_put_holiday_clears_hours_on_type_change_to_closure`: PUT with `{"holiday_type": "closure"}` on an override_open record sets `custom_hours_start` and `custom_hours_end` to NULL.
      - `test_delete_holiday_removes_record`: DELETE `/admin/holidays/{id}` returns 200 and subsequent GET does not include that id.
      - `test_delete_holiday_404_wrong_tenant`: DELETE with a valid id belonging to a different tenant returns 404.
    - Uses `pytest.mark.asyncio`, `AsyncClient`, and existing test auth fixtures from `pytest.ini` + project test setup.
    - Each test cleans up its created records (teardown or use a transactional fixture).

- [ ] **3.2** Write agent prompt injection tests
  - Files: `tests/test_clinic_holidays_integration.py`
  - Depends on: none (tests `build_system_prompt` directly — pure function)
  - Acceptance:
    - Class `TestAgentPromptInjection` with:
      - `test_build_system_prompt_includes_holidays_section`: Call `build_system_prompt(...)` with `upcoming_holidays=[{"date": "2026-12-25", "name": "Navidad", "source": "library", "holiday_type": "closure", "custom_hours": None}]`. Assert `"## FERIADOS PROXIMOS"` in result, `"2026-12-25: Navidad"` in result, `"CERRADO"` in result, `"REGLA:"` in result.
      - `test_build_system_prompt_custom_hours_format`: Call with `upcoming_holidays=[{"date": "2026-05-01", "name": "Día del Trabajador", "custom_hours": {"start": "09:00", "end": "13:00"}}]`. Assert `"HORARIO ESPECIAL 09:00–13:00"` in result.
      - `test_build_system_prompt_empty_list_no_section`: Call with `upcoming_holidays=[]`. Assert `"## FERIADOS PROXIMOS"` NOT in result.
      - `test_build_system_prompt_none_no_section`: Call with `upcoming_holidays=None`. Assert `"## FERIADOS PROXIMOS"` NOT in result.
      - `test_build_system_prompt_limits_to_7_holidays`: Call with a list of 10 holidays. Assert the result contains exactly 7 bullet points (`•`) in the holidays section (not all 10).
    - Import `build_system_prompt` directly from `orchestrator_service.main`.
    - Tests are synchronous (build_system_prompt is not async).

- [ ] **3.3** Write buffer_task holiday wiring tests
  - Files: `tests/test_clinic_holidays_integration.py`
  - Depends on: none (mocks the holiday service)
  - Acceptance:
    - Class `TestBufferTaskHolidayWiring` with:
      - `test_buffer_task_calls_get_upcoming_holidays`: Mock `services.holiday_service.get_upcoming_holidays` to return a known list. Call the buffer_task processing path. Assert the mock was called with `(pool, tenant_id, days_ahead=30)`.
      - `test_buffer_task_passes_holidays_to_build_system_prompt`: Same mock setup. Assert the `build_system_prompt` call includes the mocked holidays in `upcoming_holidays` kwarg.
      - `test_buffer_task_handles_holiday_service_exception_gracefully`: Mock `get_upcoming_holidays` to raise `Exception("DB down")`. Assert buffer_task does NOT raise; processing continues; `upcoming_holidays=[]` is used (or None — check actual behavior in buffer_task.py:692).
    - Use `unittest.mock.patch` or `pytest-mock`'s `mocker.patch`.
    - These tests may require extracting the holiday-fetch block into a testable helper if the buffer_task is too monolithic. If so, document the helper extraction as a sub-task.

---

## Phase 4: Frontend Implementation

- [ ] **4.1** Add state variables and section skeleton to ClinicsView
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 2.1, 2.2
  - Acceptance:
    - Add all state variables from design.md section 2.3 (holidaysSectionOpen, holidayList, holidaysLoading, holidaysFetchError, newHoliday, addingSaving, addError, addSuccess, editingHolidayId, editForm, deletingHolidayId).
    - Add the `HolidayItem` and `NewHolidayForm` types (or import from 2.2).
    - Add the `useEffect` that triggers `fetchHolidays()` when `holidaysSectionOpen && editingClinica`.
    - Add empty `fetchHolidays()` async function (body: just sets `holidayList = []` temporarily).
    - Add the collapsible section JSX placeholder in the correct location (after working_hours div, before the submit buttons div at line ~1079).
    - Section renders the header with `CalendarX` icon and `t('clinics.holidays.section_title')` label and a chevron toggle.
    - Section only renders when `editingClinica !== null`.
    - All existing tests pass (no functional change yet).

- [ ] **4.2** Implement fetchHolidays and list render
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 4.1
  - Acceptance:
    - `fetchHolidays()` calls `api.get('/admin/holidays', { params: { days: 90 } })` and sets `holidayList` from `res.data.upcoming`.
    - Loading state shows a spinner (use `Loader2` from lucide-react with `animate-spin`).
    - Error state shows `t('clinics.holidays.fetch_error')` inline in the section.
    - Empty state (list empty) shows `t('clinics.holidays.empty_message')`.
    - Non-empty list renders rows as described in design.md section 3 and REQ-5.3.
    - Each row shows: formatted date (`dd/MM/yyyy`), name, type badge, source badge.
    - Rows with `source='custom'` show edit (Pencil icon) and delete (X icon) buttons.
    - Rows with `source='library'` show no action buttons (read-only display).
    - Section header badge shows count of `holidayList.filter(h => h.source === 'custom').length`.

- [ ] **4.3** Implement inline add form
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 4.2
  - Acceptance:
    - Form rendered below the list, inside the section body.
    - Fields: date (input[type=date] min=today), name (input[type=text]), holiday_type (select), custom hours inputs (conditional on holiday_type=override_open), is_recurring (checkbox).
    - Submit button disabled during `addingSaving`.
    - `handleAddHoliday` validates per REQ-5.7 before calling API.
    - On success: form resets to defaults, `addSuccess` shows for 2s, list refreshes.
    - On 409: shows `t('clinics.holidays.conflict_error')` inline.
    - On other error: shows `t('clinics.holidays.fetch_error')` inline.
    - Form uses same dark-mode input classes as rest of modal.

- [ ] **4.4** Implement delete flow
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 4.2
  - Acceptance:
    - Clicking delete (X) on a custom holiday row sets `deletingHolidayId = holiday.id`.
    - Row transforms to show inline confirmation: `t('clinics.holidays.delete_confirm')` + "Confirmar" button + "Cancelar" button.
    - Clicking Cancelar: `setDeletingHolidayId(null)` — row restores to normal.
    - Clicking Confirmar: calls `DELETE /admin/holidays/{id}`, resets `deletingHolidayId`, calls `fetchHolidays()`.
    - Only one row can be in "confirming delete" state at a time.

- [ ] **4.5** Implement inline edit for custom holidays
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 4.2
  - Acceptance:
    - Clicking edit (Pencil) on a custom holiday row: sets `editingHolidayId = holiday.id` and `editForm` to the holiday's current values.
    - Row transforms into editable form (same fields as add form, pre-populated).
    - Clicking Cancel: resets `editingHolidayId = null`.
    - Clicking Save: validates (same rules as add), calls `PUT /admin/holidays/{id}` with changed fields, resets state, calls `fetchHolidays()`.
    - Only one row can be in edit mode at a time. Opening edit for row B while row A is in edit mode closes row A.

- [ ] **4.6** Implement modal state reset on close
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 4.1
  - Acceptance:
    - The modal close handler (everywhere `setIsModalOpen(false)` is called) also calls:
      - `setHolidaysSectionOpen(false)`
      - `setHolidayList([])`
      - `setEditingHolidayId(null)`
      - `setDeletingHolidayId(null)`
      - `setAddError(null)`
      - `setAddSuccess(false)`
    - Verify by manually opening modal for clinic A (expand holidays), closing, opening for clinic B — holidays section is collapsed and empty, fetches fresh data on expand.

---

## Phase 5: Verification

- [ ] **5.1** Run prompt injection tests and confirm they pass
  - Files: `tests/test_clinic_holidays_integration.py`
  - Depends on: 3.2
  - Acceptance:
    - `pytest tests/test_clinic_holidays_integration.py::TestAgentPromptInjection -v` exits 0.
    - All 5 tests in the class pass.
    - If any fail, fix `build_system_prompt` or the test (not the other way — re-read the code before modifying the test).

- [ ] **5.2** Run buffer_task wiring tests and confirm they pass
  - Files: `tests/test_clinic_holidays_integration.py`
  - Depends on: 3.3
  - Acceptance:
    - `pytest tests/test_clinic_holidays_integration.py::TestBufferTaskHolidayWiring -v` exits 0.
    - All 3 tests pass.
    - `test_buffer_task_handles_holiday_service_exception_gracefully` MUST pass — confirms the fallback behavior is in place.

---

## Phase 6: End-to-End Smoke Test

- [ ] **6.1** Manual end-to-end verification
  - Depends on: all prior tasks
  - Acceptance checklist:
    - [ ] Open ClinicsView, click Edit on an existing clinic.
    - [ ] "Feriados y Dias Especiales" section is collapsed by default.
    - [ ] Expand section — spinner shows, then holiday list loads (national holidays for tenant's country_code should appear).
    - [ ] Add a custom closure: date = tomorrow, name = "Test cierre", type = Cerrado. Click Agregar. Row appears in list with [Custom][Cerrado] badges.
    - [ ] Open AgendaView — the new custom holiday appears as a red dot on the calendar for that date.
    - [ ] Add a custom override_open: date = next week, name = "Horario reducido", type = "Con horario especial", hours 09:00–13:00. Row appears.
    - [ ] Delete the closure: click X → confirm → row disappears.
    - [ ] Edit the override_open: change name to "Turno reducido" → save → row shows updated name.
    - [ ] Close modal and reopen for the same clinic — holidays section is collapsed, list is empty until expanded.
    - [ ] Open modal for a different clinic — holidays section shows that clinic's holidays (different tenant would require different auth; test with same tenant, different data).
    - [ ] Verify agent prompt: trigger a conversation in WhatsApp mock for a date that now has a custom closure — agent should mention the clinic is closed on that date (inspect prompt via debug log or test).

---

## Task Count Summary

| Phase | Tasks | TDD order |
|-------|-------|-----------|
| 1 — Schema audit | 2 (1.2 conditional) | — |
| 2 — Types + i18n | 2 | prerequisite |
| 3 — Tests | 3 | BEFORE Phase 4 + 5 |
| 4 — Frontend | 6 | AFTER Phase 3 |
| 5 — Verification | 2 | AFTER Phase 3+4 |
| 6 — E2E | 1 | last |
| **Total** | **16 (+ 1 conditional)** | |
