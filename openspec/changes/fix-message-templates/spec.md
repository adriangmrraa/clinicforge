# Spec — DLD-1: Fix Message Templates
**Change:** fix-message-templates
**Status:** draft
**Date:** 2026-04-17

---

## Context

Templates sent to patients via WhatsApp render markdown literally — `**bold**` appears as `**bold**`, not bold text. Additionally several templates use opening punctuation (¡, ¿) which is considered informal and inconsistent with the brand voice. The "Segundo Aviso de Turno" automation playbook uses a coercive, threatening tone ("lamentablemente deberemos liberar el espacio") that damages patient trust. All four issues must be fixed together because they share the same root cause: templates were written for a UI context, not for plain-text messaging channels.

---

## Requirements

### R1 — No markdown bold in patient-facing templates

No template, tool response, or system-generated message delivered to a patient MUST contain `**...**` markdown syntax. Emphasis MUST be expressed using:
- CAPS for critical keywords (e.g., `URGENCIA`, `ACCIONES INMEDIATAS`)
- Plain prose restructuring (line breaks, numbered lists already available in the channel)
- Emoji as a visual separator if already present in the block (do not add new ones)

**Scope:** All four triage responses in `triage_urgency` (`emergency`, `high`, `normal`, `low`), plus any other patient-facing string found to contain `**...**` during implementation.

### R2 — No opening ¡ or ¿ punctuation marks

No patient-facing template MUST use `¡` or `¿` as an opening character. Closing `!` and `?` are allowed. This applies to:
- Hardcoded strings in tool return values
- Automation step `message_text` seeds in migration files
- Agent prompt examples that the LLM will reproduce verbatim

**Boundary:** Internal admin UI strings, Nova internal Telegram messages, and HTML email templates (which render in a browser and support all punctuation) are OUT OF SCOPE. The ¡/¿ ban applies only to strings sent to patients via WhatsApp, Instagram DM, or Facebook Messenger.

### R3 — "Segundo Aviso de Turno" must use a warm, non-threatening tone

The automation step seeded in migration `048_seed_default_playbooks.py` currently reads:

> "de no recibir respuesta en la próxima hora, lamentablemente deberemos liberar el espacio para otro paciente."

This MUST be rewritten to:
- NOT mention releasing or losing the slot as a punishment
- NOT use a deadline as pressure
- Invite the patient to confirm in a warm, caring way
- Be brief (one message, two sentences maximum)
- Use voseo consistently (rioplatense)

### R4 — All hardcoded templates must follow the brand voice

Brand voice is: **cercano, seguro, profesional**. Characteristics:
- Voseo (Argentina/Rioplatense): "agendás", "te escribimos", "contanos"
- No corporate stiffness, no aggression, no alarm beyond what the clinical situation warrants
- Honest urgency for clinical emergencies (`emergency`), calm confidence for everything else
- First person plural for the clinic ("te escribimos", "estamos para ayudarte"), first person singular for the bot when appropriate

This applies to the triage response dictionary as a whole: the `emergency` level may use strong language (it IS an emergency), but the framing must remain supportive, not robotic.

---

## Scenarios

### Scenario 1 — Triage LOW does not render markdown

**Given** a patient sends a message describing a routine checkup need
**When** the agent calls `triage_urgency` and the result is `"low"`
**Then** the returned string MUST NOT contain `**` or `__`
**And** the key terms (e.g., "REVISION DE RUTINA") MUST be readable as plain text in a WhatsApp chat bubble

### Scenario 2 — Triage EMERGENCY does not render markdown

**Given** a patient describes severe dental pain, bleeding, or inability to breathe
**When** the agent calls `triage_urgency` and the result is `"emergency"`
**Then** the returned string MUST NOT contain `**` or `__`
**And** critical actions MUST still be clearly distinguished using CAPS and numbered list formatting
**And** the clinical urgency MUST be communicated with the same severity as before

### Scenario 3 — Triage HIGH and NORMAL do not render markdown

**Given** any patient message that resolves to `"high"` or `"normal"` triage level
**When** `triage_urgency` returns its response
**Then** the returned string MUST NOT contain `**` or `__`

### Scenario 4 — Segundo Aviso tone is warm

**Given** the `Segundo Aviso de Turno` automation playbook is triggered for a patient who has not confirmed
**When** the message is delivered via WhatsApp
**Then** the message MUST NOT contain the word "liberar", "lamentablemente", or any equivalent threat of losing the slot
**And** the message MUST invite the patient to confirm in a friendly, calm tone
**And** the message MUST be grammatically correct in voseo

### Scenario 5 — Segundo Aviso does not use opening ¡

**Given** the `Segundo Aviso de Turno` automation step message text
**When** inspected as plain text
**Then** the string MUST NOT start with or contain `¡`

### Scenario 6 — Specialists agent greeting does not use opening ¡

**Given** the ReceptionAgent prompt in `specialists.py` that defines greeting templates
**When** the agent generates a greeting for a new lead or existing patient
**Then** the example strings in the prompt MUST NOT use `¡` as an opening character
**And** the agent MUST still be warm and inviting using plain `Hola` openings

### Scenario 7 — Social prompt does not use markdown bold in patient-facing copy

**Given** the social channel prompt in `social_prompt.py`
**When** the agent uses it to reply to a patient on Instagram or Facebook
**Then** the response strings the agent is instructed to produce (CTA lines, booking confirmations) MUST NOT instruct the LLM to emit `**...**` markdown
**Note:** Internal structural headers in the prompt itself (used for LLM orientation, not reproduced to the patient) are acceptable

