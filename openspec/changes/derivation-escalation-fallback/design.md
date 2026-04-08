# DESIGN: Derivation Escalation Fallback

**Change**: `derivation-escalation-fallback`
**Status**: DESIGNED
**Date**: 2026-04-07

---

## Architecture Decisions

### D1: Where escalation logic lives — tool vs. agent

**Decision: In the `check_availability` tool (transparent to the agent)**

The tool already owns the derivation rule query inline (~line 1404). Escalation is a natural extension of that same block: try primary → if empty and escalation enabled → try fallback → return whichever has slots.

The agent receives a result that already has the correct slots (primary or fallback). The agent's only responsibility is to use the professional name embedded in the slot string when calling `book_appointment`.

**Rejected: Agent-level escalation** (agent calls `check_availability` twice: once for primary, once for fallback). This requires the agent to reason about when to retry, which professional to retry with, and what message to show — all non-trivial for an LLM and fragile under prompt regressions. The tool approach is deterministic.

---

### D2: How to scope the "is primary available" check before escalating

**Decision: Use `max_wait_days_before_escalation` as the window for BOTH the primary check and the fallback search.**

We do NOT want to escalate if the primary has slots available in day 8 and the rule has `max_wait_days = 7`. We check: "does the primary have ANY slot in the next N days?" If yes → no escalation. This keeps the semantics simple: "the patient will wait at most N days for the primary; if not, escalate".

The existing `check_availability` already iterates day-by-day up to a configurable limit. The escalation check simply caps that iteration at `max_wait_days_before_escalation` for the primary professional specifically.

---

### D3: Fallback resolution when `fallback_team_mode = true`

**Decision: Re-use the existing "no derivation filter" code path**

When `fallback_team_mode = true`, the escalation path clears `derivation_filter_prof_id` and runs the slot search against all active professionals for the tenant (the existing baseline query). No new SQL or logic is needed.

This is correct and efficient: the existing multi-professional slot scan already handles this case optimally.

---

## Alembic Migration: `037_derivation_escalation_fallback.py`

**File**: `orchestrator_service/alembic/versions/037_derivation_escalation_fallback.py`
**Revision**: `037`
**Down revision**: `036`

```python
# upgrade()
def upgrade():
    conn = op.get_bind()
    existing = [row[0] for row in conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='professional_derivation_rules'"
    )]
    if "enable_escalation" not in existing:
        op.add_column("professional_derivation_rules",
            sa.Column("enable_escalation", sa.Boolean(), nullable=False,
                      server_default=sa.text("false")))
    if "fallback_professional_id" not in existing:
        op.add_column("professional_derivation_rules",
            sa.Column("fallback_professional_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_derivation_fallback_professional",
            "professional_derivation_rules", "professionals",
            ["fallback_professional_id"], ["id"],
            ondelete="SET NULL"
        )
    if "fallback_team_mode" not in existing:
        op.add_column("professional_derivation_rules",
            sa.Column("fallback_team_mode", sa.Boolean(), nullable=False,
                      server_default=sa.text("false")))
    if "max_wait_days_before_escalation" not in existing:
        op.add_column("professional_derivation_rules",
            sa.Column("max_wait_days_before_escalation", sa.Integer(),
                      nullable=False, server_default=sa.text("7")))
    if "escalation_message_template" not in existing:
        op.add_column("professional_derivation_rules",
            sa.Column("escalation_message_template", sa.Text(), nullable=True))
    if "criteria_custom" not in existing:
        op.add_column("professional_derivation_rules",
            sa.Column("criteria_custom", postgresql.JSONB(), nullable=True))

# downgrade()
def downgrade():
    op.drop_constraint("fk_derivation_fallback_professional",
                       "professional_derivation_rules", type_="foreignkey")
    op.drop_column("professional_derivation_rules", "criteria_custom")
    op.drop_column("professional_derivation_rules", "escalation_message_template")
    op.drop_column("professional_derivation_rules", "max_wait_days_before_escalation")
    op.drop_column("professional_derivation_rules", "fallback_team_mode")
    op.drop_column("professional_derivation_rules", "fallback_professional_id")
    op.drop_column("professional_derivation_rules", "enable_escalation")
```

