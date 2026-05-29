# Proposal: Post-Booking Context Loss — DLD-88 / DLD-89 / DLD-92

## Intent

Resolver 3 bugs de producción donde Paula pierde contexto post-agendamiento y reincide en el flujo de booking como si no hubiera agendado. Los 3 comparten la misma causa raíz: no hay una barrera explícita que evite que el agente ofrezca turnos nuevos cuando el paciente ya tiene un turno confirmado activo en la conversación.

## Scope

### In Scope
- **[REGLAS NUEVAS EN PROMPT]** Agregar REGLA POST-BOOKING explícita que detenga el flujo de booking post-confirmación. Reforzar REGLA ANTI-RE-BOOKING. Agregar a REGLA DE CONTINUIDAD variante post-booking. Agregar a PASO 3b prioridad de "mismo día" para reagendamiento.
- **[GUARD EN CÓDIGO]** En `check_availability`: si el estado conversacional es BOOKED/PAYMENT_PENDING y el mensaje del paciente NO contiene señal explícita de "quiero otro turno", rechazar la tool call.
- **[GUARD EN CÓDIGO]** En `book_appointment`: si hay `last_booked_appointment_id` en el state, validar que el LLM no esté duplicando. Agregar logging de advertencia.
- **[STATE MACHINE]** Extender TTL de BOOKED/PAYMENT_PENDING a 24h para que no expire durante la misma conversación.

### Out of Scope
- Refactor completo de la state machine (solo se extiende TTL y se agregan guards).
- Cambios en `confirm_slot` (no es necesario, el guard en `check_availability` corta antes).
- Cambios en la UI del frontend.
- Migraciones de BD.

## Approach

**Tres líneas de defensa:**

1. **Prompt** — Nueva REGLA POST-BOOKING que instruye al LLM explícitamente: "Después de confirmar un turno, NO ofrezcas turnos nuevos. Respondé preguntas generales sin reiniciar el booking. Solo si el paciente dice EXPLÍCITAMENTE 'quiero OTRO turno' o 'quiero CAMBIAR el turno', podés iniciar un nuevo flujo." + Reforzar REGLA ANTI-RE-BOOKING y REGLA DE CONTINUIDAD.

2. **Código (guard en check_availability)** — Si `get_state()` devuelve BOOKED/PAYMENT_PENDING y el input del paciente NO contiene señal de nuevo turno ("otro turno", "otra fecha", "quiero cambiar", "nuevo turno", "agendame otro"), la tool retorna un mensaje de advertencia en vez de ejecutar.

3. **Código (guard en book_appointment)** — Si `get_state()` tiene `last_booked_appointment_id` y no hay `force_new=true`, la tool rechaza con advertencia.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` — System prompt (~line 10243-10270) | Modified | Nueva REGLA POST-BOOKING + REGLA ANTI-RE-BOOKING reforzada + REGLA DE CONTINUIDAD post-booking |
| `orchestrator_service/main.py` — REGLA DE CONTINUIDAD (~line 10197) | Modified | Agregar excepción post-booking |
| `orchestrator_service/main.py` — PASO 3b (~line 10083) | Modified | Prioridad "mismo día" para reagendamiento |
| `orchestrator_service/main.py` — `check_availability` (~line 1657) | Modified | Guard que verifica estado BOOKED antes de buscar slots |
| `orchestrator_service/main.py` — `book_appointment` (~line 3060) | Modified | Guard que verifica last_booked_appointment_id |
| `orchestrator_service/services/conversation_state.py` | Modified | TTL de BOOKED/PAYMENT_PENDING de 30min a 24h |
| `orchestrator_service/main.py` — `reschedule_appointment` | Modified | No resetear estado a IDLE |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Guard en check_availability bloquea booking legítimo (paciente dice "quiero otro turno") | Bajo | Usar regex de detección de intención explícita, no bloquea mensajes con "otro", "nuevo", "cambiar" |
| TTL de 24h en BOOKED mantiene datos stale | Bajo | Si el paciente vuelve al otro día, el state expiró o el guard es fácil de override con señal explícita |
| LLM ignora la REGLA POST-BOOKING | Medio | Los guards en código atrapan estos casos (defensa en profundidad) |

## Rollback Plan

Revertir commit en `main.py` y `conversation_state.py`. Cambios localizados, diff fácil de reversar.

## Dependencies

Ninguna.

## Success Criteria

- [ ] **DLD-89**: Paciente con turno confirmado pregunta sobre obra social → agente responde sin ofrecer turnos nuevos
- [ ] **DLD-92**: Paciente con turno confirmado describe su procedimiento → agente reconoce que ya tiene turno, no ofrece otro
- [ ] **DLD-88**: Paciente pide reagendar → agente busca del mismo día primero, no entra en loop
- [ ] Paciente dice EXPLÍCITAMENTE "quiero otro turno" → agente puede iniciar nuevo booking
- [ ] check_availability con estado BOOKED devuelve advertencia si no hay señal de nuevo turno
- [ ] book_appointment con last_booked_appointment_id existente rechaza duplicado
- [ ] state BOOKED no expira durante la misma conversación (TTL 24h)
