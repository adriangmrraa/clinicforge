# SPEC: Clinic Support, Complaints & Review Config

**Change**: `clinic-support-complaints-config`
**Project**: ClinicForge
**Scope**: Tenant schema, admin endpoint, system prompt formatter, `derivhumano` tool, followup job, frontend modal
**Out of scope**: Nova, complaint history dashboard, external review API

---

## RFC Keywords

Throughout this document: MUST = mandatory, SHALL = equivalent to MUST, SHOULD = recommended, MAY = optional.

---

## REQ-1: Tenant Model — New Columns

The `tenants` table MUST gain the following 7 nullable columns. All MUST be nullable with no default (except `auto_send_review_link_after_followup`), so existing rows are unaffected.

| Column | SQL Type | Nullable | Default | Constraint |
|--------|----------|----------|---------|------------|
| `complaint_escalation_email` | TEXT | YES | — | Valid email format when present |
| `complaint_escalation_phone` | TEXT | YES | — | No format constraint enforced at DB level |
| `expected_wait_time_minutes` | INTEGER | YES | — | Must be > 0 when present |
| `revision_policy` | TEXT | YES | — | Max length 2000 chars enforced at app layer |
| `review_platforms` | JSONB | YES | — | Array of `{name, url, show_after_days}` objects |
| `complaint_handling_protocol` | JSONB | YES | — | Object with keys `level_1`, `level_2`, `level_3` |
| `auto_send_review_link_after_followup` | BOOLEAN | NO | `false` | — |

**Tenant isolation**: All reads and writes MUST include `WHERE tenant_id = $x`. The columns are on the `tenants` table — isolation is implicit via tenant row ownership.

**SQLAlchemy model**: The `Tenant` class in `orchestrator_service/models.py` MUST add the 7 new column definitions in the same order as the Alembic migration.

**Backward compatibility**: All 7 columns are nullable (except the boolean which defaults to false). Existing tenants that do not configure these fields MUST experience no behavior change.

---

## REQ-2: Pydantic Validation Schemas

### REQ-2.1 — `ReviewPlatformItem` schema

```
name: str          (required, max 100 chars)
url: str           (required, must be a valid HTTP/HTTPS URL)
show_after_days: int (optional, default 1, must be >= 1)
```

**Given** `url = "not-a-url"`, **When** validated, **Then** MUST raise a `422 Unprocessable Entity` with a message referencing the `url` field.

**Given** `show_after_days = 0`, **When** validated, **Then** MUST raise `422` with a message referencing `show_after_days`.

### REQ-2.2 — `ComplaintHandlingProtocol` schema

```
level_1: str    (optional — if absent, defaults to generic empathize text)
level_2: str    (optional — if absent, defaults to generic escalation text)
level_3: str    (optional — if absent, defaults to derivhumano trigger)
```

All three fields are plain text descriptions, max 500 chars each. Unknown additional keys MUST be rejected.

### REQ-2.3 — Validation in `update_tenant` endpoint

When `review_platforms` is provided in the request body:
- MUST be a JSON array.
- Each element MUST conform to `ReviewPlatformItem`.
- An empty array `[]` is valid (clears all platforms).
- A non-array value MUST return 422.

When `complaint_handling_protocol` is provided:
- MUST be a JSON object.
- Keys other than `level_1`, `level_2`, `level_3` MUST be rejected with 422.
- An empty object `{}` is valid (clears the protocol).

When `complaint_escalation_email` is provided:
- If non-empty, MUST pass basic email format validation (contains `@` and `.`).

When `expected_wait_time_minutes` is provided:
- If non-null, MUST be a positive integer. Zero or negative MUST return 422.

---

## REQ-3: PUT /admin/tenants/{id} — Accept New Fields

The `update_tenant` endpoint MUST accept the 7 new fields in the request body (alongside existing fields).

**Handling rules**:

| Field | Handling |
|-------|---------|
| `complaint_escalation_email` | Store as-is or NULL if empty string |
| `complaint_escalation_phone` | Store as-is or NULL if empty string |
| `expected_wait_time_minutes` | Cast to int; NULL if empty/null |
| `revision_policy` | Store as-is; NULL if empty string; max 2000 chars enforced |
| `review_platforms` | Serialize to JSON string via `json.dumps()` before storing as JSONB |
| `complaint_handling_protocol` | Serialize to JSON string via `json.dumps()` before storing as JSONB |
| `auto_send_review_link_after_followup` | Cast to bool; default `false` if absent |

