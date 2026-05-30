# Design: langchain-migration (0.1.0 → 1.x)

## Architecture impact

NINGUNO. El agent pipeline (TORA solo + multi-agent) mantiene la misma estructura: `ChatOpenAI` → `create_openai_tools_agent` → `AgentExecutor` con `DENTAL_TOOLS`. Solo cambian import paths y versiones de dependencias.

## Technical approach

### Phase 1: requirements.txt (foundation)

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

- `langchain-core` no estaba pinned explícitamente (era transitive). Ahora lo pineamos.
- `langchain-classic` es nuevo — bridge package oficial que provee `AgentExecutor` + `create_openai_tools_agent` removidos en 1.0.
- Verificar si `numpy` se usa directamente — langchain 0.1.0 lo trae como transitive, 1.x no.

### Phase 2: Import fixes (4 cambios quirúrgicos)

#### 2a. AgentExecutor + create_openai_tools_agent

**main.py:48-59** — reemplazar try/except chain:
```python
# Antes (chain de 3 fallbacks):
try:
    from langchain.agents import AgentExecutor, create_openai_tools_agent
except ImportError:
    try:
        from langchain_community.agent_toolkits.base import create_agent_executor as AgentExecutor
    except:
        AgentExecutor = None
        create_openai_tools_agent = None

# Después (1 línea):
from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
```

**agents/specialists.py:16** — mismo cambio, import directo.

Sin try/except — si `langchain-classic` no está instalado, fail fast al arrancar es correcto.

#### 2b. Messages (lead_recovery.py:150)
```python
# from langchain.schema import SystemMessage, HumanMessage  # ROTO en 1.x
from langchain_core.messages import SystemMessage, HumanMessage
```

#### 2c. Callback (buffer_task.py:1867-1875)
```python
# Eliminar fallback roto, dejar solo path canónico:
from langchain_community.callbacks import get_openai_callback
```

### Phase 3: ChatOpenAI param hygiene (opcional, recomendado)

Renombrar en 4 archivos × 5 instanciaciones:
- `openai_api_key=` → `api_key=`
- `openai_api_base=` → `base_url=`

No es breaking (aliases Pydantic), pero elimina deprecation warnings y alinea con SDK `openai` nativo.

### Phase 4: Verificación

1. `pip install -r requirements.txt` en venv existente
2. Import smoke: `from langchain_classic.agents import AgentExecutor; print('OK')`
3. Tool smoke: `from orchestrator_service.main import DENTAL_TOOLS; print(len(DENTAL_TOOLS))`
4. `pytest tests/ -q --tb=no` → 571+ passed, 0 failed
5. Grep negativo: confirmar 0 imports legacy

## Alembic migration impact
**Ninguna.** No se toca el schema.

## Backwards compatibility
- `@tool` decorator: idéntico en 0.1 y 1.x — las 21 tools no cambian
- `AgentExecutor` de `langchain-classic`: MISMO código que langchain 0.3.x
- `ChatOpenAI` params: aliases siguen funcionando incluso si no renombramos
- Servicios OpenAI directos: CERO impacto (no usan LangChain)
