# .spec.md: WhatsApp Automations & AI Templates v1.0

## 1. Context & Business Goal
Integrate automated WhatsApp communications for Dr. Delgado's clinic to improve appointment adherence and patient engagement.
- **Reminders**: 24h before confirmed appointments.
- **Feedback**: 45m after appointment completion.
- **Meta Ads Templates**: Integration with campaigns to allow follow-ups outside the 24h window.

## 2. Technical Architecture

### 2.1 Trigger System (The Cron/Scheduler)
We will implement a periodic background task in `orchestrator_service` using a simple `asyncio` loop or `APScheduler` if available.
- **Frequency**: Every 15 minutes.
- **Check 1: Reminders**: Find `appointments` where `status = 'confirmed'`, `datetime` is between 24h and 25h from now, and `reminder_sent = FALSE`.
- **Check 2: Feedback**: Find `appointments` where `status = 'Completado'`, `completed_at` is ~45m ago, and a new flag `feedback_sent = FALSE`.

### 2.2 Template Management (YCloud)
Update `YCloudClient` to support `templates`.
- **Method**: `send_template(phone, template_name, [params])`.
- **Parameters Mapping**: Use patient/appointment data to fill template variables ({{1}} = First Name, {{2}} = Time, etc.).

### 2.3 Idempotency & Tracking
New table `automation_logs`:
- `id`, `tenant_id`, `appointment_id`, `patient_id`, `template_name`, `status` (sent, received, failed), `sent_at`.

## 3. Implementation Phases

### Phase 1: Infrastructure
1.  **Database Evolution**: Add `automation_logs` table and `feedback_sent` column to `appointments`.
2.  **YCloud Enrichment**: Add template support to `YCloudClient`.

### Phase 2: Orchestrator Logic
1.  **Scheduler Loop**: Implement the periodic checker in a new `services/automation_service.py`.
2.  **Logic Handlers**: Specific logic for "24h Reminder" and "45m Feedback".
3.  **Tenant/Sovereignty**: Ensure each clinic's automations run independently with their own credentials.

### Phase 3: AI Integration
1.  **Synthesis Task**: Before sending a "Post-Consultation" message, the AI summarizes the patient journey to customize the message if the template allows (or to choose the best template).

## 4. Specific Automated Messages (The Templates)
1.  **Reminder 24h**: "Hola {{1}}, te recordamos tu cita de mañana a las {{2}} en {{3}}. ¿Confirmas tu asistencia?"
2.  **Feedback 45m**: "Hola {{1}}, gracias por elegir a la Dra. Delgado. ¿Cómo fue tu experiencia hoy? Nos encantaría recibir tu reseña aquí: {{2}}"
