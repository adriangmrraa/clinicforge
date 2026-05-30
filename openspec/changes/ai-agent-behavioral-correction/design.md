# DESIGN: AI Agent Behavioral Correction

**Change**: `ai-agent-behavioral-correction`
**Status**: DESIGNED
**Date**: 2026-04-04

---

## Architecture Decisions

### D1: Structure of 8 emotional flows in the prompt

**Decision: B — Separate named sections with clear headers**

Each flow (F1-F8) is an independent `## FLUJO F{N}` block injected into the system prompt. This keeps flows isolated, testable, and easy to modify without affecting the rest of the prompt.

**Rationale**: The prompt is already ~420 lines. Adding 8 flows as one monolithic block makes it unreadable and untestable. Separate sections allow:
- Selective testing per flow
- Easy addition/removal of flows per tenant (future)
- Clear debugging when a flow misfires

**Rejected**: Option C (conditional injection) adds unnecessary complexity for the initial version. All 8 flows apply to all tenants — they're behavioral patterns, not feature flags.

---

### D2: How to resolve `{professional_name}` for positioning text

**Decision: D — `specialty_pitch` IS the complete positioning text including the professional name**

The `tenants.system_prompt_template` column (renamed conceptually to `specialty_pitch`) contains the FULL positioning text. When populated, it replaces ALL hardcoded positioning blocks including "La Dra. Laura Delgado se especializa en...".

For references outside the positioning block (e.g., "la Dra." in flow messages), we resolve `{professional_name}` from the **first active professional** in the tenant's `professionals` table, with fallback to `"la profesional"`.

**Resolution strategy for `{professional_name}`**:
```sql
SELECT first_name || ' ' || COALESCE(last_name, '')
FROM professionals
WHERE tenant_id = $1 AND is_active = true
ORDER BY id ASC
LIMIT 1
```
- If result exists: `"Dr/a. {first_name} {last_name}"` (e.g., "Dra. Laura Delgado")
- If no professionals: `"la profesional"` / `"nuestro equipo"`

**Why not a dedicated FK or column**: The spec explicitly says "No new `primary_professional_id` FK on tenants table". Using the first active professional is good enough — most single-practitioner clinics have exactly one professional. Multi-professional clinics should set `system_prompt_template` to avoid this resolution entirely.

---

### D3: Insertion points for new blocks in the prompt

The current prompt structure (line numbers from `build_system_prompt()` return statement, starting at line 6048):

```
1. REGLA DE IDIOMA                        (line 6048)
2. GREETING diferenciado                   (line 6049)
3. IDENTIDAD Y TONO                       (line 6050-6056)
4. POLÍTICA DE PUNTUACIÓN                 (line 6057-6058)
5. INFORMACIÓN DEL CONSULTORIO            (line 6060-6066)
6. FLUJO DE IMPLANTES Y PRÓTESIS          (line 6068-6100)
7. ESTUDIOS PREVIOS                       (line 6101-6105)
8. MANEJO DE OBJECIONES                   (line 6107-6147)
9. DICCIONARIO DE SINÓNIMOS               (line 6149-6152)
10. SINÓNIMOS PARA ACCIONES               (line 6154-6159)
11. WHATSAPP (EXPERIENCIA MOBILE)         (line 6175-6180)
12. REGLAS CORE                           (line 6182-6186)
13. FAQs / Insurance / Derivation         (line 6209-6213)
14. ADMISIÓN — DATOS MÍNIMOS              (line 6215-6221)
15. REGLAS DE CONVERSACIÓN Y TONO         (line 6234-6242)
16. ESTRUCTURA DE RESPUESTA               (line 6244-6251)
17. FRASES BASE                           (line 6253-6259)
18. DIFERENCIACIÓN DRA. vs EQUIPO         (line 6261-6263)
19. FLUJO DE AGENDAMIENTO (PASOS 1-10)    (line 6265+)
```

**New blocks insertion plan**:

