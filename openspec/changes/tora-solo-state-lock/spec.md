# Spec — C2: TORA-Solo State Lock + Date Validator

**Change ID:** `tora-solo-state-lock`
**Umbrella:** `openspec/changes/dual-engine-umbrella/proposal.md`
**Companion:** `proposal.md` (por change), `design.md`, `tasks.md` (fase siguiente)
**Status:** Draft
**Fecha:** 2026-04-07

---

## 1. Objetivos

1. **Eliminar la inversión DD/MM → MM/DD en el texto de respuesta del LLM**: un validador de presentación, ejecutado post-`ainvoke` y pre-send, detecta y corrige automáticamente cualquier fecha que el LLM reformatee respecto del valor canónico devuelto por la tool.
2. **Introducir un state machine programático por conversación**: almacenado en Redis, keyed por `(tenant_id, phone_number)`, que fuerza a TORA a transitar correctamente de `OFFERED_SLOTS` → `SLOT_LOCKED` → `BOOKED` sin depender únicamente del system prompt.
3. **Garantizar que `list_my_appointments` encuentre el turno recién creado**: unificando el path de normalización de teléfono con la función `normalize_phone_digits()` ya existente, eliminando el posible mismatch entre la query SQL y el código Python.
4. **Mantener comportamiento degradado seguro cuando Redis no esté disponible**: todos los nuevos componentes basados en Redis deben fallar silenciosamente hacia `IDLE`, preservando el comportamiento actual como fallback.
5. **Proveer cobertura de tests verificable**: cada fix debe tener casos unit/integration que sean ejecutables con `pytest` sin infraestructura externa (mocks de Redis permitidos).

---

## 2. Alcance

### 2.1 Bugs cubiertos en C2

| # | Severidad | Descripción |
|---|-----------|-------------|
| 1 | 🔴 CRÍTICO | Fecha invertida en confirmación: el LLM reformatea `12/05` → `05/12` en su texto de respuesta, independientemente del valor correcto que retornó la tool |
| 4 | 🔴 CRÍTICO | Pérdida de state tras "Agéndame el del X": el LLM re-llama `check_availability` en lugar de `confirm_slot` → `book_appointment`, rompiendo el flujo de reserva |
| 5 | 🟠 ALTO | `list_my_appointments` retorna "sin turnos" inmediatamente después de crear el turno; causa vinculada al Bug #4 y a potencial mismatch en normalización de teléfono |

### 2.2 NO cubierto en C2

- **Quick wins (C1):** mejoras de prompt aisladas, logs de debug, ajustes de texto — corresponden al change `tora-solo-quick-wins`.
- **Engine router + UI selector (C3):** arquitectura dual TORA/Nova, routing por canal, selector de motor en el frontend — corresponde al change `dual-engine-router`.
- **Refactor completo del system prompt:** limpieza total de las instrucciones de flujo en `main.py:6713-6840` — fuera de alcance; solo se añade el bloque de hardening de fechas y el slot de inyección de `STATE_HINT`.
- **Eliminación del soft-lock Redis existente (`slot_lock:`):** el slot lock de 120s en `main.py:4555-4568` coexiste con el nuevo state machine. No se toca.
- **Migraciones Alembic:** C2 no introduce cambios en el esquema de base de datos. Toda la persistencia nueva es Redis.
- **Nova (voice assistant):** fuera de scope.

---

## 3. Bug #1 — Date validator en presentation layer

### 3.1 Estado actual y diagnóstico real

**Importante:** este bug NO es del parser Python. La exploración previa confirmó:
- `parse_date()` en `main.py:1472` usa `dateutil.parser.parse(..., dayfirst=True)` correctamente.
- `book_appointment` en `main.py:2189` también resuelve la fecha con `dayfirst=True`.
- `opt['date_display']` en `main.py:2038` se construye a partir del objeto `date` ya parseado — el valor es correcto.

**Causa real:** el LLM, al generar el texto de respuesta *después* de recibir el resultado de la tool, reformatea la fecha de forma autónoma. La tool retorna `date_display='12/05'` (12 de mayo) y el LLM escribe en su respuesta "Sábado 05/12" (interpretando incorrectamente el formato MM/DD).

Este comportamiento es no determinístico y no puede corregirse solo con el parser Python. Requiere una capa de validación post-LLM.

**Verificado por:** explore agent, conversación de smoke con Juan Román Riquelme.

### 3.2 Solución: validador post-LLM en presentation layer

