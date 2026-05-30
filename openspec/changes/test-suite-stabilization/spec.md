# Spec: test-suite-stabilization

## Requirements

### REQ-TS-1: Suite verde como gate
`pytest tests/` (sin flags) DEBE terminar con exit code 0 — todos los tests unit pasan, los tests integration/e2e quedan deselected por default vía marker filtering.

**Acceptance:**
- `pytest tests/ -q` reporta `0 failed`.
- `pytest tests/ -m integration` corre los integration tests cuando hay Postgres disponible (gated por `INTEGRATION_DB_URL` env var).
- `pytest tests/ -m e2e` está documentado como manual-only.

### REQ-TS-2: tenants fixture canónica
DEBE existir un único helper compartido en `tests/conftest.py` (o `tests/fixtures/tenants.py`) que cree filas de `tenants` con TODAS las columnas NOT NULL del schema actual, incluyendo `language`, `country_code`, `ai_engine_mode`, `working_hours`. Cualquier test que inserte tenants DEBE usarlo.

**Acceptance:**
- `KeyError` por columnas faltantes desaparece de los logs (bucket C1).
- El fixture acepta overrides por kwargs (`tenant_factory(language="en")`).

### REQ-TS-3: db.pool inicializado en endpoint tests
Los tests que invocan endpoints FastAPI o tools que tocan `db.pool` DEBEN:
- Usar el fixture `mock_db_pool` (existente en `conftest.py`) cuando son tests unit, O
- Marcarse `@pytest.mark.integration` y usar `real_db_pool` (existente) cuando necesitan DB real.

NO DEBE haber tests que llamen `db.pool.fetchrow` sin uno de los dos paths.

### REQ-TS-4: Patches alineados con código actual
Los `monkeypatch.setattr` y `mocker.patch` DEBEN apuntar a símbolos que EXISTEN en el código actual. Tests que patchean atributos removidos DEBEN actualizarse al nuevo path o eliminarse si el feature ya no existe.

### REQ-TS-5: Guardrails textuales con regex no-substring
Los tests de guardrail (bucket C4) DEBEN usar regex con word boundaries o pattern matching contextual, NO `substring not in output`. La palabra "peligroso" puede aparecer legítimamente en `"peligroso para la clínica"` cuando el contexto es información operacional, no consejo médico.

### REQ-TS-6: Migration test loader robusto
El loader de tests de Alembic migrations DEBE manejar filenames con caracteres no-Python (guiones) usando `importlib.util.spec_from_file_location` con un `name` slug-safe.

### REQ-TS-7: Tools test signatures sincronizadas
Los tests que invocan tools de LangChain DEBEN usar la firma actual del tool (`@tool` decorator + `args_schema`). Cuando el tool elimine o renombre un arg, el test DEBE actualizarse en el mismo PR que el cambio.

### REQ-TS-8: State machine — evidencia antes de "fix"
Para los fallos del bucket C7 (state machine), el equipo DEBE:
1. Leer el código de producción que setea el estado (`buffer_task.py`, `services/state_machine.py`).
2. Determinar si el estado dejó de setearse por bug o por refactor intencional.
3. Si bug → reparar producción y dejar el test como está.
4. Si refactor → actualizar el test al nuevo contrato y documentar en commit message.

NO se aceptan PRs que sólo cambien `assert "OFFERED_SLOTS"` por `assert "IDLE"` sin justificación.

### REQ-TS-9: System prompt textual guard
El test que verifica que `main.py` no contiene la frase `"turnos más disponibles"` DEBE pasar. Si el prompt actual la contiene, DEBE removerse del prompt (no del test) y reemplazarse por la formulación aprobada del pack `tora-solo-quick-wins`.

### REQ-TS-10: Intent detector — ordinales en español
`_detect_selection_intent` DEBE reconocer las formas: `"el 1"`, `"el 1ro"`, `"el primero"`, `"la primera"`, `"el segundo"`, etc. Tests del bucket C8 que validan esto son requirements legítimos, no expectativas obsoletas.

### REQ-TS-11: Archivos huérfanos eliminados
- `tests/test_tiendanube.py` DEBE eliminarse (servicio no existe en el repo).
- `tests/test_whatsapp.py` DEBE moverse a `whatsapp_service/tests/` con su propio `requirements-dev.txt` que incluya `prometheus_client`, O agregarse a `collect_ignore` en `pytest.ini` con comentario explicando por qué.
- `tests/test_telegram_multimedia.py` DEBE actualizar el path del patch (`services.telegram_bot.openai` → path real) o marcar el test como `xfail` con razón.

## Non-goals

- No agregar nuevos tests más allá de los necesarios para reproducir bugs reales descubiertos en C7/C8.
- No subir cobertura.
