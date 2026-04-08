# SDD Tasks: Clinic Bot Name Editable

**Change**: `clinic-bot-name-editable`
**Status**: PENDING
**Date**: 2026-04-07
**Methodology**: TDD strict — test before implementation in every phase

---

## Dependency Graph

```
Phase 1 (migration + ORM)
    ↓
Phase 2 (backend endpoint)
    ↓
Phase 3 (buffer_task)
    ↓
Phase 4 (frontend + i18n)
    ↓
Phase 5 (e2e verification)
```

---

## Phase 1 — Database

### 1.1 Write Alembic migration
- [ ] Create `orchestrator_service/alembic/versions/033_clinic_bot_name.py`
- [ ] `upgrade()`: `op.add_column("tenants", sa.Column("bot_name", sa.String(50), nullable=True))`
- [ ] `downgrade()`: `op.drop_column("tenants", "bot_name")`
- [ ] Verify `down_revision = "032"` (or bump if other migrations merged first)
- [ ] Run `alembic upgrade head` locally and confirm no error

### 1.2 ORM update
- [ ] Add `bot_name = Column(String(50), nullable=True)` to `Tenant` class in `models.py`
- [ ] Position: after `ai_engine_mode` column

---

## Phase 2 — Backend Endpoint

### 2.1 Test: GET includes bot_name
- [ ] Write test: `GET /admin/tenants` response includes `bot_name` field (None for existing tenant)

### 2.2 Test: PUT validates and persists bot_name
- [ ] Write test: valid name `"Nova"` → 200, DB row has `bot_name = "Nova"`
- [ ] Write test: empty string `""` → 200, DB row has `bot_name = NULL`
- [ ] Write test: invalid pattern `"N@va!!"` → 422
- [ ] Write test: too long (51 chars) → 422

### 2.3 Implementation
- [ ] Add `bot_name` to the SELECT in `get_tenants()` (raw SQL string)
- [ ] Add `bot_name` handler block in `update_tenant()` with validation + normalization (see design.md §3)

### 2.4 Verify no schema needed
- [ ] Confirm endpoint uses `Dict[str, Any]` — no Pydantic schema to update
- [ ] (If a TenantCreate/TenantUpdate Pydantic schema exists, add `bot_name: Optional[str] = None` with validators — current code does NOT use one, so this step is a no-op)

---

## Phase 3 — buffer_task.py

### 3.1 Test: bot_name flows into build_system_prompt
- [ ] Write test: tenant row with `bot_name = "Mia"` → `build_system_prompt` called with `bot_name="Mia"`
- [ ] Write test: tenant row with `bot_name = None` → `build_system_prompt` called with `bot_name="TORA"`
- [ ] Write test: tenant row with `bot_name = ""` → `build_system_prompt` called with `bot_name="TORA"`

### 3.2 Implementation
- [ ] In `buffer_task.py:890`, replace:
  ```python
  bot_name="TORA",
  ```
  with:
  ```python
  bot_name=tenant_row.get("bot_name") or "TORA",
  ```
  (adjust variable name to match actual tenant dict at that scope)

### 3.3 Regression check
- [ ] Confirm no other hardcoded `"TORA"` remains in `buffer_task.py`
- [ ] Run existing buffer_task tests — all must pass

---

## Phase 4 — Frontend

### 4.1 Add input field to Edit Clinic modal
- [ ] In `ClinicsView.tsx`, add `bot_name` text input after `clinic_name` field
- [ ] Use dark-mode input classes: `bg-white/[0.04] border border-white/[0.08] text-white`
- [ ] Wire to `editingClinic.bot_name` state (null-safe: `?? ''`)
- [ ] Add `maxLength={50}` attribute

### 4.2 i18n keys
- [ ] Add `clinics.fields.bot_name_label/placeholder/helper` to `es.json`
- [ ] Add same keys to `en.json`
- [ ] Add same keys to `fr.json`
- [ ] Verify no key collision with existing flat `clinics.*` keys

### 4.3 Save/load flow
- [ ] Confirm `editingClinic` is populated from `GET /admin/tenants` response (includes `bot_name`)
- [ ] Confirm save action sends `bot_name` in the PUT payload
- [ ] Manual test: set name → save → reload modal → value persists

---

## Phase 5 — End-to-End Verification

### 5.1 Happy path
- [ ] Via UI: set `bot_name = "Nova"` for a tenant → save
- [ ] Verify DB: `SELECT bot_name FROM tenants WHERE id = X` returns `"Nova"`
- [ ] Send a test message via the AI agent for that tenant
- [ ] Verify the system prompt contains `"Nova"` (not `"TORA"`)

### 5.2 Fallback path
- [ ] Clear `bot_name` (save empty) → DB row has NULL
- [ ] Send a test message via the AI agent → system prompt contains `"TORA"`

---

## Acceptance Checklist

- [ ] All Phase 1–3 tests pass (`pytest tests/`)
- [ ] GET response includes `bot_name`
- [ ] PUT with invalid pattern returns 422
- [ ] `buffer_task.py` uses tenant's `bot_name` with TORA fallback
- [ ] UI shows the field, saves correctly, loads correctly
- [ ] i18n keys present in es/en/fr
- [ ] Existing tenants unaffected (bot name remains TORA)
