# Spec — C1: TORA-Solo Quick Wins

**Change ID:** `tora-solo-quick-wins`
**Umbrella:** `openspec/changes/dual-engine-umbrella/proposal.md`
**Companion:** `proposal.md` (por cambio), `design.md`, `tasks.md` (se crean en la próxima fase)
**Status:** Draft
**Fecha:** 2026-04-07

---

## 1. Objetivos

- Eliminar la filtración de marcadores internos (`[INTERNAL_PRICE:...]`, `[INTERNAL_DEBT:...]`) en los mensajes enviados al paciente, preservando la capacidad de razonamiento del LLM.
- Prevenir la carga de precios con escala incorrecta en `treatment_types.base_price` mediante validación en escritura y pista visual en el frontend.
- Asegurar que los días feriados sean excluidos de las búsquedas de disponibilidad en todos los code paths, incluido `_get_slots_for_extra_day`.
- Propagar el parámetro `time_preference` ('mañana'/'tarde') a los días de expansión de rango para que el filtro horario sea consistente en toda la búsqueda.
- Reducir la repetición del saludo institucional completo en conversaciones ya iniciadas, usando un flag Redis con TTL de 4 horas.
- Eliminar la doble invocación del agente LangChain en la lógica dead-end recovery cuando ya se ejecutó al menos una herramienta en el primer intento.

---

## 2. Alcance

### 2.1 Bugs cubiertos en C1

| Bug # | Severidad | Descripción breve |
|-------|-----------|-------------------|
| #2 | Alta | Marcadores `[INTERNAL_PRICE/DEBT:...]` expuestos al paciente |
| #3 | Media | Precios en escala incorrecta ($7.000.000 por blanqueamiento) |
| #6 | Alta | `_get_slots_for_extra_day()` no chequea feriados |
| #7 | Media | `time_preference` no se propaga a días de expansión de rango |
| #8 | Baja | Saludo institucional completo se repite en cada turno |
| #9 | Alta | Dead-end recovery re-invoca el agente aunque ya se llamó una tool |

### 2.2 NO cubierto en C1 (va a C2 o C3)

- **Bug #1** — Parser de fechas (lógica de resolución ambigua): va a C2.
- **Bug #4** — State machine de flujo de turno (cancelación/reprogramación mid-flow): va a C2.
- **Bug #5** — `list_my_appointments` retorna vacío para pacientes con turnos activos: va a C2.
- **Engine router**, UI selector de motor, arquitectura multi-agente: van a C3.
- Refactor del array `DENTAL_TOOLS`.
- Refactor completo del system prompt.

---

## 3. Bug #2 — Strip de marcadores `[INTERNAL_*]` en outbound

### 3.1 Estado actual

- `orchestrator_service/main.py:2047` emite `[INTERNAL_PRICE:{int(avail_price)}]` como parte del output de la tool `check_availability`.
- `main.py:2053` emite de igual manera `[INTERNAL_DEBT:{int(debt_amount)}]`.
- El output de la tool vuelve al LLM para razonamiento (correcto), pero ese mismo texto termina formando parte del mensaje final enviado al paciente.
- `services/response_sender.py` (método `send_sequence`) y el bloque de envío en `services/buffer_task.py:1700-1768` no contienen ninguna expresión regular de sanitización que elimine estos marcadores antes de la salida al canal de mensajería (YCloud / Chatwoot).
- Resultado observable: el paciente recibe literalmente `[INTERNAL_PRICE:7000000]` dentro del mensaje.

### 3.2 Solución propuesta

Aplicar el strip en el único chokepoint de salida: `ResponseSender.send_sequence()` en `services/response_sender.py`, antes de que el texto sea dividido en burbujas y enviado.

**Patrón regex a aplicar:**

```python
import re

_INTERNAL_MARKER_RE = re.compile(r'\[INTERNAL_[A-Z_]+:[^\]]*\]')

def _strip_internal_markers(text: str) -> str:
    return _INTERNAL_MARKER_RE.sub('', text).strip()
```

