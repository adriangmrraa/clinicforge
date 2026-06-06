# Delta Spec: Corrección de estructura del booking flow — numeración y orden (B1, B3, B7)

## ADDED Requirements

### Requirement: B1 — Crear PASO 5 (Validación pre-booking)

El system prompt DEBE contener un PASO 5 entre PASO 4c y PASO 6 que valide todos los prerrequisitos antes de llamar `book_appointment`.

El sistema DEBE insertar el siguiente bloque entre la línea 10832 (fin de PASO 4c) y la línea 10833 (inicio de PASO 6):

```
PASO 5: VALIDACIÓN PRE-BOOKING — Antes de agendar, verificá:
• ¿El CONTEXTO DEL PACIENTE tiene nombre y DNI? Si falta → volver a PASO 4b.
• ¿check_availability devolvió [INTERNAL_DEBT:...] en el slot elegido? Si sí, avisá al paciente del saldo pendiente ANTES de llamar book_appointment. PROHIBIDO bloquear el turno por deuda — el paciente puede agendar igual, pero debe saber que tiene saldo registrado.
• ¿El paciente confirmó el slot (PASO 4c exitoso)? Si no, no llamar book_appointment.
• Todo OK → ir a PASO 6.
```

#### Scenario: B1.1 — Happy path sin deuda

- GIVEN un paciente con nombre y DNI en contexto, un slot confirmado vía `confirm_slot`, y `check_availability` sin `[INTERNAL_DEBT]`
- WHEN el agente evalúa PASO 5
- THEN el agente salta las verificaciones de deuda y pasa directamente a PASO 6 para ejecutar `book_appointment`

#### Scenario: B1.2 — Deuda pendiente detectada

- GIVEN un paciente con nombre y DNI en contexto, un slot confirmado, y `check_availability` devolvió `[INTERNAL_DEBT:$15000]` en el slot
- WHEN el agente evalúa PASO 5
- THEN el agente informa al paciente: "Tenés un saldo pendiente de $15.000 registrado en el sistema" pero procede a PASO 6 para agendar igual
- AND el agente NO bloquea el turno por la deuda

#### Scenario: B1.3 — Datos del paciente incompletos

- GIVEN un paciente sin nombre o DNI en el contexto del paciente
- WHEN el agente evalúa PASO 5
- THEN el agente retrocede a PASO 4b para solicitar los datos faltantes
- AND NO llama `book_appointment` sin completar la admisión

## MODIFIED Requirements

### Requirement: B3 — Mover POST-ATENCIÓN al final del prompt

El bloque "SEGUIMIENTO POST-ATENCIÓN (PROTOCOLO ESTRICTO)" (actualmente líneas 10511-10520) DEBE ser extraído de su posición actual y reubicado DESPUÉS de PASO 10 (línea 10921), ANTES de "INSTRUCCIONES DE TRATAMIENTO (POST-AGENDAMIENTO)" (línea 10923).

(Previously: El bloque estaba entre "DIFERENCIACIÓN DRA. vs EQUIPO" y "FLUJO DE AGENDAMIENTO", interrumpiendo la secuencia lógica del booking flow.)

#### Scenario: B3.1 — Posición correcta después del movimiento

- GIVEN el system prompt
- WHEN se examina la ubicación del bloque POST-ATENCIÓN
- THEN el bloque DEBE aparecer inmediatamente después de PASO 10 (línea ~10921) y antes de INSTRUCCIONES DE TRATAMIENTO (línea ~10923)
- AND el bloque NO DEBE aparecer entre DIFERENCIACIÓN DRA. vs EQUIPO y FLUJO DE AGENDAMIENTO

#### Scenario: B3.2 — Contenido sin alteración

- GIVEN el bloque POST-ATENCIÓN movido
- WHEN se compara el contenido textual del bloque contra el original (líneas 10511-10520)
- THEN el contenido DEBE ser idéntico palabra por palabra, sin modificaciones

### Requirement: B7 — Renombrar PASO 1 duplicado de FAQs

La línea 10474 DEBE cambiar de `PASO 1 — FAQs PARA TODO LO DEMÁS (VOZ OFICIAL):` a `SECCIÓN FAQ — VOZ OFICIAL:`.

(Previously: Había dos secciones con etiqueta "PASO 1" — FAQs (línea 10474) y SALUDO E IDENTIDAD (línea 10584) — causando colisión semántica.)

#### Scenario: B7.1 — Sin colisión de etiquetas

- GIVEN el system prompt después del renombrado
- WHEN se buscan todas las ocurrencias de `PASO 1`
- THEN DEBE existir EXACTAMENTE UNA sección con etiqueta "PASO 1" (la de SALUDO E IDENTIDAD en línea 10584)
- AND la sección de FAQ DEBE titularse "SECCIÓN FAQ — VOZ OFICIAL"

#### Scenario: B7.2 — Funcionalidad FAQ preservada

- GIVEN el título renombrado de la sección FAQ
- WHEN el agente busca la sección de FAQs para responder una pregunta general
- THEN el contenido y las reglas de la sección FAQ DEBEN ser idénticos al original
- AND el agente DEBE seguir usando las FAQs como fuente de verdad para temas generales

## REMOVED Requirements

(Ninguno. No se eliminan secciones ni se depreca comportamiento existente.)
