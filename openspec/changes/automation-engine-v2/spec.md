# Spec: Automation Engine V2 — Playbooks Clínicos

## S1: Database Schema

### S1.1: `automation_playbooks` table

```sql
CREATE TABLE automation_playbooks (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Identity
    name            TEXT NOT NULL,                          -- "Escudo Anti-Ausencias"
    description     TEXT,                                   -- Shown on card: "Le recuerda al paciente..."
    icon            TEXT DEFAULT '📋',                      -- Emoji for card
    category        TEXT NOT NULL DEFAULT 'custom',         -- retention, revenue, reputation, clinical, recovery, custom

    -- Trigger
    trigger_type    TEXT NOT NULL,                          -- appointment_reminder, appointment_completed, no_show, lead_no_booking, patient_inactive, payment_pending, appointment_created
    trigger_config  JSONB NOT NULL DEFAULT '{}'::jsonb,     -- { "hours_before": 24 } or { "days_after": 7 } or { "inactive_days": 90 }

    -- Conditions (filters)
    conditions      JSONB NOT NULL DEFAULT '{}'::jsonb,     -- { "treatments": ["implante_*", "cirugia_*"], "professionals": [2], "patient_type": "all", "channels": ["whatsapp"] }

    -- Execution control
    is_active       BOOLEAN NOT NULL DEFAULT false,
    is_system       BOOLEAN NOT NULL DEFAULT false,         -- Pre-built playbooks
    max_messages_per_day INTEGER NOT NULL DEFAULT 2,        -- Hard cap per patient per day
    frequency_cap_hours INTEGER DEFAULT 24,                 -- Min hours between playbook runs for same patient
    schedule_hour_min INTEGER NOT NULL DEFAULT 9,           -- Don't send before this hour
    schedule_hour_max INTEGER NOT NULL DEFAULT 20,          -- Don't send after this hour

    -- Abort conditions
    abort_on_booking    BOOLEAN NOT NULL DEFAULT true,      -- Stop if patient books appointment
    abort_on_human      BOOLEAN NOT NULL DEFAULT true,      -- Stop if human takes over chat
    abort_on_optout     BOOLEAN NOT NULL DEFAULT true,      -- Stop if patient says "no me escriban"

    -- Stats (cached, updated by executor)
    stats_cache     JSONB DEFAULT '{}'::jsonb,              -- { "sent": 145, "confirmed": 112, "confirm_rate": 0.77, "last_sent_at": "..." }

    -- Meta
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_playbooks_tenant_active ON automation_playbooks(tenant_id, is_active);
CREATE INDEX idx_playbooks_trigger ON automation_playbooks(trigger_type);
```

### S1.2: `automation_steps` table

