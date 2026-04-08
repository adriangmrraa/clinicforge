# SPEC: Treatment Pre/Post Instructions Enhancement

**Change**: `treatment-pre-post-instructions-enhancement`
**Project**: ClinicForge
**Scope**: `treatment_types` fields enhancement — no new tables, no new endpoints, no Nova changes.

---

## RFC Keywords

MUST = mandatory, SHALL = equivalent to MUST, SHOULD = recommended, MAY = optional.

---

## SPEC 1 — Data Shape Contract

### 1.1 `post_instructions` (JSONB dict — new shape)

The `post_instructions` column MUST store a JSON object matching the `PostInstructions` schema when configured with the new format:

```json
{
  "care_duration_days": <integer | null>,
  "dietary_restrictions": ["<string>", ...],
  "activity_restrictions": ["<string>", ...],
  "allowed_medications": ["<string>", ...],
  "prohibited_medications": ["<string>", ...],
  "sutures_removal_day": <integer | null>,
  "normal_symptoms": ["<string>", ...],
  "alarm_symptoms": ["<string>", ...],
  "escalation_message": "<string | null>"
}
```

All keys are optional (nullable). Arrays default to `[]`. A row with `post_instructions = NULL` MUST produce no post-op behavior change (no injection, no alarm check).

**Legacy shape** (existing rows with list format `[{timing, content}]`): The system MUST read legacy list rows without error. The `get_treatment_instructions` tool MUST format them using the existing timing-label renderer (preserving current behavior). The frontend MUST show legacy data in the "Secuencia de seguimiento" sub-section and offer a migration button. The migration `038` MUST transform legacy list rows to `{"general_notes": "<JSON-serialized original list>"}` during upgrade.

### 1.2 `pre_instructions` (JSONB dict — promoted from TEXT)

The `pre_instructions` column MUST be JSONB after migration `038`. It MUST store a JSON object matching the `PreInstructions` schema:

```json
{
  "preparation_days_before": <integer | null>,
  "fasting_required": <boolean | null>,
  "fasting_hours": <integer | null>,
  "medications_to_avoid": ["<string>", ...],
  "medications_to_take": ["<string>", ...],
  "what_to_bring": ["<string>", ...],
  "general_notes": "<string | null>"
}
```

All keys are optional (nullable). Arrays default to `[]`. Legacy TEXT content is preserved in `general_notes` during migration.

**Backwards compat read**: the `get_treatment_instructions` tool MUST handle the case where asyncpg returns the JSONB column as a string (defensive `json.loads`), consistent with existing patterns in the codebase.

### 1.3 `followup_template` (JSONB list — unchanged)

`followup_template` MUST NOT be modified. Its current shape `[{hours_after, message}]` is consumed by `orchestrator_service/jobs/followups.py` and is out of scope. No migration, no schema change, no tool change touches this column.

---

## SPEC 2 — Migration `038`

### 2.1 Upgrade

The migration MUST execute in this order:

1. **Transform `pre_instructions` data** (before ALTER): For each row where `pre_instructions IS NOT NULL`, execute:
   ```sql
   UPDATE treatment_types
   SET pre_instructions = jsonb_build_object('general_notes', pre_instructions)
   WHERE pre_instructions IS NOT NULL;
   ```
   This runs while the column is still TEXT, so the cast to text is implicit.

2. **ALTER COLUMN TYPE**: `ALTER TABLE treatment_types ALTER COLUMN pre_instructions TYPE JSONB USING pre_instructions::jsonb;`

3. **Transform `post_instructions` legacy list data**: For each row where `post_instructions IS NOT NULL` and `jsonb_typeof(post_instructions) = 'array'`:
   ```sql
   UPDATE treatment_types
   SET post_instructions = jsonb_build_object('general_notes', post_instructions::text)
   WHERE post_instructions IS NOT NULL
     AND jsonb_typeof(post_instructions) = 'array';
   ```
   This preserves the original list as a JSON string in `general_notes`, readable by both the old tool logic and the new formatter.

### 2.2 Downgrade

1. **Restore `post_instructions` list rows**: For each row where `post_instructions` is a JSONB object with `general_notes` key whose value parses as a JSON array, restore the original array:
   ```sql
   UPDATE treatment_types
   SET post_instructions = (post_instructions->>'general_notes')::jsonb
   WHERE post_instructions IS NOT NULL
     AND jsonb_typeof(post_instructions) = 'object'
     AND post_instructions ? 'general_notes'
     AND jsonb_typeof((post_instructions->>'general_notes')::jsonb) = 'array';
   ```

