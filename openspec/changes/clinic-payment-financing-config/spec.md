# SPEC: Clinic Payment & Financing Configuration

**Change**: `clinic-payment-financing-config`
**Project**: ClinicForge
**Scope**: `tenants` schema + backend endpoint + system prompt formatter + frontend modal section
**Out of scope**: Nova, seña/receipt flow, insurance providers, per-professional pricing

---

## RFC Keywords

Throughout this document: MUST = mandatory, SHALL = equivalent to MUST, SHOULD = recommended, MAY = optional.

---

## REQ-1: Database Schema — 8 new columns on `tenants`

**REQ-1.1** The `tenants` table MUST gain the following columns via Alembic migration `035_add_payment_financing_config.py`:

| Column | Type | Default | Nullable | Constraint |
|--------|------|---------|----------|------------|
| `payment_methods` | JSONB | NULL | YES | Array of allowed method strings |
| `financing_available` | BOOLEAN | FALSE | YES (server_default 'false') | — |
| `max_installments` | INTEGER | NULL | YES | CHECK 1 <= value <= 24 |
| `installments_interest_free` | BOOLEAN | TRUE | YES (server_default 'true') | — |
| `financing_provider` | TEXT | NULL | YES | — |
| `financing_notes` | TEXT | NULL | YES | — |
| `cash_discount_percent` | DECIMAL(5,2) | NULL | YES | CHECK 0 <= value <= 100 |
| `accepts_crypto` | BOOLEAN | FALSE | YES (server_default 'false') | — |

**REQ-1.2** The migration MUST include both `upgrade()` and `downgrade()` functions.

**REQ-1.3** `downgrade()` MUST drop all 8 columns in reverse order with `IF EXISTS` guard.

**REQ-1.4** The `payment_methods` column MUST accept NULL and also a JSON array. The backend MUST validate that each element is one of the allowed method tokens before persisting (see REQ-2.3).

**REQ-1.5** `max_installments` CHECK constraint MUST be named `ck_tenants_max_installments_range`.

**REQ-1.6** `cash_discount_percent` CHECK constraint MUST be named `ck_tenants_cash_discount_range`.

**REQ-1.7** The SQLAlchemy `Tenant` model in `models.py` MUST be updated to include all 8 columns, matching the DB types exactly.

---

## REQ-2: Backend Endpoint — PUT /admin/tenants/{id}

**REQ-2.1** The existing `PUT /admin/tenants/{tenant_id}` endpoint (in `admin_routes.py`) MUST accept all 8 new fields in the request body (dict-based, no Pydantic model required — consistent with existing endpoint pattern).

**REQ-2.2** Fields MUST be handled with the same presence-check pattern already used: `if "field_name" in data:` guards so that omitting a field in the request does NOT overwrite it to NULL.

**REQ-2.3** `payment_methods` validation MUST:
- Accept `None` or missing key (no change)
- Accept an empty list `[]` (stored as NULL)
- Reject any element not in the allowed set: `{"cash", "credit_card", "debit_card", "transfer", "mercado_pago", "rapipago", "pagofacil", "modo", "uala", "naranja", "crypto", "other"}`
- If invalid elements are present, raise `HTTPException(status_code=422, detail="payment_methods contains invalid values: {invalid_set}")`

**REQ-2.4** `max_installments` validation MUST:
- Accept `None` or missing (no change)
- Accept integer 1-24 (inclusive)
- Reject values outside that range with `HTTPException(status_code=422, detail="max_installments must be between 1 and 24")`
- Coerce string "6" to int 6 (consistent with `max_chairs` pattern)

**REQ-2.5** `cash_discount_percent` validation MUST:
- Accept `None` or missing (no change)
- Accept float/decimal 0.0-100.0 (inclusive)
- Reject values outside that range with `HTTPException(status_code=422, detail="cash_discount_percent must be between 0 and 100")`
- Coerce string "10.5" to float 10.5

**REQ-2.6** `financing_available`, `installments_interest_free`, `accepts_crypto` MUST be stored as Python `bool`. Truthy string coercion ("true", "1", "yes") MUST be handled.

**REQ-2.7** `financing_provider` and `financing_notes` MUST be stored as `None` when the value is an empty string `""` (consistent with `bank_alias` pattern).

