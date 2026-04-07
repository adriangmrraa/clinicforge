# Spec — Multi-Agent System con Memoria Compartida por Paciente

**Change ID:** `tora-to-multi-agent`
**Companion:** `proposal.md`, `tasks.md`
**Fecha:** 2026-04-07

---

## 1. Objetivos técnicos

- **O1**: Reemplazar el agente monolítico Tora por un sistema de 1 supervisor + 6 agentes especializados sin romper canales actuales.
- **O2**: Introducir `PatientContext` como memoria compartida canónica entre agentes, con aislamiento multi-tenant enforced por código.
- **O3**: Habilitar routing por `tenant_id` vía feature flag `ENABLE_MULTI_AGENT`.
- **O4**: Alcanzar ≥92% de tool-call accuracy en el eval set con paridad o mejor latencia.

---

## 2. Módulos nuevos

### 2.1 `orchestrator_service/agents/`

```
agents/
├── __init__.py
├── base.py                 # BaseAgent abstract class
├── supervisor.py           # SupervisorAgent (router)
├── reception.py            # ReceptionAgent
├── booking.py              # BookingAgent
├── triage.py               # TriageAgent
├── billing.py              # BillingAgent
├── anamnesis.py            # AnamnesisAgent
├── handoff.py              # HandoffAgent
├── graph.py                # LangGraph StateGraph wiring
├── state.py                # AgentState TypedDict
└── prompts/
    ├── supervisor.md
    ├── reception.md
    ├── booking.md
    ├── triage.md
    ├── billing.md
    ├── anamnesis.md
    └── handoff.md
```

### 2.2 `orchestrator_service/services/patient_context.py`

Servicio único para cargar/actualizar la memoria compartida. No existe acceso directo a PG desde los agentes.

---

## 3. Modelos de datos

### 3.1 Tabla nueva: `patient_context_snapshots`

Usada para checkpointing de LangGraph por `(tenant_id, phone_number)`.

```sql
CREATE TABLE patient_context_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone_number    TEXT NOT NULL,
    thread_id       TEXT NOT NULL,           -- LangGraph checkpoint thread
    state           JSONB NOT NULL,          -- AgentState serializado
    active_agent    TEXT,                    -- supervisor | reception | booking | ...
    hop_count       INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, phone_number, thread_id)
);

CREATE INDEX idx_patient_ctx_tenant_phone
    ON patient_context_snapshots (tenant_id, phone_number);
```

### 3.2 Tabla nueva: `agent_turn_log`

Auditoría por turno (para debugging y eval).

```sql
CREATE TABLE agent_turn_log (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    phone_number    TEXT NOT NULL,
    turn_id         UUID NOT NULL,
    agent_name      TEXT NOT NULL,
    input_tokens    INT,
    output_tokens   INT,
    tools_called    JSONB,                   -- [{name, args, result_summary}]
    handoff_to      TEXT,                    -- siguiente agente si hubo handoff
    duration_ms     INT,
    model           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_turn_log_tenant_turn
    ON agent_turn_log (tenant_id, turn_id);
```

Migración: `orchestrator_service/alembic/versions/010_multi_agent_store.py`.

### 3.3 Campo en `tenants`

```sql
ALTER TABLE tenants
    ADD COLUMN multi_agent_enabled BOOLEAN DEFAULT FALSE,
    ADD COLUMN multi_agent_mode    TEXT    DEFAULT 'shadow';  -- shadow | live
```

---

## 4. Decisión de framework: LangGraph vs OpenAI Agents SDK

| Criterio | LangGraph | OpenAI Agents SDK |
|----------|-----------|-------------------|
| Compatibilidad con LangChain actual | ✅ nativo | ❌ reescribir tools |
| Checkpointing persistente | ✅ PG/Redis | ❌ manual |
| pgvector RAG integration | ✅ ya existe | ⚠️ indirecto |
| Curva de aprendizaje equipo | media | baja |
| Madurez multi-agent | alta | alta |
| Lock-in | LangChain | OpenAI |

**Elegido: LangGraph** (`langgraph>=0.2.0`). Añadir a `requirements.txt`.

