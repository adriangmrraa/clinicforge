# Tasks: Financial Command Center

**Change:** `financial-command-center`
**Project:** `clinicforge`

---

## Execution Batches

| Batch | Phase | Tasks | Parallel? | Depends On |
|-------|-------|-------|-----------|------------|
| **Batch 1** | Phase 1 Foundation | T1.1, T1.2, T1.3, T1.4 | ✅ All parallel | None |
| **Batch 2** | Phase 1 Endpoints | T1.5, T1.6, T1.7, T1.8, T1.9, T1.10 | ✅ All parallel | Batch 1 |
| **Batch 3** | Phase 2 Frontend | T2.1, T2.2, T2.3, T2.4, T2.5, T2.6, T2.7, T2.8 | ✅ T2.1 first, then rest parallel | Batch 2 |
| **Batch 4** | Phase 3 PDF | T3.1, T3.2, T3.3, T3.4 | ✅ T3.1 first, then rest parallel | Batch 2 (T3.1), Batch 3 (T3.4) |
| **Batch 5** | Phase 4+5 Polish | T4.1, T4.2, T4.3, T5.1, T5.2, T5.3, T5.4, T5.5 | ✅ All parallel | Batch 4 |

---

## Phase 1: Foundation (Backend — DB + ORM + Services + Core Endpoints)

### T1.1: Create Alembic Migration 020

**Description:** Create `020_financial_command_center.py` migration with 3 new tables and all indexes.

**Tables to create:**
1. `professional_commissions` — commission rates per professional (default + per-treatment overrides)
2. `liquidation_records` — persistent liquidation snapshots with status tracking
3. `professional_payouts` — payment tracking to professionals

**Requirements:**
- All tables include `tenant_id` with FK to `tenants(id) ON DELETE CASCADE`
- `professional_commissions`: UNIQUE constraint on `(tenant_id, professional_id, treatment_code)`
- `liquidation_records`: UNIQUE constraint on `(tenant_id, professional_id, period_start, period_end)`
- `liquidation_records`: CHECK constraint on status IN ('draft', 'generated', 'approved', 'paid')
- `professional_payouts`: CHECK constraint on payment_method IN ('transfer', 'cash', 'check')
- All indexes include `tenant_id` as leading column
- Composite index on `liquidation_records(tenant_id, professional_id, period_start, period_end)` for idempotency
- Migration must be additive only — no ALTER TABLE on existing tables

**Files:**
- `orchestrator_service/alembic/versions/020_financial_command_center.py` (NEW)

**Dependencies:** None

**Estimated effort:** M

**Acceptance criteria:**
- [ ] `alembic upgrade head` executes without errors
- [ ] `alembic downgrade -1` reverts cleanly
- [ ] All 3 tables created with correct constraints
- [ ] All indexes created
- [ ] No modifications to existing tables

---

### T1.2: Add ORM Models to models.py

**Description:** Add 6 SQLAlchemy ORM models to `models.py` — 3 new financial models + 3 existing table models.

**New models (3):**
1. `ProfessionalCommission` → `professional_commissions` table
2. `LiquidationRecord` → `liquidation_records` table
3. `ProfessionalPayout` → `professional_payouts` table

**Existing table models (3):**
4. `TreatmentPlan` → `treatment_plans` table (exists in DB from migration 018, no ORM model yet)
5. `TreatmentPlanItem` → `treatment_plan_items` table
6. `TreatmentPlanPayment` → `treatment_plan_payments` table

**Requirements:**
- All models follow existing SQLAlchemy patterns in `models.py`
- Proper relationships: `professional`, `tenant`, `payouts`, `items`, `payments`
- Use `Numeric(12, 2)` for monetary columns, `Numeric(5, 2)` for percentages
- `DateTime(timezone=True)` for all timestamps
- `JSONB` for `notes` field on `LiquidationRecord`
- `UniqueConstraint` on `ProfessionalCommission` matching the DB constraint
- `back_populates` for bidirectional relationships

**Files:**
- `orchestrator_service/models.py` (MODIFIED — add 6 classes)

**Dependencies:** T1.1 (migration must exist first, but models can be written in parallel since they reference table names, not migration state)

**Estimated effort:** M

**Acceptance criteria:**
- [ ] All 6 models importable without errors
- [ ] Relationships work: `liquidation_record.payouts`, `plan.items`, `plan.payments`
- [ ] Column types match migration schema
- [ ] UniqueConstraint on ProfessionalCommission matches DB

---

### T1.3: Create liquidation_service.py

**Description:** Create `orchestrator_service/services/liquidation_service.py` with all liquidation business logic.

**Functions to implement:**

1. **`generate_liquidation(tenant_id, professional_id, period_start, period_end, generated_by)`**
   - Idempotent: return existing record if `(tenant_id, professional_id, period_start, period_end)` exists
   - Get professional commissions (default + per-treatment overrides)
   - Query appointments in period for professional (reuse logic from `analytics_service.get_professionals_liquidation`)
   - Include `treatment_plan_payments` associated with the professional
   - Calculate: `total_billed`, `total_paid`, `total_pending`
   - Apply commissions: per-treatment override or default; if no config, use 0% with warning log
   - `commission_amount` = SUM(billing_amount * commission_pct / 100)
   - `payout_amount` = commission_amount
   - Create `liquidation_record` with status='generated'
   - Add audit trail entry to `notes` JSONB

2. **`generate_bulk_liquidations(tenant_id, period_start, period_end, generated_by)`**
   - Get all active professionals: `SELECT id FROM professionals WHERE tenant_id=$1 AND is_active=true`
   - Call `generate_liquidation()` for each
   - Return array of created records + counts (generated_count, skipped_count)

3. **`get_liquidation_detail(tenant_id, liquidation_id)`**
   - Fetch `liquidation_record` verifying `tenant_id`
   - Re-execute appointment query for period to get current treatment groups
   - Return: liquidation_record + treatment_groups + payouts

4. **`update_liquidation_status(tenant_id, liquidation_id, new_status, updated_by, notes)`**
   - Validate transitions: draft→generated, generated→approved, approved→paid (reject jumps)
   - Update status + timestamp (approved_at, paid_at)
   - Add audit trail entry to `notes` JSONB array
   - If status='paid' and no payout exists, create auto-payout for `payout_amount`
   - Invalidate PDF cache

5. **`create_payout(tenant_id, liquidation_id, amount, payment_method, reference_number, notes, created_by)`**
   - Verify liquidation exists and belongs to tenant
   - Validate: amount > 0, payment_method in ['transfer', 'cash', 'check'], liquidation not in 'draft'
   - Create `professional_payout` record
   - Calculate total payouts: if `SUM(amounts) >= liquidation.payout_amount`, set status='paid'
   - Add audit trail entry to `notes`
   - Invalidate PDF cache

