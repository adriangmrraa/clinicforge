# Spec: AI Tools Integration — Treatment Plan Billing

**Change**: treatment-plan-billing
**Module**: AI Tools (Nova + WhatsApp Agent)
**Status**: Draft
**Date**: 2026-04-03
**Depends on**: spec-database.md, spec-backend.md

---

## Overview

Este spec cubre las modificaciones a las herramientas de IA que soportan el sistema de presupuesto y
facturación por plan de tratamiento. Hay dos agentes afectados:

1. **Nova** — asistente de voz interno (OpenAI Realtime API) con 50 tools en `nova_tools.py`
2. **Agente WhatsApp** — LangChain agent en `main.py` con `DENTAL_TOOLS`

Los cambios se dividen en:
- **3 tools nuevas** en Nova (Categoría C — Facturación)
- **3 tools modificadas** en Nova (`registrar_pago`, `facturacion_pendiente`, `resumen_financiero`)
- **1 tool modificada** en el agente WhatsApp (`verify_payment_receipt`)
- **1 modificación en buffer_task.py** — detección de comprobantes para planes

---

## Precondiciones

Estas tables deben existir antes de que los tools funcionen (creadas en spec-database.md):

```
treatment_plans          — plan maestro por paciente
treatment_plan_items     — ítems del plan (tratamientos)
treatment_plan_payments  — pagos registrados contra el plan
```

La columna `appointments.plan_item_id` también debe existir.

---

## FR-NOVA-01: `ver_presupuesto_paciente` (NUEVA)

### Descripción

Permite a Nova buscar y mostrar el/los plan/es de tratamiento activos de un paciente.
Soporta búsqueda por `patient_id` (cuando ya se tiene el ID) o por nombre (cuando la Dra.
habla por voz: "Mostrame el presupuesto de María García").

### Casos de uso

- "Mostrame el presupuesto de Juan Pérez"
- "¿Cuánto debe María García?"
- "¿Qué tratamientos tiene presupuestados Romina?"
- "Ver plan de tratamiento del paciente 42"

### Tool Schema (OpenAI Realtime format)

```json
{
  "type": "function",
  "name": "ver_presupuesto_paciente",
  "description": "Muestra el/los presupuesto(s) de tratamiento de un paciente: ítems, precios estimados/aprobados, pagos realizados y saldo pendiente. Busca por nombre o ID.",
  "parameters": {
    "type": "object",
    "properties": {
      "patient_id": {
        "type": "integer",
        "description": "ID numérico del paciente (opcional si se provee patient_name)"
      },
      "patient_name": {
        "type": "string",
        "description": "Nombre o apellido del paciente para buscar (opcional si se provee patient_id)"
      },
      "plan_id": {
        "type": "string",
        "description": "UUID del plan específico a mostrar. Si se omite, muestra todos los planes activos."
      },
      "include_completed": {
        "type": "boolean",
        "description": "Si incluir planes completados/cancelados. Default: false (solo activos)."
      }
    }
  }
}
```

### Reglas de negocio

1. Si se provee `patient_name` sin `patient_id`, hacer búsqueda fuzzy (ILIKE `%nombre%`) en `patients`.
   Si encuentra más de 1 paciente, retornar lista con nombres para que Nova pida aclaración.
2. Si el paciente no tiene ningún plan activo, decirlo claramente.
3. La respuesta incluye para cada plan:
   - Nombre del plan y estado (draft / approved / in_progress / completed)
   - Ítems con precio estimado y precio aprobado (si fue aprobado)
   - Total aprobado (o estimado si aún no fue aprobado)
   - Total pagado hasta la fecha
   - Saldo pendiente
   - Fecha de aprobación (si aplica)
4. Los montos de pagos se obtienen de `treatment_plan_payments`, nunca de `appointments.billing_amount`
   para turnos vinculados a un plan.

### Input/Output Example

**Input:**
```json
{ "patient_name": "María García" }
```

**Output (exitoso, un plan):**
```
Presupuesto de María García:

[Rehabilitación oral completa — EN PROGRESO]
Estado: aprobado el 15/03/2026
Ítems:
  1. Implante pieza 36 — $350.000
  2. Tratamiento de conducto pieza 14 — $80.000
  3. Corona cerámica pieza 14 — $90.000
Total aprobado: $420.000
Total pagado: $150.000 (35%)
Saldo pendiente: $270.000
```

