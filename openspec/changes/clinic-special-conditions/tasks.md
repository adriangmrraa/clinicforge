# Tasks: Clinic Special Conditions

**Change**: `clinic-special-conditions`
**Status**: READY
**Date**: 2026-04-07
**TDD**: Strict — test tasks come BEFORE implementation tasks within each phase.
**Total tasks**: 32

---

## Dependency Graph

```
1.1 (migration 036) → 1.2 (ORM model)
1.1 + 1.2 → 2.1 (Pydantic schema) → 2.2 (endpoint extension test) → 2.3 (endpoint impl)
2.1 → 3.1 (formatter unit tests) → 3.2 (formatter impl)
3.2 → 3.3 (build_system_prompt wiring test) → 3.4 (build_system_prompt wiring impl)
3.4 → 3.5 (buffer_task query extension)
3.5 → 3.6 (triage cross-reference prompt test) → 3.7 (triage cross-reference prompt impl)
2.3 → 4.1 (GET tenant includes new fields test) → 4.2 (GET tenant query extension)
4.2 → 4.3 (frontend state extension) → 4.4 (pregnancy sub-block UI)
4.4 → 4.5 (pediatric sub-block UI) → 4.6 (high-risk protocols editor UI)
4.6 → 4.7 (anamnesis gate toggle UI) → 4.8 (i18n keys)
All Phase 1-3 → 5.1-5.5 (scenario verification)
All Phase 1-3 → 5.6 (anti-medical-advice guardrail tests)
All phases → 5.7 (migration round-trip test)
```

---

## Phase 1: Infrastructure (Migration + Model)

- [ ] 1.1 Create Alembic migration `036_add_clinic_special_conditions.py`
  - Files: `orchestrator_service/alembic/versions/036_add_clinic_special_conditions.py`
  - Depends on: none
  - Acceptance:
    - `revision = "036"`, `down_revision = "035"`
    - `upgrade()` adds all 8 columns with correct SQL types and defaults:
      - `accepts_pregnant_patients BOOLEAN NOT NULL DEFAULT true`
      - `pregnancy_restricted_treatments JSONB DEFAULT '[]'`
      - `pregnancy_notes TEXT`
      - `accepts_pediatric BOOLEAN NOT NULL DEFAULT true`
      - `min_pediatric_age_years INTEGER` (nullable)
      - `pediatric_notes TEXT`
      - `high_risk_protocols JSONB DEFAULT '{}'`
      - `requires_anamnesis_before_booking BOOLEAN NOT NULL DEFAULT false`
    - `downgrade()` drops all 8 columns in reverse order
    - Idempotency guard: uses `inspector.get_columns("tenants")` check before each `add_column`
    - File naming convention: `036_add_clinic_special_conditions.py`

- [ ] 1.2 Add 8 attributes to `Tenant` SQLAlchemy ORM class
  - Files: `orchestrator_service/models.py`
  - Depends on: 1.1
  - Acceptance:
    - `Tenant` class gains all 8 new `Column` definitions after `max_chairs`
    - Types match migration: `Boolean`, `JSONB`, `Text`, `Integer`
    - Server defaults match migration: `server_default="true"`, `server_default="false"`, etc.
    - No other model changes

---

## Phase 2: Backend — Pydantic Schema + Endpoint (TDD order)

### Pydantic schema

- [ ] 2.1 Define `HighRiskProtocol` Pydantic model in `admin_routes.py`
  - Files: `orchestrator_service/admin_routes.py`
  - Depends on: none (pure code addition)
  - Acceptance:
    - `HighRiskProtocol(BaseModel)` with fields: `requires_medical_clearance: bool = False`, `requires_pre_appointment_call: bool = False`, `restricted_treatments: list[str] = []`, `notes: str = ""`
    - `model_config = {"extra": "forbid"}` — unknown keys raise `ValidationError`
    - `HighRiskProtocol(requires_medical_clearance="yes")` raises `ValidationError` (string is not bool)
    - `HighRiskProtocol(unknown_field=True)` raises `ValidationError`

### Endpoint tests (TDD — write tests BEFORE endpoint implementation)

