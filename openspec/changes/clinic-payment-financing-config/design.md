# DESIGN: Clinic Payment & Financing Configuration

**Change**: `clinic-payment-financing-config`
**Status**: DESIGNED
**Date**: 2026-04-07

---

## Architecture Decisions

### D1: All 8 columns on tenants — no junction table

**Decision**: Add 8 columns directly to `tenants`. No separate `tenant_payment_config` table.

**Rationale**: Payment/financing config is 1:1 with a tenant. There is no need for a junction table. All existing payment data (`bank_cbu`, `consultation_price`) already lives directly on `tenants`. Adding a junction table for 8 columns introduces a join with zero benefit.

**Rejected**: A separate JSONB `payment_config` column. While that avoids schema changes, it complicates:
- Typed validation (CHECK constraints cannot reach inside JSONB values at the DB level)
- SQLAlchemy model clarity
- Column-level migrations (adding/removing individual fields cleanly)

---

### D2: payment_methods as JSONB array, not a junction table or bitmask

**Decision**: `payment_methods JSONB` storing a JSON array of string tokens (e.g., `["cash","credit_card","mercado_pago"]`).

**Rationale**: The set of valid payment methods can vary per country and will grow over time (new fintech players). JSONB array is flexible for reads, indexable with `@>` operator, and avoids a many-to-many table. The allowed token set is validated at the application layer (admin_routes.py) rather than in a FK reference table, which is consistent with the `working_hours` JSONB pattern already in the project.

**Frontend** renders this as a multi-checkbox group, not a free-text field, so the token set is constrained at entry time.

---

### D3: Injection point in build_system_prompt()

**Current prompt structure** (relevant sections, from build_system_prompt() in main.py ~line 6400+):

```
... [anamnesis section]
## DATOS BANCARIOS PARA COBRO DE SEÑA        ← bank_section (if bank_holder_name set)
    [seña flow rules]
[next section: insurance providers / working hours / etc.]
```

**Decision**: Inject `_format_payment_options()` output IMMEDIATELY AFTER `bank_section`, before the insurance/working-hours sections.

**Rationale**: Payment methods and bank transfer data are semantically related (both answer "¿cómo pago?"). Grouping them keeps the payment domain together in the prompt, which helps the LLM find the relevant context efficiently.

---

## Component Diffs

### Alembic Migration: `035_add_payment_financing_config.py`

```python
# orchestrator_service/alembic/versions/035_add_payment_financing_config.py

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None

def upgrade():
    # Check column existence before adding (idempotency guard — project convention)
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing = [c["name"] for c in inspector.get_columns("tenants")]

    if "payment_methods" not in existing:
        op.add_column("tenants", sa.Column("payment_methods", postgresql.JSONB(), nullable=True))

    if "financing_available" not in existing:
        op.add_column("tenants", sa.Column(
            "financing_available", sa.Boolean(), nullable=True,
            server_default=sa.text("false")
        ))

    if "max_installments" not in existing:
        op.add_column("tenants", sa.Column("max_installments", sa.Integer(), nullable=True))
        op.create_check_constraint(
            "ck_tenants_max_installments_range",
            "tenants",
            "max_installments IS NULL OR (max_installments >= 1 AND max_installments <= 24)"
        )

    if "installments_interest_free" not in existing:
        op.add_column("tenants", sa.Column(
            "installments_interest_free", sa.Boolean(), nullable=True,
            server_default=sa.text("true")
        ))

    if "financing_provider" not in existing:
        op.add_column("tenants", sa.Column("financing_provider", sa.Text(), nullable=True))

    if "financing_notes" not in existing:
        op.add_column("tenants", sa.Column("financing_notes", sa.Text(), nullable=True))

    if "cash_discount_percent" not in existing:
        op.add_column("tenants", sa.Column(
            "cash_discount_percent", sa.Numeric(5, 2), nullable=True
        ))
        op.create_check_constraint(
            "ck_tenants_cash_discount_range",
            "tenants",
            "cash_discount_percent IS NULL OR (cash_discount_percent >= 0 AND cash_discount_percent <= 100)"
        )

    if "accepts_crypto" not in existing:
        op.add_column("tenants", sa.Column(
            "accepts_crypto", sa.Boolean(), nullable=True,
            server_default=sa.text("false")
        ))

def downgrade():
    # Drop in reverse order, constraints first
    try:
        op.drop_constraint("ck_tenants_cash_discount_range", "tenants", type_="check")
    except Exception:
        pass
    try:
        op.drop_constraint("ck_tenants_max_installments_range", "tenants", type_="check")
    except Exception:
        pass

    for col in [
        "accepts_crypto", "cash_discount_percent", "financing_notes",
        "financing_provider", "installments_interest_free", "max_installments",
        "financing_available", "payment_methods"
    ]:
        try:
            op.drop_column("tenants", col)
        except Exception:
            pass
```

