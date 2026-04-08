# DESIGN: Clinic Support, Complaints & Review Config

**Change**: `clinic-support-complaints-config`
**Status**: DESIGNED
**Date**: 2026-04-07

---

## Architecture Decisions

### D1: JSONB vs. normalized tables for `review_platforms` and `complaint_handling_protocol`

**Decision: JSONB columns on `tenants`**

Both fields have a small, fixed-shape schema (array of 3-field objects for platforms; 3 text fields for protocol). A normalized table would require a tenant FK, a separate admin endpoint, and a JOIN on every tenant fetch. The pattern established by `tenants.working_hours` (JSONB) and `tenant_insurance_providers` (separate table) shows the project mixes both strategies. For small, tightly-coupled config with no cross-tenant querying needs, JSONB on `tenants` is consistent with `working_hours`.

**Rejected**: Separate table for `review_platforms` adds complexity for no gain at this scale. Future: if platforms need per-platform analytics or complex scheduling, migrate to a table then.

---

### D2: Complaint detection strategy in `derivhumano`

**Decision: Keyword matching on `reason` string (no LLM re-invocation)**

The `reason` parameter is already a LangChain-generated string describing why the tool was called. The LLM has already read the conversation. Adding a keyword scan on `reason` is O(n_keywords) CPU, zero latency, zero token cost, and zero failure mode.

**Rejected**: Passing a `complaint: bool` flag — would require the LLM to explicitly decide it's a complaint every time. This is unreliable (LLM may not set the flag for ambiguous cases) and changes the tool schema (breaking existing callers).

**Rejected**: A second LLM call to classify `reason` — prohibitive cost for a simple routing decision.

---

### D3: Formatter as a standalone function vs. inline in `build_system_prompt()`

**Decision: Standalone `_format_support_policy(tenant_row)` function**

Matches the existing pattern: `_format_insurance_providers()` is a standalone formatter injected into the prompt. This makes the function independently unit-testable without calling the entire `build_system_prompt()`.

**Placement in prompt**: After the `## PROTOCOLO DE QUEJAS` analog position, between `FAQs/Insurance` and `ADMISIÓN — DATOS MÍNIMOS`. This is position 14.5 in the current prompt section order.

---

### D4: Followup job review link — append vs. separate message

**Decision: Append to existing followup message**

The followup job sends a WhatsApp message to the patient. Appending the review link to that message (rather than sending a second message) avoids the patient receiving two messages in quick succession, which can feel spammy. The review request is a natural P.S. after the clinical follow-up.

Format:
```
[existing message]

---
Si querés dejarnos una reseña, nos ayudaría muchísimo 🙏
• Google Maps: https://...
• Instagram: https://...
```

---

### D5: Migration number

**Decision: `039`** — the current head is `038` (treatment-pre-post-instructions). This change adds `039_add_tenant_support_complaints.py`.

---

### D6: Frontend section design — collapsible, not a new tab

**Decision: Collapsible section inside the existing Tab 1 (Edit Clinic) modal**

The existing modal has ~12 sections (name/phone, address, consultation price, chairs, country, system prompt, banking, derivation email, calendar, working hours). Adding "Soporte y Quejas" as a collapsible section at the end (before the Submit button) is consistent with how the modal is structured. Adding a new tab would require a tab system refactor.

The section is collapsed by default (closed state shows just the section title + chevron) to reduce initial visual complexity.

---

## File-by-File Change Plan

### File 1: `orchestrator_service/alembic/versions/039_add_tenant_support_complaints.py`

**New migration file.**

```python
"""039 — Add support/complaints config to tenants

Revision ID: 039
Revises: 038
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade():
    # All nullable to avoid disrupting existing rows
    op.add_column("tenants", sa.Column("complaint_escalation_email", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("complaint_escalation_phone", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("expected_wait_time_minutes", sa.Integer(), nullable=True))
    op.add_column("tenants", sa.Column("revision_policy", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("review_platforms", JSONB(), nullable=True))
    op.add_column("tenants", sa.Column("complaint_handling_protocol", JSONB(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column(
            "auto_send_review_link_after_followup",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade():
    op.drop_column("tenants", "auto_send_review_link_after_followup")
    op.drop_column("tenants", "complaint_handling_protocol")
    op.drop_column("tenants", "review_platforms")
    op.drop_column("tenants", "revision_policy")
    op.drop_column("tenants", "expected_wait_time_minutes")
    op.drop_column("tenants", "complaint_escalation_phone")
    op.drop_column("tenants", "complaint_escalation_email")
```