6. **`get_payouts_for_liquidation(tenant_id, liquidation_id)`**
   - Return all payouts for a liquidation, ordered by payment_date DESC

7. **`invalidate_liquidation_pdf(tenant_id, liquidation_id)`**
   - Delete cached PDF file at `/app/uploads/liquidations/{tenant_id}/{liquidation_id}.pdf`

**Requirements:**
- ALL queries must include `WHERE tenant_id = $1` filter (soberanía de datos)
- Use SQLAlchemy ORM for new models, raw SQL for existing tables (per AD-08)
- Proper error handling with HTTPException for: professional not found (404), invalid dates (400), invalid status transition (400)
- Warning log when no commission config found
- Audit trail format: `{"action": "...", "by": "...", "at": "...", ...}`

**Files:**
- `orchestrator_service/services/liquidation_service.py` (NEW)

**Dependencies:** T1.1, T1.2

**Estimated effort:** L

**Acceptance criteria:**
- [ ] Idempotent generation: call twice with same params → same record returned
- [ ] Calculations match `analytics_service.get_professionals_liquidation` for same period
- [ ] Empty period → liquidation with $0 totals, status='generated'
- [ ] No commission config → 0% with warning in logs
- [ ] Valid status transitions only
- [ ] Auto-complete to 'paid' when payouts cover payout_amount
- [ ] Audit trail entries in notes JSONB after each action
- [ ] PDF cache invalidated on status change and payout creation

---

### T1.4: Create financial_dashboard_service.py

**Description:** Create `orchestrator_service/services/financial_dashboard_service.py` with all financial aggregation logic.

**Functions to implement:**

1. **`get_financial_summary(tenant_id, period_start, period_end)`**
   - `total_revenue` = SUM(billing_amount) from appointments (completed/paid) + SUM(treatment_plan_payments.amount)
   - `total_payouts` = SUM(professional_payouts.amount)
   - `net_profit` = total_revenue - total_payouts
   - `pending_collections` = appointments with payment_status != 'paid' AND billing_amount > 0

2. **`get_revenue_by_professional(tenant_id, period_start, period_end)`**
   - GROUP BY professional_id, JOIN professionals for names
   - Return: `[{professional_id, professional_name, total_revenue, appointment_count}]`
   - Sort by total_revenue DESC

3. **`get_revenue_by_treatment(tenant_id, period_start, period_end)`**
   - GROUP BY treatment_code, JOIN treatment_types for names
   - Calculate percentage of total revenue per treatment
   - Return: `[{treatment_code, treatment_name, total_revenue, percentage}]`
   - Sort by total_revenue DESC

4. **`get_daily_cash_flow(tenant_id, period_start, period_end)`**
   - GROUP BY DATE(appointment_date)
   - Include payouts per day from professional_payouts
   - Return: `[{date, revenue, payouts}]`
   - Sort by date ASC

5. **`get_mom_growth(tenant_id, current_period_start, current_period_end)`**
   - Calculate current period revenue and payouts
   - Calculate previous period revenue and payouts (same duration, shifted back)
   - Return: `{current_revenue, previous_revenue, growth_pct, current_payouts, previous_payouts, payout_growth_pct}`

6. **`get_top_treatments(tenant_id, period_start, period_end, limit=5)`**
   - Top N treatments by revenue
   - Return: `[{treatment_code, treatment_name, revenue, count}]`

7. **`get_pending_collections(tenant_id, period_start, period_end)`**
   - Appointments with payment_status != 'paid' AND billing_amount > 0
   - Include: patient_name, treatment_name, amount_pending, days_overdue, professional_name
   - Sort by amount_pending DESC

**Requirements:**
- ALL queries must include `WHERE tenant_id = $1` filter
- Use SQLAlchemy ORM for new models, raw SQL for existing tables
- Handle empty periods gracefully (return 0, empty arrays)
- Use `Decimal` for monetary calculations

**Files:**
- `orchestrator_service/services/financial_dashboard_service.py` (NEW)

**Dependencies:** T1.1, T1.2

**Estimated effort:** L

**Acceptance criteria:**
- [ ] Financial summary returns correct totals matching raw data
- [ ] Revenue by professional matches individual appointment sums
- [ ] Revenue by treatment percentages sum to ~100%
- [ ] Daily cash flow has one entry per day with data
- [ ] MoM growth correctly calculates previous period of same duration
- [ ] Pending collections shows correct days_overdue calculation
- [ ] Empty period returns zeros and empty arrays (no errors)
- [ ] All queries filtered by tenant_id

---

### T1.5: Implement EP-FC-01 + EP-FC-02 (Generate Liquidations)

**Description:** Implement POST endpoints for single and bulk liquidation generation in `admin_routes.py`.

**EP-FC-01: POST /admin/liquidations/generate**
- Request body: `{professional_id, period_start, period_end}`
- Validate: dates format YYYY-MM-DD, start <= end, range <= 366 days, professional exists
- Call `liquidation_service.generate_liquidation()`
- Return 201 for new records, 200 for existing (idempotent)
- Include `generated_by` from current user email

**EP-FC-02: POST /admin/liquidations/generate-bulk**
- Request body: `{period_start, period_end}`
- Call `liquidation_service.generate_bulk_liquidations()`
- Return: `{generated_count, skipped_count, liquidations: [...]}`

**Requirements:**
- Protect with `Depends(get_current_user)` and role check (CEO only)
- `tenant_id` from `Depends(get_resolved_tenant_id)`
- Validate date format and range
- Return proper HTTP status codes (201 created, 200 existing, 400 validation, 404 not found, 403 forbidden)

**Files:**
- `orchestrator_service/admin_routes.py` (MODIFIED — add 2 endpoints)

**Dependencies:** T1.1, T1.2, T1.3

**Estimated effort:** M

**Acceptance criteria:**
- [ ] POST generate creates new liquidation with correct totals
- [ ] POST generate again with same params returns existing record (200)
- [ ] POST generate-bulk creates liquidations for all active professionals
- [ ] Invalid dates return 400
- [ ] Non-existent professional returns 404
- [ ] Non-CEO user gets 403
- [ ] Response includes treatment_groups detail

---

### T1.6: Implement EP-FC-03 + EP-FC-04 (List + Detail Liquidations)

**Description:** Implement GET endpoints for listing and viewing liquidation details.

**EP-FC-03: GET /admin/liquidations**
- Query params: `professional_id` (optional), `status` (optional), `period_start`, `period_end`, `page`, `page_size`
- Return paginated list with total count and total_pages
- Default page_size: 20, max: 100

