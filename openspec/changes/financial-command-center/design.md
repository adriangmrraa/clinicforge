# Technical Design: Financial Command Center

## Architecture Decisions

### AD-01: Database migration strategy

**Decision:** Migration 020 creates 3 new tables (`liquidation_records`, `professional_payouts`, `professional_commissions`) plus indexes. The existing `GET /admin/analytics/professionals/liquidation` endpoint stays as-is.

**Rationale:** The current liquidation query in `analytics_service.get_professionals_liquidation()` is computed on-the-fly from raw appointment data. It has no persistent records, no status tracking, and no audit trail. Rather than modifying that query (which would break `ProfessionalAnalyticsView`), we create a parallel persistent system. The old endpoint remains as a fallback and reference for calculation validation.

**Backward compatibility:**
- Existing endpoint `GET /admin/analytics/professionals/liquidation` is untouched
- `ProfessionalAnalyticsView` continues to work during the transition
- `LiquidationTab.tsx` is enhanced to prefer persistent records with fallback to computed data
- Migration is additive only — no table modifications, no column drops

**Index strategy:** All indexes include `tenant_id` as the leading column to support the mandatory tenant isolation filter. Composite index on `(tenant_id, professional_id, period_start, period_end)` enforces the idempotency constraint.

### AD-02: Commission calculation approach

**Decision:** Commissions are stored in `professional_commissions` with a default percentage per professional and optional per-treatment overrides. Commission rates are applied at liquidation **generation time** (snapshot), not at appointment booking time.

**Rationale:**
- **Historical accuracy:** Commission rates change over time. A professional might go from 30% to 35% in April. If we applied commissions at appointment time, we'd need to retroactively recalculate every past appointment when the rate changes. By snapshotting at generation time, each liquidation preserves the rates that were active when it was created.
- **Auditability:** The `commission_pct` and `commission_amount` are stored directly on `liquidation_records`, making it trivial to answer "how much did we pay this professional and why?"
- **Flexibility:** Per-treatment overrides allow nuanced arrangements (e.g., 35% on implants, 25% on crowns, 30% default).

**Fallback behavior:** If a professional has no commission configuration, the system uses 0% (professional receives 100% of billed amount) and logs a warning. This is a safe default — it's better to overpay than underpay, and the warning prompts the CEO to configure proper rates.

**Commission application at generation:**
```
For each appointment in the period:
  1. Look up commission override for this treatment_code
  2. If no override, use the professional's default commission_pct
  3. If no config at all, use 0% (with warning)
  4. commission_amount += billing_amount * (commission_pct / 100)
```

### AD-03: Liquidation generation is idempotent

**Decision:** Generating a liquidation for the same `(tenant_id, professional_id, period_start, period_end)` returns the existing record instead of creating a duplicate. This is enforced by a `UNIQUE` constraint at the database level.

**Rationale:**
- **Double-click protection:** CEO clicks "Generar Liquidaciones" twice → only one record created
- **Bulk generation safety:** `generate-bulk` iterates over all professionals; if some already have liquidations for the period, they are skipped gracefully
- **API simplicity:** The endpoint returns 200 for existing records and 201 for new ones, letting the frontend display "3 already existed, 2 new" messages

**Implementation:**
```sql
CONSTRAINT uq_liquidation_period UNIQUE (tenant_id, professional_id, period_start, period_end)
```

The service first checks for an existing record. If found, it returns it (200). If not, it creates a new one (201). The unique constraint is the final safety net.

### AD-04: Service layer separation

**Decision:** Two new service modules are created:
- `liquidation_service.py` — liquidation generation, commission application, status transitions, payout creation, detail retrieval
- `financial_dashboard_service.py` — aggregated financial metrics, chart data, MoM growth, pending collections

