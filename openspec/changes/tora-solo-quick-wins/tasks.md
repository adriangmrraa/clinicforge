# Tasks — C1: TORA-Solo Quick Wins

**Change ID:** `tora-solo-quick-wins`
**Companion:** `spec.md`, `design.md`
**Branch:** `feat/c1-tora-quick-wins`

---

## Convención

- Cada tarea = 1 commit atómico
- Cada commit referencia el bug en el mensaje: `fix(tora): bug #N — descripción`
- Tests primero o en paralelo (TDD del proyecto — los tests deben **fallar en `main`** antes de aplicar el fix)
- Ninguna tarea modifica schema de base de datos — C1 es cero migraciones Alembic
- Multi-tenant: cada función nueva que recibe `tenant_id` lo usa como parámetro de aislamiento, nunca como global

---

## Sprint 1 — Fixes (1 semana)

### Bug #9 — Dead-end recovery guard

- [ ] T1.1 Crear `tests/test_dead_end_recovery_guard.py` con 4 casos:
  - (a) `intermediate_steps` no vacío + dead-end phrase + output corto → NO se realiza segunda invocación a `executor.ainvoke`
  - (b) `intermediate_steps` vacío + dead-end phrase + output corto → SÍ se realiza segunda invocación
  - (c) `intermediate_steps` vacío + output largo (> 200 chars) → NO re-invocación
  - (d) `intermediate_steps` vacío + sin dead-end phrase + output corto → NO re-invocación
- [ ] T1.2 Verificar que T1.1 falla en `main` (tests rojos confirman el bug)
- [ ] T1.3 Modificar `orchestrator_service/services/buffer_task.py:1529-1588`:
  - Después del primer `ainvoke`, extraer `intermediate_steps = result.get('intermediate_steps', [])`
  - Añadir `tool_was_called = len(intermediate_steps) > 0`
  - Añadir `and not tool_was_called` a la condición del dead-end recovery
- [ ] T1.4 Correr `pytest tests/test_dead_end_recovery_guard.py` — verificar 4 tests verdes
- [ ] T1.5 Correr `pytest` completo — verificar 0 regresiones
- [ ] T1.6 Commit: `fix(tora): bug #9 — dead-end recovery solo si no hubo tool calls`

---

### Bug #2 — Strip INTERNAL markers en outbound

- [ ] T2.1 Crear `tests/test_response_sender_strip.py` con 5 casos:
  - Input `"Tenés disponibilidad el martes [INTERNAL_PRICE:7000000]"` → output sin marcador
  - Input `"[INTERNAL_DEBT:50000] Tu saldo pendiente es bajo"` → marcador al inicio eliminado
  - Input `"Texto sin marcadores"` → output idéntico al input
  - Input `"[INTERNAL_FOO:bar] texto [INTERNAL_PRICE:1000] fin"` → ambos marcadores eliminados
  - Input `"[INTERNAL_PRICE:7000000][INTERNAL_DEBT:0]"` → string vacío después de `.strip()`
- [ ] T2.2 Verificar que T2.1 falla en `main`
- [ ] T2.3 En `orchestrator_service/services/response_sender.py`:
  - Añadir import `re` si no existe
  - Añadir constante `_INTERNAL_MARKER_RE = re.compile(r'\[INTERNAL_[A-Z_]+:[^\]]*\]')`
  - Añadir función `_strip_internal_markers(text: str) -> str` con docstring
  - Llamar `_strip_internal_markers(text)` en `send_sequence()` antes de `_split_into_bubbles()` (o antes del primer split/fragmentación del texto)
- [ ] T2.4 Correr `pytest tests/test_response_sender_strip.py` — 5 tests verdes
- [ ] T2.5 Correr `pytest` completo — 0 regresiones
- [ ] T2.6 Commit: `fix(tora): bug #2 — strip [INTERNAL_*] markers en response sender`

---

### Bug #6 — Holiday filter en extra-day slot generator

- [ ] T3.1 Crear `tests/test_holiday_filter_extra_day.py` con 3 casos:
  - Mock de `check_is_holiday` retornando `True` → `_get_slots_for_extra_day` retorna lista vacía
  - Mock de `check_is_holiday` retornando `False` → `_get_slots_for_extra_day` retorna slots normalmente (lista no vacía)
  - Integration: llamada a rango que incluye un feriado → la fecha del feriado no aparece en los slots retornados por el loop de expansión
- [ ] T3.2 Verificar que T3.1 falla en `main`
- [ ] T3.3 En `orchestrator_service/main.py`, función `_get_slots_for_extra_day` (~línea 892):
  - Verificar si `check_is_holiday` está importado/disponible en el scope; si no, agregar el import
  - Añadir al inicio del cuerpo: `if await check_is_holiday(target_date, tenant_id, db.pool): return []`
