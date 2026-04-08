# Tasks: Derivation Escalation Fallback

**Change**: `derivation-escalation-fallback`
**Status**: READY
**Date**: 2026-04-07
**TDD**: Strict — test tasks come BEFORE implementation tasks within each phase.
**Total tasks**: 28

---

## Dependency Graph

```
1.1 (migration) → 1.2 (ORM)
1.1 + 1.2 → 2.1 (Pydantic test) → 2.2 (Pydantic impl) → 2.3 (CRUD test) → 2.4 (CRUD impl)
2.4 → 3.1 (formatter test) → 3.2 (formatter impl)
2.4 → 4.1 (count helper test) → 4.2 (count helper impl) → 4.3 (escalation algo test) → 4.4 (escalation algo impl)
4.4 → 4.5 (book_appointment contract test) → 4.6 (book_appointment return format impl)
3.2 + 4.4 → 5.1 (i18n keys) → 5.2 (frontend type + state) → 5.3 (frontend UI test) → 5.4 (frontend UI impl)
All phases → 6.1–6.4 (Gherkin e2e scenarios)
All phases → 6.5 (regression: existing rules unchanged)
```

---

## Phase 1: Infrastructure (DB + Model)

- [ ] 1.1 Create Alembic migration `037_derivation_escalation_fallback.py`
  - File: `orchestrator_service/alembic/versions/037_derivation_escalation_fallback.py`
  - Depends on: none
  - Acceptance:
    - `revision = "037"`, `down_revision = "036"`
    - `upgrade()` adds 6 columns to `professional_derivation_rules` with idempotency guard on `enable_escalation`
    - `upgrade()` creates FK constraint `fk_derivation_fallback_professional` → `professionals.id` ON DELETE SET NULL
    - `downgrade()` drops FK constraint, then drops all 6 columns in reverse order
    - Running `upgrade()` on a DB with existing rules: all existing rows have `enable_escalation = false`, `fallback_team_mode = false`, `max_wait_days_before_escalation = 7`, others NULL
    - Running `downgrade()` after `upgrade()`: all 6 columns absent, pre-existing data intact
    - Uses `from alembic import op; import sqlalchemy as sa; from sqlalchemy.dialects import postgresql` imports

- [ ] 1.2 Add 6 escalation fields to `ProfessionalDerivationRule` ORM model
  - File: `orchestrator_service/models.py`
  - Depends on: 1.1
  - Acceptance:
    - 6 new `Column(...)` attributes added after `description` in `ProfessionalDerivationRule`
    - `fallback_professional_id` uses `ForeignKey("professionals.id", ondelete="SET NULL")`
    - `criteria_custom` uses `JSONB` (imported from `sqlalchemy.dialects.postgresql`)
    - No other model classes modified
    - Python import of `JSONB` added if not already present in `models.py`

---

## Phase 2: Backend — Pydantic Schemas + Endpoints (TDD)

### 2a — Pydantic validation

- [ ] 2.1 Write unit tests for `DerivationRuleCreate`/`Update` validation
  - File: `tests/test_derivation_escalation_fallback.py` (new file)
  - Depends on: 1.1, 1.2
  - Test class: `TestDerivationEscalationPydantic`
  - Acceptance:
    - `test_defaults_no_escalation`: create model with only required fields → `enable_escalation = False`, `max_wait_days_before_escalation = 7`, `fallback_team_mode = False`
    - `test_max_wait_days_too_high`: pass `max_wait_days_before_escalation = 31` → `ValidationError` raised
    - `test_max_wait_days_too_low`: pass `max_wait_days_before_escalation = 0` → `ValidationError` raised
    - `test_max_wait_days_boundary_valid`: pass `max_wait_days_before_escalation = 1` and `= 30` → no error
    - Tests FAIL before implementation (red phase)

- [ ] 2.2 Implement `DerivationRuleCreate`/`Update` Pydantic changes
  - File: `orchestrator_service/admin_routes.py`
  - Depends on: 2.1
  - Acceptance:
    - 6 new fields added with correct types, defaults, and `Field(ge=1, le=30)` on `max_wait_days_before_escalation`
    - Tests 2.1 pass (green phase)

### 2b — Endpoint validation

