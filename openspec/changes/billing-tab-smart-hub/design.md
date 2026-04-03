# Design: Billing Tab Smart Hub

**Change**: billing-tab-smart-hub
**Date**: 2026-04-03

---

## Architecture Decisions

### AD-01: billing-summary como endpoint separado (no reusar calendar)

**Decisión**: Crear `GET /admin/patients/{id}/billing-summary` nuevo en vez de filtrar el endpoint de calendario.

**Rationale**: El endpoint de calendario no filtra por patient_id, filtra por date range + professional. Un endpoint dedicado es más eficiente (1 query vs filtro client-side) y retorna datos pre-agrupados por tratamiento.

**Tradeoff**: Un endpoint más que mantener. Pero es read-only y simple.

---

### AD-02: generate-plan-from-appointments como operación atómica

**Decisión**: Un solo endpoint que crea plan + items + vincula appointments + migra pagos, todo en una transacción DB.

**Rationale**: Si algo falla a mitad (ej: vincular appointment #3 de 5), el paciente queda con un plan incompleto. La transacción garantiza todo-o-nada.

**Pattern**:
```python
async with pool.acquire() as conn:
    async with conn.transaction():
        plan_id = await conn.fetchval("INSERT INTO treatment_plans ...")
        for group in treatment_groups:
            item_id = await conn.fetchval("INSERT INTO treatment_plan_items ...")
            for apt in group.appointments:
                await conn.execute("UPDATE appointments SET plan_item_id = $1 ...", item_id)
            # Migrate verified payments
```

---

### AD-03: PDF sigue patrón exact de Digital Records

**Decisión**: Reusar la misma infraestructura de WeasyPrint + FileResponse + email que usa DigitalRecordsTab.

**Rationale**: No reinventar la rueda. El pattern ya maneja: generación async, cache en disco, lazy regeneration, email con adjunto SMTP.

**Diferencia**: El presupuesto NO usa IA para generar narrativa (a diferencia de fichas clínicas). Es puro data → template → PDF.

---

### AD-04: BillingTab carga billing-summary SIEMPRE como primer fetch

**Decisión**: Al montar la pestaña, SIEMPRE llamar a `/billing-summary` primero. Si `has_active_plan`, cargar el plan detail también. Si no, mostrar estado 2 (appointments).

**Rationale**: Esto garantiza que:
- Turnos existentes siempre se muestran (aunque no haya plan)
- Si hay plan, se carga en paralelo
- El componente nunca muestra "vacío" cuando hay data

**Flow**:
```
Mount → GET /billing-summary
  ├── has_active_plan=true → GET /treatment-plans/{id} → Estado 3
  ├── appointments.length > 0 → Estado 2
  └── appointments.length === 0 → Estado 1
```

---

### AD-05: Migración de pagos: solo verificados, sin duplicar

**Decisión**: Al generar plan desde turnos, solo migrar pagos de appointments con `payment_receipt_data.status = 'verified'` o `'verified_manual'`. Verificar que no exista ya en `treatment_plan_payments` antes de crear.

**Rationale**: No queremos:
- Migrar pagos pendientes (no confirmados)
- Duplicar un pago que ya se registró manualmente en el plan
- Crear accounting_transactions duplicados

**Check**:
```python
existing = await conn.fetchval(
    "SELECT id FROM treatment_plan_payments WHERE plan_id=$1 AND notes LIKE $2",
    plan_id, f"%migrated:apt:{apt_id}%"
)
if not existing:
    # Crear payment con notes="migrated:apt:{apt_id}"
```

---

### AD-06: AppointmentForm billing tab — conditional render, no eliminar

**Decisión**: No eliminar la pestaña Facturación del modal. Hacerla read-only cuando `plan_item_id` exists, y mostrar link al plan.

**Rationale**: Eliminar la pestaña rompe el flujo para turnos que NO están en planes. Mantener ambos modos con un flag.

---

### AD-07: Budget service como módulo separado

**Decisión**: Crear `orchestrator_service/services/budget_service.py` para gather_budget_data + generate_budget_pdf.

**Rationale**: Separar de digital_records_service.py porque:
- No usa IA (no hay narrative generation)
- Template diferente
- Datos diferentes (plan, items, payments vs clinical records)

---

## File Change Map

### Nuevos archivos
```
orchestrator_service/services/budget_service.py       — gather_budget_data, generate_budget_pdf
orchestrator_service/templates/budget/presupuesto.html — Jinja2 template
```

### Archivos modificados
```
orchestrator_service/admin_routes.py                   — 4 endpoints nuevos
orchestrator_service/email_service.py                  — send_budget_email
frontend_react/src/components/BillingTab.tsx            — Rediseño completo (3 estados)
frontend_react/src/components/AppointmentForm.tsx       — Billing tab conditional
frontend_react/src/locales/es.json                     — i18n keys nuevas
frontend_react/src/locales/en.json                     — i18n keys nuevas
frontend_react/src/locales/fr.json                     — i18n keys nuevas
```

### No se tocan
```
orchestrator_service/services/digital_records_service.py  — patrón de referencia, no se modifica
orchestrator_service/models.py                            — no se agregan tablas
orchestrator_service/alembic/                             — no hay migración nueva
```
