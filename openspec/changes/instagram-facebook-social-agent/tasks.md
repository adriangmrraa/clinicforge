# Tasks — Instagram/Facebook Social Agent

> TDD-first checklist. Every code task is preceded by its test task.
> Phase ordering respects the dependency chain:
> migration → model → services → prompt builder → engine (solo) → engine (multi) → buffer wiring → admin API → frontend → integration tests → manual rollout → verify/archive

---

## Phase 0 — Pre-flight

- [x] **P0-1** Confirm alembic head is `039_add_tenant_support_complaints`
  - Run `ls orchestrator_service/alembic/versions/` and verify the highest numbered file is `039_add_tenant_support_complaints.py`
  - If a `040_*` file already exists, STOP and resolve the conflict before proceeding
  - Record the confirmed head in a comment at the top of the new migration file
  - **Done**: Head confirmed `039`, revision ID = `"039"`

- [x] **P0-2** Record current `build_system_prompt` signature
  - Read `orchestrator_service/main.py` lines ~7304–7414
  - Write down the complete param list (name + default) — this is the regression baseline
  - Identify the exact line where the ANTI-MARKDOWN block starts and ends
  - **Done**: Signature has 39 params. ANTI-MARKDOWN block at lines 7414-7422 (inside patient_context block). Last param: `support_policy_block: str = ""`

- [x] **P0-3** Create golden snapshot of WhatsApp prompt output
  - Create `tests/fixtures/` directory if it does not exist
  - Using the canonical tenant fixture (tenant_id matching the test DB seed), call `build_system_prompt(channel="whatsapp", ...)` with all new params at their defaults
  - Write the output string to `tests/fixtures/golden_prompt_whatsapp.txt`
  - This file is committed and MUST NOT change unless the WhatsApp path is intentionally modified
  - **Done**: `tests/fixtures/golden_prompt_whatsapp.txt` generated via `tests/generate_golden_prompt.py`, 42681 chars, includes REGLA ANTI-MARKDOWN (WHATSAPP) block (channel-gated)

> **Dependency**: P0-3 requires the test DB to be available. If running on CI without a live DB, generate the golden file via a unit test that mocks DB calls and captures the assembled string.

---

## Phase 1 — Migration + Model

> **Depends on**: Phase 0 (confirmed head = 039)

- [x] **P1-1** [TEST] Write failing migration test
  - File: `tests/test_migration_040.py` (~60 LOC)
  - **Done**: 17 tests, source-inspection strategy (no live DB). Confirmed FAIL before code.

- [x] **P1-2** [CODE] Write migration `040_add_social_ig_fields.py` (~50 LOC)
  - File: `orchestrator_service/alembic/versions/040_add_social_ig_fields.py`
  - `revision = "040_add_social_ig_fields"`, `down_revision = "039"`
  - **Done**: 17/17 tests GREEN. Commit: `feat(migration): add social IG/FB fields to tenants (040)`

- [x] **P1-3** [CODE] Extend `Tenant` ORM model (~6 LOC)
  - File: `orchestrator_service/models.py`
  - **Done**: 4 columns added under `# Social agent: Instagram / Facebook channels (migration 040)`

- [ ] **P1-4** Run migration on test DB and verify
  - `alembic upgrade head` → confirm `alembic current` shows `040_add_social_ig_fields`
  - Inspect columns via `\d tenants` (psql) or equivalent
  - Accept: all 4 columns visible with correct types and defaults

- [ ] **P1-5** Rollback smoke test
  - `alembic downgrade -1` → `alembic upgrade head`
  - Accept: no error, schema identical to P1-4 result

---

## Phase 2 — CTA Routes Parser Module

> **Depends on**: nothing (pure module, no DB)

- [x] **P2-1** [TEST] Write failing unit tests for `social_routes.py`
  - File: `tests/test_social_routes.py` (~90 LOC)
  - **Done**: 27 tests covering structure, pitch rules, keyword matching, None/empty, fallback. Confirmed FAIL before code.

