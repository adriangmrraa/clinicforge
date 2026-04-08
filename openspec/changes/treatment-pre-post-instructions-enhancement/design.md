# Technical Design: Treatment Pre/Post Instructions Enhancement

**Change**: `treatment-pre-post-instructions-enhancement`
**Project**: ClinicForge
**Date**: 2026-04-07

---

## 1. Architecture Overview

This change is entirely contained within the existing `treatment_types` table. No new tables, no new API endpoints, no new services. The change flows through four layers:

```
Frontend modal (TreatmentsView.tsx)
    ↓ JSON body with PreInstructions / PostInstructions dicts
Backend CRUD endpoints (admin_routes.py)
    ↓ Pydantic validation + json.dumps()
PostgreSQL treatment_types table (pre_instructions JSONB, post_instructions JSONB)
    ↑ asyncpg fetchrow()
get_treatment_instructions tool (main.py:6032)
    ↓ Formatted string
LangChain agent → patient-facing WhatsApp message
```

---

## 2. Database Layer

### 2.1 Column State After Migration `038`

| Column | Before | After |
|--------|--------|-------|
| `pre_instructions` | `TEXT` | `JSONB` |
| `post_instructions` | `JSONB` (list shape) | `JSONB` (dict shape — new; list shape preserved in legacy rows) |
| `followup_template` | `JSONB` | `JSONB` (unchanged) |

### 2.2 Migration File

**Path**: `orchestrator_service/alembic/versions/038_treatment_instructions_enhancement.py`

**Revision chain**: `revision = "038"`, `down_revision = "037"`

**Upgrade execution order** (critical — order matters due to column type):

```python
def upgrade():
    conn = op.get_bind()

    # Step 1: Data transform for pre_instructions (must happen BEFORE ALTER TYPE)
    # Wrap all non-null TEXT values in {"general_notes": "<original>"}
    conn.execute(sa.text("""
        UPDATE treatment_types
        SET pre_instructions = jsonb_build_object('general_notes', pre_instructions)
        WHERE pre_instructions IS NOT NULL
    """))

    # Step 2: ALTER pre_instructions TEXT -> JSONB
    # At this point all non-null rows are valid JSON strings of the form '{"general_notes": "..."}'
    if _column_type(conn, 'treatment_types', 'pre_instructions') != 'jsonb':
        op.alter_column(
            'treatment_types', 'pre_instructions',
            type_=JSONB(),
            postgresql_using='pre_instructions::jsonb'
        )

    # Step 3: Transform post_instructions legacy list rows -> dict with general_notes
    # Only affects rows where the JSONB value is an array (legacy timed sequence format)
    conn.execute(sa.text("""
        UPDATE treatment_types
        SET post_instructions = jsonb_build_object('general_notes', post_instructions::text)
        WHERE post_instructions IS NOT NULL
          AND jsonb_typeof(post_instructions) = 'array'
    """))


def downgrade():
    conn = op.get_bind()

    # Step 1: Restore post_instructions array rows
    # Only restore rows that were arrays (identified by general_notes value being a JSON array)
    conn.execute(sa.text("""
        UPDATE treatment_types
        SET post_instructions = (post_instructions->>'general_notes')::jsonb
        WHERE post_instructions IS NOT NULL
          AND jsonb_typeof(post_instructions) = 'object'
          AND post_instructions ? 'general_notes'
          AND jsonb_typeof(((post_instructions->>'general_notes'))::jsonb) = 'array'
    """))

    # Step 2: ALTER pre_instructions JSONB -> TEXT (extract general_notes)
    op.alter_column(
        'treatment_types', 'pre_instructions',
        type_=sa.Text(),
        postgresql_using="pre_instructions->>'general_notes'"
    )
```

**Idempotency guard helper** (reuse project pattern from `012`):
```python
def _column_type(conn, table, column):
    row = conn.execute(sa.text(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": table, "c": column}).fetchone()
    return row[0] if row else None
```

