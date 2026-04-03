# Tasks: Billing Tab Smart Hub

---

## FASE 1: BACKEND — Endpoints nuevos

### Tarea 1.1 — EP-NEW-01: GET /admin/patients/{id}/billing-summary

**Archivo**: `orchestrator_service/admin_routes.py`

**Implementación**:
1. Nuevo endpoint con `Depends(verify_admin_token)`, tenant_id del JWT
2. Query appointments del paciente con LEFT JOINs a treatment_types y professionals
3. Agrupación en Python por treatment_code
4. Calcular totals (estimated, paid, pending)
5. Check si tiene plan activo (`treatment_plans WHERE status IN ('draft','approved','in_progress')`)
6. Retornar response shape de spec-backend.md

**Criterios de aceptación**:
- [ ] Paciente con turnos retorna appointments + treatment_groups + totals
- [ ] Paciente sin turnos retorna arrays vacíos + totals en 0
- [ ] has_active_plan=true cuando hay plan, con active_plan_id
- [ ] payment_receipt_data se incluye parseada (no raw string)
- [ ] Tenant isolation: solo turnos del tenant

---

### Tarea 1.2 — EP-NEW-02: POST /admin/patients/{id}/generate-plan-from-appointments

**Archivo**: `orchestrator_service/admin_routes.py`

**Implementación**:
1. Validar que no tenga plan activo (409 si ya tiene)
2. Validar que tenga turnos (422 si no tiene)
3. Dentro de transacción DB:
   a. INSERT treatment_plan (status='draft', name auto-generado)
   b. Por cada treatment_group: INSERT treatment_plan_item
   c. UPDATE appointments SET plan_item_id = item_id
   d. Por cada appointment con payment verificado: INSERT treatment_plan_payment + accounting_transaction
4. Recalcular estimated_total del plan
5. Emitir TREATMENT_PLAN_CREATED socket event
6. Retornar plan_id, counts

**Criterios de aceptación**:
- [ ] Crea plan con items correspondientes a cada tratamiento
- [ ] Appointments quedan vinculados (plan_item_id set)
- [ ] Pagos verificados se migran como treatment_plan_payments
- [ ] accounting_transactions sync (sin duplicar)
- [ ] Si ya tiene plan activo → 409
- [ ] Si no tiene turnos → 422
- [ ] Transacción: si falla, nada se commitea

---

### Tarea 1.3 — Budget service + PDF template

**Archivos nuevos**:
- `orchestrator_service/services/budget_service.py`
- `orchestrator_service/templates/budget/presupuesto.html`

**Implementación budget_service.py**:
1. `gather_budget_data(pool, plan_id, tenant_id)` — queries plan + items + payments + clinic + patient
2. `generate_budget_pdf(plan_id, tenant_id)` — Jinja2 render + WeasyPrint (en asyncio.to_thread)
3. Cache en `/app/uploads/budgets/{tenant_id}/{plan_id}.pdf`

**Implementación presupuesto.html**:
- Header: logo clínica + datos
- Datos paciente: nombre, DNI, teléfono
- Tabla tratamientos: nombre | estimado | final | estado
- Totales: estimado, aprobado, pagado, pendiente
- Condiciones de pago
- Firma profesional + firma paciente
- Footer: fecha generación

**Criterios de aceptación**:
- [ ] PDF se genera sin errores
- [ ] Logo se muestra si tenant tiene logo_url
- [ ] Tabla de items correcta con precios formateados
- [ ] Totales cuadran (estimated_total, approved_total, paid, pending)
- [ ] PDF se cachea en disco

---

### Tarea 1.4 — EP-NEW-03 + EP-NEW-04: PDF download + email

**Archivo**: `orchestrator_service/admin_routes.py` + `orchestrator_service/email_service.py`

**Implementación EP-NEW-03** (POST /treatment-plans/{id}/generate-pdf):
1. Llamar budget_service.generate_budget_pdf()
2. Retornar FileResponse con PDF
3. Filename: `Presupuesto_{patient_name}.pdf`

**Implementación EP-NEW-04** (POST /treatment-plans/{id}/send-email):
1. Generar PDF (lazy, reusar cache)
2. Llamar email_service.send_budget_email()
3. Retornar success

**Implementación send_budget_email**:
1. Agregar método en email_service.py
2. Subject: "Presupuesto de tratamiento — {clinic_name}"
3. Body HTML simple + PDF adjunto
4. Patrón MIMEMultipart igual que digital records

**Criterios de aceptación**:
- [ ] PDF se descarga con nombre correcto
- [ ] Email llega con PDF adjunto
- [ ] Si PDF no existe, se genera on-the-fly
- [ ] Error de email no crashea (HTTP 500 con mensaje)

---

## FASE 2: FRONTEND — BillingTab rediseño

### Tarea 2.1 — Estado 2: appointments_only view

**Archivo**: `frontend_react/src/components/BillingTab.tsx`

**Implementación**:
1. Nuevo state: `billingData` que almacena response de billing-summary
2. useEffect on mount: `GET /admin/patients/{id}/billing-summary`
3. Decisión de estado:
   - `billingData.has_active_plan` → cargar plan detail (estado 3 existente)
   - `billingData.appointments.length > 0` → estado 2
   - else → estado 1
