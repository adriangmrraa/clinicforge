# Spec Frontend: Tab "Presupuesto y Facturación" — BillingTab

**Change**: treatment-plan-billing
**Artifact**: spec-frontend
**Status**: Draft
**Date**: 2026-04-03

---

## 1. Scope

This spec covers the complete frontend implementation of Tab 6 "Presupuesto y Facturación" in `PatientDetail.tsx`. It includes the `BillingTab` component, four child modals, the integration patch to `PatientDetail.tsx`, and the i18n key additions required across all three locale files.

Out of scope: backend endpoints, Alembic migrations, Nova tools (separate specs).

---

## 2. Functional Requirements

### FR-001 — Plan Selector Bar
- **FR-001.1** When the patient has 0 treatment plans, render an empty state: centered icon + message "Este paciente no tiene presupuestos" + primary CTA button "Crear presupuesto".
- **FR-001.2** When the patient has exactly 1 plan, auto-select it on mount. Do not render a dropdown.
- **FR-001.3** When the patient has 2+ plans, render a `<select>` dropdown. Each `<option>` shows the plan name + status badge text (e.g. "Rehabilitación oral — Borrador"). Add a "Nuevo plan" button to the right of the dropdown.
- **FR-001.4** The selected plan ID is the source of truth for all child sections. Changing the dropdown must reset the payment and item views to the new plan.
- **FR-001.5** After any CRUD action that creates a plan, the selector must reload the plan list and auto-select the newly created plan.

### FR-002 — Plan Header Card
- **FR-002.1** Display the plan name. The name is editable inline: clicking it transforms it into an `<input>`. Pressing Enter or clicking outside triggers `PATCH /admin/treatment-plans/{planId}` with `{ name }` and reverts to static text.
- **FR-002.2** Display a status badge with the following color mapping:
  - `draft` → `bg-white/10 text-white/60`
  - `approved` → `bg-blue-500/10 text-blue-400`
  - `in_progress` → `bg-yellow-500/10 text-yellow-400`
  - `completed` → `bg-green-500/10 text-green-400`
  - `cancelled` → `bg-red-500/10 text-red-400`
- **FR-002.3** Display the assigned professional's name if `professional_id` is set; otherwise show "Sin profesional".
- **FR-002.4** Show the "Aprobar presupuesto" button ONLY when `status === 'draft'`. Clicking it opens `ApprovePlanModal`.
- **FR-002.5** Display a 4-cell summary row: "Total estimado" | "Total aprobado" | "Pagado" | "Pendiente". All values formatted as currency (ARS, locale `es-AR`).
  - Total estimado = sum of `item.estimated_price`
  - Total aprobado = `plan.approved_total ?? estimatedTotal`
  - Pagado = sum of `payment.amount`
  - Pendiente = approved_total − pagado (can be negative if overpaid, show in red)

### FR-003 — Financial Progress Bar
- **FR-003.1** Render a full-width rounded bar. The green filled portion represents `(totalPaid / approvedTotal) * 100`, clamped to [0, 100].
- **FR-003.2** Below the bar, show the text: `$170.000 / $420.000 (40%)` using the resolved totals.
- **FR-003.3** If `approvedTotal === 0`, show the bar empty (0%) with text "Sin total aprobado".
- **FR-003.4** If `totalPaid >= approvedTotal`, fill the bar fully green and show "Pagado completo" badge.