---

## ORM Diff — `ProfessionalDerivationRule`

Add after `description = Column(Text, nullable=True)`:

```python
# --- Escalation fallback fields (migration 037) ---
enable_escalation = Column(Boolean, nullable=False, server_default="false")
fallback_professional_id = Column(
    Integer, ForeignKey("professionals.id", ondelete="SET NULL"), nullable=True
)
fallback_team_mode = Column(Boolean, nullable=False, server_default="false")
max_wait_days_before_escalation = Column(Integer, nullable=False, server_default="7")
escalation_message_template = Column(Text, nullable=True)
criteria_custom = Column(JSONB, nullable=True)
```

No changes to `__table_args__` are needed (existing indexes cover `tenant_id`).

---

## Pydantic Schema Diff

### `DerivationRuleCreate` and `DerivationRuleUpdate`

Add after `description: Optional[str] = None`:

```python
# Escalation fields
enable_escalation: bool = False
fallback_professional_id: Optional[int] = None
fallback_team_mode: bool = False
max_wait_days_before_escalation: int = Field(default=7, ge=1, le=30)
escalation_message_template: Optional[str] = None
criteria_custom: Optional[dict] = None
```

### `_validate_derivation_rule()` additions

```python
# After existing target_professional_id check:
if data.fallback_professional_id is not None and data.fallback_team_mode:
    raise HTTPException(422,
        "No se puede especificar fallback_professional_id cuando fallback_team_mode es true")

if data.fallback_professional_id is not None:
    fb_exists = await db.pool.fetchval(
        "SELECT id FROM professionals WHERE id = $1 AND tenant_id = $2",
        data.fallback_professional_id, tenant_id,
    )
    if not fb_exists:
        raise HTTPException(422,
            "El profesional de fallback no pertenece a esta clínica")

# Implicit team mode when escalation enabled but no fallback configured:
if data.enable_escalation and not data.fallback_professional_id and not data.fallback_team_mode:
    data.fallback_team_mode = True  # safe default, mutate before INSERT
```

---

## `_format_derivation_rules()` — Before / After

### Before (current behavior):

Prompt block for a rule:
```
REGLA 1 — Implantes VIP:
  Aplica a: new_patient / Categorías: implantes,cirugia
  Acción: agendar con Dr. Juan Pérez (ID: 3)
```

### After (new behavior when `enable_escalation = true`):

```
REGLA 1 — Implantes VIP:
  Aplica a: new_patient / Categorías: implantes,cirugia
  Acción primaria: agendar con Dr. Juan Pérez (ID: 3)
  Escalación activa: si Dr. Juan Pérez no tiene turnos en 7 días → intentar con Dr. Carlos García (ID: 5)
  Mensaje para el paciente al escalar: "Hoy Dr. Pérez no tiene turnos disponibles en los próximos días, pero podemos coordinar con Dr. García que también atiende este tipo de casos. ¿Te parece bien?"
```

### Pseudocode for the new formatter:

```python
def _format_derivation_rules(rules: list) -> str:
    if not rules:
        return ""
    lines = ["DERIVACIÓN DE PACIENTES — REGLAS (evaluar EN ORDEN, primera que coincida gana):"]
    for i, rule in enumerate(rules, start=1):
        rule_name = rule.get("rule_name") or f"Regla {i}"
        condition = rule.get("patient_condition") or "cualquier paciente"
        categories = rule.get("categories") or ""
        prof_name = rule.get("target_professional_name")
        prof_id = rule.get("target_professional_id")
        enable_esc = rule.get("enable_escalation", False)
        fallback_pid = rule.get("fallback_professional_id")
        fallback_pname = rule.get("fallback_professional_name")  # NEW: enriched by caller
        fallback_team = rule.get("fallback_team_mode", False)
        max_days = rule.get("max_wait_days_before_escalation", 7)
        esc_msg = rule.get("escalation_message_template")

        lines.append(f"REGLA {i} — {rule_name}:")
        cat_suffix = f" / Categorías: {categories}" if categories else ""
        lines.append(f"  Aplica a: {condition}{cat_suffix}")

        if not enable_esc:
            # Current behavior unchanged
            if prof_name and prof_id:
                lines.append(f"  Acción: agendar con {prof_name} (ID: {prof_id})")
            else:
                lines.append("  Acción: sin filtro de profesional (equipo)")
        else:
            # New escalation-aware block
            if prof_name and prof_id:
                lines.append(f"  Acción primaria: agendar con {prof_name} (ID: {prof_id})")
            else:
                lines.append("  Acción primaria: sin filtro de profesional (equipo)")

            if fallback_team:
                fallback_desc = "intentar con cualquier profesional activo del equipo"
                fallback_display = "el equipo"
            elif fallback_pid and fallback_pname:
                fallback_desc = f"intentar con {fallback_pname} (ID: {fallback_pid})"
                fallback_display = fallback_pname
            else:
                fallback_desc = "intentar con cualquier profesional activo del equipo"
                fallback_display = "el equipo"

            lines.append(
                f"  Escalación activa: si {prof_name or 'el profesional asignado'} "
                f"no tiene turnos en {max_days} días → {fallback_desc}"
            )

            if not esc_msg:
                esc_msg = (
                    f"Hoy {prof_name or '{primary}'} no tiene turnos disponibles en los próximos días, "
                    f"pero podemos coordinar con {fallback_display} que también atiende este tipo de casos. "
                    "¿Te parece bien?"
                )
            lines.append(f'  Mensaje para el paciente al escalar: "{esc_msg}"')

    lines.append("")
    lines.append("Si ninguna regla coincide → sin filtro de profesional (equipo disponible).")
    return "\n".join(lines)
```

**Caller enrichment**: The caller of `_format_derivation_rules()` (inside `build_system_prompt()`) already receives `derivation_rules` list. The list must be enriched with `fallback_professional_name` before being passed. This enrichment MUST happen in `buffer_task.py` when fetching derivation rules — add a LEFT JOIN on `professionals` aliased as `fp` for the fallback:

```sql
SELECT dr.id, dr.rule_name, dr.patient_condition, dr.treatment_categories,
       dr.target_type, dr.target_professional_id, dr.priority_order,
       dr.is_active, dr.description,
       dr.enable_escalation, dr.fallback_professional_id,
       dr.fallback_team_mode, dr.max_wait_days_before_escalation,
       dr.escalation_message_template,
       p.first_name || ' ' || COALESCE(p.last_name, '') AS target_professional_name,
       fp.first_name || ' ' || COALESCE(fp.last_name, '') AS fallback_professional_name
FROM professional_derivation_rules dr
LEFT JOIN professionals p ON dr.target_professional_id = p.id
LEFT JOIN professionals fp ON dr.fallback_professional_id = fp.id
WHERE dr.tenant_id = $1 AND dr.is_active = true
ORDER BY dr.priority_order ASC, dr.id ASC
```

---

## `check_availability` — Escalation Algorithm Pseudocode

The change is isolated to the `# 0b. DERIVATION RULES` block (~line 1404). Full pseudocode:

