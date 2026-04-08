# SDD Proposal: Multi-Agent Tenant Context Parity

**Change**: `multi-agent-tenant-context-parity`
**Status**: PROPOSED
**Date**: 2026-04-08
**Author**: SDD orchestrator

---

## 1. Intent

### Problem statement

Bring the multi-agent engine (`MultiAgentEngine` in `orchestrator_service/agents/`) to **feature parity** with TORA solo (`build_system_prompt()` in `main.py`) for tenant-configured context awareness.

After the 2026-04-08 UI config gaps batch (7 packs merged), TORA solo automatically injects 8 tenant-configured prompt blocks every conversation:

1. `_format_insurance_providers()` — coverage by treatment, copay, pre-auth, prepaid distinction
2. `_format_payment_options()` — methods, financing, installments, cash discount, crypto
3. `_format_special_conditions()` — pregnancy, pediatric, high-risk protocols
4. `_format_upcoming_holidays()` — holidays + special-hours days
5. `_format_support_policy()` — graduated complaint protocol, escalation channels, review platforms
6. `_format_derivation_rules()` — derivation rules + escalation fallback
7. `_format_pre/post_instructions_dict()` — pre/post treatment protocols (via `get_treatment_instructions` tool)
8. RAG-injected FAQs + clinic_basics (bot_name, specialty_pitch, clinic_name, working_hours, sede)

The multi-agent specialists (Reception, Booking, Triage, Billing, Anamnesis, Handoff in `agents/specialists.py`) **do not call `build_system_prompt()`**. They have their own minimal system prompts that include task-specific instructions but NOT the tenant context blocks. As a result:

- Patient asks Booking specialist "¿hay turno el feriado del 25?" → specialist doesn't know about configured holidays → improvises
- Patient asks Billing specialist "¿cuánto cuesta con cuotas?" → specialist doesn't see `payment_options` block → says "consultá con la clínica"
- Patient asks Triage specialist "estoy embarazada" → specialist doesn't see `special_conditions` block → may give unsafe advice

**The tools they DO share with TORA solo** (`check_availability` with escalation, `get_treatment_instructions` with alarm tags, `check_insurance_coverage`) work correctly in both engines because the logic lives in the tool body, not the prompt. But that's only ~3 of the 8 capabilities — the rest are prompt-level.

### Why this matters

- **Multi-agent currently has reduced capability** vs TORA solo for tenants that configured the new fields (special conditions, payment, holidays, support policy, etc.)
- **Tenants who switch to multi-agent mode lose features** even though those features are configured in the same UI
- **Inconsistency between engines** breaks the "engine choice is transparent to the user" contract from the dual-engine pack

### Goal

Multi-agent specialists should access the same tenant-configured context as TORA solo, but **distributed per specialist** (not duplicated everywhere) for token efficiency and clean separation of concerns.

---

## 2. Scope

### In scope

| Area | Files | Change |
|------|-------|--------|
| Tenant context builder | `orchestrator_service/agents/tenant_context.py` (NEW) | Build all 8 prompt blocks ONCE per turn, return as dict |
| Agent state | `orchestrator_service/agents/state.py` | Add `tenant_context: dict` field |
| Graph entry point | `orchestrator_service/agents/graph.py` | Call context builder, store in state, propagate to specialists |
| Specialists | `orchestrator_service/agents/specialists.py` | Each specialist's prompt template references the relevant blocks from state |
| Block-to-specialist mapping | (in specialists.py) | Per-specialist whitelist of relevant blocks |
| Intent-aware filtering | (in tenant_context.py) | Reuse `classify_intent()` from buffer_task; pass intent_tags to context builder |
| Reuse existing formatters | `agents/tenant_context.py` imports from `main.py` | No duplication of formatter logic |

### Out of scope

- Changes to TORA solo (`build_system_prompt`) — already complete
- New formatters or new tenant fields — all 7 packs already shipped
- Changes to LangChain tools (`DENTAL_TOOLS`) — they already work in both engines
- Supervisor routing logic — unchanged
- New specialist agents — work with the existing 6
- Token budget tuning — 8000 for reasoning models already addressed in nova fix

---

## 3. Success criteria