---

### File 2: `orchestrator_service/models.py`

Add to the `Tenant` class after `derivation_email`:

```python
# --- Support / complaints / review config (migration 039) ---
complaint_escalation_email = Column(Text, nullable=True)
complaint_escalation_phone = Column(Text, nullable=True)
expected_wait_time_minutes = Column(Integer, nullable=True)
revision_policy = Column(Text, nullable=True)
review_platforms = Column(JSONB, nullable=True)
complaint_handling_protocol = Column(JSONB, nullable=True)
auto_send_review_link_after_followup = Column(Boolean, nullable=False, server_default="false")
```

---

### File 3: `orchestrator_service/admin_routes.py`

#### 3A: Pydantic schemas (add near top of file, with other inline schemas)

```python
from pydantic import BaseModel, validator
from typing import List, Optional
import re as _re_email

class ReviewPlatformItem(BaseModel):
    name: str
    url: str
    show_after_days: int = 1

    @validator("url")
    def url_must_be_http(cls, v):
        if not v.startswith("http://") and not v.startswith("https://"):
            raise ValueError("url must start with http:// or https://")
        return v

    @validator("show_after_days")
    def days_must_be_positive(cls, v):
        if v < 1:
            raise ValueError("show_after_days must be >= 1")
        return v

class ComplaintHandlingProtocol(BaseModel):
    level_1: Optional[str] = None
    level_2: Optional[str] = None
    level_3: Optional[str] = None

    class Config:
        extra = "forbid"  # Reject unknown keys
```

#### 3B: `GET /admin/tenants` — extend SELECT and response

Add the 7 new columns to the existing SELECT query:

```python
"SELECT id, clinic_name, bot_phone_number, config, address, google_maps_url, "
"working_hours, consultation_price, bank_cbu, bank_alias, bank_holder_name, "
"derivation_email, logo_url, max_chairs, country_code, system_prompt_template, "
# NEW:
"complaint_escalation_email, complaint_escalation_phone, expected_wait_time_minutes, "
"revision_policy, review_platforms, complaint_handling_protocol, "
"auto_send_review_link_after_followup, "
"created_at, updated_at FROM tenants WHERE id = ANY($1::int[]) ORDER BY id ASC"
```

In the response loop, add JSONB defensive parsing:

```python
for field in ("review_platforms", "complaint_handling_protocol"):
    if isinstance(d.get(field), str):
        try:
            d[field] = json.loads(d[field])
        except Exception:
            d[field] = None
```

#### 3C: `PUT /admin/tenants/{id}` — new field handlers

Add after the `system_prompt_template` block (before the `if not updates:` guard):

