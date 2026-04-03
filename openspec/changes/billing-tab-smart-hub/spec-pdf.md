# Spec: Billing Tab Smart Hub — PDF de Presupuesto

---

## Template: presupuesto.html

### Ubicación
`orchestrator_service/templates/budget/presupuesto.html`

### Datos de entrada
```python
template.render(
    clinic=clinic_data,       # name, address, phone, logo_url
    patient=patient_data,     # full_name, dni, phone, email
    professional=prof_data,   # full_name, specialty
    plan=plan_data,           # name, status, approved_total, created_at, approved_at
    items=items_list,         # [{treatment_name, estimated_price, approved_price, status}]
    payments=payments_list,   # [{date, amount, method, notes}]
    totals=totals_data,       # {estimated, approved, paid, pending, progress_pct}
    generated_at=datetime,    # Fecha de generación
)
```

### Diseño del PDF

```
┌──────────────────────────────────────────────────┐
│  [LOGO]  Clínica Dra. Laura Delgado              │
│          Dirección | Teléfono                     │
│                                                    │
│  ═══════════════════════════════════              │
│  PRESUPUESTO DE TRATAMIENTO                       │
│  ═══════════════════════════════════              │
│                                                    │
│  Paciente: Lucas Puig                             │
│  DNI: 457899000                                    │
│  Teléfono: +5493434732389                         │
│  Fecha: 3 de abril de 2026                        │
│                                                    │
│  Profesional: Dra. Laura Delgado                  │
│  ─────────────────────────────────                │
│                                                    │
│  DETALLE DE TRATAMIENTOS                          │
│  ┌────────────────────┬────────────┬────────────┐ │
│  │ Tratamiento        │ Estimado   │ Final      │ │
│  ├────────────────────┼────────────┼────────────┤ │
│  │ Limpieza dental    │ $5.000     │ $5.000     │ │
│  │ Implante pieza 36  │ $200.000   │ $180.000   │ │
│  │ Corona definitiva  │ $150.000   │ $140.000   │ │
│  ├────────────────────┼────────────┼────────────┤ │
│  │ TOTAL              │ $355.000   │ $325.000   │ │
│  └────────────────────┴────────────┴────────────┘ │
│                                                    │
│  ESTADO DE PAGOS                                  │
│  Total aprobado: $325.000                         │
│  Pagado: $20.000                                  │
│  Saldo pendiente: $305.000                        │
│                                                    │
│  CONDICIONES                                      │
│  • Presupuesto válido por 30 días                 │
│  • Precios sujetos a evaluación clínica           │
│  • Métodos de pago: Efectivo, Transferencia,      │
│    Tarjeta de débito/crédito                      │
│                                                    │
│  ─────────────────────────────────                │
│                                                    │
│  Firma profesional          Firma paciente        │
│  ___________________       ___________________    │
│                                                    │
│  Generado: 3/4/2026 a las 17:30                   │
└──────────────────────────────────────────────────┘
```

### Estilos CSS (inline para WeasyPrint)
- Font: system-ui, sans-serif
- Colores: negro sobre blanco (impresión)
- Logo: max-height 60px, float left
- Tabla: borders 1px solid #ccc, padding 8px
- Total row: font-weight bold, background #f5f5f5
- Footer: font-size 10px, color #666

### Función gather_budget_data()

```python
async def gather_budget_data(pool, plan_id: str, tenant_id: int) -> dict:
    """Recopila datos para el PDF de presupuesto."""
    # 1. Plan + patient + professional
    plan = await pool.fetchrow("""
        SELECT tp.*,
               pat.first_name || ' ' || COALESCE(pat.last_name, '') as patient_name,
               pat.dni, pat.phone_number, pat.email,
               prof.first_name || ' ' || COALESCE(prof.last_name, '') as professional_name,
               prof.specialty
        FROM treatment_plans tp
        JOIN patients pat ON tp.patient_id = pat.id
        LEFT JOIN professionals prof ON tp.professional_id = prof.id
        WHERE tp.id = $1 AND tp.tenant_id = $2
    """, plan_id, tenant_id)

    # 2. Items
    items = await pool.fetch("""
        SELECT tpi.*, tt.name as treatment_name
        FROM treatment_plan_items tpi
        LEFT JOIN treatment_types tt ON tt.code = tpi.treatment_type_code AND tt.tenant_id = $1
        WHERE tpi.plan_id = $2 AND tpi.tenant_id = $1
        ORDER BY tpi.sort_order, tpi.created_at
    """, tenant_id, plan_id)

    # 3. Payments
    payments = await pool.fetch("""
        SELECT * FROM treatment_plan_payments
        WHERE plan_id = $1 AND tenant_id = $2
        ORDER BY payment_date DESC
    """, plan_id, tenant_id)

    # 4. Clinic
    clinic = await pool.fetchrow("""
        SELECT name, address, phone, logo_url FROM tenants WHERE id = $1
    """, tenant_id)

    return { "plan": plan, "items": items, "payments": payments, "clinic": clinic }
```

### Email de presupuesto

Usar el mismo patrón de `email_service`:
```python
def send_budget_email(self, to_email, pdf_path, patient_name, clinic_name):
    """Envía presupuesto por email con PDF adjunto."""
    # Subject: "Presupuesto de tratamiento — {clinic_name}"
    # Body HTML: template simple con mensaje + instrucciones
    # Attachment: PDF
```
