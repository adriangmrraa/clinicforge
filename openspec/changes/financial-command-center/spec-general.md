# Spec General: Financial Command Center

---

## 1. Objetivo

Transformar el sistema financiero de clinicforge de vistas desconectadas y cálculos efímeros a un **centro de comando unificado** con gestión real de liquidaciones, comisiones configurables, tracking de pagos y visibilidad financiera global.

---

## 2. Componentes del Cambio

| # | Componente | Spec | Archivos Afectados |
|---|-----------|------|-------------------|
| 1 | Migración Alembic 020 | spec-backend.md §1 | `alembic/versions/020_financial_command_center.py` |
| 2 | ORM Models (3 nuevos + 3 faltantes) | spec-backend.md §2 | `models.py` |
| 3 | Liquidation Service | spec-backend.md §3 | `services/liquidation_service.py` (nuevo) |
| 4 | Financial Dashboard Service | spec-backend.md §4 | `services/financial_dashboard_service.py` (nuevo) |
| 5 | Endpoints financieros (~13) | spec-backend.md §5 | `admin_routes.py` |
| 6 | FinancialCommandCenterView | spec-frontend.md §1-4 | `views/FinancialCommandCenterView.tsx` (nuevo) |
| 7 | ProfessionalLiquidationsView | spec-frontend.md §5 | `views/ProfessionalLiquidationsView.tsx` (nuevo) |
| 8 | Componentes financieros | spec-frontend.md §6 | `components/finance/` (nuevo) |
| 9 | LiquidationTab mejorado | spec-frontend.md §6 FR-19 | `components/analytics/LiquidationTab.tsx` |
| 10 | PDF Template | spec-pdf.md §1 | `templates/liquidation/liquidation_statement.html` (nuevo) |
| 11 | Email Template | spec-pdf.md §3 | `templates/liquidation/liquidation_email.html` (nuevo) |
| 12 | i18n keys | spec-frontend.md §8 | `locales/{es,en,fr}.json` |
| 13 | RBAC | spec-general.md §3 | `admin_routes.py`, `AuthContext` |
| 14 | Audit Trail | spec-general.md §5 | `liquidation_service.py` |

---

## 3. RBAC (Control de Acceso por Rol)

### 3.1 Matriz de Permisos

| Endpoint / Vista | CEO | Professional | Secretary |
|-----------------|-----|-------------|-----------|
| `POST /admin/liquidations/generate` | ✅ | ❌ | ❌ |
| `POST /admin/liquidations/generate-bulk` | ✅ | ❌ | ❌ |
| `GET /admin/liquidations` | ✅ | ❌ (ver abajo) | ❌ |
| `GET /admin/liquidations/{id}` | ✅ | ❌ (ver abajo) | ❌ |
| `PATCH /admin/liquidations/{id}` | ✅ | ❌ | ❌ |
| `POST /admin/liquidations/{id}/payout` | ✅ | ❌ | ❌ |
| `GET /admin/liquidations/{id}/payouts` | ✅ | ❌ (ver abajo) | ❌ |
| `GET /admin/financial-dashboard` | ✅ | ❌ | ❌ |
| `GET /admin/professionals/{id}/commissions` | ✅ | ❌ (ver abajo) | ❌ |
| `PUT /admin/professionals/{id}/commissions` | ✅ | ❌ | ❌ |
| `GET /admin/reconciliation` | ✅ | ❌ | ❌ |
| `GET /admin/liquidations/{id}/pdf` | ✅ | ✅ (solo propias) | ❌ |
| `POST /admin/liquidations/{id}/send-email` | ✅ | ❌ | ❌ |
| `/finanzas` (ruta frontend) | ✅ | ❌ (redirect) | ❌ (redirect) |
| `/mis-liquidaciones` (ruta frontend) | ❌ | ✅ | ❌ (redirect) |

### 3.2 Endpoints para Profesionales (Own Data Only)

Agregar endpoints bajo prefijo `/my/` para acceso self-service de profesionales:

| Endpoint | Descripción |
|----------|-------------|
| `GET /my/liquidations` | Lista liquidaciones del profesional logueado (usa `professional_id` del JWT) |
| `GET /my/liquidations/{id}` | Detalle de una liquidación propia (read-only) |
| `GET /my/liquidations/{id}/pdf` | Descarga PDF de liquidación propia |
| `GET /my/commissions` | Ve su propia configuración de comisiones |

**Implementación:**
- Extraer `professional_id` del token JWT del usuario
- Forzar filtro `WHERE professional_id = {jwt_professional_id}`
- Solo métodos GET (read-only)

### 3.3 Middleware de Validación

Para endpoints admin existentes, agregar validación de rol:

```python
# En admin_routes.py, para cada endpoint financiero:
@router.post("/liquidations/generate")
async def generate_liquidation(
    body: GenerateLiquidationRequest,
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    if current_user.role != "ceo":
        raise HTTPException(status_code=403, detail="Acceso restringido a administradores")
    # ... lógica
```

---

## 4. Tenant Isolation (Aislamiento por Clínica)

### 4.1 Regla de Soberanía

**TODAS** las queries de base de datos DEBEN incluir el filtro `tenant_id`. Esta es la regla inviolable del sistema.

### 4.2 Aplicación por Componente

| Componente | Cómo se aplica tenant_id |
|-----------|-------------------------|
| `liquidation_service.generate_liquidation()` | Parámetro obligatorio, filtrado en todas las queries |
| `liquidation_service.generate_bulk_liquidations()` | Filtra profesionales por `tenant_id` |
| `financial_dashboard_service.*` | Todas las agregaciones con `WHERE tenant_id = $1` |
| Endpoints admin | `tenant_id` viene de `Depends(get_resolved_tenant_id)` |
| Endpoints `/my/` | `tenant_id` del JWT + `professional_id` del JWT |
| PDF generation | Verifica `liquidation_record.tenant_id == current_tenant_id` |

### 4.3 Verificación

Cada query SQL en los nuevos servicios debe tener:
```sql
WHERE ... AND tenant_id = $1
```

O en SQLAlchemy:
```python
session.query(LiquidationRecord).filter_by(tenant_id=tenant_id)
```

---

## 5. Audit Trail

### 5.1 Formato de Auditoría en `notes` (JSONB)

Cada cambio significativo en una liquidación agrega una entrada al array `audit_trail` dentro del campo `notes`:

```json
{
  "audit_trail": [
    {
      "action": "generated",
      "by": "ceo@clinic.com",
      "at": "2026-04-01T10:00:00Z",
      "details": {
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
        "total_billed": 500000.00
      }
    },
    {
      "action": "status_change",
      "from": "generated",
      "to": "approved",
      "by": "ceo@clinic.com",
      "at": "2026-04-02T14:00:00Z",
      "notes": "Revisado y conforme"
    },
    {
      "action": "payout_created",
      "by": "ceo@clinic.com",
      "at": "2026-04-03T10:00:00Z",
      "details": {
        "amount": 150000.00,
        "payment_method": "transfer",
        "reference_number": "TXN-12345"
      }
    },
    {
      "action": "status_change",
      "from": "approved",
      "to": "paid",
      "by": "ceo@clinic.com",
      "at": "2026-04-03T10:00:00Z",
      "notes": ""
    },
    {
      "action": "email_sent",
      "to": "profesional@email.com",
      "by": "ceo@clinic.com",
      "at": "2026-04-03T10:05:00Z"
    }
  ]
}
```

### 5.2 Eventos Auditados

| Evento | Action | Detalles |
|--------|--------|----------|
| Generación | `generated` | Período, totales |
| Cambio de status | `status_change` | from, to, notes |
| Pago creado | `payout_created` | amount, method, reference |
| Email enviado | `email_sent` | to_email |
| Comisión actualizada | `commission_updated` | old_commission, new_commission, per_treatment_changes |
| PDF generado | `pdf_generated` | cached: true/false |

### 5.3 Auditoría de Comisiones

Los cambios en `professional_commissions` también se registran:

```python
# En el endpoint PUT /admin/professionals/{id}/commissions
audit_entry = {
    "action": "commission_updated",
    "by": current_user.email,
    "at": datetime.utcnow().isoformat(),
    "old_default": old_default_pct,
    "new_default": new_default_pct,
    "per_treatment_changes": [
        {"treatment": "implant", "old": 30, "new": 35},
        {"treatment": "crown", "old": None, "new": 25}  # None = nuevo override
    ]
}
```

---

## 6. i18n (Internacionalización)

### 6.1 Archivos a Modificar

- `frontend_react/src/locales/es.json` — Español (default)
- `frontend_react/src/locales/en.json` — English
- `frontend_react/src/locales/fr.json` — Français

### 6.2 Namespaces

| Namespace | Vista/Componente | Keys |
|-----------|-----------------|------|
| `finance` | FinancialCommandCenterView | Títulos, tabs, KPI labels |
| `liquidation` | LiquidationManager, ProfessionalLiquidationsView | Estados, acciones, mensajes |
| `reconciliation` | ReconciliationView | Conciliación, discrepancias |
| `commissions` | CommissionEditor | Comisiones, validaciones |
| `professional_liquidations` | ProfessionalLiquidationsView | Vista self-service |

### 6.3 PDF en Idioma de la Clínica

El PDF de liquidación usa el idioma configurado en `tenants.config.ui_language`:

```python
language = clinic_data.get("ui_language", "es")

# Traducciones para el PDF
translations = {
    "es": {
        "title": "LIQUIDACIÓN DE HONORARIOS PROFESIONALES",
        "summary": "RESUMEN",
        "total_sessions": "Total de sesiones",
        "total_billed": "Total facturado",
        "commission": "Comisión aplicada",
        "net_payout": "NETO A LIQUIDAR",
        "detail": "DETALLE DE SESIONES",
        "payment_history": "HISTORIAL DE PAGOS",
        "paid": "Pagado",
        "pending": "Pendiente",
        "partial": "Parcial",
    },
    "en": {
        "title": "PROFESSIONAL FEES STATEMENT",
        "summary": "SUMMARY",
        "total_sessions": "Total sessions",
        "total_billed": "Total billed",
        "commission": "Commission applied",
        "net_payout": "NET PAYOUT",
        "detail": "SESSION DETAILS",
        "payment_history": "PAYMENT HISTORY",
        "paid": "Paid",
        "pending": "Pending",
        "partial": "Partial",
    },
    "fr": {
        "title": "RELEVÉ D'HONORAIRES PROFESSIONNELS",
        "summary": "RÉSUMÉ",
        "total_sessions": "Total des séances",
        "total_billed": "Total facturé",
        "commission": "Commission appliquée",
        "net_payout": "NET À PAYER",
        "detail": "DÉTAIL DES SÉANCES",
        "payment_history": "HISTORIQUE DES PAIEMENTS",
        "paid": "Payé",
        "pending": "En attente",
        "partial": "Partiel",
    }
}
```

### 6.4 Interpolación Dinámica

Usar el sistema nativo de interpolación:

```typescript
// En componentes React
t('finance.period_revenue', { amount: formatCurrency(revenue), period: periodLabel })
t('liquidation.generated_success', { count: generatedCount })
```

---

## 7. Manejo de Errores

### 7.1 Escenarios de Error

| Escenario | Código HTTP | Mensaje | Comportamiento |
|-----------|-------------|---------|----------------|
| Comisión no configurada | 200 (con warning) | "Sin configuración de comisiones. Se aplica 0%." | Liquidación generada con commission_pct=0, warning en logs |
| Sin appointments en período | 200 | N/A | Liquidación creada con $0 en todos los totales |
| Período inválido | 400 | "Formato de fecha inválido. Usar YYYY-MM-DD." | Rechazar request |
| start_date > end_date | 400 | "start_date debe ser menor o igual a end_date." | Rechazar request |
| Período > 366 días | 400 | "El rango no puede superar 366 días." | Rechazar request |
| Profesional no existe | 404 | "Profesional no encontrado" | Rechazar request |
| Transición de estado inválida | 400 | "Transición inválida: {from} → {to}" | Rechazar request |
| Rol insuficiente | 403 | "Acceso restringido a administradores" | Rechazar request |
| Tenant mismatch | 403 | "No tienes acceso a este recurso" | Rechazar request |
| PDF generation failure | 200 (fallback) | N/A | Retorna HTML en lugar de PDF, log warning |
| Email send failure | 500 | "Error al enviar el email" | Log error, no rollback de liquidación |