**EP-FC-04: GET /admin/liquidations/{id}**
- Return full detail: liquidation_record + treatment_groups + payouts
- Call `liquidation_service.get_liquidation_detail()`
- Verify tenant ownership

**Requirements:**
- Protect with auth + role check (CEO only)
- Pagination with offset/limit
- Include professional name in list response
- Sort by generated_at DESC

**Files:**
- `orchestrator_service/admin_routes.py` (MODIFIED — add 2 endpoints)

**Dependencies:** T1.1, T1.2, T1.3

**Estimated effort:** M

**Acceptance criteria:**
- [ ] List returns paginated results with correct total
- [ ] Filters work: by professional_id, status, period
- [ ] Detail returns treatment_groups and payouts
- [ ] Pagination defaults: page=1, page_size=20
- [ ] Non-CEO gets 403
- [ ] Non-existent ID returns 404

---

### T1.7: Implement EP-FC-05 + EP-FC-06 + EP-FC-07 (Status, Payout, Payouts)

**Description:** Implement PATCH for status updates and POST/GET for payouts.

**EP-FC-05: PATCH /admin/liquidations/{id}**
- Request: `{status, notes}`
- Validate status transition (draft→generated→approved→paid)
- Call `liquidation_service.update_liquidation_status()`
- Return updated liquidation with audit trail

**EP-FC-06: POST /admin/liquidations/{id}/payout**
- Request: `{amount, payment_method, reference_number, notes}`
- Validate: amount > 0, method in ['transfer', 'cash', 'check'], liquidation not in 'draft'
- Call `liquidation_service.create_payout()`
- Return 201 with created payout

**EP-FC-07: GET /admin/liquidations/{id}/payouts**
- Return all payouts for a liquidation
- Call `liquidation_service.get_payouts_for_liquidation()`

**Requirements:**
- Protect with auth + role check (CEO only)
- Invalid status transition → 400 with descriptive message
- Auto-complete to 'paid' when payouts cover payout_amount
- Audit trail entries in notes JSONB

**Files:**
- `orchestrator_service/admin_routes.py` (MODIFIED — add 3 endpoints)

**Dependencies:** T1.1, T1.2, T1.3

**Estimated effort:** M

**Acceptance criteria:**
- [ ] Status transition draft→generated→approved→paid works
- [ ] Invalid transition (e.g., draft→paid) returns 400
- [ ] Payout creation updates liquidation status when fully covered
- [ ] Payout list returns all payments ordered by date
- [ ] Audit trail entries visible in notes JSONB
- [ ] Non-CEO gets 403

---

### T1.8: Implement EP-FC-08 (Financial Dashboard)

**Description:** Implement GET /admin/financial-dashboard endpoint aggregating all metrics.

**EP-FC-08: GET /admin/financial-dashboard**
- Query params: `period_start` (required), `period_end` (required)
- Call all financial_dashboard_service functions
- Return single aggregated response:
  ```json
  {
    "summary": {...},
    "revenue_by_professional": [...],
    "revenue_by_treatment": [...],
    "daily_cash_flow": [...],
    "mom_growth": {...},
    "top_treatments": [...],
    "pending_collections": [...]
  }
  ```

**Requirements:**
- Protect with auth + role check (CEO only)
- All sub-queries filtered by tenant_id
- Handle empty periods gracefully

**Files:**
- `orchestrator_service/admin_routes.py` (MODIFIED — add 1 endpoint)

**Dependencies:** T1.1, T1.2, T1.4

**Estimated effort:** S

**Acceptance criteria:**
- [ ] Single endpoint returns all dashboard data
- [ ] Summary totals are correct
- [ ] Charts data properly formatted for Recharts
- [ ] MoM growth calculates previous period correctly
- [ ] Empty period returns zeros/empty arrays

---

### T1.9: Implement EP-FC-09 + EP-FC-10 (Commission CRUD)

**Description:** Implement GET and PUT endpoints for professional commission configuration.

**EP-FC-09: GET /admin/professionals/{id}/commissions**
- Return: `{professional_id, professional_name, default_commission_pct, per_treatment: [...]}`
- If no config: return 0% with warning field
- Include treatment names from treatment_types

**EP-FC-10: PUT /admin/professionals/{id}/commissions**
- Request: `{default_commission_pct, per_treatment: [{treatment_code, commission_pct}]}`
- Validate: percentages 0-100, treatment_code exists in treatment_types
- Upsert default commission (treatment_code = NULL)
- Upsert per-treatment overrides
- Delete overrides no longer in the list
- Return updated config with timestamp

**Requirements:**
- Protect with auth + role check (CEO only)
- Use `INSERT ... ON CONFLICT DO UPDATE` for upserts
- Log commission changes for audit trail

**Files:**
- `orchestrator_service/admin_routes.py` (MODIFIED — add 2 endpoints)

**Dependencies:** T1.1, T1.2

**Estimated effort:** M

**Acceptance criteria:**
- [ ] GET returns current commission config with treatment names
- [ ] GET with no config returns 0% with warning
- [ ] PUT creates/updates default and per-treatment commissions
- [ ] PUT removes overrides no longer in the list
- [ ] Invalid percentage (>100 or <0) returns 400
- [ ] Non-existent treatment_code returns 400
- [ ] Non-CEO gets 403

---

### T1.10: Implement EP-FC-11 (Reconciliation)

**Description:** Implement GET /admin/reconciliation endpoint for financial reconciliation.

**EP-FC-11: GET /admin/reconciliation**
- Query params: `period_start` (required), `period_end` (required)
- Calculate:
  - `total_patient_payments` = SUM of paid appointments + treatment_plan_payments
  - `total_professional_payouts` = SUM of professional_payouts
  - `difference` = patient_payments - professional_payouts
- Detect discrepancies:
  - `payment_without_liquidation`: paid appointments not in any liquidation record
  - `payout_without_liquidation`: payouts with no matching liquidation (referential integrity)
- Return: `{period_start, period_end, total_patient_payments, total_professional_payouts, difference, discrepancies: [...], discrepancy_count}`

**Requirements:**
- Protect with auth + role check (CEO only)
- Discrepancy detection algorithm: set difference of paid appointments vs liquidated appointments
- Include appointment details in each discrepancy

**Files:**
- `orchestrator_service/admin_routes.py` (MODIFIED — add 1 endpoint)

**Dependencies:** T1.1, T1.2, T1.3

**Estimated effort:** M

**Acceptance criteria:**
- [ ] Totals match raw payment data
- [ ] Discrepancies correctly identify paid appointments without liquidations
- [ ] Empty period returns zero totals and empty discrepancies
- [ ] Non-CEO gets 403

---

