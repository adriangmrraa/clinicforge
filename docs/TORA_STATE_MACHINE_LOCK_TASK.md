# TORA — Booking State Machine Lock (tarea pendiente)

> **Estado:** análisis hecho, sin implementar.
> **Prioridad:** 🔴 crítica — afecta conversión real de bookings.
> **Origen:** conversación de prueba con "Juan Román Riquelme" (07/04/2026), donde TORA entró en loop tras `Agéndame el del 12 de mayo` y confirmó la fecha invertida (`Sábado 05/12`).

---

## Síntoma observable

Cuando un paciente elige un slot ya propuesto por TORA (ej: "El 12/05 me queda bien 10hs"), el agente:

1. **Vuelve a llamar `check_availability`** en lugar de avanzar a `confirm_slot` / `book_appointment`.
2. Re-muestra una grilla de horarios diferente a la anterior.
3. El paciente queda atrapado en un loop hasta que repite varias veces su elección.
4. Cuando finalmente bookea, la fecha puede haber mutado (el LLM mezcla los slots de los distintos `check_availability` y elige uno alucinado).

Mismo patrón se observa en:
- "Tengo algún turno ya agendado?" → responde "Sin turnos" justo después de haber confirmado uno.
- Doble respuesta de slots con texto distinto en ventana de 30s.

---

## Hipótesis principal

**El system prompt no impone reglas duras de transición de estados al LLM.** Hoy describe los tools disponibles pero no le dice al modelo cuándo NO usar cada uno. Con `gpt-4o-mini` (modelo chico, propenso a re-ejecutar tools "tentadores"), esto se traduce en loops.

El flujo correcto es una máquina de estados estricta:

```
SEARCH ──► PROPOSE ──► USER_PICKS ──► CONFIRM_SLOT ──► COLLECT_DATA ──► BOOK ──► CONFIRMED
                          │                                                      │
                          └──── (nuevo criterio del usuario) ────► SEARCH        └──► POST_BOOK
```

Hoy el agente no tiene ningún mecanismo para saber "estoy en `USER_PICKS`, no debo volver a `SEARCH` a menos que el usuario cambie explícitamente el criterio".

---

## Causas concurrentes (no descartar)

1. **Buffer de mensajes con debounce muy corto** (`buffer_task.py`): si "Agéndame el del 12 de mayo" llega justo cuando el buffer cierra, el LLM puede procesarlo en dos turnos distintos y re-disparar `check_availability` en el segundo.
2. **Falta de "slot lock" en el contexto del agente**: cuando se proponen slots, no se persiste en Redis cuáles fueron ofrecidos en el último turno. El LLM no tiene memoria estructurada de "estos son los slots vivos, el usuario debe elegir uno de estos".
3. **Tool `confirm_slot` existe pero el LLM no lo invoca**: ya está en `DENTAL_TOOLS` (ver `CLAUDE.md`), pero el prompt no lo hace obligatorio antes de `book_appointment`.
4. **`gpt-4o-mini` como modelo del agente principal**: modelos chicos con muchos tools disponibles tienden a re-ejecutar tools de búsqueda en lugar de avanzar el flujo conversacional. Bug conocido en LangChain agents.

---

## Propuesta de solución (a discutir)

Tres caminos, ordenados de menor a mayor esfuerzo:

### A. Endurecer el system prompt (parche rápido, horas)
- Agregar sección **"REGLAS DE TRANSICIÓN DE ESTADOS"** al system prompt, con reglas explícitas tipo:
  > Si el usuario elige un slot ya propuesto en el último turno, NUNCA llames `check_availability`. Llamá `confirm_slot` con ese slot exacto y avanzá a pedir nombre + DNI.
  > Si ya confirmaste un turno en esta conversación, `list_my_appointments` debe encontrarlo. Si no aparece, NO inventes "Sin turnos" — reportá el error.