**Dónde aplicarlo:** al inicio de `send_sequence()` (o en el helper inmediatamente anterior al split en burbujas), sobre la variable de texto completo antes de cualquier fragmentación.

**Qué NO tocar:** el output de la tool que regresa al agente LangChain. Los marcadores deben seguir presentes en `intermediate_steps` para que el LLM los use en su razonamiento. Solo se eliminan en la salida final al usuario.

**Formato del marcador a limpiar:**

- `[INTERNAL_PRICE:NNNNNNN]`
- `[INTERNAL_DEBT:NNNNNNN]`
- Patrón genérico `[INTERNAL_*:*]` para cubrir futuros marcadores sin cambio adicional.

### 3.3 Archivos afectados

- `orchestrator_service/services/response_sender.py` — añadir `_strip_internal_markers()` (función privada a nivel de módulo) e invocarla en `send_sequence()` sobre el texto saliente antes del split en burbujas.

### 3.4 Test plan

- **Unit test** (`tests/test_response_sender_strip.py`):
  1. Input: `"Tenés disponibilidad el martes [INTERNAL_PRICE:7000000]"` → output sin marcador.
  2. Input: `"[INTERNAL_DEBT:50000] Tu saldo pendiente es bajo"` → marcador al inicio eliminado.
  3. Input: `"Texto sin marcadores"` → output idéntico al input.
  4. Input: `"[INTERNAL_FOO:bar] texto [INTERNAL_PRICE:1000] fin"` → ambos marcadores eliminados.
  5. Input: `"[INTERNAL_PRICE:7000000][INTERNAL_DEBT:0]"` → string vacío o sólo espacios tras strip.
- **Integration test**: mockear `check_availability` para que su output contenga `[INTERNAL_PRICE:70000]`, ejecutar el pipeline hasta `send_sequence`, capturar el texto enviado y verificar que no contiene el substring `[INTERNAL_`.

### 3.5 Riesgos

- **Riesgo:** que el LLM dependa del marcador en el texto del mensaje final para algún razonamiento posterior. Evaluación: los marcadores son metadata que el LLM ya procesó en `intermediate_steps`; al llegar a la etapa de redacción del mensaje final el marcador no agrega información nueva. Riesgo bajo.
- **Riesgo:** que un marcador legítimo para el usuario (futuros features) use la misma sintaxis. Mitigación: el patrón `[INTERNAL_*]` por convención es solo para uso interno; documentar esto en el módulo.

---

## 4. Bug #3 — Validación de escala de precio y pista en UI

### 4.1 Estado actual

- `treatment_types.base_price` es `DECIMAL(12,2)` en la base de datos.
- El endpoint de escritura (`POST/PUT /admin/treatment-types`) no aplica ninguna validación de rango o escala sobre `base_price`.
- El renderer en `main.py:3947` aplica `f"${int(row['base_price']):,}".replace(",", ".")` directamente, sin conversión.
- El renderer en `main.py:1664-1666` lee `base_price` igualmente sin validación.
- El input del formulario en `TreatmentsView.tsx` no tiene ningún hint de unidad ni preview formateado.
- Resultado observable: si un operador ingresa `7000000` creyendo que es el precio en pesos, el bot lo muestra como `$7.000.000` cuando probablemente el valor correcto era `70000` ($70.000).

### 4.2 Solución propuesta

**a) Validador server-side en el write path:**

En `admin_routes.py`, dentro de los handlers `POST /admin/treatment-types` y `PUT /admin/treatment-types/{code}`:

1. Leer `tenant.consultation_price` del tenant activo (ya disponible en el contexto del endpoint).
2. Si `base_price > tenant.consultation_price * 100` Y el request body no incluye `confirm_unusual_price: true`, retornar HTTP 422 con:
   ```json
   {
     "detail": "Precio inusualmente alto. ¿Estás seguro? Si es correcto, incluí confirm_unusual_price=true en el cuerpo."
   }
   ```
