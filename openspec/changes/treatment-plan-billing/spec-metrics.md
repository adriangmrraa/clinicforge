# Spec: Metrics & Analytics Integration — Treatment Plan Billing

**Change**: treatment-plan-billing
**Spec module**: metrics
**Status**: Draft
**Date**: 2026-04-03
**Depends on**: `spec-database.md` (tables: `treatment_plans`, `treatment_plan_items`, `treatment_plan_payments`)

---

## 1. Overview

This spec covers every metric surface that must be updated to incorporate treatment plan payments as a first-class financial source. There are four distinct surfaces:

| Surface | File | Function |
|---------|------|----------|
| Dashboard KPIs | `admin_routes.py` | `get_dashboard_stats()` |
| Liquidation (professional settlements) | `analytics_service.py` | `AnalyticsService.get_professionals_liquidation()` |
| ROI Dashboard | `services/metrics_service.py` | `MetricsService._get_billing_revenue()` |
| Nova voice tools | `services/nova_tools.py` | `_resumen_financiero()`, `_facturacion_pendiente()`, `_registrar_pago()` |

### Non-goals

- Do not change how `accounting_transactions` is queried for `total_revenue` — plan payments already sync there by design (see proposal). No query change is required for that KPI.
- Do not add new API endpoints in this spec — metrics changes are internal query changes.
- No frontend changes — all metric data is already consumed via existing response shapes.

---

## 2. Backward Compatibility Contract (MANDATORY)

This is the single most critical rule. **Every query change must preserve behavior for legacy appointments.**

| Condition | Billing source | Rule |
|-----------|---------------|------|
| `appointments.plan_item_id IS NULL` | `appointments.billing_amount` / `payment_status` | No change. Existing logic is untouched. |
| `appointments.plan_item_id IS NOT NULL` | `treatment_plan_payments` aggregated at plan level | The appointment-level `billing_amount` / `payment_status` is ignored for financial aggregations. |

**Why this matters**: The migration adds `plan_item_id` as a nullable FK. Existing appointments will always have `plan_item_id = NULL`. Any metric query that doesn't filter on this column will get the same result as before — this is intentional. The changes below only ADD new subqueries for the plan path; they do not modify the legacy path.

---

## 3. Dashboard KPIs

### 3.1 Metric: `pending_payments`

**Current query** (line 2287–2296, `admin_routes.py`):
```sql
SELECT COALESCE(SUM(billing_amount), 0)
FROM appointments
WHERE tenant_id = $1
  AND payment_status IN ('pending', 'partial')
  AND status NOT IN ('cancelled')
```

**Problem**: This query correctly captures appointment-level pending payments. But once a plan exists, the pending balance is at the plan level — `approved_total` minus `SUM(treatment_plan_payments.amount)`. An appointment linked to a plan has no meaningful `billing_amount` of its own; it would be NULL or 0.

**Required change**: Replace with a UNION approach that sums both sources.

**New query**:
```sql
SELECT
    COALESCE(legacy_pending.amount, 0) + COALESCE(plan_pending.amount, 0)
FROM
    -- Source 1: legacy appointments (no plan)
    (
        SELECT COALESCE(SUM(a.billing_amount), 0) AS amount
        FROM appointments a
        WHERE a.tenant_id = $1
          AND a.plan_item_id IS NULL
          AND a.payment_status IN ('pending', 'partial')
          AND a.status NOT IN ('cancelled')
    ) AS legacy_pending,
    -- Source 2: approved plans with outstanding balance
    (
        SELECT COALESCE(
            SUM(
                tp.approved_total
                - COALESCE(paid.total_paid, 0)
            ), 0
        ) AS amount
        FROM treatment_plans tp
        LEFT JOIN (
            SELECT plan_id, SUM(amount) AS total_paid
            FROM treatment_plan_payments
            WHERE tenant_id = $1
            GROUP BY plan_id
        ) paid ON paid.plan_id = tp.id
        WHERE tp.tenant_id = $1
          AND tp.status IN ('approved', 'in_progress')
          AND tp.approved_total IS NOT NULL
          AND (tp.approved_total - COALESCE(paid.total_paid, 0)) > 0
    ) AS plan_pending
```

**Backward compatibility**: `plan_item_id IS NULL` filter on Source 1 guarantees legacy appointments contribute only to the legacy total. If no plans exist, `plan_pending.amount = 0`.

**Edge case**: A plan in `draft` status has no `approved_total` yet — it is excluded (`tp.status IN ('approved', 'in_progress')`). A plan in `completed` or `cancelled` status is excluded. This is intentional: pending balance only accrues on active plans.