- [ ] 2.3 Write integration tests for `_validate_derivation_rule()` new checks
  - File: `tests/test_derivation_escalation_fallback.py`
  - Depends on: 2.2
  - Test class: `TestDerivationEscalationValidation`
  - Acceptance:
    - `test_fallback_pid_conflict_with_team_mode`: pass `fallback_professional_id=5, fallback_team_mode=True` → HTTP 422 `"No se puede especificar fallback_professional_id cuando fallback_team_mode es true"`
    - `test_fallback_pid_wrong_tenant`: mock DB to return None for fallback professional → HTTP 422 `"El profesional de fallback no pertenece a esta clínica"`
    - `test_implicit_team_mode`: pass `enable_escalation=True, fallback_professional_id=None, fallback_team_mode=False` → `data.fallback_team_mode` becomes `True` (no error)
    - Tests FAIL before implementation (red phase)

- [ ] 2.4 Implement `_validate_derivation_rule()` additions + persist new fields in POST/PUT
  - File: `orchestrator_service/admin_routes.py`
  - Depends on: 2.3
  - Acceptance:
    - 3 new validation checks added (conflict guard, fallback tenant isolation, implicit team mode)
    - INSERT and UPDATE SQL statements include all 6 new fields
    - GET endpoint SELECT includes all 6 new fields
    - Tests 2.3 pass (green phase)

---

## Phase 3: Prompt Formatter (TDD)

- [ ] 3.1 Write unit tests for `_format_derivation_rules()` escalation output
  - File: `tests/test_derivation_escalation_fallback.py`
  - Depends on: none (pure function, no DB)
  - Test class: `TestFormatDerivationRulesEscalation`
  - Acceptance:
    - `test_no_escalation_rule_unchanged`: rule with `enable_escalation=False` → output matches current format exactly (no "Acción primaria", no "Escalación activa")
    - `test_escalation_team_mode`: rule with `enable_escalation=True, fallback_team_mode=True, max_wait_days_before_escalation=5` → output contains "Acción primaria", "Escalación activa: si ... no tiene turnos en 5 días → intentar con cualquier profesional activo del equipo"
    - `test_escalation_specific_professional`: rule with `enable_escalation=True, fallback_professional_id=5, fallback_professional_name="Dr. García"` → output contains "intentar con Dr. García (ID: 5)"
    - `test_escalation_custom_template`: rule with `escalation_message_template="Hoy {primary} no puede atenderte, pero {fallback} sí."` → output contains that template verbatim in the "Mensaje para el paciente" line
    - `test_escalation_default_template`: rule with `escalation_message_template=None` → output contains built-in default Spanish template with `{primary}` and `{fallback}` resolved
    - Tests FAIL before implementation (red phase)

- [ ] 3.2 Implement `_format_derivation_rules()` escalation-aware rewrite
  - File: `orchestrator_service/main.py`
  - Depends on: 3.1
  - Acceptance:
    - Function signature unchanged (accepts same `rules: list` parameter)
    - Rules with `enable_escalation=False` produce identical output to today
    - Rules with `enable_escalation=True` produce escalation block as per design.md
    - `fallback_professional_name` is read from rule dict (enriched by caller — see task 4.7)
    - All 5 test cases in 3.1 pass (green phase)

---

## Phase 4: Tool Integration (TDD)

### 4a — Count helper

- [ ] 4.1 Write unit tests for `_count_slots_for_prof()` helper
  - File: `tests/test_derivation_escalation_fallback.py`
  - Depends on: 1.1, 1.2
  - Test class: `TestCountSlotsForProf`
  - Acceptance:
    - `test_returns_0_when_no_slots`: mock DB to return empty schedule → returns 0
    - `test_returns_positive_when_slots_exist`: mock DB with 2 available slots → returns 2
    - `test_respects_max_days_cap`: mock provides slots only on day 8, max_days=7 → returns 0
    - Uses `pytest-asyncio` (async function), mock via `unittest.mock.AsyncMock` or `pytest-mock`
    - Tests FAIL before implementation (red phase)

- [ ] 4.2 Implement `_count_slots_for_prof()` private async helper
  - File: `orchestrator_service/main.py`
  - Depends on: 4.1
  - Acceptance:
    - New private async function `_count_slots_for_prof(tenant_id, prof_id, treatment_name, max_days) -> int`
    - Iterates over the next `max_days` days from today checking for available slots for the given professional
    - Returns integer count (0 = saturated or no working days in window)
    - Does NOT format any output strings (count only)
    - Tests 4.1 pass (green phase)

### 4b — Escalation algorithm in `check_availability`