```python
if "complaint_escalation_email" in data:
    val = data.get("complaint_escalation_email")
    if val and "@" not in val:
        raise HTTPException(status_code=422, detail="complaint_escalation_email: formato inválido")
    params.append(val or None)
    updates.append(f"complaint_escalation_email = ${len(params)}")

if "complaint_escalation_phone" in data:
    params.append(data.get("complaint_escalation_phone") or None)
    updates.append(f"complaint_escalation_phone = ${len(params)}")

if "expected_wait_time_minutes" in data:
    val = data.get("expected_wait_time_minutes")
    if val is not None and str(val).strip() != "":
        ival = int(val)
        if ival <= 0:
            raise HTTPException(status_code=422, detail="expected_wait_time_minutes must be > 0")
        params.append(ival)
    else:
        params.append(None)
    updates.append(f"expected_wait_time_minutes = ${len(params)}")

if "revision_policy" in data:
    val = data.get("revision_policy")
    if val and len(val) > 2000:
        raise HTTPException(status_code=422, detail="revision_policy: máximo 2000 caracteres")
    params.append(val or None)
    updates.append(f"revision_policy = ${len(params)}")

if "review_platforms" in data:
    val = data.get("review_platforms")
    if val is not None:
        if not isinstance(val, list):
            raise HTTPException(status_code=422, detail="review_platforms must be a JSON array")
        # Validate each item with Pydantic
        validated = []
        for item in val:
            try:
                validated.append(ReviewPlatformItem(**item).dict())
            except Exception as e:
                raise HTTPException(status_code=422, detail=f"review_platforms item invalid: {e}")
        params.append(json.dumps(validated))
    else:
        params.append(None)
    updates.append(f"review_platforms = ${len(params)}::jsonb")

if "complaint_handling_protocol" in data:
    val = data.get("complaint_handling_protocol")
    if val is not None:
        if not isinstance(val, dict):
            raise HTTPException(status_code=422, detail="complaint_handling_protocol must be a JSON object")
        try:
            validated_protocol = ComplaintHandlingProtocol(**val).dict(exclude_none=True)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"complaint_handling_protocol invalid: {e}")
        params.append(json.dumps(validated_protocol))
    else:
        params.append(None)
    updates.append(f"complaint_handling_protocol = ${len(params)}::jsonb")

if "auto_send_review_link_after_followup" in data:
    val = data.get("auto_send_review_link_after_followup")
    params.append(bool(val) if val is not None else False)
    updates.append(f"auto_send_review_link_after_followup = ${len(params)}")
```

---

### File 4: `orchestrator_service/main.py`

#### 4A: `_format_support_policy(tenant_row)` — new function

Place near `_format_insurance_providers()`.

**Pseudocode with sample Spanish output**:

```python
def _format_support_policy(tenant_row: dict) -> str:
    """
    Formats the support/complaints/review block for the system prompt.
    Returns "" if no support fields are configured (backward compat).
    """
    complaint_email = tenant_row.get("complaint_escalation_email") or ""
    complaint_phone = tenant_row.get("complaint_escalation_phone") or ""
    wait_minutes = tenant_row.get("expected_wait_time_minutes")
    revision_policy = (tenant_row.get("revision_policy") or "").strip()
    review_platforms_raw = tenant_row.get("review_platforms") or []
    protocol_raw = tenant_row.get("complaint_handling_protocol") or {}

    # Parse JSONB if returned as string
    if isinstance(review_platforms_raw, str):
        try: review_platforms_raw = json.loads(review_platforms_raw)
        except: review_platforms_raw = []
    if isinstance(protocol_raw, str):
        try: protocol_raw = json.loads(protocol_raw)
        except: protocol_raw = {}

    # Short-circuit: if all fields empty, return ""
    has_config = any([complaint_email, complaint_phone, wait_minutes,
                      revision_policy, review_platforms_raw, protocol_raw])
    if not has_config:
        return ""

    # Default level descriptions
    default_l1 = ("Empatizá. Di: \"Lamento mucho que hayas tenido esa experiencia. "
                  "Tu comentario es muy valioso para nosotros.\"\n"
                  "Si el paciente se calma → preguntá si podés ayudar en algo más.\n"
                  "Si el paciente insiste o se enoja más → NIVEL 2.")
    default_l2 = ("Empatizá + ofrecé revisión si aplica.\n"
                  "Di: \"Quiero que quedes satisfecho/a. Vamos a coordinar para que el profesional revise tu caso.\"\n"
                  "Ejecutar derivhumano SOLO si el paciente persiste tras esta respuesta.")
    default_l3 = ("Ejecutar derivhumano INMEDIATAMENTE con detalle completo.\n"
                  "Si hay síntomas físicos → ejecutar TAMBIÉN triage_urgency.")

    l1 = protocol_raw.get("level_1") or default_l1
    l2 = protocol_raw.get("level_2") or default_l2
    l3 = protocol_raw.get("level_3") or default_l3

    lines = ["## PROTOCOLO DE SOPORTE Y QUEJAS", ""]
    lines.append("ESCALAMIENTO GRADUADO (SEGUÍ ESTE ORDEN — NUNCA SALTEAR NIVELES):")
    lines.append("REGLA: NUNCA pasar directamente a NIVEL 2 o NIVEL 3 sin haber aplicado el NIVEL anterior en esta conversación.")
    lines.append("")

    # Level 1
    lines.append("NIVEL 1 — Queja leve (espera, incomodidad menor, comentario negativo):")
    lines.append(l1)
    if wait_minutes:
        lines.append(f"[TIEMPO DE ESPERA ESTÁNDAR DE LA CLÍNICA: {wait_minutes} minutos. Si el paciente menciona que esperó más, reconocelo.]")
    lines.append("")

    # Level 2
    lines.append("NIVEL 2 — Queja moderada (tratamiento, cobro, atención):")
    lines.append(l2)
    if revision_policy:
        lines.append(f"[POLÍTICA DE REVISIÓN: {revision_policy}]")
    lines.append("")

    # Level 3
    lines.append("NIVEL 3 — Queja grave (mala práctica, dolor persistente post-tratamiento, cobro incorrecto, amenaza):")
    lines.append(l3)
    if complaint_email:
        lines.append(f"[EMAIL DE QUEJAS: {complaint_email} — la notificación llega a este buzón específico]")
    if complaint_phone:
        lines.append(f"[TELÉFONO DIRECTO PARA QUEJAS GRAVES: {complaint_phone}]")
    lines.append("")

    # Global rules
    lines.append("REGLAS GLOBALES DE QUEJAS:")
    lines.append("• SIEMPRE empatizar ANTES de escalar. NUNCA decir \"no puedo ayudarte\".")
    lines.append("• NUNCA pedir disculpas por el profesional — usá \"entiendo tu preocupación\" en vez de \"perdón por el error\".")
    lines.append("• NUNCA confirmar errores de cobro o mala praxis — eso implica responsabilidad legal. Siempre: \"entiendo tu preocupación, vamos a revisarlo\".")
    lines.append("• NUNCA escalar a NIVEL 2 sin haber aplicado NIVEL 1 en esta conversación.")
    lines.append("")

    # Review platforms
    if review_platforms_raw:
        lines.append("RESEÑAS:")
        lines.append("Cuando un paciente expresa satisfacción o pregunta dónde dejar una reseña:")
        for p in review_platforms_raw:
            lines.append(f"• {p.get('name', 'Plataforma')}: {p.get('url', '')}")
        lines.append("Ofrecé el link directamente: \"Si querés dejarnos una reseña, nos ayudaría muchísimo: [link]\"")
        lines.append("")

    return "\n".join(lines)
```

**Sample output when fully configured**:

```
## PROTOCOLO DE SOPORTE Y QUEJAS

ESCALAMIENTO GRADUADO (SEGUÍ ESTE ORDEN — NUNCA SALTEAR NIVELES):
REGLA: NUNCA pasar directamente a NIVEL 2 o NIVEL 3 sin haber aplicado el NIVEL anterior en esta conversación.

NIVEL 1 — Queja leve (espera, incomodidad menor, comentario negativo):
Empatizá. Di: "Lamento mucho que hayas tenido esa experiencia. Tu comentario es muy valioso para nosotros."
Si el paciente se calma → preguntá si podés ayudar en algo más.
Si el paciente insiste o se enoja más → NIVEL 2.
[TIEMPO DE ESPERA ESTÁNDAR DE LA CLÍNICA: 15 minutos. Si el paciente menciona que esperó más, reconocelo.]

NIVEL 2 — Queja moderada (tratamiento, cobro, atención):
Empatizá + ofrecé revisión si aplica.
Di: "Quiero que quedes satisfecho/a. Vamos a coordinar para que el profesional revise tu caso."
Ejecutar derivhumano SOLO si el paciente persiste tras esta respuesta.
[POLÍTICA DE REVISIÓN: Ajustes gratuitos los primeros 30 días post-tratamiento.]

NIVEL 3 — Queja grave (mala práctica, dolor persistente post-tratamiento, cobro incorrecto, amenaza):
Ejecutar derivhumano INMEDIATAMENTE con detalle completo.
Si hay síntomas físicos → ejecutar TAMBIÉN triage_urgency.
[EMAIL DE QUEJAS: quejas@clinica.com — la notificación llega a este buzón específico]

REGLAS GLOBALES DE QUEJAS:
• SIEMPRE empatizar ANTES de escalar. NUNCA decir "no puedo ayudarte".
• NUNCA pedir disculpas por el profesional — usá "entiendo tu preocupación" en vez de "perdón por el error".
• NUNCA confirmar errores de cobro o mala praxis — eso implica responsabilidad legal.
• NUNCA escalar a NIVEL 2 sin haber aplicado NIVEL 1 en esta conversación.

RESEÑAS:
Cuando un paciente expresa satisfacción o pregunta dónde dejar una reseña:
• Google Maps: https://g.co/r/xxx
• Instagram: https://ig.me/xxx
Ofrecé el link directamente: "Si querés dejarnos una reseña, nos ayudaría muchísimo: [link]"
```

