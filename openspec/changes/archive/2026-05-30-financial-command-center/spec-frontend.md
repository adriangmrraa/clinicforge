# Spec: Financial Command Center — Frontend

---

## 1. Nueva Ruta: `/finanzas` — FinancialCommandCenterView

### 1.1 Configuración de ruta (App.tsx)

```tsx
<Route
  path="/finanzas"
  element={
    <ProtectedRoute allowedRoles={['ceo']}>
      <FinancialCommandCenterView />
    </ProtectedRoute>
  }
/>
```

**Acceso:** Solo rol `ceo`. Redirigir a `/dashboard` si otro rol intenta acceder.

### 1.2 Estructura de la vista

```
┌──────────────────────────────────────────────────────────────┐
│  Centro de Comando Financiero                    [CEO Name]  │
├──────────────────────────────────────────────────────────────┤
│  [📊 Dashboard]  [📋 Liquidaciones]  [⚖️ Conciliación]       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Contenido del tab activo                                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Componente principal:** `FinancialCommandCenterView.tsx`
- Estado de tab activo: `dashboard` | `liquidaciones` | `conciliacion`
- Tabs con íconos y labels
- Cada tab carga su contenido bajo demanda (lazy)

---

## 2. Tab 1: Dashboard Financiero

### FR-01: KPI Cards

Cuatro tarjetas de métricas principales en la parte superior:

```
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ 💰 Ingresos     │ │ 📋 Liquidaciones│ │ 👥 Pagos a      │ │ 📈 Ganancia     │
│   $1.500.000    │ │   Pendientes    │ │   Profesionales │ │   Neta          │
│   Marzo 2026    │ │   3             │ │   $450.000      │ │   $1.050.000    │
│   ↑ 25% vs ant. │ │   $450.000      │ │   Marzo 2026    │ │   Margen: 70%   │
└─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘
```

**Datos:** `GET /admin/financial-dashboard?period_start=X&period_end=X`

**Comportamiento:**
- Período default: mes actual (primer y último día)
- Selector de período en la esquina superior derecha (date range picker)
- Indicador de crecimiento MoM en la card de ingresos (verde si positivo, rojo si negativo)
- Formato de moneda: ARS con separador de miles (punto) y decimales

### FR-02: Revenue por Profesional (Bar Chart)

```
┌──────────────────────────────────────────┐
│ Ingresos por Profesional                 │
│                                          │
│  Dra. Pérez  ████████████████████ $500K  │
│  Dr. García  ██████████████ $350K        │
│  Dra. López  ██████████ $250K            │
│  Dr. Ruiz    ████████ $200K              │
│  Dra. Torres ████ $100K                  │
│                                          │
│  [Ver detalle →]                         │
└──────────────────────────────────────────┘
```

**Datos:** `revenue_by_professional` del dashboard endpoint
**Librería:** Recharts `<BarChart>` horizontal
**Click en barra:** Navega a Tab Liquidaciones con filtro por ese profesional

### FR-03: Revenue por Tratamiento (Pie Chart)

```
┌──────────────────────────────────────────┐
│ Ingresos por Tratamiento                 │
│                                          │
│         ╭─────────╮                      │
│       ╱   Implante  │ 40%                │
│      │   Corona   │ 25%                  │
│       ╲  Limpieza │ 20%                  │
│         ╰─────────╮ 15%                  │
│                                          │
│  ■ Implante  ■ Corona  ■ Limpieza  ■ Otro│
└──────────────────────────────────────────┘
```

**Datos:** `revenue_by_treatment` del dashboard endpoint
**Librería:** Recharts `<PieChart>`
**Tooltip:** treatment_name + revenue + percentage

### FR-04: Daily Cash Flow (Line Chart)

```
┌──────────────────────────────────────────┐
│ Flujo de Caja Diario                     │
│                                          │
│  $60K ┤    ╭──╮                          │
│  $40K ┤  ╭╯    ╰──╮  ╭──╮               │
│  $20K ┤╭╯          ╰╮╯    ╰─            │
│   $0K ┼────────────────────────────      │
│       1  5  10  15  20  25  30          │
│                                          │
│  ─ Ingresos  ─┄ Pagos                   │
└──────────────────────────────────────────┘
```

**Datos:** `daily_cash_flow` del dashboard endpoint
**Librería:** Recharts `<LineChart>` con 2 líneas (revenue y payouts)
**Tooltip:** fecha + revenue + payouts + diferencia

### FR-05: Pending Collections Alert List

```
┌──────────────────────────────────────────┐
│ ⚠️ Cobros Pendientes (5)                 │
│                                          │
│  Lucas Puig     Implante     $180.000   │
│  María López    Corona       $45.000    │
│  Juan García    Limpieza     $5.000     │
│                                          │
│  [Ver todos →]                           │
└──────────────────────────────────────────┘
```

**Datos:** `pending_collections` del dashboard endpoint
**Comportamiento:**
- Mostrar máximo 5 items (los de mayor monto)
- Click en "Ver todos" → expande la lista completa
- Cada item muestra: paciente, tratamiento, monto pendiente, días de atraso
- Color coding: >30 días = rojo, 15-30 días = naranja, <15 días = amarillo

### FR-06: MoM Comparison Indicator

```
┌──────────────────────────────────────────┐
│ Comparación Mes a Mes                    │
│                                          │
│  Este mes:    $1.500.000  ████████████  │
│  Mes anterior: $1.200.000  ██████████   │
│                                          │
│  Crecimiento: +25.0% ↑                    │
└──────────────────────────────────────────┘
```

**Datos:** `mom_growth` del dashboard endpoint
**Visual:** Barra comparativa con indicador de crecimiento

---

## 3. Tab 2: Liquidaciones

### FR-07: Period Selector + Bulk Generate

```
┌──────────────────────────────────────────────────────────────┐
│  Período: [01/03/2026] — [31/03/2026]   [🔄 Generar Liquidaciones] │
└──────────────────────────────────────────────────────────────┘
```

**Comportamiento:**
- Date range picker con preset: "Este mes", "Mes anterior", "Trimestre", "Personalizado"
- Botón "Generar Liquidaciones" → llama `POST /admin/liquidations/generate-bulk`
- Loading state: spinner + texto "Generando liquidaciones..."
- Success toast: "5 liquidaciones generadas correctamente"
- Si ya existen: "3 liquidaciones ya existían, 2 nuevas generadas"

### FR-08: Tabla de Liquidaciones

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Profesional      │ Período      │ Facturado  │ Comisión │ Payout    │ Estado   │ Acciones │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ Dra. Pérez       │ Mar 2026     │ $500.000   │ 30%      │ $150.000  │ Aprobado │ [👁️][📄] │
│ Dr. García       │ Mar 2026     │ $350.000   │ 25%      │ $87.500   │ Generado │ [👁️][✅][📄] │
│ Dra. López       │ Mar 2026     │ $250.000   │ 30%      │ $75.000   │ Pagado   │ [👁️][📄] │
│ Dr. Ruiz         │ Mar 2026     │ $200.000   │ 0% ⚠️    │ $200.000  │ Draft    │ [👁️][✅] │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

**Datos:** `GET /admin/liquidations?period_start=X&period_end=X`
**Paginación:** 20 items por página, con selector de página

**Columnas:**
- Profesional: nombre completo
- Período: formato "Mar 2026"
- Facturado: total_billed formateado
- Comisión: commission_pct + badge de warning si es 0%
- Payout: payout_amount formateado
- Estado: badge de color (ver FR-15)
- Acciones: ver detalle, aprobar, descargar PDF

**Acciones por estado:**
- `draft` → [Ver detalle] [Aprobar]
- `generated` → [Ver detalle] [Aprobar] [Descargar PDF]
- `approved` → [Ver detalle] [Marcar pagado] [Descargar PDF]
- `paid` → [Ver detalle] [Descargar PDF]

### FR-09: Expandir Detalle de Liquidación

Click en 👁️ o en la fila expande un accordion con el detalle:

```
┌──────────────────────────────────────────────────────────────┐
│ Dra. Pérez — Marzo 2026                              [✕]     │
├──────────────────────────────────────────────────────────────┤
│  Resumen:                                                    │
│  Total facturado: $500.000  |  Pagado: $450.000             │
│  Pendiente: $50.000  |  Comisión: 30% ($150.000)            │
│                                                              │
│  Detalle por Paciente/Treatment:                             │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ▼ Lucas Puig                                           │  │
│  │   Implante dental — 2 sesiones — $200.000             │  │
│  │   15/03/2026 — Consulta inicial — $50.000 ✅          │  │
│  │   22/03/2026 — Colocación — $150.000 ✅               │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │ ▼ María López                                          │  │
│  │   Corona — 3 sesiones — $140.000                      │  │
│  │   ...                                                  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Historial de pagos:                                         │
│  03/04/2026 — Transferencia — $150.000 — Ref: TXN-12345    │
│                                                              │
│  [💳 Registrar Pago]  [📄 Descargar PDF]  [📧 Enviar Email] │
└──────────────────────────────────────────────────────────────┘
```

**Patrón:** Reusar `ProfessionalAccordion` existente para el grouping por paciente/tratamiento
**Datos:** `GET /admin/liquidations/{id}` (reutiliza lógica de `get_professionals_liquidation`)

### FR-10: Export CSV

Botón "Exportar CSV" en la tabla de liquidaciones.

**Comportamiento:**
- Genera CSV con todas las liquidaciones del período visible
- Columnas: profesional, período, total_billed, commission_pct, commission_amount, payout_amount, status, generated_at
- Download automático del archivo

---

## 4. Tab 3: Conciliación

### FR-11: Vista de Conciliación

```
┌──────────────────────────────────────────────────────────────┐
│  Conciliación Financiera                                     │
│  Período: [01/03/2026] — [31/03/2026]     [🔄 Actualizar]   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│  │ Cobrado de      │ │ Pagado a        │ │ Diferencia      ││
│  │ Pacientes       │ │ Profesionales   │ │                 ││
│  │ $1.500.000      │ │ $450.000        │ │ $1.050.000      ││
│  └─────────────────┘ └─────────────────┘ └─────────────────┘│
│                                                              │
│  Discrepancias detectadas (3):                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ⚠️ Turno #12345 — María López — Limpieza — $5.000    │  │
│  │    Fecha: 15/03/2026 — Profesional: Dra. Pérez        │  │
│  │    Pago registrado sin liquidación asociada             │  │
│  │    [Resolver] [Ignorar]                                │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │ ⚠️ Turno #12346 — Juan García — Corona — $45.000     │  │
│  │    ...                                                  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**Datos:** `GET /admin/reconciliation?period_start=X&period_end=X`