---

### 3.2 Metric: `today_revenue`

**Current query** (line 2299–2310, `admin_routes.py`):
```sql
SELECT COALESCE(SUM(billing_amount), 0)
FROM appointments
WHERE tenant_id = $1
  AND payment_status = 'paid'
  AND DATE(appointment_datetime AT TIME ZONE 'America/Argentina/Buenos_Aires') = CURRENT_DATE
```

**Problem**: Plan payments are not tied to an appointment datetime — they are recorded via `treatment_plan_payments.payment_date`. A plan payment made today is invisible to this query.

**Required change**: UNION with plan payments made today.

**New query**:
```sql
SELECT
    COALESCE(legacy_today.amount, 0) + COALESCE(plan_today.amount, 0)
FROM
    -- Source 1: legacy paid appointments today
    (
        SELECT COALESCE(SUM(a.billing_amount), 0) AS amount
        FROM appointments a
        WHERE a.tenant_id = $1
          AND a.plan_item_id IS NULL
          AND a.payment_status = 'paid'
          AND DATE(a.appointment_datetime AT TIME ZONE 'America/Argentina/Buenos_Aires') = CURRENT_DATE
    ) AS legacy_today,
    -- Source 2: plan payments recorded today
    (
        SELECT COALESCE(SUM(tpp.amount), 0) AS amount
        FROM treatment_plan_payments tpp
        WHERE tpp.tenant_id = $1
          AND DATE(tpp.payment_date AT TIME ZONE 'America/Argentina/Buenos_Aires') = CURRENT_DATE
    ) AS plan_today
```

**Backward compatibility**: Same as above — `plan_item_id IS NULL` isolates legacy appointments. If no `treatment_plan_payments` table exists (pre-migration), the query fails — this is expected, the migration must run first.

---

### 3.3 Metric: `total_revenue`

**Current query** (line 2155–2164, `admin_routes.py`):
```sql
SELECT COALESCE(SUM(at.amount), 0)
FROM accounting_transactions at
WHERE at.tenant_id = $1
  AND at.transaction_type = 'payment'
  AND at.status = 'completed'
  AND at.created_at >= CURRENT_DATE - {interval_expr}
```

**No change required.** Per the proposal, every `treatment_plan_payment` insertion creates a corresponding `accounting_transaction` row (with `transaction_type = 'payment'`, `status = 'completed'`). This sync happens in the `POST /admin/treatment-plans/{plan_id}/payments` endpoint. Therefore, `total_revenue` automatically includes plan payments once the sync is in place. The query is correct as-is.

**Verification requirement**: The implementation spec for the payments endpoint MUST guarantee the `accounting_transactions` insert is atomic with the `treatment_plan_payments` insert (single transaction, no partial writes).

---

### 3.4 Metric: `estimated_revenue`

**No change required.** This metric sums `treatment_types.base_price` for AI-sourced appointments. It is a forward-looking projection of appointment-level bookings, not a financial ledger. Treatment plans are a billing abstraction — they do not affect the appointment source or type.

---

## 4. Professional Liquidation

### 4.1 Current behavior

`AnalyticsService.get_professionals_liquidation()` (line 340–600, `analytics_service.py`):

1. Fetches all appointments in the date range with `COALESCE(a.billing_amount, tt.base_price, 0)` as revenue.
2. Groups by `(patient_id, treatment_code)` as a proxy for "treatment episode."
3. Computes `total_billed`, `total_paid`, `total_pending` per group.

**Problem**: For appointments in a plan, the `billing_amount` at appointment level is NULL (or 0 — the actual money lives in `treatment_plan_payments`). The grouping key `(patient_id, treatment_code)` also loses the plan context — two different plans with the same treatment code for the same patient would merge into one group, which is incorrect.

### 4.2 Required changes

**Change A — New plan column in the base query**: Add `a.plan_item_id`, `tpi.plan_id`, and `tp.name AS plan_name` to the SELECT. Also add `tp.approved_total`.

**Base query delta**:
```sql
-- Add to SELECT:
a.plan_item_id,
tpi.plan_id,
tp.name AS plan_name,
tp.approved_total AS plan_approved_total,
tp.status AS plan_status

-- Add to FROM/JOINs (after the treatment_types LEFT JOIN):
LEFT JOIN treatment_plan_items tpi
    ON tpi.id = a.plan_item_id AND tpi.tenant_id = $1
LEFT JOIN treatment_plans tp
    ON tp.id = tpi.plan_id AND tp.tenant_id = $1
```

**Change B — Plan payments subquery**: After fetching appointment rows, also fetch aggregated plan payments for any plans visible in the result set.