### FR-004 — Items Section
- **FR-004.1** Section title "Tratamientos" with a "Agregar tratamiento" button aligned to the right.
- **FR-004.2** On desktop (≥ 768px), render a table with columns: Tratamiento | Precio est. | Precio final | Turnos | Estado. On mobile (< 768px), render each item as a stacked card.
- **FR-004.3** Tratamiento column: show `item.custom_description` if set; otherwise show the treatment type name resolved from `item.treatment_type_code`.
- **FR-004.4** Precio est. column: read-only, formatted currency. Shows `item.estimated_price`.
- **FR-004.5** Precio final column: inline editable. Clicking the cell shows an `<input type="number">` pre-filled with `item.approved_price ?? item.estimated_price`. Pressing Enter calls `PATCH /admin/treatment-plan-items/{itemId}` with `{ approved_price }`. Pressing Escape cancels. Shows a subtle edit icon on hover when not editing.
- **FR-004.6** Turnos column: show the count of linked appointments. On hover (desktop) or tap (mobile), expand a small popover/tooltip listing each appointment with date and status badge (matching the existing appointment status color system: confirmed=green, pending=yellow, cancelled=red).
- **FR-004.7** Estado column: badge with same status system as plans: `pending`, `in_progress`, `completed`, `cancelled`.
- **FR-004.8** Each item row has a trailing delete icon (Trash2 from lucide-react). Clicking shows an inline confirmation: "¿Eliminar este tratamiento del plan?" with Confirm/Cancel. Confirmed calls `DELETE /admin/treatment-plan-items/{itemId}`.
- **FR-004.9** If the plan has 0 items, show: "No hay tratamientos en este plan. Agregá el primero." with a CTA button.
- **FR-004.10** Clicking "Agregar tratamiento" opens `AddItemModal`.

### FR-005 — Payments Section
- **FR-005.1** Section title "Pagos registrados" with a "Registrar pago" button aligned right. Button is disabled if `plan.status === 'cancelled'`.
- **FR-005.2** Table columns: Fecha | Monto | Método | Registrado por | Notas | (delete).
- **FR-005.3** Método column shows an icon + label:
  - `cash` → `Banknote` icon + "Efectivo"
  - `transfer` → `ArrowRightLeft` icon + "Transferencia"
  - `card` → `CreditCard` icon + "Tarjeta"
- **FR-005.4** Notas column: truncated to 40 chars with a "..." tooltip showing full text on hover.
- **FR-005.5** Each payment row has a trailing delete icon (Trash2). Clicking it shows an inline confirmation before calling `DELETE /admin/treatment-plan-payments/{paymentId}`.
- **FR-005.6** If 0 payments, show: "No hay pagos registrados aún." (no CTA — CTA lives in the header row).
- **FR-005.7** Clicking "Registrar pago" opens `RegisterPaymentModal`.

### FR-006 — Modals

#### FR-006.1 CreatePlanModal
- Fields:
  - `name` (text, required): "Nombre del presupuesto" — placeholder "Rehabilitación oral completa"
  - `professional_id` (select, optional): populated from `GET /admin/professionals`. Placeholder "Sin profesional asignado".
  - `notes` (textarea, optional): "Notas internas"
- Submit calls `POST /admin/treatment-plans` with `{ patient_id, name, professional_id, notes, tenant_id }`.
- On success: close modal, reload plans list, auto-select new plan, emit internal event to trigger item addition flow.

#### FR-006.2 AddItemModal
- Fields:
  - `treatment_type_code` (select): populated from `GET /admin/treatment-types`. Options: code + name + base_price. Placeholder "Seleccionar tratamiento".
  - `custom_description` (text, optional): "Descripción personalizada" — placeholder "Implante pieza 36". If filled, overrides the treatment type name in the items table.
  - `estimated_price` (number): auto-filled when a treatment type is selected (from `base_price`). Editable.
- Submit calls `POST /admin/treatment-plan-items` with `{ plan_id, treatment_type_code, custom_description, estimated_price }`.
- On success: close modal, reload items for the current plan.

#### FR-006.3 RegisterPaymentModal
- Fields:
  - `amount` (number, required): placeholder = pending balance in ARS. Shows helper text "Saldo pendiente: $X".
  - `payment_method` (toggle, required): three buttons "Efectivo | Transferencia | Tarjeta". Default: "Efectivo".
  - `payment_date` (date, required): default = today in ISO format.
  - `notes` (textarea, optional).
- Submit calls `POST /admin/treatment-plan-payments` with `{ plan_id, amount, payment_method, payment_date, notes }`.
- On success: close modal, reload payments and plan summary.