- [x] **P2-2** [CODE] Implement `social_routes.py` (~180 LOC)
  - File: `orchestrator_service/services/social_routes.py`
  - **Done**: 27/27 tests GREEN. Commit: `feat(social-routes): add CTA routes parser for IG/FB agent`
  - Pitches rewritten from source doc — no WhatsApp redirect, direct booking trigger in all 4 routes

---

## Phase 3 — Social Preamble Builder

> **Depends on**: Phase 2 (`CTARoute`, `CTA_ROUTES`)

- [x] **P3-1** [TEST] Write failing unit tests for `social_prompt.py`
  - File: `tests/test_social_prompt.py` (~80 LOC)
  - `test_preamble_contains_channel_identity`: result contains `"instagram"` or `"facebook"` depending on `channel` arg
  - `test_preamble_contains_self_reference_when_handle_provided`: result contains `instagram_handle` value when not None
  - `test_preamble_omits_self_reference_when_handle_none`: no `None` string in output; section gracefully absent
  - `test_preamble_contains_cta_routes_block`: result contains each `CTARoute.group` name and `pitch_template` substring
  - `test_preamble_contains_landings_urls`: when `social_landings = {"blanqueamiento": "https://example.com"}`, result contains that URL
  - `test_preamble_handles_none_landings`: `social_landings=None` → no exception, landings section absent or empty
  - `test_preamble_contains_friend_detection_rules`: result contains "AMIGO" and "LEAD"
  - `test_preamble_forbidden_triage_urgency`: result contains "`triage_urgency`" and a prohibition word ("NUNCA" or "prohibid")
  - `test_preamble_markdown_allowed`: result contains "markdown" (markdown enabled instruction)
  - `test_preamble_voseo`: result contains "voseo" or "vos " or "agendamos" (voseo pronoun usage instruction)
  - `test_preamble_medical_ethics_rule`: result contains some form of "diagnóstico" and "DM" or "por acá"
  - `test_preamble_is_pure_function`: calling twice with same args returns identical string
  - Run: confirm all tests FAIL

- [x] **P3-2** [CODE] Implement `social_prompt.py` (~120 LOC)
  - File: `orchestrator_service/services/social_prompt.py`
  - Signature: `build_social_preamble(tenant_id: int, channel: str, social_landings: Optional[dict], instagram_handle: Optional[str], facebook_page_id: Optional[str], cta_routes: list[CTARoute]) -> str`
  - Builds sections: identity block (channel + handle), friend-vs-lead detection rules (verbatim from design §6), CTA routes block (loop over `cta_routes`: group name + pitch + landing URL if present), tool allow-list + `triage_urgency` prohibition (from design §7), medical ethics rule, markdown-allowed statement, voseo instruction
  - Pure function: no I/O, no DB calls
  - Run P3-1: all tests PASS
  - **Done**: 21/21 tests GREEN. Commit: `feat(social-prompt): add social media preamble builder`

---

## Phase 4 — Solo Engine Integration (`build_system_prompt`)

> **Depends on**: Phase 3 (`build_social_preamble`), Phase 0 (golden file created)

