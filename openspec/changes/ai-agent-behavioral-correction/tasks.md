# Tasks: AI Agent Behavioral Correction

**Change**: `ai-agent-behavioral-correction`
**Status**: READY
**Date**: 2026-04-04
**TDD**: Strict — test tasks come BEFORE implementation tasks within each phase.
**Total tasks**: 30

---

## Dependency Graph

```
1.1 (migration) → 1.2 (model)
1.1 + 1.2 → 2.1 (CF1 test) → 2.2 (CF1 impl)
1.1 + 1.2 → 2.3 (CF2 test) → 2.4 (CF2 impl)
1.1 + 1.2 → 2.5 (CF3 test) → 2.6 (CF3 impl)
1.1 + 1.2 → 2.7 (CF4 test) → 2.8 (CF4 impl) → 2.9 (CF4 get_service_details impl)
2.8 → 2.10 (CF5 test) → 2.11 (CF5 buffer_task impl) → 2.12 (CF5 build_system_prompt impl)
2.12 → 3.1 (bot identity) → 3.2 (prohibitions) → 3.3 (tone) → 3.4 (escalation)
3.4 → 3.5 (specialty_pitch + greeting) → 3.6 (F1-F8 flows) → 3.7 (implant flow guard)
3.7 → 3.8 (triage docstring) → 3.9 (remove hardcoded positioning)
All Phase 3 → 4.1-4.9 (scenario verification)
All phases → 4.10 (integration smoke test)
```

---

## Phase 1: Infrastructure (DB + Model)

- [ ] 1.1 Create Alembic migration 022: add `patient_display_name` to `treatment_types`
  - Files: `orchestrator_service/alembic/versions/022_add_patient_display_name.py`
  - Depends on: none
  - Acceptance:
    - `revision = "022"`, `down_revision = "021"`
    - `upgrade()` calls `op.add_column('treatment_types', sa.Column('patient_display_name', sa.Text(), nullable=True))`
    - `downgrade()` calls `op.drop_column('treatment_types', 'patient_display_name')`
    - Uses idempotency guard: check if column already exists before adding (consistent with project migration style from 021)
    - File follows naming convention `022_add_patient_display_name.py`

- [ ] 1.2 Add `patient_display_name` to `TreatmentType` SQLAlchemy model
  - Files: `orchestrator_service/models.py`
  - Depends on: 1.1
  - Acceptance:
    - `TreatmentType` class has `patient_display_name = Column(Text, nullable=True)` added after `is_available_for_booking`
    - No other model changes
    - `system_prompt_template` already exists on `Tenant` — verify it's present (no change needed)

---

## Phase 2: Code Fixes (TDD order)

### CF1 — Remove "Hay X turnos más disponibles" message

- [ ] 2.1 Write unit test for CF1: verify `check_availability` output never contains slot count message
  - Files: `tests/test_agent_behavioral_correction.py` (new file)
  - Depends on: none
  - Acceptance:
    - Test class `TestCheckAvailabilityOutput`
    - Test `test_no_extra_slots_message_single_slot`: mock tool output with 1 slot — assert string `"turnos más disponibles"` is NOT in result
    - Test `test_no_extra_slots_message_many_slots`: mock tool output with 5 slots (> 3) — assert `"turnos más disponibles"` NOT in result and `"Hay "` followed by a digit is NOT in result
    - Tests use `pytest` + `pytest-asyncio` if async, or plain `pytest` if the function is sync
    - Tests FAIL before CF1 implementation (red phase)

- [ ] 2.2 Implement CF1: remove the "Hay X turnos más disponibles" block from `check_availability`
  - Files: `orchestrator_service/main.py`
  - Depends on: 2.1
  - Acceptance:
    - Lines containing `if total_today > 3:` and the `lines.append(f"\nHay {total_today - 3} turnos más disponibles..."` block are deleted entirely
    - No replacement message is added
    - Existing tests still pass (`pytest tests/test_check_availability_holiday.py`)
    - Test 2.1 passes (green phase)

### CF2 — `_format_insurance_providers()`: use `copay_notes`

