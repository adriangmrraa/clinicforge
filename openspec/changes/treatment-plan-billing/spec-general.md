# Spec General: Treatment Plan Billing System

**Change**: treatment-plan-billing
**Artifact**: spec-general
**Status**: Draft
**Date**: 2026-04-03

---

## 1. Resumen Ejecutivo

El sistema de **Treatment Plan Billing** introduce un modelo de presupuestos y facturación unificado a nivel plan de tratamiento por paciente. Este cambio reemplaza el modelo actual de billing aislado por turno (`appointments.billing_amount`), permitiendo:

- Crear presupuestos globales que agrupan múltiples tratamientos simultáneos
- Aprobar precios finales (los base_price son estimativos, la Dra. siempre ajusta)
- Registrar pagos parciales en efectivo, transferencia o tarjeta
- Visualizar progreso financiero y de sesiones desde una pestaña dedicada
- Alimentar las métricas existentes (dashboard, liquidación, ROI)

El modelo actual (appointment-level billing) no soporta presupuestos globales ni pagos manuales. Este cambio introduce el concepto de **Plan de Tratamiento** como unidad de facturación, vinculado a pacientes, profesionales y turnos.

---

## 2. Componentes que se Implementan

### 2.1 Base de Datos

Tres nuevas tablas + una columna en appointments:

| Tabla | Propósito |
|-------|-----------|
| `treatment_plans` | Cabecera del presupuesto: nombre, estado, totales, aprobador |
| `treatment_plan_items` | Tratamientos individuales dentro del plan |
| `treatment_plan_payments` | Pagos registrados contra el plan |
| `appointments.plan_item_id` | FK opcional para vincular turnos a ítems del plan |

### 2.2 Backend (API REST)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/admin/patients/{patient_id}/treatment-plans` | GET | Lista planes de un paciente |
| `/admin/patients/{patient_id}/treatment-plans` | POST | Crea nuevo plan |
| `/admin/treatment-plans/{plan_id}` | GET | Detalle completo del plan |
| `/admin/treatment-plans/{plan_id}` | PUT | Actualiza plan (incluye aprobación) |
| `/admin/treatment-plans/{plan_id}` | DELETE | Cancela plan (soft-delete) |
| `/admin/treatment-plans/{plan_id}/items` | POST | Agrega ítem al plan |
| `/admin/treatment-plan-items/{item_id}` | PUT | Actualiza ítem |
| `/admin/treatment-plan-items/{item_id}` | DELETE | Elimina ítem |
| `/admin/treatment-plans/{plan_id}/payments` | POST | Registra pago |
| `/admin/treatment-plans/{plan_id}/payments` | GET | Historial de pagos |
| `/admin/treatment-plan-payments/{payment_id}` | DELETE | Elimina pago |
| `/admin/appointments/{id}/link-plan-item` | PUT | Vincula turno a ítem |

### 2.3 Frontend (Tab 6)

Componente `BillingTab` integrado en `PatientDetail.tsx`:

- **PlanSelectorBar**: Selector de planes (dropdown si hay 2+)
- **PlanHeaderCard**: Nombre, estado, profesional, KPIs financieros
- **FinancialProgressBar**: Barra de progreso visual
- **ItemsSection**: Tabla de tratamientos con edición inline
- **PaymentsSection**: Tabla de pagos con acciones
- **Modals**: CreatePlan, AddItem, RegisterPayment, ApprovePlan

### 2.4 Métricas e Integración

- Cada `treatment_plan_payment` sincroniza con `accounting_transactions`
- Dashboard `pending_payments` incluye balance de planes
- Liquidación profesional agrupa por plan
- Nova tools para gestión por voz

### 2.5 AI Tools (Nova + WhatsApp)

Herramientas para el agente IA:

- `create_treatment_plan`: Crear plan desde conversación
- `list_treatment_plans`: Listar planes del paciente
- `approve_treatment_plan`: Aprobar plan con precio final
- `register_treatment_payment`: Registrar pago
- `get_treatment_plan_summary`: Resumen financiero del paciente
- `actualizar_email_paciente`: Guardar email del paciente

### 2.6 Email Notifications

Sistema de confirmación de pagos por email:

- **Trigger**: Se envía cuando se concreta un pago (verificado por IA o registrado manualmente)
- **Flujo**:
  - Si el paciente tiene email → confirmación automática
  - Si NO tiene email → el agente WhatsApp lo pide amablemente
- **Contenido**: monto, método, saldo actualizado del plan, datos de la clínica