2. **ALTER COLUMN TYPE back to TEXT**:
   ```sql
   ALTER TABLE treatment_types ALTER COLUMN pre_instructions TYPE TEXT USING (pre_instructions->>'general_notes');
   ```
   This extracts `general_notes` back to plain text. Any structured keys added by the new UI are dropped on downgrade (acceptable — downgrade is emergency rollback).

### 2.3 Idempotency

The migration MUST use idempotency guards consistent with project style (check `_column_exists` or use `IF NOT EXISTS`). The migration MUST be safe to run on a DB where `pre_instructions` is already JSONB (e.g., after a partial failure).

Revision ID: `038`, Down-revision: `037`.

---

## SPEC 3 — Pydantic Schemas (`admin_routes.py`)

### 3.1 New Nested Models

```python
class PreInstructions(BaseModel):
    preparation_days_before: Optional[int] = None
    fasting_required: Optional[bool] = None
    fasting_hours: Optional[int] = None
    medications_to_avoid: Optional[List[str]] = []
    medications_to_take: Optional[List[str]] = []
    what_to_bring: Optional[List[str]] = []
    general_notes: Optional[str] = None

class PostInstructions(BaseModel):
    care_duration_days: Optional[int] = None
    dietary_restrictions: Optional[List[str]] = []
    activity_restrictions: Optional[List[str]] = []
    allowed_medications: Optional[List[str]] = []
    prohibited_medications: Optional[List[str]] = []
    sutures_removal_day: Optional[int] = None
    normal_symptoms: Optional[List[str]] = []
    alarm_symptoms: Optional[List[str]] = []
    escalation_message: Optional[str] = None
```

### 3.2 Request Schema Changes

In `TreatmentCreateRequest`, `TreatmentUpdateRequest`, `TreatmentPatchRequest`:

- `pre_instructions: Optional[Union[PreInstructions, str, dict]] = None`
- `post_instructions: Optional[Union[PostInstructions, list, dict, str]] = None`

The backend MUST coerce incoming data:
- If `pre_instructions` is a `str` → wrap as `PreInstructions(general_notes=value)` before storing.
- If `post_instructions` is a `list` → store as-is (legacy timed sequence, still valid).
- If `post_instructions` is a `dict` → validate as `PostInstructions` shape.

### 3.3 Validation Updates

`_validate_treatment_instruction_fields()` (currently at `admin_routes.py:8444`) MUST be updated:
- Remove the `isinstance(post_instructions, list)` check that rejects non-list values (since the new shape is a dict).
- Add optional validation: if `post_instructions` is a dict, check that `care_duration_days`, if present, is a positive integer.
- Keep the `pre_instructions` length check (2000 chars) for backward compat — apply it to `general_notes` if input is a dict.

---

## SPEC 4 — `get_treatment_instructions` Tool Enhancement

The tool (`main.py:6032`) MUST be updated to handle the new shape while preserving backward compat with the legacy list shape.

### 4.1 Pre-Instructions Formatting

When `pre_instructions` is a dict (new shape):

```
PRE-TRATAMIENTO — {treatment_name}:
• Preparacion: llegar con X dias de anticipacion. [if preparation_days_before]
• Ayuno: [SI, X horas | NO requerido | No especificado]
• Medicamentos a evitar: [list or "ninguno especificado"]
• Medicamentos a tomar: [list or omit if empty]
• Traer: [list or omit if empty]
• Notas: [general_notes or omit]
```

When `pre_instructions` is a plain string (legacy TEXT, now wrapped in `{"general_notes": "..."}`): format as before (raw text injection, prefixed with `INSTRUCCIONES PRE-TRATAMIENTO:`).

### 4.2 Post-Instructions Formatting

When `post_instructions` is a dict (new shape):

```
POST-TRATAMIENTO — {treatment_name}:
Periodo de cuidado: X dias.

DIETA: [list items | "sin restricciones especificadas"]
ACTIVIDAD FISICA: [list items | omit if empty]
MEDICACION PERMITIDA: [list items | omit if empty]
MEDICACION PROHIBIDA: [list items | omit if empty]
PUNTOS: retiro al dia X. [if sutures_removal_day]

SINTOMAS NORMALES (esperados):
[list items | omit section if empty]

SINTOMAS DE ALARMA (requieren atencion medica):
[list items | omit section if empty]

[escalation_message if present]
```

