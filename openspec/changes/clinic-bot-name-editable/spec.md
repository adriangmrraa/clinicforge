# SDD Spec: Clinic Bot Name Editable

**Change**: `clinic-bot-name-editable`
**Status**: DRAFT
**Date**: 2026-04-07

---

## RFC Keywords

The key words MUST, MUST NOT, SHOULD, MAY follow RFC 2119.

---

## Requirements

### REQ-1: Database Column

The `tenants` table MUST gain a `bot_name` column with the following constraints:
- Type: `VARCHAR(50)`
- Nullable: yes (NULL = use default "TORA")
- No server-side default value (NULL is the default)
- Existing rows remain NULL after migration

### REQ-2: Pydantic Validation

Any Pydantic schema that accepts tenant input MUST validate `bot_name` as follows:
- Type: `Optional[str]`, default `None`
- Max length: 50 characters
- Pattern: `^[A-Za-z0-9 _-]+$` (alphanumeric, space, underscore, hyphen only)
- Empty string `""` MUST be coerced to `None` before persisting

### REQ-3: Endpoint Persistence

`PUT /admin/tenants/{tenant_id}` MUST:
- Accept `bot_name` in the request body
- Normalize empty string to `None`
- Persist the value to the DB
- Return the updated value in subsequent `GET /admin/tenants` responses

### REQ-4: Runtime Fallback in buffer_task.py

`buffer_task.py` line 890 MUST replace the hardcoded `bot_name="TORA"` with:

```python
bot_name=tenant_row.get("bot_name") or "TORA",
```

Where `tenant_row` is the tenant record already in scope at that call site. The fallback MUST be `"TORA"` when the value is `None` or empty string.

### REQ-5: Behavioral Scenarios (Gherkin)

```gherkin
Feature: Configurable bot name per tenant

  Scenario: Tenant sets a custom bot name
    Given a tenant with bot_name = "Nova"
    When the AI agent builds the system prompt for that tenant
    Then the prompt MUST contain "Nova" wherever {bot_name} is resolved
    And the first patient greeting MUST use "Nova"

  Scenario: Tenant has no bot_name set (NULL)
    Given a tenant with bot_name = NULL
    When the AI agent builds the system prompt for that tenant
    Then the prompt MUST contain "TORA" wherever {bot_name} is resolved

  Scenario: Invalid bot_name is rejected
    Given a tenant admin sends PUT /admin/tenants/1 with bot_name = "N@va!!"
    Then the API MUST return HTTP 422
    And the error MUST indicate invalid pattern
```

### REQ-6: Internationalization

The following i18n keys MUST be present in `es.json`, `en.json`, and `fr.json` under the `clinics.fields` namespace:

| Key | Purpose |
|-----|---------|
| `clinics.fields.bot_name_label` | Field label in the form |
| `clinics.fields.bot_name_placeholder` | Placeholder text shown in the empty input |
| `clinics.fields.bot_name_helper` | Helper text below the input |

### REQ-7: Tenant Isolation

The `bot_name` field MUST be scoped to a single tenant. `PUT /admin/tenants/{tenant_id}` already verifies the caller's `tenant_id` via `verify_admin_token`. No additional isolation logic is required — the existing pattern is sufficient.

---

## Out of Scope

- Read-only display of `bot_name` in the patient-facing UI
- Validation of uniqueness across tenants (two clinics can use the same name)
- Migration of the hardcoded `"TORA"` string in `main.py:6450` default parameter — that default remains as the last-resort fallback in `build_system_prompt()`
