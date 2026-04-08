# Tasks: Clinic Support, Complaints & Review Config

**Change**: `clinic-support-complaints-config`
**Status**: READY
**Date**: 2026-04-07
**TDD**: Strict — test tasks come BEFORE implementation tasks within each phase.
**Total tasks**: 34

---

## Dependency Graph

```
1.1 (migration) → 1.2 (model)
1.1 + 1.2 → 2.1 (REQ-2/3 test) → 2.2 (endpoint impl)
2.2 → 3.1 (formatter test) → 3.2 (formatter impl) → 3.3 (prompt injection test) → 3.4 (prompt injection impl)
2.2 → 4.1 (derivhumano test) → 4.2 (derivhumano impl)
2.2 → 5.1 (followup test) → 5.2 (followup impl)
3.4 → 6.1 (SC-1 scenario test)
4.2 → 6.2 (SC-2 scenario test)
3.4 → 6.3 (SC-3 scenario test)
5.2 → 6.4 (SC-4 scenario test)
[independent] 7.1 (frontend) → 7.2 (i18n)
All phases → 8.1 (migration round-trip test)
```

---

## Phase 1: Infrastructure (DB + Model)

- [ ] 1.1 Create Alembic migration `039`: add 7 support/complaint columns to `tenants`
  - Files: `orchestrator_service/alembic/versions/039_add_tenant_support_complaints.py`
  - Depends on: none
  - Acceptance:
    - `revision = "039"`, `down_revision = "038"`
    - `upgrade()` calls `op.add_column` for all 7 columns in order:
      `complaint_escalation_email` (TEXT, nullable),
      `complaint_escalation_phone` (TEXT, nullable),
      `expected_wait_time_minutes` (INTEGER, nullable),
      `revision_policy` (TEXT, nullable),
      `review_platforms` (JSONB, nullable),
      `complaint_handling_protocol` (JSONB, nullable),
      `auto_send_review_link_after_followup` (BOOLEAN, not null, server_default='false')
    - `downgrade()` calls `op.drop_column` for all 7 in reverse order
    - File follows naming convention `039_add_tenant_support_complaints.py`
    - `auto_send_review_link_after_followup` uses `sa.Boolean()` with `server_default="false"` and `nullable=False`

- [ ] 1.2 Add 7 new columns to `Tenant` SQLAlchemy model
  - Files: `orchestrator_service/models.py`
  - Depends on: 1.1
  - Acceptance:
    - `Tenant` class adds the 7 columns after `derivation_email` (see design File 2)
    - `auto_send_review_link_after_followup = Column(Boolean, nullable=False, server_default="false")`
    - JSONB columns use `Column(JSONB, nullable=True)` — consistent with `working_hours`
    - No other model changes

---

## Phase 2: Backend — Pydantic Schemas + Endpoint (TDD)

- [ ] 2.1 Write unit tests for REQ-2 and REQ-3 validations
  - Files: `tests/test_support_complaints_config.py` (new file)
  - Depends on: none (pure unit tests against Pydantic models)
  - Acceptance:
    - Test class `TestReviewPlatformItem`:
      - `test_valid_platform`: `{name: "Google", url: "https://g.co/r", show_after_days: 1}` → validates without error
      - `test_invalid_url_no_scheme`: `url = "g.co/r"` → raises `ValidationError` mentioning `url`
      - `test_invalid_days_zero`: `show_after_days = 0` → raises `ValidationError` mentioning `show_after_days`
      - `test_default_days`: no `show_after_days` provided → defaults to `1`
    - Test class `TestComplaintHandlingProtocol`:
      - `test_valid_all_levels`: `{level_1: "...", level_2: "...", level_3: "..."}` → validates
      - `test_valid_partial`: only `level_1` provided → validates (others are optional)
      - `test_extra_key_rejected`: `{level_1: "...", extra_key: "x"}` → raises `ValidationError`
    - Test class `TestUpdateTenantValidation` (integration-style, may use `TestClient` from FastAPI):
      - `test_invalid_complaint_email`: PUT body with `complaint_escalation_email = "notanemail"` → returns 422
      - `test_negative_wait_time`: PUT body with `expected_wait_time_minutes = -1` → returns 422
      - `test_zero_wait_time`: `expected_wait_time_minutes = 0` → returns 422
      - `test_review_platforms_not_array`: `review_platforms = "not-a-list"` → returns 422
      - `test_revision_policy_too_long`: `revision_policy = "x" * 2001` → returns 422
      - `test_valid_full_update`: all 7 fields valid → returns 200 with `{"status": "updated"}`
    - All tests FAIL before Phase 2 implementation (red phase)