**Output (múltiples pacientes encontrados):**
```
Encontré 3 pacientes con ese nombre:
  - María García (ID 42) — DNI 28.345.678
  - María del Carmen García (ID 87) — DNI 33.210.456
  - María García López (ID 115) — DNI 40.123.789
¿A cuál te referís?
```

**Output (sin plan):**
```
María García no tiene presupuestos activos. ¿Querés que cree uno?
```

### Errores

| Condición | Respuesta |
|-----------|-----------|
| Sin `patient_id` ni `patient_name` | "Necesito el nombre o ID del paciente." |
| Paciente no encontrado | "No encontré ningún paciente con ese nombre." |
| DB error | "Error al obtener el presupuesto. Intentá de nuevo." |

### Integración con tools existentes

- `buscar_paciente` — si Nova ya tiene el patient_id de una acción previa, pasar directamente
- `aprobar_presupuesto` — flujo natural post-visualización: ver → aprobar
- `registrar_pago_plan` — flujo natural post-visualización: ver → registrar pago

---

## FR-NOVA-02: `registrar_pago_plan` (NUEVA)

### Descripción

Registra un pago contra un plan de tratamiento (no contra un turno individual). Crea un registro
en `treatment_plan_payments` y un `accounting_transaction` sincronizado. Emite evento
`BILLING_UPDATED` por Socket.IO para refrescar el frontend.

### Casos de uso

- "María pagó $50.000 en efectivo"
- "Registrá un pago de $30.000 con transferencia para el plan de Juan"
- "Entraron $80.000 de Romina, tarjeta"
- "Anotá un pago parcial de $25.000 para el plan 'Rehabilitación oral' de García"

### Tool Schema

```json
{
  "type": "function",
  "name": "registrar_pago_plan",
  "description": "Registra un pago parcial o total contra el plan de tratamiento de un paciente. Crea el registro de pago y actualiza el balance del plan. Solo CEO y secretarias.",
  "parameters": {
    "type": "object",
    "properties": {
      "patient_id": {
        "type": "integer",
        "description": "ID del paciente (opcional si se provee patient_name)"
      },
      "patient_name": {
        "type": "string",
        "description": "Nombre del paciente para buscar su plan (opcional si se provee patient_id)"
      },
      "plan_id": {
        "type": "string",
        "description": "UUID del plan específico. Si el paciente tiene un solo plan activo, se usa ese. Si tiene varios, este campo es obligatorio."
      },
      "amount": {
        "type": "number",
        "description": "Monto del pago (obligatorio)"
      },
      "method": {
        "type": "string",
        "enum": ["cash", "transfer", "card", "insurance"],
        "description": "Método de pago: cash=efectivo, transfer=transferencia, card=tarjeta, insurance=obra social"
      },
      "appointment_id": {
        "type": "string",
        "description": "UUID del turno asociado a este pago (opcional, para vincular el pago a una sesión específica)"
      },
      "notes": {
        "type": "string",
        "description": "Notas adicionales del pago"
      }
    },
    "required": ["amount", "method"]
  }
}
```

### Reglas de negocio

1. **Resolución de plan**: Si `plan_id` no se provee:
   - Buscar planes con `status IN ('approved', 'in_progress')` para el paciente
   - Si hay exactamente 1 → usarlo automáticamente
   - Si hay 0 → error: "Este paciente no tiene planes activos para registrar pagos"
   - Si hay más de 1 → pedir `plan_id` o nombre del plan: "¿A qué plan corresponde: [lista]?"

2. **Resolución de paciente**: Igual que `ver_presupuesto_paciente` (fuzzy match si solo hay nombre).

3. **Validación de monto**: El pago no puede superar el saldo pendiente (`approved_total - suma(payments)`).
   Si supera → advertir pero permitir (puede ser overpayment intencional, ej: redondeo).

4. **Estado del plan**: Si después del pago `suma(payments) >= approved_total`, actualizar
   `treatment_plans.status = 'completed'` automáticamente.

5. **Accounting sync**: Crear `accounting_transactions` con:
   ```
   transaction_type = 'payment'
   amount = <monto>
   payment_method = <method>
   description = "Pago plan: {plan.name} — {patient.full_name}"
   status = 'completed'
   ```

