# Spec: Billing Tab Smart Hub — Frontend

---

## Rediseño de BillingTab.tsx

### 3 Estados del componente

El componente decide qué renderizar basado en:
- `billingData.appointments.length` — tiene turnos?
- `billingData.has_active_plan` — tiene plan formal?

```typescript
type BillingViewState = 'loading' | 'empty' | 'appointments_only' | 'plan_view';
```

### Estado 1: empty (sin turnos ni plan)

```
┌──────────────────────────────────────┐
│           📋                         │
│   Sin actividad aún                  │
│   Este paciente no tiene turnos      │
│   agendados ni presupuestos.         │
│                                      │
│   [+ Crear presupuesto vacío]        │
└──────────────────────────────────────┘
```

### Estado 2: appointments_only (con turnos, sin plan)

**Sección: Resumen de turnos**

Cards por tratamiento, cada una muestra:
- Nombre del tratamiento (badge de color por categoría)
- Lista de turnos: fecha, hora, profesional, status badge
- Monto (billing_amount o base_price)
- Status de pago con receipt info si existe:
  - ✅ Verificado ($X seña) — verde
  - ⏳ Pendiente — amarillo
  - 🔍 En revisión — naranja

**Sección: Totales**
```
Total estimado: $8.099.998
Pagado: $20.000 (0.2%)
Pendiente: $8.079.998
```

**Sección: Acciones**
```
[✨ Generar presupuesto desde turnos]  ← botón primario grande
[+ Crear presupuesto vacío]            ← botón secundario pequeño
```

**API call**: `GET /admin/patients/{patientId}/billing-summary`

### Estado 3: plan_view (con plan formal)

Vista actual mejorada con:
- Todo lo existente (header, items, pagos, progress bar)
- NUEVO: Botones de PDF y email

```
┌──────────────────────────────────────┐
│ Plan: Tratamiento de Lucas   [APROBADO] │
│ Dra. Delgado — Aprobado: 3 Abr 2026    │
│                                          │
│ [📄 Generar PDF] [📧 Enviar email]      │
│                                          │
│ ... items, pagos, progress bar ...       │
└──────────────────────────────────────┘
```

**Botón "Generar PDF"**:
- `POST /admin/treatment-plans/{planId}/generate-pdf`
- responseType: 'blob' → trigger download
- Loading spinner mientras genera

**Botón "Enviar email"**:
- Modal con input de email (pre-filled con patient email)
- `POST /admin/treatment-plans/{planId}/send-email`
- Success toast

---

## Componentes nuevos

### AppointmentBillingCard
Muestra un grupo de tratamiento con sus turnos y billing.

```tsx
interface TreatmentGroupCardProps {
  group: {
    treatment_code: string;
    treatment_name: string;
    base_price: number;
    appointments: AppointmentBilling[];
    total_billed: number;
    total_paid: number;
    total_pending: number;
  };
}
```

### PaymentReceiptBadge
Mini badge que muestra el estado del comprobante.

```tsx
// ✅ Verificado ($20.000)
// ⏳ Pendiente
// 🔍 En revisión
// ❌ Rechazado
```

### BudgetPdfModal
Modal para enviar PDF por email.

```tsx
interface BudgetPdfModalProps {
  planId: string;
  patientEmail?: string;
  onClose: () => void;
}
```

---

## API Calls Summary

| Acción | Endpoint | Trigger |
|--------|----------|---------|
| Load billing data | `GET /admin/patients/{id}/billing-summary` | On tab mount + refreshKey |
| Generate plan from appointments | `POST /admin/patients/{id}/generate-plan-from-appointments` | Button click |
| Download PDF | `POST /admin/treatment-plans/{id}/generate-pdf` (blob) | Button click |
| Send email | `POST /admin/treatment-plans/{id}/send-email` | Modal confirm |
| Existing: load plan detail | `GET /admin/treatment-plans/{id}` | After plan select |
| Existing: register payment | `POST /admin/treatment-plans/{id}/payments` | Modal confirm |

---

## i18n keys nuevas (billing.*)

```json
{
  "billing": {
    "no_activity": "Sin actividad aún",
    "no_activity_desc": "Este paciente no tiene turnos agendados ni presupuestos.",
    "create_empty": "Crear presupuesto vacío",
    "appointments_summary": "Resumen de turnos",
    "generate_from_appointments": "Generar presupuesto desde turnos",
    "total_estimated": "Total estimado",
    "receipt_verified": "Verificado",
    "receipt_pending": "Pendiente",
    "receipt_review": "En revisión",
    "generate_pdf": "Generar PDF",
    "send_email": "Enviar por email",
    "send_email_title": "Enviar presupuesto por email",
    "send_email_to": "Email del paciente",
    "send_email_success": "Presupuesto enviado",
    "generating_pdf": "Generando PDF...",
    "plan_belongs": "Este turno pertenece al plan",
    "go_to_plan": "Ver presupuesto"
  }
}
```

---

## Responsive (Mobile)

- Treatment group cards: stack vertically, full width
- Appointment rows dentro de cada card: compact (fecha + status en una línea, monto en otra)
- Botones de acción: full width en mobile, inline en desktop
- PDF/Email modals: bottom-sheet en mobile

---

## Modal de turno: Facturación simplificada

### Archivo: AppointmentForm.tsx

En la pestaña "Facturación" del modal de editar turno, cambiar a:

**Si el turno tiene plan_item_id**:
```
┌──────────────────────────────────┐
│ Este turno pertenece al plan:    │
│ "Tratamiento de Lucas"           │
│                                  │
│ [Ver presupuesto completo →]     │
│                                  │
│ Resumen:                         │
│ Monto: $7.899.998               │
│ Estado: ✅ Pagado                │
└──────────────────────────────────┘
```
Los campos de billing son read-only. El botón navega a PatientDetail pestaña 6.

**Si el turno NO tiene plan_item_id**: Mantener el comportamiento actual (editable).
