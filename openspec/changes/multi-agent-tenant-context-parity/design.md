# SDD Design: Multi-Agent Tenant Context Parity

**Change**: `multi-agent-tenant-context-parity`
**Status**: DESIGNED
**Date**: 2026-04-08

---

## Guiding principle (architectural north star)

**Each multi-agent specialist is a DEEPER, more FOCUSED expansion of ONE stage of TORA solo's system prompt — not a generic agent with TORA's blocks bolted on.**

TORA solo lives under a token budget constraint. Its single system prompt must cover identity, FAQs, booking flow, anamnesis, triage, billing, escalation, and treatment instructions all at once. Each section is necessarily shallow because all 8 must coexist.

Multi-agent flips that constraint. Each specialist owns ONE stage and has the full token budget for it. So:

- **TORA solo Reception** gets ~500 tokens for "identity + greeting + FAQs handling"
- **Multi-agent Reception** can have 2000 tokens for the SAME stage — with richer disambiguation rules, more nuanced FAQ-vs-tool decisions, more explicit handoff triggers

The same applies to every other stage. The multi-agent's value proposition is **stage depth**, enabled by **stage isolation**.

This pack delivers the **first half**: making the tenant-configured context blocks (insurance, payment, holidays, etc.) reach each specialist via a clean per-specialist whitelist. The **second half** — expanding each specialist's own prompt with richer stage-specific instructions — is intentionally deferred to a follow-up pack so this PR remains scope-bounded and reviewable.

The whitelist enforced in this pack is designed so the follow-up pack can extend each specialist's prompt without restructuring the context-injection mechanism.

---

## Architecture Decisions

### D1: Where to call the context builder — supervisor or graph entry?

**Decision: Graph entry point (`run_turn` in `agents/graph.py`).**

The supervisor decides WHICH specialist to invoke. The context builder runs BEFORE that decision because the supervisor itself may need the clinic_basics block for its own routing reasoning ("if patient mentions X and clinic offers Y..."). Calling the builder in the graph entry guarantees the supervisor has the same view as the specialists.

**Rejected**: building per specialist call. Would query the DB N times per turn (once per specialist invocation in the same turn). Wasteful.

**Rejected**: building inside the supervisor. The supervisor is a routing function; mixing data fetching there muddles its responsibility. Graph entry is the natural boundary.

---

### D2: How to pass context to specialists — AgentState dict vs prompt template variables

**Decision: AgentState dict with named keys, referenced in each specialist's prompt template at format time.**

```python
# graph.py
state["tenant_context"] = await build_tenant_context_blocks(...)
# specialists.py
prompt = BOOKING_PROMPT.format(**state["tenant_context"])
```

This keeps the specialist prompt templates declarative (named slots) and the data fetching centralized. Specialists do not call the DB themselves.

**Rejected**: passing as keyword arguments through every method signature. Fragile and verbose.

**Rejected**: a global context manager. Hidden coupling, hard to test.

---

### D3: Per-specialist block whitelist

**Decision: explicit dict in `specialists.py`** (not in `tenant_context.py`) so the mapping lives next to the specialists that consume it.

```python
SPECIALIST_BLOCKS = {
    "reception": ["clinic_basics", "faqs_section", "holidays_section"],
    "booking":   ["clinic_basics", "holidays_section", "derivation_rules_section", "sede_info_text"],
    "triage":    ["clinic_basics", "special_conditions_block"],
    "billing":   ["clinic_basics", "insurance_section", "payment_section", "bank_info"],
    "anamnesis": ["clinic_basics", "special_conditions_block"],
    "handoff":   ["clinic_basics", "support_policy_block"],
}
```

Why each specialist gets these and not others:

| Specialist | Why these blocks |
|-----------|------------------|
| Reception | First-touch greeting → bot_name + clinic_basics. Patient asks generic questions → FAQs. Patient asks "¿están abiertos hoy?" → holidays. NO insurance/payment because those are billing's job. NO special_conditions because Reception doesn't make medical decisions. |
| Booking | Needs to know when the clinic is closed (holidays + sede), which professional to derive to (rules + escalation), which sede applies for the requested day. Does NOT need insurance/payment (billing handles those AFTER booking). |
| Triage | Owns medical safety. Needs `special_conditions` to flag pregnant/diabetic/etc. patients before scheduling anything risky. Does NOT need payment/insurance (orthogonal). |
| Billing | Owns money conversations. Needs insurance coverage details, payment methods, financing options, bank info for seña. Does NOT need clinical context. |
| Anamnesis | Collects medical history. Needs `special_conditions` to know which questions to dig deeper on (e.g., if tenant flags diabetes as high-risk, ask follow-ups about diabetes medication). |
| Handoff | Owns escalation. Needs `support_policy` to follow the graduated complaint protocol and know which channel (email/phone) to escalate to. |

