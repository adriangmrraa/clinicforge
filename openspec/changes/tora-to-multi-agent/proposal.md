# Proposal — Reemplazo de Tora por Sistema Multi-Agente con Memoria Compartida por Paciente

**Status:** Draft
**Owner:** Platform / AI
**Branch:** `claude/multi-agent-system-plan-k2UCI`
**Fecha:** 2026-04-07

---

## 1. Contexto

Hoy, el "cerebro" conversacional de ClinicForge es **Tora**: un único agente LangChain (`orchestrator_service/main.py`) con ~14 tools (`DENTAL_TOOLS`) que atiende WhatsApp/Instagram/Facebook/Web. Todo el razonamiento — triaje, disponibilidad, booking, cobros, anamnesis, derivación humana, upsell de implantes — vive en **un solo system prompt monolítico** y un solo loop de tool-calling.

### Problemas observados

1. **Prompt saturado**: el system prompt mezcla reglas comerciales, triaje clínico, lógica de sedes, protocolo de pagos, etiqueta WhatsApp. Cada mejora agrega líneas y degrada obediencia a reglas previas (regresiones silenciosas).
2. **Un solo contexto de memoria**: toda la conversación se carga en cada turno, sin separación entre "memoria clínica del paciente" vs "estado de la tarea actual" vs "políticas de la clínica".
3. **Tools en conflicto**: `check_availability`, `verify_payment_receipt`, `triage_urgency` y `derivhumano` compiten por atención del LLM; el agente a veces elige la tool incorrecta bajo presión.
4. **Sin especialización**: un mismo modelo `gpt-4o-mini` maneja tanto un triaje de urgencia dental (crítico) como un "¿cuánto sale la limpieza?" (trivial). No hay rutado por costo/criticidad.
5. **Difícil de evaluar**: no hay forma de testear "el agente de cobros" en aislamiento, porque no existe como unidad.
6. **Memoria por paciente ausente como primitivo**: hoy se reconstruye desde `patients`, `medical_history`, `chat_messages`, `patient_memories` en cada turno vía `buffer_task.py`. No hay una capa canónica compartida entre agentes.

### Oportunidad

Migrar a una arquitectura **multi-agente con orquestador + memoria compartida por paciente**, inspirada en los patrones *supervisor* de LangGraph y *handoff* de OpenAI Agents SDK, manteniendo 100% de compatibilidad con los canales actuales (WhatsApp, BFF, Nova voice).

---

## 2. Propuesta

### 2.1 Arquitectura objetivo

```
                         ┌───────────────────────────┐
                         │   Channel Adapter Layer   │
                         │ (WhatsApp / Web / Nova)   │
                         └─────────────┬─────────────┘
                                       │ PatientTurn
                                       ▼
                        ┌──────────────────────────────┐
                        │      Supervisor Agent        │
                        │  (router + policy + guard)   │
                        └──┬────────┬────────┬─────────┘
                           │        │        │
              ┌────────────┘        │        └──────────────┐
              ▼                     ▼                       ▼
     ┌────────────────┐   ┌──────────────────┐   ┌────────────────────┐
     │ Reception Agent│   │  Booking Agent   │   │  Triage Agent      │
     │ (saludo, FAQ,  │   │ (disponibilidad, │   │ (urgencia clínica, │
     │  precios)      │   │  reserva, sede)  │   │  derivación)       │
     └────────┬───────┘   └────────┬─────────┘   └─────────┬──────────┘
              │                    │                       │
              ▼                    ▼                       ▼
     ┌────────────────┐   ┌──────────────────┐   ┌────────────────────┐
     │ Billing Agent  │   │ Anamnesis Agent  │   │  Handoff Agent     │
     │ (seña, recibo, │   │ (historia médica,│   │ (derivhumano,      │
     │  verificación) │   │  link público)   │   │  email staff)      │
     └────────┬───────┘   └────────┬─────────┘   └─────────┬──────────┘
              │                    │                       │
              └────────────┬───────┴───────────────────────┘
                           ▼
              ┌────────────────────────────┐
              │  Patient Shared Memory     │
              │  (PatientContext store)    │
              │  pgvector + Redis + PG     │
              └────────────────────────────┘
```

### 2.2 Componentes

| Componente | Rol | Modelo sugerido |
|------------|-----|-----------------|
| **Supervisor** | Lee el turno, decide qué agente activar (routing), aplica guardrails (human override 24h, tenant policies), decide cuándo cerrar turno | `gpt-4o-mini` |
| **Reception Agent** | Saludo diferenciado, FAQs (vía RAG pgvector), precios de consulta, navegación general | `gpt-4o-mini` |
| **Booking Agent** | `check_availability`, `confirm_slot`, `book_appointment`, `reschedule`, `cancel`, sede resolution | `gpt-4o-mini` |
| **Triage Agent** | `triage_urgency`, detección implante/prótesis, positioning comercial, escalado a humano por dolor severo | `gpt-4o` (crítico) |
| **Billing Agent** | `verify_payment_receipt`, cobro de seña, estados `payment_status`, manejo de partial | `gpt-4o-mini` |
| **Anamnesis Agent** | `save_patient_anamnesis`, `get_patient_anamnesis`, link público, nombre-protección para menores/terceros | `gpt-4o-mini` |
| **Handoff Agent** | `derivhumano`, ventana 24h de silencio, email multi-canal al staff | `gpt-4o-mini` |