### 2.3 SQLAlchemy Model Update (`models.py`)

**File**: `orchestrator_service/models.py:749`

Change:
```python
# Before
pre_instructions = Column(Text, nullable=True)

# After
pre_instructions = Column(JSONB, nullable=True)
```

Import `JSONB` is already present in `models.py` (used by `post_instructions` on line 750).

---

## 3. Backend Layer

### 3.1 New Pydantic Models (`admin_routes.py`)

Add before the first request schema class (around line 120):

```python
class PreInstructions(BaseModel):
    preparation_days_before: Optional[int] = None
    fasting_required: Optional[bool] = None
    fasting_hours: Optional[int] = None
    medications_to_avoid: Optional[List[str]] = Field(default_factory=list)
    medications_to_take: Optional[List[str]] = Field(default_factory=list)
    what_to_bring: Optional[List[str]] = Field(default_factory=list)
    general_notes: Optional[str] = None

class PostInstructions(BaseModel):
    care_duration_days: Optional[int] = None
    dietary_restrictions: Optional[List[str]] = Field(default_factory=list)
    activity_restrictions: Optional[List[str]] = Field(default_factory=list)
    allowed_medications: Optional[List[str]] = Field(default_factory=list)
    prohibited_medications: Optional[List[str]] = Field(default_factory=list)
    sutures_removal_day: Optional[int] = None
    normal_symptoms: Optional[List[str]] = Field(default_factory=list)
    alarm_symptoms: Optional[List[str]] = Field(default_factory=list)
    escalation_message: Optional[str] = None
```

### 3.2 Request Schema Changes

Three schemas updated (`TreatmentCreateRequest` at line ~121, two update schemas at lines ~856, ~877):

```python
# Before
pre_instructions: Optional[str] = None
post_instructions: Optional[Any] = None

# After
pre_instructions: Optional[Union[PreInstructions, str, dict]] = None
post_instructions: Optional[Union[PostInstructions, list, dict, str]] = None
```

### 3.3 Coercion Before Storage

In the INSERT and UPDATE handlers, before `json.dumps(treatment.pre_instructions)`:

```python
def _coerce_pre_instructions(value):
    """Normalize pre_instructions to dict before storage."""
    if value is None:
        return None
    if isinstance(value, str):
        return {"general_notes": value}
    if isinstance(value, PreInstructions):
        return value.dict(exclude_none=False)
    if isinstance(value, dict):
        return value
    return None

def _coerce_post_instructions(value):
    """Normalize post_instructions to dict or list before storage."""
    if value is None:
        return None
    if isinstance(value, list):
        return value  # legacy timed sequence — store as-is
    if isinstance(value, PostInstructions):
        return value.dict(exclude_none=False)
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {"general_notes": value}
    return None
```

Replace direct `json.dumps(treatment.pre_instructions)` with `json.dumps(_coerce_pre_instructions(treatment.pre_instructions))` (and same for post) at lines ~8692-8696 and ~8768-8772.

### 3.4 Validation Helper Update (`_validate_treatment_instruction_fields`)

Current code at `admin_routes.py:8444` validates that `post_instructions` is a list. This MUST be updated:

```python
if treatment.post_instructions is not None:
    post = treatment.post_instructions
    if isinstance(post, PostInstructions):
        # New structured format — validate care_duration_days > 0 if set
        if post.care_duration_days is not None and post.care_duration_days <= 0:
            raise HTTPException(422, "care_duration_days debe ser mayor a 0")
    elif isinstance(post, list):
        # Legacy timed sequence — existing validation unchanged
        for item in post:
            if not isinstance(item, dict):
                raise HTTPException(422, "Cada elemento de post_instructions debe ser un objeto")
            timing = item.get("timing")
            if timing is not None and timing not in ("before", "after", "day_of", "same_day",
                                                       "immediate", "24h", "48h", "72h", "1w",
                                                       "stitch_removal", "custom"):
                raise HTTPException(422, f"Valor de timing inválido: '{timing}'")
    elif isinstance(post, dict):
        # Raw dict — accept without strict validation (flexible for future keys)
        pass
    else:
        raise HTTPException(422, "post_instructions debe ser un objeto o lista")
```

