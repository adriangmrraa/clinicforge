# Verification Report

**Change**: budget-installments-ux (DLD-20 + DLD-27)
**Mode**: Standard (no test runner available for integration tests)

---

## Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 22 |
| Tasks complete (structurally verified) | 19 |
| Tasks incomplete | 3 (Phase 5: testing — 5.1, 5.2, 5.3) |

Phase 5 testing tasks (unit + integration tests) were not written. No test files exist for this change.

---

## Correctness (Static — Structural Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| REQ-INST-01: Installment Entity | ✅ Implemented | Migration 058 creates table with all columns, CHECK constraints, UNIQUE, indexes. Model in models.py:1790 matches. |
| REQ-INST-02: Auto-Generate | ✅ Implemented | POST endpoint at admin_routes.py:14812. Validates plan status (400), checks paid (409), equal split with remainder, custom amounts with sum validation, frequency-based dates (monthly/biweekly/weekly/custom). |
| REQ-INST-03: List Installments | ✅ Implemented | GET endpoint at admin_routes.py:14956. Ordered by installment_number ASC with overdue CASE. |
| REQ-INST-04: Update Installment | ✅ Implemented | PATCH endpoint at admin_routes.py:15033. Rejects paid (409), dynamic SET clause. |
| REQ-INST-05: Overdue Detection | ✅ Implemented | SQL CASE in both list (14994) and plan detail (13520) queries. Never stored — computed at read time. |
| REQ-PAY-01: Payment + Installment | ✅ Implemented | register_plan_payment modified (14500-14580). Validates installment ownership + status, marks paid in transaction. |
| REQ-PAY-02: Payment Response | ✅ Implemented | Schema has installment_id + installment_number. Payment INSERT includes installment_id. |
| REQ-DETAIL-01: Plan Detail | ✅ Implemented | installments array + installments_count + installments_paid_count + next_due_date in response (13550-13592). |
| REQ-NAV-01: Navigation Fix | ✅ Implemented | BillingTab.tsx:367-368 resets selectedPlanId and planDetail on patientId change. |
| REQ-UI-INST-01: Installment Grid | ✅ Implemented | Grid with status badges (amber/green/red), pay button on pending/overdue. |
| REQ-UI-INST-02: Payment Modal Selector | ✅ Implemented | Dropdown with installment options + "Pago libre". Auto-fill amount. openPaymentModalForInstallment function. |

---

## Coherence (Design Decisions)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| D1: Overdue computed via SQL CASE | ✅ Yes | CASE in both list + detail queries |
| D2: Logic inline in admin_routes.py | ✅ Yes | All endpoints in admin_routes.py, no new service file |
| D3: No data migration for existing plans | ✅ Yes | No migration of JSON notes data |
| D4: Bidirectional FKs | ✅ Yes | installment.payment_id + payment.installment_id |

---

## Sovereignty Protocol (tenant_id)

All 12 SQL queries against treatment_plan_installments include `AND tenant_id = $N`. ✅ Compliant.

---

## i18n

| Locale | Keys | Status |
|--------|------|--------|
| es.json | 14 installment keys | ✅ |
| en.json | 14 installment keys | ✅ |
| fr.json | 14 installment keys | ✅ |

---

## Migration

| Check | Status |
|-------|--------|
| upgrade() present | ✅ |
| downgrade() present | ✅ |
| down_revision = "057" | ✅ (correct chain) |
| Table with all constraints | ✅ |
| Indexes created | ✅ (2 indexes) |
| FK on payments added | ✅ |

---

## Issues Found

**CRITICAL**: None

**WARNING**:
- W1: Phase 5 testing tasks (5.1, 5.2, 5.3) not implemented — no test files for installment logic.

**SUGGESTION**:
- S1: Consider adding `fr.json` to the affected areas list in design.md (was missing, but implemented correctly).

---

## Verdict

**PASS WITH WARNINGS**

All 11 spec requirements implemented and structurally verified. All design decisions followed. Sovereignty protocol respected. Migration correct with upgrade/downgrade. Frontend nav fix applied. i18n complete in 3 locales. Only gap: no automated tests written (Phase 5).
