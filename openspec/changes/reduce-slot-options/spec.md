# Spec — DLD-4: Reducir opciones de slot de 3 a 2

**Change ID:** `reduce-slot-options`
**Status:** Draft
**Fecha:** 2026-04-17

---

## 1. Objetivos

Reducir la cantidad de opciones de horario que `check_availability` retorna al paciente de 3 a exactamente 2. El objetivo es hacer la elección más rápida y simple para el paciente — dos opciones claras generan menor fricción de decisión que tres.

---

## 2. Alcance

### 2.1 Archivos afectados

| Archivo | Tipo de cambio |
|---------|----------------|
| `orchestrator_service/main.py` | Lógica de negocio + prompt del sistema |
| `orchestrator_service/agents/specialists.py` | Prompt del agente multi-motor |

### 2.2 NO incluido en este cambio

- Modificar la lógica de búsqueda de disponibilidad (`_get_slots_for_extra_day`, holidays, `time_preference`).
- Cambiar el comportamiento de `confirm_slot` o `book_appointment`.
- Alterar el formato de salida de la tool (estructura JSON de `options`).
- Tests de integración de calendario (fuera del scope de esta corrección puntual).

---

## 3. Requisitos

### R1 — `check_availability` DEBE retornar exactamente 2 opciones

**Estado actual:** `max_options=3` en `main.py:2527`. La función auxiliar `pick_representative_slots` usa este valor en cinco lugares del algoritmo de selección (líneas 1376, 1378, 1411, 1447, 1451–1452, 1459, 1482, 1485, 1515, 1518).

**Cambio requerido:** Cambiar el argumento en el call site de `pick_representative_slots` en `main.py:2527`:

```python
# Antes
max_options=3,

# Después
max_options=2,
```

La función `pick_representative_slots` recibe `max_options` como parámetro; su valor por defecto en la firma es `3` (`main.py:1310`). **Ese default también debe cambiar a `2`** para evitar que cualquier otro caller futuro herede el valor antiguo.

**Criterio de cumplimiento:** `len(options) <= 2` en toda respuesta de `check_availability`. Nunca 3, nunca 4.

---

### R2 — Las 2 opciones DEBEN provenir del mismo día cuando haya disponibilidad suficiente

**Estado actual:** La lógica en modo fecha específica (`search_range_days=1`) intenta tomar `min(max_options - 1, len(slots))` slots del día pedido y reserva 1 cupo para un "comodín" de otro día.

Con `max_options=3` esto era: hasta 2 del día pedido + 1 comodín.
Con `max_options=2` sin ajuste esto sería: hasta 1 del día pedido + 1 comodín — incorrecto.

**Cambio requerido:** En modo fecha específica (`search_range_days == 1`), la lógica de reparto DEBE cambiar para tomar **hasta 2 slots del mismo día** y solo usar el comodín si el día pedido tiene menos de 2 slots disponibles.

Regla explícita:
- Si el día pedido tiene >= 2 slots libres → tomar exactamente 2 del mismo día. No agregar comodín.
- Si el día pedido tiene exactamente 1 slot libre → tomar ese 1 + buscar 1 comodín en días siguientes.
- Si el día pedido tiene 0 slots → aplicar lógica existente de auto-avance (`auto_advanced`).

**Criterio de cumplimiento:** Cuando un paciente pide "el jueves" y el jueves tiene 4 horarios libres, ambas opciones mostradas deben ser del jueves.

---

### R3 — El system prompt DEBE decir "2 opciones", no "2-3 opciones"

**Estado actual:** Cinco ocurrencias en `main.py` contienen el texto "2-3" en contexto de opciones de turno:

| Línea (aprox.) | Texto actual |
|----------------|--------------|
| 1589 | `"La tool devuelve 2-3 opciones concretas de horario con sede."` |
| 2517 | `"# Seleccionar 2-3 opciones representativas (con multi-día si hace falta)"` |
| 8945 | `"Mostrar 2-3 opciones de turno."` |
| 9210 | `"La tool devuelve 2-3 opciones con emojis numerados (1️⃣ 2️⃣ 3️⃣)"` |

**Cambio requerido:** Reemplazar cada ocurrencia por "2 opciones" (o "exactamente 2 opciones" donde corresponda mayor énfasis). La mención de `3️⃣` en la línea 9210 se aborda en R5.

El comentario de código en línea 2517 (no es prompt del sistema sino un comentario Python) también debe actualizarse para mantener consistencia documental.

**Criterio de cumplimiento:** Búsqueda de `"2-3"` en `main.py` dentro de contextos de slot/turno no retorna ningún resultado.

---

### R4 — `specialists.py` DEBE decir "2 opciones", no "2-3 opciones"

**Estado actual:** Dos ocurrencias en `orchestrator_service/agents/specialists.py`:

| Línea (aprox.) | Texto actual |
|----------------|--------------|
| 279 | `"Nunca listas gigantes de horarios — ofrecé 2-3 opciones concretas."` |
| 283 | `"Devolvés 2-3 slots al paciente."` |

**Cambio requerido:** Reemplazar ambas por "2 opciones concretas" y "Devolvés 2 slots al paciente." respectivamente.

**Criterio de cumplimiento:** Búsqueda de `"2-3"` en `specialists.py` retorna cero resultados.

---

### R5 — La numeración emoji DEBE usar solo 1️⃣ 2️⃣

**Estado actual:**
- `main.py:2535`: `emoji_nums = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]` — el array incluye 3️⃣ y más.
- `main.py:9210` (system prompt): lista `(1️⃣ 2️⃣ 3️⃣)` como referencia de formato.

