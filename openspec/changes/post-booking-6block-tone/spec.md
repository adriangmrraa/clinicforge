# Spec — DLD-2: Fix agent tone and conversation flow (6-block model)

**Change:** `post-booking-6block-tone`
**Ticket:** DLD-2
**Approach:** Prompt-only — rewrite of `SECUENCIA POST-BOOKING` in `orchestrator_service/main.py`
**Status:** draft

---

## Context

### What exists today

The current post-booking response is defined in `main.py` (line ~9255) and `tests/fixtures/golden_prompt_whatsapp.txt` (line ~364) under the section `SECUENCIA POST-BOOKING (DOS MOMENTOS — ORDEN ESTRICTO)`.

Current structure (2 moments, ~4 blocks):
- Momento 1, Burbuja 1: appointment confirmation (raw data from `book_appointment`)
- Momento 1, Burbuja 2: seña data (if `bank_holder_name` configured)
- Momento 2, Burbuja 3: "cómo nos conociste?" — new patients only
- Momento 2, Burbuja 4: anamnesis link

### Problems identified

1. **Single LLM response split by `\n\n`**: all blocks are generated in one inference turn. The LLM can collapse or reorder them when uncertain which are conditional.
2. **No cross-turn enforcement**: after the booking response, there is no instruction preventing the LLM from generating a different structure in a follow-up turn that re-covers the same ground.
3. **Administrative tone**: "Confirmación del turno (datos de book_appointment tal cual)" is a data-dump, not a celebration moment. The patient receives a receipt, not a welcome.
4. **No email collection block**: email is only mentioned in `PASO 8b` as a reactive rule ("if they give an email"), not as a proactive, positioned ask with a reason.
5. **No OSDE/insurance confirmation block**: the existing rules are in the "OBRAS SOCIALES" section 80+ lines away from the booking sequence, so the LLM doesn't reliably connect them.
6. **Vocabulary mismatch**: the prompt uses "control" and "revisión" for first appointments — the doctor's commercial positioning uses "Evaluación/Diagnóstico".

### What `book_appointment` returns (internal tags available)
The tool return value contains:
- `[INTERNAL_SEÑA_DATA] ... [/INTERNAL_SEÑA_DATA]` — bank data block, present only when `bank_holder_name` is configured.
- `[INTERNAL_PATIENT_PHONE:{phone}]` — patient phone for third-party bookings.
- `[INTERNAL_ANAMNESIS_URL:{url}]` — unique anamnesis link for the patient.
- Appointment summary text (treatment, date, time, professional, sede, price).

Whether the patient is new is determined by the conversation context: "Nombre registrado" absent in the patient context section = new patient.

Insurance mention is determined by conversation history analysis (the LLM reads prior turns where the patient mentioned "OSDE", "obra social", "prepaga", "cobertura").

---

## Requirements

### R1 — 6-block structure
Post-booking response MUST follow this sequence of 6 blocks in strict order. Each block is separated by `\n\n` to generate distinct WhatsApp bubbles. Blocks are conditionally included based on the rules in R4–R8.

```
[Block 1] Confirmation     — ALWAYS
[Block 2] Data collection  — CONDITIONAL: only if email is missing
[Block 3] Seña             — CONDITIONAL: only if [INTERNAL_SEÑA_DATA] is present
[Block 4] Preparation      — CONDITIONAL: only if anamnesis is incomplete
[Block 5] Origin           — CONDITIONAL: only for new patients
[Block 6] OSDE             — CONDITIONAL: only if patient mentioned insurance in this conversation
```

### R2 — Bubble separation
Each block MUST be written as an independent paragraph separated by `\n\n`. No block may contain sub-blocks or merged objectives. One block = one objective = one WhatsApp bubble.

### R3 — Block 1: Confirmation
- Tone: celebratory, warm, personalized. NOT administrative.
- MUST include: patient name (first name), treatment name using R10 vocabulary, day + date + time, professional name, sede + address (from `book_appointment` response).
- MUST NOT include: raw internal tags, price (unless patient already asked), bank data.
- Opening MUST NOT be "Turno confirmado" or similar neutral/administrative phrasing.
- Example opening register: "¡Genial, [Nombre]! Ya te agendamos tu Evaluación con la Dra. [X]..."

### R4 — Block 2: Data collection
- Included ONLY when the patient has not yet provided an email in this conversation.
- If email was already collected earlier in the conversation → skip this block entirely.
- Ask for email only once per conversation. If the patient already responded with an email in a prior turn → skip.
- Positioning: the request must include a reason that benefits the patient (e.g., "para enviarte el resumen de tu visita").
- MUST NOT frame the email request as a mandatory form field.