- [ ] 2.2 Implement Pydantic schemas and endpoint field handlers
  - Files: `orchestrator_service/admin_routes.py`
  - Depends on: 2.1, 1.1
  - Acceptance:
    - `ReviewPlatformItem` Pydantic model added near top of file
    - `ComplaintHandlingProtocol` Pydantic model added with `extra = "forbid"`
    - `GET /admin/tenants` SELECT query extended with 7 new columns
    - `GET /admin/tenants` response loop adds defensive `json.loads()` for `review_platforms` and `complaint_handling_protocol`
    - `PUT /admin/tenants/{id}` handler adds 7 new `if "field" in data:` blocks per design File 3C
    - `json.dumps()` used to serialize JSONB fields before passing to asyncpg
    - Tests from 2.1 pass (green phase)

---

## Phase 3: Formatter + Prompt Injection (TDD)

- [ ] 3.1 Write unit tests for `_format_support_policy()`
  - Files: `tests/test_support_complaints_config.py`
  - Depends on: none (pure unit test — function takes a dict, returns a string)
  - Acceptance:
    - Test class `TestFormatSupportPolicy`:
      - `test_empty_tenant_row_returns_empty_string`: `_format_support_policy({})` → returns `""`
      - `test_all_null_fields_returns_empty_string`: all 7 fields set to `None` → returns `""`
      - `test_minimal_config_returns_block_header`: `{expected_wait_time_minutes: 20}` → result starts with `"## PROTOCOLO DE SOPORTE Y QUEJAS"`
      - `test_wait_time_in_output`: `{expected_wait_time_minutes: 15}` → result contains `"15 minutos"`
      - `test_revision_policy_in_output`: `{revision_policy: "ajustes gratuitos 30 días"}` → result contains `"ajustes gratuitos 30 días"` in NIVEL 2 section
      - `test_complaint_email_in_output`: `{complaint_escalation_email: "q@c.com"}` → result contains `"q@c.com"` in NIVEL 3 section
      - `test_review_platforms_in_output`: `{review_platforms: [{"name": "Google", "url": "https://g.co", "show_after_days": 1}]}` → result contains `"Google"` and `"https://g.co"`
      - `test_custom_protocol_level_overrides_default`: `{complaint_handling_protocol: {"level_1": "Di: Escuché."}}` → NIVEL 1 section contains `"Di: Escuché."` and does NOT contain the default `"Lamento mucho"`
      - `test_jsonb_as_string_is_parsed`: `{review_platforms: '[{"name":"G","url":"https://x","show_after_days":1}]'}` (string) → result still contains `"G"` (tests the `json.loads` fallback)
      - `test_graduated_escalation_rule_always_present`: any non-empty config → result contains `"NUNCA pasar directamente a NIVEL 2 o NIVEL 3"`
      - `test_legal_disclaimer_always_present`: any non-empty config → result contains `"NUNCA confirmar errores de cobro o mala praxis"`
    - Tests FAIL before 3.2 implementation (red phase)

- [ ] 3.2 Implement `_format_support_policy()` function
  - Files: `orchestrator_service/main.py`
  - Depends on: 3.1
  - Acceptance:
    - New function `_format_support_policy(tenant_row: dict) -> str` added near `_format_insurance_providers()`
    - All logic matches the design pseudocode (design File 4A)
    - All tests from 3.1 pass (green phase)

