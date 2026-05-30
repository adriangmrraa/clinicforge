# SDD Proposal: AI Agent Behavioral Correction

**Change**: `ai-agent-behavioral-correction`
**Status**: PROPOSED
**Date**: 2026-04-04
**Author**: SDD Orchestrator

---

## 1. Intent

### Problem Statement

The patient-facing AI agent has 8 critical behavioral problems identified by the clinic owner (Dra. Laura Delgado) that damage patient experience and conversion rates. These problems fall into two categories:

**A. Behavioral failures** (prompt-level): The agent lacks emotional intelligence flows for specific high-value scenarios (urgency, fear, bad prior experience, unknown insurance, aesthetic intent, bone loss/rejection cases, multiple tooth loss). It jumps to transactional responses (price + turnos + address) instead of following a containment-first approach.

**B. Multi-tenancy failures** (code-level): 5 hardcoded "Dra. Laura Delgado" references in the prompt, hardcoded specialty pitch in greetings, internal treatment names exposed to patients, insurance copay data ignored, and a dead `system_prompt_template` column that was never wired up.

### Why This Matters

- **Conversion loss**: High-value leads (implants, fear patients, bone-loss cases) are being mishandled or lost to premature human escalation
- **Non-portable agent**: The agent cannot serve any tenant other than Dra. Laura Delgado's clinic without prompt surgery
- **Professional credibility**: Patients see internal codes (e.g., "R.I.S.A.") instead of human-readable treatment names
- **Incomplete data usage**: `copay_notes` data exists in DB but the prompt ignores it; `system_prompt_template` column exists but is dead code

---

## 2. Scope

### In Scope

| Area | Files | What Changes |
|------|-------|-------------|
| System prompt | `orchestrator_service/main.py` (`build_system_prompt()`, ~line 5705) | Restructure prompt: add 8 emotional flows, prohibitions block, tone/variation rules, replace hardcoded content with template variables |
| Greeting templates | `orchestrator_service/main.py` (lines 5873-5904) | Remove hardcoded "La Dra. se especializa en rehabilitacion oral..." — replace with `{doctor_specialty_pitch}` from DB |
| Implant/prosthesis flow | `orchestrator_service/main.py` (lines 6068-6104) | Replace hardcoded "La Dra. Laura Delgado" with `{lead_professional_name}` resolved from tenant config |
| Bad experience flow | `orchestrator_service/main.py` (lines 6128-6147) | Same — replace hardcoded doctor name with template variable |
| DRA. vs EQUIPO section | `orchestrator_service/main.py` (lines 6261-6263) | Replace hardcoded specialties list with data from `treatment_types` + `professionals` tables |
| Triage urgency docstring | `orchestrator_service/main.py` (line 2795) | Remove "Dra. Maria Laura Delgado" from docstring |
| Insurance formatting | `orchestrator_service/main.py` (`_format_insurance_providers()`, line 5600) | Include `copay_notes` for `accepted` providers instead of generic hardcoded text |
| Availability message | `orchestrator_service/main.py` (line 1898) | Change "Hay X turnos mas disponibles" to a softer message or remove |
| Treatment display name | `orchestrator_service/models.py`, Alembic migration, `main.py` (`list_services` tool) | Add `patient_display_name` column to `treatment_types`; use it in patient-facing tool output |
| Tenant prompt template | `orchestrator_service/main.py` (`build_system_prompt()`) | Wire up existing `tenants.system_prompt_template` column as persona override |
| Prompt caller | `orchestrator_service/buffer_task.py` (~line 583) | Pass new fields to `build_system_prompt()` (lead professional, specialty pitch, tenant prompt template) |

### Out of Scope

- **Nova** (internal dashboard assistant) — separate system, separate prompt
- **Frontend UI** — no admin UI for configuring emotional flows (future change)
- **New admin endpoints** — no CRUD for emotional flow configuration
- **WhatsApp service** — no changes to message routing/delivery
- **RAG system** — no changes to embedding/retrieval logic

---

## 3. Approach

### Layer 1: Prompt Refactor (behavioral correction)

#### 1A. New Emotional Flow Blocks

Add 8 structured flow blocks to the prompt, each following the pattern: **detect trigger -> emotional containment -> orient -> convert**. These replace or augment existing partial flows.

