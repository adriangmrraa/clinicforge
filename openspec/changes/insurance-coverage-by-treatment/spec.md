# SPEC: Insurance Coverage by Treatment

**Change**: `insurance-coverage-by-treatment`
**Project**: ClinicForge
**Scope**: `tenant_insurance_providers` data model, backend CRUD, AI prompt formatter, frontend Tab 2 modal
**Out of scope**: Nova, billing, public forms, third-party insurance APIs

---

## RFC Keywords

Throughout this document: MUST = mandatory, SHALL = equivalent to MUST, SHOULD = recommended, MAY = optional.

---

## REQ-1: Pydantic Schema for `coverage_by_treatment`

### REQ-1.1 — `TreatmentCoverage` model

A new Pydantic model `TreatmentCoverage` MUST be defined in `admin_routes.py` with the following fields:

| Field | Type | Required | Constraints |
|---|---|---|---|
| `covered` | `bool` | MUST | — |
| `copay_percent` | `float` | MUST | 0.0 ≤ value ≤ 100.0 |
| `requires_pre_authorization` | `bool` | MUST | — |
| `pre_auth_leadtime_days` | `int` | MUST | ≥ 0 |
| `waiting_period_days` | `int` | MUST | ≥ 0 |
| `max_annual_coverage` | `Optional[float]` | SHOULD | NULL or > 0 |
| `notes` | `str` | MUST | max 500 chars; empty string is valid |

All fields MUST have sensible defaults so that a minimal `{"covered": true}` entry is valid:
- `copay_percent`: 0.0
- `requires_pre_authorization`: false
- `pre_auth_leadtime_days`: 0
- `waiting_period_days`: 0
- `max_annual_coverage`: null
- `notes`: ""

### REQ-1.2 — `coverage_by_treatment` dict schema

`InsuranceProviderCreate` and `InsuranceProviderUpdate` MUST replace `restrictions: Optional[str]` with:

```python
coverage_by_treatment: Optional[dict[str, TreatmentCoverage]] = None
```

Keys of the dict MUST be treatment codes (strings). The endpoint MUST validate that each key is a non-empty string. The endpoint SHOULD (but is not required to) validate that each key exists in `treatment_types` for the tenant — a WARNING log is acceptable instead of a hard 422 for unknown codes, to allow forward-compatibility.

### REQ-1.3 — Validation constraints

- `copay_percent` outside [0, 100] MUST raise HTTP 422 with message: "copay_percent debe estar entre 0 y 100"
- `pre_auth_leadtime_days` < 0 MUST raise HTTP 422 with message: "pre_auth_leadtime_days no puede ser negativo"
- `waiting_period_days` < 0 MUST raise HTTP 422 with message: "waiting_period_days no puede ser negativo"
- `max_annual_coverage` present and ≤ 0 MUST raise HTTP 422 with message: "max_annual_coverage debe ser positivo"
- `notes` longer than 500 chars MUST raise HTTP 422

### REQ-1.4 — New top-level fields

`InsuranceProviderCreate` and `InsuranceProviderUpdate` MUST add:

```python
is_prepaid: bool = False
employee_discount_percent: Optional[float] = None  # 0.0-100.0
default_copay_percent: Optional[float] = None       # 0.0-100.0
```

`employee_discount_percent` and `default_copay_percent`, when present, MUST be in [0, 100].

---

## REQ-2: CRUD Endpoints Accept New Shape

### REQ-2.1 — GET `/admin/insurance-providers`

The response for each provider MUST include:
- All existing fields (id, provider_name, status, external_target, requires_copay, copay_notes, ai_response_template, sort_order, is_active, created_at, updated_at)
- `coverage_by_treatment` (JSONB, parsed to dict — never returned as raw string)
- `is_prepaid` (bool)
- `employee_discount_percent` (float or null)
- `default_copay_percent` (float or null)
- The deprecated `restrictions` column MUST NOT appear in the response after migration