## Phase 2: Financial Dashboard (Backend + Frontend)

### T2.1: Create TypeScript Types

**Description:** Create `frontend_react/src/types/finance.ts` with all TypeScript interfaces for the financial domain.

**Interfaces to define:**
- `LiquidationRecord` — id, professional_id, professional_name, period_start, period_end, total_billed, total_paid, total_pending, commission_pct, commission_amount, payout_amount, status, generated_at, approved_at, paid_at, generated_by, notes, treatment_groups, payouts
- `ProfessionalPayout` — id, liquidation_id, amount, payment_method, payment_date, reference_number, notes, created_at
- `ProfessionalCommission` — professional_id, professional_name, default_commission_pct, per_treatment[]
- `CommissionOverride` — treatment_code, treatment_name, commission_pct
- `FinancialSummary` — total_revenue, total_payouts, net_profit, pending_collections
- `RevenueByProfessional` — professional_id, professional_name, total_revenue, appointment_count
- `RevenueByTreatment` — treatment_code, treatment_name, total_revenue, percentage
- `DailyCashFlow` — date, revenue, payouts
- `MoMGrowth` — current_revenue, previous_revenue, growth_pct, current_payouts, previous_payouts, payout_growth_pct
- `PendingCollection` — patient_id, patient_name, appointment_id, treatment_name, amount_pending, days_overdue, professional_name
- `Discrepancy` — type, appointment_id, patient_name, treatment_name, amount, appointment_date, professional_name, description
- `ReconciliationReport` — period_start, period_end, total_patient_payments, total_professional_payouts, difference, discrepancies, discrepancy_count
- `FinancialDashboardResponse` — summary, revenue_by_professional, revenue_by_treatment, daily_cash_flow, mom_growth, top_treatments, pending_collections
- `LiquidationListResponse` — liquidations[], total, page, page_size, total_pages
- `TreatmentGroup` — patient_id, patient_name, treatment_code, treatment_name, sessions[], total
- `TreatmentSession` — appointment_id, date, description, amount, payment_status

**Files:**
- `frontend_react/src/types/finance.ts` (NEW)

**Dependencies:** None (can be written in parallel with backend)

**Estimated effort:** S

**Acceptance criteria:**
- [ ] All interfaces match backend response shapes
- [ ] No TypeScript compilation errors
- [ ] Types exported for use across components

---

### T2.2: Create FinancialCommandCenterView

**Description:** Create `frontend_react/src/views/FinancialCommandCenterView.tsx` — the main financial view with 3 tabs.

**Structure:**
- PageHeader with title "Centro de Comando Financiero"
- Tab navigation: Dashboard, Liquidaciones, Conciliación (with icons)
- Period selector (date range picker) in top-right corner
- Default period: current month
- Each tab loads content on demand (conditional rendering)
- Scroll isolation: `h-screen` + `overflow-hidden` global, `overflow-y-auto` internal

**Requirements:**
- Protected route: CEO only (enforced by ProtectedRoute in App.tsx, but also check role)
- Use existing UI components: GlassCard, PageHeader
- Tab state: `dashboard` | `liquidaciones` | `conciliacion`
- Period state shared across tabs
- Responsive: tabs scroll horizontally on mobile

**Files:**
- `frontend_react/src/views/FinancialCommandCenterView.tsx` (NEW)

**Dependencies:** T2.1

**Estimated effort:** M

**Acceptance criteria:**
- [ ] 3 tabs render correctly
- [ ] Period selector updates shared state
- [ ] Tab content switches without page reload
- [ ] Scroll isolation works (no horizontal overflow)
- [ ] Non-CEO redirected from route (via ProtectedRoute)

---

### T2.3: Create FinancialDashboard Component

**Description:** Create `frontend_react/src/components/finance/FinancialDashboard.tsx` — Tab 1 with KPIs and charts.

**Sub-components (can be inline or separate files):**
1. **KPI Cards (4):** Ingresos, Liquidaciones Pendientes, Pagos a Profesionales, Ganancia Neta
   - Each card: icon, value, label, MoM indicator (green/red)
   - Format: ARS currency with thousands separator

2. **RevenueBarChart:** Horizontal bar chart (Recharts) — revenue by professional
   - Click on bar → navigate to Liquidaciones tab with professional filter

3. **TreatmentPieChart:** Pie chart (Recharts) — revenue by treatment
   - Tooltip: treatment_name + revenue + percentage

4. **CashFlowLineChart:** Line chart (Recharts) — daily cash flow with 2 lines (revenue, payouts)
   - Tooltip: date + revenue + payouts + difference

5. **PendingCollectionsAlert:** List of top 5 pending collections
   - Color coding: >30 days = red, 15-30 = orange, <15 = yellow
   - "Ver todos" to expand full list

6. **MoMComparison:** Bar comparison — current vs previous month with growth percentage

**Requirements:**
- Fetch data from `GET /admin/financial-dashboard?period_start=X&period_end=X`
- Loading states for each section
- Error handling with retry
- Responsive: 4-col KPIs on desktop, 2-col on tablet, 1-col on mobile
- Charts: 2-col on desktop, 1-col on tablet/mobile

**Files:**
- `frontend_react/src/components/finance/FinancialDashboard.tsx` (NEW)

**Dependencies:** T2.1, T2.2, Batch 2 (endpoints must exist)

**Estimated effort:** L

**Acceptance criteria:**
- [ ] All 4 KPI cards display correct values with formatting
- [ ] Bar chart renders with professional names and revenue
- [ ] Pie chart renders with treatment distribution
- [ ] Line chart shows daily revenue and payouts
- [ ] Pending collections shows correct color coding
- [ ] MoM comparison shows growth percentage
- [ ] Responsive layout works on all breakpoints
- [ ] Loading states shown during data fetch
- [ ] Error states with retry button

---

### T2.4: Create LiquidationManager Component

**Description:** Create `frontend_react/src/components/finance/LiquidationManager.tsx` — Tab 2 with liquidation table and actions.

**Features:**
1. **Period Selector + Bulk Generate:**
   - Date range picker with presets: "Este mes", "Mes anterior", "Trimestre", "Personalizado"
   - "Generar Liquidaciones" button → POST /admin/liquidations/generate-bulk
   - Loading state: spinner + "Generando liquidaciones..."
   - Success toast: "X liquidaciones generadas correctamente"

2. **Liquidation Table:**
   - Columns: Profesional, Período, Facturado, Comisión, Payout, Estado, Acciones
   - Pagination: 20 per page
   - Status badges (use LiquidationStatusBadge from T2.5)
   - Warning badge for 0% commission

