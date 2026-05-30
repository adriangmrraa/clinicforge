# Proposal: test-suite-stabilization

## Intent

Estabilizar la suite de pytest del orchestrator eliminando los **70 fallos pre-existentes** que arrastra el repo desde antes del commit `ab44b14` (test infra + pythonpath priority). Recuperar la suite como gate confiable para CI y futuros packs SDD.

## Why

- Hoy `pytest tests/` reporta `70 failed, 462 passed, 14 skipped`. Ningún desarrollador puede usar la suite como señal de salud — el ruido oculta regresiones reales.
- Los 70 fallos son **deuda técnica acumulada de 7 packs SDD** (031–038) donde tests quedaron desincronizados con refactors de producción.
- Bloquea el siguiente paso natural: agregar CI con gate de tests verdes y migrar `langchain 0.1.0 → 0.3.x`.

## Scope

**IN:**
- Reparar los 70 fallos categorizados en 8 buckets (C1–C8 abajo).
- NO cambiar comportamiento de producción salvo que un test revele un bug real (caso C7/C8).
- Marcar correctamente tests de integración/e2e con sus markers (`@pytest.mark.integration`, `@pytest.mark.e2e`) para que `pytest tests/` corra solo unit por defecto.
- Documentar excepciones legítimas (`test_tiendanube.py` huérfano, `test_whatsapp.py` deps de otro servicio) en `pytest.ini` con `collect_ignore` o eliminarlos si no aplican.

**OUT:**
- Migración langchain 0.1.0 → 0.3.x (change separado).
- CI pipeline (change separado, depende de éste).
- Nuevos tests de cobertura (no es lo que pide este change).

## Buckets de fallos (categorización con evidencia)

| # | Bucket | Síntoma representativo | Causa raíz | Tests aprox |
|---|--------|------------------------|------------|------|
| C1 | tenants fixture incompleta | `KeyError: 'language'` | El insert mock de `tenants` no incluye la columna `language` agregada por migración reciente | ~20 |
| C2 | `db.pool` None en endpoint tests | `'NoneType' has no attribute 'fetchrow'` | Tests llaman endpoints FastAPI/tools sin inicializar `db.pool` ni mockearlo | ~12 |
| C3 | Patches a atributos removidos | `module does not have attribute 'get_redis'/'openai'/'execute'` | Refactors movieron símbolos; los `monkeypatch.setattr(...)` apuntan a paths viejos | ~7 |
| C4 | Guardrail string-match brittle | `'peligroso' not in '...peligroso para la clínica'` | El test prohibe substring; el contexto legítimo lo contiene | ~5 |
| C5 | Migration loader con `-` en nombre | `Migration must have revision` | `importlib.util.spec_from_file_location` falla en filenames con guiones; usar slug con underscores | ~2 |
| C6 | Firma de tool cambió | `unexpected keyword 'receipt_description'` | El tool renombró/eliminó arg; el test no se actualizó | ~1 |
| C7 | State machine semántica nueva | `'IDLE' == 'OFFERED_SLOTS'` | Investigar: ¿el handler dejó de setear el estado o el test es obsoleto? **Decisión por test, no en bloque.** | ~10 |
| C8 | Guards textuales + intent detector | `'turnos más disponibles' found 1`, `"el 1ro" intent False` | El prompt de main.py contiene la frase prohibida (regresión textual del sistema prompt). Intent detector no reconoce ordinales en español. | ~13 |

## Approach

Atacar bucket por bucket en commits separados, no en un mega-commit. Cada bucket genera 1 PR (o 1 commit lineal) con su propio scope claro. C1 y C2 son los más rentables (casi la mitad de los fallos) y los más mecánicos.

## Risks

- **C7 (state machine)** puede esconder un bug real de producción introducido por algún pack reciente. Requiere lectura del código antes de "actualizar" el test — NO bajar la barra del test sin entender por qué el estado dejó de setearse.
- **C8 (guard textual)** detecta literalmente que el system prompt de `main.py` contiene una frase que un pack anterior se comprometió a eliminar. Si la eliminamos del prompt, validar manualmente que la AI no la genere en runtime.
- Tests en C2 que necesitan DB real deben moverse a `@pytest.mark.integration` y NO repararse con mocks frágiles.

## Out of scope (explícito)

- Reescribir la suite con un framework nuevo.
- Convertir tests unit a integration por capricho.
- Tocar `test_tiendanube.py` (servicio inexistente — eliminar archivo) o `test_whatsapp.py` (deps de otro repo — mover a `whatsapp_service/tests/` o ignorar).
