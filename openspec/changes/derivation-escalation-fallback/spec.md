# SPEC: Derivation Escalation Fallback

**Change**: `derivation-escalation-fallback`
**Project**: ClinicForge
**Scope**: `professional_derivation_rules` schema, `check_availability` tool, `book_appointment` tool, `_format_derivation_rules()`, frontend derivation modal
**Out of scope**: Nova, RAG embeddings for rules, escalation analytics, multi-level chains

---

## RFC Keywords

Throughout this document: MUST = mandatory, SHALL = equivalent to MUST, SHOULD = recommended, MAY = optional.

---

## REQ-1: ORM and Schema Update

**Location**: `orchestrator_service/alembic/versions/037_derivation_escalation_fallback.py` + `orchestrator_service/models.py`

### 1.1 Migration `037`

The `upgrade()` function MUST add the following columns to the `professional_derivation_rules` table:

| Column | SQL type | Constraint | Server default |
|--------|----------|-----------|----------------|
| `enable_escalation` | `BOOLEAN` | NOT NULL | `false` |
| `fallback_professional_id` | `INTEGER` | nullable, FK → `professionals.id` ON DELETE SET NULL | — |
| `fallback_team_mode` | `BOOLEAN` | NOT NULL | `false` |
| `max_wait_days_before_escalation` | `INTEGER` | NOT NULL | `7` |
| `escalation_message_template` | `TEXT` | nullable | — |
| `criteria_custom` | `JSONB` | nullable | — |

The `downgrade()` function MUST drop all 6 columns in reverse order.

The migration MUST include an idempotency guard (check column existence via `information_schema.columns` before adding, consistent with project migration style) for `enable_escalation` at minimum.

**Given** the migration runs on an existing database with 5 active derivation rules,
**When** `alembic upgrade head` is executed,
**Then** all 5 existing rows MUST have `enable_escalation = false`, `fallback_team_mode = false`, `max_wait_days_before_escalation = 7`, and all nullable columns NULL. **Zero behavior change for existing rules.**

**Given** the migration is rolled back,
**When** `alembic downgrade -1` is executed,
**Then** all 6 columns MUST be removed and existing non-escalation data MUST remain intact.

### 1.2 SQLAlchemy ORM

`ProfessionalDerivationRule` in `orchestrator_service/models.py` MUST add the following attributes after `description`:

```python
enable_escalation = Column(Boolean, nullable=False, server_default="false")
fallback_professional_id = Column(Integer, ForeignKey("professionals.id", ondelete="SET NULL"), nullable=True)
fallback_team_mode = Column(Boolean, nullable=False, server_default="false")
max_wait_days_before_escalation = Column(Integer, nullable=False, server_default="7")
escalation_message_template = Column(Text, nullable=True)
criteria_custom = Column(JSONB, nullable=True)
```

No other model classes MUST be modified by this change.

---

## REQ-2: Pydantic Schemas and Endpoint Validation

**Location**: `orchestrator_service/admin_routes.py`

### 2.1 `DerivationRuleCreate` and `DerivationRuleUpdate`

Both Pydantic models MUST add the following optional fields:

```python
enable_escalation: bool = False
fallback_professional_id: Optional[int] = None
fallback_team_mode: bool = False
max_wait_days_before_escalation: int = Field(default=7, ge=1, le=30)
escalation_message_template: Optional[str] = None
criteria_custom: Optional[dict] = None
```

The `Field(ge=1, le=30)` constraint on `max_wait_days_before_escalation` MUST cause Pydantic to return HTTP 422 if the value is outside 1–30.

### 2.2 `_validate_derivation_rule()` Additional Checks

The existing validation function MUST be extended with:

1. **Fallback professional tenant isolation** (same pattern as `target_professional_id`):
   - If `data.fallback_professional_id is not None`, MUST query `professionals WHERE id = $1 AND tenant_id = $2`. If not found, raise HTTP 422: `"El profesional de fallback no pertenece a esta clínica"`.

2. **Logical conflict guard**:
   - If `data.fallback_team_mode is True` AND `data.fallback_professional_id is not None`, MUST raise HTTP 422: `"No se puede especificar fallback_professional_id cuando fallback_team_mode es true"`.

3. **Escalation fields required when enabled**:
   - If `data.enable_escalation is True` AND `data.fallback_professional_id is None` AND `data.fallback_team_mode is False`, the system MUST interpret this as implicit team mode (set `fallback_team_mode = True` server-side). MUST NOT raise an error — this is a safe default.

### 2.3 CRUD Persistence

`POST /admin/derivation-rules` and `PUT /admin/derivation-rules/{rule_id}` MUST persist the 6 new fields in their respective INSERT and UPDATE statements.

`GET /admin/derivation-rules` MUST return the 6 new fields for every rule.

