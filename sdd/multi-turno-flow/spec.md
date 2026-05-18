# Delta: Multi-turno flow

## ADDED Requirements

### Requirement: PASO 3b para pacientes con turno existente

The system prompt SHALL include a new step (PASO 3b) between PASO 3 and PASO 4 that instructs the agent on how to handle patients who already have an appointment and request a second one.

#### Scenario: Paciente con turno pide segundo turno mismo día distinta hora

- GIVEN a patient who already has an appointment on Tuesday 19/05 at 10:00 with Eli
- AND the patient asks "Ahora quiero un turno para blanqueamiento el mismo día pero a las 15:00"
- WHEN the agent processes this request
- THEN the agent MUST acknowledge the existing appointment
- AND the agent MUST offer available slots at 15:00 (or nearby) without mentioning 10:00
- AND the agent MUST allow the booking if the professional is available at 15:00

#### Scenario: Paciente con turno pide segundo turno mismo día misma hora

- GIVEN a patient who already has an appointment on Tuesday 19/05 at 10:00
- AND the patient asks for another appointment on Tuesday 19/05 at 10:00
- WHEN the agent processes this request
- THEN the agent MUST NOT offer 10:00
- AND the agent MUST say something like "Ya tenés un turno a las 10:00. ¿Querés otra hora o probamos otro día?"

#### Scenario: Paciente con turno pide segundo turno otro día

- GIVEN a patient who already has an appointment on Tuesday 19/05 at 10:00
- AND the patient asks for another appointment on Friday 22/05
- WHEN the agent processes this request
- THEN the agent MUST offer available slots on Friday normally
- AND the agent MUST NOT block the request

## Coverage

| Type | Count |
|------|-------|
| New requirements | 1 |
| Scenarios | 3 |