The `GET /admin/tenants` endpoint response MUST include all 7 new fields. For JSONB fields, the response MUST apply `json.loads()` defensively (asyncpg may return them as strings).

**Tenant isolation**: The endpoint MUST verify `user_data.role == "ceo"` (existing check). The `tenant_id` comes from the URL path, not from request body.

---

## REQ-4: `_format_support_policy()` — Prompt Formatter

A new function `_format_support_policy(tenant_row: dict) -> str` MUST be added to `orchestrator_service/main.py`.

**REQ-4.1 — Empty result when unconfigured**

**Given** all 7 fields are NULL or absent from `tenant_row`,
**When** `_format_support_policy(tenant_row)` is called,
**Then** it MUST return an empty string `""`. No prompt block is injected.

**REQ-4.2 — Full block when configured**

**Given** at least one of the 7 fields is non-NULL,
**When** `_format_support_policy(tenant_row)` is called,
**Then** it MUST return a string that starts with `"## PROTOCOLO DE SOPORTE Y QUEJAS"`.

**REQ-4.3 — `expected_wait_time_minutes` in prompt**

**Given** `expected_wait_time_minutes = 20`,
**When** the formatter runs,
**Then** the output MUST contain a phrase referencing "20 minutos" as the standard wait time.

**REQ-4.4 — `revision_policy` in prompt**

**Given** `revision_policy = "ajustes gratuitos los primeros 30 días"`,
**When** the formatter runs,
**Then** the output MUST contain that policy text in the NIVEL 2 section.

**REQ-4.5 — `review_platforms` in prompt**

**Given** `review_platforms = [{"name": "Google Maps", "url": "https://g.co/r/xxx", "show_after_days": 1}]`,
**When** the formatter runs,
**Then** the output MUST include "Google Maps" and "https://g.co/r/xxx" in a reseñas block.

**REQ-4.6 — `complaint_handling_protocol` overrides defaults**