```python
# 0b. DERIVATION RULES (extended for escalation)
derivation_filter_prof_id: Optional[int] = None
escalation_message_prefix: str = ""  # NEW

if not clean_name and not forced_prof_id and treatment_name:
    try:
        rules = await db.pool.fetch("""
            SELECT id, target_professional_id, treatment_categories, patient_condition,
                   enable_escalation, fallback_professional_id, fallback_team_mode,
                   max_wait_days_before_escalation, escalation_message_template
            FROM professional_derivation_rules
            WHERE tenant_id = $1 AND is_active = true
            ORDER BY priority_order ASC, id ASC
        """, tenant_id)

        tname_lower = (treatment_name or "").lower()
        for rule in rules:
            cats = rule.get("treatment_categories") or ""
            cat_list = [c.strip().lower() for c in cats.split(",") if c.strip()]
            if cat_list and any(c in tname_lower for c in cat_list):
                primary_pid = rule.get("target_professional_id")
                enable_esc = rule.get("enable_escalation", False)

                if primary_pid:
                    derivation_filter_prof_id = int(primary_pid)

                    if enable_esc:
                        # Check primary availability within max_wait_days window
                        max_days = rule.get("max_wait_days_before_escalation") or 7
                        primary_slots = await _count_slots_for_prof(
                            tenant_id, primary_pid, treatment_name, max_days
                        )
                        if primary_slots == 0:
                            # PRIMARY SATURATED — attempt fallback
                            logger.info(
                                f"escalation triggered: rule {rule['id']}, "
                                f"primary prof {primary_pid} has 0 slots in {max_days} days → trying fallback"
                            )
                            fb_team = rule.get("fallback_team_mode", False)
                            fb_pid = rule.get("fallback_professional_id")
                            if fb_team or (fb_pid is None and not fb_team):
                                # Team mode: clear filter, use all active professionals
                                derivation_filter_prof_id = None
                                fallback_label = "el equipo"
                            else:
                                derivation_filter_prof_id = int(fb_pid)
                                # Resolve name for message
                                fb_row = await db.pool.fetchrow(
                                    "SELECT first_name, last_name FROM professionals "
                                    "WHERE id = $1 AND tenant_id = $2",
                                    fb_pid, tenant_id
                                )
                                fallback_label = f"{fb_row['first_name']} {fb_row.get('last_name','')}" if fb_row else "el equipo"

                            # Resolve primary name for message
                            pr_row = await db.pool.fetchrow(
                                "SELECT first_name, last_name FROM professionals "
                                "WHERE id = $1 AND tenant_id = $2",
                                primary_pid, tenant_id
                            )
                            primary_label = f"{pr_row['first_name']} {pr_row.get('last_name','')}" if pr_row else "el profesional asignado"

                            tmpl = rule.get("escalation_message_template") or (
                                f"Hoy {primary_label} no tiene turnos disponibles en los próximos días, "
                                f"pero podemos coordinar con {fallback_label} "
                                f"que también atiende este tipo de casos. ¿Te parece bien?"
                            )
                            escalation_message_prefix = tmpl.replace(
                                "{primary}", primary_label
                            ).replace("{fallback}", fallback_label) + "\n\n"
                        # else: primary has slots — continue normally
                break
    except Exception as _der_err:
        logger.debug(f"derivation rules lookup skipped: {_der_err}")

# ... existing slot query continues using derivation_filter_prof_id ...
# At the END of the function, prepend escalation_message_prefix to result string if set:
# return escalation_message_prefix + existing_result
```

**`_count_slots_for_prof` helper** (new private async function):

```python
async def _count_slots_for_prof(
    tenant_id: int, prof_id: int, treatment_name: str, max_days: int
) -> int:
    """Count available slots for a specific professional in the next max_days days.
    Returns 0 if none found. Used only for escalation pre-check."""
    # Reuse existing slot-finding logic with a max_days cap
    # Returns integer count of available slots (0 = saturated)
```

This helper MUST be a lightweight version of the existing slot-finding loop, returning only a count (not formatting strings). It avoids code duplication by extracting the core iteration logic.

---

## Frontend Modal — Escalation Sub-section

**File**: `frontend_react/src/views/ClinicsView.tsx`

The escalation sub-section is added at the bottom of the form inside the derivation rule modal, before the action buttons.

**Layout (conditional rendering)**:

```tsx
{/* Escalation section — always shown as a collapsible toggle */}
<div className="border border-white/[0.06] rounded-lg p-4 space-y-4 bg-white/[0.01]">
  <div className="flex items-center justify-between">
    <div>
      <p className="text-sm font-semibold text-white/70">{t('settings.derivation.escalation.toggle')}</p>
      <p className="text-xs text-white/30 mt-0.5">{t('settings.derivation.escalation.toggleHint')}</p>
    </div>
    <button type="button"
      onClick={() => setDerivationForm(p => ({ ...p, enable_escalation: !p.enable_escalation }))}
      className={`relative w-10 h-5 rounded-full transition-colors ${derivationForm.enable_escalation ? 'bg-blue-500' : 'bg-white/10'}`}>
      <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform ${derivationForm.enable_escalation ? 'translate-x-5' : ''}`} />
    </button>
  </div>

  {derivationForm.enable_escalation && (
    <>
      {/* max_wait_days_before_escalation */}
      <div className="space-y-1">
        <label className="text-sm font-semibold text-white/60">
          {t('settings.derivation.escalation.maxWaitDays')}
        </label>
        <input type="number" min={1} max={30}
          value={derivationForm.max_wait_days_before_escalation ?? 7}
          onChange={e => setDerivationForm(p => ({ ...p, max_wait_days_before_escalation: parseInt(e.target.value) || 7 }))}
          className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white ..." />
        <p className="text-xs text-white/30">{t('settings.derivation.escalation.maxWaitDaysHint')}</p>
      </div>

      {/* fallback_team_mode radio */}
      <div className="space-y-2">
        <label className="text-sm font-semibold text-white/60">{t('settings.derivation.escalation.fallbackMode')}</label>
        <label className="flex items-center gap-3 cursor-pointer ...">
          <input type="radio" checked={derivationForm.fallback_team_mode === true}
            onChange={() => setDerivationForm(p => ({ ...p, fallback_team_mode: true, fallback_professional_id: undefined }))} />
          <span className="text-sm text-white/70">{t('settings.derivation.escalation.fallbackTeam')}</span>
        </label>
        <label className="flex items-center gap-3 cursor-pointer ...">
          <input type="radio" checked={derivationForm.fallback_team_mode === false}
            onChange={() => setDerivationForm(p => ({ ...p, fallback_team_mode: false }))} />
          <span className="text-sm text-white/70">{t('settings.derivation.escalation.fallbackSpecific')}</span>
        </label>
      </div>

      {/* fallback_professional_id — only when specific mode */}
      {!derivationForm.fallback_team_mode && (
        <div className="space-y-1">
          <label className="text-sm font-semibold text-white/60">
            {t('settings.derivation.escalation.fallbackProfessional')}
          </label>
          <select value={derivationForm.fallback_professional_id || ''}
            onChange={e => setDerivationForm(p => ({ ...p, fallback_professional_id: e.target.value ? parseInt(e.target.value) : undefined }))}
            className="w-full px-4 py-2 bg-[#0d1117] border border-white/[0.08] rounded-lg text-white ...">
            <option value="">—</option>
            {derivationProfessionals
              .filter(p => p.id !== derivationForm.target_professional_id)
              .map(p => (
                <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>
              ))
            }
          </select>
        </div>
      )}

      {/* escalation_message_template */}
      <div className="space-y-1">
        <label className="text-sm font-semibold text-white/60">
          {t('settings.derivation.escalation.messageTemplate')}
        </label>
        <textarea value={derivationForm.escalation_message_template || ''} rows={3}
          onChange={e => setDerivationForm(p => ({ ...p, escalation_message_template: e.target.value }))}
          placeholder={t('settings.derivation.escalation.messageTemplatePlaceholder')}
          className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white ... resize-none text-sm" />
      </div>
    </>
  )}