El validador se ejecuta en `services/buffer_task.py`, en el punto exacto después de `executor.ainvoke()` y antes de `response_sender.send_sequence()` (aproximadamente `buffer_task.py:998-1507`).

Flujo de ejecución por turno:
```
executor.ainvoke(input)
  → result = {output: str, intermediate_steps: list}
  → canonical_dates = extract_canonical_dates(result.intermediate_steps)  ← nuevo
  → corrected_output = validate_and_correct_dates(result.output, canonical_dates)  ← nuevo
  → response_sender.send_sequence(corrected_output)
```

El validador nunca bloquea ni lanza excepciones hacia el exterior. Si falla internamente, loguea y devuelve el texto original sin modificar.

### 3.3 Algoritmo del validador

**Módulo:** `orchestrator_service/services/date_validator.py`

```
función extract_canonical_dates(intermediate_steps: list) → dict[str, str]:
  """
  Recorre los outputs de cada tool en intermediate_steps.
  Busca claves 'date_display', 'fecha', 'date' en los dicts de resultado.
  Retorna: { 'canonico_raw': 'display_string' }
    ej: { '2025-05-12': '12/05', '2025-06-03': '03/06/2025' }
  """
  dates = {}
  para cada (action, observation) en intermediate_steps:
    si observation es dict:
      para cada key en ['date_display', 'fecha', 'appointment_date', 'date']:
        si key existe en observation:
          parsear el valor → objeto date
          agregar a dates[iso_string] = valor_display_original
  retornar dates

función validate_and_correct_dates(llm_text: str, canonical_dates: dict) → str:
  """
  Busca patrones de fecha en llm_text via regex.
  Compara contra canonical_dates.
  Si encuentra un swap (DD↔MM), reemplaza con el canónico.
  """
  si canonical_dates está vacío: retornar llm_text sin cambios

  PATTERN = r'\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b'

  para cada match en PATTERN.finditer(llm_text):
    parte_a = match.group(1)  # lo que el LLM puso como "día"
    parte_b = match.group(2)  # lo que el LLM puso como "mes"

    para cada (iso_date, display) en canonical_dates:
      dia_canonico, mes_canonico = extraer de iso_date

      si parte_a == mes_canonico Y parte_b == dia_canonico:
        # Swap detectado: LLM invirtió DD/MM
        reemplazar match.group(0) con display (el canónico)
        log.warning(f"[DateValidator] Corrección: '{match.group(0)}' → '{display}'")
        break

  retornar texto corregido

función correct_weekday_date_mismatch(llm_text: str, canonical_dates: dict) → str:
  """
  Detecta patrones "Día NombreDiaSemana DD/MM" donde DD/MM está swapeado.
  Reemplaza solo la parte de fecha, preservando el nombre del día de semana.
  """
  WEEKDAY_PATTERN = r'(Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'
  # lógica similar a validate_and_correct_dates pero sobre el grupo de fecha
  ...
```

La función principal expuesta al exterior es:

```
función validate_dates_in_response(llm_text: str, intermediate_steps: list) → str:
  canonical = extract_canonical_dates(intermediate_steps)
  text = validate_and_correct_dates(llm_text, canonical)
  text = correct_weekday_date_mismatch(text, canonical)
  retornar text
```

### 3.4 Hardening del system prompt

Añadir al bloque de instrucciones de reserva en `main.py` (cerca de la línea 6713), bajo la sección de PASO 4 o en un bloque dedicado de "Reglas de formato":

```
## Regla de formato de fechas (OBLIGATORIA)
Cuando menciones una fecha en tu respuesta (en cualquier formato: DD/MM, DD/MM/AAAA,
"Lunes 12 de mayo", etc.), copiala TAL CUAL viene del resultado de la tool.
NUNCA reformatees la fecha. NUNCA inviertas el día y el mes.
Si la tool retornó "12/05", vos escribís "12/05". No "05/12". No "mayo 12". No "12/5/2025" si la tool no lo puso así.
```

Este texto es un **safety net de segundo nivel**. El validador de código es la barrera principal.

### 3.5 Archivos afectados

| Archivo | Tipo de cambio | Descripción |
|---------|----------------|-------------|
| `orchestrator_service/services/date_validator.py` | **Nuevo** | Módulo completo del validador: `extract_canonical_dates`, `validate_and_correct_dates`, `correct_weekday_date_mismatch`, `validate_dates_in_response` |
| `orchestrator_service/services/buffer_task.py` | **Modificado** | Insertar llamada a `validate_dates_in_response` entre `executor.ainvoke()` y `response_sender.send_sequence()` (~línea 998-1507) |
| `orchestrator_service/main.py` | **Modificado** | Añadir bloque de hardening de fechas al system prompt (~línea 6713-6840) |