6. **Socket.IO**: Emitir `BILLING_UPDATED` con `{ plan_id, tenant_id, patient_id }`.

7. **RBAC**: Solo `ceo` y `secretary` pueden registrar pagos.

### Input/Output Example

**Input:**
```json
{
  "patient_name": "María García",
  "amount": 50000,
  "method": "cash",
  "notes": "Pago primera cuota"
}
```

**Output (exitoso):**
```
Pago registrado para María García:
  Monto: $50.000 (efectivo)
  Plan: Rehabilitación oral completa
  Total pagado hasta ahora: $200.000 de $420.000 (47%)
  Saldo pendiente: $220.000
```

**Output (plan completado):**
```
Pago final registrado para Juan Pérez:
  Monto: $80.000 (transferencia)
  Plan: Implante y corona pieza 36 — COMPLETADO
  Total cobrado: $350.000 / $350.000 (100%)
  El plan quedó marcado como completado.
```

**Output (overpayment warning):**
```
⚠️ Atención: el monto ($50.000) supera el saldo pendiente ($30.000).
¿Confirmás igualmente el pago?
```

### Errores

| Condición | Respuesta |
|-----------|-----------|
| Sin `amount` o `method` | "Necesito el monto y el método de pago." |
| Paciente con múltiples planes | Listar planes y pedir aclaración |
| Plan en estado `draft` | "El plan aún no fue aprobado. Aprobalo primero con 'aprobar_presupuesto'." |
| Plan `completed` o `cancelled` | "Este plan ya está cerrado. ¿Querés crear uno nuevo?" |
| DB error | "Error al registrar el pago. Intentá de nuevo." |

### Integración con tools existentes

- `ver_presupuesto_paciente` — verificar balance antes de registrar
- `aprobar_presupuesto` — el plan debe estar aprobado para aceptar pagos
- `registrar_pago` (existente) — NO reemplaza este tool; `registrar_pago` sigue para pagos de turnos sin plan

---

## FR-NOVA-03: `aprobar_presupuesto` (NUEVA)

### Descripción

Aprueba un plan de tratamiento fijando el precio final. Cambia `status` de `draft` a `approved`.
Registra quién aprobó y cuándo. El precio aprobado puede diferir del estimado (la Dra. siempre ajusta).

### Casos de uso

- "Aprobá el presupuesto de María por $420.000"
- "Cerrá el plan de Juan en $350.000"
- "Confirmar presupuesto 'Rehabilitación oral' de García con precio final $480.000"

### Tool Schema

```json
{
  "type": "function",
  "name": "aprobar_presupuesto",
  "description": "Aprueba un plan de tratamiento fijando el precio final acordado con el paciente. Cambia el estado de draft a approved. Solo CEO.",
  "parameters": {
    "type": "object",
    "properties": {
      "plan_id": {
        "type": "string",
        "description": "UUID del plan a aprobar (opcional si se provee patient_name y el paciente tiene un solo plan draft)"
      },
      "patient_id": {
        "type": "integer",
        "description": "ID del paciente (para encontrar su plan draft)"
      },
      "patient_name": {
        "type": "string",
        "description": "Nombre del paciente para buscar su plan draft"
      },
      "approved_total": {
        "type": "number",
        "description": "Precio final aprobado en pesos (obligatorio)"
      },
      "notes": {
        "type": "string",
        "description": "Notas de la aprobación (ej: 'precio acordado en consulta')"
      }
    },
    "required": ["approved_total"]
  }
}
```

### Reglas de negocio

1. Buscar plan con `status = 'draft'` para el paciente. Si tiene más de uno, listar y pedir aclaración.
2. Setear:
   ```
   status = 'approved'
   approved_total = <approved_total>
   approved_by = <user_id del contexto>
   approved_at = NOW()
   ```
3. El `approved_total` puede ser mayor, menor o igual al `estimated_total`. No hay restricción.
4. Si el `approved_total` es 0 → error: "El precio aprobado no puede ser cero."
5. **No modifica los `approved_price` de los ítems individuales** — eso es responsabilidad de la UI.
6. **RBAC**: Solo `ceo` puede aprobar.
7. Emitir `BILLING_UPDATED` por Socket.IO.

### Input/Output Example

**Input:**
```json
{
  "patient_name": "María García",
  "approved_total": 420000,
  "notes": "Precio acordado en consulta del 02/04/2026"
}
```