#### FR-006.4 ApprovePlanModal
- Shows: "Aprobar presupuesto" title.
- Body: "Revisá el total antes de aprobar. Una vez aprobado, el plan queda activo y se puede comenzar a cobrar."
- Field: `approved_total` (number, required). Pre-filled with current `estimatedTotal`. Shows label "Total aprobado (ARS)".
- Submit calls `PATCH /admin/treatment-plans/{planId}` with `{ status: 'approved', approved_total }`.
- On success: close modal, reload plan header.

### FR-007 — Real-time Updates
- `BillingTab` listens on its own socket connection (via the `socketRef` passed from `PatientDetail` or a dedicated one).
- Events that trigger `reloadPlan()` (full re-fetch of the selected plan):
  - `TREATMENT_PLAN_UPDATED` with matching `patient_id`
  - `BILLING_UPDATED` with matching `patient_id`
- On event receipt: silently re-fetch without resetting the selected plan ID or scroll position.

### FR-008 — Responsive Behavior
- Mobile (< 768px):
  - Plan selector bar stacks vertically: dropdown on top, "Nuevo plan" button full-width below.
  - Plan header summary: 2x2 grid instead of 4-column row.
  - Items section: card layout (one card per item, all fields stacked).
  - Payments section: simplified rows showing amount, method icon, and date only. Tap to expand full row.
  - All modals are full-screen (bottom sheet style: `fixed inset-x-0 bottom-0 rounded-t-2xl`).
- Desktop (≥ 768px):
  - All sections use table layout.
  - Modals are centered dialogs (`max-w-md mx-auto`).

### FR-009 — Error States
- All API errors are caught and shown as an inline `bg-red-500/10 text-red-400` error banner inside the relevant section (not a global alert or toast).
- Network errors on inline edits (plan name, approved_price) must revert the field to its previous value and show an error indicator (red border + error text below the input).
- Forbidden errors (403) should display "No tenés permisos para realizar esta acción" and disable the triggering action.

### FR-010 — Loading States
- On initial mount (`loadPlans`): render a skeleton loader for the Plan Selector Bar — a gray rounded bar with pulse animation.
- On plan detail fetch: render skeleton loaders for the header card, items table, and payments table simultaneously.
- Inline saves (plan name, approved_price): show a `Loader2` spinner (lucide-react, size 14) replacing the save icon while the request is in flight.
- Modal submit buttons: show `Loader2 animate-spin` and disable the button while the request is in flight.

---

## 3. Component Hierarchy

```
BillingTab
├── PlanSelectorBar
│   ├── <select> (plan dropdown, shown when N≥2)
│   └── CreatePlanButton → CreatePlanModal
├── EmptyState (shown when 0 plans)
│   └── CreatePlanButton → CreatePlanModal
├── PlanHeaderCard (shown when plan selected)
│   ├── InlinePlanNameEditor
│   ├── StatusBadge
│   ├── ApprovePlanButton → ApprovePlanModal
│   └── SummaryKPIRow [4 cells]
├── FinancialProgressBar (shown when plan selected)
├── ItemsSection (shown when plan selected)
│   ├── ItemsTable (desktop) / ItemsCards (mobile)
│   │   └── ItemRow
│   │       ├── InlineApprovedPriceEditor
│   │       ├── AppointmentsPopover
│   │       └── DeleteItemConfirm
│   └── AddItemButton → AddItemModal
└── PaymentsSection (shown when plan selected)
    ├── PaymentsTable
    │   └── PaymentRow
    │       └── DeletePaymentConfirm
    └── RegisterPaymentButton → RegisterPaymentModal
```

**All modals** are rendered at the `BillingTab` root level (not nested inside sections) to avoid z-index and scroll isolation issues. They use a shared `Modal` base component (`frontend_react/src/components/Modal.tsx`) if it accepts `isOpen` + `onClose` props; otherwise implement a standalone overlay.

---

## 4. State Management

`BillingTab` is a single self-contained component. No global state (no Context, no Zustand) is required. All state lives in `useState` hooks at the `BillingTab` level or in each modal.

