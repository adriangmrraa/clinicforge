# Spec: Digital Patient Record
**Change**: `digital-patient-record`
**Status**: approved
**Date**: 2026-03-31

---

## 1. Data Model

### 1.1 Table: `patient_digital_records`

```sql
CREATE TABLE patient_digital_records (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    patient_id    INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    created_by    UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Document identity
    template_type VARCHAR(30) NOT NULL,
    title         TEXT NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'draft',

    -- Data layer (Layer 1 output — source of truth)
    source_data   JSONB NOT NULL DEFAULT '{}',

    -- AI layer (Layer 2 output — narrative text only)
    ai_content    JSONB NOT NULL DEFAULT '{}',

    -- Assembled HTML (Layer 3 output — Jinja2 rendered)
    html_content  TEXT,

    -- PDF artifact
    pdf_path      TEXT,
    pdf_size      INTEGER,
    pdf_generated_at TIMESTAMPTZ,

    -- Edit history
    edit_history  JSONB NOT NULL DEFAULT '[]',

    -- AI generation metadata (anti-hallucination audit trail)
    generation_metadata JSONB NOT NULL DEFAULT '{}',

    -- Email delivery log
    last_sent_to  TEXT,
    last_sent_at  TIMESTAMPTZ,
    send_count    INTEGER NOT NULL DEFAULT 0,

    -- Audit
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Constraints:**

```sql
ALTER TABLE patient_digital_records
  ADD CONSTRAINT ck_pdr_template_type
    CHECK (template_type IN (
      'clinical_report',
      'post_surgery',
      'odontogram_art',
      'authorization_request'
    ));

ALTER TABLE patient_digital_records
  ADD CONSTRAINT ck_pdr_status
    CHECK (status IN ('draft', 'final', 'sent', 'archived'));
```

**Indexes:**

```sql
CREATE INDEX idx_pdr_tenant         ON patient_digital_records (tenant_id);
CREATE INDEX idx_pdr_patient        ON patient_digital_records (patient_id);
CREATE INDEX idx_pdr_tenant_patient ON patient_digital_records (tenant_id, patient_id);
CREATE INDEX idx_pdr_status         ON patient_digital_records (status);
CREATE INDEX idx_pdr_created_at     ON patient_digital_records (created_at DESC);
CREATE INDEX idx_pdr_template_type  ON patient_digital_records (template_type);
```

**Column semantics:**

| Column | Description |
|--------|-------------|
| `source_data` | Raw data collected from DB in Layer 1 (patient, appointments, clinical records, anamnesis, tenant). NEVER modified after generation. |
| `ai_content` | JSON object with one key per AI-generated narrative field. Keys match template section names. |
| `html_content` | Final Jinja2-assembled HTML. Regenerated on every edit. |
| `pdf_path` | Relative path under `/app/uploads/patients/{tenant_id}/{patient_id}/records/` |
| `edit_history` | Array of `{timestamp, field, old_value, new_value, edited_by}`. Append-only. |
| `generation_metadata` | `{model, prompt_tokens, completion_tokens, generated_at, validation_passed, null_fields, hallucination_flags}` |

---

### 1.2 SQLAlchemy ORM Class

File: `orchestrator_service/models.py`

```python
class PatientDigitalRecord(Base):
    __tablename__ = 'patient_digital_records'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    patient_id = Column(Integer, ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    template_type = Column(String(30), nullable=False)
    title = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default='draft')
    source_data = Column(JSONB, nullable=False, default={})
    ai_content = Column(JSONB, nullable=False, default={})
    html_content = Column(Text)
    pdf_path = Column(Text)
    pdf_size = Column(Integer)
    pdf_generated_at = Column(DateTime(timezone=True))
    edit_history = Column(JSONB, nullable=False, default=[])
    generation_metadata = Column(JSONB, nullable=False, default={})
    last_sent_to = Column(Text)
    last_sent_at = Column(DateTime(timezone=True))
    send_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "template_type IN ('clinical_report','post_surgery','odontogram_art','authorization_request')",
            name='ck_pdr_template_type'
        ),
        CheckConstraint(
            "status IN ('draft','final','sent','archived')",
            name='ck_pdr_status'
        ),
        Index('idx_pdr_tenant', 'tenant_id'),
        Index('idx_pdr_patient', 'patient_id'),
        Index('idx_pdr_tenant_patient', 'tenant_id', 'patient_id'),
        Index('idx_pdr_status', 'status'),
        Index('idx_pdr_created_at', created_at.desc()),
        Index('idx_pdr_template_type', 'template_type'),
    )
