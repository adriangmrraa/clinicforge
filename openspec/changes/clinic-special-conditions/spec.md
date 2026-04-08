# SPEC: Clinic Special Conditions

**Change**: `clinic-special-conditions`
**Project**: ClinicForge
**Scope**: Tenant schema + backend formatter + `triage_urgency` wiring + frontend Edit Clinic modal
**Out of scope**: Nova, anamnesis form modifications, per-professional overrides, medical advice

---

## RFC Keywords

Throughout this document: MUST = mandatory, SHALL = equivalent to MUST, SHOULD = recommended, MAY = optional.

---

## REQ-1 — Tenant Model: 7 New Columns

The `tenants` table MUST gain the following columns via Alembic migration `036`:

| Column | SQL type | Nullable | Default | Constraint |
|--------|----------|----------|---------|------------|
| `accepts_pregnant_patients` | BOOLEAN | NOT NULL | `true` | — |
| `pregnancy_restricted_treatments` | JSONB | nullable | `'[]'` | Must be a JSON array |
| `pregnancy_notes` | TEXT | nullable | null | — |
| `accepts_pediatric` | BOOLEAN | NOT NULL | `true` | — |
| `min_pediatric_age_years` | INTEGER | nullable | null | CHECK ≥ 0 |
| `pediatric_notes` | TEXT | nullable | null | — |
| `high_risk_protocols` | JSONB | nullable | `'{}'` | Must be a JSON object |
| `requires_anamnesis_before_booking` | BOOLEAN | NOT NULL | `false` | — |

**Migration requirements**:
- Migration file: `036_add_clinic_special_conditions.py`
- `revision = "036"`, `down_revision = "035"`
- `upgrade()`: `op.add_column` for each column with the correct types and defaults
- `downgrade()`: `op.drop_column` for each column
- Idempotency guard: check column existence before adding (consistent with project convention from migration `021`)
- SQLAlchemy `Tenant` class in `models.py` MUST be updated with all 8 new attributes

**Given** the migration is applied to an existing database,
**When** `alembic upgrade head` runs,
**Then** the `tenants` table MUST have all 8 new columns with their defaults without affecting any existing row data.

**Given** downgrade is executed,
**When** `alembic downgrade -1` runs,
**Then** all 8 columns MUST be removed cleanly.

---

## REQ-2 — Pydantic Validation Schema

### HighRiskProtocol (per-condition schema)

The system MUST define a Pydantic model `HighRiskProtocol` with the following fields:

```python
class HighRiskProtocol(BaseModel):
    requires_medical_clearance: bool = False
    requires_pre_appointment_call: bool = False
    restricted_treatments: list[str] = []   # treatment code strings
    notes: str = ""                          # policy text shown to patient
```

### SpecialConditionsUpdate (used in PUT endpoint)

The system MUST define a Pydantic model `SpecialConditionsUpdate`:

```python
class SpecialConditionsUpdate(BaseModel):
    accepts_pregnant_patients: Optional[bool] = None
    pregnancy_restricted_treatments: Optional[list[str]] = None
    pregnancy_notes: Optional[str] = None
    accepts_pediatric: Optional[bool] = None
    min_pediatric_age_years: Optional[int] = Field(None, ge=0)
    pediatric_notes: Optional[str] = None
    high_risk_protocols: Optional[dict[str, HighRiskProtocol]] = None
    requires_anamnesis_before_booking: Optional[bool] = None
```

**Validation rules**:
- `min_pediatric_age_years` MUST be `>= 0` if provided
- `high_risk_protocols` values MUST conform to `HighRiskProtocol` schema; unknown extra keys are rejected (strict validation)
- `pregnancy_restricted_treatments` MUST be a list of strings (treatment codes); non-string elements MUST be rejected with HTTP 422
- All fields are optional in the update schema (partial update pattern consistent with existing `update_tenant`)

**Given** a PUT request sends `{"high_risk_protocols": {"diabetes": {"requires_medical_clearance": "yes"}}}`,
**When** the endpoint validates the body,
**Then** HTTP 422 MUST be returned because `"yes"` is not a boolean.

**Given** a PUT request sends `{"min_pediatric_age_years": -1}`,
**When** the endpoint validates,
**Then** HTTP 422 MUST be returned.

---

## REQ-3 — PUT /admin/tenants Accepts New Fields