```sql
-- Called after collecting all plan_ids from the appointment rows
SELECT plan_id,
       COALESCE(SUM(amount), 0) AS total_paid,
       COUNT(*) AS payment_count
FROM treatment_plan_payments
WHERE tenant_id = $1
  AND plan_id = ANY($2::uuid[])
GROUP BY plan_id
```

**Change C — Python aggregation split**:

The existing aggregation loop builds `(patient_id, treatment_code)` group keys. Split this into two paths:

```
for row in rows:
    if row["plan_item_id"] is not None:
        # Plan path: key = plan_id
        group_key = row["plan_id"]
        # billing comes from treatment_plan_payments, not billing_amount
    else:
        # Legacy path: key = (patient_id, treatment_code) — unchanged
        group_key = (row["patient_id"], row["treatment_code"])
```

**Plan group metadata**:
```python
{
    "type": "plan",               # NEW discriminator field
    "plan_id": plan_id,
    "plan_name": row["plan_name"],
    "plan_status": row["plan_status"],
    "patient_id": pat_id,
    "patient_name": ...,
    "approved_total": float(row["plan_approved_total"] or 0),
    "sessions": [],               # appointment rows in this plan
    "total_billed": float(plan_approved_total),   # = approved_total
    "total_paid": 0.0,            # filled from plan_payments subquery
    "total_pending": 0.0,         # = approved_total - total_paid
}
```

**Legacy group metadata** (unchanged shape):
```python
{
    "type": "appointment",        # NEW discriminator field
    # ... existing fields
}
```

**Change D — Populate plan payment totals**:

After building the group map, fetch plan payments and populate:
```python
plan_ids = [g["plan_id"] for g in groups if g["type"] == "plan"]
if plan_ids:
    payment_rows = await pool.fetch(plan_payments_query, tenant_id, plan_ids)
    payment_map = {r["plan_id"]: float(r["total_paid"]) for r in payment_rows}
    for g in groups:
        if g["type"] == "plan":
            paid = payment_map.get(g["plan_id"], 0.0)
            g["total_paid"] = paid
            g["total_pending"] = max(0.0, g["total_billed"] - paid)
```

### 4.3 Response shape change

The existing response shape per group is:
```json
{
  "patient_name": "...",
  "treatment_code": "...",
  "treatment_name": "...",
  "total_billed": 0.0,
  "total_paid": 0.0,
  "total_pending": 0.0,
  "sessions": []
}
```

Plan groups add:
```json
{
  "type": "plan",
  "plan_id": "uuid",
  "plan_name": "Rehabilitación oral completa",
  "plan_status": "in_progress",
  "approved_total": 150000.0,
  "total_billed": 150000.0,
  "total_paid": 75000.0,
  "total_pending": 75000.0,
  "sessions": [...]
}
```

Legacy groups add only `"type": "appointment"`. The `type` field is new but additive — the frontend can use it optionally.

**Backward compatibility**: Legacy groups are rendered with the same shape as before. Adding `"type"` is non-breaking (extra field). Plan groups are new rows that did not exist before.

---

## 5. ROI Dashboard

### 5.1 `MetricsService._get_billing_revenue()`

**Current query** (line 365–378, `services/metrics_service.py`):
```sql
SELECT COALESCE(SUM(billing_amount), 0)
FROM appointments
WHERE tenant_id = $1
  AND payment_status IN ('paid', 'partial')
  AND appointment_datetime >= $2::timestamp
  AND appointment_datetime <= $3::timestamp
```

**Problem**: Plan payments are not reflected in `appointments.billing_amount`. A patient who paid $150,000 via plan payments will show $0 here if their appointments have no `billing_amount`.

**Required change**: Add plan payments within the same date range. The `treatment_plan_payments.payment_date` is the correct temporal anchor (not `appointment_datetime`).

**New query**:
```python
async def _get_billing_revenue(tenant_id: int, date_from: str, date_to: str) -> float:
    try:
        # Source 1: legacy appointment billing
        appt_revenue = await db.pool.fetchval("""
            SELECT COALESCE(SUM(billing_amount), 0)
            FROM appointments
            WHERE tenant_id = $1
              AND plan_item_id IS NULL
              AND payment_status IN ('paid', 'partial')
              AND appointment_datetime >= $2::timestamp
              AND appointment_datetime <= $3::timestamp
        """, tenant_id, date_from, date_to)

        # Source 2: plan payments in the same date range
        plan_revenue = await db.pool.fetchval("""
            SELECT COALESCE(SUM(amount), 0)
            FROM treatment_plan_payments
            WHERE tenant_id = $1
              AND payment_date >= $2::timestamp
              AND payment_date <= $3::timestamp
        """, tenant_id, date_from, date_to)

        return float(appt_revenue or 0) + float(plan_revenue or 0)
    except Exception:
        return 0.0
```

