# Spec 07: Backend Analytics (Marketing Stats)

## 1. Contexto y Objetivos
**Objetivo:** Proveer datos agregados para el análisis de rendimiento de las campañas.
**Problema:** Falta de visión consolidada de ROI por campaña.

## 2. Requerimientos Técnicos

### Backend (Endpoint)
- **Ruta:** `GET /admin/marketing/stats`
- **Query SQL:**
  - Agrupar por `meta_campaign_name` (o ID si no enriquecido).
  - Filtro: `acquisition_source = 'META_ADS'` AND `tenant_id = $tenant`.
  - Métricas: Leads, Conversaciones activas, Citas agendadas.

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Scenario: Obtener estadísticas
  Given pacientes atribuidos a campañas
  When se consulta el endpoint
  Then retorna lista agrupada por campaña con conteos correctos
```

## 4. Esquema de Datos (Response)

```json
[
  { "campaign": "Promo X", "leads": 10, "appointments": 2 }
]
```

## 5. Riesgos y Mitigación
- **Riesgo:** Performance query.
- **Mitigación:** Monitorear tiempos, planificar índices.

## 6. Compliance SDD v2.0
- **Soberanía:** Absoluta.