- [ ] T3.4 Revisar los loops de range expansion en `main.py:1140-1170` y `main.py:1208-1280`:
  - Para cada fecha candidata en el loop, aplicar el mismo guard antes de llamar a `_get_slots_for_extra_day`
- [ ] T3.5 Correr `pytest tests/test_holiday_filter_extra_day.py` — 3 tests verdes
- [ ] T3.6 Correr `pytest` completo — 0 regresiones
- [ ] T3.7 Commit: `fix(tora): bug #6 — _get_slots_for_extra_day filtra feriados`

---

### Bug #7 — time_preference propagado a extra days

- [ ] T4.1 Crear `tests/test_time_preference_extra_day.py` con 4 casos:
  - `time_preference='tarde'` → ningún slot retornado tiene `hour < 13`
  - `time_preference='mañana'` → ningún slot retornado tiene `hour >= 13`
  - `time_preference=None` → se retornan slots de ambos turnos sin filtrar
  - `time_preference='tarde'` con solo slots de mañana disponibles → lista vacía (comportamiento correcto, documentado)
- [ ] T4.2 Verificar que T4.1 falla en `main`
- [ ] T4.3 En `orchestrator_service/main.py`, función `_get_slots_for_extra_day` (~línea 892):
  - Extender la firma añadiendo `time_preference: Optional[str] = None` como último parámetro
  - Añadir el filtro horario dentro del loop de slots:
    ```
    if time_preference == "mañana" and current.hour >= 13: continue
    if time_preference == "tarde" and current.hour < 13: continue
    ```
  - Añadir/actualizar docstring documentando el contrato de lista vacía
- [ ] T4.4 Buscar TODOS los call sites de `_get_slots_for_extra_day` en `main.py` con búsqueda textual
  - Actualizar cada call site para pasar `time_preference=time_preference` (desde el contexto de `check_availability`)
  - Confirmar que no queda ningún call site sin actualizar antes de cerrar el commit
- [ ] T4.5 Correr `pytest tests/test_time_preference_extra_day.py` — 4 tests verdes
- [ ] T4.6 Correr `pytest` completo — 0 regresiones
- [ ] T4.7 Commit: `fix(tora): bug #7 — time_preference propagado a extra-day generator`

---

### Bug #8 — Saludo único por sesión vía Redis flag

- [ ] T5.1 Crear `orchestrator_service/services/greeting_state.py` con:
  - Docstring de módulo (contrato key Redis, TTL, fallback)
  - `async def has_greeted(tenant_id: str, phone_number: str, redis_client) -> bool`
  - `async def mark_greeted(tenant_id: str, phone_number: str, redis_client) -> None`
  - Fallback silencioso: si Redis lanza excepción, `has_greeted` retorna `False`
- [ ] T5.2 Crear `tests/test_greeting_state.py` con 6 casos (usar `fakeredis` o mock del cliente Redis):
  - `has_greeted` retorna `False` cuando la key no existe
  - Después de `mark_greeted`, `has_greeted` retorna `True`
  - Después de que el TTL expira (avanzar reloj de fakeredis), `has_greeted` vuelve a `False`
  - `has_greeted` retorna `False` cuando Redis lanza excepción (fallback conservador)
  - `mark_greeted` no lanza excepción cuando Redis falla (falla silenciosa)
  - Keys de dos tenants diferentes son independientes (tenant A greeted no afecta a tenant B)
- [ ] T5.3 Verificar que T5.2 falla en `main`
- [ ] T5.4 Modificar `orchestrator_service/services/buffer_task.py` — sección pre-build:
  - Importar `has_greeted` desde `greeting_state`
  - Antes de `build_system_prompt`: resolver `is_greeting_pending` con try/except fallback a `True`
  - Pasar `is_greeting_pending=is_greeting_pending` a `build_system_prompt`
- [ ] T5.5 Modificar `orchestrator_service/main.py`, función `build_system_prompt` (~línea 6171):
  - Añadir kwarg `is_greeting_pending: bool = True` con default `True` (compatibilidad hacia atrás)
  - Envolver el bloque GREETING completo (~líneas 6352-6383) con `if is_greeting_pending:`
  - Añadir el `else:` con placeholder corto (solo contexto de status del paciente, sin presentación institucional)
- [ ] T5.6 Modificar `orchestrator_service/services/buffer_task.py` — sección post-send:
  - Importar `mark_greeted` desde `greeting_state`
  - En el path de éxito de envío: `if is_greeting_pending: await mark_greeted(tenant_id, phone_number, redis_client)`
