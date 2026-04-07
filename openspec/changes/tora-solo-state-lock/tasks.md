# Tasks — C2: TORA-Solo State Lock + Date Validator

**Change ID:** `tora-solo-state-lock`
**Companion:** `spec.md`, `design.md`
**Branch:** `feat/c2-tora-state-lock`

---

## Convention

- Cada tarea = 1 commit (excepto donde explícitamente se agrupan).
- Conventional commits: `fix(tora):` o `feat(tora):` o `test(tora):`.
- Tests primero o junto al código en el mismo commit (TDD del proyecto).
- Sin migraciones Alembic en este change.
- Spanish (es-AR) en mensajes de commit y comentarios.

---

## Sprint 1 — Bug #5 phone normalization (Día 1)

- [x] T1.1 Crear `tests/test_phone_normalization.py` con 5 casos edge (número con +54, con 9, con guiones, con espacios, sin prefijo).
- [ ] T1.2 Crear `tests/test_book_then_list.py` integration test: book_appointment → list_my_appointments debe retornar el turno recién creado.
- [x] T1.3 Refactor `orchestrator_service/main.py:3360-3433` (`list_my_appointments`) — usar `normalize_phone_digits()` Python antes del query, eliminar `REGEXP_REPLACE` del SQL.
- [x] T1.4 Añadir log INFO `(input_phone, normalized, results_count)` en `list_my_appointments`.
- [x] T1.5 Correr `pytest tests/test_phone_normalization.py tests/test_book_then_list.py` — todos verdes.
- [ ] T1.6 Commit: `fix(tora): bug #5 — unify phone normalization in list_my_appointments`.

---

## Sprint 2 — Bug #1 date validator (Día 2-3)

- [x] T2.1 Crear `orchestrator_service/services/date_validator.py` con dataclass `CanonicalDate` y stubs de las 2 funciones públicas.
- [x] T2.2 Crear `tests/test_date_validator.py` con 10 casos (swap claro DD↔MM, sin canónicas, múltiples fechas, fecha ya correcta, formato con weekday, formato DD/MM/YYYY, canónica ambigua, texto sin fechas, tool output sin fecha, fecha imposible).
- [x] T2.3 Implementar `extract_canonical_dates(intermediate_steps)` — parsea outputs de `check_availability`, `book_appointment`, `list_my_appointments`, `reschedule_appointment`.
- [x] T2.4 Implementar `validate_and_correct(text, canonical_dates)` — regex + swap detection + replace + logging WARNING por corrección.
- [x] T2.5 Implementar helper privado `_match_with_swap(text_date, canonicals)`.
- [x] T2.6 Correr `pytest tests/test_date_validator.py` — verdes.
- [ ] T2.7 Crear `tests/test_buffer_task_date_validator.py` con 3 casos integration (happy con corrección, happy sin corrección, error en validador → fail safe).
- [x] T2.8 Modificar `orchestrator_service/services/buffer_task.py` — llamar `date_validator.validate_and_correct` después de `executor.ainvoke()` y antes de `response_sender.send_sequence()`.
- [ ] T2.9 Correr pytest de integration — verdes.
- [ ] T2.10 Commit: `feat(tora): bug #1 — date validator post-LLM`.

---

## Sprint 3 — Bug #4 state machine (Día 4-7)

### Fase A — Module standalone (Día 4)

- [x] T3.1 Crear `orchestrator_service/services/conversation_state.py` con constants (`VALID_STATES`, `CONVSTATE_TTL`, `REDIS_KEY_PREFIX`) y stubs de `get_state`, `set_state`, `transition`, `reset`.
- [x] T3.2 Crear `tests/test_conversation_state.py` con 8 casos (get not found → IDLE, set+get roundtrip, transition happy, transition conflict returns False, reset, Redis fail en get → IDLE, Redis fail en set → warn no raise, state inválido → ValueError).
- [x] T3.3 Implementar las 4 funciones contra Redis async client. Fallback safe en todos los catch.
- [x] T3.4 Correr `pytest tests/test_conversation_state.py` — verdes.
- [x] T3.5 Commit: `feat(tora): bug #4 — conversation_state module (standalone)`.

### Fase B — Hooks en tools (Día 5)

- [x] T4.1 Hook en `check_availability` (`main.py:1291`) — `await conversation_state.set_state(..., 'OFFERED_SLOTS', last_offered_slots=[...])` al final del happy path.
- [x] T4.2 Hook en `confirm_slot` (`main.py:4504`) — `set_state('SLOT_LOCKED', last_locked_slot={...})` al final del happy path.
- [x] T4.3 Hook en `book_appointment` (`main.py:2101`) — `set_state('BOOKED')` o `set_state('PAYMENT_PENDING')` según `requires_sena`.
- [x] T4.4 Hook en `verify_payment_receipt` — `set_state('PAYMENT_VERIFIED')` en success.
- [x] T4.5 Hooks en `cancel_appointment` y `reschedule_appointment` — `reset()` al final.
- [x] T4.6 Tests unit por cada tool con mock de `conversation_state.set_state` (6 tests nuevos en `tests/test_buffer_task_state_guard.py`).
- [ ] T4.7 Smoke test manual: ejercer un booking completo y verificar que TORA sigue funcionando igual (fase write-only, sin enforcement).
- [x] T4.8 Commit: `feat(tora): bug #4 — state hooks in 6 tools (write-only mode)`.

