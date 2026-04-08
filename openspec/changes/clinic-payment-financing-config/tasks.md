# Tasks: Clinic Payment & Financing Configuration

**Change**: `clinic-payment-financing-config`
**Status**: READY
**Date**: 2026-04-07
**TDD**: Strict — test tasks come BEFORE implementation tasks within each phase.
**Total tasks**: 28

---

## Dependency Graph

```
1.1 (migration) → 1.2 (model update)
1.2 → 2.1 (endpoint test) → 2.2 (endpoint impl)
2.2 → 3.1 (formatter test) → 3.2 (formatter impl) → 3.3 (build_system_prompt integration)
3.3 → 3.4 (buffer_task caller update)
1.2 + 2.2 → 4.1 (frontend formData + state) → 4.2 (payment methods UI) → 4.3 (financing UI)
4.3 → 4.4 (i18n keys) → 4.5 (manual QA checklist)
3.4 + 4.5 → 5.1 → 5.2 → 5.3 → 5.4 → 5.5 (e2e scenario tests)
All Phase 5 → 5.6 (backward compat regression)
```

---

## Phase 1: Infrastructure (DB + Model)

### Task 1.1 — Alembic migration 035

- [ ] Create `orchestrator_service/alembic/versions/035_add_payment_financing_config.py`
  - `revision = "035"`, `down_revision = "034"`
  - `upgrade()` adds all 8 columns with idempotency guards (check `inspector.get_columns("tenants")` before each `add_column`)
  - `upgrade()` creates CHECK constraints `ck_tenants_max_installments_range` and `ck_tenants_cash_discount_range`
  - `downgrade()` drops CHECK constraints first (with try/except), then drops all 8 columns in reverse order
  - Acceptance test: run `alembic upgrade 035` on a fresh DB, verify all 8 columns exist with correct types; run `alembic downgrade 034`, verify all 8 columns are gone
  - Files: `orchestrator_service/alembic/versions/035_add_payment_financing_config.py`
  - Depends on: none

### Task 1.2 — SQLAlchemy Tenant model update

- [ ] Add 8 new columns to `Tenant` class in `orchestrator_service/models.py`
  - Insert after `bank_holder_name = Column(Text)`, before `derivation_email`
  - Use `Numeric(5, 2)` for `cash_discount_percent` (import `Numeric` already present)
  - Use `JSONB` for `payment_methods` (already imported)
  - Use `text("false")` / `text("true")` for boolean server_defaults (already used pattern)
  - Acceptance: `from models import Tenant` imports without error; `Tenant.__table__.columns` includes all 8 new columns
  - Files: `orchestrator_service/models.py`
  - Depends on: 1.1

---

## Phase 2: Backend Endpoint (TDD order)

### Task 2.1 — Write tests for update_tenant() new fields

- [ ] Create test file `tests/test_payment_financing_endpoint.py`
  - Test class: `TestUpdateTenantPaymentFields`
  - `test_valid_payment_methods_accepted` — PUT with `{"payment_methods": ["cash","credit_card"]}` → returns 200, DB row has correct value
  - `test_invalid_payment_method_rejected` — PUT with `{"payment_methods": ["bitcoin_illegal"]}` → returns 422 with "invalid values" in detail
  - `test_max_installments_valid_range` — PUT with `{"max_installments": 12}` → 200
  - `test_max_installments_out_of_range_high` — PUT with `{"max_installments": 25}` → 422 "between 1 and 24"
  - `test_max_installments_out_of_range_low` — PUT with `{"max_installments": 0}` → 422 "between 1 and 24"
  - `test_cash_discount_valid` — PUT with `{"cash_discount_percent": 10.5}` → 200
  - `test_cash_discount_over_100` — PUT with `{"cash_discount_percent": 101}` → 422 "between 0 and 100"
  - `test_cash_discount_negative` — PUT with `{"cash_discount_percent": -1}` → 422 "between 0 and 100"
  - `test_financing_available_bool_coercion` — PUT with `{"financing_available": "true"}` → stored as Python True
  - `test_omitted_fields_not_overwritten` — PUT with only `{"clinic_name": "X"}` → all payment fields unchanged in DB
  - `test_empty_payment_methods_stores_null` — PUT with `{"payment_methods": []}` → DB has NULL not `[]`
  - `test_financing_notes_empty_string_stores_null` — PUT with `{"financing_notes": ""}` → DB has NULL
  - Files: `tests/test_payment_financing_endpoint.py`
  - Depends on: 1.2

### Task 2.2 — Implement update_tenant() new fields

- [ ] Add payment/financing field handling blocks to `update_tenant()` in `orchestrator_service/admin_routes.py`
  - Add `ALLOWED_PAYMENT_METHODS` set constant (module-level or inside function)
  - Add 8 field blocks per design.md (presence-check pattern, same as existing fields)
  - All 12 tests from 2.1 MUST pass
  - Files: `orchestrator_service/admin_routes.py`
  - Depends on: 2.1

### Task 2.3 — Extend GET /admin/tenants SELECT

