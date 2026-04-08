# SDD Tasks: Multi-Agent Tenant Context Parity

**Change**: `multi-agent-tenant-context-parity`
**Status**: READY
**Date**: 2026-04-08
**TDD**: tests written before implementation per phase

---

## Dependency graph

```
1.1 (audit) → 1.2 (state field) → 1.3 (whitelist constants)
1.2 + 1.3 → 2.1 (builder skeleton) → 2.2 (formatter imports) → 2.3 (block fetchers)
2.3 → 3.1 (graph entry call) → 3.2 (intent classification port) → 3.3 (state propagation)
3.3 → 4.1 (specialist prompt format hook) → 4.2 (per-specialist whitelist apply)
4.2 → 5.1 (unit tests) → 5.2 (acceptance scenarios)
5.2 → 6.1 (commit + push) → 6.2 (merge to main)
```

---

## Phase 1 — Audit + scaffolding

### Task 1.1 — Audit current multi-agent code paths
- Files to read: `agents/graph.py`, `agents/specialists.py`, `agents/state.py`, `agents/supervisor.py`, `agents/base.py`, `services/buffer_task.py:classify_intent`
- Document:
  - How `run_turn` is currently structured
  - Where each specialist's prompt comes from (template? string?)
  - What's already in AgentState
  - Any LangGraph version-specific quirks for prompt re-rendering per turn
- Acceptance: a short note in the commit message of task 1.2 referencing the file:line of the existing prompt definitions for the 6 specialists.

### Task 1.2 — Extend `AgentState` with `tenant_context` field
- File: `orchestrator_service/agents/state.py`
- Add: `tenant_context: NotRequired[dict[str, Any]]`
- Acceptance:
  - Field is `NotRequired` (existing tests with bare AgentState still pass)
  - Type is `dict[str, Any]` not strict typed dict (to allow nested dict for sede_info)

### Task 1.3 — Define the per-specialist whitelist constant
- File: `orchestrator_service/agents/tenant_context.py` (new file, just the constants for now)
- Define: `SPECIALIST_BLOCKS: dict[str, list[str]]` per spec REQ-4.1
- Define: `ALL_BLOCK_KEYS: tuple` (the canonical list of block names)
- Acceptance:
  - Constants are importable: `from agents.tenant_context import SPECIALIST_BLOCKS, ALL_BLOCK_KEYS`
  - Every key in SPECIALIST_BLOCKS values is also in ALL_BLOCK_KEYS

---

## Phase 2 — Tenant context builder

### Task 2.1 — Builder skeleton with the contract
- File: `orchestrator_service/agents/tenant_context.py`
- Add: `async def build_tenant_context_blocks(pool, tenant_id, user_message_text="", intent_tags=None) -> dict`
- Body: returns a dict with all keys from `ALL_BLOCK_KEYS` set to empty strings (placeholder)
- Acceptance:
  - Function exists, has the right signature
  - Returns a dict with all expected keys
  - Empty implementation — no real fetching yet

### Task 2.2 — Import formatters from `main.py` (with fallback)
- File: `orchestrator_service/agents/tenant_context.py`
- Add a try/except import block:
  ```python
  try:
      from main import (
          _format_insurance_providers,
          _format_payment_options,
          _format_special_conditions,
          _format_support_policy,
          _format_derivation_rules,
      )
      _MAIN_FORMATTERS_AVAILABLE = True
  except ImportError as exc:
      logger.error(f"agents.tenant_context: failed to import main formatters: {exc}")
      _MAIN_FORMATTERS_AVAILABLE = False
  ```
- Acceptance:
  - Module imports successfully even if `main` isn't available (for unit tests)
  - `_MAIN_FORMATTERS_AVAILABLE` flag controls whether the builder returns real blocks or empty fallbacks