- [ ] 2.3 Write unit test for CF2: verify `_format_insurance_providers()` uses `copay_notes`
  - Files: `tests/test_agent_behavioral_correction.py`
  - Depends on: none (pure unit test, no DB)
  - Acceptance:
    - Test class `TestFormatInsuranceProviders`
    - Test `test_accepted_with_copay_notes`: input provider `{"provider_name": "OSDE", "status": "accepted", "copay_notes": "coseguro $2.500"}` — assert output contains `"coseguro $2.500"`
    - Test `test_accepted_without_copay_notes`: input provider with `copay_notes = None` — assert output contains `"coseguro estándar"` (the fallback)
    - Test `test_accepted_empty_copay_notes`: input provider with `copay_notes = ""` — assert output contains `"coseguro estándar"` (empty string treated as null)
    - Test `test_not_accepted_provider_unchanged`: `status = "not_accepted"` — assert output behavior unchanged (no copay info injected)
    - Tests import `_format_insurance_providers` directly (make it importable or test via a wrapper)
    - Tests FAIL before CF2 implementation (red phase)

- [ ] 2.4 Implement CF2: update `_format_insurance_providers()` to include `copay_notes`
  - Files: `orchestrator_service/main.py`
  - Depends on: 2.3
  - Acceptance:
    - In the `accepted` branch, for each provider: `copay = p.get("copay_notes") or "coseguro estándar"`
    - Output line per accepted provider: `"• {provider_name} → {copay}"`
    - Generic hardcoded line `"La consulta tiene un coseguro."` is removed from the accepted default
    - Tests from 2.3 pass (green phase)

### CF3 — `list_services`: use `patient_display_name` with fallback

- [ ] 2.5 Write unit test for CF3: verify `list_services` uses `patient_display_name` when present
  - Files: `tests/test_agent_behavioral_correction.py`
  - Depends on: 1.1, 1.2 (column must exist for integration tests, but unit can mock)
  - Acceptance:
    - Test class `TestListServicesDisplayName`
    - Test `test_display_name_used_when_set`: mock DB row with `patient_display_name = "Blanqueamiento dental"`, `name = "Blanqueamiento (Zoom)"` — assert tool output contains `"Blanqueamiento dental"` and does NOT contain `"Blanqueamiento (Zoom)"`
    - Test `test_fallback_to_name_when_null`: mock DB row with `patient_display_name = None`, `name = "Implante unitario"` — assert output contains `"Implante unitario"`
    - Test `test_code_unchanged`: regardless of display name, `code` field in output MUST remain the original code
    - Tests FAIL before CF3 implementation (red phase)

- [ ] 2.6 Implement CF3: update `list_services` query and output to use `patient_display_name`
  - Files: `orchestrator_service/main.py`
  - Depends on: 2.5, 1.1
  - Acceptance:
    - SQL query for `list_services` adds `tt.patient_display_name` to SELECT
    - Output uses `display_name = r.get('patient_display_name') or r['name']`
    - `r['code']` is unchanged in output
    - Tests from 2.5 pass (green phase)

### CF4 — `get_service_details`: same display name logic

- [ ] 2.7 Write unit test for CF4: verify `get_service_details` uses `patient_display_name`
  - Files: `tests/test_agent_behavioral_correction.py`
  - Depends on: 1.1, 1.2
  - Acceptance:
    - Test class `TestGetServiceDetailsDisplayName`
    - Test `test_display_name_used_when_set`: mock row with `patient_display_name = "Consulta inicial"` — assert output contains `"Consulta inicial"`
    - Test `test_fallback_when_null`: mock row with `patient_display_name = None`, `name = "Consulta"` — assert output contains `"Consulta"`
    - Tests FAIL before CF4 implementation (red phase)

- [ ] 2.8 Implement CF4: update `get_service_details` to use `patient_display_name`
  - Files: `orchestrator_service/main.py`
  - Depends on: 2.7, 1.1
  - Acceptance:
    - Both query paths in `get_service_details` (by code and by name) add `patient_display_name` to SELECT
    - Output uses `row.get('patient_display_name') or row['name']` as display label
    - Tests from 2.7 pass (green phase)

### CF5 — Wire `system_prompt_template` into `build_system_prompt()`