- [ ] 3.3 Write unit tests for `build_system_prompt()` injection
  - Files: `tests/test_support_complaints_config.py`
  - Depends on: 3.2
  - Acceptance:
    - Test class `TestBuildSystemPromptSupportInjection`:
      - `test_support_block_injected_when_configured`: call `build_system_prompt(..., tenant_row={"expected_wait_time_minutes": 10})` → returned prompt contains `"## PROTOCOLO DE SOPORTE Y QUEJAS"`
      - `test_support_block_absent_when_unconfigured`: call `build_system_prompt(..., tenant_row={})` → returned prompt does NOT contain `"## PROTOCOLO DE SOPORTE Y QUEJAS"`
      - `test_support_block_absent_when_no_tenant_row`: call `build_system_prompt()` without `tenant_row` param → no error, no support block
      - `test_backward_compat_existing_callers`: call `build_system_prompt()` with the existing param set (no `tenant_row`) → function does not raise TypeError
    - Tests FAIL before 3.4 implementation (red phase)

- [ ] 3.4 Add `tenant_row` parameter to `build_system_prompt()` and inject support policy block
  - Files: `orchestrator_service/main.py`, `orchestrator_service/services/buffer_task.py`
  - Depends on: 3.3
  - Acceptance:
    - `build_system_prompt()` signature adds `tenant_row: dict = None` as a new parameter with default `None`
    - Inside function: calls `_format_support_policy(tenant_row or {})` and assigns result to `support_policy_block`
    - `support_policy_block` inserted between the insurance/FAQ block and the `ADMISIÓN — DATOS MÍNIMOS` block (position 14.5 in prompt structure)
    - `buffer_task.py` tenant SELECT query extended to include all 7 new fields
    - `buffer_task.py` passes `tenant_row=full_tenant_row_dict` to `build_system_prompt()`
    - Tests from 3.3 pass (green phase)

---

## Phase 4: `derivhumano` Tool Modification (TDD)

- [ ] 4.1 Write unit tests for `derivhumano` complaint routing
  - Files: `tests/test_support_complaints_config.py`
  - Depends on: 1.1, 1.2
  - Acceptance:
    - Test class `TestDervhumanoComplaintRouting`:
      - `test_complaint_keyword_detection`: for each keyword in `COMPLAINT_KEYWORDS` set, verify `any(kw in reason_lower for kw in COMPLAINT_KEYWORDS)` returns True when keyword present in reason
      - `test_no_complaint_keyword_no_routing`: reason = `"paciente solicitó hablar con un humano"` → no complaint keywords matched → `is_complaint = False`
      - `test_complaint_routing_adds_complaint_email`: mock `db.pool.fetchrow` to return `{"complaint_escalation_email": "q@c.com"}`; mock `emails` set; run complaint routing logic → `"q@c.com"` is in `emails`
      - `test_both_emails_when_both_set`: mock tenant returning both `complaint_escalation_email = "q@c.com"` and `derivation_email = "d@c.com"`; after full routing logic → both addresses in `emails`
      - `test_fallback_when_no_complaint_email`: mock tenant returning `complaint_escalation_email = None` → no new email added; existing behavior unchanged
      - `test_sql_uses_tenant_id_isolation`: verify the SELECT for `complaint_escalation_email` includes `WHERE id = $1` with the tenant_id context var value
    - Tests FAIL before 4.2 implementation (red phase)

- [ ] 4.2 Implement `derivhumano` complaint routing
  - Files: `orchestrator_service/main.py`
  - Depends on: 4.1, 1.1
  - Acceptance:
    - `COMPLAINT_KEYWORDS` frozenset defined at module level (not inside the function)
    - Keyword check runs on `reason.lower()` after the existing `derivation_email` block
    - `db.pool.fetchrow("SELECT complaint_escalation_email FROM tenants WHERE id = $1", tenant_id)` executed only when `is_complaint = True`
    - When `complaint_escalation_email` is not NULL, it is added to `emails` set
    - Existing `emails` population logic (derivation_email + professionals) is NOT modified
    - Tests from 4.1 pass (green phase)

---

## Phase 5: Followup Job Modification (TDD)