- [ ] 2.2 Write unit/integration tests for the updated `update_tenant` endpoint
  - Files: `tests/test_clinic_special_conditions.py` (new file)
  - Depends on: 2.1, 1.1
  - Test class: `TestUpdateTenantSpecialConditions`
  - Acceptance:
    - `test_accepts_pregnant_patients_set_false`: PUT with `{"accepts_pregnant_patients": false}` → DB has `false`
    - `test_pregnancy_restricted_treatments_valid`: PUT with `{"pregnancy_restricted_treatments": ["xray_panoramic"]}` → DB stores JSON array
    - `test_pregnancy_restricted_treatments_invalid_type`: PUT with `{"pregnancy_restricted_treatments": [123]}` → HTTP 422
    - `test_min_pediatric_age_negative`: PUT with `{"min_pediatric_age_years": -1}` → HTTP 422
    - `test_high_risk_protocols_valid`: PUT with valid `high_risk_protocols` dict → stored correctly
    - `test_high_risk_protocols_invalid_bool_field`: PUT with `{"high_risk_protocols": {"diabetes": {"requires_medical_clearance": "yes"}}}` → HTTP 422
    - `test_high_risk_protocols_extra_key`: PUT with unknown key in protocol → HTTP 422
    - `test_requires_anamnesis_gate_toggle`: PUT with `{"requires_anamnesis_before_booking": true}` → DB has `true`
    - `test_non_ceo_rejected`: non-CEO user → HTTP 403
    - `test_partial_update_other_fields_unchanged`: setting only `pregnancy_notes` does not change `accepts_pediatric`
    - All tests use pytest + pytest-asyncio; mock DB connection or use test DB per project convention
    - Tests FAIL before endpoint implementation (red phase)

- [ ] 2.3 Implement `update_tenant` endpoint extension
  - Files: `orchestrator_service/admin_routes.py`
  - Depends on: 2.2
  - Acceptance:
    - All 8 new fields handled in the `update_tenant` function per the design file
    - `HighRiskProtocol` validation applied per-condition in `high_risk_protocols` dict
    - JSONB fields serialized with `json.dumps()` and cast with `::jsonb` in SQL
    - Integer `min_pediatric_age_years` validated `>= 0`
    - `pregnancy_restricted_treatments` validated as list of strings
    - All tests from 2.2 pass (green phase)

---

## Phase 3: Formatter + `build_system_prompt()` Wiring (TDD order)

### `_format_special_conditions()` — test first

- [ ] 3.1 Write unit tests for `_format_special_conditions()`
  - Files: `tests/test_clinic_special_conditions.py`
  - Depends on: none (pure unit test)
  - Test class: `TestFormatSpecialConditions`
  - Acceptance:
    - `test_empty_returns_empty_string`: all fields null/default → returns `""`
    - `test_accepts_pregnant_false`: `accepts_pregnant_patients=False` → output contains "no se atienden pacientes embarazadas"
    - `test_pregnancy_notes_verbatim`: `pregnancy_notes="Consultar con médico"` → output contains `"Consultar con médico"` verbatim
    - `test_pregnancy_restricted_resolves_code`: `pregnancy_restricted_treatments=["xray_panoramic"]` with `treatment_name_map={"xray_panoramic": "Radiografía panorámica"}` → output contains "Radiografía panorámica"
    - `test_pregnancy_restricted_fallback_code`: same but no `treatment_name_map` → output contains `"xray_panoramic"` raw code
    - `test_min_pediatric_age`: `min_pediatric_age_years=6` → output contains "desde los 6 años"
    - `test_accepts_pediatric_false`: → output contains "no se atienden pacientes pediátricos"
    - `test_high_risk_clearance`: `high_risk_protocols={"diabetes": {"requires_medical_clearance": True, "notes": "Pedir HbA1c"}}` → output contains "diabetes" and "clearance médico" and "Pedir HbA1c"
    - `test_high_risk_pre_call`: `requires_pre_appointment_call=True` → output contains "llamada del equipo antes del turno"
    - `test_anamnesis_gate_active`: `requires_anamnesis_before_booking=True` → output contains "ANAMNESIS GATE (ACTIVO)" and "EXCEPCIÓN" (emergency bypass)
    - `test_anamnesis_gate_inactive`: `requires_anamnesis_before_booking=False` → output does NOT contain "ANAMNESIS GATE"
    - `test_regla_de_oro_always_present_when_configured`: any non-empty config → output contains "NUNCA dar consejo médico"
    - `test_fallback_rule_always_present_when_configured`: any non-empty config → output contains "condición NO listada"
    - Anti-medical-advice tests:
      - `test_no_dangerous_language_pregnancy_restricted`: output MUST NOT contain "peligroso", "contraindicado médicamente", "no debes", "prohibido para embarazadas"
      - `test_no_dangerous_language_high_risk`: same check for high_risk protocols output
    - Tests FAIL before 3.2 (red phase)