- [ ] 2.9 Write unit tests for CF5: verify `build_system_prompt()` injects `specialty_pitch` correctly
  - Files: `tests/test_agent_behavioral_correction.py`
  - Depends on: none (pure unit test against the function)
  - Acceptance:
    - Test class `TestBuildSystemPromptTemplateVars`
    - Test `test_specialty_pitch_injected_when_set`: call `build_system_prompt(..., specialty_pitch="Especialista en implantes guiados.")` — assert `"Especialista en implantes guiados."` is in the returned prompt string
    - Test `test_specialty_pitch_no_hardcoded_name_when_set`: same call with `specialty_pitch` set — assert `"Laura Delgado"` does NOT appear in the returned prompt (validates hardcoded name was replaced)
    - Test `test_specialty_pitch_fallback_when_none`: call `build_system_prompt(..., specialty_pitch=None)` — assert returned prompt does NOT raise and does NOT contain empty interpolation like `"La  se especializa"`
    - Test `test_bot_name_in_prompt`: call `build_system_prompt(..., bot_name="TORA")` — assert `"TORA"` appears in the returned prompt string
    - Test `test_professional_name_in_flows`: call `build_system_prompt(..., professional_name="María García")` — assert `"María García"` appears in the prompt
    - Tests FAIL before CF5 implementation (red phase)

- [ ] 2.10 Implement CF5-A: update `buffer_task.py` to fetch `system_prompt_template` and resolve `professional_name`
  - Files: `orchestrator_service/services/buffer_task.py`
  - Depends on: 2.9
  - Acceptance:
    - Tenant SQL query adds `system_prompt_template` to SELECT
    - After tenant row fetch: `specialty_pitch = (tenant_row["system_prompt_template"] or "") if tenant_row else ""`
    - New async query to `professionals` table: `SELECT first_name, last_name FROM professionals WHERE tenant_id = $1 AND is_active = true ORDER BY id ASC LIMIT 1`
    - Result: `lead_professional_name = f"{first_name} {last_name or ''}".strip()` (fallback to `""` on exception)
    - Both values passed to `build_system_prompt()` as `specialty_pitch=specialty_pitch`, `professional_name=lead_professional_name`, `bot_name="TORA"`
    - Wrapped in `try/except` to avoid breaking the message processing pipeline on failure

- [ ] 2.11 Implement CF5-B: add `specialty_pitch`, `professional_name`, `bot_name` parameters to `build_system_prompt()`
  - Files: `orchestrator_service/main.py`
  - Depends on: 2.10
  - Acceptance:
    - Function signature adds: `specialty_pitch: str = ""`, `professional_name: str = ""`, `bot_name: str = "TORA"`
    - All 3 parameters have safe defaults (backward-compatible — no existing callers break)
    - Inside function: `prof_display = professional_name if professional_name else "la profesional"` and `prof_display_full = f"el/la Dr/a. {professional_name}" if professional_name else "nuestro equipo"`
    - Tests from 2.9 pass (green phase)

---

## Phase 3: Prompt Refactor

> All tasks in this phase modify `orchestrator_service/main.py` inside `build_system_prompt()`.
> Tasks are ordered to follow the prompt section order from the design document.
> Each task is independently verifiable by inspecting the returned prompt string.

- [ ] 3.1 Add TORA bot identity to IDENTIDAD Y TONO block
  - Files: `orchestrator_service/main.py`
  - Depends on: 2.11
  - Acceptance:
    - First line of IDENTIDAD Y TONO block uses `{bot_name}` variable: `f"Tu nombre es {bot_name}."`
    - Block includes: "Si un paciente te pregunta cómo te llamás, respondé: 'Me llamo {bot_name}...'"
    - Block includes: "NUNCA te presentes con otro nombre."
    - All 3 GREETING templates updated to use `"Soy {bot_name}, la asistente virtual de {clinic_name}."` (replaces `"Soy la asistente virtual de..."`)

- [ ] 3.2 Add PROHIBICIONES block (P1–P8) after POLÍTICA DE PUNTUACIÓN
  - Files: `orchestrator_service/main.py`
  - Depends on: 2.11
  - Acceptance:
    - New named block `PROHIBICIONES (LEER 5 VECES):` inserted before INFORMACIÓN DEL CONSULTORIO
    - Contains all 8 prohibition rules matching SPEC 2 (P1–P7 from spec, + P8 re treatment prices)
    - Rule P8 uses `{price_text}` variable (already computed in the function)
    - No existing section is removed at this step

