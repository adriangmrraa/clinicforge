# 🗺️ PLAN DE IMPLEMENTACIÓN: SISTEMA DE BÚSQUEDA POR CIUDAD

## 📋 CONTEXTO
**Problema identificado:** No hay forma de filtrar/buscar pacientes por ciudad en el frontend.
**Impacto:** Imposible segmentar pacientes geográficamente para marketing o análisis.
**Prioridad:** MEDIA (importante para negocio, no crítica para funcionamiento básico)

## 🎯 OBJETIVOS
1. **Filtro por ciudad** en lista de pacientes
2. **Búsqueda por ciudad/barrio** con autocomplete
3. **Estadísticas por ciudad** en dashboard
4. **Exportación segmentada** por ubicación

## 🔧 IMPLEMENTACIÓN TÉCNICA

### **FASE 1: BACKEND - ENDPOINTS DE BÚSQUEDA**

#### **1.1 Endpoint de búsqueda por ciudad:**
```python
# En admin_routes.py
@router.get("/admin/patients/search")
async def search_patients(
    city: Optional[str] = Query(None),
    # ... otros filtros existentes
):
    query = "SELECT * FROM patients WHERE tenant_id = $1"
    params = [tenant_id]
    
    if city:
        query += " AND city ILIKE $2"
        params.append(f"%{city}%")
    
    # ... resto de la lógica existente
```

#### **1.2 Endpoint de ciudades únicas:**
```python
@router.get("/admin/patients/cities")
async def get_unique_cities():
    rows = await pool.fetch("""
        SELECT DISTINCT city 
        FROM patients 
        WHERE tenant_id = $1 AND city IS NOT NULL AND city != ''
        ORDER BY city
    """, tenant_id)
    return [row["city"] for row in rows]
```

### **FASE 2: FRONTEND - COMPONENTES DE BÚSQUEDA**

#### **2.1 Modificar PatientsListView.tsx:**
- Agregar campo de búsqueda "Ciudad" junto a los filtros existentes
- Implementar autocomplete con endpoint `/admin/patients/cities`
- Agregar badge de filtro activo cuando se filtra por ciudad

#### **2.2 Componente CityFilter.tsx:**
```tsx
interface CityFilterProps {
  value: string;
  onChange: (city: string) => void;
  cities: string[];
}

const CityFilter: React.FC<CityFilterProps> = ({ value, onChange, cities }) => {
  return (
    <div className="relative">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Filtrar por ciudad..."
        list="city-suggestions"
        className="w-full px-3 py-2 border rounded-lg"
      />
      <datalist id="city-suggestions">
        {cities.map(city => (
          <option key={city} value={city} />
        ))}
      </datalist>
    </div>
  );
};
```

### **FASE 3: DASHBOARD - ESTADÍSTICAS POR CIUDAD**

#### **3.1 Endpoint de estadísticas:**
```python
@router.get("/admin/metrics/city-distribution")
async def get_city_distribution():
    rows = await pool.fetch("""
        SELECT 
            city,
            COUNT(*) as patient_count,
            COUNT(CASE WHEN status = 'active' THEN 1 END) as active_count,
            COUNT(CASE WHEN acquisition_source = 'INSTAGRAM' THEN 1 END) as instagram_count
        FROM patients 
        WHERE tenant_id = $1 AND city IS NOT NULL AND city != ''
        GROUP BY city
        ORDER BY patient_count DESC
        LIMIT 10
    """, tenant_id)
    
    return [
        {
            "city": row["city"],
            "patient_count": row["patient_count"],
            "active_count": row["active_count"],
            "instagram_count": row["instagram_count"]
        }
        for row in rows
    ]
```

#### **3.2 Componente CityDistributionChart.tsx:**
- Gráfico de barras con distribución de pacientes por ciudad
- Tooltips con métricas detalladas
- Filtro por rango de fechas

### **FASE 4: MEJORAS AVANZADAS (OPCIONAL)**

#### **4.1 Geocoding automático:**
- Usar API de Google Maps/OpenStreetMap para normalizar nombres de ciudades
- Extraer provincia/región automáticamente
- Validar que ciudades existan

#### **4.2 Mapa interactivo:**
- Integración con Leaflet/Mapbox
- Mostrar concentración de pacientes por ubicación
- Heatmap de densidad