- [ ] 3.2 Implement `_format_special_conditions()` in `main.py`
  - Files: `orchestrator_service/main.py`
  - Depends on: 3.1
  - Acceptance:
    - Function placed near other `_format_*` helpers, before `build_system_prompt()`
    - Signature: `def _format_special_conditions(tenant_data: dict, treatment_name_map: dict | None = None) -> str`
    - Returns `""` when all fields are null/default
    - Implements pregnancy, pediatric, high-risk, and anamnesis gate blocks per design pseudocode
    - Includes REGLA DE ORO block and fallback rule when any block is non-empty
    - JSONB defensively handled: `isinstance(val, str)` → `json.loads(val)` before iteration
    - All tests from 3.1 pass (green phase)

### `build_system_prompt()` wiring

- [ ] 3.3 Write unit test for `build_system_prompt()` injection of special conditions block
  - Files: `tests/test_clinic_special_conditions.py`
  - Depends on: 3.2
  - Test class: `TestBuildSystemPromptSpecialConditions`
  - Acceptance:
    - `test_special_conditions_injected_when_present`: call `build_system_prompt(..., special_conditions_block="TEST BLOCK")` → returned prompt contains "TEST BLOCK"
    - `test_special_conditions_absent_when_empty`: call with `special_conditions_block=""` → returned prompt does NOT contain "CONDICIONES ESPECIALES"
    - `test_backward_compatible_no_param`: call without `special_conditions_block` param → no error, prompt unchanged from previous behavior
    - Tests FAIL before 3.4 (red phase)

- [ ] 3.4 Add `special_conditions_block` parameter to `build_system_prompt()`
  - Files: `orchestrator_service/main.py`
  - Depends on: 3.3
  - Acceptance:
    - Function signature gains `special_conditions_block: str = ""` (with default — backward-compatible)
    - Inside function: `if special_conditions_block: prompt_parts.append(special_conditions_block)` (or equivalent injection in the prompt string construction)
    - Injected after the insurance/derivation section, before the booking flow
    - Tests from 3.3 pass (green phase)

### `buffer_task.py` query extension

- [ ] 3.5 Extend `buffer_task.py` tenant query to fetch 8 new columns and call formatter
  - Files: `orchestrator_service/services/buffer_task.py`
  - Depends on: 3.4, 1.1
  - Acceptance:
    - Tenant SELECT query includes all 8 new column names
    - After tenant row fetch: build `treatment_name_map` via async query to `treatment_types` (wrapped in `try/except`)
    - Call `_format_special_conditions(dict(tenant_row), treatment_name_map=treatment_name_map)` wrapped in `try/except` (non-fatal)
    - Pass `special_conditions_block=special_conditions_block` to `build_system_prompt()`
    - JSONB columns defensively handled: if value is a string → `json.loads()` before passing to formatter
    - No existing parameters to `build_system_prompt()` are removed or renamed

### `triage_urgency` cross-reference

- [ ] 3.6 Write test for triage cross-reference prompt instruction
  - Files: `tests/test_clinic_special_conditions.py`
  - Depends on: 3.2
  - Test class: `TestTriageCrossReference`
  - Acceptance:
    - `test_triage_instruction_present_when_high_risk_configured`: call `_format_special_conditions` with a non-empty `high_risk_protocols` → output contains "triage_urgency" reference (the POST-TRIAGE instruction)
    - `test_triage_instruction_absent_when_no_high_risk`: call with only pregnancy config → output does NOT contain the triage cross-reference
    - Tests FAIL before 3.7 (red phase)