#### 4B: Inject into `build_system_prompt()`

Add `tenant_row: dict = None` as a new parameter with default `None`.

Inside the function, after the insurance/FAQ block:

```python
# --- Support, complaints, and review policy ---
support_policy_block = _format_support_policy(tenant_row or {})
# Injected as section 14.5, between FAQs/insurance and ADMISIÓN
```

In the final prompt assembly, insert `support_policy_block` between the insurance block and the admisión block. When empty string, it contributes nothing.

The `tenant_row` is passed from `buffer_task.py` alongside the other params already extracted from the tenant query.

**buffer_task.py change**: Extend the tenant SELECT to include the 7 new columns. Pass `tenant_row=full_tenant_row` to `build_system_prompt()`.

#### 4C: `derivhumano` tool — complaint routing

**Pseudocode**:

```python
# After the existing emails.add(tenant_data["derivation_email"]) block:

COMPLAINT_KEYWORDS = {
    "queja", "molestia", "insatisfecho", "insatisfecha",
    "cobrar", "cobro", "error", "revisión", "revision",
    "reclamo", "experiencia", "espera", "trato", "brusco",
    "arruinaron", "mal hecho"
}

reason_lower = (reason or "").lower()
is_complaint = any(kw in reason_lower for kw in COMPLAINT_KEYWORDS)

if is_complaint:
    # Fetch complaint_escalation_email for this tenant
    support_row = await db.pool.fetchrow(
        "SELECT complaint_escalation_email FROM tenants WHERE id = $1",
        tenant_id
    )
    if support_row and support_row.get("complaint_escalation_email"):
        emails.add(support_row["complaint_escalation_email"].strip())
        logger.info(f"Queja detectada — notificación a complaint_escalation_email: {support_row['complaint_escalation_email']}")
# If complaint but no complaint_escalation_email: existing derivation_email already added above
```

Note: This block runs AFTER the existing `derivation_email` fetch, ensuring both addresses receive the email when both are configured.

---

### File 5: `orchestrator_service/jobs/followups.py`

#### 5A: Extend the tenant query

The existing query selects `t.id as tenant_id, t.name as tenant_name, t.whatsapp_credentials`. Extend to:

```sql
t.id as tenant_id,
t.name as tenant_name,           -- NOTE: actual column may be clinic_name
t.whatsapp_credentials,
t.auto_send_review_link_after_followup,
t.review_platforms
```

Note: The existing query uses `t.name` but the `Tenant` model has `clinic_name`. During implementation, verify the actual column name against the ORM. Use `t.clinic_name` if needed.

#### 5B: Build review suffix after sending the followup message