### 2.7 Welcome Emails

Sistema de emails de bienvenida a nuevos usuarios:

- **Trigger**: Cuando se crea un nuevo profesional, secretaria o CEO
- **Tipos**:
  - Profesional: credenciales, información de agenda
  - Secretaria: credenciales, gestión de turnos/pacientes
  - CEO/Admin: credenciales, dashboard y métricas
- **Integración**: Se activa en auth_routes.py y admin_routes.py

---

## 3. Flujos Principales

### 3.1 Flujo: Crear Plan de Tratamiento

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Recepcionista abre PatientDetail → Tab "Presupuesto"          │
│  2. Sin planes existentes → clic en "Crear presupuesto"            │
│  3. CreatePlanModal: nombre, profesional (opcional), notas         │
│  4. POST /admin/treatment-plans → status="draft"                  │
│  5. Selector auto-selecciona el nuevo plan                        │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Flujo: Agregar Tratamientos al Plan

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. En BillingTab → sección "Tratamientos" → "Agregar"           │
│  2. AddItemModal: selecciona treatment_type (carga base_price)     │
│  3. Opcional: descripción personalizada ("Implante pieza 36")     │
│  4. POST /admin/treatment-plan-items                              │
│  5. estimated_total del plan se recalcula automáticamente        │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.3 Flujo: Aprobar Plan

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Plan en estado "draft" → clic "Aprobar presupuesto"           │
│  2. ApprovePlanModal: muestra estimated_total prellenado           │
│  3. Dra. ajusta approved_total (descuento global)                 │
│  4. PATCH /admin/treatment-plans/{id} con status="approved"        │
│  5. Plan queda activo, ahora se pueden registrar pagos             │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.4 Flujo: Registrar Pagos

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Plan aprobado → clic "Registrar pago"                         │
│  2. RegisterPaymentModal: monto, método (efectivo/transferencia)  │
│  3. POST /admin/treatment-plan-payments                            │
│  4. Sync automático con accounting_transactions                   │
│  5. Si primer pago: plan avanza a "in_progress"                    │
│  6. KPIs recalculan: pagado, pendiente, barra de progreso          │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.5 Flujo: Vincular Turnos

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. En agenda, al crear/editar turno → opción "Vincular a plan"   │
│  2. PUT /admin/appointments/{id}/link-plan-item                   │
│  3. Turno se vincula a ítem del plan                               │
│  4. ItemsSection muestra count de turnos vinculados               │
│  5. El billing del turno NO usa billing_amount (usa payments)     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.6 Flujo: Ver Métricas

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Dashboard muestra:                                             │
│     - Ingresos del período (plans + appointments legacy)           │
│     - Pendientes por cobrar (suma de approved_total - payments)   │
│  2. Liquidación profesional: agrupa por plan                      │
│  3. Nova: "Resumen financiero del paciente" → suma de planes     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.7 Flujo: Confirmación de Pago por Email

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Se registra un pago (por IA o manualmente)                     │
│  2. Sistema verifica si patient.email existe                       │
│  3. SI existe → email de confirmación enviado automáticamente      │
│  4. SI NO existe → agente WhatsApp pide: "¿Me pasás tu email?"    │
│  5. Paciente responde con email                                    │
│  6. Nova o agente actualiza email del paciente                    │
│  7. Se envía la confirmación                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.8 Flujo: Bienvenida a Nuevos Usuarios

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Admin crea nuevo usuario (profesional/secretaria/CEO)          │
│  2. POST /auth/register o POST /admin/professionals               │
│  3. Sistema detecta rol del nuevo usuario                          │
│  4. Se envía email de bienvenida con credenciales                 │
│  5. Email incluye: datos de clínica, login, funcionalidades       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Diagrama de Arquitectura Conceptual

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                    FRONTEND (React)                                   │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │  PatientDetail.tsx                                                             │  │
│  │  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌───────┐ ┌──────┐ ┌─────────────────┐  │  │
│  │  │ Summary │ │ History  │ │ Docs  │ │ Anam. │ │ Rec. │ │ BillingTab (NEW)│  │  │
│  │  └─────────┘ └──────────┘ └────────┘ └───────┘ └──────┘ └─────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬─────────────────────────────────────────────────────┘
                                 │ HTTP + Socket.IO
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATOR (FastAPI)                                     │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │  admin_routes.py                                                              │  │
│  │  - Treatment Plans CRUD    (EP-01 a EP-05)                                     │  │
│  │  - Plan Items CRUD        (EP-06 a EP-08)                                     │  │
│  │  - Payments CRUD          (EP-09 a EP-11)                                      │  │
│  │  - Appointment Linking    (EP-12)                                             │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                                  │
│                                    ▼                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │  Socket.IO Events                                                             │  │
│  │  - TREATMENT_PLAN_CREATED / UPDATED                                         │  │
│  │  - BILLING_UPDATED                                                           │  │
│  │  - APPOINTMENT_UPDATED                                                       │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬──────────────────────────────────────────────────────┘
                                 │ asyncpg
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              POSTGRESQL                                            │
│                                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │  treatment_plans                 treatment_plan_items                       │  │
│  │  ┌─────────────────────────────┐  ┌────────────────────────────────────┐   │  │
│  │  │ id (UUID)                   │  │ id (UUID)                          │   │  │
│  │  │ tenant_id (INT)             │◄──│ plan_id (UUID) FK CASCADE          │   │  │
│  │  │ patient_id (INT) FK         │  │ tenant_id (INT)                    │   │  │
│  │  │ name (VARCHAR)              │  │ treatment_type_code (VARCHAR)      │   │  │
│  │  │ status (VARCHAR)           │  │ custom_description (TEXT)          │   │  │
│  │  │ estimated_total (DECIMAL)  │  │ estimated_price (DECIMAL)           │   │  │
│  │  │ approved_total (DECIMAL)   │  │ approved_price (DECIMAL)           │   │  │
│  │  │ approved_by (INT)          │  │ status (VARCHAR)                   │   │  │
│  │  │ approved_at (TIMESTAMPTZ)  │  │ sort_order (INT)                   │   │  │
│  │  └─────────────────────────────┘  └────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │  treatment_plan_payments         appointments (new column)                 │  │
│  │  ┌─────────────────────────────┐  ┌────────────────────────────────────┐   │  │
│  │  │ id (UUID)                   │  │ ...existing columns...            │   │  │
│  │  │ plan_id (UUID) FK CASCADE   │  │ plan_item_id (UUID) FK SET NULL   │   │  │
│  │  │ tenant_id (INT)             │◄─┤     REFERENCES treatment_plan_   │   │  │
│  │  │ amount (DECIMAL)             │  │       items(id) ON DELETE SET    │   │  │
│  │  │ payment_method (VARCHAR)    │  │       NULL                        │   │  │
│  │  │ payment_date (TIMESTAMPTZ)  │  └────────────────────────────────────┘   │  │
│  │  │ recorded_by (INT)            │                                            │  │
│  │  │ appointment_id (UUID)       │                                            │  │
│  │  │ accounting_transaction_id   │                                            │  │
│  │  │ receipt_data (JSONB)         │                                            │  │
│  │  └─────────────────────────────┘                                            │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │  accounting_transactions (sync)                                               │  │
│  │  - reference_id ← treatment_plan_payment.id                                  │  │
│  │  - reference_type ← 'treatment_plan_payment'                                 │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                    NOVA (AI Agent)                                    │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │  Tools disponibles:                                                          │  │
│  │  - create_treatment_plan       (crear plan)                                  │  │
│  │  - list_treatment_plans        (listar planes del paciente)                 │  │
│  │  - approve_treatment_plan      (aprobar plan)                                │  │
│  │  - register_treatment_payment (registrar pago)                              │  │
│  │  - get_treatment_plan_summary  (resumen financiero)                         │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Modelo de Datos: Relaciones

