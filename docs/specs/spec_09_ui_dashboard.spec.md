# Spec 09: UI Dashboard Widget (Marketing ROI)

## 1. Contexto y Objetivos
**Objetivo:** Resumen ejecutivo en Dashboard principal.
**Problema:** Visibilidad nula del rendimiento de ads.

## 2. Requerimientos Técnicos

### Frontend (React)
- **Componente:** `MarketingPerformanceCard.tsx` en Dashboard.
- **Datos:** Consume endpoint stats (Spec 07).
- **Vista:** Tabla compacta o Cards con KPIs (Total Leads, Citas).

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Scenario: Widget en Dashboard
  Given datos de marketing disponibles
  When carga el dashboard
  Then el widget muestra resumen de campañas activas
```

## 4. UI/UX
- **Responsividad:** Adaptable a grid de dashboard.

## 5. Riesgos y Mitigación
- **Riesgo:** Carga lenta.
- **Mitigación:** Skeleton loading state.

## 6. Compliance SDD v2.0
- **Diseño:** Nexus standard cards.
