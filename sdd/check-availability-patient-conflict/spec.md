# Delta: Patient self-conflict guard in check_availability

## ADDED Requirements

### Requirement: Excluir slots donde el paciente ya tiene turno

`check_availability` MUST exclude time slots where the requesting patient already has an existing appointment, regardless of which professional is assigned to that appointment.

#### Scenario: Paciente pide segundo turno el mismo día a la misma hora

- GIVEN a patient who already has an appointment for endodoncia with Eli on **Tuesday 19/05 at 10:00**
- AND the patient asks for a blanqueamiento appointment
- WHEN `check_availability` is called with `treatment_name=blanqueamiento` for Tuesday 19/05
- THEN the returned available slots MUST NOT include 10:00 (or any time overlapping with 10:00-10:30)
- AND the slot with Laura at 10:00 MUST NOT be offered

#### Scenario: Paciente pide segundo turno otro día / otro horario

- GIVEN a patient who already has an appointment on Tuesday 19/05 at 10:00 with Eli
- AND the patient asks for a blanqueamiento appointment on **Friday 22/05**
- WHEN `check_availability` is called for Friday 22/05
- THEN all available slots on Friday MUST be offered normally
- AND no slots on Friday are blocked by the Tuesday appointment

#### Scenario: Paciente pide segundo turno mismo día diferente horario

- GIVEN a patient who already has an appointment on Tuesday 19/05 at 10:00 with Eli
- AND the patient asks for a blanqueamiento appointment on Tuesday 19/05 at **15:00**
- WHEN `check_availability` is called
- THEN 15:00 MUST be offered as available (different time, same day is valid)
- AND 10:00 MUST NOT be offered

#### Scenario: Otro paciente diferente pide turno a la misma hora

- GIVEN patient A has an appointment on Tuesday 19/05 at 10:00 with Eli
- AND patient B (different patient) asks for an appointment on Tuesday 19/05 at 10:00
- WHEN `check_availability` is called for patient B
- THEN 10:00 MUST be offered as available (different patient can use the same slot)
- AND only professional availability constraints apply

## MODIFIED Requirements

### Requirement: Preservar patient_id en patient lookup

The patient lookup in `check_availability` SHALL preserve `p.id` from the query result for use in the patient conflict guard, in addition to the existing `assigned_professional_id` and `unpaid` fields.

(Previously: `patient_row["id"]` was only used for the SQL GROUP BY and was discarded after extracting `assigned_professional_id` and debt info.)

#### Scenario: Patient lookup succeeds

- GIVEN a patient exists with `p.id = 19` for `phone = +5493434732389`
- WHEN `check_availability` performs the patient lookup
- THEN `_ca_patient_id` MUST be set to 19
- AND the patient conflict guard MUST use this value

#### Scenario: Patient lookup fails or no patient found

- GIVEN no patient is found for the given phone number
- WHEN `check_availability` performs the patient lookup
- THEN `_ca_patient_id` MUST be `None` or undefined
- AND the patient conflict guard MUST be skipped gracefully

### Matriz de casos completa

| Escenario | Profesional | ¿Se ofrece? | Regla |
|-----------|-------------|------------|-------|
| Mismo paciente, misma hora | Mismo prof | ❌ No | Profesional ocupado (ya funciona) |
| Mismo paciente, misma hora | Distinto prof | ❌ No | **Paciente ocupado (este fix)** |
| Mismo paciente, distinta hora | Cualquiera | ✅ Sí | Válido |
| Mismo paciente, otro día | Cualquiera | ✅ Sí | Sin conflicto |
| Distinto paciente, misma hora | Mismo prof | ❌ No | Profesional ocupado (ya funciona) |
| Distinto paciente, misma hora | Distinto prof | ✅ Sí | Multi-silla válido |
| Distinto paciente, distinta hora | Cualquiera | ✅ Sí | Sin conflicto |

## Coverage Summary

| Type | Count |
|------|-------|
| New requirements | 1 |
| Modified requirements | 1 |
| Happy path scenarios | 4 |
| Edge case scenarios | 1 |
| Casos en matriz | 7 |
