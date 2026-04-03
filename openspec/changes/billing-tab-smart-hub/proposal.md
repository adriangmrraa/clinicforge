# Proposal: Billing Tab Smart Hub

**Change**: billing-tab-smart-hub
**Date**: 2026-04-03

---

## Intent

Transformar la pestaña 6 "Presupuesto" de un módulo aislado (lienzo en blanco) a un **hub central de facturación inteligente** que:

1. Pre-carga automáticamente los turnos existentes del paciente con su billing data
2. Permite generar un plan de tratamiento formal con un click a partir de esa data
3. Genera PDF de presupuesto profesional (como las Fichas Digitales de pestaña 5)
4. Centraliza toda la gestión de pagos (reemplazando la pestaña Facturación del modal de turno)

## Problem Statement

### Situación actual
- Un paciente agenda por WhatsApp, paga la seña, el comprobante se verifica
- La Dra. abre la ficha → pestaña Presupuesto → ve "No hay presupuestos" (vacío)
- Toda la data de billing está en el modal de editar turno → fragmentada, no centralizada
- No se puede generar un PDF de presupuesto para enviar al paciente
- La Dra. tiene que crear un plan desde cero y agregar todo manualmente

### Lo que debería pasar
- La Dra. abre la pestaña → ve inmediatamente los turnos del paciente agrupados por tratamiento con sus montos y comprobantes
- Un botón "Generar presupuesto" arma el plan automáticamente desde esa data
- Puede ajustar precios, agregar tratamientos adicionales, aprobar
- Genera PDF profesional y lo envía por email al paciente
- Los pagos futuros (efectivo, transferencia, cuotas) se gestionan exclusivamente desde acá

## Scope

### In Scope
1. **Endpoint nuevo**: `GET /admin/patients/{id}/billing-summary` — retorna turnos + billing agrupados por tratamiento
2. **BillingTab rediseño**: 3 estados inteligentes (sin turnos, con turnos sin plan, con plan formal)
3. **Auto-generación de plan**: botón que crea plan + items + migra pagos existentes desde appointments
4. **PDF de presupuesto**: template Jinja2, generación, descarga, envío por email (patrón de pestaña 5)
5. **Modal de turno**: pestaña Facturación pasa a vista resumida con link a pestaña 6

### Out of Scope
- Factura electrónica AFIP
- Integración contable externa
- Presupuestos múltiples por paciente (se mantiene la funcionalidad pero no es el foco)

## Approach

### Estado 1: Sin turnos
```
┌────────────────────────────────────┐
│      📋 Sin actividad aún         │
│  Este paciente no tiene turnos    │
│  agendados ni presupuestos.       │
│                                    │
│  [+ Crear presupuesto vacío]      │
└────────────────────────────────────┘
```

### Estado 2: Con turnos, sin plan formal (CASO MÁS COMÚN)
```
┌────────────────────────────────────────────────────┐
│  Turnos del paciente                               │
│  ──────────────────────────────────────            │
│  🦷 Cleaning (Limpieza dental)                    │
│     Turno: 07/04/2026 — Dr. Pérez — SCHEDULED     │
│     Monto: $7.899.998                              │
│     Pago: ✅ Verificado ($20.000 seña)             │
│                                                    │
│  🦷 Implante                                      │
│     Turno: 15/04/2026 — Dra. Delgado — SCHEDULED  │
│     Monto: $200.000                                │
│     Pago: ⏳ Pendiente                             │
│                                                    │
│  ════════════════════════════════════              │
│  Total estimado: $8.099.998                        │
│  Pagado: $20.000 | Pendiente: $8.079.998           │
│                                                    │
│  [✨ Generar presupuesto desde turnos]             │
│  [+ Crear presupuesto vacío]                       │
└────────────────────────────────────────────────────┘
```

### Estado 3: Con plan formal
```
Vista actual mejorada:
- Header del plan con status
- Items con turnos vinculados
- Pagos registrados
- Barra de progreso
- [📄 Generar PDF] [📧 Enviar por email]
```

### PDF de presupuesto
Template profesional con:
- Logo de la clínica + datos del profesional
- Datos del paciente (nombre, DNI, teléfono)
- Tabla de tratamientos con precios (estimado vs aprobado)
- Total del presupuesto
- Condiciones de pago (cuotas, métodos aceptados)
- Espacio para firma
- Fecha de validez

### Endpoint nuevo: GET /admin/patients/{id}/billing-summary
Retorna:
```json
{
  "appointments": [
    {
      "id": "uuid",
      "datetime": "2026-04-07T07:00:00",
      "status": "scheduled",
      "treatment_code": "cleaning",
      "treatment_name": "Limpieza dental",
      "professional_name": "Dr. Pérez",
      "billing_amount": 7899998,
      "payment_status": "paid",
      "payment_receipt": { "status": "verified", "amount_detected": 20000 }
    }
  ],
  "treatment_groups": [
    {
      "treatment_code": "cleaning",
      "treatment_name": "Limpieza dental",
      "base_price": 5000,
      "appointments": [...],
      "total_billed": 7899998,
      "total_paid": 20000,
      "total_pending": 7879998
    }
  ],
  "totals": {
    "estimated": 8099998,
    "paid": 20000,
    "pending": 8079998
  },
  "has_active_plan": false,
  "active_plan_id": null
}
```

### Auto-generación de plan
Cuando la Dra. toca "Generar presupuesto desde turnos":
1. Crea `treatment_plan` con nombre auto-generado ("Tratamiento de [paciente]")
2. Por cada treatment_group, crea un `treatment_plan_item` con el estimated_price
3. Vincula cada appointment al item correspondiente (plan_item_id)
4. Migra pagos verificados: por cada appointment con payment_status='paid', crea un `treatment_plan_payment`
5. El plan se crea en estado `draft` — la Dra. ajusta y aprueba

### Modal de turno: Facturación simplificada
La pestaña "Facturación" del modal de editar turno pasa a mostrar:
- Resumen read-only del billing actual
- Si tiene plan: "Este turno pertenece al plan [nombre]" + botón "Ver presupuesto"
- El botón navega a la pestaña 6 del paciente

## Risks

| Risk | Mitigation |
|------|------------|
| Migración de pagos duplica accounting_transactions | Solo migrar si no existe en plan_payments ya |
| Plan auto-generado tiene precios incorrectos | Draft por defecto, Dra. siempre revisa y aprueba |
| PDF generation no disponible (WeasyPrint) | Fallback: mostrar HTML printable |

## Success Criteria

- Paciente con turnos existentes → pestaña muestra resumen inmediato (no vacío)
- "Generar presupuesto" crea plan con items y pagos pre-cargados en < 2 segundos
- PDF profesional descargable y enviable por email
- La Dra. puede gestionar todo el ciclo de facturación desde una sola pestaña