The endpoint MUST apply `json.loads()` to `coverage_by_treatment` if asyncpg returns it as a string (defensive pattern consistent with `tenants.working_hours`).

### REQ-2.2 — POST `/admin/insurance-providers`

MUST accept `coverage_by_treatment` as a dict and serialize to JSONB on INSERT. If `coverage_by_treatment` is null, store `'{}'::jsonb`.

MUST accept `is_prepaid`, `employee_discount_percent`, `default_copay_percent`.

The existing `restrictions`-required validation for `status='restricted'` MUST be removed. `status='restricted'` now means the provider is covered with per-treatment restrictions defined in `coverage_by_treatment`.

### REQ-2.3 — PUT `/admin/insurance-providers/{id}`

Same as POST. Full replacement of `coverage_by_treatment` on update (not merge/patch).

### REQ-2.4 — Tenant isolation

Every query MUST include `WHERE tenant_id = $x`. The `tenant_id` MUST be resolved from the authenticated user via `Depends(get_resolved_tenant_id)`, never from the request body or URL params.

---

## REQ-3: `_format_insurance_providers` MUST emit per-treatment rules

### REQ-3.1 — Enriched prompt block

When a provider has `coverage_by_treatment` with at least one entry, `_format_insurance_providers()` MUST emit:

```
{provider_name}{prepaga_flag} — coseguro por defecto: {default_copay_percent}%
  Tratamientos cubiertos:
  • {treatment_display_name} ({code}): cubierto, coseguro {copay_percent}%{preauth_clause}{waiting_clause}{notes_clause}
  Tratamientos NO cubiertos:
  • {treatment_display_name} ({code}){notes_clause}
```

Where:
- `{prepaga_flag}` = " (prepaga)" if `is_prepaid` else ""
- `{preauth_clause}` = ", requiere preautorización ({N} días hábiles)" if `requires_pre_authorization` else ""
- `{waiting_clause}` = ", carencia {N} días" if `waiting_period_days > 0` else ""
- `{notes_clause}` = ". Nota: {notes}" if `notes` is non-empty else ""

### REQ-3.2 — Fallback behavior

When `coverage_by_treatment` is empty dict (`{}`), the formatter MUST fall back to the current generic block:

```
{provider_name}: trabajamos con esta obra social. {copay_notes or "coseguro estándar"}
```

This preserves backwards compatibility for providers migrated from legacy data with empty coverage.

### REQ-3.3 — Output cap

The formatter MUST NOT emit more than 10 treatment entries per provider. If a provider has > 10 treatment entries, emit the first 10 (sorted: covered first, then by treatment code) and append: "... y otros tratamientos — consultá con la clínica".

### REQ-3.4 — Treatment display names

The formatter receives provider dicts from the prompt builder (`build_system_prompt`). The prompt builder MUST pass treatment display names (from `treatment_types.patient_display_name or name`) so the formatter can show human-readable names instead of codes.

---

## REQ-4: Agent MUST answer 6 patient queries

The AI agent (via the system prompt section emitted by `_format_insurance_providers`) MUST be capable of answering the following scenarios correctly:

### Scenario A — Copay percentage

**Given** OSDE has `coverage_by_treatment["IMPT"] = {covered: true, copay_percent: 30}`
**When** patient asks "¿OSDE cubre el implante? ¿Cuánto tengo que pagar yo?"
**Then** agent responds with "con OSDE el implante tiene un coseguro del 30%" (or equivalent), does NOT say "no tengo información sobre cobertura específica"

### Scenario B — Pre-authorization

**Given** Swiss Medical has `coverage_by_treatment["EXTRAC"] = {covered: true, requires_pre_authorization: true, pre_auth_leadtime_days: 3}`
**When** patient asks "¿Necesito autorización para la extracción con Swiss Medical?"
**Then** agent responds with "sí, se requiere preautorización con un plazo de 3 días hábiles"

### Scenario C — Waiting period