```python
# After building `message` string and before calling send_whatsapp_message():

review_suffix = ""
if apt.get("auto_send_review_link_after_followup"):
    platforms_raw = apt.get("review_platforms") or []
    if isinstance(platforms_raw, str):
        try:
            platforms_raw = json.loads(platforms_raw)
        except Exception:
            platforms_raw = []

    days_since = (date.today() - apt["appointment_datetime"].date()).days
    eligible = [
        p for p in platforms_raw
        if isinstance(p, dict) and days_since >= p.get("show_after_days", 1)
    ]
    if eligible:
        review_suffix = "\n\n---\nSi querés dejarnos una reseña, nos ayudaría muchísimo 🙏"
        for p in eligible:
            review_suffix += f"\n• {p.get('name', 'Reseña')}: {p.get('url', '')}"

final_message = message + review_suffix
```

Pass `final_message` (not `message`) to `send_whatsapp_message()`.

---

### File 6: Frontend — `frontend_react/src/views/ClinicsView.tsx`

#### 6A: `formData` state extension

Add the 7 new fields to the `formData` initial state (and the shape populated from `editingClinica`):

```typescript
complaint_escalation_email: editingClinica?.complaint_escalation_email ?? '',
complaint_escalation_phone: editingClinica?.complaint_escalation_phone ?? '',
expected_wait_time_minutes: editingClinica?.expected_wait_time_minutes ?? '',
revision_policy: editingClinica?.revision_policy ?? '',
review_platforms: editingClinica?.review_platforms ?? [],
complaint_handling_protocol: editingClinica?.complaint_handling_protocol ?? {},
auto_send_review_link_after_followup: editingClinica?.auto_send_review_link_after_followup ?? false,
```

#### 6B: New collapsible section — structure

Insert after the `Email de derivación` section (around line 1005), before the `Calendar provider` section:

```tsx
{/* --- Soporte, Quejas y Reseñas --- */}
<div className="space-y-3 border-t border-white/[0.06] pt-4 mt-4">
    {/* Collapsible header */}
    <button
        type="button"
        onClick={() => setSupportSectionOpen(prev => !prev)}
        className="flex items-center justify-between w-full text-left"
    >
        <h3 className="text-sm font-bold text-white/60 flex items-center gap-2">
            <MessageSquare size={14} className="text-orange-400" />
            {t('clinics.support_section_title')}
        </h3>
        <ChevronDown
            size={16}
            className={`text-white/40 transition-transform ${supportSectionOpen ? 'rotate-180' : ''}`}
        />
    </button>
    <p className="text-xs text-white/30">{t('clinics.support_section_help')}</p>

    {supportSectionOpen && (
        <div className="space-y-4 pt-2">
            {/* Sub-block 1: Escalation contacts */}
            <div className="space-y-2 bg-white/[0.02] p-3 rounded-lg border border-white/[0.04]">
                <p className="text-xs font-semibold text-orange-400/80">Contactos de escalamiento</p>
                <div className="space-y-1">
                    <label className="text-xs text-white/50">{t('clinics.complaint_escalation_email_label')}</label>
                    <input
                        type="email"
                        placeholder="quejas@clinica.com"
                        className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white placeholder-white/20 focus:ring-2 focus:ring-orange-500 outline-none"
                        value={formData.complaint_escalation_email}
                        onChange={e => setFormData(prev => ({ ...prev, complaint_escalation_email: e.target.value }))}
                    />
                    <p className="text-xs text-white/30">{t('clinics.complaint_escalation_email_help')}</p>
                </div>
                <div className="space-y-1">
                    <label className="text-xs text-white/50">{t('clinics.complaint_escalation_phone_label')}</label>
                    <input
                        type="tel"
                        placeholder="+54911..."
                        className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white placeholder-white/20 focus:ring-2 focus:ring-orange-500 outline-none"
                        value={formData.complaint_escalation_phone}
                        onChange={e => setFormData(prev => ({ ...prev, complaint_escalation_phone: e.target.value }))}
                    />
                    <p className="text-xs text-white/30">{t('clinics.complaint_escalation_phone_help')}</p>
                </div>
            </div>

            {/* Sub-block 2: Wait/revision policy */}
            <div className="space-y-2 bg-white/[0.02] p-3 rounded-lg border border-white/[0.04]">
                <p className="text-xs font-semibold text-orange-400/80">Política de espera y revisión</p>
                <div className="space-y-1">
                    <label className="text-xs text-white/50">{t('clinics.expected_wait_time_label')}</label>
                    <input
                        type="number"
                        min="1"
                        max="120"
                        placeholder="15"
                        className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white placeholder-white/20 focus:ring-2 focus:ring-orange-500 outline-none"
                        value={formData.expected_wait_time_minutes}
                        onChange={e => setFormData(prev => ({ ...prev, expected_wait_time_minutes: e.target.value }))}
                    />
                    <p className="text-xs text-white/30">{t('clinics.expected_wait_time_help')}</p>
                </div>
                <div className="space-y-1">
                    <label className="text-xs text-white/50">{t('clinics.revision_policy_label')}</label>
                    <textarea
                        rows={2}
                        placeholder={t('clinics.revision_policy_placeholder')}
                        className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white placeholder-white/20 focus:ring-2 focus:ring-orange-500 outline-none resize-y"
                        value={formData.revision_policy}
                        onChange={e => setFormData(prev => ({ ...prev, revision_policy: e.target.value }))}
                    />
                    <p className="text-xs text-white/30">{t('clinics.revision_policy_help')}</p>
                </div>
            </div>

            {/* Sub-block 3: Review platforms key-value list editor */}
            <div className="space-y-2 bg-white/[0.02] p-3 rounded-lg border border-white/[0.04]">
                <p className="text-xs font-semibold text-orange-400/80">{t('clinics.review_platforms_label')}</p>
                <p className="text-xs text-white/30">{t('clinics.review_platforms_help')}</p>
                {formData.review_platforms.map((p, idx) => (
                    <div key={idx} className="grid grid-cols-[1fr_2fr_80px_auto] gap-2 items-center">
                        <input
                            type="text"
                            placeholder={t('clinics.review_platform_name')}
                            className="px-2 py-1 bg-white/[0.04] border border-white/[0.08] rounded text-xs text-white"
                            value={p.name}
                            onChange={e => {
                                const updated = [...formData.review_platforms];
                                updated[idx] = { ...updated[idx], name: e.target.value };
                                setFormData(prev => ({ ...prev, review_platforms: updated }));
                            }}
                        />
                        <input
                            type="url"
                            placeholder="https://..."
                            className="px-2 py-1 bg-white/[0.04] border border-white/[0.08] rounded text-xs text-white"
                            value={p.url}
                            onChange={e => {
                                const updated = [...formData.review_platforms];
                                updated[idx] = { ...updated[idx], url: e.target.value };
                                setFormData(prev => ({ ...prev, review_platforms: updated }));
                            }}
                        />
                        <input
                            type="number"
                            min="1"
                            placeholder={t('clinics.review_platform_days')}
                            className="px-2 py-1 bg-white/[0.04] border border-white/[0.08] rounded text-xs text-white"
                            value={p.show_after_days ?? 1}
                            onChange={e => {
                                const updated = [...formData.review_platforms];
                                updated[idx] = { ...updated[idx], show_after_days: parseInt(e.target.value) || 1 };
                                setFormData(prev => ({ ...prev, review_platforms: updated }));
                            }}
                        />
                        <button
                            type="button"
                            onClick={() => {
                                const updated = formData.review_platforms.filter((_, i) => i !== idx);
                                setFormData(prev => ({ ...prev, review_platforms: updated }));
                            }}
                            className="text-xs text-red-400 hover:text-red-300"
                        >
                            {t('clinics.review_platform_remove')}
                        </button>
                    </div>
                ))}
                <button
                    type="button"
                    onClick={() => setFormData(prev => ({
                        ...prev,
                        review_platforms: [...prev.review_platforms, { name: '', url: '', show_after_days: 1 }]
                    }))}
                    className="text-xs font-medium text-orange-400 hover:text-orange-300"
                >
                    + {t('clinics.review_platform_add')}
                </button>
                {/* Auto-send toggle */}
                <label className="flex items-center gap-2 mt-2 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={formData.auto_send_review_link_after_followup}
                        onChange={e => setFormData(prev => ({ ...prev, auto_send_review_link_after_followup: e.target.checked }))}
                        className="w-4 h-4 rounded border-white/[0.08] text-orange-400"
                    />
                    <span className="text-xs text-white/60">{t('clinics.auto_review_label')}</span>
                </label>
                <p className="text-xs text-white/30">{t('clinics.auto_review_help')}</p>
            </div>

            {/* Sub-block 4: Complaint protocol levels */}
            <div className="space-y-2 bg-white/[0.02] p-3 rounded-lg border border-white/[0.04]">
                <p className="text-xs font-semibold text-orange-400/80">{t('clinics.complaint_protocol_label')}</p>
                <p className="text-xs text-white/30">{t('clinics.complaint_protocol_help')}</p>
                {['level_1', 'level_2', 'level_3'].map((level, idx) => (
                    <div key={level} className="space-y-1">
                        <label className="text-xs text-white/50">
                            {t(`clinics.complaint_protocol_${level}`)}
                        </label>
                        <textarea
                            rows={2}
                            className="w-full px-2 py-1 bg-white/[0.04] border border-white/[0.08] rounded text-xs text-white resize-y"
                            value={(formData.complaint_handling_protocol as any)?.[level] ?? ''}
                            onChange={e => setFormData(prev => ({
                                ...prev,
                                complaint_handling_protocol: {
                                    ...prev.complaint_handling_protocol,
                                    [level]: e.target.value || undefined
                                }
                            }))}
                        />
                    </div>
                ))}
            </div>
        </div>
    )}
</div>
```