---

## 5. `AgentState` (TypedDict)

```python
class AgentState(TypedDict):
    # Identidad
    tenant_id: str
    phone_number: str
    turn_id: str

    # Entrada
    user_message: str
    user_attachments: list[dict]  # imágenes, audios

    # Memoria del paciente (cargada por PatientContext.load)
    patient_profile: dict          # nombre, dni, email, guardian_phone...
    medical_history: dict
    recent_turns: list[dict]       # últimos N chat_messages
    patient_memories: list[str]    # patient_memories table
    linked_minors: list[dict]
    future_appointments: list[dict]
    is_new_lead: bool
    human_override_until: datetime | None

    # Semántica
    rag_faqs: list[dict]           # top-5 FAQs relevantes

    # Estado del grafo
    active_agent: str              # set por el supervisor
    hop_count: int
    max_hops: int                  # default 5
    handoff_reason: str | None

    # Salida
    agent_messages: list[AIMessage]
    tools_called: list[dict]
    reply_to_user: str | None      # texto final a enviar por el canal
    should_close_turn: bool
```

---

## 6. Contrato `PatientContext`

```python
class PatientContext:
    @classmethod
    async def load(
        cls, tenant_id: UUID, phone_number: str,
        include_rag_for: str | None = None,
    ) -> "PatientContext":
        """
        Carga profile + episodic + (opcionalmente) semantic desde
        patients, medical_history, chat_messages, patient_memories.
        MUST enforce tenant_id filter en todas las queries.
        """

    async def apply_delta(self, delta: ContextDelta) -> None:
        """
        Aplica cambios (nueva anamnesis, slot bloqueado, nota clínica)
        en una transacción atómica. Emite evento audit_log.
        """

    def to_agent_state(self, user_message: str) -> AgentState:
        """Serializa para LangGraph."""
```

**Invariantes:**
- Cada método valida `tenant_id` contra el JWT del turno (Sovereignty Protocol §1).
- Ningún agente usa `asyncpg.Connection` directamente; pasa por `PatientContext`.
- Lock optimista Redis `lock:patient_ctx:{tenant_id}:{phone}` con TTL 30s.

---

## 7. Supervisor — Routing rules

El Supervisor implementa routing determinístico-primero, LLM-segundo:

### Reglas determinísticas (pre-LLM)
1. Si `human_override_until > now()` → responder vacío (silencio 24h). **Fin de turno.**
2. Si `user_attachments` tiene imagen y `patient` tiene `payment_status='pending'` → `BillingAgent`.
3. Si `user_message` matchea regex de emergencia (sangrado, trauma, hinchazón severa) → `TriageAgent`.
4. Si `hop_count >= max_hops` → `HandoffAgent` con razón `max_hops_exceeded`.

### Routing por LLM (fallback)
Si no matcheó ninguna regla, el Supervisor LLM elige entre: `reception | booking | triage | billing | anamnesis | handoff | end`.

Prompt del supervisor (<500 tokens): ver `agents/prompts/supervisor.md`.

**Tool-choice forzado** a `route_to` (single function) para máxima predictibilidad.

---

## 8. Distribución de tools existentes

| Tool (actual `DENTAL_TOOLS`) | Agente dueño |
|------------------------------|--------------|
| `list_professionals` | Reception |
| `list_services` | Reception |
| `check_availability` | Booking |
| `confirm_slot` | Booking |
| `book_appointment` | Booking |
| `list_my_appointments` | Booking |
| `cancel_appointment` | Booking |
| `reschedule_appointment` | Booking |
| `triage_urgency` | Triage |
| `save_patient_anamnesis` | Anamnesis |
| `get_patient_anamnesis` | Anamnesis |
| `save_patient_email` | Reception (también Anamnesis) |
| `verify_payment_receipt` | Billing |
| `derivhumano` | Handoff |

Los agentes solo ven sus tools en el binding (`llm.bind_tools([...])`), no todas.

---

## 9. Feature flag y rollout