```

---

### 1.3 Alembic Migration

**Number**: 013 (next after 012)
**File**: `orchestrator_service/alembic/versions/013_add_patient_digital_records.py`

```python
"""add patient_digital_records table

Revision ID: 013
Revises: 012
Create Date: 2026-03-31
"""
revision = 'r3s4t5u6v7w8'
down_revision = 'q2r3s4t5u6v7'
```

The migration MUST include both `upgrade()` and `downgrade()`. The `upgrade()` MUST use `_table_exists()` guard before creating the table. The `downgrade()` MUST drop the table in reverse order.

---

## 2. API Endpoints

All endpoints MUST:
- Be registered in `orchestrator_service/admin_routes.py` under prefix `/admin`
- Use `Depends(verify_admin_token)` for auth
- Extract `tenant_id` from the authenticated user JWT, NEVER from request params
- Return consistent JSON responses with `{"success": bool, "data": ..., "error": str|null}`

### 2.1 List Records

```
GET /admin/patients/{patient_id}/digital-records
```

**Query params**: `template_type?: string`, `status?: string`, `limit?: int = 20`, `offset?: int = 0`

**Response 200**:
```json
{
  "records": [
    {
      "id": "uuid",
      "template_type": "clinical_report",
      "title": "Informe Clínico — Juan Pérez — 2026-03-31",
      "status": "final",
      "created_at": "2026-03-31T10:00:00Z",
      "updated_at": "2026-03-31T10:05:00Z",
      "pdf_path": "/admin/patients/42/digital-records/uuid/pdf",
      "last_sent_to": "juan@example.com",
      "last_sent_at": "2026-03-31T10:10:00Z"
    }
  ],
  "total": 3
}
```

**Scenario**:
- Given a valid JWT with tenant A and patient_id belonging to tenant A
- When GET is called
- Then ONLY records where `tenant_id = JWT.tenant_id AND patient_id = {patient_id}` are returned

---

### 2.2 Get Record Detail

```
GET /admin/patients/{patient_id}/digital-records/{record_id}
```

**Response 200**: Full record including `source_data`, `ai_content`, `html_content`, `edit_history`

**Response 404**: `{"error": "record_not_found"}` if `record_id` does not exist or belongs to a different tenant

---

### 2.3 Generate New Record

```
POST /admin/patients/{patient_id}/digital-records/generate
```

**Request body**:
```json
{
  "template_type": "clinical_report",
  "language": "es"
}
```

`template_type` MUST be one of: `clinical_report`, `post_surgery`, `odontogram_art`, `authorization_request`
`language` MUST be one of: `es`, `en`, `fr`. Defaults to `es`.

**Response 201**:
```json
{
  "record": { ...full record object... },
  "validation_warnings": ["field_x was null, placeholder used"]
}
```

**Response 422**: `{"error": "invalid_template_type"}`

**Scenarios**:
- Given a valid request for `clinical_report`
- When the endpoint is called
- Then Layer 1 runs (data gathering), Layer 2 runs (AI narrative), Layer 3 runs (Jinja2 assembly), record saved with status `draft`
- And `validation_warnings` lists every field that fell back to a placeholder

- Given a patient with no clinical records
- When `post_surgery` is requested
- Then `source_data.clinical_records` is `[]`, Layer 2 generates narrative from empty context, post-generation validation flags the record

---

### 2.4 Update / Edit Record

```
PATCH /admin/patients/{patient_id}/digital-records/{record_id}
```

**Request body** (all optional, at least one required):
```json
{
  "title": "string",
  "ai_content": { "section_key": "new text" },
  "status": "final"
}
```

**Behavior**:
- MUST append to `edit_history` for every changed field
- MUST regenerate `html_content` after content changes
- MUST NOT regenerate `source_data` (source data is immutable after generation)
- MUST NOT set `status = final` if any hallucination flags exist in `generation_metadata`

**Response 200**: Updated record

---

### 2.5 Regenerate AI Section

```
POST /admin/patients/{patient_id}/digital-records/{record_id}/regenerate
```

**Request body**:
```json
{
  "section_key": "clinical_summary",
  "instruction": "Make it more formal"
}
```

**Behavior**:
- Reruns Layer 2 ONLY for the specified section
- Uses the SAME `source_data` (no DB re-query)
- Updates `ai_content[section_key]`
- Appends to `edit_history`
- Regenerates `html_content`
- MUST NOT alter `source_data`

**Response 200**: Updated record

---

### 2.6 Download PDF

```
GET /admin/patients/{patient_id}/digital-records/{record_id}/pdf
```

**Behavior**:
- If `pdf_path` exists and `pdf_generated_at > updated_at`, serve cached file
- If stale or missing, regenerate with WeasyPrint from current `html_content`
- Returns `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="{title}.pdf"`

**Response 200**: Binary PDF stream

**Response 404**: `{"error": "record_not_found"}`

---

### 2.7 Send via Email

```
POST /admin/patients/{patient_id}/digital-records/{record_id}/send-email
```

**Request body**:
```json
{
  "to_email": "doctor@clinic.com"
}
```

**Behavior**:
- Generates PDF if not cached
- Calls `email_service.send_digital_record_email()`
- Updates `last_sent_to`, `last_sent_at`, increments `send_count`
- Updates `status` to `sent` if it was `final`

**Response 200**: `{"sent": true, "to_email": "doctor@clinic.com"}`

**Response 422**: `{"error": "invalid_email"}`

**Response 500**: `{"error": "smtp_send_failed", "detail": "..."}`

---

### 2.8 Delete Record

```
DELETE /admin/patients/{patient_id}/digital-records/{record_id}
```

**Behavior**:
- Soft delete: SHOULD set `status = archived` instead of hard deletion
- Hard delete: MAY be implemented as separate endpoint for admin cleanup
- If `pdf_path` is set, SHOULD delete the file from disk

**Response 200**: `{"deleted": true}`

---

## 3. AI Generation Pipeline

### 3.1 Layer 1 — Data Gathering (Pure Python, NO AI)

**Rule**: Layer 1 MUST NEVER call OpenAI. It MUST return a fully typed dict. Every field that has no data MUST be explicitly set to `null` or `[]` or `{}`. No implicit None-to-string coercion.

#### Common data for all template types:

```python
{
  "patient": {
    "id": int,
    "first_name": str | null,
    "last_name": str | null,
    "full_name": str,          # "{first_name} {last_name}".strip()
    "birth_date": str | null,  # ISO date string
    "age_years": int | null,   # calculated, null if birth_date is null
    "gender": str | null,
    "dni": str | null,
    "phone_number": str,
    "email": str | null,
    "insurance_provider": str | null,
    "insurance_id": str | null,
    "insurance_valid_until": str | null,
    "city": str | null,
    "status": str,
    "created_at": str,         # ISO datetime
    "urgency_level": str
  },
  "tenant": {
    "clinic_name": str,
    "address": str | null,
    "phone": str | null,
    "country_code": str,
    "timezone": str
  },
  "language": str              # "es" | "en" | "fr"
}
```

#### `clinical_report` — additional data:

```python
{
  "anamnesis": {
    "completed": bool,
    "completed_at": str | null,
    "base_diseases": str | null,
    "habitual_medication": str | null,
    "allergies": str | null,
    "previous_surgeries": str | null,
    "is_smoker": bool | null,
    "is_pregnant": bool | null,
    "has_pacemaker": bool | null,
    "blood_pressure_issues": bool | null,
    "diabetes": bool | null,
    "heart_condition": bool | null,
    "bleeding_disorder": bool | null,
    "dental_anxiety_level": str | null,
    "last_dental_visit": str | null,
    "main_concern": str | null,
    "additional_notes": str | null
  },
  "clinical_records": [
    {
      "id": str,               # UUID as string
      "record_date": str,      # ISO date
      "professional_name": str | null,
      "diagnosis": str | null,
      "clinical_notes": str | null,
      "recommendations": str | null,
      "treatments": list       # raw JSONB
    }
  ],                           # ordered by record_date DESC, max 20 records
  "appointments": {
    "total_count": int,
    "completed_count": int,
    "upcoming": [
      {
        "datetime": str,
        "appointment_type": str,
        "professional_name": str | null,
        "status": str
      }
    ],                         # max 3 upcoming
    "last_completed": str | null  # ISO datetime of last completed appointment
  }
}
```

#### `post_surgery` — additional data:

Same as `clinical_report` plus:
```python
{
  "surgery_record": {
    "id": str | null,          # UUID of most recent clinical record
    "record_date": str | null,
    "procedure_description": str | null,  # clinical_notes
    "diagnosis": str | null,
    "professional_name": str | null,
    "recommendations": str | null
  }
  # If no clinical records exist, surgery_record has all null fields
}
```

#### `odontogram_art` — additional data:

```python
{
  "odontogram": {
    "version": str | null,     # "2.0" or "legacy"
    "teeth": [
      {
        "fdi": int,            # FDI tooth number (11-48)
        "status": str,         # one of 10 statuses (see section 5)
        "surfaces": {
          "vestibular": str | null,
          "palatino": str | null,
          "mesial": str | null,
          "distal": str | null,
          "oclusal": str | null
        } | null
      }
    ],
    "has_data": bool,          # false if odontogram is empty
    "record_date": str | null,
    "professional_name": str | null
  }
}
```

The data gatherer MUST normalize both legacy and v2 odontogram formats into the unified `teeth` array. Legacy format `{tooth_number: {status, surface}}` MUST be converted to FDI notation.

#### `authorization_request` — additional data:

Same as `clinical_report` anamnesis plus:
```python
{
  "requesting_professional": {
    "full_name": str | null,
    "specialty": str | null,
    "registration_id": str | null,
    "email": str | null
  },
  "authorization_target": {
    # Injected from request body at generation time
    "procedure_name": str,
    "procedure_code": str | null,
    "insurance_name": str | null,
    "estimated_sessions": int | null,
    "clinical_justification_hint": str | null  # optional user-provided hint
  }
}
```

---

### 3.2 Layer 2 — AI Narrative (OpenAI, constrained)

**File**: `orchestrator_service/services/digital_record_service.py`

#### System Prompt (exact rules):

```
You are a medical document writer for a dental clinic software system.
Your ONLY job is to write the narrative text sections for a patient record.