### R5 — Block 3: Seña
- Included ONLY when `[INTERNAL_SEÑA_DATA]` is present in the `book_appointment` response.
- MUST open with a value-first positioning sentence that explains WHY the seña benefits the patient (it "reserves" the slot, avoids losing it, etc.).
- MUST include all three bank fields that appear in `[INTERNAL_SEÑA_DATA]`: Seña amount, Alias, CBU, Titular.
- MUST end with the phrase "no es obligatorio" (or equivalent natural rioplatense phrasing) to remove pressure.
- MUST NOT frame the seña as a requirement to keep the appointment.

### R6 — Block 4: Preparation / anamnesis
- Included ONLY when `[INTERNAL_ANAMNESIS_URL]` is present AND the patient has not yet completed the anamnesis (i.e., `anamnesis_completed_at` is null — this is already tracked; if the URL is in the tool response it means it should be sent).
- The anamnesis URL MUST be included as a clean URL (no markdown link format `[text](url)`).
- The block MUST include the phrase "para ahorrar tiempo en tu consulta" or equivalent.
- For bookings made for a minor: "para completar la ficha médica de [nombre del menor]".
- For bookings made for an adult third party: "para que se lo reenvíes a [nombre del tercero]".
- For new patients only: append "Recordá traer DNI y llegar 10 minutos antes." at the end of this block (not as a separate block).

### R7 — Block 5: Origin
- Included ONLY for new patients (patient context does NOT contain "Nombre registrado" before this booking).
- Phrasing: "Por cierto, ¿cómo nos conociste? Redes, recomendación, Google...?"
- If the patient responds → call `book_appointment`'s `acquisition_source` parameter OR update via the patient profile tool to record the source.
- If the patient does not respond → do NOT insist, do NOT repeat in subsequent turns.

### R8 — Block 6: OSDE / insurance confirmation
- Included ONLY when the patient mentioned an insurance provider (OSDE, Swiss Medical, OSECAC, Galeno, IOMA, "mi obra social", "prepaga", "cobertura", "convenio", etc.) in any earlier turn of the current conversation.
- Content: confirm coverage status using `check_insurance_coverage` if not already called, OR reference the result already obtained.
- Phrasing must be reassuring and action-oriented: frame it as "ya sabemos cómo manejarlo" rather than "todavía hay que verificar".
- If coverage was confirmed as accepted: "Como ya vimos, tu cobertura aplica para esta consulta 😊 Te esperamos el [fecha]."
- If coverage was NOT confirmed or is unknown: "Si llevás el carnet de tu obra social, en la consulta chequeamos la cobertura en el momento."
- MUST NOT give specific copay amounts (existing rule, maintained).

### R9 — Tone
Every block MUST be warm, professional, and conversion-oriented. The overall register is: a knowledgeable, caring human assistant who is excited the patient is coming in, not a booking system confirming a transaction.

Specific tone rules:
- Use patient's first name at least in Block 1.
- Use voseo throughout (rioplatense register).
- Emoji usage: 1-2 per block maximum, purposeful (not decorative).
- Avoid: "queda confirmado", "se procede a", "por favor tenga en cuenta", "a continuación", "como se indicó".
- Prefer: "¡Listo!", "¡Ya estás agendado/a!", "Te esperamos", "Cualquier cosa, acá estamos".

### R10 — Vocabulary for first appointments
When the treatment is a first appointment (consultation, evaluation, check-up, screening), use the following vocabulary:
- Use: "Evaluación", "Diagnóstico", "Consulta de Evaluación"
- Do NOT use: "Control", "Revisión", "Chequeo"

This rule applies to Block 1 (confirmation text) and any mention of the appointment type in subsequent blocks.

### R11 — One objective per block
Each block MUST contain exactly one objective. Mixing objectives within a single block is forbidden.

| Block | Objective |
|-------|-----------|
| 1 | Make the patient feel celebrated and clearly informed about their appointment |
| 2 | Collect email with a clear benefit reason |
| 3 | Present the seña as a friendly option, not a barrier |
| 4 | Reduce friction at the appointment via anamnesis preparation |
| 5 | Attribute the lead source without pressure |
| 6 | Reassure the patient about insurance coverage |

---

## Scenarios

### Scenario 1 — New patient, seña configured, anamnesis needed, no insurance mentioned

