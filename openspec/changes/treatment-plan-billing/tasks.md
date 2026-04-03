# Breakdown de Tareas: Treatment Plan Billing System

**Change**: treatment-plan-billing
**Status**: Draft
**Date**: 2026-04-03

---

## Resumen Ejecutivo

Este documento desglosa el cambio `treatment-plan-billing` en tareas ejecutables organizadas por módulo. Cada tarea especifica: descripción, archivos afectados, dependencias y orden de implementación.

**Total de tareas identificadas**: 50

---

## Orden de Implementación Recomendado

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                          FASE 1: DATABASE (2 tareas)                          │
│  1.1 → Migración Alembic 018                                                    │
│  1.2 → Validación de estructura                                                │
├────────────────────────────────────────────────────────────────────────────────┤
│                          FASE 2: BACKEND API (13 tareas)                      │
│  2.1 → Modelos Pydantic                                                         │
│  2.2 → Endpoints CRUD planes (EP-01 a EP-05)                                   │
│  2.3 → Endpoints CRUD items (EP-06 a EP-08)                                    │
│  2.4 → Endpoints payments (EP-09 a EP-11)                                       │
│  2.5 → Endpoint linking turnos (EP-12)                                         │
│  2.6 → Helpers y utilidades                                                    │
├────────────────────────────────────────────────────────────────────────────────┤
│                          FASE 3: FRONTEND (10 tareas)                          │
│  3.1 → Componente BillingTab                                                   │
│  3.2 → Integración PatientDetail                                              │
│  3.3 → i18n keys                                                               │
│  3.4 → Testing unitario                                                         │
├────────────────────────────────────────────────────────────────────────────────┤
│                          FASE 4: METRICS (5 tareas)                            │
│  4.1 → Dashboard KPIs                                                           │
│  4.2 → Liquidación profesional                                                 │
│  4.3 → ROI dashboard                                                           │
├────────────────────────────────────────────────────────────────────────────────┤
│                          FASE 5: AI TOOLS (8 tareas)                           │
│  5.1 → Nova tools nuevas                                                       │
│  5.2 → Nova tools modificadas                                                  │
│  5.3 → WhatsApp agent                                                           │
├────────────────────────────────────────────────────────────────────────────────┤
│                          FASE 6: EMAIL & NOTIFICATIONS (7 tareas)             │
│  6.1 → Email service                                                           │
│  6.2 → Integración endpoints (payment confirmation)                            │
│  6.3 → Integración email en verify_payment_receipt                             │
│  6.4 → Nova tool + Endpoint actualizar_email_paciente                         │
│  6.5 → [x] Welcome email: profesional                                          │
│  6.6 → Welcome email: secretary                                               │
│  6.7 → Welcome email: CEO                                                      │
├────────────────────────────────────────────────────────────────────────────────┤
│                          FASE 7: VERIFICACIÓN (5 tareas)                       │
│  7.1 → Tests unitarios                                                           │
│  7.2 → Tests de integración                                                    │
│  7.3 → E2E                                                                     │
│  7.4 → Documentación                                                           │
│  7.5 → Backward compatibility                                                   │
└────────────────────────────────────────────────────────────────────────────────┘
```
┌────────────────────────────────────────────────────────────────────────────────┐
│                          FASE 1: DATABASE (2 tareas)                          │
│  1.1 → Migración Alembic 018                                                    │
│  1.2 → Validación de estructura                                                │
├────────────────────────────────────────────────────────────────────────────────┤
│                          FASE 2: BACKEND API (13 tareas)                      │
│  2.1 → Modelos Pydantic                                                         │
│  2.2 → Endpoints CRUD planes (EP-01 a EP-05)                                   │
│  2.3 → Endpoints CRUD items (EP-06 a EP-08)                                    │
│  2.4 → Endpoints payments (EP-09 a EP-11)                                       │
│  2.5 → Endpoint linking turnos (EP-12)                                         │
│  2.6 → Helpers y utilidades                                                    │
├────────────────────────────────────────────────────────────────────────────────┤
│                          FASE 3: FRONTEND (10 tareas)                          │
│  3.1 → Componente BillingTab                                                   │
│  3.2 → Integración PatientDetail                                              │
│  3.3 → i18n keys                                                               │
│  3.4 → Testing unitario                                                         │
├────────────────────────────────────────────────────────────────────────────────┤
│                          FASE 4: METRICS (5 tareas)                            │
│  4.1 → Dashboard KPIs                                                           │
│  4.2 → Liquidación profesional                                                 │
│  4.3 → ROI dashboard                                                           │
├────────────────────────────────────────────────────────────────────────────────┤
│                          FASE 5: AI TOOLS (8 tareas)                           │
│  5.1 → Nova tools nuevas                                                       │
│  5.2 → Nova tools modificadas                                                  │
│  5.3 → WhatsApp agent                                                           │
├────────────────────────────────────────────────────────────────────────────────┤
│                          FASE 6: EMAIL (4 tareas)                              │
│  6.1 → Email service                                                            │
│  6.2 → Integración endpoints                                                   │
│  6.3 → Nova tool email                                                          │
├────────────────────────────────────────────────────────────────────────────────┤
│                          FASE 7: VERIFICACIÓN (5 tareas)                        │
│  7.1 → Tests unitarios                                                           │
│  7.2 → Tests de integración                                                    │
│  7.3 → E2E                                                                     │
│  7.4 → Documentación                                                           │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## FASE 1: DATABASE

### Tarea 1.1 — Migración Alembic 018

**Descripción**: Crear archivo de migración Alembic que crea las tres tablas nuevas y agrega la columna `appointments.plan_item_id`.

**Archivos afectados**:
- `orchestrator_service/alembic/versions/018_treatment_plan_billing.py` (CREAR)

**Dependencias**:
- Migration 017 (`odontogram_v3_format`) debe estar aplicada
- Tablas existentes: `tenants`, `patients`, `professionals`, `users`, `treatment_types`, `accounting_transactions`

**Contenido de la migración**:
- CREATE TABLE `treatment_plans`
- CREATE TABLE `treatment_plan_items`
- CREATE TABLE `treatment_plan_payments`
- ALTER TABLE `appointments ADD COLUMN plan_item_id UUID NULL`
- CREATE INDEX en cada tabla con filtro `tenant_id`
- CREATE INDEX partial en `appointments.plan_item_id WHERE IS NOT NULL`
- CHECK constraints para status, precios, montos
- Función `downgrade()` para rollback

**Criterios de aceptación**:
- [x] `alembic upgrade head` ejecuta sin errores
- [x] `alembic downgrade 017` revierte correctamente
- [x] Las 3 tablas existen con todos los campos especificados
- [x] Todos los índices creados
- [x] CHECK constraints activos

---

### Tarea 1.2 — Validación de estructura de base de datos

**Descripción**: Verificar que la migración se aplicó correctamente consultando el catálogo de PostgreSQL.

**Archivos afectados**:
- Ninguno (script de validación)

**Dependencias**:
- Tarea 1.1 completada

**Validaciones requeridas**:
- [ ] `treatment_plans` tiene columnas: `id` (UUID), `tenant_id`, `patient_id`, `professional_id`, `name`, `status`, `estimated_total`, `approved_total`, `approved_by`, `approved_at`, `notes`, `created_at`, `updated_at`
- [ ] `treatment_plan_items` tiene columnas: `id` (UUID), `plan_id`, `tenant_id`, `treatment_type_code`, `custom_description`, `estimated_price`, `approved_price`, `status`, `sort_order`, `created_at`, `updated_at`
- [ ] `treatment_plan_payments` tiene columnas: `id` (UUID), `plan_id`, `tenant_id`, `amount`, `payment_method`, `payment_date`, `recorded_by`, `appointment_id`, `receipt_data`, `notes`, `created_at`
- [ ] `appointments` tiene columna `plan_item_id` (UUID, nullable)
- [ ] FK constraints: `treatment_plan_items.plan_id → treatment_plans.id` (CASCADE), `treatment_plan_payments.plan_id → treatment_plans.id` (CASCADE), `appointments.plan_item_id → treatment_plan_items.id` (SET NULL)
- [ ] CHECK constraints activos en las 3 tablas

---

## FASE 2: BACKEND API

### Tarea 2.1 — Modelos Pydantic

**Descripción**: Crear los modelos Pydantic para validación de request/response en los endpoints.

**Archivos afectados**:
- `orchestrator_service/schemas/treatment_plan.py` (CREAR)
- `orchestrator_service/schemas/__init__.py` (CREAR)

**Dependencias**:
- Tarea 1.1 completada

**Modelos creados**:
```python
# Enums
class PlanStatus(str, Enum): draft, approved, in_progress, completed, cancelled
class ItemStatus(str, Enum): pending, completed, cancelled
class PaymentMethod(str, Enum): cash, transfer, card, insurance