---

### models.py — Tenant ORM diff

Add after `bank_holder_name = Column(Text)` and before `derivation_email`:

```python
# New payment/financing columns (migration 035)
payment_methods = Column(JSONB, nullable=True)
financing_available = Column(Boolean, nullable=True, server_default=text("false"))
max_installments = Column(Integer, nullable=True)
installments_interest_free = Column(Boolean, nullable=True, server_default=text("true"))
financing_provider = Column(Text, nullable=True)
financing_notes = Column(Text, nullable=True)
cash_discount_percent = Column(Numeric(5, 2), nullable=True)
accepts_crypto = Column(Boolean, nullable=True, server_default=text("false"))
```

---

### admin_routes.py — update_tenant() diff

Add the following blocks inside `update_tenant()`, after the existing `bank_holder_name` block and before the `derivation_email` block:

```python
ALLOWED_PAYMENT_METHODS = {
    "cash", "credit_card", "debit_card", "transfer", "mercado_pago",
    "rapipago", "pagofacil", "modo", "uala", "naranja", "crypto", "other"
}

if "payment_methods" in data:
    val = data.get("payment_methods")
    if val is None or val == [] or val == "":
        params.append(None)
    else:
        if not isinstance(val, list):
            val = list(val)
        invalid = set(val) - ALLOWED_PAYMENT_METHODS
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"payment_methods contains invalid values: {invalid}"
            )
        params.append(json.dumps(val) if val else None)
    updates.append(f"payment_methods = ${len(params)}::jsonb")

if "financing_available" in data:
    val = data.get("financing_available")
    if val is None:
        params.append(False)
    elif isinstance(val, bool):
        params.append(val)
    else:
        params.append(str(val).lower() in ("true", "1", "yes"))
    updates.append(f"financing_available = ${len(params)}")

if "max_installments" in data:
    val = data.get("max_installments")
    if val is None or str(val).strip() == "":
        params.append(None)
    else:
        ival = int(val)
        if not (1 <= ival <= 24):
            raise HTTPException(status_code=422, detail="max_installments must be between 1 and 24")
        params.append(ival)
    updates.append(f"max_installments = ${len(params)}")

if "installments_interest_free" in data:
    val = data.get("installments_interest_free")
    if val is None:
        params.append(True)
    elif isinstance(val, bool):
        params.append(val)
    else:
        params.append(str(val).lower() in ("true", "1", "yes"))
    updates.append(f"installments_interest_free = ${len(params)}")

if "financing_provider" in data:
    params.append(data.get("financing_provider") or None)
    updates.append(f"financing_provider = ${len(params)}")

if "financing_notes" in data:
    params.append(data.get("financing_notes") or None)
    updates.append(f"financing_notes = ${len(params)}")

if "cash_discount_percent" in data:
    val = data.get("cash_discount_percent")
    if val is None or str(val).strip() == "":
        params.append(None)
    else:
        fval = float(val)
        if not (0.0 <= fval <= 100.0):
            raise HTTPException(status_code=422, detail="cash_discount_percent must be between 0 and 100")
        params.append(fval)
    updates.append(f"cash_discount_percent = ${len(params)}")

if "accepts_crypto" in data:
    val = data.get("accepts_crypto")
    if val is None:
        params.append(False)
    elif isinstance(val, bool):
        params.append(val)
    else:
        params.append(str(val).lower() in ("true", "1", "yes"))
    updates.append(f"accepts_crypto = ${len(params)}")
```

Also extend the SELECT in `GET /admin/tenants` to include:
```sql
payment_methods, financing_available, max_installments, installments_interest_free,
financing_provider, financing_notes, cash_discount_percent, accepts_crypto
```

---

### main.py — _format_payment_options() full pseudocode

