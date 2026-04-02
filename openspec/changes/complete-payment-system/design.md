# Technical Design: Complete Payment System (seña + treatment + cuotas)

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE PAYMENT SYSTEM FLOW                            │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────┐
                    │           APPOINTMENT LIFECYCLE             │
                    └─────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   SCHEDULED  │───▶│  CONFIRMED   │───▶│  COMPLETED   │───▶│   ARCHIVED   │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ PENDING     │    │ SEÑA_PAID    │    │ PAID_COMPLETE │
│ (sin pagar) │    │ (seña pagada)│    │ (todo pagado) │
└──────────────┘    └──────────────┘    └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   PARTIAL    │
                    │ (cuotas)     │
                    └──────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENT PAYMENT FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

PACIENTE ENVÍA COMPROBANTE
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ buffer_task.py                                                              │
│ - Clasifica como payment_receipt                                           │
│ - Si tiene turno con payment_stage != 'paid_complete'                    │
│   → llama verify_payment_receipt                                          │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ verify_payment_receipt (MODIFIED)                                           │
│                                                                             │
│ 1. Recibe: appointment_id, receipt_description, amount_detected            │
│                                                                             │
│ 2. Detecta tipo de pago:                                                  │
│    - amount <= seña_expected → seña                                        │
│    - amount >= treatment_expected → treatment                               │
│    - amount == cuota_X → installment                                       │
│                                                                             │
│ 3. Actualiza appointment:                                                │
│    - payment_type = 'seña'|'treatment'|'installment'                    │
│    - payment_stage según monto                                             │
│    - Crea/actualiza appointment_installments si es cuota                 │
│                                                                             │
│ 4. Guarda en patient_documents                                             │
│                                                                             │
│ 5. Envía email confirmación                                                │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PatientDetail UI (MODIFIED)                                                 │
│                                                                             │
│ Pestaña "Facturación":                                                     │
│ - Lista de turnos con estados de pago                                       │
│ - Botón "Registrar pago manualmente"                                       │
│ - Indicadores visuales por estado                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 2. Database Changes

### 2.1 New Table: appointment_installments

```sql
CREATE TABLE appointment_installments (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    installment_number INTEGER NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    due_date DATE,
    paid_date DATE,
    payment_status VARCHAR(20) DEFAULT 'pending',
    receipt_document_id INTEGER REFERENCES patient_documents(id),
    source_details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, appointment_id, installment_number)
);

CREATE INDEX idx_installments_tenant_appointment ON appointment_installments(tenant_id, appointment_id);
CREATE INDEX idx_installments_due_date ON appointment_installments(due_date);
CREATE INDEX idx_installments_status ON appointment_installments(payment_status);
```

### 2.2 Extensions to appointments

```sql
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS payment_type VARCHAR(20);
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS payment_stage VARCHAR(20) DEFAULT 'pending';

-- payment_type: 'seña' | 'treatment' | 'installment'
-- payment_stage: 'pending' | 'seña_paid' | 'partial' | 'paid_complete'
```

## 3. Component Design

### 3.1 verify_payment_receipt Extensions (main.py)

```python
# Current (seña only):
expected_amount = billing_amount or calculate_seña()

# New (multi-type):
def calculate_expected_amount(billing_amount, payment_type, installment_number=None):
    if payment_type == 'seña':
        return billing_amount * Decimal('0.5')  # 50%
    elif payment_type == 'treatment':
        return billing_amount  # Full amount
    elif payment_type == 'installment':
        # Get from appointment_installments
        return get_installment_amount(installment_number)
    return billing_amount * Decimal('0.5')

# Flow:
1. Detect payment_type based on amount vs billing_amount
2. Save payment_type in payment_receipt_data
3. Update payment_stage accordingly
4. If installment: create/update appointment_installments
```

### 3.2 BillingTab Component (Frontend)

```tsx
// PatientDetail.tsx - New tab
const BillingTab = ({ patientId, billingSummary }) => {
  return (
    <div className="space-y-4">
      {/* Summary Card */}
      <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-4">
        <h3 className="text-lg font-semibold text-white mb-2">Resumen de Pagos</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-white/40">Total Pendiente</p>
            <p className="text-xl font-bold text-red-400">${totalPending}</p>
          </div>
          <div>
            <p className="text-xs text-white/40">Pagado</p>
            <p className="text-xl font-bold text-green-400">${totalPaid}</p>
          </div>
        </div>
      </div>

      {/* Appointments List */}
      {appointments.map(apt => (
        <AppointmentBillingCard 
          key={apt.id} 
          appointment={apt}
          onRegisterPayment={handleRegisterPayment}
        />
      ))}
    </div>
  );
};

// Payment Stage Indicators
const stageColors = {
  pending: 'bg-red-500',
  seña_paid: 'bg-yellow-500', 
  partial: 'bg-orange-500',
  paid_complete: 'bg-green-500'
};

const stageLabels = {
  pending: 'Sin pagar',
  seña_paid: 'Seña pagada',
  partial: 'En cuotas',
  paid_complete: 'Pagado 💰'
};
```

### 3.3 Installment Management

```python
# backend: Create installments when billing_installments is set
async def create_installments(appointment_id, billing_amount, billing_installments):
    installment_amount = billing_amount / billing_installments
    
    for i in range(1, billing_installments + 1):
        due_date = calculate_due_date(appointment_datetime, i, billing_installments)
        
        await db.pool.execute("""
            INSERT INTO appointment_installments 
            (tenant_id, appointment_id, installment_number, amount, due_date)
            VALUES ($1, $2, $3, $4, $5)
        """, tenant_id, appointment_id, i, installment_amount, due_date)
```