```
Patient (1) ──► (N) TreatmentPlan
    │
    └── (N) Appointment ──► (0..1) TreatmentPlanItem ◄── (N) TreatmentPlanPayment
                                        ▲
                                        │
                                  appointments
                                  .plan_item_id
```

### Reglas de negocio

1. **Turnos con plan**: Si `appointments.plan_item_id IS NOT NULL`, el ingreso se contabiliza vía `treatment_plan_payments`, NO vía `appointments.billing_amount`.

2. **Turnos sin plan**: Si `plan_item_id IS NULL`, el billing funciona con el modelo legacy (billing_amount).

3. **Estados del plan**:
   - `draft` → editable, sin pagos
   - `approved` → precio bloqueado, acepta pagos
   - `in_progress` → tratamiento activo
   - `completed` → tratamiento terminado
   - `cancelled` → cancelado (soft-delete)

4. **Dual billing**: Los dos modelos coexisten. La capa de métricas debe hacer UNION o SUM condicional para evitar doble-conteo.

---

## 6. Integración con Sistema Existente

### 6.1 Métricas (Dashboard + Liquidación)

```sql
-- Ingresos legacy (turnos sin plan)
SELECT SUM(billing_amount)
FROM appointments
WHERE tenant_id = $1 AND payment_status IN ('partial', 'paid')
  AND plan_item_id IS NULL;

-- Ingresos de planes
SELECT SUM(amount)
FROM treatment_plan_payments
WHERE tenant_id = $1 AND payment_date BETWEEN $2 AND $3;

-- Pendientes por cobrar
SELECT tp.approved_total - COALESCE(SUM(tpp.amount), 0)
FROM treatment_plans tp
LEFT JOIN treatment_plan_payments tpp ON tpp.plan_id = tp.id
WHERE tp.tenant_id = $1 AND tp.status IN ('approved', 'in_progress')
GROUP BY tp.id;
```