**Backward compatibility**: The `plan_item_id IS NULL` filter on Source 1 ensures appointments in a plan don't double-count. If `treatment_plan_payments` does not exist (pre-migration), Source 2 raises an exception and the outer try/except returns 0.0 — same fallback behavior as before.

**Note on partial plan payments**: The current ROI query includes `payment_status IN ('paid', 'partial')` for appointments, which means it counts partial payments. Plan payments are always exact amounts — there is no `payment_status` on `treatment_plan_payments` (each row IS a payment). The full sum of plan payments in the range is the correct equivalent.

---

## 6. Nova Voice Tools

### 6.1 `_resumen_financiero()`

**Current behavior** (line 3877–3959, `services/nova_tools.py`):
- Queries `appointments` grouped by `appointment_type` and `professional_id`.
- Shows `total_revenue = SUM(billing_amount)` for the period.
- Shows `pending_payments` from appointments where `payment_status = 'pending'`.

**Required changes**:

**Change A — Add plan summary section**:

After the existing appointment queries, add:
```sql
SELECT
    tp.id AS plan_id,
    tp.name AS plan_name,
    tp.status AS plan_status,
    tp.approved_total,
    pat.first_name || ' ' || COALESCE(pat.last_name, '') AS patient_name,
    COALESCE(SUM(tpp.amount), 0) AS total_paid
FROM treatment_plans tp
JOIN patients pat ON pat.id = tp.patient_id AND pat.tenant_id = $1
LEFT JOIN treatment_plan_payments tpp
    ON tpp.plan_id = tp.id AND tpp.tenant_id = $1
    AND tpp.payment_date >= NOW() - INTERVAL '1 day' * $2
WHERE tp.tenant_id = $1
  AND tp.status IN ('approved', 'in_progress')
  AND tp.approved_total IS NOT NULL
GROUP BY tp.id, tp.name, tp.status, tp.approved_total, patient_name
ORDER BY tp.approved_total DESC
LIMIT 10
```

**Change B — Adjust `total_revenue` calculation**:

Current: `total_revenue = sum(float(r["revenue"]) for r in by_treatment)`
New:
```python
appt_revenue = sum(float(r["revenue"]) for r in by_treatment)
plan_revenue = sum(float(r["total_paid"]) for r in plan_rows)
total_revenue = appt_revenue + plan_revenue
```

**Change C — Add plan section to the response text**:

```python
if plan_rows:
    parts.append("\nPlanes de tratamiento activos:")
    for r in plan_rows:
        pending = float(r["approved_total"]) - float(r["total_paid"])
        pct = int(float(r["total_paid"]) / float(r["approved_total"]) * 100) if r["approved_total"] else 0
        parts.append(
            f"  - {r['patient_name']} — {r['plan_name']}: "
            f"${int(float(r['approved_total'])):,} total, "
            f"${int(float(r['total_paid'])):,} pagado ({pct}%), "
            f"${int(pending):,} pendiente"
        )
```

**Backward compatibility**: `plan_rows` will be empty if no plans exist. All existing text output is preserved; plan section appends at the end.

---

### 6.2 `_facturacion_pendiente()`

**Current behavior** (line 2171–2199, `services/nova_tools.py`):
- Queries `appointments` where `status = 'completed'` and `payment_status IN ('pending', NULL)`.
- Returns a list of 20 appointments with patient, type, date, and base_price.

**Problem**:
1. It queries `base_price` from `treatment_types` as a fallback price, but a plan appointment has neither `billing_amount` nor a meaningful standalone price — the price is at the plan level.
2. Active plans with outstanding balances are completely invisible to this tool.

**Required changes**:

**Change A — Filter out plan appointments from legacy query**:

Add `AND a.plan_item_id IS NULL` to the existing WHERE clause:
```sql
WHERE a.tenant_id = $1
  AND a.plan_item_id IS NULL           -- NEW: exclude plan appointments
  AND a.status = 'completed'
  AND (a.payment_status = 'pending' OR a.payment_status IS NULL)
ORDER BY a.appointment_datetime DESC
LIMIT 20
```

