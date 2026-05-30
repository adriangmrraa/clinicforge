# Proposal: Budget Installments & UX (DLD-20 + DLD-27)

## Intent

The secretary cannot track individual installment payments or navigate the budget view reliably. DLD-20 asks for payment method on budgets (already exists). DLD-27 asks for installments, manual payment marking, and account summaries. Real gap: installments exist only as a number in JSON — no per-installment tracking, due dates, or status.

## Scope

### In Scope
- **New `treatment_plan_installments` table** with per-installment tracking (number, amount, due_date, status, linked payment)
- **Auto-generate installments** when configuring cuotas on an approved plan
- **Installment UI in BillingTab** — visual grid showing each cuota with status, due date, pay button
- **Navigation fix** — resolve "stuck" state in BillingTab.tsx after plan creation
- **Installment-aware payment registration** — link payments to specific installments
- **Overdue detection** — mark installments past due_date as overdue

### Out of Scope
- Interest calculation on overdue installments (future)
- Automatic payment reminders via WhatsApp (future)
- Restructuring the 2600-line BillingTab into sub-components (tech debt, separate PR)

## Approach

1. **Migration 057**: Create `treatment_plan_installments` table + add `installment_id` FK on `treatment_plan_payments`
2. **Backend**: CRUD endpoints for installments, auto-generation on plan approval with installments config, overdue cron job
3. **Frontend**: Installment grid in BillingTab, payment-to-installment linking in payment modal, navigation state fix

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `orchestrator_service/models.py` | New | `TreatmentPlanInstallment` model |
| `orchestrator_service/alembic/versions/057_*` | New | Migration for installments table |
| `orchestrator_service/admin_routes.py` | Modified | Installment CRUD + auto-generation logic |
| `orchestrator_service/schemas/treatment_plan.py` | Modified | Installment schemas |
| `frontend_react/src/components/BillingTab.tsx` | Modified | Installment UI + navigation fix |
| `frontend_react/src/types/finance.ts` | Modified | `TreatmentPlanInstallment` type |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| BillingTab regression (2600 lines) | High | Focused changes, manual QA on create/edit/navigate flows |
| Existing plans with JSON installments | Medium | Migration script auto-generates installment records from existing config |
| Payment linking backwards compat | Low | `installment_id` is nullable on payments — existing payments unaffected |

## Rollback Plan

1. `alembic downgrade -1` removes the installments table and FK
2. Frontend: revert BillingTab changes — old JSON-based installments still work
3. No data loss: existing `treatment_plan_payments` untouched

## Dependencies

- Current alembic head: `056_add_delivery_status_chat_messages`
- No external dependencies

## Success Criteria

- [ ] Secretary can configure N installments with due dates on a treatment plan
- [ ] Each installment shows status (pending/paid/overdue) in the UI
- [ ] Payments can be linked to a specific installment
- [ ] Budget view navigation works without getting stuck
- [ ] Existing plans/payments continue working (backwards compatible)
