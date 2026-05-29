# Spec: Post-Booking Context Loss — DLD-88 / DLD-89 / DLD-92

## Problema General

Paula pierde contexto después de confirmar un turno. Cuando el paciente hace preguntas generales post-booking (obra social, tratamiento, dirección), Paula reinicia el flujo de agendamiento como si no hubiera turno, ofreciendo turnos nuevos, duplicando citas y confundiendo al paciente.

---

## R1: REGLA POST-BOOKING (Prompt)

### Descripción
Nueva sección en el system prompt que instruye al agente sobre qué hacer DESPUÉS de confirmar un turno. Debe insertarse después de `REGLA ANTI-RE-BOOKING` y antes de `SECUENCIA POST-BOOKING`.

### Regla
```
=== REGLA POST-BOOKING (INQUEBRANTABLE) ===
Cuando YA CONFIRMASTE un turno con book_appointment en esta conversación:

1. El paciente YA TIENE turno. NO ofrezcas turnos nuevos.
2. Si el paciente hace una pregunta GENERAL (obra social, tratamiento, procedimiento, dirección, seña, horario, etc.):
   → Respondé la pregunta NORMALMENTE.
   → NO ofrezcas "te paso turnos disponibles", "te ayudo a coordinar", "querés agendar", ni ninguna variante.
   → NO llames check_availability. NO llames confirm_slot. NO llames book_appointment.
   → El turno ya está agendado. Solo respondé la consulta puntual.
3. Si el paciente describe su problema clínico (dolor, molestia, lo que sea):
   → Reconocé que ya tiene turno: "Entiendo, la Dra. Laura te va a evaluar en tu turno del [día] a las [hora]."
   → NO ofrezcas un nuevo turno. NO reinicies el flujo de booking.
4. La ÚNICA excepción para iniciar un nuevo booking es cuando el paciente dice EXPLÍCITAMENTE:
   "quiero OTRO turno", "necesito otro turno", "agendame otro", "dame otro turno", "quiero CAMBIAR el turno",
   "puedo mover el turno", "reagendá", "reprogramá", o similar con intención CLARA de nuevo/cambio de turno.
5. Si el paciente dice algo ambiguo como "sí", "dale", "ok" sin referirse a un nuevo turno:
   → NO interpretes como solicitud de nuevo turno.
   → Respondé amablemente.
```

### Escenarios

| # | Contexto | Paciente dice | Comportamiento esperado |
|---|----------|---------------|------------------------|
| 1.1 | Turno confirmado ✅ | "Tengo Federada Salud, cubre?" | Responde sobre cobertura. NO ofrece turnos. |
| 1.2 | Turno confirmado ✅ | "Es por un mucocele que tengo" | "La Dra. Laura te evalúa en tu turno del [día]." NO ofrece turno nuevo. |
| 1.3 | Turno confirmado ✅ | "Cuál es la dirección?" | Da la dirección. NO ofrece turnos. |
| 1.4 | Turno confirmado ✅ | "Quiero sacar otro turno para mi hijo" | "Claro, decime qué necesita." Inicia nuevo booking para el hijo. |
| 1.5 | Turno confirmado ✅ | "Se puede cambiar el turno?" | Inicia flujo de reschedule. |
| 1.6 | Turno confirmado ✅ | "Necesito otro turno, este es para control y también quiero una limpieza" | Reconoce que ya tiene un turno. Si es explícito "otro turno", puede iniciar nuevo booking. |
| 1.7 | Turno confirmado ✅ | "Dale, gracias" | Responde "De nada 😊" SIN ofrecer turnos. |

---

## R2: REGLA ANTI-RE-BOOKING — REFORZADA (Prompt)

### Descripción
La regla actual (línea 10243) ya existe pero tiene un agujero: solo prohíbe llamar tools para el *mismo* turno, no impide iniciar un *nuevo* flujo. Se agrega:
- Referencia explícita a PRÓXIMO TURNO en el contexto
- Prohibición explícita de ofrecer "te paso turnos disponibles" post-booking
- Conexión con REGLA POST-BOOKING

### Escenarios

