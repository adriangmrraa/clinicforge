# Tasks: Booking Loop and Slot-Locked Fixes

## Phase 1: Setup / Foundation

- [x] 1.1 Verify imports and dependencies for Redis state retrieval (`get_state`) in `orchestrator_service/agents/supervisor.py`.

## Phase 2: Core Implementation

- [x] 2.1 Modify `orchestrator_service/agents/supervisor.py`: Fetch Redis state inside `route()`. If `SLOT_LOCKED`, route to `booking` directly.
- [x] 2.2 Add handoff exception in `orchestrator_service/agents/supervisor.py`: Route to `handoff` if the user message matches `HANDOFF_PATTERNS`.
- [x] 2.3 Modify `orchestrator_service/services/buffer_task.py`: Build and inject the `state_hint` when the active state is `SLOT_LOCKED`.
- [x] 2.4 Include details of `last_locked_slot` (date, time, professional, treatment) and instructions to collect numeric DNI/name in the `state_hint`.
- [x] 2.5 Modify `orchestrator_service/main.py`: Inject strict prompt rules for `SLOT_LOCKED` state under `build_system_prompt()`.
- [x] 2.6 Modify `orchestrator_service/agents/specialists.py`: Add the identical `SLOT_LOCKED` rules to the `BookingAgent` system prompt.

## Phase 3: Testing / Verification

- [x] 3.1 Create `orchestrator_service/tests/test_slot_locked_fixes.py` to unit test the deterministic routing in `SupervisorAgent.route()`.
- [x] 3.2 Implement tests in `test_slot_locked_fixes.py` for supervisor routing exception (message matching handoff keywords routes to `handoff`).
- [x] 3.3 Add tests in `test_slot_locked_fixes.py` to verify that `buffer_task` correctly builds the `state_hint` from `last_locked_slot` details.
- [x] 3.4 Run tests: `pytest orchestrator_service/tests/test_slot_locked_fixes.py` to verify all routing and hint injection tests pass.

## Phase 4: Cleanup / Documentation

- [x] 4.1 Add inline comments in modified files documenting the routing bypass and context hint injection mechanism.