- [ ] 5.1 Write unit tests for followup job review link logic
  - Files: `tests/test_support_complaints_config.py`
  - Depends on: 1.1
  - Acceptance:
    - Test class `TestFollowupReviewLink`:
      - `test_no_review_when_flag_false`: appointment dict with `auto_send_review_link_after_followup = False` → `review_suffix` is empty string `""`
      - `test_no_review_when_no_platforms`: flag=True but `review_platforms = []` → `review_suffix` is empty string
      - `test_review_appended_when_eligible`: flag=True, `review_platforms = [{"name": "Google", "url": "https://g.co", "show_after_days": 1}]`, `days_since = 1` → `review_suffix` contains `"https://g.co"`
      - `test_platform_not_eligible_if_days_not_met`: flag=True, platform with `show_after_days = 3`, `days_since = 1` → `review_suffix` is empty (1 < 3)
      - `test_multiple_platforms_both_eligible`: two platforms with `show_after_days = 1` and `show_after_days = 2`, `days_since = 2` → both URLs in `review_suffix`
      - `test_platform_jsonb_as_string_parsed`: `review_platforms` is a JSON string → parsed correctly, review suffix includes URL
      - `test_final_message_contains_original_and_suffix`: `final_message = message + review_suffix` → assert `final_message.startswith(message[:20])` and `final_message.endswith(review_suffix[-20:])`
    - Tests FAIL before 5.2 implementation (red phase)

- [ ] 5.2 Implement followup job review link logic
  - Files: `orchestrator_service/jobs/followups.py`
  - Depends on: 5.1, 1.1
  - Acceptance:
    - Tenant SELECT query in `send_post_treatment_followups()` extended to include `t.auto_send_review_link_after_followup, t.review_platforms`
    - Note: verify actual tenant column name (`clinic_name` vs `name`) and fix if needed — existing bug in followups.py uses `t.name` but model has `clinic_name`
    - Review suffix logic follows design File 5B pseudocode
    - `days_since = (date.today() - apt["appointment_datetime"].date()).days` used for gate check
    - `json.loads()` fallback applied when `review_platforms` is a string
    - `final_message = message + review_suffix` passed to `send_whatsapp_message()`
    - Tests from 5.1 pass (green phase)

---

## Phase 6: Frontend Modal Section (TDD)

- [ ] 6.1 Write unit/component tests for Soporte y Quejas section
  - Files: `frontend_react/src/views/__tests__/ClinicsView.support.test.tsx` (new file)
  - Depends on: none (pure component tests with mock data)
  - Acceptance:
    - Test: section header "Soporte, Quejas y Reseñas" is present in the modal when `isModalOpen = true`
    - Test: section is collapsed by default (content of the 4 sub-blocks is not rendered on initial render)
    - Test: clicking the section header toggles the `supportSectionOpen` state and reveals the sub-blocks
    - Test: adding a review platform item (click "+ Agregar plataforma") renders a new row with name/url/days inputs
    - Test: removing a review platform item removes it from the array
    - Test: `auto_send_review_link_after_followup` checkbox reflects formData value
    - Test: `complaint_escalation_email` input updates formData correctly
    - Test: all 3 level textareas for complaint protocol update `complaint_handling_protocol.level_1/2/3`
    - Tests FAIL before 6.2 implementation (red phase)

- [ ] 6.2 Implement Soporte y Quejas section in ClinicsView.tsx
  - Files: `frontend_react/src/views/ClinicsView.tsx`
  - Depends on: 6.1
  - Acceptance:
    - `supportSectionOpen` state variable added (`useState(false)`)
    - `MessageSquare` imported from `lucide-react`
    - 7 new fields added to `formData` state initial value and to the form reset on `editingClinica` change
    - The collapsible section follows the structure from design File 6B
    - Section uses orange accent color (`text-orange-400`, `focus:ring-orange-500`) consistent with the "complaint" context — differentiated from the blue accent used in other sections
    - `handleSubmit` includes all 7 new fields in the PUT payload
    - Tests from 6.1 pass (green phase)

- [ ] 6.3 Add i18n keys to all 3 locale files
  - Files: `frontend_react/src/locales/es.json`, `en.json`, `fr.json`
  - Depends on: none (independent)
  - Acceptance:
    - All 25 keys from REQ-9 added to all 3 files
    - Spanish values match REQ-9 exactly
    - English values are accurate translations (not machine-literal)
    - French values are accurate translations
    - No existing keys are modified
    - JSON files remain valid (no trailing commas, correct nesting)

