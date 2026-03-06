# 📋 INFORME DE DESFASES: DOCUMENTACIÓN vs CÓDIGO REAL

**Fecha:** 6 de Marzo 2026  
**Proyecto:** ClinicForge  
**Auditoría realizada:** Automatizada  
**Estado:** 🟡 DESFASES IDENTIFICADOS

## 🎯 RESUMEN EJECUTIVO

Se identificaron **desfases críticos** entre la documentación y el código real. La documentación actual describe un sistema que no coincide completamente con la implementación real.

### **✅ LO QUE SÍ COINCIDE:**
1. **System Prompt** - Correctamente documentado vs implementado
2. **Sistema de Jobs** - Correctamente documentado vs implementado  
3. **AutomationService** - Correctamente documentado como desactivado
4. **Estructura general** - Coincide en su mayoría

### **❌ DESFASES CRÍTICOS IDENTIFICADOS:**

## 1. 🚨 CAMPO `city` EN PACIENTES

### **Documentación actual dice:**
- Campo `city` es **obligatorio** para pacientes nuevos
- Está incluido en el proceso de admisión
- Es parte de la tool `book_appointment`

### **Realidad del código:**
- ✅ **Tool `book_appointment`** SÍ espera parámetro `city`
- ❌ **Parches automáticos (`db.py`)** NO incluyen `ADD COLUMN city`
- ✅ **Migración manual (`patch_022`)** SÍ incluye `ADD COLUMN city`
- ⚠️  **Estado en producción:** Depende de si se ejecutó `patch_022`

### **Consecuencia:**
- **Sin migración ejecutada:** `book_appointment` FALLARÁ al intentar insertar `city`
- **Documentación incorrecta:** Dice que `city` existe cuando puede no existir
- **Proceso de admisión:** Incompleto sin campo `city`

## 2. 🔄 SISTEMA DE PARCHES AUTOMÁTICOS

### **Documentación actual dice:**
- Sistema de parches idempotentes en `db.py`
- Campos automáticamente agregados al iniciar

### **Realidad del código:**
- ✅ **Parches para jobs:** `reminder_sent`, `followup_sent` SÍ están en `db.py`
- ❌ **Parche para `city`:** NO está en `db.py`, solo en migración manual
- ⚠️  **Inconsistencia:** Algunos campos automáticos, otros manuales

## 3. 📊 DOCUMENTACIÓN DE CAMPOS OBLIGATORIOS

### **Documentación actual (`NUEVO_PROCESO_ADMISION_ANAMNESIS.md`):**
Lista 7 campos obligatorios para pacientes nuevos:
1. first_name
2. last_name  
3. dni
4. birth_date
5. email
6. city
7. acquisition_source

### **Realidad del código:**
- ✅ **Tool valida:** Los 7 campos son requeridos para pacientes `status='guest'`
- ❌ **BD puede no tener:** `city` si no se ejecutó migración
- ⚠️  **Validación inconsistente:** Tool valida campo que puede no existir

## 4. 🗄️ ESQUEMA DE BASE DE DATOS DOCUMENTADO

### **Documentación actual (`SISTEMA_JOBS_PROGRAMADOS.md`):**
Menciona campos completos para appointments:
- `reminder_sent`, `reminder_sent_at`
- `followup_sent`, `followup_sent_at`

### **Realidad del código:**
- ✅ **Parches SÍ existen** en `db.py` para estos campos
- ✅ **Índices SÍ existen** para optimización
- ✅ **Coincide completamente** con documentación

## 📈 ANÁLISIS DE IMPACTO

### **Impacto ALTO:**
1. **Creación de pacientes** - Puede fallar si `city` no existe en BD
2. **Proceso de admisión** - Incompleto sin campo `city`
3. **Consistencia de datos** - Pacientes sin información de ubicación

### **Impacto MEDIO:**
1. **Documentación engañosa** - Describe sistema que no existe completamente
2. **Mantenimiento** - Dos sistemas de migración (automático vs manual)

### **Impacto BAJO:**
1. **Jobs programados** - Funcionan correctamente
2. **System prompt** - Correctamente implementado
3. **AutomationService** - Correctamente desactivado

## 🔧 ACCIONES CORRECTIVAS REQUERIDAS