**Given** OSDE has `coverage_by_treatment["IMPT"] = {waiting_period_days: 180}`
**When** patient asks "¿Cuánto tengo que esperar para que OSDE me cubra el implante?"
**Then** agent responds with "la cobertura de implantes con OSDE tiene una carencia de 180 días"

### Scenario D — Not covered

**Given** Swiss Medical has `coverage_by_treatment["BLAN"] = {covered: false}`
**When** patient asks "¿Swiss Medical cubre el blanqueamiento?"
**Then** agent responds with a clear "ese tratamiento no está cubierto por Swiss Medical" and offers to book as a private patient

### Scenario E — Prepaga vs obra social distinction

**Given** Swiss Medical has `is_prepaid = true`
**When** patient asks "Swiss Medical es prepaga o obra social?"
**Then** agent responds correctly identifying it as prepaga

### Scenario F — Default copay fallback

**Given** OSDE has `default_copay_percent = 20` and no entry for treatment "LIMPZ" in `coverage_by_treatment`
**When** patient asks "¿Cuánto coseguro pago con OSDE para la limpieza?"
**Then** agent responds "OSDE tiene un coseguro general del 20%; para ese tratamiento específico podés consultarnos directamente"

---

## REQ-5: Backwards-Compatible Migration of Legacy Data

### REQ-5.1 — Automatic migration in `upgrade()`

The Alembic migration `034_insurance_coverage_by_treatment.py` MUST:

1. Add columns `coverage_by_treatment JSONB DEFAULT '{}'`, `is_prepaid BOOLEAN DEFAULT FALSE`, `employee_discount_percent DECIMAL(5,2) NULL`, `default_copay_percent DECIMAL(5,2) NULL`
2. For each existing row:
   - If `restrictions` is a valid JSON array of strings → migrate each element `code` to `{code: {"covered": true, "copay_percent": 0, "requires_pre_authorization": false, "pre_auth_leadtime_days": 0, "waiting_period_days": 0, "max_annual_coverage": null, "notes": ""}}` and set `coverage_by_treatment` to that dict
   - If `restrictions` is NULL or empty string → set `coverage_by_treatment = '{}'::jsonb`
   - If `restrictions` is non-JSON text → set `coverage_by_treatment = '{}'::jsonb`, log a warning
3. Drop column `restrictions` after migration

### REQ-5.2 — Clean downgrade

`downgrade()` MUST:
1. Add back `restrictions TEXT NULL`
2. For each row: if `coverage_by_treatment` is non-empty, serialize covered=true treatment codes back to a JSON array string; else set NULL
3. Drop `coverage_by_treatment`, `is_prepaid`, `employee_discount_percent`, `default_copay_percent`

### REQ-5.3 — Zero data loss guarantee

The migration MUST be tested against a database that has:
- Rows with valid JSON array in `restrictions`
- Rows with NULL `restrictions`
- Rows with empty string `restrictions`

After `upgrade()` and `downgrade()`, the covered treatment codes in `restrictions` MUST be equivalent to the original set.

---

## REQ-6: UI MUST Validate Coverage JSON Before Save

### REQ-6.1 — Per-treatment coverage matrix

The frontend modal for insurance providers (Tab 2 in `ClinicsView`) MUST show a per-treatment coverage matrix when `status` is `accepted` or `restricted`.

The matrix MUST have:
- One row per active treatment type for the tenant (loaded from `GET /admin/treatment-types`)
- Columns: covered (toggle), copay % (number input 0–100), requires pre-auth (checkbox), waiting period days (number input ≥ 0), notes (text input)
- An "expand/collapse" affordance so the matrix is not overwhelming by default

### REQ-6.2 — Client-side validation

Before submitting the form, the frontend MUST validate:
- `copay_percent` values are between 0 and 100 (show inline error)
- `waiting_period_days` values are non-negative integers (show inline error)
- `notes` per treatment does not exceed 500 characters (show character count)

The submit button MUST be disabled while any validation error is active.

### REQ-6.3 — State shape