```python
_PAYMENT_METHOD_LABELS = {
    "cash": "Efectivo",
    "credit_card": "Tarjeta de crédito",
    "debit_card": "Tarjeta de débito",
    "transfer": "Transferencia bancaria",
    "mercado_pago": "Mercado Pago",
    "rapipago": "Rapipago",
    "pagofacil": "Pago Fácil",
    "modo": "MODO",
    "uala": "Ualá",
    "naranja": "Tarjeta Naranja",
    "crypto": "Criptomonedas",
    "other": "Otros medios",
}

def _format_payment_options(
    payment_methods: list = None,
    financing_available: bool = False,
    max_installments: int = None,
    installments_interest_free: bool = True,
    financing_provider: str = "",
    financing_notes: str = "",
    cash_discount_percent: float = None,
    accepts_crypto: bool = False,
) -> str:
    lines = []

    # Payment methods block
    if payment_methods:
        labels = [_PAYMENT_METHOD_LABELS.get(m, m) for m in payment_methods]
        lines.append(f"Medios de pago aceptados: {', '.join(labels)}.")

    # Financing block
    if financing_available:
        parts = []
        if max_installments:
            interest_str = "sin interés" if installments_interest_free else "con interés"
            parts.append(f"hasta {max_installments} cuotas {interest_str}")
        if financing_provider:
            parts.append(f"con {financing_provider}")
        if parts:
            lines.append(f"Financiación disponible: {', '.join(parts)}.")
        else:
            lines.append("Financiación disponible (consultá condiciones con la clínica).")
        if financing_notes:
            lines.append(f"Nota sobre financiación: {financing_notes}")

    # Cash discount block
    if cash_discount_percent is not None and float(cash_discount_percent) > 0:
        pct = int(cash_discount_percent) if float(cash_discount_percent) == int(cash_discount_percent) else cash_discount_percent
        lines.append(f"Descuento por pago en efectivo: {pct}%.")

    # Crypto block
    if accepts_crypto:
        lines.append("Criptomonedas: aceptamos pago en criptomonedas.")

    if not lines:
        return ""  # No section emitted — backward compat

    disclaimer = (
        "(Información orientativa — las condiciones pueden variar. "
        "Para confirmación final, derivar al administrativo de la clínica.)"
    )
    block = "## MEDIOS DE PAGO Y FINANCIACIÓN\n"
    block += "\n".join(lines)
    block += f"\n{disclaimer}"
    return block
```

**Sample output for a maximally-configured tenant:**
```
## MEDIOS DE PAGO Y FINANCIACIÓN
Medios de pago aceptados: Efectivo, Tarjeta de crédito, Tarjeta de débito, Mercado Pago.
Financiación disponible: hasta 6 cuotas sin interés, con Mercado Pago.
Nota sobre financiación: Válido solo con Visa y Mastercard, hasta dic 2026.
Descuento por pago en efectivo: 10%.
(Información orientativa — las condiciones pueden variar. Para confirmación final, derivar al administrativo de la clínica.)
```

---

### build_system_prompt() — new parameters and injection point

**New parameter signature** (add after existing `bank_holder_name: str = ""`):

```python
payment_methods: list = None,
financing_available: bool = False,
max_installments: int = None,
installments_interest_free: bool = True,
financing_provider: str = "",
financing_notes: str = "",
cash_discount_percent: float = None,
accepts_crypto: bool = False,
```

**Injection** (after the `bank_section` construction block, ~line 6444):

```python
payment_section = _format_payment_options(
    payment_methods=payment_methods,
    financing_available=financing_available,
    max_installments=max_installments,
    installments_interest_free=installments_interest_free,
    financing_provider=financing_provider,
    financing_notes=financing_notes,
    cash_discount_percent=cash_discount_percent,
    accepts_crypto=accepts_crypto,
)
```

Then in the return string, append `{payment_section}` immediately after `{bank_section}`.

---

### buffer_task.py — caller update

The tenant row is already fetched in `buffer_task.py`. Extend the SELECT to include the 8 new columns and pass them to `build_system_prompt()`:

```python
# In the build_system_prompt() call inside buffer_task.py:
payment_methods=tenant.get("payment_methods") or [],
financing_available=bool(tenant.get("financing_available") or False),
max_installments=tenant.get("max_installments"),
installments_interest_free=bool(tenant.get("installments_interest_free") if tenant.get("installments_interest_free") is not None else True),
financing_provider=tenant.get("financing_provider") or "",
financing_notes=tenant.get("financing_notes") or "",
cash_discount_percent=tenant.get("cash_discount_percent"),
accepts_crypto=bool(tenant.get("accepts_crypto") or False),
```