**Change B — Add plan pending query**:
```sql
SELECT
    tp.id AS plan_id,
    tp.name AS plan_name,
    tp.approved_total,
    COALESCE(SUM(tpp.amount), 0) AS total_paid,
    pat.first_name || ' ' || COALESCE(pat.last_name, '') AS patient_name
FROM treatment_plans tp
JOIN patients pat ON pat.id = tp.patient_id AND pat.tenant_id = $1
LEFT JOIN treatment_plan_payments tpp ON tpp.plan_id = tp.id AND tpp.tenant_id = $1
WHERE tp.tenant_id = $1
  AND tp.status IN ('approved', 'in_progress')
  AND tp.approved_total IS NOT NULL
GROUP BY tp.id, tp.name, tp.approved_total, patient_name
HAVING (tp.approved_total - COALESCE(SUM(tpp.amount), 0)) > 0
ORDER BY (tp.approved_total - COALESCE(SUM(tpp.amount), 0)) DESC
LIMIT 10
```

**Change C — Combine both in the response**:

```python
lines = [f"Facturacion pendiente:"]

if plan_rows:
    lines.append(f"\nPlanes con saldo pendiente ({len(plan_rows)}):")
    for r in plan_rows:
        balance = float(r["approved_total"]) - float(r["total_paid"])
        lines.append(
            f"• {r['patient_name']} — Plan '{r['plan_name']}': "
            f"${int(balance):,} pendiente de ${int(float(r['approved_total'])):,}"
        )

if appt_rows:
    lines.append(f"\nTurnos sin cobrar ({len(appt_rows)}):")
    for r in appt_rows:
        # ... existing logic
```

If both are empty: return `"No hay facturacion pendiente. Todo al dia."` (unchanged).

**Backward compatibility**: If no plans exist, `plan_rows` is empty and the output is identical to today.

---

### 6.3 `_registrar_pago()`

**Current behavior** (line 2097–2168, `services/nova_tools.py`):
- Requires `appointment_id`, `amount`, `method`.
- Updates `appointments.billing_amount` + `payment_status = 'paid'`.
- Inserts into `accounting_transactions`.

**Problem**: Nova cannot register a plan payment. If a patient asks "registrá un pago de $50,000 al plan de Adrian," the tool has no way to do it.

**Required change**: Accept `plan_id` as an alternative to `appointment_id`.

**New parameter logic**:

```python
appt_id = args.get("appointment_id")
plan_id = args.get("plan_id")
amount = args.get("amount")
method = args.get("method")

if not amount or not method:
    return "Necesito el monto y el método de pago."
if not appt_id and not plan_id:
    return "Necesito appointment_id o plan_id."
```

**Plan payment path**:
```python
if plan_id:
    try:
        plan_uuid = uuid.UUID(plan_id)
    except ValueError:
        return "ID de plan inválido."

    plan = await db.pool.fetchrow("""
        SELECT tp.id, tp.name, tp.approved_total,
               pat.first_name || ' ' || COALESCE(pat.last_name, '') AS patient_name,
               pat.id AS patient_id,
               COALESCE(SUM(tpp.amount), 0) AS total_paid
        FROM treatment_plans tp
        JOIN patients pat ON pat.id = tp.patient_id
        LEFT JOIN treatment_plan_payments tpp ON tpp.plan_id = tp.id
        WHERE tp.id = $1 AND tp.tenant_id = $2
        GROUP BY tp.id, tp.name, tp.approved_total, patient_name, pat.id
    """, plan_uuid, tenant_id)

    if not plan:
        return "No encontré ese plan de tratamiento."

    # Insert treatment_plan_payment
    payment_id = uuid.uuid4()
    await db.pool.execute("""
        INSERT INTO treatment_plan_payments
            (id, plan_id, tenant_id, amount, payment_method, payment_date,
             recorded_by, notes)
        VALUES ($1, $2, $3, $4, $5, NOW(), $6, $7)
    """, payment_id, plan_uuid, tenant_id,
         Decimal(str(amount)), method,
         args.get("recorded_by_user_id"),   # may be None
         args.get("notes"))

    # Sync to accounting_transactions
    await db.pool.execute("""
        INSERT INTO accounting_transactions
            (id, tenant_id, patient_id, transaction_type,
             amount, payment_method, description, status)
        VALUES ($1, $2, $3, 'payment', $4, $5, $6, 'completed')
    """, uuid.uuid4(), tenant_id, plan["patient_id"],
         Decimal(str(amount)), method,
         f"Pago plan '{plan['name']}' — registrado via Nova")

    remaining = float(plan["approved_total"] or 0) - float(plan["total_paid"]) - float(amount)
    method_label = {"cash": "efectivo", "card": "tarjeta", "transfer": "transferencia"}.get(method, method)
    await _nova_emit("PAYMENT_CONFIRMED", {"plan_id": str(plan_uuid), "tenant_id": tenant_id})
    return (
        f"Pago de {_fmt_money(amount)} en {method_label} registrado para el plan "
        f"'{plan['name']}' de {plan['patient_name']}. "
        f"Saldo restante: {_fmt_money(max(0, remaining))}."
    )
```