- [ ] 4.3 Write integration tests for escalation algorithm in `check_availability`
  - File: `tests/test_derivation_escalation_fallback.py`
  - Depends on: 4.2
  - Test class: `TestCheckAvailabilityEscalation`
  - Acceptance:
    - `test_no_escalation_when_disabled`: rule with `enable_escalation=False`, primary has 0 slots → result does NOT contain escalation message, result IS the standard "no disponibilidad"
    - `test_no_escalation_when_primary_has_slots`: rule with `enable_escalation=True`, primary has 3 slots → result does NOT contain escalation message, result contains primary's slots
    - `test_escalation_fires_team_mode`: rule with `enable_escalation=True, fallback_team_mode=True`, primary 0 slots, team has 2 → result contains escalation message prefix + 2 team slots
    - `test_escalation_fires_specific_prof`: rule with `enable_escalation=True, fallback_professional_id=5`, primary 0 slots, fallback prof has 1 slot → result contains escalation message with fallback prof name + 1 slot
    - `test_escalation_exhausted`: rule with `enable_escalation=True`, primary 0 slots, fallback also 0 slots → result is standard "no disponibilidad" WITHOUT escalation message
    - Tests use mocked DB pool and mocked `_count_slots_for_prof`
    - Tests FAIL before implementation (red phase)

- [ ] 4.4 Implement escalation algorithm in `check_availability` `# 0b. DERIVATION RULES` block
  - File: `orchestrator_service/main.py`
  - Depends on: 4.3
  - Acceptance:
    - SQL query for derivation rules extended to include all 6 new escalation columns
    - Escalation check runs only when `enable_escalation=True` AND primary prof returned 0 slots
    - `escalation_message_prefix` is prepended to tool return string when fallback slots are found
    - `{primary}` and `{fallback}` placeholders resolved to professional names in the message
    - Fallback professional name fetched from DB and included in slot string (so agent can extract for `book_appointment`)
    - INFO log emitted on escalation trigger
    - Tests 4.3 pass (green phase)
    - Existing tests in `tests/test_agent_behavioral_correction.py` and other test files continue to pass

- [ ] 4.5 Write test for `book_appointment` contract: correct professional used post-escalation
  - File: `tests/test_derivation_escalation_fallback.py`
  - Depends on: 4.4
  - Test class: `TestBookAppointmentEscalationContract`
  - Acceptance:
    - `test_book_uses_fallback_prof_name`: simulate agent flow → `check_availability` returns fallback slots with fallback prof name in string → assert that the string contains the fallback prof name so agent can pass it to `book_appointment`
    - `test_book_does_not_re_resolve_derivation`: `book_appointment` called with `professional_name="García"` → does NOT query `professional_derivation_rules` (mock verifies no such call)
    - Tests FAIL before implementation (red phase)

- [ ] 4.6 Ensure `check_availability` return string includes fallback professional name in slot entries
  - File: `orchestrator_service/main.py`
  - Depends on: 4.5
  - Acceptance:
    - When escalation fires and fallback is a specific professional, each slot line MUST include the fallback professional's name (already the case for normal multi-professional results — verify it works for escalation path)
    - Tests 4.5 pass (green phase)

- [ ] 4.7 Update `buffer_task.py` derivation rules query to include escalation columns + fallback name JOIN
  - File: `orchestrator_service/services/buffer_task.py` (or wherever the derivation rules query for `build_system_prompt()` lives — search for the query that feeds `derivation_rules` to `build_system_prompt`)
  - Depends on: 3.2
  - Acceptance:
    - Query extended with LEFT JOIN on `professionals fp ON dr.fallback_professional_id = fp.id`
    - SELECT includes `fp.first_name || ' ' || COALESCE(fp.last_name, '') AS fallback_professional_name`
    - SELECT includes all 6 new escalation columns
    - `_format_derivation_rules()` receives enriched dicts with `fallback_professional_name`

---

## Phase 5: Frontend Modal (TDD)

- [ ] 5.1 Add i18n keys to all 3 locale files
  - Files: `frontend_react/src/locales/es.json`, `en.json`, `fr.json`
  - Depends on: none
  - Acceptance:
    - 10 new keys added under `settings.derivation.escalation` in each file
    - Spanish values match spec.md REQ-9 exactly
    - English and French translations provided (values per design.md)
    - No existing keys modified

- [ ] 5.2 Extend `DerivationRule` TypeScript type and `derivationForm` state defaults
  - File: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 5.1
  - Acceptance:
    - `DerivationRule` interface (or type) extended with 6 optional fields matching design.md
    - `emptyDerivationForm` / initial form state includes `enable_escalation: false`, `fallback_team_mode: false`, `max_wait_days_before_escalation: 7`, others undefined/empty
    - Editing an existing rule pre-populates new fields from the API response
    - TypeScript compiles without errors (`npm run build` does NOT fail — but do NOT run the build per project rules)

