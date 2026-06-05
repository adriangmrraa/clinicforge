# Exploration: Booking Omission and Reschedule Fallback Fixes

## Current State

We are addressing two critical bugs in the AI Agent booking and reschedule workflows:

### Issue 1: Omission of `book_appointment` after providing DNI
When a patient chooses a slot, the slot is locked temporarily via `confirm_slot` and they are asked to provide their name/surname and DNI to complete the booking. When they provide their DNI, the LLM is often distracted by:
1. **Clinical data/visual descriptions** present in the user's message (e.g. descriptions of teeth, x-rays, or symptoms).
2. **Existing profile context** or other rules in the system prompt.
3. The **"Detección de Paciente Existente" (Migration)** rule.

This distraction leads to the LLM responding with a conversational message instead of executing the `book_appointment` tool call. Since the tool call is omitted, the slot expires after 5 minutes, turn amnesia occurs, and the "Detección de Paciente Existente" rule may trigger incorrectly because the LLM is confused about whether the patient already has an active registration or history.

#### Causa Raíz
The system prompts (both the solo prompt generated in `main.py` and the `BookingAgent` prompt in `specialists.py`) do not prioritize the execution of `book_appointment` when the user provides the final required booking data (such as DNI). The agent lacks a "Tool-First Execution" directive for the final phase of agendamiento. The prompt contains complex rules (e.g., migration, emotional flows) that run concurrently, and without an explicit order of execution, the LLM prioritizes conversational outputs or other rule checks.

### Issue 2: Unilateral booking during rescheduling
When a patient requests to reschedule ("reprogramar"), the agent is expected to:
1. Identify the current upcoming appointment by calling `list_my_appointments`.
2. Check new availability by calling `check_availability`.
3. Call `reschedule_appointment` once the patient selects a new slot.

However, if `list_my_appointments` returns empty (meaning the patient has no future active appointments in the system), the agent is supposed to notify the patient and offer a standard booking flow. Instead, the agent hallucinates/books a slot directly (calling `book_appointment` or attempting `reschedule_appointment` on a non-existent original appointment).

#### Causa Raíz
In `main.py` under the "REPROGRAMAR TURNO" section and in `specialists.py` under the "CANCELACIÓN Y REPROGRAMACIÓN" instructions, there is no fallback rule defined for the case where `list_my_appointments` does not return any active upcoming appointments (i.e., when the list is empty). Without guidance, the LLM tries to execute a reschedule flow using fake/hallucinated original appointment details, or falls back to an incorrect unilateral `book_appointment` call.

---

## Affected Areas

- **`orchestrator_service/main.py`**:
  - `build_system_prompt()` function:
    - Update `PASO 4b: DATOS DE ADMISIÓN` / `PASO 4c: RESERVA TEMPORAL` to include strict guidelines for calling `book_appointment` immediately upon DNI submission, bypassing clinical distraction and migration rules.
    - Update `REPROGRAMAR TURNO (flujo obligatorio)` to handle the fallback when `list_my_appointments` returns empty.
- **`orchestrator_service/agents/specialists.py`**:
  - `BookingAgent` system prompt:
    - Add a strict instruction for confirming with DNI in the booking state machine, enforcing tool calling before any conversational response.
    - Add a fallback rule for rescheduling when `list_my_appointments` returns no upcoming appointments.

---

## Approaches

### Approach A (Recommended)
Add explicit and block-level rules in both system prompts that:
1. Force tool execution (`book_appointment` / `confirm_slot`) **first** and **without delay** when a DNI is provided during booking.
2. Explicitly bypass the migration checks and clinical distraction responses in the confirmation turn.
3. Explicitly intercept empty upcoming appointment lists in the rescheduling flow and redirect the conversation to asking the patient if they want to schedule a new appointment from scratch.

*   **Pros**: Highly targeted, minimum changes in code architecture, low-risk, resolves the issues immediately by refining prompt steering.
*   **Cons**: Relies on prompt engineering; needs clear, unambiguous wording.
*   **Effort**: Low.

### Approach B
Implement programmatical intercepts in the orchestrator before passing messages to LLMs (e.g., if a slot is pre-reserved and DNI pattern is found, hardcode the tool call).
*   **Pros**: 100% reliable execution.
*   **Cons**: High architectural complexity, bypasses LLM reasoning, hard to handle edge cases where the DNI might not be for booking or is ambiguous.
*   **Effort**: High.

---

## Recommendation

**Approach A** is recommended. The project relies on LangChain agents guided by detailed prompt state machines. Adding strict execution overrides is the standard practice in this codebase (like the `REGLA CERO` and `REGLA DE NO-ELECCIÓN`).

## Ready for Proposal
Yes.