**Legacy appointment path**: unchanged from current implementation.

**Tool schema update** (Nova tool definition at line 328):
```json
{
  "name": "registrar_pago",
  "description": "Registra un pago para un turno o un plan de tratamiento.",
  "parameters": {
    "type": "object",
    "properties": {
      "appointment_id": {
        "type": "string",
        "description": "UUID del turno. Exclusivo con plan_id."
      },
      "plan_id": {
        "type": "string",
        "description": "UUID del plan de tratamiento. Exclusivo con appointment_id."
      },
      "amount": {
        "type": "number",
        "description": "Monto a registrar."
      },
      "method": {
        "type": "string",
        "enum": ["cash", "transfer", "card", "insurance"],
        "description": "Método de pago."
      },
      "notes": {
        "type": "string",
        "description": "Nota opcional."
      }
    },
    "required": ["amount", "method"]
  }
}
```

---

## 7. Functional Requirements

| ID | Surface | Requirement |
|----|---------|-------------|
| FM-01 | Dashboard | `pending_payments` MUST include outstanding balances from `approved` and `in_progress` treatment plans. |
| FM-02 | Dashboard | `pending_payments` MUST exclude appointments with `plan_item_id IS NOT NULL` to avoid double-counting. |
| FM-03 | Dashboard | `today_revenue` MUST include `treatment_plan_payments` with `payment_date = CURRENT_DATE`. |
| FM-04 | Dashboard | `total_revenue` MUST require no query change (guaranteed by accounting_transactions sync). |
| FM-05 | Dashboard | `estimated_revenue` MUST NOT change. |
| FM-06 | Liquidation | Appointments with `plan_item_id IS NOT NULL` MUST be grouped by `plan_id`, not `(patient_id, treatment_code)`. |
| FM-07 | Liquidation | Plan groups MUST use `treatment_plan_payments` total as `total_paid` and `approved_total` as `total_billed`. |
| FM-08 | Liquidation | Appointments without `plan_item_id` MUST continue using the existing grouping and `billing_amount` logic. |
| FM-09 | Liquidation | Response MUST include a `"type"` discriminator field (`"plan"` or `"appointment"`) per group. |
| FM-10 | ROI | `_get_billing_revenue()` MUST include plan payments dated within the requested range. |
| FM-11 | ROI | `_get_billing_revenue()` MUST exclude plan-linked appointments from the `appointments` sum. |
| FM-12 | Nova | `_resumen_financiero()` MUST include active plan totals and paid-to-date per plan. |
| FM-13 | Nova | `_resumen_financiero()` total revenue MUST sum appointment billing + plan payments. |
| FM-14 | Nova | `_facturacion_pendiente()` MUST include plans with outstanding balance. |
| FM-15 | Nova | `_facturacion_pendiente()` MUST exclude plan-linked appointments (they are covered by plan section). |
| FM-16 | Nova | `_registrar_pago()` MUST accept `plan_id` as an alternative to `appointment_id`. |
| FM-17 | Nova | Plan payment via `_registrar_pago()` MUST insert into both `treatment_plan_payments` AND `accounting_transactions` atomically. |
| FM-18 | All | All queries MUST include `tenant_id = $1` filter. No cross-tenant data leakage. |

---

## 8. Scenarios

### Scenario A — Pure legacy (no plans exist)

**Setup**: Tenant has 50 appointments, all with `plan_item_id = NULL`. No `treatment_plans` rows.

**Expected behavior**:
- `pending_payments`: Source 1 returns same value as today. Source 2 returns 0. Total = same as today.
- `today_revenue`: Source 1 returns same value as today. Source 2 returns 0. Total = same as today.
- Liquidation: All appointments take the legacy path. No plan groups. Output identical to today.
- `_get_billing_revenue()`: Source 1 = same. Source 2 = 0. Total = same.
- Nova tools: No plan rows appended. Output identical to today.

**Regression risk**: None. This is the safest scenario.

---

### Scenario B — Pure plan (all appointments in plans)

**Setup**: Tenant has 10 appointments, all with `plan_item_id IS NOT NULL`. Two plans: Plan A ($100,000 approved, $60,000 paid), Plan B ($80,000 approved, $0 paid).

