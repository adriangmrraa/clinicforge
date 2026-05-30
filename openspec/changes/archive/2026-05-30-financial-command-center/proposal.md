# Proposal: Centro de Comando Financiero (Financial Command Center)

## Intent

Transformar el sistema financiero de clinicforge de vistas desconectadas y cálculos efímeros a un **centro de comando unificado** con gestión real de liquidaciones, comisiones profesionales, tracking de pagos y visibilidad financiera global.

Actualmente las "liquidaciones" son una vista computada on-the-fly: no hay historial, no se pueden marcar como pagadas, no hay PDFs, no hay comisiones configurables, y el CEO no tiene un dashboard financiero con tendencias y conciliación.

## Scope

### In Scope

| Pilar | Entregable | Detalle |
|-------|-----------|---------|
| **Liquidaciones Reales** | Tabla `liquidation_records` | Snapshots persistentes (período, professional_id, totales, status: pending\|approved\|paid) |
| | Tabla `professional_payouts` | Tracking de pagos (monto, método, fecha, referencia) |
| | Tabla `professional_commissions` | Tasas de comisión por profesional (default %) y opcionalmente por tratamiento |
| | Generación 1-click | Snapshot de período → liquidación creada con totales calculados |
| | Flujo de aprobación | pending → approved → paid con fecha y referencia |
| | PDF de liquidaciones | Documento descargable/enviable al profesional |
| **Dashboard Financiero** | Ruta `/finanzas` | FinancialCommandCenterView con métricas globales |
| | Revenue por profesional | Gráfico de barras |
| | Revenue por tratamiento | Gráfico de torta |
| | Comparación MoM | Mes actual vs mes anterior |
| | Alertas de cobro pendiente | Saldos outstanding de planes de tratamiento |
| | Cash flow timeline | Entradas diarias |
| | Margen de ganancia | Revenue - payouts profesionales |
| **Conciliación y Portal** | Ledger financiero unificado | Todos los movimientos de dinero en un lugar |
| | Reporte de conciliación | Patient payments vs professional payouts |
| | Detección de discrepancias | Alertas automáticas |
| | Portal profesional `/mis-liquidaciones` | Profesionales ven sus propias liquidaciones |
| | Audit trail | Historial de cambios en facturación |
| **Backend** | ORM models en `models.py` | LiquidationRecord, ProfessionalPayout, ProfessionalCommission |
| | Servicio `liquidation_service.py` | Lógica de generación, aprobación, PDF |
| | Servicio `financial_dashboard_service.py` | Agregaciones y métricas |
| | Nuevos endpoints en `admin_routes.py` | CRUD liquidaciones, dashboard, payouts |
| | Migración Alembic `020_financial_command_center.py` | Nuevas tablas e índices |
| **Frontend** | `FinancialCommandCenterView.tsx` | Vista principal de finanzas |
| | Componentes financieros | Charts, tablas, alertas |
| | `LiquidationTab.tsx` mejorado | Integración con liquidaciones reales |
| | `ProfessionalLiquidationsView.tsx` | Vista self-service para profesionales |
| | i18n keys | es/en/fr para todas las nuevas cadenas |

### Out of Scope

- Integración con pasarelas de pago externas (MercadoPago, Stripe)
- Facturación electrónica AFIP / comprobantes fiscales
- Gestión de impuestos / retenciones
- Presupuesto anual / forecasting financiero
- Multi-moneda (solo ARS)
- Notificaciones push/SMS de liquidaciones (solo PDF descargable por ahora)

## Approach

### Fase 1: Cimientos (Backend)
1. **Migración Alembic**: Crear 3 tablas nuevas (`liquidation_records`, `professional_payouts`, `professional_commissions`) + índices por `tenant_id`, `professional_id`, `period_start`
2. **ORM Models**: Agregar a `models.py` las 3 clases SQLAlchemy con relaciones a `professionals`, `tenants`
3. **Liquidation Service**: Nuevo `services/liquidation_service.py` con:
   - `generate_liquidation(tenant_id, professional_id, period_start, period_end)` → snapshot
   - `approve_liquidation(liquidation_id)` → cambia status
   - `mark_paid(liquidation_id, payout_data)` → crea payout + actualiza liquidación
   - `generate_pdf(liquidation_id)` → genera documento PDF
   - `get_liquidation_history(tenant_id, filters)` → listado con paginación
4. **Financial Dashboard Service**: Nuevo `services/financial_dashboard_service.py` con:
   - `get_revenue_by_professional(tenant_id, period)` → barras
   - `get_revenue_by_treatment(tenant_id, period)` → torta
   - `get_mom_comparison(tenant_id)` → mes actual vs anterior
   - `get_pending_collections(tenant_id)` → saldos pendientes
   - `get_cash_flow(tenant_id, days)` → timeline diario
   - `get_profit_margin(tenant_id, period)` → revenue - payouts