### 7.2 Logging

```python
# Warning: comisión no configurada
logger.warning(
    f"Professional {professional_id} has no commission config. Using 0% (100% payout). "
    f"Tenant: {tenant_id}"
)

# Warning: PDF fallback
logger.warning(
    f"PDF generation failed for liquidation {liquidation_id}. "
    f"Returning HTML fallback. Error: {str(e)}"
)

# Error: email failure
logger.error(
    f"Failed to send liquidation email for {liquidation_id} to {to_email}. Error: {str(e)}",
    exc_info=True
)
```

---

## 8. Flujos Principales

### Flujo 1: Generación y Aprobación de Liquidación

```
CEO abre /finanzas → Tab Liquidaciones
    ↓
Selecciona período → Click "Generar Liquidaciones"
    ↓
POST /admin/liquidations/generate-bulk
    ↓
Liquidaciones creadas con status='generated'
    ↓
CEO revisa tabla → Click en fila para ver detalle
    ↓
Verifica treatment groups y montos
    ↓
Click "Aprobar" → PATCH /admin/liquidations/{id} {status: 'approved'}
    ↓
Status cambia a 'approved', approved_at set
    ↓
CEO puede descargar PDF o enviar por email
```

### Flujo 2: Pago a Profesional

```
CEO ve liquidación aprobada
    ↓
Click "Registrar Pago" → Modal CommissionEditor
    ↓
Ingresa monto, método, referencia
    ↓
POST /admin/liquidations/{id}/payout
    ↓
ProfessionalPayout creado
    ↓
Si payout_amount cubre total → status auto-cambia a 'paid'
    ↓
PDF caché invalidado
    ↓
CEO puede enviar email con PDF al profesional
```

### Flujo 3: Portal Profesional

```
Profesional logueado → /mis-liquidaciones
    ↓
GET /my/liquidations (filtrado por professional_id del JWT)
    ↓
Ve lista read-only de sus liquidaciones
    ↓
Click para ver detalle → treatment groups
    ↓
Click "Descargar PDF" → GET /my/liquidations/{id}/pdf
```

### Flujo 4: Conciliación

```
CEO abre /finanzas → Tab Conciliación
    ↓
Selecciona período
    ↓
GET /admin/reconciliation
    ↓
Ve summary: cobrado vs pagado
    ↓
Ve lista de discrepancias
    ↓
Click "Resolver" → modal para asociar appointment a liquidación
    ↓
O click "Ignorar" → marca como resuelta
```

---

## 9. Diagrama de Arquitectura