### 3.6 Test plan

**Unit tests (`tests/test_date_validator.py`):**

| Caso | Input LLM | Canónico (tool) | Expected output |
|------|-----------|-----------------|-----------------|
| 1 | "Te confirmo el turno para el 05/12" | `date_display='12/05'` | "Te confirmo el turno para el 12/05" |
| 2 | "Sábado 05/12 a las 14:00" | `date_display='12/05'` | "Sábado 12/05 a las 14:00" |
| 3 | "12/05 a las 10:00" | `date_display='12/05'` | "12/05 a las 10:00" (sin cambio) |
| 4 | Sin fechas en respuesta | `date_display='12/05'` | Texto sin cambio |
| 5 | Sin tool results con fechas | Texto con "05/12" | Texto sin cambio (no corrige sin canónico) |
| 6 | "03/06/2025" | `date_display='03/06/2025'` | Sin cambio (correcto) |
| 7 | "06/03/2025" | `date_display='03/06/2025'` | "03/06/2025" |
| 8 | "Lunes 07/04 y Miércoles 09/04" (dos fechas, ambas correctas) | dos canónicos correctos | Sin cambio |
| 9 | "Lunes 04/07 y Miércoles 04/09" (ambas invertidas) | `07/04` y `09/04` | "Lunes 07/04 y Miércoles 09/04" |
| 10 | Intermediate steps sin estructura de dict (string raw) | — | Texto sin cambio (no crashea) |

**Integration tests:**
- Simular un `intermediate_steps` con output de `check_availability` que incluye `date_display='12/05'`, y un `llm_text` con "05/12" → verificar que el texto resultante contiene "12/05".
- Verificar que el validador no modifica textos donde la fecha ya está correcta.

**Smoke manual:**
- Reproducir la conversación reportada con Juan Román Riquelme (fecha 12 de mayo invertida) → validar que la respuesta enviada al paciente muestra "12/05" y no "05/12".

### 3.7 Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Falso positivo: el validador corrige una fecha que el LLM puso intencionalmente en formato diferente | Baja | Medio | Solo corrige si existe `date_display` canónico en `intermediate_steps` de la misma respuesta. Sin canónico, no actúa. |
| Regex no captura formatos textuales ("doce de mayo") | Media | Bajo | El validador cubre formatos numéricos. Formatos textuales no son afectados por el swap DD/MM. Aceptable. |
| Performance overhead | Muy baja | Muy bajo | Se ejecuta una vez por turno de conversación, sobre un string de texto corto. Costo despreciable. |
| El validador oculta el bug en lugar de corregirlo | N/A | Bajo | Es un safety net explícito, documentado. El hardening del prompt es la solución de raíz complementaria. |

---

## 4. Bug #4 — Conversation state machine en Redis

### 4.1 Estado actual

- **No existe estado programático entre turnos de conversación.** El flujo de reserva (availability → confirm → book) está definido exclusivamente en el system prompt (`main.py:6713-6840`).
- El LLM, al ser stateless por naturaleza, puede ignorar o malinterpretar las instrucciones del prompt y re-llamar `check_availability` cuando el usuario ya eligió un slot.
- El soft-lock Redis de 120s en `main.py:4504` y `main.py:4555-4568` existe para el slot individual (key `slot_lock:{tenant_id}:{slot_hash}`), pero no modela el estado de la conversación.
- Consecuencia observable: el usuario dice "Agéndame el del 12 de mayo" y TORA responde con nuevas opciones de disponibilidad en lugar de proceder con la confirmación.

### 4.2 Diseño del state machine

#### 4.2.1 Estados