---

## 4. Tool Layer (`main.py`)

### 4.1 `get_treatment_instructions` Rewrite

The function at `main.py:6032` is updated. Key design decisions:

**Reading both shapes**:
```python
pre = row["pre_instructions"]
post = row["post_instructions"]

# Defensive: asyncpg may return JSONB as string
if isinstance(pre, str):
    try:
        pre = json.loads(pre)
    except Exception:
        pre = {"general_notes": pre}

if isinstance(post, str):
    try:
        post = json.loads(post)
    except Exception:
        post = None
```

**Pre-instructions formatter** (new structured path):
```python
def _format_pre_instructions_dict(pre: dict, treatment_name: str) -> str:
    lines = [f"PRE-TRATAMIENTO — {treatment_name}:"]
    if pre.get("preparation_days_before"):
        lines.append(f"• Preparación: llegar preparado con {pre['preparation_days_before']} día(s) de anticipación")
    fasting = pre.get("fasting_required")
    if fasting is True:
        hours = pre.get("fasting_hours")
        lines.append(f"• Ayuno: SI — {hours} horas" if hours else "• Ayuno: SI")
    elif fasting is False:
        lines.append("• Ayuno: NO requerido")
    for item in (pre.get("medications_to_avoid") or []):
        lines.append(f"• Evitar medicamento: {item}")
    for item in (pre.get("medications_to_take") or []):
        lines.append(f"• Tomar: {item}")
    for item in (pre.get("what_to_bring") or []):
        lines.append(f"• Traer: {item}")
    if pre.get("general_notes"):
        lines.append(f"• Notas: {pre['general_notes']}")
    return "\n".join(lines)
```

**Post-instructions formatter** (new structured dict path):
```python
def _format_post_instructions_dict(post: dict, treatment_name: str) -> tuple[str, bool]:
    """Returns (formatted_string, has_alarm_symptoms)."""
    lines = [f"POST-TRATAMIENTO — {treatment_name}:"]
    if post.get("care_duration_days"):
        lines.append(f"Período de cuidado: {post['care_duration_days']} días.")
    if post.get("dietary_restrictions"):
        lines.append("DIETA:")
        for r in post["dietary_restrictions"]:
            lines.append(f"  • {r}")
    if post.get("activity_restrictions"):
        lines.append("ACTIVIDAD FÍSICA:")
        for r in post["activity_restrictions"]:
            lines.append(f"  • {r}")
    if post.get("allowed_medications"):
        lines.append("MEDICACIÓN PERMITIDA:")
        for m in post["allowed_medications"]:
            lines.append(f"  • {m}")
    if post.get("prohibited_medications"):
        lines.append("MEDICACIÓN PROHIBIDA:")
        for m in post["prohibited_medications"]:
            lines.append(f"  • {m}")
    if post.get("sutures_removal_day"):
        lines.append(f"PUNTOS: retiro al día {post['sutures_removal_day']}.")
    if post.get("normal_symptoms"):
        lines.append("SÍNTOMAS NORMALES (esperados):")
        for s in post["normal_symptoms"]:
            lines.append(f"  • {s}")
    has_alarms = bool(post.get("alarm_symptoms"))
    if has_alarms:
        lines.append("SÍNTOMAS DE ALARMA (requieren atención médica urgente):")
        for s in post["alarm_symptoms"]:
            lines.append(f"  ⚠ {s}")
    if post.get("escalation_message"):
        lines.append(post["escalation_message"])
    if has_alarms:
        lines.append(
            "[ALARM_ESCALATION: Si el paciente describe alguno de los síntomas de alarma de arriba, "
            "llamá derivhumano INMEDIATAMENTE con urgency='alta'. No preguntes más, actúa.]"
        )
    return "\n".join(lines), has_alarms
```