- [ ] 3.7 Add triage cross-reference instruction to `_format_special_conditions()` high-risk block
  - Files: `orchestrator_service/main.py`
  - Depends on: 3.6
  - Acceptance:
    - When `high_risk_protocols` is non-empty, formatter appends:
      ```
      INSTRUCCIÓN POST-TRIAGE: Si triage_urgency identifica síntomas compatibles con una condición
      de alto riesgo listada, reestablecé la política de la clínica al comunicar el resultado.
      ```
    - Tests from 3.6 pass (green phase)

---

## Phase 4: Frontend (TDD order)

### GET tenant query extension

- [ ] 4.1 Write test for GET tenant endpoint including new fields
  - Files: `tests/test_clinic_special_conditions.py`
  - Depends on: 1.1, 2.3
  - Test class: `TestGetTenantNewFields`
  - Acceptance:
    - `test_get_tenants_includes_special_conditions_fields`: mock DB row with special condition fields → GET `/admin/tenants` response includes `accepts_pregnant_patients`, `min_pediatric_age_years`, `high_risk_protocols`, etc.
    - `test_get_tenants_defaults_when_null`: DB row with NULLs → response includes `null` for nullable fields, `true` for boolean defaults
    - Tests FAIL before 4.2 (red phase)

- [ ] 4.2 Extend GET `/admin/tenants` query to include 8 new columns
  - Files: `orchestrator_service/admin_routes.py`
  - Depends on: 4.1, 1.1
  - Acceptance:
    - The SELECT query on line ~2593 is extended to include all 8 new columns
    - JSONB columns (`high_risk_protocols`, `pregnancy_restricted_treatments`) are returned as parsed objects (not raw strings) — apply `json.loads` defensively consistent with other JSONB fields
    - Tests from 4.1 pass (green phase)

### Frontend — form state and UI

- [ ] 4.3 Extend `formData` TypeScript state in `ClinicsView.tsx`
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 4.2
  - Acceptance:
    - The `formData` state interface (or the `useState` initial value) gains all 8 new fields with correct TypeScript types
    - Initial values: `accepts_pregnant_patients: true`, `pregnancy_restricted_treatments: []`, `pregnancy_notes: ""`, `accepts_pediatric: true`, `min_pediatric_age_years: null`, `pediatric_notes: ""`, `high_risk_protocols: {}`, `requires_anamnesis_before_booking: false`
    - `handleEdit` (or equivalent populate-form function) maps the 8 new fields from the API response into `formData`
    - `handleSubmit` includes all 8 new fields in the PUT request body

- [ ] 4.4 Implement Pregnancy sub-block UI
  - Files: `frontend_react/src/views/ClinicsView.tsx`, `frontend_react/src/locales/es.json`, `en.json`, `fr.json`
  - Depends on: 4.3, 4.8 (i18n keys must exist)
  - Acceptance:
    - Section header uses `t('clinics.special_conditions_section')` key
    - Legal disclaimer rendered in amber-toned alert box
    - Checkbox for `accepts_pregnant_patients` with label `t('clinics.accepts_pregnant')`
    - Text input for `pregnancy_restricted_treatments` (comma-separated, parses to `string[]`)
    - Textarea for `pregnancy_notes` with `t('clinics.pregnancy_notes_help')` caption
    - All inputs use dark mode classes: `bg-white/[0.04] border border-white/[0.08] text-white`
    - `onChange` handlers update `formData` state correctly

- [ ] 4.5 Implement Pediatric sub-block UI
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 4.3, 4.8
  - Acceptance:
    - Checkbox for `accepts_pediatric`
    - Number input for `min_pediatric_age_years` (`min="0"`, stores `null` when empty)
    - Textarea for `pediatric_notes`
    - All dark mode styling applied

