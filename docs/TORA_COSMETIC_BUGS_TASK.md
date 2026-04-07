# TORA — Bugs Cosméticos y de UX (tarea pendiente)

> **Estado:** análisis hecho, sin implementar.
> **Prioridad:** 🟠 media — no rompen booking pero erosionan credibilidad del producto.
> **Origen:** conversación de prueba con "Juan Román Riquelme" (07/04/2026).
> **Relación:** independientes del fix de state machine (ver `TORA_STATE_MACHINE_LOCK_TASK.md`). Se pueden resolver en paralelo.

---

## Bug #2 — Marker `[INTERNAL_PRICE:7000000]` filtrado al paciente

### Síntoma
En medio del mensaje de availability, el paciente ve:
```
⏱️ Duración: 60 min
[INTERNAL_PRICE:7000000]
📍 Dirección: Salta 147...
```

### Causa probable
La tool `check_availability` (en `orchestrator_service/main.py`) arma un string que incluye markers internos pensados para que el LLM "vea" el precio sin mostrarlo. Pero el string completo se manda al usuario sin pasar por una capa de saneamiento.

### Fix propuesto
Una de dos opciones:
1. **Strip en el agente**: antes de enviar la respuesta del LLM al usuario, regex `\[INTERNAL_[^\]]+\]` y eliminar.
2. **No mezclar contextos**: que `check_availability` devuelva un dict `{user_text, internal_context}` y solo `user_text` viaje al canal.

La opción 2 es más limpia pero requiere refactor de varias tools. La opción 1 es un parche de 5 líneas que se puede meter en `_process_and_respond` o equivalente.

### Validación
Test unitario: cualquier respuesta del agente que contenga `[INTERNAL_*]` debe fallar antes de llegar al canal de salida.

---

## Bug #3 — Precio mal escalado: $7.000.000 para un blanqueamiento

### Síntoma
TORA muestra "$7,000,000" como valor del Blanqueamiento BEYOND®. Siete millones de pesos para un blanqueamiento es absurdo (~U$S 5.500).

### Causa probable
Tres hipótesis, en orden de probabilidad:
1. **Data entry error**: alguien cargó `7000000` en `treatment_types.base_price` queriendo decir `70000` o `700000`. Verificable con `SELECT code, name, base_price FROM treatment_types WHERE tenant_id = X;`.
2. **Centavos sin dividir**: el campo guarda centavos (común en sistemas de pago) y el formateador no divide por 100.
3. **Doble multiplicación**: alguien aplica un factor de inflación o conversión dos veces.

### Fix propuesto
- **Si es #1**: corregir el dato en la DB, sumar validación en el form de creación de tratamientos (`base_price > 100_000_000` → warning "¿Estás seguro? Equivale a $X").
- **Si es #2**: crear un helper `format_currency(amount, locale='es-AR')` y migrar todos los puntos de uso. Documentar en `models.py` que el campo es en pesos enteros.
- **Si es #3**: rastrear la cadena de cálculo desde la query hasta el render.

### Validación
Smoke test manual: pedir presupuesto de cada tratamiento configurado y verificar que el precio mostrado coincida con el de la UI admin.

---

## Bug #6 — Feriados ofrecidos como disponibles

### Síntoma
TORA propone el `17/08` como slot. El usuario lo elige. Solo entonces TORA dice "el 17/08 es feriado, no se puede". El paciente queda con la sensación de que el sistema no sabe lo que ofrece.

### Causa probable
`check_availability` consulta `working_hours` del tenant pero **no consulta `holiday_service`** al armar la lista. El bloqueo por feriados solo se aplica en el momento de `book_appointment`, demasiado tarde.

### Fix propuesto
En `check_availability`, antes de devolver slots:
```python
from services.holiday_service import is_holiday
slots = [s for s in slots if not await is_holiday(s.date, country='AR', region=tenant.region)]
```
Bonus: si un día queda completamente vacío por feriado, anotarlo en el contexto interno para que el LLM pueda decir "el 17 es feriado, te ofrezco el 18 en su lugar".

### Validación
- Slot ofrecido en feriado nacional (1ro de mayo, 9 de julio, 25 de mayo) → debe estar excluido de la lista.
- Slot ofrecido en feriado provincial (depende del tenant) → también excluido si `tenant.region` está configurado.

---

## Bug #7 — Filtro "por la tarde" no se aplica

### Síntoma
Usuario: "Por la tarde en mayo tienen algo?"
TORA responde: `10:00, 10:00, 13:00`. Solo el último es "tarde" y por poco.

