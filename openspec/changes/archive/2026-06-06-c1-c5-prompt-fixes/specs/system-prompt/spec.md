# Delta Spec: System Prompt — C1-C5 Corrections

**Change**: c1-c5-prompt-fixes
**Domain**: system-prompt
**Type**: Delta (5 modifications)
**Date**: 2026-06-06

---

## C1: Eliminar regla temporal expirada

### ADDED Requirements

None — behavior already exists as permanent rule.

### MODIFIED Requirements

#### Requirement: Modalidad de atención (PASO 2c)

El agente DEBE preguntar "¿Te atendés de forma particular o con obra social?" como regla PERMANENTE antes de buscar disponibilidad, sin referencia a fecha de vencimiento ni restricción temporal.

(Previously: La pregunta estaba dentro de una regla temporal con fecha de vigencia 2026-05-15 que restringía turnos con obra social a partir de esa fecha.)

#### Scenario: Paciente nuevo sin mención de obra social

- GIVEN un paciente nuevo que pide un turno
- WHEN el agente está por buscar disponibilidad
- THEN el agente pregunta "¿Te atendés de forma particular o con obra social?"
- AND NO hay restricción de fecha para ninguna de las dos modalidades

#### Scenario: Paciente nuevo con obra social

- GIVEN un paciente nuevo que dice tener obra social
- WHEN el agente busca disponibilidad
- THEN el agente agenda en el próximo turno disponible, SIN limitación de fecha mínima

### REMOVED Requirements

#### Requirement: Regla temporal de operación

(Reason: Vencida el 2026-05-15. La restricción de agendar obra social solo desde 15/05/2026 ya no aplica.)

---

## C2: Instrucción post-booking email

### ADDED Requirements

#### Requirement: Post-booking email collection

Después de confirmar un turno con `book_appointment`, el agente DEBE ofrecer al paciente que proporcione su email para enviarle la confirmación por escrito (BLOQUE 2 de la SECUENCIA POST-BOOKING). Si el paciente proporciona el email, el agente DEBE llamar `save_patient_email` con los parámetros adecuados según sea para sí mismo o para tercero/menor.

#### Scenario: Paciente da email post-booking

- GIVEN un turno confirmado exitosamente con book_appointment
- WHEN el agente envía BLOQUE 2 pidiendo el email
- AND el paciente responde con una dirección de email válida
- THEN el agente llama `save_patient_email(email="...")` sin patient_phone (para sí mismo)

#### Scenario: Paciente ya tiene email registrado

- GIVEN un paciente con email visible en su contexto
- WHEN el agente ejecuta la SECUENCIA POST-BOOKING
- THEN el agente OMITE BLOQUE 2 sin preguntar

---

## C3: Excepción a No-Elección por duda sobre profesional

### MODIFIED Requirements

#### Requirement: Regla de No-Elección

La REGLA DE NO-ELECCIÓN (el paciente no eligió un slot explícitamente) NO aplica cuando la duda del paciente es sobre el profesional que lo atenderá. En ese caso, el agente DEBE validar al paciente, explicar quién es el profesional, y preguntar si desea proceder.

(Previously: La No-Elección era absoluta — cualquier señal de duda detenía el flujo sin excepción.)

#### Scenario: Paciente duda del profesional (no del horario)

- GIVEN un paciente que ha visto opciones de turno
- WHEN el paciente expresa duda sobre quién lo va a atender (ej: "no conozco al doctor")
- THEN la REGLA DE NO-ELECCIÓN NO se activa
- AND el agente explica quién es el profesional y pregunta si desea continuar

#### Scenario: Paciente duda del horario (No-Elección aplica)

- GIVEN un paciente que ha visto opciones de turno
- WHEN el paciente expresa duda sobre el horario (ej: "no sé qué horario me queda bien")
- THEN la REGLA DE NO-ELECCIÓN se activa normalmente

---

## C4: Expandir F1 con subcaso "esta clínica"

### MODIFIED Requirements

#### Requirement: F1 — Mala experiencia previa (splitted)

El flujo F1 se divide en dos sub-flujos:
- F1a (comportamiento existente, renombrado): Mala experiencia en OTRO lugar. Mantiene triggers y protocolo actual.
- F1b (NUEVO): Mala experiencia en ESTA clínica/profesional. Activa PROTOCOLO DE SOPORTE Y QUEJAS con derivación a humano solo si el paciente acepta.

#### Scenario: F1a — Mala experiencia en otro lugar

- GIVEN un paciente que menciona mala experiencia sin referirse a esta clínica
- WHEN el agente detecta el trigger de F1
- THEN aplica F1a: valida, orienta, ofrece evaluación
- AND NO deriva a humano

#### Scenario: F1b — Mala experiencia en esta clínica

- GIVEN un paciente que menciona mala experiencia refiriéndose explícitamente a "la doctora", "la Dra.", "esta clínica", "acá", o un profesional de la clínica
- WHEN el agente detecta el trigger de F1b
- THEN aplica F1b: valida empáticamente, ofrece revisión
- AND deriva a humano SOLO si el paciente acepta

### MODIFIED Requirements

#### Requirement: Regla de prioridad — tratamiento previo fallido (gate)

El gate de prioridad se actualiza para bifurcar entre F1a (experiencia externa) y F1b (experiencia interna), en lugar de bifurcar entre F1 y MIGRACIÓN.

(Previously: El gate bifurcaba entre F1 (para menciones sin especificar) y MIGRACIÓN (para menciones explícitas de "con la doctora").

#### Scenario: Gate detecta experiencia externa

- GIVEN paciente dice "me hice un tratamiento y me fue mal" sin especificar dónde
- WHEN el gate evalúa
- THEN aplica F1a

#### Scenario: Gate detecta experiencia interna

- GIVEN paciente dice "con la doctora no me resultó"
- WHEN el gate evalúa
- THEN aplica F1b (NO MIGRACIÓN)

---

## C5: Documentar tools y corregir referencias

### ADDED Requirements

#### Requirement: Documentar confirm_appointment

El prompt DEBE incluir una sección que describa la tool `confirm_appointment`: su propósito (confirmar turno programado/pendiente), cuándo usarla (solo cuando el paciente pide confirmar explícitamente), y precauciones (preguntar cuál turno si hay ambigüedad).

#### Requirement: Documentar link_payment_to_patient

El prompt DEBE incluir una sección que describa la tool `link_payment_to_patient`: su propósito (vincular comprobante de tercero a paciente), cuándo usarla (solo cuando el remitente NO es el paciente), y diferencia con `verify_payment_receipt`.

### MODIFIED Requirements

#### Requirement: Referencia a list_patient_documents

La referencia en el prompt que dice "usá la tool `list_patient_documents`" DEBE cambiarse porque dicha tool NO existe como LangChain @tool (es admin route). El texto modificado DEBE informar al agente que los documentos están registrados en la ficha del paciente y disponibles para el equipo, sin intentar invocar una tool inexistente.

(Previously: El prompt instruía al agente a usar `list_patient_documents` como si fuera una tool invocable.)