**Rationale:**
- **Separation of concerns:** Liquidation logic (CRUD, state machine, audit trail) is fundamentally different from dashboard logic (aggregations, trend analysis, cross-period comparisons). Mixing them would create a bloated, hard-to-test service.
- **Testability:** Each service can be unit-tested independently. Liquidation service tests focus on state transitions and idempotency. Dashboard service tests focus on aggregation accuracy and edge cases (empty periods, zero revenue).
- **Existing `analytics_service.py` is left untouched:** It already handles professional analytics, appointment metrics, and the existing liquidation query. Adding financial dashboard logic would violate the single responsibility principle and risk regressions in an already-complex file.

**Service boundaries:**
| `liquidation_service.py` | `financial_dashboard_service.py` |
|---|---|
| generate_liquidation() | get_financial_summary() |
| generate_bulk_liquidations() | get_revenue_by_professional() |
| get_liquidation_detail() | get_revenue_by_treatment() |
| update_liquidation_status() | get_daily_cash_flow() |
| create_payout() | get_mom_growth() |
| get_payouts_for_liquidation() | get_top_treatments() |
| | get_pending_collections() |

### AD-05: PDF generation reuses existing pattern

**Decision:** PDF generation follows the exact pattern established by `budget_service.py` (Digital Records): gather data → Jinja2 render → WeasyPrint → disk cache → FileResponse.

**Rationale:**
- **WeasyPrint is already installed** and working for budget PDFs. No new dependencies.
- **Proven pattern:** The gather → render → generate pipeline is battle-tested. `budget_service.py` already handles async WeasyPrint execution via `run_in_executor`, disk caching, and fallback to HTML.
- **Template location:** `templates/liquidation/liquidation_statement.html` follows the same directory structure as `templates/budget/`.

**PDF caching strategy:**
- PDFs are cached on disk at `/app/uploads/liquidations/{tenant_id}/{liquidation_id}.pdf`
- Cache is invalidated on any state change: status update, payout creation, notes modification
- Invalidated by calling `invalidate_liquidation_pdf()` from `update_liquidation_status()`, `create_payout()`, and any PATCH to the liquidation
- Second request for the same liquidation serves the cached file instantly

**i18n in PDFs:** The template uses the clinic's `ui_language` setting to render labels in the correct language (es/en/fr). Translation dictionaries are embedded in the service, not in the template, to keep the HTML clean.

### AD-06: Frontend architecture

**Decision:** Two new routes are added:
- `/finanzas` — `FinancialCommandCenterView` with 3 tabs (Dashboard, Liquidaciones, Conciliación), CEO-only access
- `/mis-liquidaciones` — `ProfessionalLiquidationsView`, professional-only access, read-only

**Rationale:**
- **Single unified view for CEO:** The `/finanzas` route consolidates all financial operations into one place. Three tabs provide logical separation without navigation overhead.
- **Component reuse:** Financial components reuse existing patterns — `GlassCard` for KPI cards, `PageHeader` for titles, `recharts` for charts (already in the project), `ProfessionalAccordion` from analytics for treatment group display.
- **Separate professional portal:** Professionals get a simpler, read-only view at `/mis-liquidaciones`. This avoids role-based conditional rendering complexity and provides a clean UX for each persona.
- **RBAC at route level:** `ProtectedRoute` with `allowedRoles` enforces access control. Non-CEO users are redirected from `/finanzas`; non-professionals are redirected from `/mis-liquidaciones`.

**Component hierarchy:**
```
FinancialCommandCenterView
├── FinancialDashboard (Tab 1)
│   ├── KPI Cards (4)
│   ├── RevenueBarChart
│   ├── TreatmentPieChart
│   ├── CashFlowLineChart
│   ├── PendingCollectionsAlert
│   └── MoMComparison
├── LiquidationManager (Tab 2)
│   ├── PeriodSelector + BulkGenerate
│   ├── LiquidationTable
│   │   └── LiquidationStatusBadge
│   ├── LiquidationDetail (accordion)
│   └── CommissionEditor (modal)
└── ReconciliationView (Tab 3)
    ├── Summary Cards
    └── DiscrepancyList
```