The whitelist is enforced at prompt-format time: blocks not in the list for a given specialist are simply not interpolated into its template.

---

### D4: Reuse formatters from `main.py` vs re-implementing

**Decision: import from `main.py`.**

The 6 formatters (`_format_insurance_providers`, `_format_payment_options`, `_format_special_conditions`, `_format_support_policy`, `_format_derivation_rules`, `_format_pre/post_instructions_dict`) are the source of truth for how each block is rendered. Re-implementing them in `agents/tenant_context.py` would create drift over time as one side gets fixes and the other doesn't.

Import path: `from main import _format_insurance_providers, ...`

**Cycle risk**: `main.py` does NOT import from `agents/`. The dependency graph is acyclic:

```
agents/tenant_context.py  →  main.py  →  (no agents/ imports)
agents/graph.py           →  agents/tenant_context.py
agents/specialists.py     →  state.py
```

**Fallback**: if the import ever fails (e.g., during refactoring), the builder logs a clear error and returns an all-empty dict. Specialists fall back to their bare prompts. Graceful degradation, not a hard crash.

---

### D5: Intent classification — port `classify_intent` or call buffer_task's

**Decision: import `classify_intent` from `services.buffer_task`** (not duplicate).

```python
# agents/graph.py
try:
    from services.buffer_task import classify_intent
except ImportError:
    def classify_intent(messages: list) -> set:
        return set()  # safe default = inject everything
```

The function is pure (no I/O, no state). Importing is safe and avoids duplication.

---

### D6: FAQs RAG — when to call it

**Decision: call RAG inside `build_tenant_context_blocks` once, store the result.**

The RAG function `format_all_context_with_rag(tenant_id, user_text, faqs)` from `services.embedding_service` already returns a dict with `faqs_section`, `insurance_section`, `derivation_section`, `instructions_section`. We use the `faqs_section` for Reception and (optionally) `insurance_section` for Billing if it's already RAG-filtered.

Strategy: prefer RAG-filtered sections over full sections when both are available. RAG section is shorter and semantically targeted.

```python
# Inside build_tenant_context_blocks
rag_context = await format_all_context_with_rag(pool, tenant_id, user_message_text, faqs)
faqs_section = rag_context.get("faqs_section") or _format_faqs_static(faqs)  # fallback
```

If RAG is unavailable (pgvector not configured), fall back to static formatter.

---

### D7: `clinic_basics` block content

This is a NEW block that doesn't exist in `main.py`. Define it here:

```python
def _format_clinic_basics(tenant_row: dict) -> str:
    """Always-present block for any specialist. Contains identity essentials."""
    bot_name = tenant_row.get("bot_name") or "TORA"
    clinic_name = tenant_row.get("clinic_name") or "la clínica"
    specialty = (tenant_row.get("system_prompt_template") or "").strip()
    parts = [
        f"## CLÍNICA",
        f"Sos {bot_name}, asistente virtual de {clinic_name}.",
    ]
    if specialty:
        parts.append(f"\n{specialty}")
    return "\n".join(parts)
```

Token budget: ~50-150 tokens depending on specialty_pitch length. Cheap.

---

### D8: `sede_info_text` block content

The `sede_info` returned by `tenant_context.py` is a dict (per spec REQ-1.2). For interpolation into the Booking specialist prompt, we need a STRING version. Add a sibling function:

```python
def _format_sede_info_text(sede_info: dict) -> str:
    if not sede_info:
        return ""
    loc = sede_info.get("location") or ""
    addr = sede_info.get("address") or ""
    maps = sede_info.get("maps_url") or ""
    if not loc and not addr:
        return ""
    parts = ["## SEDE PARA HOY"]
    if loc:
        parts.append(f"Ubicación: {loc}")
    if addr:
        parts.append(f"Dirección: {addr}")
    if maps:
        parts.append(f"Maps: {maps}")
    return "\n".join(parts)
```

The Booking template references `{sede_info_text}` not `{sede_info}` — the dict stays in state for any future tool that needs structured access.

---

### D9: Token budget per specialist (rough estimates)

Assume worst case (all configured fields populated):

