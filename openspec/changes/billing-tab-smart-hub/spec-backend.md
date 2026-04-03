# Spec: Billing Tab Smart Hub — Backend

---

## EP-NEW-01: GET /admin/patients/{patient_id}/billing-summary

Retorna el resumen completo de facturación del paciente: turnos con billing agrupados por tratamiento, totales, y si tiene plan activo.

### Request
```
GET /admin/patients/{patient_id}/billing-summary
Authorization: Bearer {jwt}
X-Admin-Token: {token}
```

### SQL Query
```sql
SELECT
    a.id as appointment_id,
    a.appointment_datetime,
    a.status as appointment_status,
    a.appointment_type,
    COALESCE(tt.name, a.appointment_type, 'Consulta') as treatment_name,
    tt.base_price,
    tt.code as treatment_code,
    COALESCE(a.billing_amount, tt.base_price, 0) as billing_amount,
    a.billing_installments,
    a.billing_notes,
    a.payment_status,
    a.payment_receipt_data,
    a.plan_item_id,
    prof.first_name || ' ' || COALESCE(prof.last_name, '') as professional_name,
    a.duration_minutes
FROM appointments a
LEFT JOIN treatment_types tt ON tt.code = a.appointment_type AND tt.tenant_id = $1
LEFT JOIN professionals prof ON prof.id = a.professional_id AND prof.tenant_id = $1
WHERE a.tenant_id = $1
  AND a.patient_id = $2
  AND a.status NOT IN ('cancelled', 'deleted')
ORDER BY a.appointment_datetime DESC
```

### Response Shape
```json
{
  "appointments": [
    {
      "id": "uuid",
      "datetime": "ISO8601",
      "status": "scheduled|confirmed|completed",
      "treatment_code": "cleaning",
      "treatment_name": "Limpieza dental",
      "base_price": 5000.0,
      "billing_amount": 7899998.0,
      "billing_installments": 1,
      "billing_notes": "...",
      "payment_status": "pending|partial|paid",
      "payment_receipt": { ... } | null,
      "professional_name": "Dr. Pérez",
      "plan_item_id": "uuid" | null,
      "duration_minutes": 30
    }
  ],
  "treatment_groups": [
    {
      "treatment_code": "cleaning",
      "treatment_name": "Limpieza dental",
      "base_price": 5000.0,
      "appointments": [ ...references... ],
      "appointment_count": 1,
      "total_billed": 7899998.0,
      "total_paid": 20000.0,
      "total_pending": 7879998.0
    }
  ],
  "totals": {
    "estimated": 8099998.0,
    "paid": 20000.0,
    "pending": 8079998.0,
    "appointment_count": 2
  },
  "has_active_plan": false,
  "active_plan_id": null
}
```

### Lógica de agrupación (Python)
```python
# Agrupar por treatment_code
groups = {}
for apt in appointments:
    code = apt["treatment_code"] or "sin_tipo"
    if code not in groups:
        groups[code] = { "appointments": [], "total_billed": 0, "total_paid": 0 }
    groups[code]["appointments"].append(apt)
    groups[code]["total_billed"] += apt["billing_amount"]
    if apt["payment_status"] == "paid":
        groups[code]["total_paid"] += apt["billing_amount"]

# Check active plan
active_plan = await pool.fetchrow(
    "SELECT id FROM treatment_plans WHERE tenant_id=$1 AND patient_id=$2 AND status IN ('draft','approved','in_progress') LIMIT 1",
    tenant_id, patient_id
)
```

---

## EP-NEW-02: POST /admin/patients/{patient_id}/generate-plan-from-appointments

Genera un plan de tratamiento automáticamente a partir de los turnos existentes del paciente.

### Request Body
```json
{
  "name": "Tratamiento de Lucas Puig",  // opcional, auto-genera si no se envía
  "professional_id": 5                   // opcional
}
```

### Lógica
1. Fetch appointments del paciente (misma query que billing-summary)
2. Crear `treatment_plan` con status='draft'
3. Por cada treatment_group, crear `treatment_plan_item`:
   - `treatment_type_code` = group.treatment_code
   - `estimated_price` = SUM(billing_amount) del grupo (o base_price si billing_amount es 0)
   - `custom_description` = treatment_name
4. Vincular cada appointment al item: `UPDATE appointments SET plan_item_id = $item_id WHERE id = $apt_id`
5. Por cada appointment con payment_status='paid' Y payment_receipt_data.status='verified':
   - Crear `treatment_plan_payment` con amount = payment_receipt_data.amount_detected (o billing_amount)
   - Sync a `accounting_transactions` (si no existe ya)
6. Recalcular totales del plan

### Response
```json
{
  "status": "created",
  "plan_id": "uuid",
  "items_created": 2,
  "payments_migrated": 1,
  "estimated_total": 8099998.0
}
```

### Validaciones
- Si ya tiene plan activo → HTTP 409 "El paciente ya tiene un presupuesto activo"
- Si no tiene turnos → HTTP 422 "No hay turnos para generar presupuesto"
- Emitir TREATMENT_PLAN_CREATED socket event

---

## EP-NEW-03: POST /admin/treatment-plans/{plan_id}/generate-pdf

Genera un PDF de presupuesto profesional.

### Lógica (patrón de Digital Records)
1. Fetch plan detail (items, payments, totals)
2. Fetch patient data (nombre, DNI, teléfono)
3. Fetch tenant data (clinic name, address, logo_url)
4. Render Jinja2 template `templates/budget/presupuesto.html` con los datos
5. Generar PDF con WeasyPrint (en thread)
6. Guardar en disco: `/app/uploads/budgets/{tenant_id}/{plan_id}.pdf`
7. Retornar FileResponse

### Response
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="Presupuesto_LucasPuig.pdf"
```

---

## EP-NEW-04: POST /admin/treatment-plans/{plan_id}/send-email

Envía el PDF de presupuesto por email al paciente.

### Request Body
```json
{
  "to_email": "paciente@email.com"
}
```

### Lógica
1. Generar PDF si no existe (lazy, como digital records)
2. Enviar email con PDF adjunto via `email_service.send_budget_email()`
3. Registrar envío (fecha, destinatario)

### Response
```json
{
  "success": true,
  "message": "Presupuesto enviado a paciente@email.com"
}
```