```sql
CREATE TABLE automation_steps (
    id              SERIAL PRIMARY KEY,
    playbook_id     INTEGER NOT NULL REFERENCES automation_playbooks(id) ON DELETE CASCADE,

    -- Ordering
    step_order      INTEGER NOT NULL DEFAULT 0,             -- 0, 1, 2, 3...
    step_label      TEXT,                                   -- Optional label: "Recordatorio inicial"

    -- Action
    action_type     TEXT NOT NULL,                          -- send_template, send_text, send_instructions, wait, wait_response, notify_team, update_status

    -- Timing
    delay_minutes   INTEGER NOT NULL DEFAULT 0,             -- 0=immediate, 60=1h, 1440=24h
    schedule_hour_min INTEGER,                              -- Override playbook default (NULL = use playbook)
    schedule_hour_max INTEGER,                              -- Override playbook default (NULL = use playbook)

    -- Content: send_template
    template_name   TEXT,                                   -- YCloud template name
    template_lang   TEXT DEFAULT 'es',
    template_vars   JSONB DEFAULT '{}'::jsonb,              -- { "1": "nombre_paciente", "2": "dia_semana", ... }

    -- Content: send_text
    message_text    TEXT,                                   -- "Hola {{nombre_paciente}}, ¿cómo te sentís?"

    -- Content: send_instructions
    instruction_source TEXT DEFAULT 'from_treatment',       -- "from_treatment" (auto from treatment_types) or "custom"
    custom_instructions TEXT,                               -- Custom text if source=custom

    -- Content: notify_team
    notify_channel  TEXT DEFAULT 'telegram',                -- telegram, dashboard, both
    notify_message  TEXT,                                   -- "⚠️ {{nombre_paciente}} reporta dolor post-cirugía"

    -- Content: update_status
    update_field    TEXT,                                   -- "appointment_status", "patient_tag"
    update_value    TEXT,                                   -- "confirmed", "post_op_ok"

    -- Response handling (for wait_response action)
    wait_timeout_minutes INTEGER DEFAULT 120,               -- 2h default

    -- Branching: keyword classification
    -- Each key is a keyword group name, value is { "keywords": [...], "next_step_order": N, "action": "continue|notify|pause" }
    response_rules  JSONB DEFAULT '[]'::jsonb,
    -- Example:
    -- [
    --   { "name": "urgencia", "keywords": ["dolor","sangra","fiebre","hinchado"], "action": "notify_and_pause", "notify_msg": "⚠️ Paciente reporta dolor" },
    --   { "name": "positivo", "keywords": ["bien","perfecto","genial","todo ok"], "action": "continue" },
    --   { "name": "negativo", "keywords": ["no puedo","cancelar","no voy"], "action": "abort" }
    -- ]

    on_no_response  TEXT DEFAULT 'continue',                -- continue (next step), abort, retry, notify_team
    on_unclassified TEXT DEFAULT 'pass_to_ai',              -- pass_to_ai, continue, pause

    -- Branching: next step overrides
    on_response_next_step INTEGER,                          -- Go to this step_order on positive response (NULL = next in sequence)
    on_no_response_next_step INTEGER,                       -- Go to this step_order on timeout (NULL = next in sequence)

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_steps_playbook ON automation_steps(playbook_id, step_order);
```

### S1.3: `automation_executions` table

```sql
CREATE TABLE automation_executions (
    id              SERIAL PRIMARY KEY,
    playbook_id     INTEGER NOT NULL REFERENCES automation_playbooks(id) ON DELETE CASCADE,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Target
    patient_id      INTEGER REFERENCES patients(id) ON DELETE SET NULL,
    phone_number    TEXT NOT NULL,
    appointment_id  UUID,                                   -- If triggered by appointment event

    -- State
    current_step_order INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'running',         -- running, waiting_response, paused, completed, aborted, human_takeover
    pause_reason    TEXT,                                    -- "negative_sentiment", "human_override", "opt_out", "keyword:dolor"

    -- Timing
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    next_step_at    TIMESTAMPTZ,                            -- When to execute next step (executor polls this)
    completed_at    TIMESTAMPTZ,

    -- Tracking
    messages_sent   INTEGER NOT NULL DEFAULT 0,             -- Counter for daily cap
    messages_sent_today INTEGER NOT NULL DEFAULT 0,         -- Reset daily
    last_message_at TIMESTAMPTZ,
    last_response_at TIMESTAMPTZ,                           -- When patient last responded within this execution

    -- Context (accumulated data during execution)
    context         JSONB DEFAULT '{}'::jsonb,              -- { "patient_name": "María", "treatment": "implante_simple", ... }

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_executions_pending ON automation_executions(next_step_at) WHERE status IN ('running', 'waiting_response');
CREATE INDEX idx_executions_patient ON automation_executions(tenant_id, phone_number, status);
CREATE INDEX idx_executions_playbook ON automation_executions(playbook_id, status);
```

### S1.4: `automation_events` table

```sql
CREATE TABLE automation_events (
    id              SERIAL PRIMARY KEY,
    execution_id    INTEGER NOT NULL REFERENCES automation_executions(id) ON DELETE CASCADE,
    step_id         INTEGER REFERENCES automation_steps(id) ON DELETE SET NULL,

    event_type      TEXT NOT NULL,                          -- step_executed, message_sent, message_delivered, message_read, button_clicked, response_received, response_classified, timeout, aborted, paused, resumed, completed
    event_data      JSONB DEFAULT '{}'::jsonb,              -- { "classification": "positive", "response_text": "todo bien", "template_name": "..." }

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_execution ON automation_events(execution_id, created_at);
CREATE INDEX idx_events_type ON automation_events(event_type);
```