# Request models
class TreatmentPlanItemCreate(BaseModel)
class CreateTreatmentPlanBody(BaseModel)
class UpdateTreatmentPlanBody(BaseModel)
class AddPlanItemBody(BaseModel)
class UpdatePlanItemBody(BaseModel)
class RegisterPaymentBody(BaseModel)
class LinkPlanItemBody(BaseModel)

# Response models
class TreatmentPlanResponse(BaseModel)
class TreatmentPlanDetailResponse(BaseModel)
class TreatmentPlanItemResponse(BaseModel)
class TreatmentPlanPaymentResponse(BaseModel)
# Helpers
class PlanSummary(BaseModel)
class PaymentWithReceiptResponse(BaseModel)
```

**Criterios de aceptación**:
- [x] Todos los modelos tienen validación de tipos
- [x] Campos opcionales correctamente marcados
- [x] Enums para status: `draft`, `approved`, `in_progress`, `completed`, `cancelled`
- [x] Enums para payment_method: `cash`, `transfer`, `card`, `insurance`

---

### Tarea 2.2 — Endpoints CRUD Treatment Plans (EP-01 a EP-05)

**Descripción**: Implementar los 5 endpoints para gestión de planes.

**Archivos afectados**:
- `orchestrator_service/admin_routes.py` (MODIFICAR)

**Dependencias**:
- Tarea 2.1 completada

**Endpoints a implementar**:

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/admin/patients/{patient_id}/treatment-plans` | GET | Lista planes de paciente (EP-01) |
| `/admin/patients/{patient_id}/treatment-plans` | POST | Crea nuevo plan (EP-02) |
| `/admin/treatment-plans/{plan_id}` | GET | Detalle completo del plan (EP-03) |
| `/admin/treatment-plans/{plan_id}` | PUT | Actualiza plan / aprobación (EP-04) |
| `/admin/treatment-plans/{plan_id}` | DELETE | Soft-cancel plan (EP-05) |