CRITICAL RULES — ZERO TOLERANCE:
1. You MUST use ONLY data from the JSON provided. NEVER invent, assume, or extrapolate clinical data.
2. If a field in the JSON is null, you MUST use the placeholder format: [NO DATA: field_name]
3. NEVER write a specific diagnosis, treatment, procedure, or medication that is not explicitly present in the source_data JSON.
4. NEVER use phrases like "the patient likely", "probably", "may have", "appears to" regarding clinical facts.
5. NEVER fill in patient vitals, lab values, or clinical measurements not in the source_data.
6. Date references MUST come from the JSON. NEVER use today's date as a clinical date.
7. Write in {language}. Formal, professional, third-person voice.
8. Return a JSON object. ONLY narrative text values. NEVER include source_data fields directly.
9. Each narrative section MUST include only what the data supports. Shorter is safer than speculative.
10. If source_data.clinical_records is [] (empty), you MUST say so explicitly in the narrative. NEVER invent past consultations.

SELF-CHECK before returning:
- Does every clinical claim have a corresponding source_data field?
- Are all null fields replaced with [NO DATA: ...] placeholders?
- Is there any invented data? If yes, remove it.
```

#### Per-template prompt instructions:

**`clinical_report`**: Generate these sections only:
- `clinical_summary`: 2–4 sentence overview of the patient's health context based on anamnesis and clinical history. Use [NO DATA] for any missing field.
- `anamnesis_narrative`: Prose description of the anamnesis findings. Explicitly state "No anamnesis completada" if `anamnesis.completed` is false.
- `treatment_history_narrative`: Summary of past clinical records. If `clinical_records` is empty, write "Sin registros clínicos en el sistema."
- `recommendations_summary`: Consolidate all `recommendations` fields across clinical records. If none, write "Sin recomendaciones registradas."

**`post_surgery`**: Generate:
- `procedure_narrative`: Describe the procedure from `surgery_record.procedure_description`. If null, use [NO DATA: procedure_description].
- `post_op_instructions_narrative`: Write post-operative care instructions based ONLY on `surgery_record.recommendations`. If null, write "Sin indicaciones registradas."
- `follow_up_narrative`: Reference upcoming appointments if any. Otherwise "Sin turnos de control programados."

**`odontogram_art`**: Generate:
- `odontogram_findings_narrative`: Textual description of the odontogram state, listing statuses found. If `odontogram.has_data` is false, write "Sin odontograma registrado."
- `treatment_priorities_narrative`: Based ONLY on the statuses present, describe urgency levels. MUST NOT add clinical judgement beyond status names.

**`authorization_request`**: Generate:
- `clinical_justification`: Formal paragraph justifying the requested procedure based on `authorization_target.clinical_justification_hint` + relevant anamnesis fields. If hint is null, write from anamnesis only. If anamnesis is also incomplete, state "Justificación pendiente de completar por el profesional."
- `patient_background`: 2-sentence patient background for the insurer. From anamnesis + clinical records.

#### AI call parameters:
- Model: `gpt-4o-mini` (default) or value from `system_config` table key `MODEL_DIGITAL_RECORDS`
- Temperature: `0.3` (low for consistency)
- Max tokens: `1200`
- Response format: `{"type": "json_object"}`

---

### 3.3 Post-Generation Validation

After Layer 2 returns, the service MUST run these checks:

```python
VALIDATION_RULES = [
    # Check 1: No forbidden speculative phrases
    {
        "type": "regex_forbidden",
        "patterns": [
            r"probablemente", r"parece que", r"podría tener",
            r"likely", r"probably", r"may have", r"appears to",
            r"sugiere que el paciente"
        ],
        "severity": "error"
    },
    # Check 2: Placeholder integrity — if source null, placeholder must exist
    {
        "type": "placeholder_check",
        "severity": "warning"
    },
    # Check 3: No invented dates (any date string not present in source_data)
    {
        "type": "date_origin_check",
        "severity": "error"
    },
    # Check 4: Empty records honest statement
    {
        "type": "empty_records_honesty",
        "severity": "error"
    }
]
```

If any `error`-severity check fails:
- `generation_metadata.hallucination_flags` is set with details
- `status` remains `draft`
- Response includes `validation_warnings`
- The record is saved but MUST NOT be promotable to `final` while flags exist

If only `warning`-severity issues:
- `generation_metadata.validation_passed = true` with note
- `status` = `draft` (user can promote to `final`)

---

### 3.4 Placeholder System

When source data is null, Layer 2 is instructed to produce `[NO DATA: field_name]`.

The Jinja2 template MUST render these placeholders as styled spans:
```html
<span class="pdr-placeholder">[NO DATA: field_name]</span>
```

In print CSS: `pdr-placeholder` renders with a dotted underline and light grey color, making missing data visible in the PDF.

---

## 4. Template Types

### 4.1 Common HTML Structure

All templates MUST include:
1. **Header block**: Clinic logo (if `tenant.logo_url` exists), clinic name, address, generated date
2. **Patient identity block**: Name, DOB, age, DNI, insurance, phone, email
3. **Document metadata footer**: Document type, generation date, professional (if applicable), document ID (UUID)
4. **Print watermark**: "DOCUMENTO CLÍNICO — {clinic_name}" in light grey diagonal text

### 4.2 Template: `clinical_report`

**Title format**: `"Informe Clínico — {patient.full_name} — {date}"`

**Sections** (in order):

| Section | Data source | Description |
|---------|-------------|-------------|
| Patient header | JSON direct | Identity block |
| Critical alerts | JSON direct | Anamnesis flags: is_smoker, has_pacemaker, diabetes, heart_condition, bleeding_disorder, is_pregnant. Rendered as coloured alert badges. |
| Medical antecedents | JSON direct (raw fields) | Table: diseases, medications, allergies, surgeries |
| Clinical summary | AI narrative | `ai_content.clinical_summary` |
| Treatment history | JSON direct (table) + AI narrative | List of clinical records as table, then `ai_content.treatment_history_narrative` |
| Anamnesis detail | JSON direct | Formatted table of all anamnesis fields present |
| Recommendations | AI narrative | `ai_content.recommendations_summary` |
| Upcoming appointments | JSON direct | Table of up to 3 upcoming appointments |

**Rule**: Every data cell in tables MUST come from `source_data` JSON directly, NOT from AI narrative. AI narrative is only allowed in the "narrative" subsections.

---

### 4.3 Template: `post_surgery`

**Title format**: `"Indicaciones Post-Operatorias — {patient.full_name} — {date}"`

**Sections**:

| Section | Data source | Description |
|---------|-------------|-------------|
| Patient header | JSON direct | Identity block |
| Procedure | JSON direct (surgery_record) + AI narrative | Date, professional, procedure (from clinical_notes). `ai_content.procedure_narrative` below. |
| Post-op instructions | AI narrative | `ai_content.post_op_instructions_narrative` |
| Critical alerts | JSON direct | Allergy and medication alerts relevant to post-op |
| Follow-up | JSON direct (appointments) + AI narrative | Next appointment if any, plus `ai_content.follow_up_narrative` |
| Emergency contact | JSON direct | Clinic phone, address |
| Signature block | JSON direct | Professional name, registration_id, date |

---

### 4.4 Template: `odontogram_art`

**Title format**: `"Odontograma — {patient.full_name} — {date}"`

**Sections**:

| Section | Data source | Description |
|---------|-------------|-------------|
| Patient header | JSON direct | Identity block |
| Odontogram SVG | Server-side SVG (see 4.4.1) | Full 32-tooth FDI grid |
| Status legend | JSON direct | Color key for each status present |
| Findings narrative | AI narrative | `ai_content.odontogram_findings_narrative` |
| Treatment priorities | AI narrative | `ai_content.treatment_priorities_narrative` |
| Professional sign-off | JSON direct | Professional name + date |

#### 4.4.1 Odontogram SVG Spec

The SVG MUST replicate the React `ToothSVG` component's visual output adapted for print (white background).

**Color mapping** (print-adapted, same semantic colors as UI but on white bg):

| Status | UI color (dark bg) | Print color (white bg) | Fill | Border |
|--------|-------------------|----------------------|------|--------|
| `sano` | green-500 | #16a34a | transparent | #16a34a |
| `caries` | red-500 | #dc2626 | #fecaca | #dc2626 |
| `obturado` | blue-400 | #2563eb | #dbeafe | #2563eb |
| `corona` | yellow-400 | #ca8a04 | #fef9c3 | #ca8a04 |
| `ausente` | gray-500 | #6b7280 | #f3f4f6 | #6b7280 |
| `extraccion` | orange-500 | #ea580c | #ffedd5 | #ea580c |
| `implante` | purple-500 | #7c3aed | #ede9fe | #7c3aed |
| `fractura` | red-700 | #b91c1c | #fee2e2 | #b91c1c |
| `endodoncia` | teal-400 | #0d9488 | #ccfbf1 | #0d9488 |
| `movilidad` | pink-400 | #db2777 | #fce7f3 | #db2777 |

**FDI Layout** (2 rows × 2 quadrants):
- Row 1: Upper arch — quadrant 1 (18→11, right to left) | quadrant 2 (21→28, left to right)
- Row 2: Lower arch — quadrant 4 (48→41, right to left) | quadrant 3 (31→38, left to right)

**Tooth SVG shape**: Simplified rounded rectangle (40×50px per tooth) with:
- 5 surface triangles (vestibular=top, palatino=bottom, mesial=left, distal=right, oclusal=center circle)
- FDI number below each tooth (10px sans-serif, centered)
- Grid spacing: 44px per tooth, 60px row height
- Total SVG size: approx 800×160px

**SVG generation**: Python function `generate_odontogram_svg(teeth: list[dict]) -> str` in `digital_record_service.py`. MUST use pure SVG (no external dependencies). Tooth coordinates calculated programmatically from FDI number.

**If `odontogram.has_data` is false**: Render the full 32-tooth grid with all teeth in `sano` (empty/outline) state, with a text overlay: "Sin odontograma registrado".

---

### 4.5 Template: `authorization_request`

**Title format**: `"Solicitud de Autorización — {procedure_name} — {patient.full_name}"`

**Sections**:

| Section | Data source | Description |
|---------|-------------|-------------|
| Insurance header | JSON direct | Insurer name (or placeholder), date, policy ID |
| Patient identity | JSON direct | Full identity block |
| Requesting professional | JSON direct | Name, specialty, registration_id |
| Procedure requested | JSON direct | Procedure name, code, estimated sessions |
| Clinical justification | AI narrative | `ai_content.clinical_justification` |
| Patient background | AI narrative | `ai_content.patient_background` |
| Supporting anamnesis | JSON direct | Table of relevant medical conditions |
| Signature block | JSON direct | Professional name, registration_id, date, signature line |

---

## 5. Frontend

### 5.1 New Tab in PatientDetail

File: `frontend_react/src/views/PatientDetail.tsx`

**TabType**: extend to `'summary' | 'history' | 'documents' | 'anamnesis' | 'digital_records'`

**Tab button** (added after anamnesis tab):
```tsx
<button onClick={() => setActiveTab('digital_records')} ...>
  <FileText size={14} />
  <span className="hidden sm:inline">{t('patient_detail.tabs.digital_records')}</span>