All queries MUST include `tenant_id` isolation (Regla de Oro — mandatory).

**Given** a `POST /admin/derivation-rules` request with `enable_escalation = true`, `max_wait_days_before_escalation = 3`, `fallback_team_mode = true`,
**When** the rule is created,
**Then** `GET /admin/derivation-rules` MUST return those exact values for that rule ID.

**Given** a `PUT /admin/derivation-rules/{id}` request with `max_wait_days_before_escalation = 50`,
**When** the endpoint processes the request,
**Then** HTTP 422 MUST be returned with a message referencing the 1–30 range constraint.

**Given** a `PUT /admin/derivation-rules/{id}` request with `fallback_professional_id` referencing a professional from a different tenant,
**When** the endpoint processes the request,
**Then** HTTP 422 MUST be returned: `"El profesional de fallback no pertenece a esta clínica"`.

---

## REQ-3: `_format_derivation_rules()` Prompt Emission

**Location**: `orchestrator_service/main.py`, `_format_derivation_rules()` function

When a rule has `enable_escalation = true`, the function MUST append escalation context to that rule's block in the prompt.

**Required output when `enable_escalation = false` (or absent)**:
```
REGLA N — {rule_name}:
  Aplica a: {condition} / Categorías: {categories}
  Acción: agendar con {prof_name} (ID: {prof_id})
```
(Identical to current behavior.)

**Required output when `enable_escalation = true`**:
```
REGLA N — {rule_name}:
  Aplica a: {condition} / Categorías: {categories}
  Acción primaria: agendar con {prof_name} (ID: {prof_id})
  Escalación activa: si {prof_name} no tiene turnos en {max_wait_days} días → {fallback_description}
  Mensaje para el paciente al escalar: "{escalation_message_template_or_default}"
```

Where `{fallback_description}` MUST be:
- If `fallback_team_mode = true`: `"intentar con cualquier profesional activo del equipo"`
- If `fallback_professional_id` is set: `"intentar con {fallback_prof_name} (ID: {fallback_professional_id})"`

Where `{escalation_message_template_or_default}` MUST be:
- The rule's `escalation_message_template` if non-null and non-empty
- Otherwise the built-in default: `"Hoy {primary} no tiene turnos disponibles en los próximos días, pero podemos coordinar con {fallback} del equipo que también atiende este tipo de casos. ¿Te parece bien?"`

The function signature MUST be extended to accept the fallback professional name (when applicable). The existing `rules` list items MUST be enriched by the caller with `fallback_professional_name` when `fallback_professional_id` is set.

The prompt footer (after all rules) MUST remain:
```
Si ninguna regla coincide → sin filtro de profesional (equipo disponible).
```

**Given** a rule with `enable_escalation = false`,
**When** `_format_derivation_rules()` processes that rule,
**Then** no escalation line MUST appear in the output for that rule.

**Given** a rule with `enable_escalation = true`, `fallback_team_mode = true`, `max_wait_days_before_escalation = 5`,
**When** `_format_derivation_rules()` processes that rule,
**Then** the output MUST contain `"si ... no tiene turnos en 5 días → intentar con cualquier profesional activo del equipo"`.

---

## REQ-4: `check_availability` Tool — Escalation Algorithm

**Location**: `orchestrator_service/main.py`, section `# 0b. DERIVATION RULES` (~line 1404)

### 4.1 Current behavior (preserved when `enable_escalation = false`)

The current inline query at ~line 1409 MUST be extended to also SELECT the 6 new escalation columns. All existing logic (match by `treatment_categories`, `patient_condition`, `priority_order`) MUST remain unchanged.

### 4.2 Escalation check (new behavior when `enable_escalation = true`)

After the rule match, if the primary professional is selected, MUST:

1. Attempt availability search for the primary professional using the tool's existing slot-finding logic, scoped to `max_wait_days_before_escalation` days from today.
2. If **at least 1 slot found**: proceed normally. No escalation triggered.
3. If **zero slots found** AND `enable_escalation = true`: enter escalation path.
   - Log at INFO level: `f"📅 escalation triggered: rule {rule_id}, primary prof {primary_prof_id} has 0 slots in {max_wait_days} days → trying fallback"`
   - Determine fallback target:
     - `fallback_team_mode = true` → clear `derivation_filter_prof_id` (use all active professionals)
     - `fallback_professional_id` set → set `derivation_filter_prof_id = fallback_professional_id`
   - Re-run slot search with fallback target, same window.
   - If fallback slots found: use them. Prepend `escalation_message_template` (or built-in default with `{primary}` and `{fallback}` resolved) to the tool return string.
   - If fallback also empty: return standard "no disponibilidad" message (no escalation message shown to patient).