```typescript
// BillingTab state
const [plans, setPlans] = useState<TreatmentPlan[]>([]);
const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
const [planDetail, setPlanDetail] = useState<TreatmentPlanDetail | null>(null);
const [loadingPlans, setLoadingPlans] = useState(true);
const [loadingDetail, setLoadingDetail] = useState(false);
const [error, setError] = useState<string | null>(null);

// Modal visibility
const [showCreatePlan, setShowCreatePlan] = useState(false);
const [showAddItem, setShowAddItem] = useState(false);
const [showRegisterPayment, setShowRegisterPayment] = useState(false);
const [showApprovePlan, setShowApprovePlan] = useState(false);

// Inline edit state (items)
const [editingItemId, setEditingItemId] = useState<string | null>(null);
const [editingItemPrice, setEditingItemPrice] = useState<string>('');

// Inline edit state (plan name)
const [editingPlanName, setEditingPlanName] = useState(false);
const [planNameDraft, setPlanNameDraft] = useState('');

// Inline delete confirmations
const [deletingItemId, setDeletingItemId] = useState<string | null>(null);
const [deletingPaymentId, setDeletingPaymentId] = useState<string | null>(null);
```

`planDetail` contains the fully denormalized plan object from the detail endpoint:

```typescript
interface TreatmentPlanDetail {
  id: string;
  name: string;
  status: 'draft' | 'approved' | 'in_progress' | 'completed' | 'cancelled';
  professional_id: number | null;
  professional_name: string | null;
  approved_total: number | null;
  estimated_total: number;         // computed server-side: sum of items.estimated_price
  notes: string | null;
  approved_at: string | null;
  items: TreatmentPlanItem[];
  payments: TreatmentPlanPayment[];
}

interface TreatmentPlanItem {
  id: string;
  treatment_type_code: string | null;
  treatment_type_name: string | null;   // resolved by backend JOIN
  custom_description: string | null;
  estimated_price: number;
  approved_price: number | null;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  sort_order: number;
  appointments: LinkedAppointment[];
}

interface LinkedAppointment {
  id: number;
  appointment_date: string;
  status: string;
}

interface TreatmentPlanPayment {
  id: string;
  amount: number;
  payment_method: 'cash' | 'transfer' | 'card';
  payment_date: string;
  recorded_by_name: string;            // resolved by backend JOIN
  notes: string | null;
}
```

---

## 5. API Calls

All calls use `import api from '../api/axios'`. Auth headers are auto-injected.

| Method | Endpoint | Called When |
|--------|----------|-------------|
| `GET` | `/admin/treatment-plans?patient_id={patientId}` | `BillingTab` mount + after plan creation |
| `GET` | `/admin/treatment-plans/{planId}` | Plan selection change + after any CRUD on items/payments |
| `POST` | `/admin/treatment-plans` | CreatePlanModal submit |
| `PATCH` | `/admin/treatment-plans/{planId}` | Inline plan name edit + ApprovePlanModal submit |
| `DELETE` | `/admin/treatment-plans/{planId}` | (future, not in this spec) |
| `GET` | `/admin/treatment-types` | AddItemModal open (cached in modal state) |
| `POST` | `/admin/treatment-plan-items` | AddItemModal submit |
| `PATCH` | `/admin/treatment-plan-items/{itemId}` | Inline approved_price edit |
| `DELETE` | `/admin/treatment-plan-items/{itemId}` | Item delete confirmation |
| `GET` | `/admin/professionals` | CreatePlanModal open (to populate selector) |
| `POST` | `/admin/treatment-plan-payments` | RegisterPaymentModal submit |
| `DELETE` | `/admin/treatment-plan-payments/{paymentId}` | Payment delete confirmation |

Data fetching strategy:
- Plans list: fetched once on mount, re-fetched after plan creation only.
- Plan detail: fetched on `selectedPlanId` change. Also re-fetched after item/payment CRUD and after Socket.IO events.
- Treatment types list: fetched on `AddItemModal` open, stored in modal-local state, not re-fetched until modal is unmounted.
- Professionals list: fetched on `CreatePlanModal` open, same caching strategy.

---

## 6. Integration with PatientDetail.tsx