| Flow | Trigger Detection | Current State | New Behavior |
|------|-------------------|---------------|-------------|
| **F1: Bad Experience** | "mala experiencia", "me hicieron mal", etc. | Exists (line 6128) but hardcodes "Dra. Laura Delgado" | Replace doctor name with `{lead_professional_name}`. Keep 4-message structure. |
| **F2: Urgency** | "dolor", "urgente", "emergencia" | Jumps to triage + availability + price in one message | Add emotional containment step BEFORE triage. Structure: empathize (1 msg) -> triage_urgency (1 msg) -> check_availability (1 msg). NEVER show price in urgency context. |
| **F3: Aesthetic Intent** | "mejorar sonrisa", "arreglar dientes", vague aesthetic | Triggers implant/prosthesis menu incorrectly | Add disambiguation step: "Que es lo que queres mejorar? Color, forma, alineacion, piezas faltantes?" BEFORE any treatment flow. Only trigger implant flow if patient explicitly mentions missing teeth/implants. |
| **F4: Unknown Insurance** | OS not in `tenant_insurance_providers` list | Agent escalates to human | New fallback: "No tengo info sobre esa OS pero igual podemos atenderte de forma particular. Queres que te pase disponibilidad?" + offer to check with clinic async. NEVER escalate just for unknown OS. |
| **F5: Price Inquiry** | "cuanto sale", "precio", "costo" | Shows price immediately without context | Enforce value-building sequence: (1) explain personalized evaluation needed, (2) position professional expertise, (3) THEN show consultation price. Treatment prices only after `get_service_details`. |
| **F6: Multiple Tooth Loss** | "perdi varios dientes", "se me cayeron", emotional distress | Goes straight to treatment assignment | Add emotional connection: validate distress -> normalize -> explain that recovery IS possible -> position professional -> THEN offer evaluation. |
| **F7: Fear/Anxiety + Internal Names** | "miedo" + agent mentions internal treatment codes | `list_services` exposes raw `name` field; agent confirms patient's prior diagnosis | Agent must NEVER confirm a patient's self-diagnosis. Must say "eso lo determina el profesional en la evaluacion". Treatment names: use `patient_display_name` when available. |
| **F8: Bone Loss/Prior Rejection** | "no tengo hueso", "me dijeron que no se puede", "rechazado" | Generic response | HIGH-PRIORITY flow: validate -> reframe ("muchos casos que parecian imposibles se resolvieron con planificacion") -> position professional expertise in complex cases -> urgent CTA to evaluation. |

#### 1B. Prohibitions Block (new section)

Add a consolidated `PROHIBICIONES` section to the prompt:

```
PROHIBICIONES (LEER 5 VECES):
- PROHIBIDO dar precio + direccion + turnos en un solo mensaje de urgencia
- PROHIBIDO repetir la bio/presentacion en cada mensaje (solo en el GREETING inicial)
- PROHIBIDO confirmar el diagnostico del paciente ("si, necesitas X")
- PROHIBIDO exponer nombres internos de tratamientos (usar patient_display_name)
- PROHIBIDO escalar a humano por: miedo, mala experiencia, OS desconocida, frustracion
- PROHIBIDO usar siempre la misma frase — variar la expresion manteniendo el tono
- PROHIBIDO responder con lenguaje corporativo/generico — usar voseo rioplatense calido
```

#### 1C. Tone and Variation Rules (new section)

```
VARIACION DE RESPUESTA (OBLIGATORIO):
- NUNCA uses la misma frase de apertura 2 veces seguidas en una conversacion
- Tene al menos 3 variantes para: saludo, cierre, empatia, ofrecimiento de turno
- Alterna entre: pregunta abierta, comentario empatico, dato util, anecdota breve
- El tono es HUMANO: como una persona real que trabaja en la clinica y LE IMPORTA el paciente
```

#### 1D. Template Variables for Multi-Tenancy

Replace the 5 hardcoded "Dra. Laura Delgado" references with template variables:

| Hardcoded Text | Replacement Variable | Source |
|----------------|---------------------|--------|
| "La Dra. se especializa en rehabilitacion oral con implantes, protesis y cirugia guiada" | `{specialty_pitch}` | `tenants.system_prompt_template` or new `tenants.specialty_pitch` field |
| "La Dra. Laura Delgado se especializa en este tipo de tratamientos" | `{lead_professional_name}` + `{lead_professional_specialty}` | `professionals` table (owner/lead professional) |
| "SERVICIOS DE LA DRA. (implantes, protesis, ATM...)" | Dynamic from `treatment_types` + `professionals` assignment | Already in DB, just needs formatting |
| "Dra. Maria Laura Delgado" in triage docstring | Remove entirely (docstring, not patient-facing) | N/A |

**Key decision**: We will NOT add a new `specialty_pitch` column. Instead, we wire up the EXISTING `tenants.system_prompt_template` column which was always intended for this purpose. If populated, it provides the persona/specialty pitch. If NULL, we generate a generic pitch from the `professionals` and `treatment_types` tables.

### Layer 2: Code Fixes

#### 2A. `_format_insurance_providers()` — Use copay_notes

