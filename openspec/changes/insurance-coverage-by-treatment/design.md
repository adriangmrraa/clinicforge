# DESIGN: Insurance Coverage by Treatment

**Change**: `insurance-coverage-by-treatment`
**Status**: DESIGNED
**Date**: 2026-04-07

---

## Architecture Decisions

### D1: JSONB column vs. new junction table

**Decision: JSONB column `coverage_by_treatment` on `tenant_insurance_providers`**

Rationale: The codebase already uses JSONB for structured per-entity data (`treatment_types.post_instructions`, `treatment_types.followup_template`, `tenants.working_hours`). A separate `insurance_treatment_coverage` table would require a new ORM model, new FK, extra JOIN in every query, extra migration complexity, and extra CRUD endpoints — none of which is justified for data that is always read/written as a unit together with the provider record.

JSONB is flexible enough to add fields later without a new migration. Keys are treatment codes (stable business identifiers). asyncpg handles JSONB serialization natively.

**Rejected alternative**: new relational table. See proposal.md Section 4.

---

### D2: JSONB handling — asyncpg returns JSONB as string

asyncpg versions prior to 0.29 return JSONB columns as Python strings in some contexts. The existing codebase already handles this for `tenants.working_hours` in `admin_routes.py`. The same defensive pattern MUST be applied here:

```python
# In list_insurance_providers endpoint:
for row in rows:
    r = dict(row)
    if isinstance(r.get("coverage_by_treatment"), str):
        r["coverage_by_treatment"] = json.loads(r["coverage_by_treatment"])
    result.append(r)
```

---

### D3: Migration filename

**Decision: `034_insurance_coverage_by_treatment.py`**

Current head is `033_clinic_bot_name.py` (after bot_name change). This change uses revision `034`.

#### Full Alembic migration design

```python
# orchestrator_service/alembic/versions/034_insurance_coverage_by_treatment.py

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None

# upgrade() pseudocode:
def upgrade():
    # 1. Add new columns
    op.add_column("tenant_insurance_providers",
        sa.Column("coverage_by_treatment", JSONB, nullable=False, server_default="'{}'"))
    op.add_column("tenant_insurance_providers",
        sa.Column("is_prepaid", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("tenant_insurance_providers",
        sa.Column("employee_discount_percent", sa.Numeric(5, 2), nullable=True))
    op.add_column("tenant_insurance_providers",
        sa.Column("default_copay_percent", sa.Numeric(5, 2), nullable=True))

    # 2. Data migration: convert existing restrictions arrays
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, restrictions FROM tenant_insurance_providers")
    ).fetchall()
    for row in rows:
        coverage = {}
        restrictions_val = row["restrictions"]
        if restrictions_val:
            try:
                codes = json.loads(restrictions_val)
                if isinstance(codes, list):
                    for code in codes:
                        if isinstance(code, str) and code.strip():
                            coverage[code.strip()] = {
                                "covered": True,
                                "copay_percent": 0.0,
                                "requires_pre_authorization": False,
                                "pre_auth_leadtime_days": 0,
                                "waiting_period_days": 0,
                                "max_annual_coverage": None,
                                "notes": "",
                            }
            except (json.JSONDecodeError, TypeError):
                pass  # Unrecognizable format → empty coverage
        conn.execute(
            sa.text(
                "UPDATE tenant_insurance_providers "
                "SET coverage_by_treatment = :cov::jsonb WHERE id = :id"
            ),
            {"cov": json.dumps(coverage), "id": row["id"]},
        )

    # 3. Drop the old restrictions column
    op.drop_column("tenant_insurance_providers", "restrictions")


# downgrade() pseudocode:
def downgrade():
    # 1. Restore restrictions column
    op.add_column("tenant_insurance_providers",
        sa.Column("restrictions", sa.Text, nullable=True))

    # 2. Reverse data migration: extract covered=true codes back to JSON array
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, coverage_by_treatment FROM tenant_insurance_providers")
    ).fetchall()
    for row in rows:
        codes = []
        coverage = row["coverage_by_treatment"]
        if isinstance(coverage, str):
            coverage = json.loads(coverage) if coverage else {}
        if isinstance(coverage, dict):
            codes = [k for k, v in coverage.items()
                     if isinstance(v, dict) and v.get("covered", False)]
        restrictions_val = json.dumps(codes) if codes else None
        conn.execute(
            sa.text(
                "UPDATE tenant_insurance_providers "
                "SET restrictions = :r WHERE id = :id"
            ),
            {"r": restrictions_val, "id": row["id"]},
        )

    # 3. Drop new columns
    op.drop_column("tenant_insurance_providers", "coverage_by_treatment")
    op.drop_column("tenant_insurance_providers", "is_prepaid")
    op.drop_column("tenant_insurance_providers", "employee_discount_percent")
    op.drop_column("tenant_insurance_providers", "default_copay_percent")
```