The following changes are required in `PatientDetail.tsx`. They are minimal and surgical — no existing logic is modified.

### 6.1 TabType update

```typescript
// Before
type TabType = 'summary' | 'history' | 'documents' | 'anamnesis' | 'digital_records';

// After
type TabType = 'summary' | 'history' | 'documents' | 'anamnesis' | 'digital_records' | 'billing';
```

### 6.2 New state

```typescript
const [billingRefreshKey, setBillingRefreshKey] = useState(0);
```

### 6.3 Socket.IO listeners (add to the existing useEffect)

```typescript
socketRef.current.on('TREATMENT_PLAN_UPDATED', (payload: { patient_id?: number }) => {
  const currentPatientId = id ? parseInt(id) : null;
  if (payload.patient_id && payload.patient_id === currentPatientId) {
    setBillingRefreshKey(prev => prev + 1);
  }
});

socketRef.current.on('BILLING_UPDATED', (payload: { patient_id?: number }) => {
  const currentPatientId = id ? parseInt(id) : null;
  if (payload.patient_id && payload.patient_id === currentPatientId) {
    setBillingRefreshKey(prev => prev + 1);
  }
});
```

### 6.4 renderTabContent — new case

```typescript
case 'billing':
  return (
    <BillingTab
      patientId={parseInt(id!)}
      refreshKey={billingRefreshKey}
    />
  );
```

### 6.5 Tab button (add after the `digital_records` button)

```tsx
<button
  onClick={() => setActiveTab('billing')}
  className={`flex-shrink-0 py-3 px-3 lg:px-4 text-xs lg:text-sm font-medium transition-colors whitespace-nowrap ${
    activeTab === 'billing'
      ? 'text-primary border-b-2 border-primary'
      : 'text-white/40 hover:text-white/70 hover:bg-white/[0.04]'
  }`}
>
  <div className="flex items-center justify-center gap-1.5">
    <Receipt size={16} />
    <span className="hidden sm:inline">{t('patient_detail.tabs.billing')}</span>
    <span className="sm:hidden">Presup.</span>
  </div>
</button>
```

`Receipt` must be added to the existing lucide-react import in `PatientDetail.tsx`.

### 6.6 BillingTab import

```typescript
import BillingTab from '../components/BillingTab';
```

---

## 7. Component Props Interface

```typescript
// BillingTab.tsx
interface BillingTabProps {
  patientId: number;
  refreshKey: number;   // incrementing this triggers a full re-fetch of the plans list
}

export default function BillingTab({ patientId, refreshKey }: BillingTabProps)
```

When `refreshKey` changes, `BillingTab` calls `loadPlans()` again. If a plan was previously selected and still exists in the new list, it remains selected.

---

## 8. i18n Keys

The following keys must be added to all three locale files: `es.json`, `en.json`, `fr.json`.

Located at: `frontend_react/src/locales/`

### 8.1 patient_detail namespace

| Key | ES | EN | FR |
|-----|----|----|-----|
| `patient_detail.tabs.billing` | `Presupuesto` | `Budget` | `Budget` |

### 8.2 billing namespace (new top-level key)