---

## Phase 7: Acceptance Scenario Verification

- [ ] 7.1 Verify SC-1 — Level-1 complaint: wait time
  - Files: `tests/test_support_complaints_config.py`
  - Depends on: 3.4
  - Acceptance:
    - Test `test_sc1_wait_time_complaint`:
      - Tenant row: `{expected_wait_time_minutes: 15, complaint_handling_protocol: {"level_1": "Empatizá. Reconocé la espera."}}`
      - Call `build_system_prompt(..., tenant_row=tenant_row)` with this row
      - Assert returned prompt contains `"15 minutos"` in the PROTOCOLO DE SOPORTE Y QUEJAS section
      - Assert returned prompt contains `"Empatizá. Reconocé la espera."` in NIVEL 1
      - Assert returned prompt contains `"NUNCA pasar directamente a NIVEL 2"` (no-skip rule)
      - Assert returned prompt does NOT contain `derivhumano` in the NIVEL 1 instructions (level 1 must not trigger escalation)

- [ ] 7.2 Verify SC-2 — Billing complaint → dual email routing
  - Files: `tests/test_support_complaints_config.py`
  - Depends on: 4.2
  - Acceptance:
    - Test `test_sc2_complaint_keyword_routing`:
      - `reason = "queja de cobro incorrecto en turno anterior"` → `is_complaint = True` (keywords: "queja" + "cobro")
      - Mock `db.pool.fetchrow` to return `complaint_escalation_email = "quejas@c.com"`
      - Assert `"quejas@c.com"` added to `emails` set
      - `derivation_email = "info@c.com"` already in `emails` from prior block
      - Assert `"info@c.com"` still in `emails` (not replaced — both present)
    - Test `test_sc2_legal_disclaimer_in_prompt`:
      - Call `_format_support_policy({complaint_escalation_email: "q@c.com", complaint_handling_protocol: {"level_3": "Derivar."}})`
      - Assert result contains `"NUNCA confirmar errores de cobro o mala praxis"`

- [ ] 7.3 Verify SC-3 — Patient requests review link
  - Files: `tests/test_support_complaints_config.py`
  - Depends on: 3.2
  - Acceptance:
    - Test `test_sc3_review_link_in_prompt`:
      - `tenant_row = {review_platforms: [{"name": "Google Maps", "url": "https://g.co/r/xxx", "show_after_days": 1}]}`
      - Call `_format_support_policy(tenant_row)`
      - Assert result contains `"Google Maps"` and `"https://g.co/r/xxx"`
      - Assert result contains `"Ofrecé el link directamente"` (the agent instruction to share the URL)
    - Test `test_sc3_no_require_to_ask_clinic`:
      - Assert the review section does NOT contain the phrase `"consultá con la clínica"` or similar
      - The agent instruction says to share the URL, not redirect to the clinic

- [ ] 7.4 Verify SC-4 — Followup job review link
  - Files: `tests/test_support_complaints_config.py`
  - Depends on: 5.2
  - Acceptance:
    - Test `test_sc4_review_appended_to_followup`:
      - Mock appointment with `auto_send_review_link_after_followup = True`
      - `review_platforms = [{"name": "Instagram", "url": "https://ig.me/xxx", "show_after_days": 1}]`
      - `appointment_datetime` = yesterday (days_since = 1)
      - Run review suffix logic (extracted from followup job as a pure function for testability)
      - Assert `review_suffix` contains `"https://ig.me/xxx"`
      - Assert `review_suffix` contains `"Instagram"`
      - Assert `final_message = message + review_suffix` is longer than `message` alone
    - Test `test_sc4_followup_sent_flag_updated`:
      - After `send_whatsapp_message` returns True, the UPDATE SQL that sets `followup_sent = true` MUST be executed
      - This is verified by checking the mock call to `db.pool.execute` includes `followup_sent = true`

---

## Phase 8: Migration Round-Trip Test

