# Delta Spec: Derivaciones — Eliminar hardcode de profesional en flujos emocionales

**Change**: `bug-b4-b5-b9-derivaciones-sin-hardcode`
**Domain**: `prompt/derivation-rules`
**Type**: Delta

---

## ADDED Requirements

### Requirement: F1 CTA SIN PROFESIONAL

El flujo F1 (Mala experiencia previa) MUST NOT mencionar un profesional específico en su CTA. El CTA SHALL ser genérico, delegando la asignación del profesional al flujo de agendamiento (PASO 3) que usa las tools `list_services` + derivación.

#### Scenario: F1 no menciona a la Dra. Delgado

- GIVEN un paciente que dice "fui a otro dentista y me fue mal"
- WHEN el bot aplica el flujo F1
- THEN el CTA (M3) MUST NOT decir "con la Dra. Laura Delgado"
- AND el CTA SHALL decir "el equipo" o similar genérico

### Requirement: F8b CTA SIN PROFESIONAL

El flujo F8b (Opiniones diferentes) MUST NOT mencionar un profesional específico en su CTA.

#### Scenario: F8b no menciona a la Dra. Delgado

- GIVEN un paciente que dice "cada dentista me dice algo distinto"
- WHEN el bot aplica el flujo F8b
- THEN el CTA (M3) MUST NOT decir "con la Dra. Laura Delgado"
- AND el CTA SHALL ser genérico

### Requirement: F2 ESCALA ODONTOLOGÍA GENERAL AL EQUIPO

Cuando un paciente expresa dolor/urgencia Y menciona un tratamiento de odontología general (endodoncia, conducto, caries, arreglo, limpieza), el bot SHALL escalar al equipo en lugar de agendar directamente.

#### Scenario: Dolor + endodoncia escala al equipo

- GIVEN un paciente que dice "estoy con dolor, me dijeron que necesito un conducto"
- WHEN el bot procesa el mensaje
- THEN el bot SHALL contener (M1)
- AND el bot SHALL NO agendar directamente con la Dra. Delgado
- AND el bot SHALL escalar al equipo humano
- AND el bot SHALL NO decir "Sí, hacemos endodoncia"

#### Scenario: Dolor general sin tratamiento específico

- GIVEN un paciente que dice "me duele una muela"
- WHEN el bot procesa el mensaje
- THEN el bot SHALL contener (M1) + orientar (M2)
- AND el bot SHALL llamar triage_urgency
- AND el bot MAY ofrecer turno según la urgencia sin mencionar profesional específico

### Requirement: F2 PROHIBE LISTAR PROFESIONALES

El flujo F2 (Urgencia/Dolor) MUST NOT listar profesionales por nombre. El bot SHALL NO decir frases como "la consulta de urgencia la puede hacer X, Y o Z".

#### Scenario: F2 no lista profesionales

- GIVEN un paciente que dice "estoy con mucho dolor"
- WHEN el bot procesa el mensaje
- THEN el bot SHALL contener (M1)
- AND el bot SHALL NO decir "la consulta de urgencia la puede hacer" seguido de nombres
- AND el bot SHALL NO listar profesionales disponibles

### Requirement: PROHIBICIÓN DE CONFIRMAR TRATAMIENTOS

El bot MUST NOT decir "Sí, hacemos [tratamiento]" o "Eso entra en [tratamiento]" como respuesta cerrada sin verificar con list_services y sin seguir la derivación correspondiente.

#### Scenario: Bot no confirma endodoncia sin escalar

- GIVEN un paciente que dice "me dijeron que tengo que hacerme un tratamiento de conducto"
- WHEN el bot procesa el mensaje
- THEN el bot MUST NOT responder "Sí, eso entra en Endodoncia"
- AND el bot SHALL usar list_services para verificar el tratamiento
- AND el bot SHALL seguir el flujo de derivación (escalar al equipo)

### Requirement: ORTODONCIA SIN NOMBRAR A LA DRA.

Cuando el paciente consulta por ortodoncia sola (sin cirugía asociada), el bot MUST NOT mencionar a la Dra. Laura Delgado como profesional que realiza el tratamiento. Ortodoncia es atendida por el equipo.

#### Scenario: Ortodoncia sin cirugía

- GIVEN un paciente que dice "quiero información sobre ortodoncia"
- WHEN el bot responde
- THEN el bot SHALL mencionar al equipo (no a la Dra. Delgado)
- AND el bot SHALL aplicar la Regla 2 de derivación (tratamientos generales → equipo)

#### Scenario: Ortodoncia + posible cirugía ortognática

- GIVEN un paciente que dice "necesito ortodoncia porque tengo problemas de mordida"
- WHEN el bot detecta posible componente quirúrgico
- THEN el bot MAY mencionar a la Dra. Delgado como profesional que evalúa el caso

---

## MODIFIED Requirements

### Requirement: F1 — CTA genérico (línea 9538)

El CTA de F1 SHALL cambiar de:
```
"Te ayudo a coordinar una evaluación con {prof_display_full}."
```
a:
```
"Te ayudo a coordinar una evaluación. El equipo te va a indicar el profesional mas adecuado para tu caso."
```

(Previously: hardcodeaba a "la Dra. Laura Delgado" via `{prof_display_full}`)

### Requirement: F8b — CTA genérico (línea 9607)

El CTA de F8b SHALL cambiar de:
```
"Te ayudo a coordinar una evaluación con {prof_display_full}."
```
a:
```
"Te ayudo a coordinar una evaluación. El equipo te va a indicar el profesional mas adecuado para tu caso."
```

(Previously: hardcodeaba a "la Dra. Laura Delgado" via `{prof_display_full}`)

---

## REMOVED Requirements

Ninguno.