---

### D4: ORM Model update (`models.py`)

Replace `restrictions = Column(Text, nullable=True)` with:

```python
# REMOVE:
restrictions = Column(Text, nullable=True)

# ADD after existing columns, before external_target:
coverage_by_treatment = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
is_prepaid = Column(Boolean, nullable=False, server_default="false")
employee_discount_percent = Column(DECIMAL(5, 2), nullable=True)
default_copay_percent = Column(DECIMAL(5, 2), nullable=True)
```

Import `JSONB` from `sqlalchemy.dialects.postgresql` (already imported in models.py for other models — verify).

---

### D5: Backend Pydantic schema + endpoint diff

#### New `TreatmentCoverage` model (add in admin_routes.py before InsuranceProviderCreate):

```python
class TreatmentCoverage(BaseModel):
    covered: bool = True
    copay_percent: float = 0.0
    requires_pre_authorization: bool = False
    pre_auth_leadtime_days: int = 0
    waiting_period_days: int = 0
    max_annual_coverage: Optional[float] = None
    notes: str = ""
```

#### Updated `InsuranceProviderCreate` diff:

```python
# REMOVE:
restrictions: Optional[str] = None

# ADD:
coverage_by_treatment: Optional[dict[str, TreatmentCoverage]] = None
is_prepaid: bool = False
employee_discount_percent: Optional[float] = None
default_copay_percent: Optional[float] = None
```

Same change for `InsuranceProviderUpdate`.

#### `_validate_insurance_provider` diff:

Remove the `status == 'restricted'` → `restrictions` required check entirely.

Add:
```python
# Validate coverage entries
if data.coverage_by_treatment:
    for code, cov in data.coverage_by_treatment.items():
        if not code.strip():
            raise HTTPException(422, "Los códigos de tratamiento no pueden estar vacíos")
        if not (0 <= cov.copay_percent <= 100):
            raise HTTPException(422, "copay_percent debe estar entre 0 y 100")
        if cov.pre_auth_leadtime_days < 0:
            raise HTTPException(422, "pre_auth_leadtime_days no puede ser negativo")
        if cov.waiting_period_days < 0:
            raise HTTPException(422, "waiting_period_days no puede ser negativo")
        if cov.max_annual_coverage is not None and cov.max_annual_coverage <= 0:
            raise HTTPException(422, "max_annual_coverage debe ser positivo")
        if len(cov.notes) > 500:
            raise HTTPException(422, "notes no puede superar 500 caracteres por tratamiento")
if data.employee_discount_percent is not None and not (0 <= data.employee_discount_percent <= 100):
    raise HTTPException(422, "employee_discount_percent debe estar entre 0 y 100")
if data.default_copay_percent is not None and not (0 <= data.default_copay_percent <= 100):
    raise HTTPException(422, "default_copay_percent debe estar entre 0 y 100")
```

#### INSERT / UPDATE SQL diff:

```sql
-- BEFORE:
INSERT INTO tenant_insurance_providers (
    tenant_id, provider_name, status, restrictions, external_target,
    requires_copay, copay_notes, ai_response_template, sort_order, is_active, updated_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())

-- AFTER:
INSERT INTO tenant_insurance_providers (
    tenant_id, provider_name, status, coverage_by_treatment, external_target,
    requires_copay, copay_notes, ai_response_template, sort_order, is_active,
    is_prepaid, employee_discount_percent, default_copay_percent, updated_at
) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())
```