| New Block | Insert Position | Rationale |
|-----------|----------------|-----------|
| `{bot_name}` identity | Inside block 3 (IDENTIDAD Y TONO), first line | Bot name is part of identity |
| `PROHIBICIONES` | After block 4 (PUNTUACIÓN), before block 5 | Prohibitions are global rules, must be read early |
| `TONO Y VARIACIÓN` | Replace block 15 (REGLAS DE CONVERSACIÓN) | Extends existing tone rules |
| `ESCALATION RULES` | Replace the `derivhumano` rule in block 12 (REGLAS CORE) | Consolidates escalation logic |
| `{specialty_pitch}` | Replace blocks 16-18 (ESTRUCTURA + FRASES + DIFERENCIACIÓN) | All three are positioning content — `specialty_pitch` replaces them when set |
| `F1-F8 flows` | Replace block 8 (MANEJO DE OBJECIONES) entirely | The 8 flows ARE the objection handling system — they replace the current partial flows |
| `F3` guard on implant flow | Modify block 6 header | Add "SOLO si el paciente menciona explícitamente dientes faltantes/implantes" |

**Key principle**: REPLACE existing partial flows, don't duplicate. The current "OBJECIÓN DE MIEDO", "MALA EXPERIENCIA PREVIA", and "OBJECIÓN DE PRECIO" blocks (lines 6107-6147) are superseded by F7, F1, and F5 respectively.

---

### D4: Migration numbering

**Decision**: Migration `022` (next after `021_telegram_authorized_users.py`).

The spec referenced `009` but the actual latest is `021`. Corrected to `022`.

---

### D5: `check_availability` — remove vs soften

**Decision: Remove entirely**

The spec is clear: "This block MUST be removed entirely. No replacement message SHALL be added." The line creates sales pressure that conflicts with emotional flows (especially F2 urgency). Removing it is safe — patients can always ask for more options.

---

### D6: TORA identity injection

**Decision**: Add to the IDENTIDAD Y TONO block, first line.

```
Tu nombre es TORA.
• Si un paciente te pregunta cómo te llamás, respondé: "Me llamo TORA, soy la asistente virtual de {clinic_name}."
• NUNCA te presentes con otro nombre.
```

Also update the 3 GREETING templates to use "Soy TORA, la asistente virtual de..." instead of "Soy la asistente virtual de...".

---

## File-by-File Change Plan

### File 1: `orchestrator_service/models.py`

**Change**: Add `patient_display_name` to `TreatmentType`.

```python
# After line 736 (is_available_for_booking)
patient_display_name = Column(Text, nullable=True)
```

No other model changes needed. `system_prompt_template` already exists on `Tenant` (line 168).

---

### File 2: `orchestrator_service/alembic/versions/022_add_patient_display_name.py`

**New migration file**.

```python
"""add patient_display_name to treatment_types

Revision ID: 022_patient_display_name
Revises: 021_telegram_authorized_users (actual rev ID from file)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '022abc123def'
down_revision = '<021_revision_id>'  # Read from 021 file
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('treatment_types',
        sa.Column('patient_display_name', sa.Text(), nullable=True)
    )

def downgrade():
    op.drop_column('treatment_types', 'patient_display_name')
```

---

### File 3: `orchestrator_service/services/buffer_task.py`

**Changes** (2 modifications):

#### 3A: Add `system_prompt_template` to tenant query (line 107)

```python
# BEFORE:
"SELECT clinic_name, address, google_maps_url, working_hours, consultation_price, bank_cbu, bank_alias, bank_holder_name FROM tenants WHERE id = $1"

# AFTER:
"SELECT clinic_name, address, google_maps_url, working_hours, consultation_price, bank_cbu, bank_alias, bank_holder_name, system_prompt_template FROM tenants WHERE id = $1"
```

#### 3B: Resolve `professional_name` + extract `specialty_pitch` + pass to `build_system_prompt()` (after line 122)