**Output:**
```
Presupuesto aprobado:
  Paciente: María García
  Plan: Rehabilitación oral completa
  Estimado original: $390.000
  Precio final aprobado: $420.000
  Aprobado por: Dra. Laura Delgado — 03/04/2026
El plan ya está listo para recibir pagos.
```

### Errores

| Condición | Respuesta |
|-----------|-----------|
| Plan no en estado `draft` | "Este plan ya fue aprobado el [fecha]. ¿Querés modificar el precio?" |
| `approved_total` = 0 | "El precio final no puede ser cero." |
| Sin permiso (no CEO) | "Solo el CEO puede aprobar presupuestos." |
| Paciente sin planes draft | "No hay presupuestos pendientes de aprobación para este paciente." |

### Integración con tools existentes

- `ver_presupuesto_paciente` — revisión antes de aprobar
- `registrar_pago_plan` — habilitado tras aprobación

---

## FR-NOVA-04: Modificar `facturacion_pendiente` (EXISTENTE)

### Descripción del cambio

La implementación actual en `_facturacion_pendiente()` solo consulta `appointments` con
`payment_status = 'pending'`. Debe extenderse para incluir planes de tratamiento con saldo pendiente.

### Cambio en Tool Schema

No cambia el schema (no requiere parámetros). Solo cambia el output.

### Cambio en implementación

Agregar una segunda sección al resultado. La query actual se mantiene intacta (backward compatible).
Agregar:

```sql
SELECT
    tp.id,
    tp.name AS plan_name,
    p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name,
    tp.approved_total,
    COALESCE(
        (SELECT SUM(tpp.amount)
         FROM treatment_plan_payments tpp
         WHERE tpp.plan_id = tp.id AND tpp.tenant_id = $1),
        0
    ) AS total_paid
FROM treatment_plans tp
JOIN patients p ON p.id = tp.patient_id
WHERE tp.tenant_id = $1
  AND tp.status IN ('approved', 'in_progress')
  AND tp.approved_total IS NOT NULL
HAVING (tp.approved_total - COALESCE(SUM_paid, 0)) > 0
ORDER BY tp.updated_at DESC
LIMIT 20
```

### Output esperado (nuevo formato)

```
Facturación pendiente:

[TURNOS SIN COBRAR — 3]
• Ana López — ortodoncia (12/03/2026) — $15.000
• Carlos Ruiz — implante (20/03/2026) — $80.000
• Beatriz Sosa — consulta (01/04/2026) — $8.000

[PLANES CON SALDO PENDIENTE — 2]
• María García — "Rehabilitación oral completa" — Aprobado $420.000 / Pagado $150.000 / Pendiente $270.000
• Juan Pérez — "Implante pieza 36" — Aprobado $350.000 / Pagado $280.000 / Pendiente $70.000

Total pendiente de cobro: $443.000
```

Si no hay planes con saldo → omitir la sección de planes sin mostrar "0 planes".

---

## FR-NOVA-05: Modificar `resumen_financiero` (EXISTENTE)

### Descripción del cambio

Agregar una sección de planes al resumen financiero. La implementación actual en
`_resumen_financiero()` solo consulta `appointments.billing_amount`. Los pagos de planes están
en `treatment_plan_payments` y no aparecen en el resumen.

### Cambio en Tool Schema

No cambia el schema (el parámetro `periodo` se mantiene).

### Lógica adicional

Agregar consulta de pagos de planes para el mismo período:

```sql
SELECT
    COALESCE(SUM(tpp.amount), 0) AS plan_revenue,
    COUNT(DISTINCT tpp.plan_id) AS active_plans,
    COALESCE(SUM(tp.approved_total), 0) AS total_approved,
    COALESCE(SUM(tp.approved_total), 0) -
        COALESCE(SUM(tpp.amount), 0) AS total_pending
FROM treatment_plan_payments tpp
JOIN treatment_plans tp ON tp.id = tpp.plan_id
WHERE tpp.tenant_id = $1
  AND tpp.created_at >= NOW() - INTERVAL '1 day' * $2
```

### Output esperado (nueva sección al final)