</div>
```

**TypeScript type extension** for `DerivationRule`:

```typescript
interface DerivationRule {
  // ... existing fields ...
  enable_escalation?: boolean;
  fallback_professional_id?: number;
  fallback_team_mode?: boolean;
  max_wait_days_before_escalation?: number;
  escalation_message_template?: string;
  criteria_custom?: Record<string, unknown>;
}
```

**`derivationForm` state initialization** for new fields:

```typescript
const emptyDerivationForm = {
  // ... existing defaults ...
  enable_escalation: false,
  fallback_professional_id: undefined,
  fallback_team_mode: false,
  max_wait_days_before_escalation: 7,
  escalation_message_template: '',
  criteria_custom: undefined,
};
```

---

## i18n Keys List

New keys to add to `es.json`, `en.json`, `fr.json` under `settings.derivation.escalation`:

```json
// es.json
"escalation": {
  "toggle": "Escalación automática",
  "toggleHint": "Si el profesional asignado no tiene turnos, el bot intentará con otro profesional antes de decirle al paciente que no hay disponibilidad.",
  "maxWaitDays": "Días de espera antes de escalar",
  "maxWaitDaysHint": "Si no hay turnos en este período, se activa el fallback. Rango: 1–30 días.",
  "fallbackMode": "Fallback a",
  "fallbackTeam": "Cualquier profesional activo del equipo",
  "fallbackSpecific": "Profesional específico",
  "fallbackProfessional": "Profesional de fallback",
  "messageTemplate": "Mensaje al paciente cuando escala (opcional)",
  "messageTemplatePlaceholder": "Ej: Hoy {primary} no tiene disponibilidad, pero {fallback} puede atenderte esta semana."
}

// en.json
"escalation": {
  "toggle": "Automatic escalation",
  "toggleHint": "If the assigned professional has no slots, the bot will try another professional before telling the patient there is no availability.",
  "maxWaitDays": "Wait days before escalating",
  "maxWaitDaysHint": "If no slots found within this period, the fallback is triggered. Range: 1–30 days.",
  "fallbackMode": "Fall back to",
  "fallbackTeam": "Any active team professional",
  "fallbackSpecific": "Specific professional",
  "fallbackProfessional": "Fallback professional",
  "messageTemplate": "Message to patient when escalating (optional)",
  "messageTemplatePlaceholder": "E.g.: Today {primary} has no availability, but {fallback} can see you this week."
}

// fr.json
"escalation": {
  "toggle": "Escalade automatique",
  "toggleHint": "Si le professionnel assigné n'a pas de créneaux, le bot essaiera avec un autre professionnel avant d'informer le patient.",
  "maxWaitDays": "Jours d'attente avant escalade",
  "maxWaitDaysHint": "Si aucun créneau n'est trouvé dans cette période, le fallback est déclenché. Plage : 1–30 jours.",
  "fallbackMode": "Fallback vers",
  "fallbackTeam": "N'importe quel professionnel actif",
  "fallbackSpecific": "Professionnel spécifique",
  "fallbackProfessional": "Professionnel de secours",
  "messageTemplate": "Message au patient lors de l'escalade (optionnel)",
  "messageTemplatePlaceholder": "Ex : Aujourd'hui {primary} n'a pas de disponibilité, mais {fallback} peut vous recevoir cette semaine."
}
```

---

## Backwards Compatibility

- `enable_escalation` defaults to `false` in DB and Pydantic. All existing rules are unaffected.
- `_format_derivation_rules()` produces identical output for rules with `enable_escalation = false`.
- `check_availability` behavior for rules without escalation: identical (the escalation check only runs if `enable_escalation = true` AND a derivation rule matched AND `target_professional_id` is set).
- Frontend: the escalation section is collapsed by default (`enable_escalation = false`). Existing rules render the form without showing the escalation fields.

---

## Security

- Tenant isolation is maintained:
  - `fallback_professional_id` validated against `professionals WHERE tenant_id = X` in `_validate_derivation_rule()` (same guard as `target_professional_id`).
  - All `check_availability` queries use `tenant_id` from `current_tenant_id.get()` context var (never from request params).
  - `_format_derivation_rules()` only receives pre-fetched tenant-scoped rules.
- No new attack surface: `criteria_custom` JSONB is stored as-is and never evaluated in this change.