### S1.5: `patients` table addition

```sql
ALTER TABLE patients ADD COLUMN last_automation_message_at TIMESTAMPTZ;
```

---

## S2: Backend API Endpoints

### S2.1: Playbook CRUD

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/playbooks` | List all playbooks for tenant (with stats_cache) |
| `POST` | `/admin/playbooks` | Create playbook (with steps in body) |
| `GET` | `/admin/playbooks/{id}` | Get playbook with all steps |
| `PATCH` | `/admin/playbooks/{id}` | Update playbook config |
| `DELETE` | `/admin/playbooks/{id}` | Delete playbook (cascades steps + executions) |
| `PATCH` | `/admin/playbooks/{id}/toggle` | Activate/deactivate |
| `POST` | `/admin/playbooks/{id}/duplicate` | Clone playbook with all steps |

### S2.2: Step CRUD

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/playbooks/{id}/steps` | List steps ordered by step_order |
| `POST` | `/admin/playbooks/{id}/steps` | Add step (auto-assigns next step_order) |
| `PATCH` | `/admin/playbooks/{id}/steps/{step_id}` | Update step config |
| `DELETE` | `/admin/playbooks/{id}/steps/{step_id}` | Delete step (reorders remaining) |
| `POST` | `/admin/playbooks/{id}/steps/reorder` | Reorder steps: `{ "order": [3, 1, 2] }` |

### S2.3: Execution & Analytics

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/playbooks/{id}/executions` | Active executions (with pagination) |
| `GET` | `/admin/playbooks/{id}/stats` | Aggregated KPIs: sent, confirmed, aborted, avg_completion_time |
| `POST` | `/admin/playbooks/{id}/executions/{exec_id}/abort` | Manually abort an execution |
| `POST` | `/admin/playbooks/{id}/executions/{exec_id}/resume` | Resume a paused execution |

### S2.4: Templates (existing, unchanged)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/automations/ycloud-templates` | List approved YCloud templates (already exists) |

---

## S3: Executor Job (`playbook_executor.py`)

Runs every **5 minutes** via JobScheduler.

### Algorithm

```
1. SELECT * FROM automation_executions
   WHERE status IN ('running')
   AND next_step_at <= NOW()
   ORDER BY next_step_at ASC
   LIMIT 100

2. For each execution:
   a. Load playbook + current step
   b. Pre-flight check:
      - Patient already received max_messages_per_day today? → skip, retry tomorrow
      - Patient has last_automation_message_at < frequency_cap? → skip
      - Human override active? → abort execution
      - Patient booked appointment? (if abort_on_booking) → complete execution
      - Current time within schedule_hour_min/max? → defer to next valid window
   c. Execute step action:
      - send_template → YCloudClient.send_template()
      - send_text → ResponseSender.send_sequence()
      - send_instructions → load from treatment_types.post_instructions → send
      - notify_team → send to Telegram / emit socket event
      - update_status → UPDATE appointment/patient record
      - wait_response → set status='waiting_response', set next_step_at=NOW()+timeout
   d. Log automation_event
   e. Update patients.last_automation_message_at (if message was sent)
   f. Advance: set current_step_order++, calculate next_step_at
   g. If last step → set status='completed'

3. Process waiting_response executions:
   - SELECT WHERE status='waiting_response' AND next_step_at <= NOW()
   - Timeout reached → apply on_no_response rule (continue/abort/retry/notify)
```

### Response Classification (triggered from chat_webhooks.py)

When a patient message arrives and there's an active execution in `waiting_response`:

```
Layer 1: Button text match (instant, free)
  → Exact match against template button texts
  → Already implemented in chat_webhooks.py

Layer 2: Keyword match (instant, free)
  → Check response_rules[].keywords from the current step
  → Match → apply the rule's action (continue/notify/pause/abort)

Layer 3: LLM classification (1-3s, ~$0.001)
  → ONLY if layers 1-2 didn't match AND on_unclassified='classify_with_ai'
  → Prompt: "Classify this patient response: {text}. Options: positive, negative, urgent, question, scheduling"
  → Apply mapped action
```

---

## S4: Frontend Components

### S4.1: PlaybooksView.tsx (main page)

