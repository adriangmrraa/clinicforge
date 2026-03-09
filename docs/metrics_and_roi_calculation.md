# Métricas y Cálculo de ROI - ClinicForge

## 📊 **SISTEMA UNIFICADO DE MÉTRICAS**

### **Fuentes de Datos:**
1. **WhatsApp Referrals** (YCloud webhooks)
2. **Leads Forms** (Meta Ads webhooks)
3. **Conversiones** (Leads → Pacientes)

### **Modelos de Atribución:**
1. **First Touch (Primer Contacto)**: Atribuye al primer anuncio que el usuario vio/hizo clic
2. **Last Touch (Último Contacto)**: Atribuye al último anuncio antes de la conversión
3. **Conversion (Conversión)**: Atribuye al lead form que generó la conversión directa

## 🎯 **CÓMO SE CALCULA EL ROI**

### **Fórmula Base:**
```
ROI = ((Valor Total Generado - Inversión Total) / Inversión Total) × 100
```

### **Componentes del Cálculo:**

#### **1. Inversión Total (Spend):**
- **Meta Ads Spend**: Obtenido via Meta Ads API (requiere token)
- **Costo por Lead**: Inversión / Total Leads
- **Costo por Paciente**: Inversión / Total Pacientes

#### **2. Valor Total Generado:**
```
Valor Total = (Pacientes WhatsApp × Valor Promedio) + (Pacientes Leads × Valor Promedio)
```

#### **3. Valor Promedio por Paciente:**
- **Valor Estimado**: $500 USD por paciente (configurable)
- **Basado en**: Tratamientos promedio, frecuencia de visitas, LTV

### **Métricas Clave:**

#### **Para WhatsApp Referrals:**
```
Pacientes por Campaña = COUNT(pacientes con first_touch_source = 'META_ADS')
Costo por Paciente = Inversión Campaña / Pacientes Campaña
ROI Campaña = ((Pacientes × Valor Promedio) - Inversión) / Inversión × 100
```

#### **Para Leads Forms:**
```
Leads por Campaña = COUNT(leads con campaign_id = X)
Conversiones = COUNT(leads con status = 'converted')
Tasa Conversión = Conversiones / Leads × 100
Costo por Lead = Inversión Campaña / Leads
Costo por Conversión = Inversión Campaña / Conversiones
```

## 🔄 **COMPARACIÓN FIRST TOUCH vs LAST TOUCH**

### **First Touch Attribution:**
- **Ventaja**: Mide alcance y descubrimiento
- **Desventaja**: Puede atribuir conversiones a campañas no efectivas
- **Ideal para**: Brand awareness, top of funnel

### **Last Touch Attribution:**
- **Ventaja**: Mide efectividad directa de conversión
- **Desventaja**: Ignora contribuciones anteriores
- **Ideal para**: Performance marketing, bottom of funnel

### **Ejemplo Práctico:**
```
Usuario: Ve Anuncio A (First Touch) → Ve Anuncio B (Last Touch) → Convierte

First Touch ROI: Atribuye conversión a Anuncio A
Last Touch ROI: Atribuye conversión a Anuncio B
```

## 📈 **DASHBOARD DE MÉTRICAS UNIFICADAS**

### **Endpoint: `/admin/metrics/roi/dashboard`**
```json
{
  "first_touch_metrics": {
    "total_patients": 150,
    "total_interactions": 1000,
    "average_conversion_rate": 15.0,
    "average_roi": 250.0
  },
  "last_touch_metrics": {
    "total_patients": 120, 
    "total_interactions": 800,
    "average_conversion_rate": 15.0,
    "average_roi": 300.0
  },
  "comparison": {
    "attribution_difference": {
      "patients": -30,
      "conversion_rate": 0.0,
      "roi": 50.0
    }
  }
}
```

### **Interpretación:**
- **Last Touch muestra ROI más alto** (50 puntos más)
- **First Touch muestra más pacientes** (30 pacientes más)
- **Conclusión**: Las campañas de descubrimiento (first touch) traen más pacientes, pero las de conversión (last touch) son más eficientes

## 🎨 **VISUALIZACIÓN EN FRONTEND**

### **Gráficos Recomendados:**
1. **ROI por Campaña** (barras agrupadas: first vs last touch)
2. **Tendencia de Pacientes** (línea: WhatsApp vs Leads)
3. **Mix de Atribución** (torta: first/last/conversion/organic)
4. **Top Campañas** (tabla con métricas clave)

