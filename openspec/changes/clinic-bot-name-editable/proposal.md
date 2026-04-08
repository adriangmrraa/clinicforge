# SDD Proposal: Clinic Bot Name Editable

**Change**: `clinic-bot-name-editable`
**Status**: PROPOSED
**Date**: 2026-04-07
**Author**: SDD Orchestrator

---

## 1. Intent

### Problem Statement

The bot's display name "TORA" is hardcoded in `buffer_task.py:890`:

```python
bot_name="TORA",  # hardcoded — no tenant can override
```

This means every clinic using ClinicForge has a bot named "TORA" with no way to change it from the UI. A clinic called "DentalPro" can't name their bot "Nova" or "Mia". This is a multi-tenancy failure: per-tenant customization is impossible for one of the most patient-visible pieces of data.

### Why This Matters

- **Brand identity**: Clinics want to own the bot's name as part of their brand
- **Multi-tenancy**: A SaaS platform must let each tenant configure their own identity
- **Current workaround**: None exists — support would need to redeploy for each name change

---

## 2. Scope

### In scope
- Add `bot_name VARCHAR(50) NULL` column to `tenants` table via Alembic migration
- Wire the column through: ORM → endpoint → `buffer_task.py` fallback chain
- UI: single text input in the Edit Clinic modal (Tab 1)
- i18n: 3 keys in es/en/fr

### Out of scope
- Per-professional bot names
- Bot avatar or persona beyond the name
- Any prompt logic changes beyond the existing `{bot_name}` placeholder

---

## 3. Approach

Store `bot_name` as a nullable `VARCHAR(50)` on the `tenants` table. NULL means "use default TORA". This is purely additive — zero migration risk, zero breaking change for existing tenants.

The existing `build_system_prompt()` function already accepts a `bot_name` parameter and uses it via `{bot_name}` placeholders throughout the prompt. The only broken link is `buffer_task.py:890` hardcoding `"TORA"` instead of reading the tenant row.

**Why DB column over config JSONB or in-code list:**
- DB column: typed, queryable, validatable at API level, zero config drift
- JSONB config key: no schema enforcement, harder to validate length/pattern
- In-code list: would require redeploy per new tenant, defeats the purpose

---

## 4. Success Criteria

1. A tenant with `bot_name = "Nova"` has the agent greet patients as "Nova"
2. A tenant with `bot_name = NULL` has the agent greet patients as "TORA" (default)
3. The UI allows setting and clearing the bot name from the Edit Clinic modal
4. Invalid values (too long, special chars) are rejected with HTTP 422

---

## 5. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Migration conflict (another SDD change adds column to tenants first) | Low | Low | Check `down_revision` at merge time |
| Empty string persisted as bot name | Low | Medium | Endpoint normalizes `""` → `None` before storing |

Overall risk: **LOW** — purely additive, no existing behavior changes for current tenants.