**Given** a new patient (no "Nombre registrado" in context) books an appointment for the first time,
**And** `[INTERNAL_SEÑA_DATA]` is present in the `book_appointment` response,
**And** `[INTERNAL_ANAMNESIS_URL]` is present,
**And** no insurance mention exists in the conversation history,
**When** the agent generates the post-booking response,
**Then** the response MUST contain exactly 5 blocks in order: Confirmation → Seña → Preparation → Origin.
**And** Block 2 (email) is NOT present because no email was explicitly requested in this scenario (email collection is opportunistic — see note below).
**And** each block is separated by `\n\n`.
**And** Block 1 uses the patient's first name and celebratory tone.
**And** Block 3 contains seña amount + bank data + "no es obligatorio".
**And** Block 4 contains the clean anamnesis URL + "para ahorrar tiempo" + "Recordá traer DNI y llegar 10 minutos antes."
**And** Block 5 contains "¿cómo nos conociste?".

> NOTE on Block 2 (email): Block 2 is included when the agent has not yet collected the email AND the treatment type typically benefits from it (any treatment). For the full happy path, Block 2 appears between Confirmation and Seña, making 5 blocks total (or 6 if insurance also applies).

### Scenario 2 — Existing patient, no seña, anamnesis already completed

**Given** an existing patient ("Nombre registrado" present in context) books an appointment,
**And** `[INTERNAL_SEÑA_DATA]` is NOT present,
**And** anamnesis was already completed (`anamnesis_completed_at` is not null — URL not present in response),
**When** the agent generates the post-booking response,
**Then** the response MUST contain exactly 1 block: Confirmation only.
**And** no seña block, no preparation block, no origin block, no OSDE block.

### Scenario 3 — Patient mentioned OSDE earlier in conversation

**Given** the patient said "¿aceptan OSDE?" at any earlier turn,
**And** `check_insurance_coverage` was called and returned a result,
**When** the agent generates the post-booking response,
**Then** Block 6 (OSDE confirmation) MUST appear as the last block.
**And** if coverage is accepted: tone is reassuring, references the prior confirmation.
**And** if coverage is unknown: instructs patient to bring insurance card.
**And** Block 6 MUST NOT quote a copay amount.

### Scenario 4 — Third-party booking (booking for another adult)

**Given** the interlocutor is booking for another adult (not a minor),
**And** `[INTERNAL_PATIENT_PHONE]` is present,
**And** `[INTERNAL_ANAMNESIS_URL]` is present,
**When** the agent generates the post-booking response,
**Then** Block 1 addresses the INTERLOCUTOR ("Ya le agendamos la Evaluación a [nombre del tercero]...").
**And** Block 4 instructs the interlocutor to forward the link: "para que se lo reenvíes a [nombre del tercero]".
**And** Block 5 (origin) is NOT included — origin attribution is only for the primary interlocutor's first booking.

### Scenario 5 — Minor booking

**Given** the interlocutor is booking for a minor,
**And** `[INTERNAL_PATIENT_PHONE]` contains the auto-generated minor phone,
**And** `[INTERNAL_ANAMNESIS_URL]` is present,
**When** the agent generates the post-booking response,
**Then** Block 1 names the minor: "Ya le agendamos la Evaluación a [nombre del menor]...".
**And** Block 4 says: "para completar la ficha médica de [nombre del menor]".
**And** Block 5 (origin) is NOT included — same rule as third-party.

### Scenario 6 — Email already collected earlier in the conversation

**Given** the patient already provided their email in a prior turn (before booking),
**And** `save_patient_email` was already called successfully,
**When** the agent generates the post-booking response,
**Then** Block 2 (email collection) MUST NOT appear.
**And** the remaining applicable blocks are included as per R1 conditions.

### Scenario 7 — Vocabulary enforcement for first appointment

**Given** the treatment being booked is a `CONSULTA` or first-visit type,
**When** the agent generates Block 1 of the post-booking response,
**Then** the word "Evaluación" or "Diagnóstico" MUST appear in the appointment description.
**And** the words "control", "revisión", or "chequeo" MUST NOT appear.

---

## Acceptance Criteria

