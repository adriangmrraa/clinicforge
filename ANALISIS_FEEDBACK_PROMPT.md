# Análisis Profundo del Feedback — Dra. Laura Delgado (Mayo 2026)

## Objetivo

Vas a realizar un análisis EXTENSO y METÓDICO de cada uno de los 13 casos del documento de feedback. Vas a revisar el código REAL del proyecto ClinicForge para validar cada caso, no asumir nada. Tu objetivo es dar la respuesta más precisa posible.

## Archivo de Feedback

**Ubicación:** `C:\Users\Asus\Documents\estabilizacion\Laura Delgado\Feedback - Dra. Delgado - Mayo.md`

**Contenido del archivo:**
```
1. Presentación del agente: no decir "asistente virtual"
2. Paciente con dolor: contener antes de agendar
3. Consulta de precio: responder precio antes de pedir datos
4. Fraseo: "te ayudo a coordinar" vs "te busco el turno"
5. Obras sociales: confirmar específicamente por nombre
6. Coseguro: no afirmar monto fijo
7. Implantes: dar contexto breve sin abrumar
8. No confirmar turno si el paciente no eligió opción
9. Mensaje post-turno: desglosar en pasos
10. Quitar "Entiendo" antes de informar precio
11. ATM/dolor de mandíbula: contención sin invalidar + sin términos clínicos
12. Obras sociales: flujo completo con tres caminos
13. ATM = consulta general (regla de negocio)
```

## Ruta del Proyecto

**Carpeta raíz:** `C:\Users\Asus\Documents\estabilizacion\Laura Delgado\clinicforge`

**Archivos principales a revisar:**

| Archivo | Descripción |
|---------|-------------|
| `orchestrator_service/main.py` | 12,000+ líneas. Contains `build_system_prompt()`, flujos F1-F8, post-booking 5 bloques, reglas de precios, obras sociales, coseguro |
| `orchestrator_service/services/buffer_task.py` | Procesamiento de mensajes, system prompt dinámico por tenant |
| `orchestrator_service/agents/specialists.py` | Agentes especializados (triage, derivación, cobros) |
| `orchestrator_service/admin_routes.py` | Endpoints de administración, configuración de tenants |
| `orchestrator_service/services/nova_prompt.py` | Nova system prompt builder |
| `orchestrator_service/services/nova_tools.py` | Tools disponibles para el agente |

## Instrucciones de Análisis

Para CADA caso, debes:

### Paso 1: Buscar en el Código
- Usar `grep` o `read` para encontrar dónde vive esa lógica
- Buscar en los archivos mencionados arriba
- NUNCA asumir, SIEMPRE verificar con código real

### Paso 2: Documentar lo que Encontrás
- **Qué hay actualmente:** Copiar la sección relevante del código
- **Dónde vive:** Ruta exacta y líneas (ej: main.py:9149-9150)
- **Estado:** Una de estas opciones:
  - ✅ YA IMPLEMENTADO (con código que lo Prueba)
  - 🟡 PARCIALMENTE IMPLEMENTADO (falta alguna parte)
  - ❌ NO IMPLEMENTADO (no existe esa lógica)
  - ⚠️ PROBLEMA DE LÓGICA (existe pero no funciona bien)

### Paso 3: Clasificar la Complejidad
| Tipo | Descripción |
|------|-------------|
| 🟢 BAJA | Solo cambio de texto en prompt |
| 🟡 MEDIA | Cambiar lógica de flujo o agregar regla |
| 🔴 ALTA | Cambio arquitectural (estado, multi-paso) |

### Paso 4: Dar lauby de Corrección Sugerida
- Cómo arreglarlo
- Dónde hacer el cambio
- Si necesita más de un archivo, especificar cuáles

## Preguntas Clave a Responder para Cada Caso

1. **¿Existe esta lógica en el código?** (evidencia: código encontrado)
2. **Si existe, funciona correctamente?** (o hay un bug?)
3. **Si no existe, dónde debería vivir?**
4. **¿Qué tipo de cambio requiere?**
5. **¿Hay algo en el feedback que contradiga el código?**

## Formato de Respuesta

Para cada caso, usar este formato:

```
### CASO XX: [Título del caso]

**📍 Dónde Vive:** [línea específica de código]
**📍 Código Actual:**
```python
[código relevante copiado]
```

**✅ Estado:** [YA IMPLEMENTADO / PARCIAL / NO IMPLEMENTADO / PROBLEMA]

**🔧 Tipo de Fix:** [BAJA / MEDIA / ALTA]

**🔧 Cómo Arreglarlo:**
[descripción específica]
```

## IMPORTANTE: Reglas de Trabajo

1. **NUNCA asumir** — siempre buscar en el código real
2. **Si no encontrás algo**, no decir "no existe" — decir "no encontré evidencia"
3. **Si encontrás algo pero no funciona**, explicar el bug con precisión
4. **Usar información de memoria** solo como补充, nunca como fuente principal
5. **Contrastá tu análisis** con el análisis previo (si se lo proporcionás)

## Contexto Adicional (del análisis previo)

El análisis previo clasificó los casos así:

| Caso | Clasificación Previa |
|------|---------------------|
| 01 | BAJA - cambio de texto |
| 02 | YA RESUELTO |
| 03 | MEDIA - lógica de flujo |
| 04 | BAJA - texto |
| 05 | MEDIA-ALTA - DB + lógica |
| 06 | YA RESUELTO |
| 07 | MEDIA - prompt limits |
| 08 | MEDIA-ALTA - lógica flow |
| 09 | ALTA - Arquitectura |
| 10 | BAJA - texto |
| 11 | MEDIA - prompt + detección |
| 12 | ALTA - Flow completo |
| 13 | MEDIA - DB + pricing |

**Tu trabajo es validar o corregir estas clasificaciones basándote en el código REAL.**

## output Esperado

Al final, vas a entregar:

1. **Tabla resumen** con el estado real de cada caso
2. **Análisis detallado** de cada uno de los 13 casos con código
3. **Clasificación corregida** de complejidad
4. **Steps de corrección sugeridos** para cada caso

¡Mucha suerte! Este trabajo es importante para la Dra. Laura y su clínica.