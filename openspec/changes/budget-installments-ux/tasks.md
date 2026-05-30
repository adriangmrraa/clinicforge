# Tasks: Budget Installments & UX (DLD-20 + DLD-27)

## Phase 1: Database & Models

- [ ] 1.1 Create `orchestrator_service/alembic/versions/057_treatment_plan_installments.py` — DDL from design.md: `treatment_plan_installments` table (UUID pk, tenant_id FK, plan_id FK, installment_number, amount, due_date, status CHECK pending|paid, paid_at, payment_id FK, timestamps, UNIQUE plan_id+number, indexes) + `installment_id` FK column on `treatment_plan_payments`. Include upgrade() and downgrade().
- [ ] 1.2 Add `TreatmentPlanInstallment` class in `orchestrator_service/models.py` after line 1773. Follow TreatmentPlanPayment pattern. Add `installments` relationship to `TreatmentPlan` model. Add `installment_id` + `installment` relationship to `TreatmentPlanPayment`.

## Phase 2: Schemas

- [ ] 2.1 Add to `orchestrator_service/schemas/treatment_plan.py`: `InstallmentStatus` enum (pending|paid|overdue), `GenerateInstallmentsBody` (count 1-24, start_date, frequency, custom_amounts), `UpdateInstallmentBody` (due_date, amount), `InstallmentResponse` (id, number, amount, due_date, status, paid_at, payment_id).
- [ ] 2.2 Modify `RegisterPaymentBody` — add `installment_id: Optional[str] = None`.
- [ ] 2.3 Modify `TreatmentPlanPaymentResponse` — add `installment_id: Optional[str]`, `installment_number: Optional[int]`.
- [ ] 2.4 Modify `TreatmentPlanDetailResponse` — add `installments: List[InstallmentResponse]`, `installments_count: int`, `installments_paid_count: int`, `next_due_date: Optional[date]`.
- [ ] 2.5 Export new schemas from `orchestrator_service/schemas/__init__.py`.

## Phase 3: Backend Endpoints

- [ ] 3.1 Add `POST /admin/treatment-plans/{plan_id}/installments/generate` in `admin_routes.py` — validate plan status (approved|in_progress), check no paid installments exist (409), delete pending installments, generate N records with equal split (last absorbs remainder) or custom_amounts, compute due_dates by frequency. (REQ-INST-02)
- [ ] 3.2 Add `GET /admin/treatment-plans/{plan_id}/installments` — query with `CASE WHEN due_date < CURRENT_DATE AND status = 'pending' THEN 'overdue' ELSE status END`, ORDER BY installment_number. (REQ-INST-03, REQ-INST-05)
- [ ] 3.3 Add `PATCH /admin/treatment-plan-installments/{id}` — reject if status=paid (409), update due_date/amount on pending only. (REQ-INST-04)
- [ ] 3.4 Add `DELETE /admin/treatment-plans/{plan_id}/installments` — delete all pending installments, reject if any paid (409).
- [ ] 3.5 Modify `register_plan_payment` endpoint — accept `installment_id`, validate installment is pending (409 if paid), after payment INSERT: UPDATE installment set status=paid, paid_at=NOW(), payment_id. Set installment_id on payment record. (REQ-PAY-01)
- [ ] 3.6 Modify `get_treatment_plan_detail` endpoint — JOIN installments with overdue CASE, add installments array + installments_count + installments_paid_count + next_due_date to response. (REQ-DETAIL-01)

## Phase 4: Frontend

- [ ] 4.1 **Nav fix** in `BillingTab.tsx` line 345 useEffect — add `setSelectedPlanId(null); setPlanDetail(null);` before `loadBillingSummary()`. (REQ-NAV-01)
- [ ] 4.2 Add `TreatmentPlanInstallment` interface to BillingTab.tsx types section. Extend `TreatmentPlanDetail` with `installments`, `installments_count`, `installments_paid_count`, `next_due_date`.
- [ ] 4.3 Add installment grid section in plan_view — render after payments section. Each row: cuota number, amount (formatCurrency), due_date, status badge (pending=amber, paid=green, overdue=red), pay button on pending/overdue. Add "Generar cuotas" button when no installments. (REQ-UI-INST-01)
- [ ] 4.4 Add generate installments modal — inputs: count (1-24), start_date, frequency (monthly|biweekly|weekly|custom). Calls POST generate endpoint. Refreshes plan detail on success.
- [ ] 4.5 Modify payment registration modal — add installment selector dropdown. Options: pending/overdue installments labeled "Cuota N — $X — Vence DD/MM" + "Pago libre". Auto-fill amount on selection. Pass installment_id in POST body. (REQ-UI-INST-02)
- [ ] 4.6 Add i18n keys to `es.json`, `en.json`, `fr.json` — installment.generate, installment.cuota, installment.due_date, installment.overdue, installment.paid, installment.pending, installment.free_payment, installment.count, installment.frequency, installment.monthly, installment.biweekly, installment.weekly, installment.custom, installment.no_installments, installment.generate_title, installment.cannot_regenerate.

## Phase 5: Testing

- [ ] 5.1 Unit test: installment amount calculation — equal split with remainder, custom amounts validation (sum != approved_total → error).
- [ ] 5.2 Integration test: generate → list → pay → verify status transitions. Cover REQ-INST-02 scenarios (draft rejection, regenerate with paid block).
- [ ] 5.3 Integration test: overdue computation — create installment with past due_date, verify GET returns status=overdue.
