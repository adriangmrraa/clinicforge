# Design: Booking Omission and Reschedule Fallback Fixes

## Technical Approach
This design addresses two bugs in the booking and rescheduling flows. We enforce immediate booking execution upon DNI entry (preventing clinical/migration distractions) and guarantee a clean fallback when trying to reschedule with no future appointments. To ensure parity between the Solo and Multi-Agent engines, we update the monolithic system prompt, the `BookingAgent` prompt, and the LangGraph `SupervisorAgent` routing logic.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Route only via LLM prompt updates. | High latency, potential routing failure if LLM prioritizes clinical pain over DNI. | Rejected. |
| Add a deterministic DNI priority rule in `SupervisorAgent` + update prompts. | Ensures 100% routing accuracy to `booking` for DNI entries, preventing triage diversion. | **Selected**. |

### Rationale
In Multi-Agent mode, the supervisor evaluates every turn. If a user provides a DNI alongside text like "me duele la muela", the supervisor's default regex/LLM logic would route to `triage` (which lacks the `book_appointment` tool). Adding a deterministic check in `SupervisorAgent` before the emergency patterns guarantees that confirmation inputs always route to `booking` first.

## Data Flow

### Booking Confirmation
```
[User Message: DNI + Clinical pain]
       │
       ▼
[SupervisorAgent] (DNI pattern matched -> route to "booking")
       │
       ▼
[BookingAgent / Monolithic Agent] (DNI confirmation rule active)
       │
       ▼
[book_appointment Tool Call] (Success -> Turn Confirmed)
```

### Rescheduling Fallback
```
[User Message: "Quiero reprogramar"]
       │
       ▼
[list_my_appointments Tool Call]
       │
       ├─► [Appointments Found] ──► check_availability ──► reschedule_appointment
       │
       └─► [No Upcoming Appointments]
                   │
                   ▼
         [Inform: "No encuentro ningún turno..."] ──► Offer new booking
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` | Modify | Update `build_system_prompt` to inject the DNI confirmation rule and reschedule fallback in the monolithic prompt. |
| `orchestrator_service/agents/specialists.py` | Modify | Update `BookingAgent` base prompt to inject the DNI confirmation rule and reschedule fallback. |
| `orchestrator_service/agents/supervisor.py` | Modify | Add a deterministic rule in `route()` to route DNI or DNI-keyword messages directly to `booking` before emergency checks. |
| `orchestrator_service/agents/prompts/supervisor.md` | Modify | Update LLM routing rules to prioritize booking when DNI/confirmation is provided. |

## Interfaces / Contracts

### 1. `SupervisorAgent` Deterministic Route Change (`supervisor.py`)
In the `route` method, before the `EMERGENCY_PATTERNS` loop, evaluate:
```python
# Rule 3: DNI / Confirmation flow priority
if re.search(r"\b\d{7,11}\b", msg) or any(x in msg for x in ["dni", "mi dni", "nro de documento", "mi documento", "nro documento"]):
    return "booking"
```

### 2. DNI Confirmation Prompt Injection
This block is added in `main.py` and `specialists.py` (`BookingAgent` prompt):
```text
⚠️ REGLA DE CONFIRMACIÓN CON DNI (CRÍTICA E INQUEBRANTABLE):
- Cuando el paciente proporcione su DNI para confirmar el slot pre-reservado (ej: tras `confirm_slot` o durante el proceso de reserva), debés llamar a `book_appointment` de inmediato en ese mismo turno.
- Ignorá cualquier descripción clínica o comentario sobre dolor/molestia que acompañe al DNI en ese mensaje (no des contención clínica ni desvíes el flujo hasta confirmar).
- Queda PROHIBIDO disparar la regla de "DETECCIÓN DE PACIENTE EXISTENTE SIN DATOS EN SISTEMA (MIGRACIÓN)" o derivar a humano (`derivhumano`) en este punto. El ingreso del DNI es parte del flujo normal de agendamiento y debe culminar con la ejecución de `book_appointment`.
```

### 3. Rescheduling Fallback Prompt Injection
Update the rescheduling rules to handle empty lists:
```text
⚠️ FALLBACK SI NO TIENE TURNOS FUTUROS ACTIVOS:
- Si `list_my_appointments` devuelve que no existen turnos futuros (lista vacía), decile al paciente de forma amable: "No encuentro ningún turno agendado a tu nombre en el sistema."
- Preguntale si desea coordinar un nuevo turno desde cero (si acepta, iniciá check_availability).
- Queda PROHIBIDO inventar o alucinar datos de turnos anteriores, llamar a `reschedule_appointment` con datos ficticios, o agendar/reprogramar de forma unilateral sin consentimiento expreso.
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Prompt formatting and parser stability. | Run standard prompt tests to verify no syntax breakages. |
| Integration (Solo) | Scenario 1: DNI + Clinical text -> calls `book_appointment`. | Execute mock conversation turn with monolithic engine. |
| Integration (Multi) | Scenario 1: DNI + Clinical text -> routes to booking -> calls `book_appointment`. | Execute mock turn with multi-agent engine. |
| Integration | Scenario 2: Reschedule empty -> calls `list_my_appointments` -> reports no turn -> offers new booking. | Execute rescheduling mock turn with no future appointments in DB. |

## Migration / Rollout
No database migrations or configuration schema changes are required. The changes can be rolled out directly with the next application restart.
