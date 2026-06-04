# Tasks: Robustez en Confirmaciones HSM (hsm-confirmations-robustness)

## Phase 1: Webhook Intercept Synonyms

- [x] 1.1 In `orchestrator_service/routes/chat_webhooks.py`, expand the `_CONFIRM_BUTTONS` list to include: `"conservo"`, `"asisto"`, `"voy"`, `"acepto"`, `"confirmo"`, `"conservo ✅"`, `"asisto ✅"`, `"voy ✅"`, `"acepto ✅"`, `"confirmo ✅"`, `"sí, voy"`, `"si, voy"`, `"sí, asisto"`, `"si, asisto"`.
- [x] 1.2 In `orchestrator_service/routes/chat_webhooks.py`, ensure incoming message text is lowercased, stripped, and matched cleanly against the updated `_CONFIRM_BUTTONS` set.

## Phase 2: Core Tool Implementation

- [x] 2.1 In `orchestrator_service/main.py`, implement `@tool async def confirm_appointment` accepting optional params: `appointment_id`, `approximate_time`, and `target_date`.
- [x] 2.2 In `confirm_appointment`, extract `tenant_id` from `current_tenant_id.get()` and enforce multi-tenancy filter `tenant_id = $x` in all SQL queries.
- [x] 2.3 If `appointment_id` is provided, fetch the corresponding appointment; verify `tenant_id` ownership and raise/return error if mismatched or not found.
- [x] 2.4 If `appointment_id` is omitted, fetch the patient using normalized `current_customer_phone.get()` and query their future upcoming appointments (`appointment_datetime > NOW()`) in state `'scheduled'` or `'pending'`. Join with `professionals` and `treatment_types` to fetch names.
- [x] 2.5 If `target_date` is specified, parse it with `parse_date` and filter list to appointments matching the parsed date (in localized tenant timezone).
- [x] 2.6 If `approximate_time` is specified, parse it to hour and minute (with PM adjustment for morning/afternoon fallback) and match the closest localized appointment.
- [x] 2.7 Update the matched appointment status to `'confirmed'` and set `updated_at = NOW()`.
- [x] 2.8 Compute time discrepancies: if parsed `approximate_time` differs from localized appointment time, include a `WARNING` in the response string.
- [x] 2.9 Format response strings exactly: success without warning, success with warning, and error when no appointments exist.
- [x] 2.10 Emit the `APPOINTMENT_UPDATED` Socket.IO event to the tenant room `tenant:{tenant_id}`.
- [x] 2.11 Trigger the Telegram notification with `fire_telegram_notification` setting `source="agent_tool"`.
- [x] 2.12 Register `confirm_appointment` in `DENTAL_TOOLS` list in `orchestrator_service/main.py`.

## Phase 3: Agent Integration

- [x] 3.1 In `orchestrator_service/agents/specialists.py`, import `confirm_appointment` inside `BookingAgent._get_tools()` and add it to the returned tool list.
- [x] 3.2 In `orchestrator_service/agents/specialists.py`, update the system prompt for `BookingAgent` to guide the LLM to call `confirm_appointment` for natural language confirmations and handle warning outputs.

## Phase 4: Testing & Verification

- [x] 4.1 Write integration tests in `tests/test_hsm_confirmation_webhook.py` to verify synonym matching quick replies intercept and confirm appointments without LLM involvement.
- [x] 4.2 Write tests in `tests/test_confirm_appointment_tool.py` to check the tool's time proximity calculations, target date parsing, and discrepancy warnings.
- [x] 4.3 Verify multi-tenant data isolation: verify the tool blocks actions on appointments of a different tenant.

## Phase 5: Review & Merge

- [x] 5.1 Run project linter and validation checks on modified files.
- [x] 5.2 Confirm all database operations enforce the strict multi-tenancy `tenant_id` filter.
- [x] 5.3 Commit changes using Conventional Commits style.