5. **Endpoints**: Agregar a `admin_routes.py` las rutas protegidas con `tenant_id` filter obligatorio

### Fase 2: Dashboard CEO (Frontend)
1. **FinancialCommandCenterView**: Vista principal con KPIs, charts (recharts), alertas
2. **Componentes reutilizables**: RevenueBarChart, TreatmentPieChart, CashFlowTimeline, PendingCollectionsAlert
3. **LiquidationTab mejorado**: Reemplazar vista computada con datos reales de `liquidation_records`

### Fase 3: Portal Profesional + Conciliación
1. **ProfessionalLiquidationsView**: Ruta `/mis-liquidaciones` con filtro por profesional logueado
2. **ConciliationReport**: Tabla de conciliación payments vs payouts con detección de discrepancias
3. **PDF download**: Endpoint que genera y sirve PDF de liquidación

## Affected Areas

| Área | Impacto | Descripción |
|------|---------|-------------|
| `orchestrator_service/models.py` | Modificado | 3 nuevos ORM models |
| `orchestrator_service/admin_routes.py` | Modificado | ~15 nuevos endpoints |
| `orchestrator_service/analytics_service.py` | Modificado | Integración con comisiones |
| `orchestrator_service/services/liquidation_service.py` | Nuevo | Servicio de liquidaciones |
| `orchestrator_service/services/financial_dashboard_service.py` | Nuevo | Servicio de métricas |
| `orchestrator_service/alembic/versions/020_financial_command_center.py` | Nuevo | Migración de schema |
| `frontend_react/src/views/FinancialCommandCenterView.tsx` | Nuevo | Vista principal finanzas |
| `frontend_react/src/views/ProfessionalLiquidationsView.tsx` | Nuevo | Portal profesional |
| `frontend_react/src/components/finance/` | Nuevo | Componentes financieros |
| `frontend_react/src/components/analytics/LiquidationTab.tsx` | Modificado | Integración con datos reales |
| `frontend_react/src/App.tsx` | Modificado | Nuevas rutas |
| `frontend_react/src/locales/{es,en,fr}.json` | Modificado | Keys i18n |

## Risks

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Migración falla en BD con datos existentes | Media | Alto | Backup previo; migración idempotente; testing en staging |
| Cálculos de liquidación no coinciden con vista actual | Media | Alto | Validar contra `get_professionals_liquidation` existente en paralelo |
| Performance en agregaciones con muchos datos | Media | Medio | Índices por tenant_id + period; caché de dashboard |
| PDF generation bloquea el request loop | Baja | Medio | Generación asíncrona o endpoint dedicado |
| Confusión de roles (CEO vs profesional) | Baja | Alto | Middleware de validación de rol en cada endpoint |
| Scope creep (el cambio es grande) | Alta | Alto | Fases bien definidas; out of scope explícito |

## Rollback Plan

1. **Migración**: `alembic downgrade -1` revierte las 3 tablas nuevas sin afectar datos existentes
2. **Endpoints**: Los nuevos endpoints son aditivos; no modifican rutas existentes
3. **Frontend**: Las nuevas vistas son rutas nuevas; no modifican vistas existentes
4. **LiquidationTab**: Se mantiene la vista computada como fallback si el servicio nuevo falla
5. **Si algo falla críticamente**: `git revert` del commit + `alembic downgrade -1`

## Dependencies

- Python packages: `weasyprint` o `reportlab` para generación de PDFs
- Frontend: `recharts` (ya presente en el proyecto para gráficos)
- Existing: `analytics_service.get_professionals_liquidation()` como referencia de cálculo
- Existing: `treatment_plan_payments` y `accounting_transactions` como fuente de datos

## Success Criteria

- [ ] CEO puede generar una liquidación con 1 click para un profesional y período
- [ ] Liquidación queda persistida con status `pending` → `approved` → `paid`
- [ ] PDF de liquidación descargable y con datos correctos
- [ ] Dashboard `/finanzas` muestra revenue por profesional, tratamiento, MoM, cash flow
- [ ] Margen de ganancia calculado correctamente (revenue - payouts)
- [ ] Profesional logueado ve sus liquidaciones en `/mis-liquidaciones`
- [ ] Reporte de conciliación muestra payments vs payouts con discrepancias
- [ ] Todos los queries filtrados por `tenant_id` (soberanía de datos)
- [ ] i18n completo en es/en/fr
- [ ] Migración Alembic ejecuta sin errores en BD existente
