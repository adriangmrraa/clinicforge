# Tasks: Treatment Pre/Post Instructions Enhancement

**Change**: `treatment-pre-post-instructions-enhancement`
**Status**: READY
**Date**: 2026-04-07
**TDD**: Strict — test tasks precede implementation tasks within each phase.
**Total tasks**: 28

---

## Dependency Graph

```
1.1 (migration) → 1.2 (model update)
1.1 + 1.2 → 2.1 (schema test) → 2.2 (schema impl)
2.2 → 2.3 (coercion test) → 2.4 (coercion impl)
2.4 → 2.5 (validation test) → 2.6 (validation impl)
1.1 + 1.2 → 3.1 (tool test — pre dict) → 3.2 (tool impl — pre dict)
3.2 → 3.3 (tool test — post dict) → 3.4 (tool impl — post dict)
3.4 → 3.5 (tool test — alarm detection) → 3.6 (tool impl — alarm detection)
3.6 → 3.7 (tool test — no-instructions path) → 3.8 (tool impl — no-instructions path)
3.8 → 3.9 (prompt update)
All Phase 3 → 4.1-4.5 (frontend)
All phases → 5.1-5.5 (acceptance verification)
```

---

## Phase 1: Database + Model

- [ ] 1.1 Create Alembic migration `038_treatment_instructions_enhancement.py`
  - **File**: `orchestrator_service/alembic/versions/038_treatment_instructions_enhancement.py`
  - **Depends on**: none
  - **Acceptance**:
    - `revision = "038"`, `down_revision = "037"`
    - `upgrade()` executes in order: (1) UPDATE pre_instructions → jsonb_build_object, (2) ALTER COLUMN TYPE to JSONB, (3) UPDATE post_instructions array rows → dict with general_notes
    - `downgrade()` executes in order: (1) restore post_instructions array rows from general_notes, (2) ALTER COLUMN TYPE back to TEXT using `->>'general_notes'` cast
    - All three SQL operations are wrapped in try/except with logging (consistent with project style)
    - Uses `_column_type()` idempotency guard before ALTER to skip if already JSONB
    - Idempotency: safe to run on a DB where `pre_instructions` is already JSONB

- [ ] 1.2 Update `TreatmentType` SQLAlchemy model
  - **File**: `orchestrator_service/models.py:749`
  - **Depends on**: 1.1
  - **Acceptance**:
    - `pre_instructions = Column(JSONB, nullable=True)` — type changed from `Text` to `JSONB`
    - `post_instructions` and `followup_template` remain unchanged
    - `JSONB` import already exists in models.py (used by `post_instructions`) — no new import needed
    - No other model changes

---

## Phase 2: Backend — Pydantic Schemas + Validation

### 2.1 Write tests for Pydantic schema coercion

- [ ] 2.1 Write unit tests for `PreInstructions` and `PostInstructions` schema coercion
  - **File**: `tests/test_treatment_instructions_enhancement.py` (new file)
  - **Depends on**: none
  - **Acceptance**:
    - Test class `TestPreInstructionsSchema`:
      - `test_pre_instructions_from_dict`: pass `{"fasting_required": True, "fasting_hours": 6}` — assert `PreInstructions` model parses without error, `.fasting_required = True`, `.fasting_hours = 6`
      - `test_pre_instructions_all_optional`: pass `{}` — assert no validation error, all fields default to None/[]
      - `test_pre_instructions_general_notes_preserved`: pass `{"general_notes": "Texto legado"}` — assert `.general_notes = "Texto legado"`
    - Test class `TestPostInstructionsSchema`:
      - `test_post_instructions_from_dict`: pass full dict with all keys — assert all fields parse correctly
      - `test_post_instructions_minimal`: pass `{"care_duration_days": 7}` — assert `.care_duration_days = 7`, all lists default to `[]`
      - `test_post_instructions_list_is_accepted`: verify that `Optional[Union[PostInstructions, list]]` on the request schema accepts a legacy list without error
    - Tests FAIL before 2.2 implementation (red phase)

