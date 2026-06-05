# Reschedule & Cancellation Guard Specification

## Purpose
Ensure `BookingAgent` does not reschedule, cancel, or confirm slots when the patient has no active future appointments, preventing slot hallucinations and tool bypasses.

## Business Logic
| Input Scenario | Validation Rule | Action / Guardrail |
|----------------|-----------------|--------------------|
| Request reschedule/cancel | MUST call `list_my_appointments` first | Verify patient's upcoming appointments |
| No future appointments found | PROHIBITED from calling `confirm_slot`, `book_appointment`, `cancel_appointment`, or `reschedule_appointment` | Inform patient of no active bookings |
| Request reschedule + no future appointments | Redirect to regular booking flow | Ask for preferred day/time and call `check_availability` |
| Request cancellation + no future appointments | Inform no active bookings exist | Ask if they want to schedule a new appointment |

## Guardrails
- **No Direct Book/Confirm**: BookingAgent SHALL NOT execute `confirm_slot` or `book_appointment` if the user message requests a reschedule or cancel but `list_my_appointments` returned no future appointments.
- **Strict Verification**: Every reschedule or cancellation request MUST trigger `list_my_appointments` to prevent conversation-level hallucinations.

## Acceptance Criteria (Gherkin)

### Scenario 1: Patient requests reschedule, has exactly one future appointment
- GIVEN a patient has exactly one future appointment in the system
- WHEN the patient requests to reschedule their appointment
- THEN the agent MUST call `list_my_appointments` to retrieve the appointment details
- AND the agent MUST confirm the exact details (date, time, treatment) before calling `cancel_appointment` for the existing slot and checking availability for the new slot

### Scenario 2: Patient requests reschedule, has NO future appointments
- GIVEN a patient has no future appointments in the system
- WHEN the patient requests to reschedule their appointment
- THEN the agent MUST call `list_my_appointments` and find no future appointments
- AND the agent MUST inform the patient that no active bookings were found
- AND the agent MUST ask for preferred day and time to start a fresh booking flow

### Scenario 3: Patient requests cancellation, has NO future appointments
- GIVEN a patient has no future appointments in the system
- WHEN the patient requests to cancel their appointment
- THEN the agent MUST call `list_my_appointments` and find no future appointments
- AND the agent MUST inform the patient that no active bookings exist
- AND the agent MUST ask if they would like to schedule a new appointment