- [ ] 3.3 Add TONO Y VARIACIÓN block (replaces REGLAS DE CONVERSACIÓN Y TONO)
  - Files: `orchestrator_service/main.py`
  - Depends on: 2.11
  - Acceptance:
    - Old `REGLAS DE CONVERSACIÓN Y TONO` section (lines ~6234-6242) is REMOVED
    - New `TONO Y VARIACIÓN (OBLIGATORIO):` block inserted at the same position (before POSICIONAMIENTO)
    - Contains all rules from design 4G: voseo, 2-emoji max, variation requirement, 4-line max per bubble, always close with CTA or soft question
    - Content matches SPEC 3 exactly

- [ ] 3.4 Update ESCALATION RULES: replace single `derivhumano` rule with full block
  - Files: `orchestrator_service/main.py`
  - Depends on: 2.11
  - Acceptance:
    - The existing single-line escalation rule in REGLAS CORE is REMOVED
    - New `REGLAS DE ESCALACIÓN (derivhumano):` block added per design 4I
    - "ESCALAR (OBLIGATORIO)" section lists 3 allowed triggers exactly
    - "NO ESCALAR (PROHIBIDO)" section lists all 9 prohibited triggers with corresponding flow references (F1–F8 + frustration)
    - Decision rule at end: "Si el trigger está en 'NO ESCALAR' Y el paciente NO pidió explícitamente un humano → derivhumano PROHIBIDO."

- [ ] 3.5 Add specialty_pitch to GREETING templates and POSICIONAMIENTO block
  - Files: `orchestrator_service/main.py`
  - Depends on: 2.11
  - Acceptance:
    - `greeting_specialty = specialty_pitch if specialty_pitch else "La Dra. se especializa en rehabilitación oral con implantes, prótesis y cirugía guiada."` computed before greeting construction
    - Each of the 3 GREETING templates uses `{greeting_specialty}` instead of hardcoded specialty text
    - Conditional POSICIONAMIENTO block added per design 4H:
      - If `specialty_pitch` non-empty: inject `POSICIONAMIENTO PROFESIONAL:` block with the pitch text and usage instructions
      - If `specialty_pitch` empty/None: keep current ESTRUCTURA DE RESPUESTA + FRASES BASE + DIFERENCIACIÓN DRA. vs EQUIPO blocks as fallback (replacing `"Dra. Laura Delgado"` in fallback with `{prof_display_full}`)

- [ ] 3.6 Add F1–F8 emotional flows block (replaces MANEJO DE OBJECIONES entirely)
  - Files: `orchestrator_service/main.py`
  - Depends on: 3.5
  - Acceptance:
    - Old `MANEJO DE OBJECIONES` section (including sub-sections: OBJECIÓN DE MIEDO, MALA EXPERIENCIA PREVIA, OBJECIÓN DE PRECIO) is REMOVED entirely
    - New `FLUJOS EMOCIONALES (F1-F8) — CONTENER > ORIENTAR > CONVERTIR` block inserted at the same position
    - All 8 flows present: F1 (mala experiencia), F2 (urgencia), F3 (estético), F4 (OS desconocida), F5 (precio), F6 (pérdida múltiple), F7 (miedo), F8 (sin hueso/rechazado)
    - Each flow has: trigger keywords, protocol steps (M1-M4 as required), postcondition where specified, PROHIBIDO list
    - F1, F3, F6, F7, F8 use `{prof_display_full}` variable (not hardcoded name)
    - F5 uses `{price_text}` for consultation price
    - F2 explicitly states: no price/address in M1-M2, max 2 messages before appointment offer
    - F8 marked as ALTA PRIORIDAD