| Specialist | Blocks | Estimated tokens |
|------------|--------|------------------|
| Reception | clinic_basics (100) + faqs_section RAG (1500 top-K) + holidays_section (300) | ~2000 |
| Booking | clinic_basics (100) + holidays_section (300) + derivation_rules_section (800) + sede_info_text (100) | ~1300 |
| Triage | clinic_basics (100) + special_conditions_block (1500) | ~1700 |
| Billing | clinic_basics (100) + insurance_section (2500) + payment_section (500) + bank_info (200) | ~3300 |
| Anamnesis | clinic_basics (100) + special_conditions_block (1500) | ~1700 |
| Handoff | clinic_basics (100) + support_policy_block (1000) | ~1200 |

Plus the specialist's own task instructions (~1000-2000 tokens). All specialists stay well under 8000 tokens. Billing has the largest footprint (~5000 with its own instructions) but is still ~30% of TORA solo's full prompt (~18000 tokens).

This is what "more efficient" means: each specialist sees ~2-5k context tokens vs TORA solo's ~18k.

---

### D10: How specialists currently build their prompts

Looking at `agents/specialists.py:128-150` (Booking):

```python
booking = create_react_agent(
    model=model,
    tools=[check_availability, confirm_slot, book_appointment, ...],
    prompt=ChatPromptTemplate.from_messages([
        ("system", BOOKING_SYSTEM_PROMPT),  # ← static string today
        MessagesPlaceholder("messages"),
    ]),
)
```

The change: convert each specialist's system prompt from a static string to a `lambda state: BOOKING_SYSTEM_PROMPT.format(**select_blocks(state, "booking"))` so it's re-rendered per turn with the current state.

Alternative: use LangGraph's pattern of passing state through the agent's `messages_modifier` or similar. The exact mechanism depends on the LangGraph version in use. The implementation will inspect the actual code and pick the cleanest hook.

---

### D11: Behavior when `tenant_context` is missing or empty

```python
def select_blocks(state: AgentState, specialist: str) -> dict[str, str]:
    """Return only the blocks the given specialist is allowed to see, with empty fallbacks."""
    ctx = state.get("tenant_context") or {}
    allowed = SPECIALIST_BLOCKS.get(specialist, ["clinic_basics"])
    return {key: ctx.get(key, "") for key in allowed}
```

If `tenant_context` is missing entirely (e.g., builder failed), every block is `""`. Specialists fall back to their bare prompts.

---

### D12: New file structure

```
orchestrator_service/agents/
├── __init__.py
├── base.py                  (unchanged)
├── graph.py                 (modified — calls builder, populates state)
├── model_resolver.py        (unchanged)
├── prompts/
│   ├── __init__.py
│   ├── supervisor.md        (unchanged)
│   └── specialist_blocks.md (NEW — documents the whitelist for human readers)
├── specialists.py           (modified — each specialist consumes its whitelist)
├── state.py                 (modified — adds tenant_context field)
├── supervisor.py            (unchanged — supervisor doesn't need the blocks for routing)
└── tenant_context.py        (NEW — the builder + whitelist + helpers)
```

---

### D13: What happens during the FOLLOW-UP pack (out of scope for this one)

The follow-up pack (`multi-agent-specialist-deepening`) will:
- Expand each specialist's own task-specific instructions (the parts above the context blocks) using the freed token budget
- Add intent-aware sub-sections within each specialist (e.g., Booking for "implant" intent gets the implant flow that today only TORA solo has)
- Possibly add 1-2 new specialists for high-volume verticals (e.g., a dedicated "Postop" specialist for days 1-7 after a surgery)

This pack lays the groundwork by ensuring the context plumbing exists. The deepening pack won't need to touch `tenant_context.py` or `state.py` — only the specialist prompt templates.

---

## Files affected

| File | Status | Purpose |
|------|--------|---------|
| `orchestrator_service/agents/tenant_context.py` | NEW | Builder + whitelist + helpers |
| `orchestrator_service/agents/state.py` | MODIFY | Add `tenant_context: NotRequired[dict]` |
| `orchestrator_service/agents/graph.py` | MODIFY | Call builder in run_turn, populate state |
| `orchestrator_service/agents/specialists.py` | MODIFY | Each specialist's prompt template references its whitelist |
| `orchestrator_service/agents/prompts/specialist_blocks.md` | NEW | Human-readable doc of the whitelist |
| `tests/test_multi_agent_tenant_context.py` | NEW | Unit tests per REQ-8 |

No changes to: `main.py`, `services/buffer_task.py`, `services/embedding_service.py`, `models.py`, any migration, any frontend file.
