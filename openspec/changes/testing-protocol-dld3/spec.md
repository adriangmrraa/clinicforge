# Spec — DLD-3: Testing Protocol Before Applying Changes in Production

**Change ID:** `testing-protocol-dld3`
**Ticket:** DLD-3
**Status:** Draft
**Fecha:** 2026-04-17

---

## RFC Keywords

Throughout this document: MUST = mandatory, SHALL = equivalent to MUST, SHOULD = recommended, MAY = optional.

---

## Context

### What already exists

- CI pipeline (`.github/workflows/ci.yml`): lint (ruff + ESLint), pytest against a real Postgres 13 + Redis container, Alembic migration run, frontend build.
- Health probe endpoints: `GET /admin/ai-engine/health` probes both engines (solo + multi) in parallel and returns `ok`, `latency_ms`, `detail` per engine. Defined in `orchestrator_service/routes/ai_engine_health.py`.
- Agent probe: `agents/graph.py:probe()` runs a synthetic turn on a minimal fake state — used by the health endpoint to confirm multi-engine liveness without touching real data.
- Existing test suite (`tests/`) with fixture factory `tests/fixtures/tenants.py` (`make_tenant_row`) and 40+ test files covering individual tools, services, and e2e flows.

### What is missing (gap analysis from exploration)

| Gap | Impact |
|-----|--------|
| No sandbox tenant in production | Changes cannot be validated against real infrastructure without risking real patient data |
| Golden file coverage is WhatsApp-only (no golden files exist at all yet — the CI probe covers routing logic only) | Prompt regressions on Instagram, Facebook, and Telegram go undetected |
| No post-deploy smoke test script | After a deploy to production, the only signal is observing live traffic |
| No dedicated test phone number that does NOT send real WhatsApp messages | Any test via the real sandbox tenant could reach a real patient |
| No enforced gate requiring golden file update before merge | Prompt changes merge without verifying output stability |

---

## 1. Requirements

### R1 — Sandbox Tenant in Production

A tenant row with `clinic_name = 'ClinicForge Sandbox'` and `id = SANDBOX_TENANT_ID` (an agreed-upon UUID stored in an environment variable `SANDBOX_TENANT_ID`) MUST exist in the production database at all times. This tenant MUST NOT be deleted or repurposed.

The sandbox tenant MUST have the following configuration:
- `ai_engine_mode`: `'solo'` (default; CEO can toggle for engine tests)
- `config.sandbox: true` — a sentinel JSONB field used by middleware to restrict outbound messaging
- `owner_email`: a clinic-team internal email address (e.g. `sandbox@clinicforge.io`)
- All non-nullable columns populated with realistic values (use `make_tenant_row()` defaults as reference)

A one-time seed script (`scripts/seed_sandbox_tenant.py`) MUST create the sandbox tenant via the existing ORM path (not raw SQL) and be idempotent (safe to run twice without creating a duplicate).

### R2 — Golden File Regression Tests for All Channels

Golden file tests MUST cover the following channels:

| Channel | File path |
|---------|-----------|
| WhatsApp | `tests/golden/whatsapp.json` |
| Instagram | `tests/golden/instagram.json` |
| Facebook | `tests/golden/facebook.json` |
| Telegram | `tests/golden/telegram.json` |

Each golden file MUST contain at least the following scenario categories:

| Category | Minimum scenarios per channel |
|----------|-------------------------------|
| New patient greeting | 1 |
| Appointment booking (happy path) | 1 |
| Urgency / pain triage | 1 |
| Human handoff trigger | 1 |
| Out-of-scope deflection | 1 |

**Golden file format** (JSON array of objects):
```json
[
  {
    "id": "string — unique scenario identifier (snake_case)",
    "channel": "whatsapp | instagram | facebook | telegram",
    "description": "string — human-readable scenario name",
    "input": {
      "phone": "string",
      "text": "string",
      "tenant_id": "string (SANDBOX_TENANT_ID or test UUID)"
    },
    "expected_output": {
      "contains": ["string — substrings that MUST appear in the response"],
      "not_contains": ["string — substrings that MUST NOT appear"],
      "tool_calls": ["string — tool names that MUST have been invoked, empty list if none required"]
    }
  }
]
```

