# Design: Post-Booking Context Loss — DLD-88 / DLD-89 / DLD-92

## ADR-1: Defensa en 3 capas (Prompt + Código + State)

| Capa | Qué hace | Riesgo mitigado |
|------|----------|-----------------|
| Prompt (R1-R4) | Instruye al LLM para no reiniciar booking post-confirmación | LLM ignora las reglas |
| Código guards (R5-R6) | `check_availability` y `book_appointment` validan estado antes de ejecutar | Guard no cubre todos los paths |
| State Machine (R7) | TTL de BOOKED/PAYMENT_PENDING extendido a 24h | State expira durante conversación |

Las 3 capas son necesarias porque cada una cubre un vector de falla distinto.

## ADR-2: Guard en `check_availability` — temprano y liviano

El guard se coloca AL INICIO de `check_availability`, justo después del log de estado actual (línea 1696). Si el estado es BOOKED/PAYMENT_PENDING, verifica si el mensaje del paciente tiene señal de nuevo turno. Si no, retorna mensaje de advertencia y corta.

**No toca la lógica de búsqueda de slots existente** — es un early return antes de cualquier query pesada.

## ADR-3: No tocar `reschedule_appointment`

`reschedule_appointment` ya tiene su propio flujo y no necesita cambios de código. La mejora en el prompt (PASO 3b prioridad mismo día) es suficiente.

## ADR-4: TTL diferenciado en `conversation_state.py`

TLT se calcula según el estado: BOOKED/PAYMENT_PENDING usan el nuevo `BOOKED_TTL = 86400` (24h). El resto mantiene `CONVSTATE_TTL = 1800` (30min). Esto evita que el state expire durante conversaciones largas post-booking.

## Diagrama de Flujo

```
Mensaje del paciente
       │
       ▼
┌─────────────────────────────────┐
│  check_availability             │
│                                 │
│  1. Obtener estado conversación │
│  2. ¿BOOKED o PAYMENT_PENDING?  │
│  ├─ NO → flujo normal           │
│  └─ SI →                        │
│      ├─ ¿Señal nuevo turno?     │
│      │  ├─ SI → flujo normal    │
│      │  └─ NO → return          │
│      │      BOOKING_ALREADY_    │
│      │      EXISTS              │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  book_appointment               │
│                                 │
│  1. Obtener estado conversación │
│  2. ¿last_booked_appointment_id?│
│  ├─ NO → flujo normal           │
│  └─ SI → return                 │
│      DUPLICATE_BOOKING          │
└─────────────────────────────────┘
```

## Cambios Específicos

### 1. `check_availability` — Guard temprano (main.py, línea 1695)

REEMPLAZAR el warning log actual:

```python
# ANTES (líneas 1695-1696):
if _ca_state_str in ("OFFERED_SLOTS", "SLOT_LOCKED", "BOOKED", "PAYMENT_PENDING"):
    logger.warning(f"📊 BOOKING_FLOW | ⚠️ check_availability called in state={_ca_state_str} — possible loop! phone={_ca_phone}")

# DESPUÉS:
if _ca_state_str in ("BOOKED", "PAYMENT_PENDING"):
    # DLD-89/92: Verificar si hay intención explícita de nuevo turno
    _intent_signals = r'\b(otro turno|nuevo turno|otra fecha|otro día|quiero cambiar|reagend|reprogram|mover el turno|cancel|dame otro|agendame otro|necesito otro|sacá otro|quiero uno más|turno para)\b'
    if not re.search(_intent_signals, date_query + " " + (treatment_name or ""), re.IGNORECASE):
        logger.warning(f"📊 BOOKING_FLOW | 🚫 check_availability BLOCKED: state={_ca_state_str} — no new-booking intent detected. phone={_ca_phone}")
        return (
            "BOOKING_ALREADY_EXISTS: El paciente ya tiene un turno confirmado en esta conversación. "
            "No se debe ofrecer un nuevo turno a menos que el paciente lo solicite explícitamente "
            "(diciendo 'quiero otro turno', 'necesito reagendar', etc.). "
            "Respondé la consulta del paciente sin ofrecer turnos nuevos."
        )
    else:
        logger.info(f"📊 BOOKING_FLOW | check_availability ALLOWED despite state={_ca_state_str} — new-booking intent detected. phone={_ca_phone}")

if _ca_state_str in ("OFFERED_SLOTS", "SLOT_LOCKED"):
    logger.warning(f"📊 BOOKING_FLOW | ⚠️ check_availability called in state={_ca_state_str} — possible loop! phone={_ca_phone}")
```

### 2. `book_appointment` — Guard duplicado (main.py, ~línea 3060)

INSERTAR justo después del log de entrada (después del logger.info de BOOK START):

```python
# DLD-89/92: Verificar que no se esté duplicando un turno ya confirmado
try:
    from services.conversation_state import get_state as _ba_get_state
    _ba_state = await _ba_get_state(tenant_id, chat_phone)
    _ba_apt_id = _ba_state.get("last_booked_appointment_id") if isinstance(_ba_state, dict) else None
    if _ba_apt_id:
        logger.warning(
            f"📅 BOOK BLOCKED: existing_apt_id={_ba_apt_id} phone={chat_phone} "
            f"treatment={treatment_reason!r} date_time={date_time!r}"
        )
        return (
            f"DUPLICATE_BOOKING: El paciente ya tiene un turno confirmado (ID #{_ba_apt_id}) "
            f"en esta conversación. No se debe agendar otro turno a menos que el paciente "
            f"lo solicite explícitamente. Respondé la consulta del paciente."
        )
except Exception as _ba_err:
    logger.warning(f"📅 BOOK: duplicate check failed (non-blocking): {_ba_err}")
```