The existing `PUT /admin/tenants/{tenant_id}` endpoint MUST accept and persist the 8 new fields.

**Extension rules** (consistent with current `update_tenant` pattern):

- If a key is absent from the request body → column is unchanged (partial update)
- If `accepts_pregnant_patients` is provided → `UPDATE tenants SET accepts_pregnant_patients = $n`
- If `high_risk_protocols` is provided → validate via `HighRiskProtocol` schema per key, then serialize to JSONB: `UPDATE tenants SET high_risk_protocols = $n::jsonb`
- If `pregnancy_restricted_treatments` is provided → serialize to JSONB array
- Boolean fields MUST accept `true`/`false` (not strings)
- `min_pediatric_age_years` with value `null` in JSON → stores SQL NULL

**Tenant isolation**: the endpoint MUST only update the tenant whose `id` matches the authenticated user's tenant. The existing `verify_admin_token` + CEO role check MUST remain in place.

**Given** a CEO sends `PUT /admin/tenants/5` with `{"accepts_pregnant_patients": false, "pregnancy_notes": "Consulte con su médico"}`,
**When** the request is processed,
**Then** `tenants.accepts_pregnant_patients` for tenant 5 MUST be `false` and `pregnancy_notes` MUST be the provided string.

**Given** a non-CEO user sends the same request,
**When** processed,
**Then** HTTP 403 MUST be returned.

---

## REQ-4 — `_format_special_conditions()` Formatter

The system MUST implement a new pure function `_format_special_conditions(tenant_data: dict) -> str` in `orchestrator_service/main.py`.

### Output contract

**Input**: a dict with the 8 new fields (plus at minimum `clinic_name`). Fields may be `None` if the tenant has not configured them.

**Output**: a multi-line string to be injected into the system prompt. MUST be empty string (`""`) if all 8 fields have their default/null values (no output when nothing is configured, to avoid bloating the prompt).

### Framing rules (mandatory — enforced by formatter, not prompt)

- Every statement about restrictions MUST be prefixed with "Según política de la clínica" or "Según nuestra política"
- MUST NOT use language like: "es peligroso", "no debes", "está contraindicado médicamente", "es un riesgo para tu salud"
- MUST include the REGLA block: "NUNCA dar consejo médico. Solo reestablecer la política de la clínica."
- The generated text MUST end with: "REGLA CRÍTICA: Si el paciente menciona una condición de alto riesgo Y no tiene anamnesis completada Y la clínica exige anamnesis previa → enviar link de anamnesis ANTES de confirmar turno."

### Pregnancy block (when `accepts_pregnant_patients` or `pregnancy_notes` or `pregnancy_restricted_treatments` is configured)

- If `accepts_pregnant_patients = false`: MUST include "Según política de la clínica, no se atienden pacientes embarazadas en este momento."
- If `accepts_pregnant_patients = true` (or null/default): MUST include "Según política de la clínica, se atienden pacientes embarazadas."
- If `pregnancy_restricted_treatments` is a non-empty list: MUST resolve each treatment code to its display name (via a passed `treatment_names` dict argument) and list them as restricted. If a code is not found in the dict, include the code as-is.
- If `pregnancy_notes` is non-empty: MUST include the full text as the "Mensaje para paciente" verbatim.

### Pediatric block (when `accepts_pediatric` or `min_pediatric_age_years` or `pediatric_notes` is configured)

- If `accepts_pediatric = false`: MUST include "Según política de la clínica, no se atienden pacientes pediátricos."
- If `min_pediatric_age_years` is an integer: MUST include "La clínica atiende pacientes desde los N años."
- If `pediatric_notes` is non-empty: include verbatim.

### High-risk protocols block (when `high_risk_protocols` is a non-empty object)

For each condition key:
- MUST include: condition name + whether medical clearance is required + whether pre-appointment call is required + list of restricted treatment codes (resolved to names when possible) + notes verbatim.
- MUST NOT add language like "este paciente no puede operarse" — only restate what the protocol says.

### Anamnesis gate block

- If `requires_anamnesis_before_booking = true`: MUST include the REGLA CRÍTICA instruction (as described above) prominently at the end of the block.
- If `false` or null: MUST NOT include the gate instruction.

**Given** all 8 fields are null/default,
**When** `_format_special_conditions({...defaults...})` is called,
**Then** the return value MUST be `""` (empty string — no prompt bloat).

