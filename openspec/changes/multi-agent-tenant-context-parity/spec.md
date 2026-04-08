# SDD Spec: Multi-Agent Tenant Context Parity

**Change**: `multi-agent-tenant-context-parity`
**Project**: ClinicForge
**Scope**: `orchestrator_service/agents/` only — no changes to TORA solo, tools, models, or DB schema

---

## RFC Keywords

MUST = mandatory, SHALL = equivalent to MUST, SHOULD = recommended, MAY = optional.

---

## REQ-1 — Tenant Context Builder

A new module `orchestrator_service/agents/tenant_context.py` MUST expose an async function `build_tenant_context_blocks()` with the following contract:

### REQ-1.1 — Signature

```python
async def build_tenant_context_blocks(
    pool,
    tenant_id: int,
    user_message_text: str = "",
    intent_tags: set[str] | None = None,
) -> dict[str, str | dict]:
    ...
```

### REQ-1.2 — Returned dict shape

The dict MUST contain the following keys (all values are strings, except `sede_info` which is a dict):

| Key | Source / Formatter | Empty when... |
|-----|--------------------|---------------|
| `clinic_basics` | clinic_name, bot_name, specialty_pitch, working_hours summary | always non-empty (clinic_name fallback) |
| `insurance_section` | `_format_insurance_providers()` from main.py | tenant has no insurance providers |
| `payment_section` | `_format_payment_options()` from main.py | none of the 8 payment fields configured |
| `special_conditions_block` | `_format_special_conditions()` from main.py | none of the 8 special-conditions fields configured |
| `support_policy_block` | `_format_support_policy()` from main.py | none of the 7 support-complaints fields configured |
| `derivation_rules_section` | `_format_derivation_rules()` from main.py | no active derivation rules |
| `holidays_section` | `_format_upcoming_holidays()` from main.py | no holidays in next 30 days |
| `faqs_section` | RAG top-K via `format_all_context_with_rag()` | no FAQs configured OR RAG returns empty |
| `bank_info` | bank_cbu/alias/holder formatted | bank fields all null |
| `sede_info` | dict with location/address/maps_url for current day | working_hours not configured |

### REQ-1.3 — Behavior

- Function MUST do all DB queries in parallel where possible (`asyncio.gather`).
- Function MUST be idempotent and side-effect-free (no DB writes).
- Function MUST tolerate any individual block failing (catch exception, return empty string for that block, log at debug level — non-fatal).
- Function MUST NOT raise on database errors — return a dict where the failing block is empty.
- Function MUST reuse existing formatters from `main.py`. NO duplication of formatter logic.
- Function SHOULD complete in under 500ms for typical tenants (3-5 DB queries + RAG embedding lookup).

### REQ-1.4 — Imports

The module MUST import its formatters from `main` (not re-implement them):

```python
from main import (
    _format_insurance_providers,
    _format_payment_options,
    _format_special_conditions,
    _format_support_policy,
    _format_derivation_rules,
)
```

If the import fails (e.g., circular import), the function MUST log a clear error and return a dict with all empty values (so the multi-agent still works, just without the context — graceful degradation).

---

## REQ-2 — AgentState extension

`orchestrator_service/agents/state.py`'s `AgentState` TypedDict MUST gain a new field:

```python
tenant_context: NotRequired[dict[str, str | dict]]
```

The field is `NotRequired` so existing tests/callers that build AgentState without it remain valid.

---

## REQ-3 — Graph entry point integration

`orchestrator_service/agents/graph.py`'s `run_turn()` MUST:

### REQ-3.1
Call `classify_intent(messages)` from `services/buffer_task` (or a port of it) to compute `intent_tags` from the patient's incoming messages. If import fails, default to `set()` (safe default = inject all blocks).

### REQ-3.2
Call `build_tenant_context_blocks(pool, tenant_id, user_message_text, intent_tags)` ONCE per turn, before dispatching to any specialist.

### REQ-3.3
Store the result in `state["tenant_context"]` so all specialists in the same turn read from it.

### REQ-3.4
The call MUST be wrapped in try/except. On failure, log the error and set `state["tenant_context"] = {}` so specialists fall back to their bare prompts.

---

## REQ-4 — Specialist prompt integration

`orchestrator_service/agents/specialists.py` — each of the 6 specialists MUST be updated to consume the relevant blocks from `state["tenant_context"]` per the whitelist below.

### REQ-4.1 — Block-to-specialist whitelist (NORMATIVE)

| Specialist | Blocks the specialist receives in its prompt |
|------------|------------------------------------------------|
| **Reception** (general questions, greetings, FAQs, holidays) | `clinic_basics`, `faqs_section`, `holidays_section` |
| **Booking** (turnos, agendamiento, derivation) | `clinic_basics`, `holidays_section`, `derivation_rules_section`, `sede_info` |
| **Triage** (síntomas, urgencia, condiciones especiales) | `clinic_basics`, `special_conditions_block` |
| **Billing** (precios, obras sociales, pagos) | `clinic_basics`, `insurance_section`, `payment_section`, `bank_info` |
| **Anamnesis** (recolección de historial médico) | `clinic_basics`, `special_conditions_block` |
| **Handoff** (quejas, escalación humana) | `clinic_basics`, `support_policy_block` |

### REQ-4.2 — Prompt template format

Each specialist's existing system prompt template MUST be modified to interpolate the relevant blocks. Example for Booking:

```python
BOOKING_SYSTEM_PROMPT = """You are the Booking specialist...

{clinic_basics}

{holidays_section}

{derivation_rules_section}

{sede_info_text}

[existing booking instructions...]
"""
```

Empty blocks render as empty strings → zero overhead for tenants without that config.

### REQ-4.3 — Defensive default