### 6.2 Socket.IO

| Evento | Payload | Escucha |
|--------|---------|----------|
| `TREATMENT_PLAN_CREATED` | `{plan_id, patient_id, tenant_id, name, status}` | BillingTab |
| `TREATMENT_PLAN_UPDATED` | `{plan_id, tenant_id, status?, estimated_total?}` | BillingTab |
| `BILLING_UPDATED` | `{plan_id, tenant_id, payment_id?, amount?}` | BillingTab |
| `APPOINTMENT_UPDATED` | `{id, plan_item_id, tenant_id}` | BillingTab |

### 6.3 i18n

El componente usa el namespace `billing` para todas las traducciones:

```json
{
  "billing.treatments": "Tratamientos",
  "billing.payments": "Pagos registrados",
  "billing.approve_plan": "Aprobar presupuesto",
  ...
}
```

---

## 7. Referencias a Specs Detalladas

| Spec | Artefacto | Descripción |
|------|-----------|-------------|
| [spec-database.md](spec-database.md) | spec-database | Migración Alembic: tablas, índices, constraints, downgrade |
| [spec-backend.md](spec-backend.md) | spec-backend | Endpoints API REST, validaciones, reglas multi-tenant, Socket.IO |
| [spec-frontend.md](spec-frontend.md) | spec-frontend | Componente BillingTab, modales, integración con PatientDetail |
| [spec-metrics.md](spec-metrics.md) | spec-metrics | Integración con dashboard, accounting_transactions, KPIs |
| [spec-ai-tools.md](spec-ai-tools.md) | spec-ai-tools | Nova tools para gestión por voz |
| [spec-email-notifications.md](spec-email-notifications.md) | spec-email | Emails de confirmación de pagos, solicitud de email |
| [spec-welcome-emails.md](spec-welcome-emails.md) | spec-welcome | Emails de bienvenida a nuevos usuarios |
| [proposal.md](proposal.md) | proposal | Proposal original: intent, problem statement, scope, risks |

---

## 8. Precedencia y Dependencias

### 8.1 Dependencias Externas

- **Migration 017** (`odontogram_v3_format`) debe estar aplicada antes de ejecutar la migration 018
- **treatment_types** debe tener `base_price` populado para que los ítems de plan tomen valores por defecto
- **accounting_transactions** tabla existente (usada para sync de pagos)

### 8.2 Orden de Implementación Recomendado

1. **spec-database**: Ejecutar migración Alembic primero
2. **spec-backend**: Implementar endpoints CRUD
3. **spec-frontend**: Crear BillingTab y mods
4. **spec-metrics**: Ajustar queries de dashboard
5. **spec-ai-tools**: Agregar Nova tools

---

## 9. Success Criteria

- [ ] La Dra. puede crear un presupuesto con múltiples tratamientos
- [ ] La Dra. puede aprobar el presupuesto con precio final personalizado
- [ ] La Dra. puede registrar pagos en efectivo desde la UI
- [ ] El dashboard refleja ingresos/pendientes correctamente (sin doble-conteo)
- [ ] La liquidación profesional muestra ingresos agrupados por plan
- [ ] Los turnos vinculados a ítems muestran progreso de tratamiento
- [ ] Nova puede gestionar planes por voz

---

## 10. Out of Scope

- Generación de PDF de presupuesto (futuro)
- Integración con sistemas contables externos
- Factura electrónica AFIP
- Seguros/obras sociales en el plan (existe en appointments, se mantiene ahí)
- Asignación de pagos por ítem específico
- Programación de cuotas (UI)

---

*Spec generado: 2026-04-03 — treatment-plan-billing/spec-general*
