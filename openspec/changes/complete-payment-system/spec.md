# Specs: Sistema Integral de Pagos por Turno

## 1. Overview

Extender el sistema de pagos para manejar el flujo completo: seña, pago de tratamiento completo post-turno, y cuotas. El sistema debe permitir gestionar pagos por turno con múltiples etapas, verificación IA de comprobantes, y métricas de cobro.

## 2. Functional Requirements

### FR-01: Estados de Pago Multi-Etapa
El sistema DEBE tener estados de pago diferenciados para cada etapa:
- **pending**: Sin pago (grís/rojo)
- **seña_paid**: Seña pagada, resto pendiente (amarillo)
- **partial**: Pago parcial o en cuotas (naranja)
- **paid_complete**: Tratamiento completo pagado (verde con símbolo $)

### FR-02: Tipos de Pago
El sistema DEBE soportar tipos de pago configurables:
- **seña**: Pago inicial al agendar (50% typical)
- **treatment**: Pago completo del tratamiento
- **installment**: Sistema de cuotas

### FR-03: Sistema de Cuotas
El sistema DEBE permitir configurar cuotas por turno:
- Número de cuotas configurables
- Fecha de vencimiento por cuota
- Seguimiento individual de cada cuota
- Registro de pago por cuota

### FR-04: Verificación IA de Comprobantes
El agente DEBE verificar comprobantes diferenciando el tipo:
- Si monto <= seña_expected → seña
- Si monto >= treatment_expected → treatment
- Si es cuota específica → installment con número de cuota

### FR-05: UI de Facturación en PatientDetail
La pestaña Facturación DEBE mostrar:
- Lista de turnos con monto total, estado de pago, cuotas
- Indicador visual por estado (colores diferenciados)
- Botón para registrar pago manualmente
- Historial de pagos por turno

### FR-06: Mail Post-Turno
El sistema DEBE enviar comunicación post-consulta:
- Email al paciente después de atenderse
- Plantilla con datos del turno y saldo pendiente
- Posibilidad de pagos pendientes

### FR-07: Recordatorios de Pago
El sistema DEBE enviar recordatorios automáticos:
- automation_rules con trigger payment_reminder
- Buscar turnos con payment_status pending/partial y fecha vencida
- Enviar por WhatsApp o email

### FR-08: Métricas de Cobro
El dashboard DEBE mostrar:
- Tasa de cobro: (turnos paid_complete / turnos atendidos) × 100
- Tiempo promedio: días entre turno y pago completo
- Cuotas vencidas: alertas

## 3. Scenarios

### Scenario 1: Paciente paga seña al agendar
**Given** el paciente agenda turno
**When** envía comprobante de seña
**Then** verify_payment_receipt detecta monto ≤ seña_expected
**And** payment_stage = 'seña_paid'
**And** appointment status = 'confirmed'

### Scenario 2: Paciente paga tratamiento completo post-turno
**Given** el turno se atendió y está completado
**When** el paciente envía comprobante del resto
**And** verify_payment_receipt detecta monto >= resto
**Then** payment_stage = 'paid_complete'
**And** email de confirmación de pago enviado

### Scenario 3: Paciente configura plan de cuotas
**Given** la secretaria crea turno con billing_installments = 3
**When** guarda el turno
**Then** se crean 3 registros en appointment_installments
**And** cada cuota tiene due_date calculada (ej: fecha turno + 30/60/90 días)

### Scenario 4: Paciente paga cuota específica
**Given** el paciente tiene plan de 3 cuotas
**When** envía comprobante de "cuota 2 de $5000"
**And** verify_payment_receipt detecta monto de cuota
**Then** se actualiza solo la cuota #2 como pagada
**And** payment_stage = 'partial' hasta completar todas

### Scenario 5: Recordatorio de cuota vencida
**Given** hay una cuota vencida sin pagar
**When** el job de recordatorios se ejecuta
**Then** automation_rules dispara payment_reminder
**And** paciente recibe WhatsApp/email recordatorio

### Scenario 6: Secretaria marca pago manualmente
**Given** la secretaria ve turno con payment_stage = 'partial'
**When** hace clic en "Registrar pago" y selecciona monto
**Then** payment_stage se actualiza según monto
**And** se crea registro en accounting_transactions

## 4. Architecture Decisions

### AD-01: Extender payment_status
- Agregar `payment_stage` paralelo a `payment_status`
- `payment_status` = 'paid'/'pending'/'partial' (BACKWARD COMPAT)
- `payment_stage` = 'pending'/'seña_paid'/'partial'/'paid_complete' (NEW)

### AD-02: Tabla appointment_installments
- Tabla separada para cuotas (1:N con appointments)
- Campos: installment_number, amount, due_date, paid_date, status
- Permite seguimiento granular

### AD-03: verify_payment_receipt con payment_type
- Agregar parámetro opcional `payment_type`
- Detectar tipo basado en monto vs expected
- Guardar tipo en payment_receipt_data

### AD-04: Colores UI
- pending: bg-red-500
- seña_paid: bg-yellow-500  
- partial: bg-orange-500
- paid_complete: bg-green-500 + icono $

### AD-05: Extender automation_rules
- Agregar trigger_type 'payment_reminder'
- Job similar a appointment_reminders pero para pagos

## 5. Database Schema

```sql
-- Tabla de cuotas
CREATE TABLE appointment_installments (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    appointment_id INTEGER REFERENCES appointments(id),
    installment_number INTEGER NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    due_date DATE,
    paid_date DATE,
    payment_status VARCHAR(20) DEFAULT 'pending',
    receipt_document_id INTEGER REFERENCES patient_documents(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Extensión appointments
ALTER TABLE appointments ADD COLUMN payment_type VARCHAR(20);
ALTER TABLE appointments ADD COLUMN payment_stage VARCHAR(20) DEFAULT 'pending';
```

## 6. API Endpoints

### GET /patients/{id}/billing-summary
```json
{
  "patient_id": 42,
  "total_pending": 50000,
  "turnos": [
    {
      "appointment_id": 1,
      "treatment": "Ortodoncia",
      "billing_amount": 100000,
      "payment_stage": "seña_paid",
      "seña_paid": 50000,
      "remaining": 50000,
      "installments": []
    }
  ]
}
```

### POST /appointments/{id}/register-payment
```json
{
  "amount": 25000,
  "payment_type": "installment", 
  "installment_number": 2,
  "receipt_image": "base64..."
}
```

## 7. Frontend Components

### BillingTab (PatientDetail)
- Lista de turnos con estados de pago
- Filtros por estado
- Total pendiente resumido

### InstallmentCard
- Número de cuota / total
- Fecha vencimiento
- Estado (pagada/pendiente/vencida)
- Botón registrar pago