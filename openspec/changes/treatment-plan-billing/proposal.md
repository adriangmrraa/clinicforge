# Proposal: Treatment Plan Billing System

**Change**: treatment-plan-billing
**Status**: Draft
**Date**: 2026-04-03

---

## Intent

Implementar un sistema de presupuesto y facturación a nivel **plan de tratamiento por paciente**, reemplazando el modelo actual de billing aislado por turno. La Dra. necesita:
- Crear un presupuesto global por paciente que agrupe 1-N tratamientos simultáneos
- Aprobar el precio final (los base_price son estimativos, ella SIEMPRE ajusta)
- Registrar pagos parciales en efectivo, transferencia o tarjeta
- Ver progreso financiero y de sesiones desde una pestaña dedicada
- Que todo alimente las métricas existentes (dashboard, liquidación, ROI)

## Problem Statement

### Modelo actual (appointment-level billing)
- `appointments.billing_amount` / `payment_status` — cada turno tiene su propio billing
- No existe concepto de "plan de tratamiento" como unidad de facturación
- No hay forma de registrar pagos en efectivo desde la UI
- 3 fuentes de verdad desconectadas: `appointments.billing_amount`, `accounting_transactions`, `clinical_records.treatments[].cost`
- `requires_multiple_sessions` y `session_gap_days` existen en `treatment_types` pero nadie los usa
- La Dra. gestiona presupuestos en papel/Excel — imposible de medir

### Impacto
- No se puede saber cuánto debe un paciente en total (solo por turno)
- No se puede trackear progreso de tratamientos multi-sesión
- Pagos en efectivo no quedan registrados
- Métricas de ingresos/pendientes son inexactas

## Scope

### In Scope
1. **Database**: 3 nuevas tablas (`treatment_plans`, `treatment_plan_items`, `treatment_plan_payments`) + `plan_item_id` FK en appointments
2. **Backend**: CRUD endpoints para plans, items, payments
3. **Frontend**: Tab 6 "Presupuesto y Facturación" en PatientDetail
4. **Metrics**: Integrar plan payments con `accounting_transactions` y dashboard KPIs
5. **AI Tools**: Nova tools para gestionar planes y pagos por voz
6. **Migración**: Alembic migration con upgrade + downgrade

### Out of Scope
- Generación de PDF de presupuesto (futuro)
- Integración con sistemas contables externos
- Factura electrónica AFIP
- Seguros/obras sociales en el plan (existe en appointments, se mantiene ahí)

## Approach

### Nuevo modelo de datos

```
Patient (1) ──→ (N) TreatmentPlan
TreatmentPlan (1) ──→ (N) TreatmentPlanItem
TreatmentPlanItem (1) ──→ (N) Appointment (via plan_item_id)
TreatmentPlan (1) ──→ (N) TreatmentPlanPayment
TreatmentPlanPayment (N) ──→ (1) AccountingTransaction (sync)
```

### Tablas

**treatment_plans**
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| tenant_id | INT FK | Multi-tenant |
| patient_id | INT FK | |
| professional_id | INT FK NULL | Profesional principal (puede ser null) |
| name | VARCHAR(200) | "Rehabilitación oral completa" |
| status | VARCHAR(20) | draft / approved / in_progress / completed / cancelled |
| estimated_total | DECIMAL(12,2) | Suma de estimated_price de items |
| approved_total | DECIMAL(12,2) | Precio final aprobado por Dra. |
| approved_by | INT FK NULL | user_id |
| approved_at | TIMESTAMPTZ NULL | |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

**treatment_plan_items**
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| plan_id | UUID FK | |
| tenant_id | INT FK | |
| treatment_type_code | VARCHAR(50) | FK conceptual a treatment_types.code |
| custom_description | TEXT | "Implante pieza 36" — libre |
| estimated_price | DECIMAL(12,2) | Desde treatment_types.base_price |
| approved_price | DECIMAL(12,2) NULL | Precio final (Dra. modifica) |
| status | VARCHAR(20) | pending / in_progress / completed / cancelled |
| sort_order | INT DEFAULT 0 | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

**treatment_plan_payments**
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| plan_id | UUID FK | |
| tenant_id | INT FK | |
| amount | DECIMAL(12,2) | |
| payment_method | VARCHAR(20) | cash / transfer / card / insurance |
| payment_date | TIMESTAMPTZ | |
| recorded_by | INT FK | user_id que registra |
| appointment_id | UUID FK NULL | Turno asociado (opcional) |
| receipt_data | JSONB NULL | Datos de comprobante |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | |

**Columna nueva en appointments:**
```sql
plan_item_id UUID NULL REFERENCES treatment_plan_items(id)
```

### Frontend — Tab 6

Secciones:
1. **Plan selector** — Si tiene múltiples planes, dropdown. Botón "Nuevo plan"
2. **Header** — Nombre, estado (badge), profesional, fecha aprobación
3. **Items table** — Tratamiento | Precio est. | Precio aprobado | Turnos vinculados | Estado
4. **Payments table** — Fecha | Monto | Método | Registrado por | Notas
5. **Summary bar** — Total aprobado | Pagado (%) | Pendiente | Barra de progreso
6. **Actions** — "Aprobar plan", "Registrar pago", "Agregar tratamiento"

### Metrics Integration
- Cada `treatment_plan_payment` crea un `accounting_transaction` (sync)
- Dashboard `pending_payments` incluye balance de planes
- Liquidación profesional agrupa por plan
- Nova `resumen_financiero` incluye planes

## Risks

| Risk | Mitigation |
|------|------------|
| Doble-conteo: billing de appointment + plan payment | Plan payments reemplazan appointment billing para turnos con plan_item_id |
| Migración rompe métricas existentes | Backward compatible: turnos sin plan siguen usando billing_amount |
| Complejidad UI para la Dra. | Tab simple, flujo lineal: crear plan → agregar items → aprobar → registrar pagos |

## Dependencies

- Migration 016 (clinical_record_summaries) debe estar aplicada
- treatment_types table con base_price populado
- accounting_transactions table existente (poco usada, pero la estructura sirve)

## Success Criteria

- La Dra. puede crear un presupuesto, aprobar precio final, registrar pagos en efectivo
- El dashboard refleja ingresos/pendientes correctamente
- La liquidación profesional muestra ingresos por plan
- Turnos vinculados a items muestran progreso del tratamiento