- [ ] 2.2 Implement `PreInstructions` and `PostInstructions` Pydantic models + update request schemas
  - **File**: `orchestrator_service/admin_routes.py`
  - **Depends on**: 2.1
  - **Acceptance**:
    - `PreInstructions` and `PostInstructions` classes added before first request schema class (around line 120)
    - `TreatmentCreateRequest.pre_instructions: Optional[Union[PreInstructions, str, dict]] = None`
    - `TreatmentCreateRequest.post_instructions: Optional[Union[PostInstructions, list, dict, str]] = None`
    - Same changes in `TreatmentUpdateRequest` and `TreatmentPatchRequest`
    - Required imports: `Union` already in `typing` (check and add if missing), `Field` from pydantic
    - Tests from 2.1 pass (green phase)

### 2.3 Write tests for coercion helpers

- [ ] 2.3 Write unit tests for `_coerce_pre_instructions` and `_coerce_post_instructions`
  - **File**: `tests/test_treatment_instructions_enhancement.py`
  - **Depends on**: 2.2
  - **Acceptance**:
    - Test class `TestCoercionHelpers`:
      - `test_coerce_pre_string_to_dict`: input `"Texto libre"` → output `{"general_notes": "Texto libre"}`
      - `test_coerce_pre_none_is_none`: input `None` → output `None`
      - `test_coerce_pre_model_to_dict`: input `PreInstructions(fasting_required=True)` → output is a dict with key `fasting_required: true`
      - `test_coerce_post_list_preserved`: input `[{timing: "24h", content: "Reposo"}]` → output is the same list
      - `test_coerce_post_model_to_dict`: input `PostInstructions(care_duration_days=7)` → output is a dict with `care_duration_days: 7`
      - `test_coerce_post_string_json`: input `'{"care_duration_days": 3}'` → output is a dict
    - Tests FAIL before 2.4 (red phase)

- [ ] 2.4 Implement `_coerce_pre_instructions` and `_coerce_post_instructions` helpers + wire into INSERT/UPDATE handlers
  - **File**: `orchestrator_service/admin_routes.py`
  - **Depends on**: 2.3
  - **Acceptance**:
    - Both helpers implemented as module-level functions
    - INSERT handler (~line 8692): `json.dumps(treatment.pre_instructions)` replaced with `json.dumps(_coerce_pre_instructions(treatment.pre_instructions))`
    - UPDATE handler (~line 8768): same replacement
    - Same for post_instructions in both handlers
    - Tests from 2.3 pass (green phase)

### 2.4 Write tests for validation update

- [ ] 2.5 Write unit tests for updated `_validate_treatment_instruction_fields`
  - **File**: `tests/test_treatment_instructions_enhancement.py`
  - **Depends on**: 2.2
  - **Acceptance**:
    - Test class `TestValidateTreatmentInstructionFields`:
      - `test_post_dict_accepted`: pass `TreatmentCreateRequest(post_instructions=PostInstructions(care_duration_days=7))` — assert no HTTPException raised
      - `test_post_list_accepted`: pass list of valid timed dicts — assert no HTTPException raised
      - `test_post_invalid_care_duration`: pass `PostInstructions(care_duration_days=0)` — assert HTTPException 422
      - `test_post_list_invalid_timing_still_raises`: pass list with `timing="invalid_value"` — assert HTTPException 422
      - `test_pre_string_accepted`: pass `pre_instructions="short text"` — assert no HTTPException (length < 2000)
      - `test_pre_string_too_long`: pass string of 2001 chars — assert HTTPException 422
    - Tests FAIL before 2.6 (red phase)

- [ ] 2.6 Update `_validate_treatment_instruction_fields` in `admin_routes.py`
  - **File**: `orchestrator_service/admin_routes.py:8444`
  - **Depends on**: 2.5
  - **Acceptance**:
    - Removes old `if not isinstance(treatment.post_instructions, list)` rejection logic
    - Adds `PostInstructions` dict path with `care_duration_days > 0` check
    - Keeps legacy list validation with expanded timing values (adds `immediate`, `24h`, `48h`, `72h`, `1w`, `stitch_removal`, `custom` to the valid set)
    - `pre_instructions` length check now applies to: string length if str, or `len(general_notes)` if dict
    - Tests from 2.5 pass (green phase)