```
Finanzas últimos 30 días:
Facturación por turnos: $485.000
Pagos pendientes: 3 turnos ($103.000)

Por tratamiento:
  - implante: 4 turnos, $320.000 (3 pagados)
  - consulta: 8 turnos, $96.000 (6 pagados)
  - ortodoncia: 2 turnos, $69.000 (1 pagado)

Por profesional:
  - Dra. Laura: 14 turnos, $485.000

[PLANES DE TRATAMIENTO]
Ingresos por planes (período): $230.000
Planes activos: 5
Total presupuestado (aprobado): $1.750.000
Total cobrado (histórico): $680.000
Pendiente total: $1.070.000
```

---

## FR-NOVA-06: Modificar `registrar_pago` (EXISTENTE)

### Descripción del cambio

El tool actual requiere `appointment_id` obligatorio. Extenderlo para que, si se provee `plan_id`
en lugar de `appointment_id`, delegue al flujo de `registrar_pago_plan`.

### Cambio en Tool Schema

```json
{
  "type": "function",
  "name": "registrar_pago",
  "description": "Registra el pago de un turno completado O de un plan de tratamiento. Si se provee plan_id, registra contra el plan. Si se provee appointment_id, registra contra el turno. Solo para CEO y secretarias.",
  "parameters": {
    "type": "object",
    "properties": {
      "appointment_id": {
        "type": "string",
        "description": "UUID del turno (obligatorio si no se provee plan_id)"
      },
      "plan_id": {
        "type": "string",
        "description": "UUID del plan de tratamiento (obligatorio si no se provee appointment_id)"
      },
      "amount": {
        "type": "number",
        "description": "Monto pagado"
      },
      "method": {
        "type": "string",
        "enum": ["cash", "card", "transfer", "insurance"],
        "description": "Método de pago"
      },
      "notes": {
        "type": "string",
        "description": "Notas del pago"
      }
    },
    "required": ["amount", "method"]
  }
}
```

### Lógica de routing

```python
if plan_id:
    # Delegar a _registrar_pago_plan con el plan_id directo
    return await _registrar_pago_plan({
        "plan_id": plan_id,
        "amount": amount,
        "method": method,
        "appointment_id": appointment_id,  # opcional, puede venir junto
        "notes": notes
    }, tenant_id, user_role)
elif appointment_id:
    # Comportamiento actual sin cambios
    ...
else:
    return "Necesito appointment_id o plan_id para registrar el pago."
```

**Invariante**: si se proveen ambos, `plan_id` tiene precedencia y `appointment_id` se
registra como campo opcional en `treatment_plan_payments.appointment_id`.

---

## FR-WA-01: Modificar `verify_payment_receipt` en `main.py` (AGENTE WHATSAPP)

### Descripción del cambio

La función actual (`verify_payment_receipt` en `main.py`, línea ~4141) busca el monto esperado
exclusivamente en `appointments.billing_amount`. Cuando el paciente tiene un plan de tratamiento
activo, el pago puede corresponder a una cuota del plan (cuyo monto no está en `billing_amount`).

### Cambio requerido

Extender la resolución del `expected_amount` para que:
1. Primero revise si el paciente tiene planes activos con saldo pendiente
2. Si tiene plan activo → el monto esperado es el saldo pendiente del plan
3. Si tiene plan activo Y turno con `billing_amount` → usar el mayor (para no rechazar
   pagos que corresponden al plan)
4. Cuando la verificación es exitosa y existe un plan activo → crear `treatment_plan_payment`
   en lugar de (o además de) actualizar `appointments.payment_status`

### Pseudocódigo del cambio

```python
# Después de obtener `apt` (el turno), buscar también plan activo:
patient_id = await get_patient_id_by_phone(phone, tenant_id)
active_plan = None
plan_pending_balance = 0.0

if patient_id:
    active_plan = await pool.fetchrow("""
        SELECT tp.id, tp.name, tp.approved_total,
               COALESCE(
                   (SELECT SUM(amount) FROM treatment_plan_payments
                    WHERE plan_id = tp.id AND tenant_id = $1),
                   0
               ) AS total_paid
        FROM treatment_plans tp
        WHERE tp.patient_id = $2
          AND tp.tenant_id = $1
          AND tp.status IN ('approved', 'in_progress')
        ORDER BY tp.updated_at DESC
        LIMIT 1
    """, tenant_id, patient_id)

    if active_plan:
        plan_pending_balance = float(active_plan['approved_total']) - float(active_plan['total_paid'])

# Priority for expected_amount:
# 1. billing_amount en el turno (seña específica)
# 2. saldo pendiente del plan activo
# 3. 50% del precio del profesional
# 4. 50% del precio del tratamiento
# 5. 50% del precio del tenant

if apt and apt["billing_amount"] and float(apt["billing_amount"]) > 0:
    expected_amount = float(apt["billing_amount"])
    payment_context = "appointment"
elif plan_pending_balance > 0:
    expected_amount = plan_pending_balance  # cuota libre o total pendiente
    payment_context = "plan"
else:
    # ... lógica actual de fallback 50%
    payment_context = "appointment_50pct"
```