```python
# After bank_holder_name extraction:
specialty_pitch = (tenant_row["system_prompt_template"] or "") if tenant_row else ""

# Resolve lead professional name
lead_professional_name = ""
try:
    lead_prof_row = await pool.fetchrow(
        "SELECT first_name, last_name FROM professionals WHERE tenant_id = $1 AND is_active = true ORDER BY id ASC LIMIT 1",
        tenant_id,
    )
    if lead_prof_row:
        lead_professional_name = f"{lead_prof_row['first_name']} {lead_prof_row['last_name'] or ''}".strip()
except Exception:
    pass
```

#### 3C: Pass new params to `build_system_prompt()` (line 583)

Add to the call:
```python
specialty_pitch=specialty_pitch,
professional_name=lead_professional_name,
bot_name="TORA",
```

---

### File 4: `orchestrator_service/main.py`

This is the largest change. Broken into sub-changes:

#### 4A: `build_system_prompt()` signature (line 5705)

Add 3 new parameters:

```python
def build_system_prompt(
    ...existing params...,
    specialty_pitch: str = "",
    professional_name: str = "",
    bot_name: str = "TORA",
) -> str:
```

#### 4B: Professional name resolution with fallback (inside function, before prompt construction)

```python
# Resolve professional_name with fallback
prof_display = professional_name if professional_name else "la profesional"
prof_display_full = f"el/la Dr/a. {professional_name}" if professional_name else "nuestro equipo"
```

#### 4C: GREETING templates (lines 5873-5904)

Replace "Soy la asistente virtual" with "Soy {bot_name}, la asistente virtual".
Replace "La Dra. se especializa en rehabilitación oral con implantes, prótesis y cirugía guiada." with `{specialty_pitch}` when set, or keep current hardcoded text as fallback.

```python
# Greeting specialty line
greeting_specialty = specialty_pitch if specialty_pitch else f"La Dra. se especializa en rehabilitación oral con implantes, prótesis y cirugía guiada."

# Then in each greeting template:
# "Soy {bot_name}, la asistente virtual del {clinic_name}.\n{greeting_specialty}"
```

#### 4D: IDENTIDAD Y TONO block (line 6050)

Insert bot name identity:

```python
f"""Tu nombre es {bot_name}.
• Si un paciente te pregunta cómo te llamás, respondé: "Me llamo {bot_name}, soy la asistente virtual de {clinic_name}."
• NUNCA te presentes con otro nombre."""
```

#### 4E: New PROHIBICIONES block (after POLÍTICA DE PUNTUACIÓN, ~line 6058)

```python
prohibiciones_block = f"""
PROHIBICIONES (LEER 5 VECES):
1. PROHIBIDO dar precio + dirección + turnos en un solo mensaje de urgencia.
2. PROHIBIDO repetir la bio/presentación en cada mensaje (solo en el GREETING inicial).
3. PROHIBIDO confirmar el diagnóstico del paciente ("sí, necesitás X"). Solo la profesional determina el tratamiento en la evaluación.
4. PROHIBIDO exponer nombres internos de tratamientos al paciente.
5. PROHIBIDO escalar a humano por: miedo, mala experiencia, OS desconocida, frustración, precio.
6. PROHIBIDO usar siempre la misma frase — variá la expresión manteniendo el tono.
7. PROHIBIDO responder con lenguaje corporativo/genérico. Frases prohibidas: "estamos aquí para ayudarte", "es un placer asistirte", "no dudes en contactarnos", "nuestro equipo está a tu disposición", "estimado/a paciente".
8. PROHIBIDO dar precios de tratamiento específico. SOLO el precio de consulta ({price_text}) está permitido.
"""
```

#### 4F: Replace MANEJO DE OBJECIONES (lines 6107-6147) with 8 emotional flows

The entire block from "## MANEJO DE OBJECIONES" through "MALA EXPERIENCIA PREVIA" is replaced with:

