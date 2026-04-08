# SDD Proposal: Treatment Pre/Post Instructions Enhancement

**Change**: `treatment-pre-post-instructions-enhancement`
**Status**: PROPOSED
**Date**: 2026-04-07
**Author**: SDD Orchestrator

---

## 1. Intent

### Problem Statement

When a patient who recently had a dental procedure sends a message such as "me sangra después de la extracción", "¿puedo comer normal?", "¿cuándo me saco los puntos?", or "¿puedo hacer ejercicio?", the AI agent has no structured source of truth. It either improvises general medical advice (dangerous and legally risky), escalates to `derivhumano` prematurely (wasteful), or falls back to hardcoded generic text that doesn't reflect the clinic's actual protocols.

Symmetrically, when a patient about to have a procedure asks "¿tengo que ayunar?" or "¿qué medicamentos debo evitar?", the agent also improvises — because `pre_instructions` is a plain, unstructured text blob that the agent can read verbatim but cannot reason about in structured ways.

### What Already Exists (verified in codebase)

The `treatment_types` table already has the needed columns — they were added in migration `012_add_clinical_rules_engine.py`:

| Column | Current Type | Current Shape | Source |
|--------|-------------|---------------|--------|
| `pre_instructions` | `TEXT` | Plain free-text string | `models.py:749` |
| `post_instructions` | `JSONB` | `list[{timing, content, book_followup?, custom_days?}]` — a **timed outbound sequence**, not a recovery protocol dict | `models.py:750` |
| `followup_template` | `JSONB` | `list[{hours_after, message}]` — WhatsApp message templates for `followups.py` job | `models.py:751` |

The `get_treatment_instructions` tool exists in `main.py:6032` and is already in `DENTAL_TOOLS`. The system prompt already has rules at `main.py:7159-7163` that tell the agent to call this tool after booking and when asked about post-op care.

### What Is Wrong

1. `post_instructions` stores a **timed outbound sequence** (immediate/24h/48h/72h/1w/stitch_removal), not a **recovery protocol dict**. The agent reads the list of timed instructions verbatim — but when a patient asks "¿qué puedo comer?" there is no `dietary_restrictions` key to answer from. The agent falls back to improvisation.

2. `pre_instructions` is plain `TEXT`. The `get_treatment_instructions` tool dumps it raw into the response. There is no structured way for the agent to answer "¿necesito ayunar?" vs "¿qué tengo que traer?" because all pre-instructions are a single undifferentiated blob.

3. Neither field has a **care_duration_days** concept — the agent cannot determine if a patient is within the recovery window when they ask a post-op question.

4. There is no **alarm symptom detection** — when a patient describes a symptom in `alarm_symptoms`, the agent should immediately call `derivhumano`. Today it does not.

5. `followup_template.hours_after` / `message` is used exclusively by `followups.py` for outbound WhatsApp scheduling. This must be preserved exactly — `followup_template` is **out of scope** for this change.

### Why This Matters

- **Patient safety**: improvised post-op advice is a clinical liability.
- **Conversion protection**: premature escalation for routine recovery questions erodes patient trust and wastes professional time.
- **Zero new infrastructure needed**: the columns exist, the tool exists, the prompt rules exist. We only need to improve the shape of the data and the tool's ability to reason about it.

---

## 2. Scope

### In Scope

| Area | Files | What Changes |
|------|-------|-------------|
| DB migration | `alembic/versions/038_treatment_instructions_enhancement.py` | Convert `pre_instructions` TEXT → JSONB; document `post_instructions` shape; data-preserving upgrade + safe downgrade |
| SQLAlchemy model | `orchestrator_service/models.py` | `pre_instructions` column type: `Text` → `JSONB` |
| Pydantic schemas | `orchestrator_service/admin_routes.py` | `TreatmentCreateRequest`, `TreatmentUpdateRequest`, `TreatmentPatchRequest` — add typed nested models `PreInstructions` + `PostInstructions`; accept both new shape and legacy string/list |
| `get_treatment_instructions` tool | `orchestrator_service/main.py:6032` | Read new structured shape; surface `care_duration_days`, `dietary_restrictions`, `activity_restrictions`, `allowed_medications`, `prohibited_medications`, `sutures_removal_day`, `alarm_symptoms`, `normal_symptoms` in formatted output; alarm symptom detection triggers `derivhumano` instruction |
| System prompt | `orchestrator_service/main.py` (~line 7159) | Extend `INSTRUCCIONES DE TRATAMIENTO` block with alarm escalation rule and post-op query handling |
| Validation helper | `orchestrator_service/admin_routes.py` (`_validate_treatment_instruction_fields`) | Update to validate new structured shape for both fields |
| Frontend modal | `frontend_react/src/views/TreatmentsView.tsx` | Enhance existing instructions modal (line ~1122) — replace `<textarea>` for `pre_instructions` with structured sub-fields; add structured `PostInstructions` section alongside existing timed sequence; add legal disclaimer banner |