| # | Contexto | Comportamiento esperado |
|---|----------|------------------------|
| 2.1 | Contexto del paciente tiene "PRÓXIMO TURNO" + paciente no pidió OTRO turno | NO ofrecer turnos nuevos. La existencia del turno en contexto es SUFICIENTE para no reiniciar booking. |
| 2.2 | Contexto del paciente tiene "PRÓXIMO TURNO" + paciente dice "quiero otro turno" | Puede iniciar nuevo booking (PASO 3b). |
| 2.3 | book_appointment acaba de confirmar + paciente escribe cualquier cosa | Aplica REGLA POST-BOOKING (R1). |

---

## R3: REGLA DE CONTINUIDAD — VARIANTE POST-BOOKING (Prompt)

### Descripción
Agregar al final de `REGLA DE CONTINUIDAD` (línea 10197) una excepción post-booking:

```
⚠️ VARIANTE POST-BOOKING: Si el paciente YA TIENE turno confirmado en esta conversación
y hace una pregunta lateral, NO retomés el tema del turno. El turno YA ESTÁ CONFIRMADO.
Solo respondé la pregunta. No hay "opciones pendientes" porque ya eligió.
```

### Escenarios

| # | Contexto | Paciente dice | Comportamiento esperado |
|---|----------|---------------|------------------------|
| 3.1 | Turno confirmado, paciente pregunta obra social | "Y con OSDE cómo sería?" | Responde sobre OSDE. NO retoma "te queda mejor el 1 o el 2". |
| 3.2 | Paciente con oferta de slots vigente pregunta lateral | "Aceptan American Express?" | Responde sobre medios de pago. DESPUÉS retoma opciones pendientes (comportamiento actual, sin cambios). |

---

## R4: PASO 3b — PRIORIDAD "MISMO DÍA" PARA REAGENDAMIENTO (Prompt)

### Descripción
Modificar PASO 3b (línea 10083) para que cuando el paciente pida reagendar, la prioridad sea buscar del mismo día PRIMERO.

### Regla actual
```
PASO 3b: PACIENTE CON TURNO EXISTENTE — Si el paciente YA TIENE un turno agendado...
• El nuevo turno NO puede ser en el mismo horario. Ofrecé otras opciones disponibles.
• Si pide el mismo día pero distinta hora → OK, agendá normalmente si hay disponibilidad.
```

### Regla modificada
```
PASO 3b: PACIENTE CON TURNO EXISTENTE — Si el paciente YA TIENE un turno agendado...
• PRIMERO: Si el paciente pide reagendar/cambiar/mover el turno, buscá disponibilidad en el MISMO DÍA antes de ofrecer otras fechas.
• Si hay disponibilidad el mismo día → ofrecé esas opciones primero.
• Si NO hay disponibilidad el mismo día → recién ahí ofrecé otros días cercanos.
• El nuevo turno NO puede ser en el mismo horario.
```

### Escenarios

| # | Contexto | Paciente dice | Comportamiento esperado |
|---|----------|---------------|------------------------|
| 4.1 | Turno 26/05 13:30 | "Puedo moverlo a otro horario el mismo día?" | Busca disponibilidad el 26/05 PRIMERO. Ofrece opciones. |
| 4.2 | Turno 26/05 13:30, sin disponibilidad el 26/05 | "Puedo moverlo?" | Busca 26/05, no hay. Busca días siguientes. Ofrece opciones. |
| 4.3 | Turno 26/05 13:30 | "Quiero cambiarlo al jueves" | Busca el jueves PRIMERO (el día que pidió), no otro día. |

---

## R5: Guard en `check_availability` (Código)

### Descripción
Si el estado conversacional del paciente es `BOOKED` o `PAYMENT_PENDING`, `check_availability` debe verificar si el mensaje del paciente contiene intención explícita de nuevo turno. Si NO la contiene, la tool debe retornar un mensaje de advertencia en vez de ejecutar la búsqueda.

### Señales de intención explícita de NUEVO turno
```
"otro turno", "nuevo turno", "otra fecha", "otro día", "quiero cambiar",
"reagendá", "reprogramá", "mover el turno", "cancelá", "dame otro",
"agendame otro", "necesito otro", "sacá otro", "quiero uno más",
"turno para [nombre]" (tercero), "para mi [hijo/madre/etc]"
```

