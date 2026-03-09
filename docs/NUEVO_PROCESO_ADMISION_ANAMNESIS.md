# Nuevo Proceso de Admisión y Sistema de Anamnesis Automatizado

**Fecha de implementación:** Marzo 2026  
**Propósito:** Documentar el nuevo flujo completo de admisión de pacientes y sistema de anamnesis médica automatizada para la Dra. María Laura Delgado.

---

## 1. Resumen Ejecutivo

### **¿Qué cambió?**
1. **Proceso de admisión completo**: 7 campos obligatorios para pacientes nuevos
2. **Eliminación de obra social**: La clínica atiende exclusivamente de forma particular
3. **Sistema de anamnesis automatizada**: Recolección y almacenamiento de historial médico completo
4. **Identidad especializada**: Asistente ahora es "secretaria virtual de la Dra. María Laura Delgado"
5. **Frontend mejorado**: Odontograma digital y gestión de documentos clínicos

### **Valor entregado:**
- **Para pacientes**: Atención más personalizada y segura
- **Para la Dra.**: Información completa antes de cada consulta
- **Para el negocio**: Datos valiosos para seguimiento y análisis de adquisición

---

## 2. Nuevos Campos Obligatorios para Pacientes Nuevos

### **2.1 Lista completa de campos requeridos:**
1. **Nombre** (`first_name`) - Texto, mínimo 2 caracteres
2. **Apellido** (`last_name`) - Texto, mínimo 2 caracteres  
3. **DNI** (`dni`) - Solo dígitos (7-8 caracteres)
4. **Fecha de nacimiento** (`birth_date`) - Formato DD/MM/AAAA
5. **Email** (`email`) - Email válido para comunicación
6. **Ciudad/Barrio** (`city`) - Ubicación del paciente ⚠️ *(Requiere migración o parche automático)*
7. **Cómo nos conoció** (`acquisition_source`) - Instagram, Google, Referido, Otro

**⚠️ NOTA IMPORTANTE SOBRE EL CAMPO `city`:**
- **En producción:** El campo `city` se agrega automáticamente al iniciar el servicio (parche 28 en `db.py`)
- **Si el campo no existe:** La tool `book_appointment` validará pero el sistema manejará el caso
- **Verificación:** Ejecutar `patch_022_patient_admission_fields.sql` para garantizar disponibilidad
- **Backward compatibility:** Sistema funciona incluso si `city` no existe (usa valor por defecto)

### **2.2 Validaciones implementadas:**
- ✅ **Fecha**: Formato estricto DD/MM/AAAA, validación de números
- ✅ **Email**: Expresión regular para formato válido
- ✅ **DNI**: Solo dígitos, mínimo 7-8 caracteres
- ✅ **Nombre/Apellido**: Mínimo 2 caracteres cada uno
- ✅ **Fuente**: Normalización a valores estándar

### **2.3 Mensajes de error específicos:**
- Formato fecha inválido: "❌ Error: Formato de fecha de nacimiento inválido. Usá DD/MM/AAAA (ej. 15/05/1990)."
- Email inválido: "❌ Error: Email inválido. Proporcioná un email válido."
- Campos faltantes: Lista específica de campos que faltan

---

## 3. Sistema de Anamnesis Automatizada

### **3.1 Tool `save_patient_anamnesis`:**
**Parámetros (todos opcionales pero recomendados):**
- `base_diseases`: Enfermedades de base (hipertensión, diabetes, etc.)
- `habitual_medication`: Medicación habitual que toma
- `allergies`: Alergias conocidas (medicamentos, alimentos, etc.)
- `previous_surgeries`: Cirugías previas (especialmente bucales)
- `is_smoker`: ¿Es fumador? (Sí/No)
- `smoker_amount`: Cantidad que fuma (ej: "10 cigarrillos/día", "ocasional")
- `pregnancy_lactation`: Embarazo o lactancia (Sí/No, semanas si aplica)
- `negative_experiences`: Experiencias negativas previas en odontología
- `specific_fears`: Miedos específicos relacionados con tratamientos dentales

### **3.2 Flujo obligatorio:**
```
book_appointment exitoso → Preguntas de salud → save_patient_anamnesis
```

### **3.3 Almacenamiento en BD:**
```json
{
  "base_diseases": "Hipertensión controlada",
  "allergies": "Penicilina",
  "is_smoker": "No",
  "anamnesis_completed_at": "2026-03-01T14:30:00Z",
  "anamnesis_completed_via": "ai_assistant"
}
```

**Campo utilizado:** `medical_history JSONB` en tabla `patients`

---

## 4. Actualización del System Prompt

### **4.1 Nueva identidad:**
- **Antes**: "Asistente de la clínica"
- **Ahora**: "Secretaria virtual de la Dra. María Laura Delgado (Cirujana Maxilofacial e Implantóloga en Neuquén)"

### **4.2 Tono específico:**
- Voseo rioplatense profesional pero cálido
- Ejemplos: "¿Qué necesitás?", "Podés", "Tenés", "Contame", "Fijate", "Dale", "Mirá"

### **4.3 FAQs obligatorias:**
- **¿Obra social?**: "No, atendemos de forma particular, pero organizamos el pago en etapas para que sea accesible."
- **¿Costos?**: "El valor se determina tras la evaluación clínica y estudios."
- **¿Duele?**: "La doctora trabaja con anestesia y técnicas de mínima invasión."
- **¿Poco hueso/Rechazados por otros?**: "La Dra. trabaja con protocolos avanzados 3D para pacientes con poco hueso y casos complejos. Vale la pena una segunda opinión."

