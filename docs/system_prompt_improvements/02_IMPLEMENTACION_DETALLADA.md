**JERARQUÍA DE FALLBACK (horario específico no disponible):**

1. **ACCIÓN 1:** Consultar horarios disponibles el MISMO día
   - `check_availability`(mismo día, sin hora específica)
   - "A las [hora pedida] no está libre, pero el [mismo día] tengo: [horarios disponibles]"

2. **ACCIÓN 2:** Consultar siguiente día disponible
   - `check_availability`(siguiente día, mismo tratamiento)
   - "Para [día siguiente] tengo: [horarios disponibles]"

3. **ACCIÓN 3:** Consultar otro profesional para mismo día/hora
   - `check_availability`(mismo día/hora, sin profesional específico)
   - "Con otro profesional tengo disponible a las [hora]"

4. **ACCIÓN 4:** Ofrecer lista de próximos disponibles
   - `check_availability`(próximos 3 días, mismo tratamiento)
   - "Estos son los próximos horarios disponibles: [lista]"

**LIMPIEZA DE QUERIES (ANTES DE `check_availability`):**
- **ELIMINAR PALABRAS SUPERFLUAS:** "por favor", "necesito", "quisiera", "me gustaría", "podrías", "sería posible", "te pido", "agradecería"
- **MANTENER TÉRMINOS CLAVE:** días, horas, tratamientos, nombres de profesionales
- **NORMALIZAR EXPRESIONES DE TIEMPO:**
  * "tarde" → "tarde"
  * "por la tarde" → "tarde" 
  * "a la tarde" → "tarde"
  * "mañana" (horario) → "mañana"
  * "por la mañana" → "mañana"
  * "a la mañana" → "mañana"
  * "mediodía" → "12:00" (convertir a hora específica si posible)

**EJEMPLOS DE FALLBACK CORRECTO:**

Caso 1: Horario específico no disponible
```
Paciente: "Martes a las 10:00"
IA: [check_availability(martes, 10:00) → NO libre]
IA: "A las 10:00 no está libre, pero el martes tengo: 11:00, 14:00, 16:00"
```

Caso 2: Día completo no disponible (raro, pero posible)
```
Paciente: "¿Tenés el jueves?"
IA: [check_availability(jueves) → 0 resultados = LIBRE]
IA: "El jueves está libre en el horario de atención. ¿Para qué horario te gustaría?"
```

Caso 3: Tratamiento + día general
```
Paciente: "Limpieza el miércoles"
IA: [check_availability(limpieza, miércoles)]
IA: "Para limpieza el miércoles tengo: 10:00, 11:00, 15:00"
IA: "¿Alguno te sirve?" ← CTA natural
```

**FALLBACK PARA TRATAMIENTOS NO ENCONTRADOS:**
- SI `list_services` no encuentra término → usar diccionario de sinónimos
- SI aún no encuentra → "No encuentro '[término]' específicamente. ¿Te refieres a alguno de estos? [mostrar primeros 3-4 de `list_services`]"
- NUNCA inventar tratamientos que no están en `list_services`