### Comportamiento
```python
if state in ("BOOKED", "PAYMENT_PENDING") and not _has_new_booking_intent(patient_message):
    return (
        "BOOKING_ALREADY_EXISTS: El paciente ya tiene un turno confirmado en esta conversación. "
        "No se debe ofrecer un nuevo turno a menos que el paciente lo solicite explícitamente. "
        "Respondé la consulta del paciente sin ofrecer turnos nuevos."
    )
```

Si el mensaje SÍ contiene intención explícita, la tool continúa normalmente.

### Escenarios

| # | Estado | Mensaje paciente | check_availability |
|---|--------|-----------------|-------------------|
| 5.1 | BOOKED | "Tengo Federada Salud" | ❌ Bloqueado → retorna BOOKING_ALREADY_EXISTS |
| 5.2 | BOOKED | "Es por un mucocele" | ❌ Bloqueado → retorna BOOKING_ALREADY_EXISTS |
| 5.3 | BOOKED | "Quiero otro turno para mi hijo" | ✅ Permite ejecución (señal explícita) |
| 5.4 | BOOKED | "Necesito reagendar" | ✅ Permite ejecución (señal explícita) |
| 5.5 | BOOKED | "Dale gracias" | ❌ Bloqueado |
| 5.6 | IDLE | "Tengo Federada Salud" | ✅ Permite ejecución (no hay booking activo) |
| 5.7 | OFFERED_SLOTS | "Tengo Federada Salud" | ✅ Permite ejecución (no hay booking confirmado, aplica REGLA DE CONTINUIDAD normal) |

---

## R6: Guard en `book_appointment` (Código)

### Descripción
Si `last_booked_appointment_id` existe en el state, `book_appointment` debe verificar que el LLM no esté duplicando un turno. Si detecta duplicación potencial, retorna advertencia.

### Escenarios

| # | Estado | Intención | book_appointment |
|---|--------|-----------|-----------------|
| 6.1 | BOOKED con apt_id=123, nuevo intento sin señal de nuevo turno | LLM intenta agendar otro turno para el mismo paciente | ❌ Rechaza con "DUPLICATE_BOOKING: El paciente ya tiene turno confirmado (#123)" |
| 6.2 | BOOKED con apt_id=123, paciente dijo "otro turno" | LLM pasa force_new_booking | ✅ Permite (con logging de advertencia) |

---

## R7: State Machine — TTL Extendido (Código)

### Descripción
El TTL de `CONVSTATE_TTL` se mantiene en 1800s globalmente, pero los estados `BOOKED` y `PAYMENT_PENDING` deben usar un TTL más largo (24h = 86400s) para no expirar durante la misma conversación.

### Cambio en `conversation_state.py`
```python
# Al setear BOOKED o PAYMENT_PENDING, usar TTL de 24h
if state in ("BOOKED", "PAYMENT_PENDING"):
    ttl = 86400  # 24 horas
else:
    ttl = CONVSTATE_TTL  # 30 minutos default
```

### Escenarios

| # | Estado | Tiempo | Comportamiento |
|---|--------|--------|----------------|
| 7.1 | BOOKED | 35 min después (antes expiraba) | ✅ Sigue vivo, guard R5 puede verificar |
| 7.2 | BOOKED | 25h después | ❌ Expirado → IDLE (normal, el paciente no va a escribir post 24h sin nuevo mensaje) |
| 7.3 | OFFERED_SLOTS | 35 min después | ❌ Expirado → IDLE (comportamiento actual, correcto) |

---

## R8: Logging

Agregar logging en:
- `check_availability` cuando bloquea por BOOKED state: `📅 CHECK_AVAILABILITY BLOCKED: state={state} phone={phone}`
- `book_appointment` cuando detecta `last_booked_appointment_id` previo: `📅 BOOK BLOCKED: existing_apt_id={id} phone={phone}`
- `book_appointment` cuando force_new_booking=true: `📅 BOOK FORCE NEW: existing_apt_id={id} phone={phone}`