### AD-07: Reconciliation approach

**Decision:** Reconciliation is a simple comparison: sum of patient payments vs sum of professional payouts in a period. Discrepancies are appointments with `payment_status='paid'` that are not included in any `liquidation_record`.

**Rationale:**
- **Simplicity over complexity:** A complex matching algorithm (fuzzy matching, heuristics) would be fragile and hard to debug. A simple set-difference approach is transparent and auditable.
- **Manual review workflow:** Discrepancies are surfaced for manual review, not auto-resolved. The CEO can "Resolve" (associate appointment to a liquidation) or "Ignore" (mark as not a real discrepancy).
- **Two discrepancy types:**
  1. `payment_without_liquidation` — appointment is paid but not in any liquidation
  2. `payout_without_liquidation` — payout exists but liquidation is missing (referential integrity check)

**Detection algorithm:**
```
1. SELECT all appointments with payment_status='paid' in period
2. SELECT all appointments referenced in liquidation_records in period
3. Discrepancies = set(1) - set(2)
4. Also check: payouts with no matching liquidation_record
```

### AD-08: ORM models for existing tables

**Decision:** Add SQLAlchemy ORM models for `treatment_plans`, `treatment_plan_items`, and `treatment_plan_payments` — tables that currently exist in the database (created by migrations 018 and 019) but have no ORM representation.

**Rationale:**
- **Type safety for new code:** The financial dashboard and liquidation services need to query treatment plan payments. Using raw SQL for these queries is error-prone and lacks IDE support. ORM models provide type hints, relationship navigation, and query builder support.
- **No refactoring of existing code:** Existing raw SQL queries in `analytics_service.py`, `admin_routes.py`, and other files are left as-is. Refactoring them to use ORM would be a high-risk change with no business value. The principle is: new code uses ORM, existing code stays as-is.
- **Relationship navigation:** ORM relationships (`plan.items`, `plan.payments`) make it easy to fetch related data without manual JOINs in new services.

**Model additions summary:**
| Model | Table | Purpose |
|---|---|---|
| `ProfessionalCommission` | `professional_commissions` | NEW — commission rates |
| `LiquidationRecord` | `liquidation_records` | NEW — liquidation snapshots |
| `ProfessionalPayout` | `professional_payouts` | NEW — payout tracking |
| `TreatmentPlan` | `treatment_plans` | EXISTING table, NEW model |
| `TreatmentPlanItem` | `treatment_plan_items` | EXISTING table, NEW model |
| `TreatmentPlanPayment` | `treatment_plan_payments` | EXISTING table, NEW model |

---

## Data Flow Diagrams

### 1. Liquidation Generation Flow

```
┌─────────────┐
│   CEO UI    │  Select period + professional(s)
│  /finanzas  │  Click "Generar Liquidaciones"
└──────┬──────┘
       │ POST /admin/liquidations/generate-bulk
       ▼
┌─────────────────────────────────┐
│      admin_routes.py            │
│  verify_admin_token()           │
│  get_resolved_tenant_id()       │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│    liquidation_service.py       │
│                                 │
│  1. Check existing record       │
│     (tenant_id, prof_id,        │
│      period_start, period_end)  │───── EXISTS ──► Return 200
│     │                           │
│     NOT FOUND                   │
│     ▼                           │
│  2. Get professional commissions│
│     (default + per-treatment)   │
│     │                           │
│     ▼                           │
│  3. Query appointments          │
│     in period for professional  │
│     │                           │
│     ▼                           │
│  4. Calculate totals:           │
│     total_billed, total_paid,   │
│     total_pending               │
│     │                           │
│     ▼                           │
│  5. Apply commissions:          │
│     per-treatment or default    │
│     commission_amount =         │
│     SUM(amount * pct / 100)     │
│     │                           │
│     ▼                           │
│  6. INSERT liquidation_record   │
│     status = 'generated'        │
│     │                           │
│     ▼                           │
│  7. Return 201 + record         │
└─────────────────────────────────┘
       │
       ▼
┌─────────────┐
│   CEO UI    │  Toast: "5 liquidaciones generadas"
│  /finanzas  │  Table refreshes with new records
└─────────────┘
```