- [ ] 5.3 Write frontend unit/integration tests for escalation modal section
  - File: `frontend_react/src/views/__tests__/ClinicsView.derivation.test.tsx` (new) or appropriate test file
  - Depends on: 5.2
  - Test class / describe block: `DerivationModal escalation section`
  - Acceptance:
    - `test_escalation_section_hidden_by_default`: render modal → escalation sub-fields NOT visible (toggle is OFF)
    - `test_escalation_section_visible_when_toggle_on`: click toggle → escalation sub-fields appear
    - `test_fallback_team_mode_hides_professional_dropdown`: toggle ON, select "Qualquier profesional" → professional dropdown NOT rendered
    - `test_fallback_specific_shows_professional_dropdown`: toggle ON, select "Profesional específico" → professional dropdown rendered
    - `test_submit_includes_escalation_fields`: fill in escalation fields, submit form → POST body includes `enable_escalation: true`, `max_wait_days_before_escalation: 5`, etc.
    - Tests FAIL before implementation (red phase)

- [ ] 5.4 Implement escalation sub-section in derivation rule modal
  - File: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 5.3
  - Acceptance:
    - Escalation section added inside the `<form>` before the action buttons
    - Toggle button follows dark mode design system (dark background, blue when active)
    - All sub-fields use same input styling as existing modal fields (see lines 1485–1553 of ClinicsView.tsx for reference)
    - Fallback professional dropdown filters out the already-selected `target_professional_id` (can't be your own fallback)
    - Submit handler sends all 6 new fields to POST/PUT endpoint
    - Tests 5.3 pass (green phase)
    - No regressions in existing form behavior (rule_name, patient_condition, etc.)

---

## Phase 6: End-to-End Scenarios

- [ ] 6.1 E2E test — Scenario 1: Primary available, no escalation triggered
  - File: `tests/test_derivation_escalation_fallback.py`
  - Depends on: all Phase 4 tasks
  - Test: `test_e2e_primary_available_no_escalation`
  - Acceptance: per Gherkin Scenario 1 in spec.md REQ-7 — primary has slots, result contains primary slots, no escalation message

- [ ] 6.2 E2E test — Scenario 2: Primary saturated, fallback to specific professional
  - File: `tests/test_derivation_escalation_fallback.py`
  - Depends on: all Phase 4 tasks
  - Test: `test_e2e_primary_saturated_fallback_specific`
  - Acceptance: per Gherkin Scenario 2 in spec.md REQ-7 — escalation fires, result contains Dr. García slots, escalation message has correct `{primary}` and `{fallback}` values, INFO log emitted

- [ ] 6.3 E2E test — Scenario 3: Primary saturated, fallback to team
  - File: `tests/test_derivation_escalation_fallback.py`
  - Depends on: all Phase 4 tasks
  - Test: `test_e2e_primary_saturated_fallback_team`
  - Acceptance: per Gherkin Scenario 3 in spec.md REQ-7 — custom `escalation_message_template` used, `{primary}` resolved to "Dra. López", `{fallback}` resolved to "el equipo"

- [ ] 6.4 E2E test — Scenario 4: Escalation disabled, standard no-availability behavior
  - File: `tests/test_derivation_escalation_fallback.py`
  - Depends on: all Phase 4 tasks
  - Test: `test_e2e_escalation_disabled_no_availability`
  - Acceptance: per Gherkin Scenario 4 in spec.md REQ-7 — `enable_escalation=False`, primary saturated, result is standard "no disponibilidad", no fallback query executed

- [ ] 6.5 Regression: existing derivation rules unchanged behavior
  - File: `tests/test_derivation_escalation_fallback.py`
  - Depends on: all phases
  - Test: `test_regression_existing_rules_no_change`
  - Acceptance:
    - Load a rule dict matching the pre-migration schema (no escalation fields at all)
    - `_format_derivation_rules()` produces output identical to the old format
    - `check_availability` with such a rule produces output identical to current behavior
    - Verifies zero regression for tenants that never touch escalation settings

- [ ] 6.6 Run full test suite
  - Command: `pytest tests/test_derivation_escalation_fallback.py -v`
  - Depends on: all prior tasks
  - Acceptance:
    - All 28 test cases GREEN
    - No regressions in `tests/test_agent_behavioral_correction.py` or other existing test files
    - Coverage for new code path >= 80% (measured with `pytest --cov=orchestrator_service`)
