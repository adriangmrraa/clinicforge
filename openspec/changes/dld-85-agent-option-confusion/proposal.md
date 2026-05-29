# Proposal: DLD-85 — Agent Option Confusion (Day number vs Option number)

## Intent

El agente confunde el día de la semana + número de día (ej: "martes dos", "el martes 2") con el número de opción (1 o 2) cuando el paciente elige entre turnos ofrecidos. Esto puede causar que se agende el turno INCORRECTO o se genere doble booking. Es urgente porque está en producción.

## Scope

### In Scope
- **[CORRECTIVO CORE]** Revisar y fortalecer la prioridad del parámetro `slot_index` en el system prompt del agente — el LLM DEBE pasar `slot_index=N` y `interpreted_date=YYYY-MM-DD` en lugar de texto libre.
- **[CORRECTIVO FALLBACK]** Arreglar la lógica de fallback en `book_appointment` (línea 3241) para que el regex `r"(?:opci[oó]n\s*)?(\d)"` NO capture dígitos que forman parte de un día del mes (ej: "martes 2", "el 15", "dos") y solo capture cuando es claramente un número de opción.
- **[CORRECTIVO SYSTEM PROMPT]** Agregar regla explícita en el system prompt para resolver "día de semana + número" vs "número de opción".
- **[ESCENARIOS]** Agregar logging en el slot matching para identificar falsos positivos.
- **[TESTING]** Validar con los escenarios del ticket.

### Out of Scope
- Refactor del sistema de `parse_datetime` (es demasiado grande y riesgoso tocarlo ahora).
- Cambios en `confirm_slot` (tiene la misma arquitectura, se beneficia indirectamente de la mejora del prompt).
- Migración de Redis a otro store (no es el problema acá).

## Approach

**Dos líneas de defensa:**

1. **Prevención (LLM/Prompt)**: Reforzar el system prompt para que el LLM SIEMPRE use `slot_index` + `interpreted_date` cuando el paciente elige de opciones ofrecidas. El prompt actual ya lo dice, pero los casos ambiguos como "martes dos" no están cubiertos explícitamente.

2. **Detección (Fallback code)**: En el fallback de `book_appointment`, mejorar el regex para discriminar cuándo un dígito es realmente un número de opción vs parte de una fecha:
   - Si el texto contiene un día de la semana (lunes, martes...) seguido de un número → es DÍA, no opción.
   - Si el texto contiene mes + número → es FECHA, no opción.
   - Si el texto contiene "el primero"/"el segundo"/"opción X" → es OPCIÓN.
   - Si el texto es solo un número ("1", "2") sin contexto de fecha → es OPCIÓN.
   - Agregar una función `_match_option_number(text, offered_slots)` con estas reglas.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `orchestrator_service/main.py:9900-10100` | Modified | System prompt — reglas de resolución de slot más explícitas |
| `orchestrator_service/main.py:3240-3264` | Modified | Fallback regex matching en `book_appointment` |
| `orchestrator_service/main.py:3017` | Modified | Logging en slot matching |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM sigue sin pasar slot_index correctamente | Med | La defensa en código (fallback mejorado) atrapa estos casos |
| Fallback nuevo introduce falsos negativos | Bajo | Test con los 4+ escenarios del ticket antes de deploy |
| Regresión en flujo normal (paciente dice "1") | Bajo | El regex actual para "1"/"2" solos se mantiene igual |

## Rollback Plan

Revertir el commit en `main.py`. El cambio es pequeño y localizado.

## Dependencies

Ninguna.

## Success Criteria

- [ ] "martes dos" → se resuelve al slot del martes que coincide (día, no número de opción)
- [ ] "martes 2 de junio" → se resuelve al slot del día 2
- [ ] "el primero" → se resuelve a slot_index=1
- [ ] "1" → se resuelve a slot_index=1 (sin cambios)
- [ ] "2️⃣" → se resuelve a slot_index=2 (sin cambios)
- [ ] "el de las 10" → se resuelve al slot con hora 10:00
- [ ] Logging agregado captura cada resolución de slot con sus parámetros
- [ ] Sin regresión en flujo normal (confirmación de un solo número sigue funcionando)