```python
flows_block = f"""
## FLUJOS EMOCIONALES (F1-F8) — CONTENER > ORIENTAR > CONVERTIR

### F1 — MALA EXPERIENCIA PREVIA
Triggers: "mala experiencia", "me hicieron mal", "no confío", "me lastimaron"
Protocolo en MENSAJES SEPARADOS:
M1 — Validar: Una línea cálida sin juzgar.
M2 — Normalizar: "Es más común de lo que parece." NO culpar al profesional anterior.
M3 — Posicionar: "{prof_display_full} trabaja con diagnóstico preciso y planificación personalizada." NO repetir la bio si ya se usó.
M4 — CTA: "Si querés, te ayudo a coordinar una evaluación." USAR "evaluación", NO "turno".
Postcondición: Si acepta → check_availability(treatment_name='Consulta').
PROHIBIDO: derivhumano, combinar M1-M4, usar "turno" en M4.

### F2 — URGENCIA / DOLOR
Triggers: "me duele", "dolor", "urgencia", "emergencia", "inflamación", "se me cayó"
Protocolo:
M1 — Contención emocional: Validar el dolor. Una línea empática.
M2 — UNA sola pregunta: "Desde cuándo te duele?" o "Hay inflamación?"
M3 — Turno urgente: Llamar triage_urgency + check_availability('Consulta') inmediato.
PROHIBIDO: precio/dirección/maps en M1-M2. Máximo 2 mensajes antes de ofrecer turno.

### F3 — PACIENTE ESTÉTICO (intención vaga)
Triggers: "mejorar mi sonrisa", "quiero verme mejor", "no me gusta mi sonrisa", "diseño de sonrisa"
Protocolo:
M1 — Normalizar el objetivo sin asignar tratamiento.
M2 — Pregunta diagnóstica: "Qué querés mejorar: color, forma, alineación o piezas faltantes?"
M3 — CTA a evaluación después de que responda.
PROHIBIDO: Mostrar menú de emojis de implantes. Sugerir tratamiento antes de M2. Usar términos diagnósticos.
Nota: Si menciona dientes faltantes → F6 tiene precedencia.

### F4 — OBRA SOCIAL DESCONOCIDA
Trigger: Paciente menciona OS que NO está en la lista de insurance_providers.
Protocolo:
M1 — Afirmar cobertura general: "Trabajamos con varias obras sociales."
M2 — Clarificar variabilidad: "Los detalles de cobertura varían, podemos verificarlo."
M3 — Oferta condicional: Solo si el paciente pide explícitamente verificar.
PROHIBIDO: derivhumano. Decir "no trabajamos con esa". Pedir que llame a la clínica.

### F5 — PRECIO DIRECTO
Triggers: "cuánto sale", "precio", "presupuesto", "cuánto cuesta"
Protocolo:
M1 — Construir valor: "Cada caso es diferente y necesita evaluación personalizada."
M2 — Precio de consulta: "${price_text}" (si está configurado). Mencionar descuento por OS si aplica.
M3 — CTA: Cierre consultivo con "evaluación".
PROHIBIDO: Dar precio de tratamiento específico. Saltear M1 e ir directo al precio.

### F6 — PÉRDIDA MÚLTIPLES DIENTES
Triggers: "perdí varios dientes", "no tengo dientes", "se me cayeron", "quiero algo fijo", "dentadura"
Protocolo:
M1 — Conexión emocional/funcional: Comer, sonreír, calidad de vida. NO listar tratamientos.
M2 — Alternativas existen: "Hay diferentes enfoques según cada caso." Sin nombres de tratamiento.
M3 — Posicionar: "{prof_display_full} se especializa en rehabilitación de casos complejos."
M4 — CTA: "evaluación".
PROHIBIDO: Asignar tratamiento. Usar nombres de protocolo (R.I.S.A., All-on-4, zigomático). Mostrar menú de emojis.

### F7 — MIEDO AL TRATAMIENTO
Triggers: "miedo", "pánico", "terror", "me asusta", "no me animo", "fobia"
Protocolo en MENSAJES SEPARADOS:
M1 — Validar: "Es totalmente normal."
M2 — Social proof: "Muchos pacientes llegan con ese mismo temor y se sienten más tranquilos después de la evaluación." Mencionar enfoque personalizado.
M3 — CTA: Coordinar consulta "con calma".
PROHIBIDO: Confirmar diagnóstico previo del paciente. Usar nombres de procedimiento. derivhumano.

### F8 — SIN HUESO / CASO RECHAZADO (ALTA PRIORIDAD)
Triggers: "no tengo hueso", "me rechazaron", "me dijeron que no se puede", "no soy candidato"
Protocolo:
M1 — Validar sin confirmar ni negar el diagnóstico anterior.
M2 — Alternativas con lenguaje cauteloso: "En muchos casos existen alternativas." NO prometer.
M3 — Posicionar: "{prof_display_full} se especializa en casos complejos y pacientes previamente rechazados."
M4 — CTA: "evaluación".
PROHIBIDO: Confirmar diagnóstico ajeno. Prometer resultados. Usar nombres de protocolo. derivhumano.
"""
```