4. If **zero slots found** AND `enable_escalation = false`: return standard "no disponibilidad" (current behavior).

**Scope constraint**: The escalation path ONLY runs when a derivation rule matched AND the primary professional returned 0 slots. It MUST NOT run when no rule matched or when a rule matched but `target_professional_id` is NULL.

**Invariant**: The slot search window for the primary availability check MUST use `max_wait_days_before_escalation` as the upper bound, not the tool's default search window. This prevents escalating when the primary IS available but just not within the first few days.

### 4.3 SQL change for the derivation rules query

The existing query at ~line 1409 MUST be extended:

```sql
SELECT id, target_professional_id, treatment_categories, patient_condition,
       enable_escalation, fallback_professional_id, fallback_team_mode,
       max_wait_days_before_escalation, escalation_message_template
FROM professional_derivation_rules
WHERE tenant_id = $1 AND is_active = true
ORDER BY priority_order ASC, id ASC
```

**Given** a derivation rule matches treatment "Implantes", `enable_escalation = false`,
**When** `check_availability` is called for "Implantes",
**Then** the result MUST behave identically to the current implementation (no escalation).

**Given** a derivation rule matches, `enable_escalation = true`, primary has 0 slots in 7 days, `fallback_team_mode = true`, team has 2 available slots,
**When** `check_availability` is called,
**Then** the result MUST contain the 2 fallback slots AND the escalation message template (resolved with `{primary}` = primary prof name, `{fallback}` = "el equipo").

**Given** a derivation rule matches, `enable_escalation = true`, primary has 0 slots, fallback also has 0 slots,
**When** `check_availability` is called,
**Then** the result MUST contain the standard "no disponibilidad" message WITHOUT an escalation message header.

---

## REQ-5: `book_appointment` Tool — Escalation Chain Respect

**Location**: `orchestrator_service/main.py`, `book_appointment` tool (~line 2101)

