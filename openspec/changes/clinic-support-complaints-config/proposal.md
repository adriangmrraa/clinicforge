# SDD Proposal: Clinic Support, Complaints & Review Config

**Change**: `clinic-support-complaints-config`
**Status**: PROPOSED
**Date**: 2026-04-07
**Author**: SDD Orchestrator

---

## 1. Intent

### Problem Statement

The patient-facing AI agent has no configurable policy for handling complaint scenarios. This is documented as **debilidad #4 — Quejas y Experiencias Negativas** in `docs/debilidades-system-prompt.md`.

**Current state**:
- The agent either calls `derivhumano` immediately for any negative comment (too eager — wastes human time, feels cold to the patient) or improvises an empathetic response with no policy guidance (inconsistent quality, legally risky).
- There is no graduated escalation protocol: level-1 complaints (waiting time, minor discomfort) receive the same response as level-3 complaints (billing dispute, professional conduct).
- The agent has no way to collect positive reviews: there is no mechanism to send a patient to a review platform (Google Maps, Instagram, Facebook) after treatment.
- The current `derivhumano` tool always routes to `derivation_email` — a single address shared with all escalations. Complaints are mixed with general handoffs, so the clinic has no differentiated inbox for complaint management.

### Why This Matters

- **Reputation risk**: A complaint handled without empathy and with immediate bot-deflection can turn into a negative public review.
- **Human time waste**: Level-1 complaints (a patient waited 15 minutes) should NOT activate `derivhumano`. This wastes staff attention and trains staff to ignore handoff notifications.
- **Missed review collection**: After a successful implant or cosmetic treatment, the agent never asks the patient to leave a review. Competitors do. This is a concrete revenue-affecting gap.
- **Non-configurable**: The policy is hardcoded. A clinic that wants to offer free revisions in the first 30 days post-treatment cannot express that policy through the current system. The agent either makes it up or says nothing.
- **No legal disclaimer audit trail**: When a patient files a billing complaint ("me cobraron de más"), the clinic needs a record. The current system has no structured complaint logging.

---

## 2. Scope

### In Scope

| Area | Files | What Changes |
|------|-------|-------------|
| DB schema | `orchestrator_service/models.py` + Alembic `039` | Add 7 new columns to `tenants` |
| Pydantic schemas | `orchestrator_service/admin_routes.py` | Validate and persist new fields |
| Endpoint | `orchestrator_service/admin_routes.py` — `PUT /admin/tenants/{id}` | Accept new fields |
| Prompt formatter | `orchestrator_service/main.py` — `_format_support_policy()` (new function) | Emit support/complaint block into system prompt |
| `build_system_prompt()` | `orchestrator_service/main.py` | Call `_format_support_policy()` and inject output |
| `derivhumano` tool | `orchestrator_service/main.py` | Route complaint escalations to `complaint_escalation_email` |
| Followup job | `orchestrator_service/jobs/followups.py` | Send review link N days after appointment if `auto_send_review_link_after_followup=True` |
| Frontend modal | `frontend_react/src/views/ClinicsView.tsx` | New collapsible section "Soporte y Quejas" in Tab 1 (Edit Clinic modal) |
| i18n | `frontend_react/src/locales/es.json`, `en.json`, `fr.json` | New translation keys |

### Out of Scope

- **Nova** (internal copilot) — separate system, separate prompt.
- **Complaint history dashboard** — no new admin reporting UI for complaints.
- **External review platform API integration** — review links are plain URLs, not API calls.
- **Automated response to reviews** — out of scope; the agent only sends a link.
- **SMS/email review requests** — only WhatsApp, via the existing followup job.

---

## 3. Approach

### Layer 1: New Tenant Configuration Fields

Add 7 new nullable columns to `tenants`:

| Column | Type | Purpose |
|--------|------|---------|
| `complaint_escalation_email` | TEXT | Separate inbox for complaint notifications; if NULL, `derivhumano` falls back to `derivation_email` |
| `complaint_escalation_phone` | TEXT | Direct WhatsApp/phone for serious complaints; agent can share this in level-3 scenarios |
| `expected_wait_time_minutes` | INTEGER | Used by the agent to answer "me hicieron esperar mucho" with clinic's own standard ("nuestro tiempo de espera estándar es X minutos") |
| `revision_policy` | TEXT | Clinic policy on rework/touch-ups, e.g., "ajustes gratuitos los primeros 30 días post-tratamiento" |
| `review_platforms` | JSONB | Array of `{name, url, show_after_days}` — platforms the agent can share after treatment |
| `complaint_handling_protocol` | JSONB | Graduated protocol: `{level_1: "empathize+log", level_2: "offer_revision", level_3: "escalate_to_human"}` |
| `auto_send_review_link_after_followup` | BOOLEAN | If TRUE, followup job also sends review platform links N days post-treatment |

### Layer 2: `_format_support_policy()` — New Prompt Formatter

A new function in `main.py` analogous to the existing `_format_insurance_providers()`. Takes the tenant row and emits a `## PROTOCOLO DE SOPORTE Y QUEJAS` section injected into the system prompt.

When the tenant has no configuration, the section is omitted (no behavior change for existing tenants).

Sample output when fully configured (Spanish):