#### 4G: TONO Y VARIACIÓN block (replaces REGLAS DE CONVERSACIÓN Y TONO at lines 6234-6242)

```python
tone_block = """
TONO Y VARIACIÓN (OBLIGATORIO):
• Voseo rioplatense SIEMPRE: "podés", "tenés", "querés". NUNCA "puedes", "tienes".
• Registro informal-profesional. Sos personal de salud, no un call center.
• Máximo 2 emojis por mensaje. Solo al inicio o final, nunca en medio de frase.
• NUNCA repitas la misma frase de apertura 2 veces en una conversación.
• Variá entre: pregunta abierta, comentario empático, dato útil.
• Cerrá SIEMPRE con: pregunta suave de acción O CTA de confirmación. Nunca terminar con afirmación sola.
• Cada burbuja WhatsApp: máximo 4 líneas.
"""
```

#### 4H: Replace DIFERENCIACIÓN DRA. vs EQUIPO (line 6261-6263) and ESTRUCTURA/FRASES

When `specialty_pitch` is set, replace all three blocks with:

```python
if specialty_pitch:
    positioning_block = f"""
POSICIONAMIENTO PROFESIONAL:
{specialty_pitch}

Usá esta información para posicionar al profesional en los flujos F1, F3, F5, F6, F7, F8.
NO la repitas textualmente en cada mensaje — adaptala al contexto de la conversación.
"""
else:
    # Keep current hardcoded blocks as fallback
    positioning_block = f"""
ESTRUCTURA DE RESPUESTA (6 PASOS — aplicar en servicios premium):
...existing content...

FRASES BASE:
...existing content...

DIFERENCIACIÓN DRA. vs EQUIPO:
• SERVICIOS DE LA DRA. (...): Más empatía, más autoridad, más posicionamiento, cierre consultivo elaborado. Siempre posicionar a {prof_display_full} como especialista.
• SERVICIOS DEL EQUIPO (...): Flujo más simple y operativo.
"""
```

#### 4I: ESCALATION RULES (update derivhumano rule in POLÍTICAS section, ~line 6206)

Replace the single-line `derivhumano` rule with:

```python
escalation_block = """
REGLAS DE ESCALACIÓN (derivhumano):
ESCALAR (OBLIGATORIO):
• Paciente pide EXPLÍCITAMENTE hablar con alguien: "quiero hablar con una persona", "pasame con la doctora"
• Emergencia médica real: sangrado incontrolable, trauma facial severo, infección sistémica
• Amenaza o agresión explícita

NO ESCALAR (PROHIBIDO llamar derivhumano):
• Miedo o ansiedad → Usar F7
• Mala experiencia previa → Usar F1
• Pregunta de precio → Usar F5
• OS desconocida → Usar F4
• Urgencia dental → Usar F2
• Intención estética vaga → Usar F3
• Pérdida de dientes → Usar F6
• Caso rechazado → Usar F8
• Frustración sin pedir humano → Empatía + continuar flujo
REGLA: Si el trigger está en "NO ESCALAR" Y el paciente NO pidió explícitamente un humano → derivhumano PROHIBIDO.
"""
```

