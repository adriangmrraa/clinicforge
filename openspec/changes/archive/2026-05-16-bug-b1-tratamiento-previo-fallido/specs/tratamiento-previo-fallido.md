# Delta Spec: Tratamiento previo fallido — Neutralidad

**Change**: `bug-b1-tratamiento-previo-fallido`
**Domain**: `prompt/agent-behavior`
**Type**: Delta (modifica comportamiento existente)

---

## ADDED Requirements

### Requirement: NEUTRALIDAD EN TRATAMIENTO PREVIO

Cuando un paciente menciona un tratamiento, cirugía o procedimiento dental previo que resultó en una mala experiencia, el bot NO MUST asumir que dicho tratamiento fue realizado en la clínica. El bot SHALL responder con empatía neutral, sin referirse a "historial con la clínica" ni "estamos actualizando los registros", a menos que el paciente indique EXPLÍCITAMENTE que el tratamiento fue en esta clínica.

#### Scenario: Happy path — Paciente menciona implante fallido sin especificar lugar

- GIVEN un paciente nuevo que dice "me hice implantes y me fue mal"
- WHEN el bot procesa el mensaje
- THEN el bot NO must responder "parece que ya tenés un historial con la clínica"
- AND el bot SHALL validar la experiencia ("lamento que hayas tenido una mala experiencia previa")
- AND el bot SHALL ofrecer evaluación sin asumir el lugar del tratamiento previo

#### Scenario: Edge case — Paciente dice explícitamente que fue en otro lado

- GIVEN un paciente que dice "me hice implantes en otro lugar y me fue mal"
- WHEN el bot procesa el mensaje
- THEN el bot MUST NO activar la sección de MIGRACIÓN
- AND el bot SHALL aplicar el flujo F1 (Mala experiencia previa)
- AND el bot SHALL responder con empatía neutral

#### Scenario: Edge case — Paciente existente REAL menciona turno previo con la Dra.

- GIVEN un paciente que dice "tengo un turno pendiente con la doctora" o "la doctora me dijo que vuelva"
- WHEN el bot procesa el mensaje
- THEN el bot MAY activar la sección de MIGRACIÓN (caso legítimo)
- AND el bot SHALL derivar al equipo como "Paciente existente no migrado"

### Requirement: RESPUESTA MODELO PARA TRATAMIENTO PREVIO FALLIDO

El bot SHOULD tener disponible en su prompt la respuesta modelo aprobada por la Dra. Laura Delgado para casos de tratamiento previo fallido.

#### Scenario: Respuesta modelo incorporada

- GIVEN que se agregó la respuesta modelo al prompt
- WHEN el bot enfrenta un caso de tratamiento previo fallido sin lugar especificado
- THEN el bot MAY usar la respuesta modelo o una equivalente que cumpla con la regla de neutralidad
- AND la respuesta MUST incluir: validación de la experiencia + ofrecimiento de evaluación + mención de estudios previos como opcionales

### Requirement: TRIGGERS DE MIGRACIÓN ACOTADOS

La sección `DETECCIÓN DE PACIENTE EXISTENTE SIN DATOS EN SISTEMA (MIGRACIÓN)` MUST excluir explícitamente los casos donde el paciente menciona un tratamiento en otro lugar o una mala experiencia con otro profesional.

#### Scenario: Trigger de migración no se activa con mala experiencia externa

- GIVEN la sección de MIGRACIÓN en el prompt con triggers acotados
- WHEN un paciente dice "fui a otro dentista y me fue mal" o "me hicieron implantes pero no me quedaron bien"
- THEN la MIGRACIÓN MUST NOT activarse
- AND el flujo F1 SHALL ser el que procese el caso

---

## MODIFIED Requirements

### Requirement: F1 — MALA EXPERIENCIA PREVIA (Triggers ampliados)

Los triggers del flujo F1 SHALL ampliarse para incluir explícitamente casos de "me hice [tratamiento] y me fue mal", "en otro lado", y variantes similares.

(Previously: los triggers eran "no me fue bien", "mala experiencia", "me hicieron mal", "fui a otro y...", "me arruinaron", "no confío")

#### Scenario: Nuevo trigger en F1 captura el caso

- GIVEN el flujo F1 con triggers ampliados
- WHEN un paciente dice "me hice implantes y me fue mal"
- THEN el F1 SHALL activarse correctamente
- AND la respuesta SHALL seguir el protocolo M1 → M2 → M3 de F1

---

## REMOVED Requirements

Ninguno.