| Key | ES | EN | FR |
|-----|----|----|-----|
| `billing.no_plans` | `Este paciente no tiene presupuestos` | `This patient has no budgets` | `Ce patient n'a pas de devis` |
| `billing.create_first` | `Crear primer presupuesto` | `Create first budget` | `Créer le premier devis` |
| `billing.new_plan` | `Nuevo plan` | `New plan` | `Nouveau plan` |
| `billing.plan_name` | `Nombre del presupuesto` | `Budget name` | `Nom du devis` |
| `billing.plan_name_placeholder` | `Rehabilitación oral completa` | `Full oral rehabilitation` | `Réhabilitation orale complète` |
| `billing.professional` | `Profesional` | `Professional` | `Professionnel` |
| `billing.no_professional` | `Sin profesional asignado` | `No professional assigned` | `Aucun professionnel` |
| `billing.notes` | `Notas internas` | `Internal notes` | `Notes internes` |
| `billing.status.draft` | `Borrador` | `Draft` | `Brouillon` |
| `billing.status.approved` | `Aprobado` | `Approved` | `Approuvé` |
| `billing.status.in_progress` | `En curso` | `In progress` | `En cours` |
| `billing.status.completed` | `Completado` | `Completed` | `Terminé` |
| `billing.status.cancelled` | `Cancelado` | `Cancelled` | `Annulé` |
| `billing.approve_plan` | `Aprobar presupuesto` | `Approve budget` | `Approuver le devis` |
| `billing.approve_confirm` | `Revisá el total antes de aprobar. Una vez aprobado, el plan queda activo y se puede comenzar a cobrar.` | `Review the total before approving. Once approved, the plan is active and payments can be recorded.` | `Vérifiez le total avant d'approuver. Une fois approuvé, le plan est actif.` |
| `billing.approved_total` | `Total aprobado (ARS)` | `Approved total (ARS)` | `Total approuvé (ARS)` |
| `billing.estimated_total` | `Total estimado` | `Estimated total` | `Total estimé` |
| `billing.paid` | `Pagado` | `Paid` | `Payé` |
| `billing.pending` | `Pendiente` | `Pending` | `En attente` |
| `billing.paid_complete` | `Pagado completo` | `Fully paid` | `Payé intégralement` |
| `billing.no_approved_total` | `Sin total aprobado` | `No approved total` | `Pas de total approuvé` |
| `billing.treatments` | `Tratamientos` | `Treatments` | `Traitements` |
| `billing.add_treatment` | `Agregar tratamiento` | `Add treatment` | `Ajouter un traitement` |
| `billing.no_items` | `No hay tratamientos en este plan. Agregá el primero.` | `No treatments in this plan. Add the first one.` | `Aucun traitement dans ce plan.` |
| `billing.treatment` | `Tratamiento` | `Treatment` | `Traitement` |
| `billing.estimated_price` | `Precio est.` | `Est. price` | `Prix est.` |
| `billing.approved_price` | `Precio final` | `Final price` | `Prix final` |
| `billing.appointments_count` | `Turnos` | `Appointments` | `Rendez-vous` |
| `billing.status_item` | `Estado` | `Status` | `Statut` |
| `billing.item_status.pending` | `Pendiente` | `Pending` | `En attente` |
| `billing.item_status.in_progress` | `En curso` | `In progress` | `En cours` |
| `billing.item_status.completed` | `Completado` | `Completed` | `Terminé` |
| `billing.item_status.cancelled` | `Cancelado` | `Cancelled` | `Annulé` |
| `billing.delete_item_confirm` | `¿Eliminar este tratamiento del plan?` | `Remove this treatment from the plan?` | `Supprimer ce traitement du plan ?` |
| `billing.select_treatment` | `Seleccionar tratamiento` | `Select treatment` | `Sélectionner un traitement` |
| `billing.custom_description` | `Descripción personalizada` | `Custom description` | `Description personnalisée` |
| `billing.custom_description_placeholder` | `Implante pieza 36` | `Implant tooth 36` | `Implant dent 36` |
| `billing.payments` | `Pagos registrados` | `Recorded payments` | `Paiements enregistrés` |
| `billing.register_payment` | `Registrar pago` | `Record payment` | `Enregistrer un paiement` |
| `billing.no_payments` | `No hay pagos registrados aún.` | `No payments recorded yet.` | `Aucun paiement enregistré.` |
| `billing.date` | `Fecha` | `Date` | `Date` |
| `billing.amount` | `Monto` | `Amount` | `Montant` |
| `billing.method` | `Método` | `Method` | `Méthode` |
| `billing.recorded_by` | `Registrado por` | `Recorded by` | `Enregistré par` |
| `billing.method.cash` | `Efectivo` | `Cash` | `Espèces` |
| `billing.method.transfer` | `Transferencia` | `Transfer` | `Virement` |
| `billing.method.card` | `Tarjeta` | `Card` | `Carte` |
| `billing.payment_date` | `Fecha de pago` | `Payment date` | `Date de paiement` |
| `billing.pending_balance_helper` | `Saldo pendiente: ` | `Pending balance: ` | `Solde en attente : ` |
| `billing.delete_payment_confirm` | `¿Eliminar este pago?` | `Delete this payment?` | `Supprimer ce paiement ?` |
| `billing.error_load` | `Error al cargar los presupuestos` | `Error loading budgets` | `Erreur de chargement des devis` |
| `billing.error_save` | `Error al guardar los cambios` | `Error saving changes` | `Erreur lors de l'enregistrement` |
| `billing.error_permission` | `No tenés permisos para realizar esta acción` | `You don't have permission to do this` | `Vous n'avez pas les permissions` |
| `billing.saving` | `Guardando...` | `Saving...` | `Enregistrement...` |