#### 4J: Modify FLUJO DE IMPLANTES Y PRÓTESIS (lines 6068-6100)

Replace "La Dra." references:
- Line 6076: `"La Dra. es quien define"` → `"{prof_display} es quien define"`
- Line 6086: `"La Dra. Laura Delgado se especializa..."` → `"{prof_display_full} se especializa en este tipo de tratamientos, incluyendo casos complejos."`
- Line 6093: `"así la Dra. ya los tiene"` → `"así ya los tiene para tu consulta"`

Add guard at the top of the block:
```
IMPORTANTE: Este flujo se activa SOLO si el paciente menciona explícitamente implantes, prótesis, dentadura, o dientes faltantes. Si la intención es estética vaga ("mejorar sonrisa") → usar F3.
```

#### 4K: Remove "Hay X turnos más disponibles" (lines 1897-1900)

Delete:
```python
if total_today > 3:
    lines.append(
        f"\nHay {total_today - 3} turnos más disponibles si preferís otro horario."
    )
```

#### 4L: `_format_insurance_providers()` — use `copay_notes` (lines 5600-5640)

Replace the generic response line (line 5619):
```python
# BEFORE:
'Respuesta por defecto para OS aceptada: "Sí 😊 trabajamos con tu obra social. La consulta tiene un coseguro. ¿Querés que te pase turnos disponibles?"',

# AFTER:
# Remove the generic line. Add per-provider copay info:
```

In the `accepted` section (line 5624-5626), change from just listing names to including copay info:

```python
if accepted:
    acc_lines = []
    for p in accepted:
        copay = p.get("copay_notes") or "coseguro estándar"
        acc_lines.append(f"  • {p['provider_name']} → {copay}")
    lines.append("Aceptadas:")
    lines.extend(acc_lines)
```

#### 4M: `list_services` tool — use `patient_display_name` (lines 3390-3428)

In the query (line 3390), add `tt.patient_display_name`:
```python
query = """SELECT tt.id, tt.code, tt.name, tt.patient_display_name, tt.base_price, tt.priority
           FROM treatment_types tt
           WHERE tt.tenant_id = $1 AND tt.is_active = true AND tt.is_available_for_booking = true"""
```

In the output line (line 3428), use `patient_display_name` with fallback:
```python
display_name = r.get('patient_display_name') or r['name']
res += f"• {display_name} (código: {r['code']}){price}{prof_str} [prioridad: {priority_val}]\n"
```

#### 4N: `get_service_details` tool — use `patient_display_name` (lines 3449-3453)

Add `patient_display_name` to the SELECT queries. Use `row.get('patient_display_name') or row['name']` in output.

#### 4O: `triage_urgency` docstring (line 2795)

Replace `"Dra. María Laura Delgado"` with `"el profesional"` or remove the name entirely.

---

## New Parameters for `build_system_prompt()`

```python
def build_system_prompt(
    clinic_name: str,
    current_time: str,
    response_language: str,
    hours_start: str = "08:00",
    hours_end: str = "19:00",
    ad_context: str = "",
    patient_context: str = "",
    clinic_address: str = "",
    clinic_maps_url: str = "",
    clinic_working_hours: dict = None,
    faqs: list = None,
    patient_status: str = "new_lead",
    consultation_price: float = None,
    sede_info: dict = None,
    anamnesis_url: str = "",
    bank_cbu: str = "",
    bank_alias: str = "",
    bank_holder_name: str = "",
    upcoming_holidays: list = None,
    insurance_providers: list = None,
    derivation_rules: list = None,
    # --- NEW PARAMETERS ---
    specialty_pitch: str = "",       # From tenants.system_prompt_template
    professional_name: str = "",     # Resolved from first active professional
    bot_name: str = "TORA",          # Bot identity name
) -> str:
```