3. **Actions per status:**
   - draft: [Ver detalle] [Aprobar]
   - generated: [Ver detalle] [Aprobar] [Descargar PDF]
   - approved: [Ver detalle] [Marcar pagado] [Descargar PDF]
   - paid: [Ver detalle] [Descargar PDF]

4. **Expandable Detail:**
   - Click row or 👁️ → accordion with treatment groups
   - Reuse `ProfessionalAccordion` pattern for patient/treatment grouping
   - Show payout history
   - Actions: [Registrar Pago] [Descargar PDF] [Enviar Email]

5. **Export CSV:**
   - Button to export current view as CSV
   - Columns: profesional, período, total_billed, commission_pct, commission_amount, payout_amount, status, generated_at

**Requirements:**
- Fetch from `GET /admin/liquidations` with filters
- Status update: PATCH /admin/liquidations/{id}
- Payout creation: POST /admin/liquidations/{id}/payout (modal form)
- Commission editor modal (T2.6) accessible from table (gear icon per row)
- Loading and error states

**Files:**
- `frontend_react/src/components/finance/LiquidationManager.tsx` (NEW)

**Dependencies:** T2.1, T2.2, T2.5, Batch 2

**Estimated effort:** L

**Acceptance criteria:**
- [ ] Bulk generate works with loading state and toast
- [ ] Table shows correct data with pagination
- [ ] Status badges show correct colors
- [ ] Expandable detail shows treatment groups
- [ ] Approve action works with confirmation
- [ ] Payout registration modal works
- [ ] CSV export downloads correct file
- [ ] Commission editor accessible from table

---

### T2.5: Create LiquidationStatusBadge Component

**Description:** Create `frontend_react/src/components/finance/LiquidationStatusBadge.tsx` — reusable status badge.

**Status mapping:**
- `draft` → gray badge: "Borrador"
- `generated` → blue badge: "Generada"
- `approved` → green badge: "Aprobada"
- `paid` → dark green badge: "Pagada"

**Props:**
```tsx
interface LiquidationStatusBadgeProps {
  status: 'draft' | 'generated' | 'approved' | 'paid';
}
```

**Requirements:**
- Use TailwindCSS for styling
- Consistent with existing badge patterns in the project
- Include i18n via `useTranslation()`

**Files:**
- `frontend_react/src/components/finance/LiquidationStatusBadge.tsx` (NEW)

**Dependencies:** T2.1

**Estimated effort:** S

**Acceptance criteria:**
- [ ] All 4 statuses render with correct colors and labels
- [ ] i18n keys used for labels
- [ ] Consistent sizing and styling

---

### T2.6: Create CommissionEditor Modal

**Description:** Create `frontend_react/src/components/finance/CommissionEditor.tsx` — modal for editing professional commissions.

**Features:**
- Modal with title "Configurar Comisiones — {professionalName}"
- Default commission input (percentage 0-100)
- Per-treatment overrides table:
  - Columns: Tratamiento, Comisión (%), Remove button
  - "Agregar tratamiento" dropdown to add new override
- Validation: percentage 0-100, warning if 0%
- Save: PUT /admin/professionals/{id}/commissions
- Load: GET /admin/professionals/{id}/commissions

**Props:**
```tsx
interface CommissionEditorProps {
  professionalId: number;
  professionalName: string;
  onClose: () => void;
  onSuccess: () => void;
}
```

**Requirements:**
- Use existing modal pattern from project
- Validate percentages on input
- Warning message for 0%: "Comisión 0%: el profesional recibe el 100% del cobro"
- Success toast on save

**Files:**
- `frontend_react/src/components/finance/CommissionEditor.tsx` (NEW)

**Dependencies:** T2.1, Batch 2 (EP-FC-09, EP-FC-10)

**Estimated effort:** M

**Acceptance criteria:**
- [ ] Modal opens with current commission data
- [ ] Default commission editable with validation
- [ ] Per-treatment overrides can be added/removed
- [ ] Save updates backend correctly
- [ ] 0% warning displayed
- [ ] Invalid percentage (>100, <0) shows error
- [ ] Success toast on save

---

### T2.7: Add Routes to App.tsx

**Description:** Add `/finanzas` and `/mis-liquidaciones` routes to `frontend_react/src/App.tsx`.

**Routes to add:**
```tsx
<Route
  path="/finanzas"
  element={
    <ProtectedRoute allowedRoles={['ceo']}>
      <FinancialCommandCenterView />
    </ProtectedRoute>
  }
/>
<Route
  path="/mis-liquidaciones"
  element={
    <ProtectedRoute allowedRoles={['professional']}>
      <ProfessionalLiquidationsView />
    </ProtectedRoute>
  }
/>
```

**Requirements:**
- Import new view components
- Use existing `ProtectedRoute` component with `allowedRoles`
- Ensure wildcard routes (`/*`) are preserved for nested routes

**Files:**
- `frontend_react/src/App.tsx` (MODIFIED)

**Dependencies:** T2.2, T4.2

**Estimated effort:** S

**Acceptance criteria:**
- [ ] `/finanzas` route accessible to CEO only
- [ ] `/mis-liquidaciones` route accessible to professionals only
- [ ] Non-authorized roles are redirected
- [ ] No breaking changes to existing routes

---

### T2.8: Add i18n Keys

**Description:** Add all finance-related i18n keys to `es.json`, `en.json`, and `fr.json`.

**Namespaces to add:**
1. **`finance`** — FinancialCommandCenterView titles, tabs, KPI labels
2. **`liquidation`** — LiquidationManager states, actions, messages
3. **`reconciliation`** — ReconciliationView titles, discrepancy labels
4. **`commissions`** — CommissionEditor labels, validations
5. **`professional_liquidations`** — ProfessionalLiquidationsView labels

**Requirements:**
- All 3 languages (es/en/fr) must have complete translations
- Use interpolation for dynamic values: `{{count}}`, `{{amount}}`, `{{period}}`
- Follow existing i18n patterns in the project
- Use `useTranslation()` with namespace: `const { t } = useTranslation()`

**Files:**
- `frontend_react/src/locales/es.json` (MODIFIED)
- `frontend_react/src/locales/en.json` (MODIFIED)
- `frontend_react/src/locales/fr.json` (MODIFIED)

**Dependencies:** T2.1

**Estimated effort:** M

**Acceptance criteria:**
- [ ] All keys present in all 3 language files
- [ ] No missing translations when switching languages
- [ ] Interpolation works for dynamic values
- [ ] Keys match those used in components

---

## Phase 3: PDF + Email

### T3.1: Create Liquidation Statement HTML Template

**Description:** Create `orchestrator_service/templates/liquidation/liquidation_statement.html` — Jinja2 template for PDF generation.