| Estado | Descripción | TTL | Transiciones válidas desde este estado |
|--------|-------------|-----|----------------------------------------|
| `IDLE` | Estado por defecto. Ningún flujo de reserva en curso. | — (no existe key en Redis) | → `OFFERED_SLOTS` |
| `OFFERED_SLOTS` | `check_availability` retornó opciones al paciente. El paciente todavía no eligió. | 1800s | → `SLOT_LOCKED`, → `IDLE` (cancelación explícita o TTL) |
| `SLOT_LOCKED` | `confirm_slot` ejecutado exitosamente. Slot reservado soft. | 1800s | → `BOOKED`, → `PAYMENT_PENDING`, → `OFFERED_SLOTS` (rechazo del slot), → `IDLE` |
| `BOOKED` | `book_appointment` exitoso. Turno confirmado en base de datos. Sin seña requerida. | 1800s | → `IDLE` (turno cancelado o TTL) |
| `PAYMENT_PENDING` | `book_appointment` exitoso pero requiere seña (depósito bancario). Esperando comprobante. | 1800s | → `PAYMENT_VERIFIED`, → `IDLE` |
| `PAYMENT_VERIFIED` | `verify_payment_receipt` exitoso. Pago confirmado. | 1800s | → `IDLE` (TTL o reset explícito) |

**Nota:** `IDLE` no tiene key en Redis — es el estado inferido cuando la key no existe o expiró.

#### 4.2.2 Diagrama de transiciones

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
                    ▼                                         │
              ┌─────────┐                                     │
              │  IDLE   │ ◄─── TTL expiry (cualquier estado) │
              └────┬────┘ ◄─── cancel/reschedule             │
                   │                                         │
          check_availability OK                              │
                   │                                         │
                   ▼                                         │
          ┌────────────────┐                                 │
          │ OFFERED_SLOTS  │ ◄─── rechazo de slot confirmado │
          └───────┬────────┘                                 │
                  │                                          │
          confirm_slot OK                                    │
                  │                                          │
                  ▼                                          │
          ┌──────────────┐                                   │
          │ SLOT_LOCKED  │ ──── slot rechazado ──────────────┘
          └──────┬───────┘
                 │
         book_appointment OK
         ┌───────┴────────┐
         │                │
    sin seña          con seña requerida
         │                │
         ▼                ▼
     ┌────────┐    ┌─────────────────┐
     │ BOOKED │    │ PAYMENT_PENDING │
     └────────┘    └────────┬────────┘
                            │
                  verify_payment_receipt OK
                            │
                            ▼
                   ┌─────────────────┐
                   │ PAYMENT_VERIFIED │
                   └─────────────────┘
```

#### 4.2.3 Storage en Redis

**Key:** `convstate:{tenant_id}:{phone_number_normalized}`

- `phone_number_normalized`: resultado de `normalize_phone_digits(phone_number)` — misma función que el resto del sistema.

**Value (JSON serializado):**
```json
{
  "state": "OFFERED_SLOTS",
  "last_offered_slots": [
    {
      "date": "2025-05-12",
      "time": "10:00",
      "professional_id": 3,
      "professional_name": "Dra. García",
      "service": "Consulta general",
      "slot_index": 1
    }
  ],
  "last_locked_slot": null,
  "updated_at": "2026-04-07T14:32:00Z"
}
```

**TTL:** 1800 segundos (30 minutos). Si expira, el estado vuelve a `IDLE` implícitamente.

**Operaciones atómicas:** usar `SET key value EX 1800` para writes (atómico con TTL). Usar `GET` + `json.loads` para reads.

### 4.3 Hooks en las tools (`main.py`)

Cada hook es una llamada asincrónica al módulo `conversation_state.py` al final de la ejecución exitosa de la tool. Si Redis no está disponible, el hook falla silenciosamente (log warning, no exception).

| Tool | Línea aprox. | Acción de state |
|------|-------------|-----------------|
| `check_availability` | ~main.py:2038 (post-construcción de `opt`) | `set_state(tenant_id, phone, OFFERED_SLOTS, last_offered_slots=[...opciones retornadas...])`  |
| `confirm_slot` | ~main.py:4504 (post-Redis slot lock exitoso) | `set_state(tenant_id, phone, SLOT_LOCKED, last_locked_slot={...slot...})` |
| `book_appointment` | ~main.py:2189 (post-INSERT exitoso) | Si seña requerida → `set_state(..., PAYMENT_PENDING)`. Si no → `set_state(..., BOOKED)` |
| `verify_payment_receipt` | (post-verificación exitosa) | `set_state(tenant_id, phone, PAYMENT_VERIFIED)` |
| `cancel_appointment` | (post-cancelación exitosa) | `reset_state(tenant_id, phone)` → IDLE |
| `reschedule_appointment` | (post-reprogramación exitosa) | `reset_state(tenant_id, phone)` → IDLE |

Los valores de `tenant_id` y `phone` se obtienen de `current_tenant_id.get()` y `current_customer_phone.get()` (context vars ya disponibles en todas las tools, patrón existente en `main.py`).

### 4.4 Guards en `buffer_task.py`

#### 4.4.1 Input-side guard (pre-`ainvoke`)

**Posición:** inmediatamente antes de la llamada a `executor.ainvoke(input)` en `buffer_task.py`.

**Lógica:**

```
state_data = await conversation_state.get_state(tenant_id, phone_number)
current_state = state_data.get("state", "IDLE")