- [ ] 3.7 Modify FLUJO DE IMPLANTES Y PRÓTESIS: add F3 guard + replace hardcoded doctor name
  - Files: `orchestrator_service/main.py`
  - Depends on: 3.6
  - Acceptance:
    - Guard added at TOP of the implant/prosthesis flow block: `"IMPORTANTE: Este flujo se activa SOLO si el paciente menciona explícitamente implantes, prótesis, dentadura, o dientes faltantes. Si la intención es estética vaga ('mejorar sonrisa') → usar F3."`
    - All occurrences of `"La Dra."` within this block replaced with `{prof_display}` or `{prof_display_full}` (context-appropriate)
    - Specifically: `"La Dra. Laura Delgado se especializa en este tipo de tratamientos..."` → `"{prof_display_full} se especializa en este tipo de tratamientos, incluyendo casos complejos."`
    - `"así la Dra. ya los tiene"` → `"así ya los tiene para tu consulta"`

- [ ] 3.8 Remove hardcoded "Dra. Maria Laura Delgado" from `triage_urgency` docstring
  - Files: `orchestrator_service/main.py`
  - Depends on: none (isolated change)
  - Acceptance:
    - Docstring of `triage_urgency` tool (line ~2795) no longer contains `"Dra. María Laura Delgado"` or `"Dra. Maria Laura Delgado"` (any spelling variant)
    - Replaced with `"el profesional"` or removed entirely (no patient-facing impact — docstring is tool metadata)
    - Verified via: `grep "Laura Delgado" orchestrator_service/main.py` returns 0 results when `specialty_pitch` path is active

- [ ] 3.9 Final audit: verify zero hardcoded personal name occurrences remain
  - Files: `orchestrator_service/main.py`
  - Depends on: 3.1 through 3.8
  - Acceptance:
    - `grep -n "Laura Delgado" orchestrator_service/main.py` returns only lines that are inside the hardcoded fallback path (i.e., `specialty_pitch` is empty/None), and those lines use `{prof_display_full}` variable expansion — NOT the literal string
    - If any literal `"Laura Delgado"` string remains outside the fallback path, it MUST be replaced before this task is checked off
    - Document all remaining occurrences (if any in fallback) in a comment block at top of `build_system_prompt()`

---

## Phase 4: Testing & Verification

- [ ] 4.1 Run full unit test suite and confirm all new tests pass (green phase)
  - Files: `tests/test_agent_behavioral_correction.py`
  - Depends on: all Phase 2 tasks
  - Acceptance:
    - `pytest tests/test_agent_behavioral_correction.py -v` exits 0
    - All tests from tasks 2.1, 2.3, 2.5, 2.7, 2.9 pass
    - No pre-existing tests broken: `pytest tests/ -v --ignore=tests/test_agent_behavioral_correction.py` exits 0

- [ ] 4.2 Scenario test — AC-F1: Mala experiencia previa
  - Files: manual test / scenario script
  - Depends on: 3.6
  - Acceptance (per SPEC):
    - Trigger phrase "mala experiencia" produces 4 separate messages (M1–M4)
    - M4 uses word "evaluación", NOT "turno"
    - `derivhumano` NOT called
    - `{professional_name}` appears in M3 (not hardcoded "Laura Delgado")
    - Verified by calling `build_system_prompt()` with known inputs and checking the prompt text contains F1 rules

- [ ] 4.3 Scenario test — AC-F2: Urgencia / dolor
  - Depends on: 3.6, 2.2 (CF1 code fix)
  - Acceptance:
    - Prompt text for F2 specifies max 2 messages before appointment offer
    - F2 block explicitly prohibits price/address in M1-M2
    - String `"turnos más disponibles"` does NOT appear anywhere in `check_availability` output (confirmed by 2.1)

- [ ] 4.4 Scenario test — AC-F3: Paciente estético
  - Depends on: 3.6, 3.7
  - Acceptance:
    - F3 trigger phrases present in prompt
    - F3 PROHIBIDO section explicitly mentions: "Mostrar menú de emojis de implantes"
    - Implant flow block has the guard that redirects vague aesthetic intent to F3
    - "No soy candidato" does NOT trigger F3 (F8 has precedence per spec)

- [ ] 4.5 Scenario test — AC-F4: Obra social desconocida
  - Depends on: 3.6
  - Acceptance:
    - F4 PROHIBIDO section includes: "derivhumano", "Decir 'no trabajamos con esa'", "Pedir que llame a la clínica"
    - F4 only escalates IF patient explicitly requests it (conditional offer, M3)