---

## Frontend Design

### Location

The new section goes inside the Edit/Create Clinic modal (`ClinicsView.tsx`), after the existing `## Datos Bancarios` section and before the `Email de derivacion` section.

### Structure

```
[border-t divider]
Section header: "Pagos y Financiación"   ← collapsible toggle (ChevronDown icon)
  [collapse body — shown when expanded]

  Multi-checkbox: "Medios de pago aceptados"
    [ ] Efectivo (cash)
    [ ] Tarjeta de crédito (credit_card)
    [ ] Tarjeta de débito (debit_card)
    [ ] Transferencia bancaria (transfer)
    [ ] Mercado Pago (mercado_pago)
    [ ] Rapipago (rapipago)
    [ ] Pago Fácil (pagofacil)
    [ ] MODO (modo)
    [ ] Ualá (uala)
    [ ] Tarjeta Naranja (naranja)
    [ ] Criptomonedas (crypto)
    → Rendered as a 2-column checkbox grid (grid-cols-2 gap-2)

  Toggle (checkbox): "¿Ofrecen financiación / cuotas?"  ← financing_available

  [Conditional block — visible ONLY when financing_available=true]
    Input (number, 1-24): "Cuotas máximas"              ← max_installments
    Toggle (checkbox): "Sin interés"                     ← installments_interest_free
    Input (text): "Proveedor de financiación"            ← financing_provider
    Textarea (2 rows): "Notas de financiación"          ← financing_notes

  Input (number, 0-100, step=0.01): "Descuento por pago en efectivo (%)" ← cash_discount_percent
  Toggle (checkbox): "Aceptan criptomonedas"            ← accepts_crypto
```

### Layout Classes

- Section wrapper: `space-y-3 border-t border-white/[0.06] pt-4 mt-4`
- Section header row: `flex items-center justify-between cursor-pointer` (click to expand/collapse)
- Header text: `text-sm font-bold text-white/60 flex items-center gap-2`
- Collapse chevron: `ChevronDown size={14}` with `rotate-180` class when expanded
- Help text: `text-xs text-white/30`
- Checkbox grid: `grid grid-cols-2 gap-2 mt-2`
- Checkbox item: `flex items-center gap-2 text-sm text-white/70`
- Conditional financing block: `space-y-3 pl-4 border-l border-white/[0.06] mt-2` (visual indent)
- Input fields: `w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none`

### State

Add to `formData` initial state and `useEffect` (editingClinica load):

```typescript
payment_methods: [] as string[],
financing_available: false,
max_installments: '',
installments_interest_free: true,
financing_provider: '',
financing_notes: '',
cash_discount_percent: '',
accepts_crypto: false,
```

Add local state for section collapse:
```typescript
const [paymentSectionExpanded, setPaymentSectionExpanded] = useState(false)
```

### Checkbox toggle helper

```typescript
const togglePaymentMethod = (method: string) => {
  setFormData(prev => ({
    ...prev,
    payment_methods: prev.payment_methods.includes(method)
      ? prev.payment_methods.filter(m => m !== method)
      : [...prev.payment_methods, method]
  }))
}
```

### Submit inclusion

The `handleSubmit` POST/PUT body MUST include all 8 new fields:
```typescript
payment_methods: formData.payment_methods,
financing_available: formData.financing_available,
max_installments: formData.max_installments !== '' ? Number(formData.max_installments) : null,
installments_interest_free: formData.installments_interest_free,
financing_provider: formData.financing_provider || null,
financing_notes: formData.financing_notes || null,
cash_discount_percent: formData.cash_discount_percent !== '' ? Number(formData.cash_discount_percent) : null,
accepts_crypto: formData.accepts_crypto,
```

---

## Security

**Tenant isolation**: Already enforced. The `update_tenant()` endpoint uses `verify_admin_token` which resolves the authenticated user's tenant list. The `tenant_id` comes from the URL path, not the request body, and the CEO-role check ensures only authorized users can modify any tenant. This is identical to every other field on this endpoint. No new security surface is introduced.

**Payment data sensitivity**: None of the new fields are sensitive (they describe clinic policy, not patient data). No encryption required.

**Prompt injection**: The `financing_notes` field is admin-controlled (CEO only). Still, the formatter MUST NOT interpolate it as a raw f-string inside prompt instruction blocks — it is presented as a `Nota:` sub-line inside the data section, not as instructions to the LLM.