- **Header**: "Estrategias de Automatización" + subtitle "Activá protocolos clínicos automatizados"
- **Gallery**: Grid of PlaybookCard components (2 cols desktop, 1 col mobile)
- **Categories**: Horizontal filter tabs: Todos, Retención, Ingresos, Reputación, Clínico, Recuperación
- **"+ Crear estrategia"** button opens empty config modal

### S4.2: PlaybookCard.tsx

Displays per playbook:
- Icon + name + description (human-readable, one sentence)
- Status toggle (on/off)
- KPI badges: "78% confirman" / "14 enviados hoy" / "3.2h ahorradas"
- Category badge color-coded
- [⚙️ Configurar] [📊 Historial] buttons
- If inactive: shows "💡 Activalo para..." hint

### S4.3: PlaybookConfigModal.tsx (conversational config)

Sections (not tabs — vertical scroll):

**1. ¿Cuándo se activa?**
- Trigger type selector (dropdown with human labels)
- Trigger timing: "24 horas antes del turno" / "3 días después" / "90 días sin turno"

**2. ¿Para quién?**
- Treatment filter: chips multi-select from treatment_types
- Professional filter: chips multi-select from professionals
- Patient type: all / new_only / existing_only

**3. Secuencia de pasos**
- Ordered list of StepEditor components
- [+ Agregar paso] button at bottom
- Each step has ⬆️⬇️ reorder buttons and 🗑️ delete

**4. Controles de seguridad**
- Max messages per day (number input, default 2)
- Schedule window (hour range picker)
- Abort conditions (checkboxes: on booking, on human override, on opt-out)

**5. Vista previa**
- MessagePreview component showing WhatsApp bubble mock
- Updates in real-time as message text changes

### S4.4: StepEditor.tsx (per-step config)

Collapsible card for each step. Shows:

- **Step number** + optional label
- **Type selector**: dropdown with icons per action type
- **Timing**: "Ejecutar [inmediatamente / después de X horas/días]"
- **Content** (dynamic based on type):
  - send_template → template selector + variable mapper
  - send_text → textarea with {{variable}} autocomplete
  - send_instructions → radio: from treatment / custom
  - notify_team → channel selector + message textarea
  - update_status → field selector + value input
- **Response handling** (only for send_template, send_text, send_instructions):
  - "¿Esperar respuesta?" toggle
  - Timeout duration
  - Keyword rules builder: [grupo] [palabras clave] → [acción]
  - On no response: dropdown (continuar / abortar / reintentar / notificar)
  - On unclassified: dropdown (pasar al agente IA / continuar / pausar)

### S4.5: StepTimeline.tsx

Visual vertical timeline:
- Each step = node with icon + label + delay badge
- Connecting lines between steps
- Branch indicators (fork icon) where response handling splits
- Active step highlighted (green pulse) for running executions
- Completed steps grayed out

### S4.6: MessagePreview.tsx

WhatsApp-style bubble mock:
- Green bubble with message text
- Variables replaced with sample data ("María", "lunes", "14/05", "10:00")
- Template buttons rendered below (if send_template)
- Timestamp mock

---

## S5: Pre-built Playbooks (Seeded on First Activation)

| # | Name | Trigger | Steps Summary |
|---|------|---------|---------------|
| 1 | Escudo Anti-Ausencias | appointment_reminder (24h before) | HSM template con botones → si no confirma: +2h Seguimiento Rápido → si no responde: notify team |
| 2 | Protocolo Post-Quirúrgico | appointment_completed (treatment=cirugia*,implante*) | +3h send_instructions → +24h "¿Cómo te sentís?" → branch on keywords (dolor→notify, bien→continue) → +7d reseña Google |
| 3 | Motor de Reseñas Google | appointment_completed (treatment=implante*,cirugia*,estetica*) | +7d send_template (Post-Implantes/Post-Cirugía/Blanqueamiento según tratamiento) |
| 4 | Recuperador de No-Shows | no_show | Inmediato: "Notamos que no pudiste asistir" → +24h "¿Querés reprogramar?" → +7d último intento → abort |
| 5 | Cobrador de Seña | appointment_created (payment_pending) | -24h del turno: "Recordá tu saldo de ${{saldo}}" → post-turno si sigue pendiente: recordatorio |
| 6 | Reactivador de Pacientes | patient_inactive (90 days) | "Te extrañamos" → +30d si no responde: "Control cada 6 meses" → abort |
| 7 | Bienvenida Primer Contacto | lead_first_message | Inmediato: mensaje de bienvenida personalizado (ya lo hace el agente, este es un refuerzo configurable) |
| 8 | Seguimiento Post-Consulta | appointment_completed (treatment=consulta*) | +48h: "¿Pudiste pensar en lo que conversamos?" → +7d si no agendó: soft close |
| 9 | Segundo Aviso | linked to playbook #1 | +2h sin confirmar recordatorio → HSM Seguimiento Rápido con 3 botones |

