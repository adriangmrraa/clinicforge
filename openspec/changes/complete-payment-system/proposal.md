# Proposal: Sistema Integral de Pagos por Turno (Sena + Tratamiento Completo + Cuotas)

## Intent

Extender el sistema actual de pagos para manejar el flujo completo de facturación por turno:
1. **Seña** (ya funciona) - pago inicial al agendar
2. **Pago de tratamiento completo** - después del turno, el paciente paga el resto
3. **Cuotas** - sistema de pagos parcelados configurable por turno
4. **Verificación IA** - el agente verifica comprobantes de cualquier tipo (seña/tratamiento/cuota)
5. **Métricas de cobro** - tracking de tasa de cobro, tiempo hasta pago completo

## Scope

### In Scope
- Extender `verify_payment_receipt` para soportar tipos de pago (seña/tratamiento/cuota)
- Nuevo estado de pago `paid_complete` (diferente de `paid` que es solo seña)
- UI en PatientDetail: nueva pestaña "Facturación" con historial de pagos por turno
- UI en Appointment modal: mostrar estado de cada cuota, fechas, registrar pagos
- Sistema de cuotas: guardar fecha de vencimiento por cuota, seguimiento individual
- Recordatorios automáticos de pago pendiente (extender automation_rules)
- Mail post-turno con plantilla Meta (después de atender)
- Métricas: tasa de cobro, tiempo promedio, cuotas vencidas

### Out of Scope
- Generación de facturas/recibos formales (facturación fiscal)
- Integración con sistema contable externo
- Portal de pago online (solo transferencia manual por ahora)

## Approach

### 1. Extender modelo de pagos
- Agregar campo `payment_type` a appointments: 'seña' | 'treatment' | 'installment'
- Agregar campo `payment_stage` a appointments: 'pending' | 'seña_paid' | 'partial' | 'paid_complete'
- Crear tabla `appointment_installments` para seguimiento de cuotas

### 2. Modificar verify_payment_receipt
- Agregar parámetro `payment_type` (seña/treatment/installment)
- Ajustar monto esperado según el tipo
- Guardar tipo en `payment_receipt_data.payment_type`
- Actualizar el estado correcto según tipo de pago

### 3. Nueva UI de Facturación en PatientDetail
- Pestaña "Facturación" con lista de turnos
- Cada turno muestra: monto, estado (con nuevos estados), cuotas
- Botón para registrar pago manualmente
- Indicador visual de estado (nuevo color verde con $ para paid_complete)

### 4. Flujo del Agente IA
- Después del turno completado → agent envía mail/post-turno
- Agent gestiona pagos pendientes: "¿Tiene el saldo pendiente? ¿Quiere pagar?"
- Agent verifica comprobantes y actualiza el turno correspondiente

### 5. Recordatorios de pago
- Extender automation_rules con trigger `payment_reminder`
- Job que busca pagos pendientes con fecha vencida
- Envía recordatorio por WhatsApp/email

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `models.py` | Modificado | Agregar payment_type, payment_stage, appointment_installments |
| `verify_payment_receipt` | Modificado | Soporte para tipos de pago |
| `admin_routes.py` | Modificado | Nuevo endpoint facturación, update estados |
| `PatientDetail.tsx` | Modificado | Nueva pestaña Facturación |
| `AppointmentForm.tsx` | Modificado | Mostrar estado de cuotas, registrar pagos |
| `email_service.py` | Modificado | Mail post-turno con plantilla |
| `automation_rules` | Modificado | Nuevo trigger payment_reminder |
| `jobs/` | Modificado | Job recordatorios de pago |

## UI Design - Estados de Pago

| Estado | Color | Icono | Significado |
|--------|-------|-------|--------------|
| `pending` | 🔴 Rojo | - | Sin pagar |
| `seña_paid` | 🟡 Amarillo | - | Seña pagada, resto pendiente |
| `partial` | 🟠 Naranja | - | Pago parcial (cuotas) |
| `paid_complete` | 🟢 Verde | 💰 | Tratamiento completo pagado |

## Data Model

```sql
-- Tabla de cuotas por turno
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
ALTER TABLE appointments ADD COLUMN payment_type VARCHAR(20); -- 'seña'|'treatment'|'installment'
ALTER TABLE appointments ADD COLUMN payment_stage VARCHAR(20); -- 'pending'|'seña_paid'|'partial'|'paid_complete'
```

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Confusión seña vs treatment | Medium | clarificar en UI con badges diferenciados |
| Cuotas vencidas sin notificación | Medium | crear job de recordatorios |
| Agent no detecta tipo de pago | Low | clasificar según monto y contexto |

## Rollback Plan
- Revertir estados agregados a appointment
- Eliminar tabla appointment_installments
- Revertir cambios en verify_payment_receipt

## Dependencies
- whatsapp-multi-attachment-analysis (ya implementado) - usa Vision para verificar
- payment_cooldown (ya implementado) - evita re-verificación

## Success Criteria
- [ ] Paciente puede pagar seña → se marca como seña_paid
- [ ] Después del turno, paciente puede pagar tratamiento completo → paid_complete
- [ ] Secretarias pueden ver historial de pagos en Pestaña Facturación
- [ ] Sistema de cuotas funciona (crear plan, seguir cuotas, registrar pagos)
- [ ] Agent gestiona pagos pendientes post-turno
- [ ] Métricas de cobro visibles en dashboard
- [ ] Recordatorios de pago funcionando