### 2.3 Memoria compartida por paciente

Una única abstracción `PatientContext` accesible por todos los agentes, con 4 capas:

1. **Profile** (persistente, PG): `patients` + `medical_history` + `anamnesis_token` + `guardian_phone` + minors vinculados.
2. **Episodic** (persistente, PG): últimos N turnos de `chat_messages` + `patient_memories` + notas clínicas.
3. **Semantic** (pgvector): FAQs + documentos clínicos del tenant (ya existe vía `embedding_service`).
4. **Working** (Redis, TTL 30 min): estado del turno actual — qué agente tiene el control, slots soft-locked, recibo en verificación, borrador de anamnesis.

Contrato único: `PatientContext.load(tenant_id, phone) -> PatientContext` y `PatientContext.save_delta(delta)`. Los agentes **no** tocan PostgreSQL directamente; pasan por este servicio. Esto habilita auditoría, multi-tenant safety, y tests aislados.

### 2.4 Orquestación

Se evalúan dos caminos:

- **Opción A — LangGraph Supervisor (recomendada)**: grafo con nodo `supervisor` + N nodos agente + edge condicional. Estado compartido = `PatientContext`. Nativo checkpointing (Redis/PG) para reanudar turnos. Alineado con el stack LangChain actual.
- **Opción B — OpenAI Agents SDK con handoffs**: más simple pero requiere reescribir tools y perder integración LangChain/pgvector FAQ.

**Decisión propuesta:** Opción A. Ver `spec.md` §4 para el trade-off detallado.

### 2.5 Compatibilidad

- **Canales**: el `Channel Adapter Layer` expone exactamente la misma interfaz que hoy consume `buffer_task.py`. WhatsApp service no cambia.
- **Nova voice**: queda fuera del alcance de esta migración (Realtime API tiene su propio loop de tools). El Supervisor y Nova coexistirán hasta fase 3.
- **Tools existentes**: se reutilizan tal cual, pero se reparten entre agentes. Cero reescritura de `DENTAL_TOOLS` en la fase 1.
- **Feature flag**: `ENABLE_MULTI_AGENT=false` por default. Activable por `tenant_id`.

---

## 3. Beneficios esperados

| Métrica | Hoy (Tora) | Objetivo (multi-agente) |
|---------|------------|-------------------------|
| System prompt size | ~8k tokens | <2k por agente |
| Tool-call accuracy (eval set) | ~82% | >92% |
| Costo por turno promedio | baseline | -20% (routing a agentes baratos) |
| Latencia p50 | baseline | ≤ baseline (+1 hop supervisor compensado por prompts cortos) |
| Tests unitarios por agente | 0 | ≥ 10 por agente |
| Regresión al agregar feature | alta | baja (aislamiento) |

---

## 4. Riesgos

1. **Latencia del supervisor**: 1 hop extra. Mitigación: supervisor con prompt ultra-corto + tool-choice forzado.
2. **Loops entre agentes**: mitigación con `max_hops=5` por turno y guardrail en el supervisor.
3. **Memoria desincronizada**: mitigación con lock Redis optimista por `(tenant_id, phone)`.
4. **Costo de migración**: ~3 sprints. Mitigación con feature flag por tenant + canary.
5. **Regresión en tenants en producción**: mitigación con shadow mode (multi-agente corre en paralelo, no responde) durante 1 semana por tenant.

---

## 5. Scope

**In scope (Fase 1):**
- Supervisor + 6 agentes en WhatsApp/Web
- `PatientContext` service + migración Alembic
- Feature flag por tenant
- Eval harness con 50 conversaciones reales anotadas
- Shadow mode

**Out of scope (fases futuras):**
- Migración de Nova voice
- Agente de Marketing/ROI (ya existe como dashboard, no conversacional)
- Agentes proactivos (lead recovery, reminders) — seguirán como jobs

---

## 6. Entregables

1. `proposal.md` (este archivo)
2. `spec.md` — especificación técnica detallada
3. `tasks.md` — breakdown de tareas ejecutables
4. Prototipo en `orchestrator_service/agents/` (fase de implementación)
5. Migración Alembic `010_patient_context_store.py`
6. Eval harness en `tests/agents/`

---

## 7. Referencias

- LangGraph Multi-Agent Supervisor pattern — https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/
- OpenAI Agents SDK handoffs — https://openai.github.io/openai-agents-python/handoffs/
- Estado actual de Tora: `orchestrator_service/main.py` (`DENTAL_TOOLS`, system prompt ~línea 2000+)
- RAG system: `orchestrator_service/services/embedding_service.py`
- Buffer/turn assembly: `orchestrator_service/services/buffer_task.py`