### Task 2.3 — Implement the actual fetchers
- File: `orchestrator_service/agents/tenant_context.py`
- For each block, write a small async helper that does ONE focused query and returns the formatted string:
  - `_fetch_clinic_basics(pool, tenant_id) -> str` — selects clinic_name, bot_name, system_prompt_template from tenants
  - `_fetch_insurance_section(pool, tenant_id, treatment_display_map) -> str` — fetches active insurance providers, calls `_format_insurance_providers`
  - `_fetch_payment_section(pool, tenant_id) -> str` — fetches payment columns, calls `_format_payment_options`
  - `_fetch_special_conditions_block(pool, tenant_id, treatment_display_map) -> str` — same pattern
  - `_fetch_support_policy_block(pool, tenant_id) -> str` — same pattern
  - `_fetch_derivation_rules_section(pool, tenant_id) -> str` — fetches active rules with both prof joins, calls `_format_derivation_rules`
  - `_fetch_holidays_section(pool, tenant_id) -> str` — calls `services.holiday_service.get_upcoming_holidays`, formats inline (TORA does it inline too)
  - `_fetch_faqs_section(pool, tenant_id, user_message_text) -> str` — calls `services.embedding_service.format_all_context_with_rag` and returns the faqs_section, falls back to static if RAG unavailable
  - `_fetch_bank_info(pool, tenant_id) -> str` — selects bank_cbu/alias/holder_name, formats as a small block
  - `_fetch_sede_info(pool, tenant_id) -> dict` + `_format_sede_info_text(sede_info: dict) -> str` per design D8
  - `_fetch_treatment_display_map(pool, tenant_id) -> dict` — small helper used by insurance and special_conditions formatters
- Top-level `build_tenant_context_blocks` orchestrates these via `asyncio.gather` where independent
- Each helper is wrapped in try/except: on error, return empty string (or empty dict for sede_info), log at debug level
- Acceptance:
  - All 10 blocks defined
  - Errors in any single helper do not crash the builder
  - The builder uses `asyncio.gather` for parallel fetches where possible
  - All `WHERE tenant_id = $1` filters are present in every query

---

## Phase 3 — Graph integration

### Task 3.1 — Call the builder from `run_turn`
- File: `orchestrator_service/agents/graph.py`
- In `run_turn` (or the equivalent entry point), AFTER existing patient_context loading, call `build_tenant_context_blocks`
- Pass `pool`, `tenant_id` (from ctx), the latest user message text (joined from messages), and the result of `classify_intent`
- Acceptance:
  - The call happens once per turn, not per specialist
  - Wrapped in try/except — on failure, set `state["tenant_context"] = {}` and log