- [ ] Update the SELECT query in the tenant list endpoint to include all 8 new columns
  - Find the query at ~line 2593 in `admin_routes.py`
  - Append: `payment_methods, financing_available, max_installments, installments_interest_free, financing_provider, financing_notes, cash_discount_percent, accepts_crypto`
  - Acceptance: `GET /admin/tenants` response includes all 8 fields (can be NULL for unconfigured tenants)
  - Files: `orchestrator_service/admin_routes.py`
  - Depends on: 2.2

---

## Phase 3: Prompt Formatter (TDD order)

### Task 3.1 — Write tests for _format_payment_options()

- [ ] Create test file `tests/test_payment_formatter.py`
  - Test class: `TestFormatPaymentOptions`
  - `test_empty_config_returns_empty_string` — all args default → returns `""`
  - `test_none_payment_methods_returns_empty_string` — `payment_methods=None` → returns `""`
  - `test_payment_methods_emits_labels` — `payment_methods=["cash","credit_card"]` → output contains "Efectivo" and "Tarjeta de crédito"
  - `test_unknown_method_token_falls_back_to_token` — `payment_methods=["other_new"]` → contains "other_new" in output (no crash)
  - `test_financing_block_emitted_when_true` — `financing_available=True, max_installments=6, installments_interest_free=True, financing_provider="MP"` → output contains "6 cuotas sin interés" and "MP"
  - `test_financing_block_not_emitted_when_false` — `financing_available=False, max_installments=6` → "cuotas" NOT in output
  - `test_installments_with_interest` — `financing_available=True, max_installments=3, installments_interest_free=False` → output contains "con interés"
  - `test_cash_discount_emitted` — `cash_discount_percent=10.0` → output contains "10%" and "efectivo"
  - `test_cash_discount_zero_not_emitted` — `cash_discount_percent=0.0` → no discount line
  - `test_cash_discount_none_not_emitted` — `cash_discount_percent=None` → no discount line
  - `test_accepts_crypto_emitted` — `accepts_crypto=True` → output contains "criptomonedas"
  - `test_accepts_crypto_false_not_emitted` — `accepts_crypto=False` → "criptomonedas" NOT in output
  - `test_disclaimer_present_when_any_field_set` — any truthy field → output contains "Información orientativa"
  - `test_disclaimer_absent_when_empty` — all defaults → disclaimer NOT in output
  - `test_financing_notes_included` — `financing_available=True, financing_notes="Solo Visa"` → output contains "Solo Visa"
  - `test_full_config_sample_output` — maximal config → output matches expected snapshot (see design.md sample)
  - `test_integer_discount_no_decimal_point` — `cash_discount_percent=10.0` → output contains "10%" not "10.0%"
  - Files: `tests/test_payment_formatter.py`
  - Depends on: none (pure function, no DB)

### Task 3.2 — Implement _format_payment_options()

- [ ] Add `_PAYMENT_METHOD_LABELS` dict and `_format_payment_options()` function to `orchestrator_service/main.py`
  - Place near other `_format_*` helpers (before `build_system_prompt()`)
  - All 17 tests from 3.1 MUST pass
  - Files: `orchestrator_service/main.py`
  - Depends on: 3.1

### Task 3.3 — Integrate into build_system_prompt()

- [ ] Add 8 new keyword parameters to `build_system_prompt()` signature (all with backward-compat defaults)
  - Call `_format_payment_options(...)` inside the function body
  - Inject `payment_section` output immediately after `bank_section` in the return string
  - Acceptance: existing unit tests for `build_system_prompt()` still pass; new integration test shows payment block appears in output when at least one field is set
  - Add `test_build_system_prompt_with_payment_section` to `tests/test_payment_formatter.py`
  - Files: `orchestrator_service/main.py`
  - Depends on: 3.2

### Task 3.4 — Update buffer_task.py caller

- [ ] Extend the tenant SELECT in `buffer_task.py` to fetch all 8 new columns
  - Pass the 8 new fields from the tenant row to `build_system_prompt()`
  - Handle asyncpg JSONB-as-string: `payment_methods = json.loads(tenant["payment_methods"])` if string, else use as-is (same defensive pattern as `working_hours`)
  - Acceptance: start the orchestrator locally; verify no KeyError or AttributeError on message processing for a tenant without payment config
  - Files: `orchestrator_service/buffer_task.py`
  - Depends on: 3.3

---

## Phase 4: Frontend (QA checklist, minimal unit tests)

### Task 4.1 — Extend formData and state

- [ ] Add 8 new fields to `formData` initial state in `ClinicsView.tsx`
  - Add to both the initial state object and the `useEffect` that populates form from `editingClinica`
  - Add `paymentSectionExpanded` boolean state (default: `false`)
  - Add `togglePaymentMethod(method: string)` helper function
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 2.3

### Task 4.2 — Implement payment methods checkbox UI

- [ ] Add the "Pagos y Financiación" collapsible section header and the payment methods multi-checkbox grid
  - Insert after the `## Datos Bancarios` section (after line ~996)
  - Header uses `ChevronDown` icon (already imported), rotates when expanded
  - Checkbox grid is 2-column (grid-cols-2), one checkbox per allowed method token
  - All labels from design.md METHOD_LABELS
  - Uses `t('clinics.payment_section')` etc. for all visible strings
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 4.1