3. Si `confirm_unusual_price=true`, la validación se omite y el precio se guarda tal cual.
4. Si `tenant.consultation_price` es NULL, el validador se omite (no hay referencia para comparar).

**b) Pista visual en el frontend:**

En `TreatmentsView.tsx` (modal de creación/edición de tratamiento):

1. Agregar label secondary debajo del input de precio: `"Ingresá el monto en pesos argentinos"`.
2. Agregar preview en vivo usando `Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' })` que se actualiza al escribir.
3. Agregar tooltip en el ícono de info junto al label: `"Ej: 70000 = $70.000 — No uses puntos ni comas, solo el número entero"`.

**c) Endpoint de auditoría:**

`GET /admin/treatments/price-audit` (requiere auth normal de admin):

```json
{
  "tenant_id": "uuid",
  "suspicious": [
    {
      "code": "BLANQUEAMIENTO",
      "name": "Blanqueamiento dental",
      "base_price": 7000000,
      "consultation_price": 15000,
      "ratio": 466.7
    }
  ]
}
```

Criterio: `base_price > tenant.consultation_price * 100`. Retorna lista vacía si no hay casos sospechosos.

En `TreatmentsView.tsx`: botón "Auditar precios" (visible solo para roles CEO/admin) que abre un modal con la lista retornada. Si la lista está vacía, muestra "Todos los precios parecen correctos".

**No se realiza ninguna migración de datos.** El operador decide manualmente si corregir los precios marcados.

### 4.3 Archivos afectados

- `orchestrator_service/admin_routes.py` — validador en POST/PUT de treatment-types + endpoint GET `/admin/treatments/price-audit`.
- `frontend_react/src/views/TreatmentsView.tsx` — hint de unidad, preview formateado, modal de auditoría.
- **Sin migración Alembic.** El campo `base_price` ya existe con el tipo correcto.

### 4.4 Test plan

- **Unit (validador):**
  1. `base_price=70000`, `consultation_price=15000` → pasa (ratio 4.7x, bajo el umbral 100x).
  2. `base_price=7000000`, `consultation_price=15000`, sin flag → HTTP 422.
  3. `base_price=7000000`, `consultation_price=15000`, `confirm_unusual_price=true` → HTTP 200.
- **Unit (audit endpoint):** mock de treatment rows con 1 sospechoso + 2 normales → verifica que solo el sospechoso aparece en `suspicious`.
- **E2E manual:** editar un tratamiento, ingresar `7000000`, intentar guardar sin flag → verificar que aparece el warning 422. Luego guardar con el flag y verificar que persiste.

### 4.5 Riesgos

- **Falsos positivos:** clínicas con implantes guiados o cirugías complejas con precios legítimamente altos (ej. $500.000 ARS). Mitigación: el umbral relativo (`consultation_price * 100`) es mucho menos restrictivo que un valor absoluto. Además, el flag `confirm_unusual_price=true` permite bypassear el warning cuando el operador confirma.
- **consultation_price NULL:** si el tenant no configuró precio de consulta, el validador no tiene referencia. Solución: skip silencioso del validador en ese caso (documentado en el código).

---

## 5. Bug #6 — Holiday check en `_get_slots_for_extra_day`

### 5.1 Estado actual

- La función `_get_slots_for_extra_day()` en `orchestrator_service/main.py:892-1075` genera slots para días adicionales durante la expansión de rango de búsqueda.
- El check de feriados mediante `check_is_holiday(target_date, tenant_id, db.pool)` sí está implementado en el path principal de `check_availability` (`main.py:1592-1612`).
- `_get_slots_for_extra_day()` no invoca `check_is_holiday` en ningún punto de su cuerpo.
- Los paths de range expansion (`pick_representative_slots` en `main.py:1076` y el loop en `main.py:1140-1170`) también están potencialmente expuestos.
- Resultado observable: el bot puede ofrecer un turno el día de un feriado nacional si ese día fue alcanzado por expansión de rango (ej. búsqueda "la próxima semana" que incluye un feriado).

