# Delta for Booking and Slot-Locking System

## Purpose
Prevent routing amnesia, routing loops, and tool invocation loops when a patient has pre-reserved a slot (`SLOT_LOCKED` state) by restricting supervisor routing, injecting explicit context hints, and constraining the agent's prompts and tools.

## ADDED Requirements

### Requirement: Supervisor Slot Lock Bypass Routing
When a patient's session state is `SLOT_LOCKED`, the routing supervisor MUST bypass LLM-based routing and route all incoming messages directly to the `booking` agent.
- Exception: If the patient's message matches human handoff keywords or intent (e.g., requests a human operator), the supervisor SHALL route to the `human_intervention` handler instead.
- If Redis queries fail, the system SHALL log the warning and fall back to dynamic LLM-based routing.

#### Scenario: Routing to booking during slot lock
- GIVEN a patient session in `SLOT_LOCKED` state
- WHEN the patient sends a text message or document
- THEN the supervisor MUST route the message directly to the `booking` agent
- AND bypass dynamic LLM routing.

#### Scenario: Human handoff exception during slot lock
- GIVEN a patient session in `SLOT_LOCKED` state
- WHEN the patient sends a message saying "Quiero hablar con una persona"
- THEN the supervisor MUST route to the human intervention handler.

---

### Requirement: Buffer Task State Hint Injection
The task buffering system in `buffer_task.py` MUST inject a detailed `state_hint` when the patient's state is `SLOT_LOCKED`.
- The hint MUST contain:
  1. Notification that the patient has a slot pre-reserved (locked).
  2. The details of the locked slot (date, time, professional/service if available).
  3. Strict instructions to focus solely on collecting the missing patient DNI and full name.
  4. Prohibitions against offering new slots or searching availability.

#### Scenario: Slot Locked state hint injection
- GIVEN a patient session in `SLOT_LOCKED` state with a pre-reserved slot for Oct 10th at 15:00
- WHEN a message is processed by `buffer_task.py`
- THEN the system MUST inject the `state_hint` with details of the Oct 10th 15:00 slot
- AND command the LLM to only ask for the patient's name and DNI.

---

### Requirement: Booking Agent Tool and Re-offer Restriction
Under `SLOT_LOCKED` state, the `BookingAgent` in `specialists.py` and the monolithic agent in `main.py` MUST NOT call `check_availability` or offer alternative slot options unless the patient explicitly requests to reschedule.
- The agents MUST insist on collecting the missing name and DNI digits to confirm the existing lock.
- If the patient gives non-digit confirmation (e.g., "Así es") when asked for DNI, the agent MUST insist on numeric DNI inputs.

#### Scenario 1: User asks about insurance during slot lock
- GIVEN a session in `SLOT_LOCKED` state with missing DNI
- WHEN the user asks "Aceptan OSDE?"
- THEN the agent MUST answer the coverage question
- AND immediately request the missing DNI without searching for other slots.

#### Scenario 2: User provides name but no DNI during slot lock
- GIVEN a session in `SLOT_LOCKED` state with missing DNI
- WHEN the user replies with their name "Adrián"
- THEN the agent MUST confirm receipt of the name
- AND immediately ask for the numeric DNI
- AND MUST NOT call `check_availability` or re-offer slots.

#### Scenario 3: User provides ambiguous validation instead of DNI digits
- GIVEN a session in `SLOT_LOCKED` state with missing DNI
- WHEN the agent asks for DNI and the user replies "Así es"
- THEN the agent MUST politely insist on receiving the DNI numbers
- AND MUST NOT restart the slot selection or check availability.
