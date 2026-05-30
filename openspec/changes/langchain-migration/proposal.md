# Proposal: langchain-migration (0.1.0 → 1.x)

## Intent

Migrar ClinicForge de `langchain==0.1.0` / `langchain-openai==0.0.5` (enero 2024, sin soporte de seguridad desde mayo 2024) a la versión estable actual `langchain>=1.2.0` / `langchain-openai>=1.1.0` sin romper funcionalidad existente.

## Why

1. **Seguridad**: 27+ meses sin patches de seguridad
2. **Peso muerto**: langchain 0.1.0 trae `numpy` como transitive dep innecesariamente (eliminado en 1.x)
3. **Compatibilidad**: no soporta features nuevos de OpenAI (`max_completion_tokens` para o1/o3, `tool_choice: required`, streaming structured output)
4. **Prerequisito**: para futuras features LangGraph, multi-agent nativo, streaming de agents
5. **Debt técnica**: `main.py` ya tiene un try/except shim anticipando la remoción de `AgentExecutor` — completar lo que empezamos

## Scope

**IN:**
- Bump versiones en `requirements.txt` (5 packages)
- Fix 4 import paths rotos por la migración
- Simplificar try/except shim de `AgentExecutor`
- (Opcional) Renombrar params ChatOpenAI deprecados
- Verificar suite verde (571 tests)

**OUT:**
- Migración `AgentExecutor` → LangGraph (change separado — rewrite del agent pipeline)
- Endpoints OpenAI directos (voz, vision, whisper, embeddings, Realtime) — no usan LangChain
- Actualización de modelos OpenAI
- Deprecation warnings de Pydantic v2 en `odontogram_utils.py` y `treatment_plan.py`

## Approach: Option C — langchain-classic bridge

| Opción | Esfuerzo | Riesgo | Resultado |
|--------|----------|--------|-----------|
| A — Quedarse en 0.3.x | Medio | Bajo | Ya vieja (sept 2024), sin soporte |
| B — 1.x + rewrite con LangGraph | Alto | Medio | Futureproof pero scope grande |
| **C — 1.x + langchain-classic** | **Bajo** | **Bajo** | **Versión actual, sin rewrite** |

`langchain-classic` es un package oficial del equipo de LangChain que mantiene `AgentExecutor`, `create_openai_tools_agent`, y otras APIs legacy removidas en 1.0. Recibe bug fixes y es la ruta de migración recomendada oficialmente.

## Cambios concretos

### requirements.txt
```diff
- langchain==0.1.0
- langchain-openai==0.0.5
- langchain-community==0.0.13
+ langchain>=1.2.0,<2.0.0
+ langchain-openai>=1.1.0,<2.0.0
+ langchain-core>=1.2.0,<2.0.0
+ langchain-community>=0.4.0,<1.0.0
+ langchain-classic>=1.0.0,<2.0.0
```

### Import fixes (4 cambios)

| # | Archivo | Antes | Después |
|---|---------|-------|---------|
| 1 | `main.py:48-59` | `from langchain.agents import AgentExecutor, create_openai_tools_agent` (try/except chain) | `from langchain_classic.agents import AgentExecutor, create_openai_tools_agent` |
| 2 | `agents/specialists.py:16` | `from langchain.agents import AgentExecutor, create_openai_tools_agent` | `from langchain_classic.agents import AgentExecutor, create_openai_tools_agent` |
| 3 | `jobs/lead_recovery.py:150` | `from langchain.schema import SystemMessage, HumanMessage` | `from langchain_core.messages import SystemMessage, HumanMessage` |
| 4 | `services/buffer_task.py:1867-1875` | try community / except langchain.callbacks | `from langchain_community.callbacks import get_openai_callback` (sin fallback) |

### (Opcional) ChatOpenAI param hygiene (4 archivos)
`openai_api_key=` → `api_key=`, `openai_api_base=` → `base_url=`

## Risks

1. **Transitive dependency conflicts**: `pip install` puede fallar si otro dep pide una versión incompatible de `pydantic`, `httpx`, etc. Mitigación: instalar en venv limpio, resolver conflicts antes de commit.
2. **Pydantic v2 internal**: langchain 1.x usa Pydantic v2 internamente. Tools con `args_schema` Pydantic v1 → rompen. ClinicForge NO usa `args_schema` explícitos → riesgo cero.
3. **`langchain-classic` lifecycle**: es mantenido oficialmente pero no recibirá features nuevos — sólo bug fixes. Para features nuevos hay que migrar a LangGraph eventualmente.

## Test plan
1. `pip install -r requirements.txt` en venv limpio
2. `python -c "from langchain_classic.agents import AgentExecutor; print('OK')"`
3. `pytest tests/ -q --tb=no` → 571 passed, 0 failed
4. Smoke test manual: mensaje WhatsApp → TORA responde
5. Nova widget (Realtime) funciona (usa OpenAI directo, zero impacto esperado)