**Cambio requerido:**

1. Reducir el array a `["1️⃣", "2️⃣"]`. El loop `for i, opt in enumerate(options)` ya está acotado por `len(options)`, con lo cual si `max_options=2` nunca se accede al índice 2. Sin embargo, dejar 3️⃣ en el array es confuso y permitiría que un bug futuro lo use; truncarlo es la defensa correcta.

2. Actualizar el system prompt (línea 9210) para referenciar solo `(1️⃣ 2️⃣)`.

3. Los ejemplos en líneas 9234–9235 mencionan `1️⃣` y `2️⃣` solamente; **no requieren cambio**.

**Criterio de cumplimiento:** El array `emoji_nums` contiene exactamente 2 elementos. El system prompt no menciona `3️⃣` en contexto de opciones de slot.

---

## 4. Escenarios

### Escenario 1 — Día con disponibilidad amplia (caso nominal)

```
Dado que el tenant tiene horarios disponibles martes y miércoles
Y el paciente pide "quiero el martes"
Cuando el agente llama check_availability con search_range_days=1
Entonces la respuesta contiene exactamente 2 opciones
Y ambas opciones son del martes
Y el mensaje muestra 1️⃣ y 2️⃣ solamente
```

### Escenario 2 — Día con un solo slot libre

```
Dado que el martes solo tiene 1 slot libre (10:00)
Y el paciente pide "el martes"
Cuando el agente llama check_availability con search_range_days=1
Entonces la respuesta contiene exactamente 2 opciones
Y la opción 1️⃣ es del martes (10:00)
Y la opción 2️⃣ es del siguiente día disponible (comodín)
```

### Escenario 3 — Rango amplio (mitad de mes)

```
Dado que el paciente pide "cualquier día de mayo"
Cuando el agente llama check_availability con search_range_days > 1
Entonces la respuesta contiene exactamente 2 opciones
Y las opciones provienen de días diferentes dentro del rango (distribución espaciada)
```

### Escenario 4 — Sin disponibilidad en el día pedido

```
Dado que el miércoles está cerrado (feriado o sin horarios)
Y el paciente pide "el miércoles"
Cuando el agente llama check_availability
Entonces el sistema auto-avanza al siguiente día hábil
Y retorna exactamente 2 opciones de ese día
Y el mensaje incluye el aviso de auto-avance existente
```

### Escenario 5 — Consistencia del prompt en multi-motor

```
Dado que el tenant tiene ai_engine_mode = 'multi'
Y el paciente pide disponibilidad
Cuando el BookingAgent llama check_availability
Entonces el prompt de specialists.py no menciona "2-3" en ninguna instrucción
Y la respuesta al paciente contiene exactamente 2 opciones con 1️⃣ 2️⃣
```

---

## 5. Criterios de aceptación

| ID | Criterio | Verificación |
|----|----------|--------------|
| AC-1 | `check_availability` nunca retorna más de 2 opciones | `assert len(options) <= 2` en test unitario de `pick_representative_slots` |
| AC-2 | Con >= 2 slots en el día pedido, ambas opciones son del mismo día | Test: día con 5 slots → options[0].date == options[1].date |
| AC-3 | Con 1 slot en el día pedido, la segunda opción es de otro día | Test: día con 1 slot → options[0].date != options[1].date |
| AC-4 | El array `emoji_nums` tiene exactamente 2 elementos | `assert len(emoji_nums) == 2` |
| AC-5 | No existe la cadena `"2-3"` en contextos de slot en `main.py` | `grep "2-3" main.py` retorna solo ocurrencias NO relacionadas a turnos (ej: "2-3 líneas por burbuja" en instrucción de longitud de mensaje — esa NO se toca) |
| AC-6 | No existe la cadena `"2-3"` en `specialists.py` | `grep "2-3" specialists.py` retorna 0 resultados |
| AC-7 | El system prompt no lista `3️⃣` como opción de slot | Búsqueda de `"3️⃣"` en el bloque de instrucciones de `check_availability` en `main.py` retorna 0 |
| AC-8 | El default de `max_options` en la firma de `pick_representative_slots` es 2 | Inspección directa de `main.py:1310` |

---

## 6. Notas de implementación

### 6.1 Ocurrencia "2-3 líneas por burbuja" — NO tocar

`main.py:8893` contiene `"Mensajes CORTOS y NATURALES. Máximo 2-3 líneas por burbuja."` — esta ocurrencia se refiere a longitud de mensajes, no a cantidad de opciones de slot. **No debe modificarse.**

### 6.2 Occurrencias en `nova_daily_analysis.py` y `digital_records_service.py` — fuera de scope

Los archivos `services/nova_daily_analysis.py` y `services/digital_records_service.py` también contienen "2-3" pero en contextos de resúmenes clínicos y análisis de Nova, completamente desvinculados de la lógica de slots. No se tocan.

### 6.3 Orden de implementación recomendado

1. Cambiar `max_options` default en la firma (`main.py:1310`) y en el call site (`main.py:2527`).
2. Ajustar la lógica de reparto en modo fecha específica (R2 — líneas 1376–1379).
3. Reducir `emoji_nums` a 2 elementos (`main.py:2535`).
4. Actualizar las 4 ocurrencias de "2-3" en `main.py` que referencian slots.
5. Actualizar las 2 ocurrencias en `specialists.py`.
6. Escribir/actualizar tests unitarios de `pick_representative_slots`.