### 3.4 Post-Appointment Email

```python
# email_service.py - Add new function
async def send_post_appointment_email(patient, appointment, pending_amount):
    template = """
    Hola {patient_name},
    
    Tu turno de {treatment} con {professional} del {date} ha sido completado.
    
    {saldo_pendiente}
    
    Para completar tu pago, puedes transferir a:
    CBU: {cbu}
    Alias: {alias}
    
    ¡Te esperamos en tu próxima visita!
    """
    # Send via existing email_service
```

### 3.5 Payment Reminder Job

```python
# jobs/payment_reminders.py - Similar to appointment_reminders
async def send_payment_reminders():
    # Find overdue installments
    overdue = await db.pool.fetch("""
        SELECT ai.*, p.first_name, p.last_name, p.phone_number, a.treatment
        FROM appointment_installments ai
        JOIN appointments a ON a.id = ai.appointment_id
        JOIN patients p ON p.id = a.patient_id
        WHERE ai.due_date < CURRENT_DATE
          AND ai.payment_status = 'pending'
          AND a.status IN ('completed', 'archived')
        ORDER BY ai.due_date ASC
    """)
    
    # Trigger automation_rules for each
    for installment in overdue:
        await trigger_automation_rule(
            tenant_id=installment['tenant_id'],
            trigger_type='payment_reminder',
            patient_id=installment['patient_id'],
            context={'installment_id': installment['id']}
        )
```

## 4. API Endpoints

### 4.1 GET /patients/{id}/billing-summary

```json
{
  "patient_id": 42,
  "total_pending": 50000,
  "total_paid": 50000,
  "appointments": [
    {
      "id": 1,
      "treatment": "Ortodoncia",
      "appointment_datetime": "2026-04-15T10:00:00Z",
      "billing_amount": 100000,
      "payment_type": "installment",
      "payment_stage": "partial",
      "seña_paid": 20000,
      "paid_amount": 40000,
      "remaining": 60000,
      "installments": [
        {"number": 1, "amount": 20000, "due_date": "2026-05-15", "status": "paid", "paid_date": "2026-04-20"},
        {"number": 2, "amount": 20000, "due_date": "2026-06-15", "status": "pending"},
        {"number": 3, "amount": 20000, "due_date": "2026-07-15", "status": "pending"}
      ]
    }
  ]
}
```

### 4.2 POST /appointments/{id}/register-payment

```json
{
  "amount": 20000,
  "payment_type": "installment",
  "installment_number": 2,
  "notes": "Cuota de mayo"
}
```

### 4.3 PUT /appointments/{id}/billing-installments

```json
{
  "installments": 3,
  "first_due_date": "2026-05-15"
}
```

## 5. Integration Points

| File | Change | Description |
|------|--------|--------------|
| `models.py` | Modify | Add payment_type, payment_stage fields |
| `main.py` | Modify | Extend verify_payment_receipt |
| `admin_routes.py` | Modify | Billing endpoints, create_installments |
| `email_service.py` | Modify | Add post-appointment email |
| `jobs/payment_reminders.py` | Create | Payment reminder job |
| `PatientDetail.tsx` | Modify | Add BillingTab |
| `AppointmentForm.tsx` | Modify | Show installment details |

## 6. Agent IA Context

```
RULE: POST-APPOINTMENT PAYMENT MANAGEMENT
─────────────────────────────────────────
After an appointment is completed:
1. The system sends a post-appointment message to the patient
2. Check if patient has pending payments (payment_stage != 'paid_complete')
3. If pending, ask: "¿Tiene el saldo pendiente? ¿Quiere realizar el pago?"
4. If patient sends a receipt:
   - Use verify_payment_receipt with payment_type detection
   - The system will automatically detect if it's:
     * Seña (first payment)
     * Treatment (full payment)
     * Installment (specific cuota)
5. Update the appointment and notify the clinic

When patient asks about their balance:
- Use list_patient_appointments to show billing status
- Explain what payments are pending and due dates
```

## 7. Error Handling

| Scenario | Handling |
|----------|-----------|
| Amount doesn't match any expected | Ask patient for clarification |
| Installment not found | Create new installment record |
| Duplicate payment | Warn and allow manual override |
| Payment exceeds total | Mark as overpaid, refund process |

## 8. Metrics & Dashboard

```python
# admin_routes.py - Add billing metrics
@app.get("/admin/dashboard/billing-metrics")
async def get_billing_metrics(tenant_id):
    # Tasa de cobro
    total_completed = count_appointments(status='completed')
    total_paid = count_appointments(payment_stage='paid_complete')
    collection_rate = (total_paid / total_completed) * 100
    
    # Tiempo promedio de cobro
    avg_days_to_pay = calculate_avg_days_to_payment()
    
    # Cuotas vencidas
    overdue_installments = count_overdue_installments()
    
    return {
        "collection_rate": collection_rate,
        "avg_days_to_pay": avg_days_to_pay,
        "overdue_installments": overdue_installments,
        "pending_amount": calculate_pending_amount()
    }
```

## 9. Rollback Plan

1. Remove `payment_type`, `payment_stage` columns (keep for data migration)
2. Drop `appointment_installments` table
3. Revert verify_payment_receipt to original logic
4. Hide BillingTab in frontend
5. Disable payment_reminder automation trigger