```python
# orchestrator_service/services/agent_router.py
async def process_turn(tenant_id, phone, message, attachments):
    tenant = await load_tenant(tenant_id)
    if tenant.multi_agent_enabled:
        if tenant.multi_agent_mode == "shadow":
            asyncio.create_task(run_multi_agent_shadow(...))
            return await run_tora_legacy(...)
        else:  # "live"
            return await run_multi_agent_graph(...)
    return await run_tora_legacy(...)
```

Modos:
- **off** (default): Tora legacy.
- **shadow**: Tora responde al paciente; multi-agente corre en paralelo, solo loggea en `agent_turn_log`. Sin efectos laterales (tools en modo dry-run).
- **live**: multi-agente responde y ejecuta tools. Tora desactivado para ese tenant.

Plan de rollout: `off → shadow (1 semana) → live (canary 1 tenant) → live (10%) → live (100%)`.

---

## 10. Guardrails

1. **Multi-tenant**: `PatientContext.load` enforcea `tenant_id`. Tests de fuzz incluidos.
2. **Max hops**: 5 agentes por turno; excedido → Handoff.
3. **Timeout por turno**: 45s wall clock; excedido → mensaje genérico + handoff.
4. **Token budget**: 8k tokens input por agente; excedido → truncar `recent_turns`.
5. **Tool sandbox**: en shadow mode, tools de escritura (`book_appointment`, `save_patient_anamnesis`, `verify_payment_receipt`, `derivhumano`) corren en modo dry-run.

---

## 11. Observabilidad

- Cada hop escribe en `agent_turn_log`.
- Métricas Prometheus: `agent_turn_duration_ms`, `agent_hops_per_turn`, `agent_handoffs_total{from,to}`, `agent_tool_calls_total{agent,tool}`.
- Dashboard nuevo en `views/MultiAgentView.tsx` (fase 2).

---

## 12. Testing

### 12.1 Unitarios (`tests/agents/`)
- `test_supervisor_routing.py` — 20 casos de routing determinístico + LLM.
- `test_patient_context.py` — load/save/tenant isolation/lock.
- `test_booking_agent.py`, `test_triage_agent.py`, etc. — ≥10 por agente.

### 12.2 Eval harness (`tests/agents/eval/`)
- 50 conversaciones WhatsApp reales anotadas.
- Métrica: tool-call accuracy, respuesta final similarity (LLM-as-judge).
- Corre en CI al mergear a `main`.

### 12.3 Fuzz multi-tenant
- Test que simula 2 tenants concurrentes y verifica que ningún dato cruza.

---

## 13. Variables de entorno nuevas

| Var | Descripción | Default |
|-----|-------------|---------|
| `MULTI_AGENT_ENABLED_GLOBAL` | Kill switch global | `false` |
| `MULTI_AGENT_MAX_HOPS` | Tope hops por turno | `5` |
| `MULTI_AGENT_TURN_TIMEOUT_S` | Timeout wall clock | `45` |
| `MULTI_AGENT_CHECKPOINT_BACKEND` | `redis` \| `postgres` | `postgres` |
| `MODEL_SUPERVISOR` | Modelo del supervisor | `gpt-4o-mini` |
| `MODEL_TRIAGE` | Modelo de triage | `gpt-4o` |

---

## 14. Criterios de aceptación

- [ ] `ENABLE_MULTI_AGENT=true` en un tenant sandbox responde correctamente los 50 casos del eval.
- [ ] Shadow mode corre 1 semana sin diferencia > 10% vs Tora en los casos eval.
- [ ] Tool-call accuracy ≥ 92% en eval set.
- [ ] Latencia p50 ≤ 1.1× Tora legacy.
- [ ] 0 fugas cross-tenant en fuzz.
- [ ] Cobertura tests ≥ 80% en `orchestrator_service/agents/`.
- [ ] Documentación actualizada en `CLAUDE.md`.

---

## 15. No-objetivos

- No se migra Nova voice (Realtime API) en esta fase.
- No se cambia el formato de `chat_messages`.
- No se elimina `main.py` del agente legacy — queda como fallback hasta fase 3.
- No se modifican canales (WhatsApp service sigue igual).