### Out of Scope

- `followup_template` — not touched; `followups.py` reads it and its current shape is correct.
- `followups.py` job — no changes.
- Nova tools — `get_treatment_instructions` is a patient-facing tool; Nova has its own `listar_tratamientos` tool.
- New admin endpoints — no new routes; existing CREATE/UPDATE endpoints absorb the new shape.
- New DB tables — zero new tables.
- Any migration beyond `pre_instructions` column type change — `post_instructions` is already JSONB.

---

## 3. Approach

### 3A. New Data Shape

#### `post_instructions` (JSONB — **replace list shape with dict shape**)

Current shape (list): `[{timing, content, book_followup?, custom_days?}]`

New shape (dict):
```json
{
  "care_duration_days": 7,
  "dietary_restrictions": ["No comer caliente por 24h", "No alcohol por 72h"],
  "activity_restrictions": ["No actividad física intensa por 48h"],
  "allowed_medications": ["Ibuprofeno 400mg cada 8h"],
  "prohibited_medications": ["Aspirina"],
  "sutures_removal_day": 7,
  "normal_symptoms": ["Ligero sangrado las primeras 24h", "Hinchazón moderada los primeros 3 días"],
  "alarm_symptoms": ["Sangrado abundante que no cede después de 30 min", "Fiebre mayor a 38.5°C"],
  "escalation_message": "Contactá inmediatamente a la clínica al [PHONE] o dirigite a urgencias."
}
```

**Migration strategy for existing data**: `post_instructions` is already JSONB. Production rows MAY contain:
- `NULL` → leave as NULL (no action)
- A list `[{timing, content}]` → the list is the old outbound-sequence format; migrate to `{"general_notes": "<serialized list>"}` so data is not lost, but agents receive it as a dict.
- A dict that already matches the new shape → preserve as-is, backfill missing keys with null.
- A string (asyncpg-returned JSONB as text) → parse, then apply list/dict logic above.

#### `pre_instructions` (TEXT → JSONB)

New shape (dict):
```json
{
  "preparation_days_before": 1,
  "fasting_required": false,
  "fasting_hours": null,
  "medications_to_avoid": ["Aspirina 5 días antes"],
  "medications_to_take": [],
  "what_to_bring": ["DNI", "Estudios previos"],
  "general_notes": "Evitar fumar el día del tratamiento"
}
```

**Migration strategy**: `pre_instructions` is currently `TEXT`. Any existing value is a plain string — wrap in `{"general_notes": "<original text>"}` on upgrade. On downgrade: extract `general_notes` key back to plain TEXT, drop remaining keys.

### 3B. Backwards Compatibility

- All fields nullable — zero behavior change if unset.
- Legacy list data in `post_instructions` is preserved in `general_notes`; the updated tool reads both dict and legacy list shapes.
- Legacy TEXT in `pre_instructions` is preserved in `general_notes`; the tool reads both dict and string shapes.
- The Pydantic schema accepts `Optional[Union[PreInstructions, str]]` for `pre_instructions` and `Optional[Union[PostInstructions, list, str]]` for `post_instructions`.
- Existing timed post-instruction entries (`timing`, `content`) continue to be readable and editable in the UI under the separate "Secuencia de seguimiento" sub-section (existing behavior preserved).

### 3C. Agent Enhancement

The `get_treatment_instructions` tool is updated to:
1. Read `care_duration_days` and check if the patient's last appointment for this treatment falls within the window (query via `current_customer_phone.get()`).
2. Format a rich response per-section: pre-op checklist, dietary/activity restrictions, normal vs alarm symptoms.
3. If any alarm symptom in `alarm_symptoms` is detected in the patient's message (via substring or semantic match), the tool returns an escalation instruction that tells the agent to call `derivhumano`.
4. If the treatment has no configured instructions, the tool returns a standardized message: "Este tratamiento no tiene cuidados configurados. Te recomiendo contactar directamente a la clínica para más indicaciones." (eliminates improvisation).