- [ ] 4.6 Implement High-Risk Protocols dynamic card editor
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 4.3, 4.8
  - Acceptance:
    - Renders one card per condition key in `formData.high_risk_protocols`
    - Each card shows: text input for condition name, checkbox for `requires_medical_clearance`, checkbox for `requires_pre_appointment_call`, text input for `restricted_treatments` (comma-separated), textarea for `notes`
    - "Agregar condición" button appends a new blank card entry
    - Trash/remove button on each card removes that condition from the map
    - `formData.high_risk_protocols` is always kept as a valid JavaScript object (serialization happens at submit)
    - On submit, the object is passed to the API as a nested JSON object (not a string)
    - Dark mode styling applied throughout

- [ ] 4.7 Implement Anamnesis Gate toggle
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 4.3, 4.8
  - Acceptance:
    - Checkbox / toggle for `requires_anamnesis_before_booking`
    - Help text using `t('clinics.requires_anamnesis_help')`
    - Visually separated as its own sub-section within the special conditions block

- [ ] 4.8 Add i18n keys to all 3 locale files
  - Files: `frontend_react/src/locales/es.json`, `en.json`, `fr.json`
  - Depends on: none (can be done before or parallel to UI tasks)
  - Acceptance:
    - All 25 keys from REQ-8 added to each of the 3 locale files
    - Keys nested under the `clinics` namespace (consistent with existing `clinics.*` keys)
    - Spanish values match REQ-8 table exactly
    - English and French values provided (see REQ-8)
    - `npm run lint` (frontend) passes after changes

---

## Phase 5: Scenario Verification + Guardrail Tests

- [ ] 5.1 Scenario test SC-1: Pregnant patient + restricted treatment
  - Files: `tests/test_clinic_special_conditions.py`
  - Depends on: Phase 3 complete
  - Test class: `TestAcceptanceScenarios`
  - Acceptance:
    - `test_sc1_pregnant_restricted_treatment`: build prompt with `accepts_pregnant_patients=True`, `pregnancy_restricted_treatments=["xray_panoramic"]`, `pregnancy_notes="Se pospone post primer trimestre"` → prompt contains the restriction text and the notes verbatim
    - Verify prompt DOES NOT contain "peligroso" or "contraindicado médicamente"
    - Verify prompt includes instruction to offer consultation

- [ ] 5.2 Scenario test SC-2: Pediatric minimum age
  - Depends on: Phase 3 complete
  - Acceptance:
    - `test_sc2_min_age_6`: `min_pediatric_age_years=6` → prompt contains "desde los 6 años"
    - `test_sc2_no_pediatric`: `accepts_pediatric=False` → prompt contains "no se atienden pacientes pediátricos"
    - Both tests verify absence of generic child-care disclaimers

- [ ] 5.3 Scenario test SC-3: Diabetic + restricted extraction
  - Depends on: Phase 3 complete
  - Acceptance:
    - `test_sc3_diabetes_clearance`: `high_risk_protocols={"diabetes": {"requires_medical_clearance": True, "notes": "Pedimos HbA1c reciente"}}` → prompt contains "diabetes", "clearance médico", "Pedimos HbA1c reciente"
    - Verify prompt DOES NOT say "la diabetes impide el tratamiento" or equivalent

- [ ] 5.4 Scenario test SC-4: Anticoagulated patient
  - Depends on: Phase 3 complete
  - Acceptance:
    - `test_sc4_anticoagulants_pre_call`: `high_risk_protocols={"anticoagulants": {"requires_medical_clearance": True, "requires_pre_appointment_call": True, "notes": "Requiere autorización del hematólogo"}}` → prompt contains "llamada del equipo antes del turno" and "Requiere autorización del hematólogo"
    - Verify no medication advice language

- [ ] 5.5 Scenario test SC-5: Immunosuppressed + anamnesis gate
  - Depends on: Phase 3 complete
  - Acceptance:
    - `test_sc5_anamnesis_gate_active`: `requires_anamnesis_before_booking=True` with high-risk config → prompt contains "ANAMNESIS GATE (ACTIVO)" and the EXCEPCIÓN clause for emergency bypass
    - `test_sc5_gate_inactive_by_default`: `requires_anamnesis_before_booking=False` → "ANAMNESIS GATE" NOT in prompt