---

## Phase 3: Tool + Prompt

### 3.1 Pre-instructions dict path

- [ ] 3.1 Write unit tests for structured `pre_instructions` formatting
  - **File**: `tests/test_treatment_instructions_enhancement.py`
  - **Depends on**: none (pure unit test, mock DB row)
  - **Acceptance**:
    - Test class `TestGetTreatmentInstructionsPre`:
      - `test_pre_dict_fasting_yes`: mock row `pre_instructions = {"fasting_required": True, "fasting_hours": 6}` — assert tool output contains `"Ayuno: SI"` and `"6 horas"`
      - `test_pre_dict_fasting_no`: mock row `fasting_required = False` — assert output contains `"Ayuno: NO requerido"`
      - `test_pre_dict_what_to_bring`: mock row `what_to_bring = ["DNI", "Estudios"]` — assert output contains `"DNI"` and `"Estudios"`
      - `test_pre_legacy_string_wrapped`: mock row `pre_instructions = {"general_notes": "Texto legado"}` — assert output contains `"Texto legado"`
      - `test_pre_null_no_section`: mock row `pre_instructions = None`, `timing = "pre"` — assert output is the no-instructions message
    - Tests FAIL before 3.2 (red phase)

- [ ] 3.2 Implement pre-instructions dict formatter in `get_treatment_instructions`
  - **File**: `orchestrator_service/main.py:6032`
  - **Depends on**: 3.1
  - **Acceptance**:
    - `_format_pre_instructions_dict(pre: dict, treatment_name: str) -> str` added as inner function or module-level helper
    - Tool reads `pre` as dict; defensive `json.loads` for string values (existing pattern)
    - When `pre` is a dict → calls `_format_pre_instructions_dict`
    - When `pre` has only `general_notes` (legacy wrapped string) → falls back to raw text injection with prefix `INSTRUCCIONES PRE-TRATAMIENTO:`
    - Tests from 3.1 pass (green phase)

### 3.2 Post-instructions dict path

- [ ] 3.3 Write unit tests for structured `post_instructions` dict formatting
  - **File**: `tests/test_treatment_instructions_enhancement.py`
  - **Depends on**: none
  - **Acceptance**:
    - Test class `TestGetTreatmentInstructionsPost`:
      - `test_post_dict_dietary`: mock `dietary_restrictions = ["No comer caliente por 24h"]` — assert output contains `"DIETA:"` and `"No comer caliente por 24h"`
      - `test_post_dict_care_duration`: mock `care_duration_days = 7` — assert output contains `"7 días"`
      - `test_post_dict_sutures`: mock `sutures_removal_day = 7` — assert output contains `"retiro al día 7"`
      - `test_post_legacy_list_still_works`: mock `post_instructions = [{"timing": "24h", "content": "Reposo absoluto"}]` — assert output contains `"24hs"` (old timing label renderer unchanged)
      - `test_post_null_returns_no_instructions_message`: mock `post_instructions = None` — assert exact message returned
    - Tests FAIL before 3.4 (red phase)

- [ ] 3.4 Implement post-instructions dict formatter in `get_treatment_instructions`
  - **File**: `orchestrator_service/main.py:6032`
  - **Depends on**: 3.3
  - **Acceptance**:
    - `_format_post_instructions_dict(post: dict, treatment_name: str) -> tuple[str, bool]` implemented
    - Tool branches: if `post` is dict → `_format_post_instructions_dict`; if `post` is list → existing timing renderer; if `post` is None → no-instructions message
    - No-instructions message is EXACTLY: `"Este tratamiento no tiene cuidados configurados. Te recomiendo contactar directamente a la clínica para más indicaciones."`
    - Tests from 3.3 pass (green phase)

### 3.3 Alarm symptom detection