- Agregar few-shot examples del flujo correcto en el prompt.
- **Pro:** se puede probar en horas. **Contra:** sigue dependiendo de que el LLM "obedezca".

### B. Slot lock en Redis + validación a nivel código (medio, 1-2 días)
- Cuando `check_availability` propone slots, persistir en Redis `tora:slots:{tenant}:{phone}` con TTL 10 min: la lista de slots vivos.
- `confirm_slot` valida que el slot pedido esté en esa lista; si no, devuelve error y obliga al LLM a re-buscar.
- `book_appointment` exige que haya pasado por `confirm_slot` exitoso (otra clave Redis `tora:locked_slot:{tenant}:{phone}`).
- **Pro:** independiente del modelo, no hay alucinaciones de fechas. **Contra:** más código, más estado.

### C. Reemplazar el agente LangChain por una FSM explícita (alto, 1 semana+)
- Máquina de estados en código Python pura (`enum BookingState`), el LLM solo se usa para NLU (detectar intent + extraer entities).
- El "qué tool llamar después" lo decide el código, no el modelo.
- **Pro:** robustez máxima, fácil de testear. **Contra:** mucho refactor, perdés flexibilidad conversacional.

### Recomendación: **A + B combinados**
1. Empezar por A para detener la sangría en producción esta misma semana.
2. Agregar B en paralelo para blindar el flujo a nivel código.
3. Considerar C solo si tras A+B siguen apareciendo loops.

---

## Validación del fix

Tests E2E que deberían pasar **antes** de dar por cerrada esta tarea:

1. **Happy path**: usuario pide blanqueamiento → recibe slots → elige uno → confirma datos → bookea. **Sin** llamadas redundantes a `check_availability` después de la elección.
2. **Cambio de criterio**: usuario pide mayo, después dice "mejor por la tarde" → SÍ debe re-llamar `check_availability` con filtro tiempo.
3. **Confirmación post-booking**: usuario bookea → en el siguiente turno pregunta "tengo turno?" → `list_my_appointments` debe devolver el booking recién creado.
4. **Fecha argentina**: "12/05" siempre se interpreta como 12 de mayo (DD/MM), nunca como 5 de diciembre. Validar con `dayfirst=True` en `parse_date` y reforzar en el prompt.
5. **Buffer race**: enviar 3 mensajes en 2 segundos (`Agéndame el 12/05`, `a las 10`, `gracias`) → el agente procesa el bloque como una sola intención y avanza, no re-busca.

---

## Bugs relacionados (tracking)

| # | Bug | Causa raíz compartida |
|---|-----|----------------------|
| 1 | Fecha invertida `12/05 → 05/12` | State machine + parser sin `dayfirst` |
| 4 | Loop tras "Agéndame el del 12 de mayo" | State machine |
| 5 | "Sin turnos" después de bookear | State machine (booking nunca se persistió) |
| 9 | Doble respuesta de slots | Buffer race + state machine |

Los 4 se cierran con la misma fix de A+B.

---

## Archivos a tocar (referencia)

- `orchestrator_service/main.py` — system prompt del agente, definición de `DENTAL_TOOLS`
- `orchestrator_service/services/buffer_task.py` — ventana de debounce del buffer
- `orchestrator_service/main.py` — implementaciones de `check_availability`, `confirm_slot`, `book_appointment`
- `orchestrator_service/utils/` — `parse_date()` con `dayfirst=True`
- `tests/test_booking_flow.py` — nuevos tests E2E del state machine

---

## Notas para Engram

- Esta tarea es la #1 en prioridad de bugs de TORA observados el 07/04/2026.
- Bloquea la promesa "100% óptimo" del agente.
- Los bugs cosméticos (`[INTERNAL_PRICE]` filtrado, precio mal escalado, saludo repetido, feriado ofrecido) son separables y NO dependen de esta tarea.
- Decisión pendiente del owner: ¿se prueba A solo primero, o se va directo a A+B?