---

## S6: Variables Disponibles

Variables que se pueden usar en `message_text`, `notify_message`, `template_vars`:

| Variable | Source | Example |
|----------|--------|---------|
| `{{nombre_paciente}}` | patients.first_name | María |
| `{{apellido_paciente}}` | patients.last_name | López |
| `{{telefono}}` | patients.phone_number | +5491112345678 |
| `{{tratamiento}}` | appointments.appointment_type → treatment_types.name | Implante Simple |
| `{{categoria_tratamiento}}` | treatment_types.category | implantes |
| `{{profesional}}` | professionals.first_name + last_name | Laura Delgado |
| `{{fecha_turno}}` | appointments.appointment_datetime formatted | 14/05 |
| `{{hora_turno}}` | appointments.appointment_datetime formatted | 10:00 |
| `{{dia_semana}}` | appointments.appointment_datetime day name | lunes |
| `{{sede}}` | tenant working_hours[day].location | Sede Norte |
| `{{precio}}` | treatment_types.base_price | $45.000 |
| `{{saldo_pendiente}}` | appointments.billing_amount - paid | $22.500 |
| `{{dias_sin_turno}}` | NOW() - last appointment date | 45 |
| `{{link_anamnesis}}` | generated from patient.anamnesis_token | https://app.../anamnesis/1/abc |
| `{{nombre_clinica}}` | tenants.clinic_name | Clínica Dra. Laura Delgado |

---

## S7: Scenarios

### SC1: CEO activa playbook pre-armado
1. CEO abre PlaybooksView → ve galería de cards
2. Click "🚀 Activar" en "Escudo Anti-Ausencias"
3. Modal se abre con todos los pasos pre-configurados
4. CEO revisa, ajusta horarios si quiere
5. Click "Guardar y activar"
6. Card cambia a ON con stats iniciales

### SC2: CEO crea playbook custom
1. Click "+ Crear estrategia"
2. Elige trigger: "Turno completado"
3. Filtra: solo tratamientos "Endolifting"
4. Agrega paso 1: send_text "Hola {{nombre_paciente}}, ¿cómo te sentís?"
5. Agrega paso 2: wait_response 24h, keywords: dolor→notify, bien→continue
6. Agrega paso 3: send_template "Reseña Google" (si todo bien)
7. Guarda

### SC3: Paciente confirma turno via botón
1. Executor envía HSM recordatorio con botones
2. Paciente toca "Confirmar asistencia ✅"
3. chat_webhooks.py intercepta → busca execution en waiting_response
4. Actualiza appointment status=confirmed
5. Avanza execution al siguiente paso
6. Responde "✅ Tu turno quedó confirmado"
7. Emite socket APPOINTMENT_UPDATED

### SC4: Paciente reporta dolor post-cirugía
1. Executor envió "¿Cómo te sentís?" y está en waiting_response
2. Paciente responde "me duele mucho la muela"
3. Layer 2 keyword match: "duele" → grupo "urgencia"
4. Action: notify_and_pause → envía Telegram al equipo, pausa execution
5. Equipo ve notificación, llama al paciente
6. Puede resumir o abortar desde el dashboard

### SC5: Pre-flight check bloquea mensaje
1. Executor quiere enviar paso 2 de playbook A al paciente María
2. Pre-flight: María ya recibió 2 mensajes hoy (de playbook B)
3. Executor posterga next_step_at a mañana 09:00
4. Logs: "skipped: daily_cap_reached"
