# SDD Proposal: prompt-behavioral-fixes-v2

**Change name**: `prompt-behavioral-fixes-v2`
**Tickets**: DLD-39, DLD-40, DLD-41, DLD-43, DLD-44
**Priority**: High (production issues found during live doctor testing)
**Date**: 2026-04-25

---

## 1. Intent

Five behavioral defects in the patient-facing AI agent (TORA) were found during **real production testing with the doctor**. These are NOT theoretical -- patients are seeing raw internal tags, hardcoded emergency numbers, overly complex greetings, internal surgery classification names, and missing evaluation-first guidance for surgical consultations.

These issues directly damage patient trust and clinical safety. They must be fixed before the next showcase round (DLD-22 critical priority).

### Why now?

- The prior SDD change `ai-agent-behavioral-correction` (engram #546, #548, #549) addressed template variables, emotional flows, and prohibitions at a structural level, but **did not fix these 5 specific production issues** because they were discovered later during live testing.
- Some overlap exists (e.g., `patient_display_name` was planned in the prior change's Phase 1 migration 022), but the prior change's Phase 1-2 code fixes were never fully applied to production. This proposal takes a surgical, ticket-driven approach instead of the broader 30-task plan.

---

## 2. Scope

### In scope

| Ticket | Summary | Type |
|--------|---------|------|
| DLD-43 | `[CONSULTA_PREVIA_REQUISITOS:...]` raw tag shown to patient | Tool response + post-processing |
| DLD-40 | Agent mentions emergency number 107 | Tool response + prompt |
| DLD-39 | Welcome message too complex (double questions) | Prompt (greeting template) |
| DLD-44 | Agent classifies surgery type ("Cirugia Compleja") to patient | Tool response + data fix |
| DLD-41 | Agent doesn't explain surgery needs prior evaluation | Data fix + prompt |

### Files touched

| File | Changes |
|------|---------|
| `orchestrator_service/main.py` | Tool responses (`check_availability`, `triage_urgency`, `list_services`), greeting template in `build_system_prompt()`, new prompt prohibition |
| `orchestrator_service/services/buffer_task.py` | Post-processing safety net for bracket tags |
| SQL (data fix, NOT migration) | `UPDATE treatment_types` for surgery `is_high_ticket` and `consultation_requirements` |

### Out of scope

- Booking flow fixes (DLD-42, DLD-45) -- separate change
- Multi-agent engine changes -- solo engine only
- New Alembic migrations -- all fixes use existing columns
- Frontend changes -- all fixes are backend/prompt only
- Full re-implementation of the 30-task behavioral correction plan

---

## 3. Approach

Fixes are grouped by type for clean implementation order.

### Group A: Tool Response Changes (DLD-43, DLD-40, DLD-44)

#### A1. DLD-43 -- Remove bracket tag from `check_availability` response

**Root cause**: `check_availability` (main.py ~lines 2557-2561) appends `[CONSULTA_PREVIA_REQUISITOS:{text}]` as a raw bracket tag. The LLM sometimes passes this verbatim to the patient.

**Fix strategy** (two-pronged):

1. **Rewrite the tag as natural language instruction** in the tool response. Instead of:
   ```
   [CONSULTA_PREVIA_REQUISITOS:Se requiere evaluacion previa]
   ```
   Return:
   ```
   NOTA IMPORTANTE PARA EL AGENTE (NO mostrar al paciente): Este tratamiento requiere evaluacion presencial previa antes de agendar. Explicale al paciente que primero necesita una consulta de evaluacion.
   ```
   This reads as an instruction to the LLM, not as data to forward.

2. **Post-processing safety net** in `buffer_task.py`: strip any remaining `[CONSULTA_PREVIA_REQUISITOS:...]` patterns from final outbound messages (same pattern as existing `INTERNAL_SEDE` stripping).

#### A2. DLD-40 -- Remove hardcoded 107 from `triage_urgency`

**Root cause**: `triage_urgency` tool (main.py ~lines 4493-4499) returns a hardcoded string containing "llama al 107" in the emergency response path.

**Fix strategy**:

1. **Remove the hardcoded number**. Replace with generic language: "contacta a emergencias medicas de tu zona" or "llama a emergencias".
2. **Add prompt prohibition** in the PROHIBICIONES block of `build_system_prompt()`:
   ```
   - NUNCA menciones numeros de emergencia especificos (107, 911, etc.). Decile al paciente que contacte a emergencias medicas de su zona.
   ```
   This covers both the tool response AND any LLM hallucination of emergency numbers.

#### A3. DLD-44 -- Hide internal treatment classification from patient

**Root cause**: `list_services` tool returns `treatment_types.name` which includes internal classifications like "Cirugia Simple" and "Cirugia Compleja". The LLM shows these to the patient.

**Fix strategy**:

1. **Use `patient_display_name` column** (already exists on `treatment_types` table). Modify `list_services` to return `patient_display_name` when not null, falling back to `name`.
2. **SQL data fix**: Set `patient_display_name` for surgery types:
   ```sql
   UPDATE treatment_types
   SET patient_display_name = 'Consulta de Cirugia'
   WHERE name ILIKE '%cirug%';
   ```
   (Exact values to be confirmed with the doctor.)
3. **Add prompt prohibition**:
   ```
   - NUNCA muestres clasificaciones internas de tratamientos (Simple/Compleja, Tipo I/II, etc.) al paciente. Usa siempre el nombre amigable del servicio.
   ```

### Group B: Prompt Changes (DLD-39)

#### B1. DLD-39 -- Simplify greeting template

**Root cause**: `build_system_prompt()` (main.py ~lines 8915-8933) constructs a greeting that combines `specialty_pitch` (from DB `system_prompt_template`) with an appended "En que te puedo ayudar?". If the `specialty_pitch` already contains a question, the patient sees a double-question greeting.

**Fix strategy**:

1. **Rewrite the greeting rule** to be simple and non-compound. The new greeting template for `new_lead`:
   ```
   Hola! Soy {bot_name}, asistente virtual de {clinic_name}. En que te puedo ayudar?
   ```
   Drop the `specialty_pitch` from the greeting entirely. The specialty pitch should be used AFTER the patient states their interest (positioning phase), not in the opening message.

2. **Simplify all 3 greeting variants** (new_lead, patient_no_appointment, patient_with_appointment) to one warm question each -- no stacking.

3. **Relocate specialty_pitch usage**: If `specialty_pitch` exists, inject it into the positioning/implant flow section instead of the greeting. This preserves the doctor's configured text but moves it to the right moment in the conversation.

### Group C: Data Fixes (DLD-41, DLD-44)

#### C1. DLD-41 -- Mark surgery types as high-ticket

**Root cause**: Surgery treatment types in DB do NOT have `is_high_ticket=true`. When false, `check_availability` skips the evaluation-first messaging.

**Fix strategy**:

1. **SQL update** (run via admin or startup script, NOT Alembic migration):
   ```sql
   UPDATE treatment_types
   SET is_high_ticket = true,
       consultation_requirements = 'Requiere evaluacion presencial previa. El profesional debe examinar al paciente antes de planificar cualquier cirugia.'
   WHERE name ILIKE '%cirug%'
     AND (is_high_ticket IS NULL OR is_high_ticket = false);
   ```

2. **Add prompt reinforcement**:
   ```
   - Para CUALQUIER mencion de cirugia, SIEMPRE explicar que requiere evaluacion presencial primero, sin excepcion.
   ```

#### C2. DLD-44 -- Set patient_display_name for surgery types

(Covered in A3 above -- combined SQL update.)

### Group D: Post-Processing Safety Net (DLD-43)

#### D1. Strip bracket tags in buffer_task.py

**Root cause**: Even if the LLM is instructed not to forward bracket tags, it sometimes does. A safety net in `buffer_task.py` is needed.

**Fix strategy**:

1. **Add regex strip** in the message post-processing section of `buffer_task.py` (where `INTERNAL_SEDE` and similar tags are already stripped):
   ```python
   # Strip any remaining internal bracket tags
   import re
   message = re.sub(r'\[CONSULTA_PREVIA_REQUISITOS:[^\]]*\]', '', message)
   message = re.sub(r'\[INTERNAL_[A-Z_]*:[^\]]*\]', '', message)  # Generic catch-all
   ```

2. This is a **defense-in-depth** measure. The primary fix (A1) should prevent most leakage, but this catches edge cases.

---

## 4. Implementation Order

```
Phase 1: Data fixes (C1, C2)     -- SQL only, no code changes
Phase 2: Tool responses (A1-A3)  -- main.py tool function changes
Phase 3: Post-processing (D1)    -- buffer_task.py safety net
Phase 4: Prompt changes (B1)     -- build_system_prompt() greeting rewrite
Phase 5: Verification            -- manual test of all 5 scenarios
```

Each phase is independently deployable. Phases 2+3 fix the most user-visible issues (raw tags, 107 number). Phase 4 (greeting) is cosmetic but important for first impression.

---

## 5. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Greeting change breaks showcase flow (DLD-22) | HIGH | Test the exact showcase scenario after greeting rewrite. The simpler greeting should actually improve it. |
| `patient_display_name` fallback breaks services listing | MEDIUM | `list_services` uses `COALESCE(patient_display_name, name)` -- null-safe. Only surgery types get the override. |
| Post-processing regex strips legitimate patient text | LOW | The regex pattern `[CONSULTA_PREVIA_REQUISITOS:...]` is extremely specific. Generic catch-all only targets `[INTERNAL_*:...]` patterns which are never patient-generated. |
| Removing 107 from triage leaves no emergency guidance | LOW | Replaced with "contacta emergencias de tu zona" -- still provides direction without liability of wrong number. |
| SQL update hits wrong treatment types | MEDIUM | Use `WHERE name ILIKE '%cirug%'` which is specific. Verify with `SELECT` first. Scoped per tenant_id if needed. |
| Specialty pitch removal from greeting loses doctor's configured messaging | LOW | Pitch is relocated to positioning phase, not deleted. Doctor's text still appears, just at a better moment in the conversation. |

### Regression guard for DLD-22 (showcase flow)

The booking/showcase flow goes: greeting -> patient states interest -> agent lists services -> agent checks availability -> books. Changes touch steps 1 (greeting), 3 (list_services display names), and 4 (check_availability tag format). After implementation, the FULL booking flow must be tested end-to-end with a real WhatsApp message to confirm no regression.

---

## 6. Out of Scope

- **DLD-42 / DLD-45**: Booking flow bugs (double-booking, slot selection issues) -- separate change
- **Full 30-task behavioral correction plan**: The prior `ai-agent-behavioral-correction` SDD planned emotional flows F1-F8, escalation rules, etc. Those were partially applied (Phase 3 prompt refactor). This change does NOT revisit that broader scope -- it fixes 5 specific production bugs.
- **Multi-agent engine**: All fixes target SoloEngine (TORA). MultiAgentEngine inherits prompt changes automatically via shared `build_system_prompt()`.
- **New Alembic migrations**: `patient_display_name` column already exists. `is_high_ticket` already exists. Only SQL data updates needed.
- **Frontend changes**: All fixes are backend prompt/tool/data -- no UI changes.

---

## 7. Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| `patient_display_name` column on `treatment_types` | EXISTS | Added by prior behavioral correction Phase 1 or baseline migration |
| `is_high_ticket` column on `treatment_types` | EXISTS | Part of priority_fields migration (011) |
| `consultation_requirements` column on `treatment_types` | EXISTS | Part of priority_fields migration (011) |
| Prior behavioral correction Phase 3 (prompt refactor) | APPLIED | Engram #549 confirms all 9 tasks done. PROHIBICIONES block exists. |
| `INTERNAL_SEDE` stripping pattern in buffer_task.py | EXISTS | We extend the same pattern for new tags |

---

## 8. Estimated Impact

| Metric | Estimate |
|--------|----------|
| Files modified | 3 (`main.py`, `buffer_task.py`, SQL script) |
| Lines changed in `main.py` | ~40-60 (tool responses + prompt prohibitions + greeting) |
| Lines changed in `buffer_task.py` | ~5-10 (regex safety net) |
| SQL statements | 2 UPDATEs (surgery is_high_ticket + patient_display_name) |
| Prompt size delta | ~+3 lines (2 new prohibitions, greeting simplified saves ~5 lines, net small increase) |
| New files | 0 |
| New migrations | 0 |
| Risk to existing functionality | Low (all changes are additive or cosmetic) |

---

## 9. Success Criteria

After implementation, these 5 scenarios must pass:

1. **DLD-43**: Patient asks about a treatment with consultation requirements. Agent explains the requirement in natural language. NO bracket tags visible in any message.
2. **DLD-40**: Patient describes severe emergency symptoms. Agent recommends seeking emergency care WITHOUT mentioning "107" or any specific phone number.
3. **DLD-39**: New patient sends first message. Receives ONE simple greeting with ONE question. No compound multi-question message.
4. **DLD-44**: Patient asks about surgery. Agent refers to it as "Consulta de Cirugia" or similar patient-friendly name. NEVER shows "Cirugia Simple" or "Cirugia Compleja".
5. **DLD-41**: Patient mentions surgery. Agent ALWAYS explains that surgical procedures require a prior in-person evaluation before scheduling.