When `post_instructions` is a list (legacy timed sequence): use existing timing-label renderer (unchanged).

When `post_instructions` is NULL or the treatment does not exist: return EXACTLY:
`"Este tratamiento no tiene cuidados configurados. Te recomiendo contactar directamente a la clínica para más indicaciones."`
NEVER improvise medical advice. NEVER say "según lo que sé en general...".

### 4.3 Alarm Symptom Detection

When `timing` is `"post"` or `"all"` AND `alarm_symptoms` list is non-empty:

The tool response MUST append an internal escalation hint wrapped in a tag that the system prompt instructs the agent to act upon:

```
[ALARM_ESCALATION: Si el paciente describe alguno de los síntomas de alarma de arriba, llamá derivhumano INMEDIATAMENTE con urgencia=alta. No preguntes más, actúa.]
```

The system prompt `INSTRUCCIONES DE TRATAMIENTO` block MUST instruct the agent:
- If the tool response contains `[ALARM_ESCALATION:...]` AND the patient's message contains any of the alarm symptoms listed → call `derivhumano` with `urgency="alta"` before responding.
- The patient-facing message before `derivhumano` MUST use `escalation_message` if present, otherwise the default: "Lo que describís requiere atención médica. Estoy derivándote con la clínica ahora."

### 4.4 Care Duration Window Check

The tool MUST attempt to detect if the patient has a recent appointment for this treatment within `care_duration_days` using `current_customer_phone.get()`. If yes, inject the post-instructions context. If `care_duration_days` is NULL, inject unconditionally (no window check). If the phone lookup fails or no appointment is found, still inject instructions (fail-safe: better to over-inform than under-inform).

---

## SPEC 5 — System Prompt Update

The existing block at `main.py:~7159`:

```
INSTRUCCIONES DE TRATAMIENTO (POST-AGENDAMIENTO):
• Después de confirmar un turno con book_appointment, llamá get_treatment_instructions(treatment_code, 'pre').
• Si hay instrucciones pre-tratamiento → incluílas en el mensaje de confirmación.
• Si el paciente pregunta por cuidados post-operatorios → llamá get_treatment_instructions(treatment_code, 'post').
• NUNCA inventes instrucciones médicas. Solo usá las del catálogo configurado.
```

MUST be extended with:

```
• Si la respuesta de get_treatment_instructions contiene [ALARM_ESCALATION:...] Y el paciente describió síntomas → llamá derivhumano(urgency="alta") ANTES de responder. Usá el escalation_message del protocolo si está disponible.
• Si get_treatment_instructions devuelve "Este tratamiento no tiene cuidados configurados" → NO improvises. Repetí esa frase al paciente y ofrecé derivar a la clínica.
```

---

## SPEC 6 — Frontend Modal Enhancement (`TreatmentsView.tsx`)

### 6.1 Legal Disclaimer Banner

At the top of the Instructions modal body (before Section 1), add a non-dismissible banner:

```
Aviso: Los protocolos configurados aquí son informativos y específicos de esta clínica.
No constituyen consejo médico profesional para el paciente.
```

Style: `bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs rounded-xl px-4 py-2`.

### 6.2 `StringListEditor` Component

A new internal component (can be defined inline in `TreatmentsView.tsx` or as a separate file):

```tsx
interface StringListEditorProps {
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
  placeholder?: string;
}
```

Renders: a list of text inputs with remove buttons + an "Agregar" button. Minimum height: 1 row always visible. Used for all `string[]` fields in `PreInstructions` and `PostInstructions`.

### 6.3 Pre-Instructions Section Redesign

Section 1 (currently a plain `<textarea>`) MUST become two collapsible sub-sections:

**Sub-section A — "Preparación general" (structured fields)**:
- `preparation_days_before`: number input, label "Días de preparación previos"
- `fasting_required`: toggle/checkbox, label "¿Requiere ayuno?"
- `fasting_hours`: number input, shown only when `fasting_required = true`, label "Horas de ayuno"
- `medications_to_avoid`: `StringListEditor`, label "Medicamentos a evitar"
- `medications_to_take`: `StringListEditor`, label "Medicamentos a tomar"
- `what_to_bring`: `StringListEditor`, label "Qué traer"
- `general_notes`: small `<textarea>` (4 rows), label "Notas adicionales"

**Sub-section B — "Datos en formato anterior" (legacy)**:
- Visible only when `pre_instructions` loaded from DB is a plain string (not yet migrated).
- Shows a read-only textarea with the original text.
- Shows a "Migrar al formato estructurado" button: on click, populates `general_notes` with the original text and hides Sub-section B.

