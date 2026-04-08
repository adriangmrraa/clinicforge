# SDD Proposal: Clinic Payment & Financing Configuration

**Change**: `clinic-payment-financing-config`
**Status**: PROPOSED
**Date**: 2026-04-07
**Author**: SDD Orchestrator

---

## 1. Intent

### Problem Statement

The patient-facing AI agent cannot answer five of the most common payment queries that any prospective patient asks before booking. This is a critical gap that causes unnecessary human escalations and lost conversions.

**The five unanswered queries:**

| # | Patient message | Agent response today | Expected response |
|---|-----------------|---------------------|-------------------|
| Q1 | "¿Aceptan tarjeta de credito?" | "No tengo esa información, te comunico con la clínica" | "Sí, aceptamos tarjeta de crédito y débito." |
| Q2 | "¿Se puede pagar en cuotas?" | "No tengo esa información, te comunico con la clínica" | "Sí, trabajamos con hasta 6 cuotas sin interés con Visa y Mastercard." |
| Q3 | "¿Hacen descuento si pago en efectivo?" | "No tengo esa información, te comunico con la clínica" | "Sí, hay un 10 % de descuento pagando en efectivo." |
| Q4 | "¿Aceptan Mercado Pago?" | "No tengo esa información, te comunico con la clínica" | "Sí, podés pagar por Mercado Pago. También transferencia bancaria." |
| Q5 | "¿Aceptan cripto / Bitcoin?" | "No tengo esa información, te comunico con la clínica" | "En este momento no trabajamos con criptomonedas." |

**Root cause**: The `tenants` table only stores `bank_cbu`, `bank_alias`, `bank_holder_name`, and `consultation_price`. There is no structured storage for payment method support, financing terms, or cash discounts. The agent therefore has nothing to inject into the system prompt for this domain and correctly defaults to escalation.

### Why This Matters

- **Conversion rate**: Payment Q&A happens before the booking decision. Every escalation to a human for a question the system should answer is a friction point that reduces conversion.
- **Multi-tenancy**: Each clinic has different payment arrangements. A hardcoded answer in the prompt is not an option; this must be per-tenant data.
- **Legal correctness**: Financing claims ("sin interés", "12 cuotas") must reflect the clinic's actual agreement with card issuers. If the agreement changes, the clinic administrator must be able to update the agent's behavior without a code deploy.

---

## 2. Scope

### In Scope

| Area | What Changes |
|------|-------------|
| PostgreSQL schema | 8 new nullable columns on `tenants` table |
| Alembic migration | `035_add_payment_financing_config.py` (upgrade + downgrade) |
| SQLAlchemy model | `Tenant` class in `models.py` |
| Backend endpoint | `PUT /admin/tenants/{id}` — accept and persist new fields |
| System prompt formatter | New `_format_payment_options()` helper in `main.py` |
| `build_system_prompt()` | Inject payment/financing section after existing bank section |
| Frontend modal | New collapsible "Pagos y Financiacion" section in Tab 1 (Clinicas) |
| i18n | New keys in `es.json`, `en.json`, `fr.json` |

### Out of Scope

- **Appointment billing flow**: The existing seña/payment receipt flow (`verify_payment_receipt`, `billing_amount`) is unchanged.
- **Nova**: Internal AI assistant — separate prompt, no changes.
- **ROI dashboard**: Payment method analytics are not in scope.
- **Insurance providers**: The existing `tenant_insurance_providers` table is unchanged.
- **Per-professional pricing**: `professionals.consultation_price` override is unchanged.

---

## 3. Approach

### Option A — FAQ-only approach

Add a free-text FAQ entry per clinic for each payment-related question. The agent retrieves it via RAG.

**Pros**: Zero schema change, zero migration, zero endpoint change. Done in 2 hours.

**Cons**:
- Relies on clinic admins writing well-formed FAQs. In practice they write "sí aceptamos tarjeta" without specifying which cards, conditions, or installment count.
- Cannot enforce validation (e.g., cash discount must be 0-100, installments must be 1-24).
- Agent cannot reason structurally about combinations ("¿tienen cuotas sin interés?" requires knowing BOTH `financing_available=true` AND `installments_interest_free=true`).
- No way to conditionally show financing sub-fields in the UI (show installment count only when `financing_available=true`).

