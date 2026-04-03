# Spec General: Billing Tab Smart Hub

---

## Objetivo
Transformar la pestaña 6 en el hub central de facturación que pre-carga datos existentes, genera presupuestos automáticamente, y produce PDFs profesionales.

## Componentes del cambio

| # | Componente | Spec | Archivos |
|---|-----------|------|----------|
| 1 | Endpoint billing-summary | spec-backend.md EP-NEW-01 | admin_routes.py |
| 2 | Endpoint generate-plan-from-appointments | spec-backend.md EP-NEW-02 | admin_routes.py |
| 3 | Endpoint generate-pdf | spec-backend.md EP-NEW-03 | admin_routes.py, budget_service.py |
| 4 | Endpoint send-email | spec-backend.md EP-NEW-04 | admin_routes.py, email_service.py |
| 5 | BillingTab rediseño (3 estados) | spec-frontend.md | BillingTab.tsx |
| 6 | PDF template | spec-pdf.md | templates/budget/presupuesto.html |
| 7 | gather_budget_data | spec-pdf.md | services/budget_service.py |
| 8 | AppointmentForm simplificación | spec-frontend.md | AppointmentForm.tsx |
| 9 | i18n keys | spec-frontend.md | es.json, en.json, fr.json |

## Flujos principales

### Flujo 1: Paciente nuevo post-chat
```
Chat WhatsApp → Turno agendado → Seña pagada → Comprobante verificado
    ↓
Dra. abre ficha → Pestaña Presupuesto
    ↓
Estado 2: Ve turnos con billing data pre-cargada
    ↓
Click "Generar presupuesto desde turnos"
    ↓
Plan draft creado con items + pagos migrados
    ↓
Dra. ajusta precios → Aprueba
    ↓
Click "Generar PDF" → Descarga
    ↓
Click "Enviar email" → Paciente recibe presupuesto
```

### Flujo 2: Gestión de pagos continua
```
Paciente envía comprobante por WhatsApp
    ↓
IA verifica contra saldo del plan
    ↓
treatment_plan_payment creado automáticamente
    ↓
Dra. abre pestaña Presupuesto → ve pago actualizado
    ↓
Barra de progreso avanza
    ↓
Cuando fully paid → plan auto-completa
```

### Flujo 3: Presupuesto desde cero
```
Dra. abre ficha de paciente sin turnos
    ↓
Estado 1: "Sin actividad"
    ↓
Click "Crear presupuesto vacío"
    ↓
Agrega items manualmente
    ↓
Aprueba → PDF → Email
```

## Diagrama de arquitectura

```
BillingTab.tsx
├── Estado empty → EmptyState component
├── Estado appointments_only
│   ├── GET /billing-summary → TreatmentGroupCards
│   ├── Button: "Generar presupuesto" → POST /generate-plan-from-appointments
│   └── Button: "Crear vacío" → POST /treatment-plans (existente)
└── Estado plan_view
    ├── GET /treatment-plans/{id} (existente)
    ├── Items + Payments (existente)
    ├── Button: "Generar PDF" → POST /generate-pdf → blob download
    ├── Button: "Enviar email" → Modal → POST /send-email
    └── Button: "Registrar pago" (existente)
```

## Prioridad de implementación

1. **EP-NEW-01** (billing-summary) — sin esto no hay datos para mostrar
2. **BillingTab rediseño** (estados 1 y 2) — la experiencia core
3. **EP-NEW-02** (generate-plan) — el botón mágico
4. **EP-NEW-03 + EP-NEW-04** (PDF + email) — el deliverable final
5. **PDF template** — diseño profesional
6. **AppointmentForm simplificación** — polish
