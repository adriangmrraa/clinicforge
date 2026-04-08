# SDD Design: Clinic Bot Name Editable

**Change**: `clinic-bot-name-editable`
**Status**: DRAFT
**Date**: 2026-04-07

---

## 1. Alembic Migration

### Migration Numbering

**Primary scenario** (this change merged first, before other SDD changes in openspec/changes/):
- Filename: `033_clinic_bot_name.py`
- `revision = "033"`
- `down_revision = "032"` (current head: `032_multi_agent_tables.py`)

**Fallback scenario** (if other SDD changes are merged before this one):
- The implementer MUST check the current Alembic head at merge time via `alembic heads`
- Bump `revision` to the next available number
- Set `down_revision` to the actual current head
- Rename the file to match the new number

### Migration Pseudocode

```python
# File: orchestrator_service/alembic/versions/033_clinic_bot_name.py
revision = "033"
down_revision = "032"

def upgrade():
    op.add_column(
        "tenants",
        sa.Column("bot_name", sa.String(50), nullable=True)
    )

def downgrade():
    op.drop_column("tenants", "bot_name")
```

No index needed — this column is read once per message processing, not used in WHERE clauses.

---

## 2. ORM Change

**File**: `orchestrator_service/models.py` — `Tenant` class

Add after `ai_engine_mode`:

```python
bot_name = Column(String(50), nullable=True)
```

---

## 3. Backend Endpoint Change

**File**: `orchestrator_service/admin_routes.py`

### GET /admin/tenants — add `bot_name` to SELECT

Current SELECT in `get_tenants()` lists explicit columns. Add `bot_name` to that list:

```sql
SELECT id, clinic_name, bot_phone_number, ..., bot_name FROM tenants WHERE id = ANY($1::int[])
```

### PUT /admin/tenants/{id} — add handler block

The `update_tenant()` function uses a pattern of `if "field" in data: ...`. Add after the `system_prompt_template` block:

```python
if "bot_name" in data:
    raw = data.get("bot_name")
    # Normalize empty string to None
    params.append(raw.strip() if raw and raw.strip() else None)
    updates.append(f"bot_name = ${len(params)}")
```

**Note**: Pattern and max-length validation (`^[A-Za-z0-9 _-]+$`, max 50) MUST be enforced here with an explicit check that raises `HTTPException(422)` before appending to params. The current endpoint uses `Dict[str, Any]` (no Pydantic schema), so validation is manual.

```python
if "bot_name" in data:
    raw = data.get("bot_name")
    normalized = raw.strip() if raw and raw.strip() else None
    if normalized is not None:
        import re as _re
        if len(normalized) > 50 or not _re.match(r'^[A-Za-z0-9 _-]+$', normalized):
            raise HTTPException(status_code=422, detail="bot_name: máximo 50 caracteres, solo letras, números, espacios, guiones y guiones bajos.")
    params.append(normalized)
    updates.append(f"bot_name = ${len(params)}")
```

---

## 4. buffer_task.py Change

**File**: `orchestrator_service/services/buffer_task.py` — line 890

Before:
```python
bot_name="TORA",
```

After:
```python
bot_name=tenant_row.get("bot_name") or "TORA",
```

The variable name may differ depending on what the tenant dict is called at that scope. Confirm the exact variable name at line 890 before applying. The pattern `... or "TORA"` handles both `None` and empty string.

---

## 5. Frontend Change

**File**: `frontend_react/src/views/ClinicsView.tsx`

### Placement in the Edit Clinic modal

The modal Tab 1 "Clínicas" already contains a sequence of form fields. Place the `bot_name` input immediately **after** the `clinic_name` field and **before** the `bot_phone_number` field. Rationale: these are the three "identity" fields for the clinic — name, bot name, bot phone.

### Input element

```tsx
<div>
  <label className="block text-sm text-white/60 mb-1">
    {t('clinics.fields.bot_name_label')}
  </label>
  <input
    type="text"
    value={editingClinic.bot_name ?? ''}
    onChange={e => setEditingClinic({ ...editingClinic, bot_name: e.target.value })}
    placeholder={t('clinics.fields.bot_name_placeholder')}
    maxLength={50}
    className="w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-white placeholder-white/30 focus:outline-none focus:border-white/20 text-sm"
  />
  <p className="text-xs text-white/40 mt-1">
    {t('clinics.fields.bot_name_helper')}
  </p>
</div>
```

The `editingClinic` state already holds all tenant fields. Add `bot_name?: string | null` to the TypeScript type for that state if it is explicitly typed.

---

## 6. i18n Keys

Add to the `clinics` object in all three locale files. Suggested position: after `system_prompt_template_help`.

### es.json
```json
"fields": {
  "bot_name_label": "Nombre del bot",
  "bot_name_placeholder": "TORA",
  "bot_name_helper": "Nombre del bot que verán los pacientes. Dejá vacío para usar el default 'TORA'."
}
```

### en.json
```json
"fields": {
  "bot_name_label": "Bot name",
  "bot_name_placeholder": "TORA",
  "bot_name_helper": "The bot name patients will see. Leave empty to use the default 'TORA'."
}
```

### fr.json
```json
"fields": {
  "bot_name_label": "Nom du bot",
  "bot_name_placeholder": "TORA",
  "bot_name_helper": "Nom du bot visible par les patients. Laissez vide pour utiliser 'TORA' par défaut."
}
```

**Note**: The `clinics` object in the locale files currently does NOT have a `fields` sub-object. Add it as a new nested key. Verify no collision with existing flat keys (`clinics.bot_name_label` etc. don't exist today).

---

## 7. Backwards Compatibility

- All existing tenants have `bot_name = NULL` after migration
- `NULL or "TORA"` evaluates to `"TORA"` — zero behavior change for current tenants
- `build_system_prompt(bot_name="TORA")` default parameter in `main.py:6450` remains unchanged as last-resort fallback
- No data backfill needed
