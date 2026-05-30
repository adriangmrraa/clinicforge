# Proposal: Automation Engine V2 — Playbooks Clínicos

## Intent

Replace flat automation_rules with a **Playbook-based engine**: multi-step sequences where each step is fully configurable from the UI (action type, delay, message content, response handling, branching, schedule window). Playbooks are NOT just "WhatsApp template senders" — they are **clinical protocol automators** that can send templates, free text, treatment instructions, notify the team, update records, and create internal tasks. CEO sees "business objectives" (reduce no-shows, get reviews), not technical triggers. Max 2 messages/day per patient, 24h window auto-close on no-response.

## Scope

### In Scope
- 4 new DB tables: `automation_playbooks`, `automation_steps`, `automation_executions`, `automation_events`
- `last_automation_message_at` column on `patients` for global cooldown (max 2/day configurable)
- Backend: playbook + steps CRUD endpoints, executor job (every 5 min), 3-layer response classifier (buttons → keywords → LLM)
- Frontend: PlaybooksView with card gallery, conversational config modal, **per-step configuration UI** (type, delay, message, variables, response handling, branching, schedule window), step timeline visualization, WhatsApp message preview
- 8 action types per step: `send_template`, `send_text`, `send_instructions`, `wait`, `wait_response`, `branch`, `notify_team`, `update_status`
- Per-step configurable fields: delay (hours/days), schedule window (hour min/max), message content with variable picker, response classification rules (keyword lists per outcome), timeout duration, branch targets (on response / no response / keyword match)
- 9 pre-built playbook templates with all steps pre-configured (Recordatorio, Post-Quirúrgico, Reseña Google, No-Show Recovery, Cobro Saldo, Reactivación, Bienvenida, Post-Consulta, Segundo Aviso)
- Abort conditions: patient booked, human override, opt-out, objective met
- Pre-flight check: no duplicate messages to same patient across playbooks
- Step reordering (move up/down) and step deletion from UI

### Out of Scope
- Multi-channel sequences (Instagram/Facebook templates) — WhatsApp only for V2
- Visual drag-and-drop step builder — use ordered list + timeline preview
- A/B testing of messages
- Removal of old MetaTemplatesView (stays until full migration)

## Approach

**Hybrid migration**: new tables alongside old. New executor runs in parallel with legacy jobs. Migrate one trigger_type at a time starting with `appointment_reminder`. Old jobs remain until all playbooks are live.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `alembic/versions/047_*` | New | Migration: 4 tables + patients column |
| `models.py` | Modified | ORM classes for playbooks, steps, executions, events |
| `jobs/playbook_executor.py` | New | Processes pending executions every 5 min |
| `routes/playbook_routes.py` | New | CRUD for playbooks + steps + execution status + stats |
| `routes/chat_webhooks.py` | Modified | Extend button/response intercept → advance execution state |
| `services/playbook_classifier.py` | New | 3-layer response classifier (buttons → keywords → LLM) |
| `views/PlaybooksView.tsx` | New | Card gallery + config modal + per-step editor + timeline |
| `components/PlaybookCard.tsx` | New | Objective card with KPIs and status |
| `components/StepEditor.tsx` | New | Per-step config: type, delay, message, vars, branches |
| `components/StepTimeline.tsx` | New | Visual sequence with connecting lines |
| `components/MessagePreview.tsx` | New | WhatsApp bubble preview with variable substitution |

## Step Configuration Schema

Each step exposes these configurable fields in the UI:

| Field | Type | Description |
|-------|------|-------------|
| `action_type` | select | send_template, send_text, send_instructions, wait, wait_response, branch, notify_team, update_status |
| `delay_value` | number | How long to wait before executing |
| `delay_unit` | select | minutes, hours, days |
| `schedule_hour_min` | number | Earliest hour to send (default 9) |
| `schedule_hour_max` | number | Latest hour to send (default 20) |
| `template_name` | select | YCloud approved template (for send_template) |
| `template_vars` | map | Variable → value mapping (for send_template) |
| `message_text` | textarea | Free text with {{variables}} (for send_text) |
| `instruction_source` | select | "from_treatment" or "custom" (for send_instructions) |
| `custom_instructions` | textarea | Custom instructions text (if source=custom) |
| `wait_timeout_value` | number | How long to wait for response |
| `wait_timeout_unit` | select | minutes, hours, days |
| `on_response_keywords` | map | keyword_group → next_step (e.g., "dolor,sangra,fiebre" → notify_team step) |
| `on_response_positive` | select | Next step if positive response |
| `on_response_negative` | select | Next step if negative/concerning response |
| `on_no_response` | select | Next step if timeout reached |
| `on_response_other` | select | What to do with unclassified responses (pass_to_ai, continue, pause) |
| `notify_channel` | select | telegram, dashboard, both (for notify_team) |
| `notify_message` | textarea | Team notification text with {{variables}} |
| `update_field` | select | appointment_status, patient_tag, etc. (for update_status) |
| `update_value` | text | New value for the field |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Executor misses pending steps after restart | Med | Query by `next_step_at <= NOW()`, not in-memory timers |
| Patient gets 3+ messages in one day | Med | `last_automation_message_at` + pre-flight check (hard cap 2/day) |
| LLM classification cost explosion | Low | Layers 1-2 handle 95% of responses; LLM only for ambiguous |
| Migration breaks existing reminders | Med | Old jobs stay active until playbook equivalent is validated per-tenant |
| Step config complexity overwhelms CEO | Med | Pre-built playbooks come with all steps pre-configured; CEO only tweaks |

## Rollback Plan

- New tables are additive — `DROP TABLE` reverts cleanly
- Old `automation_rules` + jobs untouched during migration
- Feature flag: `tenants.config.use_playbooks_v2` (boolean) — per-tenant opt-in
- If issues: set flag to false → old system resumes immediately

## Dependencies

- YCloud API key configured per tenant (already exists)
- Approved WhatsApp templates in Meta (6 already approved)

## Success Criteria

- [ ] CEO can activate pre-built playbooks from card gallery in <30 seconds
- [ ] Each step is individually configurable: type, delay, message, response handling, schedule
- [ ] Steps can be reordered, added, and deleted from the UI
- [ ] Appointment reminder sends HSM template with buttons, responses auto-processed
- [ ] No patient receives >2 automated messages per day
- [ ] Execution state persists across server restarts
- [ ] Metrics show confirmation rate, messages sent, time saved per playbook
- [ ] Pre-built playbooks work out-of-the-box with one click