**Given** `accepts_pregnant_patients = false`,
**When** `_format_special_conditions({...})` is called,
**Then** the output MUST contain "no se atienden pacientes embarazadas" and MUST NOT contain "es peligroso" or "contraindicado médicamente".

**Given** `pregnancy_notes = "Consulte con su médico antes de la extracción"`,
**When** `_format_special_conditions({...})` is called,
**Then** the output MUST contain the notes string verbatim and MUST NOT modify or reframe it.

**Given** `high_risk_protocols = {"diabetes": {"requires_medical_clearance": true, "notes": "Pedimos HbA1c reciente"}}`,
**When** `_format_special_conditions({...})` is called,
**Then** the output MUST include "diabetes", "clearance médico", and "Pedimos HbA1c reciente".

---

## REQ-5 — Acceptance Scenarios (Gherkin)

### SC-1: Pregnant patient + restricted treatment

```gherkin
Given a tenant has accepts_pregnant_patients = true
  And pregnancy_restricted_treatments = ["xray_panoramic"]
  And pregnancy_notes = "Las radiografías panorámicas se posponen para después del primer trimestre"
When a patient says "Estoy embarazada de 10 semanas, puedo hacerme una radiografía panorámica?"
Then the agent MUST say "Según nuestra política, las radiografías panorámicas se posponen para después del primer trimestre"
And the agent MUST NOT say "es peligroso" or "no debes" or give radiation dosage information
And the agent MUST offer to book a consultation appointment
And the agent MUST NOT call derivhumano
```

### SC-2: Pediatric minimum age

```gherkin
Given a tenant has accepts_pediatric = true
  And min_pediatric_age_years = 6
When a parent says "Mi hijo tiene 4 años, lo atienden?"
Then the agent MUST say "La clínica atiende pacientes desde los 6 años"
And the agent MUST offer an alternative (e.g., "cuando cumpla 6 años, con gusto coordinamos")
And the agent MUST NOT say the child "no puede" receive dental care generically

Given a tenant has accepts_pediatric = false
When a parent asks about pediatric care
Then the agent MUST say "Según nuestra política, la clínica no atiende pacientes pediátricos actualmente"
And the agent MUST NOT say anything implying they should seek emergency care
```

### SC-3: Diabetic patient + extraction

```gherkin
Given a tenant has high_risk_protocols.diabetes.requires_medical_clearance = true
  And high_risk_protocols.diabetes.restricted_treatments = ["extraction_complex"]
  And high_risk_protocols.diabetes.notes = "Solicitamos control glucémico reciente antes de cirugías"
When a patient says "Tengo diabetes, me quiero hacer una extracción compleja"
Then the agent MUST say "Según nuestra política, solicitamos control glucémico reciente antes de cirugías"
And the agent MUST NOT say "la diabetes impide el tratamiento"
And the agent MUST offer a consultation appointment (NOT the surgical appointment directly)
And the agent MUST NOT call derivhumano unless patient requests human
```

### SC-4: Anticoagulated patient + surgery

```gherkin
Given a tenant has high_risk_protocols.anticoagulants.requires_medical_clearance = true
  And high_risk_protocols.anticoagulants.requires_pre_appointment_call = true
  And high_risk_protocols.anticoagulants.notes = "Requiere autorización del hematólogo antes de procedimientos quirúrgicos"
When a patient says "Tomo anticoagulantes, quiero hacerme un implante"
Then the agent MUST restate the clearance requirement from notes
And the agent MUST mention "alguien del equipo te contactará antes del turno" (pre-appointment call)
And the agent MUST offer a consultation evaluation (NOT the implant surgery directly)
And the agent MUST NOT say "no podés operarte" or give dosage/medication advice
And derivhumano MUST NOT be called
```

### SC-5: Immunosuppressed + anamnesis gate

```gherkin
Given a tenant has requires_anamnesis_before_booking = true
  And high_risk_protocols.immunosuppressed.requires_medical_clearance = true
  And the patient has no completed anamnesis (medical_history.anamnesis_completed_at IS NULL)
When a patient says "Estoy inmunosuprimida por trasplante, quiero implantes"
Then the agent MUST send the anamnesis link BEFORE confirming any appointment
And the agent MUST explain that the clinic requires the medical form to be completed first
And AFTER the anamnesis is completed: the agent MAY proceed with booking a consultation
And the agent MUST NOT complete a surgical appointment booking without the completed anamnesis
And derivhumano MUST NOT be called
```