**Given** `complaint_handling_protocol = {"level_1": "Di: Escuché tu comentario."}`,
**When** the formatter runs,
**Then** the NIVEL 1 block MUST contain "Di: Escuché tu comentario." (tenant's custom instruction takes precedence over generic default).

**REQ-4.7 — `complaint_escalation_email` appears in NIVEL 3**

**Given** `complaint_escalation_email = "quejas@clinica.com"`,
**When** the formatter runs,
**Then** the NIVEL 3 block MUST reference that email address so the LLM knows the complaint was routed there.

---

## REQ-5: Agent MUST Follow Graduated Escalation

The agent MUST NOT skip levels. The system prompt block produced by `_format_support_policy()` MUST contain an explicit constraint:

```
REGLA: NUNCA pasar directamente a NIVEL 2 o NIVEL 3 sin haber aplicado el NIVEL anterior en esta conversación.
NIVEL 1 → NIVEL 2: solo si el paciente no se conforma o expresa mayor enojo tras la respuesta de NIVEL 1.
NIVEL 2 → NIVEL 3: solo si el paciente persiste después de la respuesta de NIVEL 2.
```

**Prohibition**: The agent MUST NOT call `derivhumano` for a first complaint message unless the complaint explicitly triggers NIVEL 3 criteria (physical harm, explicit legal threat, billing fraud claim).

---

## REQ-6: `derivhumano` Tool — Complaint Routing

**REQ-6.1 — Complaint detection**

The `derivhumano` function MUST inspect `reason` for complaint keywords (case-insensitive): `queja`, `molestia`, `insatisfecho`, `insatisfecha`, `cobrar`, `cobro`, `mal`, `error`, `revisión`, `revision`, `reclamo`, `experiencia`, `espera`, `trato`, `brusco`, `arruinaron`, `mal hecho`.

If any keyword matches AND `complaint_escalation_email` is set on the tenant, the notification email MUST be sent to `complaint_escalation_email` instead of — or in addition to — `derivation_email`.

**REQ-6.2 — Both emails when both are set**

**Given** `complaint_escalation_email = "quejas@c.com"` AND `derivation_email = "info@c.com"`,
**When** `derivhumano` is called with a complaint reason,
**Then** the email MUST be sent to BOTH addresses.

**REQ-6.3 — Fallback to `derivation_email`**

**Given** `complaint_escalation_email = NULL`,
**When** `derivhumano` is called with a complaint reason,
**Then** the email MUST be sent to `derivation_email` (existing behavior, no regression).

**REQ-6.4 — Non-complaint reasons unchanged**

**Given** `reason = "paciente solicitó hablar con un humano"` (no complaint keyword),
**When** `derivhumano` is called,
**Then** routing MUST follow the existing logic (to `derivation_email` + professional emails). Complaint routing MUST NOT be triggered.

**REQ-6.5 — SQL isolation**

The query to fetch `complaint_escalation_email` MUST include `WHERE id = $1` with the `current_tenant_id` context variable. MUST NOT join against other tenants' rows.

---

## REQ-7: Followup Job — Review Link

**REQ-7.1 — Flag guard**

**Given** `auto_send_review_link_after_followup = false` (or NULL / not set),
**When** the followup job runs,
**Then** the review link MUST NOT be appended to any message. Existing followup behavior is unchanged.

**REQ-7.2 — Platform eligibility**

**Given** `auto_send_review_link_after_followup = true` AND `review_platforms = [{"name": "Google Maps", "url": "https://...", "show_after_days": 1}]`,
**When** the appointment was completed exactly 1 day ago,
**Then** the followup message MUST include a review request for Google Maps with its URL.

**REQ-7.3 — `show_after_days` gate**

**Given** a platform has `show_after_days = 3` AND the appointment was completed 1 day ago,
**When** the followup job runs (D+1),
**Then** that platform MUST NOT be included in the review request (days since appointment < show_after_days).

**REQ-7.4 — Multiple platforms**

**Given** two platforms with `show_after_days = 1` and `show_after_days = 2` AND days_since = 2,
**When** the followup job runs,
**Then** BOTH platforms MUST be included (2 >= 1 and 2 >= 2).

**REQ-7.5 — Tenant isolation in followup job**

The query that fetches `review_platforms` and `auto_send_review_link_after_followup` MUST scope by `tenant_id`. Mixed tenant platform lists are not permitted.

---

## REQ-8: Acceptance Scenarios (Gherkin)

### SC-1 — Level-1 complaint: excessive wait time

```gherkin
Given a tenant with expected_wait_time_minutes = 15
  And complaint_handling_protocol.level_1 = "Empatizá. Reconocé la espera."
When a patient sends "estuve esperando 1 hora, es una falta de respeto"
Then the agent MUST respond with level-1 empathy
  And the agent MUST NOT call derivhumano
  And the response MUST reference "15 minutos" as the clinic standard
  And the response MUST NOT include pricing or appointment offers in the first message
```

### SC-2 — Level-3 complaint: billing dispute → complaint email routing

```gherkin
Given a tenant with complaint_escalation_email = "quejas@clinica.com"
  And derivation_email = "info@clinica.com"
  And complaint_handling_protocol.level_3 = "Derivar inmediatamente"
When the system prompt includes the PROTOCOLO DE SOPORTE Y QUEJAS block
  And derivhumano is called with reason = "queja de cobro incorrecto en turno anterior"
Then complaint keyword "queja" AND "cobro" are detected in reason
  And email MUST be sent to "quejas@clinica.com"
  And email MUST ALSO be sent to "info@clinica.com"
  And the agent response MUST use "entiendo tu preocupación" framing
  And the response MUST NOT say "hubo un error de cobro"
```

### SC-3 — Patient requests review link

```gherkin
Given a tenant with review_platforms = [{"name": "Google Maps", "url": "https://g.co/xxx", "show_after_days": 1}]
When a patient says "¿dónde puedo dejar una reseña?"
Then the system prompt MUST contain the review platforms section
  And the agent MUST provide the Google Maps URL directly in the response
  And the response MUST NOT require the patient to "ask the clinic"
```

### SC-4 — Followup job sends review link

```gherkin
Given a tenant with auto_send_review_link_after_followup = true
  And review_platforms = [{"name": "Instagram", "url": "https://ig.me/xxx", "show_after_days": 1}]
  And an appointment completed exactly 1 day ago
When send_post_treatment_followups() runs
Then the outgoing WhatsApp message MUST contain the Instagram review URL
  And the message MUST include standard followup content (not replace it)
  And the appointment's followup_sent field MUST be set to true after sending
```

---

## REQ-9: Internationalization (i18n)

The following keys MUST be added to all 3 locale files (`es.json`, `en.json`, `fr.json`):

| Key | Spanish value |
|-----|--------------|
| `clinics.support_section_title` | `"Soporte, Quejas y Reseñas"` |
| `clinics.support_section_help` | `"Configurá cómo el agente maneja quejas de pacientes y solicitudes de reseña."` |
| `clinics.complaint_escalation_email_label` | `"Email de quejas"` |
| `clinics.complaint_escalation_email_help` | `"Recibe notificaciones de quejas. Si no se configura, se usa el email de derivación general."` |
| `clinics.complaint_escalation_phone_label` | `"Teléfono directo para quejas graves"` |
| `clinics.complaint_escalation_phone_help` | `"El agente puede compartir este número en quejas de nivel 3."` |
| `clinics.expected_wait_time_label` | `"Tiempo de espera estándar (minutos)"` |
| `clinics.expected_wait_time_help` | `"El agente lo usa para validar quejas de espera."` |
| `clinics.revision_policy_label` | `"Política de revisión / retoques"` |
| `clinics.revision_policy_placeholder` | `"Ej: Ajustes gratuitos los primeros 30 días post-tratamiento"` |
| `clinics.revision_policy_help` | `"El agente cita esta política al manejar quejas estéticas o post-tratamiento."` |
| `clinics.review_platforms_label` | `"Plataformas de reseñas"` |
| `clinics.review_platforms_help` | `"El agente comparte estos links cuando el paciente pide dejar una reseña."` |
| `clinics.review_platform_name` | `"Nombre"` |
| `clinics.review_platform_url` | `"URL"` |
| `clinics.review_platform_days` | `"Días post-tratamiento"` |
| `clinics.review_platform_add` | `"Agregar plataforma"` |
| `clinics.review_platform_remove` | `"Eliminar"` |
| `clinics.complaint_protocol_label` | `"Protocolo de escalamiento"` |
| `clinics.complaint_protocol_help` | `"Instrucciones por nivel. Si no se completan, el agente usa el protocolo por defecto."` |
| `clinics.complaint_protocol_level1` | `"Nivel 1 — Queja leve"` |
| `clinics.complaint_protocol_level2` | `"Nivel 2 — Queja moderada"` |
| `clinics.complaint_protocol_level3` | `"Nivel 3 — Queja grave"` |
| `clinics.auto_review_label` | `"Enviar link de reseña automáticamente post-seguimiento"` |
| `clinics.auto_review_help` | `"Cuando está activo, el job de seguimiento adjunta el link de reseña al mensaje post-tratamiento."` |

---

## REQ-10: Tenant Isolation

Every SQL statement introduced by this change MUST satisfy:

1. `tenants` reads/writes use `WHERE id = $x` where `$x` is resolved from the authenticated user's JWT (via `current_tenant_id` context var or `get_resolved_tenant_id` dependency).
2. The `derivhumano` tool reads `complaint_escalation_email` via `SELECT complaint_escalation_email FROM tenants WHERE id = $1` with `current_tenant_id.get()`.
3. The followup job JOIN against tenants is on `a.tenant_id = t.id` — identical to the existing pattern in `followups.py`.
4. No cross-tenant reads are permitted at any layer.

---

## Dependencies

- REQ-1 (migration) MUST run before REQ-2/REQ-3 (endpoint validation) can be tested end-to-end.
- REQ-4 (`_format_support_policy`) depends on the new fields being readable from the tenant row passed into `build_system_prompt()`.
- REQ-6 (`derivhumano` routing) requires REQ-1 to add `complaint_escalation_email` to the `tenants` table.
- REQ-7 (followup job) requires REQ-1 to add `auto_send_review_link_after_followup` and `review_platforms`.
- REQ-9 (i18n) is independent but MUST be completed before REQ frontend work is merged.

---

## Out of Scope (explicit)

- Nova behavioral changes for complaint handling.
- A new `complaint_log` table (structured audit trail) — deferred to a future change.
- Sending emails directly from the frontend — all email routing is backend-only.
- Review platform OAuth / API submission (Google Business API, etc.).
- Automatic reply to the `complaint_escalation_email` inbox.
