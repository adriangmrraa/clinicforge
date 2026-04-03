# Tasks: Treatment Plan Billing — Fixes & Stabilization

---

## FASE 1: CRITICAL FIXES (8 tareas)

### Tarea 1.1 — Fix C1: EP-11 Runtime Crash

**Archivo**: `orchestrator_service/admin_routes.py`
**Cambio**:
- Agregar `request: Request` al signature del endpoint DELETE `/admin/treatment-plan-payments/{payment_id}`
- Cambiar `Request` (clase) → `request` (instancia) en la llamada a `emit_appointment_event`

**Criterio de aceptación**:
- [ ] DELETE payment no crashea
- [ ] Evento BILLING_UPDATED se emite correctamente

---

### Tarea 1.2 — Fix C2: EP-04 approved_by consistente

**Archivo**: `orchestrator_service/admin_routes.py`
**Cambio**:
- Verificar que `approved_by` almacena `user_data.email` consistentemente (ya que la columna es VARCHAR)
- Asegurar que EP-03 retorna `approved_by` como string usable en la UI
- Agregar comentario documentando que es email, no ID

**Criterio de aceptación**:
- [ ] Aprobación no falla con DB type error
- [ ] EP-03 muestra quién aprobó

---

### Tarea 1.3 — Fix C3: EP-09 transacción DB

**Archivo**: `orchestrator_service/admin_routes.py`
**Cambio**:
- Envolver INSERT payment + INSERT accounting_transaction + UPDATE plan status en `async with pool.acquire() as conn: async with conn.transaction():`
- Mover todos los db.pool.execute/fetchrow dentro de conn.execute/fetchrow

**Criterio de aceptación**:
- [ ] Si accounting_transaction INSERT falla, payment INSERT se revierte
- [ ] Si plan UPDATE falla, ambos INSERTs se revierten

---

### Tarea 1.4 — Fix C4: ItemStatus enum

**Archivo**: `orchestrator_service/schemas/treatment_plan.py`
**Cambio**: Agregar `IN_PROGRESS = "in_progress"` al enum `ItemStatus`

**Criterio de aceptación**:
- [ ] PUT item con status='in_progress' pasa validación Pydantic

---

### Tarea 1.5 — Fix C5: CreateTreatmentPlanBody schema

**Archivo**: `orchestrator_service/schemas/treatment_plan.py`
**Cambio**:
- `professional_id: Optional[int] = Field(None, ...)`
- Remover `patient_id` del body (viene del path)

**Criterio de aceptación**:
- [ ] POST create plan sin professional_id no falla
- [ ] POST create plan con professional_id funciona

---

### Tarea 1.6 — Fix C6: Nova _registrar_pago_plan accounting_transactions

**Archivo**: `orchestrator_service/services/nova_tools.py`
**Cambio**: Después del INSERT en treatment_plan_payments, agregar INSERT en accounting_transactions con los mismos datos (amount, payment_method, tenant_id, patient_id).

**Criterio de aceptación**:
- [ ] Pago registrado por Nova aparece en accounting_transactions
- [ ] Dashboard total_revenue incluye el pago

---

### Tarea 1.7 — Fix C7: Nova _registrar_pago_plan auto-complete

**Archivo**: `orchestrator_service/services/nova_tools.py`
**Cambio**: Después del INSERT payment:
```python
total_paid = await db.pool.fetchval(
    "SELECT COALESCE(SUM(amount), 0) FROM treatment_plan_payments WHERE plan_id = $1 AND tenant_id = $2",
    plan_id, tenant_id
)
if total_paid >= float(plan["approved_total"]):
    await db.pool.execute(
        "UPDATE treatment_plans SET status = 'completed', updated_at = NOW() WHERE id = $1",
        plan_id
    )
```

**Criterio de aceptación**:
- [ ] Plan con saldo 0 después de pago cambia a status 'completed'
- [ ] Plan con saldo > 0 mantiene status actual

---

### Tarea 1.8 — Fix C8: i18n caracter corrupto

**Archivo**: `frontend_react/src/locales/es.json`
**Cambio**: `billing.no_approved_total`: `"Sin批准 total"` → `"Sin total aprobado"`

**Criterio de aceptación**:
- [ ] UI muestra "Sin total aprobado" sin caracteres rotos

---

## FASE 2: HIGH FIXES (12 tareas)

