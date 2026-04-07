# Design — C1: TORA-Solo Quick Wins

**Change ID:** `tora-solo-quick-wins`
**Companion:** `spec.md`, `tasks.md`
**Status:** Draft
**Fecha:** 2026-04-07

---

## 1. Resumen del approach

C1 es una intervención quirúrgica sobre 6 bugs localizados del agente TORA. La filosofía guía es **cero cambios de arquitectura**: no se introduce nueva infraestructura, no se tocan tablas de base de datos, no se modifica el flujo general de `buffer_task.py → executor.ainvoke → response_sender`. Cada fix es un bisturí aplicado al punto exacto donde el bug ocurre.

El orden de aplicación sigue el principio de riesgo ascendente: primero los fixes más aislados (una función, un archivo), luego los que tocan múltiples archivos, y al final el que tiene la mayor superficie de cambio (bug #3 con backend + frontend). Cada bug vive en su propio commit, con sus propios tests, de modo que un fallo en el commit de bug #7 no bloquea ni revierte los fixes ya mergeados de los bugs #9, #2 y #6.

Los seis bugs pertenecen a la "Clase B" del umbrella (`dual-engine-umbrella/proposal.md §2.3`): higiene mecánica. Ninguno de ellos requiere la máquina de estados de C2 ni el motor multi-agente de C3. Esa distinción es lo que habilita shiippear C1 en una semana con riesgo bajo y permite que C2 y C3 se desarrollen en paralelo sobre la misma base de código estabilizada.

---

## 2. Decisiones de diseño

### 2.1 Un commit por bug

Cada uno de los 6 bugs se implementa y mergea en un commit separado. Justificación:

- **Rollback quirúrgico:** si el fix de bug #7 introduce una regresión, se puede revertir ese commit sin afectar los fixes ya desplegados de #9, #2, #6.
- **Revisión más limpia:** el revisor ve exactamente qué cambió para resolver un problema específico, no un diff de 400 líneas mezclando 6 concerns distintos.
- **Testabilidad independiente:** cada commit pasa o falla en CI de manera autónoma. Un test roto en #8 no bloquea el deploy de #2.
- La única excepción evaluada es bugs #6 y #7 (ver §2.4).

### 2.2 Bug #2 — Strip en `response_sender.py`, NO en cada tool

**Decisión:** el strip de marcadores `[INTERNAL_*]` se aplica en `ResponseSender.send_sequence()`, que es el único chokepoint de salida al canal de mensajería (YCloud / Chatwoot).

**Alternativas descartadas:**

| Alternativa | Por qué se descartó |
|-------------|-------------------|
| Strip dentro de cada tool que emite marcadores | Hay al menos 2 herramientas que emiten marcadores hoy (`check_availability` en líneas 2047 y 2053). A futuro podrían agregarse más. Mantener el strip en cada tool es una convención frágil: un nuevo tool podría olvidar aplicarlo. |
| Strip post-LLM en `buffer_task.py` antes de llamar a `send_sequence` | Funcionaría, pero duplica el punto de sanitización. Si `buffer_task.py` tiene múltiples paths de envío, hay que agregarlo en cada uno. `response_sender.py` es el punto único garantizado. |
| No strip — cambiar el prompt para que el LLM nunca repita los marcadores | El LLM puede alucinarlo en el texto final. Depender del prompt para garantizar que NO aparezca algo es inseguro por definición. |

**Trade-off aceptado:** el LLM sigue recibiendo los marcadores en `intermediate_steps` (necesario para su razonamiento sobre precios y deudas). Solo el output final al paciente queda limpio. La separación entre el dato interno y la presentación al usuario es correcta por diseño.

### 2.3 Bug #3 — Validación en write path + UI hint, NO migración de datos

**Decisión:** el validador se activa en la escritura (`POST/PUT /admin/treatment-types`) y el endpoint de auditoría lee los datos existentes. No se auto-corrigen datos persistidos.

**Por qué no auto-corregir datos existentes:** una migración de datos que divide automáticamente todos los precios `> consultation_price * 100` por 100 podría destruir datos legítimos de clínicas con precios reales de cirugías complejas (ej. implantes con `base_price = 800000` ARS que ES correcto). La decisión de si un precio histórico está mal escalado pertenece al operador, no al sistema.

**Por qué el threshold es relativo y no absoluto:** `base_price > consultation_price * 100` captura la escala relativa (el tratamiento cuesta más de 100 consultas) sin asumir valores absolutos de moneda. Un threshold absoluto de `> 500000` sería incorrecto para clínicas con consultas a $10.000 ARS o para escenarios de inflación. El tenant que no tiene `consultation_price` configurado queda excluido del validador (skip silencioso) porque no hay referencia para comparar.

**Cómo se evitan falsos positivos:** el campo `confirm_unusual_price: bool = False` en el body del request permite al operador declarar explícitamente que el precio es correcto y saltear el warning. El flujo de frontend debe manejar el 422 mostrando una confirmación al usuario antes de reenviar con `confirm_unusual_price=true`.

### 2.4 Bug #6 + #7 — Decisión sobre commits compartidos

**Decisión: DOS commits separados, NO uno compartido.**

Justificación:

- Bug #6 (holiday check) y Bug #7 (time_preference) modifican la misma función `_get_slots_for_extra_day` en `main.py:892`.
- La tentación natural es combinarlos en un solo commit porque el diff es sobre el mismo archivo y función.
- Sin embargo, los tests son conceptualmente distintos: #6 testea el comportamiento con feriados (mock de `check_is_holiday`), #7 testea el comportamiento con filtro horario (`time_preference`).
- Combinarlos en un commit hace más difícil identificar cuál fix introdujo una regresión si alguno de los tests falla en el futuro.
- **Excepción:** si al momento de implementar ambos bugs el cambio de firma de `_get_slots_for_extra_day` (para agregar `time_preference: Optional[str]`) entra en conflicto con la adición del holiday check, se recomienda aplicar #6 primero (solo el guard `return []` al inicio, sin cambio de firma), y #7 segundo (extensión de la firma + filtro interno). La firma de #6 no cambia, la de #7 sí: separando los commits se evita el conflicto.

### 2.5 Bug #8 — Redis flag, NO columna en `patients`

**Decisión:** Redis con TTL de 4 horas como flag de sesión de saludo. Sin columna nueva en la tabla `patients`.

**Comparación de alternativas:**

| Opción | Ventajas | Desventajas |
|--------|----------|-------------|
| Columna `greeted_at TIMESTAMPTZ` en `patients` | Persistente, auditable, visible en consultas SQL | Requiere migración Alembic (violación del principio de C1 "cero schema changes"), la columna persiste indefinidamente aunque solo tenga valor de sesión, no expira sola |
| Redis flag `greet:{tenant_id}:{phone}` TTL 4h | Sin migración, expira automáticamente, costo operacional mínimo | Volátil (se pierde si Redis se reinicia), race condition teórica en multi-worker |
| Columna en `chat_conversations` | Granularidad por conversación | Requiere migración, no es "por sesión de 4h" sino por conversación |

El estado de saludo es inherentemente efímero: si el paciente no escribe en 4 horas, merece un saludo nuevo. Esa naturaleza efímera encaja perfectamente con Redis + TTL. El fallback ante Redis caído (retornar `False`, es decir "asumir que no fue saludado") garantiza que el error sea conservador: se puede dar el saludo de más, nunca de menos.

### 2.6 Bug #9 — Inspect `intermediate_steps`, NO eliminar el dead-end recovery

**Decisión:** agregar una guarda `not tool_was_called` a la condición del dead-end recovery. No eliminar el mecanismo.

**Justificación de mantener el recovery:** el dead-end recovery sirve para el caso donde el LLM genera una frase de stalling ("dejame buscar un momento") sin haber llamado ninguna herramienta. Este caso es real: el LLM puede alucinar una respuesta de "voy a buscar" sin realmente buscar. En ese escenario, el recovery re-invoca y frecuentemente produce una respuesta correcta. Eliminar el recovery completamente significaría que el paciente recibe una frase de stalling sin que el sistema intente recuperarse.

**La guarda es quirúrgica:** `intermediate_steps = result.get('intermediate_steps', [])` es un campo estándar de LangChain. Si tiene elementos, el agente ya hizo trabajo; una respuesta corta posterior es un problema de redacción del LLM (que el paciente puede resolver con su siguiente mensaje), no un dead-end. La re-invocación en ese caso sería redundante y potencialmente dañina (llamar `check_availability` dos veces → duplicar la respuesta de disponibilidad o ejecutar dos veces `confirm_slot` que tiene efectos secundarios en Redis).

---

## 3. Diagramas de flujo

### 3.1 Bug #2 — Outbound flow con strip

```
Tool check_availability devuelve:
  "Tenés disponibilidad el martes a las 10:00 [INTERNAL_PRICE:7000000]"
    │
    ▼ (LangChain procesa intermediate_steps, usa el marcador para razonamiento)
    │
LLM redacta mensaje final:
  "El costo del blanqueamiento es $7.000 [INTERNAL_PRICE:7000000]"
    │
    ▼
buffer_task.py recibe response_text del ainvoke
    │
    ▼
ResponseSender.send_sequence(text)
    │
    ▼ NEW: _strip_internal_markers(text)
  "El costo del blanqueamiento es $7.000 "  ← marcador eliminado, strip() del trailing space
    │
    ▼
_split_into_bubbles(text)
    │
    ▼
YCloud API / Chatwoot → paciente recibe mensaje limpio
```

### 3.2 Bug #8 — Redis greeting flag flow

```
Mensaje entrante del paciente
    │
    ▼
buffer_task.py — resolver tenant_id + phone
    │
    ▼
greeting_state.has_greeted(tenant_id, phone, redis)
    │
    ├── False (primera vez o TTL expirado)
    │       │
    │       ▼
    │   is_greeting_pending = True
    │       │
    │       ▼
    │   build_system_prompt(..., is_greeting_pending=True)
    │   → incluye bloque GREETING completo ("Soy TORA, asistente de [clínica]...")
    │       │
    │       ▼
    │   executor.ainvoke(...)
    │       │
    │       ▼
    │   [envío exitoso]
    │       │
    │       ▼
    │   greeting_state.mark_greeted(tenant_id, phone, redis)  ← TTL 4h
    │
    └── True (dentro de las 4 horas de sesión)
            │
            ▼
        is_greeting_pending = False
            │
            ▼
        build_system_prompt(..., is_greeting_pending=False)
        → bloque GREETING reemplazado por placeholder corto
          (solo contexto de status del paciente, sin presentación institucional)
            │
            ▼
        executor.ainvoke(...)  → respuesta sin "Soy TORA..."
```

### 3.3 Bug #9 — Dead-end recovery con guarda

```
executor.ainvoke(input) → result
    │
    ▼
output = result.get('output', '')
intermediate_steps = result.get('intermediate_steps', [])
    │
    ├── intermediate_steps NO vacío  (el agente llamó al menos 1 tool)
    │       │
    │       ▼
    │   tool_was_called = True
    │       │
    │       ▼
    │   [GUARDA: skip dead-end recovery]
    │       │
    │       ▼
    │   ResponseSender.send_sequence(output)  → envío directo
    │
    └── intermediate_steps VACÍO  (el agente no llamó ningún tool)
            │
            ▼
        tool_was_called = False
            │
            ├── is_dead_end_phrase(output) AND len(output) < 200
            │       │
            │       ▼
            │   [dead-end recovery legítimo]
            │   result = await executor.ainvoke(input)  ← 2da invocación
            │       │
            │       ▼
            │   ResponseSender.send_sequence(result['output'])
            │
            └── NOT (dead-end phrase AND short)
                    │
                    ▼
                ResponseSender.send_sequence(output)  → envío directo
```

---

## 4. Cambios por archivo

### 4.1 `orchestrator_service/services/response_sender.py`

- Añadir constante de módulo: `_INTERNAL_MARKER_RE = re.compile(r'\[INTERNAL_[A-Z_]+:[^\]]*\]')`
- Añadir función privada `_strip_internal_markers(text: str) -> str` que aplica `_INTERNAL_MARKER_RE.sub('', text).strip()`
- En el método `send_sequence()`: llamar a `_strip_internal_markers(text)` sobre el argumento de texto completo, **antes** de la llamada a `_split_into_bubbles()` o cualquier fragmentación
- Añadir comentario de módulo documentando la convención: los marcadores `[INTERNAL_*:*]` son exclusivamente para uso interno del razonamiento del LLM y nunca deben llegar al paciente

### 4.2 `orchestrator_service/main.py`

Cambios agrupados por bug:

**Bug #6 (`_get_slots_for_extra_day`, ~línea 892):**
- Al inicio del cuerpo de la función, añadir: `if await check_is_holiday(target_date, tenant_id, db.pool): return []`
- Verificar que `check_is_holiday` ya está importado/disponible en el scope; si no, añadir el import correspondiente
- Revisar el loop de range expansion en `main.py:1140-1170` y `main.py:1208-1280`: para cada fecha candidata en el loop, aplicar el mismo guard antes de llamar a `_get_slots_for_extra_day`

**Bug #7 (`_get_slots_for_extra_day`, ~línea 892):**
- Extender la firma de la función agregando `time_preference: Optional[str] = None` como último parámetro con default `None`
- Dentro del cuerpo, en el loop de generación de slots, agregar el filtro horario:
  ```
  if time_preference == "mañana" and current.hour >= 13: continue
  if time_preference == "tarde" and current.hour < 13: continue
  ```
- Actualizar TODOS los call sites en `check_availability` y en los loops de range expansion para pasar `time_preference=time_preference` (o el nombre de la variable local donde esté disponible)
- Añadir docstring a `_get_slots_for_extra_day` documentando el contrato: si `time_preference` filtra todos los slots del día, se retorna lista vacía (comportamiento correcto)

**Bug #8 (`build_system_prompt`, ~línea 6171):**
- Añadir `is_greeting_pending: bool = True` como kwarg con default `True` (compatibilidad hacia atrás)
- Dentro de `build_system_prompt`, envolver el bloque GREETING completo (~líneas 6352-6383) con:
  ```
  if is_greeting_pending:
      # bloque GREETING completo actual
  else:
      # placeholder corto: solo línea de contexto de status del paciente
  ```
- El placeholder corto NO incluye "Soy TORA", ni nombre de clínica, ni instrucciones de presentación institucional

### 4.3 `orchestrator_service/admin_routes.py`

**Bug #3:**
- Extender el modelo `TreatmentTypeCreate` / `TreatmentTypeUpdate` (o el schema Pydantic equivalente) con campo opcional: `confirm_unusual_price: bool = False`
- En los handlers `POST /admin/treatment-types` y `PUT /admin/treatment-types/{code}`:
  1. Leer `tenant.consultation_price` del tenant activo (ya disponible en contexto de endpoint vía `current_user`)
  2. Si `base_price > tenant.consultation_price * 100` Y `confirm_unusual_price` es `False` Y `consultation_price` no es `None` → retornar `HTTPException(422, detail="Precio inusualmente alto. ¿Estás seguro? Si es correcto, incluí confirm_unusual_price=true en el cuerpo.")`
  3. Si `confirm_unusual_price=True` → omitir la validación y guardar normalmente
- Añadir nuevo endpoint:
  ```
  GET /admin/treatments/price-audit
  ```
  - Requiere auth normal (`Depends(verify_admin_token)`)
  - Leer `tenant.consultation_price` del tenant activo
  - Si `consultation_price` es `None`: retornar `{"suspicious": [], "warning": "consultation_price no configurado"}`
  - Consultar todos los `treatment_types` del tenant
  - Filtrar los que cumplen `base_price > consultation_price * 100`
  - Retornar la shape definida en §6.3
  - Documentar con docstring FastAPI para que aparezca en Swagger

### 4.4 `orchestrator_service/services/buffer_task.py`

**Bug #8 (pre-build):**
- Antes de la llamada a `build_system_prompt`, añadir:
  ```python
  is_greeting_pending = True
  try:
      is_greeting_pending = not await has_greeted(tenant_id, phone_number, redis_client)
  except Exception:
      pass  # fallback conservador: saludar si Redis falla
  ```
- Pasar `is_greeting_pending=is_greeting_pending` como kwarg a `build_system_prompt`

**Bug #8 (post-send):**
- En el path de éxito de envío (después de que el mensaje fue enviado sin excepción), añadir:
  ```python
  if is_greeting_pending:
      await mark_greeted(tenant_id, phone_number, redis_client)
  ```
- Solo marcar si `is_greeting_pending=True` para evitar escrituras Redis innecesarias en turnos subsiguientes

**Bug #9 (`buffer_task.py:1529-1588`):**
- Después del primer `result = await executor.ainvoke(...)`, extraer:
  ```python
  intermediate_steps = result.get('intermediate_steps', [])
  tool_was_called = len(intermediate_steps) > 0
  ```
- Añadir `and not tool_was_called` a la condición de activación del dead-end recovery

### 4.5 NUEVO `orchestrator_service/services/greeting_state.py`

Módulo nuevo con:
- Docstring de módulo explicando: contrato Redis key, TTL, convención de naming, y comportamiento de fallback
- Función `has_greeted(tenant_id: str, phone_number: str, redis_client) -> bool`
- Función `mark_greeted(tenant_id: str, phone_number: str, redis_client) -> None`
- Sin estado global ni dependencias de importación de `main.py` (módulo autocontenido)
- El tipo de `redis_client` debe ser compatible con el cliente Redis async que ya usa el proyecto (verificar en `buffer_task.py` el tipo usado)

### 4.6 `frontend_react/src/views/TreatmentsView.tsx`

**Bug #3:**
- En el modal de creación/edición de tratamiento, debajo del input de `base_price`:
  - Añadir texto helper: clave i18n `treatments.price_hint` ("Ingresá el monto en pesos argentinos")
  - Añadir preview en vivo: `Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)` que se actualiza en cada keystroke del input
  - Añadir ícono de info (`<Info />` de lucide-react) con tooltip: clave i18n `treatments.price_tooltip`
- Añadir botón "Auditar precios" (clave i18n `treatments.audit_button`):
  - Visible solo si `user?.role === 'ceo'` o `user?.role === 'admin'` (ver note en §10)
  - Al hacer clic, llama a `GET /admin/treatments/price-audit` via `api` de Axios
  - Resultado se muestra en un modal de lectura: lista de tratamientos sospechosos con columnas `nombre`, `precio actual`, `precio consulta`, `ratio`
  - Si lista vacía: mostrar mensaje con clave i18n `treatments.audit_all_ok`
- En el submit del formulario:
  - Si el endpoint retorna 422 con mensaje de precio inusual: mostrar un `Alert` o `Dialog` de confirmación con el mensaje
  - Si el operador confirma: reenviar con `confirm_unusual_price: true` en el body
  - Si cancela: dejar el formulario abierto sin cerrar

### 4.7 `frontend_react/src/locales/{es,en,fr}.json`

Claves nuevas a agregar en los tres archivos:

**Bug #3:**
- `treatments.price_hint` — "Ingresá el monto en pesos argentinos" / "Enter the amount in Argentine pesos" / "Entrez le montant en pesos argentins"
- `treatments.price_tooltip` — "Ej: 70000 = $70.000 — No uses puntos ni comas, solo el número entero" / (equivalente en EN y FR)
- `treatments.audit_button` — "Auditar precios" / "Audit prices" / "Auditer les prix"
- `treatments.audit_all_ok` — "Todos los precios parecen correctos" / "All prices look correct" / "Tous les prix semblent corrects"
- `treatments.audit_modal_title` — "Precios con escala sospechosa" / "Prices with suspicious scale" / "Prix avec échelle suspecte"
- `treatments.price_confirm_unusual` — "El precio ingresado es inusualmente alto. ¿Confirmas que es correcto?" / (equivalente en EN y FR)

---

## 5. Estructuras de datos nuevas

### 5.1 Redis keys nuevas

| Key | Type | TTL | Set by | Read by |
|-----|------|-----|--------|---------|
| `greet:{tenant_id}:{phone_number}` | string (`'1'`) | 14400s (4h) | `greeting_state.mark_greeted` | `greeting_state.has_greeted` |

**Notas:**
- `tenant_id` es el identificador entero del tenant (mismo que se usa en queries)
- `phone_number` incluye el prefijo `+` si el proyecto lo usa consistentemente (verificar formato existente en otras keys Redis del proyecto)
- No hay otras keys Redis nuevas en C1

### 5.2 Sin DB migrations en C1

C1 no introduce **ningún cambio de schema de base de datos**. No se crea ningún archivo en `orchestrator_service/alembic/`. No se modifica `orchestrator_service/models.py`. La cadena de migraciones queda en `009_pgvector_faq_embeddings` tal como está. C2 y C3 continuarán la cadena a partir de ese punto.

---

## 6. Contratos de funciones nuevas

### 6.1 `_strip_internal_markers(text: str) -> str`

```python
# Módulo: orchestrator_service/services/response_sender.py
# Acceso: privada al módulo (prefijo _)

_INTERNAL_MARKER_RE = re.compile(r'\[INTERNAL_[A-Z_]+:[^\]]*\]')

def _strip_internal_markers(text: str) -> str:
    """
    Elimina todos los marcadores internos del texto antes de enviarlo al paciente.

    Los marcadores [INTERNAL_*:*] son metadata para el razonamiento del LLM.
    Nunca deben ser visibles en el canal de mensajería (YCloud/Chatwoot).

    Ejemplos:
      Input:  "Tenés turno el martes [INTERNAL_PRICE:7000000] ¿te viene bien?"
      Output: "Tenés turno el martes ¿te viene bien?"

      Input:  "[INTERNAL_DEBT:50000] Tu deuda es..."
      Output: "Tu deuda es..."

      Input:  "[INTERNAL_PRICE:1000][INTERNAL_DEBT:0]"
      Output: ""
    """
    return _INTERNAL_MARKER_RE.sub('', text).strip()
```

### 6.2 `has_greeted` y `mark_greeted`

```python
# Módulo: orchestrator_service/services/greeting_state.py
# Convención Redis key: greet:{tenant_id}:{phone_number}
# TTL: 14400 segundos (4 horas)

async def has_greeted(tenant_id: str, phone_number: str, redis_client) -> bool:
    """
    Retorna True si el paciente ya recibió el saludo institucional completo
    en la sesión actual (dentro de las últimas 4 horas).

    Fallback: si Redis no está disponible, retorna False (comportamiento
    conservador: se vuelve a saludar antes que omitir el saludo).
    """
    ...

async def mark_greeted(tenant_id: str, phone_number: str, redis_client) -> None:
    """
    Registra que el paciente recibió el saludo institucional completo.
    El flag expira automáticamente en 14400 segundos (4 horas).

    Después de la expiración, el próximo mensaje del paciente recibirá
    el saludo completo nuevamente (comportamiento de nueva sesión).

    Si Redis no está disponible, falla silenciosamente (no crítico).
    """
    ...
```

### 6.3 Endpoint `GET /admin/treatments/price-audit`

**Request:**
```
GET /admin/treatments/price-audit
Headers:
  Authorization: Bearer {jwt_token}
  X-Admin-Token: {admin_token}
```

**Response 200:**
```json
{
  "tenant_id": 123,
  "consultation_price": 15000.00,
  "suspicious": [
    {
      "code": "BLANQUEAMIENTO",
      "name": "Blanqueamiento dental",
      "base_price": 7000000.00,
      "ratio": 466.7
    }
  ],
  "total_treatments": 12,
  "total_suspicious": 1
}
```

**Response 200 (sin consultation_price configurada):**
```json
{
  "tenant_id": 123,
  "consultation_price": null,
  "suspicious": [],
  "warning": "consultation_price no configurado — no es posible detectar escala incorrecta",
  "total_treatments": 12,
  "total_suspicious": 0
}
```

**Response 401/403:** autenticación fallida (comportamiento estándar del middleware existente).

---

## 7. Casos de test (resumen, el detalle va en cada test file)

| Bug | Test type | File | Cantidad |
|-----|-----------|------|----------|
| #2 | unit | `tests/test_response_sender_strip.py` | 5 |
| #3 | unit | `tests/test_treatments_validator.py` | 4 |
| #6 | unit | `tests/test_holiday_filter_extra_day.py` | 3 |
| #7 | unit | `tests/test_time_preference_extra_day.py` | 4 |
| #8 | unit | `tests/test_greeting_state.py` | 6 |
| #9 | unit | `tests/test_dead_end_recovery_guard.py` | 4 |

**Total: 26 tests nuevos.** Todos son unit tests — no requieren base de datos real, se usan mocks/fakes para Redis, asyncpg pool y executor de LangChain. El proyecto ya tiene `pytest-asyncio` en modo `auto` configurado en `pytest.ini`.

---

## 8. Orden de implementación recomendado

1. **Bug #9 — Dead-end recovery guard** (`buffer_task.py` únicamente)
   - El fix más aislado: una sola condición en un solo archivo
   - Al eliminarlo primero, las pruebas de los demás bugs no van a sufrir dobles invocaciones del agente durante el desarrollo
   - Si falla en CI: afecta solo `buffer_task.py`, no bloquea los demás commits

2. **Bug #2 — Strip INTERNAL markers** (`response_sender.py` únicamente)
   - Alta severidad, superfice mínima (un archivo, una función nueva)
   - Los tests son completamente aislados (función pura sobre strings)
   - Puede implementarse en paralelo con #9 si hay más de un desarrollador

3. **Bug #6 — Holiday filter en extra-day** (`main.py`)
   - Extensión de cobertura de función existente, sin cambio de firma
   - Tests requieren mock de `check_is_holiday` (async)
   - Implementar antes de #7 para evitar conflicto de firma en el mismo archivo

4. **Bug #7 — time_preference en extra days** (`main.py`)
   - Depende de la misma función que #6, pero SIN conflicto si #6 ya está mergeado
   - Cambio de firma + filtro + actualización de call sites
   - Implementar secuencialmente después de #6 para evitar conflictos de merge

5. **Bug #8 — Greeted_at Redis flag** (`greeting_state.py` nuevo + `buffer_task.py` + `main.py`)
   - Introduce módulo nuevo: más archivos afectados, mayor superficie de revisión
   - Implementar después de que #9 ya está mergeado (para que `buffer_task.py` tenga un solo diff limpio)

6. **Bug #3 — Price scale validator + UI hint + audit** (`admin_routes.py` + `TreatmentsView.tsx` + `locales/`)
   - La mayor superficie: backend + frontend + i18n
   - Dejarlo al final permite que todos los demás fixes ya estén mergeados y el entorno de test esté estable
   - Si el timeline aprieta, este es el único fix que puede trasladarse a C1.1 sin afectar los demás

---

## 9. Riesgos de implementación

| # | Riesgo | Probabilidad | Mitigación |
|---|--------|-------------|------------|
| R1 | El strip de `_strip_internal_markers` elimina texto legítimo que usa sintaxis `[PALABRA:valor]` que no es marcador interno | Baja | El patrón `[INTERNAL_[A-Z_]+:]` es suficientemente específico. Solo afecta marcadores con prefijo `INTERNAL_` en mayúsculas y uppercase. Documentar la convención para que futuros markers sigan el mismo patrón. |
| R2 | Bug #7: algún call site de `_get_slots_for_extra_day` no se actualiza y `time_preference` queda `None` silenciosamente | Media | La búsqueda de call sites debe hacerse con `rg '_get_slots_for_extra_day'` antes de cerrar el commit. El default `None` hace que el comportamiento sea idéntico al actual en ese call site, por lo que la regresión es silenciosa, no catastrófica. |
| R3 | Bug #6: `check_is_holiday` hace query a DB — en búsquedas de 7 días se agregan hasta 7 queries extra | Baja-Media | Aceptable para el volumen de conversaciones concurrentes esperado. Si el performance se convierte en problema en C2/C3, se puede cachear en Redis con TTL de 24h. Documentar como deuda técnica explícita. |
| R4 | Bug #8: race condition en multi-worker — dos workers procesan mensajes del mismo paciente, ambos ven `has_greeted=False`, ambos saludan y llaman `mark_greeted` | Baja | El peor caso es el saludo dos veces en una ventana muy pequeña. No es un problema de correctitud funcional. Aceptable para el volumen actual. |
| R5 | Bug #3: `consultation_price` NULL en el tenant — el validador hace skip silencioso pero el developer que mantiene el código no lo sabe | Baja | Documentar el skip con un comentario explícito en el código y en el docstring del endpoint. |
| R6 | Bug #8: el build de `build_system_prompt` tiene múltiples call sites en `main.py` además del que gestiona `buffer_task.py` | Media | Antes de implementar, buscar todos los call sites de `build_system_prompt` con `rg 'build_system_prompt'`. Si algún call site no provee `is_greeting_pending`, el default `True` mantiene el comportamiento actual. |
| R7 | Bug #3: el botón "Auditar precios" en el frontend llama al endpoint durante la carga inicial o en un polling — costo de query innecesario | Baja | El endpoint solo se llama al hacer clic en el botón (on-demand). No hay polling. |

---

## 10. Open questions para el apply phase

1. **Tipo del cliente Redis en `greeting_state.py`:** verificar qué tipo usa `buffer_task.py` para el cliente Redis async (¿`aioredis.Redis`, `redis.asyncio.Redis`, o instancia de `ConnectionPool`?). La firma de `has_greeted` y `mark_greeted` debe ser compatible con ese tipo exacto. Revisar los imports en `buffer_task.py` antes de escribir el módulo.

2. **Formato del `phone_number` en la key Redis:** confirmar si `buffer_task.py` trabaja con el número con prefijo `+` (ej. `+5491112345678`) o sin él. La key Redis debe usar el mismo formato para garantizar consistencia. Revisar el valor de la variable `customer_phone` (o `phone_number`) en el contexto de `buffer_task.py`.

3. **Call sites de `build_system_prompt`:** hacer una búsqueda de `build_system_prompt` en `main.py` para contar cuántos call sites existen. Si hay más de uno (ej. uno para el flow de WhatsApp y otro para el flow de test/preview), decidir si todos deben recibir `is_greeting_pending` o solo el path de `buffer_task.py`.

4. **Role check en el botón "Auditar precios" (frontend):** la spec dice "CEO/admin". Verificar los valores exactos de `user?.role` que usa el proyecto (puede ser `'ceo'`, `'CEO'`, `'admin'`, `'superadmin'`, etc.). Ver `ConfigView.tsx:898` donde ya hay un gate por rol — usar el mismo valor de string que se usa ahí.

5. **Confirm flow ante 422 en TreatmentsView.tsx:** la forma exacta de presentar la confirmación (modal de diálogo vs. alert inline vs. toast con botón de confirmar) no está especificada en detalle. El apply phase debe elegir la que sea más consistente con el resto de los modales de la UI existente. Revisar cómo otros formularios en `TreatmentsView.tsx` o `PatientsView.tsx` manejan errores de validación del backend.