- [ ] 3.5 Write unit tests for alarm symptom escalation
  - **File**: `tests/test_treatment_instructions_enhancement.py`
  - **Depends on**: 3.4
  - **Acceptance**:
    - Test class `TestAlarmSymptomEscalation`:
      - `test_alarm_symptoms_appends_tag`: mock `alarm_symptoms = ["Sangrado abundante"]` — assert tool output contains `[ALARM_ESCALATION:`
      - `test_no_alarm_symptoms_no_tag`: mock `alarm_symptoms = []` — assert `[ALARM_ESCALATION:` NOT in output
      - `test_alarm_escalation_message_included`: mock `alarm_symptoms = ["Fiebre >38.5"]`, `escalation_message = "Contactar clínica urgente"` — assert `"Contactar clínica urgente"` in output
      - `test_alarm_tag_not_in_pre_path`: mock `timing = "pre"`, `alarm_symptoms = ["X"]` — assert `[ALARM_ESCALATION:` NOT in output (alarm tag only appears for post/all with alarm symptoms)
    - Tests FAIL before 3.6 (red phase)

- [ ] 3.6 Implement alarm symptom detection and `[ALARM_ESCALATION:...]` tag injection
  - **File**: `orchestrator_service/main.py:6032`
  - **Depends on**: 3.5
  - **Acceptance**:
    - When `alarm_symptoms` list is non-empty in a `post` dict → `[ALARM_ESCALATION:...]` appended to tool output
    - Tag is appended AFTER the `escalation_message` line (if present)
    - Tag is NOT appended for the `timing = "pre"` path
    - Tag content matches: `[ALARM_ESCALATION: Si el paciente describe alguno de los síntomas de alarma de arriba, llamá derivhumano INMEDIATAMENTE con urgency='alta'. No preguntes más, actúa.]`
    - Tests from 3.5 pass (green phase)

### 3.4 No-instructions path + system prompt

- [ ] 3.7 Write unit test for no-instructions path
  - **File**: `tests/test_treatment_instructions_enhancement.py`
  - **Depends on**: 3.4
  - **Acceptance**:
    - Test class `TestNoInstructionsPath`:
      - `test_both_null_returns_standard_message`: mock row with `pre_instructions = None` and `post_instructions = None`, `timing = "all"` — assert exact no-instructions message returned
      - `test_treatment_not_found_returns_not_found`: mock `db.pool.fetchrow` returning `None` — assert `"No se encontró el tratamiento."` returned
      - `test_no_instructions_message_exact_text`: assert the returned string is exactly `"Este tratamiento no tiene cuidados configurados. Te recomiendo contactar directamente a la clínica para más indicaciones."` — no leading/trailing whitespace
    - Tests FAIL before 3.8 (red phase)

- [ ] 3.8 Implement no-instructions path (replace current fallback message)
  - **File**: `orchestrator_service/main.py:6032`
  - **Depends on**: 3.7
  - **Acceptance**:
    - The current fallback `"Este tratamiento no tiene instrucciones configuradas."` (line ~6091) is replaced with the standardized message from SPEC 4.2
    - No other changes to the fallback path
    - Tests from 3.7 pass (green phase)

- [ ] 3.9 Update system prompt `INSTRUCCIONES DE TRATAMIENTO` block
  - **File**: `orchestrator_service/main.py` (~line 7159)
  - **Depends on**: 3.6, 3.8
  - **Acceptance**:
    - Two new bullet points appended to the `INSTRUCCIONES DE TRATAMIENTO` block (after the existing 4 bullets)
    - First new bullet: alarm escalation rule (verbatim from SPEC 5)
    - Second new bullet: no-improvisation rule for the standardized no-instructions message (verbatim from SPEC 5)
    - Existing 4 bullets MUST NOT be modified
    - Verified by: `grep -A 10 "INSTRUCCIONES DE TRATAMIENTO" orchestrator_service/main.py` shows 6 bullets

---

## Phase 4: Frontend

- [ ] 4.1 Add TypeScript interfaces for `PreInstructionsForm` and `PostInstructionsForm`
  - **File**: `frontend_react/src/views/TreatmentsView.tsx`
  - **Depends on**: none (frontend can proceed in parallel with backend)
  - **Acceptance**:
    - `PreInstructionsForm` interface with all fields from design section 5.2
    - `PostInstructionsForm` interface with all fields from design section 5.2
    - Both added after `TreatmentInstructions` interface (line ~52)
    - Default empty objects exported as constants: `emptyPreForm`, `emptyPostForm`
    - TypeScript compilation passes (no type errors introduced)

