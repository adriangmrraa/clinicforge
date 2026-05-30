# Spec: langchain-migration (0.1.0 → 1.x)

## REQ-LM-1: Version bump a 1.x
`requirements.txt` DEBE pinear:
```
langchain>=1.2.0,<2.0.0
langchain-openai>=1.1.0,<2.0.0
langchain-core>=1.2.0,<2.0.0
langchain-community>=0.4.0,<1.0.0
langchain-classic>=1.0.0,<2.0.0
```
**Acceptance**: `pip install -r requirements.txt` completa sin conflictos.

## REQ-LM-2: AgentExecutor via langchain-classic
Todo import de `AgentExecutor` y `create_openai_tools_agent` DEBE venir de `langchain_classic.agents`.
**Archivos**: `main.py`, `agents/specialists.py`.
**Acceptance**: `python -c "from langchain_classic.agents import AgentExecutor, create_openai_tools_agent; print('OK')"` pasa.

## REQ-LM-3: Imports canónicos de messages
Todo import de `SystemMessage`, `HumanMessage`, `AIMessage` DEBE venir de `langchain_core.messages`.
**Archivo**: `jobs/lead_recovery.py:150`.
**Acceptance**: `rg "from langchain.schema" orchestrator_service/` → 0 resultados.

## REQ-LM-4: Callback sin fallback roto
`get_openai_callback` DEBE importarse SOLO de `langchain_community.callbacks`.
**Archivo**: `services/buffer_task.py`.
**Acceptance**: `rg "from langchain.callbacks" orchestrator_service/` → 0 resultados.

## REQ-LM-5: Suite verde post-migración
`pytest tests/ -q --tb=no` DEBE reportar 0 failed.
**Acceptance**: 571+ passed, 0 failed.

## REQ-LM-6: Pydantic v2 compatibilidad
Ningún código usado por LangChain debe depender de Pydantic v1 API.
**Verificación**: `rg "pydantic_v1|from pydantic.v1" orchestrator_service/` → 0 resultados.
**Nota**: Las deprecation warnings de Pydantic v2 en `odontogram_utils.py` y `treatment_plan.py` son pre-existentes y out of scope.

## REQ-LM-7: ChatOpenAI params hygiene (recomendado)
Renombrar `openai_api_key` → `api_key`, `openai_api_base` → `base_url`.
**Archivos**: `main.py`, `agents/specialists.py`, `core/openai_compat.py`, `jobs/lead_recovery.py`.
**Acceptance**: `rg "openai_api_key|openai_api_base" orchestrator_service/` → 0 resultados.

## REQ-LM-8: Zero impacto en servicios OpenAI directos
Los archivos que usan SDK `openai` directo (embedding, vision, whisper, Realtime, TTS, telegram) NO DEBEN tener imports de `langchain*`.
**Acceptance**: `rg "from langchain" services/embedding_service.py services/vision_service.py services/whisper_service.py routes/nova_routes.py services/telegram_bot.py` → 0 resultados.

## REQ-LM-9: Try/except shim simplificado
El bloque try/except en `main.py:48-59` DEBE simplificarse a import directo de `langchain_classic`.
**Acceptance**: no hay try/except chain para `AgentExecutor` imports.

## REQ-LM-10: numpy como transitive dep
Si `numpy` es usado directamente en el proyecto, DEBE agregarse explícitamente a `requirements.txt`. Si no, verificar que la remoción de la transitive dep no rompe nada.
**Verificación**: `rg "import numpy" orchestrator_service/`.

## Non-goals
- NO migrar AgentExecutor → LangGraph
- NO cambiar modelos OpenAI
- NO tocar servicios con SDK openai directo
- NO resolver deprecation warnings de Pydantic v2 pre-existentes