**Acciones por discrepancia:**
- "Resolver" → modal para asociar el appointment a una liquidación existente o crear una nueva
- "Ignorar" → marca la discrepancia como resuelta (no se muestra más)

---

## 5. Nueva Ruta: `/mis-liquidaciones` — ProfessionalLiquidationsView

### FR-12: Vista Self-Service para Profesionales

```
┌──────────────────────────────────────────────────────────────┐
│  Mis Liquidaciones                              [Prof Name]  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Período: [01/03/2026] — [31/03/2026]                       │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Marzo 2026                              [✅ Aprobado]  │  │
│  │ Total facturado: $500.000                              │  │
│  │ Tu comisión (30%): $150.000                            │  │
│  │ Pagado: $150.000 — 03/04/2026                         │  │
│  │ [📄 Descargar PDF]                                     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Febrero 2026                            [✅ Pagado]    │  │
│  │ Total facturado: $420.000                              │  │
│  │ Tu comisión (30%): $126.000                            │  │
│  │ Pagado: $126.000 — 05/03/2026                         │  │
│  │ [📄 Descargar PDF]                                     │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**Configuración de ruta (App.tsx):**
```tsx
<Route
  path="/mis-liquidaciones"
  element={
    <ProtectedRoute allowedRoles={['professional']}>
      <ProfessionalLiquidationsView />
    </ProtectedRoute>
  }
