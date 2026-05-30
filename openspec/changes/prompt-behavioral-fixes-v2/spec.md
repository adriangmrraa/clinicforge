# SDD Specs: prompt-behavioral-fixes-v2

**Change**: `prompt-behavioral-fixes-v2`
**Tickets**: DLD-39, DLD-40, DLD-41, DLD-43, DLD-44
**Date**: 2026-04-25
**Status**: SPEC

---

## Ticket DLD-43: Raw bracket tag `[CONSULTA_PREVIA_REQUISITOS:...]` shown to patient

**Problem**: When a treatment has `consultation_requirements` set and `is_high_ticket=true`, the `check_availability` tool appends a raw bracket tag `[CONSULTA_PREVIA_REQUISITOS:{text}]` to its response. The LLM sometimes forwards this verbatim to the patient in the WhatsApp message.

**Root Cause**: `orchestrator_service/main.py:2561` — the line `lines.append(f"[CONSULTA_PREVIA_REQUISITOS:{_consult_reqs}]")` uses a bracket-tag format that the LLM treats as passthrough data rather than an instruction.

**Specification**:

1. **MUST change** (`main.py:2561`): Replace the bracket tag with a natural language instruction directed at the LLM. The new text MUST:
   - Be clearly framed as an instruction TO the agent (not data for the patient)
   - Contain the word "IMPORTANTE" or "INSTRUCCION" to signal it's a directive
   - Include an explicit "NO mostrar al paciente" guard
   - Preserve the actual `consultation_requirements` content from the DB
   - Example format:
     ```
     INSTRUCCION PARA EL AGENTE (NO mostrar al paciente): Este tratamiento requiere evaluacion presencial previa. {_consult_reqs}. Explicale al paciente que primero necesita una consulta de evaluacion antes de programar el procedimiento.
     ```

2. **MUST add** (`buffer_task.py`, in the post-processing section between line ~2419 and ~2426 — after `[LOCAL_IMAGE:]` stripping and before the date validator): A regex safety net that strips any residual bracket tags from the final `response_text`. Two patterns:
   - Specific: `r'\[CONSULTA_PREVIA_REQUISITOS:[^\]]*\]'` → strip to empty string
   - Generic catch-all: `r'\[INTERNAL_[A-Z_]*:[^\]]*\]'` → strip to empty string
   - After stripping, collapse any resulting double newlines or leading/trailing whitespace

3. **MUST NOT change**:
   - The `is_high_ticket` conditional logic (lines 2552-2563) — the branching stays
   - The `[LOCAL_IMAGE:]` tag system (used for multimedia extraction, different pattern)
   - The `[INTERNAL_BOOKING_CONTEXT]` tag in `buffer_task.py:1108` — this is injected into the PROMPT context, not the outbound response, so it's not affected

**Acceptance Criteria**:

- **AC-1**: Given a treatment with `is_high_ticket=true` and `consultation_requirements='Requiere evaluacion presencial previa'`, when `check_availability` is called, then the tool response contains a natural language instruction mentioning the requirement, and does NOT contain any text matching the pattern `[CONSULTA_PREVIA_REQUISITOS:...]`.
- **AC-2**: Given a treatment with `is_high_ticket=true` and `consultation_requirements=NULL`, when `check_availability` is called, then no consultation requirements text is appended at all (no empty tag, no empty instruction).
- **AC-3**: Given that the LLM response somehow contains `[CONSULTA_PREVIA_REQUISITOS:some text]` (edge case), when `buffer_task.py` post-processes the response, then the bracket tag is stripped from the final outbound message.
- **AC-4**: Given that the LLM response contains `[INTERNAL_ANYTHING:some text]`, when `buffer_task.py` post-processes the response, then the bracket tag is stripped from the final outbound message.
- **AC-5**: Given a normal patient message without bracket tags, when `buffer_task.py` post-processes the response, then the response text is unchanged (regex does not match normal text).

**Regression Guards**:
- The `[LOCAL_IMAGE:]` extraction flow MUST still work (different regex pattern, different handling — extracts URLs, does not just strip)
- The `is_high_ticket=true` path MUST still show "evaluacion de {treatment}" instead of plain "{treatment}" in the slot header
- The date validator MUST still run after tag stripping

---

## Ticket DLD-40: Agent mentions emergency number 107

**Problem**: When the triage tool classifies symptoms as "emergency", the response includes "Llama al 107 (emergencias medicas)" — a hardcoded Argentine emergency number that may be wrong depending on the patient's location and creates legal liability.

**Root Cause**: `orchestrator_service/main.py:4498` — the `responses["emergency"]` string literal contains `"Llamá al 107 (emergencias médicas)"` as step 3 of the emergency protocol.