---

## REQ-6 — Anti-Medical-Advice Guardrail

The system prompt block generated by `_format_special_conditions()` MUST contain the following instruction verbatim (or semantically equivalent):

```
REGLA DE ORO — CONDICIONES ESPECIALES:
NUNCA dar consejo médico. NUNCA decir que algo "es peligroso" o "está contraindicado" sin que sea la política explícita de la clínica.
Ante cualquier condición especial:
1. Tranquilizar al paciente ("muchos pacientes con tu condición se atienden normalmente")
2. Reestablecer la política de la clínica usando las notas configuradas
3. Ofrecer evaluación presencial
4. Sugerir completar la ficha médica (anamnesis)
NUNCA reemplazar la evaluación profesional con una respuesta del chat.
```

This rule MUST appear regardless of which sub-blocks are populated.

---

## REQ-7 — Fallback for Unconfigured Conditions

When a patient mentions a condition that is NOT in `high_risk_protocols` and is NOT pregnancy/pediatric:

The agent MUST respond with the fallback: "Gracias por avisarnos. Es importante que el profesional lo sepa. Te recomiendo mencionarlo en la consulta y completar tu ficha médica."

The agent MUST NOT:
- Say the condition prevents treatment
- Escalate to `derivhumano` for the condition alone
- Give generic health advice about the condition

---

## REQ-8 — i18n Keys

The following keys MUST be added to `es.json`, `en.json`, and `fr.json`:

| Key | es | en | fr |
|-----|----|----|-----|
| `clinics.special_conditions_section` | "Condiciones Especiales y Restricciones Clínicas" | "Special Conditions & Clinical Restrictions" | "Conditions Spéciales et Restrictions Cliniques" |
| `clinics.special_conditions_disclaimer` | "Esta configuración describe la política de la clínica y es usada por el agente de IA para orientar al paciente. No constituye asesoramiento médico ni reemplaza la evaluación profesional." | "This configuration describes the clinic's policy and is used by the AI agent to guide patients. It does not constitute medical advice or replace professional evaluation." | "Cette configuration décrit la politique de la clinique et est utilisée par l'agent IA pour guider les patients. Elle ne constitue pas un conseil médical et ne remplace pas l'évaluation professionnelle." |
| `clinics.pregnancy_section` | "Embarazo" | "Pregnancy" | "Grossesse" |
| `clinics.accepts_pregnant` | "Atender pacientes embarazadas" | "Accept pregnant patients" | "Accepter les patientes enceintes" |
| `clinics.pregnancy_restricted_treatments` | "Tratamientos con restricción (embarazo)" | "Restricted treatments (pregnancy)" | "Traitements restreints (grossesse)" |
| `clinics.pregnancy_restricted_help` | "Códigos de tratamiento separados por coma. Ej: xray_panoramic, whitening" | "Comma-separated treatment codes. E.g.: xray_panoramic, whitening" | "Codes de traitement séparés par virgule." |
| `clinics.pregnancy_notes` | "Mensaje para la paciente embarazada" | "Message for pregnant patient" | "Message pour la patiente enceinte" |
| `clinics.pregnancy_notes_help` | "Este texto será repetido al paciente tal como lo escribís. No es asesoramiento médico." | "This text will be repeated to the patient exactly as written. Not medical advice." | "Ce texte sera répété au patient tel quel. Ce n'est pas un conseil médical." |
| `clinics.pediatric_section` | "Pacientes Pediátricos" | "Pediatric Patients" | "Patients Pédiatriques" |
| `clinics.accepts_pediatric` | "Atender pacientes pediátricos" | "Accept pediatric patients" | "Accepter les patients pédiatriques" |
| `clinics.min_pediatric_age` | "Edad mínima (años)" | "Minimum age (years)" | "Âge minimum (ans)" |
| `clinics.min_pediatric_age_help` | "Dejar vacío si no hay edad mínima" | "Leave empty if there is no minimum age" | "Laisser vide s'il n'y a pas d'âge minimum" |
| `clinics.pediatric_notes` | "Notas para pacientes pediátricos" | "Notes for pediatric patients" | "Notes pour les patients pédiatriques" |
| `clinics.high_risk_section` | "Protocolos de Alto Riesgo" | "High-Risk Protocols" | "Protocoles à Haut Risque" |
| `clinics.high_risk_help` | "Configurá qué hacer cuando un paciente menciona una condición médica específica. Cada entrada describe la política de la clínica, no asesoramiento médico." | "Configure what to do when a patient mentions a specific medical condition. Each entry describes clinic policy, not medical advice." | "Configurez ce qu'il faut faire quand un patient mentionne une condition médicale spécifique." |
| `clinics.add_condition` | "Agregar condición" | "Add condition" | "Ajouter une condition" |
| `clinics.condition_name` | "Condición (ej: diabetes, anticoagulants)" | "Condition (e.g.: diabetes, anticoagulants)" | "Condition (ex: diabète, anticoagulants)" |
| `clinics.requires_medical_clearance` | "Requiere clearance médico" | "Requires medical clearance" | "Nécessite un avis médical" |
| `clinics.requires_pre_call` | "Requiere llamada previa al turno" | "Requires pre-appointment call" | "Nécessite un appel pré-rendez-vous" |
| `clinics.condition_notes` | "Mensaje para el paciente (política de la clínica)" | "Patient message (clinic policy)" | "Message pour le patient (politique de la clinique)" |
| `clinics.anamnesis_gate_section` | "Control de Anamnesis" | "Anamnesis Gate" | "Contrôle d'Anamnèse" |
| `clinics.requires_anamnesis_before_booking` | "Exigir anamnesis completada antes de confirmar turno (pacientes de alto riesgo)" | "Require completed anamnesis before confirming appointment (high-risk patients)" | "Exiger une anamnèse complète avant de confirmer le rendez-vous" |
| `clinics.requires_anamnesis_help` | "Si está activado, el agente enviará el formulario médico al paciente antes de confirmar un turno cuando detecte una condición de alto riesgo." | "If enabled, the agent will send the medical form to the patient before confirming an appointment when it detects a high-risk condition." | "Si activé, l'agent enverra le formulaire médical avant de confirmer un rendez-vous lors d'une condition à risque." |