**REGLA DE ORO DEL FALLBACK:** Siempre ofrecer alternativas CONCRETAS, no solo decir "no hay". El paciente quiere soluciones, no problemas.
```

---

## 🧪 EJEMPLOS COMPLETOS DE CONVERSACIÓN MEJORADA

### **Ejemplo 1: Término coloquial + acción directa**
```
PACIENTE: "Quiero sacarme una muela"
IA: [Mapea "sacar muela" → "Extracción Dental"]
IA: [Valida con `list_services`("Extracción Dental")]
IA: "Para extracción dental, ¿correcto?" ← Confirmación sutil
PACIENTE: "Sí"
IA: [check_availability("Extracción Dental")] ← ACCIÓN DIRECTA
IA: "Para extracción dental tengo estos horarios disponibles:"
IA: "📅 Martes: 10:00, 14:00, 16:00"
IA: "📅 Miércoles: 11:00, 15:00"
IA: "¿Te sirve alguno de estos?" ← CTA natural
```

### **Ejemplo 2: Horario específico no disponible (fallback)**
```
PACIENTE: "Blanqueamiento el jueves a las 9:00"
IA: [check_availability("Blanqueamiento", "jueves 9:00") → NO libre]
IA: "A las 9:00 no está libre para blanqueamiento."
IA: "Pero el jueves tengo disponibles: 10:30, 14:00, 16:30"
IA: "¿Alguno de estos horarios te sirve?" ← Alternativas concretas
```

### **Ejemplo 3: Consulta vaga + CTA apropiado**
```
PACIENTE: "¿Qué hacen?"
IA: [list_services()]
IA: "Tenemos estos tratamientos principales 🦷:"
IA: "- Limpieza Dental"
IA: "- Blanqueamiento"  
IA: "- Implantes"
IA: "- Extracciones"
IA: "¿Sobre cuál te gustaría más información?" ← CTA para contexto vago
```

### **Ejemplo 4: Info específica + gate anti-alucinación**
```
PACIENTE: "¿Cómo es el tratamiento de implantes?"
IA: [get_service_details("Implante Dental")] ← GATE OBLIGATORIO
IA: [SI tool tiene info: mostrar info exacta]
IA: [SI tool no tiene: "No tengo los detalles aquí. La Dra. te explica todo en consultorio. ¿Coordinamos turno?"]
```

---

## 🔧 PLAN DE IMPLEMENTACIÓN TÉCNICA

### **Paso 1: Backup del archivo actual**
```bash
cd /home/node/.openclaw/workspace/projects/clinicforge
cp orchestrator_service/main.py orchestrator_service/main.py.backup.$(date +%Y%m%d)
```

### **Paso 2: Localizar función `build_system_prompt`**
- Archivo: `orchestrator_service/main.py`
- Línea aproximada: 1598
- Verificar contexto antes de editar

### **Paso 3: Insertar secciones en orden**
Usar las 5 secciones de código proporcionadas en este documento, insertando en:
1. **Diccionario:** Después de "REGLA DE ORO DE IDENTIDAD"
2. **Optimización WhatsApp:** Después de "POLÍTICA DE PUNTUACIÓN"
3. **Gate anti-alucinación:** Después de "SERVICIOS — REGLA CRÍTICA"
4. **CTAs naturales:** Después de "FLUJO DE AGENDAMIENTO Y ADMISIÓN"
5. **Fallback inteligente:** Después de "FORMATO CANÓNICO AL LLAMAR TOOLS"

### **Paso 4: Testing de construcción**
```python
# Test básico de que el prompt se construye
from orchestrator_service.main import build_system_prompt
prompt = build_system_prompt("Clínica Test", "10:00", "es")

# Verificar que las nuevas secciones están
assert "📚 DICCIONARIO DE SINÓNIMOS MÉDICOS" in prompt
assert "📱 OPTIMIZACIÓN PARA WHATSAPP" in prompt
assert "🛡️ GATE ABSOLUTO ANTI-ALUCINACIÓN" in prompt
assert "🎯 CTAS NATURALES Y CONTEXTUALES" in prompt
assert "🔄 ESTRATEGIA DE FALLBACK INTELIGENTE" in prompt

print("✅ Todas las nuevas secciones están presentes")
print(f"📏 Longitud del prompt: {len(prompt)} caracteres")
```

### **Paso 5: Testing con casos específicos**
Crear tests para:
1. Términos coloquiales del diccionario
2. Horarios no disponibles (fallback)
3. CTAs naturales (no forzados)
4. Gate anti-alucinación (obligatoriedad de `get_service_details`)

### **Paso 6: Deploy gradual**
1. **Staging environment** primero
2. **Monitoreo 24-48 horas** de conversaciones reales
3. **Ajustes** si se detectan problemas
4. **Producción** solo después de validación

---

## 📊 MÉTRICAS DE VALIDACIÓN POST-IMPLEMENTACIÓN

### **Diccionario de sinónimos:**
- **Métrica:** % de términos coloquiales mapeados correctamente
- **Objetivo:** >90% de términos entendidos sin repreguntar
- **Medición:** Logs de términos entrada vs términos buscados

### **Gate anti-alucinación:**
- **Métrica:** Conversaciones donde se describe tratamiento sin `get_service_details`
- **Objetivo:** 0% (cero alucinaciones)
- **Medición:** Revisión manual de muestras

### **CTAs naturales:**
- **Métrica:** Tasa de conversión consulta → turno agendado
- **Objetivo:** +15-20% mejora
- **Medición:** Comparativa pre/post implementación

### **Fallback inteligente:**
- **Métrica:** % de conversaciones con horario no disponible que terminan en agendamiento alternativo
- **Objetivo:** >70% de horarios no disponibles resultan en agendamiento alternativo
- **Medición:** Seguimiento de conversaciones con fallback

### **Optimización WhatsApp:**
- **Métrica:** Longitud promedio de mensajes
- **Objetivo:** <150 caracteres por mensaje
- **Medición:** Análisis estadístico de mensajes enviados

---

**Siguiente documento:** `03_PLAN_TESTING_VALIDACION.md` - Plan detallado de testing y validación.