The test runner (`tests/test_golden_files.py`) MUST:
- Load each golden file and parameterize one test per scenario entry.
- Invoke the agent using mocked DB + Redis (same pattern as existing `tests/test_agent_behavioral_correction.py`).
- Assert `contains` substrings are present (case-insensitive).
- Assert `not_contains` substrings are absent (case-insensitive).
- Assert `tool_calls` lists the expected tools (order-independent match against `intermediate_steps`).

**Channel-specific prompt injection:** the test runner MUST pass a `channel` field to `build_system_prompt()` (or its equivalent) so that channel-specific greeting blocks are activated. If `build_system_prompt` does not yet accept a `channel` parameter, this spec does NOT require adding it — the test SHOULD use the closest available injection point and document the limitation.

### R3 — Post-Deploy Smoke Test Script

A script `scripts/smoke_test.py` MUST exist and be executable with:

```bash
python scripts/smoke_test.py --base-url https://your-production-url.com --admin-token $ADMIN_TOKEN
```

The script MUST verify, in order:

| Check | Endpoint or mechanism | Pass condition |
|-------|-----------------------|----------------|
| S1 — Orchestrator liveness | `GET /health` | HTTP 200, `{"status": "ok"}` |
| S2 — BFF liveness | `GET /` on BFF (port 3000) | HTTP 200 or 204 |
| S3 — DB connectivity | `GET /admin/ai-engine/health` | Both engines return `ok: true`; any `ok: false` is a FAIL |
| S4 — Agent probe (solo engine) | `GET /admin/ai-engine/health` | `solo.ok == true` AND `solo.latency_ms < 5000` |
| S5 — Agent probe (multi engine) | `GET /admin/ai-engine/health` | `multi.ok == true` OR multi is `ok: false` with `detail` containing "disabled" (multi is opt-in) |
| S6 — Sandbox tenant reachable | `GET /admin/tenants` with `X-Tenant-ID: $SANDBOX_TENANT_ID` | HTTP 200, tenant row in response |
| S7 — Auth endpoint | `POST /auth/login` with known test credentials | HTTP 200 or 401 (reachable; 500 is a FAIL) |

The script MUST:
- Print a `[PASS]` / `[FAIL]` line per check.
- Exit with code `0` if ALL checks pass, `1` if any check fails.
- Accept a `--timeout` flag (default: 10 seconds per check).
- NOT create, modify, or delete any data in the database.

### R4 — Sandbox Test Phone Number (No Real WhatsApp Sends)

The sandbox tenant MUST have `bot_phone_number` set to a value that the outbound messaging middleware intercepts and discards instead of forwarding to YCloud.

**Implementation:** in `orchestrator_service/services/response_sender.py`, the `send_sequence()` method (the single outbound chokepoint) MUST check:

```python
if tenant_config.get("sandbox") is True:
    logger.info("[SANDBOX] Suppressing outbound message to %s: %s", phone, text[:80])
    return  # Do NOT call YCloud or any external messaging API
```

This check MUST be applied BEFORE any call to `ycloud_client`, `chatwoot_client`, or any other external messaging provider. The log line MUST include the prefix `[SANDBOX]` for easy filtering.

The same guard MUST be applied in `whatsapp_service/main.py` for any outbound call triggered from that service.

### R5 — Golden File Baseline Update Gate

Any pull request that modifies any of the following MUST include an update to the relevant golden files in the same commit before merging:

- `orchestrator_service/main.py` — changes to `build_system_prompt()` or any system prompt string constant
- `orchestrator_service/agents/` — any file in the agents directory (multi-engine prompts)
- Any file whose diff contains the string `system_prompt`, `GREETING`, `INSTRUCTIONS`, or `TORA_PROMPT`

