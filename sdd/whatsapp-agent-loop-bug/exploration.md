## Exploration: WhatsApp Agent Payment Verification Loop Bug

### Current State
The system processes incoming WhatsApp messages via `buffer_task.py`. When a patient has a pending payment (appointment with status scheduled/confirmed and payment_status pending/partial), any image they send triggers injection of "PROBABLE COMPROBANTE DE PAGO" context (lines 662‑688). This context forces the agent to call `verify_payment_receipt`. 

Simultaneously, visual context from OpenAI Vision is appended to the user input (line 541). If the image is a medical document, the visual description may conflict with the payment verification instruction, causing the agent to oscillate between attempting verification and acknowledging the medical file.

The `verify_payment_receipt` tool performs holder and amount matching. If verification fails (holder mismatch or amount mismatch), it returns an error message. The agent’s response is stored as an assistant message. 

The loop appears because:
1. The same image may be re‑processed (pending payment still exists, `has_recent_media` remains true).
2. The assistant’s response might be incorrectly enqueued again by `enqueue_buffer_and_schedule_task` (which buffers the latest chat message regardless of role).
3. No cooldown or deduplication mechanism exists to prevent repeated verification attempts on the same image.

### Affected Areas
- `orchestrator_service/services/buffer_task.py` — payment detection logic (lines 662‑688), visual context injection (line 541), dead‑end detection (lines 796‑829).
- `orchestrator_service/main.py` — `verify_payment_receipt` tool (line 4108), failure responses.
- `orchestrator_service/services/relay.py` — `enqueue_buffer_and_schedule_task` (line 31) buffers latest chat message without role filtering.
- `orchestrator_service/services/buffer_manager.py` — loop that checks for new messages after processing.

### Approaches
1. **Smart Classification (Vision Keywords)** — Use the existing vision description to decide if the image is likely a payment receipt before injecting payment context.
   - Pros: Reduces false positives, eliminates loop for medical images, uses existing data (no extra API calls).
   - Cons: Description may be ambiguous; keyword list needs maintenance; false negatives could miss real receipts.
   - Effort: Low

2. **Redis Cooldown** — After a failed verification, set a Redis key with TTL (10 minutes) to block further verification attempts for the same (tenant, phone).
   - Pros: Simple, already spec’d, prevents loop, isolates per tenant.
   - Cons: Still allows one false‑positive attempt; patient may receive confusing error message.
   - Effort: Low

3. **Flag‑based (Redis)** — Mark conversation as “payment verification attempted” and skip future attempts for the same image/conversation.
   - Pros: Precise, no extra attempts.
   - Cons: Requires storing image hash or message ID; more complex.
   - Effort: Medium

4. **Response Filtering** — Ensure `enqueue_buffer_and_schedule_task` only buffers user messages (role = ‘user’).
   - Pros: Fixes possible re‑enqueue bug, low risk.
   - Cons: May not be the primary loop cause.
   - Effort: Low

5. **Context Prioritization** — If visual context clearly indicates medical document (keywords), suppress payment context injection.
   - Pros: Similar to classification but uses same context already present.
   - Cons: May still conflict with payment context if description is generic.
   - Effort: Low

6. **Hybrid (Classification + Cooldown + Role Filter)** — Combine the most robust elements:
   - Use vision keywords to suppress payment context when image is clearly non‑payment.
   - Add Redis cooldown for failed attempts (safety net).
   - Add role filter to prevent assistant‑message re‑enqueue.
   - Pros: Addresses multiple root causes, reduces false positives, prevents loop.
   - Cons: Slightly higher complexity.
   - Effort: Medium

### Recommendation
Implement the **Hybrid approach** with the following steps:

1. **Role Filter** (quick win): Modify `enqueue_buffer_and_schedule_task` to buffer only user messages (`role = 'user'`). This eliminates any chance of assistant responses re‑triggering processing.

2. **Vision Keyword Classification**: In `buffer_task.py`, before injecting payment context, check the vision description for medical keywords (e.g., “radiografía”, “historial”, “receta”, “odontograma”, “diente”, “pieza”). If any medical keyword is present, skip the payment context injection and treat the image as a regular medical document. Also check for payment keywords (“transferencia”, “comprobante”, “pago”, “CBU”, “alias”, “titular”, “banco”, “depósito”). If payment keywords are present, keep the payment context. If neither set matches (or description missing), default to pending‑payment logic (inject payment context) because the patient expects receipt verification.

3. **Redis Cooldown**: Implement the already‑specified cooldown mechanism (`payment_verify_cooldown:{tenant_id}:{phone}`) with a 10‑minute TTL. Set the cooldown after any failed verification (holder mismatch, amount mismatch, or generic failure). When cooldown is active, suppress payment context injection entirely and respond with a generic acknowledgment.

This combination:
- Prevents loops for medical images (classification).
- Limits repeated verification attempts (cooldown).
- Fixes any re‑enqueue bug (role filter).
- Maintains backward compatibility: patients with pending payments who send actual receipts will still get verification (payment keywords or default).
- Isolates per tenant and phone.

### Risks
- **False negatives**: Real payment receipts without clear keywords may be missed. Mitigation: default behavior (inject payment context) when description ambiguous.
- **Keyword maintenance**: Medical/payment terminology may evolve. Mitigation: use a configurable list in the code (easy to update).
- **Redis availability**: If Redis is down, cooldown fails open (no protection). Mitigation: graceful fallback (skip cooldown, log warning).
- **Performance impact**: Extra keyword scanning is negligible.

### Ready for Proposal
**Yes**. The exploration confirms the root cause and proposes a concrete hybrid solution. The next step is to create a revised spec that incorporates classification and role filter alongside the existing cooldown requirement. The implementation can be phased:
- Phase 1: Role filter + cooldown (already spec’d tasks).
- Phase 2: Vision keyword classification (new tasks).

The orchestrator should present this analysis to the user and decide whether to proceed with the hybrid spec or stick with cooldown‑only.