### Task 4.3 — Implement financing sub-fields

- [ ] Add conditional financing block inside the expanded payment section
  - `financing_available` toggle checkbox
  - When `financing_available=true`, show: `max_installments` (number), `installments_interest_free` (checkbox), `financing_provider` (text), `financing_notes` (textarea 2 rows)
  - Conditional rendering via `{formData.financing_available && (...)}`
  - Add `cash_discount_percent` (number, step=0.01, min=0, max=100) — always visible (not conditional)
  - Add `accepts_crypto` toggle checkbox — always visible
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 4.2

### Task 4.4 — i18n keys

- [ ] Add all 14 i18n keys from REQ-5 to all 3 locale files
  - `frontend_react/src/locales/es.json`
  - `frontend_react/src/locales/en.json`
  - `frontend_react/src/locales/fr.json`
  - No hardcoded Spanish strings remain in the new UI section
  - Files: `frontend_react/src/locales/es.json`, `en.json`, `fr.json`
  - Depends on: 4.3

### Task 4.5 — Include new fields in handleSubmit

- [ ] Extend `handleSubmit` payload to include all 8 new fields with correct type coercion
  - `payment_methods`: array (empty array → send `[]`, backend stores as NULL)
  - `max_installments` / `cash_discount_percent`: coerce to Number or null
  - `financing_available` / `installments_interest_free` / `accepts_crypto`: bool
  - `financing_provider` / `financing_notes`: string or null
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 4.4

### Task 4.6 — Manual QA checklist

The following scenarios MUST be verified manually in the browser before marking Phase 4 complete:

- [ ] QA-4A: Create a new clinic with no payment config → submit succeeds, no console errors, all 8 fields absent from payload does not break API
- [ ] QA-4B: Edit an existing clinic → payment section shows collapsed by default, click expands it
- [ ] QA-4C: Check "Tarjeta de crédito" + "Mercado Pago" → save → reopen clinic → checkboxes are pre-checked
- [ ] QA-4D: Toggle `financing_available` on → sub-fields appear; toggle off → sub-fields disappear
- [ ] QA-4E: Enter `max_installments=25` → submit → frontend shows error OR backend returns 422 (either acceptable)
- [ ] QA-4F: Enter `cash_discount_percent=150` → submit → backend returns 422
- [ ] QA-4G: Switch language to English → all payment section labels appear in English
- [ ] QA-4H: Dark mode check — all inputs, checkboxes, labels match the dark palette from design system

---

## Phase 5: E2E Scenario Verification

Each task below verifies one of the 5 patient query scenarios from REQ-4.

### Task 5.1 — Q1: Card acceptance

- [ ] Write test `tests/test_payment_e2e_scenarios.py::TestPaymentScenarios::test_q1_card_acceptance`
  - Mock tenant with `payment_methods=["credit_card","debit_card"]`
  - Build system prompt → verify "tarjeta de crédito" appears in prompt
  - Simulate agent conversation: patient message "¿aceptan tarjeta?" → assert response contains "tarjeta" and does NOT contain "no tengo información"
  - Depends on: 3.3

### Task 5.2 — Q2: Installments

- [ ] Write test `test_q2_installments`
  - Mock tenant with `financing_available=True, max_installments=6, installments_interest_free=True, financing_provider="Mercado Pago"`
  - Build system prompt → verify "6 cuotas sin interés" and "Mercado Pago" appear in prompt
  - Depends on: 3.3

### Task 5.3 — Q3: Cash discount

- [ ] Write test `test_q3_cash_discount`
  - Mock tenant with `cash_discount_percent=10.0`
  - Build system prompt → verify "10%" and "efectivo" appear in prompt
  - Depends on: 3.3

### Task 5.4 — Q4: Mercado Pago

- [ ] Write test `test_q4_mercado_pago`
  - Mock tenant with `payment_methods=["transfer","mercado_pago"]`
  - Build system prompt → verify "Mercado Pago" in prompt
  - Depends on: 3.3

### Task 5.5 — Q5: Crypto not accepted (no section)

- [ ] Write test `test_q5_crypto_not_accepted`
  - Mock tenant with all payment fields NULL/False (default config, no crypto)
  - Build system prompt → verify "MEDIOS DE PAGO" section is NOT in prompt
  - This confirms the agent has no payment section to affirm crypto acceptance
  - Depends on: 3.3

### Task 5.6 — Backward compatibility regression

- [ ] Write test `test_backward_compat_no_payment_fields`
  - Call `build_system_prompt()` with ALL payment parameters omitted (no kwargs)
  - Assert: the returned prompt does NOT contain "MEDIOS DE PAGO"
  - Assert: the returned prompt is identical to the pre-change baseline for a standard tenant config
  - This guarantees that existing tenants (Dra. Laura Delgado) see zero prompt change until they configure payment fields
  - Files: `tests/test_payment_e2e_scenarios.py`
  - Depends on: 3.3