### 5.2 Solución propuesta

Añadir al inicio de `_get_slots_for_extra_day()`, antes de cualquier cálculo de slots:

```python
if await check_is_holiday(target_date, tenant_id, db.pool):
    return []
```

Adicionalmente, revisar `main.py:1208-1280` (cualquier otro loop de range expansion) y aplicar el mismo guard al inicio de cada iteración sobre una fecha candidata.

La función `check_is_holiday` ya existe y ya se usa en el archivo — no hay nueva lógica que implementar, solo extender su cobertura a los code paths faltantes.

### 5.3 Archivos afectados

- `orchestrator_service/main.py` — función `_get_slots_for_extra_day` (línea ~892) y cualquier otro loop de expansión de rango identificado en la zona `main.py:1140-1280`.

### 5.4 Test plan

- **Unit (aislado):** mockear `check_is_holiday` para que retorne `True` en una fecha específica. Llamar `_get_slots_for_extra_day(target_date=fecha_feriado, ...)` y verificar que el retorno es una lista vacía.
- **Unit (negativo):** mockear `check_is_holiday` para que retorne `False`. Verificar que se devuelven slots normalmente.
- **Integration:** construir una conversación de test que solicite disponibilidad en un rango que incluya un feriado conocido (ej. 25 de mayo). Verificar que el feriado no aparece en las opciones ofrecidas.

### 5.5 Riesgos

- **Mínimo.** `check_is_holiday` ya existe, ya está testeada (implícitamente) y ya funciona en el path primario. El cambio es agregar una llamada a una función conocida en una ruta ya existente.
- **Performance:** `check_is_holiday` hace una query a la base de datos. En una expansión de rango de 7 días, se agregarían hasta 7 queries adicionales. Aceptable dado el volumen de conversaciones concurrentes esperado.

---

## 6. Bug #7 — Propagación de `time_preference` a días extra

### 6.1 Estado actual

- La función `_get_slots_for_extra_day()` tiene la firma actual:
  `_get_slots_for_extra_day(target_date, tenant_id, tenant_wh, professional_name, treatment_name, duration)`
- No recibe ni aplica el parámetro `time_preference`.
- El path principal en `main.py:672-677` aplica el filtro correctamente:
  - `time_preference == "mañana"` → descarta slots con `hour >= 13`
  - `time_preference == "tarde"` → descarta slots con `hour < 13`
- Los días de expansión de rango generados por `_get_slots_for_extra_day` ignoran completamente esta preferencia.
- Resultado observable: si el paciente pidió "un turno a la tarde", el bot puede ofrecer slots de mañana para días alternativos.

### 6.2 Solución propuesta

**Cambio en la firma:**

```python
async def _get_slots_for_extra_day(
    target_date,
    tenant_id,
    tenant_wh,
    professional_name,
    treatment_name,
    duration,
    time_preference: Optional[str] = None,  # <-- NUEVO
) -> list:
```

**Filtro a replicar dentro de la función** (mismo criterio que `main.py:672-677`):

```python
if time_preference == "mañana" and current.hour >= 13:
    continue
if time_preference == "tarde" and current.hour < 13:
    continue
```

**Actualizar todos los call sites** en `main.py` que invocan `_get_slots_for_extra_day`, pasando `time_preference` desde el contexto de `check_availability` donde ya está disponible.

### 6.3 Archivos afectados

- `orchestrator_service/main.py` — firma de `_get_slots_for_extra_day` + cuerpo de la función (filtro) + todos los call sites dentro de `check_availability` y funciones de range expansion.

### 6.4 Test plan

- **Unit (`time_preference='tarde'`):** llamar `_get_slots_for_extra_day` con `time_preference='tarde'` y verificar que ningún slot en la lista retornada tiene `hour < 13`.
- **Unit (`time_preference='mañana'`):** verificar que ningún slot tiene `hour >= 13`.
- **Unit (sin preferencia):** llamar con `time_preference=None` y verificar que se devuelven slots de ambos turnos sin filtrar.
- **Unit (día completamente vacío por filtro):** si todos los slots disponibles son de mañana y el filtro es 'tarde', verificar que el retorno es lista vacía (comportamiento esperado y documentado).