### 2. Financial Dashboard Data Aggregation

```
┌─────────────┐
│   CEO UI    │  Mount /finanzas → Tab Dashboard
│  /finanzas  │  Default: current month
└──────┬──────┘
       │ GET /admin/financial-dashboard?period_start=&period_end=
       ▼
┌─────────────────────────────────┐
│      admin_routes.py            │
│  verify_admin_token()           │
│  get_resolved_tenant_id()       │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────┐
│         financial_dashboard_service.py          │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │ get_financial_summary()                   │  │
│  │  - SUM(billing_amount) FROM appointments  │  │
│  │  - SUM(amount) FROM treatment_plan_pmts   │  │
│  │  - SUM(amount) FROM professional_payouts   │  │
│  │  → revenue, payouts, profit, pending      │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │ get_revenue_by_professional()             │  │
│  │  - GROUP BY professional_id               │  │
│  │  - JOIN professionals for names           │  │
│  │  → [{prof_name, revenue, count}]          │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │ get_revenue_by_treatment()                │  │
│  │  - GROUP BY treatment_code                │  │
│  │  - JOIN treatment_types for names         │  │
│  │  → [{treatment_name, revenue, %}]         │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │ get_daily_cash_flow()                     │  │
│  │  - GROUP BY DATE(appointment_date)        │  │
│  │  - SUM(billing_amount) per day            │  │
│  │  → [{date, revenue, payouts}]             │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │ get_mom_growth()                          │  │
│  │  - Current period revenue                 │  │
│  │  - Previous period (same duration)        │  │
│  │  → {current, previous, growth_pct}        │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │ get_pending_collections()                 │  │
│  │  - appointments WHERE payment_status≠paid │  │
│  │  - AND billing_amount > 0                 │  │
│  │  → [{patient, treatment, amount, days}]   │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  Aggregate all results → single JSON response   │
└─────────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│   CEO UI    │  KPI Cards + Charts render
│  /finanzas  │  Recharts: Bar, Pie, Line
└─────────────┘
```

### 3. Reconciliation Flow

```
┌─────────────┐
│   CEO UI    │  Tab Conciliación → Select period
│  /finanzas  │  Click "Actualizar"
└──────┬──────┘
       │ GET /admin/reconciliation?period_start=&period_end=
       ▼
┌─────────────────────────────────┐
│      admin_routes.py            │
│  verify_admin_token()           │
│  get_resolved_tenant_id()       │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│         Reconciliation Logic                │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │ Step 1: Total patient payments        │  │
│  │ SELECT SUM(billing_amount)            │  │
│  │ FROM appointments                     │  │
│  │ WHERE tenant_id = $1                  │  │
│  │ AND payment_status = 'paid'           │  │
│  │ AND appointment_date BETWEEN ...      │  │
│  │ + SUM(amount) FROM treatment_plan_pmts│  │
│  └───────────────────────────────────────┘  │
│  ┌───────────────────────────────────────┐  │
│  │ Step 2: Total professional payouts    │  │
│  │ SELECT SUM(amount)                    │  │
│  │ FROM professional_payouts             │  │
│  │ WHERE tenant_id = $1                  │  │
│  │ AND payment_date BETWEEN ...          │  │
│  └───────────────────────────────────────┘  │
│  ┌───────────────────────────────────────┐  │
│  │ Step 3: Find discrepancies            │  │
│  │                                       │  │
│  │ Paid appointments:                    │  │
│  │   SELECT id FROM appointments         │  │
│  │   WHERE payment_status='paid'         │  │
│  │   AND date BETWEEN ...                │  │
│  │                                       │  │
│  │ Liquidated appointments:              │  │
│  │   SELECT a.id FROM appointments a     │  │
│  │   JOIN liquidation_records lr         │  │
│  │   ON a.professional_id = lr.prof_id   │  │
│  │   AND a.date BETWEEN lr.period        │  │
│  │   WHERE lr.tenant_id = $1             │  │
│  │                                       │  │
│  │ Discrepancy = Paid - Liquidated       │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Response: {                                │
│    total_patient_payments,                  │
│    total_professional_payouts,              │
│    difference,                              │
│    discrepancies: [...],                    │
│    discrepancy_count                        │
│  }                                          │
└─────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│   CEO UI    │  Summary cards + Discrepancy list
│  /finanzas  │  [Resolver] [Ignorar] per item
└─────────────┘
```