### Tarea 2.1 — Fix H1+H2+H3+H4: Migration 019 correctiva

**Archivo**: `orchestrator_service/alembic/versions/019_treatment_plan_billing_fixes.py`
**Cambio**: Nueva migración Alembic con:
- ALTER payment_date TYPE TIMESTAMPTZ, DEFAULT NOW()
- DROP FK constraint en appointment_id
- ADD 7 CHECK constraints (estimated_total >= 0, approved_total >= 0, approved_consistency, item prices >= 0, description check)
- DROP + ADD item status CHECK con 'in_progress'
- ALTER custom_description TYPE TEXT
- ALTER name TYPE VARCHAR(200)

**Criterio de aceptación**:
- [ ] alembic upgrade head ejecuta sin error
- [ ] alembic downgrade revierte todo
- [ ] payment_date acepta timestamp con hora
- [ ] items pueden tener status 'in_progress'
- [ ] montos negativos son rechazados por DB

---

### Tarea 2.2 — Fix H5: EP-03 appointments array en items

**Archivo**: `orchestrator_service/admin_routes.py`
**Cambio**: En EP-03, modificar query de items para incluir subquery JSON_AGG de appointments vinculados:
```sql
(SELECT JSON_AGG(JSON_BUILD_OBJECT(
    'id', a.id, 'datetime', a.appointment_datetime,
    'status', a.status, 'type', a.appointment_type
)) FROM appointments a WHERE a.plan_item_id = tpi.id AND a.tenant_id = $1) as appointments
```

**Criterio de aceptación**:
- [ ] EP-03 items incluyen `appointments: [{id, datetime, status, type}]`
- [ ] Items sin turnos vinculados tienen `appointments: null` o `[]`

---

### Tarea 2.3 — Fix H6: EP-03 progress_pct y approved_by_name

**Archivo**: `orchestrator_service/admin_routes.py`
**Cambio**:
- Computar `progress_pct = round(paid_total / approved_total * 100, 1) if approved_total > 0 else 0`
- `approved_by_name` = valor de `approved_by` (ya es email/nombre)

**Criterio de aceptación**:
- [ ] Response incluye progress_pct (float 0-100)
- [ ] Response incluye approved_by_name (string o null)

---

### Tarea 2.4 — Fix H7: EP-05 no auto-cancelar items

**Archivo**: `orchestrator_service/admin_routes.py`
**Cambio**: Remover el `UPDATE treatment_plan_items SET status = 'cancelled'` del endpoint EP-05.

**Criterio de aceptación**:
- [ ] Items mantienen su estado original al cancelar plan

---

### Tarea 2.5 — Fix H8: EP-05 evento correcto

**Archivo**: `orchestrator_service/admin_routes.py`
**Cambio**: Cambiar `"TREATMENT_PLAN_CANCELLED"` → `"TREATMENT_PLAN_UPDATED"`

**Criterio de aceptación**:
- [ ] Frontend recibe TREATMENT_PLAN_UPDATED al cancelar plan

---

### Tarea 2.6 — Fix H9: Nova aprobar_presupuesto búsqueda por nombre

**Archivo**: `orchestrator_service/services/nova_tools.py`
**Cambio**: Si solo viene `patient_name` (sin patient_id y sin plan_id):
1. Buscar pacientes con ILIKE
2. Buscar planes draft de esos pacientes
3. Si 1 resultado → aprobar
4. Si múltiples → listar para aclarar

**Criterio de aceptación**:
- [ ] "Aprobá el presupuesto de María por $420.000" funciona
- [ ] Múltiples coincidencias → pide aclaración

---

### Tarea 2.7 — Fix H10: verify_payment_receipt priority chain

**Archivo**: `orchestrator_service/main.py`
**Cambio**: Mover el plan check DESPUÉS de billing_amount check pero ANTES de los fallbacks (prof_price, treatment_price, tenant_price).

**Criterio de aceptación**:
- [ ] Paciente con plan activo y billing_amount=0 → verifica contra plan
- [ ] Paciente con billing_amount>0 → verifica contra billing_amount (prioridad)
- [ ] Paciente sin plan ni billing_amount → usa fallbacks genéricos

---

### Tarea 2.8 — Fix H11: BillingTab notas

**Archivo**: `frontend_react/src/components/BillingTab.tsx`
**Cambio**:
- Agregar columna "Notas" en la tabla de pagos (truncar a 40 chars, tooltip on hover)
- Agregar `<textarea>` para notas en RegisterPaymentModal

