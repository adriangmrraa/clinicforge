# Tasks: Insurance Coverage by Treatment

**Change**: `insurance-coverage-by-treatment`
**Status**: READY
**Date**: 2026-04-07
**TDD**: Strict — test tasks come BEFORE implementation tasks in every phase.
**Total tasks**: 28

---

## Dependency Graph

```
1.1 (migration) → 1.2 (ORM update) → 1.3 (migration data test)

1.2 → 2.1 (Pydantic test) → 2.2 (Pydantic impl)
2.2 → 2.3 (endpoints test) → 2.4 (endpoints impl)
2.4 → 2.5 (list endpoint JSONB parse test) → 2.6 (list endpoint JSONB parse impl)

1.2 + 2.4 → 3.1 (formatter test — empty coverage) → 3.2 (formatter impl)
3.2 → 3.3 (formatter test — rich coverage) → 3.4 (formatter integration with build_system_prompt)
3.4 → 3.5 (treatment_display_map wiring test) → 3.6 (treatment_display_map wiring impl)

2.4 + 3.6 → 4.1 (frontend types + state shape)
4.1 → 4.2 (frontend validation util test) → 4.3 (frontend validation impl)
4.3 → 4.4 (frontend CoverageMatrixRow component)
4.4 → 4.5 (frontend CoverageMatrix component)
4.5 → 4.6 (frontend modal integration)
4.6 → 4.7 (i18n keys)

All phases → 5.1–5.6 (end-to-end scenarios)
```

---

## Phase 1: Infrastructure (DB + Model)

### 1.1 — Write Alembic migration 034

- **Files**: `orchestrator_service/alembic/versions/034_insurance_coverage_by_treatment.py`
- **Depends on**: none
- **Acceptance**:
  - `revision = "034"`, `down_revision = "033"`
  - `upgrade()`:
    - Adds `coverage_by_treatment JSONB NOT NULL DEFAULT '{}'`
    - Adds `is_prepaid BOOLEAN NOT NULL DEFAULT FALSE`
    - Adds `employee_discount_percent DECIMAL(5,2) NULL`
    - Adds `default_copay_percent DECIMAL(5,2) NULL`
    - Migrates each row: valid JSON array in `restrictions` → `coverage_by_treatment` dict with `covered=true` entries and all other fields at default values
    - Rows with NULL/empty/non-JSON `restrictions` → `coverage_by_treatment = '{}'`
    - Drops `restrictions` column after data migration
  - `downgrade()`:
    - Adds back `restrictions TEXT NULL`
    - Reverse data migration: `covered=true` codes → JSON array string
    - Drops `coverage_by_treatment`, `is_prepaid`, `employee_discount_percent`, `default_copay_percent`
  - Migration is idempotent: checks if columns already exist before adding (consistent with project style)
  - Uses `op.get_bind()` for inline data migration (consistent with existing migrations in this project)

### 1.2 — Update `TreatmentInsuranceProvider` ORM model

