# Delta: check_availability retry with broader range

## ADDED Requirements

### Requirement: Reintentar con rango más amplio si 0 slots

The system prompt PASO 4 SHALL include an instruction to retry `check_availability` with a broader date range (`search_mode='week'` or `search_mode='month'`) when the initial call returns 0 slots or a "no availability" message. The professional MUST NOT change on retry.

#### Scenario: Sin disponibilidad en fecha exacta, reintenta con semana

- GIVEN a patient asks for an appointment on a specific date
- WHEN `check_availability` is called with `search_mode='exact'` and returns 0 slots
- THEN the agent MUST call `check_availability` again with `search_mode='week'` to expand the range
- AND the agent MUST NOT change the professional
- AND if the second call returns slots, the agent MUST offer them to the patient

#### Scenario: Sin disponibilidad en semana, reintenta con mes

- GIVEN a patient asks for an appointment "esta semana"
- WHEN `check_availability` is called with `search_mode='week'` and returns 0 slots
- THEN the agent MAY call `check_availability` again with `search_mode='month'`
- AND the agent MUST NOT change the professional
- AND if still no slots, the agent MUST inform the patient and optionally offer waitlist

#### Scenario: Sin disponibilidad incluso después de reintentar

- GIVEN the agent has retried with broader ranges and all return 0 slots
- WHEN the agent has exhausted retry options
- THEN the agent MUST inform the patient: "No encontré disponibilidad para las próximas semanas"
- AND the agent MUST NOT call `derivhumano` for this reason alone

#### Scenario: book_appointment falla por disponibilidad

- GIVEN the agent has called `book_appointment` for a confirmed slot
- WHEN `book_appointment` returns "no hay disponibilidad" or similar
- THEN the agent MUST offer other slots from the previously offered options
- AND the agent MUST NOT tell the patient "no hay disponibilidad" without offering alternatives

## Coverage

| Type | Count |
|------|-------|
| New requirements | 1 |
| Scenarios | 4 |