- [ ] T5.7 Correr `pytest tests/test_greeting_state.py` — 6 tests verdes
- [ ] T5.8 Correr `pytest` completo — 0 regresiones
- [ ] T5.9 Commit: `fix(tora): bug #8 — saludo único por sesión vía Redis flag`

---

### Bug #3 — Price scale validator + UI hint + audit

- [ ] T6.1 Crear `tests/test_treatments_validator.py` con 4 casos:
  - `base_price=70000`, `consultation_price=15000` → POST/PUT retorna 200 (ratio 4.7x, bajo umbral)
  - `base_price=7000000`, `consultation_price=15000`, sin flag → HTTP 422 con mensaje esperado
  - `base_price=7000000`, `consultation_price=15000`, `confirm_unusual_price=True` → HTTP 200
  - `base_price=7000000`, `consultation_price=None` → HTTP 200 (skip silencioso, sin referencia)
- [ ] T6.2 Verificar que T6.1 falla en `main`
- [ ] T6.3 En `orchestrator_service/admin_routes.py`:
  - Extender el schema Pydantic de `TreatmentTypeCreate`/`TreatmentTypeUpdate` con `confirm_unusual_price: bool = False`
  - En handlers `POST /admin/treatment-types` y `PUT /admin/treatment-types/{code}`: leer `tenant.consultation_price` y aplicar la validación con umbral 100x
- [ ] T6.4 En `orchestrator_service/admin_routes.py`:
  - Añadir endpoint `GET /admin/treatments/price-audit` con docstring FastAPI (aparece en Swagger)
  - Implementar query: filtrar tratamientos del tenant donde `base_price > consultation_price * 100`
  - Retornar shape definida en `design.md §6.3`
- [ ] T6.5 Correr `pytest tests/test_treatments_validator.py` — 4 tests verdes
- [ ] T6.6 En `frontend_react/src/locales/es.json`, `en.json`, `fr.json`:
  - Añadir claves: `treatments.price_hint`, `treatments.price_tooltip`, `treatments.audit_button`, `treatments.audit_all_ok`, `treatments.audit_modal_title`, `treatments.price_confirm_unusual`
- [ ] T6.7 En `frontend_react/src/views/TreatmentsView.tsx`:
  - Añadir helper text + preview `Intl.NumberFormat('es-AR', {style:'currency', currency:'ARS'})` debajo del input de precio
  - Añadir ícono `<Info />` con tooltip usando clave i18n `treatments.price_tooltip`
  - Añadir botón "Auditar precios" gated por rol CEO/admin que llama al endpoint y muestra modal con resultados
  - Manejar respuesta 422 del submit: mostrar confirmación antes de reenviar con `confirm_unusual_price: true`
- [ ] T6.8 Correr `pytest` completo — 0 regresiones
- [ ] T6.9 Smoke test manual: editar tratamiento → ingresar `7000000` → verificar warning 422 → confirmar → verificar que persiste
- [ ] T6.10 Commit: `fix(tora): bug #3 — price scale validator + UI hint + audit endpoint`

---

## Sprint 2 — Verificación

- [ ] V1 Smoke test conversacional: replay de una conversación completa con número de test de WhatsApp — búsqueda de turno → ver precio → confirmar → booking
- [ ] V2 Verificar que los 6 bugs son CERO reproducibles en entorno local
- [ ] V3 Correr `pytest` suite completa — 0 regresiones nuevas
- [ ] V4 Correr `npm run lint` en `frontend_react/` — 0 errores de ESLint
- [ ] V5 Verificar que el endpoint `GET /admin/treatments/price-audit` aparece en Swagger (`http://localhost:8000/docs`)
- [ ] V6 Code review interno — revisar los 6 commits en el PR
- [ ] V7 Merge PR `feat/c1-tora-quick-wins` → `main`

---

## Definition of Done

- [ ] Los 6 commits están en la rama con mensajes conventional commits correctos
- [ ] Todos los 26 tests nuevos pasan (`pytest tests/test_response_sender_strip.py tests/test_treatments_validator.py tests/test_holiday_filter_extra_day.py tests/test_time_preference_extra_day.py tests/test_greeting_state.py tests/test_dead_end_recovery_guard.py`)
- [ ] `pytest` suite completa pasa sin regresiones nuevas
- [ ] Smoke test conversacional reproduce 0 bugs de los 6 corregidos
- [ ] Endpoint de auditoría documentado en Swagger
- [ ] `greeting_state.py` tiene docstring de módulo con contrato Redis key/TTL
- [ ] PR aprobado y mergeado
- [ ] No se modificó `CLAUDE.md` (se actualiza al cierre del umbrella C1+C2+C3)
- [ ] No se creó ni modificó ninguna migración Alembic