**Design requirements:**
- A4 format with margins (2cm top/bottom, 1.5cm left/right)
- Professional styling with clinic header (logo, name, address, phone)
- Document title: "LIQUIDACIÓN DE HONORARIOS PROFESIONALES"
- Summary section: total sessions, billed, paid, pending, commission, net payout
- Detail section: patient groups with session tables
- Payment history section
- Signature lines (clinic + professional)
- Footer with generation timestamp

**Template variables:**
- `clinic`: name, address, phone, logo_url, ui_language
- `professional`: full_name, specialty, license_number
- `period`: start, end, label
- `summary`: total_sessions, total_billed, total_paid, total_pending, commission_pct, commission_amount, payout_amount
- `treatment_groups`: [{patient_name, treatment_name, sessions: [{date, description, amount, payment_status}], total}]
- `payouts`: [{date, amount, payment_method, reference_number, notes}]
- `generated_at`, `status`, `notes`

**i18n:** Use embedded translation dictionaries based on `clinic.ui_language` (es/en/fr)

**CSS:** Inline styles for WeasyPrint compatibility (no external stylesheets)

**Files:**
- `orchestrator_service/templates/liquidation/liquidation_statement.html` (NEW)

**Dependencies:** T1.1, T1.2, T1.3

**Estimated effort:** M

**Acceptance criteria:**
- [ ] Template renders correctly with sample data
- [ ] A4 format with proper margins
- [ ] All sections present: header, summary, detail, payouts, signatures, footer
- [ ] Status badge styled correctly per status
- [ ] Table formatting clean and readable
- [ ] i18n works for es/en/fr
- [ ] Logo displays if available
- [ ] CSS compatible with WeasyPrint

---

### T3.2: Implement EP-FC-12 (PDF Generation)

**Description:** Implement GET /admin/liquidations/{id}/pdf endpoint with caching.

**Logic:**
1. Verify ownership: `liquidation_record.tenant_id == current_tenant_id`
2. Check cache: if PDF exists at `/app/uploads/liquidations/{tenant_id}/{liquidation_id}.pdf` and status unchanged, serve cached file
3. Gather data: liquidation record, professional, clinic, treatment groups, payouts
4. Render Jinja2 template
5. Generate PDF with WeasyPrint (in thread executor via `run_in_executor`)
6. Save to cache directory
7. Return FileResponse with proper Content-Disposition header

**Requirements:**
- Follow existing pattern from `budget_service.py`
- Async WeasyPrint execution via `run_in_executor`
- Fallback to HTML if WeasyPrint fails (log warning, return HTML response)
- Filename format: `Liquidacion_{prof_name}_{period_label}.pdf`
- Audit trail: log PDF generation in notes

**Files:**
- `orchestrator_service/admin_routes.py` (MODIFIED — add endpoint)
- `orchestrator_service/services/liquidation_service.py` (MODIFIED — add PDF generation function)

**Dependencies:** T1.1, T1.2, T1.3, T3.1

**Estimated effort:** M

**Acceptance criteria:**
- [ ] PDF downloads with correct filename
- [ ] PDF contains all liquidation data
- [ ] A4 format with professional styling
- [ ] Cache works: second request serves cached file instantly
- [ ] Cache invalidates on status change
- [ ] HTML fallback if WeasyPrint fails
- [ ] Non-CEO gets 403
- [ ] Non-existent ID returns 404

---

### T3.3: Implement EP-FC-13 (Send Email)

**Description:** Implement POST /admin/liquidations/{id}/send-email endpoint.

**Logic:**
1. Validate email: use provided `to_email` or fallback to professional's email
2. Generate PDF (reuse T3.2 logic, use cache if available)
3. Send email with PDF attachment using existing email service
4. Subject: "Liquidación {period_label} — {clinic_name}"
5. Body: HTML template with professional greeting, period info, payout amount
6. Log email send in liquidation notes audit trail

**Email template:** `orchestrator_service/templates/liquidation/liquidation_email.html`

**Requirements:**
- Use existing email sending infrastructure
- HTML email body with clinic branding
- PDF as attachment
- i18n based on clinic's ui_language
- Error handling: log error, return 500 if email fails

**Files:**
- `orchestrator_service/admin_routes.py` (MODIFIED — add endpoint)
- `orchestrator_service/templates/liquidation/liquidation_email.html` (NEW)
- `orchestrator_service/services/liquidation_service.py` (MODIFIED — add email function)

**Dependencies:** T3.1, T3.2

**Estimated effort:** M

**Acceptance criteria:**
- [ ] Email sent with PDF attachment
- [ ] Subject includes period and clinic name
- [ ] Body uses correct language
- [ ] Email logged in audit trail
- [ ] Fallback to professional's email if not provided
- [ ] 500 error if email service fails

---

### T3.4: Add PDF Download Button to LiquidationManager

**Description:** Add PDF download and email send buttons to the LiquidationManager component.

**Features:**
- 📄 Download PDF button in table actions and detail view
- 📧 Send Email button in detail view (opens modal with email input)
- Blob download for PDF: `fetch(...).then(r => r.blob()).then(blob => download)`
- Loading state during PDF generation
- Error handling with user-friendly message

**Requirements:**
- Use existing toast/notification patterns
- Handle PDF download as blob
- Email modal with email input field
- Pre-fill professional's email if available

**Files:**
- `frontend_react/src/components/finance/LiquidationManager.tsx` (MODIFIED)

**Dependencies:** T2.4, T3.2, T3.3

**Estimated effort:** S

**Acceptance criteria:**
- [ ] PDF download button triggers file download
- [ ] Email button opens modal with email input
- [ ] Loading state shown during generation
- [ ] Error message if PDF generation fails
- [ ] Success toast on email sent

---

## Phase 4: Professional Portal

### T4.1: Add Professional-Scoped Endpoints

**Description:** Add `/my/` endpoints for professional self-service access.

**Endpoints to add:**
1. **GET /my/liquidations** — List own liquidations (extract professional_id from JWT)
2. **GET /my/liquidations/{id}** — Detail of own liquidation (read-only)
3. **GET /my/liquidations/{id}/pdf** — Download PDF of own liquidation
4. **GET /my/commissions** — View own commission config

**Requirements:**
- Extract `professional_id` from JWT token
- Force filter: `WHERE professional_id = {jwt_professional_id}`
- GET-only (read-only access)
- Also extract `tenant_id` from JWT for tenant isolation
- No role check needed (professional role implied by JWT)

**Files:**
- `orchestrator_service/admin_routes.py` (MODIFIED — add 4 endpoints under /my/ prefix)

**Dependencies:** T1.1, T1.2, T1.3, T3.2

**Estimated effort:** M

