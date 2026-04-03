# Spec: Database Migration — Treatment Plan Billing

**Change**: treatment-plan-billing
**Artifact**: spec-database
**Migration number**: 018
**Status**: Draft
**Date**: 2026-04-03
**Depends on**: migration 017 (odontogram_v3_format)

---

## Índice

1. [Contexto y alcance](#1-contexto-y-alcance)
2. [Requerimientos funcionales](#2-requerimientos-funcionales)
3. [Decisiones arquitectónicas](#3-decisiones-arquitectónicas)
4. [Esquema de tablas](#4-esquema-de-tablas)
5. [Índices](#5-índices)
6. [Reglas de integridad de datos](#6-reglas-de-integridad-de-datos)
7. [Escenarios](#7-escenarios)
8. [Migration SQL (upgrade)](#8-migration-sql-upgrade)
9. [Downgrade path](#9-downgrade-path)
10. [Checklist de validación](#10-checklist-de-validación)

---

## 1. Contexto y alcance

El modelo de billing actual vive en `appointments`: cada turno tiene `billing_amount`, `payment_status`, `billing_installments`, `billing_notes`. Este modelo es correcto para pagos por sesión, pero no soporta:

- Un presupuesto global que agrupe N tratamientos
- Precio estimado vs. precio final aprobado por la Dra. (siempre difieren)
- Pagos parciales registrados manualmente (seña en efectivo, cuotas)
- Progreso financiero a nivel de plan: cuánto se pagó, cuánto falta

Esta migración introduce el modelo `TreatmentPlan → TreatmentPlanItem → TreatmentPlanPayment` y agrega la FK opcional `appointments.plan_item_id` para vincular turnos a ítems de un plan.

**Backward compatibility**: La columna `appointments.billing_amount` NO se elimina. Los turnos sin `plan_item_id` siguen usando el modelo existente. Esta coexistencia es intencional (ver AD-003).

---

## 2. Requerimientos funcionales

### RF-DB-001: Tabla `treatment_plans`

- La tabla representa un presupuesto/plan de tratamiento para un paciente.
- Cada plan pertenece a exactamente un `tenant_id` y un `patient_id`.
- El campo `professional_id` es opcional: permite asignar un profesional principal, pero un plan puede ser multi-profesional (los ítems tienen su propio FK de tratamiento que resuelve el profesional por `treatment_types`).
- `estimated_total` es calculado (suma de `treatment_plan_items.estimated_price`); se persiste como desnormalización para rendimiento en listados. La capa de negocio es responsable de mantenerlo sincronizado.
- `approved_total` es el precio final acordado con el paciente. La Dra. siempre ajusta — puede ser menor o mayor que `estimated_total`.
- Un plan en estado `draft` puede editarse libremente. Una vez en `approved`, el precio queda bloqueado (regla de negocio, no constraint de DB).
- `status` acepta exactamente: `draft`, `approved`, `in_progress`, `completed`, `cancelled`.

### RF-DB-002: Tabla `treatment_plan_items`

- Cada ítem representa un tratamiento individual dentro del plan.
- `treatment_type_code` es una FK conceptual (no enforced con FOREIGN KEY constraint) a `treatment_types.code`. Puede ser NULL si el ítem es completamente libre (`custom_description`).
- `custom_description` permite que la Dra. escriba texto libre como "Implante pieza 36 (Straumann BL 4.1x10)".
- Al menos uno de `treatment_type_code` o `custom_description` debe tener valor — validación en la capa de aplicación, no en DB (ver AD-004).
- `approved_price` NULL significa que el ítem no fue aprobado individualmente; en ese caso el aprobado se toma del `treatment_plans.approved_total` (regla de negocio).
- `sort_order` permite que la UI muestre los ítems en el orden que quiso la Dra.
- `status` acepta exactamente: `pending`, `in_progress`, `completed`, `cancelled`.
- Cada ítem puede vincularse a N turnos vía `appointments.plan_item_id`.

### RF-DB-003: Tabla `treatment_plan_payments`

- Registra cada pago recibido contra un plan de tratamiento.
- `amount` es siempre positivo — no se registran negativos (créditos o devoluciones van como nuevo ítem con nota).
- `payment_method` acepta: `cash`, `transfer`, `card`, `insurance`.
- `appointment_id` es una FK opcional a `appointments.id` (tipo UUID). No tiene FOREIGN KEY constraint en DB porque `appointments.id` puede ser INT o UUID según la versión — ver AD-005.
- `receipt_data` almacena el JSONB del comprobante cuando `payment_method = 'transfer'`. Estructura esperada: `{"holder_name": str, "amount": float, "verified": bool, "raw_text": str}`.
- `recorded_by` es el `users.id` del staff que registra el pago. NULL si fue registrado por sistema/bot.

### RF-DB-004: Columna `appointments.plan_item_id`

- FK nullable que apunta a `treatment_plan_items.id`.
- `ON DELETE SET NULL`: si se elimina el ítem del plan, el turno no se borra — queda desvinculado.
- Un turno puede no pertenecer a ningún plan (`plan_item_id IS NULL`), en cuyo caso su billing se maneja por `billing_amount` (modelo legacy).
- Un turno con `plan_item_id != NULL` se considera parte de un plan y el ingreso debe contabilizarse via `treatment_plan_payments`, no via `billing_amount`.

---

## 3. Decisiones arquitectónicas

### AD-001: UUID como PK en tablas nuevas, INT en tablas existentes

**Decisión**: Las tres tablas nuevas usan `UUID DEFAULT gen_random_uuid()` como PK. Las FK a tablas existentes (`tenants`, `patients`, `professionals`, `users`) siguen siendo `INT`.

**Rationale**: Las tablas existentes tienen PKs enteras (convención del proyecto). Cambiarlas requeriría una migración masiva fuera de scope. Las tablas nuevas usan UUID desde el inicio para alinearse con la dirección arquitectónica del proyecto (ver `appointments.id` que ya pasó a UUID en versiones recientes) y para facilitar imports/exports sin colisiones.

**Tradeoff aceptado**: Tipos mixtos en las FK. `treatment_plan_payments.appointment_id` es UUID, `treatment_plan_payments.plan_id` es UUID — consistente dentro de las tablas nuevas.

### AD-002: `tenant_id` redundante en `treatment_plan_items` y `treatment_plan_payments`

**Decisión**: Ambas tablas hijas tienen su propio `tenant_id INT NOT NULL`, aunque podrían derivarlo de la tabla padre (`treatment_plans.tenant_id`).

**Rationale**: Patrón establecido en el proyecto (ver `appointments`, `clinical_records`, etc.). Permite queries directas con filtro `tenant_id` sin JOIN obligatorio. Crítico para aislamiento multi-tenant: nunca confiar en que el JOIN al padre resuelva el tenant — un bug en la app podría crear un ítem referenciando un plan de otro tenant si la FK no lo previene. Con `tenant_id` en cada tabla, el `WHERE tenant_id = $x` en cada query es auto-suficiente.

**Tradeoff aceptado**: Leve redundancia de dato. Se acepta por seguridad.

### AD-003: Coexistencia con `appointments.billing_amount`

**Decisión**: No se elimina `billing_amount` ni `payment_status` de `appointments`. Los dos modelos coexisten.

**Rationale**: Turnos sin plan (consulta de guardia, control rápido, etc.) deben poder tener billing sin crear un plan completo. Eliminar el modelo existente requeriría una migración de datos riesgosa y breaking changes en toda la capa de métricas. La regla de negocio es: si `plan_item_id IS NOT NULL`, el ingreso vive en `treatment_plan_payments`; si `plan_item_id IS NULL`, vive en `billing_amount`. La capa de aplicación y las queries de métricas deben respetar esta distinción.

**Tradeoff aceptado**: Dos fuentes de ingresos en la DB. La capa de métricas debe hacer UNION o SUM condicional. Se documenta explícitamente para evitar doble-conteo.

### AD-004: `treatment_type_code` como FK conceptual, sin FOREIGN KEY constraint

**Decisión**: `treatment_plan_items.treatment_type_code` no tiene `REFERENCES treatment_types(code)`.

**Rationale**: `treatment_types.code` es un `VARCHAR` y la tabla puede tener tratamientos archivados o eliminados lógicamente. Un FOREIGN KEY hard bloquearia la eliminación de tipos de tratamiento que ya tienen items históricos. La integridad se mantiene en la capa de aplicación: al crear un ítem, se valida que el código exista; si se archiva un tipo, los items existentes conservan el código como referencia histórica.

**Tradeoff aceptado**: Sin enforcement a nivel DB. Compensado por validación en aplicación y la presencia de `custom_description` como alternativa.

### AD-005: `treatment_plan_payments.appointment_id` sin FOREIGN KEY constraint

**Decisión**: La columna `appointment_id UUID NULL` no tiene `REFERENCES appointments(id)`.

**Rationale**: La tabla `appointments` usa un tipo mixto de ID a lo largo de la historia del proyecto. En alguna versión los IDs son enteros, en otras son UUIDs. Para evitar un constraint que falle en runtime por mismatch de tipos, se deja como referencia soft. La integridad se valida en la capa de aplicación antes de insertar.

**Tradeoff aceptado**: Sin enforcement a nivel DB para este FK puntual. Todos los demás FKs de las tablas nuevas sí están enforced.

### AD-006: `estimated_total` desnormalizado en `treatment_plans`

**Decisión**: Se persiste la suma de `estimated_price` de ítems como columna en `treatment_plans` en lugar de calcularlo on-the-fly.

**Rationale**: Los listados de planes (por paciente, por tenant) necesitan mostrar el total sin hacer un SUM con JOIN en cada request. La desnormalización es un patrón explícito del proyecto (ver `appointments` con campos calculados). La capa de negocio debe actualizar `estimated_total` y `updated_at` del plan cada vez que se crea, edita o elimina un ítem.

**Tradeoff aceptado**: Posible inconsistencia si un ítem se modifica por fuera de la lógica de negocio estándar (ej. script de data fix). Se acepta para el dominio actual.

### AD-007: No hay tabla de estados/historial de planes

**Decisión**: El estado del plan se almacena como un campo simple `VARCHAR`, sin tabla de auditoría de transiciones.

**Rationale**: El dominio actual no requiere auditar cada cambio de estado con timestamp y actor. Si en el futuro se necesita (ej. "quién aprobó y cuándo"), la columna `approved_by`/`approved_at` cubre el caso más crítico (aprobación). Para el resto, el campo `updated_at` del plan es suficiente en esta etapa.

**Tradeoff aceptado**: Sin historial completo de transiciones de estado. Suficiente para MVP.

---

## 4. Esquema de tablas

### 4.1 `treatment_plans`

```sql
CREATE TABLE treatment_plans (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        INT          NOT NULL REFERENCES tenants(id),
    patient_id       INT          NOT NULL REFERENCES patients(id),
    professional_id  INT          NULL     REFERENCES professionals(id),
    name             VARCHAR(200) NOT NULL,
    status           VARCHAR(20)  NOT NULL DEFAULT 'draft',
    estimated_total  DECIMAL(12,2)         DEFAULT 0,
    approved_total   DECIMAL(12,2)         NULL,
    approved_by      INT          NULL     REFERENCES users(id),
    approved_at      TIMESTAMPTZ           NULL,
    notes            TEXT,
    created_at       TIMESTAMPTZ           NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ           NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_treatment_plans_status
        CHECK (status IN ('draft', 'approved', 'in_progress', 'completed', 'cancelled')),
    CONSTRAINT chk_treatment_plans_estimated_total
        CHECK (estimated_total >= 0),
    CONSTRAINT chk_treatment_plans_approved_total
        CHECK (approved_total IS NULL OR approved_total >= 0),
    CONSTRAINT chk_treatment_plans_approved_consistency
        CHECK (
            (approved_by IS NULL AND approved_at IS NULL) OR
            (approved_by IS NOT NULL AND approved_at IS NOT NULL)
        )
);
```

**Campos clave:**

| Campo | Tipo | Nulable | Descripción |
|-------|------|---------|-------------|
| `id` | UUID | NO | PK generado por `gen_random_uuid()` |
| `tenant_id` | INT | NO | FK a `tenants.id` — aislamiento multi-tenant |
| `patient_id` | INT | NO | FK a `patients.id` — dueño del plan |
| `professional_id` | INT | SI | FK a `professionals.id` — profesional principal del plan |
| `name` | VARCHAR(200) | NO | Nombre del plan: "Rehabilitación oral 2026" |
| `status` | VARCHAR(20) | NO | Estado del plan — ver check constraint |
| `estimated_total` | DECIMAL(12,2) | NO | Suma desnormalizada de `items.estimated_price` |
| `approved_total` | DECIMAL(12,2) | SI | Precio final acordado con el paciente |
| `approved_by` | INT | SI | FK a `users.id` — quién aprobó |
| `approved_at` | TIMESTAMPTZ | SI | Cuándo fue aprobado |
| `notes` | TEXT | SI | Notas libres de la Dra. |
| `created_at` | TIMESTAMPTZ | NO | Timestamp de creación |
| `updated_at` | TIMESTAMPTZ | NO | Timestamp de última modificación |

---

### 4.2 `treatment_plan_items`

```sql
CREATE TABLE treatment_plan_items (
    id                    UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id               UUID         NOT NULL REFERENCES treatment_plans(id) ON DELETE CASCADE,
    tenant_id             INT          NOT NULL REFERENCES tenants(id),
    treatment_type_code   VARCHAR(50)  NULL,
    custom_description    TEXT,
    estimated_price       DECIMAL(12,2)         NOT NULL DEFAULT 0,
    approved_price        DECIMAL(12,2)         NULL,
    status                VARCHAR(20)  NOT NULL DEFAULT 'pending',
    sort_order            INT          NOT NULL DEFAULT 0,
    created_at            TIMESTAMPTZ           NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ           NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_treatment_plan_items_status
        CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    CONSTRAINT chk_treatment_plan_items_estimated_price
        CHECK (estimated_price >= 0),
    CONSTRAINT chk_treatment_plan_items_approved_price
        CHECK (approved_price IS NULL OR approved_price >= 0),
    CONSTRAINT chk_treatment_plan_items_description
        CHECK (
            treatment_type_code IS NOT NULL OR
            (custom_description IS NOT NULL AND custom_description <> '')
        )
);
```

**Campos clave:**

| Campo | Tipo | Nulable | Descripción |
|-------|------|---------|-------------|
| `id` | UUID | NO | PK generado por `gen_random_uuid()` |
| `plan_id` | UUID | NO | FK a `treatment_plans.id` — CASCADE DELETE |
| `tenant_id` | INT | NO | FK a `tenants.id` — redundante por aislamiento |
| `treatment_type_code` | VARCHAR(50) | SI | Código del tipo de tratamiento (FK conceptual) |
| `custom_description` | TEXT | SI | Descripción libre — ej. "Implante pieza 36" |
| `estimated_price` | DECIMAL(12,2) | NO | Precio estimado base |
| `approved_price` | DECIMAL(12,2) | SI | Precio final aprobado para este ítem específico |
| `status` | VARCHAR(20) | NO | Estado del ítem |
| `sort_order` | INT | NO | Orden de visualización en la UI |
| `created_at` | TIMESTAMPTZ | NO | Timestamp de creación |
| `updated_at` | TIMESTAMPTZ | NO | Timestamp de última modificación |

---

### 4.3 `treatment_plan_payments`

```sql
CREATE TABLE treatment_plan_payments (
    id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id          UUID          NOT NULL REFERENCES treatment_plans(id) ON DELETE CASCADE,
    tenant_id        INT           NOT NULL REFERENCES tenants(id),
    amount           DECIMAL(12,2) NOT NULL,
    payment_method   VARCHAR(20)   NOT NULL DEFAULT 'cash',
    payment_date     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    recorded_by      INT           NULL     REFERENCES users(id),
    appointment_id   UUID          NULL,
    receipt_data     JSONB         NULL,
    notes            TEXT,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_treatment_plan_payments_amount
        CHECK (amount > 0),
    CONSTRAINT chk_treatment_plan_payments_method
        CHECK (payment_method IN ('cash', 'transfer', 'card', 'insurance'))
);
```

**Campos clave:**

| Campo | Tipo | Nulable | Descripción |
|-------|------|---------|-------------|
| `id` | UUID | NO | PK generado por `gen_random_uuid()` |
| `plan_id` | UUID | NO | FK a `treatment_plans.id` — CASCADE DELETE |
| `tenant_id` | INT | NO | FK a `tenants.id` — redundante por aislamiento |
| `amount` | DECIMAL(12,2) | NO | Monto pagado — siempre > 0 |
| `payment_method` | VARCHAR(20) | NO | Método de pago — ver check constraint |
| `payment_date` | TIMESTAMPTZ | NO | Fecha/hora del pago (default NOW) |
| `recorded_by` | INT | SI | FK a `users.id` — quién registró el pago |
| `appointment_id` | UUID | SI | Referencia soft al turno asociado (sin FK constraint) |
| `receipt_data` | JSONB | SI | Datos del comprobante de transferencia |
| `notes` | TEXT | SI | Observaciones del pago |
| `created_at` | TIMESTAMPTZ | NO | Timestamp de creación del registro |

**Estructura esperada de `receipt_data`:**

```json
{
    "holder_name": "Juan Perez",
    "amount": 15000.00,
    "verified": true,
    "raw_text": "...",
    "verified_at": "2026-04-03T14:30:00Z",
    "verified_by_tool": "verify_payment_receipt"
}
```

---

### 4.4 ALTER `appointments` — columna `plan_item_id`

```sql
ALTER TABLE appointments
    ADD COLUMN plan_item_id UUID NULL
        REFERENCES treatment_plan_items(id) ON DELETE SET NULL;
```

**Comportamiento del FK:**

- `ON DELETE SET NULL`: si se elimina un `treatment_plan_items`, los turnos vinculados quedan con `plan_item_id = NULL`. El turno NO se borra.
- `ON UPDATE NO ACTION`: cambios al PK del ítem (teórico, UUID no cambia) no propagan.
- Un turno puede tener `plan_item_id IS NULL` (sin plan, billing por `billing_amount`) o `plan_item_id != NULL` (parte de un plan, billing por `treatment_plan_payments`).

---

## 5. Índices

```sql
-- treatment_plans
CREATE INDEX idx_treatment_plans_tenant_patient
    ON treatment_plans (tenant_id, patient_id);

CREATE INDEX idx_treatment_plans_tenant_status
    ON treatment_plans (tenant_id, status);

-- treatment_plan_items
CREATE INDEX idx_treatment_plan_items_plan_id
    ON treatment_plan_items (plan_id);

CREATE INDEX idx_treatment_plan_items_tenant_code
    ON treatment_plan_items (tenant_id, treatment_type_code)
    WHERE treatment_type_code IS NOT NULL;

-- treatment_plan_payments
CREATE INDEX idx_treatment_plan_payments_plan_id
    ON treatment_plan_payments (plan_id);

CREATE INDEX idx_treatment_plan_payments_tenant_date
    ON treatment_plan_payments (tenant_id, payment_date);

-- appointments (partial index — solo filas con plan)
CREATE INDEX idx_appointments_plan_item_id
    ON appointments (plan_item_id)
    WHERE plan_item_id IS NOT NULL;
```

**Rationale por índice:**

| Índice | Justificación |
|--------|---------------|
| `(tenant_id, patient_id)` en plans | Listar todos los planes de un paciente — query más frecuente |
| `(tenant_id, status)` en plans | Filtrar por estado en panel admin: "planes en progreso del tenant X" |
| `(plan_id)` en items | Cargar ítems de un plan — siempre se accede por plan |
| `(tenant_id, treatment_type_code)` en items | Analytics: cuántos ítems de tipo "implante" hay en el tenant |
| `(plan_id)` en payments | Cargar pagos de un plan — siempre se accede por plan |
| `(tenant_id, payment_date)` en payments | Dashboard de ingresos por período |
| `(plan_item_id) WHERE IS NOT NULL` en appointments | Listar turnos de un ítem — partial para no indexar NULLs |

---

## 6. Reglas de integridad de datos

### 6.1 Aislamiento multi-tenant (CRÍTICO)

**Regla**: TODA query que acceda a estas tablas DEBE incluir `WHERE tenant_id = $x`. Sin excepción.

```python
# CORRECTO
SELECT * FROM treatment_plans WHERE id = $1 AND tenant_id = $2

# INCORRECTO — nunca hacer esto
SELECT * FROM treatment_plans WHERE id = $1
```

**Regla de creación**: Cuando se crea un `treatment_plan_item`, el `tenant_id` del ítem DEBE ser igual al `tenant_id` del plan padre. La capa de aplicación valida esto antes del INSERT.

```python
# Validación en aplicación antes de insertar ítem
if plan.tenant_id != current_tenant_id:
    raise ForbiddenError("tenant mismatch")
item.tenant_id = plan.tenant_id  # siempre del plan, nunca del request
```

**Igual para `treatment_plan_payments`**: el `tenant_id` del pago se toma del plan, nunca del request.

### 6.2 Cascadas

| Operación | Tabla padre | Efecto en hija |
|-----------|-------------|----------------|
| `DELETE treatment_plans` | `treatment_plans` | CASCADE: borra todos los `treatment_plan_items` del plan |
| `DELETE treatment_plans` | `treatment_plans` | CASCADE: borra todos los `treatment_plan_payments` del plan |
| `DELETE treatment_plan_items` | `treatment_plan_items` | SET NULL: `appointments.plan_item_id` → NULL |
| `DELETE patients` | `patients` | NO CASCADE directo — `treatment_plans` tiene FK sin cascade en `patient_id`. La lógica de negocio debe eliminar/cancelar los planes del paciente antes de eliminar el paciente. |
| `DELETE professionals` | `professionals` | SET NULL implícito — no hay cascade. La FK en `treatment_plans.professional_id` es nullable; si el profesional se elimina y hay planes activos, la DB lanza error. La aplicación debe desasignar planes antes. |

**Nota sobre eliminación de pacientes**: La tabla `patients` probablemente ya tiene FK constraints que impiden el borrado si hay registros dependientes. Esta regla es consistente con el patrón existente del proyecto.

### 6.3 Consistencia de `estimated_total`

`treatment_plans.estimated_total` debe mantenerse en sincronía con la suma de `treatment_plan_items.estimated_price` del mismo plan. Es responsabilidad de la capa de aplicación actualizar este campo en cada operación sobre ítems:

- `INSERT` en `treatment_plan_items` → `estimated_total += item.estimated_price`
- `UPDATE estimated_price` en ítem → `estimated_total += (new_price - old_price)`
- `DELETE` de ítem → `estimated_total -= item.estimated_price`
- `UPDATE status = 'cancelled'` en ítem → `estimated_total -= item.estimated_price`

Nunca recalcular con un `SUM()` full-scan en cada request de listado — usar el campo desnormalizado.

### 6.4 Regla de doble-conteo en métricas

Para calcular ingresos totales sin doble-conteo:

```sql
-- Ingresos de appointments SIN plan (modelo legacy)
SELECT SUM(billing_amount)
FROM appointments
WHERE tenant_id = $1
  AND payment_status IN ('partial', 'paid')
  AND plan_item_id IS NULL;

-- Ingresos de plans
SELECT SUM(amount)
FROM treatment_plan_payments
WHERE tenant_id = $1
  AND payment_date BETWEEN $2 AND $3;

-- Total = legacy_sum + plan_payments_sum
```

**NUNCA** sumar `appointments.billing_amount` donde `plan_item_id IS NOT NULL` — ese ingreso ya está en `treatment_plan_payments`.

### 6.5 Validación de `approved_by` / `approved_at`

El check constraint en `treatment_plans` garantiza que `approved_by` y `approved_at` sean ambos NULL o ambos NOT NULL. No puede existir un plan con fecha de aprobación pero sin aprobador, ni viceversa.

### 6.6 Monto positivo en pagos

El check constraint `amount > 0` previene pagos de $0 o negativos. No se registran devoluciones como pagos negativos — si se requiere en el futuro, se agrega una tabla `treatment_plan_refunds` separada.

---

## 7. Escenarios

### Escenario 1 — Happy path: crear y aprobar un plan

**Precondición**: paciente `p1` existe en el tenant, tiene 3 tratamientos en presupuesto.

**Flujo:**
1. Se crea un `treatment_plan` con `status='draft'`, `estimated_total=0`.
2. Se insertan 3 `treatment_plan_items`:
   - Ítem A: `treatment_type_code='IMPL'`, `estimated_price=150000`
   - Ítem B: `treatment_type_code='CORONA'`, `estimated_price=80000`
   - Ítem C: `custom_description='Extracción pieza 28'`, `estimated_price=12000`
3. Después de cada INSERT, la capa de aplicación actualiza `treatment_plans.estimated_total`.
4. `estimated_total` final: `242000`.
5. La Dra. aprueba con precio `approved_total=220000` (descuento de $22.000).
6. Se actualiza `status='approved'`, `approved_by=user_id`, `approved_at=NOW()`.

**Resultado esperado:**
- `treatment_plans.status = 'approved'`
- `treatment_plans.approved_total = 220000`
- `treatment_plans.estimated_total = 242000`
- Los 3 ítems en `status='pending'`

### Escenario 2 — Registro de pagos parciales

**Precondición**: plan `pl1` en `status='approved'`, `approved_total=220000`.

**Flujo:**
1. Seña en efectivo: INSERT en `treatment_plan_payments` con `amount=50000`, `payment_method='cash'`.
2. Primer tratamiento completado, pago por transferencia: INSERT con `amount=80000`, `payment_method='transfer'`, `receipt_data={...}`.
3. La capa de aplicación calcula: `pagado=130000`, `pendiente=90000`, `progreso=59%`.

**Resultado esperado:**
- 2 filas en `treatment_plan_payments`
- La suma de `amount` es `130000`
- El plan sigue en `status='in_progress'`
- El dashboard de ingresos del día refleja los pagos

### Escenario 3 — Vincular turno a ítem de plan

**Precondición**: ítem `item_a` (implante pieza 36), turno `apt1` creado.

**Flujo:**
1. UPDATE `appointments SET plan_item_id = 'item_a_uuid' WHERE id = 'apt1_uuid' AND tenant_id = $1`.
2. La capa de aplicación actualiza `treatment_plan_items.status = 'in_progress'` para `item_a`.
3. `treatment_plans.status` pasa a `'in_progress'` (si estaba en `'approved'`).

**Resultado esperado:**
- `appointments.plan_item_id = 'item_a_uuid'`
- `treatment_plan_items.status = 'in_progress'`
- `treatment_plans.status = 'in_progress'`

### Escenario 4 — Eliminar ítem con turnos vinculados

**Precondición**: ítem `item_b` tiene 2 turnos vinculados (`apt2`, `apt3`).

**Flujo:**
1. DELETE `treatment_plan_items WHERE id = 'item_b_uuid' AND tenant_id = $1`.
2. FK `ON DELETE SET NULL` en `appointments.plan_item_id` se activa.

**Resultado esperado:**
- `item_b` eliminado
- `appointments.plan_item_id = NULL` para `apt2` y `apt3`
- Los turnos `apt2` y `apt3` existen sin plan vinculado
- `treatment_plans.estimated_total` decrementado por `item_b.estimated_price`

### Escenario 5 — Intento de acceso cross-tenant

**Precondición**: tenant A intenta acceder a un plan del tenant B.

**Flujo:**
1. `GET /admin/treatment-plans/{plan_id}` con JWT del tenant A.
2. La aplicación ejecuta: `SELECT * FROM treatment_plans WHERE id = $1 AND tenant_id = $2` con `tenant_id = tenant_A`.
3. La query no devuelve filas (el plan existe pero pertenece a tenant B).

**Resultado esperado:**
- Respuesta 404 Not Found
- Ningún dato del tenant B expuesto

### Escenario 6 — Edge case: plan cancelado con pagos registrados

**Precondición**: plan `pl2` en `status='in_progress'` con 2 pagos totalizando `$80.000`.

**Flujo:**
1. La Dra. cancela el tratamiento: UPDATE `status='cancelled'` en `treatment_plans`.
2. Los pagos en `treatment_plan_payments` NO se eliminan — son registros contables históricos.
3. La UI muestra el plan como cancelado pero conserva el historial de pagos.

**Resultado esperado:**
- `treatment_plans.status = 'cancelled'`
- 2 filas en `treatment_plan_payments` intactas
- Los pagos aparecen en el historial contable con nota de plan cancelado

### Escenario 7 — Downgrade en producción

**Precondición**: migration 018 aplicada, hay datos en las tablas nuevas.

**Comportamiento esperado:**
- La migración de downgrade BORRA todas las tablas nuevas con sus datos.
- Esto es destructivo e irreversible.
- Se debe hacer un backup previo.
- La columna `appointments.plan_item_id` se elimina: ningún turno pierde datos críticos (la columna era nullable y no reemplazaba `billing_amount`).

---

## 8. Migration SQL (upgrade)

Archivo: `orchestrator_service/alembic/versions/018_treatment_plan_billing.py`

```python
"""treatment_plan_billing: plans, items, payments, appointments.plan_item_id

Revision ID: 018
Revises: 017
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade():
    # ─── treatment_plans ────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE treatment_plans (
            id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id        INT          NOT NULL REFERENCES tenants(id),
            patient_id       INT          NOT NULL REFERENCES patients(id),
            professional_id  INT          NULL     REFERENCES professionals(id),
            name             VARCHAR(200) NOT NULL,
            status           VARCHAR(20)  NOT NULL DEFAULT 'draft',
            estimated_total  DECIMAL(12,2)         NOT NULL DEFAULT 0,
            approved_total   DECIMAL(12,2)         NULL,
            approved_by      INT          NULL     REFERENCES users(id),
            approved_at      TIMESTAMPTZ           NULL,
            notes            TEXT,
            created_at       TIMESTAMPTZ           NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ           NOT NULL DEFAULT NOW(),

            CONSTRAINT chk_treatment_plans_status
                CHECK (status IN ('draft', 'approved', 'in_progress', 'completed', 'cancelled')),
            CONSTRAINT chk_treatment_plans_estimated_total
                CHECK (estimated_total >= 0),
            CONSTRAINT chk_treatment_plans_approved_total
                CHECK (approved_total IS NULL OR approved_total >= 0),
            CONSTRAINT chk_treatment_plans_approved_consistency
                CHECK (
                    (approved_by IS NULL AND approved_at IS NULL) OR
                    (approved_by IS NOT NULL AND approved_at IS NOT NULL)
                )
        )
    """)

    op.execute("""
        CREATE INDEX idx_treatment_plans_tenant_patient
            ON treatment_plans (tenant_id, patient_id)
    """)

    op.execute("""
        CREATE INDEX idx_treatment_plans_tenant_status
            ON treatment_plans (tenant_id, status)
    """)

    # ─── treatment_plan_items ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE treatment_plan_items (
            id                    UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            plan_id               UUID         NOT NULL REFERENCES treatment_plans(id) ON DELETE CASCADE,
            tenant_id             INT          NOT NULL REFERENCES tenants(id),
            treatment_type_code   VARCHAR(50)  NULL,
            custom_description    TEXT,
            estimated_price       DECIMAL(12,2)         NOT NULL DEFAULT 0,
            approved_price        DECIMAL(12,2)         NULL,
            status                VARCHAR(20)  NOT NULL DEFAULT 'pending',
            sort_order            INT          NOT NULL DEFAULT 0,
            created_at            TIMESTAMPTZ           NOT NULL DEFAULT NOW(),
            updated_at            TIMESTAMPTZ           NOT NULL DEFAULT NOW(),

            CONSTRAINT chk_treatment_plan_items_status
                CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
            CONSTRAINT chk_treatment_plan_items_estimated_price
                CHECK (estimated_price >= 0),
            CONSTRAINT chk_treatment_plan_items_approved_price
                CHECK (approved_price IS NULL OR approved_price >= 0),
            CONSTRAINT chk_treatment_plan_items_description
                CHECK (
                    treatment_type_code IS NOT NULL OR
                    (custom_description IS NOT NULL AND custom_description <> '')
                )
        )
    """)

    op.execute("""
        CREATE INDEX idx_treatment_plan_items_plan_id
            ON treatment_plan_items (plan_id)
    """)

    op.execute("""
        CREATE INDEX idx_treatment_plan_items_tenant_code
            ON treatment_plan_items (tenant_id, treatment_type_code)
            WHERE treatment_type_code IS NOT NULL
    """)

    # ─── treatment_plan_payments ─────────────────────────────────────────────
    op.execute("""
        CREATE TABLE treatment_plan_payments (
            id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
            plan_id          UUID          NOT NULL REFERENCES treatment_plans(id) ON DELETE CASCADE,
            tenant_id        INT           NOT NULL REFERENCES tenants(id),
            amount           DECIMAL(12,2) NOT NULL,
            payment_method   VARCHAR(20)   NOT NULL DEFAULT 'cash',
            payment_date     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            recorded_by      INT           NULL     REFERENCES users(id),
            appointment_id   UUID          NULL,
            receipt_data     JSONB         NULL,
            notes            TEXT,
            created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

            CONSTRAINT chk_treatment_plan_payments_amount
                CHECK (amount > 0),
            CONSTRAINT chk_treatment_plan_payments_method
                CHECK (payment_method IN ('cash', 'transfer', 'card', 'insurance'))
        )
    """)

    op.execute("""
        CREATE INDEX idx_treatment_plan_payments_plan_id
            ON treatment_plan_payments (plan_id)
    """)

    op.execute("""
        CREATE INDEX idx_treatment_plan_payments_tenant_date
            ON treatment_plan_payments (tenant_id, payment_date)
    """)

    # ─── appointments.plan_item_id ───────────────────────────────────────────
    op.execute("""
        ALTER TABLE appointments
            ADD COLUMN plan_item_id UUID NULL
                REFERENCES treatment_plan_items(id) ON DELETE SET NULL
    """)

    op.execute("""
        CREATE INDEX idx_appointments_plan_item_id
            ON appointments (plan_item_id)
            WHERE plan_item_id IS NOT NULL
    """)


def downgrade():
    # Orden inverso de dependencias
    op.execute("DROP INDEX IF EXISTS idx_appointments_plan_item_id")
    op.execute("ALTER TABLE appointments DROP COLUMN IF EXISTS plan_item_id")

    op.execute("DROP INDEX IF EXISTS idx_treatment_plan_payments_tenant_date")
    op.execute("DROP INDEX IF EXISTS idx_treatment_plan_payments_plan_id")
    op.execute("DROP TABLE IF EXISTS treatment_plan_payments")

    op.execute("DROP INDEX IF EXISTS idx_treatment_plan_items_tenant_code")
    op.execute("DROP INDEX IF EXISTS idx_treatment_plan_items_plan_id")
    op.execute("DROP TABLE IF EXISTS treatment_plan_items")

    op.execute("DROP INDEX IF EXISTS idx_treatment_plans_tenant_status")
    op.execute("DROP INDEX IF EXISTS idx_treatment_plans_tenant_patient")
    op.execute("DROP TABLE IF EXISTS treatment_plans")
```

---

## 9. Downgrade path

### Orden de operaciones (CRÍTICO — respetar dependencias)

El downgrade DEBE ejecutarse en este orden exacto:

```
1. DROP INDEX idx_appointments_plan_item_id
2. ALTER TABLE appointments DROP COLUMN plan_item_id
3. DROP TABLE treatment_plan_payments   (depende de treatment_plans)
4. DROP TABLE treatment_plan_items      (depende de treatment_plans; appointments depende de esto)
5. DROP TABLE treatment_plans           (padre de items y payments)
```

Si se intenta en otro orden, PostgreSQL lanzará errores de FK constraint.

### Consecuencias del downgrade

| Tabla/Columna | Datos perdidos |
|---------------|----------------|
| `treatment_plans` | Todos los planes de tratamiento |
| `treatment_plan_items` | Todos los ítems de todos los planes |
| `treatment_plan_payments` | Todos los registros de pagos via plan |
| `appointments.plan_item_id` | Vinculación turno-ítem (los turnos permanecen) |

**Datos que NO se pierden en downgrade:**
- Los turnos (`appointments`) siguen existiendo con sus campos legacy (`billing_amount`, `payment_status`).
- Los pacientes, profesionales, tipos de tratamiento — sin cambios.

### Procedimiento de rollback en producción

```bash
# 1. Backup ANTES de downgrade
pg_dump -h $DB_HOST -U $DB_USER $DB_NAME > backup_pre_downgrade_018_$(date +%Y%m%d_%H%M%S).sql

# 2. Desde orchestrator_service/
alembic downgrade 017

# 3. Verificar
alembic current  # debe mostrar 017
```

---

## 10. Checklist de validación

Antes de marcar la migration como lista para apply:

### Estructura

- [ ] Las 3 tablas nuevas existen con todos los campos especificados
- [ ] `appointments.plan_item_id` existe como UUID nullable
- [ ] Todos los CHECK constraints están presentes y son correctos
- [ ] Todos los índices están creados (7 índices nuevos + 1 partial en appointments)
- [ ] El índice partial en appointments usa `WHERE plan_item_id IS NOT NULL`

### Integridad referencial

- [ ] `treatment_plan_items.plan_id` tiene CASCADE DELETE contra `treatment_plans`
- [ ] `treatment_plan_payments.plan_id` tiene CASCADE DELETE contra `treatment_plans`
- [ ] `appointments.plan_item_id` tiene SET NULL contra `treatment_plan_items`
- [ ] `treatment_type_code` NO tiene FOREIGN KEY (intencional — FK conceptual)
- [ ] `treatment_plan_payments.appointment_id` NO tiene FOREIGN KEY (intencional)

### Multi-tenant

- [ ] Las 3 tablas nuevas tienen columna `tenant_id INT NOT NULL`
- [ ] Los índices `(tenant_id, ...)` existen en las 3 tablas nuevas
- [ ] La documentación de la regla de aislamiento está en CLAUDE.md / README del change

### Downgrade

- [ ] `downgrade()` elimina tablas en el orden correcto (payments → items → plans)
- [ ] `downgrade()` usa `IF EXISTS` para ser idempotente
- [ ] `downgrade()` elimina `appointments.plan_item_id` antes de eliminar `treatment_plan_items`

### Alembic

- [ ] `revision = '018'`
- [ ] `down_revision = '017'`
- [ ] El archivo se llama `018_treatment_plan_billing.py`
- [ ] `alembic upgrade head` aplicada en entorno de dev sin errores
- [ ] `alembic downgrade 017` ejecutada post-apply sin errores
- [ ] `alembic upgrade head` re-aplicada después del downgrade — idempotente

---

*Spec generado: 2026-04-03 — treatment-plan-billing/spec-database*