### Acción post-verificación exitosa

```python
if verification_success:
    if payment_context == "plan" and active_plan:
        # Crear treatment_plan_payment
        await pool.execute("""
            INSERT INTO treatment_plan_payments
                (id, plan_id, tenant_id, amount, payment_method,
                 payment_date, recorded_by, appointment_id, receipt_data, notes)
            VALUES ($1, $2, $3, $4, $5, NOW(), NULL, $6, $7::jsonb, $8)
        """,
            uuid.uuid4(),
            active_plan['id'],
            tenant_id,
            verified_amount,
            "transfer",            # comprobante siempre es transferencia
            apt['id'] if apt else None,
            json.dumps(receipt_evidence),
            "Verificado automáticamente por IA via comprobante WhatsApp"
        )

        # Actualizar plan si está completamente pagado
        new_total_paid = float(active_plan['total_paid']) + verified_amount
        if new_total_paid >= float(active_plan['approved_total']):
            await pool.execute("""
                UPDATE treatment_plans SET status = 'completed', updated_at = NOW()
                WHERE id = $1
            """, active_plan['id'])

        # Si hay turno asociado → marcar como confirmado (seña)
        if apt:
            await pool.execute("""
                UPDATE appointments
                SET status = 'confirmed', payment_status = 'partial', updated_at = NOW()
                WHERE id = $1 AND tenant_id = $2
            """, apt['id'], tenant_id)
    else:
        # Comportamiento actual sin cambios
        ...
```

### Mensaje de confirmación al paciente (ajustado para planes)

```
# Contexto: pago de plan
"Recibí y verifiqué tu comprobante de $50.000 para el plan '{plan_name}'.
Ya lo registramos en tu ficha.
Tu saldo actualizado: pagaste $200.000 de $420.000 — te quedan $220.000.
Nos vemos el [fecha turno]."

# Contexto: plan completado tras el pago
"Recibí tu pago de $70.000. El plan '{plan_name}' quedó completamente pagado.
Muchas gracias, hasta la próxima consulta."
```

---

## FR-BUFFER-01: Modificar detección de comprobantes en `buffer_task.py`

### Descripción del cambio

La detección actual (línea ~1121) solo busca `appointments` con `payment_status = 'pending'`.
Si el paciente tiene un plan activo con saldo pendiente, la imagen también puede ser un
comprobante de pago del plan.

### Cambio requerido

Extender la query de detección para incluir planes:

```python
# Query actual (MANTENER):
pending_apt = await pool.fetchval("""
    SELECT a.id FROM appointments a
    JOIN patients p ON p.id = a.patient_id
    WHERE a.tenant_id = $1
      AND (p.phone_number = $2 OR ...)
      AND a.status IN ('scheduled', 'confirmed')
      AND (a.payment_status IS NULL OR a.payment_status = 'pending' OR a.payment_status = 'partial')
    ORDER BY a.appointment_datetime ASC LIMIT 1
""", tenant_id, external_user_id, clean_ext_pay)

# Query NUEVA (agregar):
pending_plan = await pool.fetchval("""
    SELECT tp.id FROM treatment_plans tp
    JOIN patients p ON p.id = tp.patient_id
    WHERE tp.tenant_id = $1
      AND (p.phone_number = $2
           OR REGEXP_REPLACE(p.phone_number, '[^0-9]', '', 'g') = REGEXP_REPLACE($2, '[^0-9]', '', 'g'))
      AND tp.status IN ('approved', 'in_progress')
      AND tp.approved_total IS NOT NULL
      AND tp.approved_total > COALESCE(
          (SELECT SUM(tpp.amount) FROM treatment_plan_payments tpp WHERE tpp.plan_id = tp.id),
          0
      )
    LIMIT 1
""", tenant_id, external_user_id)

has_pending_payment = (pending_apt is not None) or (pending_plan is not None)
```