/>
```

**Datos:** `GET /admin/liquidations?professional_id={logged_in_professional_id}`
**Restricciones:**
- Solo ve sus propias liquidaciones
- Vista read-only (sin botones de aprobar, generar, etc.)
- Solo puede descargar PDF

---

## 6. Componentes a Crear

### FR-13: FinancialDashboard.tsx

Componente principal del Tab 1.

```tsx
interface FinancialDashboardProps {
  periodStart: string;
  periodEnd: string;
}
```

**Contenido:**
- KPI Cards (FR-01)
- Revenue by Professional chart (FR-02)
- Revenue by Treatment chart (FR-03)
- Daily Cash Flow chart (FR-04)
- Pending Collections (FR-05)
- MoM Comparison (FR-06)

**Layout:** Grid responsive
- Desktop: 4 columnas para KPIs, 2 columnas para charts
- Tablet: 2 columnas para KPIs, 1 columna para charts
- Mobile: 1 columna todo

### FR-14: LiquidationManager.tsx

Componente principal del Tab 2.

```tsx
interface LiquidationManagerProps {
  periodStart: string;
  periodEnd: string;
}
```

**Contenido:**
- Period selector + bulk generate button (FR-07)
- Tabla de liquidaciones (FR-08)
- Detalle expandible (FR-09)
- Export CSV (FR-10)

### FR-15: LiquidationStatusBadge.tsx

Componente reutilizable para badges de estado.

```tsx
interface LiquidationStatusBadgeProps {
  status: 'draft' | 'generated' | 'approved' | 'paid';
}
```

**Estilos:**
- `draft` → gris: "Borrador"
- `generated` → azul: "Generada"
- `approved` → verde: "Aprobada"
- `paid` → verde oscuro: "Pagada"

### FR-16: ReconciliationView.tsx

Componente principal del Tab 3.

```tsx
interface ReconciliationViewProps {
  periodStart: string;
  periodEnd: string;
}
```

**Contenido:**
- Summary cards (FR-11)
- Discrepancy list con acciones

### FR-17: ProfessionalLiquidationsView.tsx

Vista completa para profesionales (FR-12).

**Contenido:**
- Lista de liquidaciones propias
- Filtro por período
- PDF download
- Sin capacidades de edición

### FR-18: CommissionEditor.tsx

Modal para editar comisiones de un profesional.

```tsx
interface CommissionEditorProps {
  professionalId: number;
  professionalName: string;
  onClose: () => void;
  onSuccess: () => void;
}
```

**Contenido:**
```
┌──────────────────────────────────────────┐
│ Configurar Comisiones — Dra. Pérez   [✕] │
├──────────────────────────────────────────┤
│                                          │
│  Comisión default: [30] %                │
│                                          │
│  Overrides por tratamiento:              │
│  ┌────────────────────────────────────┐  │
│  │ Tratamiento    │ Comisión          │  │
│  ├────────────────────────────────────┤  │
│  │ Implante       │ [35] %     [✕]   │  │
│  │ Corona         │ [25] %     [✕]   │  │
│  │ [+ Agregar tratamiento]            │  │
│  └────────────────────────────────────┘  │
│                                          │
│  [Cancelar]  [Guardar]                   │
└──────────────────────────────────────────┘
```

**Datos:**
- Load: `GET /admin/professionals/{id}/commissions`
- Save: `PUT /admin/professionals/{id}/commissions`

**Validaciones:**
- Porcentaje entre 0 y 100
- Al menos un default configurado
- Warning si default es 0%

### FR-19: Enhanced ProfessionalAnalyticsView (LiquidationTab)

Modificación al `LiquidationTab.tsx` existente en `ProfessionalAnalyticsView`:

**Cambios:**
- Ahora usa `liquidation_records` persistentes en lugar de computed-on-the-fly
- Mantiene fallback a la vista computada si el servicio nuevo falla
- Agrega link "Ver en Finanzas" para usuarios CEO:

```tsx
{userRole === 'ceo' && (
  <Link to="/finanzas" className="text-blue-600 hover:underline">
    Ver en Finanzas →
  </Link>
)}
```

---

## 7. API Calls Summary

| Acción | Endpoint | Componente | Trigger |
|--------|----------|------------|---------|
| Load dashboard | `GET /admin/financial-dashboard` | FinancialDashboard | Tab mount + period change |
| Generate bulk | `POST /admin/liquidations/generate-bulk` | LiquidationManager | Button click |
| List liquidations | `GET /admin/liquidations` | LiquidationManager | Tab mount + filters |
| Detail | `GET /admin/liquidations/{id}` | LiquidationManager | Row expand |
| Update status | `PATCH /admin/liquidations/{id}` | LiquidationManager | Action button |
| Create payout | `POST /admin/liquidations/{id}/payout` | LiquidationManager | "Registrar Pago" |
| List payouts | `GET /admin/liquidations/{id}/payouts` | LiquidationManager | Detail expand |
| Download PDF | `GET /admin/liquidations/{id}/pdf` | LiquidationManager / ProfessionalLiquidationsView | Button click (blob) |
| Send email | `POST /admin/liquidations/{id}/send-email` | LiquidationManager | Button click |
| Reconciliation | `GET /admin/reconciliation` | ReconciliationView | Tab mount + period change |
| Load commissions | `GET /admin/professionals/{id}/commissions` | CommissionEditor | Modal open |
| Save commissions | `PUT /admin/professionals/{id}/commissions` | CommissionEditor | Save button |
| Professional liquidations | `GET /admin/liquidations?professional_id=X` | ProfessionalLiquidationsView | View mount |

---

## 8. i18n Keys Nuevas

### Namespace: `finance`

```json
{
  "finance": {
    "title": "Centro de Comando Financiero",
    "tab_dashboard": "Dashboard",
    "tab_liquidations": "Liquidaciones",
    "tab_reconciliation": "Conciliación",
    "period_revenue": "Ingresos del período",
    "pending_liquidations": "Liquidaciones pendientes",
    "professional_payouts": "Pagos a profesionales",
    "net_profit": "Ganancia neta",
    "profit_margin": "Margen",
    "revenue_by_professional": "Ingresos por Profesional",
    "revenue_by_treatment": "Ingresos por Tratamiento",
    "daily_cash_flow": "Flujo de Caja Diario",
    "pending_collections": "Cobros Pendientes",
    "mom_comparison": "Comparación Mes a Mes",
    "this_month": "Este mes",
    "last_month": "Mes anterior",
    "growth": "Crecimiento",
    "see_all": "Ver todos",
    "see_detail": "Ver detalle",
    "days_overdue": "días de atraso"
  }
}
```

### Namespace: `liquidation` (extendido)

```json
{
  "liquidation": {
    "generate_liquidations": "Generar Liquidaciones",
    "generating": "Generando liquidaciones...",
    "generated_success": "Liquidaciones generadas correctamente",
    "already_exists": "liquidaciones ya existían",
    "new_generated": "nuevas generadas",
    "status_draft": "Borrador",
    "status_generated": "Generada",
    "status_approved": "Aprobada",
    "status_paid": "Pagada",
    "approve": "Aprobar",
    "mark_paid": "Marcar Pagado",
    "register_payout": "Registrar Pago",
    "payout_amount": "Monto del pago",
    "payment_method": "Método de pago",
    "payment_method_transfer": "Transferencia",
    "payment_method_cash": "Efectivo",
    "payment_method_check": "Cheque",
    "reference_number": "Número de referencia",
    "payout_history": "Historial de pagos",
    "no_payouts": "Sin pagos registrados",
    "export_csv": "Exportar CSV",
    "period": "Período",
    "billed": "Facturado",
    "commission": "Comisión",
    "payout": "Payout",
    "no_liquidations": "No hay liquidaciones para este período",
    "no_liquidations_desc": "Generá liquidaciones para ver el resumen financiero",
    "confirm_approve": "¿Aprobar esta liquidación?",
    "confirm_paid": "¿Marcar como pagada?",
    "commission_warning": "Sin configuración de comisiones (0%)"
  }
}
```

### Namespace: `reconciliation`

```json
{
  "reconciliation": {
    "title": "Conciliación Financiera",
    "total_patient_payments": "Cobrado de Pacientes",
    "total_professional_payouts": "Pagado a Profesionales",
    "difference": "Diferencia",
    "discrepancies": "Discrepancias detectadas",
    "no_discrepancies": "Sin discrepancias",
    "no_discrepancies_desc": "Todos los pagos están correctamente conciliados",
    "payment_without_liquidation": "Pago registrado sin liquidación asociada",
    "resolve": "Resolver",
    "ignore": "Ignorar",
    "confirm_ignore": "¿Ignorar esta discrepancia?"
  }
}
```

### Namespace: `commissions`

```json
{
  "commissions": {
    "title": "Configurar Comisiones",
    "default_commission": "Comisión default",
    "per_treatment": "Overrides por tratamiento",
    "add_treatment": "Agregar tratamiento",
    "remove_treatment": "Quitar override",
    "save": "Guardar",
    "cancel": "Cancelar",
    "saved_success": "Comisiones actualizadas",
    "warning_zero": "Comisión 0%: el profesional recibe el 100% del cobro",
    "invalid_percentage": "El porcentaje debe estar entre 0 y 100"
  }
}
```

### Namespace: `professional_liquidations`

```json
{
  "professional_liquidations": {
    "title": "Mis Liquidaciones",
    "no_liquidations": "No tenés liquidaciones aún",
    "no_liquidations_desc": "Las liquidaciones se generan mensualmente",
    "your_commission": "Tu comisión",
    "paid_on": "Pagado el",
    "download_pdf": "Descargar PDF"
  }
}
```

---

## 9. Responsive Design

### Desktop (>1024px)
- KPI cards: 4 columnas
- Charts: 2 columnas (bar + pie, line full width)
- Tabla liquidaciones: todas las columnas visibles
- Detalle expandible: panel lateral o accordion

### Tablet (768px - 1024px)
- KPI cards: 2 columnas
- Charts: 1 columna
- Tabla: scroll horizontal o columnas compactas

### Mobile (<768px)
- KPI cards: 1 columna (stack vertical)
- Charts: 1 columna, altura reducida
- Tabla: cards en lugar de tabla (una card por liquidación)
- Detalle: bottom sheet o página completa
- Tabs: scroll horizontal con íconos

---

## 10. Criterios de Aceptación Frontend

| # | Criterio | Verificación |
|---|----------|-------------|
| AC-FE-01 | CEO ve todas las métricas en `/finanzas` | Login como CEO → navegar a `/finanzas` → ver 3 tabs con datos |
| AC-FE-02 | Profesional solo ve sus liquidaciones en `/mis-liquidaciones` | Login como professional → navegar → solo sus datos |
| AC-FE-03 | Secretary no accede a `/finanzas` | Login como secretary → navegar → redirect a `/dashboard` |
| AC-FE-04 | Bulk generate funciona con loading state | Click button → spinner → toast de éxito |
| AC-FE-05 | Status badge muestra colores correctos | draft=gris, generated=azul, approved=verde, paid=verde oscuro |
| AC-FE-06 | Detalle expandible muestra treatment groups | Click en fila → accordion con pacientes y sesiones |
| AC-FE-07 | PDF download funciona | Click en 📄 → descarga archivo PDF |
| AC-FE-08 | CommissionEditor valida porcentajes | Input >100 → error, Input <0 → error |
| AC-FE-09 | Conciliación muestra discrepancias | Período con appointments pagados sin liquidación → lista de discrepancias |
| AC-FE-10 | i18n completo en es/en/fr | Cambiar idioma → todos los textos traducidos |
| AC-FE-11 | Responsive en mobile | Viewport <768px → layout adaptado, sin overflow horizontal |
| AC-FE-12 | Scroll isolation | La vista completa usa `h-screen` + `overflow-hidden` global, contenido interno con `overflow-y-auto` |