#### **4.3 Segmentación para marketing:**
- Crear listas de pacientes por ciudad para campañas
- Integración con Meta Ads para targeting geográfico
- Análisis de conversión por ubicación

## 📅 CRONOGRAMA ESTIMADO

### **Sprint 1 (2-3 días):**
- ✅ Endpoints backend de búsqueda y ciudades únicas
- ✅ Integración en PatientsListView
- ✅ Testing básico

### **Sprint 2 (2-3 días):**
- ✅ Endpoint de estadísticas por ciudad
- ✅ Componente de gráfico en dashboard
- ✅ Mejoras de UX/UI

### **Sprint 3 (3-5 días):**
- ⏳ Geocoding automático (opcional)
- ⏳ Mapa interactivo (opcional)
- ⏳ Segmentación marketing (opcional)

## 🔍 CONSIDERACIONES TÉCNICAS

### **Performance:**
- **Índice necesario:** `CREATE INDEX idx_patients_city ON patients(city);` (YA EXISTE en Patch 022)
- **Paginación:** Mantener paginación existente para grandes volúmenes
- **Caché:** Cachear lista de ciudades únicas (Redis, 24h TTL)

### **Calidad de datos:**
- **Normalización:** Almacenar ciudad en formato "Ciudad, Provincia"
- **Validación:** Frontend sugiere ciudades existentes
- **Limpieza:** Script para normalizar ciudades históricas

### **UX/UI:**
- **Autocomplete:** Sugerir ciudades mientras se escribe
- **Clear filters:** Botón para limpiar filtro de ciudad
- **Empty states:** Mensaje cuando no hay pacientes en una ciudad

## 🚀 VALOR DE NEGOCIO

### **Para la Dra. María Laura Delgado:**
1. **Segmentación geográfica:** Identificar de dónde vienen sus pacientes
2. **Marketing dirigido:** Campañas específicas por ciudad/barrio
3. **Expansión estratégica:** Identificar áreas con potencial de crecimiento
4. **Logística:** Optimizar rutas para visitas a domicilio (si aplica)

### **Para el sistema ClinicForge:**
1. **Feature completa:** Sistema de filtrado profesional
2. **Competitividad:** Ventaja sobre sistemas que no tienen esta funcionalidad
3. **Escalabilidad:** Base para features más avanzadas (mapas, heatmaps)

## ⚠️ RIESGOS Y MITIGACIONES

### **Riesgo 1: Calidad de datos inconsistentes**
- **Problema:** Ciudades escritas de diferentes formas (Neuquen, Neuquén, Neuquén Capital)
- **Mitigación:** Sistema de normalización + sugerencias de autocomplete

### **Riesgo 2: Performance con muchas ciudades**
- **Problema:** Autocomplete lento con 1000+ ciudades únicas
- **Mitigación:** Paginación en autocomplete + búsqueda incremental

### **Riesgo 3: Privacidad de datos**
- **Problema:** Exposición de ubicaciones específicas de pacientes
- **Mitigación:** Agregación a nivel ciudad, no dirección exacta

## 📊 MÉTRICAS DE ÉXITO

### **Técnicas:**
- Tiempo de respuesta < 200ms para búsqueda por ciudad
- 100% de cobertura de pacientes con ciudad registrada (después de migración)
- 0 errores en normalización de nombres de ciudades

### **De negocio:**
- Uso del filtro por ciudad > 20% de las sesiones administrativas
- Reducción tiempo búsqueda pacientes específicos > 50%
- Mejora en targeting campañas marketing > 30%

## 🔗 DEPENDENCIAS

### **Críticas:**
- ✅ Migración Patch 022 ejecutada (campo `city` en BD)
- ✅ Frontend PatientDetail actualizado (muestra ciudad)

### **Recomendadas:**
- Sistema de caché Redis configurado
- API de geocoding (opcional para mejoras avanzadas)

## 🎯 CONCLUSIÓN

**La implementación de búsqueda por ciudad es una funcionalidad de alto valor con esfuerzo moderado.** 

**Recomendación:** Implementar Fases 1 y 2 inmediatamente después de resolver los pendientes críticos (migración SQL). Las Fases 3 y 4 pueden considerarse para futuras iteraciones.

**Impacto inmediato:** Mejora significativa en usabilidad para segmentación geográfica.
**Esfuerzo estimado:** 4-6 días de desarrollo.
**ROI:** Alto - feature diferenciadora con múltiples casos de uso.