### 3. `conversation_state.py` — TTL extendido (línea 24)

AGREGAR constante y modificar `set_state`:

```python
# Línea 24: agregar
CONVSTATE_TTL = 1800      # 30 minutes (default)
BOOKED_TTL = 86400        # 24 hours (BOOKED / PAYMENT_PENDING)

# En set_state, línea 126: reemplazar
# ANTES:
await r.setex(key, CONVSTATE_TTL, json.dumps(state_data))
# DESPUÉS:
_ttl = BOOKED_TTL if state in ("BOOKED", "PAYMENT_PENDING") else CONVSTATE_TTL
await r.setex(key, _ttl, json.dumps(state_data))
```

### 4. Prompt — REGLA POST-BOOKING (main.py, insertar entre línea 10249 y 10251)

INSERTAR después de `REGLA ANTI-RE-BOOKING` y antes de `=== SECUENCIA POST-BOOKING ===`:

```
=== REGLA POST-BOOKING (INQUEBRANTABLE) ===
Cuando YA CONFIRMASTE un turno con book_appointment en esta conversación:

1. El paciente YA TIENE turno. NO ofrezcas turnos nuevos.
2. Si el paciente hace una pregunta GENERAL (obra social, tratamiento, dirección, seña, etc.):
   → Respondé la pregunta NORMALMENTE.
   → NO ofrezcas "te paso turnos disponibles", "te ayudo a coordinar", ni variantes.
   → NO llames check_availability, confirm_slot ni book_appointment.
3. Si el paciente describe su problema clínico:
   → "La Dra. Laura te va a evaluar en tu turno del [día] a las [hora]."
   → NO ofrezcas turno nuevo.
4. La ÚNICA excepción: paciente dice EXPLÍCITAMENTE "quiero OTRO turno",
   "necesito otro turno", "agendame otro", "quiero CAMBIAR", "reagendá",
   "reprogramá", o similar con intención CLARA de nuevo turno.
5. Si el paciente dice algo ambiguo como "sí", "dale", "ok":
   → NO interpretes como solicitud de nuevo turno.
```

### 5. Prompt — REGLA DE CONTINUIDAD variante post-booking (main.py, ~línea 10205)

AGREGAR al final de REGLA DE CONTINUIDAD:

```
   ⚠️ VARIANTE POST-BOOKING: Si el paciente YA TIENE turno confirmado en esta
   conversación y hace una pregunta lateral, NO retomés el tema del turno.
   El turno YA ESTÁ CONFIRMADO. Solo respondé la pregunta. No hay "opciones
   pendientes" porque ya eligió.
```

### 6. Prompt — PASO 3b prioridad mismo día (main.py, ~línea 10083-10088)

REEMPLAZAR el bloque con la versión que prioriza mismo día:

```
PASO 3b: PACIENTE CON TURNO EXISTENTE — Si el paciente YA TIENE un turno agendado
(aparece "PRÓXIMO TURNO" en su contexto) y pide OTRO turno:
  • Reconocé el turno existente: "Ya tenés turno el [día] a las [hora] para [tratamiento]."
  • REAGENDAMIENTO: Si el paciente pide REAGENDAR/CAMBIAR/MOVER el turno:
    → PRIMERO buscá disponibilidad en el MISMO DÍA del turno original.
    → Si hay opciones el mismo día → ofrecelas PRIMERO.
    → Si NO hay el mismo día → recién ahí ofrecé otros días cercanos.
  • El nuevo turno NO puede ser en el mismo horario. Ofrecé otras opciones disponibles.
  • Si pide el mismo día pero distinta hora → OK, agendá normalmente si hay disponibilidad.
  • Si pide el mismo día y misma hora → NO, ya está ocupado. Ofrecé otro día/hora.
  • El profesional se define por el tratamiento (PASO 3). No preguntes "¿querés con el mismo profesional?"
```

## Archivos Afectados

| Archivo | Cambio | Líneas |
|---------|--------|--------|
| `orchestrator_service/main.py` | Guard en `check_availability` | ~1695-1701 |
| `orchestrator_service/main.py` | Guard en `book_appointment` | ~3060 (después de BOOK START log) |
| `orchestrator_service/main.py` | REGLA POST-BOOKING (nueva) | entre línea 10249 y 10251 |
| `orchestrator_service/main.py` | REGLA DE CONTINUIDAD variante post-booking | ~10205 |
| `orchestrator_service/main.py` | PASO 3b prioridad mismo día | ~10083-10088 |
| `orchestrator_service/services/conversation_state.py` | BOOKED_TTL + lógica en set_state | línea 24 + línea 126 |

## Testing

| Escenario | Cómo probar |
|-----------|-------------|
| DLD-89: post-booking + pregunta OS | State se setea a BOOKED → check_availability bloquea |
| DLD-92: post-booking + describe procedimiento | State BOOKED + sin señal "otro turno" → check_availability bloquea |
| DLD-88: reagendar mismo día | LLM instruido a buscar mismo día primero |
| Nuevo turno legítimo: "quiero otro turno" | Señal en input → check_availability permite |
| State BOOKED no expira en 30 min | TTL 24h → sigue vivo después de 35 min |