**Specification**:

1. **MUST change** (`main.py:4493-4499`): Rewrite the `responses["emergency"]` string. Specifically, replace the line:
   ```
   "3. Si tenés dificultad para respirar o tragar: Llamá al 107 (emergencias médicas)\n\n"
   ```
   With:
   ```
   "3. Si tenés dificultad para respirar o tragar: Contactá a emergencias médicas de tu zona de inmediato\n\n"
   ```
   The rest of the emergency response structure (points 1, 2, and 4) MUST remain unchanged.

2. **MUST add** to the `PROHIBICIONES` block (`main.py:~9189`): A new prohibition item:
   ```
   X. PROHIBIDO mencionar números de emergencia específicos (107, 911, 112, etc.). Si el paciente necesita emergencias médicas, decile que contacte a emergencias de su zona.
   ```
   Where X is the next number in the PROHIBICIONES sequence (currently 9 items, so this would be 10).

3. **MUST NOT change**:
   - The urgency classification logic in `triage_urgency` (how it determines emergency/high/normal/low)
   - The "high", "normal", and "low" response strings
   - The `derivhumano` handoff trigger for emergencies (separate concern)

**Acceptance Criteria**:

- **AC-1**: Given a patient reports "me rompí la mandíbula en un accidente", when `triage_urgency` classifies it as "emergency", then the response does NOT contain "107", "911", "112", or any specific phone number.
- **AC-2**: Given the emergency response is returned, then it STILL contains guidance to contact emergency medical services (generic phrasing like "emergencias médicas de tu zona").
- **AC-3**: Given the system prompt is built, then the PROHIBICIONES block contains a line prohibiting specific emergency numbers.
- **AC-4**: Given a patient asks about a non-emergency dental issue, when `triage_urgency` classifies it as "normal" or "low", then the response is unchanged from current behavior.

**Regression Guards**:
- The triage persistence logic (saving to `triage_events` table) MUST still work
- The `derivhumano` call for real emergencies MUST still be triggered by the agent (this is LLM behavior guided by existing prompt rules, not affected by the tool response change)
- The "high" urgency response (48-72 hours) MUST remain unchanged

---

## Ticket DLD-39: Welcome message double questions

**Problem**: New patients receive a greeting with multiple stacked questions. The greeting template injects `specialty_pitch` (from DB `system_prompt_template`) which often already contains a question, then appends another question like "En que te puedo ayudar?". This results in a confusing compound greeting that feels robotic.

**Root Cause**: `orchestrator_service/main.py:8914-8952` — the `greeting_rule` construction for all three patient statuses (`new_lead`, `patient_no_appointment`, `patient_with_appointment`) includes `{greeting_specialty}` (line 8932, 8947) which is either the DB-configured `specialty_pitch` or a hardcoded fallback about implants/prosthetics. This pitch text often contains its own question or call-to-action, creating a double-question greeting.

**Specification**:

1. **MUST change** (`main.py:8915-8919`): Remove `specialty_pitch` from the greeting construction entirely. The `greeting_specialty` variable assignment (lines 8915-8919) MUST be deleted or moved to the implant/positioning flow section.

2. **MUST change** (`main.py:8924-8937`): Rewrite the `new_lead` greeting rule. The new greeting for variant A (simple saludo) MUST be:
   ```
   "Hola! Soy {bot_name}, asistente virtual de {clinic_name}. En que te puedo ayudar?"
   ```
   - ONE line, ONE question, no stacked content
   - The variant B (patient already stated their need) remains the same pattern: brief intro + direct response
   - The emoji (if used) is acceptable but the greeting MUST NOT contain more than ONE question mark

3. **MUST change** (`main.py:8939-8952`): Rewrite the `patient_no_appointment` greeting rule. The variant A MUST be:
   ```
   "Hola! Soy {bot_name}, asistente virtual de {clinic_name}. En que te puedo ayudar?"
   ```
   - Same simple format — NO "Necesitas agendar un turno o tenes alguna consulta?" which is a double-question
   - Variant B remains: brief intro + direct response

4. **MUST change** (`main.py:8953-8965`): The `patient_with_appointment` greeting rule. Variant A keeps the personalized appointment mention but MUST NOT stack questions. Format:
   ```
   "Hola! Soy {bot_name}, asistente virtual de {clinic_name}. Vi que tenes turno [detalles]. En que te puedo ayudar?"
   ```
   - ONE closing question only

