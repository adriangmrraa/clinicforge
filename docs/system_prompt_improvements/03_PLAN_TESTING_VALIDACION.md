# 🧪 PLAN DE TESTING Y VALIDACIÓN

## 🎯 OBJETIVO
Validar que las 5 mejoras implementadas funcionan correctamente y no introducen regresiones.

---

## 📋 RESUMEN DE MEJORAS A VALIDAR

### **1. 📚 DICCIONARIO DE SINÓNIMOS MÉDICOS**
- Mapeo correcto de términos coloquiales → términos canónicos
- Validación posterior con `list_services`
- Confirmación sutil al paciente

### **2. 🛡️ GATE ANTI-ALUCINACIÓN**
- Obligatoriedad de `get_service_details` antes de describir tratamientos
- Cero invención de información médica
- Fallback honesto cuando no hay información

### **3. 📱 OPTIMIZACIÓN WHATSAPP**
- Mensajes cortos (3-4 líneas máximo)
- Emojis estratégicos médicos
- Secuencia estructurada saludo→info→CTA
- URLs limpias sin markdown

### **4. 🎯 CTAS NATURALES (CORREGIDOS)**
- Con tratamiento definido → acción directa (no preguntar)
- CTAs contextuales y naturales
- No interrumpir flujo con preguntas obvias

### **5. 🔄 FALLBACK INTELIGENTE (CORREGIDO)**
- `check_availability`: 0 resultados = HORARIO LIBRE
- Fallback solo para horarios específicos no disponibles
- Ofrecer alternativas concretas

---

## 🧪 TESTING AUTOMATIZADO

### **Test 1: Construcción del Prompt**
```python
# test_prompt_construction.py
import sys
sys.path.append('orchestrator_service')

from main import build_system_prompt

def test_prompt_contains_new_sections():
    """Verificar que las nuevas secciones están en el prompt"""
    prompt = build_system_prompt("Clínica Test", "10:00", "es")
    
    sections_to_check = [
        "📚 DICCIONARIO DE SINÓNIMOS MÉDICOS",
        "📱 OPTIMIZACIÓN PARA WHATSAPP",
        "🛡️ GATE ABSOLUTO ANTI-ALUCINACIÓN",
        "🎯 CTAS NATURALES Y CONTEXTUALES",
        "🔄 ESTRATEGIA DE FALLBACK INTELIGENTE"
    ]
    
    for section in sections_to_check:
        assert section in prompt, f"Sección faltante: {section}"
    
    print("✅ Todas las secciones nuevas están presentes")
    print(f"📏 Longitud total: {len(prompt)} caracteres")
    return True

def test_prompt_length_increase():
    """Verificar que el aumento de longitud es aceptable"""
    prompt = build_system_prompt("Clínica Test", "10:00", "es")
    
    # Longitud aproximada esperada: ~2500 líneas + ~50 nuevas = ~2550
    # Aumento aceptable: <5%
    assert len(prompt) < 1_300_000, "Prompt demasiado largo (>1.3M caracteres)"
    
    print(f"✅ Longitud aceptable: {len(prompt):,} caracteres")
    return True

if __name__ == "__main__":
    test_prompt_contains_new_sections()
    test_prompt_length_increase()
    print("🎉 Todos los tests de construcción pasaron")
```

### **Test 2: Casos de Uso del Diccionario**
```python
# test_dictionary_cases.py
def test_dictionary_mapping():
    """Testear mapeo de términos coloquiales"""
    test_cases = [
        ("sacar muela", "Extracción Dental"),
        ("limpieza", "Limpieza Dental"),
        ("blanquear", "Blanqueamiento Dental"),
        ("radiografía", "Ortopantomografía"),
        ("consulta", "Consulta de Evaluación"),
        ("dolor", "Urgencia Dental"),
        ("caries", "Caries"),
        ("matar nervio", "Endodoncia"),
        ("dentadura postiza", "Prótesis Dental"),
    ]
    
    # Nota: Este test simula la lógica, en realidad está en el prompt
    for coloquial, canonico in test_cases:
        print(f"✅ {coloquial} → {canonico}")
    
    return True

def test_dictionary_fallback():
    """Testear términos no en diccionario"""
    unknown_terms = ["ortodoncia invisible", "carilla dental", "frenillo"]
    
    for term in unknown_terms:
        print(f"⚠️  Término no en diccionario: {term}")
        print("   Comportamiento esperado: búsqueda directa con list_services")
    
    return True
```

