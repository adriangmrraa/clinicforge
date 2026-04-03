# Spec: Treatment Plan Billing — Fixes & Stabilization

**Change**: treatment-plan-billing-fixes
**Date**: 2026-04-03

---

## 1. CRITICAL Fixes (8)

### C1 — EP-11 Runtime Crash (DELETE payment)

**Problema**: `emit_appointment_event("BILLING_UPDATED", {...}, Request)` usa la clase `Request` en vez de la instancia `request`. Además, `request` no está en la firma de la función.

**Fix**:
- Agregar `request: Request` al signature del endpoint EP-11
- Cambiar `Request` → `request` en la llamada a emit

**Archivo**: `admin_routes.py` — endpoint DELETE `/admin/treatment-plan-payments/{payment_id}`
**Criterio**: DELETE de payment no crashea, emite evento correctamente.

---

### C2 — EP-04 approved_by guarda email en vez de user ID

**Problema**: `params.append(user_data.email)` — debería ser `user_data.id` (INT). La columna `approved_by` en la migración es VARCHAR(100), pero debería ser INT. Como la migración ya existe, el fix tiene dos partes:
1. En EP-04: guardar un identificador consistente (email por ahora, ya que la columna es VARCHAR)
2. En migration 019: corregir el tipo a INT FK (ver FASE HIGH H1)

**Fix inmediato** (sin cambiar migración): Documentar que `approved_by` almacena email del usuario aprobador. Asegurar que EP-03 retorne `approved_by` como string usable.

**Fix definitivo** (con migration 019): ALTER COLUMN a INT, update datos existentes, agregar FK.

**Archivo**: `admin_routes.py` — endpoint PUT `/admin/treatment-plans/{plan_id}`
**Criterio**: Aprobación no falla con DB type error.

---

### C3 — EP-09 sin transacción DB

**Problema**: INSERT payment + INSERT accounting_transaction + UPDATE plan status son 3 queries separadas. Si la 2da falla, queda payment sin accounting_transaction.

**Fix**: Envolver en `async with pool.acquire() as conn: async with conn.transaction():`

**Archivo**: `admin_routes.py` — endpoint POST `/admin/treatment-plans/{plan_id}/payments`
**Criterio**: Si accounting_transaction INSERT falla, payment INSERT se revierte.

---

### C4 — ItemStatus enum falta 'in_progress'

**Problema**: `ItemStatus` en `schemas/treatment_plan.py` solo tiene PENDING, COMPLETED, CANCELLED. Falta IN_PROGRESS.

**Fix**: Agregar `IN_PROGRESS = "in_progress"` al enum.

**Archivo**: `orchestrator_service/schemas/treatment_plan.py`
**Criterio**: PUT item con status='in_progress' no falla validación Pydantic.

---

### C5 — CreateTreatmentPlanBody.professional_id required

**Problema**: `professional_id: int = Field(...)` es required. Debería ser Optional porque la Dra. puede crear un plan sin asignar profesional.

**Fix**: Cambiar a `professional_id: Optional[int] = Field(None, ...)`. También remover `patient_id` del body (viene del path).

**Archivo**: `orchestrator_service/schemas/treatment_plan.py`
**Criterio**: POST create plan sin professional_id no falla.

---

### C6 — Nova _registrar_pago_plan sin accounting_transactions

**Problema**: Inserta en `treatment_plan_payments` pero NO en `accounting_transactions`. Pagos por Nova no aparecen en dashboard `total_revenue`.

**Fix**: Agregar INSERT INTO accounting_transactions después del INSERT payment, igual que EP-09.

**Archivo**: `orchestrator_service/services/nova_tools.py` — función `_registrar_pago_plan`
**Criterio**: Pago registrado por Nova aparece en dashboard total_revenue.

---

### C7 — Nova _registrar_pago_plan sin auto-complete

**Problema**: No verifica si el plan está fully paid después del pago. No actualiza status a 'completed'.

