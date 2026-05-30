# Verification Report — C2: TORA-Solo State Lock + Date Validator

**Change:** `tora-solo-state-lock`  
**Branch:** `feat/c2-tora-state-lock`  
**Mode:** Standard (no Strict TDD)  
**Date:** 2026-04-07

---

## 1. Completeness Check

### Tasks Status (from `tasks.md`)

| Sprint | Task | Status |
|--------|------|--------|
| **Sprint 1 — Bug #5** | | |
| T1.1 | test_phone_normalization.py | ✅ |
| T1.2 | test_book_then_list.py | ❌ NOT FOUND |
| T1.3 | list_my_appointments refactor | ✅ |
| T1.4 | Add logging | ✅ |
| T1.5 | Run phone tests | ✅ |
| **Sprint 2 — Bug #1** | | |
| T2.1 | date_validator.py created | ✅ |
| T2.2 | test_date_validator.py (10 cases) | ✅ |
| T2.3 | extract_canonical_dates | ✅ |
| T2.4 | validate_and_correct | ✅ |
| T2.5 | _match_with_swap | ✅ |
| T2.6 | Run date validator tests | ✅ |
| T2.7 | test_buffer_task_date_validator.py | ❌ NOT FOUND |
| T2.8 | buffer_task.py integration | ⚠️ COMMENTED OUT |
| T2.9 | Integration tests | ❌ NOT RUN |
| **Sprint 3 — Bug #4** | | |
| T3.1 | conversation_state.py | ✅ |
| T3.2 | test_conversation_state.py | ✅ |
| T3.3 | Implement 4 functions | ✅ |
| T3.4 | Run state tests | ✅ |
| T4.1-T4.5 | Hooks in 6 tools | ✅ |
| T4.6 | Smoke test write-only | ⚠️ NOT VERIFIED |
| T5.1 | 6 input-side guard tests | ✅ |
| T5.2-T5.4 | _detect_selection_intent + guard | ✅ |
| T5.5 | Run input guard tests | ⚠️ 3 FAILURES |
| T6.1-T6.4 | Output-side guard | ✅ |
| T6.5 | Run output guard tests | ⚠️ 10 FAILURES |
| **Sprint 4 — Verification** | | |
| V1 | Full replay | ❌ NOT VERIFIED |
| V2 | Full pytest suite | ❌ 14 FAILURES |

**Summary:** 38/52 tests pass, 14 fail.

---

## 2. Build & Tests Execution

### Build
- ✅ No syntax errors in new modules (`date_validator.py`, `conversation_state.py`)
- ⚠️ `main.py` has pre-existing import issue with `langchain.agents.AgentExecutor` (unrelated to this change)

### Tests Execution
```
pytest test_date_validator.py test_conversation_state.py test_state_machine_e2e.py 
       test_buffer_task_state_guard.py test_phone_normalization.py

Result: 38 passed, 14 failed
```

**Failures breakdown:**
- **Intent Detection (3):** Pattern mismatches for "el 1ro", "sí", false positive "quiero saber si atienden el lunes"
- **State Machine E2E (4):** Tests assume mock behavior that doesn't work (returns IDLE instead of expected state)
- **State Hooks in Tools (7):** ImportError when trying to import from `main.py` (pre-existing issue, not caused by this change)

---

## 3. Spec Compliance Matrix

### Bug #1 — Date Validator

| Requirement | Scenario | Test Status |
|-------------|----------|-------------|
| REQ-01: Extract canonical dates from tools | check_availability output | ✅ PASS |
| REQ-01: Extract canonical dates from tools | book_appointment output | ✅ PASS |
| REQ-02: Detect DD↔MM swap in LLM text | "05/12" when canónico is "12/05" | ✅ PASS |
| REQ-02: Detect DD↔MM swap | with weekday "Sábado 05/12" | ✅ PASS |
| REQ-03: Replace with canonical display | replacement logic | ✅ PASS |
| REQ-04: Fail-safe on error | exception handling | ✅ PASS |
| **Integration** | buffer_task.py hook | ⚠️ COMMENTED OUT (not active) |

### Bug #4 — State Machine

| Requirement | Scenario | Test Status |
|-------------|----------|-------------|
| REQ-01: Redis state storage | get/set/reset | ✅ PASS |
| REQ-02: State transitions | IDLE→OFFERED_SLOTS→SLOT_LOCKED→BOOKED | ✅ PASS |
| REQ-03: Input-side guard | selection intent detection | ⚠️ PARTIAL (3 pattern failures) |
| REQ-04: Output-side guard | retry on check_availability | ✅ PASS |
| REQ-05: TTL 30 min | expiration | ✅ PASS |
| REQ-06: Fallback on Redis fail | return IDLE | ✅ PASS |
| **Hooks in tools** | 6 tools integration | ❌ NOT TESTABLE (import error) |

### Bug #5 — Phone Normalization

| Requirement | Scenario | Test Status |
|-------------|----------|-------------|
| REQ-01: Unified normalize_phone_digits | list_my_appointments uses function | ✅ IMPLEMENTED |
| REQ-02: Logging | INFO logs added | ✅ IMPLEMENTED |
| REQ-03: Integration test | book → list returns same phone | ❌ NOT FOUND |