---

## File Structure

```
orchestrator_service/
├── models.py                          # +6 ORM models (3 new + 3 existing tables)
├── admin_routes.py                    # +13 endpoints (liquidations, dashboard, reconciliation, commissions)
├── analytics_service.py               # unchanged (existing liquidation query stays as reference)
├── services/
│   ├── liquidation_service.py         # NEW: generation, commission, status, payouts, PDF
│   └── financial_dashboard_service.py # NEW: dashboard metrics, charts data, MoM growth
├── templates/liquidation/
│   ├── liquidation_statement.html     # NEW: PDF template (Jinja2 + WeasyPrint)
│   └── liquidation_email.html         # NEW: Email body template
├── alembic/versions/
│   └── 020_financial_command_center.py # NEW: migration (3 tables + indexes)

frontend_react/src/
├── views/
│   ├── FinancialCommandCenterView.tsx  # NEW: /finanzas (3 tabs, CEO only)
│   └── ProfessionalLiquidationsView.tsx # NEW: /mis-liquidaciones (professional self-service)
├── components/
│   ├── finance/
│   │   ├── FinancialDashboard.tsx      # NEW: tab 1 — KPIs, charts, alerts
│   │   ├── LiquidationManager.tsx      # NEW: tab 2 — table, detail, actions
│   │   ├── ReconciliationView.tsx      # NEW: tab 3 — summary, discrepancies
│   │   ├── LiquidationStatusBadge.tsx  # NEW: shared status badge component
│   │   └── CommissionEditor.tsx        # NEW: modal for commission config
│   └── analytics/
│       └── LiquidationTab.tsx          # ENHANCED: use persistent records with fallback
├── types/
│   └── finance.ts                      # NEW: TypeScript interfaces
├── locales/
│   ├── es.json                         # +finance, +liquidation, +reconciliation, +commissions
│   ├── en.json                         # +same namespaces
│   └── fr.json                         # +same namespaces
└── App.tsx                             # +2 routes (/finanzas, /mis-liquidaciones)
```

---

## Implementation Phases

### Phase 1: Foundation (backend only)

**Goal:** Database schema, ORM models, core services, and basic endpoints.

**Deliverables:**
- Alembic migration `020_financial_command_center.py` — 3 tables + indexes
- 6 ORM models in `models.py` (3 new tables + 3 existing table models)
- `liquidation_service.py` — `generate_liquidation()`, `generate_bulk_liquidations()`, `get_liquidation_detail()`, `update_liquidation_status()`, `create_payout()`, `get_payouts_for_liquidation()`
- `financial_dashboard_service.py` — `get_financial_summary()`, `get_revenue_by_professional()`, `get_revenue_by_treatment()`, `get_daily_cash_flow()`, `get_mom_growth()`, `get_top_treatments()`, `get_pending_collections()`
- Core endpoints in `admin_routes.py`:
  - `POST /admin/liquidations/generate` (EP-FC-01)
  - `POST /admin/liquidations/generate-bulk` (EP-FC-02)
  - `GET /admin/liquidations` (EP-FC-03)
  - `GET /admin/liquidations/{id}` (EP-FC-04)
  - `PATCH /admin/liquidations/{id}` (EP-FC-05)
  - `POST /admin/liquidations/{id}/payout` (EP-FC-06)
  - `GET /admin/liquidations/{id}/payouts` (EP-FC-07)
  - `GET /admin/financial-dashboard` (EP-FC-08)