### 6.5 Riesgos

- **Días que quedan vacíos por filtro:** si el día sólo tiene disponibilidad en mañana y el paciente pidió tarde, el día retorna vacío. Esto es el comportamiento correcto. El caller (loop de range expansion) debe avanzar al siguiente día disponible. Documentar este contrato en el docstring de la función.
- **Regresión en call sites:** si algún call site no se actualiza, `time_preference` queda como `None` (valor default) y el comportamiento es idéntico al actual. Seguro, pero sin el fix. Asegurarse de buscar todos los call sites con búsqueda textual antes de cerrar el commit.

---

## 7. Bug #8 — Saludo único por sesión vía Redis flag

### 7.1 Estado actual

- `build_system_prompt` (`main.py:6171`) inyecta el bloque GREETING completo en cada turno del sistema prompt.
- El bloque GREETING (`main.py:6352-6383`) incluye frases como "Soy TORA, la asistente virtual de [clínica]" en cada invocación.
- No existe columna `greeted_at` en `patients` (`models.py:159-187`).
- No existe ningún flag Redis que registre si ya se saludó a este paciente en la sesión actual.
- Resultado observable: en conversaciones con múltiples intercambios, el LLM puede repetir el saludo institucional completo al inicio de cada respuesta, resultando en una experiencia robótica y repetitiva.

### 7.2 Solución propuesta

**Nuevo módulo:** `orchestrator_service/services/greeting_state.py`

```python
async def has_greeted(tenant_id: str, phone_number: str, redis_client) -> bool:
    key = f"greet:{tenant_id}:{phone_number}"
    return await redis_client.exists(key) == 1

async def mark_greeted(tenant_id: str, phone_number: str, redis_client) -> None:
    key = f"greet:{tenant_id}:{phone_number}"
    await redis_client.set(key, "1", ex=14400)  # TTL = 4 horas
```

**Redis key:** `greet:{tenant_id}:{phone_number}`, TTL = 14400 segundos (4 horas).

**Integración en `buffer_task.py`:**

1. Antes de llamar a `build_system_prompt`, invocar `has_greeted(tenant_id, phone_number, redis)`.
2. Pasar el resultado como kwarg `is_greeting_pending: bool` a `build_system_prompt`.

**Integración en `build_system_prompt` (`main.py:6171`):**

- Si `is_greeting_pending=False`: reemplazar el bloque GREETING completo con un placeholder corto. El placeholder usa solo la línea contextual basada en `patient_status` (ej. "El paciente ya fue atendido antes" o "Paciente con turno próximo: ...") sin la presentación institucional.
- Si `is_greeting_pending=True` (o no recibido, para compatibilidad): comportamiento actual sin cambio.

**Post-envío:** en el path de éxito de `buffer_task.py` (después de que el mensaje fue enviado exitosamente), llamar `mark_greeted(tenant_id, phone_number, redis)`.

**Fallback ante Redis caído:** si `has_greeted` lanza excepción, retornar `False` (el saludo se envía igual). Mejor saludar de más que omitir el saludo.

### 7.3 Archivos afectados

- **Nuevo:** `orchestrator_service/services/greeting_state.py`
- **Modificado:** `orchestrator_service/services/buffer_task.py` — lectura pre-build + escritura post-send
- **Modificado:** `orchestrator_service/main.py` — `build_system_prompt` consume el kwarg `is_greeting_pending`

**Sin migración de base de datos.** Estado puro en Redis con TTL.

### 7.4 Test plan