**Enforcement mechanism:** a CI check job `golden-file-freshness` MUST be added to `.github/workflows/ci.yml`. It MUST:
1. Run `pytest tests/test_golden_files.py -v` against the current branch.
2. If the golden file tests fail, the job MUST fail with exit code 1 — blocking merge.

**Baseline update workflow (for developers):**
When a prompt change is intentional and the golden file needs updating, the developer MUST:
1. Run `python scripts/update_golden_baselines.py` (see Section 3 — Scenarios for the exact behavior).
2. Review the diff of the golden files.
3. Commit the golden file changes alongside the prompt change in the same PR.

---

## 2. Scenarios

### SC-1 — Sandbox Tenant Outbound Suppression

**Given** the sandbox tenant has `config.sandbox = true`
**And** a test message `"Hola, quiero un turno"` arrives from phone `+5491100000001`
**When** the agent processes the message and generates a response
**Then** `response_sender.py:send_sequence()` logs a `[SANDBOX]` line
**And** no HTTP call is made to YCloud or Chatwoot
**And** the internal response object is still returned (the agent ran to completion)

### SC-2 — Golden File: WhatsApp New Patient Greeting

**Given** golden file `tests/golden/whatsapp.json` scenario `id = "wa_new_patient_greeting"`
**And** the patient does not exist in the `patients` table (simulated via mock)
**When** `pytest tests/test_golden_files.py::test_golden[wa_new_patient_greeting]` runs
**Then** the agent response MUST contain the greeting phrase(s) defined in `expected_output.contains`
**And** MUST NOT contain any `[INTERNAL_*]` marker
**And** the test MUST pass without any external API calls (fully mocked)

### SC-3 — Golden File: Telegram Urgency Triage

**Given** golden file `tests/golden/telegram.json` scenario `id = "tg_urgency_pain"`
**And** input text `"me duele mucho una muela desde ayer"`
**When** the test runs
**Then** `triage_urgency` MUST appear in `intermediate_steps`
**And** the response MUST contain at least one of: `"urgente"`, `"turno"`, `"disponibilidad"` (case-insensitive)
**And** MUST NOT contain `"No puedo"` or `"no tengo acceso"`

### SC-4 — Smoke Test: All Checks Pass on Clean Deploy

**Given** a freshly deployed production environment with all services running
**When** `python scripts/smoke_test.py --base-url $PROD_URL --admin-token $ADMIN_TOKEN` runs
**Then** checks S1–S7 ALL print `[PASS]`
**And** the script exits with code `0`

### SC-5 — Smoke Test: DB Down Detected

**Given** the orchestrator is running but PostgreSQL is unreachable
**When** the smoke test runs
**Then** check S3 (`/admin/ai-engine/health`) returns `ok: false` for both engines
**And** the script prints `[FAIL]` for S3 and S4
**And** exits with code `1`

### SC-6 — Golden File Gate Blocks Merge on Prompt Change

**Given** a PR that modifies `build_system_prompt()` in `main.py`
**And** the golden files have NOT been updated to reflect the change
**When** the `golden-file-freshness` CI job runs
**Then** `pytest tests/test_golden_files.py` FAILS on at least one scenario
**And** the CI job exits with code `1`
**And** the PR is blocked from merging until golden files are updated

### SC-7 — Seed Script is Idempotent

**Given** `scripts/seed_sandbox_tenant.py` has already been run once
**When** it is run a second time
**Then** the script MUST complete without error
**And** exactly ONE sandbox tenant row exists in `tenants` (no duplicate)
**And** the script outputs `"Sandbox tenant already exists, skipping."` or equivalent

### SC-8 — Instagram Human Handoff Golden File

