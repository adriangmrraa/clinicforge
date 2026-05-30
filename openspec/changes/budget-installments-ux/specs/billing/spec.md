# Delta for Billing — Installments & UX (DLD-20 + DLD-27)

## ADDED Requirements

### REQ-INST-01: Installment Entity

The system MUST store installments as individual records in `treatment_plan_installments` with: `id` (UUID), `tenant_id`, `plan_id`, `installment_number` (INT >0), `amount` (NUMERIC 12,2 >0), `due_date` (DATE), `status` (pending|paid|overdue), `paid_at` (TIMESTAMPTZ nullable), `payment_id` (FK nullable), `created_at`, `updated_at`.

UNIQUE constraint: `(plan_id, installment_number)`. Every query MUST filter by `tenant_id`.

#### Scenario: Installment record structure

- GIVEN a treatment plan exists with status "approved"
- WHEN installments are generated
- THEN each installment record has a sequential number, calculated amount, and due_date
- AND status defaults to "pending", paid_at is null

### REQ-INST-02: Auto-Generate Installments

The system MUST provide `POST /admin/treatment-plans/{plan_id}/installments/generate` accepting: `count` (1-24), `start_date` (DATE), `frequency` (monthly|biweekly|weekly|custom), `custom_amounts` (optional list of amounts).

Equal split: `approved_total / count` (last cuota absorbs remainder). Custom: each amount from `custom_amounts`, sum MUST equal `approved_total`.

#### Scenario: Generate 3 monthly installments

- GIVEN plan approved_total = $45,000 and status = "approved" or "in_progress"
- WHEN POST generate with count=3, start_date=2026-05-01, frequency=monthly
- THEN 3 installments created: #1 $15,000 due 2026-05-01, #2 $15,000 due 2026-06-01, #3 $15,000 due 2026-07-01

#### Scenario: Generate with custom amounts

- GIVEN plan approved_total = $50,000
- WHEN POST generate with count=2, custom_amounts=[30000, 20000]
- THEN installment #1 = $30,000, #2 = $20,000

#### Scenario: Reject generation on draft plan

- GIVEN plan status = "draft"
- WHEN POST generate
- THEN 400 error: "Plan must be approved before generating installments"

#### Scenario: Regenerate replaces existing

- GIVEN plan already has 3 installments (all pending)
- WHEN POST generate with count=4
- THEN old installments deleted, 4 new ones created

#### Scenario: Block regenerate with paid installments

- GIVEN plan has installment #1 with status=paid
- WHEN POST generate
- THEN 409 error: "Cannot regenerate — installments with payments exist"

### REQ-INST-03: List Installments

`GET /admin/treatment-plans/{plan_id}/installments` MUST return all installments ordered by `installment_number` ASC.

#### Scenario: List installments

- GIVEN plan has 3 installments
- WHEN GET installments
- THEN returns array of 3 ordered by number, each with amount, due_date, status, payment_id

### REQ-INST-04: Update Installment

`PATCH /admin/treatment-plan-installments/{id}` MUST allow updating `due_date` and `amount` on pending installments only.

#### Scenario: Update due date on pending installment

- GIVEN installment status = "pending"
- WHEN PATCH with due_date = 2026-06-15
- THEN due_date updated, updated_at refreshed

#### Scenario: Reject update on paid installment

- GIVEN installment status = "paid"
- WHEN PATCH with due_date = 2026-07-01
- THEN 409 error: "Cannot modify a paid installment"

### REQ-INST-05: Overdue Detection

The system MUST mark installments as "overdue" when `due_date < today AND status = 'pending'`. This SHOULD run at plan detail retrieval time (computed, not stored).

#### Scenario: Installment past due

- GIVEN installment due_date = 2026-04-15, today = 2026-04-22, status = "pending"
- WHEN GET plan detail or GET installments
- THEN installment status returned as "overdue"

## MODIFIED Requirements

### REQ-PAY-01: Payment Registration (Modified)

`POST /admin/treatment-plans/{plan_id}/payments` MUST accept optional `installment_id` field. When provided, the system MUST set the installment's `status=paid`, `paid_at=now()`, and `payment_id` to the new payment's id.

(Previously: payments were free-form with no installment linkage)

#### Scenario: Pay a specific installment

- GIVEN plan has installment #2 with status=pending, amount=$15,000
- WHEN POST payment with amount=15000, payment_method=transfer, installment_id={inst2_id}
- THEN payment created, installment #2 status=paid, paid_at set, payment_id linked

#### Scenario: Free payment (no installment)

- GIVEN plan has installments
- WHEN POST payment with amount=5000, payment_method=cash, installment_id=null
- THEN payment created, no installment affected (backwards compatible)

#### Scenario: Reject payment on already-paid installment

- GIVEN installment #1 status = "paid"
- WHEN POST payment with installment_id={inst1_id}
- THEN 409 error: "Installment already paid"

### REQ-PAY-02: Payment Response (Modified)

`TreatmentPlanPaymentResponse` MUST include `installment_id` (nullable) and `installment_number` (nullable, computed).

(Previously: no installment reference in payment response)

### REQ-DETAIL-01: Plan Detail Response (Modified)

`TreatmentPlanDetailResponse` MUST include `installments` array alongside `items` and `payments`. Also MUST include `installments_count`, `installments_paid_count`, `next_due_date` (earliest pending/overdue due_date or null).

(Previously: no installments array in detail response)

### REQ-NAV-01: BillingTab Navigation Fix

The BillingTab component MUST properly reset state when navigating away from plan_view. Creating a plan and pressing back MUST NOT leave the view in a stuck state.

#### Scenario: Create plan and navigate back

- GIVEN user is on patient detail, billing tab, empty state
- WHEN user creates a plan, then clicks back/navigates to another patient
- THEN view resets cleanly to the new patient's billing state

#### Scenario: Switch between patients

- GIVEN user is viewing Patient A's plan
- WHEN user navigates to Patient B
- THEN BillingTab resets and loads Patient B's data (no stale state from A)

## Frontend Specs

### REQ-UI-INST-01: Installment Grid

BillingTab MUST render an installment grid when the plan has installments. Each row shows: cuota number, amount, due_date (formatted), status badge (pending=amber, paid=green, overdue=red), pay button (only if pending/overdue).

#### Scenario: Display installment grid

- GIVEN plan has 3 installments: #1 paid, #2 pending, #3 pending (due future)
- WHEN viewing plan detail
- THEN grid shows 3 rows with correct status badges and pay button only on #2 and #3

### REQ-UI-INST-02: Payment Modal Installment Selector

The payment registration modal MUST include a dropdown to select which installment to pay. Options: each pending/overdue installment labeled "Cuota N — $X — Vence DD/MM" plus "Pago libre" for unlinked payments. Selecting an installment SHOULD auto-fill the amount field.

#### Scenario: Select installment in payment modal

- GIVEN user clicks "Registrar pago" on installment #2 ($15,000, due 2026-06-01)
- WHEN payment modal opens
- THEN installment #2 is pre-selected, amount auto-filled with $15,000
