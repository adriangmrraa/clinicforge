# Nova Daily Analysis 400 Error Fix — Specification

## Purpose

Ensure Nova daily analysis runs successfully without HTTP 400 errors by validating model compatibility with JSON mode, providing fallback to a safe default, and logging detailed diagnostics for debugging.

## Requirements

### Requirement: Model Validation Before API Call

The system **MUST** validate the configured `MODEL_INSIGHTS` value against a known list of OpenAI models that support JSON mode before making the GPT API call. If the model is not recognized or does not support JSON mode, the system **SHALL** fall back to `gpt-4o-mini`.

#### Scenario: Valid Model Configured

- GIVEN `MODEL_INSIGHTS` is set to `gpt-4o-mini`
- WHEN the daily analysis job calls `_analyze_with_gpt`
- THEN the system **SHALL** use the configured model
- AND the API request **MUST** include `response_format: {"type": "json_object"}`

#### Scenario: Unrecognized Model Configured

- GIVEN `MODEL_INSIGHTS` is set to `gpt-5.4-mini`
- AND `gpt-5.4-mini` is not in the validated list of JSON‑mode‑compatible models
- WHEN the daily analysis job calls `_analyze_with_gpt`
- THEN the system **SHALL** log a warning with the invalid model name
- AND the system **MUST** fall back to `gpt-4o-mini`
- AND the API request **SHALL** be made with the fallback model

#### Scenario: Model Validation Uses Token Tracker Pricing List

- GIVEN the token tracker defines `MODEL_PRICING` with supported models
- WHEN validating the `MODEL_INSIGHTS` value
- THEN the validation **SHALL** use the keys of `MODEL_PRICING` as the list of known models
- AND any model not present in `MODEL_PRICING` **MUST** be treated as unrecognized

### Requirement: JSON Mode Compatibility Check

The system **MUST** ensure that the selected model supports JSON mode. If the model does not support JSON mode, the system **SHALL** either omit the `response_format` parameter or fall back to a model that does support it.

#### Scenario: Model Supports JSON Mode

- GIVEN the selected model is `gpt-4o-mini`
- AND `gpt-4o-mini` supports JSON mode
- WHEN constructing the OpenAI API request
- THEN the request **MUST** include `"response_format": {"type": "json_object"}`

#### Scenario: Model Does Not Support JSON Mode

- GIVEN the selected model is `gpt-5.4-mini` (hypothetical unsupported)
- AND validation detects that JSON mode is not supported
- WHEN constructing the OpenAI API request
- THEN the request **SHALL** omit the `response_format` parameter
- OR the system **MAY** fall back to a model that does support JSON mode

### Requirement: Enhanced Error Handling and Diagnostics

When the OpenAI API returns an HTTP 400 error, the system **MUST** log the full HTTP response (including error message and body) to aid debugging. The log **SHALL** include the tenant ID, configured model, and fallback model used.

#### Scenario: API Returns 400 Due to Model Incompatibility

- GIVEN the configured model is `gpt-5.4-mini`
- AND the model does not support JSON mode
- WHEN the OpenAI API returns a 400 error with details
- THEN the system **MUST** capture the entire HTTP response and log it at ERROR level with a distinct tag (e.g., `nova_analysis_gpt_error_detail`)
- AND the system **SHALL** attempt fallback to `gpt-4o-mini` (if not already using it)
- AND the analysis job **SHALL** continue with the fallback model

#### Scenario: API Returns 400 for Other Reasons

- GIVEN a valid model is configured
- WHEN the OpenAI API returns a 400 error unrelated to model compatibility (e.g., malformed prompt)
- THEN the system **MUST** log the full error details
- AND the analysis job **MAY** abort for that tenant (existing behavior)

### Requirement: Manual Test After Fix

After the fix is deployed, a manual test **MUST** be performed to verify that the daily analysis job completes without 400 errors. The test **SHALL** include setting `MODEL_INSIGHTS` to `gpt-5.4-mini` (or another edge‑case model) and verifying that fallback occurs and analysis results are cached in Redis.

#### Scenario: Manual Verification of Fallback

- GIVEN the fix is deployed to the target environment
- WHEN an administrator sets `MODEL_INSIGHTS` to `gpt-5.4-mini` via the dashboard
- AND triggers a manual daily analysis run
- THEN the logs **SHALL** show a warning about model validation and fallback
- AND the Redis key `nova_daily:{tenant_id}` **MUST** be populated with analysis results
- AND the `/admin/nova/daily-analysis` endpoint **SHALL** return `available: true`

## Out of Scope

- Modifying the token‑tracker pricing list (already includes required models)
- Adding UI warnings about model incompatibility (future enhancement)
- Changing the default `MODEL_INSIGHTS` value (remains `gpt-4o-mini`)

## Acceptance Criteria

1. Daily analysis job completes without HTTP 400 errors when `MODEL_INSIGHTS` is set to any value.
2. Unrecognized or JSON‑mode‑incompatible models trigger a fallback to `gpt-4o-mini` with a clear warning log.
3. Full HTTP error details are logged for any 400 response from OpenAI.
4. Manual test with `MODEL_INSIGHTS=gpt-5.4-mini` results in successful analysis and Redis caching.
5. Existing behavior is unchanged for valid models (e.g., `gpt-4o-mini`).