**Acceptance criteria:**
- [ ] Professional sees only their own liquidations
- [ ] Cannot access other professionals' data
- [ ] PDF download works for own liquidations
- [ ] Commission config viewable
- [ ] All endpoints are GET-only (no mutations)
- [ ] Tenant isolation enforced

---

### T4.2: Create ProfessionalLiquidationsView

**Description:** Create `frontend_react/src/views/ProfessionalLiquidationsView.tsx` — self-service view for professionals.

**Features:**
- PageHeader: "Mis Liquidaciones"
- Period filter (date range picker)
- List of own liquidations as cards (not table):
  - Período, status badge, total facturado, comisión, payout, paid date
  - Download PDF button
- Read-only: no approve, generate, or edit actions
- Empty state: "No tenés liquidaciones aún"

**Requirements:**
- Protected route: professional only
- Fetch from `GET /my/liquidations`
- PDF download from `GET /my/liquidations/{id}/pdf`
- Responsive: cards stack on mobile
- Scroll isolation

**Files:**
- `frontend_react/src/views/ProfessionalLiquidationsView.tsx` (NEW)

**Dependencies:** T2.1, T4.1

**Estimated effort:** M

**Acceptance criteria:**
- [ ] Professional sees only their liquidations
- [ ] Cards display correct information
- [ ] PDF download works
- [ ] No edit/approve actions visible
- [ ] Empty state shown when no liquidations
- [ ] Responsive layout
- [ ] Non-professional redirected

---

### T4.3: RBAC Enforcement

**Description:** Ensure all financial routes and endpoints are properly protected by role.

**Backend enforcement:**
- Add role checks to all financial endpoints in `admin_routes.py`:
  - CEO-only: generate, generate-bulk, list, detail, status update, payout, dashboard, commissions, reconciliation, send-email
  - Professional (own data): /my/ endpoints
  - Secretary: no access to financial endpoints
- Verify `get_current_user` dependency on all routes
- Verify `get_resolved_tenant_id` dependency on all routes

**Frontend enforcement:**
- `ProtectedRoute` with `allowedRoles` on `/finanzas` (CEO) and `/mis-liquidaciones` (professional)
- No financial navigation links shown to non-authorized roles in sidebar
- Redirect unauthorized access to `/dashboard`

**Files:**
- `orchestrator_service/admin_routes.py` (MODIFIED — verify/add role checks)
- `frontend_react/src/App.tsx` (MODIFIED — verify ProtectedRoute config)
- `frontend_react/src/components/Sidebar.tsx` or equivalent (MODIFIED — hide financial nav for non-CEO)

**Dependencies:** T2.7, T4.1

**Estimated effort:** S

**Acceptance criteria:**
- [ ] CEO can access all financial endpoints
- [ ] Professional can only access /my/ endpoints
- [ ] Secretary gets 403 on all financial endpoints
- [ ] Frontend redirects unauthorized routes
- [ ] Sidebar doesn't show financial links to non-CEO

---

## Phase 5: Reconciliation + Polish

### T5.1: Create ReconciliationView Component

**Description:** Create `frontend_react/src/components/finance/ReconciliationView.tsx` — Tab 3 of FinancialCommandCenterView.

**Features:**
1. **Summary Cards (3):**
   - Cobrado de Pacientes (total_patient_payments)
   - Pagado a Profesionales (total_professional_payouts)
   - Diferencia (difference)

2. **Discrepancy List:**
   - Each discrepancy: type, patient name, treatment, amount, date, professional, description
   - Actions: [Resolver] [Ignorar] per item
   - "Resolver" → modal to associate appointment to liquidation (future enhancement, for now just acknowledge)
   - "Ignorar" → confirmation dialog

3. **Empty State:** "Sin discrepancias — Todos los pagos están correctamente conciliados"

**Requirements:**
- Fetch from `GET /admin/reconciliation?period_start=X&period_end=X`
- Period selector shared with parent view
- Loading and error states
- Responsive layout

**Files:**
- `frontend_react/src/components/finance/ReconciliationView.tsx` (NEW)

**Dependencies:** T2.1, T2.2, T1.10

**Estimated effort:** M

**Acceptance criteria:**
- [ ] Summary cards display correct totals
- [ ] Discrepancies listed with details
- [ ] Resolve/Ignore buttons present
- [ ] Empty state shown when no discrepancies
- [ ] Responsive layout
- [ ] Loading and error states

---

### T5.2: Enhance Existing LiquidationTab

**Description:** Modify `frontend_react/src/components/analytics/LiquidationTab.tsx` to use persistent records with fallback.

**Changes:**
- Prefer data from `GET /admin/liquidations` (persistent records)
- Fallback to computed data from `GET /analytics/professionals/liquidation` if new service fails
- Add "Ver en Finanzas →" link for CEO users:
  ```tsx
  {userRole === 'ceo' && (
    <Link to="/finanzas" className="text-blue-600 hover:underline">
      Ver en Finanzas →
    </Link>
  )}
  ```
- Maintain backward compatibility — no breaking changes

**Requirements:**
- Feature flag or try-catch pattern for fallback
- Don't remove existing computed logic
- Add link only for CEO role (check AuthContext)

**Files:**
- `frontend_react/src/components/analytics/LiquidationTab.tsx` (MODIFIED)

**Dependencies:** T2.7, Batch 2

**Estimated effort:** S

**Acceptance criteria:**
- [ ] LiquidationTab tries persistent records first
- [ ] Falls back to computed data on error
- [ ] "Ver en Finanzas" link visible for CEO only
- [ ] No breaking changes to existing functionality
- [ ] Existing ProfessionalAnalyticsView still works

---

### T5.3: Error Handling, Edge Cases, Loading States

**Description:** Comprehensive error handling across all new components and endpoints.

**Backend edge cases:**
- Empty periods → return zeros/empty arrays (not errors)
- Professional not found → 404
- Invalid date format → 400 with message
- Date range > 366 days → 400
- Start date > end date → 400
- Invalid status transition → 400
- Commission not configured → 200 with warning in logs
- WeasyPrint failure → HTML fallback with warning log
- Email failure → 500 with error log

**Frontend edge cases:**
- Loading states for all async operations
- Error states with retry buttons
- Empty states for lists with no data
- Network error handling (toast notifications)
- Form validation for commission editor, payout modal
- Debounced search/filter inputs

**Requirements:**
- Consistent error message format across all endpoints
- User-friendly error messages (not technical details)
- Loading spinners on all buttons that trigger async actions
- Toast notifications for success/error

**Files:**
- Multiple files across backend and frontend (MODIFIED)

**Dependencies:** All previous tasks

**Estimated effort:** M