- [ ] 8.1 Integration smoke test: alembic upgrade → downgrade → upgrade
  - Files: Migration `039`
  - Depends on: 1.1, 1.2
  - Acceptance:
    - `alembic upgrade head` runs without error against a test database
    - All 7 columns exist in `tenants` after upgrade
    - `auto_send_review_link_after_followup` has default value `false` for existing rows
    - `alembic downgrade -1` removes all 7 columns cleanly
    - Second `alembic upgrade head` re-adds all 7 without error
    - No data in other `tenants` columns is affected at any step
    - Existing `tenants` rows have `auto_send_review_link_after_followup = false` after upgrade (server_default works)

---

## File Summary

| File | Tasks | Change type |
|------|-------|-------------|
| `orchestrator_service/alembic/versions/039_add_tenant_support_complaints.py` | 1.1 | NEW FILE |
| `orchestrator_service/models.py` | 1.2 | MODIFY — add 7 columns to Tenant |
| `tests/test_support_complaints_config.py` | 2.1, 3.1, 3.3, 4.1, 5.1, 6.1 (partial), 7.1–7.4 | NEW FILE |
| `orchestrator_service/admin_routes.py` | 2.2 | MODIFY — schemas + endpoint |
| `orchestrator_service/main.py` | 3.2, 3.4, 4.2 | MODIFY — formatter + injection + derivhumano |
| `orchestrator_service/services/buffer_task.py` | 3.4 | MODIFY — tenant query + pass tenant_row |
| `orchestrator_service/jobs/followups.py` | 5.2 | MODIFY — review suffix logic |
| `frontend_react/src/views/ClinicsView.tsx` | 6.2 | MODIFY — new collapsible section |
| `frontend_react/src/views/__tests__/ClinicsView.support.test.tsx` | 6.1 | NEW FILE |
| `frontend_react/src/locales/es.json` | 6.3 | MODIFY — 25 new keys |
| `frontend_react/src/locales/en.json` | 6.3 | MODIFY — 25 new keys |
| `frontend_react/src/locales/fr.json` | 6.3 | MODIFY — 25 new keys |

---

## Notes for Implementer

1. **TDD is mandatory**: create `tests/test_support_complaints_config.py` before editing `main.py`, `admin_routes.py`, or `followups.py`. Confirm red (fail) before each implementation task, green (pass) after.

2. **Migration style**: Follow `030`'s pattern — no idempotency guard needed for `ADD COLUMN` (Alembic handles it). Use `revision = "039"`, `down_revision = "038"`.

3. **JSONB serialization**: asyncpg may return JSONB columns as strings. Always apply `json.loads()` defensively in both the admin endpoint response and inside `_format_support_policy()`. The test `test_jsonb_as_string_is_parsed` explicitly covers this.

4. **`followups.py` bug note**: The existing query uses `t.name` but the ORM model has `clinic_name`. Verify against the actual DB column and fix during task 5.2 if necessary. Do not introduce new bugs in the same pattern.

5. **`derivhumano` keyword set**: Define `COMPLAINT_KEYWORDS` as a `frozenset` at module level (not inside the function) for O(1) lookup and to keep the function clean.

6. **Frontend section color**: Use orange accent (`text-orange-400`, `border-orange-500/20`, `focus:ring-orange-500`) for the Soporte y Quejas section to visually distinguish it from the blue-accented standard fields. This follows the existing pattern where banking uses `text-blue-400` and the support section gets its own color for quick visual identification.

7. **`_format_support_policy()` placement**: Place the new function immediately after `_format_insurance_providers()` in `main.py`. This keeps the formatter functions co-located and makes them easy to find.

8. **`extract_review_suffix()` helper**: Consider extracting the review suffix logic in `followups.py` into a pure function `_build_review_suffix(platforms_raw, days_since, flag)` for testability. This is not strictly required but makes task 5.1 tests significantly cleaner.

9. **Prompt token budget**: `_format_support_policy()` returns `""` when unconfigured. Confirm that the empty string does not inject a blank line into the prompt (strip the result or use conditional injection in `build_system_prompt()`).

10. **`auto_send_review_link_after_followup` in frontend**: The checkbox state MUST default to `false` when creating a new clinic. When editing, read from the API response. Avoid treating `undefined` as `false` silently — use `?? false` not just `||`.