Python side: serialize `coverage_by_treatment` with:
```python
json.dumps({k: v.dict() for k, v in (data.coverage_by_treatment or {}).items()})
```

---

### D6: `_format_insurance_providers` rewrite

#### Before (current behavior, simplified):

```python
# For accepted providers:
lines.append(f"  • {p['provider_name']} → {p.get('copay_notes') or 'coseguro estándar'}")

# No per-treatment detail, no preauth, no waiting period
```

#### After (new behavior):

```python
def _format_insurance_providers(providers: list, treatment_display_map: dict = None) -> str:
    """
    providers: list of dicts from tenant_insurance_providers (is_active=true)
    treatment_display_map: {code: display_name} from treatment_types for this tenant
    """
    if not providers:
        return ""

    treatment_display_map = treatment_display_map or {}
    lines = ["OBRAS SOCIALES — REGLAS DE RESPUESTA:"]

    accepted = [p for p in providers if p.get("status") in ("accepted", "restricted")]
    derivation = [p for p in providers if p.get("status") == "external_derivation"]
    rejected = [p for p in providers if p.get("status") == "rejected"]

    for p in accepted:
        prepaga_flag = " (prepaga)" if p.get("is_prepaid") else ""
        default_copay = p.get("default_copay_percent")
        default_copay_str = f" — coseguro por defecto: {default_copay}%" if default_copay is not None else ""
        lines.append(f"{p['provider_name']}{prepaga_flag}{default_copay_str}:")

        coverage = p.get("coverage_by_treatment") or {}
        if isinstance(coverage, str):
            try:
                coverage = json.loads(coverage)
            except Exception:
                coverage = {}

        if not coverage:
            # Fallback: legacy row or freshly created without coverage details
            copay_str = p.get("copay_notes") or "coseguro estándar"
            lines.append(f"  Respuesta: 'Sí, trabajamos con {p['provider_name']}. {copay_str}. ¿Querés turno?'")
            continue

        covered_entries = [(k, v) for k, v in coverage.items() if v.get("covered", False)]
        not_covered_entries = [(k, v) for k, v in coverage.items() if not v.get("covered", False)]

        # Cap at 10 total entries
        all_entries = covered_entries + not_covered_entries
        capped = all_entries[:10]
        overflow = len(all_entries) > 10

        covered_capped = [(k, v) for k, v in capped if v.get("covered", False)]
        not_covered_capped = [(k, v) for k, v in capped if not v.get("covered", False)]

        if covered_capped:
            lines.append("  Cubiertos:")
            for code, cov in covered_capped:
                display = treatment_display_map.get(code, code)
                copay_str = f", coseguro {cov.get('copay_percent', 0)}%" if cov.get('copay_percent', 0) > 0 else ", sin coseguro"
                preauth = f", requiere preautorización ({cov.get('pre_auth_leadtime_days', 0)} días hábiles)" if cov.get("requires_pre_authorization") else ""
                waiting = f", carencia {cov.get('waiting_period_days')} días" if cov.get("waiting_period_days", 0) > 0 else ""
                notes = f". Nota: {cov['notes']}" if cov.get("notes") else ""
                lines.append(f"    • {display} ({code}): cubierto{copay_str}{preauth}{waiting}{notes}")

        if not_covered_capped:
            lines.append("  NO cubiertos:")
            for code, cov in not_covered_capped:
                display = treatment_display_map.get(code, code)
                notes = f". Nota: {cov['notes']}" if cov.get("notes") else ""
                lines.append(f"    • {display} ({code}){notes}")

        if overflow:
            lines.append("    ... y otros tratamientos — consultá con la clínica")

    # derivation and rejected sections: unchanged from current behavior
    for p in derivation:
        target = p.get("external_target") or "otro centro"
        msg = (p.get("ai_response_template")
               or f"Para ese tratamiento trabajamos a través de {target}. Te paso el contacto.")
        lines.append(f"  • {p['provider_name']} → Derivar a {target}. Mensaje: '{msg}'")

    if rejected:
        names = ", ".join(p["provider_name"] for p in rejected)
        lines.append(f"No aceptadas: {names}")

    lines.append("")
    lines.append(
        "Si el paciente menciona una OS que NO está en esta lista → "
        '"No tengo información sobre esa obra social. ¿Querés que consulte con la clínica?"'
    )

    return "\n".join(lines)
```

