# Exploration: Bug B1 — Tratamiento previo fallido asume historial clínico

**Change**: `bug-b1-tratamiento-previo-fallido`
**Date**: 2026-05-16
**Source**: Pruebas Bot Paula 14-15 Mayo 2026 (Prueba 1)

---

## 1. Síntoma

Cuando un paciente dice "me hice implantes y me fue mal" (sin especificar dónde), el bot Paula responde:

> "Entiendo, parece que ya tenés un historial con la clínica. Estamos actualizando los registros, así que te voy a pasar con el equipo para que puedan revisar tu caso y ponerte al día."

**Problema**: El bot asume que el tratamiento previo fue en la clínica cuando el paciente nunca dijo eso. En la prueba real, el paciente tuvo que aclarar "no, no me entendiste, fue en otro lado."

---

## 2. Análisis de código

### 2.1 Sección responsable — `main.py` líneas 9464-9471

```
## DETECCIÓN DE PACIENTE EXISTENTE SIN DATOS EN SISTEMA (MIGRACIÓN)
La clínica está migrando a esta plataforma. Muchos pacientes YA se atienden con la doctora pero NO figuran cargados en el sistema...
SEÑALES de paciente existente: menciona turno previo, dice "ya me atiendo", "tengo un turno pendiente",
"tenía turno para cirugía", "ya me hicieron una consulta", "la doctora me dijo",
cancela/reprograma algo que no figura, habla con familiaridad sobre tratamientos en curso.
CUANDO DETECTES ESTO:
1. NO intentes agendar un turno nuevo.
2. Respondé: "Entiendo, parece que ya tenés un historial con la clínica..."
3. Llamá derivhumano con motivo: "Paciente existente no migrado..."
```

### 2.2 Trigger problemático

La señal `"menciona turno previo"` es demasiado amplia. Un paciente que dice "me hice implantes y me fue mal" está mencionando un tratamiento previo, pero NO necesariamente en esta clínica.

El trigger `"habla con familiaridad sobre tratamientos en curso"` también es ambiguo — un paciente puede hablar con familiaridad sobre su propia experiencia dental sin ser paciente de la Dra. Delgado.

### 2.3 Conflicto con F1 (Mala experiencia previa) — líneas 9514-9520

```
=== F1: MALA EXPERIENCIA PREVIA ===
TRIGGER: "no me fue bien", "mala experiencia", "me hicieron mal", "fui a otro y...", "me arruinaron", "no confío"
```

El F1 ya existe y tiene la respuesta correcta para estos casos. El problema es que la sección de **MIGRACIÓN (línea 9464) aparece ANTES que F1 (línea 9514)** en el prompt, y sus triggers son tan amplios que interceptan casos que deberían ir a F1.

### 2.4 Prohibiciones existentes (línea 9476)

```
3. PROHIBIDO escalar a humano (derivhumano) por: miedo, mala experiencia, precio, obra social desconocida, frustración.
```

Ya existe una prohibición de NO escalar por mala experiencia. Pero la MIGRACIÓN hace exactamente eso (derivhumano) cuando detecta falsamente un "paciente existente".

### 2.5 Reglas de escalación (líneas 9655-9656)

```
• Mala experiencia previa con otro profesional → usar FLUJO F1
```

Ya existe la regla que dice que mala experiencia con OTRO profesional va a F1. El problema es que la MIGRACIÓN se ejecuta antes y la bypassa.

---

## 3. Orden de los eventos en el prompt

El system prompt se construye en este orden (líneas 8928-10118):

```
1. IDENTIDAD Y TONO          (9441-9462)
2. DETECCIÓN MIGRACIÓN       (9464-9471) ← INTERCEPTA el trigger
3. PROHIBICIONES             (9473-9495)
4. INFORMACIÓN CONSULTORIO   (9500-9506)
5. FLUJOS EMOCIONALES F1-F9  (9512-9598) ← DEBERÍA llegar acá
6. REGLAS CORE               (9621-9624)
...
```

La DETECCIÓN DE MIGRACIÓN está en la posición #2, antes que los flujos emocionales. Cuando el LLM evalúa el prompt secuencialmente, la sección de migración "atrapa" el caso antes de que llegue a F1.

---

## 4. Respuesta modelo definida por Laura (del documento de pruebas)

```
"Entiendo, lamento que hayas tenido una mala experiencia previa. En estos casos
lo mejor es evaluar bien qué ocurrió y qué opciones reales hay antes de avanzar.
Si tenés estudios previos, podés traerlos a la consulta.
¿Querés que coordinemos una evaluación?"
```

Características de esta respuesta:
- NO asume dónde fue el tratamiento → neutralidad
- Valida la emoción ("lamento que hayas tenido...")
- Ofrece solución ("evaluar qué opciones hay")
- CTA a evaluación (no a "turno")

---

## 5. Regla propuesta (del documento de pruebas)

```
Cuando un paciente menciona un tratamiento previo fallido, no asumir que fue
en la clínica. Responder con empatía neutral y derivar a evaluación.
```

---

## 6. Resumen de cambios necesarios

| # | Cambio | Tipo | Ubicación |
|---|--------|------|-----------|
| 1 | Acotar triggers de MIGRACIÓN: "menciona turno previo" debe excluir casos donde el paciente habla de tratamiento en otro lugar | Modificar texto prompt | `main.py` ~línea 9466 |
| 2 | Agregar regla explícita de neutralidad para tratamiento previo fallido | Nuevo texto prompt | `main.py` ~línea 9468 (entre migración y prohibiciones) |
| 3 | Agregar la respuesta modelo de Laura como referencia | Nuevo texto prompt | `main.py` junto a la nueva regla |

---

## 7. Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `orchestrator_service/main.py` | Modificaciones de texto en `build_system_prompt()` — solo cambios en el string del prompt. Sin cambios de lógica. |

**Riesgo**: Bajo. Es un cambio de texto en el prompt. Rollback: revertir el texto.