### **ACCIÓN 1 (CRÍTICA): Agregar parche para `city` en `db.py`**
```sql
-- Agregar al final de la lista de parches en db.py
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='city') THEN
        ALTER TABLE patients ADD COLUMN city VARCHAR(100);
    END IF;
END $$;
```

### **ACCIÓN 2 (ALTA): Actualizar documentación de admisión**
- Especificar que `city` requiere migración `patch_022` o parche automático
- Documentar estado actual: "Campo `city` disponible después de ejecutar migración"
- Agregar nota sobre dependencia de migración

### **ACCIÓN 3 (MEDIA): Unificar sistema de migraciones**
- Opción A: Mover todos los campos a parches automáticos
- Opción B: Documentar claramente qué campos son automáticos vs manuales
- Recomendación: Usar solo parches automáticos para consistencia

### **ACCIÓN 4 (BAJA): Verificar tool `book_appointment`**
- Agregar validación: verificar si campo `city` existe antes de usarlo
- Manejo de error elegante si `city` no existe
- Logging claro del problema

## 📋 PLAN DE ACTUALIZACIÓN

### **FASE 1 (Inmediata): Corregir desfase crítico**
1. Agregar parche para `city` en `db.py`
2. Actualizar `NUEVO_PROCESO_ADMISION_ANAMNESIS.md` con nota sobre migración
3. Verificar que tool `book_appointment` maneje caso de campo ausente

### **FASE 2 (Corto plazo): Actualizar documentación completa**
1. Revisar todos los documentos vs código real
2. Actualizar `00_INDICE_DOCUMENTACION.md` con estado real
3. Crear documento `ESTADO_ACTUAL_SISTEMA.md` con realidad vs documentación

### **FASE 3 (Mediano plazo): Unificar sistema**
1. Decidir estrategia: solo parches automáticos o documentación clara
2. Implementar sistema consistente
3. Actualizar toda documentación para reflejar sistema unificado

## 🎯 RECOMENDACIONES

### **Para desarrollo actual:**
1. **Ejecutar migración `patch_022`** en todos los entornos
2. **Agregar parche automático** para `city` como respaldo
3. **Actualizar documentación** para reflejar dependencia de migración

### **Para futuros desarrollos:**
1. **Usar solo parches automáticos** en `db.py` para consistencia
2. **Auditoría regular** documentación vs código
3. **Script de verificación** automática de desfases

### **Para documentación:**
1. **Marcar claramente** qué requiere migración manual
2. **Incluir scripts** para verificar estado del sistema
3. **Mantener documento** `DESFASES_CONOCIDOS.md` actualizado

## 📊 ESTADO ACTUAL POR COMPONENTE

| Componente | Estado | Coincidencia | Acción Requerida |
|------------|--------|--------------|------------------|
| **System Prompt** | ✅ | 95% | Ninguna |
| **Jobs Programados** | ✅ | 100% | Ninguna |
| **AutomationService** | ✅ | 100% | Ninguna |
| **Campo `city`** | ❌ | 0% | **CRÍTICA** |
| **Parches automáticos** | ⚠️ | 80% | Media |
| **Documentación admisión** | ⚠️ | 60% | Alta |
| **Tool book_appointment** | ⚠️ | 70% | Media |

## 🏁 CONCLUSIÓN

**Existen desfases significativos entre documentación y código real**, particularmente en el campo `city` para pacientes. 

### **Riesgos identificados:**
1. **Fallo en producción** si `city` no existe y se usa `book_appointment`
2. **Documentación engañosa** para desarrolladores nuevos
3. **Sistema inconsistente** con dos métodos de migración

### **Acciones inmediatas recomendadas:**
1. ✅ Ejecutar `patch_022_patient_admission_fields.sql` en producción
2. ✅ Agregar parche automático para `city` en `db.py`
3. ✅ Actualizar documentación para reflejar realidad actual
4. ✅ Crear script de verificación de desfases regular

**La documentación debe reflejar EXACTAMENTE la realidad del código, incluyendo dependencias de migración y estado actual del sistema.**

---

**Auditoría completada:** 6 de Marzo 2026  
**Próxima auditoría recomendada:** 1 semana después de correcciones