### Scenario 8 — Followup job template does not use opening ¿ at start of sentence

**Given** the post-appointment followup message built in `jobs/followups.py`
**When** the message is sent to a patient on WhatsApp
**Then** the question "Tuviste alguna molestia o va todo bien?" MUST be preceded by a sentence connector, not standalone `¿`
**And** the full message MUST NOT start a new sentence with `¿` as a first character

---

## Acceptance Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| AC-1 | `triage_urgency` responses dict contains zero occurrences of `**` or `__` | `rg '\*\*' orchestrator_service/main.py` returns no match in the `responses` dict block |
| AC-2 | `Segundo Aviso de Turno` message text in migration 048 does not contain "liberar", "lamentablemente", or "liberar el espacio" | `rg 'liberar\|lamentablemente' orchestrator_service/alembic/versions/048_seed_default_playbooks.py` returns no match |
| AC-3 | `Segundo Aviso de Turno` message text does not contain `¡` | `rg '¡' orchestrator_service/alembic/versions/048_seed_default_playbooks.py` returns no match in that playbook's step |
| AC-4 | ReceptionAgent greeting examples in `specialists.py` do not contain opening `¡` | `rg '¡' orchestrator_service/agents/specialists.py` returns no match in the greeting template strings |
| AC-5 | `social_prompt.py` CTA and instruction strings do not instruct the LLM to emit `**...**` to the patient | Code review of the revised file |
| AC-6 | `followups.py` does not start a sentence with `¿` as the first character of a message segment | `rg '^¿' orchestrator_service/jobs/followups.py` returns no match |
| AC-7 | All four triage levels use CAPS for section headers instead of markdown bold | Read the `responses` dict and verify no `**` present |
| AC-8 | Brand voice check: no triage or automation template uses "estimado/a", "lamentablemente", "le informamos", or other formal/legalistic register | `rg 'estimado|lamentablemente|le informamos' orchestrator_service/` returns no match in patient-facing strings |

---

## Files to Modify

| File | Location of Issue | Rule Violated |
|------|-------------------|---------------|
| `orchestrator_service/main.py` | `triage_urgency` tool, `responses` dict (~line 4321–4345): all four levels use `**...**` for section headers and inline emphasis | R1, R4 |
| `orchestrator_service/main.py` | `reschedule_appointment` return string (~line 4774): `¡Listo!` opener | R2 |
| `orchestrator_service/main.py` | `verify_payment_receipt` return string (~line 6437): `¡El plan está completamente saldado!` and `¡Gracias!` | R2 |
| `orchestrator_service/main.py` | `list_services` inline injection (~line 5065): `¡IMPORTANTE PARA LA IA!` — internal LLM instruction, keep but verify it is never surfaced to the patient | R2 (low priority — internal directive) |
| `orchestrator_service/alembic/versions/048_seed_default_playbooks.py` | `Segundo Aviso de Turno` step message (~line 364): threatening tone + `¡Gracias!` opener-exclamation | R2, R3, R4 |
| `orchestrator_service/agents/specialists.py` | ReceptionAgent greeting examples (~line 188–192): `¡Hola!` and `¡Bien!` openers | R2 |
| `orchestrator_service/services/social_prompt.py` | CTA section header `**Disparadores (palabras clave):**` and structural bold headers (~line 67, 84–92): instruct LLM with markdown that may bleed into patient output | R1 (review — structural headers may be acceptable if clearly separated from patient-facing copy) |
| `orchestrator_service/jobs/followups.py` | Post-appointment message (~line 103): `¿Tuviste alguna molestia...` starts a new segment with `¿` | R2 |
| `orchestrator_service/services/buffer_task.py` | Payment receipt injection prompt (~line 2027, 2043): `¡Recibí tu comprobante!` inside an agent instruction string reproduced to the patient | R2 |

### Out of Scope (do NOT modify)

| File | Reason |
|------|--------|
| `orchestrator_service/services/email_templates.py` | HTML email, renders in browser — `¡Hola!` is correct HTML Spanish punctuation |
| `orchestrator_service/jobs/smart_alerts.py` | Nova internal Telegram messages to clinic staff — not patient-facing |
| `orchestrator_service/jobs/nova_morning.py` | Nova daily briefing to clinic staff — not patient-facing |
| `orchestrator_service/main.py` FastAPI description block | Swagger UI / internal docs — not patient-facing |
| `orchestrator_service/services/social_prompt.py` structural prompt headers | LLM orientation markers, never reproduced verbatim to the patient |

---

## Notes for Implementation

1. The `048_seed_default_playbooks.py` migration is an Alembic seed. Fixing the text there does NOT retroactively update existing tenants — a companion data migration must UPDATE the `message_text` column in `automation_steps` for all rows where `step_label = 'Segundo aviso'`. This may be a new migration (e.g., `050_fix_segundo_aviso_tone.py`) or an inline UPDATE in `049` if it has not yet been applied to production. Check with the team before deciding.

2. The triage `responses` dict change is purely cosmetic (CAPS vs `**`) and carries zero functional risk. It is safe to ship independently.

3. When rewriting "Segundo Aviso", a candidate replacement is:
   `"Hola {{nombre_paciente}}, te recordamos que tu turno de mañana a las {{hora_turno}} todavia no fue confirmado. Cuando puedas, avisanos un Si para tenerlo listo. Gracias!"`
   The exact copy is the implementer's call — this is illustrative only. The spec constraint is: warm, no threat, two sentences max, voseo.

4. Do NOT rewrite the `¿...?` pattern across the entire codebase. The closing `?` is correct Spanish. Only the OPENING `¡` and `¿` are banned per R2.
