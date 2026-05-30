# Exploration: Automation Engine V2 — Playbook-Based Motor

## Current State

### Database Tables
- **`automation_rules`**: Flat rules with `trigger_type`, `condition_json` (JSONB), `message_type` (free_text|hsm), `ycloud_template_name`, `ycloud_template_vars` (JSONB), `channels` (ARRAY), `send_hour_min/max`. No support for multi-step sequences, delays, branching, or execution tracking.
- **`automation_logs`**: Event log per send attempt. Fields: `trigger_type`, `status`, `message_preview`, `template_name`, `skip_reason`, `error_details`, `triggered_at`, `sent_at`, `delivered_at`. No link to execution state (which step a patient is on).
- **`appointments`**: Has `reminder_sent`, `reminder_sent_at`, `followup_sent`, `followup_sent_at` — tracking is per-appointment, not per-automation-flow.
- **`patients`**: Has `no_followup` boolean. No `last_automation_message_at` for cooldown control.

### Jobs (Backend Execution)
| Job | Trigger Type | Schedule | Reads Rule? | Sends Template? | Status |
|-----|-------------|----------|-------------|-----------------|--------|
| `reminders.py` | `appointment_reminder` | Daily 10 AM | ✅ Yes (incl. HSM) | ✅ Yes (just implemented) | **Working** |
| `followups.py` | `post_treatment_followup` | Daily 11 AM | Partial (skips if HSM rule exists) | ❌ Only free text | **Partial** |
| `lead_recovery.py` | `lead_meta_no_booking` | Every 15 min | ✅ Yes (condition_json for delays) | ❌ Only free text (AI-generated) | **Working but no HSM** |
| `admin_routes.py:send_post_appointment_feedback` | `post_appointment_completed` | Event-driven (on complete) | ✅ Yes (free_text_message) | ❌ Only free text | **Partial** |
| N/A | `patient_reactivation` | — | — | — | **UI only, no job** |
| N/A | `appointment_status_change` | — | — | — | **UI only, no job** |

### Frontend (MetaTemplatesView.tsx)
- Functional CRUD for rules: create, edit, toggle, delete
- Template selector that fetches approved YCloud templates via `/admin/automations/ycloud-templates`
- Variable mapping UI for HSM templates
- Logs viewer with filters (trigger, status, channel, date range)
- Stats (sent count, delivery rate)
- **Missing**: no concept of steps/sequences, no playbook gallery, no execution tracking, no preview simulation

### Button Response Handling (chat_webhooks.py)
- Already implemented: intercepts template quick-reply buttons before AI agent
- Handles: confirm (→ update appointment status), cancel (→ cancel appointment), reschedule (→ empathetic reply + pass to AI)
- Covers templates 5 (Recordatorio) and 6 (Seguimiento Rápido) button texts

### YCloud Integration
- `YCloudClient.send_template()` — sends HSM with components (positional params)
- `GET /admin/automations/ycloud-templates` — proxy to YCloud API, returns approved templates
- 6 approved templates in Meta: Post-Implantes, Post-Cirugía, Blanqueamiento, Armonización, Recordatorio de Asistencia, Seguimiento Rápido

## Affected Areas

### New tables needed (Alembic migration)
- `automation_playbooks` — replaces/extends automation_rules (adds category, icon, description, frequency_cap, stats cache)
- `automation_steps` — ordered steps within a playbook (action_type, delay, template, branching)
- `automation_executions` — per-patient-per-playbook state tracking (current_step, status, next_step_at)
- `automation_events` — granular event log for analytics (replaces automation_logs partially)
- Add `last_automation_message_at` to `patients` table for global cooldown

### Backend files
- `orchestrator_service/jobs/` — new `playbook_executor.py` job that processes pending executions
- `orchestrator_service/admin_routes.py` — new CRUD endpoints for playbooks, steps, executions
- `orchestrator_service/routes/chat_webhooks.py` — extend button intercept to check execution state
- `orchestrator_service/models.py` — new ORM classes

### Frontend files
- `frontend_react/src/views/MetaTemplatesView.tsx` — major rewrite → PlaybooksView
- New components: PlaybookCard, PlaybookConfigModal, StepTimeline, MessagePreview

## Approaches

### 1. Evolutionary (extend current system)
Keep `automation_rules` table, add `automation_steps` as child. Refactor jobs to read steps.
- Pros: Less migration risk, backward compatible, smaller diff
- Cons: Awkward schema (rules ≠ playbooks conceptually), existing jobs become messy
- Effort: Medium

### 2. Clean Break (new tables, new UI, migrate data)
New `automation_playbooks` + `automation_steps` + `automation_executions` tables. New PlaybooksView.tsx. Migrate existing automation_rules data to new schema. Old jobs deprecated gradually.
- Pros: Clean architecture, proper execution tracking, no legacy baggage
- Cons: Bigger migration, need to handle both old and new during transition
- Effort: High

### 3. Hybrid (new tables alongside, gradual migration)
Create new tables. Build new PlaybooksView. Keep old MetaTemplatesView temporarily. New playbook executor runs alongside old jobs. Migrate rules one trigger_type at a time.
- Pros: Zero downtime, gradual, can validate per-playbook
- Cons: Temporary code duplication, two systems running in parallel
- Effort: Medium-High

## Recommendation

**Approach 3 (Hybrid)** — Build the new system alongside the old one:

1. New tables (playbooks, steps, executions, events) via Alembic migration
2. New executor job that processes playbook executions
3. New UI (PlaybooksView) as a separate page — old MetaTemplatesView stays until all rules are migrated
4. Migrate one trigger_type at a time: start with `appointment_reminder` (already has HSM + button intercept)
5. Once all triggers migrated, remove old jobs and MetaTemplatesView

This avoids breaking production while building the new system incrementally.

## Risks

1. **Execution state management**: Long-running sequences (days/weeks) require robust state persistence. If the server restarts, pending executions must resume correctly.
2. **Message flooding**: Without proper cooldown logic, multiple playbooks could fire at the same patient simultaneously. The `frequency_cap_hours` + `last_automation_message_at` + pre-flight check are critical.
3. **Template variable ordering**: Meta uses positional `{{1}}`, `{{2}}` — if the step config has wrong order, messages render incorrectly. Need validation in the UI.
4. **LLM classification cost**: If Capa 3 (LLM classification) fires too often, costs escalate. Must ensure Capas 1-2 handle 90%+ of responses.
5. **Migration data integrity**: Existing automation_rules have active executions (reminders sent today). Migration must not re-trigger already-sent messages.

## Ready for Proposal

Yes — the codebase is well understood. Proceed to proposal with:
- Hybrid approach (new tables alongside old)
- Phased implementation (F1: DB + API, F2: UI, F3: Executor, F4: Response classification, F5: Metrics)
- Start with appointment_reminder playbook as pilot
