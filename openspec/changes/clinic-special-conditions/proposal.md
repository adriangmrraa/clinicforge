# SDD Proposal: Clinic Special Conditions

**Change**: `clinic-special-conditions`
**Status**: PROPOSED
**Date**: 2026-04-07
**Author**: SDD Orchestrator

---

## 1. Intent

### Problem Statement

The patient-facing AI agent has no configurable, per-tenant understanding of which patients or treatments are restricted by clinic policy. This is **debilidad #5** from `docs/debilidades-system-prompt.md`:

> "Embarazo / Condiciones Especiales — Alto impacto, frecuencia media. Las embarazadas y pacientes con condiciones especiales necesitan tranquilidad. Sin respuesta, pueden pensar que no pueden atenderse o sentir inseguridad."

The current state is improvisation: the agent gives generic reassurances ("muchos tratamientos son seguros durante el embarazo") with no knowledge of what THIS clinic actually does or does not accept, and no knowledge of which treatments carry risk for which conditions.

Specifically:

| Scenario | Current agent behavior | Expected behavior |
|----------|----------------------|-------------------|
| Pregnant patient asks about X-ray | Generic "el profesional evaluará" | Restates clinic policy — e.g., "según nuestra política, las radiografías convencionales se evitan en el primer trimestre" |
| Child under minimum age | No minimum age awareness | "Nuestro equipo atiende pacientes desde los X años" |
| Diabetic patient asks about extraction | Generic answer | "Para pacientes con diabetes, solicitamos un control glucémico reciente antes de cirugías" |
| Anticoagulated patient asks about surgery | Generic answer | "Para pacientes anticoagulados, requerimos autorización médica previa. Igual podemos coordinar la consulta." |
| Immunosuppressed patient asks about implants | Generic answer | Restates clinic's pre-clearance requirement, offers evaluation |

The root cause: the tenant model has no columns for special condition policy. The agent cannot tell the patient what the CLINIC says — only what a generic AI would say. This is a medical liability risk and a patient trust gap.

### Why This Matters

- **Trust and conversion**: A pregnant patient who hears a confident, policy-grounded answer is far more likely to book than one who gets a vague deflection.
- **Legal/medical compliance**: The agent MUST NOT give medical advice. It can only restate the clinic's own policy. Without configurable policy, it either says nothing useful or improvises something that could be legally problematic.
- **High-risk patient safety**: Patients with diabetes, anticoagulants, or immunosuppression require pre-appointment protocols. If the agent books them without flagging the requirement, the clinic may receive unprepared patients.
- **Pediatric clarity**: Many parents write asking from what age children are seen. Without a configured minimum age, the agent gives a vague answer that doesn't help the parent decide.

---

## 2. Scope

### In Scope

| Area | Files | What Changes |
|------|-------|-------------|
| Tenant DB schema | `orchestrator_service/models.py` + Alembic `036` | 7 new columns on `tenants` |
| Tenant update endpoint | `orchestrator_service/admin_routes.py` (`update_tenant`) | Accept and persist new fields |
| Prompt formatter | `orchestrator_service/main.py` | New `_format_special_conditions()` function + injection into `build_system_prompt()` |
| `triage_urgency` wiring | `orchestrator_service/main.py` | Cross-reference tenant special condition policy in triage output |
| `buffer_task.py` | `orchestrator_service/services/buffer_task.py` | Pass new tenant fields to `build_system_prompt()` |
| Frontend — Edit Clinic modal | `frontend_react/src/views/ClinicsView.tsx` | New "Condiciones Especiales" section with 4 sub-blocks |
| i18n | `frontend_react/src/locales/es.json`, `en.json`, `fr.json` | New translation keys |

### Out of Scope

- **Nova** — internal assistant, separate prompt; does not interact with external patients
- **Anamnesis form** — already captures conditions in `medical_history` JSONB; this change does not modify the form
- **`triage_urgency` complete rewrite** — only add a context injection step; the existing urgency classification logic is unchanged
- **Medical advice** — the agent NEVER gives clinical advice; it only restates the configured clinic policy
- **Per-professional special conditions** — all config is tenant-wide; professional-level overrides are out of scope
- **WhatsApp service** — no routing or delivery changes

---

## 3. Approach

### Layer 1: Tenant Schema — 7 New Columns

Add to `tenants` table (Alembic migration `036`):

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `accepts_pregnant_patients` | BOOLEAN | `true` | Whether clinic accepts pregnant patients at all |
| `pregnancy_restricted_treatments` | JSONB | `[]` | Array of treatment `code` strings restricted/contraindicated during pregnancy |
| `pregnancy_notes` | TEXT | null | What to tell a pregnant patient (policy text, NOT medical advice) |
| `accepts_pediatric` | BOOLEAN | `true` | Whether clinic treats pediatric patients |
| `min_pediatric_age_years` | INTEGER | null | Minimum age in years; null = no minimum |
| `pediatric_notes` | TEXT | null | Additional note for pediatric patients |
| `high_risk_protocols` | JSONB | `{}` | Per-condition protocol map (see structure below) |
| `requires_anamnesis_before_booking` | BOOLEAN | `false` | Gate booking for high-risk patients who lack a completed anamnesis |

