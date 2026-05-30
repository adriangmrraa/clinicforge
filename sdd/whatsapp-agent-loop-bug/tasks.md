# Tasks: WhatsApp Agent Payment Verification Loop Bug

## Phase 1: Infrastructure (Redis Key Setup & Helper Functions)

- [ ] 1.1 Create Redis helper module `orchestrator_service/services/payment_cooldown.py` with functions:
  - `is_cooldown_active(redis_client, tenant_id, phone)` - returns True if cooldown key exists
  - `set_cooldown(redis_client, tenant_id, phone, ttl_seconds=600)` - sets key with TTL
  - Helper to construct key: `payment_verify_cooldown:{tenant_id}:{phone}`
- [ ] 1.2 Add Redis client initialization in `buffer_task.py` import section (reuse existing Redis connection from orchestrator_service)
- [ ] 1.3 Add logging import for cooldown events in `buffer_task.py`

## Phase 2: Implementation (Integrate Cooldown in buffer_task.py)

- [ ] 2.1 Add cooldown check BEFORE injecting "PROBABLE COMPROBANTE DE PAGO" context:
  - Import `is_cooldown_active` from payment_cooldown
  - Check: if `has_pending_payment` AND NOT `is_cooldown_active(tenant_id, phone)`
  - Only then inject payment verification context
- [ ] 2.2 After failed payment verification, call `set_cooldown()`:
  - Need to detect verification failure - likely via tool result or agent response pattern
  - Alternative: add check at start of processing - if cooldown active, skip verification entirely
- [ ] 2.3 Add logging when verification is blocked by cooldown (observability requirement)
- [ ] 2.4 Update `media_context` when cooldown active - respond with generic acknowledgment instead of verification prompt

## Phase 3: Testing (Manual Test Scenarios)

- [ ] 3.1 Test Scenario A: Image sent with pending payment, no prior verification attempt
  - Expected: Payment verification triggered normally
- [ ] 3.2 Test Scenario B: Image sent within 10 minutes after failed verification
  - Expected: Generic acknowledgment, no re-verification attempt
  - Check logs for "verification blocked by cooldown"
- [ ] 3.3 Test Scenario C: Image sent after cooldown expires (10+ minutes)
  - Expected: Normal verification behavior resumes
- [ ] 3.4 Test Scenario D: Different tenant with same phone - verify isolation
  - Expected: Cooldown from Tenant A does not affect Tenant B
- [ ] 3.5 Test Scenario E: Multiple images sent within cooldown window
  - Expected: All receive generic acknowledgment, no verification attempts

## Phase 4: Configuration & Polish

- [ ] 4.1 Make cooldown TTL configurable via environment variable (e.g., `PAYMENT_COOLDOWN_SECONDS`)
- [ ] 4.2 Add Redis connection error handling - graceful fallback if Redis unavailable