### Contexto enriquecido para el agente

Si la detección activa proviene de un plan (`pending_plan is not None`):

```python
if pending_plan and not pending_apt:
    media_context += (
        "PROBABLE COMPROBANTE DE PAGO (PLAN DE TRATAMIENTO): "
        "El paciente tiene un plan de tratamiento con saldo pendiente y acaba de enviar una imagen. "
        "Es MUY probable que sea un comprobante de transferencia para cubrir una cuota del plan. "
        "ACCIÓN OBLIGATORIA: Usá 'verify_payment_receipt' para verificar el comprobante. "
        "Pasá la descripción visual como 'receipt_description' y el monto detectado como 'amount_detected'. "
        "NO digas 'ya lo guardé en tu ficha'. Decí 'Recibí tu comprobante, voy a verificarlo' y ejecutá la tool. "
        "Si la verificación es exitosa → confirmá el pago indicando el saldo actualizado del plan. "
        "Si falla → explicá qué falló (titular o monto incorrecto)."
    )
elif pending_apt and pending_plan:
    # Ambos pendientes: dar prioridad al turno (seña)
    # Usar contexto actual sin cambios — verify_payment_receipt resolverá contra el turno
    pass
```

---

## Escenarios de uso — Nova Voice

### Escenario 1: Gestión completa de plan por voz

```
Dra.: "Nova, mostrame el presupuesto de María García"
Nova: [llama ver_presupuesto_paciente(patient_name="María García")]
      "María tiene un plan de rehabilitación oral por $420.000. Pagó $150.000,
       le quedan $270.000 pendientes."

Dra.: "Aprobá el plan en $420.000"
Nova: [llama aprobar_presupuesto(patient_name="María García", approved_total=420000)]
      "Plan aprobado. $420.000 precio final. Ya pueden registrar pagos."

Dra.: "Ella pagó $80.000 en efectivo hoy"
Nova: [llama registrar_pago_plan(patient_name="María García", amount=80000, method="cash")]
      "Registrado. María pagó $80.000 en efectivo. Total pagado: $230.000 de $420.000.
       Saldo pendiente: $190.000."
```

### Escenario 2: Resumen financiero con planes

```
Dra.: "Nova, dame el resumen financiero del mes"
Nova: [llama resumen_financiero(periodo="mes")]
      "Mes de marzo: $485.000 en turnos, 3 pendientes.
       Planes de tratamiento: $230.000 cobrado este mes,
       5 planes activos, $1.070.000 total pendiente."
```

### Escenario 3: Facturación pendiente completa

```
Dra.: "¿Qué está pendiente de cobro?"
Nova: [llama facturacion_pendiente()]
      "3 turnos sin cobrar por $103.000 y
       2 planes con saldo pendiente: María García debe $270.000,
       Juan Pérez debe $70.000. Total: $443.000."
```

### Escenario 4: WhatsApp — Pago de cuota por imagen

```
Paciente (WhatsApp): [envía imagen de comprobante]
Buffer task: detecta plan activo con saldo pendiente → has_pending_payment = True
Agente: "Recibí tu comprobante, voy a verificarlo..."
        [llama verify_payment_receipt(receipt_description=..., amount_detected="50000")]
Agente: "Verificado. Registramos tu pago de $50.000 para el plan 'Rehabilitación oral'.
         Saldo actualizado: $220.000 pendientes de $420.000."
```

---

## Consideraciones técnicas

### Resolución de paciente por nombre (patrón compartido)

Los tres tools nuevos necesitan buscar paciente por nombre. Extraer función helper:

```python
async def _resolve_patient_by_name_or_id(
    args: Dict, tenant_id: int
) -> Tuple[Optional[int], Optional[str]]:
    """
    Returns (patient_id, error_message).
    If error_message is not None, the tool should return it directly.
    """
    patient_id = args.get("patient_id")
    patient_name = args.get("patient_name")

    if not patient_id and not patient_name:
        return None, "Necesito el nombre o ID del paciente."

    if patient_id:
        return patient_id, None

    rows = await db.pool.fetch("""
        SELECT id, first_name, last_name, dni
        FROM patients
        WHERE tenant_id = $1
          AND (first_name ILIKE $2 OR last_name ILIKE $2
               OR (first_name || ' ' || last_name) ILIKE $2)
        LIMIT 5
    """, tenant_id, f"%{patient_name}%")

    if not rows:
        return None, f"No encontré ningún paciente con nombre '{patient_name}'."
    if len(rows) > 1:
        names = "\n".join([
            f"  - {r['first_name']} {r['last_name'] or ''} (ID {r['id']}, DNI {r['dni'] or 'sin DNI'})"
            for r in rows
        ])
        return None, f"Encontré varios pacientes:\n{names}\n¿A cuál te referís?"

    return rows[0]['id'], None
```

### RBAC por tool

| Tool | Roles permitidos |
|------|-----------------|
| `ver_presupuesto_paciente` | ceo, secretary, professional |
| `registrar_pago_plan` | ceo, secretary |
| `aprobar_presupuesto` | ceo |
| `facturacion_pendiente` | ceo, secretary |
| `resumen_financiero` | ceo |
| `registrar_pago` (modificado) | ceo, secretary |

### Manejo de Decimal/UUID en asyncpg

- Todos los montos (`amount`, `approved_total`) deben ser `Decimal(str(value))` antes de pasarlos
  a asyncpg. El pattern existente en `_registrar_pago()` aplica.
- Los UUIDs de planes (`plan_id`) deben ser `uuid.UUID(plan_id_str)` con try/except ValueError.
- Los IDs enteros de pacientes vienen como int desde OpenAI, no necesitan conversión.

### Socket.IO events

| Evento | Payload | Cuándo |
|--------|---------|--------|
| `BILLING_UPDATED` | `{ plan_id, patient_id, tenant_id }` | `registrar_pago_plan`, `aprobar_presupuesto` |
| `PAYMENT_CONFIRMED` | `{ appointment_id, tenant_id }` | `registrar_pago` (existente, sin cambios) |

El frontend escucha `BILLING_UPDATED` para refrescar el Tab 6 "Presupuesto y Facturación"
del PatientDetail.

### Backward compatibility

- `registrar_pago` con solo `appointment_id` → comportamiento idéntico al actual
- `facturacion_pendiente` → la sección de turnos es idéntica; se agrega la sección de planes
- `resumen_financiero` → la sección de turnos es idéntica; se agrega la sección de planes
- Turnos sin `plan_item_id` → `verify_payment_receipt` funciona exactamente igual que antes

---

## Archivos afectados

| Archivo | Tipo de cambio |
|---------|----------------|
| `orchestrator_service/services/nova_tools.py` | Agregar 3 tools nuevas, modificar 3 existentes |
| `orchestrator_service/main.py` | Modificar `verify_payment_receipt` (~línea 4141) |
| `orchestrator_service/services/buffer_task.py` | Agregar detección de planes con saldo pendiente (~línea 1121) |

---

## Criterios de aceptación

- [ ] `ver_presupuesto_paciente` retorna plan con ítems, pagos y saldo pendiente correctos
- [ ] `ver_presupuesto_paciente` con nombre ambiguo lista candidatos y pide aclaración
- [ ] `registrar_pago_plan` crea `treatment_plan_payment` y `accounting_transaction`
- [ ] `registrar_pago_plan` emite `BILLING_UPDATED` por Socket.IO
- [ ] `registrar_pago_plan` actualiza `status = 'completed'` cuando saldo llega a 0
- [ ] `aprobar_presupuesto` solo permitido para CEO
- [ ] `aprobar_presupuesto` rechaza plan que no está en estado `draft`
- [ ] `facturacion_pendiente` muestra sección de planes además de turnos
- [ ] `resumen_financiero` incluye subtotales de planes en el período
- [ ] `registrar_pago` con `plan_id` delega correctamente a `_registrar_pago_plan`
- [ ] `verify_payment_receipt` detecta plan activo y crea `treatment_plan_payment` en caso exitoso
- [ ] `buffer_task.py` detecta imagen como potencial comprobante cuando hay plan con saldo pendiente
- [ ] Todos los montos usan `Decimal` antes de escribir a asyncpg
- [ ] Todos los UUIDs tienen try/except ValueError
- [ ] Backward compatibility: turnos sin plan no se ven afectados