Current behavior: For `accepted` providers, shows generic "Si, trabajamos con tu obra social. La consulta tiene un coseguro."

Fix: If `copay_notes` exists for a provider, include it: "Si, trabajamos con {provider_name}. {copay_notes}. Queres que te pase turnos?"

#### 2B. `check_availability` — Soften "X turnos mas" message

Line 1898: `f"\nHay {total_today - 3} turnos mas disponibles si preferis otro horario."`

Change to: `f"\nTambien hay otros horarios disponibles si ninguno te queda comodo."` (remove exact count — it's unnecessary pressure and can feel pushy in sensitive contexts).

#### 2C. `treatment_types.patient_display_name` — New column

- Alembic migration: Add `patient_display_name VARCHAR(200)` to `treatment_types` (nullable, defaults to NULL)
- Update `models.py`: Add column to `TreatmentType` class
- Update `list_services` tool: Return `patient_display_name or name` in patient-facing output
- Update `get_service_details` tool: Same logic
- **Backward compatible**: If `patient_display_name` is NULL, falls back to `name` (current behavior)

#### 2D. Wire up `tenants.system_prompt_template`

- In `buffer_task.py`: Read `tenants.system_prompt_template` from DB (already loaded in tenant query)
- Pass to `build_system_prompt()` as new parameter
- In `build_system_prompt()`: If `system_prompt_template` is not NULL/empty, inject it as the persona/specialty section instead of the hardcoded specialty pitch
- If NULL: Generate a generic pitch from available data (professionals + treatment_types)

---

## 4. Rollback Plan

### Risk Level: LOW-MEDIUM

The changes are confined to:
1. **Prompt text** (no schema changes required for behavioral fixes) — rollback = revert the prompt string
2. **One Alembic migration** (patient_display_name) — rollback = `alembic downgrade -1`
3. **Two function fixes** (_format_insurance_providers, check_availability output) — rollback = revert functions

### Rollback Steps

1. `git revert <commit>` for prompt + code changes
2. `alembic downgrade -1` for the patient_display_name migration
3. Restart orchestrator service

### Feature Flag Option

Not required. The behavioral changes improve all tenants. The `patient_display_name` column is backward-compatible (NULL = use `name`). The `system_prompt_template` is backward-compatible (NULL = use generated pitch).

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Prompt length increase | MEDIUM | The 8 emotional flows add ~200-300 lines. Monitor token usage via `token_tracker`. Consider consolidating overlapping flows. Current prompt is ~420 lines; target max ~600 lines. |
| Behavioral regression in working flows | MEDIUM | The booking flow (PASO 1-10) is well-tested and should NOT be modified. Only add new sections and replace hardcoded names. Test with real WhatsApp conversations before deploy. |
| `system_prompt_template` injection risk | LOW | The template is admin-controlled (only clinic owners can edit via admin UI). No patient input reaches this field. Still, sanitize for prompt injection markers. |
| LLM may not follow all 8 new flows perfectly | MEDIUM | Priority-rank the flows. Test each scenario independently. The most impactful are F2 (urgency), F3 (aesthetic), and F8 (bone loss). If the LLM struggles with all 8, reduce to the top 5. |
| `patient_display_name` column unused by tenants | LOW | Backward compatible. If not set, behavior is identical to current. Can be populated gradually. |
| Breaking existing prompt structure | LOW | Use additive changes (new sections) rather than rewriting existing working sections. Only modify the 5 lines with hardcoded names. |

---

## 6. Implementation Order

1. **Alembic migration**: `patient_display_name` on `treatment_types` + model update
2. **Code fixes**: `_format_insurance_providers()`, `check_availability` message, `list_services`/`get_service_details` display name logic
3. **Wire `system_prompt_template`**: buffer_task.py + build_system_prompt() parameter
4. **Prompt refactor**: Replace hardcoded names with template variables
5. **Prompt refactor**: Add 8 emotional flow blocks + prohibitions + variation rules
6. **Testing**: Verify each of the 8 scenarios with mock conversations

---

## 7. Success Criteria

- [ ] Zero hardcoded "Laura Delgado" or "Dra." references in the prompt (replaced with template variables)
- [ ] `tenants.system_prompt_template` is read and injected when populated
- [ ] `patient_display_name` column exists and is used in patient-facing tool output
- [ ] `copay_notes` appears in insurance formatting for `accepted` providers
- [ ] Urgency flow includes emotional containment BEFORE triage+availability
- [ ] Aesthetic intent triggers disambiguation, NOT implant menu
- [ ] Unknown insurance does NOT escalate to human
- [ ] Agent never repeats bio after the initial greeting
- [ ] Agent varies response phrasing across a conversation