---

## 9. Dark Mode Classes — Reference

All classes follow the established design system defined in `CLAUDE.md`.

| Element | Class |
|---------|-------|
| Section card | `bg-white/[0.02] border border-white/[0.06] rounded-xl p-4` |
| Section title | `text-sm font-semibold text-white` |
| Table header row | `text-[10px] font-bold text-white/40 uppercase` |
| Table cell | `text-sm text-white py-3` |
| Table row hover | `hover:bg-white/[0.02] transition-colors` |
| Table divider | `border-b border-white/[0.04]` |
| Inline edit input | `bg-white/[0.04] border border-white/[0.08] text-white rounded px-2 py-1 text-sm` |
| Inline edit input focus | `focus:outline-none focus:border-white/30` |
| Inline edit input error | `border-red-500/50 focus:border-red-500` |
| Primary button | `bg-white text-[#0a0e1a] font-semibold rounded-lg px-4 py-2 text-sm hover:bg-white/90` |
| Secondary button | `bg-white/[0.06] text-white border border-white/[0.08] rounded-lg px-4 py-2 text-sm hover:bg-white/[0.1]` |
| Danger button | `bg-red-500/10 text-red-400 border border-red-500/20 rounded-lg px-3 py-1.5 text-sm hover:bg-red-500/20` |
| Progress bar track | `bg-white/[0.06] rounded-full h-2` |
| Progress bar fill | `bg-green-500 rounded-full h-2 transition-all duration-300` |
| Error banner | `bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg p-3 text-sm` |
| Skeleton loader | `bg-white/[0.04] rounded animate-pulse` |
| Modal overlay | `fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end md:items-center justify-center p-0 md:p-4` |
| Modal container (desktop) | `bg-[#0d1117] border border-white/[0.08] rounded-2xl md:rounded-xl w-full md:max-w-md p-6` |
| Modal container (mobile) | `rounded-t-2xl rounded-b-none` |
| KPI cell | `bg-white/[0.02] border border-white/[0.06] rounded-xl p-3` |
| KPI label | `text-[10px] text-white/40 uppercase font-bold` |
| KPI value | `text-base font-bold text-white` |

---

## 10. Scenarios (Acceptance Criteria)

### Scenario 1 — Create a plan (happy path)
1. User opens PatientDetail for patient ID 42, navigates to "Presupuesto" tab.
2. No plans exist → empty state is shown with "Crear primer presupuesto" button.
3. User clicks the button → `CreatePlanModal` opens.
4. User enters name "Implante pieza 36 + blanqueamiento", selects professional "Dra. Laura", leaves notes empty.
5. User clicks "Crear" → `POST /admin/treatment-plans` is called → spinner shows on button.
6. On success: modal closes, `GET /admin/treatment-plans?patient_id=42` is called, new plan is auto-selected.
7. Plan header shows "Implante pieza 36 + blanqueamiento" in `draft` status badge. All KPI cells show $0.
8. Items section shows "No hay tratamientos" empty state. Payments section shows "No hay pagos".

### Scenario 2 — Add items to a plan
1. From Scenario 1, user clicks "Agregar tratamiento".
2. `AddItemModal` opens → user selects treatment type "Implante osseointegrado" (base_price: $250.000).
3. `estimated_price` field is auto-filled with 250000. User changes to 200000 and sets custom description "Implante pieza 36".
4. User clicks "Agregar" → `POST /admin/treatment-plan-items` is called.
5. On success: modal closes, items table shows one row: "Implante pieza 36 | $200.000 | $200.000 | 0 turnos | Pendiente".
6. Progress bar remains at 0% (no payments). KPI "Total estimado" shows $200.000.