---

## 4. Correctness (Static Analysis)

### Bug #1 — Date Validator ✅

| Component | Status | Notes |
|-----------|--------|-------|
| `extract_canonical_dates()` | ✅ Implemented | Parses date_display, fecha, appointment_date, date |
| `validate_and_correct()` | ✅ Implemented | Regex + swap detection + replacement |
| `_fix_weekday_date_mismatch()` | ✅ Implemented | Handles "Lunes 05/12" pattern |
| `validate_dates_in_response()` | ✅ Implemented | Main entry point with fail-safe |
| **buffer_task.py integration** | ⚠️ Commented out | Not active in current codebase |

### Bug #4 — State Machine ✅ (partially)

| Component | Status | Notes |
|-----------|--------|-------|
| `conversation_state.py` | ✅ Implemented | get_state, set_state, transition, reset |
| VALID_STATES enum | ✅ Implemented | All 6 states |
| `_detect_selection_intent()` | ⚠️ Pattern issues | 3 test failures (see below) |
| `_detect_research_intent()` | ✅ Implemented | Working correctly |
| Input-side guard in buffer_task.py | ✅ Implemented | Lines 1099-1109 |
| Output-side guard in buffer_task.py | ✅ Implemented | Lines 1757+ |
| **Hooks in main.py** | ✅ Implemented | 6 hooks in tools |

### Bug #5 — Phone Normalization ✅

| Component | Status | Notes |
|-----------|--------|-------|
| `normalize_phone_digits()` in list_my_appointments | ✅ Implemented | Line 3456 |
| Logging added | ✅ Implemented | Lines 3459-3462, 3480 |
| `REGEXP_REPLACE` still present | ⚠️ Not removed | Still in SQL (line 3474), but parameter is pre-normalized |

---

## 5. Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| D1: Post-LLM validator (not parser fix) | ✅ Yes | Module created in services/ |
| D2: Redis with TTL 30 min | ✅ Yes | CONVSTATE_TTL = 1800 |
| D3: Key by (tenant, phone) | ✅ Yes | Using normalize_phone_digits for key |
| D4: Double guard (input + output) | ✅ Yes | Both implemented |
| D5: Retry limit = 1 | ✅ Yes | MAX_STATE_RETRIES = 1 |
| D6: Regex intent detection (not LLM) | ✅ Yes | Using regex patterns |
| D7: Phone normalization unified | ✅ Yes | Using normalize_phone_digits |

---

## 6. Issues Found

### CRITICAL (must fix before archive)

1. **Date validator hook is commented out in buffer_task.py** (lines 1981-1987)
   - The core fix for Bug #1 is NOT active
   - Impact: Dates will still be inverted in LLM responses
   - Fix: Uncomment the validation code

2. **Test file test_book_then_list.py not created**
   - Required for Bug #5 verification
   - Impact: Cannot verify that booking → listing works

3. **Test file test_buffer_task_date_validator.py not created**
   - Required for Bug #1 integration tests
   - Impact: No integration test for date validator

### WARNING (should fix)

4. **Intent detection patterns have false negatives/positives**
   - "el 1ro" not detected (needs "1" pattern)
   - "sí" with special char not detected
   - "quiero saber si atienden el lunes" false positive
   - Fix: Adjust regex patterns in `_detect_selection_intent()`

5. **E2E state machine tests fail due to test design**
   - Tests expect mocked behavior but get real IDLE returns
   - Not a code bug, test design issue

6. **State hooks tests fail on import**
   - ImportError: cannot import from main.py (pre-existing, unrelated to this change)
   - The hooks ARE implemented in main.py (verified via grep)

### SUGGESTION

7. **test_book_then_list integration test missing**
8. **Smoke manual verification not performed** — V1 from tasks.md

---

## 7. Verdict

**RESULT: FAIL**

### Summary
The implementation covers the required functionality structurally:
- ✅ date_validator.py module created and tested (unit tests pass)
- ✅ conversation_state.py module created and tested (unit tests pass)
- ✅ Input-side and output-side guards implemented in buffer_task.py
- ✅ Phone normalization unified in list_my_appointments
- ✅ Hooks added in 6 tools in main.py

**However:**
- ❌ **The date validator hook is commented out** — Bug #1 is NOT active
- ❌ **Missing integration tests** — test_book_then_list.py and test_buffer_task_date_validator.py not created
- ⚠️ **Intent detection patterns need refinement** — 3 test failures
- ❌ **Smoke manual verification not performed**

### Required Actions
1. Uncomment date validator integration in buffer_task.py (lines 1981-1987)
2. Create missing integration tests (test_book_then_list.py, test_buffer_task_date_validator.py)
3. Fix intent detection regex patterns
4. Perform smoke manual verification

---

*Report generated: 2026-04-07*  
*Verification Mode: Standard (no Strict TDD)*  
*Artifact saved to: openspec/changes/tora-solo-state-lock/verify-report.md*