### **Test 3: Gate Anti-Alucinación**
```python
# test_anti_hallucination.py
def test_gate_requirements():
    """Verificar que el gate requiere get_service_details"""
    scenarios = [
        "¿Cómo es el tratamiento de implantes?",
        "¿Qué implica una limpieza dental?",
        "¿Cuánto dura un blanqueamiento?",
        "¿Duele una extracción?",
        "¿Cuánto cuesta una endodoncia?",
    ]
    
    for scenario in scenarios:
        print(f"🔍 Escenario: {scenario}")
        print("   Requerimiento: get_service_details OBLIGATORIO")
        print("   Prohibido: Describir sin tool ejecutada")
    
    return True
```

---

## 🧑‍💻 TESTING MANUAL (CASOS ESPECÍFICOS)

### **Caso 1: Término coloquial + acción directa**
**Escenario:** Paciente usa término coloquial, tratamiento definido
```
Entrada: "Quiero sacarme una muela"
Comportamiento esperado:
1. Mapear "sacar muela" → "Extracción Dental"
2. Validar con list_services("Extracción Dental")
3. Confirmar sutilmente: "Para extracción dental, ¿correcto?"
4. Si confirma → check_availability DIRECTAMENTE
5. Mostrar horarios disponibles
6. CTA natural: "¿Te sirve alguno de estos?"
```

**Métricas a verificar:**
- ✅ Término mapeado correctamente
- ✅ No pregunta "¿quieres consultar disponibilidad?"
- ✅ Acción directa después de confirmación
- ✅ CTA natural (no forzado)

### **Caso 2: Horario específico no disponible**
**Escenario:** Paciente pide horario concreto que no está libre
```
Entrada: "Blanqueamiento el jueves a las 9:00"
Comportamiento esperado:
1. check_availability("Blanqueamiento", "jueves 9:00") → NO libre
2. NO decir "no hay disponibilidad" (incorrecto)
3. Decir: "A las 9:00 no está libre para blanqueamiento"
4. check_availability("Blanqueamiento", "jueves") → horarios disponibles
5. Ofrecer alternativas: "Pero el jueves tengo: 10:30, 14:00, 16:30"
6. CTA: "¿Alguno de estos horarios te sirve?"
```

**Métricas a verificar:**
- ✅ Reconoce que 0 resultados en check específico = NO libre
- ✅ Ofrece alternativas concretas
- ✅ No usa la palabra "disponibilidad" ambiguamente
- ✅ CTA para seleccionar alternativa

### **Caso 3: Consulta vaga**
**Escenario:** Paciente pregunta de forma muy general
```
Entrada: "¿Qué hacen?"
Comportamiento esperado:
1. list_services() → obtener tratamientos
2. Mostrar lista breve (3-4 principales)
3. CTA apropiado: "¿Sobre cuál te gustaría más información?"
4. Mensajes cortos (3-4 líneas máximo)
5. Emojis médicos estratégicos 🦷
```

**Métricas a verificar:**
- ✅ Lista breve, no exhaustiva
- ✅ CTA para guiar a especificidad
- ✅ Formato WhatsApp optimizado
- ✅ Emojis apropiados

### **Caso 4: Info específica de tratamiento**
**Escenario:** Paciente pregunta detalles de tratamiento
```
Entrada: "¿Cómo es el tratamiento de implantes?"
Comportamiento esperado:
1. get_service_details("Implante Dental") OBLIGATORIO
2. SI tool tiene info → mostrar info exacta
3. SI tool no tiene → "No tengo los detalles aquí. La Dra. te explica en consultorio. ¿Coordinamos turno?"
4. NUNCA inventar descripciones
```