**REQ-2.8** The `GET /admin/tenants` endpoint (existing) MUST include all 8 new fields in its SELECT query so the frontend can read them on modal open.

---

## REQ-3: System Prompt Formatter — _format_payment_options()

**REQ-3.1** A new function `_format_payment_options(tenant: dict) -> str` MUST be added to `main.py`.

**REQ-3.2** If ALL 8 new fields are NULL/False/empty, the function MUST return an empty string `""`. In this case, no "MEDIOS DE PAGO" section is emitted in the prompt. Agent behavior for payment queries MUST remain identical to the pre-change state (escalation to human).

**REQ-3.3** If at least one payment field has a meaningful value (truthy, or a non-empty list), the function MUST return a prompt block with the heading `## MEDIOS DE PAGO Y FINANCIACIÓN`.

**REQ-3.4** The output MUST include a disclaimer line: `"(Información orientativa — las condiciones pueden variar. Para confirmación final, derivar al administrativo de la clínica.)"`.

**REQ-3.5** Payment methods MUST be formatted as a human-readable Spanish enumeration using the following label map:

| Token | Spanish label |
|-------|--------------|
| `cash` | Efectivo |
| `credit_card` | Tarjeta de crédito |
| `debit_card` | Tarjeta de débito |
| `transfer` | Transferencia bancaria |
| `mercado_pago` | Mercado Pago |
| `rapipago` | Rapipago |
| `pagofacil` | Pago Fácil |
| `modo` | MODO |
| `uala` | Ualá |
| `naranja` | Tarjeta Naranja |
| `crypto` | Criptomonedas |
| `other` | Otros medios |

**REQ-3.6** Financing block rules:
- MUST be emitted only if `financing_available` is `True`.
- MUST include installment count if `max_installments` is set: "Hasta {N} cuotas".
- MUST include "sin interés" if `installments_interest_free=True`, "con interés" otherwise.
- MUST include `financing_provider` name if set: "con {provider}".
- MUST include `financing_notes` verbatim as a sub-note if set.

**REQ-3.7** Cash discount block rules:
- MUST be emitted only if `cash_discount_percent` is not NULL and > 0.
- Format: "{N}% de descuento pagando en efectivo."

**REQ-3.8** Crypto block rules:
- If `accepts_crypto=True`: emit "Criptomonedas: sí aceptamos pago en criptomonedas."
- If `accepts_crypto=False` AND `crypto` is NOT in `payment_methods`: emit nothing (absence of crypto is the default — no need to state it).
- If the agent is asked about crypto and the section is empty, it MAY escalate to human.

**REQ-3.9** Injection point: `_format_payment_options()` MUST be called in `build_system_prompt()` and its result injected IMMEDIATELY AFTER the `bank_section` block (which ends after the seña flow rules), before the next section.

**REQ-3.10** The new parameters for `build_system_prompt()` MUST be:
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
All parameters default to their "empty/off" state so that all existing callers work without modification.

---

## REQ-4: Agent Behavior — Given/When/Then Scenarios

The following 5 scenarios MUST pass after implementation:

### Scenario Q1 — Card acceptance

```
GIVEN tenant has payment_methods = ["credit_card", "debit_card"]
WHEN patient sends "¿aceptan tarjeta de crédito?"
THEN agent responds with a message that:
  - CONTAINS "tarjeta de crédito" (or "crédito")
  - DOES NOT contain "no tengo esa información"
  - DOES NOT call derivhumano
```

### Scenario Q2 — Installments

```
GIVEN tenant has financing_available=true, max_installments=6, installments_interest_free=true, financing_provider="Mercado Pago"
WHEN patient sends "¿puedo pagar en cuotas?"
THEN agent responds with a message that:
  - CONTAINS "6 cuotas" (or "seis cuotas")
  - CONTAINS "sin interés" (or "sin cargo")
  - CONTAINS "Mercado Pago"
  - DOES NOT call derivhumano
```

### Scenario Q3 — Cash discount

```
GIVEN tenant has cash_discount_percent=10.0
WHEN patient sends "¿hay descuento por efectivo?"
THEN agent responds with a message that:
  - CONTAINS "10" followed by "%" or "descuento"
  - CONTAINS "efectivo"
  - DOES NOT call derivhumano
```

