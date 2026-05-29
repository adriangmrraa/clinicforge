# Spec: Slot Resolution — Agent Option Confusion (DLD-85)

## Problem

Cuando el agente ofrece 2 opciones de turno numeradas y el paciente responde con una frase que combina día de semana + número (ej: "martes dos"), el sistema confunde ese número con un número de opción.

**Ejemplo concreto:**
- Opción 1: Martes 02/06 — 10:00 hs
- Opción 2: Martes 16/06 — 15:00 hs
- Paciente: "martes dos"
- **Resultado actual (BUG):** El regex `r"(?:opci[oó]n\s*)?(\d)"` captura "2" → idx=1 (0-based) → selecciona Opción 1 (martes 02/06 10:00) — o peor, `parse_datetime("martes dos")` agarra cualquier fecha.
- **Resultado esperado:** Debería coincidir con Opción 2 (martes 16/06 15:00) porque ambas opciones son martes y "dos" se refiere al DÍA 2 de junio... O en realidad en este caso AMBAS son martes, entonces no es inequívoco. Pero si una opción es martes y otra jueves, "martes dos" debería seleccionar la opción de martes.

## Requirements

### R1: Resolución por día de semana (inequívoco)
Si el paciente dice un día de la semana (lunes, martes...) y SOLO UNA opción cae en ese día, se debe seleccionar ESA opción. NO interpretar el texto como número de opción.

**Escenarios:**
| Opciones | Paciente dice | Resultado |
|----------|--------------|-----------|
| 1️⃣ Miércoles 04/06 10:00 / 2️⃣ Martes 10/06 15:00 | "martes" | Opción 2 |
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Martes 16/06 15:00 | "martes" | Ambas son martes → preguntar cuál |
| 1️⃣ Lunes 03/06 10:00 / 2️⃣ Viernes 06/06 15:00 | "el lunes" | Opción 1 |
| 1️⃣ Lunes 03/06 10:00 / 2️⃣ Lunes 10/06 15:00 | "lunes" | Ambas son lunes → preguntar cuál |

### R2: Resolución por día de semana + número de día
Si el paciente dice día + número (ej: "martes dos", "martes 2", "martes 2 de junio"), y SOLO UNA opción cae en ese día de semana + el número de día coincide con la fecha de una opción, se selecciona ESA opción.

**Escenarios:**
| Opciones | Paciente dice | Resultado |
|----------|--------------|-----------|
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Martes 16/06 15:00 | "martes dos" | Ambas martes, día 2 = Opción 1 |
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Martes 16/06 15:00 | "martes 16" | Ambas martes, día 16 = Opción 2 |
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Jueves 05/06 15:00 | "martes dos" | Solo martes = Opción 1 (inequívoco por R1) |
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Jueves 12/06 15:00 | "martes 2" | Solo martes + día 2 = Opción 1 |

### R3: Resolución por número ordinal
"el primero", "el segundo", "la primera opción", "opción 1", "opción 2", "1", "2" → se resuelven como número de opción.

**Escenarios:**
| Opciones | Paciente dice | Resultado |
|----------|--------------|-----------|
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Jueves 12/06 15:00 | "el primero" | Opción 1 |
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Jueves 12/06 15:00 | "el segundo" | Opción 2 |
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Jueves 12/06 15:00 | "1" | Opción 1 |
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Jueves 12/06 15:00 | "2️⃣" | Opción 2 |
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Jueves 12/06 15:00 | "opción 2" | Opción 2 |

### R4: Resolución por hora
"el de las 10", "el de la mañana", "las 3 de la tarde" → se resuelven por hora del slot.

**Escenarios:**
| Opciones | Paciente dice | Resultado |
|----------|--------------|-----------|
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Jueves 12/06 15:00 | "el de las 10" | Opción 1 |
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Jueves 12/06 15:00 | "el de la tarde" | Opción 2 |
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Martes 02/06 15:00 | "el de las 3" | Opción 2 |

### R5: Prevención en LLM (system prompt)
El system prompt DEBE instruir explícitamente al LLM para que:
- SIEMPRE pase `slot_index` + `interpreted_date` cuando el paciente elige de opciones ofrecidas.
- NUNCA pase el texto del paciente como `date_time` si el paciente eligió una opción.
- Para casos ambiguos (día de semana mencionado), resuelva usando REGLA DE RESOLUCIÓN DE SLOT.

### R6: Fallback en código (defensa en profundidad)
La función de fallback en `book_appointment` DEBE:
1. Antes de aplicar regex de opción numérica, verificar si el texto contiene un día de la semana.
2. Si contiene día de la semana, intentar matchear contra las opciones por día primero.
3. Solo si el match por día falla, intentar el regex de opción numérica.
4. El regex de opción numérica NO debe capturar dígitos que forman parte de una fecha.
5. Agregar logging estructurado de cada intento de resolución.

### R7: Logging
Cada resolución de slot DEBE loguear:
- Input del paciente (raw)
- Opciones ofrecidas
- Regla que matcheó (dia_semana, dia_semana_numero, ordinal, hora, opcion_numerica, fallback_parse_datetime)
- Slot seleccionado (o "none" si falló)
- Tiempo de resolución

### R8: Casos borde
| Opciones | Paciente dice | Resultado |
|----------|--------------|-----------|
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Martes 16/06 15:00 | "el martes que viene" | Ambas martes → preguntar fecha |
| 1️⃣ Miércoles 04/06 10:00 / 2️⃣ Viernes 06/06 15:00 | "miercoles cuatro" | Día miércoles, día 4 no matchea → inequívoco por R1 (solo miércoles) → Opción 1 |
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Jueves 05/06 15:00 | "el martes a las 10" | Martes → Opción 1 + hora 10 → Opción 1 confirmada |
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Martes 02/06 15:00 | "el de las 10" | Mismo día, hora 10 → Opción 1 |
| 1️⃣ Martes 02/06 10:00 / 2️⃣ Martes 02/06 15:00 | "el de las 3" | Mismo día, hora 15 → Opción 2 |

## No Requirements

- No se modifica el schema de BD.
- No se modifica el modelo `Appointment`.
- No se modifican las tools `confirm_slot`, `check_availability`, `list_my_appointments`.
- No se agregan nuevas tools.
