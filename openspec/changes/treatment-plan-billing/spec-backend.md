# Spec Backend — Treatment Plan Billing

**Change**: `treatment-plan-billing`
**Artifact**: `spec-backend`
**Status**: Draft
**Fecha**: 2026-04-03
**Depende de**: `proposal.md`

---

## Índice

1. [Contexto y Alcance](#1-contexto-y-alcance)
2. [Convenciones Globales](#2-convenciones-globales)
3. [Modelo de Datos (referencia)](#3-modelo-de-datos-referencia)
4. [FR-01 — Treatment Plans CRUD](#4-fr-01--treatment-plans-crud)
5. [FR-02 — Plan Items CRUD](#5-fr-02--plan-items-crud)
6. [FR-03 — Payments](#6-fr-03--payments)
7. [FR-04 — Appointment Linking](#7-fr-04--appointment-linking)
8. [Eventos Socket.IO](#8-eventos-socketio)
9. [Reglas de Aislamiento Multi-Tenant](#9-reglas-de-aislamiento-multi-tenant)
10. [Decisiones Arquitectónicas](#10-decisiones-arquitectónicas)
11. [Errores Estándar](#11-errores-estándar)

---

## 1. Contexto y Alcance

Este spec cubre **exclusivamente los endpoints backend** del sistema de planes de tratamiento y facturación. Todos los endpoints viven en `orchestrator_service/admin_routes.py`, bajo el router existente `APIRouter(prefix="/admin")`.

### Stack
- **Framework**: FastAPI con `async/await`
- **DB Driver**: `asyncpg` — queries raw SQL con parámetros posicionales `$1, $2, ...`
- **Auth**: `Depends(verify_admin_token)` en todos los endpoints
- **tenant_id**: siempre extraído desde el JWT vía `Depends(get_resolved_tenant_id)` — **NUNCA** de query params ni del body
- **Tiempo real**: Socket.IO a través de `request.app.state.emit_appointment_event`

### Lo que NO cubre este spec
- Migración Alembic (spec separado o incluido en design)
- Frontend React (spec separado)
- Nova AI tools
- Generación de PDF de presupuesto

---

## 2. Convenciones Globales

### 2.1 Autenticación

Todos los endpoints usan el patrón existente:

```python
user_data=Depends(verify_admin_token),
tenant_id: int = Depends(get_resolved_tenant_id),
```

`user_data` expone: `user_data.id` (int), `user_data.role` (str), `user_data.tenant_id` (int).

### 2.2 Queries SQL

Raw asyncpg. Parámetros siempre posicionales:

```python
row = await db.pool.fetchrow(
    "SELECT id FROM treatment_plans WHERE id = $1 AND tenant_id = $2",
    plan_id, tenant_id
)
```

Nunca f-strings con valores de usuario. Los f-strings solo se usan para construir fragmentos de cláusulas fijas (ej: `ORDER BY`, intervalos de fecha ya validados internamente).

### 2.3 IDs

- `treatment_plans.id`, `treatment_plan_items.id`, `treatment_plan_payments.id`: **UUID** — se generan con `str(uuid.uuid4())` en Python antes del INSERT.
- `patients.id`, `users.id`, `professionals.id`: **INT**.

### 2.4 Serialización de respuestas

asyncpg retorna `Record` objects. Convertir a `dict` antes de retornar:

```python
return dict(row)
# o para listas:
return [dict(r) for r in rows]
```

Campos `DECIMAL` se retornan como `Decimal` de Python — deben convertirse a `float` al serializar si FastAPI no los maneja automáticamente. Campos `UUID` se convierten a `str`.

### 2.5 Emit Socket.IO

Usar el helper existente:

```python
async def emit_appointment_event(event_type: str, data: dict, request: Request):
    if hasattr(request.app.state, "emit_appointment_event"):
        await request.app.state.emit_appointment_event(event_type, data)
```

Siempre en bloque `try/except` para no romper la respuesta HTTP si el socket falla:

```python
try:
    await emit_appointment_event("TREATMENT_PLAN_UPDATED", payload, request)
except Exception as e:
    logger.warning(f"Socket emit failed: {e}")
```

### 2.6 Tags FastAPI

Todos los endpoints de este feature usan `tags=["Planes de Tratamiento"]`.

---

## 3. Modelo de Datos (referencia)

Definición completa en el spec de migración. Aquí se listan solo las columnas relevantes para validación y lógica de endpoints.

### treatment_plans
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | UUID PK | |
| `tenant_id` | INT FK | Aislamiento multi-tenant |
| `patient_id` | INT FK | |
| `professional_id` | INT FK NULL | Profesional principal del plan |
| `name` | VARCHAR(200) NOT NULL | |
| `status` | VARCHAR(20) | `draft` / `approved` / `in_progress` / `completed` / `cancelled` |
| `estimated_total` | DECIMAL(12,2) | Computado: SUM de `items.estimated_price` |
| `approved_total` | DECIMAL(12,2) NULL | Precio final aprobado por la Dra. |
| `approved_by` | INT FK NULL | `users.id` |
| `approved_at` | TIMESTAMPTZ NULL | |
| `notes` | TEXT NULL | |
| `created_at` | TIMESTAMPTZ | `DEFAULT NOW()` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT NOW()` |

### treatment_plan_items
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | UUID PK | |
| `plan_id` | UUID FK | |
| `tenant_id` | INT FK | |
| `treatment_type_code` | VARCHAR(50) NULL | FK conceptual a `treatment_types.code` |
| `custom_description` | TEXT NOT NULL | Descripción libre del ítem |
| `estimated_price` | DECIMAL(12,2) NULL | Pre-cargado desde `treatment_types.base_price` |
| `approved_price` | DECIMAL(12,2) NULL | Precio final del ítem |
| `status` | VARCHAR(20) | `pending` / `in_progress` / `completed` / `cancelled` |
| `sort_order` | INT | `DEFAULT 0` |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

### treatment_plan_payments
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | UUID PK | |
| `plan_id` | UUID FK | |
| `tenant_id` | INT FK | |
| `amount` | DECIMAL(12,2) NOT NULL | |
| `payment_method` | VARCHAR(20) | `cash` / `transfer` / `card` / `insurance` |
| `payment_date` | TIMESTAMPTZ | `DEFAULT NOW()` si no se provee |
| `recorded_by` | INT FK | `users.id` del usuario que registra |
| `appointment_id` | UUID FK NULL | Turno asociado (opcional) |
| `accounting_transaction_id` | UUID NULL | FK al registro sync en `accounting_transactions` |
| `receipt_data` | JSONB NULL | Datos de comprobante si aplica |
| `notes` | TEXT NULL | |
| `created_at` | TIMESTAMPTZ | |

### appointments (columna nueva)
| Columna | Tipo | Notas |
|---------|------|-------|
| `plan_item_id` | UUID FK NULL | FK a `treatment_plan_items.id` — puede ser NULL |

---

## 4. FR-01 — Treatment Plans CRUD

### EP-01: `GET /admin/patients/{patient_id}/treatment-plans`

**Descripción**: Lista todos los planes de tratamiento de un paciente, con campos computados agregados.

#### Parámetros

| Parámetro | Origen | Tipo | Requerido | Descripción |
|-----------|--------|------|-----------|-------------|
| `patient_id` | path | int | Sí | ID del paciente |
| `tenant_id` | JWT | int | Sí (auto) | Extraído por `get_resolved_tenant_id` |
| `status` | query | string | No | Filtro por estado. Valores: `draft`, `approved`, `in_progress`, `completed`, `cancelled` |

#### Declaración Python

```python
@router.get(
    "/patients/{patient_id}/treatment-plans",
    tags=["Planes de Tratamiento"],
    summary="Listar planes de tratamiento de un paciente",
)
async def list_patient_treatment_plans(
    patient_id: int,
    status: Optional[str] = Query(None),
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
```

#### Query SQL

```sql
SELECT
    tp.id,
    tp.name,
    tp.status,
    tp.estimated_total,
    tp.approved_total,
    tp.notes,
    tp.created_at,
    tp.updated_at,
    tp.professional_id,
    CONCAT(pr.first_name, ' ', pr.last_name) AS professional_name,
    COUNT(tpi.id)                              AS items_count,
    COALESCE(SUM(tpp.amount), 0)               AS paid_total,
    COALESCE(
        tp.approved_total - SUM(tpp.amount),
        tp.estimated_total - COALESCE(SUM(tpp.amount), 0)
    )                                          AS pending_total
FROM treatment_plans tp
LEFT JOIN professionals pr  ON pr.id = tp.professional_id AND pr.tenant_id = tp.tenant_id
LEFT JOIN treatment_plan_items tpi ON tpi.plan_id = tp.id AND tpi.tenant_id = tp.tenant_id
                                   AND tpi.status != 'cancelled'
LEFT JOIN treatment_plan_payments tpp ON tpp.plan_id = tp.id AND tpp.tenant_id = tp.tenant_id
WHERE tp.patient_id = $1
  AND tp.tenant_id  = $2
  -- [AND tp.status = $3]  -- Solo si se provee filtro
GROUP BY tp.id, pr.first_name, pr.last_name
ORDER BY tp.created_at DESC
```

Nota: si `status` se provee, se agrega `AND tp.status = $3` y se pasa como tercer parámetro.

#### Schema de respuesta

```json
[
  {
    "id": "uuid",
    "name": "Rehabilitación oral completa",
    "status": "approved",
    "estimated_total": 150000.00,
    "approved_total": 140000.00,
    "items_count": 3,
    "paid_total": 70000.00,
    "pending_total": 70000.00,
    "professional_id": 5,
    "professional_name": "Dra. Laura Delgado",
    "notes": null,
    "created_at": "2026-04-01T10:00:00Z",
    "updated_at": "2026-04-02T15:30:00Z"
  }
]
```

#### Validaciones

- `status` query param: si se provee, debe ser uno de `['draft', 'approved', 'in_progress', 'completed', 'cancelled']`. Si no es válido → HTTP 422 con mensaje descriptivo.
- El paciente debe existir para el `tenant_id` del JWT. Si no existe → HTTP 404 `"Paciente no encontrado"`.
- Si el paciente existe pero no tiene planes → retornar lista vacía `[]`, no 404.

#### Casos de error

| Condición | HTTP | Mensaje |
|-----------|------|---------|
| `patient_id` no pertenece al tenant | 404 | `"Paciente no encontrado"` |
| `status` query inválido | 422 | `"Estado inválido. Valores permitidos: draft, approved, in_progress, completed, cancelled"` |

---

### EP-02: `POST /admin/patients/{patient_id}/treatment-plans`

**Descripción**: Crea un nuevo plan de tratamiento para el paciente. Opcionalmente puede incluir ítems iniciales.

#### Parámetros

| Parámetro | Origen | Tipo | Requerido | Descripción |
|-----------|--------|------|-----------|-------------|
| `patient_id` | path | int | Sí | |
| body | JSON | `CreateTreatmentPlanBody` | Sí | |

#### Modelo Pydantic — body

```python
class TreatmentPlanItemCreate(BaseModel):
    treatment_type_code: Optional[str] = None
    custom_description: str
    estimated_price: Optional[float] = None  # Si None, se intenta desde treatment_types.base_price

class CreateTreatmentPlanBody(BaseModel):
    name: str
    professional_id: Optional[int] = None
    notes: Optional[str] = None
    items: Optional[List[TreatmentPlanItemCreate]] = []
```

#### Declaración Python

```python
@router.post(
    "/patients/{patient_id}/treatment-plans",
    tags=["Planes de Tratamiento"],
    summary="Crear plan de tratamiento",
    status_code=201,
)
async def create_treatment_plan(
    patient_id: int,
    body: CreateTreatmentPlanBody,
    request: Request,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
```

#### Lógica de negocio

1. Verificar que el paciente existe y pertenece al `tenant_id`.
2. Si `professional_id` se provee, verificar que el profesional existe y pertenece al `tenant_id`.
3. Generar `plan_id = str(uuid.uuid4())`.
4. Para cada ítem en `body.items`:
   a. Si `treatment_type_code` se provee y `estimated_price` es None: buscar `base_price` en `treatment_types` filtrando por `code = $x AND tenant_id = $y`.
   b. Si `treatment_type_code` no existe en la tabla → continuar con `estimated_price = None` (no es error bloqueante; la Dra. puede dejarlo vacío).
5. Computar `estimated_total = SUM(item.estimated_price)` de los ítems donde `estimated_price` no es None.
6. INSERT en `treatment_plans`.
7. INSERT en `treatment_plan_items` para cada ítem (en la misma transacción de base).
8. Emitir `TREATMENT_PLAN_CREATED`.
9. Retornar el plan creado con sus ítems.

#### Query SQL — Inserción del plan

```sql
INSERT INTO treatment_plans (
    id, tenant_id, patient_id, professional_id,
    name, status, estimated_total, notes,
    created_at, updated_at
)
VALUES ($1, $2, $3, $4, $5, 'draft', $6, $7, NOW(), NOW())
RETURNING id, name, status, estimated_total, approved_total,
          professional_id, notes, created_at, updated_at
```

#### Query SQL — Inserción de ítem

```sql
INSERT INTO treatment_plan_items (
    id, plan_id, tenant_id, treatment_type_code,
    custom_description, estimated_price, status, sort_order,
    created_at, updated_at
)
VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7, NOW(), NOW())
RETURNING id, custom_description, estimated_price, status, sort_order
```

`sort_order` se asigna como el índice posicional del ítem en la lista (0-based).

#### Schema de respuesta (HTTP 201)

```json
{
  "id": "uuid",
  "name": "Implante pieza 36 + corona",
  "status": "draft",
  "estimated_total": 85000.00,
  "approved_total": null,
  "professional_id": 5,
  "professional_name": "Dra. Laura Delgado",
  "notes": null,
  "items": [
    {
      "id": "uuid",
      "treatment_type_code": "IMPLANTE",
      "custom_description": "Implante pieza 36",
      "estimated_price": 60000.00,
      "approved_price": null,
      "status": "pending",
      "sort_order": 0
    }
  ],
  "created_at": "2026-04-03T12:00:00Z",
  "updated_at": "2026-04-03T12:00:00Z"
}
```

#### Evento Socket.IO

```python
await emit_appointment_event("TREATMENT_PLAN_CREATED", {
    "plan_id": plan_id,
    "patient_id": patient_id,
    "tenant_id": tenant_id,
    "name": body.name,
    "status": "draft"
}, request)
```

#### Validaciones

- `body.name`: no vacío, max 200 caracteres.
- `professional_id`: si se provee, debe existir y pertenecer al mismo `tenant_id`.
- Cada ítem: `custom_description` no puede estar vacío.
- `estimated_price` si se provee: debe ser `>= 0`.

#### Casos de error

| Condición | HTTP | Mensaje |
|-----------|------|---------|
| Paciente no existe / tenant mismatch | 404 | `"Paciente no encontrado"` |
| `professional_id` inválido | 404 | `"Profesional no encontrado"` |
| `name` vacío | 422 | `"El nombre del plan es requerido"` |
| `custom_description` vacío en ítem | 422 | `"La descripción del ítem no puede estar vacía"` |
| `estimated_price` negativo | 422 | `"El precio estimado no puede ser negativo"` |

---

### EP-03: `GET /admin/treatment-plans/{plan_id}`

**Descripción**: Detalle completo de un plan: ítems con turnos vinculados, historial de pagos, campos computados.

#### Parámetros

| Parámetro | Origen | Tipo | Requerido |
|-----------|--------|------|-----------|
| `plan_id` | path | UUID str | Sí |
| `tenant_id` | JWT | int | Sí (auto) |

#### Declaración Python

```python
@router.get(
    "/treatment-plans/{plan_id}",
    tags=["Planes de Tratamiento"],
    summary="Detalle completo de un plan de tratamiento",
)
async def get_treatment_plan_detail(
    plan_id: str,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
```

#### Queries SQL

**Plan base + aprobador:**

```sql
SELECT
    tp.*,
    CONCAT(pr.first_name, ' ', pr.last_name)       AS professional_name,
    CONCAT(ua.first_name, ' ', ua.last_name)        AS approved_by_name
FROM treatment_plans tp
LEFT JOIN professionals pr ON pr.id = tp.professional_id AND pr.tenant_id = tp.tenant_id
LEFT JOIN users ua          ON ua.id = tp.approved_by
WHERE tp.id = $1 AND tp.tenant_id = $2
```

**Ítems con turnos vinculados:**

```sql
SELECT
    tpi.id,
    tpi.treatment_type_code,
    tpi.custom_description,
    tpi.estimated_price,
    tpi.approved_price,
    tpi.status,
    tpi.sort_order,
    tpi.created_at,
    tpi.updated_at,
    -- Turnos vinculados (agrupados como JSON array)
    COALESCE(
        JSON_AGG(
            JSON_BUILD_OBJECT(
                'id',                   a.id,
                'appointment_datetime', a.appointment_datetime,
                'status',               a.status,
                'appointment_type',     a.appointment_type
            )
        ) FILTER (WHERE a.id IS NOT NULL),
        '[]'::json
    ) AS appointments
FROM treatment_plan_items tpi
LEFT JOIN appointments a ON a.plan_item_id = tpi.id AND a.tenant_id = tpi.tenant_id
WHERE tpi.plan_id = $1 AND tpi.tenant_id = $2
GROUP BY tpi.id
ORDER BY tpi.sort_order ASC, tpi.created_at ASC
```

**Pagos:**

```sql
SELECT
    tpp.id,
    tpp.amount,
    tpp.payment_method,
    tpp.payment_date,
    tpp.notes,
    tpp.appointment_id,
    tpp.created_at,
    CONCAT(u.first_name, ' ', u.last_name) AS recorded_by_name,
    a.appointment_type                      AS appointment_type
FROM treatment_plan_payments tpp
LEFT JOIN users u ON u.id = tpp.recorded_by
LEFT JOIN appointments a ON a.id = tpp.appointment_id
WHERE tpp.plan_id = $1 AND tpp.tenant_id = $2
ORDER BY tpp.payment_date DESC
```

**Computados en Python** (sobre resultados ya obtenidos):

```python
paid_total     = sum(p["amount"] for p in payments)
approved_total = plan["approved_total"] or plan["estimated_total"]
pending_total  = float(approved_total) - float(paid_total)
progress_pct   = round((float(paid_total) / float(approved_total) * 100), 1) if approved_total else 0.0
```

#### Schema de respuesta

```json
{
  "id": "uuid",
  "name": "Rehabilitación oral completa",
  "status": "in_progress",
  "estimated_total": 150000.00,
  "approved_total": 140000.00,
  "paid_total": 70000.00,
  "pending_total": 70000.00,
  "progress_pct": 50.0,
  "professional_id": 5,
  "professional_name": "Dra. Laura Delgado",
  "approved_by": 1,
  "approved_by_name": "Laura Delgado",
  "approved_at": "2026-04-02T10:00:00Z",
  "notes": "Incluye extracción previa",
  "created_at": "2026-04-01T10:00:00Z",
  "updated_at": "2026-04-03T09:00:00Z",
  "items": [
    {
      "id": "uuid",
      "treatment_type_code": "IMPLANTE",
      "custom_description": "Implante pieza 36",
      "estimated_price": 80000.00,
      "approved_price": 75000.00,
      "status": "in_progress",
      "sort_order": 0,
      "appointments": [
        {
          "id": "uuid",
          "appointment_datetime": "2026-04-10T10:00:00Z",
          "status": "scheduled",
          "appointment_type": "IMPLANTE"
        }
      ]
    }
  ],
  "payments": [
    {
      "id": "uuid",
      "amount": 70000.00,
      "payment_method": "transfer",
      "payment_date": "2026-04-02T11:00:00Z",
      "recorded_by_name": "Recepcionista García",
      "appointment_type": null,
      "notes": "Seña inicial"
    }
  ]
}
```

#### Casos de error

| Condición | HTTP | Mensaje |
|-----------|------|---------|
| `plan_id` no existe o tenant mismatch | 404 | `"Plan de tratamiento no encontrado"` |

---

### EP-04: `PUT /admin/treatment-plans/{plan_id}`

**Descripción**: Actualiza metadatos del plan. El caso especial de **aprobación** establece `status='approved'`, `approved_by`, y `approved_at=NOW()`.

#### Parámetros

| Parámetro | Origen | Tipo | Requerido |
|-----------|--------|------|-----------|
| `plan_id` | path | UUID str | Sí |
| body | JSON | `UpdateTreatmentPlanBody` | Sí |
| `tenant_id` | JWT | int | Sí (auto) |

#### Modelo Pydantic — body

```python
class UpdateTreatmentPlanBody(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    approved_total: Optional[float] = None
    professional_id: Optional[int] = None
    notes: Optional[str] = None
```

#### Declaración Python

```python
@router.put(
    "/treatment-plans/{plan_id}",
    tags=["Planes de Tratamiento"],
    summary="Actualizar plan de tratamiento",
)
async def update_treatment_plan(
    plan_id: str,
    body: UpdateTreatmentPlanBody,
    request: Request,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
```

#### Lógica de negocio

Se construyen las cláusulas SET dinámicamente solo para campos no-None en el body (patrón ya usado en admin_routes.py para UPDATE de appointments):

```python
updates = []
params = []

if body.name is not None:
    params.append(body.name)
    updates.append(f"name = ${len(params)}")

if body.approved_total is not None:
    params.append(body.approved_total)
    updates.append(f"approved_total = ${len(params)}")

if body.professional_id is not None:
    params.append(body.professional_id)
    updates.append(f"professional_id = ${len(params)}")

if body.notes is not None:
    params.append(body.notes)
    updates.append(f"notes = ${len(params)}")

# Caso especial: aprobación
if body.status is not None:
    valid_statuses = ['draft', 'approved', 'in_progress', 'completed', 'cancelled']
    if body.status not in valid_statuses:
        raise HTTPException(422, f"Estado inválido")
    params.append(body.status)
    updates.append(f"status = ${len(params)}")

    if body.status == 'approved':
        params.append(user_data.id)
        updates.append(f"approved_by = ${len(params)}")
        updates.append("approved_at = NOW()")

updates.append("updated_at = NOW()")
params.extend([plan_id, tenant_id])

query = f"""
    UPDATE treatment_plans
    SET {', '.join(updates)}
    WHERE id = ${len(params)-1} AND tenant_id = ${len(params)}
    RETURNING *
"""
```

#### Restricciones de transición de estado

| Estado actual | Transiciones permitidas |
|--------------|------------------------|
| `draft` | `approved`, `cancelled` |
| `approved` | `in_progress`, `cancelled` |
| `in_progress` | `completed`, `cancelled` |
| `completed` | — (ninguna, es estado final) |
| `cancelled` | — (ninguna, es estado final) |

Si la transición no es válida → HTTP 422 con mensaje descriptivo.

Nota: `cancelled` como estado final significa soft-cancel — el plan queda en DB, solo inaccesible para flujos normales. El EP-05 (`DELETE`) usa este mecanismo.

#### Schema de respuesta

```json
{
  "status": "updated",
  "plan": {
    "id": "uuid",
    "name": "Rehabilitación oral completa",
    "status": "approved",
    "approved_total": 140000.00,
    "approved_by": 1,
    "approved_at": "2026-04-03T10:00:00Z",
    "updated_at": "2026-04-03T10:00:00Z"
  }
}
```

#### Evento Socket.IO

```python
await emit_appointment_event("TREATMENT_PLAN_UPDATED", {
    "plan_id": plan_id,
    "tenant_id": tenant_id,
    "status": nuevo_status,
    "approved_total": body.approved_total,
}, request)
```

#### Casos de error

| Condición | HTTP | Mensaje |
|-----------|------|---------|
| Plan no existe / tenant mismatch | 404 | `"Plan de tratamiento no encontrado"` |
| Transición de estado inválida | 422 | `"Transición inválida de 'completed' a 'draft'"` |
| `status` desconocido | 422 | `"Estado inválido. Valores permitidos: ..."` |
| `professional_id` inválido | 404 | `"Profesional no encontrado"` |
| `approved_total` negativo | 422 | `"El total aprobado no puede ser negativo"` |

---

### EP-05: `DELETE /admin/treatment-plans/{plan_id}`

**Descripción**: Soft-cancel del plan. Establece `status='cancelled'`. No elimina físicamente ningún registro.

#### Declaración Python

```python
@router.delete(
    "/treatment-plans/{plan_id}",
    tags=["Planes de Tratamiento"],
    summary="Cancelar plan de tratamiento (soft delete)",
)
async def cancel_treatment_plan(
    plan_id: str,
    request: Request,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
```

#### Lógica

1. Verificar existencia y tenant.
2. Verificar que el plan NO está en `status='completed'`. Un plan completado no puede cancelarse.
3. Si ya está en `cancelled` → retornar `{"status": "already_cancelled"}` (idempotente).
4. `UPDATE treatment_plans SET status='cancelled', updated_at=NOW() WHERE id=$1 AND tenant_id=$2`.
5. **NO** cancelar ítems automáticamente — quedan en su estado actual para referencia histórica.
6. **NO** deshacer pagos registrados — permanecen vinculados al plan.
7. Emitir `TREATMENT_PLAN_UPDATED` con `status: 'cancelled'`.

#### Schema de respuesta

```json
{ "status": "cancelled", "plan_id": "uuid" }
```

#### Casos de error

| Condición | HTTP | Mensaje |
|-----------|------|---------|
| Plan no existe / tenant mismatch | 404 | `"Plan de tratamiento no encontrado"` |
| Plan en estado `completed` | 422 | `"No se puede cancelar un plan completado"` |

---

## 5. FR-02 — Plan Items CRUD

### EP-06: `POST /admin/treatment-plans/{plan_id}/items`

**Descripción**: Agrega un ítem al plan y recalcula `estimated_total`.

#### Parámetros

| Parámetro | Origen | Tipo | Requerido |
|-----------|--------|------|-----------|
| `plan_id` | path | UUID str | Sí |
| body | JSON | `AddPlanItemBody` | Sí |

#### Modelo Pydantic — body

```python
class AddPlanItemBody(BaseModel):
    treatment_type_code: Optional[str] = None
    custom_description: str
    estimated_price: Optional[float] = None
    approved_price: Optional[float] = None
```

#### Declaración Python

```python
@router.post(
    "/treatment-plans/{plan_id}/items",
    tags=["Planes de Tratamiento"],
    summary="Agregar ítem a un plan de tratamiento",
    status_code=201,
)
async def add_plan_item(
    plan_id: str,
    body: AddPlanItemBody,
    request: Request,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
```

#### Lógica de negocio

1. Verificar plan existe y pertenece al tenant.
2. Verificar plan no está en `status='cancelled'` ni `'completed'` (no se agregan ítems a planes cerrados).
3. Si `treatment_type_code` se provee y `estimated_price` es None:
   ```sql
   SELECT base_price FROM treatment_types
   WHERE code = $1 AND tenant_id = $2 AND is_active = true
   ```
   Si no encuentra el code → `estimated_price` queda en None (no error bloqueante).
4. Determinar `sort_order`:
   ```sql
   SELECT COALESCE(MAX(sort_order), -1) + 1
   FROM treatment_plan_items
   WHERE plan_id = $1 AND tenant_id = $2
   ```
5. Generar `item_id = str(uuid.uuid4())`.
6. INSERT en `treatment_plan_items`.
7. Recalcular y actualizar `estimated_total` del plan:
   ```sql
   UPDATE treatment_plans
   SET estimated_total = (
       SELECT COALESCE(SUM(estimated_price), 0)
       FROM treatment_plan_items
       WHERE plan_id = $1 AND tenant_id = $2 AND status != 'cancelled'
   ),
   updated_at = NOW()
   WHERE id = $1 AND tenant_id = $2
   ```
8. Emitir `TREATMENT_PLAN_UPDATED`.

#### Schema de respuesta (HTTP 201)

```json
{
  "item": {
    "id": "uuid",
    "plan_id": "uuid",
    "treatment_type_code": "BLANQUEAMIENTO",
    "custom_description": "Blanqueamiento LED 1 sesión",
    "estimated_price": 15000.00,
    "approved_price": null,
    "status": "pending",
    "sort_order": 2
  },
  "plan_estimated_total": 165000.00
}
```

#### Casos de error

| Condición | HTTP | Mensaje |
|-----------|------|---------|
| Plan no existe / tenant mismatch | 404 | `"Plan de tratamiento no encontrado"` |
| Plan en estado `cancelled` o `completed` | 422 | `"No se pueden agregar ítems a un plan cerrado"` |
| `custom_description` vacío | 422 | `"La descripción del ítem es requerida"` |
| `estimated_price` negativo | 422 | `"El precio no puede ser negativo"` |

---

### EP-07: `PUT /admin/treatment-plan-items/{item_id}`

**Descripción**: Actualiza un ítem. Al modificar precios, recalcula totales del plan padre.

#### Parámetros

| Parámetro | Origen | Tipo | Requerido |
|-----------|--------|------|-----------|
| `item_id` | path | UUID str | Sí |
| body | JSON | `UpdatePlanItemBody` | Sí |

#### Modelo Pydantic — body

```python
class UpdatePlanItemBody(BaseModel):
    custom_description: Optional[str] = None
    estimated_price: Optional[float] = None
    approved_price: Optional[float] = None
    status: Optional[str] = None
    sort_order: Optional[int] = None
```

#### Declaración Python

```python
@router.put(
    "/treatment-plan-items/{item_id}",
    tags=["Planes de Tratamiento"],
    summary="Actualizar ítem de plan de tratamiento",
)
async def update_plan_item(
    item_id: str,
    body: UpdatePlanItemBody,
    request: Request,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
```

#### Lógica de negocio

1. Verificar que el ítem existe y pertenece al `tenant_id`.
2. Obtener `plan_id` del ítem para recalcular totales.
3. Construir UPDATE dinámico (igual que EP-04).
4. Si `body.estimated_price` o `body.approved_price` se actualizan → recalcular `estimated_total` del plan (mismo query que EP-06, paso 7).
5. Emitir `TREATMENT_PLAN_UPDATED` con `plan_id`.

#### Validaciones de estado del ítem

| Estado actual | Transiciones permitidas |
|--------------|------------------------|
| `pending` | `in_progress`, `cancelled` |
| `in_progress` | `completed`, `cancelled` |
| `completed` | — |
| `cancelled` | — |

#### Schema de respuesta

```json
{
  "status": "updated",
  "item_id": "uuid",
  "plan_estimated_total": 165000.00
}
```

#### Casos de error

| Condición | HTTP | Mensaje |
|-----------|------|---------|
| Ítem no existe / tenant mismatch | 404 | `"Ítem no encontrado"` |
| Transición de estado inválida | 422 | `"Transición inválida de 'completed' a 'pending'"` |
| `estimated_price` o `approved_price` negativos | 422 | `"El precio no puede ser negativo"` |

---

### EP-08: `DELETE /admin/treatment-plan-items/{item_id}`

**Descripción**: Elimina físicamente un ítem del plan. Desvincula turnos asociados y recalcula totales.

**Decisión de diseño**: Se hace hard-delete del ítem (a diferencia del soft-cancel del plan) porque un ítem incorrecto no tiene valor histórico y confundiría los totales. Si se desea preservar el ítem sin contarlo, usar EP-07 con `status='cancelled'`.

#### Declaración Python

```python
@router.delete(
    "/treatment-plan-items/{item_id}",
    tags=["Planes de Tratamiento"],
    summary="Eliminar ítem de plan de tratamiento",
)
async def delete_plan_item(
    item_id: str,
    request: Request,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
```

#### Lógica

1. Verificar que el ítem existe y pertenece al `tenant_id`. Guardar `plan_id`.
2. Verificar que el ítem no está en `status='completed'` (no se puede eliminar trabajo ya realizado).
3. Desvincular turnos:
   ```sql
   UPDATE appointments
   SET plan_item_id = NULL
   WHERE plan_item_id = $1 AND tenant_id = $2
   ```
4. Eliminar el ítem:
   ```sql
   DELETE FROM treatment_plan_items
   WHERE id = $1 AND tenant_id = $2
   ```
5. Recalcular `estimated_total` del plan (mismo query que EP-06 paso 7).
6. Emitir `TREATMENT_PLAN_UPDATED`.

#### Schema de respuesta

```json
{
  "status": "deleted",
  "item_id": "uuid",
  "plan_estimated_total": 150000.00
}
```

#### Casos de error

| Condición | HTTP | Mensaje |
|-----------|------|---------|
| Ítem no existe / tenant mismatch | 404 | `"Ítem no encontrado"` |
| Ítem en estado `completed` | 422 | `"No se puede eliminar un ítem completado. Use estado 'cancelled' para descartarlo"` |

---

## 6. FR-03 — Payments

### EP-09: `POST /admin/treatment-plans/{plan_id}/payments`

**Descripción**: Registra un pago sobre el plan. Sincroniza con `accounting_transactions`. Auto-avanza el estado del plan si aplica.

#### Parámetros

| Parámetro | Origen | Tipo | Requerido |
|-----------|--------|------|-----------|
| `plan_id` | path | UUID str | Sí |
| body | JSON | `RegisterPaymentBody` | Sí |

#### Modelo Pydantic — body

```python
class RegisterPaymentBody(BaseModel):
    amount: float
    payment_method: str           # cash / transfer / card / insurance
    payment_date: Optional[str] = None   # ISO 8601; si None → NOW()
    appointment_id: Optional[str] = None
    notes: Optional[str] = None
```

#### Declaración Python

```python
@router.post(
    "/treatment-plans/{plan_id}/payments",
    tags=["Planes de Tratamiento"],
    summary="Registrar pago en plan de tratamiento",
    status_code=201,
)
async def register_plan_payment(
    plan_id: str,
    body: RegisterPaymentBody,
    request: Request,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
```

#### Lógica de negocio

1. Verificar plan existe y pertenece al tenant. Plan debe estar en `approved` o `in_progress` (no se puede pagar un plan `draft`, `cancelled`, o `completed`).
2. Si `appointment_id` se provee: verificar que el turno existe, pertenece al mismo tenant, y el paciente del turno coincide con el paciente del plan.
3. Parsear `payment_date`: si None → `datetime.now(timezone.utc)`. Si se provee string → `datetime.fromisoformat(body.payment_date)`.
4. Generar `payment_id = str(uuid.uuid4())`.
5. INSERT en `treatment_plan_payments`.
6. **Sync con accounting_transactions**:
   ```sql
   INSERT INTO accounting_transactions (
       id, tenant_id, patient_id, amount,
       transaction_type, payment_method, status,
       description, reference_id, reference_type,
       created_at, updated_at
   ) VALUES (
       $1, $2, $3, $4,
       'payment', $5, 'completed',
       $6, $7, 'treatment_plan_payment',
       NOW(), NOW()
   )
   RETURNING id
   ```
   Guardar `accounting_transaction_id` y actualizar el registro del pago:
   ```sql
   UPDATE treatment_plan_payments
   SET accounting_transaction_id = $1
   WHERE id = $2
   ```
7. **Auto-avance de estado del plan**: si el plan estaba en `approved` → cambiarlo a `in_progress`.
8. Emitir `BILLING_UPDATED`.

#### Nota sobre `accounting_transactions`

Se asume la estructura existente en la tabla (observada en uso en admin_routes.py líneas 2155-2163). Los campos `reference_id` y `reference_type` son la clave para vincular pagos de plan vs. pagos de turno legacy. Si la tabla no tiene estas columnas, se omite y se documenta como deuda técnica en el spec de migración.

#### Schema de respuesta (HTTP 201)

```json
{
  "payment": {
    "id": "uuid",
    "plan_id": "uuid",
    "amount": 70000.00,
    "payment_method": "transfer",
    "payment_date": "2026-04-03T11:00:00Z",
    "recorded_by": 1,
    "appointment_id": null,
    "notes": "Seña 50%",
    "created_at": "2026-04-03T11:00:00Z"
  },
  "plan_status": "in_progress",
  "accounting_transaction_id": "uuid"
}
```

#### Evento Socket.IO

```python
await emit_appointment_event("BILLING_UPDATED", {
    "plan_id": plan_id,
    "tenant_id": tenant_id,
    "payment_id": payment_id,
    "amount": body.amount,
    "plan_status": nuevo_status,
}, request)
```

#### Validaciones

- `amount`: requerido, mayor que 0.
- `payment_method`: debe ser uno de `['cash', 'transfer', 'card', 'insurance']`.
- `payment_date`: si se provee, debe ser un timestamp ISO 8601 parseable.
- `appointment_id`: si se provee, validar que pertenece al mismo paciente y tenant del plan.

#### Casos de error

| Condición | HTTP | Mensaje |
|-----------|------|---------|
| Plan no existe / tenant mismatch | 404 | `"Plan de tratamiento no encontrado"` |
| Plan en estado inválido para pagos | 422 | `"Solo se pueden registrar pagos en planes aprobados o en progreso"` |
| `amount` <= 0 | 422 | `"El monto debe ser mayor a cero"` |
| `payment_method` inválido | 422 | `"Método de pago inválido. Valores: cash, transfer, card, insurance"` |
| `appointment_id` no pertenece al paciente del plan | 422 | `"El turno no pertenece al paciente de este plan"` |
| `payment_date` mal formateado | 422 | `"Formato de fecha inválido. Use ISO 8601"` |

---

### EP-10: `GET /admin/treatment-plans/{plan_id}/payments`

**Descripción**: Historial de pagos de un plan.

#### Declaración Python

```python
@router.get(
    "/treatment-plans/{plan_id}/payments",
    tags=["Planes de Tratamiento"],
    summary="Historial de pagos de un plan de tratamiento",
)
async def get_plan_payments(
    plan_id: str,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
```

#### Query SQL

```sql
SELECT
    tpp.id,
    tpp.amount,
    tpp.payment_method,
    tpp.payment_date,
    tpp.notes,
    tpp.appointment_id,
    tpp.created_at,
    CONCAT(u.first_name, ' ', u.last_name) AS recorded_by_name,
    a.appointment_type                      AS appointment_type
FROM treatment_plan_payments tpp
LEFT JOIN users u        ON u.id = tpp.recorded_by
LEFT JOIN appointments a ON a.id = tpp.appointment_id
WHERE tpp.plan_id = $1 AND tpp.tenant_id = $2
ORDER BY tpp.payment_date DESC
```

#### Schema de respuesta

```json
[
  {
    "id": "uuid",
    "amount": 70000.00,
    "payment_method": "transfer",
    "payment_date": "2026-04-03T11:00:00Z",
    "recorded_by_name": "Recepcionista García",
    "appointment_type": null,
    "appointment_id": null,
    "notes": "Seña 50%",
    "created_at": "2026-04-03T11:00:00Z"
  }
]
```

#### Casos de error

| Condición | HTTP | Mensaje |
|-----------|------|---------|
| Plan no existe / tenant mismatch | 404 | `"Plan de tratamiento no encontrado"` |

---

### EP-11: `DELETE /admin/treatment-plan-payments/{payment_id}`

**Descripción**: Elimina un pago y su `accounting_transaction` correspondiente. Requiere que el usuario sea `ceo` o `secretary` (no cualquier staff).

**Decisión de diseño**: Los pagos se eliminan físicamente (hard delete) porque no existe el concepto de "anular pago" en este contexto. La auditoría se hace vía logs de aplicación, no en DB.

#### Declaración Python

```python
@router.delete(
    "/treatment-plan-payments/{payment_id}",
    tags=["Planes de Tratamiento"],
    summary="Eliminar pago de plan (con confirmación de rol)",
)
async def delete_plan_payment(
    payment_id: str,
    request: Request,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
```

#### Lógica

1. Verificar que el pago existe y pertenece al `tenant_id`. Guardar `plan_id` y `accounting_transaction_id`.
2. Verificar rol: solo `ceo` y `secretary` pueden eliminar pagos:
   ```python
   if user_data.role not in ['ceo', 'secretary']:
       raise HTTPException(403, "Solo administradores pueden eliminar pagos")
   ```
3. Si `accounting_transaction_id` existe:
   ```sql
   DELETE FROM accounting_transactions
   WHERE id = $1 AND tenant_id = $2
   ```
4. Eliminar el pago:
   ```sql
   DELETE FROM treatment_plan_payments
   WHERE id = $1 AND tenant_id = $2
   ```
5. Emitir `BILLING_UPDATED`.

#### Schema de respuesta

```json
{ "status": "deleted", "payment_id": "uuid", "plan_id": "uuid" }
```

#### Casos de error

| Condición | HTTP | Mensaje |
|-----------|------|---------|
| Pago no existe / tenant mismatch | 404 | `"Pago no encontrado"` |
| Rol insuficiente | 403 | `"Solo administradores pueden eliminar pagos"` |

---

## 7. FR-04 — Appointment Linking

### EP-12: `PUT /admin/appointments/{id}/link-plan-item`

**Descripción**: Vincula un turno a un ítem de plan de tratamiento. Establece `appointments.plan_item_id`.

#### Parámetros

| Parámetro | Origen | Tipo | Requerido |
|-----------|--------|------|-----------|
| `id` | path | UUID str | Sí |
| body | JSON | `LinkPlanItemBody` | Sí |

#### Modelo Pydantic — body

```python
class LinkPlanItemBody(BaseModel):
    plan_item_id: Optional[str] = None  # None = desvincular
```

#### Declaración Python

```python
@router.put(
    "/appointments/{id}/link-plan-item",
    tags=["Planes de Tratamiento"],
    summary="Vincular turno a ítem de plan de tratamiento",
)
async def link_appointment_to_plan_item(
    id: str,
    body: LinkPlanItemBody,
    request: Request,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
```

#### Lógica de negocio

**Caso 1: Vincular (`plan_item_id` no es None)**

1. Verificar que el turno existe y pertenece al `tenant_id`. Obtener `patient_id` del turno.
2. Verificar que el ítem existe y pertenece al `tenant_id`. Obtener `plan_id` del ítem.
3. Verificar que el plan del ítem pertenece al **mismo paciente** que el turno:
   ```sql
   SELECT patient_id FROM treatment_plans
   WHERE id = $1 AND tenant_id = $2
   ```
   Si `plan.patient_id != appointment.patient_id` → HTTP 422.
4. Verificar que el plan no está en `cancelled`.
5. UPDATE el turno:
   ```sql
   UPDATE appointments
   SET plan_item_id = $1, updated_at = NOW()
   WHERE id = $2 AND tenant_id = $3
   ```
6. Emitir `APPOINTMENT_UPDATED`.

**Caso 2: Desvincular (`plan_item_id` es None)**

1. Verificar que el turno existe y pertenece al `tenant_id`.
2. UPDATE el turno:
   ```sql
   UPDATE appointments
   SET plan_item_id = NULL, updated_at = NOW()
   WHERE id = $1 AND tenant_id = $2
   ```
3. Emitir `APPOINTMENT_UPDATED`.

#### Schema de respuesta

```json
{
  "status": "linked",
  "appointment_id": "uuid",
  "plan_item_id": "uuid"
}
```

O para desvincular:

```json
{
  "status": "unlinked",
  "appointment_id": "uuid",
  "plan_item_id": null
}
```

#### Casos de error

| Condición | HTTP | Mensaje |
|-----------|------|---------|
| Turno no existe / tenant mismatch | 404 | `"Turno no encontrado"` |
| Ítem no existe / tenant mismatch | 404 | `"Ítem de plan no encontrado"` |
| Paciente del turno ≠ paciente del plan | 422 | `"El turno y el plan pertenecen a pacientes distintos"` |
| Plan del ítem en estado `cancelled` | 422 | `"No se puede vincular a un ítem de plan cancelado"` |

---

## 8. Eventos Socket.IO

Todos los eventos se emiten con el helper `emit_appointment_event` existente en `admin_routes.py`. El nombre del evento es el primer argumento (string). El frontend escucha estos eventos en el socket client.

| Evento | Emitido en | Payload mínimo |
|--------|-----------|----------------|
| `TREATMENT_PLAN_CREATED` | EP-02 | `{plan_id, patient_id, tenant_id, name, status}` |
| `TREATMENT_PLAN_UPDATED` | EP-04, EP-05, EP-06, EP-07, EP-08 | `{plan_id, tenant_id, status?, estimated_total?}` |
| `BILLING_UPDATED` | EP-09, EP-11 | `{plan_id, tenant_id, payment_id?, amount?}` |
| `APPOINTMENT_UPDATED` | EP-12 | `{id, plan_item_id, tenant_id}` |

### Contrato de emisión

- Los eventos se emiten DESPUÉS de que la operación en DB se confirma (no antes).
- Si el emit falla → se loguea el warning pero la respuesta HTTP ya fue enviada exitosamente.
- No se retira el emit del flujo aunque falle. El frontend se recupera en el próximo polling/refresh.

---

## 9. Reglas de Aislamiento Multi-Tenant

Estas reglas son **no negociables** y aplican a todos los endpoints de este feature.

### 9.1 Extracción de tenant_id

```python
# CORRECTO
tenant_id: int = Depends(get_resolved_tenant_id)

# INCORRECTO — NUNCA hacer esto
tenant_id = request.query_params.get("tenant_id")
tenant_id = body.tenant_id
```

### 9.2 Todas las queries incluyen tenant_id

Cualquier SELECT, INSERT, UPDATE o DELETE sobre tablas de este feature debe incluir `AND tenant_id = $x` (o `tenant_id = $x` en WHERE inicial).

```sql
-- CORRECTO
SELECT * FROM treatment_plans WHERE id = $1 AND tenant_id = $2

-- INCORRECTO
SELECT * FROM treatment_plans WHERE id = $1
```

### 9.3 Validaciones cruzadas entre entidades

Cuando se verifica que un `plan_item_id` pertenece a un plan que pertenece a un paciente, **cada salto debe verificar tenant_id**:

```sql
-- Verificar que un ítem es del tenant
SELECT tpi.plan_id, tp.patient_id
FROM treatment_plan_items tpi
JOIN treatment_plans tp ON tp.id = tpi.plan_id AND tp.tenant_id = tpi.tenant_id
WHERE tpi.id = $1 AND tpi.tenant_id = $2
```

### 9.4 INSERT siempre incluye tenant_id explícito

```sql
INSERT INTO treatment_plan_items (id, plan_id, tenant_id, ...)
VALUES ($1, $2, $3, ...)
-- tenant_id = $3 es SIEMPRE el del JWT, nunca del body
```

---

## 10. Decisiones Arquitectónicas

### DA-01: Hard delete para ítems y pagos, soft delete para planes

**Decisión**: Los planes se soft-cancelan (`status='cancelled'`). Los ítems y pagos se hard-deletean cuando el usuario los elimina explícitamente.

**Razón**: El plan tiene valor histórico y de referencia para el paciente. Un ítem o pago eliminado generalmente es un error de carga — no tiene valor histórico. Para "cancelar" un ítem sin eliminarlo, existe `status='cancelled'`.

**Trade-off**: Se pierde trazabilidad de "quién borró el pago X el día Y". Mitigation: loggear la eliminación en el logger de aplicación.

### DA-02: Sync síncrono con accounting_transactions

**Decisión**: El INSERT en `accounting_transactions` ocurre dentro del mismo request que el INSERT del pago, no en un background task.

**Razón**: Si el sync falla, el pago tampoco debe quedar registrado — son atómicos. Un pago sin accounting_transaction rompería las métricas del dashboard.

**Trade-off**: Levemente más latencia en EP-09. Aceptable dado que es una acción administrativa, no en tiempo real.

**Implementación**: Usar una transacción de DB explícita con asyncpg:
```python
async with db.pool.acquire() as conn:
    async with conn.transaction():
        payment_row = await conn.fetchrow("INSERT INTO treatment_plan_payments ...")
        tx_row = await conn.fetchrow("INSERT INTO accounting_transactions ...")
        await conn.execute("UPDATE treatment_plan_payments SET accounting_transaction_id = $1 WHERE id = $2", tx_row["id"], payment_row["id"])
```

### DA-03: Recálculo de estimated_total en endpoints de ítem

**Decisión**: `estimated_total` en `treatment_plans` se recalcula con un query de agregación cada vez que se modifica, agrega o elimina un ítem (EP-06, EP-07, EP-08).

**Razón**: Evita inconsistencias entre la suma de ítems y el campo `estimated_total` del plan. Es preferible un query más vs. datos incorrectos.

**Trade-off**: Más queries por operación. Aceptable porque los planes no tienen más de ~20 ítems en promedio.

### DA-04: approved_total como campo manual (no computado)

**Decisión**: `approved_total` es un campo que la Dra. establece manualmente al aprobar el plan. NO es la suma de `approved_price` de los ítems.

**Razón**: La Dra. ajusta el precio final del plan globalmente ("te hago el plan a 140.000 en total"), no ítem por ítem. El `approved_price` por ítem existe para referencia, pero el monto total acordado es el del campo del plan.

**Trade-off**: Puede haber inconsistencia entre `SUM(items.approved_price)` y `plan.approved_total`. Esa inconsistencia es intencional y esperada — refleja el descuento global.

### DA-05: Restricción de eliminación de pagos a roles CEO/Secretary

**Decisión**: Solo usuarios con role `ceo` o `secretary` pueden eliminar pagos (EP-11).

**Razón**: Eliminar un pago es una operación con impacto en métricas de ingresos. No debe ser accesible a cualquier staff.

**Trade-off**: Agrega una restricción que no existe en otros DELETEs del sistema. Es coherente con el patrón ya establecido en `admin_routes.py` donde ciertas operaciones verifican `user_data.role`.

### DA-06: Transición de estado `approved` → `in_progress` automática al registrar el primer pago

**Decisión**: Cuando se registra el primer pago en un plan `approved`, el plan avanza automáticamente a `in_progress` (EP-09).

**Razón**: La Dra. no debería tener que hacer dos acciones (registrar pago + cambiar estado). Un pago registrado implica que el tratamiento comenzó.

**Trade-off**: Cambio implícito de estado que podría sorprender. Se refleja en la respuesta del EP-09 (`plan_status: "in_progress"`) para que el frontend lo muestre.

### DA-07: EP-12 como extensión del endpoint de appointments existente

**Decisión**: El linking usa un endpoint dedicado `PUT /admin/appointments/{id}/link-plan-item` en lugar de agregar `plan_item_id` al body del PUT general de appointments.

**Razón**: El UPDATE general de appointments ya es complejo y tiene su propia lógica de validación. Mezclar el linking ahí acopla dos responsabilidades distintas. Un endpoint dedicado es más explícito, testeable y fácil de mantener.

**Trade-off**: Un endpoint más en el router. Aceptable.

---

## 11. Errores Estándar

Se usan los códigos HTTP estándar del sistema existente:

| Código | Cuándo usarlo |
|--------|--------------|
| 200 | Operación exitosa (GET, PUT, DELETE que retornan datos) |
| 201 | Recurso creado (POST) |
| 404 | Recurso no encontrado O tenant_id mismatch (nunca revelar cuál de los dos) |
| 422 | Validación de negocio fallida (datos inválidos, estado incorrecto, restricción de relación) |
| 403 | Rol insuficiente |
| 500 | Error interno no manejado (loguear siempre con `logger.exception`) |

### Formato de error consistente con el sistema existente

```python
raise HTTPException(
    status_code=404,
    detail="Plan de tratamiento no encontrado"
)
```

FastAPI serializa esto como:
```json
{ "detail": "Plan de tratamiento no encontrado" }
```

---

*Fin del spec. Próximos artefactos: `design-backend.md` (arquitectura de la migración Alembic, transacciones, índices) y `tasks.md` (breakdown de implementación).*
