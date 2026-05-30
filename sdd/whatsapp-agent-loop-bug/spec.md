# WhatsApp Agent Payment Verification Loop Bug — Specification

## Purpose

This spec prevents the WhatsApp agent from entering an infinite loop when a patient sends an image that the system incorrectly identifies as a payment receipt. The bug occurs when `buffer_task.py` detects pending payment, injects "PROBABLE COMPROBANTE DE PAGO" context, the agent attempts verification which fails, and the cycle repeats every few seconds.

## Requirements

### Requirement: Payment Verification Cooldown

The system **MUST** implement a Redis-based cooldown mechanism to prevent re-triggering payment verification for the same phone number within a 10-minute window after a failed verification attempt.

#### Scenario: Image Received with Pending Payment — Cooldown Prevents Re-trigger

- GIVEN a patient has a pending payment record for their tenant
- WHEN the patient sends an image message to the WhatsApp channel
- AND the system detects "PROBABLE COMPROBANTE DE PAGO" context
- AND no active cooldown flag exists in Redis for that phone number
- THEN the agent calls `verify_payment_receipt`
- AND if verification fails, the system **MUST** set a Redis key `payment_verify_cooldown:{phone}` with TTL of 600 seconds
- AND subsequent image messages within 10 minutes **MUST NOT** trigger another verification attempt
- AND the agent **SHALL** respond with a generic acknowledgment instead of re-attempting verification

#### Scenario: Image Received with Pending Payment — After Cooldown Expires

- GIVEN a patient has a pending payment record for their tenant
- WHEN the patient sends an image message after the 10-minute cooldown has expired
- THEN the system **SHALL** treat this as a fresh verification attempt
- AND the cooldown flag **MUST** be cleared or ignored

#### Scenario: Image Received without Pending Payment

- GIVEN a patient has NO pending payment record for their tenant
- WHEN the patient sends an image message
- THEN the system **MUST NOT** attempt payment verification
- AND no cooldown flag **SHALL** be set
- AND the image **SHALL** be processed as a regular media attachment

#### Scenario: Multiple Images within Cooldown Window

- GIVEN a patient sent an image that failed payment verification
- AND the cooldown flag is active in Redis
- WHEN the patient sends additional images within the 10-minute window
- THEN each subsequent image **MUST NOT** trigger `verify_payment_receipt`
- AND the agent **SHALL** respond with a message that does not reference payment verification

### Requirement: Cooldown Key Structure

The Redis cooldown key **MUST** follow the pattern `payment_verify_cooldown:{tenant_id}:{phone_number}` to ensure isolation between clinics.

#### Scenario: Cooldown Isolation between Tenants

- GIVEN Tenant A has a patient with phone `+1234567890`
- AND Tenant B has a different patient with the same phone `+1234567890`
- WHEN either patient sends an image that triggers verification
- THEN the cooldown **MUST** be specific to each tenant
- AND Tenant A's cooldown **SHALL NOT** affect Tenant B's verification attempts

### Requirement: Cooldown Implementation Details

- The cooldown TTL **MUST** be configurable with a default of 600 seconds (10 minutes)
- The Redis key **MUST** use the `EXPIRE` command to set TTL atomically
- The system **SHOULD** log when a verification is blocked by cooldown for observability

## Out of Scope

- Modifying the verification logic itself (the bug is in re-triggering, not verification accuracy)
- UI changes to inform patients about the cooldown
- Automatic retry logic after cooldown expiry (manual retry by patient is expected)

## Acceptance Criteria

1. After a failed payment verification, subsequent image messages within 10 minutes do NOT trigger another verification
2. Cooldown is isolated per tenant and phone number
3. No cooldown is set when there is no pending payment
4. System logs when verification is blocked by cooldown
5. After cooldown expires, normal verification behavior resumes