</button>
```

**Icon**: `FileText` from `lucide-react`

---

### 5.2 DigitalRecordsTab Component

File: `frontend_react/src/components/DigitalRecordsTab.tsx`

**Props**:
```typescript
interface DigitalRecordsTabProps {
  patientId: number;
  patientName: string;
  tenantId: number;
}
```

**States**:
```typescript
type ViewState = 'list' | 'generating' | 'preview' | 'editing';
```

**Layout**:

```
┌─────────────────────────────────────────────────────────┐
│  [+ Nueva Ficha]                          [filter dropdown] │
├─────────────────────────────────────────────────────────┤
│  RecordCard  RecordCard  RecordCard  ...                  │
└─────────────────────────────────────────────────────────┘
```

**RecordCard** shows: template_type badge, title, status badge, created_at, [Ver] [PDF] [Email] action buttons.

---

### 5.3 Generation Flow

1. User clicks `+ Nueva Ficha`
2. Modal opens with 4 template cards (visual selector, not dropdown):
   - `clinical_report` — "Informe Clínico" — FileText icon
   - `post_surgery` — "Indicaciones Post-Operatorias" — Stethoscope icon
   - `odontogram_art` — "Odontograma" — Activity icon
   - `authorization_request` — "Solicitud de Autorización" — ClipboardList icon
3. For `authorization_request`: secondary form shows `procedure_name`, `procedure_code` (optional), `insurance_name` (optional), `clinical_justification_hint` (optional textarea)
4. Language selector: `ES | EN | FR` (defaults to `ES`)
5. User clicks `Generar`
6. Modal closes, tab enters `generating` state with a spinner and message: `t('digital_records.generating_message')`
7. POST to `/admin/patients/{id}/digital-records/generate`
8. On success: enter `preview` state

**Scenario** (Loading):
- Given user clicks Generate
- When the API call is in flight
- Then the Generate button is disabled and shows a spinner
- And a full-tab loading overlay shows with message

---

### 5.4 Preview State

Full-tab preview showing:
- Rendered HTML inside an `<iframe>` or sanitized `dangerouslySetInnerHTML` wrapper using `<SafeHTML>`
- Toolbar: `[Editar] [Descargar PDF] [Enviar por Email] [Finalizar] [Volver]`
- Validation warnings panel (if any) — amber banner at top
- If `generation_metadata.hallucination_flags` is not empty: red banner with flag details, Finalizar button disabled

---

### 5.5 Edit Flow

When user clicks `Editar`:
- Each AI-narrative section becomes an inline `<textarea>` (auto-height)
- Hard data sections (JSON-sourced tables) are read-only with a lock icon
- Per-section `[Regenerar con IA]` button triggers POST to `/regenerate` endpoint
- `[Guardar Cambios]` button sends PATCH
- `[Cancelar]` reverts to preview state

---

### 5.6 PDF Download

Clicking `Descargar PDF`:
1. GET `/admin/patients/{id}/digital-records/{record_id}/pdf`
2. Show loading indicator
3. On success: trigger browser download via blob URL
4. On error: show toast with `t('digital_records.pdf_error')`

---

### 5.7 Email Send Modal

Clicking `Enviar por Email` opens a modal:
```
┌─────────────────────────────────┐
│  Enviar Ficha por Email          │
│                                  │
│  Para: [___________________]     │
│        (pre-filled with patient  │
│         email if available)      │
│                                  │
│  [Cancelar]    [Enviar]          │
└─────────────────────────────────┘
```

- Email input MUST be validated (RFC 5322 basic check)
- `Enviar` button shows spinner while in flight
- On success: toast `t('digital_records.email_sent')`
- On error: toast with error message

---

### 5.8 i18n Keys Required

Add to `es.json`, `en.json`, `fr.json`:

```json
"digital_records": {
  "tab_title": "Ficha Digital",
  "new_record": "Nueva Ficha",
  "generating_message": "Generando ficha clínica con IA...",
  "generating_subtitle": "Esto puede tomar unos segundos",
  "select_template": "Seleccionar tipo de ficha",
  "template_clinical_report": "Informe Clínico",
  "template_clinical_report_desc": "Historia completa del paciente con anamnesis y evolución",
  "template_post_surgery": "Indicaciones Post-Operatorias",
  "template_post_surgery_desc": "Cuidados e instrucciones post-procedimiento",
  "template_odontogram_art": "Odontograma",
  "template_odontogram_art_desc": "Estado dental visual con narrativa clínica",
  "template_authorization_request": "Solicitud de Autorización",
  "template_authorization_request_desc": "Documento para obra social o seguro médico",
  "language_label": "Idioma del documento",
  "generate_button": "Generar",
  "edit_button": "Editar",
  "preview_button": "Vista previa",
  "download_pdf": "Descargar PDF",
  "send_email": "Enviar por Email",
  "finalize_button": "Finalizar",
  "back_button": "Volver",
  "save_changes": "Guardar Cambios",
  "regenerate_section": "Regenerar con IA",
  "pdf_error": "Error al generar el PDF",
  "email_sent": "Ficha enviada correctamente",
  "email_error": "Error al enviar el email",
  "email_to_label": "Para",
  "email_modal_title": "Enviar Ficha por Email",
  "send_button": "Enviar",
  "validation_warnings": "Advertencias de validación",
  "hallucination_flags": "Datos no verificables detectados — no se puede finalizar",
  "status_draft": "Borrador",
  "status_final": "Final",
  "status_sent": "Enviado",
  "status_archived": "Archivado",
  "no_records": "No hay fichas digitales generadas",
  "no_records_subtitle": "Generá la primera ficha clínica con IA",
  "readonly_section_tooltip": "Esta sección contiene datos directos del sistema y no puede editarse aquí",
  "authorization_procedure_label": "Procedimiento a autorizar",
  "authorization_code_label": "Código de procedimiento (opcional)",
  "authorization_insurance_label": "Nombre de la obra social (opcional)",
  "authorization_hint_label": "Indicación clínica para la justificación (opcional)",
  "last_sent": "Último envío",
  "send_count": "Enviado {{count}} veces",
  "generated_at": "Generado el {{date}}",
  "section_locked": "Sección con datos del sistema"
},
"patient_detail": {
  "tabs": {
    "digital_records": "Ficha Digital"
  }
}
```

**Note**: `en.json` and `fr.json` MUST also receive translated versions of all keys above.

---

## 6. Nova Integration

### 6.1 Tool: `generar_ficha_digital`

File: `orchestrator_service/services/nova_tools.py`

**Schema** (flat format for OpenAI Realtime API):
```json
{
  "type": "function",
  "name": "generar_ficha_digital",
  "description": "Genera una ficha clínica digital en PDF para un paciente. Usa IA para redactar las secciones narrativas basándose en los datos reales del paciente en el sistema. Soporta 4 tipos de documento.",
  "parameters": {
    "type": "object",
    "properties": {
      "patient_id": {
        "type": "integer",
        "description": "ID del paciente para quien se genera la ficha"
      },
      "template_type": {
        "type": "string",
        "enum": ["clinical_report", "post_surgery", "odontogram_art", "authorization_request"],
        "description": "Tipo de documento a generar"
      },
      "language": {
        "type": "string",
        "enum": ["es", "en", "fr"],
        "description": "Idioma del documento. Por defecto 'es'."
      },
      "authorization_procedure": {
        "type": "string",
        "description": "Solo para authorization_request: nombre del procedimiento a autorizar"
      }
    },
    "required": ["patient_id", "template_type"]
  }
}
```

**Implementation contract**:
- Calls `POST /admin/patients/{patient_id}/digital-records/generate` internally (reuses the same pipeline)
- Uses `current_tenant_id.get()` for tenant isolation
- MUST validate `patient_id` belongs to current tenant before calling
- Returns a voice-friendly summary: `"Ficha generada: {title}. Podés descargarlo desde la pestaña Ficha Digital del paciente."`
- If `validation_warnings` is non-empty, Nova MUST verbally mention: `"Se generó con algunas advertencias de datos incompletos."`

**Scenario**:
- Given Nova receives command "generá el informe clínico del paciente 42"
- When `generar_ficha_digital(patient_id=42, template_type="clinical_report")` is called
- Then the record is created and Nova confirms with the document title

---

### 6.2 Tool: `enviar_ficha_digital`

**Schema**:
```json
{
  "type": "function",
  "name": "enviar_ficha_digital",
  "description": "Envía una ficha clínica digital por email. Requiere que la ficha esté ya generada. Busca automáticamente la ficha más reciente si no se especifica record_id.",
  "parameters": {
    "type": "object",
    "properties": {
      "patient_id": {
        "type": "integer",
        "description": "ID del paciente"
      },
      "to_email": {
        "type": "string",
        "description": "Email de destino. Si no se especifica, usa el email del paciente."
      },
      "record_id": {
        "type": "string",
        "description": "UUID de la ficha específica a enviar. Si no se especifica, usa la más reciente con status='final'."
      },
      "template_type": {
        "type": "string",
        "enum": ["clinical_report", "post_surgery", "odontogram_art", "authorization_request"],
        "description": "Filtra por tipo de ficha al buscar la más reciente. Opcional."
      }
    },
    "required": ["patient_id"]
  }
}
```

**Implementation contract**:
- If `to_email` is null: fetch from `patients.email` — if also null, return error: `"El paciente no tiene email registrado. Pedile el email primero."`
- If `record_id` is null: query most recent record with `status IN ('draft','final')` for the patient
- If no record exists: return error: `"No hay fichas generadas para este paciente. Primero generá una con generar_ficha_digital."`
- Calls `POST /admin/patients/{patient_id}/digital-records/{record_id}/send-email` internally
- Returns: `"Ficha enviada a {to_email} correctamente."` or error message

**Scenario**:
- Given Nova receives "enviá la ficha al doctor"
- When `enviar_ficha_digital(patient_id=42, to_email="doctor@clinic.com")` is called
- And the most recent final record is found
- Then the email is sent and Nova confirms

---

## 7. Email Service Extension

### 7.1 New Method: `send_digital_record_email`

File: `orchestrator_service/email_service.py`

**MIME type change required**: The existing methods use `MIMEMultipart("alternative")`. For attachments, MUST use `MIMEMultipart("mixed")` with nested `MIMEMultipart("alternative")` for the HTML body.

**Method signature**:
```python
def send_digital_record_email(
    self,
    to_email: str,
    pdf_path: str,
    patient_name: str,
    document_title: str,
    clinic_name: str | None = None,
) -> bool:
    ...