### 6.4 Post-Instructions Section Redesign

Section 2 becomes two collapsible tabs or panels:

**Panel A — "Protocolo de recuperación" (new structured fields)**:
- `care_duration_days`: number input, label "Días de cuidado post-operatorio"
- `dietary_restrictions`: `StringListEditor`, label "Restricciones alimentarias"
- `activity_restrictions`: `StringListEditor`, label "Restricciones de actividad física"
- `allowed_medications`: `StringListEditor`, label "Medicación permitida"
- `prohibited_medications`: `StringListEditor`, label "Medicación prohibida"
- `sutures_removal_day`: number input, label "Día de retiro de puntos (si aplica)"
- `normal_symptoms`: `StringListEditor`, label "Síntomas normales (tranquilizadores)"
- `alarm_symptoms`: `StringListEditor`, label "Síntomas de alarma (requieren derivación urgente)", input styled with red accent when non-empty
- `escalation_message`: `<textarea>` (2 rows), label "Mensaje de escalación de emergencia"

**Panel B — "Secuencia de seguimiento programado" (existing timed list)**:
Identical to the current Section 2 implementation (timing + content + book_followup). Preserved exactly.

### 6.5 Form State Separation

The modal state MUST separate structured fields from legacy timed fields:
- `preInstructions: PreInstructionsForm` — maps to `PreInstructions` shape
- `postInstructions: PostInstructionsForm` — maps to `PostInstructions` shape
- `timedSequence: PostInstruction[]` — existing list, stored in `post_instructions` only when `PostInstructions` shape is empty/null

On save: if `postInstructions` has any non-empty field → send `post_instructions` as a dict. If only `timedSequence` has entries (legacy mode) → send `post_instructions` as list. If both → dict takes precedence (timedSequence is migrated to `general_notes`).

---

## SPEC 7 — Acceptance Criteria (Gherkin)

### AC-1: Patient with recent extraction asks about bleeding

```gherkin
Given a patient had an appointment for treatment_code="EXTRACCION" 2 days ago
And "EXTRACCION" has post_instructions.normal_symptoms = ["Ligero sangrado las primeras 24h"]
And post_instructions.alarm_symptoms = ["Sangrado abundante que no cede después de 30 min"]
And post_instructions.care_duration_days = 7
When the patient sends "me sigue sangrando bastante"
Then the agent calls get_treatment_instructions("EXTRACCION", "post")
And the tool response contains [ALARM_ESCALATION:...]
And the agent calls derivhumano with urgency="alta"
And the agent does NOT improvise additional advice
```

### AC-2: Patient asks about diet after extraction

```gherkin
Given "EXTRACCION" has post_instructions.dietary_restrictions = ["No comer caliente por 24h", "No alcohol por 72h"]
When the patient sends "¿qué puedo comer después?"
Then the agent calls get_treatment_instructions("EXTRACCION", "post")
And the response contains "No comer caliente por 24h"
And the response contains "No alcohol por 72h"
And the agent does NOT invent dietary advice beyond what is in the protocol
```

### AC-3: Pre-op fasting query for implant treatment

```gherkin
Given "IMPLANTE" has pre_instructions.fasting_required = true and pre_instructions.fasting_hours = 6
When the patient asks "¿tengo que ayunar para el implante?"
Then the agent calls get_treatment_instructions("IMPLANTE", "pre")
And the response contains "Ayuno: SI, 6 horas"
And the agent answers based on this data without improvising
```

### AC-4: Patient describes alarm symptom → immediate escalation

```gherkin
Given "EXTRACCION" has alarm_symptoms = ["Fiebre mayor a 38.5°C"]
And the patient sends "tengo fiebre de 39 desde ayer"
When the agent calls get_treatment_instructions("EXTRACCION", "post")
Then the tool response contains [ALARM_ESCALATION:...]
And the agent calls derivhumano BEFORE sending any advisory message
```

### AC-5: Treatment without configured instructions → no improvisation

```gherkin
Given "LIMPIEZA" has post_instructions = NULL
When the patient asks "¿qué cuidados tengo que tener después de la limpieza?"
Then the agent calls get_treatment_instructions("LIMPIEZA", "post")
And the tool returns "Este tratamiento no tiene cuidados configurados. Te recomiendo contactar directamente a la clínica para más indicaciones."
And the agent relays this message verbatim
And the agent does NOT add improvised advice
```