```
## PROTOCOLO DE SOPORTE Y QUEJAS

ESCALAMIENTO GRADUADO:
NIVEL 1 — Queja leve (espera, incomodidad menor):
• Empatizá. Di: "Lamento mucho que hayas tenido esa experiencia. Tu comentario es muy valioso para nosotros."
• Si el paciente se calma → preguntá si podés ayudar en algo más.
• Si el paciente insiste → NIVEL 2.
[TIEMPO DE ESPERA ESTÁNDAR: 15 minutos. Si superó ese tiempo, reconocelo.]

NIVEL 2 — Queja moderada (tratamiento, cobro, atención):
• Empatizá + ofrecé revisión si aplica.
[POLÍTICA DE REVISIÓN: Ajustes gratuitos los primeros 30 días post-tratamiento.]
• Di: "Quiero que quedes satisfecho/a. Vamos a coordinar para que el profesional revise tu caso."
• Ejecutar SOLO si el paciente persiste: derivhumano("Queja: {resumen}")

NIVEL 3 — Queja grave (mala práctica, dolor post-tratamiento severo, cobro incorrecto):
• Ejecutar derivhumano INMEDIATAMENTE con detalle completo.
• Si hay síntomas físicos: ejecutar TAMBIÉN triage_urgency.
[EMAIL DE QUEJAS: quejas@clinica.com — este email recibe la notificación automática]

REGLAS:
• SIEMPRE empatizar ANTES de escalar. NUNCA decir "no puedo ayudarte".
• NUNCA pedir disculpas por el profesional — decí "entiendo tu preocupación" en vez de "perdón por el error".
• NUNCA escalar a NIVEL 2 sin pasar por NIVEL 1 en la misma conversación.

RESEÑAS:
Cuando un paciente feliz menciona que está contento con el resultado:
[PLATAFORMAS: Google Maps (https://...), Instagram (https://...)]
• Ofrecé el link directamente: "Si querés dejarnos una reseña, te ayudaría muchísimo: [link]"
```

### Layer 3: `derivhumano` Tool Modification

When `derivhumano` is called with a complaint-classified reason (detected by keyword matching), it routes to `complaint_escalation_email` instead of (or in addition to) `derivation_email`. If `complaint_escalation_email` is NULL, it falls back to the existing behavior.

Complaint detection: keyword presence in `reason` (case-insensitive): `queja`, `molestia`, `insatisfecho`, `cobrar`, `cobro`, `mal`, `error`, `revisión`, `reclamo`, `experiencia`, `espera`, `trato`.

### Layer 4: Followup Job Modification

When `auto_send_review_link_after_followup = TRUE` and `review_platforms` has at least one entry, the followup job appends a review request to the post-treatment message, selecting the platform with the smallest `show_after_days` that is <= days since appointment.

---

## 4. Success Criteria

Four acceptance scenarios:

| # | Scenario | Expected Agent Behavior |
|---|----------|------------------------|
| SC-1 | Patient says "me hicieron esperar 1 hora" | Agent empathizes (level 1), does NOT call `derivhumano`, acknowledges wait time policy if configured |
| SC-2 | Patient says "me cobraron de más, estoy muy enojado" | Agent empathizes, references revision policy if set, then escalates to `derivhumano` routing to `complaint_escalation_email`; NOT to `derivation_email` |
| SC-3 | Patient asks "dónde puedo dejar una reseña?" | Agent shares configured review_platforms URLs directly in chat |
| SC-4 | Followup job runs 2 days after completed appointment when `auto_send_review_link_after_followup=TRUE` | Review link is appended to the followup message for platforms with `show_after_days <= 2` |

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Legal: clinic acknowledging "cobro incorrecto" implicates clinic in liability | HIGH | Prompt rules MUST forbid the agent from confirming billing errors; agent MUST use "entiendo tu preocupación" framing, never "sí, hubo un error". Documented in spec prohibitions. |
| Review request timing: sending too soon (same day) feels pushy | MEDIUM | `show_after_days` guard in `review_platforms` schema. Default enforced in followup job: minimum 1 day. |
| Complaint email routing split: staff may miss complaints if they only watch `derivation_email` | LOW | Backend sends to BOTH `complaint_escalation_email` AND `derivation_email` when both are set. No notifications are silently dropped. |
| JSONB shape drift for `complaint_handling_protocol` | LOW | Pydantic validation with strict schema. Unknown keys rejected. |
| Followup job referencing `review_platforms` — SQL join required | LOW | The followup job is refactored to JOIN tenants on `auto_send_review_link_after_followup` and `review_platforms`. |
| `revision_policy` used to make agent promise results | MEDIUM | Prompt injection guard: revision policy text is displayed verbatim but the prompt explicitly prohibits the agent from promising outcomes. |

---

## 6. Alternatives

### Alt A: Use FAQs for complaint policy (current approach)
Clinics can already put complaint-handling text in FAQs. This requires per-FAQ setup for every scenario, doesn't route to a separate email, and doesn't integrate with `derivhumano`.

**Rejected**: FAQs are not structured, not queryable from tool code, and don't differentiate complaint emails from handoff emails.

### Alt B: New `complaint_policies` table (normalized)
A separate table with one row per level, FK to tenant. More normalized, supports N levels.

**Rejected**: The graduated levels (1-2-3) are fixed by the spec and by the debilidades document. A JSONB column provides flexibility without a separate table. Can be normalized in a future change if levels become dynamic.

### Alt C: Dedicated `derivhumano_complaint` tool
A separate tool for complaint escalation with its own routing logic.

**Rejected**: The spec explicitly uses a flag on the existing `derivhumano` tool (`complaint=True` or keyword detection). Creating a second tool inflates the LangChain tool list and requires the LLM to choose between two similar tools — a known source of routing errors.

---

## 7. Implementation Order

1. Alembic migration `039` (7 new columns on `tenants`)
2. SQLAlchemy model update
3. Backend — Pydantic schemas + PUT endpoint
4. `_format_support_policy()` formatter
5. `build_system_prompt()` injection call
6. `derivhumano` complaint routing
7. Followup job review link
8. Frontend modal section
9. i18n keys
10. Tests (each phase TDD-first)