```

**Implementation requirements**:
- `to_email` MUST be validated non-empty
- `pdf_path` MUST exist on disk; if not, log error and return `False`
- PDF attached as `MIMEApplication(pdf_bytes, _subtype='pdf')`
- `Content-Disposition`: `attachment; filename="{document_title}.pdf"`
- HTML body: professional email template in the same dark-styled format as existing emails (see existing `send_handoff_email` for reference)
- Subject: `"Ficha Clínica — {patient_name} — {document_title}"`
- On success: return `True`, log `INFO`
- On any exception: log `ERROR`, return `False` (MUST NOT raise)

**Email HTML template content**:
- Header: same gradient style as existing templates, title "Ficha Clínica Digital"
- Body: "Se adjunta la ficha clínica de {patient_name} generada por {clinic_name}."
- Footer: system attribution note
- The PDF is the attachment — the HTML body is just a notification wrapper

---

## 8. Docker — WeasyPrint Dependencies

File: `orchestrator_service/Dockerfile`

**Current state**: `python:3.11-slim` base with only `curl` as system dep.

**Required additions**:

```dockerfile
RUN apt-get update && apt-get install -y \
    curl \
    # WeasyPrint system dependencies
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libxml2 \
    libxslt1.1 \
    fonts-liberation \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
```

**Python dependency** — add to `orchestrator_service/requirements.txt`:
```
weasyprint>=60.0
```

**Verification**: After adding, the build MUST succeed and `python -c "import weasyprint; print(weasyprint.__version__)"` MUST print a version without errors.

**Note on font rendering**: WeasyPrint MUST use the system fonts installed above. The Jinja2 templates MUST NOT reference Google Fonts or external CDN URLs (no internet access at PDF generation time). Use `fonts-liberation` and `fonts-dejavu-core` as fallback fonts in the CSS.

---

## 9. File Storage

PDF files MUST be stored at:
```
/app/uploads/patients/{tenant_id}/{patient_id}/records/{record_id}.pdf
```

This path pattern is consistent with the existing `patient_documents` storage at `/app/uploads/patients/{tenant_id}/{patient_id}/`.

The `pdf_path` column stores the full absolute path as persisted on disk.

The Docker Compose volume for orchestrator uploads MUST cover this path (already covered by the existing persistent volume for `/app/uploads`).

---

## 10. Service Layer Structure

**New file**: `orchestrator_service/services/digital_record_service.py`

**Functions**:

```python
async def gather_data(
    conn,
    tenant_id: int,
    patient_id: int,
    template_type: str,
    extra_params: dict | None = None,
    language: str = "es"
) -> dict:
    """Layer 1: Pure DB queries, returns source_data dict."""