**No-instructions path** (NULL or not found):
```python
return (
    "Este tratamiento no tiene cuidados configurados. "
    "Te recomiendo contactar directamente a la clínica para más indicaciones."
)
```

### 4.2 Tool Signature (unchanged)

The function signature `get_treatment_instructions(treatment_code: str, timing: str = "all") -> str` is NOT changed. Backward compat preserved for the agent's existing calling pattern.

### 4.3 System Prompt Update

In `build_system_prompt()` at the `INSTRUCCIONES DE TRATAMIENTO` block (~line 7159), append after existing rules:

```python
"• Si la respuesta de get_treatment_instructions contiene [ALARM_ESCALATION:...] "
"Y el paciente describió síntomas → llamá derivhumano(urgency='alta') ANTES de responder. "
"Usá el escalation_message del protocolo si está disponible.\n"
"• Si get_treatment_instructions devuelve 'Este tratamiento no tiene cuidados configurados' "
"→ NO improvises. Repetí esa frase al paciente y ofrecé derivar a la clínica.\n"
```

---

## 5. Frontend Layer

### 5.1 File

**Path**: `frontend_react/src/views/TreatmentsView.tsx`
**Modal location**: line ~1122 (`instructionsModalOpen` conditional block)

### 5.2 New TypeScript Interfaces

```typescript
interface PreInstructionsForm {
  preparation_days_before: number | null;
  fasting_required: boolean | null;
  fasting_hours: number | null;
  medications_to_avoid: string[];
  medications_to_take: string[];
  what_to_bring: string[];
  general_notes: string;
  _legacy_text?: string; // read-only, migration source
}

interface PostInstructionsForm {
  care_duration_days: number | null;
  dietary_restrictions: string[];
  activity_restrictions: string[];
  allowed_medications: string[];
  prohibited_medications: string[];
  sutures_removal_day: number | null;
  normal_symptoms: string[];
  alarm_symptoms: string[];
  escalation_message: string;
}
```

### 5.3 `StringListEditor` Component (inline)

```typescript
const StringListEditor: React.FC<{
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
  placeholder?: string;
  accentColor?: string;
}> = ({ label, items, onChange, placeholder, accentColor = 'blue' }) => {
  // Renders label + list of text inputs with X buttons + "Agregar" button
  // Uses project input class: "px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white text-sm"
};
```

### 5.4 Modal State

Replace single `instructionsLocal` state with:

```typescript
const [preForm, setPreForm] = useState<PreInstructionsForm>(emptyPreForm);
const [postForm, setPostForm] = useState<PostInstructionsForm>(emptyPostForm);
const [timedSequence, setTimedSequence] = useState<PostInstruction[]>([]);
const [activePanel, setActivePanel] = useState<'pre' | 'post' | 'followup'>('pre');
```

On modal open: parse loaded `pre_instructions` (dict or null → `PreInstructionsForm`; string → `{general_notes: text, _legacy_text: text}`); parse `post_instructions` (dict → `PostInstructionsForm`; list → `timedSequence`); parse `followup_template` → unchanged.

### 5.5 Save Handler

```typescript
const handleSaveInstructions = () => {
  const pre = hasAnyPreField(preForm) ? buildPreDict(preForm) : null;
  const post = hasAnyPostField(postForm)
    ? buildPostDict(postForm)
    : timedSequence.length > 0 ? timedSequence : null;
  // PATCH endpoint call with pre_instructions, post_instructions, followup_template
};
```

### 5.6 i18n Keys Required

Add to `es.json`, `en.json`, `fr.json`:

