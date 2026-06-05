# Tasks: Booking Omission and Reschedule Fallback Fixes

## Phase 1: Core Prompt Updates (Agent Prompts)

- [x] 1.1 Inject the `⚠️ REGLA DE CONFIRMACIÓN CON DNI` and `⚠️ FALLBACK SI NO TIENE TURNOS FUTUROS ACTIVOS` blocks into the `_base_prompt` within `build_system_prompt()` in `orchestrator_service/main.py`.
- [x] 1.2 Inject the same two rules (`⚠️ REGLA DE CONFIRMACIÓN CON DNI` and `⚠️ FALLBACK SI NO TIENE TURNOS FUTUROS ACTIVOS`) in the `BookingAgent` system prompt inside `orchestrator_service/agents/specialists.py`.
- [x] 1.3 Add a booking routing rule when a DNI or document is provided under `Reglas obligatorias` in the LLM routing rules of `orchestrator_service/agents/prompts/supervisor.md`.

## Phase 2: Supervisor Routing Rule Implementation

- [x] 2.1 Insert the deterministic priority check for DNI patterns and keywords inside the `route()` method of `SupervisorAgent` in `orchestrator_service/agents/supervisor.py` immediately before checking `EMERGENCY_PATTERNS`.

## Phase 3: Verification / Testing Tasks

- [x] 3.1 Test Scenario 1: Confirm instant booking by sending a DNI together with clinical text (e.g. pain) to verify that `book_appointment` is called immediately without triage detour.
- [x] 3.2 Test that providing a DNI and name during booking confirmation does not trigger the patient migration flow.
- [x] 3.3 Test Scenario 2: Request rescheduling when no upcoming appointments exist, verifying the agent informs the patient and offers to book a new appointment instead of calling `reschedule_appointment` unilaterally.