| Scenario | Expected |
|----------|----------|
| Tenant has `payment_methods=["card","cash"]`. Patient asks Billing specialist "¿aceptan tarjeta?" | Specialist responds correctly using configured payment_options block |
| Tenant has `complaint_handling_protocol={level_1:..., level_2:..., level_3:...}`. Patient complains. | Handoff specialist follows the graduated escalation, not `derivhumano` immediately |
| Tenant has 3 holidays in next 30 days. Patient asks Booking "¿atienden el 1 de mayo?" | Booking specialist mentions the configured holiday |
| Tenant has high_risk_protocol for diabetes. Pregnant patient with diabetes asks for extraction. | Triage specialist applies the special_conditions block (says "según política, requiere clearance médico") |
| Tenant has NO custom config (legacy clinic). Patient asks anything. | All blocks return empty strings, specialists behave as before. **Zero behavior regression.** |
| Multi-agent supervisor routes to Booking. Token budget for that specialist's prompt | Lower than TORA solo's full prompt (Booking gets ~3 blocks, not all 8) |
| Patient mentions "implante" (intent_tag = implant) | Only the implant-related blocks are passed; payment block omitted unless also tagged |

---

## 4. Risks

| Risk | Mitigation |
|------|-----------|
| **Token bloat in specialists** | Per-specialist block whitelist limits each prompt to the relevant subset (~2-4 blocks max). TORA solo gets all 8; specialists get fewer. |
| **Cross-specialist info leak** (e.g., Triage shows insurance) | Whitelist enforced by code, not by trust. Each specialist's prompt template references named blocks only. |
| **Breaking existing multi-agent tests** | All blocks default to `""` when tenant has no config — same as TORA solo. Existing tests with empty config remain green. |
| **Performance**: building context blocks costs DB queries | Build ONCE per turn (graph entry point), reuse across all specialist calls within the turn. ~3-5 queries total per turn (insurance, derivation, treatment_types, holidays, faqs RAG). |
| **Stale context if conversation is long** | Context is rebuilt at the start of each turn, not cached across turns. Same as TORA solo. |
| **Formatter import cycles** | `agents/tenant_context.py` imports from `main.py` — `main.py` does NOT import from `agents/`. Acyclic. |

---

## 5. Alternatives considered

### Alternative A: Inject the FULL TORA prompt into each specialist
**Rejected.** Defeats the architectural purpose of having specialists. Each specialist would have an 18k-token prompt for tasks that need 3k. Wasteful and slower.

### Alternative B: Have one shared system prompt for the supervisor that all specialists inherit
**Rejected.** LangGraph specialists are independent agents with their own prompts. Inheritance breaks the modularity. Would require restructuring the LangGraph architecture significantly.

### Alternative C: Add new tools that specialists call on-demand (e.g., `get_payment_policy()`)
**Rejected.** Forces a tool call per question that needs context. Slower (extra LLM round trip), more expensive (extra tool call), and the LLM might forget to call the tool. The prompt-injection approach proven by TORA solo is more reliable.

### **Alternative D (chosen): Per-specialist context blocks via shared state dict**
- Build all blocks ONCE in the graph entry point
- Store in `AgentState['tenant_context']`
- Each specialist's prompt template references only the blocks relevant to its responsibility
- Empty blocks = no overhead
- Mirrors TORA solo's approach but with clean per-specialist scoping

This is the chosen approach.

---

## 6. Dependencies and references

- **Depends on**: All 7 packs from the 2026-04-08 batch (already merged to main)
- **Reuses**: `classify_intent()`, `_format_insurance_providers()`, `_format_payment_options()`, `_format_special_conditions()`, `_format_support_policy()`, `_format_derivation_rules()`, `_format_upcoming_holidays()`, RAG `format_all_context_with_rag()` — all from `main.py` and `services/`
- **Inspired by**: `services/buffer_task.py` lines 287-1050 (the TORA solo wiring)
- **Architecture doc**: `CLAUDE.md` "Dual-Engine Architecture" section

---

## 7. Open questions for design phase

1. Should the context builder be sync or async? (DB queries → async)
2. Should `intent_tags` be classified by the supervisor or by the graph entry point? (Current TORA: graph-equivalent; should match for consistency)
3. Should the per-specialist block whitelist live in `specialists.py` or `tenant_context.py`?
4. How to handle the FAQs RAG section — pass the patient message to the builder, or call RAG separately per specialist?

These are answered in `design.md`.