### Fase C — Input-side guard (Día 6)

- [x] T5.1 Añadir 6 casos más a `tests/test_buffer_task_state_guard.py` para input-side (OFFERED_SLOTS+selection → hint inyectado, OFFERED_SLOTS+research → no hint, IDLE+selection → no hint, SLOT_LOCKED+selection → no hint, OFFERED_SLOTS+msg ambiguo → no hint, OFFERED_SLOTS+TTL expirado → no hint).
- [x] T5.2 Implementar `_detect_selection_intent(msg)` con regex compilada a nivel módulo en `buffer_task.py`.
- [x] T5.3 Implementar `_detect_research_intent(msg)` análogo.
- [x] T5.4 Modificar `buffer_task.py` pre-ainvoke (~line 998): leer `convstate`, si `OFFERED_SLOTS` + selection intent → inyectar bloque `[STATE_HINT: ...]` en el system prompt.
- [ ] T5.5 Correr `pytest tests/test_buffer_task_state_guard.py` — verdes.
- [ ] T5.6 Smoke manual: replay "Agéndame el del 12 de mayo" tras ver slots — verificar que el LLM va a `confirm_slot` (no re-llama `check_availability`).
- [x] T5.7 Commit: `feat(tora): bug #4 — input-side state guard with intent detection`.

### Fase D — Output-side guard (Día 7)

- [x] T6.1 Añadir 6 casos más a `tests/test_buffer_task_state_guard.py` para output-side (LLM ignora hint → retry con nudge, retry éxito → send, retry falla → degradación graceful + warn, research intent presente → no retry, state != OFFERED_SLOTS → no retry, ya se hizo 1 retry → no segundo).
- [x] T6.2 Implementar en `buffer_task.py` la inspección de `intermediate_steps` post-ainvoke: si state previo era `OFFERED_SLOTS` y se llamó `check_availability` sin research intent → retry 1x con nudge reforzado.
- [x] T6.3 Constant `MAX_STATE_RETRIES = 1` al nivel módulo.
- [x] T6.4 Logging WARNING del retry con payload `{tenant_id, phone, prev_state, tools_called, user_msg}` para análisis.
- [ ] T6.5 Correr `pytest tests/test_buffer_task_state_guard.py` — verdes (18 casos total).
- [x] T6.6 Commit: `feat(tora): bug #4 — output-side state guard with bounded retry`.

### Fase E — Integration tests + cleanup (Día 8)

- [ ] T7.1 Crear `tests/test_state_machine_e2e.py` con 5 escenarios end-to-end:
  - (a) flujo feliz: IDLE → check_availability → user picks → confirm_slot → book_appointment → BOOKED.
  - (b) re-search legítimo: IDLE → check_availability → "otra fecha" → check_availability de nuevo → state sigue OFFERED_SLOTS.
  - (c) abandono: IDLE → check_availability → sin actividad 30min → TTL expira → vuelta implícita a IDLE.
  - (d) intent ambiguo: IDLE → check_availability → user dice "1" → guard inyecta hint → LLM va a confirm_slot.
  - (e) cancel: BOOKED → cancel_appointment → IDLE.
- [ ] T7.2 Correr `pytest tests/test_state_machine_e2e.py` — verdes.
- [ ] T7.3 (Opcional) Hardening del system prompt en `main.py:6713-6840`: añadir "Al mencionar una fecha, copiala exactamente como apareció en el último resultado de check_availability".
- [ ] T7.4 Commit: `test(tora): bug #4 — state machine e2e + optional prompt hardening`.

---

## Sprint 4 — Verificación final

- [ ] V1 Replay completo de la conversación de Juan Román Riquelme (fixture de regression):
  - Cero ocurrencias de "Sábado 05/12".
  - "Agéndame el del 12 de mayo" llega efectivamente a `book_appointment`.
  - `list_my_appointments` retorna el turno creado.
- [ ] V2 Run full `pytest` suite — cero regresiones en tests existentes.
- [ ] V3 Code review interno de la rama.
- [ ] V4 Merge PR a `main`.

---

## Definition of Done

- [ ] Los commits de los 4 sprints están en la rama `feat/c2-tora-state-lock`.
- [ ] Todos los tests pasan (unit + integration + e2e) — 45 casos totales.
- [ ] Smoke conversacional reproduce 0 de los 3 bugs del scope (#1, #4, #5).
- [ ] PR aprobado y mergeado a `main`.
- [ ] No `CLAUDE.md` update en C2 (se actualiza al cierre del umbrella en C3).
- [ ] Sin migraciones Alembic nuevas (confirmado).
- [ ] Redis namespace `convstate:*` operativo en el entorno de staging con TTL verificado.