### **Filtros Disponibles:**
- Período: Diario, Semanal, Mensual, Trimestral, Anual
- Tipo de Atribución: First Touch, Last Touch
- Campaña específica
- Rango de fechas

## 🔧 **CONFIGURACIÓN REQUERIDA**

### **1. Token de Meta Ads:**
```bash
# Para métricas precisas de inversión (spend)
META_USER_LONG_TOKEN=your_token_here
```

### **2. Valor Promedio por Paciente:**
```python
# Configurable en settings
AVERAGE_PATIENT_VALUE = 500  # USD
```

### **3. Período de Retención:**
- **Datos en tiempo real**: Últimos 90 días
- **Histórico completo**: Desde inicio de implementación

## 📋 **EJEMPLOS DE CÁLCULO**

### **Ejemplo 1: Campaña "Implantes Premium"**
```
Inversión: $1,000 USD
WhatsApp Patients (First Touch): 8 pacientes
Leads Forms: 12 leads, 4 conversiones
Valor Promedio: $500 USD

Cálculo:
- Total Pacientes = 8 + 4 = 12 pacientes
- Valor Generado = 12 × $500 = $6,000 USD
- ROI = (($6,000 - $1,000) / $1,000) × 100 = 500%

Métricas:
- Costo por Paciente = $1,000 / 12 = $83.33
- Tasa Conversión Leads = 4 / 12 × 100 = 33.33%
```

### **Ejemplo 2: Comparación First vs Last Touch**
```
Campaña A (First Touch):
- Pacientes: 10, Inversión: $500, ROI: 400%

Campaña B (Last Touch):  
- Pacientes: 8, Inversión: $400, ROI: 600%

Análisis:
- Campaña A trae más pacientes (10 vs 8)
- Campaña B tiene mejor ROI (600% vs 400%)
- Recomendación: Usar A para alcance, B para conversión
```

## 🚀 **API ENDPOINTS DISPONIBLES**

### **Métricas Unificadas:**
```
GET /admin/metrics/campaigns          # Métricas por campaña
GET /admin/metrics/attribution/report # Reporte detallado
GET /admin/metrics/roi/dashboard      # Dashboard completo
GET /admin/metrics/attribution/mix    # Mix de atribución
GET /admin/metrics/trend              # Datos de tendencia
GET /admin/metrics/top/campaigns      # Top campañas
GET /admin/metrics/comparison/first-vs-last # Comparación
```

### **Parámetros Comunes:**
- `period`: daily, weekly, monthly, quarterly, yearly
- `attribution_type`: first_touch, last_touch
- `date_from`, `date_to`: Rango personalizado
- `campaign_id`: Filtro por campaña específica

## ⚠️ **CONSIDERACIONES IMPORTANTES**

### **1. Multi-Tenant:**
- Todas las métricas están aisladas por tenant_id
- No hay cruce de datos entre clínicas

### **2. Privacidad:**
- Los datos de pacientes están anonimizados en agregados
- No se exponen datos personales en métricas

### **3. Performance:**
- Cálculos en tiempo real para últimos 90 días
- Caché Redis para consultas frecuentes
- Background jobs para cálculos pesados

### **4. Integración con Meta API:**
- **Con token**: Métricas precisas de inversión (spend)
- **Sin token**: ROI estimado basado en valor promedio
- **Recomendado**: Configurar token para máxima precisión

## 🔄 **ACTUALIZACIÓN AUTOMÁTICA**

### **Schedule de Actualización:**
- **Cada hora**: Métricas de tendencia
- **Cada 6 horas**: ROI y dashboards
- **Cada 24 horas**: Reportes completos

### **Notificaciones:**
- Alertas cuando ROI < 100% por 7 días consecutivos
- Notificaciones de campañas top performers
- Reportes semanales automáticos por email

## 📚 **REFERENCIAS**

### **Documentación Relacionada:**
- [Leads Forms System](./leads_forms_system.md)
- [Meta Ads Integration](./meta_ads_integration.md)
- [WhatsApp YCloud Webhooks](./ycloud_webhooks.md)

### **Estándares de la Industria:**
- **Google Analytics 4**: Modelos de atribución
- **Meta Ads Manager**: Métricas de performance
- **Healthcare Marketing ROI**: Benchmarks de la industria

---

**Última actualización**: 1 de Marzo 2026  
**Versión**: 2.0.0  
**Estado**: ✅ Implementación Completa