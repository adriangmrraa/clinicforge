# Tasks: Post-Booking Context Loss — DLD-88 / DLD-89 / DLD-92

## Phase 1: State Machine — TTL extendido

- [x] 1.1 En `conversation_state.py`: agregar constante `BOOKED_TTL = 86400` y modificar `set_state` para usar TTL diferenciado según estado

## Phase 2: Código — Guards en tools

- [x] 2.1 En `check_availability` (main.py ~línea 1695): reemplazar warning log con guard que bloquea si state=BOOKED/PAYMENT_PENDING sin señal de nuevo turno
- [x] 2.2 En `book_appointment` (main.py ~línea 3060): insertar guard que verifica `last_booked_appointment_id` y rechaza duplicado

## Phase 3: Prompt — Reglas nuevas y reforzadas

- [x] 3.1 Insertar `=== REGLA POST-BOOKING ===` entre REGLA ANTI-RE-BOOKING y SECUENCIA POST-BOOKING (línea 10249)
- [x] 3.2 Agregar `⚠️ VARIANTE POST-BOOKING` al final de REGLA DE CONTINUIDAD (~línea 10205)
- [x] 3.3 Reemplazar PASO 3b (~línea 10083-10088) con versión que prioriza mismo día para reagendamiento

## Phase 4: Verificación

- [x] 4.1 Verificar guard en check_availability bloquea cuando state=BOOKED sin señal
- [x] 4.2 Verificar guard en check_availability permite cuando state=BOOKED con "quiero otro turno"
- [x] 4.3 Verificar guard en book_appointment rechaza duplicado con last_booked_appointment_id
- [x] 4.4 Verificar TTL de BOOKED es 24h y OFFERED_SLOTS sigue siendo 30min
- [x] 4.5 Verificar REGLA POST-BOOKING insertada en posición correcta sin pisar nada
- [x] 4.6 Verificar PASO 3b modificado sin perder funcionalidad existente
