# SDD Proposal: Insurance Coverage by Treatment

**Change**: `insurance-coverage-by-treatment`
**Status**: PROPOSED
**Date**: 2026-04-07
**Author**: SDD Orchestrator

---

## 1. Intent

### Problem Statement

The current `tenant_insurance_providers` model stores coverage information as a flat `restrictions TEXT` column containing a JSON array of treatment codes. This design can only answer ONE question: "does this insurance cover treatment X at all?" (allowed/denied binary).

Real-world patient queries the AI agent currently CANNOT answer:

| Patient query | Can agent answer? | Reason |
|---|---|---|
| "Cubre el implante OSDE?" | Partial | Only knows if "IMPT" is in the array, not how much |
| "Cuánto sale el coseguro de la consulta?" | No | `copay_notes` is a free-text blob, not structured |
| "Necesito autorización previa para la extracción?" | No | No field for pre-authorization |
| "Cuánto tiempo tengo que esperar para usar la cobertura?" | No | No waiting period field |
| "OSDE es una prepaga o una obra social?" | No | No `is_prepaid` flag |
| "Tiene límite de cobertura anual?" | No | No max annual coverage field |

Additionally, the current `restrictions` array is semantically ambiguous: it is used for BOTH "with restrictions" (`status = 'restricted'`) AND "accepted with limited coverage" providers, creating confusion in the prompt formatter.

### Why This Matters

- **Conversion loss**: Patients who ask about insurance coverage and get "no tengo información" are likely to abandon the booking.
- **AI accuracy**: `_format_insurance_providers()` cannot emit per-treatment copay percentages because the data is not structured.
- **Clinical reality**: In Argentina, obras sociales and prepagas have deeply differentiated coverage per procedure. A single `copay_notes` blob per provider is insufficient.
- **Multi-tenant readiness**: Each clinic in ClinicForge may have different coverage agreements for the same insurance provider. The new model must be tenant-scoped and treatment-scoped simultaneously.

---

## 2. Scope

### In Scope

| Area | Files | What Changes |
|---|---|---|
| Data model | `orchestrator_service/models.py` | Replace `restrictions TEXT` with `coverage_by_treatment JSONB`; add 3 new top-level columns |
| Alembic migration | `orchestrator_service/alembic/versions/034_insurance_coverage_by_treatment.py` | `upgrade()` + `downgrade()` + data migration of existing `restrictions` arrays |
| Backend Pydantic schemas | `orchestrator_service/admin_routes.py` | `InsuranceProviderCreate` / `InsuranceProviderUpdate` accept new shape; validation updated |
| Backend CRUD endpoints | `orchestrator_service/admin_routes.py` | `GET/POST/PUT /admin/insurance-providers` emit and consume `coverage_by_treatment` |
| AI prompt formatter | `orchestrator_service/main.py` (`_format_insurance_providers()`) | Rewrite to emit per-treatment coverage rules instead of the current generic block |
| Frontend modal Tab 2 | `frontend_react/src/views/ClinicsView.tsx` | Replace `restrictions` checkbox list with a per-treatment coverage matrix |
| i18n | `frontend_react/src/locales/es.json`, `en.json`, `fr.json` | New keys for coverage matrix UI |

### Out of Scope

- Nova (internal AI copilot) — does not use `_format_insurance_providers()`
- Patient-facing public forms — no insurance changes
- Billing/invoicing columns on `appointments` — separate concern
- New insurance-lookup tool for the AI agent — future change
- Third-party insurance API integrations (ARCA, COFA) — future change
- WhatsApp / BFF / Docker config — no changes

---

## 3. Approach

### Layer 1: Data Model Redesign

Replace the ambiguous `restrictions TEXT` column with a structured `coverage_by_treatment JSONB` column. The JSONB shape is keyed by treatment `code` (from `treatment_types`):

```json
{
  "IMPT": {
    "covered": true,
    "copay_percent": 30,
    "requires_pre_authorization": true,
    "pre_auth_leadtime_days": 5,
    "waiting_period_days": 180,
    "max_annual_coverage": null,
    "notes": "Solo implantes unitarios. No cubre sobredentadura."
  },
  "CONS": {
    "covered": true,
    "copay_percent": 0,
    "requires_pre_authorization": false,
    "pre_auth_leadtime_days": 0,
    "waiting_period_days": 0,
    "max_annual_coverage": null,
    "notes": ""
  }
}
```

New top-level columns on `tenant_insurance_providers`:

| Column | Type | Default | Purpose |
|---|---|---|---|
| `is_prepaid` | BOOLEAN | false | Distinguish prepaga from obra social tradicional |
| `employee_discount_percent` | DECIMAL(5,2) | NULL | Optional % discount for employees of affiliated companies |
| `default_copay_percent` | DECIMAL(5,2) | NULL | Fallback copay % when no per-treatment override exists |

The existing `copay_notes` TEXT column is RETAINED as a general-purpose free-text note for the provider level (e.g., "Pago por débito automático antes del 5 de cada mes").