**Expected behavior**:
- `pending_payments`:
  - Source 1 = 0 (all appointments are excluded by `plan_item_id IS NULL` filter)
  - Source 2 = ($100,000 - $60,000) + ($80,000 - $0) = $40,000 + $80,000 = $120,000
- `today_revenue`: depends on whether any plan payments have `payment_date = today`
- Liquidation: All appointments grouped by plan_id. Two plan groups, each with correct totals.
- `_facturacion_pendiente()`:
  - Legacy query returns 0 rows (all excluded by `plan_item_id IS NULL`)
  - Plan query returns Plan A ($40,000 pending) and Plan B ($80,000 pending)

---

### Scenario C — Mixed (the realistic case)

**Setup**: Tenant has 30 appointments total:
- 20 are legacy (`plan_item_id = NULL`), 5 paid, 15 pending
- 10 are in Plan A (`plan_item_id IS NOT NULL`). Plan A: $200,000 approved, $50,000 paid.
- Legacy appointments pending total: $45,000

**Expected behavior**:
- `pending_payments`:
  - Source 1: SUM(billing_amount) for 15 pending legacy appointments = $45,000
  - Source 2: $200,000 - $50,000 = $150,000
  - Total: $195,000

- `today_revenue`:
  - Source 1: paid legacy appointments today (e.g., $8,000)
  - Source 2: plan payments today (e.g., $20,000)
  - Total: $28,000

- Liquidation:
  - Legacy group per professional: 20 legacy appointments, grouped by (patient_id, treatment_code)
  - Plan group: 1 group for Plan A, sessions = 10 appointments, total_billed = $200,000, total_paid = $50,000

- `_get_billing_revenue()` for ROI:
  - Source 1: paid legacy appointments in date range
  - Source 2: plan payments in date range
  - Total = correct combined revenue

---

### Scenario D — Plan with partial payments (billing_amount on appointment exists)

**Setup**: An appointment has BOTH `plan_item_id IS NOT NULL` AND `billing_amount = 5000`. This would be a data migration artifact — the appointment had billing data before being linked to a plan.

**Expected behavior**:
- Dashboard `pending_payments`: Source 1 excludes this appointment (`plan_item_id IS NULL` filter). Source 2 picks up the plan. **No double-count.**
- Liquidation: Appointment takes plan path (plan_item_id IS NOT NULL wins). Its `billing_amount` is displayed in the session row for informational purposes only — it does NOT contribute to `total_billed` (plan totals come from `treatment_plan_payments`).
- ROI `_get_billing_revenue()`: Source 1 excludes this appointment. Plan payments cover it.

**Rule**: `plan_item_id IS NOT NULL` always takes precedence over `billing_amount` for financial aggregation. The `billing_amount` on a plan-linked appointment is a historical artifact — read-only for display.

---

### Scenario E — Plan in `draft` status (not yet approved)

**Setup**: Plan exists with `status = 'draft'`, `approved_total = NULL`.

**Expected behavior**:
- `pending_payments`: Plan excluded (`status NOT IN ('approved', 'in_progress')`). Correct — no commitment yet.
- Liquidation: Plan appointments grouped by plan_id, but `total_billed = 0` and `total_paid = 0`. Plan status shows as `draft`.
- Nova `_facturacion_pendiente()`: Plan excluded from pending list. Correct.
- Nova `_resumen_financiero()`: Plan excluded from active plans section.

**Rationale**: A draft plan has no financial commitment. It should appear in the patient view (Tab 6 UI) but not inflate financial metrics.

---

### Scenario F — Plan cancelled mid-treatment

**Setup**: Plan A had $100,000 approved and $30,000 paid. 3 of 10 appointments were completed. Plan is now `cancelled`.

**Expected behavior**:
- `pending_payments`: Plan excluded (`status NOT IN ('approved', 'in_progress')`). The $70,000 balance is not counted as pending.
- Liquidation: Plan group shows `plan_status = 'cancelled'`, `total_billed = $100,000`, `total_paid = $30,000`. It is included in the date range results (historical record) but can be visually flagged by the frontend with the `plan_status` field.
- Nova `_facturacion_pendiente()`: Excluded from pending. Correct.

---

## 9. Architectural Decisions

### AD-01: No new API endpoints for metrics

All changes are internal to query logic. The response shapes of existing endpoints are preserved (additive only). This avoids any frontend changes and keeps the migration risk minimal.

### AD-02: `plan_item_id IS NULL` as the universal discriminator

Using `plan_item_id IS NULL` as the filter for the legacy path is the only correct approach. Alternatives considered:

