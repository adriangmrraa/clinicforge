# Delta: CASO 1 — Booking after coverage query

## MODIFIED Requirements

### Requirement: Renombrar etiquetas de external_derivation

The text labels in `_format_insurance_providers()` for `external_derivation` providers SHALL NOT use the word "Derivar" to avoid semantic contamination with `derivhumano`.

(Previously: `"Derivación externa:"` and `"• {name} → Derivar a {target}"`)

#### Scenario: Prompt usa etiquetas neutrales

- GIVEN a provider with `status=external_derivation` exists in the DB
- WHEN `_format_insurance_providers()` generates the prompt section
- THEN the section header MUST be "Cobertura con centro externo:" (NOT "Derivación externa:")
- AND each provider line MUST say "→ Centro externo:" (NOT "→ Derivar a")

### Requirement: Instrucción post-respuesta de external_derivation

The `check_insurance_coverage` response section SHALL include a behavior instruction after the `external_derivation` response text: if the patient had already selected a day/time before asking about coverage, the agent MUST continue with the booking flow.

(Previously: Line ~10026 only specified the response text. No post-response instruction existed.)

#### Scenario: Paciente eligió día antes de preguntar por cobertura

- GIVEN a patient with pain who already selected "miércoles" as preferred day
- AND the patient then asks "Me cubre la consulta tengo issn"
- WHEN the agent calls `check_insurance_coverage` and receives `status=external_derivation`
- THEN the agent MUST respond with coverage info
- AND the agent MUST continue asking for patient name and DNI to complete the booking
- AND the agent MUST NOT call `derivhumano`

#### Scenario: Paciente solo preguntó por cobertura sin elegir día

- GIVEN a patient who only asks "Trabajan con ISSN?" without selecting any day
- WHEN the agent calls `check_insurance_coverage` and receives `status=external_derivation`
- THEN the agent MUST respond with coverage info
- AND the agent MUST wait for the patient's next instruction (no forced booking)
- AND the agent MUST NOT call `derivhumano`

## Coverage

| Type | Count |
|------|-------|
| Modified requirements | 2 |
| Happy path scenarios | 2 |
| Edge case scenarios | 1 |