- [ ] 4.2 Implement `StringListEditor` reusable component
  - **File**: `frontend_react/src/views/TreatmentsView.tsx`
  - **Depends on**: 4.1
  - **Acceptance**:
    - Component defined inline after `TreatmentImagesList` component (line ~69)
    - Props: `label: string`, `items: string[]`, `onChange: (items: string[]) => void`, `placeholder?: string`, `accentColor?: 'blue' | 'red'`
    - Renders: label, list of inputs with X buttons, "Agregar" button
    - Uses project input class: `px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white text-sm`
    - "Agregar" button: `text-blue-400 hover:text-blue-300 text-sm font-semibold flex items-center gap-1`
    - When `accentColor = 'red'`, label text is `text-red-400` and "Agregar" button is `text-red-400 hover:text-red-300`
    - When items list is empty, shows at least 1 empty input row

- [ ] 4.3 Add legal disclaimer banner and modal state split
  - **File**: `frontend_react/src/views/TreatmentsView.tsx`
  - **Depends on**: 4.1
  - **Acceptance**:
    - `instructionsLocal` state replaced with `preForm`, `postForm`, `timedSequence` states (design section 5.4)
    - Modal open handler updated to parse `pre_instructions` into `preForm` (handles dict and string cases)
    - Modal open handler updated to parse `post_instructions` into `postForm` (dict) or `timedSequence` (list)
    - Legal disclaimer banner added at top of modal body, before Section 1 (design section 6.1)
    - Banner uses: `bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs rounded-xl px-4 py-2 mb-4`
    - i18n key: `t('treatments.instructions.disclaimer')`

- [ ] 4.4 Implement structured `pre_instructions` section in modal
  - **File**: `frontend_react/src/views/TreatmentsView.tsx`
  - **Depends on**: 4.2, 4.3
  - **Acceptance**:
    - Section 1 of modal body replaced with structured sub-sections (design section 6.3)
    - Sub-section A: preparation_days_before (number input), fasting_required (checkbox/toggle), fasting_hours (shown only when fasting_required=true), medications_to_avoid (StringListEditor), medications_to_take (StringListEditor), what_to_bring (StringListEditor), general_notes (textarea 4 rows)
    - Sub-section B (legacy): shown only when `preForm._legacy_text` is non-empty; read-only textarea + "Migrar al formato estructurado" button
    - "Migrar" button: sets `preForm.general_notes = preForm._legacy_text`, clears `_legacy_text`, hides Sub-section B
    - All labels use `t()` keys from design section 5.6

- [ ] 4.5 Implement structured `post_instructions` protocol panel in modal
  - **File**: `frontend_react/src/views/TreatmentsView.tsx`
  - **Depends on**: 4.2, 4.3
  - **Acceptance**:
    - Section 2 of modal body becomes two panels with tab switcher: "Protocolo de recuperación" + "Secuencia programada"
    - Panel A (Protocolo): care_duration_days, dietary_restrictions (StringListEditor), activity_restrictions (StringListEditor), allowed_medications (StringListEditor), prohibited_medications (StringListEditor), sutures_removal_day, normal_symptoms (StringListEditor), alarm_symptoms (StringListEditor, accentColor="red"), escalation_message (textarea 2 rows)
    - Panel B (Secuencia): identical to current Section 2 implementation (timed entries + add button)
    - Save handler (design section 5.5): if postForm has any non-empty field → send dict; else if timedSequence non-empty → send list; else send null
    - Section 3 (followup_template) unchanged

---

## Phase 5: Acceptance Verification

- [ ] 5.1 Run full test suite
  - **Depends on**: all Phase 2 + Phase 3 tasks
  - **Acceptance**:
    - `pytest tests/test_treatment_instructions_enhancement.py -v` exits 0
    - All tests from tasks 2.1, 2.3, 2.5, 3.1, 3.3, 3.5, 3.7 pass
    - No pre-existing tests broken: `pytest tests/ -v --ignore=tests/test_treatment_instructions_enhancement.py` exits 0