**`high_risk_protocols` structure**:

```json
{
  "diabetes": {
    "requires_medical_clearance": true,
    "requires_pre_appointment_call": false,
    "restricted_treatments": ["surgery_implant", "extraction_complex"],
    "notes": "Solicitamos control glucémico (HbA1c) reciente antes de cirugías. La consulta de evaluación no requiere clearance previo."
  },
  "anticoagulants": {
    "requires_medical_clearance": true,
    "requires_pre_appointment_call": true,
    "restricted_treatments": ["surgery_implant", "extraction_complex", "surgery_periodontal"],
    "notes": "Requiere autorización del médico hematólogo o de cabecera antes de cualquier procedimiento quirúrgico."
  },
  "hypertension": {
    "requires_medical_clearance": false,
    "requires_pre_appointment_call": false,
    "restricted_treatments": [],
    "notes": "Informar al profesional. En casos de hipertensión no controlada se puede reprogramar el tratamiento."
  },
  "immunosuppressed": {
    "requires_medical_clearance": true,
    "requires_pre_appointment_call": false,
    "restricted_treatments": ["surgery_implant"],
    "notes": "Requiere evaluación previa del estado inmunológico con el médico tratante antes de implantes."
  },
  "cardiac": {
    "requires_medical_clearance": true,
    "requires_pre_appointment_call": true,
    "restricted_treatments": [],
    "notes": "Requiere clearance cardiológico para procedimientos bajo anestesia local. Consulta de evaluación no requiere clearance."
  }
}
```

Built-in known condition keys: `diabetes`, `anticoagulants`, `hypertension`, `immunosuppressed`, `cardiac`. Clinic can add custom conditions (free-form keys).

### Layer 2: `_format_special_conditions()` Formatter

A new pure function in `main.py` that converts the 7 tenant fields into a prompt section using strict "según política de la clínica" framing. Never medical advice — always clinic policy restatement.

Output example when `pregnancy_notes` is set and `pregnancy_restricted_treatments = ["xray_full", "whitening"]`:

```
## CONDICIONES ESPECIALES Y RESTRICCIONES (POLÍTICA DE LA CLÍNICA)

EMBARAZO:
• Según política de la clínica, se atienden pacientes embarazadas.
• Tratamientos con restricción durante el embarazo: Radiografía panorámica, Blanqueamiento dental.
• Mensaje para paciente: "Muchos tratamientos son seguros durante el embarazo. Según nuestra política, las radiografías panorámicas y el blanqueamiento se posponen para después del primer trimestre. El profesional evaluará tu caso en la consulta."
REGLA: NUNCA dar consejo médico. Solo reestablecer la política de la clínica.

PEDIATRÍA:
• La clínica atiende pacientes desde los 6 años.
• Para menores: "En la clínica atendemos niños desde los 6 años. Si tu hijo tiene X años, podemos coordinar una consulta."

CONDICIONES DE ALTO RIESGO:
• diabetes: Requiere clearance médico antes de cirugías. Nota: "Solicitamos control glucémico reciente."
• anticoagulants: Requiere clearance + llamada previa. Nota: "Requiere autorización del hematólogo."
REGLA: Ante cualquiera de estas condiciones → reestablecer la política → sugerir consulta.
REGLA CRÍTICA: Si el paciente menciona una condición Y no tiene anamnesis completada Y requires_anamnesis_before_booking=true → enviar link de anamnesis ANTES de confirmar el turno.
```

### Layer 3: `triage_urgency` Cross-Reference

When `triage_urgency` is called and the patient's `medical_history` contains a flagged condition (e.g., `anticoagulants_use: "Sí"` in anamnesis), the triage output adds a protocol reminder. This is read from the `current_tenant_id` context var (already available in tool functions) via a DB lookup of `high_risk_protocols`.

### Layer 4: Anamnesis Gate

When `requires_anamnesis_before_booking = true` AND the patient has an incomplete anamnesis AND the conversation context shows a high-risk condition mention → the agent sends the anamnesis link before proceeding to `book_appointment`. This gate logic lives in the system prompt (instructions to the agent), not in the `book_appointment` tool code, to avoid breaking the tool's API.

### Layer 5: Frontend — 4 Sub-Blocks in Edit Clinic Modal

New collapsible section "Condiciones Especiales y Restricciones Clínicas" appended after the `system_prompt_template` textarea, with:

1. **Embarazo** — toggle `accepts_pregnant_patients`, `pregnancy_restricted_treatments` (tag-style input for treatment codes), `pregnancy_notes` textarea
2. **Pediatría** — toggle `accepts_pediatric`, `min_pediatric_age_years` number input, `pediatric_notes` textarea
3. **Protocolos de Alto Riesgo** — key-value editor (condition name → `requires_medical_clearance` bool + `requires_pre_appointment_call` bool + `restricted_treatments` tags + `notes` textarea)
4. **Anamnesis Gate** — single toggle `requires_anamnesis_before_booking`