| Alternative | Problem |
|-------------|---------|
| Filter by `payment_status IS NOT NULL` | Plan appointments may still have payment_status set from before being linked |
| Filter by `billing_amount > 0` | Plan appointments may have billing_amount from before migration |
| Check if plan exists via subquery | Much more expensive; doesn't handle appointments linked to cancelled plans cleanly |

`plan_item_id IS NULL` is a structural FK field. It is NULL if and only if the appointment is not part of a plan. It cannot be set accidentally. It's the right discriminator.

### AD-03: `accounting_transactions` sync is mandatory, not optional

The `total_revenue` KPI (the primary revenue metric on the dashboard) reads from `accounting_transactions`. If plan payments are not synced there, they are invisible to the main revenue dashboard. The sync MUST happen atomically within the same database transaction as the `treatment_plan_payments` INSERT.

This means the payments endpoint (`POST /admin/treatment-plans/{plan_id}/payments`) must open a transaction, insert both rows, and commit. If the `accounting_transactions` insert fails, the plan payment insert must be rolled back.

### AD-04: Nova `_registrar_pago()` — plan path writes to `treatment_plan_payments`, NOT `appointments`

When a plan payment is registered via Nova, the write target is `treatment_plan_payments` (new table), not `appointments.billing_amount`. This is critical. Writing to `appointments` would create the double-count problem AD-01 is designed to prevent.

### AD-05: Plan payments in ROI use `payment_date`, not `appointment_datetime`

The `_get_billing_revenue()` date range is appointment-centric (based on when the appointments happened). Plan payments are made independently of appointments. Using `payment_date` is the correct temporal anchor — it represents when money actually changed hands, regardless of which appointment session triggered the payment.

### AD-06: Liquidation plan group uses `approved_total` as `total_billed`, not `SUM(session billing_amount)`

In the legacy path, `total_billed = SUM(COALESCE(billing_amount, base_price))` per session. For a plan, the correct `total_billed` is `approved_total` — the price the Dra. committed to after adjustment. Session-level prices are irrelevant once a plan is approved.

---

## 10. Files Affected

| File | Change type | Scope |
|------|-------------|-------|
| `orchestrator_service/admin_routes.py` | Modify | `get_dashboard_stats()` — `pending_payments` and `today_revenue` queries |
| `orchestrator_service/analytics_service.py` | Modify | `AnalyticsService.get_professionals_liquidation()` — base query, Python aggregation, response shape |
| `orchestrator_service/services/metrics_service.py` | Modify | `MetricsService._get_billing_revenue()` — add plan payments source |
| `orchestrator_service/services/nova_tools.py` | Modify | `_resumen_financiero()`, `_facturacion_pendiente()`, `_registrar_pago()`, tool schema for `registrar_pago` |

No frontend files require changes. No new files need to be created.

---

## 11. Testing Requirements

### Unit tests (pytest)

| Test | Description |
|------|-------------|
| `test_pending_payments_no_plans` | Tenant with legacy appointments only — `pending_payments` equals legacy sum. |
| `test_pending_payments_with_plans` | Tenant with plans — `pending_payments` includes plan balances, excludes plan-linked appointments from legacy sum. |
| `test_pending_payments_no_double_count` | Appointment with `plan_item_id IS NOT NULL` and `billing_amount > 0` — appears ONLY in plan source. |
| `test_today_revenue_includes_plan_payments` | Plan payment with `payment_date = today` — appears in `today_revenue`. |
| `test_billing_revenue_mixed` | `_get_billing_revenue()` with both legacy and plan data in range — sums both correctly. |
| `test_liquidation_plan_group` | Appointments with `plan_item_id` create a plan group with correct `total_billed` = `approved_total`. |
| `test_liquidation_legacy_unchanged` | Appointments without `plan_item_id` produce identical output to current behavior. |
| `test_liquidation_type_discriminator` | All groups include `"type"` field. Plan groups = `"plan"`, legacy groups = `"appointment"`. |
| `test_facturacion_pendiente_no_plans` | Legacy behavior preserved — plan-linked appointments excluded from legacy list. |
| `test_facturacion_pendiente_with_plans` | Plans with pending balance appear in the plan section. |
| `test_registrar_pago_by_plan_id` | Registering payment with `plan_id` writes to `treatment_plan_payments` AND `accounting_transactions`. |
| `test_registrar_pago_legacy_unchanged` | Registering payment with `appointment_id` (no `plan_id`) behaves identically to current logic. |
| `test_draft_plan_excluded_from_pending` | Plans with `status = 'draft'` do not appear in `pending_payments` or `_facturacion_pendiente()`. |
| `test_cancelled_plan_excluded_from_pending` | Plans with `status = 'cancelled'` do not inflate `pending_payments`. |