### Option B — Structured fields (SELECTED)

Add 8 typed nullable columns to `tenants`. Expose them in the modal with conditional UI logic. Generate a structured prompt section via a dedicated formatter.

**Pros**:
- Type-safe: `max_installments` is an int with a 1-24 constraint; `cash_discount_percent` is decimal(5,2) with 0-100 check; `payment_methods` is a validated JSONB array.
- Prompt formatter produces consistent, grammatically correct Spanish text regardless of how the admin fills in the data.
- Frontend can show/hide financing sub-fields based on `financing_available` toggle.
- Fully backward compatible: all fields nullable; tenants that don't configure them get no prompt section (agent behavior unchanged).
- Auditable: the payment terms are in the DB, queryable, not buried in free-text FAQs.

**Cons**:
- Requires one migration, one model change, one endpoint change, one frontend section.
- Slightly more front-end complexity for the conditional visibility.

**Decision: Option B wins.** The validation and conditional UI logic are worth the extra 3-4 hours. The FAQ approach produces ambiguous, unvalidated data that causes agent hallucinations over time.

---

## 4. Success Criteria

The five patient queries from the problem statement MUST be answerable by the agent after this change is deployed, given the following pre-conditions:

| Query | Pre-condition | Agent MUST answer |
|-------|--------------|------------------|
| Q1 — card | `payment_methods` includes `"credit_card"` | Confirm card acceptance, mention relevant brands if in `financing_notes` |
| Q2 — installments | `financing_available=true`, `max_installments=6`, `installments_interest_free=true` | "Hasta 6 cuotas sin interés" + provider if set |
| Q3 — cash discount | `cash_discount_percent=10` | "10 % de descuento pagando en efectivo" |
| Q4 — Mercado Pago | `payment_methods` includes `"mercado_pago"` | Confirm Mercado Pago acceptance |
| Q5 — crypto | `accepts_crypto=false` (or not set) | Politely deny, offer alternatives |

Additionally:
- [ ] Tenants with ALL new fields NULL show zero change in agent behavior (backward compat).
- [ ] Validation rejects `max_installments` outside 1-24 with HTTP 422.
- [ ] Validation rejects `cash_discount_percent` outside 0-100 with HTTP 422.
- [ ] Frontend "Pagos y Financiacion" section is collapsible and only shows financing sub-fields when `financing_available` is toggled on.
- [ ] All new UI strings appear correctly in es, en, fr.

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Clinic enters outdated financing info (e.g., expired card agreement) | MEDIUM | Add a `financing_notes` free-text field where admin can qualify claims ("válido hasta dic 2026"). The agent uses this qualifier in its response. |
| Agent over-commits on financing (e.g., says "sin interés" when it changed) | MEDIUM | `financing_notes` field as qualifier. Add a prohibition in the prompt: "No garantizés condiciones de financiación — siempre decí que las condiciones son informativas y pueden variar." |
| `payment_methods` JSONB array grows unbounded / invalid values | LOW | Validated on insert: only allow enum values `["cash","credit_card","debit_card","transfer","mercado_pago","rapipago","pagofacil","modo","uala","naranja","crypto","other"]`. Frontend uses checkboxes, not free text. |
| Migration collides with another in-flight migration | LOW | Confirmed current head is 034 (insurance). This change uses 035. |
| Prompt section becomes too long for high-installment configs | LOW | `_format_payment_options()` always emits a compact block (max ~6 lines). Tested with a maximally-configured tenant. |

---

## 6. Implementation Order

1. Alembic migration 035 (schema)
2. `models.py` — Tenant ORM class update
3. `admin_routes.py` — `update_tenant()` to accept and persist new fields
4. `main.py` — `_format_payment_options()` + `build_system_prompt()` integration
5. Frontend modal section (Tab 1, Clinicas)
6. i18n keys
7. Tests (TDD order: test before each implementation step)
8. E2E verification of the 5 patient query scenarios