Legal disclaimer inside the UI section: "Esta configuración describe la política de la clínica y es usada por el agente de IA para orientar al paciente. No constituye asesoramiento médico ni reemplaza la evaluación profesional."

---

## 4. Success Criteria

### 5 Acceptance Scenarios

| # | Scenario | Expected Agent Behavior |
|---|----------|------------------------|
| SC-1 | Pregnant patient asks about panoramic X-ray; clinic has `pregnancy_restricted_treatments = ["xray_panoramic"]` | Agent says "según nuestra política, las radiografías panorámicas se evitan durante el embarazo. El profesional evaluará el caso en la consulta." Does NOT give medical advice. Does NOT refuse to book consultation. |
| SC-2 | Parent asks about 4-year-old; clinic has `min_pediatric_age_years = 6` | Agent says "Nuestro equipo atiende pacientes desde los 6 años." If `accepts_pediatric = false`: "La clínica actualmente no atiende pacientes pediátricos." |
| SC-3 | Diabetic patient asks about complex extraction; clinic has `diabetes.requires_medical_clearance = true` and notes | Agent restates the clearance requirement from `notes`. Still offers to book a consultation (not a surgical appointment). Does NOT refuse. Does NOT give dietary/medication advice. |
| SC-4 | Patient mentions "tomo anticoagulantes" and asks about implant surgery; clinic has `anticoagulants` protocol | Agent: (a) restates the authorization requirement, (b) if `requires_pre_appointment_call = true` notes that someone will call before the appointment, (c) still offers evaluation consultation. Does NOT call `derivhumano` unless patient requests human. |
| SC-5 | Immunosuppressed patient asks about implants; `requires_anamnesis_before_booking = true` and patient has no completed anamnesis | Agent sends anamnesis link BEFORE confirming appointment booking. After anamnesis is completed: proceeds normally. |

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Agent gives medical advice instead of restating policy | HIGH | Strict prompt framing: every condition block in `_format_special_conditions()` must include "según política de la clínica" and the REGLA block explicitly forbids medical advice. Unit tests verify the formatter never produces language like "no debes", "es peligroso", "contraindicado médicamente". |
| Medical liability from incorrect clinic configuration | HIGH | UI disclaimer makes it unambiguous that the configuration describes clinic policy, not medical fact. Responsibility rests with the clinic owner who fills in the form. Tooltip on each field: "Este texto será repetido al paciente tal como lo escribís." |
| `high_risk_protocols` JSONB structure drift | MEDIUM | Pydantic model `HighRiskProtocol` validates structure on write. Unknown condition keys are accepted (open-ended) but each value must match the schema. |
| Anamnesis gate blocks urgent bookings | MEDIUM | The gate applies only when `requires_anamnesis_before_booking = true` AND the condition is detected. Urgency flow (F2) bypasses the gate — if `triage_urgency` returns `emergency` or `high`, booking proceeds without anamnesis gate. |
| Frontend key-value editor complexity | LOW | Use a simple `textarea` with JSON validation as the initial implementation for `high_risk_protocols` (consistent with existing JSONB fields in the app). Progressive enhancement to visual editor in a future iteration. |
| i18n burden for 3 locales | LOW | All new keys added to `es.json`, `en.json`, `fr.json` together. French keys can be mechanically translated from Spanish. |

---

## 6. Alternatives

### Alternative A: Static FAQ entries per condition (no new columns)
Add a set of static system FAQs for known conditions. Simpler — no migration needed.

**Rejected** because: FAQs are globally injected or RAG-retrieved; they cannot express per-tenant policy decisions (e.g., whether THIS clinic accepts pregnant patients or not). Generic FAQs would still be improvisation.

### Alternative B: Single JSONB `special_conditions_config` column
One JSONB column containing everything instead of 7 separate columns.

**Rejected** because: individual boolean columns (`accepts_pregnant_patients`, `accepts_pediatric`, `requires_anamnesis_before_booking`) are queryable, indexable, and self-documenting. The JSONB `high_risk_protocols` is appropriate for the open-ended, variable structure of per-condition protocols.

### Alternative C: Hardcode the 5 standard conditions in the prompt with generic text
No DB changes. Add a generic "condiciones especiales" block to `build_system_prompt()`.

**Rejected** because: this is exactly the current state (improvisation). Without per-tenant configuration, the agent cannot say what THIS clinic does — and that is the entire problem.

---

## 7. Implementation Order

1. Alembic migration `036` — 7 new columns
2. SQLAlchemy model update (`models.py`)
3. Pydantic `HighRiskProtocol` schema + validation
4. `update_tenant` endpoint accepts new fields
5. `_format_special_conditions()` formatter (TDD first)
6. `build_system_prompt()` wiring + `buffer_task.py` query extension
7. `triage_urgency` cross-reference (TDD first)
8. Frontend 4 sub-blocks + i18n keys
9. 5 scenario verification + anti-medical-advice guardrail tests