**Criterio de aceptación**:
- [ ] Tabla muestra notas truncadas
- [ ] Modal permite ingresar notas
- [ ] Notas se envían al backend

---

### Tarea 2.9 — Fix H12: BillingTab responsive mobile

**Archivo**: `frontend_react/src/components/BillingTab.tsx`
**Cambio**:
- Items: `<table className="hidden md:table">` + `<div className="md:hidden">` cards
- Payments: mismo patrón
- Modals: `items-end md:items-center` + `rounded-t-2xl md:rounded-xl`

**Criterio de aceptación**:
- [ ] Items y payments se ven como cards en mobile
- [ ] Modals son bottom-sheet en mobile
- [ ] Sin scroll horizontal en ningún breakpoint

---

## FASE 3: MEDIUM FIXES (5 tareas agrupadas)

### Tarea 3.1 — Migration 019: índices y tipos menores

**Incluye**: M1 (index names), M2 (custom_description TEXT), M3 (name VARCHAR(200))
**Ya cubierto en Tarea 2.1** — marcar como completado si 2.1 está hecho.

---

### Tarea 3.2 — Backend: status codes y response shapes

**Incluye**: M4 (EP-01 status filter), M5 (HTTP 422), M6 (response shapes), M7 (AddPlanItemBody approved_price)
**Archivos**: `admin_routes.py`, `schemas/treatment_plan.py`

**Criterio de aceptación**:
- [ ] EP-01 acepta ?status=approved
- [ ] Validation errors retornan 422
- [ ] Responses usan "status" en vez de "message"
- [ ] AddPlanItemBody tiene approved_price Optional

---

### Tarea 3.3 — Liquidation output fields

**Incluye**: M8 (plan_status, approved_total en output)
**Archivo**: `orchestrator_service/analytics_service.py`

**Criterio de aceptación**:
- [ ] Plan groups incluyen plan_status y approved_total explícito

---

### Tarea 3.4 — Nova resumen_financiero por plan individual + _resumen_semana fix

**Incluye**: M9 (per-plan detail), M11 (plan_item_id IS NULL en _resumen_semana)
**Archivo**: `orchestrator_service/services/nova_tools.py`

**Criterio de aceptación**:
- [ ] Resumen financiero lista planes individuales con nombre+paciente
- [ ] _resumen_semana no cuenta appointments con plan_item_id

---

### Tarea 3.5 — Timezone + i18n fixes

**Incluye**: M10 (timezone Argentina), M12 (15 i18n values)
**Archivos**: `admin_routes.py`, `es.json`, `en.json`, `fr.json`

**Criterio de aceptación**:
- [ ] today_revenue usa AT TIME ZONE 'America/Argentina/Buenos_Aires'
- [ ] Todos los i18n values matchean spec-frontend.md

---

## Dependency Graph

```
FASE 1 (CRITICAL):
  1.1 → 1.2 → 1.3 → 1.4 → 1.5 (backend, secuencial)
  1.6 → 1.7 (nova, secuencial)
  1.8 (frontend, independiente)

FASE 2 (HIGH):
  2.1 (migration, primero)
  2.2 → 2.3 (EP-03, secuencial)
  2.4 + 2.5 (EP-05, paralelo)
  2.6 (nova, independiente)
  2.7 (main.py, independiente)
  2.8 + 2.9 (frontend, paralelo)

FASE 3 (MEDIUM):
  3.1 (ya en 2.1)
  3.2 (backend, independiente)
  3.3 (analytics, independiente)
  3.4 (nova, independiente)
  3.5 (timezone+i18n, independiente)
```

## Execution Order Recomendado

1. **Batch 1** (parallelizable): Tarea 1.1, 1.4, 1.5, 1.8 — fixes puntuales sin dependencias
2. **Batch 2** (parallelizable): Tarea 1.2, 1.3, 1.6, 1.7 — fixes que requieren leer contexto
3. **Batch 3**: Tarea 2.1 — migration correctiva (fundación para FASE 2)
4. **Batch 4** (parallelizable): Tareas 2.2-2.9 — fixes HIGH
5. **Batch 5** (parallelizable): Tareas 3.2-3.5 — fixes MEDIUM
6. **Final**: Re-run sdd-verify para confirmar 0 findings