4. Renderizar TreatmentGroupCards (inline, no componente separado):
   - Card por tratamiento con appointments listados
   - Badge de receipt status (verified/pending/review)
   - Totales por grupo + totales globales
5. Botón "Generar presupuesto desde turnos" (primario)
6. Botón "Crear presupuesto vacío" (secundario)

**Criterios de aceptación**:
- [ ] Paciente con turnos ve resumen agrupado (no "No hay presupuestos")
- [ ] Comprobantes verificados muestran badge verde con monto
- [ ] Totales son correctos
- [ ] Mobile: cards stack vertical, full width

---

### Tarea 2.2 — Botón "Generar presupuesto desde turnos"

**Archivo**: `frontend_react/src/components/BillingTab.tsx`

**Implementación**:
1. Click → confirm dialog ("Se creará un presupuesto con los turnos existentes. ¿Continuar?")
2. POST /admin/patients/{id}/generate-plan-from-appointments
3. On success → reload billing-summary → auto-seleccionar el plan creado
4. Loading state en el botón
5. Error handling (409 si ya tiene plan, 422 si no tiene turnos)

**Criterios de aceptación**:
- [ ] Genera plan y transiciona a estado 3 (plan_view)
- [ ] Items aparecen con tratamientos y precios pre-llenados
- [ ] Pagos migrados aparecen en la tabla de pagos
- [ ] Si ya tiene plan → muestra error toast

---

### Tarea 2.3 — Botones PDF + Email en plan_view

**Archivo**: `frontend_react/src/components/BillingTab.tsx`

**Implementación**:
1. En el header del plan (estado 3), agregar botones:
   - "Generar PDF" → POST /generate-pdf → blob download
   - "Enviar email" → abre modal con input email → POST /send-email
2. Loading spinners durante generación
3. Modal de email pre-llena con patient email

**Criterios de aceptación**:
- [ ] PDF se descarga correctamente
- [ ] Email se envía con confirmación visual
- [ ] Loading state visible durante generación
- [ ] Modal es bottom-sheet en mobile

---

### Tarea 2.4 — i18n keys nuevas

**Archivos**: `es.json`, `en.json`, `fr.json`

Agregar todas las keys de spec-frontend.md:
- billing.no_activity, no_activity_desc
- billing.appointments_summary
- billing.generate_from_appointments
- billing.receipt_verified, receipt_pending, receipt_review
- billing.generate_pdf, send_email, send_email_title, send_email_to, send_email_success
- billing.generating_pdf
- billing.plan_belongs, go_to_plan

**Criterios de aceptación**:
- [ ] Todas las keys existen en los 3 idiomas
- [ ] JSON es válido (no duplicados)

---

## FASE 3: MODAL DE TURNO

### Tarea 3.1 — AppointmentForm billing tab conditional

**Archivo**: `frontend_react/src/components/AppointmentForm.tsx`

**Implementación**:
1. Cuando se carga el appointment, verificar si tiene `plan_item_id`
2. Si tiene plan_item_id:
   - Mostrar banner: "Este turno pertenece al plan [nombre]"
   - Botón "Ver presupuesto completo" que navega a PatientDetail pestaña 6
   - Campos de billing en read-only (monto, estado, receipt card)
3. Si NO tiene plan_item_id:
   - Mantener comportamiento actual (editable)

**Criterios de aceptación**:
- [ ] Turno con plan → billing read-only + link al plan
- [ ] Turno sin plan → editable como siempre
- [ ] Botón navega correctamente a PatientDetail#billing

---

## FASE 4: TESTS

### Tarea 4.1 — Tests backend

**Archivo**: `tests/test_billing_smart_hub.py`

Tests para:
- billing-summary endpoint (con y sin turnos, con y sin plan)
- generate-plan-from-appointments (happy path, 409, 422)
- gather_budget_data (data structure)
- Migración de pagos (solo verificados, sin duplicar)

### Tarea 4.2 — Tests frontend (lógica)

Tests para:
- Estado detection logic (empty, appointments_only, plan_view)
- Treatment group aggregation
- Receipt status badge mapping
- Total calculations

---

## Dependency Graph

```
1.1 (billing-summary) ──→ 2.1 (appointments_only view)
                     └──→ 2.2 (generate button)
1.2 (generate-plan)  ──→ 2.2 (generate button)
1.3 (budget service)  ──→ 1.4 (PDF + email endpoints)
1.4 (PDF + email)    ──→ 2.3 (PDF + email buttons)
2.4 (i18n) ── independent
3.1 (modal) ── independent (after 2.1)
4.x (tests) ── after all
```

## Execution Order

1. **Batch 1** (paralelo): Tarea 1.1 + 1.3 + 2.4 — endpoint summary + budget service + i18n
2. **Batch 2** (paralelo): Tarea 1.2 + 1.4 — generate-plan + PDF endpoints
3. **Batch 3**: Tarea 2.1 + 2.2 + 2.3 — frontend rediseño completo
4. **Batch 4**: Tarea 3.1 — modal conditional
5. **Batch 5**: Tarea 4.1 + 4.2 — tests
