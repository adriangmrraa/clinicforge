# Delta: Professional assignment precedence and anti-cession

## MODIFIED Requirements

### Requirement: PASO 3 debe tener orden de precedencia correcto

The system prompt PASO 3 SHALL be restructured to use this order of precedence:
1. Patient's `assigned_professional_id` (from "PROFESIONAL ASIGNADO" in patient context)
2. Treatment-assigned professionals (from `list_services`/`get_service_details`)
3. Derivation rules (from DERIVACIÓN DE PACIENTES block)
4. Fallback (no filter)

(Previously: PASO 3 only listed derivation rules then list_services, ignoring assigned_professional_id entirely)

#### Scenario: Paciente nuevo con assigned_professional_id

- GIVEN a patient who has `assigned_professional_id = 2` (Laura Delgado) in the database
- AND the patient asks "Quiero un turno para una limpieza dental"
- WHEN determining who should attend this patient
- THEN the agent MUST use Laura Delgado for check_availability
- AND the agent MUST NOT ask for professional preference
- AND the agent MUST NOT suggest other professionals

#### Scenario: Paciente nuevo sin assigned_professional_id pregunta por endodoncia

- GIVEN a new patient with NO assigned_professional_id
- AND the patient asks "Hacen endodoncia?"
- WHEN determining who should attend this patient
- THEN the agent MUST check treatment_type_professionals for endodoncia
- AND the agent MUST respond "nuestro equipo odontológico" or name only the designated professional(s)
- AND the agent MUST NOT include Laura Delgado if she's not designated for endodoncia

### Requirement: Regla anti-cesión

The system prompt SHALL include a rule that prevents the agent from changing the assigned professional when a patient insists on a professional who is NOT designated for that treatment.

(Previously: No anti-cession logic existed. The agent could cave to patient insistence.)

#### Scenario: Paciente insiste con profesional equivocado

- GIVEN a patient who asked about endodoncia
- AND the agent correctly responded "lo realiza nuestro equipo odontológico"
- WHEN the patient insists "Laura Delgado no hace endodoncia? Me gustaría atenderme con ella"
- THEN the agent MUST NOT say "Sí, la endodoncia la hace la Dra. Delgado"
- AND the agent MUST repeat: "La endodoncia la realiza nuestro equipo odontológico. ¿Querés que te agende un turno con ellos?"
- AND the agent MUST continue the conversation without ceding

#### Scenario: Paciente con assigned_professional_id insiste en cambiarse

- GIVEN a patient with assigned_professional_id = 4 (Elizabeth Ester)
- AND the patient asks "Quiero atenderme con Laura Delgado"
- WHEN the treatment requested IS within Laura's designated treatments (e.g., implantes)
- THEN the agent MAY accommodate the request (the patient can change preference)
- Exception: anti-cession only applies when the requested professional does NOT do the treatment

### Requirement: Regla en CONTEXTO DEL PACIENTE para PROFESIONAL ASIGNADO

The "REGLAS DE USO DEL CONTEXTO DEL PACIENTE" block SHALL include an instruction about how to use "PROFESIONAL ASIGNADO" when present.

(Previously: "PROFESIONAL ASIGNADO" was displayed in the context but had no corresponding rule.)

#### Scenario: Contexto tiene PROFESIONAL ASIGNADO

- GIVEN the patient context includes "PROFESIONAL ASIGNADO: Dr/a. Laura Delgado"
- WHEN the agent processes a new message from this patient
- THEN the agent MUST prioritize this professional for any booking
- AND the agent MUST NOT override this assignment without explicit admin action

## Coverage

| Type | Count |
|------|-------|
| Modified requirements | 3 |
| Happy path scenarios | 3 |
| Edge case scenarios | 2 |
