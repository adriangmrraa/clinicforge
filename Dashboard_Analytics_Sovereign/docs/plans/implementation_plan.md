# 📋 Implementation Plan: Dashboard Analytics Sovereign

## Goal Description
Implementar un sistema de BI (Business Intelligence) para clínicas dentales que ofrezca métricas críticas de ROI, salud clínica y eficiencia operativa, asegurando el aislamiento absoluto de datos por `tenant_id`.

---

## Proposed Changes

### 🔧 Database [Sovereign DB]
#### [NEW] [007_analytics_metrics.sql](file:///c:/Users/Asus/Downloads/Clinica%20Dental/Dashboard_Analytics_Sovereign/db/migrations/007_analytics_metrics.sql)
Implementar la tabla de métricas agregadas con índices únicos para evitar duplicidad de datos por día/tenant.
```sql
CREATE TABLE IF NOT EXISTS daily_analytics_metrics (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL,
    metric_date DATE NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    metric_value JSONB DEFAULT '0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, metric_date, metric_type)
);
CREATE INDEX idx_analytics_tenant_date ON daily_analytics_metrics(tenant_id, metric_date);
```

### 🧠 Backend [Sovereign Engine]
#### [NEW] [analytics_service.py](file:///c:/Users/Asus/Downloads/Clinica%20Dental/Dashboard_Analytics_Sovereign/src/services/analytics_service.py)
- Implementar la lógica de agregación que recorre citas y pagos.
- Función herculana `calculate_all_kpis(tenant_id)` para poblar la tabla de métricas.

#### [NEW] [analytics_routes.py](file:///c:/Users/Asus/Downloads/Clinica%20Dental/Dashboard_Analytics_Sovereign/src/api/analytics_routes.py)
- Endpoint `GET /admin/analytics/ceo`: Retorna LTV, ROI de IA y Conversión.
- Endpoint `GET /admin/analytics/secretary`: Retorna tiempos de espera y carga de sillones.
- **Seguridad**: Inyectar `Depends(get_current_tenant)` en cada ruta.

### 🎨 Frontend [Nexus UI]
#### [NEW] [AnalyticsDashboard.tsx](file:///c:/Users/Asus/Downloads/Clinica%20Dental/Dashboard_Analytics_Sovereign/src/views/AnalyticsDashboard.tsx)
- Implementar contenedor principal con **Scroll Isolation**.
- Componente `CEOView`: Gráficos de barra y áreas para tendencias financieras.
- Componente `SecretaryView`: Dashboards de alta densidad con alertas de "Sala de Espera".
- **Visuales**: Aplicar `backdrop-blur-2xl` y `rounded-3xl` en cada card de métrica.

---

## Verification Plan

### Automated Tests
- **Isolation Check**: Test unitario que intente consultar datos del `tenant_id` A desde un contexto de `tenant_id` B (Debe fallar).
- **KPI Accuracy**: Validar que la fórmula de ROI coincida con los datos brutos de la DB.

### Manual Verification
- Cargar datos ficticios para 2 tenants distintos y verificar que los dashboards no se crucen.
- Simular un retraso en una cita y verificar la alerta visual en la vista de Secretaría.