**New state variable**: `const [supportSectionOpen, setSupportSectionOpen] = useState(false);`

**Icon import**: Add `MessageSquare` to the `lucide-react` import.

---

### File 7: i18n — locale files

Add 25 new keys to all 3 locale files. English and French values are translations of the Spanish values above (see REQ-9 for the full key list and Spanish values).

---

## Data Flow Summary

```
Frontend modal (ClinicsView.tsx)
  └─ PUT /admin/tenants/{id}
       ├─ Pydantic validation (ReviewPlatformItem, ComplaintHandlingProtocol)
       ├─ json.dumps() for JSONB fields
       └─ UPDATE tenants SET ...

buffer_task.py (on each inbound message)
  └─ SELECT (..., complaint_escalation_email, complaint_escalation_phone,
              expected_wait_time_minutes, revision_policy, review_platforms,
              complaint_handling_protocol, auto_send_review_link_after_followup)
       FROM tenants WHERE id = $1
  └─ build_system_prompt(..., tenant_row=full_row)
       └─ _format_support_policy(tenant_row) → injected into prompt section 14.5

LangChain agent (on complaint conversation)
  └─ derivhumano(reason="queja de cobro...")
       └─ keyword detection → SELECT complaint_escalation_email FROM tenants WHERE id = $1
       └─ email sent to complaint_escalation_email + derivation_email (both)

Followup job (daily at 11:00)
  └─ SELECT ... t.auto_send_review_link_after_followup, t.review_platforms ...
  └─ eligibility check: days_since >= show_after_days
  └─ message += review_suffix
  └─ send via WhatsApp service
```

---

## Backwards Compatibility

All 7 new columns are nullable (or boolean with `server_default='false'`). The `_format_support_policy()` function returns `""` when all fields are NULL. The `build_system_prompt()` new `tenant_row` parameter defaults to `{}`. The `derivhumano` keyword check only triggers additional routing when `complaint_escalation_email` is set. The followup job check is guarded by `auto_send_review_link_after_followup`. No existing behavior changes for tenants that do not configure any of the new fields.

---

## Token Budget

| New section | Lines |
|-------------|-------|
| `## PROTOCOLO DE SOPORTE Y QUEJAS` (when fully configured) | ~25–30 |
| When unconfigured | 0 |

The change adds at most 30 prompt lines when all fields are set. This is within the stated budget (target max ~600 lines from the prior change's analysis). When unconfigured: zero overhead.