The existing `restrictions` TEXT column is DROPPED after data migration.

### Layer 2: Backend Changes

- New Pydantic model `TreatmentCoverage` validates each entry in `coverage_by_treatment`.
- `InsuranceProviderCreate` / `InsuranceProviderUpdate` replace `restrictions: Optional[str]` with `coverage_by_treatment: Optional[dict[str, TreatmentCoverage]]`.
- Validation: `copay_percent` must be 0–100; `pre_auth_leadtime_days` and `waiting_period_days` must be non-negative.
- CRUD endpoints updated; no breaking change in URL or HTTP method.

### Layer 3: AI Prompt Formatter Rewrite

`_format_insurance_providers()` receives the same list of provider dicts. After the migration, each dict has `coverage_by_treatment` JSONB. The formatter builds a much richer prompt block:

```
OSDE (prepaga) — coseguro por defecto: 20%
  • Consulta (CONS): cubierta, sin coseguro, sin preautorización
  • Implante (IMPT): cubierto, coseguro 30%, requiere preautorización (5 días hábiles), carencia 180 días
  • Blanqueamiento (BLAN): NO cubierto
```

If a provider has no `coverage_by_treatment` entries (migrated from legacy or newly created), the formatter falls back to the current generic block: "trabajamos con tu obra social, coseguro estándar".

### Layer 4: Frontend Modal Redesign

The current Tab 2 modal shows a `restrictions` checkbox list only for `status='restricted'`. The new modal shows a **per-treatment coverage matrix** for ALL statuses that involve actual coverage (accepted, restricted). The matrix has:

- Rows = treatment types active for this tenant (from `GET /admin/treatment-types`)
- Columns = covered (toggle), copay %, requires pre-auth, waiting period days, notes

---

## 4. Alternatives Considered

| Option | Description | Why Rejected |
|---|---|---|
| **A. Keep flat restrictions array** | Add more fields as additional JSON arrays or columns | Does not solve the per-treatment structured data problem; leads to proliferation of parallel columns |
| **B. New junction table `insurance_treatment_coverage`** | Normalize into a separate relational table | Adds JOIN complexity, extra migration, extra endpoint, extra ORM model; JSONB is idiomatic for this use case in this codebase (see `post_instructions`, `followup_template` on `TreatmentType`) |
| **C. coverage_by_treatment JSONB (chosen)** | Single structured column keyed by treatment code | Consistent with codebase patterns; no extra table; easy to extend per-tenant; asyncpg returns JSONB natively |
| **D. Embed coverage in treatment_types** | Add insurance coverage to the treatment record | Wrong direction — coverage depends on (provider, treatment) pair, not just treatment; would require duplicating data per insurance |

---

## 5. Backwards Compatibility

- Existing rows with `restrictions = '["IMPT","CONS"]'` are automatically migrated in `upgrade()` to `coverage_by_treatment = {"IMPT": {"covered": true}, "CONS": {"covered": true}}` with all other fields at their defaults.
- Existing rows with `restrictions = NULL` or non-JSON text get `coverage_by_treatment = {}`.
- `_format_insurance_providers()` checks: if `coverage_by_treatment` is empty dict, fall back to generic block (no behavioral regression for tenants that haven't reconfigured).
- Frontend `parseRestrictionsAsCodes()` helper is replaced by `parseCoverageByTreatment()` — old form state `restrictions` field is replaced by `coverage_by_treatment`.

---

## 6. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| JSONB validation on write | MEDIUM | Pydantic `TreatmentCoverage` model validates each entry before INSERT/UPDATE |
| asyncpg returns JSONB as string | LOW | Apply `json.loads` defensively in list endpoint (consistent with existing pattern on `tenants.working_hours`) |
| Data migration corrupts existing rows | MEDIUM | Migration runs `coverage_by_treatment = {}` for unrecognizable `restrictions` values; all cases handled explicitly; `downgrade()` restores the column |
| Frontend matrix UX is too complex | LOW | Matrix is collapsed by default; empty rows (no coverage configured) are visually de-emphasized |
| Prompt block becomes too long for tenants with 15+ treatments | MEDIUM | Formatter caps output: only emit treatments where `covered=true` or where there is an explicit note; skip `covered=false` with no notes |

---

## 7. Success Criteria

- [ ] Agent can answer "¿OSDE cubre el implante?" with copay %, pre-auth requirement, and waiting period
- [ ] Agent can distinguish prepaga from obra social tradicional
- [ ] Agent can report default copay % when no per-treatment override is set
- [ ] `_format_insurance_providers()` emits per-treatment rules for providers with `coverage_by_treatment` populated
- [ ] Existing providers with legacy `restrictions` arrays continue to work (covered=true migration)
- [ ] Frontend matrix allows setting copay %, pre-auth, waiting period per treatment
- [ ] All changes are tenant-isolated (`WHERE tenant_id = $x` on every query)
- [ ] Migration runs up and down cleanly on a database with existing insurance data