**Given** golden file `tests/golden/instagram.json` scenario `id = "ig_human_handoff"`
**And** input text `"necesito hablar con alguien"`
**When** the test runs
**Then** `derivhumano` MUST appear in `intermediate_steps`
**And** the response MUST NOT contain `"No puedo"`
**And** MUST contain at least one of: `"persona"`, `"profesional"`, `"atender"` (case-insensitive)

---

## 3. Acceptance Criteria

### AC-1 — Sandbox Tenant

- [ ] `scripts/seed_sandbox_tenant.py` exists, is executable, and creates the sandbox tenant idempotently.
- [ ] Sandbox tenant row has `config.sandbox = true` in production.
- [ ] `SANDBOX_TENANT_ID` is documented in `.env.production.example`.

### AC-2 — Outbound Suppression

- [ ] `response_sender.py:send_sequence()` has the sandbox guard as described in R4.
- [ ] `whatsapp_service/main.py` has the equivalent guard.
- [ ] Unit test `tests/test_sandbox_suppression.py` covers: (a) sandbox tenant → no YCloud call + `[SANDBOX]` log line; (b) normal tenant → YCloud call proceeds normally.

### AC-3 — Golden Files

- [ ] Four golden files exist: `tests/golden/whatsapp.json`, `tests/golden/instagram.json`, `tests/golden/facebook.json`, `tests/golden/telegram.json`.
- [ ] Each file contains at minimum 5 scenarios covering the categories in R2.
- [ ] `tests/test_golden_files.py` is parameterized and runs all scenarios without external API calls.
- [ ] All golden file tests pass on `main` at the time of merge.

### AC-4 — Smoke Test Script

- [ ] `scripts/smoke_test.py` exists and is documented in the project README (or `CLAUDE.md`).
- [ ] The script implements all 7 checks (S1–S7) as specified in R3.
- [ ] The script exits `0` on a healthy stack and `1` on any failure.
- [ ] The script makes NO writes to the database.

### AC-5 — CI Gate for Golden Files

- [ ] `.github/workflows/ci.yml` contains a `golden-file-freshness` job that runs `pytest tests/test_golden_files.py`.
- [ ] The job is listed as a required status check on the `main` branch (documented in this spec; branch protection must be configured manually in GitHub).
- [ ] The job runs on `pull_request` events targeting `main`.

### AC-6 — Baseline Update Script

- [ ] `scripts/update_golden_baselines.py` exists.
- [ ] The script runs the agent against all golden file inputs (fully mocked), captures the real output, and overwrites the `expected_output` section with the new observed values.
- [ ] The script prints a diff summary per scenario so the developer can review changes before committing.
- [ ] The script MUST NOT push or commit changes automatically — the developer must review and commit manually.

---

## 4. Out of Scope

The following items are explicitly excluded from this change:

- **Full staging environment** — A separate staging deployment (separate DB, Redis, and service instances) is architecturally the correct long-term solution. It is NOT in scope here due to infrastructure cost and setup time. This spec addresses the gap with a sandbox tenant + suppression layer as a pragmatic intermediate step. A staging environment proposal should be filed as a separate ticket.
- **Load / performance testing** — Benchmarking the agent under concurrent load, measuring p95 latency, or stress-testing database connection pools.
- **End-to-end browser tests (Playwright/Cypress)** — Frontend UI regression testing is not part of this change.
- **Real YCloud sandbox numbers** — Using a real WhatsApp Business API test number or Meta Sandbox account. The suppression layer in `response_sender.py` provides the required safety without needing YCloud account configuration changes.
- **Automatic golden file update on merge** — Golden files are updated manually by the developer as part of the PR. Automated baseline drift correction (bots that auto-update and auto-commit golden files) is not in scope and would defeat the purpose of the gate.
- **Nova (voice assistant) golden files** — Nova uses OpenAI Realtime API with a different invocation path. Its regression coverage is a separate concern.
- **Multi-tenant isolation tests** — Verifying that one tenant cannot read another tenant's data is an existing concern covered by the Sovereignty Protocol, not by this change.