**Lógica de negocio**:
- EP-01: Query con JOIN a professionals, aggregation de items y payments
- EP-02: Crear plan + opcionalmente items iniciales, validar patient_id existe
- EP-03: Detalle con items (incluyendo turnos vinculados) y payments
- EP-04: Update dinámico de campos, caso especial `status='approved'` con approved_by/at
- EP-05: Soft-cancel (status='cancelled'), no permite en completed

**Criterios de aceptación**:
- [x] EP-01 retorna lista con campos agregados (items_count, paid_total, pending_total)
- [x] EP-02 retorna plan creado con items (HTTP 201)
- [x] EP-03 retorna detalle completo con arrays de items y payments
- [x] EP-04 valida transiciones de estado (no permite completed → draft)
- [x] EP-05 no permite cancelar planes completados
- [x] Todos incluyen tenant_id en queries
- [x] Todos emit eventos Socket.IO

---

### Tarea 2.3 — Endpoints CRUD Plan Items (EP-06 a EP-08)

**Descripción**: Implementar los 3 endpoints para gestión de ítems dentro de un plan.

**Archivos afectados**:
- `orchestrator_service/admin_routes.py` (MODIFICAR)

**Dependencias**:
- Tarea 2.2 completada

**Endpoints a implementar**:

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/admin/treatment-plans/{plan_id}/items` | POST | Agrega ítem (EP-06) |
| `/admin/treatment-plan-items/{item_id}` | PUT | Actualiza ítem (EP-07) |
| `/admin/treatment-plan-items/{item_id}` | DELETE | Elimina ítem (EP-08) |

**Lógica de negocio**:
- EP-06: Agregar ítem, calcular sort_order, recalcular estimated_total del plan
- EP-07: Update dinámico, recalcular estimated_total si cambia precio
- EP-08: Hard-delete ítem, desvincular turnos (SET NULL), recalcular estimated_total

**Criterios de aceptación**:
- [x] EP-06 valida plan no está cancelled/completed
- [x] EP-06 carga base_price de treatment_types si no se provee estimated_price
- [x] EP-07 valida transiciones de estado de ítem
- [x] EP-08 no permite eliminar ítems completados (solo cancelar)
- [x] estimated_total se recalcula automáticamente

---

### Tarea 2.4 — Endpoints Payments (EP-09 a EP-11)

**Descripción**: Implementar los 3 endpoints para gestión de pagos.

**Archivos afectados**:
- `orchestrator_service/admin_routes.py` (MODIFICAR)

**Dependencias**:
- Tarea 2.3 completada

**Endpoints a implementar**:

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/admin/treatment-plans/{plan_id}/payments` | POST | Registra pago (EP-09) |
| `/admin/treatment-plans/{plan_id}/payments` | GET | Historial de pagos (EP-10) |
| `/admin/treatment-plan-payments/{payment_id}` | DELETE | Elimina pago (EP-11) |

**Lógica de negocio**:
- EP-09: Insert payment + sync accounting_transactions (TRANSACCIÓN ÚNICA), auto-avanza estado plan approved → in_progress
- EP-10: Lista pagos con JOIN a users y appointments
- EP-11: Solo CEO/secretary pueden eliminar, elimina accounting_transaction relacionado

**Criterios de aceptación**:
- [ ] EP-09 valida plan en estado approved/in_progress
- [ ] EP-09 crea accounting_transaction atómicamente
- [ ] EP-09 actualiza status a in_progress si era approved y primer pago
- [ ] EP-11 valida rol (solo ceo/secretary)

---

### Tarea 2.5 — Endpoint Appointment Linking (EP-12)

**Descripción**: Implementar endpoint para vincular turnos a ítems de plan.

**Archivos afectados**:
- `orchestrator_service/admin_routes.py` (MODIFICAR)

**Dependencias**:
- Tarea 2.4 completada