async def generate_ai_content(
    source_data: dict,
    template_type: str,
    language: str
) -> tuple[dict, dict]:
    """Layer 2: OpenAI call. Returns (ai_content, generation_metadata)."""

def validate_ai_content(
    ai_content: dict,
    source_data: dict,
    template_type: str
) -> tuple[bool, list[str]]:
    """Post-generation validation. Returns (passed, warnings_list)."""

def assemble_html(
    source_data: dict,
    ai_content: dict,
    template_type: str,
    language: str
) -> str:
    """Layer 3: Jinja2 assembly. Returns HTML string."""

def generate_pdf(
    html_content: str,
    output_path: str
) -> int:
    """WeasyPrint HTML → PDF. Returns file size in bytes."""

def generate_odontogram_svg(
    teeth: list[dict]
) -> str:
    """Pure SVG generation for the odontogram template."""
```

---

## 11. Anti-Hallucination Summary (8 Layers)

| Layer | Mechanism | Where |
|-------|-----------|-------|
| 1 | Data gathering returns explicit nulls | `gather_data()` |
| 2 | System prompt forbids invention + requires `[NO DATA]` placeholders | Layer 2 prompt |
| 3 | Temperature 0.3 reduces creative drift | OpenAI call params |
| 4 | Template direct injection: hard data comes from JSON, never AI | Jinja2 templates |
| 5 | Post-generation regex + date validation | `validate_ai_content()` |
| 6 | Placeholder rendering as visible styled spans in PDF | Jinja2 + print CSS |
| 7 | `draft`/`final` status gate — hallucination flags block promotion | PATCH endpoint rule |
| 8 | `generation_metadata` audit trail with every flag | DB column |

---

## 12. Test Scenarios

### 12.1 Unit Tests

**File**: `tests/test_digital_record_service.py`

```
GIVEN source_data with all fields null
WHEN generate_ai_content is called
THEN ai_content contains [NO DATA: ...] for every null field
AND validation_passed is True (placeholders are compliant)