si current_state == "OFFERED_SLOTS":
  si user_message_has_selection_intent(user_message):
    # Inyectar STATE_HINT en el system prompt del input
    input["system_hint"] = (
      "[STATE_HINT: El paciente está seleccionando un slot ya ofrecido. "
      "Próximo paso: llamar confirm_slot con el slot elegido, luego book_appointment. "
      "NO volver a llamar check_availability salvo que el paciente diga explícitamente "
      "que quiere otras opciones, otra fecha, u otro horario.]"
    )
```

**Función `user_message_has_selection_intent(text: str) → bool`:**

Retorna `True` si el texto del usuario contiene alguno de estos patrones (case-insensitive, normalización de acentos):
- Dígito solo o al inicio: `^[1-9]$`, `^el [1-9]`, `^opcion [1-9]`
- Palabras de confirmación de selección: `agéndame`, `reservame`, `dale`, `ese`, `esa`, `ese mismo`, `el primero`, `el segundo`, `el tercero`, `el de las`, `el del [número de día]`, `perfecto`, `listo`, `confirmá`, `confirma`, `sí ese`, `quiero ese`
- Frases compuestas: `agéndame el del \d+`, `el (lunes|martes|...) a las \d+`

**Importante:** la inyección del `STATE_HINT` se hace en el campo de input del executor, no mutando el system prompt global. La implementación exacta depende de cómo el executor acepta el sistema de hints (ver `design.md`).

#### 4.4.2 Output-side guard (post-`ainvoke`, pre-send)

**Posición:** inmediatamente después de `executor.ainvoke(input)` y antes del date validator y el send.

**Lógica:**

```
si current_state == "OFFERED_SLOTS":
  tools_called = extraer nombres de tools de intermediate_steps

  si "check_availability" en tools_called Y "confirm_slot" NO en tools_called:
    si NOT user_message_has_requery_intent(user_message):
      # El LLM ignoró el intent de selección y re-buscó disponibilidad
      # → Retry con nudge más fuerte
      si retry_count < 1:  # Limit: un solo retry
        input["force_confirm_hint"] = (
          "[CORRECCIÓN: El paciente YA eligió un slot en el turno anterior. "
          "Debés llamar confirm_slot y luego book_appointment. "
          "No busques nueva disponibilidad.]"
        )
        result = await executor.ainvoke(input)  # segundo intento
        retry_count += 1
