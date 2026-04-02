# Tasks: Complete Payment System

## Overview
Implementar sistema integral de pagos: seña + tratamiento completo + cuotas con estados diferenciados, UI de facturación, verificación IA, y métricas de cobro.

## Phase 1: Database & Backend Foundation

### 1.1 Create migration for new table and columns
- [ ] 1.1.1 Create Alembic migration `017_add_payment_stage_and_installments.py`
- [ ] 1.1.2 Create table `appointment_installments` with fields
- [ ] 1.1.3 Add columns `payment_type` and `payment_stage` to appointments
- [ ] 1.1.4 Add indexes for performance

### 1.2 Extend models.py
- [ ] 1.2.1 Add `PaymentStage` enum
- [ ] 1.2.2 Add `PaymentType` enum
- [ ] 1.2.3 Create `AppointmentInstallment` model

### 1.3 Extend verify_payment_receipt
- [ ] 1.3.1 Add `payment_type` detection logic (seña/treatment/installment)
- [ ] 1.3.2 Update payment_stage based on amount and type
- [ ] 1.3.3 Handle installment-specific logic
- [ ] 1.3.4 Save payment_type in payment_receipt_data

## Phase 2: Installment Management

### 2.1 Backend installment logic
- [ ] 2.1.1 Create function `create_installments(appointment_id, billing_amount, num_installments)`
- [ ] 2.1.2 Create function `update_installment_status(installment_id, status)`
- [ ] 2.1.3 Create function `get_installment_by_number(appointment_id, number)`
- [ ] 2.1.4 Calculate due dates based on first_due_date

### 2.2 API endpoints for installments
- [ ] 2.2.1 PUT `/appointments/{id}/billing-installments` - Create/update installments
- [ ] 2.2.2 GET `/appointments/{id}/installments` - List installments
- [ ] 2.2.3 POST `/appointments/{id}/register-payment` - Register payment for specific installment

## Phase 3: Frontend - Billing Tab

### 3.1 Create BillingTab component
- [ ] 3.1.1 Create `frontend_react/src/views/BillingTab.tsx`
- [ ] 3.1.2 Add summary cards (total pending, total paid)
- [ ] 3.1.3 Add appointment list with payment status

### 3.2 Create AppointmentBillingCard
- [ ] 3.2.1 Create `AppointmentBillingCard.tsx` component
- [ ] 3.2.2 Display payment stage with color indicator
- [ ] 3.2.3 Show installment progress (if applicable)
- [ ] 3.2.4 Add "Registrar pago" button

### 3.3 Update PatientDetail navigation
- [ ] 3.3.1 Add "Facturación" tab button
- [ ] 3.3.2 Integrate BillingTab in tab switch
- [ ] 3.3.3 Fetch billing data on mount

### 3.4 Update AppointmentForm billing section
- [ ] 3.4.1 Show payment_stage with new colors (green + $ for paid_complete)
- [ ] 3.4.2 Display installments list with status
- [ ] 3.4.3 Add "Create installments" functionality
- [ ] 3.4.4 Add manual "Mark as paid" button

## Phase 4: Post-Appointment Communication

### 4.1 Email post-appointment
- [ ] 4.1.1 Add `send_post_appointment_email()` in email_service.py
- [ ] 4.1.2 Create HTML template with pending balance
- [ ] 4.1.3 Trigger after appointment status = 'completed'

### 4.2 Trigger post-appointment communication
- [ ] 4.2.1 Modify appointment status update to trigger email
- [ ] 4.2.2 Use existing automation_rules trigger 'post_appointment_completed'

## Phase 5: Payment Reminders

### 5.1 Create payment_reminder job
- [ ] 5.1.1 Create `jobs/payment_reminders.py`
- [ ] 5.1.2 Find overdue installments (due_date < today AND status = pending)
- [ ] 5.1.3 Trigger automation_rules for each overdue installment

### 5.2 Extend automation_rules
- [ ] 5.2.1 Add 'payment_reminder' trigger type
- [ ] 5.2.2 Add UI option in MetaTemplatesView (if needed)
- [ ] 5.2.3 Handle context with installment_id

## Phase 6: Metrics & Dashboard

### 6.1 Backend metrics
- [ ] 6.1.1 Add endpoint `/admin/dashboard/billing-metrics`
- [ ] 6.1.2 Calculate collection_rate: (paid_complete / completed) * 100
- [ ] 6.1.3 Calculate avg_days_to_payment
- [ ] 6.1.4 Count overdue_installments

### 6.2 Frontend dashboard integration
- [ ] 6.2.1 Add billing metrics to main dashboard
- [ ] 6.2.2 Show collection rate percentage
- [ ] 6.2.3 Show overdue installments count

## Phase 7: Agent IA Context

### 7.1 Update AGENTS.md
- [ ] 7.1.1 Add payment management rules for post-appointment
- [ ] 7.1.2 Document how agent detects payment type
- [ ] 7.1.3 Document how to check patient balance

### 7.2 Update system prompts
- [ ] 7.2.1 Add context about pending payments after completion
- [ ] 7.2.2 Add guidance for payment verification with types

## Phase 8: Testing

### 8.1 Unit tests
- [ ] 8.1.1 Test payment_type detection logic
- [ ] 8.1.2 Test installment creation and calculation
- [ ] 8.1.3 Test payment_stage transitions

### 8.2 Integration tests
- [ ] 8.2.1 Test full flow: seña payment → verify → stage update
- [ ] 8.2.2 Test full flow: treatment payment → verify → stage update
- [ ] 8.2.3 Test full flow: installment payment → verify → installment update

### 8.3 Manual testing
- [ ] 8.3.1 Test sending receipt via WhatsApp
- [ ] 3.3.2 Test manual payment registration
- [ ] 8.3.3 Test UI display of payment stages

---

## Effort Estimation
- Phase 1 (DB): Medium
- Phase 2 (Backend installments): Medium
- Phase 3 (Frontend): Large
- Phase 4 (Email): Small
- Phase 5 (Reminders): Medium
- Phase 6 (Metrics): Small
- Phase 7 (Agent): Small
- Phase 8 (Testing): Medium

## Recommended Execution Order
1. **Phase 1** - Database & models (foundation)
2. **Phase 2** - Backend logic for installments
3. **Phase 4** - Post-appointment email (simpler)
4. **Phase 5** - Payment reminders
5. **Phase 3** - Frontend (depends on backend)
6. **Phase 6** - Metrics (depends on data)
7. **Phase 7** - Agent context (anytime)
8. **Phase 8** - Testing (end)