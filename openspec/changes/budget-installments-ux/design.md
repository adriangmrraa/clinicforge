# Design: Budget Installments & UX (DLD-20 + DLD-27)

## Technical Approach

Add `treatment_plan_installments` table for per-cuota tracking. Installments are auto-generated from plan config, payments link to specific installments. Overdue computed at read time. Nav fix: reset `selectedPlanId` on `patientId` change.

## Architecture Decisions

### D1: Overdue — computed vs stored

| Option | Tradeoff | Decision |
|--------|----------|----------|
| SQL CASE in SELECT | No cron, always fresh, slight query complexity | **Chosen** |
| Stored status + cron | Simpler queries, stale between cron runs | Rejected |

**Rationale**: The plan detail endpoint already runs a multi-join query. Adding `CASE WHEN due_date < CURRENT_DATE AND status = 'pending' THEN 'overdue' ELSE status END` is trivial. No cron needed.

### D2: Generation logic location

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Inline in admin_routes.py | Follows existing pattern (all plan logic is there) | **Chosen** |
| New service file | Cleaner separation, but breaks consistency | Rejected |

**Rationale**: `admin_routes.py` already has `recalculate_plan_estimated_total()` and all plan handlers inline. Adding a `generate_installments()` helper follows the same pattern.

### D3: Data migration for existing plans

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Auto-generate from JSON notes | Risk: JSON may be incomplete (no dates) | Rejected |
| Leave existing as-is | No risk, secretary generates fresh when needed | **Chosen** |

**Rationale**: Existing `installments` in `notes` is just a count + per-installment amount with no due dates. Can't generate meaningful records. Secretary will configure cuotas properly via the new UI.

### D4: Installment-payment relationship direction

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `installment_id` FK on payments | Payment points to installment, 1 payment = 1 installment | **Chosen** |
| `payment_id` FK on installments | Installment points to payment | Also added (bidirectional) |

**Rationale**: Spec requires both: installment knows its payment (`payment_id` on installment), payment knows its installment (`installment_id` on payment). Bidirectional FKs for easy querying from either side.

## Data Flow

```
Secretary clicks "Generar cuotas"
    → POST /treatment-plans/{id}/installments/generate
    → Validate plan status (approved|in_progress)
    → Delete existing pending installments (if any)
    → Generate N records with calculated amounts + dates
    → Return installments array

Secretary clicks "Pagar" on a cuota
    → POST /treatment-plans/{id}/payments {installment_id}
    → Create payment record (existing flow)
    → UPDATE installment: status=paid, paid_at=now(), payment_id
    → Recalculate plan paid_total
    → Return payment + updated installment

GET plan detail
    → JOIN installments with CASE for overdue
    → Return plan + items + payments + installments
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/alembic/versions/057_treatment_plan_installments.py` | Create | New table + FK on payments |
| `orchestrator_service/models.py` | Modify | Add `TreatmentPlanInstallment` class after line 1773 |
| `orchestrator_service/schemas/treatment_plan.py` | Modify | Add `InstallmentStatus` enum, `GenerateInstallmentsBody`, `UpdateInstallmentBody`, `InstallmentResponse`. Modify `RegisterPaymentBody` (+installment_id), `TreatmentPlanPaymentResponse` (+installment_id, +installment_number), `TreatmentPlanDetailResponse` (+installments array + counts) |
| `orchestrator_service/admin_routes.py` | Modify | Add 4 endpoints: generate, list, update, delete installments. Modify `register_plan_payment` to handle installment linking |
| `frontend_react/src/components/BillingTab.tsx` | Modify | (1) Add `TreatmentPlanInstallment` interface. (2) Add installment grid section. (3) Modify payment modal with installment selector. (4) Nav fix: reset `selectedPlanId` in patientId useEffect |
| `frontend_react/src/locales/es.json` | Modify | Add installment i18n keys |
| `frontend_react/src/locales/en.json` | Modify | Add installment i18n keys |

## Interfaces / Contracts

### Migration 057 DDL

```sql
CREATE TABLE treatment_plan_installments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES treatment_plans(id) ON DELETE CASCADE,
    installment_number INTEGER NOT NULL CHECK (installment_number > 0),
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    due_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'paid')),
    paid_at TIMESTAMPTZ,
    payment_id UUID REFERENCES treatment_plan_payments(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (plan_id, installment_number)
);
CREATE INDEX idx_installments_tenant_plan ON treatment_plan_installments(tenant_id, plan_id);
CREATE INDEX idx_installments_status ON treatment_plan_installments(tenant_id, status);

ALTER TABLE treatment_plan_payments
    ADD COLUMN installment_id UUID REFERENCES treatment_plan_installments(id) ON DELETE SET NULL;
```

Note: `status` column stores only `pending` | `paid`. `overdue` is computed at read time via `CASE WHEN due_date < CURRENT_DATE AND status = 'pending' THEN 'overdue' ELSE status END`.

### Backend schemas (new/modified)

```python
class InstallmentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"  # computed, never stored

class GenerateInstallmentsBody(BaseModel):
    count: int = Field(..., ge=1, le=24)
    start_date: date
    frequency: str = Field(..., pattern="^(monthly|biweekly|weekly|custom)$")
    custom_amounts: Optional[List[Decimal]] = None

class UpdateInstallmentBody(BaseModel):
    due_date: Optional[date] = None
    amount: Optional[Decimal] = Field(None, gt=0)

class InstallmentResponse(BaseModel):
    id: str
    installment_number: int
    amount: Decimal
    due_date: date
    status: str  # pending | paid | overdue (computed)
    paid_at: Optional[datetime]
    payment_id: Optional[str]

# Modified: RegisterPaymentBody adds:
    installment_id: Optional[str] = None

# Modified: TreatmentPlanPaymentResponse adds:
    installment_id: Optional[str] = None
    installment_number: Optional[int] = None

# Modified: TreatmentPlanDetailResponse adds:
    installments: List[InstallmentResponse] = []
    installments_count: int = 0
    installments_paid_count: int = 0
    next_due_date: Optional[date] = None
```

### Frontend type

```typescript
interface TreatmentPlanInstallment {
  id: string;
  installment_number: number;
  amount: number;
  due_date: string;
  status: 'pending' | 'paid' | 'overdue';
  paid_at: string | null;
  payment_id: string | null;
}
```

## Nav Bug Fix

**Root cause**: `selectedPlanId` (line 279) is NOT reset when `patientId` changes. The `useEffect` at line 345 re-fetches billing summary but `selectedPlanId` stays stale from Patient A. When plan detail loads, it may 404 or show wrong data.

**Fix**: Add to the `useEffect` at line 345:
```typescript
useEffect(() => {
    setSelectedPlanId(null);  // ← ADD THIS
    setPlanDetail(null);       // ← ADD THIS
    loadBillingSummary();
}, [patientId, refreshKey]);
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Generate installments (equal split, custom, remainder) | pytest — pure function, no DB |
| Integration | CRUD endpoints + payment linking | pytest with test DB |
| Integration | Overdue computation | pytest with past due_date |
| Manual QA | BillingTab nav fix + installment grid | Browser testing |

## Migration / Rollout

`alembic upgrade head` auto-runs on startup via `start.sh`. No data migration needed (D3 decision). Existing plans continue working — installments are additive. `installment_id` nullable on payments preserves backwards compat.

## Open Questions

None — all decisions resolved.