The frontend form state MUST use `coverage_by_treatment: Record<string, TreatmentCoverageEntry>` instead of the old `restrictions: string`. The `parseRestrictionsAsCodes()` helper MUST be replaced by `parseCoverageByTreatment()`.

### REQ-6.4 — New top-level fields

The modal MUST include fields for `is_prepaid` (checkbox), `default_copay_percent` (number input 0–100, optional), and `employee_discount_percent` (number input 0–100, optional).

---

## Acceptance Scenarios (Gherkin)

### AC-1: Create provider with structured coverage

```gherkin
Given a tenant has treatment types with codes ["CONS", "IMPT", "EXTRAC"]
When admin POSTs /admin/insurance-providers with:
  {
    "provider_name": "OSDE",
    "status": "accepted",
    "is_prepaid": false,
    "default_copay_percent": 20,
    "coverage_by_treatment": {
      "CONS": {"covered": true, "copay_percent": 0},
      "IMPT": {"covered": true, "copay_percent": 30, "waiting_period_days": 180}
    }
  }
Then the response status is 201
And the saved row has coverage_by_treatment as a JSONB dict
And the row has no restrictions column
```

### AC-2: GET returns parsed JSONB (not string)

```gherkin
Given OSDE exists with coverage_by_treatment JSONB
When admin GETs /admin/insurance-providers
Then coverage_by_treatment in the response is a dict, not a string
```

### AC-3: Validation rejects invalid copay_percent

```gherkin
Given any provider payload
When coverage_by_treatment contains {"IMPT": {"covered": true, "copay_percent": 150}}
Then response is HTTP 422 with detail containing "copay_percent debe estar entre 0 y 100"
```

### AC-4: Migration of legacy restrictions array

```gherkin
Given a row with restrictions = '["IMPT", "CONS"]' before migration
When alembic upgrade head runs
Then coverage_by_treatment = {"IMPT": {"covered": true, ...defaults}, "CONS": {"covered": true, ...defaults}}
And restrictions column no longer exists
```

### AC-5: Prompt formatter with coverage data

```gherkin
Given OSDE with coverage_by_treatment = {"IMPT": {"covered": true, "copay_percent": 30, "waiting_period_days": 180}}
When _format_insurance_providers([osde_dict]) is called
Then the output string contains "coseguro 30%"
And the output string contains "carencia 180 días"
```

### AC-6: Prompt formatter fallback for empty coverage

```gherkin
Given provider with coverage_by_treatment = {}
When _format_insurance_providers([provider_dict]) is called
Then the output string contains "coseguro estándar" or copay_notes value
And does NOT raise any exception
```

### AC-7: Frontend matrix validation blocks submit

```gherkin
Given the insurance modal is open
And user sets copay_percent to 150 for treatment IMPT
When user clicks Save
Then form does NOT submit
And an inline error "debe estar entre 0 y 100" is visible next to the IMPT row
```

### AC-8: Migration downgrade restores restrictions

```gherkin
Given migration 034 has run and coverage_by_treatment = {"IMPT": {"covered": true}}
When alembic downgrade -1 runs
Then restrictions column exists with value '["IMPT"]'
And coverage_by_treatment column no longer exists
```

---

## Dependencies

- REQ-5 (migration) MUST complete before REQ-1, REQ-2, REQ-3 can be fully tested end-to-end
- REQ-1 (Pydantic schema) MUST be implemented before REQ-2 (endpoints)
- REQ-3 (`_format_insurance_providers` rewrite) depends on the migration having added `coverage_by_treatment` to the DB
- REQ-6 (frontend) depends on REQ-2 (endpoints returning new shape)
- REQ-4 (agent scenarios) depends on REQ-3 (formatter emitting enriched prompt)

---

## Out of Scope (explicit)

- Nova behavioral changes
- New AI tool `check_insurance_coverage` (exists as planned but not in this change)
- Third-party insurance API lookup (ARCA, SSS)
- Billing/invoice impact of copay changes
- Patient-facing insurance query UI