| ID | Criterion | Verifiable by |
|----|-----------|---------------|
| AC-1 | Post-booking response always includes Block 1 (Confirmation) | Golden prompt test: any booking scenario |
| AC-2 | Blocks are separated by `\n\n` — no block content contains another block's objective | Golden prompt test: inspect whitespace structure |
| AC-3 | Block 1 contains patient first name and celebratory opener (not "queda confirmado" or equivalent) | Golden prompt test: string match |
| AC-4 | Block 3 (Seña) only appears when `[INTERNAL_SEÑA_DATA]` is present in the tool response | Golden prompt test: two scenarios with/without seña |
| AC-5 | Block 3, when present, contains seña amount + bank alias + CBU + holder + "no es obligatorio" | Golden prompt test: string inspection |
| AC-6 | Block 4 (Preparation) contains a clean URL (no markdown), "para ahorrar tiempo", and for new patients also the DNI reminder | Golden prompt test: regex URL check + string match |
| AC-7 | Block 5 (Origin) only appears for new patients (no "Nombre registrado") | Golden prompt test: two scenarios new vs. existing |
| AC-8 | Block 6 (OSDE) only appears when patient mentioned insurance in conversation | Golden prompt test: two scenarios with/without insurance mention |
| AC-9 | Block 6, when present, MUST NOT contain a specific copay amount in pesos/dollars | Golden prompt test: regex check |
| AC-10 | For first-visit treatments: "Evaluación" or "Diagnóstico" appears; "Control"/"Revisión"/"Chequeo" do NOT appear | Golden prompt test: string match |
| AC-11 | For minor/third-party bookings: Block 4 uses "forward" framing; Block 5 is absent | Golden prompt test |
| AC-12 | When email was already collected: Block 2 is absent from response | Golden prompt test: email pre-collected scenario |
| AC-13 | The golden prompt fixture at `tests/fixtures/golden_prompt_whatsapp.txt` is updated to match the new prompt text | File diff |
| AC-14 | Existing tests in `tests/` continue to pass (no regression in booking flow, state machine, date parsing) | `pytest` run |

---

## Approach Note

### Prompt-only implementation

This change is implemented exclusively as a rewrite of the `SECUENCIA POST-BOOKING` section in the system prompt. No Python code changes, no new tools, no migrations.

**Files to modify:**
1. `orchestrator_service/main.py` — lines ~9255–9289: replace the existing `SECUENCIA POST-BOOKING` block.
2. `tests/fixtures/golden_prompt_whatsapp.txt` — lines ~364–398: mirror the same replacement so the golden prompt test stays in sync.

**Why prompt-only is sufficient:**

All the data needed for the 6 blocks is already available to the LLM at the time it generates the post-booking response:
- Confirmation data: directly in the `book_appointment` tool return string.
- Seña data: `[INTERNAL_SEÑA_DATA]` block already in the tool return.
- Anamnesis URL: `[INTERNAL_ANAMNESIS_URL]` already in the tool return.
- New/existing patient: derivable from conversation context ("Nombre registrado" presence).
- Insurance mention: derivable from conversation history (earlier turns).
- Email collected: derivable from conversation history (whether `save_patient_email` was called).

**What the rewrite changes:**

| Before | After |
|--------|-------|
| 2 moments (MOMENTO 1 / MOMENTO 2) | 6 named blocks with explicit conditions |
| Tone: implicit ("datos de book_appointment tal cual") | Tone: explicit celebratory register, voseo, named opening pattern |
| Seña: presented after confirmation, no value positioning | Seña: value-first, explicit "no es obligatorio" |
| Anamnesis: separate PASO 8, no combined DNI reminder | Anamnesis: one block, conditional DNI reminder baked in |
| Origin: PASO 7c, before anamnesis | Origin: Block 5, after anamnesis (less disruptive ordering) |
| OSDE: only in separate "OBRAS SOCIALES" section | OSDE: explicit Block 6, connected to booking moment |
| Vocabulary: "control/revisión" allowed | Vocabulary: "Evaluación/Diagnóstico" mandated for first visits |

**Ordering rationale for the 6 blocks:**

1. Confirmation first: the patient needs to know their booking succeeded before anything else.
2. Email second: while the booking is fresh (peak engagement), one soft ask before any friction points.
3. Seña third: present the optional financial commitment before requesting effort (anamnesis).
4. Anamnesis fourth: effort ask — placed after the relationship is reinforced.
5. Origin fifth: light conversational question, low stakes, creates dialogue.
6. OSDE last: only for patients who already asked; it's a reassurance, not new information.

**Cross-turn enforcement:**

Add an explicit rule (already partially present) immediately before the 6-block section:
```
REGLA POST-BOOKING: Una vez ejecutado el flujo de 6 bloques, NO repetir ningún bloque en
turnos posteriores aunque el paciente no responda a todos. Cada bloque se envía UNA SOLA VEZ.
Si el paciente responde solo al bloque de seña, retomá desde ahí. No volver a enviar los
bloques ya completados.
```

---

## Out of Scope

- Changes to `book_appointment` tool logic or return value format.
- Changes to `save_patient_email` tool.
- Changes to `check_insurance_coverage` tool.
- New migrations.
- Frontend changes.
- Multi-agent (`MultiAgentEngine`) — the specialists.py prompt is separate and not covered here; it may need a follow-up change.