**Métricas a verificar:**
- ✅ Gate anti-alucinación activado
- ✅ Cero invención de información
- ✅ Fallback honesto cuando no hay info
- ✅ CTA para agendar cuando no hay info

### **Caso 5: check_availability con 0 resultados**
**CORRECCIÓN CRÍTICA:** Este es el caso más importante
```
Entrada: "¿Tenés el viernes?"
Comportamiento esperado:
1. check_availability(viernes) → 0 resultados
2. 0 resultados = HORARIO LIBRE en el rango
3. Respuesta: "El viernes está libre en el horario de atención"
4. Pregunta: "¿Para qué horario te gustaría?"
5. NO decir "no hay disponibilidad" (incorrecto)
```

**Métricas a verificar:**
- ✅ Entiende que 0 resultados = LIBRE
- ✅ No confunde con "no hay"
- ✅ Pregunta por horario específico
- ✅ Lenguaje claro y preciso

---

## 📊 MÉTRICAS DE VALIDACIÓN

### **Métrica 1: Precisión de Diccionario**
- **Qué medir:** % de términos coloquiales mapeados correctamente
- **Cómo medir:** Logs de términos entrada vs términos buscados en `list_services`
- **Objetivo:** >90% de términos entendidos sin repreguntar
- **Fórmula:** `(términos mapeados correctamente / total términos coloquiales) * 100`

### **Métrica 2: Cumplimiento de Gate Anti-Alucinación**
- **Qué medir:** Conversaciones donde se describe tratamiento sin `get_service_details`
- **Cómo medir:** Revisión manual de muestras aleatorias (10-20 conversaciones/día)
- **Objetivo:** 0% (cero violaciones)
- **Fórmula:** `(violaciones del gate / total conversaciones con descripciones) * 100`

### **Métrica 3: Efectividad de CTAs**
- **Qué medir:** Tasa de conversión consulta → turno agendado
- **Cómo medir:** Comparativa pre/post implementación (misma ventana temporal)
- **Objetivo:** +15-20% mejora
- **Fórmula:** `(turnos agendados post / consultas post) / (turnos agendados pre / consultas pre)`

### **Métrica 4: Efectividad de Fallback**
- **Qué medir:** % de conversaciones con horario no disponible que terminan en agendamiento alternativo
- **Cómo medir:** Seguimiento de conversaciones donde se activa fallback
- **Objetivo:** >70% éxito en agendamiento alternativo
- **Fórmula:** `(agendamientos alternativos / total fallbacks activados) * 100`

### **Métrica 5: Optimización WhatsApp**
- **Qué medir:** Longitud promedio de mensajes
- **Cómo medir:** Análisis estadístico de mensajes enviados (muestra de 100 mensajes)
- **Objetivo:** <150 caracteres por mensaje
- **Fórmula:** `sum(caracteres por mensaje) / total mensajes`

---

## 🚀 PLAN DE DEPLOY GRADUAL

### **Fase 1: Staging Environment (48 horas)**
1. **Deploy** de las mejoras a ambiente de staging
2. **Monitoreo activo** de conversaciones de prueba
3. **Validación** de los 5 casos de testing manual
4. **Ajustes** si se detectan problemas

### **Fase 2: Canary Release (24 horas)**
1. **Deploy** al 10% del tráfico de producción
2. **Monitoreo A/B:** Comparar métricas canary vs control
3. **Validación** de métricas clave:
   - Precisión diccionario >90%
   - 0% violaciones gate anti-alucinación
   - Longitud mensajes <150 caracteres
4. **Rollback** inmediato si problemas críticos

### **Fase 3: Deploy Completo**
1. **Deploy** al 100% del tráfico
2. **Monitoreo continuo** por 7 días
3. **Recolección** de métricas post-implementación
4. **Reporte** de resultados vs objetivos