**Exit criteria:** All endpoints return correct data via API testing (curl/Postman). Idempotency verified. Calculations match existing `get_professionals_liquidation()`.

### Phase 2: Financial Dashboard (backend + frontend)

**Goal:** CEO can see financial metrics and manage liquidations from `/finanzas`.

**Deliverables:**
- `FinancialCommandCenterView.tsx` with 3 tabs
- `FinancialDashboard.tsx` — KPI cards, bar chart, pie chart, line chart, pending collections, MoM comparison
- `LiquidationManager.tsx` — period selector, bulk generate, liquidation table, expandable detail
- `LiquidationStatusBadge.tsx` — color-coded status badges
- `CommissionEditor.tsx` — modal for configuring commissions
- Commission endpoints:
  - `GET /admin/professionals/{id}/commissions` (EP-FC-09)
  - `PUT /admin/professionals/{id}/commissions` (EP-FC-10)
- TypeScript types in `finance.ts`

**Exit criteria:** CEO logs in, navigates to `/finanzas`, sees all 3 tabs with live data. Can generate liquidations, view details, approve, and configure commissions.

### Phase 3: PDF + Email

**Goal:** Liquidation PDFs are generated, cached, and can be emailed to professionals.

**Deliverables:**
- `templates/liquidation/liquidation_statement.html` — Jinja2 PDF template
- `templates/liquidation/liquidation_email.html` — Email body template
- PDF generation logic in `liquidation_service.py` (or separate `generate_pdf()` function)
- PDF endpoint: `GET /admin/liquidations/{id}/pdf` (EP-FC-12)
- Email endpoint: `POST /admin/liquidations/{id}/send-email` (EP-FC-13)
- PDF cache invalidation on status change, payout creation, notes update

**Exit criteria:** PDF downloads with correct data, proper formatting (A4), and clinic language. Email sends with PDF attachment. Cache invalidation works correctly.

### Phase 4: Professional Portal

**Goal:** Professionals can view their own liquidations at `/mis-liquidaciones`.

**Deliverables:**
- `/my/` endpoints for professional self-service:
  - `GET /my/liquidations`
  - `GET /my/liquidations/{id}`
  - `GET /my/liquidations/{id}/pdf`
  - `GET /my/commissions`
- `ProfessionalLiquidationsView.tsx` — read-only view of own liquidations
- RBAC enforcement: extract `professional_id` from JWT, filter by it, GET-only
- Route in `App.tsx` with `allowedRoles={['professional']}`

**Exit criteria:** Professional logs in, navigates to `/mis-liquidaciones`, sees only their own liquidations. Can download PDFs. Cannot modify anything.

### Phase 5: Reconciliation + Polish

**Goal:** Financial reconciliation is available and the system is production-ready.

**Deliverables:**
- Reconciliation endpoint: `GET /admin/reconciliation` (EP-FC-11)
- `ReconciliationView.tsx` — summary cards, discrepancy list with resolve/ignore actions
- Complete i18n in es/en/fr for all new namespaces (finance, liquidation, reconciliation, commissions, professional_liquidations)
- Error handling for all edge cases (empty periods, invalid dates, missing professionals)
- Audit trail verification — all status changes logged in `notes` JSONB
- Responsive design verification (desktop, tablet, mobile)
- Scroll isolation verification (`h-screen` + `overflow-hidden` global, `overflow-y-auto` internal)

**Exit criteria:** All acceptance criteria from specs are met. CEO can perform full liquidation lifecycle: generate → review → approve → pay → send PDF. Reconciliation shows accurate data. i18n works in all 3 languages.