### Scenario Q4 — Mercado Pago / external financing

```
GIVEN tenant has payment_methods = ["transfer", "mercado_pago"], financing_available=false
WHEN patient sends "¿puedo pagar con Mercado Pago?"
THEN agent responds with a message that:
  - CONTAINS "Mercado Pago"
  - DOES NOT say "no acepto" or "no trabajamos con Mercado Pago"
  - DOES NOT call derivhumano
```

### Scenario Q5 — Crypto (not accepted)

```
GIVEN tenant has accepts_crypto=false AND "crypto" NOT in payment_methods
WHEN patient sends "¿aceptan bitcoin / cripto?"
THEN agent responds with a message that:
  - DOES NOT confirm crypto acceptance
  - OFFERS an alternative payment method OR escalates to human (both acceptable)
  - DOES NOT say "no tengo información" (it DOES have information: crypto is not accepted)
```

---

## REQ-5: Internationalization (i18n)

**REQ-5.1** All new visible strings in the frontend MUST use the `useTranslation()` hook. Hardcoded Spanish strings are NOT allowed.

**REQ-5.2** The following i18n keys MUST be added to `es.json`, `en.json`, and `fr.json`:

| Key | es | en | fr |
|-----|----|----|----|
| `clinics.payment_section` | Pagos y Financiación | Payments & Financing | Paiements & Financement |
| `clinics.payment_section_help` | Configurá los medios de pago que acepta la clínica. El agente usará esta info para responder preguntas de pacientes. | Configure the payment methods the clinic accepts. The agent uses this to answer patient queries. | Configurez les moyens de paiement acceptés par la clinique. L'agent utilise ces informations pour répondre aux questions des patients. |
| `clinics.payment_methods_label` | Medios de pago aceptados | Accepted payment methods | Moyens de paiement acceptés |
| `clinics.financing_available_label` | ¿Ofrecen financiación / cuotas? | Financing / installments available? | Financement / paiement en plusieurs fois disponible ? |
| `clinics.max_installments_label` | Cuotas máximas | Maximum installments | Nombre max. de versements |
| `clinics.max_installments_placeholder` | Ej: 6 | e.g. 6 | ex. : 6 |
| `clinics.installments_interest_free_label` | Sin interés | Interest-free | Sans intérêts |
| `clinics.financing_provider_label` | Proveedor de financiación | Financing provider | Fournisseur de financement |
| `clinics.financing_provider_placeholder` | Ej: Mercado Pago, Banco Galicia | e.g. Mercado Pago, Banco Galicia | ex. : Mercado Pago, Banco Galicia |
| `clinics.financing_notes_label` | Notas de financiación | Financing notes | Notes de financement |
| `clinics.financing_notes_placeholder` | Ej: Válido solo con Visa y Mastercard, hasta dic 2026 | e.g. Valid only for Visa and Mastercard, until Dec 2026 | ex. : Valable uniquement pour Visa et Mastercard, jusqu'en déc. 2026 |
| `clinics.cash_discount_label` | Descuento por pago en efectivo (%) | Cash payment discount (%) | Remise paiement en espèces (%) |
| `clinics.cash_discount_placeholder` | Ej: 10 | e.g. 10 | ex. : 10 |
| `clinics.accepts_crypto_label` | Aceptan criptomonedas | Accept cryptocurrency | Acceptent les cryptomonnaies |

---

## REQ-6: Backwards Compatibility

**REQ-6.1** ALL 8 new columns MUST be nullable (or have a server-side default of FALSE). A tenant with no payment configuration MUST behave identically to the pre-change system.

**REQ-6.2** All new parameters of `build_system_prompt()` MUST have defaults that reproduce the pre-change behavior. Any call site that does not pass the new parameters MUST NOT change its behavior.

**REQ-6.3** The existing `buffer_task.py` call to `build_system_prompt()` MUST be updated to pass the 8 new fields read from the tenant row. The tenant query in `buffer_task.py` MUST be extended to SELECT the 8 new columns.

**REQ-6.4** There MUST be no breaking change to any existing test. Existing tests that mock `build_system_prompt()` calls are unaffected because all new parameters are keyword-only with defaults.
