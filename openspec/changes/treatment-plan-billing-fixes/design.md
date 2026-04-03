# Design: Treatment Plan Billing — Fixes & Stabilization

**Change**: treatment-plan-billing-fixes
**Date**: 2026-04-03

---

## Architecture Decisions

### AD-01: Migration correctiva (019) en vez de recrear 018

**Decisión**: Crear migration 019 con ALTER TABLE statements para corregir tipos de columna, agregar constraints, y renombrar índices. NO reescribir 018.

**Rationale**: La migration 018 ya puede estar aplicada en entornos de staging/dev. Reescribirla rompería el chain de Alembic. Una migration correctiva es segura e idempotente.

**Tradeoff**: Dos migraciones donde podría haber una. Pero es más seguro.

---

### AD-02: approved_by y recorded_by se mantienen como VARCHAR

**Decisión**: Mantener `approved_by` y `recorded_by` como `VARCHAR(100)` almacenando email del usuario. NO cambiar a INT FK.

**Rationale**:
- La tabla `users` usa Auth0 IDs, no enteros secuenciales
- Almacenar email es más legible en queries directas y exports
- No requiere JOIN adicional para mostrar quién aprobó/registró
- Consistente con el patrón de `user_data.email` que ya usa el backend

**Tradeoff**: Sin integridad referencial por FK. Aceptable porque es campo de auditoría, no de negocio.

**Spec update**: Actualizar spec-database.md para reflejar VARCHAR(100) como tipo canónico.

---

### AD-03: payment_date cambia a TIMESTAMPTZ

**Decisión**: ALTER payment_date de DATE a TIMESTAMPTZ.

**Rationale**: Se necesita la hora exacta del pago para:
- today_revenue con timezone Argentina
- Ordenar pagos del mismo día
- Auditoría temporal precisa

**Migration**: `ALTER COLUMN payment_date TYPE TIMESTAMPTZ USING payment_date::timestamptz; ALTER COLUMN payment_date SET DEFAULT NOW();`

---

### AD-04: EP-09 usa transacción explícita

**Decisión**: Envolver los 3 writes (payment INSERT, accounting_transaction INSERT, plan status UPDATE) en `async with conn.transaction()`.

**Rationale**: Atomicidad. Si cualquier write falla, todos se revierten. Sin transacción, un fallo parcial deja datos inconsistentes.

**Pattern**:
```python
async with pool.acquire() as conn:
    async with conn.transaction():
        await conn.execute("INSERT INTO treatment_plan_payments ...")
        await conn.execute("INSERT INTO accounting_transactions ...")
        if should_advance:
            await conn.execute("UPDATE treatment_plans SET status = ...")
```

---

### AD-05: Items status CHECK incluye 'in_progress'

**Decisión**: Agregar 'in_progress' al CHECK constraint de treatment_plan_items.status.

**Migration**: DROP constraint + CREATE constraint con 4 valores.

---

### AD-06: BillingTab responsive con breakpoint md

**Decisión**: Items y payments usan table layout en `md:` y card layout en mobile. Modals usan bottom-sheet en mobile.

**Pattern**:
```tsx
{/* Desktop table */}
<table className="hidden md:table">...</table>

{/* Mobile cards */}
<div className="md:hidden space-y-3">
  {items.map(item => <ItemCard key={item.id} />)}
</div>
```

---

### AD-07: verify_payment_receipt priority chain

**Decisión**: Plan check se ejecuta DESPUÉS de billing_amount pero ANTES de los fallbacks genéricos (professional_price, treatment_price, tenant_price).

**Cadena final**:
1. `appointment.billing_amount` → si > 0, usar (appointment context)
2. **Plan pending balance** → si > 0, usar (plan context) ← NUEVO
3. `professional.consultation_price` × 50% → fallback
4. `treatment_type.base_price` × 50% → fallback
5. `tenant.consultation_price` × 50% → fallback

---

## File Change Map

### Migration 019 (nueva)
```
orchestrator_service/alembic/versions/019_treatment_plan_billing_fixes.py
```
- ALTER payment_date → TIMESTAMPTZ
- DROP FK appointment_id
- ADD 7 CHECK constraints
- DROP + CREATE 4 índices con nombres correctos
- ALTER custom_description → TEXT
- ALTER name → VARCHAR(200)
- DROP + ADD item status CHECK con 'in_progress'

### Backend
```
orchestrator_service/admin_routes.py          — EP-01,03,04,05,06,07,08,09,11
orchestrator_service/schemas/treatment_plan.py — ItemStatus, CreateTreatmentPlanBody, AddPlanItemBody
orchestrator_service/services/nova_tools.py    — _registrar_pago_plan, _aprobar_presupuesto, _resumen_financiero, _resumen_semana
orchestrator_service/main.py                   — verify_payment_receipt priority chain
orchestrator_service/analytics_service.py      — liquidation output fields
```

### Frontend
```
frontend_react/src/components/BillingTab.tsx   — notas column, notas modal field, responsive mobile
frontend_react/src/locales/es.json             — 15+ keys corregidas
frontend_react/src/locales/en.json             — keys correspondientes
frontend_react/src/locales/fr.json             — keys correspondientes
```

### Tests
```
tests/test_treatment_plan_fixes.py             — Tests para cada fix CRITICAL
```