```
FinancialCommandCenterView.tsx
├── Tab: Dashboard
│   ├── FinancialDashboard.tsx
│   │   ├── KPI Cards (4)
│   │   ├── RevenueBarChart (Recharts)
│   │   ├── TreatmentPieChart (Recharts)
│   │   ├── CashFlowLineChart (Recharts)
│   │   ├── PendingCollectionsAlert
│   │   └── MoMComparison
│   └── API: GET /admin/financial-dashboard
│
├── Tab: Liquidaciones
│   ├── LiquidationManager.tsx
│   │   ├── PeriodSelector + BulkGenerate
│   │   ├── LiquidationTable
│   │   │   ├── LiquidationStatusBadge
│   │   │   └── CommissionEditor (modal)
│   │   └── LiquidationDetail (accordion)
│   └── APIs:
│       ├── POST /admin/liquidations/generate-bulk
│       ├── GET /admin/liquidations
│       ├── GET /admin/liquidations/{id}
│       ├── PATCH /admin/liquidations/{id}
│       ├── POST /admin/liquidations/{id}/payout
│       ├── GET /admin/liquidations/{id}/pdf
│       └── POST /admin/liquidations/{id}/send-email
│
├── Tab: Conciliación
│   ├── ReconciliationView.tsx
│   └── API: GET /admin/reconciliation
│
└── Routes
    ├── /finanzas (CEO only)
    └── /mis-liquidaciones (Professional only)
        └── ProfessionalLiquidationsView.tsx

Backend:
├── liquidation_service.py
│   ├── generate_liquidation()
│   ├── generate_bulk_liquidations()
│   ├── get_liquidation_detail()
│   ├── update_liquidation_status()
│   ├── create_payout()
│   └── get_payouts_for_liquidation()
│
├── financial_dashboard_service.py
│   ├── get_financial_summary()
│   ├── get_revenue_by_professional()
│   ├── get_revenue_by_treatment()
│   ├── get_daily_cash_flow()
│   ├── get_mom_growth()
│   ├── get_top_treatments()
│   └── get_pending_collections()
│
├── admin_routes.py (13 nuevos endpoints)
├── models.py (6 nuevos models: 3 financial + 3 treatment plan)
└── alembic/versions/020_financial_command_center.py
```

---

## 10. Prioridad de Implementación

| Fase | Prioridad | Componentes | Dependencias |
|------|-----------|-------------|-------------|
| **Fase 1: Cimientos** | 1 | Migración 020, ORM Models | Ninguna |
| **Fase 2: Servicios** | 2 | liquidation_service, financial_dashboard_service | Fase 1 |
| **Fase 3: Endpoints** | 3 | Todos los endpoints de admin_routes.py | Fase 2 |
| **Fase 4: Dashboard CEO** | 4 | FinancialCommandCenterView, FinancialDashboard | Fase 3 |
| **Fase 5: Liquidaciones** | 5 | LiquidationManager, CommissionEditor | Fase 3 |
| **Fase 6: PDF** | 6 | Template, endpoint PDF, email | Fase 3 |
| **Fase 7: Portal Profesional** | 7 | ProfessionalLiquidationsView, endpoints /my/ | Fase 3 |
| **Fase 8: Conciliación** | 8 | ReconciliationView, endpoint | Fase 3 |
| **Fase 9: Polish** | 9 | i18n completo, responsive, audit trail | Todas las anteriores |

---

## 11. Criterios de Aceptación Generales

| # | Criterio | Verificación |
|---|----------|-------------|
| AC-GEN-01 | Migración ejecuta sin errores en BD existente | `alembic upgrade head` sin fallos |
| AC-GEN-02 | Rollback funciona | `alembic downgrade -1` revierte sin perder datos |
| AC-GEN-03 | Todas las queries filtradas por tenant_id | Revisar cada query SQL en services |
| AC-GEN-04 | CEO tiene acceso completo a `/finanzas` | Login CEO → ver 3 tabs con datos |
| AC-GEN-05 | Profesional solo ve sus datos en `/mis-liquidaciones` | Login professional → solo sus liquidaciones |
| AC-GEN-06 | Secretary no accede a vistas financieras | Login secretary → redirect |
| AC-GEN-07 | Audit trail registra todos los cambios | Verificar notes JSONB después de cada acción |
| AC-GEN-08 | i18n completo en es/en/fr | Cambiar idioma → todos los textos traducidos |
| AC-GEN-09 | PDF usa idioma de la clínica | Clínica en inglés → PDF en inglés |
| AC-GEN-10 | Comisión 0% si no configurada (con warning) | Profesional sin comisiones → liquidación con 0% + warning log |
| AC-GEN-11 | Generación idempotente | Llamar 2 veces → mismo record |
| AC-GEN-12 | Payout auto-completa liquidación | Payout >= payout_amount → status='paid' |
| AC-GEN-13 | Caché PDF se invalida correctamente | Cambiar status → PDF regenerado |
| AC-GEN-14 | Scroll isolation en vistas financieras | Sin overflow horizontal, contenido scrollea internamente |
| AC-GEN-15 | Responsive en mobile | Viewport <768px → layout adaptado |