### 3D. Frontend Modal Enhancement

The existing instructions modal (`TreatmentsView.tsx:1122`) currently has:
- Section 1: `pre_instructions` as a plain `<textarea>` (line 1145)
- Section 2: `post_instructions` as a list of timed entries (line 1158)
- Section 3: `followup_template` as timed WhatsApp messages (line 1211)

The enhanced modal adds:
- Section 1 becomes two sub-panels: "Texto libre (legado)" textarea + new structured fields for `pre_instructions`.
- Section 2 gets a second tab or collapsible panel: "Protocolo de recuperación" with input fields for `care_duration_days`, `dietary_restrictions[]`, `activity_restrictions[]`, `allowed_medications[]`, `prohibited_medications[]`, `sutures_removal_day`, `normal_symptoms[]`, `alarm_symptoms[]`, `escalation_message`.
- A `StringListEditor` reusable component handles all `string[]` fields (add/remove rows).
- A legal disclaimer banner at the top of Section 2: "Estos protocolos son informativos de la clínica. No constituyen consejo médico profesional."
- If existing data is in legacy format (string for pre, list for post), a "Migrar al formato estructurado" button appears that parses the legacy data and pre-fills the structured fields on save.

---

## 4. Rollback Plan

### Risk Level: LOW

- Migration `038` is data-preserving: upgrade wraps existing data; downgrade restores original format.
- Tool changes are backwards-compatible: reads both old and new shapes.
- Frontend changes are purely additive (new fields alongside existing ones).
- Schema changes in Pydantic use `Union` types — existing API consumers continue to work.

### Rollback Steps

1. `git revert <commit>` for tool + prompt changes.
2. `alembic downgrade -1` restores `pre_instructions` to TEXT and restores original JSONB content.
3. Restart orchestrator service.

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Existing `post_instructions` data in list format is lost on migration | HIGH | Migration explicitly detects list format and preserves content in `general_notes` key. Downgrade restores from this key. |
| Agent reads `alarm_symptoms` and over-escalates | MEDIUM | Alarm symptom detection is substring-based; the tool returns an escalation hint but the prompt rule requires the agent to confirm severity before calling `derivhumano`. |
| `pre_instructions` TEXT → JSONB ALTER fails if column has non-NULL values | MEDIUM | Migration uses `UPDATE ... SET pre_instructions = jsonb_build_object(...)` BEFORE the `ALTER COLUMN TYPE` so all rows are valid JSONB at time of ALTER. |
| Frontend structured form produces invalid JSONB on save | LOW | Pydantic schema validates on the backend; frontend sends clean JSON objects, not free text for structured fields. |
| `followup_template` accidentally broken | LOW | `followup_template` is explicitly out of scope; no migration touches it; `followups.py` job is not modified. |

---

## 6. Implementation Order

1. Alembic migration `038`: UPDATE pre_instructions rows → ALTER COLUMN TYPE to JSONB → data transform for post_instructions legacy list rows.
2. Update `models.py`: `pre_instructions` column type `Text` → `JSONB`.
3. Update `admin_routes.py`: Pydantic schemas + `_validate_treatment_instruction_fields()`.
4. Update `main.py`: `get_treatment_instructions` tool — structured reader + alarm detection.
5. Update `main.py`: system prompt `INSTRUCCIONES DE TRATAMIENTO` block — alarm escalation rule.
6. Update `TreatmentsView.tsx`: enhance instructions modal with `StringListEditor` + structured fields + disclaimer.

---

## 7. Success Criteria

- [ ] `pre_instructions` column is JSONB in the DB; existing plain-text values are in `general_notes` key.
- [ ] `post_instructions` structured dict shape is accepted and stored by CREATE/UPDATE endpoints.
- [ ] `get_treatment_instructions` tool returns per-section formatted output for a treatment with new shape.
- [ ] When a patient describes a symptom matching `alarm_symptoms`, the tool returns an escalation instruction.
- [ ] When a treatment has no instructions, the tool returns a standardized non-improvised message.
- [ ] Frontend modal displays structured fields for both `pre_instructions` and `post_instructions`.
- [ ] Alembic downgrade restores `pre_instructions` to TEXT without data loss.