---

## Risks and Mitigations

### R-01: Large migration on production with existing data

**Risk:** Migration 020 creates 3 new tables. If the production database is large or has lock contention, the migration could timeout or fail.

**Impact:** High — blocks deployment of the entire feature.

**Mitigation:**
- Migration is additive only (CREATE TABLE, CREATE INDEX) — no ALTER TABLE on existing tables
- Run `alembic upgrade head` during low-traffic hours
- Test migration on a staging copy of production data first
- Have rollback plan ready: `alembic downgrade -1`
- Indexes are created after tables to minimize lock duration

### R-02: Commission changes affecting historical liquidations

**Risk:** If a CEO changes a professional's commission rate, there's a concern that it might retroactively affect already-generated liquidations.

**Impact:** High — financial accuracy is critical. Trust in the system would be destroyed.

**Mitigation:**
- Commission rates are **snapshotted** at liquidation generation time. The `commission_pct` and `commission_amount` are stored directly on `liquidation_records`.
- Changing commission rates in `professional_commissions` only affects **future** liquidation generations.
- The audit trail in `notes` records when commissions were updated, providing full traceability.
- UI should display a warning when changing commissions: "This will only affect future liquidations."

### R-03: Performance of financial dashboard queries on large datasets

**Risk:** Aggregation queries (SUM, GROUP BY) over months of appointment data could be slow, especially with many professionals and treatments.

**Impact:** Medium — slow dashboard loads degrade UX but don't break functionality.

**Mitigation:**
- All aggregation queries include `WHERE tenant_id = $1` — indexes on `tenant_id` ensure fast filtering
- Date range filters (`period_start`, `period_end`) further reduce the data scanned
- Composite index on `appointments(tenant_id, professional_id, appointment_date)` supports both liquidation and dashboard queries
- If needed, implement query result caching (Redis) with TTL of 5 minutes for dashboard data
- Monitor query execution times; add EXPLAIN ANALYZE indexes if queries exceed 500ms

### R-04: PDF generation memory usage

**Risk:** WeasyPrint loads the entire HTML document and renders it to PDF in memory. For liquidations with many treatment groups (hundreds of appointments), this could consume significant memory.

**Impact:** Medium — could cause OOM errors on memory-constrained deployments.

**Mitigation:**
- WeasyPrint runs in a thread executor (`run_in_executor`), not blocking the async event loop
- PDF generation is triggered on-demand (when user clicks download), not pre-generated for all liquidations
- Disk caching means repeated downloads of the same liquidation don't re-render
- If memory becomes an issue, consider pagination in the PDF template (page breaks every N patients)
- Monitor memory usage in production; set `WEASYPRINT_MAX_PAGES` if needed

### R-05: Scope creep

**Risk:** The Financial Command Center is a large change with many interconnected components. There's a high risk of scope creep — adding features like multi-currency, tax management, or payment gateway integration.

**Impact:** High — delays delivery, increases bug surface, complicates testing.

**Mitigation:**
- Explicit out-of-scope items documented in the proposal (no MercadoPago/Stripe, no AFIP invoicing, no tax management, no forecasting, ARS only)
- Phased implementation with clear exit criteria per phase
- Each phase is independently deployable and testable
- Regular progress check-ins against the phase checklist

### R-06: Role confusion and unauthorized access

**Risk:** CEO, professional, and secretary roles have different permissions. A bug in RBAC could expose financial data to unauthorized users.

**Impact:** High — data breach, compliance violation.

**Mitigation:**
- Backend: Every financial endpoint checks `current_user.role` before processing
- Frontend: `ProtectedRoute` with `allowedRoles` prevents unauthorized route access
- Professional `/my/` endpoints extract `professional_id` from JWT and enforce `WHERE professional_id = {jwt_id}`
- Tenant isolation: every query includes `WHERE tenant_id = $1`
- Test RBAC explicitly: login as each role and verify access/denial for every endpoint