- **Files**: `orchestrator_service/models.py`
- **Depends on**: 1.1
- **Acceptance**:
  - `TenantInsuranceProvider` class:
    - `restrictions` column REMOVED
    - `coverage_by_treatment = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))` ADDED
    - `is_prepaid = Column(Boolean, nullable=False, server_default="false")` ADDED
    - `employee_discount_percent = Column(DECIMAL(5, 2), nullable=True)` ADDED
    - `default_copay_percent = Column(DECIMAL(5, 2), nullable=True)` ADDED
  - `JSONB` imported from `sqlalchemy.dialects.postgresql` (verify it's already imported; add if not)
  - No other model changes

### 1.3 — Write migration data migration test

- **Files**: `tests/test_insurance_coverage_migration.py` (new file)
- **Depends on**: 1.1
- **Acceptance**:
  - Test class `TestInsuranceCoverageMigration`
  - `test_upgrade_migrates_valid_restrictions_array`: sets up a mock row dict with `restrictions = '["IMPT", "CONS"]'`, runs the migration logic as a pure function, asserts `coverage_by_treatment["IMPT"]["covered"] == True` and `coverage_by_treatment["CONS"]["covered"] == True`
  - `test_upgrade_handles_null_restrictions`: row with `restrictions = None` → `coverage_by_treatment == {}`
  - `test_upgrade_handles_empty_string_restrictions`: row with `restrictions = ""` → `coverage_by_treatment == {}`
  - `test_upgrade_handles_invalid_json_restrictions`: row with `restrictions = "texto libre"` → `coverage_by_treatment == {}`
  - `test_downgrade_restores_covered_codes`: row with `coverage_by_treatment = {"IMPT": {"covered": True}, "CONS": {"covered": False}}` → `restrictions == '["IMPT"]'`
  - `test_downgrade_empty_coverage_gives_null`: row with `coverage_by_treatment = {}` → `restrictions == None`
  - Tests are pure Python (no DB required) — extract migration logic into a pure function `_migrate_restrictions_to_coverage(restrictions_str)` and `_migrate_coverage_to_restrictions(coverage_dict)` in the migration file, test those directly.

---

## Phase 2: Backend (TDD order)

### 2.1 — Write unit tests for `TreatmentCoverage` Pydantic schema

- **Files**: `tests/test_insurance_coverage_backend.py` (new file)
- **Depends on**: 1.2
- **Acceptance**:
  - Test class `TestTreatmentCoverageSchema`
  - `test_valid_minimal_entry`: `TreatmentCoverage(covered=True)` validates without error, all defaults applied
  - `test_copay_percent_above_100_raises`: `copay_percent=150` → `ValidationError`
  - `test_copay_percent_negative_raises`: `copay_percent=-1` → `ValidationError`
  - `test_pre_auth_leadtime_negative_raises`: `pre_auth_leadtime_days=-1` → `ValidationError`
  - `test_waiting_period_negative_raises`: `waiting_period_days=-1` → `ValidationError`
  - `test_max_annual_coverage_zero_raises`: `max_annual_coverage=0` → `ValidationError`
  - `test_notes_over_500_chars_raises`: notes string of 501 chars → `ValidationError`
  - Tests FAIL before 2.2 (red phase)

### 2.2 — Implement `TreatmentCoverage` Pydantic model + update `InsuranceProviderCreate`/`Update`

- **Files**: `orchestrator_service/admin_routes.py`
- **Depends on**: 2.1
- **Acceptance**:
  - `TreatmentCoverage` class defined with all fields, defaults, and validators (using `@validator` or `model_validator`)
  - `InsuranceProviderCreate.coverage_by_treatment: Optional[dict[str, TreatmentCoverage]] = None` replaces `restrictions`
  - `InsuranceProviderCreate.is_prepaid`, `employee_discount_percent`, `default_copay_percent` added
  - Same for `InsuranceProviderUpdate`
  - `_validate_insurance_provider()` updated: removes `restrictions` checks, adds coverage entry validation loop (see design.md D5)
  - Tests 2.1 pass (green phase)

### 2.3 — Write integration tests for CRUD endpoints

- **Files**: `tests/test_insurance_coverage_backend.py`
- **Depends on**: 2.2
- **Acceptance**:
  - Test class `TestInsuranceProviderEndpoints`
  - `test_create_provider_with_coverage`: POST with valid `coverage_by_treatment` dict → 201, response includes coverage
  - `test_create_provider_invalid_copay_percent`: POST with `copay_percent=150` → 422
  - `test_update_provider_replaces_coverage`: PUT with new `coverage_by_treatment` → full replacement, not merge
  - `test_list_providers_returns_dict_not_string`: GET → `coverage_by_treatment` is dict in response
  - `test_create_provider_no_coverage`: POST with `coverage_by_treatment=null` → 201, stored as `{}`
  - Tests use `pytest` + `httpx` (or existing test client pattern in the project — verify from existing test files)
  - Tests FAIL before 2.4 (red phase)

### 2.4 — Implement CRUD endpoint changes

- **Files**: `orchestrator_service/admin_routes.py`
- **Depends on**: 2.3
- **Acceptance**:
  - `list_insurance_providers`: SELECT includes `coverage_by_treatment`, `is_prepaid`, `employee_discount_percent`, `default_copay_percent`; does NOT select `restrictions`; applies `json.loads` if JSONB returned as string
  - `create_insurance_provider`: INSERT uses new columns; serializes `coverage_by_treatment` with `json.dumps`
  - `update_insurance_provider`: UPDATE uses new columns; same serialization
  - All queries include `tenant_id = $x` (existing pattern, preserved)
  - Embedding of coverage data into the prompt builder call in `buffer_task.py` is NOT in this task (see 3.6)
  - Tests 2.3 pass (green phase)

### 2.5 — Write test for JSONB defensive parse in list endpoint

- **Files**: `tests/test_insurance_coverage_backend.py`
- **Depends on**: 2.4
- **Acceptance**:
  - `test_list_providers_jsonb_returned_as_string`: simulate asyncpg returning `coverage_by_treatment` as string `'{"IMPT": {"covered": true}}'` → endpoint converts to dict before returning
  - Test uses a mock/patch of `db.pool.fetch` to return a row with string value
  - Tests FAIL before 2.6 (red phase)

### 2.6 — Implement JSONB defensive parse in list endpoint

- **Files**: `orchestrator_service/admin_routes.py`
- **Depends on**: 2.5
- **Acceptance**:
  - In `list_insurance_providers`, after `[dict(r) for r in rows]`, add defensive `json.loads` loop
  - Tests 2.5 pass (green phase)

---

## Phase 3: Prompt Integration (TDD order)

### 3.1 — Write unit tests for `_format_insurance_providers` — empty / legacy coverage

- **Files**: `tests/test_insurance_coverage_prompt.py` (new file)
- **Depends on**: 1.2
- **Acceptance**:
  - Test class `TestFormatInsuranceProviders`
  - `test_empty_providers_returns_empty_string`: `_format_insurance_providers([])` → `""`
  - `test_provider_with_empty_coverage_uses_fallback`: provider dict with `coverage_by_treatment = {}` → output contains `copay_notes` value or "coseguro estándar", does NOT raise
  - `test_provider_with_null_coverage_uses_fallback`: `coverage_by_treatment = None` → same fallback
  - `test_provider_with_coverage_as_string_parses_correctly`: `coverage_by_treatment = '{"IMPT": {"covered": true, "copay_percent": 30}}'` (string) → output contains "coseguro 30%", no exception
  - Tests FAIL before 3.2 (red phase)

### 3.2 — Implement `_format_insurance_providers` rewrite

- **Files**: `orchestrator_service/main.py`
- **Depends on**: 3.1
- **Acceptance**:
  - Function signature updated: `def _format_insurance_providers(providers: list, treatment_display_map: dict = None) -> str:`
  - Full rewrite per design.md D6 pseudocode
  - Fallback to generic block when `coverage_by_treatment` is empty dict (existing behavior preserved)
  - Treatment display names used from `treatment_display_map` when provided; code used as fallback when map is absent
  - Cap at 10 entries per provider with overflow message
  - `is_prepaid` flag emitted
  - `default_copay_percent` emitted when set
  - Tests 3.1 pass (green phase)

### 3.3 — Write unit tests for `_format_insurance_providers` — rich coverage

- **Files**: `tests/test_insurance_coverage_prompt.py`
- **Depends on**: 3.2
- **Acceptance**:
  - `test_covered_treatment_shows_copay_percent`: coverage with `copay_percent=30` → output contains "coseguro 30%"
  - `test_covered_treatment_with_preauth`: `requires_pre_authorization=True`, `pre_auth_leadtime_days=5` → output contains "requiere preautorización (5 días hábiles)"
  - `test_covered_treatment_with_waiting_period`: `waiting_period_days=180` → output contains "carencia 180 días"
  - `test_not_covered_treatment_labeled`: `covered=False` → treatment appears under "NO cubiertos"
  - `test_prepaid_flag_in_output`: `is_prepaid=True` → output contains "(prepaga)"
  - `test_cap_at_10_entries`: provider with 12 treatment entries → output contains the overflow message, exactly 10 treatment lines
  - `test_treatment_display_name_used`: `treatment_display_map={"IMPT": "Implante dental"}` → output contains "Implante dental (IMPT)" not just "IMPT"
  - All tests pass (green — 3.2 already implemented)

### 3.4 — Update `build_system_prompt` caller for new formatter signature

- **Files**: `orchestrator_service/main.py`
- **Depends on**: 3.2
- **Acceptance**:
  - `_format_insurance_providers(insurance_providers or [], treatment_display_map)` called with display map
  - `treatment_display_map` built from the `treatment_types` list already available in the prompt builder context
  - No change to `build_system_prompt` signature (adds no new parameter)
  - Existing callers of `build_system_prompt` unaffected

### 3.5 — Write integration test for formatter + build_system_prompt

- **Files**: `tests/test_insurance_coverage_prompt.py`
- **Depends on**: 3.4
- **Acceptance**:
  - `test_build_system_prompt_includes_coverage_detail`: call `build_system_prompt(...)` with a mock insurance provider having rich `coverage_by_treatment` and a `treatment_types` list → returned prompt string contains "coseguro" and the treatment display name
  - `test_build_system_prompt_empty_coverage_no_crash`: call with provider having `coverage_by_treatment = {}` → no exception, prompt contains generic fallback

### 3.6 — Verify `buffer_task.py` passes treatment_types to prompt builder

- **Files**: `orchestrator_service/buffer_task.py`
- **Depends on**: 3.5
- **Acceptance**:
  - Verify that `treatment_types` are already fetched in `buffer_task.py` and passed to `build_system_prompt`. If yes: no change needed, just verify.
  - If `treatment_types` are NOT passed: add the fetch (SELECT code, name, patient_display_name FROM treatment_types WHERE tenant_id = $1 AND is_active = true) and pass to `build_system_prompt`.
  - No regression in existing buffer_task behavior.

---

## Phase 4: Frontend (TDD order)

### 4.1 — Define TypeScript types and update form state shape

- **Files**: `frontend_react/src/views/ClinicsView.tsx` (or a new types file if preferred)
- **Depends on**: 2.4
- **Acceptance**:
  - `TreatmentCoverageEntry` interface defined
  - `InsuranceFormState` interface updated: `coverage_by_treatment: Record<string, TreatmentCoverageEntry>` replaces `restrictions: string`
  - `parseRestrictionsAsCodes()` replaced by `parseCoverageByTreatment()` (returns `Record<string, TreatmentCoverageEntry>` from API response)
  - TypeScript compiles without errors

### 4.2 — Write unit tests for frontend validation utility

- **Files**: `frontend_react/src/views/ClinicsView.test.tsx` (new file, or matching existing test pattern)
- **Depends on**: 4.1
- **Acceptance**:
  - `test_validateInsuranceForm_valid_form_returns_no_errors`: fully valid form → `{}`
  - `test_validateInsuranceForm_copay_above_100`: coverage entry with `copay_percent=150` → errors contains key `coverage_{code}_copay`
  - `test_validateInsuranceForm_waiting_negative`: `waiting_period_days=-1` → errors contains `coverage_{code}_waiting`
  - `test_validateInsuranceForm_notes_too_long`: 501 char notes → error present
  - `test_validateInsuranceForm_default_copay_out_of_range`: `default_copay_percent=101` → `errors.default_copay_percent` present
  - Tests use `vitest` (consistent with project frontend test setup — verify `vite.config.ts`)
  - Tests FAIL before 4.3 (red phase)

### 4.3 — Implement frontend validation utility

- **Files**: `frontend_react/src/views/ClinicsView.tsx`
- **Depends on**: 4.2
- **Acceptance**:
  - `validateInsuranceForm(form: InsuranceFormState): Record<string, string>` implemented
  - Submit button disabled when `Object.keys(validateInsuranceForm(form)).length > 0`
  - Tests 4.2 pass (green phase)

### 4.4 — Implement `CoverageMatrixRow` sub-component

- **Files**: `frontend_react/src/views/ClinicsView.tsx` (inline component or extracted)
- **Depends on**: 4.3
- **Acceptance**:
  - Props: `treatmentCode`, `treatmentName`, `entry: TreatmentCoverageEntry`, `onChange: (code, entry) => void`, `errors: Record<string, string>`
  - Renders: covered toggle, conditionally copay % input (when covered=true), pre-auth checkbox (when covered), pre-auth days input (when requires_pre_authorization), waiting days input (when covered), notes input
  - Inline error messages for validation failures
  - Dark mode styling consistent with existing modal inputs (`bg-white/[0.04] border-white/[0.08] text-white`)
  - Does NOT render when `status` is `external_derivation` or `rejected`

### 4.5 — Implement `CoverageMatrix` component

- **Files**: `frontend_react/src/views/ClinicsView.tsx`
- **Depends on**: 4.4
- **Acceptance**:
  - Props: `treatments: {code, name}[]`, `coverage: Record<string, TreatmentCoverageEntry>`, `onChange`, `errors`
  - Collapsible section (collapsed by default) with header showing count of configured treatments
  - "Marcar todos como cubiertos" quick-action button
  - Scrollable treatment list (max-height with `overflow-y-auto`)
  - One `CoverageMatrixRow` per treatment
  - Empty state: "Ningún tratamiento activo — configurá tratamientos en la sección de tratamientos"

### 4.6 — Integrate matrix into insurance modal

- **Files**: `frontend_react/src/views/ClinicsView.tsx`
- **Depends on**: 4.5
- **Acceptance**:
  - `CoverageMatrix` appears in modal form when `status` is `accepted` or `restricted`
  - Modal initial state populates `coverage_by_treatment` from existing provider data (via `parseCoverageByTreatment()`)
  - Form submit serializes `coverage_by_treatment` correctly for the API
  - New fields `is_prepaid`, `default_copay_percent`, `employee_discount_percent` rendered and wired to form state
  - `handleInsuranceSubmit` sends the new payload shape
  - On save success, local provider list refreshes
  - `max-w-lg` modal width MAY be increased to `max-w-2xl` to accommodate the matrix — verify with design

### 4.7 — Add i18n keys

- **Files**: `frontend_react/src/locales/es.json`, `en.json`, `fr.json`
- **Depends on**: 4.6
- **Acceptance**:
  - All 14 new field keys from design.md D8 added to `settings.insurance.fields`
  - All 3 new error keys added to `settings.insurance.errors`
  - Keys added to all 3 files (no missing translations)
  - No existing keys removed or renamed

---

## Phase 5: End-to-End Verification

Each task in this phase verifies one of the 6 scenarios from REQ-4. These are manual or integration tests, not unit tests.

### 5.1 — Scenario A: Copay percentage

- **Test**: Create OSDE with `coverage_by_treatment["IMPT"] = {covered: true, copay_percent: 30}`. Call `_format_insurance_providers([osde])`. Assert output contains "coseguro 30%". Build full system prompt. Verify the prompt block contains the copay detail.
- **Acceptance**: `test_scenario_a_copay_percent` in `tests/test_insurance_coverage_e2e.py`

### 5.2 — Scenario B: Pre-authorization

- **Test**: Create Swiss Medical with `coverage_by_treatment["EXTRAC"] = {covered: true, requires_pre_authorization: true, pre_auth_leadtime_days: 3}`. Assert prompt output contains "preautorización" and "3 días".
- **Acceptance**: `test_scenario_b_pre_authorization` in `tests/test_insurance_coverage_e2e.py`

### 5.3 — Scenario C: Waiting period

- **Test**: OSDE with `waiting_period_days=180` for IMPT. Assert prompt output contains "carencia 180".
- **Acceptance**: `test_scenario_c_waiting_period`

### 5.4 — Scenario D: Not covered

- **Test**: Provider with `coverage_by_treatment["BLAN"] = {covered: false}`. Assert output places "BLAN" under "NO cubiertos".
- **Acceptance**: `test_scenario_d_not_covered`

### 5.5 — Scenario E: Prepaga flag

- **Test**: Provider with `is_prepaid=True`. Assert output contains "(prepaga)".
- **Acceptance**: `test_scenario_e_prepaga_flag`

### 5.6 — Scenario F: Default copay fallback

- **Test**: Provider with `default_copay_percent=20`, no entry for "LIMPZ" in `coverage_by_treatment`. Assert prompt output contains "coseguro por defecto: 20%".
- **Acceptance**: `test_scenario_f_default_copay_fallback`

---

## Notes for Implementor

- Migration number: `034` (current head is `033_clinic_bot_name.py` after bot_name change)
- The `JSONB` import in `models.py`: check line ~10 for `from sqlalchemy.dialects.postgresql import JSONB, ARRAY` — `JSONB` is likely already imported (used in `TreatmentType.post_instructions`)
- `_format_insurance_providers` is a pure function (no I/O). All tests for it can be pure unit tests.
- The `buffer_task.py` treatment_types fetch: search for `SELECT.*treatment_types.*WHERE tenant_id` to find the existing query; if present, extend to include `patient_display_name`.
- Frontend test tooling: check `frontend_react/package.json` for `vitest` / `jest` — adapt test file extension accordingly.
- Keep migration data migration as extractable pure functions (`_migrate_restrictions_to_coverage`, `_migrate_coverage_to_restrictions`) to enable testability without a live DB.