### Scenario 3 — Approve plan
1. User clicks "Aprobar presupuesto" → `ApprovePlanModal` opens with `approved_total` pre-filled: 200000.
2. User changes to 180000 ("le hice descuento").
3. User clicks "Confirmar" → `PATCH /admin/treatment-plans/{planId}` called with `{ status: 'approved', approved_total: 180000 }`.
4. On success: plan header shows `approved` badge. "Aprobar presupuesto" button disappears. "Total aprobado" KPI shows $180.000.

### Scenario 4 — Register a cash payment
1. From Scenario 3, user clicks "Registrar pago".
2. `RegisterPaymentModal` opens. Helper text shows "Saldo pendiente: $180.000". `amount` field is empty.
3. User enters 90000, selects "Efectivo", date defaults to today.
4. User clicks "Registrar" → `POST /admin/treatment-plan-payments` called.
5. On success: modal closes, payments table shows one row. Progress bar fills to 50% (green). "Pagado" KPI shows $90.000. "Pendiente" shows $90.000.

### Scenario 5 — Inline price edit
1. User hovers over "Precio final" cell for an item → edit pencil icon appears.
2. User clicks the cell → `<input>` appears pre-filled with 200000.
3. User types 175000 and presses Enter → `PATCH /admin/treatment-plan-items/{itemId}` called with `{ approved_price: 175000 }`.
4. On success: cell shows $175.000. Plan "Total estimado" KPI does NOT change (it's based on `estimated_price`). "Total aprobado" on the plan does NOT automatically update — it's independent.
5. If user presses Escape → cell reverts to previous value, no API call made.

### Scenario 6 — Delete a payment
1. User clicks the trash icon on a payment row → inline confirm appears: "¿Eliminar este pago? [Confirmar] [Cancelar]".
2. User clicks "Confirmar" → `DELETE /admin/treatment-plan-payments/{paymentId}` called.
3. On success: row disappears, progress bar and KPIs recalculate.

### Scenario 7 — Multiple plans (dropdown)
1. Patient has 2 plans: "Plan A (Aprobado)" and "Plan B (Borrador)".
2. Plan Selector Bar shows a dropdown defaulting to the most recent plan.
3. User selects "Plan A" from dropdown → `GET /admin/treatment-plans/{planAId}` is called, all sections re-render with Plan A data.
4. "Nuevo plan" button remains visible alongside the dropdown.

### Scenario 8 — Socket.IO real-time refresh
1. User has `BillingTab` open showing Plan A.
2. From another browser session (or Nova), a payment is registered → backend emits `BILLING_UPDATED` with `{ patient_id: 42 }`.
3. `PatientDetail` receives the event, increments `billingRefreshKey`.
4. `BillingTab` receives new `refreshKey` prop → calls `loadPlans()` → fetches plan detail → payments table updates automatically.

---

## 11. File Location

| File | Path |
|------|------|
| Main component | `frontend_react/src/components/BillingTab.tsx` |
| Locale additions | `frontend_react/src/locales/es.json` |
| Locale additions | `frontend_react/src/locales/en.json` |
| Locale additions | `frontend_react/src/locales/fr.json` |
| PatientDetail patch | `frontend_react/src/views/PatientDetail.tsx` |

No new directories need to be created. `BillingTab.tsx` follows the same flat structure used by `DigitalRecordsTab.tsx` and `AnamnesisPanel.tsx`.

---

## 12. Out of Scope (deferred to future specs)

- PDF export of the treatment plan
- Per-item payment allocation (linking a payment to a specific item)
- Installment scheduling (cuotas) UI
- Plan duplication ("Copiar presupuesto")
- Editing plan status backwards (e.g., reverting approved → draft)
- Receipt file upload for transfer payments (handled by existing payment verification flow)