### Causa probable
El parser de fechas (`parse_date()` en orchestrator) no extrae `time_of_day` como entidad independiente. El LLM lee "tarde" pero no tiene un parámetro en `check_availability` para pasarle la franja horaria, así que la información se pierde.

### Fix propuesto
1. Agregar parámetro opcional `time_of_day: Literal['mañana','tarde','noche']` a `check_availability`.
2. Mapear:
   - `mañana` → 08:00–12:00
   - `tarde` → 13:00–18:00
   - `noche` → 18:00–21:00
3. En el system prompt, instruir al LLM a extraer esta entidad cuando el paciente la mencione.
4. Si hay menos de 3 slots en la franja pedida, completar con la franja contigua y marcarlo en el mensaje ("en la tarde no hay nada antes del 12, te ofrezco también una opción de la mañana").

### Validación
Tests con frases típicas: "por la tarde", "a la mañana", "después del mediodía", "antes del almuerzo", "después de las 5".

---

## Bug #8 — Saludo completo repetido en cada cambio de tema

### Síntoma
Mismo paciente, misma conversación. A los 20 minutos pregunta otra cosa y TORA vuelve a recitar:
> "Hola 😊 Soy TORA, la asistente virtual de Clínica Dra. Laura Delgado. La Dra. Laura Delgado se especializa en rehabilitación oral con implantes y prótesis, casos complejos de alta dificultad técnica..."

### Causa probable
El system prompt incluye el saludo como instrucción incondicional para cuando detecta "Hola"/"Buenas". No hay memoria de "ya saludé en esta conversación".

### Fix propuesto
1. Agregar flag `greeted_at` en `patient.context` (JSONB) o en Redis con TTL de 24h.
2. En el prompt, instrucción explícita: "Si `greeted_at` está set y es menos de 6h vieja, NO repitas el saludo completo. Respondé solo con un emoji y avanzá al tema del paciente."
3. Bonus: hacer el saludo más corto en general. La descripción de la doctora es publicidad, no un saludo. Moverla a un disclaimer que solo se muestra una vez por paciente (no por sesión).

### Validación
Conversación de 5 turnos con el mismo paciente → solo el primer turno tiene saludo completo, los demás tienen respuesta directa.

---

## Bug #9 — Doble respuesta de slots por race del buffer

### Síntoma
En la conversación, dos veces se ven respuestas casi idénticas con 1 minuto de diferencia (02:01 y 02:02), con la misma grilla de horarios pero texto ligeramente distinto.

### Causa probable
`buffer_task.py` agrupa mensajes entrantes en una ventana de N segundos. Si el usuario manda dos mensajes en rápida sucesión y el buffer cierra entre ellos, el agente procesa dos turnos donde debería procesar uno. Resultado: dos respuestas independientes a la misma intención.

### Fix propuesto
1. Aumentar la ventana de debounce a 3-5 segundos (hoy probablemente está en 1-2s).
2. Implementar "soft cancel": si llega un mensaje nuevo mientras la respuesta del turno previo aún no se envió, cancelar el primer turno y reprocesar todo junto.
3. Idempotencia: hash del último mensaje + timestamp → si en los próximos 10s llega otro turno con el mismo hash, descartar.

### Validación
Test E2E: enviar 3 mensajes con 500ms entre cada uno → el agente debe responder UNA sola vez agrupando los 3.

---

## Resumen de prioridad sugerido

| # | Bug | Esfuerzo | Visibilidad | Riesgo si no se hace |
|---|-----|----------|-------------|----------------------|
| 2 | Strip `[INTERNAL_PRICE]` | 5 min | 🔴 alta | Pérdida instantánea de credibilidad |
| 3 | Precio mal escalado | 10 min (+ data fix) | 🔴 alta | Ridículo en demos |
| 8 | Saludo repetido | 30 min | 🟠 media | Sensación de "bot tonto" |
| 6 | Feriados en availability | 1h | 🟠 media | Frustración después de elegir |
| 7 | Filtro tarde/mañana | 2h | 🟡 baja | Pérdida de relevancia, no de booking |
| 9 | Race del buffer | 3h (debug) | 🟡 baja | Confusión visual ocasional |

**Sugerencia:** atacar #2 y #3 esta misma semana (10 min total para #2 + #3 si la causa es data entry). Los demás se pueden ir resolviendo en sprints.

---

## Notas para Engram

- Todos estos bugs son **independientes del state machine lock** documentado en `TORA_STATE_MACHINE_LOCK_TASK.md`.
- Ninguno afecta tasa de conversión real, pero #2 y #3 afectan **percepción de calidad del producto en demos**.
- Si hay que priorizar entre estos y el state machine: state machine primero (afecta plata real), cosméticos después.