#### Caller change in `build_system_prompt`

`build_system_prompt` already receives `insurance_providers: list`. It also receives or can derive `treatment_types` list. Add the treatment display map construction:

```python
# Before calling _format_insurance_providers:
treatment_display_map = {
    t["code"]: t.get("patient_display_name") or t["name"]
    for t in (treatment_types or [])
}
insurance_section = _format_insurance_providers(insurance_providers or [], treatment_display_map)
```

Note: `build_system_prompt` already receives `treatment_types` via its caller chain in `buffer_task.py` — verify the parameter exists; if not, add it.

---

### D7: Frontend modal redesign

#### Component breakdown

```
InsuranceModal
├── InsuranceModalHeader (title, close button)
├── InsuranceProviderForm
│   ├── BasicFields
│   │   ├── providerName (text input)
│   │   ├── status (select: accepted/restricted/external_derivation/rejected)
│   │   ├── is_prepaid (checkbox)
│   │   ├── default_copay_percent (number input, optional)
│   │   └── employee_discount_percent (number input, optional)
│   ├── CoverageMatrix (shown when status is 'accepted' or 'restricted')
│   │   ├── CoverageMatrixHeader (expandable)
│   │   └── CoverageMatrixRow × N (one per active treatment type)
│   │       ├── treatment name + code (read-only label)
│   │       ├── covered (toggle/checkbox)
│   │       ├── copay_percent (number input 0-100, shown when covered=true)
│   │       ├── requires_pre_authorization (checkbox, shown when covered=true)
│   │       ├── pre_auth_leadtime_days (number input, shown when requires_pre_authorization=true)
│   │       ├── waiting_period_days (number input ≥0, shown when covered=true)
│   │       └── notes (text input max 500)
│   ├── ExternalDerivationFields (shown when status = 'external_derivation')
│   ├── CopayFields
│   │   ├── requires_copay (checkbox)
│   │   └── copay_notes (textarea, shown when requires_copay=true)
│   └── AiTemplateField
└── InsuranceModalFooter (cancel + save buttons)
```

#### Form state TypeScript shape

```typescript
interface TreatmentCoverageEntry {
  covered: boolean;
  copay_percent: number;
  requires_pre_authorization: boolean;
  pre_auth_leadtime_days: number;
  waiting_period_days: number;
  max_annual_coverage: number | null;
  notes: string;
}

interface InsuranceFormState {
  provider_name: string;
  status: 'accepted' | 'restricted' | 'external_derivation' | 'rejected';
  is_prepaid: boolean;
  default_copay_percent: number | null;
  employee_discount_percent: number | null;
  coverage_by_treatment: Record<string, TreatmentCoverageEntry>;
  external_target: string;
  requires_copay: boolean;
  copay_notes: string;
  ai_response_template: string;
  sort_order: number;
  is_active: boolean;
}
```

#### Validation strategy

```typescript
function validateInsuranceForm(form: InsuranceFormState): Record<string, string> {
  const errors: Record<string, string> = {};

  if (!form.provider_name.trim()) errors.provider_name = t('settings.insurance.errors.nameRequired');

  if (form.default_copay_percent !== null && (form.default_copay_percent < 0 || form.default_copay_percent > 100)) {
    errors.default_copay_percent = t('settings.insurance.errors.percentRange');
  }

  Object.entries(form.coverage_by_treatment).forEach(([code, cov]) => {
    if (cov.copay_percent < 0 || cov.copay_percent > 100) {
      errors[`coverage_${code}_copay`] = t('settings.insurance.errors.percentRange');
    }
    if (cov.waiting_period_days < 0) {
      errors[`coverage_${code}_waiting`] = t('settings.insurance.errors.nonNegative');
    }
    if (cov.notes.length > 500) {
      errors[`coverage_${code}_notes`] = t('settings.insurance.errors.notesTooLong');
    }
  });

  return errors;
}
```

Submit is disabled when `Object.keys(errors).length > 0`.