- **Unit (`greeting_state.py`):** usar `fakeredis` (o monkeypatch del cliente Redis):
  1. `has_greeted` retorna `False` cuando la key no existe.
  2. Después de `mark_greeted`, `has_greeted` retorna `True`.
  3. Expirado el TTL (avanzar reloj de fakeredis), `has_greeted` vuelve a `False`.
- **Integration:** simular dos turnos consecutivos del mismo `(tenant_id, phone)`:
  1. Primer turno: verificar que el system prompt contiene `"Soy TORA"`.
  2. Segundo turno (después de `mark_greeted`): verificar que el system prompt NO contiene `"Soy TORA"`.
- **Fallback:** mockear Redis para que lance excepción; verificar que `buffer_task.py` no explota y procede con `is_greeting_pending=True`.

### 7.5 Riesgos

- **Redis caído:** fallback seguro definido explícitamente (saludo se envía igual). Sin impacto funcional crítico.
- **Multi-process:** si múltiples workers procesan mensajes del mismo paciente simultáneamente, el flag puede no estar seteado en el segundo worker. Aceptable: el peor caso es que el saludo se envíe dos veces en una ventana muy pequeña de race condition. No es un problema de correctitud funcional.
- **TTL muy corto:** si el paciente escribe de nuevo 5 horas después, recibirá el saludo nuevamente. Esto es el comportamiento deseado (una sesión nueva merece presentación).

---

## 8. Bug #9 — Dead-end recovery solo si no hubo tool calls

### 8.1 Estado actual

- `services/buffer_task.py:1529-1588` implementa una lógica dead-end recovery: si la respuesta del LLM es corta (< umbral de caracteres) Y contiene frases de stalling ("dejame buscar", "un momento", etc.), re-invoca `executor.ainvoke()` con la esperanza de obtener una respuesta más completa.
- La condición de re-invocación NO verifica `intermediate_steps` del primer resultado.
- Si el primer `ainvoke` llamó a `check_availability` (u otra tool) y retornó un output corto, el dead-end recovery vuelve a llamar `check_availability` completo.
- Resultado observable: el paciente recibe dos respuestas de disponibilidad, o el sistema ejecuta la misma query de base de datos dos veces con posibles efectos secundarios (ej. consumo de créditos de API, locks de Redis en `confirm_slot`).

### 8.2 Solución propuesta

Modificar la condición de activación del dead-end recovery en `buffer_task.py:1529-1588`:

**Condición actual (implícita):**
```python
if is_dead_end_phrase(output) and len(output) < 200:
    result = await executor.ainvoke(...)  # re-invocación
```

**Condición propuesta:**
```python
intermediate_steps = result.get('intermediate_steps', [])
tool_was_called = len(intermediate_steps) > 0

if is_dead_end_phrase(output) and len(output) < 200 and not tool_was_called:
    result = await executor.ainvoke(...)  # solo re-invocar si no se usó ninguna tool
```

**Lógica:** si `intermediate_steps` contiene al menos un elemento, el agente ya ejecutó una herramienta. Una respuesta corta después de ejecutar una tool es un problema de redacción del LLM, no de falta de datos. Re-invocar en ese caso es doblemente incorrecto: duplica la acción y probablemente produce el mismo output corto.

El dead-end recovery queda activo exclusivamente para el caso donde el LLM generó una frase de stalling SIN haber llamado ninguna herramienta (ej. el LLM alucinó una respuesta de "voy a buscar" sin realmente buscar).

### 8.3 Archivos afectados

- `orchestrator_service/services/buffer_task.py:1529-1588` — condición de activación del dead-end recovery.

### 8.4 Test plan

- **Unit (tool ya llamada):** mock de `executor.ainvoke` que retorna `{output: "dejame buscar un momento", intermediate_steps: [("check_availability", {...result...})]}`. Verificar que NO se realiza una segunda llamada a `executor.ainvoke`.
- **Unit (sin tool, dead-end legítimo):** mock que retorna `{output: "dejame buscar", intermediate_steps: []}`. Verificar que SÍ se realiza la segunda invocación.
- **Unit (sin dead-end phrase):** mock con respuesta larga y steps vacíos → sin re-invocación.
- **Unit (tool llamada, respuesta larga):** mock con steps no vacíos y respuesta > 200 chars → sin re-invocación.