```

**Función `user_message_has_requery_intent(text: str) → bool`:**

Retorna `True` si el texto contiene indicación explícita de querer buscar de nuevo:
- "otra fecha", "otro día", "otro horario", "más opciones", "no me sirven", "no puedo ese día", "hay otro", "alguna otra", "diferente", "cambiar", "no me convence"

**Límite de retry:** exactamente 1. Si el segundo intento también llama `check_availability`, se envía el resultado sin más reintentos y se loguea como `[StateGuard] RETRY_EXHAUSTED`.

### 4.5 Archivos afectados

| Archivo | Tipo de cambio | Descripción |
|---------|----------------|-------------|
| `orchestrator_service/services/conversation_state.py` | **Nuevo** | Módulo completo: `get_state`, `set_state`, `reset_state`, `ConversationState` enum, lógica Redis con fallback |
| `orchestrator_service/services/buffer_task.py` | **Modificado** | Input-side guard (pre-ainvoke), output-side guard (post-ainvoke), integración con `conversation_state` |
| `orchestrator_service/main.py` | **Modificado** | Hooks al final de `check_availability`, `confirm_slot`, `book_appointment`, `verify_payment_receipt`, `cancel_appointment`, `reschedule_appointment` |

### 4.6 Test plan

**Unit tests (`tests/test_conversation_state.py`):**

| Caso | Descripción |
|------|-------------|
| 1 | Transición IDLE → OFFERED_SLOTS vía `set_state` |
| 2 | Transición OFFERED_SLOTS → SLOT_LOCKED vía `set_state` |
| 3 | Transición SLOT_LOCKED → BOOKED |
| 4 | Transición SLOT_LOCKED → PAYMENT_PENDING |
| 5 | Transición PAYMENT_PENDING → PAYMENT_VERIFIED |
| 6 | `reset_state` desde cualquier estado → IDLE (key eliminada) |
| 7 | TTL expiry → `get_state` retorna IDLE |
| 8 | Redis caído → `get_state` retorna `{"state": "IDLE"}` sin excepción |
| 9 | Redis caído → `set_state` falla silenciosamente (log warning, no exception) |
| 10 | `last_offered_slots` persiste correctamente en el JSON |

**Unit tests — input-side guard (`tests/test_state_guards.py`):**

| Caso | User message | Estado actual | Expected hint inyectado |
|------|-------------|---------------|-------------------------|
| 1 | "1" | OFFERED_SLOTS | STATE_HINT inyectado |
| 2 | "el primero" | OFFERED_SLOTS | STATE_HINT inyectado |
| 3 | "agéndame el del 12 de mayo" | OFFERED_SLOTS | STATE_HINT inyectado |
| 4 | "ese" | OFFERED_SLOTS | STATE_HINT inyectado |
| 5 | "dale, el de las 10" | OFFERED_SLOTS | STATE_HINT inyectado |
| 6 | "listo, confirmá el primero" | OFFERED_SLOTS | STATE_HINT inyectado |
| 7 | "agéndame el del martes" | OFFERED_SLOTS | STATE_HINT inyectado |
| 8 | "¿hay alguno más temprano?" | OFFERED_SLOTS | Sin hint (requery intent) |
| 9 | "el martes 12 de mayo" | IDLE | Sin hint (estado IDLE) |
| 10 | "quiero cancelar" | OFFERED_SLOTS | Sin hint (no es selección) |

**Unit tests — output-side guard:**

| Caso | Estado previo | Tools llamadas por LLM | User re-query? | Expected behavior |
|------|--------------|------------------------|----------------|-------------------|
| 1 | OFFERED_SLOTS | check_availability (sin confirm_slot) | No | Retry con force_confirm_hint |
| 2 | OFFERED_SLOTS | check_availability (sin confirm_slot) | Sí ("otra fecha") | Sin retry |
| 3 | OFFERED_SLOTS | confirm_slot, book_appointment | No | Sin retry (correcto) |
| 4 | OFFERED_SLOTS | check_availability (segundo retry también) | No | log RETRY_EXHAUSTED, send resultado |
| 5 | IDLE | check_availability | No | Sin retry (estado IDLE, normal) |

**Integration test:**

- Replay de la conversación de Juan Román Riquelme completa:
  - Mensaje 1: solicitud de turno → TORA responde con opciones → estado = `OFFERED_SLOTS`
  - Mensaje 2: "Agéndame el del 12 de mayo" → guard inyecta STATE_HINT → LLM llama `confirm_slot` → `book_appointment` → estado = `BOOKED`
  - Verificar que NO se llamó `check_availability` en el turno 2.
  - Verificar que el estado en Redis después del turno 2 es `BOOKED`.

### 4.7 Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Falso positivo en intent detection: usuario dice "1" en contexto no relacionado (ej: "mi hijo tiene 1 año") | Baja | Medio | El hint es una **sugerencia**, no una orden forzada al LLM. El contexto conversacional completo permite al LLM ignorarlo si es semánticamente incorrecto. |
| Redis caído o timeout | Baja (producción) | Bajo | Fallback explícito a IDLE. Comportamiento idéntico al actual. El sistema no rompe. |
| State desactualizado: dos mensajes del mismo paciente llegan simultáneamente y hay race condition en el write | Muy baja | Bajo | El buffer serializa mensajes por `(tenant_id, phone)`. No es un problema real en la arquitectura actual. |
| El output-side guard con retry duplica tokens y costo en OpenAI | Media (si el retry es frecuente) | Medio | El retry está limitado a 1 por turno. Si el problema persiste después del retry, se envía el resultado y se loguea. Monitorear frecuencia de `RETRY_EXHAUSTED` logs en las primeras semanas. |
| El state machine no se resetea si una tool falla a mitad de flujo | Media | Medio | Las tools ya tienen manejo de excepciones. Si `confirm_slot` falla, no hace la transición. Si `book_appointment` falla post-`confirm_slot`, el estado queda en `SLOT_LOCKED` hasta TTL (30min). El TTL es el mecanismo de reset de emergencia. |

---

## 5. Bug #5 — Phone normalization unificada + diagnóstico

### 5.1 Estado actual

Existen dos paths distintos de normalización de teléfono para el mismo propósito (encontrar al paciente por teléfono):

**Path A — `book_appointment` (`main.py:2189`):**
Usa `normalize_phone_digits()` definida en `main.py:269`. Esta función aplica reglas Python sobre el string (strips non-numeric, normaliza prefijos de país).

**Path B — `list_my_appointments` (`main.py:3360-3433`):**
Usa directamente `REGEXP_REPLACE(p.phone_number, '[^0-9]', '', 'g')` en SQL (`main.py:3383`).

**Problema potencial:** si `normalize_phone_digits()` aplica reglas adicionales (ej: remover el `0` de prefijo local, normalizar el `9` de Argentina, manejar el `+54`) que el `REGEXP_REPLACE` SQL no replica exactamente, los teléfonos guardados por `book_appointment` no matchean los que busca `list_my_appointments`.

**Causa secundaria vinculada a Bug #4:** si el booking nunca ocurre (porque el LLM re-llamó `check_availability`), `list_my_appointments` siempre va a retornar vacío. Bug #4 fix → Bug #5 se resuelve parcialmente.

### 5.2 Solución

**Paso 1 — Diagnóstico primero (antes de corregir):**
Añadir log INFO al inicio de `list_my_appointments` (`main.py:3360`):
```python
logger.info(
  f"[list_my_appointments] tenant={tenant_id} "
  f"input_phone='{phone_raw}' "
  f"normalized='{normalize_phone_digits(phone_raw)}'"
)
```
Y al final del resultado:
```python
logger.info(f"[list_my_appointments] results_count={len(appointments)}")
```

**Paso 2 — Unificar normalización:**
Refactorizar `list_my_appointments` para usar `normalize_phone_digits()` en Python antes de la query SQL, y pasar el valor normalizado como parámetro:
```sql
-- Antes:
WHERE REGEXP_REPLACE(p.phone_number, '[^0-9]', '', 'g') = $2