### Task 3.2 — Port `classify_intent` import
- File: `orchestrator_service/agents/graph.py`
- Add: `from services.buffer_task import classify_intent` with fallback to a no-op `lambda messages: set()` on ImportError
- Pass the result to `build_tenant_context_blocks` as `intent_tags`
- Acceptance:
  - Import is defensive
  - The fallback returns an empty set (= safe default = inject all blocks per the formatters' own logic)

### Task 3.3 — Populate state
- File: `orchestrator_service/agents/graph.py`
- Set `state["tenant_context"] = await build_tenant_context_blocks(...)`
- Make sure the state propagates through to the supervisor and specialists (LangGraph state passing)
- Acceptance:
  - A specialist invoked after `run_turn` can read `state["tenant_context"]`
  - The supervisor can also read it (in case future routing rules need clinic_basics)

---

## Phase 4 — Specialist prompt format hook

### Task 4.1 — Extract a helper to select blocks per specialist
- File: `orchestrator_service/agents/tenant_context.py`
- Add: `def select_blocks_for_specialist(state: dict, specialist_name: str) -> dict[str, str]`
  - Reads `state.get("tenant_context") or {}`
  - Returns only the keys in `SPECIALIST_BLOCKS[specialist_name]`
  - Missing keys default to empty string
- Acceptance:
  - Pure function, no I/O
  - Unknown specialist name returns just `{"clinic_basics": ""}` (safe default)

### Task 4.2 — Wire each specialist's prompt
- File: `orchestrator_service/agents/specialists.py`
- For each of the 6 specialists (Reception, Booking, Triage, Billing, Anamnesis, Handoff):
  - Convert the static system prompt string to a template with named slots matching the whitelist:
    ```python
    BOOKING_SYSTEM_PROMPT = """[existing booking instructions...]
    {clinic_basics}
    {holidays_section}
    {derivation_rules_section}
    {sede_info_text}
    """
    ```
  - At specialist creation/invocation, format the template with `select_blocks_for_specialist(state, "booking")`
  - The exact LangGraph hook depends on the version — likely `messages_modifier` or a custom prompt builder function
- Acceptance:
  - All 6 specialists updated
  - No specialist receives blocks outside its whitelist
  - Empty blocks render as empty strings (no template errors)
  - Existing specialist behavior is preserved when blocks are empty

---

## Phase 5 — Tests

### Task 5.1 — Unit tests for the builder
- File: `tests/test_multi_agent_tenant_context.py` (new)
- Test class: `TestBuildTenantContextBlocks`
  - `test_returns_all_expected_keys` — output dict contains every key in `ALL_BLOCK_KEYS`
  - `test_empty_tenant_returns_empty_blocks` — mock pool returns no rows, all blocks are empty strings
  - `test_full_tenant_returns_populated_blocks` — mock pool returns realistic rows, formatters are called, blocks are non-empty
  - `test_individual_helper_failure_returns_empty_for_that_block` — one query raises, that block is `""`, others are populated
  - `test_intent_tags_propagate_to_formatters` — verify intent_tags are forwarded
- Test class: `TestSelectBlocksForSpecialist`
  - `test_reception_gets_only_its_whitelist`
  - `test_booking_gets_only_its_whitelist`
  - `test_unknown_specialist_returns_clinic_basics_only`
  - `test_missing_state_tenant_context_returns_empty`
- Use `unittest.mock.AsyncMock` for the pool
- Acceptance: tests are pure unit tests, no DB/HTTP/LLM, importable cleanly

### Task 5.2 — Acceptance scenario tests (REQ-6)
- Same file: `tests/test_multi_agent_tenant_context.py`
- Test class: `TestAcceptanceScenarios`
  - `test_scenario_a_booking_sees_holidays`
  - `test_scenario_b_billing_answers_payment`
  - `test_scenario_c_triage_applies_special_conditions`
  - `test_scenario_d_handoff_uses_complaint_protocol`
  - `test_scenario_e_empty_config_no_regression`
  - `test_scenario_f_token_budget_bound` — assert each specialist's full prompt with full blocks is under 8000 tokens (rough char count / 4)
- These tests build a state dict, call `select_blocks_for_specialist`, format a sample prompt, and assert content
- Acceptance: 6 acceptance scenarios pass with mocked state

---

## Phase 6 — Commit + merge

### Task 6.1 — Commit phases atomically
- One commit per phase (1-5), or fewer if tightly coupled
- Each commit message documents what phase it's part of and references the spec/design
- Push the branch (`feat/multi-agent-tenant-context-parity`) after each phase to protect work

### Task 6.2 — Merge to main
- Verify branch is rebased on latest main
- Open PR or fast-forward merge depending on user preference
- Update engram with `sdd/multi-agent-tenant-context-parity/completed`
- Note in the merge commit: this is the first half of the multi-agent parity work; the second half (specialist deepening) is a separate follow-up pack

---

## Notes for implementor

1. **Don't touch TORA solo or `build_system_prompt`**. This pack is purely additive in `agents/`.
2. **Don't add new tools or new DB columns**. Everything we need is already configured.
3. **Don't fix the supervisor or routing logic**. Existing supervisor stays as is — the user's intent for "deeper expansion of each TORA stage" is for the FOLLOW-UP pack, not this one.
4. **Test the empty-tenant case heavily**. The most important test is "no regression for legacy clinics".
5. **Keep the builder under 500ms typical latency**. Use `asyncio.gather` for independent fetches.
6. **Log builder failures clearly** but never crash. Multi-agent must work even if context is empty.
7. **Document the whitelist in `agents/prompts/specialist_blocks.md`** so future devs can update it without grepping the code.
