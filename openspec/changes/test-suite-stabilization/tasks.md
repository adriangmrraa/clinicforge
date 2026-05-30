# Tasks: test-suite-stabilization

Order matters: C0 → C1 → C2 → resto en paralelo. C7/C8 al final porque pueden generar cambios de producción.

## Phase C0 — Limpieza de archivos huérfanos (precondición)

- [ ] C0.1 `git rm tests/test_tiendanube.py` (servicio inexistente, confirmado por `ls tiendanube_service` → no existe)
- [ ] C0.2 Decidir destino de `tests/test_whatsapp.py`: mover a `whatsapp_service/tests/` con su propio `pytest.ini` y `prometheus_client` en `requirements-dev.txt`, o agregar a `collect_ignore_glob` en `pytest.ini` raíz
- [ ] C0.3 Decidir destino de `tests/test_telegram_multimedia.py`: si el bot de Telegram sigue activo (verificar con `rg "telegram_bot" orchestrator_service/`), actualizar el patch path; si no, `git rm`
- [ ] C0.4 Correr `pytest tests/ -q --tb=no` y confirmar baseline post-cleanup

**Commit:** `chore(tests): remove orphan test files (tiendanube, whatsapp, telegram)`

## Phase C1 — tenants fixture canónica (~20 fallos)

- [ ] C1.1 Crear `tests/fixtures/__init__.py`
- [ ] C1.2 Crear `tests/fixtures/tenants.py` con `make_tenant_row(**overrides)` cubriendo TODAS las columnas NOT NULL de `tenants` (inspeccionar `orchestrator_service/models.py::Tenant`)
- [ ] C1.3 Exponer `tenant_factory` fixture en `tests/conftest.py` que use el helper
- [ ] C1.4 Refactorizar `tests/test_holiday_service.py` (~12 tests) para usar `tenant_factory`
- [ ] C1.5 Refactorizar `tests/test_admin_holidays.py` (~4 tests) idem
- [ ] C1.6 Refactorizar `tests/test_book_appointment_holiday.py` (~4 tests) idem
- [ ] C1.7 Refactorizar `tests/test_check_availability_holiday.py` (~4 tests) idem
- [ ] C1.8 Verificar `pytest tests/test_holiday_service.py tests/test_admin_holidays.py tests/test_book_appointment_holiday.py tests/test_check_availability_holiday.py -q` → 0 failed

**Commit:** `test(fixtures): add canonical tenants factory + fix C1 KeyError 'language' bucket`

## Phase C2 — db.pool en endpoint tests (~12 fallos)

- [ ] C2.1 Diagnosticar `tests/test_orchestrator.py::test_auth_internal_required` — leer el setup actual y entender por qué `db.pool` es None
- [ ] C2.2 Decidir estrategia: `LifespanManager` vs `AsyncMock` para `db.pool` (probablemente Mock para unit, real para integration)
- [ ] C2.3 Agregar fixture `app_with_mock_pool` en `tests/conftest.py`
- [ ] C2.4 Refactorizar `tests/test_orchestrator.py` (2 tests) para usar el fixture
- [ ] C2.5 Refactorizar `tests/test_state_machine_e2e.py` (4 tests) — decidir si son unit o integration; si integration, marcar `@pytest.mark.integration` y usar `real_db_pool`
- [ ] C2.6 Refactorizar `tests/test_payment_email_integration.py` (2 tests) idem
- [ ] C2.7 Refactorizar `tests/test_odontogram_endpoints.py` (8 tests) idem
- [ ] C2.8 Verificar suite parcial → 0 failed en estos archivos

**Commit:** `test(infra): add app_with_mock_pool fixture + fix C2 NoneType.fetchrow bucket`

## Phase C3 — Patches a símbolos removidos (~7 fallos)

- [ ] C3.1 `tests/test_greeting_state.py` — buscar dónde vive `get_redis` ahora en `services/greeting_state.py`, actualizar todos los `monkeypatch.setattr` (~6 tests)
- [ ] C3.2 Verificar suite parcial → 0 failed

**Commit:** `test(greeting-state): repoint patches to current module symbols`

## Phase C4 — Guardrails brittle (~5 fallos)

- [ ] C4.1 Crear `tests/helpers/medical_guardrails.py` con `DANGEROUS_MEDICAL_PATTERNS` regex list
- [ ] C4.2 Refactorizar `tests/test_clinic_special_conditions.py::TestAntiMedicalAdviceGuardrails` (4 tests) para usar pattern matching contextual
- [ ] C4.3 Refactorizar `tests/test_clinic_special_conditions_e2e.py::test_no_medical_advice_in_full_pipeline` o marcarlo `@pytest.mark.e2e` si necesita LLM real
- [ ] C4.4 Verificar → 0 failed