### **4.4 Horarios base específicos:**
- Lunes: 13:00 a 19:00
- Martes: 10:00 a 17:00
- Miércoles: 12:00 a 18:00
- Jueves: 10:00 a 17:00
- Viernes: 14:00 a 19:00
- Sábados: CERRADO
- Domingos: CERRADO

---

## 5. Frontend Mejorado - Página de Pacientes

### **5.1 Nueva estructura con pestañas:**
1. **Resumen**: Odontograma interactivo + información básica
2. **Historial**: Registros clínicos completos
3. **Documentos**: Galería de documentos clínicos (radiografías, estudios)

### **5.2 Componentes nuevos:**
- **`Odontogram.tsx`**: Odontograma dental interactivo
- **`DocumentGallery.tsx`**: Gestión de documentos clínicos

### **5.3 Integración con anamnesis:**
- Los datos de `save_patient_anamnesis` se muestran en la ficha del paciente
- Alertas automáticas para condiciones críticas (diabetes, hipertensión, etc.)

---

## 6. Migración de Base de Datos

### **6.1 Patch 022 - `patch_022_patient_admission_fields.sql`:**
```sql
-- Agrega campo city si no existe
ALTER TABLE patients ADD COLUMN IF NOT EXISTS city VARCHAR(100);

-- Asegura existencia de campos de admisión
-- first_touch_source (renombrado de acquisition_source en patch 020)
-- birth_date y email ya existen en esquema inicial
```

### **6.2 Campos actualizados en tabla `patients`:**
- `city` (NUEVO): Ciudad/Barrio del paciente
- `first_touch_source`: Fuente de adquisición (INSTAGRAM, GOOGLE, REFERRED, OTHER)
- `birth_date`: Fecha de nacimiento (ya existía)
- `email`: Email del paciente (ya existía)
- `medical_history`: JSONB con anamnesis completa (ya existía)

### **6.3 Eliminado:**
- `insurance_provider`: Ya no se usa (clínica particular)

---

## 7. Flujo de Trabajo Completo

### **7.1 Para pacientes nuevos:**
```
1. Paciente contacta por WhatsApp
2. Secretaria virtual se presenta (Dra. María Laura Delgado)
3. Define tratamiento con list_services
4. Consulta disponibilidad con check_availability
5. Recolecta 7 campos obligatorios
6. Ejecuta book_appointment
7. Hace preguntas de anamnesis
8. Ejecuta save_patient_anamnesis
9. Confirma turno y brinda instrucciones
```

### **7.2 Para pacientes existentes:**
```
1. Paciente contacta por WhatsApp
2. Secretaria virtual identifica paciente existente
3. Define tratamiento
4. Consulta disponibilidad
5. Ejecuta book_appointment (solo fecha y tratamiento)
6. Confirma turno
```

---

## 8. Testing y Verificación

### **8.1 Casos de prueba obligatorios:**
1. **Paciente nuevo con todos los campos correctos**
2. **Paciente nuevo con campos faltantes** (debe mostrar error específico)
3. **Paciente nuevo con formato incorrecto** (fecha, email)
4. **Paciente existente agendando nuevo turno**
5. **Flujo completo con anamnesis**

### **8.2 Verificación de datos:**
- Confirmar que `city` se guarda en BD
- Verificar normalización de `acquisition_source`
- Validar estructura JSONB de `medical_history`
- Comprobar que `insurance_provider` queda como NULL

---

## 9. Consideraciones de Compatibilidad

### **9.1 Endpoints admin existentes:**
- Mantienen compatibilidad con `insurance_provider: null`
- Nuevos campos (`city`, `first_touch_source`) disponibles en queries
- Frontend debe manejar valores NULL para `insurance_provider`

### **9.2 Migración incremental:**
- Patch 022 debe ejecutarse antes de usar nuevos campos
- Sistema funciona sin patch pero `city` será NULL
- Backward compatibility mantenida para pacientes existentes

---

## 10. Próximos Pasos

### **10.1 Inmediatos:**
1. Ejecutar migración SQL en producción
2. Probar flujo completo end-to-end
3. Verificar frontend con datos nuevos

### **10.2 Futuras mejoras:**
1. Dashboard de métricas de adquisición
2. Integración con sistema de recordatorios por email
3. Análisis de ROI por fuente de adquisición
4. Sistema de seguimiento post-consulta

---

## 11. Archivos Modificados

### **Backend:**
- `orchestrator_service/main.py` - Tools actualizadas, nuevo prompt
- `orchestrator_service/migrations/patch_022_patient_admission_fields.sql` - Migración
- `orchestrator_service/admin_routes.py` - Compatibilidad

### **Frontend:**
- `frontend_react/src/views/PatientDetail.tsx` - Nueva interfaz con pestañas
- `frontend_react/src/components/Odontogram.tsx` - Odontograma interactivo
- `frontend_react/src/components/DocumentGallery.tsx` - Gestión documentos
- `frontend_react/src/locales/*.json` - Traducciones actualizadas

### **Documentación:**
- `docs/CONTEXTO_AGENTE_IA.md` - Contexto actualizado
- `docs/12_resumen_funcional_no_tecnico.md` - Resumen funcional
- `docs/TRANSFORMACION_AGNOSTICA_NICHO.md` - Especialización
- `docs/riesgos_entendimiento_agente_agendar.md` - Riesgos actualizados
- `docs/NUEVO_PROCESO_ADMISION_ANAMNESIS.md` - Este documento

---

**Estado:** ✅ Implementado y pusheado a GitHub  
**Próxima acción:** Ejecutar migración SQL en producción