**Fix**: Después del INSERT, query SUM(amount) vs approved_total. Si >= → UPDATE status = 'completed'.

**Archivo**: `orchestrator_service/services/nova_tools.py` — función `_registrar_pago_plan`
**Criterio**: Plan con saldo 0 después de pago cambia a status 'completed'.

---

### C8 — i18n caracter chino corrupto

**Problema**: `billing.no_approved_total` tiene valor `"Sin批准 total"` con caracter chino corrupto.

**Fix**: Cambiar a `"Sin total aprobado"`.

**Archivo**: `frontend_react/src/locales/es.json`
**Criterio**: UI muestra texto correcto sin caracteres rotos.

---

## 2. HIGH Fixes (12)

### H1 — Migration: approved_by y recorded_by tipos incorrectos

**Problema**: `approved_by` (treatment_plans) y `recorded_by` (treatment_plan_payments) son VARCHAR(100). Spec dice INT FK users(id).

**Fix**: Migration 019 — ALTER COLUMN ambos a VARCHAR(100) confirmando (ya son VARCHAR, solo documentar la decisión). O si se prefiere integridad: ALTER a INT con UPDATE previo. **Decisión**: mantener VARCHAR(100) y almacenar email del usuario (más resiliente, no depende de tabla users). Actualizar spec para reflejar esto.

**Archivo**: Migration 019 (nueva) o actualizar spec
**Criterio**: Consistencia entre spec y migración documentada.

---

### H2 — Migration: payment_date es DATE, spec dice TIMESTAMPTZ

**Problema**: Se pierde la hora exacta del pago.

**Fix**: Migration 019 — `ALTER COLUMN payment_date TYPE TIMESTAMPTZ USING payment_date::timestamptz`. Cambiar default de `current_date` a `now()`.

**Archivo**: Migration 019 (nueva)
**Criterio**: payment_date almacena fecha+hora.

---

### H3 — Migration: appointment_id tiene FK, spec dice NO FK

**Problema**: FK constraint puede fallar si appointment se borra.

**Fix**: Migration 019 — `ALTER TABLE treatment_plan_payments DROP CONSTRAINT ...` la FK de appointment_id.

**Archivo**: Migration 019 (nueva)
**Criterio**: appointment_id es soft reference sin constraint.

---

### H4 — Migration: 7 CHECK constraints faltantes

**Problema**: estimated_total >= 0, approved_total >= 0, approved_consistency, item prices >= 0, description obligatoria.

**Fix**: Migration 019 — ADD CONSTRAINT para cada uno.

**Archivo**: Migration 019 (nueva)
**Criterio**: DB rechaza datos inválidos.

---

### H5 — EP-03: Items sin appointments array

**Problema**: Solo retorna `appointments_count`, no el array de turnos vinculados.

**Fix**: Agregar subquery `JSON_AGG` para appointments vinculados a cada item via plan_item_id.

**Archivo**: `admin_routes.py` — EP-03 GET plan detail
**Criterio**: Response incluye `appointments: [{id, datetime, status, type}]` por item.

---

### H6 — EP-03: Falta progress_pct y approved_by_name

**Problema**: Response no incluye campos computados del spec.

**Fix**: Computar `progress_pct = (paid_total / approved_total * 100)` en Python. Join users para `approved_by_name`.

**Archivo**: `admin_routes.py` — EP-03
**Criterio**: Response incluye progress_pct (float) y approved_by_name (string|null).

---

### H7 — EP-05: Auto-cancela items

**Problema**: DELETE plan cancela todos los items automáticamente. Spec dice preservar estado para referencia histórica.

**Fix**: Remover el `UPDATE treatment_plan_items SET status='cancelled'` del endpoint.

**Archivo**: `admin_routes.py` — EP-05
**Criterio**: Items mantienen su estado original cuando el plan se cancela.

---

### H8 — EP-05: Evento Socket.IO incorrecto

**Problema**: Emite `TREATMENT_PLAN_CANCELLED`. Spec dice `TREATMENT_PLAN_UPDATED`.