### 8.5 Riesgos

- **Caso borde:** un LLM que genuinamente necesita re-invocar después de una tool (ej. tool retornó error y el LLM no sabe cómo continuar) no recibirá la segunda oportunidad. Evaluación: en ese caso, el siguiente mensaje del usuario activa el ciclo completo nuevamente. El costo de este falso negativo es bajo comparado con el daño del duplicado.
- **Compatibilidad con `intermediate_steps`:** si la estructura del resultado de `ainvoke` cambia en versiones futuras de LangChain, `result.get('intermediate_steps', [])` retorna `[]` por default, lo cual deshabilita el dead-end recovery (comportamiento conservador, no catastrófico).

---

## 9. Plan de migración (orden de aplicación)

El orden recomendado para aplicar los 6 fixes en commits separados:

1. **Bug #9 (dead-end recovery)** — Primero. Es el fix más aislado (una sola función, sin dependencias externas) y reduce el ruido en las pruebas de los demás bugs al evitar dobles invocaciones.

2. **Bug #2 (strip markers)** — Segundo. Alta severidad y cero riesgo de regresión. El test se puede ejecutar de manera completamente aislada.

3. **Bug #6 (holiday check)** — Tercero. Función ya existente, solo se extiende su cobertura. Sin dependencias nuevas.

4. **Bug #7 (time_preference)** — Cuarto. Depende del mismo entorno que Bug #6 (misma función `_get_slots_for_extra_day`). Aplicar en el mismo PR o commit siguiente para facilitar la revisión.

5. **Bug #8 (saludo Redis)** — Quinto. Introduce un módulo nuevo (`greeting_state.py`) y modifica tres archivos. Separado para que el reviewer pueda aprobar el módulo nuevo de manera limpia.

6. **Bug #3 (price scale)** — Último. Es el más amplio: toca backend (validador + endpoint de auditoría) y frontend (UI hint + modal). Dejarlo al final permite que los fixes anteriores ya estén mergeados y el entorno de test esté estable.

**Paralelización posible:** Los bugs #2, #6 y #9 son completamente independientes entre sí y entre sí con los demás. Tres desarrolladores pueden trabajar en ellos simultáneamente. Los bugs #7 y #6 comparten el mismo archivo/función — coordinar para evitar conflictos de merge.

---

## 10. Definition of Done

- [ ] Cada uno de los 6 bugs tiene al menos 1 unit test que **falla en `main`** y **pasa con el fix aplicado**
- [ ] Los 6 fixes están en commits separados (un commit por bug, con mensaje conventional commit)
- [ ] Conversación manual de smoke test reproduce CERO de los 6 bugs en entorno local
- [ ] `pytest tests/` pasa sin regresiones nuevas
- [ ] No hay cambios en `CLAUDE.md` (se actualiza al cierre del umbrella C1+C2+C3)
- [ ] El endpoint `GET /admin/treatments/price-audit` está documentado en Swagger (docstring FastAPI)
- [ ] `greeting_state.py` tiene docstring de módulo explicando el contrato Redis key/TTL

---

## 11. Out of scope

- **Bug #1** — Ambigüedad del date parser (`interpreted_date`, `search_mode`): va a C2.
- **Bug #4** — State machine de flujo de reserva/cancelación mid-conversation: va a C2.
- **Bug #5** — `list_my_appointments` retorna vacío con turnos activos: va a C2.
- Engine router y UI selector de motor conversacional: van a C3.
- Arquitectura multi-agente y separación `TORA_TOOLS` / `NOVA_TOOLS`: va a C3.
- Refactor del array `DENTAL_TOOLS` en `main.py`.
- Refactor estructural del system prompt completo.
- Ninguna migración Alembic: C1 es cero cambios de esquema. Todos los fixes son código + Redis.