- [ ] 4.6 Scenario test — AC-F5: Precio directo
  - Depends on: 3.6
  - Acceptance:
    - F5 M2 uses `{price_text}` variable (not hardcoded number)
    - F5 M1 explicitly builds value before showing price
    - F5 PROHIBIDO includes: "Dar precio de tratamiento específico"

- [ ] 4.7 Scenario test — AC-F6: Pérdida múltiple de dientes
  - Depends on: 3.6, 3.7
  - Acceptance:
    - F6 PROHIBIDO includes: "R.I.S.A.", "All-on-4", "zigomático", "menú de emojis"
    - F6 and F3 mutual exclusion rule present: "Si menciona dientes faltantes → F6 tiene precedencia"
    - No treatment assignment in F6 steps

- [ ] 4.8 Scenario test — AC-F7 + AC-F8: Miedo y sin hueso
  - Depends on: 3.6
  - Acceptance (F7):
    - F7 PROHIBIDO includes: "Confirmar diagnóstico previo", "derivhumano", procedure names
    - F7 M1 contains "Es totalmente normal" (exact phrase or equivalent)
  - Acceptance (F8):
    - F8 marked ALTA PRIORIDAD in prompt
    - F8 M2 uses qualifying language: "en muchos casos"
    - F8 PROHIBIDO: "Confirmar diagnóstico ajeno", "Prometer resultados"

- [ ] 4.9 Verify template variables — AC-TV1: No literal "Laura Delgado" in tenant with specialty_pitch set
  - Files: `tests/test_agent_behavioral_correction.py`
  - Depends on: all Phase 3
  - Acceptance:
    - Unit test `test_no_hardcoded_name_with_specialty_pitch`: call `build_system_prompt(..., specialty_pitch="Especialista en implantes.", professional_name="Ana Gómez")` — assert `"Laura Delgado"` does NOT appear in output
    - Unit test `test_no_hardcoded_name_with_professional_name`: call with `professional_name="Ana Gómez"`, `specialty_pitch=""` — assert `"Laura Delgado"` does NOT appear in output (fallback path uses `{prof_display_full}`)

- [ ] 4.10 Integration smoke test: `alembic upgrade head` + `alembic downgrade -1` + `alembic upgrade head`
  - Files: migration 022
  - Depends on: 1.1, 1.2
  - Acceptance:
    - `alembic upgrade head` runs without error against a test database
    - `alembic downgrade -1` removes `patient_display_name` column cleanly
    - Second `alembic upgrade head` re-adds it without error
    - No data in other `treatment_types` columns is affected

---

## File Summary

| File | Tasks | Change type |
|------|-------|-------------|
| `orchestrator_service/alembic/versions/022_add_patient_display_name.py` | 1.1 | NEW FILE |
| `orchestrator_service/models.py` | 1.2 | MODIFY — add column |
| `tests/test_agent_behavioral_correction.py` | 2.1, 2.3, 2.5, 2.7, 2.9, 4.9 | NEW FILE |
| `orchestrator_service/main.py` | 2.2, 2.4, 2.6, 2.8, 2.11, 3.1–3.9 | MODIFY — multiple sub-changes |
| `orchestrator_service/services/buffer_task.py` | 2.10 | MODIFY — tenant query + professional resolution |

---

## Notes for Implementer

1. **TDD is mandatory**: create `tests/test_agent_behavioral_correction.py` before editing `main.py`. Run `pytest` to confirm tests fail (red), then implement, then confirm tests pass (green).

2. **Do not modify Phase 4 booking flow (PASOS 1-10)**: The appointment scheduling flow is well-tested and out of scope. Only add/replace sections, do not touch PASO 1–10 block.

3. **Migration style**: Follow 021's pattern — use `op.get_bind()` and idempotency guards (check column existence before adding). Use string revision IDs: `revision = "022"`, `down_revision = "021"`.

4. **Prompt changes are additive first**: Add new sections before removing old ones. Verify the prompt builds correctly with the new params, then remove replaced sections.

5. **`prof_display_full` fallback**: When `professional_name` is empty string, `prof_display_full = "nuestro equipo"`. This must never produce `"el/la Dr/a. "` with no name following.

6. **Token budget**: Estimated +44 lines on top of existing ~420. Target max is 600 lines. Count lines before and after to confirm.
