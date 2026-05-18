# Delta: CASO 2 — Agent uses derivation rules for professional assignment

## MODIFIED Requirements

### Requirement: PASO 3 debe priorizar reglas de derivación

The system prompt's PASO 3 (Professional Assignment) SHALL be restructured to consult derivation rules BEFORE using `list_services`/`get_service_details` results. The order of precedence SHALL be:
1. Derivation rules (if a matching rule exists)
2. `list_services`/`get_service_details` (fallback if no rule matches)

(Previously: PASO 3 only referenced `list_services`/`get_service_details` output, ignoring derivation rules entirely)

#### Scenario: Endodoncia con regla de derivación "equipo"

- GIVEN a patient asks "Con qué profesional me atiendo una endodoncia?"
- AND the derivation rules contain Rule 2: "Tratamientos generales → Equipo" with categories including "endodoncia"
- AND Rule 2 specifies "sin filtro de profesional (equipo)"
- WHEN the agent needs to determine who handles endodoncia
- THEN the agent MUST respond referencing "nuestro equipo odontológico" or similar
- AND the agent MUST NOT list individual professional names (Laura Delgado, Elizabeth Ester, Eli Perez)

#### Scenario: Implante con regla de derivación profesional específico

- GIVEN a patient asks "Quién hace implantes?"
- AND the derivation rules contain Rule 1: "Cirugía e implantes → Dra. Delgado" with categories including "implante"
- AND Rule 1 specifies "agendar con Laura Delgado (ID: X)"
- WHEN the agent needs to determine who handles implants
- THEN the agent MUST respond naming ONLY "Dra. Laura Delgado"
- AND the agent MUST NOT list other professionals

#### Scenario: Tratamiento sin regla de derivación configurada

- GIVEN a patient asks about a treatment that has NO matching derivation rule
- WHEN the agent needs to determine who handles it
- THEN the agent MUST fall back to `list_services`/`get_service_details` output
- AND the agent SHOULD follow the existing PASO 3 logic for the fallback case

### Requirement: get_service_details no debe appender profesionales con template

The `get_service_details` tool SHALL NOT append the "Profesionales:" line when an `ai_response_template` exists for the treatment.

(Previously: Line ~5392-5395 appended `f"\nProfesionales: {', '.join(assigned_profs)}\n"` after the template, creating contradictory information)

#### Scenario: Endodoncia con ai_response_template

- GIVEN the treatment "endodoncia" has an `ai_response_template` saying "lo realiza el equipo odontológico"
- AND the treatment has assigned professionals in `treatment_type_professionals`
- WHEN `get_service_details` returns the data for endodoncia
- THEN the response MUST contain ONLY the `ai_response_template` text
- AND the response MUST NOT include the "Profesionales:" line with individual names

## REMOVED Requirements

(No requirements removed — only behavior modified)

## Coverage

| Type | Count |
|------|-------|
| Modified requirements | 2 |
| Happy path scenarios | 3 |
| Edge case scenarios | 1 |