GIVEN ai_content containing the word "probablemente"
WHEN validate_ai_content is called
THEN validation returns (False, ["speculative_phrase_detected: probablemente"])

GIVEN a teeth array with 32 teeth (all sano)
WHEN generate_odontogram_svg is called
THEN SVG contains 32 rect/path elements
AND each element has the correct fill for status=sano

GIVEN a legacy odontogram {11: {status: "caries", surface: "oclusal"}}
WHEN gather_data normalizes the odontogram
THEN teeth array contains {fdi: 11, status: "caries", surfaces: {oclusal: "caries"}}
```

### 12.2 Integration Tests

**File**: `tests/test_digital_record_endpoints.py`

```
GIVEN a valid admin JWT for tenant 1 and patient 42 (tenant 1)
WHEN POST /admin/patients/42/digital-records/generate with template_type=clinical_report
THEN response status is 201
AND record.template_type == "clinical_report"
AND record.status == "draft"
AND record.source_data.patient.id == 42
AND record.source_data is NOT modified by AI

GIVEN a record with status=draft and hallucination_flags=[...]
WHEN PATCH /admin/patients/42/digital-records/{id} with status=final
THEN response status is 422
AND error == "cannot_finalize_with_hallucination_flags"

GIVEN a valid admin JWT for tenant 1
WHEN GET /admin/patients/99/digital-records (patient 99 belongs to tenant 2)
THEN response status is 404

GIVEN a generated record with html_content
WHEN GET /admin/patients/42/digital-records/{id}/pdf
THEN response Content-Type is application/pdf
AND response Content-Disposition contains .pdf
```

### 12.3 Email Test

```
GIVEN SMTP is configured
AND pdf_path exists on disk
WHEN send_digital_record_email is called
THEN the email is sent with PDF attached
AND the method returns True

GIVEN pdf_path does not exist
WHEN send_digital_record_email is called
THEN the method returns False
AND an ERROR is logged
AND no exception is raised
```

---

## 13. Out of Scope (Future)

The following are explicitly NOT part of this change:
- Template visual editor (drag-and-drop layout)
- Patient-facing self-service link (similar to anamnesis public link)
- Digital signature integration
- Multi-patient batch generation
- Version branching (only linear edit history is in scope)
- Template customization per tenant (single shared template per type)