-- Después:
WHERE REGEXP_REPLACE(p.phone_number, '[^0-9]', '', 'g') = $2
-- donde $2 ya es normalize_phone_digits(input_phone)
```

Esto asegura que ambos paths normalizan con la misma función. Si en el futuro `normalize_phone_digits()` cambia, el cambio afecta ambos paths simultáneamente.

**Nota:** mantener el `REGEXP_REPLACE` en SQL para normalizar el lado almacenado (en caso de que teléfonos históricos tengan formatos variados). El parámetro `$2` ahora llega pre-normalizado.

**Paso 3 — Test integrado:**
Añadir test que ejecuta `book_appointment` y luego `list_my_appointments` para el mismo paciente y verifica que el turno aparece.

### 5.3 Archivos afectados

| Archivo | Tipo de cambio | Descripción |
|---------|----------------|-------------|
| `orchestrator_service/main.py:3360-3433` | **Modificado** | Añadir logs INFO de diagnóstico; usar `normalize_phone_digits()` antes de pasar el parámetro a la query SQL |

### 5.4 Test plan

**Unit tests — phone normalization (`tests/test_phone_normalization.py`):**

| Caso | Input | Expected output de `normalize_phone_digits` |
|------|-------|---------------------------------------------|
| 1 | `+5491112345678` | `5491112345678` |
| 2 | `1112345678` | `1112345678` |
| 3 | `01112345678` | `1112345678` (strip leading 0) |
| 4 | `5491112345678` | `5491112345678` |
| 5 | `+54 9 11 1234-5678` | `5491112345678` (strip spaces y guiones) |

**Integration test (`tests/test_booking_flow.py`):**

```
# Secuencia completa
1. Crear paciente vía insert directo con phone='+5491112345678'
2. Llamar book_appointment para ese paciente → turno ID retornado
3. Llamar list_my_appointments con phone='+5491112345678'
4. Assert: el turno del paso 2 aparece en el resultado del paso 3
```

### 5.5 Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Cambio en normalización rompe patients históricos con formato diferente | Muy baja | Bajo | El `REGEXP_REPLACE` del lado DB sigue normalizando ambos lados. El cambio solo afecta cómo se prepara el parámetro `$2`. |
| Los logs de diagnóstico generan ruido en producción | Baja | Muy bajo | Son logs `INFO`, controlables con nivel de log. En producción, el log de nivel `WARNING+` ya los filtraría. |

---

## 6. Plan de aplicación

El orden de implementación es deliberado y va de menor a mayor riesgo arquitectónico:

### Orden recomendado:

**1. Bug #5 — Phone normalization (primero, más aislado y más bajo riesgo)**
- Cambio localizado en una función dentro de `main.py`.
- Sin dependencias con los otros dos fixes.
- Añade visibilidad diagnóstica inmediata con los logs.
- Si algo sale mal, el rollback es trivial (revertir 5-10 líneas).

**2. Bug #1 — Date validator (segundo, módulo nuevo aislado)**
- Módulo nuevo `date_validator.py` completamente aislado.
- Un único punto de integración en `buffer_task.py` (una línea de llamada).
- No modifica ninguna lógica existente, solo añade una transformación sobre el string de output.
- Si el validador falla, el fallback es devolver el texto original (no hay regresión).
- El hardening del system prompt es un cambio de texto puro, sin riesgo de código.

**3. Bug #4 — State machine (último, mayor riesgo y mayor superficie de cambio)**
- Módulo nuevo `conversation_state.py` + modificaciones en `buffer_task.py` + hooks en 6 tools en `main.py`.
- Mayor superficie de cambio: cualquier tool del flujo de reserva queda afectada.
- Los guards en `buffer_task.py` cambian el flujo de invocación del executor.
- Implementar primero en modo "observación": el state machine escribe y lee, pero los guards solo loguean sin actuar (feature flag). Verificar estado correcto en logs antes de activar los guards.

**Razón del orden:** cada fix es independiente. Aplicar en orden de riesgo creciente permite validar cada uno en producción antes de añadir la siguiente capa de complejidad.

---

## 7. Definition of Done

- [ ] **Date validator unit tests:** los 10 casos de `tests/test_date_validator.py` pasan sin errores.
- [ ] **State machine unit tests:** todas las transiciones definidas en `tests/test_conversation_state.py` pasan (incluyendo casos de Redis caído).
- [ ] **Input-side guard unit tests:** los 10 casos de intent detection pasan.
- [ ] **Output-side guard unit tests:** los 5 casos de retry logic pasan.
- [ ] **Phone normalization unit tests:** los 5 casos edge pasan.
- [ ] **Smoke manual — Bug #1:** reproducir la conversación de Juan Román Riquelme → cero ocurrencias de "Sábado 05/12" en los mensajes enviados al paciente.
- [ ] **Smoke manual — Bug #4:** reproducir "Agéndame el del 12 de mayo" después de recibir opciones → TORA llega a `book_appointment` en el mismo turno, sin re-llamar `check_availability`.
- [ ] **Smoke manual — Bug #5:** después del smoke de Bug #4, enviar "¿Cuándo es mi turno?" → `list_my_appointments` retorna el turno recién creado.
- [ ] **No regresiones:** `pytest tests/` completo pasa sin errores nuevos.
- [ ] **Redis fallback verificado:** con Redis deshabilitado localmente, el flujo completo de reserva funciona (con comportamiento pre-C2, sin state machine activo).

---

## 8. Out of scope

Los siguientes temas están explícitamente excluidos de C2 y se tratarán en sus respectivos changes:

- **Quick wins de TORA (C1):** mejoras aisladas de prompt, logs de debug adicionales, ajustes de texto de respuesta — ver `openspec/changes/tora-solo-quick-wins/`.
- **Engine router y UI selector (C3):** arquitectura dual TORA/Nova, routing por canal (WhatsApp vs web), selector de motor en el panel de configuración — ver `openspec/changes/dual-engine-router/`.
- **Refactor completo del system prompt:** la reestructura total de las instrucciones de flujo en `main.py:6713-6840` queda para C3 o un change dedicado. C2 solo añade el bloque de hardening de fechas y el slot de inyección de STATE_HINT.
- **Eliminación del soft-lock Redis existente (`slot_lock:`):** el soft-lock de 120s en `main.py:4555-4568` coexiste con el nuevo state machine de C2. La key `slot_lock:{tenant_id}:{slot_hash}` no se toca. La key nueva es `convstate:{tenant_id}:{phone}`. No hay colisión.
- **Migraciones Alembic:** C2 no introduce cambios en el esquema de PostgreSQL. Toda la persistencia nueva es Redis con TTL.
- **Nova voice assistant:** fuera de scope en todos los changes de la serie TORA-solo.
- **Frontend / BFF:** C2 es 100% backend. No hay cambios en `frontend_react/` ni en `bff_service/`.