When `check_availability` returns slots from a fallback professional, the agent MUST pass `professional_name` (resolved to the fallback professional's name) to `book_appointment`. This is an agent-level behavior driven by the prompt; the tool itself MUST NOT re-run derivation rule logic.

The `book_appointment` tool MUST NOT independently resolve derivation rules. It MUST honor the `professional_name` parameter as passed by the agent (already the case today). No code change is required in `book_appointment` if `check_availability` already resolves and surfaces the correct professional name in its return value.

**Implementation note**: `check_availability` MUST include the resolved professional name in its escalation return string so the agent can extract it for the subsequent `book_appointment` call. The return format MUST match the existing slot format, e.g.:
```
{escalation_message}

1️⃣ {day} {date} — {time} hs ({fallback_prof_name})
2️⃣ ...
```

**Given** the agent called `check_availability`, received fallback slots for "Dr. García",
**When** the patient confirms slot 1,
**Then** the agent MUST call `book_appointment(professional_name="García", ...)` and NOT `book_appointment(professional_name="Pérez")` (the primary professional who was saturated).

---

## REQ-6: Patient Notification When Fallback Fires

**Location**: `orchestrator_service/main.py`, `check_availability` return string when escalation is triggered

When escalation fires (primary saturated → fallback used), the tool return MUST prepend the escalation message before the slot list. The message MUST:

- Use the `escalation_message_template` if set on the rule (with `{primary}` and `{fallback}` resolved to professional names or "el equipo")
- Fall back to the built-in Spanish default if template is NULL or empty
- MUST be in Rioplatense Spanish (voseo) if using the built-in default
- MUST NOT use corporate language (no "lamentablemente", "le informamos", "estimado paciente")
- MUST NOT expose internal professional IDs

**Built-in default** (used when `escalation_message_template` is NULL):
```
Hoy {primary} no tiene turnos disponibles en los próximos días, pero podemos coordinar con {fallback} que también atiende este tipo de casos. ¿Te parece bien?
```

Where `{primary}` = primary professional's display name (first_name + last_name), `{fallback}` = fallback professional's display name or `"otro profesional del equipo"` if team mode.

---

## REQ-7: Acceptance Scenarios (Gherkin)

### Scenario 1 — Primary professional available (no escalation needed)

```gherkin
Given tenant T has derivation rule R: condition=any, categories=implantes, target=Dr. Pérez (ID=3)
And rule R has enable_escalation=true, max_wait_days_before_escalation=7
And Dr. Pérez has 3 available slots in the next 7 days
When check_availability is called with treatment_name="Implantes"
Then the result MUST contain Dr. Pérez's slots
And the result MUST NOT contain any escalation message
```

### Scenario 2 — Primary saturated, fallback to specific professional

```gherkin
Given tenant T has derivation rule R: condition=any, categories=implantes, target=Dr. Pérez (ID=3)
And rule R has enable_escalation=true, fallback_professional_id=5 (Dr. García), max_wait_days_before_escalation=7
And Dr. Pérez has 0 available slots in the next 7 days
And Dr. García has 2 available slots in the next 7 days
When check_availability is called with treatment_name="Implantes"
Then the result MUST contain Dr. García's 2 slots
And the result MUST contain the escalation message with {primary}="Dr. Pérez" and {fallback}="Dr. García"
And logger MUST have logged INFO "escalation triggered: rule R, primary prof 3 has 0 slots in 7 days"
```

### Scenario 3 — Primary saturated, fallback to team

```gherkin
Given tenant T has derivation rule R: condition=new_patient, categories=cirugia, target=Dra. López (ID=7)
And rule R has enable_escalation=true, fallback_team_mode=true, max_wait_days_before_escalation=5
And escalation_message_template="Hoy {primary} no tiene disponibilidad pero {fallback} puede atenderte esta semana."
And Dra. López has 0 slots in the next 5 days
And team has 4 slots across 2 active professionals
When check_availability is called with treatment_name="Extraccion"
Then the result MUST contain 4 slots (team result)
And the result MUST contain the custom escalation_message_template with {primary}="Dra. López" and {fallback}="el equipo"
```

### Scenario 4 — No fallback configured, enable_escalation=false (current behavior preserved)

```gherkin
Given tenant T has derivation rule R: condition=any, categories=implantes, target=Dr. Pérez (ID=3)
And rule R has enable_escalation=false (default)
And Dr. Pérez has 0 available slots in the next 7 days
When check_availability is called with treatment_name="Implantes"
Then the result MUST contain the standard "no disponibilidad" message
And the result MUST NOT contain any escalation message
And no fallback query MUST be executed
```

---

## REQ-8: Rule Evaluation Order Invariant

The evaluation of which rule matches a patient's treatment request MUST remain deterministic.

- Rules MUST be evaluated in `priority_order ASC, id ASC` order (unchanged from current).
- The FIRST matching rule wins (unchanged from current).
- Escalation logic only runs AFTER a rule has matched. It MUST NOT change which rule matches.
- Adding escalation fields to a rule MUST NOT affect its sort position.

This invariant MUST be preserved in the SQL query (current `ORDER BY priority_order ASC, id ASC`) and in the Python evaluation loop (current `break` on first match).

---

## REQ-9: i18n Keys

All new UI text in the frontend derivation modal MUST use `useTranslation()` and be added to all 3 locale files: `es.json`, `en.json`, `fr.json`.

Required new keys under `settings.derivation.escalation.*`:

| Key | Spanish value |
|-----|---------------|
| `settings.derivation.escalation.toggle` | `"Escalación automática"` |
| `settings.derivation.escalation.toggleHint` | `"Si el profesional asignado no tiene turnos, el bot intentará con otro profesional antes de decirle al paciente que no hay disponibilidad."` |
| `settings.derivation.escalation.maxWaitDays` | `"Días de espera antes de escalar"` |
| `settings.derivation.escalation.maxWaitDaysHint` | `"Si no hay turnos en este período, se activa el fallback. Rango: 1–30 días."` |
| `settings.derivation.escalation.fallbackMode` | `"Fallback a"` |
| `settings.derivation.escalation.fallbackTeam` | `"Cualquier profesional activo del equipo"` |
| `settings.derivation.escalation.fallbackSpecific` | `"Profesional específico"` |
| `settings.derivation.escalation.fallbackProfessional` | `"Profesional de fallback"` |
| `settings.derivation.escalation.messageTemplate` | `"Mensaje al paciente cuando escala (opcional)"` |
| `settings.derivation.escalation.messageTemplatePlaceholder` | `"Ej: Hoy {primary} no tiene disponibilidad, pero {fallback} puede atenderte esta semana."` |

---

## Dependencies

- REQ-1 (migration) MUST run before REQ-2 can be verified end-to-end.
- REQ-2 (Pydantic + endpoints) MUST be implemented before REQ-3 and REQ-4 have real data to test against.
- REQ-3 (`_format_derivation_rules()`) and REQ-4 (`check_availability`) are independent of each other but both depend on REQ-1 + REQ-2.
- REQ-5 (`book_appointment`) depends on REQ-4 producing the correct return format.
- REQ-9 (i18n) MUST be added before the frontend modal (Phase 5) goes live.

---

## Out of Scope (explicit)

- Nova tool changes
- Escalation event tracking / analytics
- Multi-level fallback chains (primary → fallback1 → fallback2)
- Automatic proactive escalation (without patient request)
- `criteria_custom` field evaluation in tools (stub only; document schema, ignore in evaluation)
- Changes to WhatsApp service, BFF, or unrelated frontend views
