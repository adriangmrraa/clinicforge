# 🛠️ PLAN PARA ARREGLAR FILTROS META ADS

## 🎯 **ESTADO ACTUAL:**
- ✅ **'All' funciona** (mostrando todas las campañas)
- ✅ **Nombres corregidos** (no más "Agrupado por Campaña")
- ❌ **Filtros 30d, 90d, this_year NO funcionan**

## 🔍 **HIPÓTESIS:**
1. **Meta API ignora `date_preset`** y siempre devuelve todos los datos
2. **No hay datos recientes** en la cuenta conectada
3. **Bug en combinación** de datos Meta + locales

## 📊 **DIAGNÓSTICO NECESARIO:**

### **1. Revisar logs del backend (después del deploy revertido):**
```
Buscar estos mensajes:
📊 Meta API Stats: X campaigns, Y ads for preset last_30d (range: last_30d)
📊 Local Campaign Stats: Found Z campaigns with attribution for range last_30d
```

### **2. Ejecutar queries SQL de diagnóstico:**
```sql
-- ¿Hay pacientes Meta en diferentes períodos?
SELECT 
    COUNT(*) as total_meta_patients,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') as last_30d,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '90 days') as last_90d,
    COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM created_at) = EXTRACT(YEAR FROM NOW())) as this_year
FROM patients 
WHERE acquisition_source = 'META_ADS' AND meta_campaign_id IS NOT NULL;

-- ¿Cuándo fue el último lead de Meta?
SELECT MAX(created_at) as last_meta_lead FROM patients 
WHERE acquisition_source = 'META_ADS';
```

### **3. Verificar Meta Ads Manager:**
- ¿Hay campañas activas en los últimos 30 días?
- ¿Hay gasto registrado recientemente?

## 🚀 **SOLUCIÓN PROPUESTA:**

### **Opción A: Mejorar logging y validación**
```python
# En marketing_service.py, después de obtener datos de Meta:
if meta_campaigns:
    # Verificar si Meta realmente filtró por fecha
    sample_campaign = meta_campaigns[0]
    logger.info(f"📊 Sample Campaign Data: {sample_campaign}")
    
    # Contar campañas con spend > 0 en el período
    campaigns_with_spend = [c for c in meta_campaigns if float(c.get('spend', 0)) > 0]
    logger.info(f"📊 Campaigns with spend in period: {len(campaigns_with_spend)}/{len(meta_campaigns)}")
```

### **Opción B: Implementar filtrado local como fallback**
```python
# Si Meta devuelve muchos datos pero debería filtrar
if time_range != "all" and len(meta_campaigns) > 50:  # Número arbitrario
    logger.warning(f"⚠️ Meta API may not be filtering by date_preset. Got {len(meta_campaigns)} campaigns for {time_range}")
    # Podríamos implementar filtrado local aquí
```

### **Opción C: Usar time_range con validación incremental**
```python
# Solo para los filtros que no funcionan
if time_range in ["last_30d", "last_90d", "this_year"]:
    # Intentar con time_range primero
    try:
        data = await meta_client.get_ads_insights(..., time_range=calculated_dates)
        if not data:  # Si no devuelve datos, usar date_preset
            data = await meta_client.get_ads_insights(..., date_preset=meta_preset)
    except:
        # Fallback a date_preset si time_range falla
        data = await meta_client.get_ads_insights(..., date_preset=meta_preset)
```

## 📋 **CHECKLIST DE IMPLEMENTACIÓN:**

### **FASE 1: Diagnóstico (AHORA)**
- [ ] Deploy completado con reversión
- [ ] Verificar que 'All' funciona
- [ ] Revisar logs del backend
- [ ] Ejecutar queries SQL de diagnóstico
- [ ] Reportar hallazgos

### **FASE 2: Implementación (si es necesario)**
- [ ] Agregar más logging para debug
- [ ] Implementar validación de datos Meta
- [ ] Considerar filtrado local como fallback
- [ ] Testear cada filtro individualmente

### **FASE 3: Verificación**
- [ ] 30 días muestra datos recientes
- [ ] 3 meses muestra más datos que 30 días
- [ ] Este año muestra datos del año actual
- [ ] All sigue funcionando

## ⚠️ **RIESGOS Y MITIGACIÓN:**
1. **Riesgo:** Cambios rompen funcionalidad existente
   **Mitigación:** Implementar incrementalmente, mantener fallbacks
2. **Riesgo:** Meta API inconsistente
   **Mitigación:** Agregar retries y validación
3. **Riesgo:** Performance con muchos datos
   **Mitigación:** Implementar paginación y caching

## 🎯 **CRITERIOS DE ÉXITO:**
1. Todos los filtros muestran datos apropiados para su período
2. No se rompe funcionalidad existente
3. Performance aceptable (< 5 segundos por filtro)
4. Logging suficiente para diagnóstico futuro

---

**¿Listo para proceder con el diagnóstico una vez que el deploy termine?**