**Fix**: Cambiar nombre del evento.

**Archivo**: `admin_routes.py` — EP-05
**Criterio**: Frontend recibe TREATMENT_PLAN_UPDATED con status 'cancelled'.

---

### H9 — Nova aprobar_presupuesto sin búsqueda por nombre

**Problema**: Requiere `patient_id` + `patient_name`. No funciona con solo `patient_name` (caso de voz).

**Fix**: Agregar branch: si solo `patient_name` → fuzzy search pacientes → encontrar plan draft.

**Archivo**: `nova_tools.py` — función `_aprobar_presupuesto`
**Criterio**: "Aprobá el presupuesto de María por $420.000" funciona.

---

### H10 — verify_payment_receipt: plan fallback demasiado tarde

**Problema**: Plan check solo ejecuta cuando TODOS los price lookups fallan (billing_amount, prof_price, treatment_price, tenant_price). Debería ejecutar después de billing_amount pero ANTES de los fallbacks genéricos.

**Fix**: Mover el plan check después del check de `billing_amount` y ANTES de los fallbacks de professional/treatment/tenant price.

**Archivo**: `orchestrator_service/main.py` — función `verify_payment_receipt`
**Criterio**: Paciente con plan activo y comprobante se verifica contra saldo del plan, no contra 50% del precio genérico.

---

### H11 — BillingTab: sin columna notas y sin campo notas en modal

**Problema**: Payments table no muestra notas. RegisterPaymentModal no tiene textarea para notas.

**Fix**: Agregar columna "Notas" a la tabla de pagos. Agregar textarea al modal de registro.

**Archivo**: `frontend_react/src/components/BillingTab.tsx`
**Criterio**: Usuario puede ingresar y ver notas de cada pago.

---

### H12 — BillingTab: sin responsive mobile

**Problema**: Items y payments solo tienen layout de tabla. Modals no son bottom-sheet en mobile.

**Fix**: Agregar card layout para mobile (`md:hidden` cards + `hidden md:block` table). Bottom-sheet modals con `items-end md:items-center`.

**Archivo**: `frontend_react/src/components/BillingTab.tsx`
**Criterio**: UI usable en mobile sin scroll horizontal.

---

## 3. MEDIUM Fixes (12)

### M1 — Index names no matchean spec (4 mismatches)
Cambiar nombres de índices en migration 019 (DROP + CREATE con nombre correcto).

### M2 — custom_description VARCHAR(255) → TEXT
Migration 019: ALTER COLUMN custom_description TYPE TEXT.

### M3 — treatment_plans.name VARCHAR(255) → VARCHAR(200)
Migration 019: ALTER COLUMN name TYPE VARCHAR(200). Verify no hay datos > 200 chars.

### M4 — EP-01 falta ?status= query param filter
Agregar `status: Optional[str] = Query(None)` al endpoint y filtrar en SQL.

### M5 — EP-04/06/07 usan HTTP 400, spec dice 422
Cambiar status_code a 422 en validation errors.

### M6 — EP-06/07/08 response shape no matchea spec
Cambiar `"message"` → `"status"` en responses. Agregar campos faltantes.

### M7 — EP-06 AddPlanItemBody falta approved_price
Agregar `approved_price: Optional[float] = None` al schema.

### M8 — Liquidation output falta plan_status y approved_total
Agregar ambos campos al output dict del plan group.

### M9 — _resumen_financiero totales agregados, no por plan individual
Cambiar query de fetchrow (agregado) a fetch (por plan) y formatear con nombre+paciente.

### M10 — today_revenue plan payments sin timezone
Agregar `AT TIME ZONE 'America/Argentina/Buenos_Aires'` al filtro de fecha.

### M11 — _resumen_semana no filtra plan_item_id IS NULL
Agregar `AND plan_item_id IS NULL` a la query.

### M12 — ~15 i18n keys con valores diferentes al spec
Corregir valores en es.json, en.json, fr.json según spec-frontend.md.
