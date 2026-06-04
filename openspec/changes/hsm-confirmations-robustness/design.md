# Design: Robustez en Confirmaciones HSM (hsm-confirmations-robustness)

## Technical Approach
This design addresses robustness in appointment confirmations through two complementary paths:
1. **Quick-Reply webhook-level intercept**: Expand synonym detection in `chat_webhooks.py` to bypass LLM invocation entirely when a patient replies with common confirmation keywords.
2. **LLM-Agent confirmation tool**: Introduce a new LangChain tool `confirm_appointment` in `main.py` to allow the AI BookingAgent to confirm appointments using natural language, resolve date/time discrepancies, and perform real-time UI/notification updates.

## Architecture Decisions

### Decision: In-Memory Time Proximity and Discrepancy Matching

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Resolve discrepancy and proximity inside PostgreSQL query using interval logic | Complex SQL syntax, harder timezone conversion, less readable, hard to generate customized warning details | Rejected |
| Retrieve future scheduled/pending appointments, then resolve time proximity and discrepancy warnings in Python | Highly readable, easy timezone localization via `get_active_tz()`, simple testability, precise discrepancy calculation | **Chosen** |

**Rationale**: Postgres timestamps are stored in UTC. Converting them dynamically to the tenant's localized timezone inside SQL for string-based proximity comparisons is error-prone. Retrieving future appointments for the patient and parsing/localizing in Python allows clean, simple, and robust timezone conversions and matching.

### Decision: Direct DB Pool Usage in Tool

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Use SQLAlchemy ORM inside the LangChain tool | Circular dependency risks, asynchronous ORM session overhead, inconsistent with other tools | Rejected |
| Use direct asyncpg prepared statements on `db.pool` | Consistent with standard codebase tool patterns, extremely fast, explicit SQL isolation | **Chosen** |

**Rationale**: The codebase uses direct SQL queries via `db.pool` for high-throughput concurrency and simplicity in agent tools. We preserve this pattern to avoid architectural regression.

## Data Flow

When a webhook is received:
```
[WhatsApp / YCloud Webhook] 
       │
       ▼
[chat_webhooks.py] ──(Matches _CONFIRM_BUTTONS?)──► Yes ──► [Update DB to 'confirmed']
       │                                                              │
       No                                                      [Emit SIO Room & Telegram]
       │                                                              │
       ▼                                                              ▼
[LLM Booking Agent] ────► [calls confirm_appointment()] ──► [Response Sent to Patient]
```

When `confirm_appointment` tool is called by LLM:
```
[confirm_appointment]
       │
       ├──► 1. Identify Patient & active tenant_id (context-memory)
       ├──► 2. Query future pending/scheduled appointments
       ├──► 3. Filter by target_date (if provided)
       ├──► 4. Match closest appointment based on approximate_time (if provided)
       ├──► 5. Check time discrepancy -> set WARNING if different
       ├──► 6. Update appointment state to 'confirmed'
       ├──► 7. Emit Socket.IO APPOINTMENT_UPDATED
       ├──► 8. Fire Telegram notification
       └──► 9. Return SUCCESS or ERROR text to agent
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/routes/chat_webhooks.py` | Modify | Expand `_CONFIRM_BUTTONS` list to support new confirmation synonyms and emojis. Ensure input is stripped and normalized to lowercase. |
| `orchestrator_service/main.py` | Modify | Implement `@tool async def confirm_appointment`. Register it in `DENTAL_TOOLS`. |
| `orchestrator_service/agents/specialists.py` | Modify | Import `confirm_appointment` from `main.py` and register it in `BookingAgent._get_tools()`. Update system prompt to guide LLM in invoking this tool and handling discrepancy warnings. |

## Interfaces / Contracts

### `confirm_appointment` signature (Python / LangChain)
```python
@tool
async def confirm_appointment(
    appointment_id: str = None,
    approximate_time: str = None,
    target_date: str = None
) -> str:
    """
    Confirma un turno programado o pendiente del paciente.
    appointment_id: (Opcional) UUID del turno si se conoce de antemano.
    approximate_time: (Opcional) Hora aproximada mencionada por el paciente (ej: '15:00', 'a las 3', 'tarde').
    target_date: (Opcional) Fecha mencionada por el paciente (ej: 'mañana', '2026-06-05', 'lunes').
    """
```

### Response Formats
- **Success without discrepancy**:
  `SUCCESS: Turno del 2026-06-05 a las 15:15 hs confirmado. Profesional: Dra. Laura Delgado. Tratamiento: Consulta.`
- **Success with time discrepancy warning**:
  `SUCCESS: Turno del 2026-06-05 a las 15:15 hs confirmado. Profesional: Dra. Laura Delgado. WARNING: El paciente mencionó las 15:00 hs, pero el turno está agendado a las 15:15 hs. Es obligatorio aclararle al paciente que el horario exacto es 15:15 hs.`
- **Error (no appointments found)**:
  `ERROR: No se encontró ningún turno programado o pendiente en el futuro para este paciente.`

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit / Integration | Quick Reply Synonym Matching | Mock incoming webhook payload with synonyms (`voy`, `asisto`, `conservo ✅`) and verify database updates, Socket.IO emits, and response payload. |
| Unit / Integration | `confirm_appointment` Logic | Verify time proximity selection with multiple future appointments, target_date filtering, discrepancy warnings generation, and validation of tenant isolation. |
| E2E | Natural Language Confirmation Flow | Verify LLM response when a user sends "Si confirmo para el lunes a las 3" and the appointment is at 15:15. Ensure agent output warns the user about the exact time (15:15). |

## Migration / Rollout
No database schema migrations are required. The changes are code-only and backward-compatible.
