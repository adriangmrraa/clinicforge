# Tasks: langchain-migration (0.1.0 → 1.x)

## Phase 1 — Dependencies

- [ ] 1.1 Verificar `rg "import numpy" orchestrator_service/` — si hay uso directo, agregar `numpy` a requirements.txt
- [ ] 1.2 Actualizar `requirements.txt`: bump langchain/langchain-openai/langchain-community + agregar langchain-core + langchain-classic
- [ ] 1.3 `pip install -r requirements.txt` en `.venv` existente — resolver conflicts si aparecen
- [ ] 1.4 Verificar `python -c "import langchain; print(langchain.__version__)"` → 1.2.x
- [ ] 1.5 Verificar `python -c "from langchain_classic.agents import AgentExecutor; print('OK')"`

**Commit**: `chore(deps): bump langchain 0.1.0 → 1.x + add langchain-classic bridge`

## Phase 2 — Import fixes

- [ ] 2.1 `orchestrator_service/main.py:48-59`: reemplazar try/except chain por `from langchain_classic.agents import AgentExecutor, create_openai_tools_agent`
- [ ] 2.2 `orchestrator_service/agents/specialists.py:16`: idem
- [ ] 2.3 `orchestrator_service/jobs/lead_recovery.py:150`: `from langchain.schema` → `from langchain_core.messages`
- [ ] 2.4 `orchestrator_service/services/buffer_task.py:1867-1875`: eliminar fallback `from langchain.callbacks`, dejar solo `from langchain_community.callbacks`
- [ ] 2.5 Verificar: `rg "from langchain\.(schema|callbacks|agents)" orchestrator_service/` → 0

**Commit**: `refactor(langchain): fix import paths for langchain 1.x compatibility`

## Phase 3 — ChatOpenAI param hygiene

- [ ] 3.1 `orchestrator_service/main.py`: `openai_api_key=` → `api_key=`, `openai_api_base=` → `base_url=`
- [ ] 3.2 `orchestrator_service/agents/specialists.py`: idem en `_build_llm_from_config()`
- [ ] 3.3 `orchestrator_service/core/openai_compat.py`: idem en `get_chat_model()`
- [ ] 3.4 `orchestrator_service/jobs/lead_recovery.py`: `openai_api_key=` → `api_key=`
- [ ] 3.5 Verificar: `rg "openai_api_key|openai_api_base" orchestrator_service/` → 0

**Commit**: `refactor(langchain): rename deprecated ChatOpenAI params (api_key, base_url)`

## Phase 4 — Verificación

- [ ] 4.1 `pytest tests/ -q --tb=no` → 571+ passed, 0 failed
- [ ] 4.2 Correr suite 2 veces más para descartar flakiness
- [ ] 4.3 Verificaciones negativas (5 greps):
  - `rg "from langchain\.schema" orchestrator_service/` → 0
  - `rg "from langchain\.callbacks" orchestrator_service/` → 0
  - `rg "from langchain\.agents" orchestrator_service/` → 0
  - `rg "openai_api_key|openai_api_base" orchestrator_service/` → 0
  - `rg "pydantic_v1|from pydantic\.v1" orchestrator_service/` → 0
- [ ] 4.4 Smoke test import: `python -c "from orchestrator_service.main import DENTAL_TOOLS; print(len(DENTAL_TOOLS), 'tools')"`
- [ ] 4.5 Save engram completion memory

## Notas

- NO crear venv nuevo — actualizar `.venv` existente con `pip install -r requirements.txt`
- Si `pip install` falla por conflicts, reportar exacto y proponer resolución antes de continuar
- Si algún test falla por la migración, investigar antes de "arreglar"
- Phase 3 es separable — si el user quiere dejarlo fuera, revertir solo ese commit