- [x] **P4-1** [TEST] Write failing WhatsApp regression test
  - File: `tests/test_build_system_prompt_whatsapp_regression.py` (~40 LOC)
  - Reads `tests/fixtures/golden_prompt_whatsapp.txt`
  - Calls `build_system_prompt(channel="whatsapp")` with all new params at defaults (other existing params matched to the golden fixture's tenant config)
  - Asserts output is byte-identical to the golden file content
  - Run: confirm test PASSES before any changes to `main.py` (baseline established)
  - **Done**: 2/2 tests GREEN.

- [x] **P4-2** [TEST] Write failing social-mode tests for `build_system_prompt`
  - File: `tests/test_build_system_prompt_social.py` (~70 LOC)
  - `test_social_mode_injects_preamble`: `build_system_prompt(..., channel="instagram", is_social_channel=True, ...)` → output starts with social preamble content (contains "AMIGO" and "LEAD" and route group names)
  - `test_social_mode_strips_antimarkdown_block`: with `channel="instagram"`, the string `"ANTI-MARKDOWN"` or `"NO uses asteriscos"` (whatever the WhatsApp block contains) is absent from output
  - `test_social_mode_preamble_before_base_prompt`: preamble appears before the first line of the base clinic system prompt
  - `test_whatsapp_keeps_antimarkdown_block`: `channel="whatsapp"` → ANTI-MARKDOWN block present in output
  - `test_flag_off_no_preamble`: `channel="instagram", is_social_channel=False` → preamble absent
  - `test_new_kwargs_have_safe_defaults`: calling `build_system_prompt()` with zero new kwargs raises no error and returns WhatsApp-equivalent output
  - Run: confirm all 6 tests FAIL
  - **Done**: 9/9 tests GREEN (extended set).

- [x] **P4-3** [CODE] Extend `build_system_prompt` in `main.py` (~60 LOC)
  - File: `orchestrator_service/main.py`
  - Add 5 new kwargs to signature: `channel: str = "whatsapp"`, `is_social_channel: bool = False`, `social_landings: Optional[dict] = None`, `instagram_handle: Optional[str] = None`, `facebook_page_id: Optional[str] = None`
  - Import `build_social_preamble` from `services.social_prompt` and `CTA_ROUTES` from `services.social_routes` at top of file (or inside function)
  - At top of prompt assembly: `if is_social_channel: preamble = build_social_preamble(...); prompt = preamble + "\n\n" + prompt`
  - Wrap the ANTI-MARKDOWN block in `if channel == "whatsapp":` so it is skipped for social channels
  - Extend `get_agent_executable_for_tenant()` to accept and forward the 5 new kwargs to `build_system_prompt`
  - Run P4-1 regression test: MUST still PASS (byte-identical)
  - Run P4-2 tests: all 6 PASS
  - **Done**: regression PASS, 11/11 total tests GREEN. Commit: `feat(prompt): add channel-aware social mode to build_system_prompt`

---

## Phase 5 — Multi-Agent Engine Integration

> **Depends on**: Phase 3 (`build_social_preamble`)

- [ ] **P5-1** [TEST] Write failing `AgentState` channel key tests
  - File: `tests/test_agent_state_channel.py` (~50 LOC)
  - `test_agent_state_accepts_channel_keys`: instantiate `AgentState` dict with the 5 new keys → no TypeError
  - `test_run_turn_populates_channel_from_ctx_extra`: call `graph.run_turn(ctx)` with `ctx.extra = {"channel": "instagram", "is_social_channel": True, "social_landings": None, "instagram_handle": "@test", "facebook_page_id": None}` (mock OpenAI); assert state passed to supervisor contains those keys
  - `test_run_turn_defaults_channel_to_whatsapp_when_extra_absent`: `ctx.extra = {}` → `state["channel"] == "whatsapp"` and `state["is_social_channel"] == False`
  - Run: confirm all tests FAIL

- [ ] **P5-2** [TEST] Write failing specialist preamble injection tests
  - File: `tests/test_specialists_social_preamble.py` (~60 LOC)
  - For each of the 6 specialists (Reception, Booking, Triage, Billing, Anamnesis, Handoff):
    - `test_{specialist}_injects_preamble_when_social`: call `_with_tenant_blocks(state)` with `state["is_social_channel"] = True`; assert preamble content ("AMIGO") is at the start of the returned prompt
    - `test_{specialist}_no_preamble_when_not_social`: `state["is_social_channel"] = False` → preamble absent
  - Run: confirm all tests FAIL

- [ ] **P5-3** [CODE] Extend `AgentState` TypedDict (~10 LOC)
  - File: `orchestrator_service/agents/state.py`
  - Add 5 keys: `channel: str`, `is_social_channel: bool`, `social_landings: Optional[dict]`, `instagram_handle: Optional[str]`, `facebook_page_id: Optional[str]`
  - Use `total=False` to keep backward compat with old snapshots

- [ ] **P5-4** [CODE] Wire `ctx.extra` into `AgentState` in `graph.py` (~15 LOC)
  - File: `orchestrator_service/agents/graph.py`
  - In `run_turn(ctx)`, read `ctx.extra.get("channel", "whatsapp")` and 4 other keys
  - Seed them into the initial `AgentState` dict before routing

- [ ] **P5-5** [CODE] Inject preamble in `specialists.py` (~20 LOC)
  - File: `orchestrator_service/agents/specialists.py`
  - In `_with_tenant_blocks(state)`: import `build_social_preamble` and `CTA_ROUTES`; if `state.get("is_social_channel")`, prepend `build_social_preamble(...)` to the assembled prompt block
  - Run P5-1 and P5-2: all tests PASS

---

## Phase 6 — Buffer Task Wiring

> **Depends on**: Phase 1 (migration applied), Phase 4 (`build_system_prompt` extended), Phase 5 (`AgentState` extended)

- [ ] **P6-1** [TEST] Write failing buffer task channel detection tests
  - File: `tests/test_buffer_task_social_channel.py` (~80 LOC)
  - `test_ig_message_sets_is_social_channel_true_when_flag_enabled`: mock DB returns tenant with `social_ig_active=True`; `channel="instagram"` → `ctx.extra["is_social_channel"] == True`
  - `test_ig_message_sets_is_social_channel_false_when_flag_disabled`: tenant `social_ig_active=False` → `ctx.extra["is_social_channel"] == False`
  - `test_fb_message_with_flag_sets_social_true`: `channel="facebook"`, `social_ig_active=True` → `is_social_channel == True`
  - `test_whatsapp_always_not_social_regardless_of_flag`: `channel="whatsapp"`, `social_ig_active=True` → `ctx.extra["is_social_channel"] == False`
  - `test_ctx_extra_contains_all_five_keys`: after processing, `ctx.extra` has keys `channel`, `is_social_channel`, `social_landings`, `instagram_handle`, `facebook_page_id`
  - `test_solo_path_receives_social_kwargs`: when engine is solo, `build_system_prompt` is called with `is_social_channel=True` when IG+flag
  - Run: confirm all tests FAIL

- [ ] **P6-2** [CODE] Extend `buffer_task.py` (~25 LOC)
  - File: `orchestrator_service/services/buffer_task.py`
  - In `_run_ai_for_phone` (near line 1005), add 4 new columns to the existing tenant SELECT: `social_ig_active`, `social_landings`, `instagram_handle`, `facebook_page_id`
  - Compute: `is_social_channel = channel in ("instagram", "facebook") and bool(tenant["social_ig_active"])`
  - Build `TurnContext.extra` dict including all 5 keys (or extend existing `extra` dict)
  - When calling the Solo engine directly, pass the 5 kwargs into `build_system_prompt` (or into `get_agent_executable_for_tenant`)

- [ ] **P6-3** [CODE] Confirm `engine_router.py` passes `ctx.extra` through unchanged
  - File: `orchestrator_service/services/engine_router.py`
  - Verify (read-only check): `TurnContext` flows through without stripping `extra` keys; if `extra` is dropped anywhere, fix it
  - No new LOC expected unless a bug is found
  - Run P6-1: all tests PASS

---

## Phase 7 — Admin API

> **Depends on**: Phase 1 (columns exist in DB)

- [ ] **P7-1** [TEST] Write failing admin settings social field tests
  - File: `tests/test_admin_settings_social.py` (~70 LOC)
  - `test_patch_accepts_social_ig_active`: PATCH `/admin/settings/clinic` with `{"social_ig_active": true}` → 200, DB row updated
  - `test_patch_accepts_social_landings`: PATCH with `{"social_landings": {"blanqueamiento": "https://x.com"}}` → 200, JSONB stored
  - `test_patch_accepts_instagram_handle`: PATCH with `{"instagram_handle": "@dralaura"}` → 200
  - `test_patch_accepts_facebook_page_id`: PATCH with `{"facebook_page_id": "DraLaura"}` → 200
  - `test_get_returns_social_fields`: GET `/admin/settings/clinic` → response body contains `social_ig_active`, `social_landings`, `instagram_handle`, `facebook_page_id`
  - `test_patch_rejects_handle_over_100_chars`: handle with 101 chars → 422
  - `test_tenant_isolation_social_fields`: tenant A's social fields do not leak into tenant B's GET response
  - Run: confirm all tests FAIL

- [ ] **P7-2** [CODE] Extend admin settings PATCH/GET in `admin_routes.py` (~40 LOC)
  - File: `orchestrator_service/admin_routes.py`
  - Add 4 optional fields to the settings PATCH Pydantic model: `social_ig_active: Optional[bool]`, `social_landings: Optional[dict]`, `instagram_handle: Optional[str] = Field(None, max_length=100)`, `facebook_page_id: Optional[str] = Field(None, max_length=100)`
  - Include the 4 fields in the SET clause of the update query (only when not None)
  - Include them in the GET response column SELECT
  - Run P7-1: all tests PASS

---

## Phase 8 — Frontend UI

> **Depends on**: Phase 7 (API accepts and returns social fields)

- [ ] **P8-1** [CODE] Add "Agente de Redes Sociales" section in `ConfigView.tsx` (~150 LOC)
  - File: `frontend_react/src/views/ConfigView.tsx`
  - New section in the general tab, visible to all admin roles (not CEO-gated — toggle has its own enable/disable safety)
  - Toggle: `social_ig_active` (boolean)
  - Text input: `instagram_handle` (placeholder "@tuusuario")
  - Text input: `facebook_page_id` (placeholder "NombreDePagina")
  - Collapsible "Landings de Redes Sociales" sub-section with 4 URL inputs: `blanqueamiento`, `implantes`, `lift`, `evaluacion` — these map to keys of `social_landings` JSONB
  - Save via existing PATCH `/admin/settings/clinic` — add the 4 new fields to the payload builder
  - Use `useTranslation()` for all labels

- [ ] **P8-2** [CODE] Add i18n keys to `es.json` (~30 LOC)
  - File: `frontend_react/src/locales/es.json`
  - Keys under `config.socialAgent`: `title`, `description`, `enabled`, `instagramHandle`, `instagramHandlePlaceholder`, `facebookPageId`, `facebookPageIdPlaceholder`, `landingsTitle`, `landingsDescription`, `landings.blanqueamiento`, `landings.implantes`, `landings.lift`, `landings.evaluacion`

- [ ] **P8-3** [CODE] Add i18n keys to `en.json` (~30 LOC)
  - File: `frontend_react/src/locales/en.json`
  - Same keys as P8-2, English translations

- [ ] **P8-4** [CODE] Add i18n keys to `fr.json` (~30 LOC)
  - File: `frontend_react/src/locales/fr.json`
  - Same keys as P8-2, French translations

- [ ] **P8-5** [MANUAL] UI smoke test
  - Open ConfigView in browser, scroll to "Agente de Redes Sociales"
  - Toggle ON, fill instagram_handle and a landing URL, click Save
  - Reload page: fields retain their values (DB persisted correctly)
  - Toggle OFF, Save, reload: toggle is OFF
  - Check Network tab: PATCH fires with correct payload including new fields

---

## Phase 9 — Integration Tests (End-to-End)

> **Depends on**: all prior phases complete

- [ ] **P9-1** [TEST] IG webhook → Solo engine → pitch + booking trigger
  - File: `tests/test_chatwoot_ig_full_flow.py` (~100 LOC)
  - Simulate Chatwoot IG webhook with body `"BLANQUEAMIENTO"`, tenant with `social_ig_active=True`, `social_landings={"blanqueamiento": "https://landing.com"}`
  - Mock OpenAI client; capture the `messages` list sent to the LLM
  - Assert: system message contains "blanqueamiento" pitch text and "https://landing.com"
  - Assert: system message contains "AMIGO" (friend detection rules present)
  - Assert: system message does NOT contain "ANTI-MARKDOWN" WhatsApp block

- [ ] **P9-2** [TEST] IG friend detection — casual greeting → no tools
  - File: `tests/test_chatwoot_ig_friend_detection.py` (~60 LOC)
  - Message: "Hola Lau, cómo andás?" on IG channel, `social_ig_active=True`
  - Capture LLM system prompt
  - Assert: friend detection block present in system prompt (prompt-level enforcement verified)
  - Assert: `triage_urgency` prohibition string present in system prompt

- [ ] **P9-3** [TEST] IG "ortodoncia" (no CTA group) → `list_services` tool logic
  - File: `tests/test_chatwoot_ig_list_services.py` (~60 LOC)
  - Message: "hola, info sobre ortodoncia?"
  - Assert: system prompt contains social preamble
  - Assert: `list_services` is in the allowed tools section of the preamble
  - Assert: `triage_urgency` is NOT in the allowed tools section

- [ ] **P9-4** [TEST] WhatsApp message on social-enabled tenant → no preamble (regression)
  - File: `tests/test_chatwoot_whatsapp_no_regression.py` (~50 LOC)
  - Tenant has `social_ig_active=True`, but `channel="whatsapp"`
  - Assert: system prompt does NOT contain "AMIGO" / "LEAD" preamble
  - Assert: system prompt DOES contain ANTI-MARKDOWN block
  - Assert: output is byte-identical to `tests/fixtures/golden_prompt_whatsapp.txt`

- [ ] **P9-5** [TEST] IG message on tenant with `social_ig_active=False` → standard prompt (regression)
  - File: `tests/test_social_flag_off_regression.py` (~50 LOC)
  - `channel="instagram"`, `social_ig_active=False`
  - Assert: system prompt does NOT contain social preamble
  - Assert: ANTI-MARKDOWN block is ABSENT (since channel is instagram, not whatsapp — note: block is channel-gated, not flag-gated)

> **Note on P9-5**: The ANTI-MARKDOWN block is gated by `channel == "whatsapp"`, not by `is_social_channel`. So for an IG message regardless of the flag, the ANTI-MARKDOWN block will not appear. The preamble, however, is gated by `is_social_channel` (flag + channel). Verify this matches design intent.

---

## Phase 10 — Manual Verification + Rollout

> **Depends on**: Phase 9 all green

- [ ] **P10-1** Enable `social_ig_active` for Laura's staging tenant via UI
  - Log in as CEO of the staging tenant
  - Navigate to ConfigView → "Agente de Redes Sociales"
  - Fill `instagram_handle`, `facebook_page_id`, and at minimum the `blanqueamiento` landing URL
  - Toggle ON and Save
  - Verify DB directly: `SELECT social_ig_active, instagram_handle FROM tenants WHERE id = X`

- [ ] **P10-2** IG DM "BLANQUEAMIENTO" → pitch + landing + booking flow
  - Send real IG DM "BLANQUEAMIENTO" via Chatwoot to the test tenant
  - Expected response: blanqueamiento pitch text, `https://landing.com` URL, and a direct booking trigger ("¿Qué día te queda cómodo?" or equivalent)
  - Verify: NO "¿te paso el WhatsApp?" in response
  - Verify: conversation is in Chatwoot under IG channel

- [ ] **P10-3** IG DM "Hola Lau, cómo andás?" → casual response, no tools
  - Expected: brief, warm, casual reply in voseo
  - Verify: no appointment confirmation, no anamnesis link, no tool output
  - Check `agent_turn_log` row: `tools_called = []` (or only harmless reads)

- [ ] **P10-4** IG DM "Hola, info sobre ortodoncia?" → `list_services` called
  - Expected: agent lists available services or asks follow-up
  - Check `agent_turn_log`: `tools_called` contains `list_services`

- [ ] **P10-5** IG DM with payment receipt image → `verify_payment_receipt` fires
  - If patient has a pending appointment with `payment_status = "pending"`, send a photo of a bank receipt
  - Expected: agent calls `verify_payment_receipt` and responds with confirmation or rejection based on data
  - Verify in `agent_turn_log`

- [ ] **P10-6** Monitor 48h for WhatsApp regressions
  - Check `chat_messages` for WhatsApp conversations: no unexpected preamble, no broken formatting
  - Check `agent_turn_log` for error spikes (compare error rate before/after deploy)
  - Check Chatwoot manually: WhatsApp responses look identical to pre-deploy behavior

- [ ] **P10-7** Rollback validation
  - Toggle `social_ig_active = false` from UI (do NOT redeploy)
  - Send another IG DM
  - Verify: system prompt captured in logs does NOT contain social preamble
  - Confirm preamble stops injecting within 1 turn (tenant row is read per turn)

---

## Phase 11 — Verify + Archive

- [ ] **P11-1** Run `sdd-verify` against spec
  - Execute `/sdd-verify instagram-facebook-social-agent`
  - Review all CRITICAL and WARNING findings

- [ ] **P11-2** Fix any CRITICAL/WARNING findings from P11-1
  - Address each CRITICAL before proceeding
  - Document any WARNING deferred with rationale

- [ ] **P11-3** Run `sdd-archive` to persist final state
  - Execute `/sdd-archive instagram-facebook-social-agent`
  - Confirm archive report saved to engram with `topic_key: sdd/instagram-facebook-social-agent/archive-report`

---

## Estimated LOC Summary

| Phase | File | Est. LOC |
|-------|------|----------|
| 1 | `040_add_social_ig_fields.py` | ~50 |
| 1 | `models.py` (delta) | ~6 |
| 2 | `services/social_routes.py` | ~180 |
| 3 | `services/social_prompt.py` | ~120 |
| 4 | `main.py` (delta) | ~60 |
| 5 | `agents/state.py` (delta) | ~10 |
| 5 | `agents/graph.py` (delta) | ~15 |
| 5 | `agents/specialists.py` (delta) | ~20 |
| 6 | `services/buffer_task.py` (delta) | ~25 |
| 7 | `admin_routes.py` (delta) | ~40 |
| 8 | `views/ConfigView.tsx` (delta) | ~150 |
| 8 | `locales/es.json` (delta) | ~30 |
| 8 | `locales/en.json` (delta) | ~30 |
| 8 | `locales/fr.json` (delta) | ~30 |
| **Total** | | **~766** |

## Test File Summary

| Phase | File | Est. LOC |
|-------|------|----------|
| 0 | `tests/fixtures/golden_prompt_whatsapp.txt` | golden |
| 1 | `tests/test_migration_040.py` | ~60 |
| 2 | `tests/test_social_routes.py` | ~90 |
| 3 | `tests/test_social_prompt.py` | ~80 |
| 4 | `tests/test_build_system_prompt_whatsapp_regression.py` | ~40 |
| 4 | `tests/test_build_system_prompt_social.py` | ~70 |
| 5 | `tests/test_agent_state_channel.py` | ~50 |
| 5 | `tests/test_specialists_social_preamble.py` | ~60 |
| 6 | `tests/test_buffer_task_social_channel.py` | ~80 |
| 7 | `tests/test_admin_settings_social.py` | ~70 |
| 9 | `tests/test_chatwoot_ig_full_flow.py` | ~100 |
| 9 | `tests/test_chatwoot_ig_friend_detection.py` | ~60 |
| 9 | `tests/test_chatwoot_ig_list_services.py` | ~60 |
| 9 | `tests/test_chatwoot_whatsapp_no_regression.py` | ~50 |
| 9 | `tests/test_social_flag_off_regression.py` | ~50 |
| **Total** | | **~920** |