```json
"treatments.instructions.disclaimer": "Aviso: Los protocolos configurados aquí son informativos. No constituyen consejo médico profesional para el paciente.",
"treatments.instructions.pre.fasting_required": "¿Requiere ayuno?",
"treatments.instructions.pre.fasting_hours": "Horas de ayuno",
"treatments.instructions.pre.preparation_days": "Días de preparación previos",
"treatments.instructions.pre.medications_to_avoid": "Medicamentos a evitar",
"treatments.instructions.pre.medications_to_take": "Medicamentos a tomar",
"treatments.instructions.pre.what_to_bring": "Qué traer",
"treatments.instructions.pre.general_notes": "Notas adicionales",
"treatments.instructions.pre.migrate_button": "Migrar al formato estructurado",
"treatments.instructions.post.protocol_tab": "Protocolo de recuperación",
"treatments.instructions.post.sequence_tab": "Secuencia programada",
"treatments.instructions.post.care_duration": "Días de cuidado",
"treatments.instructions.post.dietary": "Restricciones alimentarias",
"treatments.instructions.post.activity": "Restricciones de actividad física",
"treatments.instructions.post.allowed_meds": "Medicación permitida",
"treatments.instructions.post.prohibited_meds": "Medicación prohibida",
"treatments.instructions.post.sutures_day": "Día de retiro de puntos",
"treatments.instructions.post.normal_symptoms": "Síntomas normales (tranquilizadores)",
"treatments.instructions.post.alarm_symptoms": "Síntomas de alarma (derivación urgente)",
"treatments.instructions.post.escalation_msg": "Mensaje de escalación de emergencia"
```

---

## 6. Key Design Decisions

### Decision 1: Why NOT keep the list shape for `post_instructions`

The current list `[{timing, content}]` was designed for **outbound scheduled messages** (what to send the patient at 24h, 48h, etc.). It is not a recovery protocol. Merging both concepts into one list would require the agent to parse temporal offsets to answer a real-time question like "¿qué puedo comer?" — impossible to do correctly. The clean separation (dict for recovery protocol, list for timed outbound) solves both use cases without confusion.

### Decision 2: Why preserve legacy list in `general_notes`

Production data may exist. Destroying it would be irresponsible. The migration wraps it, the downgrade unwraps it, and the tool reads both shapes. The UI offers a migration button rather than auto-migrating on save.

### Decision 3: Why not a new tool `get_post_op_protocol`

The `get_treatment_instructions` tool is already in `DENTAL_TOOLS` and the system prompt already instructs the agent to call it. Adding a parallel tool would require prompt changes and agent retraining. Enhancing the existing tool is the minimal-disruption path.

### Decision 4: `[ALARM_ESCALATION:...]` tag pattern

Using a tagged string inside the tool response (rather than a separate return value) avoids changing the tool's return type (still `str`) and works with LangChain's existing tool-output pipeline. The agent is instructed in the system prompt to detect and act on this tag — same pattern as `[INTERNAL_PRICE:X]` and `[INTERNAL_DEBT:...]` already used in `check_availability`.

### Decision 5: Migration number `038`

Last confirmed migration is `037_derivation_escalation_fallback.py`. This change uses `038` as the next sequential revision. Per project naming convention: `038_treatment_instructions_enhancement.py`.

---

## 7. File Impact Summary

| File | Change Type | Notes |
|------|-------------|-------|
| `orchestrator_service/alembic/versions/038_treatment_instructions_enhancement.py` | NEW | Data-preserving migration |
| `orchestrator_service/models.py` | MODIFY | `pre_instructions` column type: `Text` → `JSONB` |
| `orchestrator_service/admin_routes.py` | MODIFY | 2 new models, 3 schema updates, 1 validation update, 2 coercion helpers, 2 INSERT/UPDATE call sites |
| `orchestrator_service/main.py` | MODIFY | `get_treatment_instructions` tool rewrite + 2-line system prompt addition |
| `frontend_react/src/views/TreatmentsView.tsx` | MODIFY | New interfaces, `StringListEditor`, modal restructure |
| `frontend_react/src/locales/es.json` | MODIFY | ~20 new i18n keys |
| `frontend_react/src/locales/en.json` | MODIFY | ~20 new i18n keys |
| `frontend_react/src/locales/fr.json` | MODIFY | ~20 new i18n keys |