- [ ] 5.6 Anti-medical-advice guardrail tests
  - Files: `tests/test_clinic_special_conditions.py`
  - Depends on: 3.2
  - Test class: `TestAntiMedicalAdviceGuardrails`
  - Acceptance:
    - For each of the following inputs, `_format_special_conditions()` output MUST NOT contain any of the prohibited phrases:
      - Prohibited: `"es peligroso"`, `"no debes"`, `"contraindicado médicamente"`, `"está prohibido para"`, `"no podés"`, `"imposible para pacientes con"`, `"no apto"`, `"apto no"`
    - Test inputs that exercise all 4 blocks (pregnancy restricted, pediatric minimum, high-risk clearance, anamnesis gate)
    - This test MUST pass even when `pregnancy_notes` or `notes` fields contain text the formatter includes verbatim — the formatter's OWN generated language must not contain the prohibited phrases (the clinic-provided notes can say anything — they're passed through verbatim)

- [ ] 5.7 Migration round-trip test
  - Files: migration `036`
  - Depends on: 1.1
  - Acceptance:
    - `alembic upgrade head` runs without error
    - `alembic downgrade -1` removes all 8 columns cleanly
    - Second `alembic upgrade head` re-adds them without error
    - No existing `tenants` row data is lost in either direction

---

## File Summary

| File | Tasks | Change type |
|------|-------|-------------|
| `orchestrator_service/alembic/versions/036_add_clinic_special_conditions.py` | 1.1 | NEW FILE |
| `orchestrator_service/models.py` | 1.2 | MODIFY — 8 new columns on Tenant |
| `orchestrator_service/admin_routes.py` | 2.1, 2.3, 4.2 | MODIFY — HighRiskProtocol model + endpoint extension + GET query |
| `tests/test_clinic_special_conditions.py` | 2.2, 3.1, 3.3, 3.6, 4.1, 5.1-5.6 | NEW FILE |
| `orchestrator_service/main.py` | 3.2, 3.4, 3.7 | MODIFY — new formatter + build_system_prompt param |
| `orchestrator_service/services/buffer_task.py` | 3.5 | MODIFY — tenant query + formatter call |
| `frontend_react/src/views/ClinicsView.tsx` | 4.3-4.7 | MODIFY — form state + 4 UI sub-blocks |
| `frontend_react/src/locales/es.json` | 4.8 | MODIFY — 25 new keys |
| `frontend_react/src/locales/en.json` | 4.8 | MODIFY — 25 new keys |
| `frontend_react/src/locales/fr.json` | 4.8 | MODIFY — 25 new keys |

---

## Notes for Implementer

1. **TDD is mandatory**: create `tests/test_clinic_special_conditions.py` before any implementation. Run `pytest` to confirm red phase, then implement, then confirm green phase.

2. **JSONB defensive handling**: both `high_risk_protocols` and `pregnancy_restricted_treatments` may be returned from asyncpg as a Python string (not a dict/list). Apply `json.loads()` defensively inside `_format_special_conditions()` and in the buffer_task query. Pattern already established for `working_hours`.

3. **`_format_special_conditions()` is non-fatal**: all calls in `buffer_task.py` must be wrapped in `try/except Exception: pass`. A misconfigured tenant must not break the AI pipeline for any patient.

4. **Legal disclaimer in UI**: the amber-toned disclaimer text (from `t('clinics.special_conditions_disclaimer')`) MUST be visible immediately when the section is expanded. It is not optional and must not be hidden behind another toggle.

5. **High-risk protocols card editor**: the condition `condition` text input is a plain string key (lowercase, no spaces recommended but not enforced). Examples: `"diabetes"`, `"anticoagulants"`, `"renal_failure"`. The API receives a JSON object with condition names as keys.

6. **Backward compatibility**: all new `build_system_prompt()` parameters have defaults. All new `buffer_task.py` additions are wrapped in `try/except`. Existing tenants with NULLs in all 8 columns get `_format_special_conditions` returning `""` — zero prompt change.

7. **i18n task 4.8 can be done in parallel with task 4.4**: the locale files don't depend on the UI components, but the components fail to compile if keys are missing. Complete 4.8 first or simultaneously.

8. **Migration idempotency**: follow the pattern from `021_telegram_authorized_users.py` — use `inspector.get_columns()` to check existence before each `add_column`. This prevents errors if the migration is run on a DB that already has some columns from a partial run.