#### Matrix UX detail

- The matrix is inside a `<details>` or collapsible section, collapsed by default.
- Rows for treatments where the user has NOT touched any field show minimal state (just the treatment name and a "covered" toggle, OFF by default).
- When `covered` is toggled ON, the copay/preauth/waiting fields expand inline.
- A "Configurar todos como cubiertos" quick-action button sets all `covered = true`.
- The matrix scrolls independently (max-height with overflow-y-auto).

---

### D8: i18n keys to add

Add to `es.json`, `en.json`, `fr.json` under `settings.insurance.fields`:

| Key | ES | EN | FR |
|---|---|---|---|
| `isPrepaid` | "Es prepaga" | "Is prepaid" | "Est une prépayée" |
| `defaultCopay` | "Coseguro por defecto (%)" | "Default copay (%)" | "Ticket modérateur par défaut (%)" |
| `employeeDiscount` | "Descuento empleados (%)" | "Employee discount (%)" | "Remise employés (%)" |
| `coverageMatrix` | "Cobertura por tratamiento" | "Coverage by treatment" | "Couverture par traitement" |
| `coverageMatrixHint` | "Configurá el detalle de cobertura para cada tratamiento" | "Set coverage details per treatment" | "Configurez la couverture par traitement" |
| `covered` | "Cubre" | "Covered" | "Couvert" |
| `copayPercent` | "Coseguro (%)" | "Copay (%)" | "Ticket mod. (%)" |
| `requiresPreAuth` | "Requiere autorización" | "Requires pre-auth" | "Autorisation requise" |
| `preAuthDays` | "Días para autorización" | "Pre-auth lead time (days)" | "Délai d'autorisation (jours)" |
| `waitingDays` | "Carencia (días)" | "Waiting period (days)" | "Délai de carence (jours)" |
| `treatmentNotes` | "Notas" | "Notes" | "Notes" |
| `configureAllCovered` | "Marcar todos como cubiertos" | "Mark all as covered" | "Tout marquer comme couvert" |
| `coverageCollapsed` | "Ver detalle de cobertura" | "View coverage details" | "Voir les détails de couverture" |

Add to `settings.insurance.errors`:

| Key | ES | EN | FR |
|---|---|---|---|
| `percentRange` | "Debe estar entre 0 y 100" | "Must be between 0 and 100" | "Doit être entre 0 et 100" |
| `nonNegative` | "No puede ser negativo" | "Cannot be negative" | "Ne peut pas être négatif" |
| `notesTooLong` | "Máximo 500 caracteres" | "Maximum 500 characters" | "Maximum 500 caractères" |

---

### D9: Security — tenant isolation reasserted

All affected queries:
- `INSERT INTO tenant_insurance_providers`: `tenant_id` is resolved from `Depends(get_resolved_tenant_id)`, NEVER from request body
- `SELECT FROM tenant_insurance_providers WHERE tenant_id = $1`: already present, unchanged
- `UPDATE tenant_insurance_providers WHERE id = $1 AND tenant_id = $2`: already present, unchanged
- `DELETE FROM tenant_insurance_providers WHERE id = $1 AND tenant_id = $2`: already present, unchanged

The Alembic migration data migration loop reads ALL rows (no tenant filter) because the migration runs with superuser context — this is correct and consistent with existing migrations.

---

### D10: Backwards compatibility summary

| Scenario | Behavior |
|---|---|
| Existing row, `restrictions = '["IMPT"]'` | Migrated to `coverage_by_treatment = {"IMPT": {"covered": true, ...defaults}}`. Agent prompt shows "IMPT: cubierto, sin coseguro" |
| Existing row, `restrictions = NULL` | `coverage_by_treatment = {}`. Formatter uses fallback generic block. No behavior change. |
| New row created with no `coverage_by_treatment` | Stored as `{}`. Formatter fallback. |
| `_format_insurance_providers()` called with old dict (no `coverage_by_treatment` key) | Defensive check: `p.get("coverage_by_treatment") or {}` → fallback. No exception. |
| Frontend opens existing provider without `coverage_by_treatment` | Initializes form state with empty `{}`. Matrix shows all treatments unconfigured. |