If `state.get("tenant_context")` is None or missing keys, the specialist MUST use empty strings for the missing blocks (graceful degradation).

### REQ-4.4 — Token budget impact

Each specialist's prompt with the new blocks SHOULD remain under 8000 tokens for typical tenants. The whitelist ensures no specialist gets all 8 blocks at once.

---

## REQ-5 — Backwards compatibility

### REQ-5.1
Tenants with NO configured context (legacy clinics) MUST experience zero behavior change. All blocks return empty strings; specialists behave as they did before this pack.

### REQ-5.2
TORA solo (`build_system_prompt`) MUST NOT be touched by this pack. It already has all the blocks.

### REQ-5.3
LangChain tools (`DENTAL_TOOLS`) MUST NOT be touched. They already work in both engines.

### REQ-5.4
The Pydantic AgentState change (REQ-2) MUST be additive (`NotRequired`). Existing callers that construct AgentState without `tenant_context` MUST continue to work.

---

## REQ-6 — Acceptance scenarios

### REQ-6.1 — Scenario A: Booking specialist sees configured holiday

**Given**: Tenant 1 has a custom holiday `{date: "2026-12-25", name: "Navidad", holiday_type: "closure"}` in `tenant_holidays`.

**When**: Patient sends "¿Atienden el 25 de diciembre?", supervisor routes to Booking specialist.

**Then**: The Booking specialist's prompt includes the formatted holidays section with "2026-12-25: Navidad — CERRADO". The specialist's response MUST mention that the clinic is closed that day.

### REQ-6.2 — Scenario B: Billing specialist answers payment question

**Given**: Tenant 1 has `payment_methods=["card","cash","transfer"]`, `financing_available=true`, `max_installments=12`.

**When**: Patient asks "¿tienen cuotas?", supervisor routes to Billing.

**Then**: The Billing specialist's prompt includes the formatted payment_section. Response mentions cuotas + max 12.

### REQ-6.3 — Scenario C: Triage specialist applies special_conditions

**Given**: Tenant 1 has `accepts_pregnant_patients=false`, `pregnancy_notes="Por seguridad, no atendemos embarazadas en cirugías"`.

**When**: Patient says "estoy embarazada y necesito una extracción", supervisor routes to Triage.

**Then**: The Triage specialist's prompt includes the formatted special_conditions block. Response uses the configured `pregnancy_notes` text and refuses to schedule a surgery (within the legal disclaimer framing).

### REQ-6.4 — Scenario D: Handoff follows graduated complaint protocol

**Given**: Tenant 1 has `complaint_handling_protocol={level_1: "Empatizar y registrar", level_2: "Ofrecer ajuste gratis", level_3: "Escalar al CEO directamente"}`.

**When**: Patient sends a complaint message, supervisor routes to Handoff.

**Then**: The Handoff specialist's prompt includes the support_policy_block with the 3 levels. Response starts at level 1 (empathize) and only escalates if the patient persists.

### REQ-6.5 — Scenario E: Empty config = no regression

**Given**: Tenant 99 has no custom config (just clinic_name set).

**When**: Patient sends any message.

**Then**: The relevant specialist's prompt includes only the clinic_basics block. All other blocks are empty strings. The specialist behaves identically to its pre-pack version. **No new prompt content is injected.**

### REQ-6.6 — Scenario F: Token budget bound

**Given**: Tenant with all 8 blocks fully configured.

**When**: Booking specialist is invoked.

**Then**: Booking's prompt contains only `clinic_basics + holidays_section + derivation_rules_section + sede_info`. The other 4 blocks (insurance, payment, special_conditions, support_policy) are NOT in Booking's prompt. Token count for Booking's full prompt with these blocks SHOULD be under 8000 tokens.

---

## REQ-7 — Tenant isolation

### REQ-7.1
`build_tenant_context_blocks(pool, tenant_id, ...)` MUST take `tenant_id` as a required parameter. All internal queries MUST filter by `WHERE tenant_id = $1`. No cross-tenant data leakage.

### REQ-7.2
The graph entry point MUST resolve `tenant_id` from the conversation context (existing pattern), not from user input.

### REQ-7.3
The AgentState `tenant_context` field MUST belong to a single turn. It SHALL NOT be persisted to LangGraph checkpoints (or if persisted, MUST be re-built on resume — never re-used across turns).

---

## REQ-8 — Tests

### REQ-8.1
A new test file `tests/test_multi_agent_tenant_context.py` MUST exist with at least the following test classes:

- `TestBuildTenantContextBlocks` — unit tests for the builder, with mocked DB:
  - `test_empty_tenant_returns_empty_blocks` (legacy clinic)
  - `test_full_tenant_returns_all_blocks_populated`
  - `test_individual_formatter_failure_returns_empty_for_that_block`
  - `test_intent_tags_passed_through_to_formatters`

- `TestSpecialistBlockMapping` — verify each specialist receives the right blocks:
  - `test_reception_gets_clinic_basics_faqs_holidays`
  - `test_booking_gets_holidays_derivation_sede`
  - `test_triage_gets_special_conditions`
  - `test_billing_gets_insurance_payment_bank`
  - `test_anamnesis_gets_special_conditions`
  - `test_handoff_gets_support_policy`
  - `test_no_specialist_gets_all_blocks` (negative test — bound enforcement)

- `TestAgentStatePropagation`:
  - `test_run_turn_populates_tenant_context_in_state`
  - `test_run_turn_handles_builder_exception_gracefully`

### REQ-8.2
Tests MUST be pure unit tests (no DB, no HTTP, no LangChain LLM calls). Use mocks for `pool.fetch`/`fetchrow` and import the formatters from `main.py` directly.

### REQ-8.3
Tests MUST NOT be required to run via CI in this pack (user runs tests manually). Just need to be writable and importable.