**Acceptance criteria:**
- [ ] All edge cases handled gracefully
- [ ] No unhandled exceptions in frontend
- [ ] All async operations have loading states
- [ ] Error messages are user-friendly
- [ ] Empty states shown for empty data
- [ ] Form validation prevents invalid submissions

---

### T5.4: Syntax Check + Full Test Suite

**Description:** Run syntax checks and verify the full implementation.

**Backend checks:**
- `python -m py_compile` on all new/modified Python files
- Verify imports in `models.py`, `liquidation_service.py`, `financial_dashboard_service.py`, `admin_routes.py`
- Check Alembic migration syntax
- Verify no circular imports

**Frontend checks:**
- `npm run lint` or `npm run check` (whatever linting is configured)
- TypeScript compilation: `npx tsc --noEmit`
- Verify all imports resolve correctly
- Check for unused variables/imports

**Integration checks:**
- Verify all endpoint paths match between backend and frontend
- Verify TypeScript types match backend response shapes
- Check i18n keys are used consistently

**Files:**
- All new and modified files

**Dependencies:** All previous tasks

**Estimated effort:** M

**Acceptance criteria:**
- [ ] No Python syntax errors
- [ ] No TypeScript compilation errors
- [ ] No linting errors
- [ ] All imports resolve
- [ ] No circular dependencies
- [ ] Endpoint paths consistent between frontend and backend

---

### T5.5: Manual Testing Checklist

**Description:** Execute manual testing to verify the full financial command center works end-to-end.

**Test scenarios:**

**Liquidation Lifecycle:**
- [ ] CEO generates liquidation for single professional → verify 201, correct totals
- [ ] CEO generates same liquidation again → verify 200 (idempotent), same record
- [ ] CEO generates bulk liquidations → verify all active professionals have records
- [ ] CEO views liquidation list → verify pagination, filters work
- [ ] CEO views liquidation detail → verify treatment groups, payouts shown
- [ ] CEO approves liquidation → verify status changes to 'approved', approved_at set
- [ ] CEO registers payout → verify payout created, status auto-changes to 'paid' if fully covered
- [ ] CEO downloads PDF → verify correct data, A4 format, clinic language
- [ ] CEO sends email → verify email received with PDF attachment

**Dashboard:**
- [ ] CEO views /finanzas → all 3 tabs visible
- [ ] Dashboard tab: 4 KPI cards with correct values
- [ ] Revenue by professional chart renders correctly
- [ ] Revenue by treatment pie chart renders correctly
- [ ] Daily cash flow line chart renders correctly
- [ ] Pending collections show correct color coding
- [ ] MoM comparison shows growth percentage
- [ ] Period selector changes update all data

**Commissions:**
- [ ] CEO views professional commissions → correct data shown
- [ ] CEO edits commissions → save works, validation enforced
- [ ] 0% commission shows warning
- [ ] Invalid percentage rejected

**Reconciliation:**
- [ ] Reconciliation tab shows correct totals
- [ ] Discrepancies detected correctly
- [ ] Resolve/Ignore actions work

**Professional Portal:**
- [ ] Professional logs in → /mis-liquidaciones accessible
- [ ] Professional sees only own liquidations
- [ ] Professional can download PDF
- [ ] Professional cannot edit/approve anything

**RBAC:**
- [ ] Secretary cannot access /finanzas (redirected)
- [ ] Secretary cannot access /mis-liquidaciones (redirected)
- [ ] Professional cannot access /finanzas (redirected)
- [ ] CEO cannot access /mis-liquidaciones (redirected)

**i18n:**
- [ ] Switch to English → all financial texts translated
- [ ] Switch to French → all financial texts translated
- [ ] PDF uses clinic's configured language

**Responsive:**
- [ ] Desktop (>1024px): 4-col KPIs, 2-col charts, full table
- [ ] Tablet (768-1024px): 2-col KPIs, 1-col charts
- [ ] Mobile (<768px): 1-col everything, cards instead of table

**Scroll Isolation:**
- [ ] No horizontal overflow on any financial view
- [ ] Content scrolls internally within containers

**Estimated effort:** L

**Dependencies:** All previous tasks

**Acceptance criteria:**
- [ ] All test scenarios pass
- [ ] No regressions in existing functionality
- [ ] All acceptance criteria from specs met

---

## Dependency Graph

```
T1.1 (migration) ──→ T1.2 (ORM) ──→ T1.3-T1.4 (services) ──→ T1.5-T1.10 (endpoints)
                                                                        ↓
T2.1 (types) ──────────────────────────────────────────────────→ T2.2-T2.8 (frontend)
                                                                        ↓
T3.1 (template) ───────────────────────────────────────────────→ T3.2-T3.4 (PDF+email)
                                                                        ↓
T4.1-T4.3 (portal) ────────────────────────────────────────────→ T5.1-T5.5 (reconciliation+polish)
```

## Parallel Execution Guide

**Batch 1 (Phase 1 Foundation — all parallel):**
- T1.1: Alembic migration
- T1.2: ORM models
- T1.3: liquidation_service.py
- T1.4: financial_dashboard_service.py

**Batch 2 (Phase 1 Endpoints — all parallel after Batch 1):**
- T1.5: EP-FC-01 + EP-FC-02 (generate)
- T1.6: EP-FC-03 + EP-FC-04 (list + detail)
- T1.7: EP-FC-05 + EP-FC-06 + EP-FC-07 (status, payout, payouts)
- T1.8: EP-FC-08 (dashboard)
- T1.9: EP-FC-09 + EP-FC-10 (commissions)
- T1.10: EP-FC-11 (reconciliation)

**Batch 3 (Phase 2 Frontend — T2.1 first, then rest parallel after Batch 2):**
- T2.1: TypeScript types (prerequisite)
- T2.2: FinancialCommandCenterView
- T2.3: FinancialDashboard
- T2.4: LiquidationManager
- T2.5: LiquidationStatusBadge
- T2.6: CommissionEditor
- T2.7: App.tsx routes
- T2.8: i18n keys

**Batch 4 (Phase 3 PDF — T3.1 first, then rest parallel):**
- T3.1: HTML template (prerequisite, depends on Batch 1)
- T3.2: PDF endpoint (depends on T3.1 + Batch 2)
- T3.3: Email endpoint (depends on T3.2)
- T3.4: PDF download button (depends on T3.2 + T2.4)

**Batch 5 (Phase 4+5 — all parallel after Batch 4):**
- T4.1: Professional /my/ endpoints
- T4.2: ProfessionalLiquidationsView
- T4.3: RBAC enforcement
- T5.1: ReconciliationView
- T5.2: Enhanced LiquidationTab
- T5.3: Error handling + edge cases
- T5.4: Syntax check + test suite
- T5.5: Manual testing checklist