- [ ] 5.2 Migration smoke test
  - **Depends on**: 1.1
  - **Acceptance**:
    - `alembic upgrade head` runs without error (including migration 038)
    - `alembic downgrade -1` restores `pre_instructions` to TEXT cleanly
    - Second `alembic upgrade head` re-applies migration without error
    - No data in `followup_template` or `post_instructions` dict rows is affected by downgrade cycle

- [ ] 5.3 AC-1 verification: alarm bleeding scenario
  - **Depends on**: 3.6, 3.9
  - **Acceptance**:
    - `get_treatment_instructions` with mock row containing `alarm_symptoms = ["Sangrado abundante que no cede"]` returns output containing `[ALARM_ESCALATION:` tag
    - System prompt contains the alarm escalation rule bullet

- [ ] 5.4 AC-5 verification: no-instructions path
  - **Depends on**: 3.8, 3.9
  - **Acceptance**:
    - `get_treatment_instructions` with `post_instructions = None` returns EXACTLY the standardized message
    - System prompt contains the no-improvisation rule bullet
    - No variation possible in the message (exact string match)

- [ ] 5.5 Frontend type check
  - **Depends on**: all Phase 4 tasks
  - **Acceptance**:
    - `cd frontend_react && npm run build` (or `tsc --noEmit`) exits 0
    - No TypeScript errors introduced by new interfaces or component
    - ESLint passes: `npm run lint` exits 0

---

## File Summary

| File | Tasks | Change Type |
|------|-------|-------------|
| `orchestrator_service/alembic/versions/038_treatment_instructions_enhancement.py` | 1.1 | NEW |
| `orchestrator_service/models.py` | 1.2 | MODIFY — column type change |
| `tests/test_treatment_instructions_enhancement.py` | 2.1, 2.3, 2.5, 3.1, 3.3, 3.5, 3.7 | NEW |
| `orchestrator_service/admin_routes.py` | 2.2, 2.4, 2.6 | MODIFY — 2 new models, 3 schema fields, 2 helpers, 1 validation block, 2 call sites |
| `orchestrator_service/main.py` | 3.2, 3.4, 3.6, 3.8, 3.9 | MODIFY — tool rewrite + 2 prompt lines |
| `frontend_react/src/views/TreatmentsView.tsx` | 4.1, 4.2, 4.3, 4.4, 4.5 | MODIFY — new interfaces, component, modal sections |
| `frontend_react/src/locales/es.json` | 4.4, 4.5 | MODIFY — ~20 new keys |
| `frontend_react/src/locales/en.json` | 4.4, 4.5 | MODIFY — ~20 new keys |
| `frontend_react/src/locales/fr.json` | 4.4, 4.5 | MODIFY — ~20 new keys |

---

## Notes for Implementer

1. **TDD is mandatory**: create `tests/test_treatment_instructions_enhancement.py` before editing `main.py` or `admin_routes.py`. Confirm red, implement, confirm green.

2. **Migration order is critical**: UPDATE before ALTER. If the ALTER runs first on a row with a text value like `"Texto"`, the USING cast `pre_instructions::jsonb` will fail because `"Texto"` is not valid JSON. The UPDATE wraps it in `jsonb_build_object` first, making the USING cast safe.

3. **`followup_template` is untouched**: do not touch `followup_template` at any point. The `followups.py` job depends on it exactly as-is.

4. **Legacy list rows in `post_instructions`**: after migration `038`, the legacy `[{timing, content}]` list rows are stored as `{"general_notes": "[{...}]"}`. The tool reads this `general_notes` value, parses it back as JSON, and if it's a list, feeds it to the existing timing-label renderer. This is the backwards-compat path — it must be tested explicitly (test `test_post_legacy_list_still_works`).

5. **Frontend save handler precedence**: if a user fills BOTH the Protocolo panel and the Secuencia panel, the dict (PostInstructions) takes precedence. The timedSequence data is NOT automatically migrated to `general_notes` on save — it is simply not sent. This is intentional: the two panels are mutually exclusive output formats.

6. **Pydantic `Union` type ordering**: Python evaluates `Union` left-to-right. Use `Optional[Union[PostInstructions, list, dict, str]]` so Pydantic tries to parse as `PostInstructions` model first before falling back to raw types. This avoids unexpected coercions.