---

## REQ-9 — Anamnesis Gate Behavior

When the system prompt includes the anamnesis gate instruction (i.e., `requires_anamnesis_before_booking = true`):

The agent MUST:
- Detect when a patient has mentioned a high-risk condition (any key in `high_risk_protocols`) AND the patient context shows `anamnesis_completed_at = null`
- Send the anamnesis URL BEFORE any call to `book_appointment`
- Include the explanation: "Antes de coordinar el turno, necesitamos que completes tu ficha médica para que el profesional pueda prepararse adecuadamente."

The agent MUST NOT:
- Use the anamnesis gate for routine (non-high-risk) bookings
- Use the anamnesis gate if `requires_anamnesis_before_booking = false`
- Block emergency bookings: if `triage_urgency` returns `emergency` or `high`, the gate MUST be bypassed

**Given** `requires_anamnesis_before_booking = true` AND patient has no completed anamnesis AND patient mentions "diabetes",
**When** the patient asks to book an appointment,
**Then** the agent MUST send the anamnesis link first.

**Given** `requires_anamnesis_before_booking = true` AND `triage_urgency` returns `emergency`,
**When** the agent processes the booking,
**Then** the anamnesis gate MUST be bypassed and the appointment MUST be offered immediately.

---

## Dependencies

- REQ-1 (migration) MUST run before REQ-3 (endpoint) can persist data
- REQ-2 (Pydantic schema) MUST be defined before REQ-3 can validate
- REQ-4 (`_format_special_conditions`) MUST be implemented before the `build_system_prompt()` injection and the triage wiring
- REQ-5 acceptance scenarios are verified after all other REQs are implemented
- REQ-8 (i18n keys) MUST be in place before the frontend section (frontend component fails to compile if keys are missing)

---

## Out of Scope (explicit)

- Nova behavioral changes
- Per-professional special conditions overrides
- Modifying the anamnesis form UI (`AnamnesisPublicView.tsx`)
- Automatic detection of conditions from existing `medical_history` JSONB (the gate checks only `anamnesis_completed_at`, not individual fields)
- WhatsApp service changes
- Changes to `triage_urgency` urgency classification algorithm