**Commit:** `test(guardrails): replace substring guards with contextual regex patterns`

## Phase C5 — Migration loader (~2 fallos)

- [ ] C5.1 Localizar el loader en `tests/test_payment_financing_migration.py`
- [ ] C5.2 Slugify el `name` del `spec_from_file_location` (`-` → `_`)
- [ ] C5.3 Verificar → 0 failed

**Commit:** `test(migration-loader): slugify module names with hyphens`

## Phase C6 — Tool signature (~1 fallo)

- [ ] C6.1 Leer firma actual de `verify_payment_receipt` tool en `orchestrator_service/main.py`
- [ ] C6.2 Actualizar `tests/test_treatments_validator.py::TestPriceScaleValidator::test_normal_price_passes` con la firma correcta (eliminar `receipt_description` o renombrar al arg actual)
- [ ] C6.3 Verificar → 0 failed

**Commit:** `test(treatments-validator): align tool call signature with current API`

## Phase C7 — State machine semántica (~10 fallos) ⚠️

**Per-test investigation. NO blanket fix.**

- [ ] C7.1 Leer `services/state_machine.py` y `services/buffer_task.py` para entender cuándo se setea cada estado
- [ ] C7.2 `test_buffer_task_state_guard.py::TestStateHooksInTools::test_check_availability_sets_offered_slots_state` — investigar por qué no setea OFFERED_SLOTS. ¿Regresión del pack `tora-solo-state-lock`?
- [ ] C7.3 Mismo para `test_confirm_slot_sets_locked_state`
- [ ] C7.4 Mismo para `test_book_appointment_sets_booked_state`
- [ ] C7.5 Mismo para `test_book_appointment_sets_payment_pending_state`
- [ ] C7.6 Mismo para `test_verify_payment_receipt_sets_payment_verified_state`
- [ ] C7.7 Mismo para `test_cancel_appointment_resets_state`
- [ ] C7.8 Mismo para `test_reschedule_appointment_resets_state`
- [ ] C7.9 `test_state_machine_e2e.py::test_happy_flow_idle_to_booked` — happy path completo, alta señal de regresión real
- [ ] C7.10 Para cada test del bucket: si bug real → fix en producción, si refactor intencional → actualizar test con justificación en commit message
- [ ] C7.11 Documentar cualquier bug encontrado en `openspec/changes/test-suite-stabilization/findings.md`
- [ ] C7.12 Verificar → 0 failed

**Commits:** uno por test (o agrupados por causa raíz). Mensajes deben distinguir `fix(state-machine): ...` (producción) de `test(state-machine): align with intentional refactor`.

## Phase C8 — Guards textuales + intent detector (~13 fallos)

- [ ] C8.1 `test_agent_behavioral_correction.py::test_no_extra_slots_phrase` — `rg "turnos m.s disponibles" orchestrator_service/main.py`, eliminar la frase del system prompt, reemplazar por la formulación aprobada del pack `tora-solo-quick-wins`
- [ ] C8.2 `test_agent_behavioral_correction.py::test_copay_notes_are_used` — leer test, identificar qué espera, fix en código o test según corresponda
- [ ] C8.3 `test_buffer_task_state_guard.py::TestIntentDetection` (3 tests) — extender `_detect_selection_intent` con regex para ordinales: `el 1`, `el 1ro`, `el primero`, `la primera`, `el segundo`, etc.
- [ ] C8.4 Resto del bucket C8 — analizar individualmente
- [ ] C8.5 Verificar → 0 failed

**Commits:** `fix(prompt): remove deprecated 'turnos más disponibles' phrase`, `feat(intent-detector): support Spanish ordinals (el 1ro, el primero...)`.

## Phase Z — Verificación final

- [ ] Z.1 `pytest tests/ -q --tb=no` → reportar `0 failed`
- [ ] Z.2 Correr la suite 3 veces seguidas para descartar flakiness
- [ ] Z.3 `pytest tests/ -m integration -q` (con Postgres local) → 0 failed
- [ ] Z.4 Actualizar `pytest.ini` con `markers` documentados y `addopts = -m "not integration and not e2e"` para que el default sea unit-only
- [ ] Z.5 Update `CLAUDE.md` con nota: "suite verde como gate, integration tests gated por env var"
- [ ] Z.6 Save engram memory `sdd/test-suite-stabilization/completed`
- [ ] Z.7 Archive change

## Out of scope (recordatorio)

- Migración langchain
- Nuevo CI pipeline
- Tests de cobertura nuevos
- Refactor del state machine más allá de lo necesario para que los tests legítimos pasen
