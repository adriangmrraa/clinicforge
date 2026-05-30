# Design: test-suite-stabilization

## Architecture overview

Este change NO altera arquitectura de producción. Toca exclusivamente:
- `tests/conftest.py` y nuevos helpers en `tests/fixtures/`
- Tests individuales rotos
- 1–2 cambios quirúrgicos en producción cuando un test revele bug real (esperado en C7/C8)
- `pytest.ini` (markers + collect_ignore)

## Approach por bucket

### C1 — tenants fixture canónica (~20 fallos)

**Solución:** crear `tests/fixtures/tenants.py` con `make_tenant_row(**overrides) -> dict` que devuelve un dict con TODAS las columnas NOT NULL del schema actual. Inspeccionar `models.py::Tenant` para listarlas.

```python
# tests/fixtures/tenants.py
from uuid import uuid4
from datetime import datetime

DEFAULT_WORKING_HOURS = {...}  # mínimo válido

def make_tenant_row(**overrides) -> dict:
    base = {
        "id": str(uuid4()),
        "name": "Test Clinic",
        "language": "es",
        "country_code": "AR",
        "ai_engine_mode": "solo",
        "working_hours": DEFAULT_WORKING_HOURS,
        "consultation_price": None,
        "created_at": datetime.utcnow(),
        # ... resto NOT NULL
    }
    base.update(overrides)
    return base
```

Refactorizar los ~20 tests del bucket C1 para importar este helper en lugar de armar dicts a mano.

**Por qué:** elimina la repetición de "el insert se cayó porque falta una columna nueva" cada vez que se hace una migración.

### C2 — db.pool en endpoint tests (~12 fallos)

**Diagnóstico primero:** abrir un test representativo (`test_orchestrator.py::test_auth_internal_required`) y entender qué inicialización le falta. Hipótesis: usa `TestClient(app)` pero no corre el `lifespan` que inicializa `db.pool`.

**Solución:**
- Agregar fixture `app_with_pool` en `conftest.py` que use `LifespanManager` (de `asgi-lifespan`) o que mockee `db.pool` con un `AsyncMock` antes de instanciar el `TestClient`.
- Tests que necesitan DB real → marcar `@pytest.mark.integration` y reutilizar `real_db_pool`.

### C3 — Patches a símbolos removidos (~7 fallos)

**Solución mecánica:** por cada fallo, leer el módulo actual, encontrar dónde vive el símbolo realmente, actualizar el path del patch. Si el símbolo desapareció de la API pública, eliminar el test (no había feature que testear).

Casos identificados:
- `services.greeting_state.get_redis` → buscar dónde vive ahora la conexión a Redis en `greeting_state.py`.
- `services.telegram_bot.openai` → módulo no importa openai directamente; el test debe patchear el cliente OpenAI en su nuevo path.

### C4 — Guardrails con substring (~5 fallos)

**Solución:** reemplazar `assert "peligroso" not in output` por:

```python
DANGEROUS_MEDICAL_PATTERNS = [
    r"\btomá\b.*\b(ibuprofeno|paracetamol)\b",
    r"\bdosis\b\s*\d+",
    r"\brecet[oa]\b",
    # ...
]
for pat in DANGEROUS_MEDICAL_PATTERNS:
    assert not re.search(pat, output), f"Pattern matched: {pat}"
```

El test debe modelar **consejo médico**, no la palabra "peligroso" suelta.

### C5 — Migration loader (~2 fallos)

**Solución:**

```python
# en lugar de:
spec = importlib.util.spec_from_file_location("module", filepath)

# usar:
slug = pathlib.Path(filepath).stem.replace("-", "_")
spec = importlib.util.spec_from_file_location(slug, filepath)
```

### C6 — Tool signature (~1 fallo)

**Solución:** abrir `tools/verify_payment_receipt.py` (o donde viva), copiar la firma actual al test. Trivial.

### C7 — State machine semántica (~10 fallos) ⚠️ CUIDADO

**Approach:** este bucket NO es mecánico. Por cada test:
1. Leer `services/state_machine.py` y el handler que debería setear el estado.
2. Git blame para ver qué pack tocó por última vez ese código.
3. Si el cambio fue intencional → actualizar test.
4. Si fue accidental → reparar producción.

Caso `test_check_availability_sets_offered_slots_state`: hay que ver si `check_availability` aún llama al state hook después del refactor del pack `tora-solo-state-lock`.

### C8 — Guards textuales + intent detector (~13 fallos)

**Sub-categorías:**

- **Guard "turnos más disponibles"**: `grep` en `main.py`, eliminar la frase del system prompt, reemplazar por "¿Querés que te muestre otro día?".
- **Intent detector ordinales**: extender `_detect_selection_intent` con regex para `el 1`, `el 1ro`, `el primero`, `la primera`, `el segundo`, etc. Test ya existe y modela el contrato deseado.

### C0 — Archivos huérfanos (precondición)

Antes de tocar nada, eliminar/ignorar:
- `tests/test_tiendanube.py` → `git rm`
- `tests/test_whatsapp.py` → mover a `whatsapp_service/tests/` o agregar a `collect_ignore_glob` en `pytest.ini`
- `tests/test_telegram_multimedia.py` → si el bot de Telegram se sigue usando, reparar; si no, `git rm`

## Alembic migration impact

**Ninguna.** Este change no toca el schema.

## Backwards compatibility

**Ninguna preocupación.** Solo se tocan tests y, en C7/C8, máximo 2 funciones de producción con cambios pequeños y sin romper API.

## Test plan (meta)

1. Después de cada bucket reparado, correr `pytest tests/ --tb=no -q` y registrar el delta de fallos.
2. Al final, correr la suite completa 3 veces seguidas para descartar flakiness.
3. Verificar que `pytest tests/ -m integration` aún corre (con `INTEGRATION_DB_URL` set) sin nuevos fallos.

## Open questions (para resolver durante apply)

1. ¿`test_clinic_special_conditions_e2e` debe correr en CI o ser manual? Probablemente manual (necesita LLM real).
2. ¿`test_payment_financing_migration` justifica testear migrations o duplica lo que Alembic ya garantiza? Si duplica, eliminar.
3. ¿Hay tests del bucket C7 que delaten un bug real introducido por `tora-solo-state-lock`? **Esto es lo más importante de descubrir.**