5. **MUST relocate** the `specialty_pitch` usage: If the tenant has a configured `specialty_pitch` in `system_prompt_template`, inject it into the implant/prosthesis commercial flow section (`implant_flow_section` in `build_system_prompt`) instead of the greeting. The pitch is valuable content — it should appear when the patient expresses interest in implants/prosthetics, NOT as part of the first hello.

6. **MUST NOT change**:
   - The `is_greeting_pending` flag logic (Bug #8 fix — lines 8920-8923)
   - The variant B behavior (brief intro when patient already stated their need)
   - The `patient_with_appointment` personalized appointment mention (just simplify the question count)

**Acceptance Criteria**:

- **AC-1**: Given a new lead sends "Hola" as first message, when the agent responds, then the greeting contains exactly ONE question mark and NO specialty pitch text.
- **AC-2**: Given a new lead sends "Quiero un turno para limpieza", when the agent responds, then it uses variant B (brief intro + addresses the booking request directly) with no specialty pitch.
- **AC-3**: Given a returning patient without appointment sends "Buenos dias", when the agent responds, then the greeting contains ONE question ("En que te puedo ayudar?") and NOT the double-question "Necesitas agendar un turno o tenes alguna consulta?".
- **AC-4**: Given a patient with a future appointment sends "Hola", when the agent responds, then the greeting mentions the appointment AND ends with ONE question.
- **AC-5**: Given a tenant has `specialty_pitch` configured in `system_prompt_template`, when the patient later mentions implants or prosthetics, then the specialty pitch content appears in the agent's positioning response (relocated, not deleted).
- **AC-6**: Given a patient was already greeted in the session (`is_greeting_pending=false`), when they send another message, then NO institutional greeting is repeated (existing Bug #8 guard preserved).

**Regression Guards**:
- The showcase/booking flow (DLD-22) MUST still work: greeting -> interest -> services -> availability -> book
- The `bot_name` and `clinic_name` variables MUST still be injected into greetings
- The `is_greeting_pending` mechanism MUST remain functional
- Variant B (brief intro for patients with explicit intent) MUST still skip the full greeting

---

## Ticket DLD-44: Agent shows internal treatment classification ("Cirugia Compleja") to patient

**Problem**: When a patient asks about surgery, the agent shows internal classification names like "Cirugia Simple" and "Cirugia Compleja" which are medical jargon not meant for patient communication. Patients should see friendly names like "Consulta de Cirugia".

**Root Cause**: Two interrelated issues:
1. `orchestrator_service/main.py:5141` — `list_services` already uses `patient_display_name` with fallback: `display_name = r.get("patient_display_name") or r["name"]`. This is correct code, BUT the `patient_display_name` column is NULL for surgery types in the database, so it falls back to the internal `name`.
2. The DB `treatment_types` table has records with `name` values like "Cirugia Simple" and "Cirugia Compleja" without corresponding `patient_display_name` values set.

**Specification**:

1. **MUST fix** (SQL data update, NOT Alembic migration): Set `patient_display_name` for all surgery-related treatment types:
   ```sql
   UPDATE treatment_types
   SET patient_display_name = 'Consulta de Cirugia'
   WHERE name ILIKE '%cirug%'
     AND (patient_display_name IS NULL OR patient_display_name = '');
   ```
   This SQL MUST be:
   - Documented in the change's apply notes (not a migration file)
   - Idempotent (safe to run multiple times)
   - Scoped with the NULL/empty check so it doesn't overwrite intentionally set values
   - Exact `patient_display_name` value to be confirmed with the doctor before applying

2. **MUST verify** (`main.py:5141`): Confirm that `list_services` already uses `patient_display_name` with fallback. Current code: `display_name = r.get("patient_display_name") or r["name"]`. This is correct — no code change needed here.

3. **MUST verify** (`main.py:2550`): Confirm that `check_availability` uses `treatment_name` which is resolved from the same `patient_display_name` fallback. If it reads directly from `treatment_types.name`, it MUST be updated to use `COALESCE(patient_display_name, name)` in its query.

4. **MUST add** to the `PROHIBICIONES` block (`main.py:~9189`): A new prohibition:
   ```
   X. PROHIBIDO mostrar clasificaciones internas de tratamientos al paciente (Simple/Compleja, Tipo I/II, Grado A/B, etc.). Siempre usa el nombre amigable del servicio.
   ```

5. **MUST NOT change**:
   - The `treatment_types.name` column values (these are internal identifiers used by staff)
   - The `treatment_types.code` column (used for booking)
   - The `list_services` query structure (it already fetches `patient_display_name`)
   - Treatment types that are NOT surgery-related

**Acceptance Criteria**:

- **AC-1**: Given surgery treatment types in the DB, when `list_services` is called, then the output shows "Consulta de Cirugia" (or the confirmed patient-friendly name), NOT "Cirugia Simple" or "Cirugia Compleja".
- **AC-2**: Given a patient asks "quiero hacerme una cirugia", when the agent responds with available services, then NO internal classification names (Simple, Compleja, etc.) appear in the message.
- **AC-3**: Given a treatment type has `patient_display_name` already set to a custom value, when the SQL update runs, then the existing custom value is NOT overwritten.
- **AC-4**: Given a non-surgery treatment type (e.g., "Limpieza Dental"), when `list_services` is called, then it displays normally using `patient_display_name` if set, otherwise `name` (existing fallback behavior unchanged).
- **AC-5**: Given the PROHIBICIONES block is updated, when the agent references any treatment in conversation, then it uses the patient-friendly display name, not internal classifications.

**Regression Guards**:
- The `code` field MUST still be returned by `list_services` (used by `check_availability` and `book_appointment`)
- The synonym mapping (`_SYNONYM_MAP` at line 5046) MUST still match against internal `name` for routing purposes (the mapping is for lookup, not display)
- The professional assignment display (`prof_str`) MUST remain unchanged
- Treatment types without `patient_display_name` set MUST still fall back to `name` gracefully

---

## Ticket DLD-41: No evaluation-first explanation for surgery

**Problem**: When a patient mentions surgery, the agent immediately shows pricing and available slots without explaining that surgical procedures require a prior in-person evaluation. This is clinically inappropriate and commercially damaging (patient sees high price without context).

**Root Cause**: `orchestrator_service/main.py:2552` — the `is_high_ticket` flag on surgery treatment types is `false` (or NULL) in the database. When `is_high_ticket` is falsy, `check_availability` skips the evaluation-first messaging path (lines 2552-2563) and goes straight to showing regular appointment slots with pricing.

**Specification**:

1. **MUST fix** (SQL data update, NOT Alembic migration): Set `is_high_ticket=true` and `consultation_requirements` for all surgery types:
   ```sql
   UPDATE treatment_types
   SET is_high_ticket = true,
       consultation_requirements = 'Requiere evaluacion presencial previa. El profesional debe examinar al paciente antes de planificar cualquier cirugia.'
   WHERE name ILIKE '%cirug%'
     AND (is_high_ticket IS NULL OR is_high_ticket = false);
   ```
   This SQL MUST be:
   - Combined with the DLD-44 SQL update (same WHERE clause, same execution context)
   - Idempotent
   - Not affect treatment types that are already `is_high_ticket=true` with their own custom requirements

2. **MUST verify** that the existing `is_high_ticket=true` code path in `check_availability` (lines 2552-2563) correctly:
   - Shows "evaluacion de {treatment}" instead of just "{treatment}" in the header
   - Appends the consultation requirements (now as natural language per DLD-43 spec)
   - These two behaviors are already coded — they just need the data flag to activate

3. **MUST add** to the system prompt (in `build_system_prompt()`, near the PROHIBICIONES or in a new REGLAS section): A reinforcement rule:
   ```
   REGLA CIRUGIA: Para CUALQUIER mencion de cirugia (extraccion, muela de juicio, implante quirurgico, etc.), SIEMPRE explicar que requiere una evaluacion presencial previa antes de agendar el procedimiento. Nunca ofrecer turno directo para cirugia sin mencionar la evaluacion primero.
   ```

4. **MUST NOT change**:
   - The `is_high_ticket` code path logic in `check_availability` (the branching at lines 2552-2563 is correct)
   - Treatment types that are NOT surgery (e.g., "Limpieza", "Consulta General" should NOT be marked high-ticket)
   - The `consultation_price` display logic (price of the evaluation consultation is fine to show — the issue was showing the surgery price directly)

**Acceptance Criteria**:

- **AC-1**: Given a patient says "Tengo que hacerme una cirugia", when the agent calls `check_availability` for a surgery type, then the slot header says "evaluacion de Consulta de Cirugia" (not just "cirugia"), and the response includes an explanation that prior evaluation is required.
- **AC-2**: Given surgery types in the DB after the SQL update, when querying `treatment_types WHERE name ILIKE '%cirug%'`, then ALL rows have `is_high_ticket=true` and `consultation_requirements` is NOT NULL.
- **AC-3**: Given a patient asks about a non-surgical treatment (e.g., "limpieza"), when `check_availability` is called, then the standard slot display is used (no evaluation-first messaging).
- **AC-4**: Given the system prompt is built, then there is an explicit rule about surgery requiring prior evaluation.
- **AC-5**: Given a treatment type already has `is_high_ticket=true` with custom `consultation_requirements`, when the SQL update runs, then its existing values are NOT overwritten (the WHERE clause filters on `is_high_ticket IS NULL OR is_high_ticket = false`).

**Regression Guards**:
- The booking flow for NON-surgical treatments MUST remain unchanged (no evaluation step injected)
- The implant/prosthesis commercial triage flow (6 emoji showcase) MUST still work — implants are already high-ticket in some setups; this change only ensures surgery types join them
- The `consultation_price` display for evaluations MUST still work correctly
- The `book_appointment` tool MUST still accept bookings for surgery evaluations normally

---

## Cross-Cutting Concerns

### Prompt Size Budget
- **Current**: ~464 lines (estimated from build_system_prompt output)
- **Maximum**: 600 lines (to stay within token limits for gpt-4o-mini context)
- **Delta from this change**:
  - +2 new PROHIBICIONES items (~2 lines)
  - +1 REGLA CIRUGIA (~2 lines)
  - Greeting simplification saves ~10-15 lines (removing specialty_pitch injection from 3 greeting variants)
  - Specialty pitch relocation to implant flow: ~2-3 lines
  - **Net**: approximately -5 to -8 lines (smaller prompt)
- **Action**: After implementation, count the actual prompt line output for a test tenant and verify it stays under 600.

### Booking Flow (DLD-22) MUST NOT Be Affected
The showcase booking flow is: greeting -> patient states interest -> `list_services` -> `check_availability` -> `book_appointment`. Changes touch steps 1 (greeting), 3 (display names), and 4 (evaluation-first for surgery). Specifically:
- Non-surgical bookings: ZERO change to flow. Greeting is simpler, display names may or may not change (only if `patient_display_name` was null), availability response is identical.
- Surgical bookings: Flow now correctly routes through evaluation-first path. This is the DESIRED behavior, not a regression.
- **Mandatory**: After implementation, run a full end-to-end booking test for at least one non-surgical and one surgical treatment.

### Showcase Flow MUST NOT Be Affected
The implant showcase flow (6 emoji options -> profundization -> positioning) is triggered by patient mention of implants/prosthetics. The relocated `specialty_pitch` should enhance this flow, not break it. Verify that:
- The 6 emoji options still appear when a patient mentions implants
- The specialty pitch text appears during positioning, not during greeting

### Backward Compatibility (All 3 Files)
| File | Compatibility Requirement |
|------|--------------------------|
| `main.py` | All existing tools continue to return valid responses. No new parameters added. No function signatures changed. Prompt changes are additive (new prohibitions) or subtractive (simpler greeting). |
| `buffer_task.py` | New regex stripping is additive only. Runs after existing `[LOCAL_IMAGE:]` extraction. Does not interfere with date validator. Normal messages (no bracket tags) pass through unchanged. |
| SQL updates | Idempotent. Only affect rows where `is_high_ticket` is null/false and `patient_display_name` is null/empty. Never overwrites intentionally configured values. |

### Combined SQL Update Script
Both DLD-41 and DLD-44 data fixes target the same rows (`WHERE name ILIKE '%cirug%'`). They SHOULD be combined into a single UPDATE statement:
```sql
UPDATE treatment_types
SET is_high_ticket = true,
    consultation_requirements = 'Requiere evaluacion presencial previa. El profesional debe examinar al paciente antes de planificar cualquier cirugia.',
    patient_display_name = COALESCE(NULLIF(patient_display_name, ''), 'Consulta de Cirugia')
WHERE name ILIKE '%cirug%'
  AND (is_high_ticket IS NULL OR is_high_ticket = false);
```
Note: `COALESCE(NULLIF(patient_display_name, ''), 'Consulta de Cirugia')` ensures we only set the display name if it's currently NULL or empty, without overwriting existing values.

### Implementation Order (from proposal, confirmed)
```
Phase 1: SQL data fixes (DLD-41 + DLD-44 combined)
Phase 2: Tool response changes in main.py (DLD-43, DLD-40, DLD-44 prohibition)
Phase 3: Post-processing safety net in buffer_task.py (DLD-43)
Phase 4: Prompt changes in main.py (DLD-39 greeting, DLD-41 surgery rule)
Phase 5: Manual verification of all 5 scenarios
```

### Tickets Explicitly Out of Scope
- **DLD-42**: Agent offers same slot repeatedly after patient declines — booking flow bug, separate change
- **DLD-45**: Other booking flow issues — separate change
- Multi-agent engine changes — solo engine only (MultiAgent inherits prompt changes via shared `build_system_prompt()`)