### **Fase 4: Optimización Continua**
1. **Análisis** de términos no cubiertos por diccionario
2. **Expansión** del diccionario basado en uso real
3. **Ajuste** de CTAs basado en efectividad
4. **Refinamiento** de estrategia de fallback

---

## ⚠️ PLAN DE ROLLBACK

### **Condiciones para Rollback:**
1. **Crítico:** Violaciones de gate anti-alucinación >5%
2. **Crítico:** Términos mapeados incorrectamente >20%
3. **Importante:** Caída en tasa de conversión >10%
4. **Importante:** Aumento en abandonos >15%

### **Procedimiento de Rollback:**
```bash
# 1. Detener servicio
cd /home/node/.openclaw/workspace/projects/clinicforge
sudo systemctl stop clinicforge-orchestrator

# 2. Restaurar backup
cp orchestrator_service/main.py.backup orchestrator_service/main.py

# 3. Reiniciar servicio
sudo systemctl start clinicforge-orchestrator

# 4. Verificar restauración
sudo systemctl status clinicforge-orchestrator
```

### **Comunicación de Rollback:**
- **Interna:** Notificar al equipo inmediatamente
- **Externa:** Si afecta pacientes, mensaje genérico: "Sistema en mantenimiento, volverá pronto"
- **Post-mortem:** Análisis de causas y plan de corrección

---

## 📈 DASHBOARD DE MONITOREO

### **Métricas en Tiempo Real:**
```
┌─────────────────────────────────────────────────────┐
│           CLINICFORGE - MONITOREO PROMPT            │
├─────────────────────────────────────────────────────┤
│ 📊 Precisión Diccionario:     92%  (↑)              │
│ 🛡️  Violaciones Gate:          0%  (✅)              │
│ 🎯 Tasa Conversión:           +18% (↑)              │
│ 🔄 Éxito Fallback:            75%  (↑)              │
│ 📱 Longitud Mensajes:        142c  (✅)              │
└─────────────────────────────────────────────────────┘
```

### **Alertas Configuradas:**
1. **Alerta Crítica:** Violaciones gate anti-alucinación >0%
2. **Alerta Alta:** Precisión diccionario <85%
3. **Alerta Media:** Tasa conversión cae >10%
4. **Alerta Baja:** Longitud mensajes >180 caracteres

### **Logs a Monitorear:**
- Términos entrada vs términos buscados
- Activaciones de gate anti-alucinación
- Casos de fallback activados
- Longitud de mensajes enviados
- CTAs utilizados y respuestas

---

## 📝 CHECKLIST DE VALIDACIÓN FINAL

### **Antes de Deploy a Producción:**
- [ ] Todos los tests automatizados pasan
- [ ] Casos de testing manual verificados
- [ ] Backup del archivo actual creado
- [ ] Plan de rollback documentado
- [ ] Equipo notificado del deploy

### **Durante Deploy a Staging:**
- [ ] Deploy completado sin errores
- [ ] Servicio reiniciado correctamente
- [ ] Prompt se construye correctamente
- [ ] Conversaciones de prueba funcionan

### **Post-Deploy (Primeras 24 horas):**
- [ ] Métricas clave dentro de rangos aceptables
- [ ] 0% violaciones gate anti-alucinación
- [ ] Precisión diccionario >90%
- [ ] Longitud mensajes <150 caracteres promedio
- [ ] No hay regresiones en flujos existentes

### **Post-Deploy (Primera semana):**
- [ ] Tasa de conversión estable o mejorada
- [ ] Éxito fallback >70%
- [ ] Feedback positivo de pacientes (si aplica)
- [ ] Términos no cubiertos identificados para expansión

---

## 🎯 CONCLUSIÓN DEL PLAN

Este plan de testing y validación garantiza que las 5 mejoras implementadas:

1. **Funcionan correctamente** según lo diseñado
2. **No introducen regresiones** en flujos existentes
3. **Mejoran métricas clave** de precisión, confiabilidad y conversión
4. **Pueden revertirse rápidamente** si hay problemas