All 3 new parameters have defaults, making this backward-compatible with any other caller.

---

## Prompt Section Order (Final)

After all changes, the prompt structure will be:

```
 1. REGLA DE IDIOMA
 2. GREETING (con {bot_name} + {greeting_specialty})
 3. IDENTIDAD Y TONO (con bot_name identity)
 4. POLÍTICA DE PUNTUACIÓN
 5. PROHIBICIONES (NEW — P1-P8)
 6. INFORMACIÓN DEL CONSULTORIO
 7. FLUJO DE IMPLANTES Y PRÓTESIS (modified: guard + template vars)
 8. ESTUDIOS PREVIOS
 9. FLUJOS EMOCIONALES F1-F8 (NEW — replaces MANEJO DE OBJECIONES)
10. DICCIONARIO DE SINÓNIMOS
11. SINÓNIMOS PARA ACCIONES
12. WHATSAPP (EXPERIENCIA MOBILE)
13. REGLAS CORE (with updated ESCALATION RULES)
14. FAQs / Insurance (with copay_notes) / Derivation
15. ADMISIÓN — DATOS MÍNIMOS
16. POST-CONFIRMACIÓN
17. TONO Y VARIACIÓN (NEW — replaces REGLAS DE CONVERSACIÓN Y TONO)
18. POSICIONAMIENTO PROFESIONAL ({specialty_pitch} or fallback blocks)
19. FLUJO DE AGENDAMIENTO (PASOS 1-10, unchanged)
```

---

## Migration SQL for 022

```sql
-- upgrade
ALTER TABLE treatment_types ADD COLUMN patient_display_name TEXT;

-- downgrade
ALTER TABLE treatment_types DROP COLUMN patient_display_name;
```

---

## Data Flow

```
Tenant DB row
  ├── system_prompt_template ──→ specialty_pitch param
  ├── clinic_name ──→ clinic_name param (existing)
  └── [other fields] ──→ existing params

Professionals DB (first active)
  └── first_name + last_name ──→ professional_name param

buffer_task.py
  └── build_system_prompt(
        ...existing...,
        specialty_pitch=tenant_row["system_prompt_template"],
        professional_name=lead_prof_name,
        bot_name="TORA",
      )

build_system_prompt()
  ├── prof_display = "Dra. Laura Delgado" (or fallback)
  ├── greeting uses bot_name + greeting_specialty
  ├── F1-F8 flows use {prof_display_full}
  ├── positioning uses specialty_pitch (or hardcoded fallback)
  └── prohibitions block uses {price_text}
```

---

## Token Budget Estimate

| Section | Current Lines | New Lines | Delta |
|---------|--------------|-----------|-------|
| Prohibitions | 0 | 8 | +8 |
| 8 Emotional Flows | ~40 (partial) | ~80 | +40 |
| Tone & Variation | ~10 | ~8 | -2 |
| Escalation Rules | 2 | 12 | +10 |
| Positioning (specialty_pitch) | ~20 | ~5 (when set) | -15 |
| Bot identity | 0 | 3 | +3 |
| **Total delta** | | | **~+44 lines** |

Within the target of ~600 lines max. The prompt stays manageable.

---

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| F1-F8 flows conflict with existing partial flows | MEDIUM | The design explicitly REPLACES MANEJO DE OBJECIONES. No duplicate flows will exist. |
| `professional_name` resolution returns wrong professional | LOW | ORDER BY id ASC is deterministic. Multi-professional clinics should use `system_prompt_template` to control positioning explicitly. |
| Prompt too long after changes | LOW | Estimated +44 lines (from ~420 to ~464). Well within limits. |
| `bot_name` hardcoded as "TORA" | LOW | Passed as parameter with default. Future: add to `tenants` table if multi-tenant customization needed. |
| Backward compatibility for tenants without `system_prompt_template` | LOW | All new params have safe defaults. NULL/empty `specialty_pitch` preserves current behavior exactly. |