**Endpoint a implementar**:

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/admin/appointments/{id}/link-plan-item` | PUT | Vincula turno a ítem (EP-12) |

**Lógica de negocio**:
- Caso 1: Vincular — valida paciente del turno = paciente del plan, plan no cancelled
- Caso 2: Desvincular — set plan_item_id = NULL

**Criterios de aceptación**:
- [x] Valida plan_item_id pertenece al mismo paciente que el turno
- [x] Valida plan no está cancelled
- [x] Desvincular usa ON DELETE SET NULL (Fk behavior)

---

### Tarea 2.6 — Helpers y utilidades

**Descripción**: Crear funciones helper reutilizables para los endpoints.

**Archivos afectados**:
- `orchestrator_service/services/treatment_plan_helpers.py` (CREAR)

**Dependencias**:
- Tarea 2.5 completada

**Funciones a crear**:
```python
async def recalculate_estimated_total(pool, plan_id, tenant_id) -> float
async def get_plan_with_totals(pool, plan_id, tenant_id) -> dict
async def validate_plan_access(pool, plan_id, tenant_id) -> bool
async def validate_item_access(pool, item_id, tenant_id) -> bool
def format_currency(amount: Decimal, locale: str = 'es-AR') -> str
```

**Criterios de aceptación**:
- [ ] recalculate_estimated_total suma prices de items no cancelados
- [ ] Todas las funciones incluyen tenant_id filter

---

## FASE 3: FRONTEND

### Tarea 3.1 — Componente BillingTab

**Descripción**: Crear el componente principal de la pestaña de presupuesto y facturación.

**Archivos afectados**:
- `frontend_react/src/components/BillingTab.tsx` (CREAR)

**Dependencias**:
- Tarea 2.5 completada (endpoints)
- Tarea 3.3 completada (i18n keys)

**Componentes a crear dentro de BillingTab**:
- PlanSelectorBar (dropdown + botón nuevo plan)
- EmptyState
- PlanHeaderCard (nombre editable inline, status badge, KPIs)
- FinancialProgressBar
- ItemsSection (tabla + edición inline de approved_price)
- PaymentsSection (tabla + eliminar)
- Modals: CreatePlanModal, AddItemModal, RegisterPaymentModal, ApprovePlanModal

**State requerido**:
```typescript
const [plans, setPlans] = useState<TreatmentPlan[]>([]);
const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
const [planDetail, setPlanDetail] = useState<TreatmentPlanDetail | null>(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
```

**Criterios de aceptación**:
- [ ] Plan selector dropdown cuando hay 2+ planes
- [ ] Auto-seleccionar plan cuando hay 1 solo
- [ ] Nombre editable inline con PATCH
- [ ] approved_price editable inline con PATCH
- [ ] Progress bar con porcentaje de pagado
- [ ] Todos los modales funcionales
- [ ] Responsive: card layout en mobile, table en desktop

---

### Tarea 3.2 — Integración PatientDetail

**Descripción**: Agregar la pestaña billing al PatientDetail existente.

**Archivos Affected**:
- `frontend_react/src/views/PatientDetail.tsx` (MODIFICAR)

**Dependencias**:
- Tarea 3.1 completada

**Cambios requeridos**:

1. Agregar import de BillingTab y Receipt icon
2. Actualizar TabType: `'billing'`
3. Agregar estado: `billingRefreshKey`
4. Agregar Socket.IO listeners para TREATMENT_PLAN_UPDATED y BILLING_UPDATED
5. Agregar caso en renderTabContent
6. Agregar botón de tab

**Criterios de aceptación**:
- [ ] Tab "Presupuesto" aparece después de "Registros Digitales"
- [ ] Click en tab muestra BillingTab
- [ ] Eventos Socket actualizan el tab automáticamente
- [ ] scroll position no se pierde al actualizar

---

### Tarea 3.3 — Claves i18n

**Descripción**: Agregar todas las traducciones necesarias para el namespace billing.

**Archivos afectados**:
- `frontend_react/src/locales/es.json` (MODIFICAR)
- `frontend_react/src/locales/en.json` (MODIFICAR)
- `frontend_react/src/locales/fr.json` (MODIFICAR)

**Dependencias**:
- Ninguna (puede hacerse en paralelo)

**Claves a agregar** (45+ keys):
```
billing.no_plans, billing.create_first, billing.new_plan,
billing.plan_name, billing.plan_name_placeholder, billing.professional,
billing.no_professional, billing.notes,
billing.status.draft, billing.status.approved, billing.status.in_progress,
billing.status.completed, billing.status.cancelled,
billing.approve_plan, billing.approve_confirm, billing.approved_total,
billing.estimated_total, billing.paid, billing.pending, billing.paid_complete,
billing.no_approved_total, billing.treatments, billing.add_treatment,
billing.no_items, billing.treatment, billing.estimated_price,
billing.approved_price, billing.appointments_count, billing.status_item,
billing.item_status.*, billing.delete_item_confirm,
billing.select_treatment, billing.custom_description,
billing.custom_description_placeholder, billing.payments,
billing.register_payment, billing.no_payments, billing.date,
billing.amount, billing.method, billing.recorded_by, billing.method.*,
billing.payment_date, billing.pending_balance_helper,
billing.delete_payment_confirm, billing.error_*, billing.saving
```

**Criterios de aceptación**:
- [x] Todas las claves existen en los 3 archivos
- [x] Traducciones apropiadas para cada idioma

---

### Tarea 3.4 — Testing unitario Frontend

**Descripción**: Crear tests unitarios para el componente BillingTab.

**Archivos afectados**:
- `frontend_react/src/components/__tests__/BillingTab.test.tsx` (CREAR)

**Dependencias**:
- Tarea 3.1 completada

**Tests a escribir**:
- Renderizado correcto con 0 planes (empty state)
- Renderizado correcto con 1 plan (auto-selecciona)
- Renderizado correcto con 2+ planes (dropdown)
- Cambio de plan actualiza vista
- Inline edit de nombre dispara API
- Inline edit de approved_price dispara API
- Eliminación de ítem confirma y dispara API
- Eliminación de pago confirma y dispara API
- Loading states mientras carga
- Error states se muestran correctamente

**Criterios de aceptación**:
- [ ] Tests pasan con jest/react-testing-library
- [ ] Coverage > 70%

---

## FASE 4: METRICS

### Tarea 4.1 — Dashboard KPIs

**Descripción**: Modificar queries de dashboard para incluir tratamiento de planes.

**Archivos afectados**:
- `orchestrator_service/admin_routes.py` (MODIFICAR) — función `get_dashboard_stats()`

**Dependencias**:
- Tarea 1.1 completada (tablas)
- spec-metrics.md

**Métricas a modificar**:

| Métrica | Cambio |
|---------|--------|
| `pending_payments` | UNION: legacy appointments (plan_item_id IS NULL) + plans con approved/in_progress |
| `today_revenue` | UNION: legacy paid appointments today + plan payments today |
| `total_revenue` | Sin cambio (usa accounting_transactions que ya tiene sync) |
| `estimated_revenue` | Sin cambio |

**Criterios de aceptación**:
- [ ] pending_payments excluye turnos con plan_item_id (evita doble-conteo)
- [ ] pending_payments incluye planes approved/in_progress con saldo pendiente
- [ ] today_revenue incluye treatment_plan_payments de hoy
- [ ] backward compatible: sin planes = mismo resultado que antes

---

### Tarea 4.2 — Liquidación Profesional

**Descripción**: Modificar analytics_service para agrupar por plan.

**Archivos afectados**:
- `orchestrator_service/analytics_service.py` (MODIFICAR) — función `get_professionals_liquidation()`

**Dependencias**:
- Tarea 4.1 completada

**Cambios requeridos**:
- Agregar `plan_item_id`, `plan_id`, `plan_name` al base query
- Agregar LEFT JOINs a treatment_plan_items y treatment_plans
- Separar agregación: appointments sin plan_key = legacy, con plan_key = plan
- Fetchear pagos de planes por plan_id
- Agregar campo `type` ("plan" o "appointment") como discriminator

**Criterios de aceptación**:
- [ ] Appointments con plan_item_id agrupados por plan_id
- [ ] total_billed = approved_total para grupos de plan
- [ ] total_paid viene de treatment_plan_payments
- [ ] Response incluye campo "type"

---

### Tarea 4.3 — ROI Dashboard

**Descripción**: Modificar metrics_service para incluir pagos de planes.

**Archivos afectados**:
- `orchestrator_service/services/metrics_service.py` (MODIFICAR) — función `_get_billing_revenue()`

**Dependencias**:
- Tarea 4.2 completada

**Cambios requeridos**:
- Source 1: legacy appointments (plan_item_id IS NULL)
- Source 2: treatment_plan_payments en el rango de fechas

**Criterios de aceptación**:
- [ ] No cuenta appointments con plan_item_id en Source 1
- [ ] Source 2 usa payment_date como temporal anchor

---

### Tarea 4.4 — Nova _resumen_financiero

**Descripción**: Modificar tool para incluir sección de planes.

**Archivos afectados**:
- `orchestrator_service/services/nova_tools.py` (MODIFICAR)

**Dependencias**:
- spec-metrics.md completado

**Cambios requeridos**:
- Agregar query de planes con approved_total y total_paid
- Sumar plan_revenue al total_revenue
- Agregar sección de planes al output

**Criterios de aceptación**:
- [ ] Output incluye "Planes de tratamiento activos" section
- [ ] Total revenue suma appointment + plan

---

### Tarea 4.5 — Nova _facturacion_pendiente

**Descripción**: Modificar tool para incluir planes pendientes.

**Archivos afectados**:
- `orchestrator_service/services/nova_tools.py` (MODIFICAR)

**Dependencias**:
- Tarea 4.4 completada

**Cambios requeridos**:
- Excluir appointments con plan_item_id de la query legacy
- Agregar query de planes con saldo pendiente
- Combinar ambos en output

**Criterios de aceptación**:
- [ ] Turnos sin plan solo muestra los sin plan_item_id
- [ ] "Planes con saldo pendiente" aparece con la lista

---

## FASE 5: AI TOOLS

### Tarea 5.1 — Nova tool: ver_presupuesto_paciente

**Descripción**: Crear tool para visualizar presupuestos de un paciente.

**Archivos afectados**:
- `orchestrator_service/services/nova_tools.py` (MODIFICAR)

**Dependencias**:
- Tarea 2.5 completada (endpoints)

**Implementación**:
```json
{
  "name": "ver_presupuesto_paciente",
  "description": "Muestra el/los presupuesto(s) de tratamiento de un paciente...",
  "parameters": {
    "patient_id": {"type": "integer"},
    "patient_name": {"type": "string"},
    "plan_id": {"type": "string"},
    "include_completed": {"type": "boolean"}
  }
}
```

**Criterios de aceptación**:
- [ ] Busca por nombre (fuzzy ILIKE) o ID
- [ ] Múltiples pacientes → lista para aclarar
- [ ] Sin planes activos → mensaje claro
- [ ] Incluye: items, precios, pagos, saldo

---

### Tarea 5.2 — Nova tool: registrar_pago_plan

**Descripción**: Crear tool para registrar pagos contra un plan.

**Archivos afectados**:
- `orchestrator_service/services/nova_tools.py` (MODIFICAR)

**Dependencias**:
- Tarea 5.1 completada

**Implementación**:
```json
{
  "name": "registrar_pago_plan",
  "description": "Registra un pago parcial o total contra el plan...",
  "parameters": {
    "patient_id": {"type": "integer"},
    "patient_name": {"type": "string"},
    "plan_id": {"type": "string"},
    "amount": {"type": "number"},
    "method": {"type": "string", "enum": ["cash", "transfer", "card", "insurance"]},
    "appointment_id": {"type": "string"},
    "notes": {"type": "string"}
  }
}
```

**Criterios de aceptación**:
- [ ] Resuelve plan automáticamente si solo hay 1 activo
- [ ] Múltiples planes → pide aclarar
- [ ] Crea treatment_plan_payment + accounting_transaction
- [ ] Auto-completa plan si total_paid >= approved_total
- [ ] Emite BILLING_UPDATED

---

### Tarea 5.3 — Nova tool: aprobar_presupuesto

**Descripción**: Crear tool para aprobar planes con precio final.

**Archivos afectados**:
- `orchestrator_service/services/nova_tools.py` (MODIFICAR)

**Dependencias**:
- Tarea 5.2 completada

**Implementación**:
```json
{
  "name": "aprobar_presupuesto",
  "description": "Aprueba un plan de tratamiento fijando el precio final...",
  "parameters": {
    "plan_id": {"type": "string"},
    "patient_id": {"type": "integer"},
    "patient_name": {"type": "string"},
    "approved_total": {"type": "number"},
    "notes": {"type": "string"}
  }
}
```

**Criterios de aceptación**:
- [ ] Solo busca planes en estado draft
- [ ] Solo CEO puede usar
- [ ] Establece status='approved', approved_by, approved_at
- [ ] approved_total puede diferir de estimated

---

### Tarea 5.4 — Nova tool: registrar_pago (modificado)

**Descripción**: Modificar tool existente para aceptar plan_id.

**Archivos afectados**:
- `orchestrator_service/services/nova_tools.py` (MODIFICAR)

**Dependencias**:
- spec-ai-tools.md

**Cambios requeridos**:
- Agregar `plan_id` como parámetro alternativo a `appointment_id`
- Si viene plan_id → delegar a lógica de registrar_pago_plan
- Actualizar description

**Criterios de aceptación**:
- [ ] Con appointment_id → comportamiento legacy
- [ ] Con plan_id → crea treatment_plan_payment
- [ ] Si ambos → plan_id tiene precedencia

---

### Tarea 5.5 — WhatsApp: verify_payment_receipt

**Descripción**: Modificar función existente para detectar planes activos.

**Archivos afectados**:
- `orchestrator_service/main.py` (MODIFICAR) — función `verify_payment_receipt` (~línea 4141)

**Dependencias**:
- Tarea 1.1 completada (tablas)

**Cambios requeridos**:
- Buscar active_plan para el paciente
- Si hay plan_pending_balance > 0 → usar como expected_amount fallback
- Si verificación exitosa + context="plan" → crear treatment_plan_payment
- Actualizar status plan si completado
- Ajustar mensaje al paciente

**Criterios de aceptacion**:
- [ ] Si turno tiene billing_amount → usa ese (prioridad)
- [ ] Si no hay turno pero hay plan → usa saldo pendiente del plan
- [ ] Crea payment en treatment_plan_payments
- [ ] Auto-completa plan si pagado completo

---

### Tarea 5.6 — Buffer task: detección de comprobantes

**Descripción**: Modificar para detectar planes con saldo pendiente.

**Archivos afectados**:
- `orchestrator_service/services/buffer_task.py` (MODIFICAR) — (~línea 1121)

**Dependencias**:
- Tarea 5.5 completada

**Cambios requeridos**:
- Agregar query para buscar pending_plan
- Si pending_plan existe → enrich media_context con instrucciones de plan
- Indicar al agente que use verify_payment_receipt

**Criterios de aceptación**:
- [ ] Si hay turno pendiente + plan pendiente → priorizar turno
- [ ] Si solo hay plan pendiente → asumír como comprobante de plan
- [ ] Mensaje enriquecido incluye instrucciones específicas

---

## FASE 6: EMAIL

### Tarea 6.1 — Email service (confirmación de pagos de planes)

**Descripción**: Implementar método send_plan_payment_confirmation_email para enviar emails de confirmación cuando se registra un pago contra un plan de tratamiento.

**Archivos afectados**:
- `orchestrator_service/email_service.py` (MODIFICAR)

**Dependencias**:
- Tarea 1.1 completada (tablas treatment_plans y treatment_plan_payments)

**Verificación previa**:
- [x] `patients` tiene columna `email`
- [x] Existencia de config SMTP en entorno

**Implementación**:
- [x] Método `send_plan_payment_confirmation_email(tenant_id, patient_id, payment_id, db_pool)` 
- [x] Retorna dict con {"success": bool, "summary": str}
- [x] Busca datos del pago con JOIN a treatment_plans, patients, tenants
- [x] Valida patient.email no sea NULL → retorna {"success": False, "summary": "Paciente sin email"}
- [x] Calcula totales: approved_total, paid_total, pending_total, paid_percentage
- [x] Renderiza templates en 3 idiomas (es/en/fr) con progress bar visual
- [x] Envía via SMTP configurado
- [x] Loggea resultado

**Template del email**:
- [x] Plan name
- [x] Monto pagado, método, fecha
- [x] Total aprobado, pagado, pendiente
- [x] Progress bar visual (porcentaje completado)
- [x] Datos de la clínica

**Criterios de aceptación**:
- [x] Si patient.email es NULL → retorna {"success": False, "summary": "Paciente sin email"}
- [x] Renderiza template con datos correctos
- [x] Usa SMTP del sistema (variables de entorno)
- [x] Loggea resultado con nivel INFO

---

### Tarea 6.2 — Integración email en endpoints [COMPLETADA]

**Descripción**: Agregar llamada a email service después de crear pago.

**Archivos afectados**:
- `orchestrator_service/admin_routes.py` (MODIFICAR) — EP-09

**Dependencias**:
- Tarea 6.1 completada

**Cambios requeridos**:
- Después de INSERT payment exitoso en EP-09
- Llamar async a send_payment_confirmation_email
- No rompe respuesta si falla (solo log warning)

**Criterios de aceptación**:
- [x] Email enviado si paciente tiene email
- [x] No falla si email service tiene problemas

---

### Tarea 6.3 — Integración email en verify_payment_receipt [COMPLETADA]

**Descripción**: Agregar lógica de email cuando se verifica comprobante.

**Archivos afectados**:
- `orchestrator_service/main.py` (MODIFICAR)

**Dependencias**:
- Tarea 6.1 completada

**Cambios requeridos**:
- [x] Después de verificar comprobante exitosamente
- [x] Obtener patient.email
- [x] Si existe → enviar email de confirmación
- [x] Si no existe → devolver flag email_required=True para que el agente pida el email

**Criterios de aceptación**:
- [x] Con email → envía automáticamente
- [x] Sin email → devuelve flag para que agente pida

---

### Tarea 6.4 — Nova tool: actualizar_email_paciente

**Descripción**: Crear tool para que Nova guarde email del paciente.

**Archivos afectados**:
- `orchestrator_service/services/nova_tools.py` (MODIFICAR)

**Dependencias**:
- Tarea 6.3 completada

**Implementación**:
```json
{
  "name": "actualizar_email_paciente",
  "description": "Guarda o actualiza el email de un paciente en su ficha",
  "parameters": {
    "patient_id": {"type": "integer"},
    "email": {"type": "string", "format": "email"}
  }
}
```

**Endpoint**:
- PUT /admin/patients/{patient_id}/email

**Criterios de aceptación**:
- [x] Valida formato de email
- [x] Actualiza patients.email
- [x] Retorna email actualizado

---

### Tarea 6.5 — Welcome email: profesional [COMPLETADA]

**Descripción**: Implementar email de bienvenida para nuevos profesionales.

**Archivos afectados**:
- `orchestrator_service/services/email_service.py` (MODIFICAR)
- `orchestrator_service/auth_routes.py` (MODIFICAR)
- `orchestrator_service/admin_routes.py` (MODIFICAR)

**Dependencias**:
- Tarea 6.1 completada
- spec-welcome-emails.md

**Implementación**:
- Agregar método `send_welcome_email(tenant_id, user_id, role, db_pool)` en email_service
- Template HTML para profesional con: credenciales, datos clínica, link login, funcionalidades
- Integrar en auth_routes.py (POST /register con role=professional)
- Integrar en admin_routes.py (POST create_professional con is_active=TRUE)

**Contenido del email**:
- Subject: "Bienvenido a {clinic_name} - Tu acceso al sistema"
- Datos: usuario, link acceso, clínica (nombre, dirección, teléfono), soporte

**Criterios de aceptación**:
- [x] Se envía solo si profesional está activo (is_active=TRUE)
- [x] Incluye credenciales y datos de la clínica
- [x] No bloquea respuesta si falla (async, solo log warning)

---

### Tarea 6.6 — Welcome email: secretary

**Descripción**: Implementar email de bienvenida para nuevas secretarias.

**Archivos afectados**:
- `orchestrator_service/services/email_service.py` (MODIFICAR)

**Dependencias**:
- Tarea 6.5 completada

**Implementación**:
- Reutilizar método send_welcome_email con role="secretary"
- Template específico para secretary con funcionalidades disponibles

**Contenido del email**:
- Subject: "Bienvenida a {clinic_name} - Tu acceso como Secretaría"
- Datos: credenciales, link acceso, clínica, funcionalidades (gestión turnos, registro pacientes, etc.)

**Criterios de aceptación**:
- [x] Se envía solo si secretary está activa
- [x] Contenido específico para rol de secretary
- [x] Funcionalidades listadas: gestión agenda, registro pacientes, confirmación turnos, historial conversaciones

---

### Tarea 6.7 — Welcome email: CEO/Admin

**Descripción**: Implementar email de bienvenida para nuevos CEO/Administradores.

**Archivos afectados**:
- `orchestrator_service/services/email_service.py` (MODIFICAR)

**Dependencias**:
- Tarea 6.6 completada

**Implementación**:
- Reutilizar método send_welcome_email con role="ceo"
- Template específico para CEO con privilegios de administrador

**Contenido del email**:
- Subject: "Bienvenido a {clinic_name} - Acceso como Administrador"
- Datos: credenciales, link acceso, clínica, dashboard/métricas, configuraciones disponibles

**Criterios de aceptación**:
- [ ] Se envía solo si usuario tiene role=ceo y status=active
- [ ] Contenido específico para rol de administrador
- [ ] Incluye: métricas, reportes, configuraciones (clínica, usuarios, agenda, Google Calendar)

---

## FASE 7: VERIFICACIÓN

### Tarea 7.1 — Tests unitarios Backend

**Descripción**: Escribir tests unitarios para lógica de negocio.

**Archivos afectados**:
- `orchestrator_service/tests/test_treatment_plans.py` (CREAR)

**Dependencias**:
- Fases 1-6 completadas

**Tests a escribir**:
- Test CRUD planes completo
- Test CRUD items con recalculo de totales
- Test payments con sync contable
- Test transición de estados
- Test validación de tenant_id

**Criterios de aceptación**:
- [ ] Tests pasan con pytest
- [ ] Coverage > 80%

---

### Tarea 7.2 — Tests de integración

**Descripción**: Tests end-to-end de los endpoints.

**Archivos afectados**:
- `orchestrator_service/tests/integration/test_treatment_plans_api.py` (CREAR)

**Dependencias**:
- Tarea 7.1 completada

**Tests a escribir**:
- Crear plan → GET detail → UPDATE → DELETE
- Agregar items → verificar estimated_total
- Registrar pago → verificar accounting_transaction
- Vincular turno → verificar plan_item_id

**Criterios de aceptación**:
- [ ] Tests corren contra test DB
- [ ] Todos los workflows principales cubiertos

---

### Tarea 7.3 — E2E Frontend

**Descripción**: Tests de usuario desde UI.

**Archivos afectados**:
- `frontend_react/e2e/treatment-plan-billing.spec.ts` (CREAR)

**Dependencias**:
- Tarea 3.1 completada

**Escenarios E2E**:
- Crear plan desde empty state
- Agregar tratamiento al plan
- Aprobar plan
- Registrar pago
- Ver progreso en barra
- Eliminar pago
- Eliminar ítem

**Criterios de aceptación**:
- [ ] Tests pasan con Playwright
- [ ] Todos los flujos principales funcionan

---

### Tarea 7.4 — Documentación de API

**Descripción**: Generar documentación OpenAPI/Swagger.

**Archivos afectados**:
- Auto-generado por FastAPI (revisar que endpoints tienen summaries y tags)

**Dependencias**:
- Tareas 2.2-2.5 completadas

**Verificación**:
- [ ] Todos los endpoints tienen tags=["Planes de Tratamiento"]
- [ ] Todos tienen summary
- [ ] Modelos Pydantic documentados

---

### Tarea 7.5 — Verificación de backward compatibility

**Descripción**: Verificar que sistema legacy funciona igual.

**Archivos afectados**:
- Ninguno (verificación)

**Dependencias**:
- Tareas 4.1-4.3 completadas

**Verificaciones**:
- [ ] Turnos sin plan muestran billing_amount igual que antes
- [ ] Dashboard KPIs igual que antes cuando no hay planes
- [ ] Liquidación de profesionales igual que antes para turnos sin plan

---

## Matriz de Dependencias

```
Tarea          | Depende de
---------------|------------------
1.1            | 017 aplicada
1.2            | 1.1
2.1            | 1.1
2.2            | 2.1
2.3            | 2.2
2.4            | 2.3
2.5            | 2.4
2.6            | 2.5
3.1            | 2.5, 3.3
3.2            | 3.1
3.3            | -
3.4            | 3.1
4.1            | 1.1
4.2            | 4.1
4.3            | 4.2
4.4            | 1.1
4.5            | 4.4
5.1            | 2.5
5.2            | 5.1
5.3            | 5.2
5.4            | -
5.5            | 1.1
5.6            | 5.5
6.1            | 1.1 (verificar email column)
6.2            | 6.1
6.3            | 6.1
6.4            | 6.3
6.5            | 6.1
6.6            | 6.5
6.7            | 6.6
7.1            | Fases 1-6
7.2            | 7.1
7.3            | 3.1
7.4            | 2.2-2.5
7.5            | 4.1-4.3
```

---

## Notas de Riesgo

| Riesgo | Mitigation |
|--------|------------|
| Doble-conteo en métricas | Validar con tests específicos (tarea 7.5) |
| Inconsistencia estimated_total | Recálculo automático en cada endpoint de ítem |
| Migración rompe existente | Backward compatible, queries legacy intactas |
| Complexity UI para Dra. | BillingTab simple, flujo lineal |

---

*Breakdown de tareas generado: 2026-04-03*
