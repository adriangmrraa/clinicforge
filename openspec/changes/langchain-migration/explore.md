# Explore: langchain-migration (0.1.0 → 1.x)

## Descubrimiento clave: LangChain ya está en 1.2.x

El user pidió migrar a "0.3.x" pero LangChain ya pasó 0.3 (sept 2024) y está en **1.2.15** (abril 2026). La migración real es `0.1.0 → 1.x`. Existe un package bridge `langchain-classic` que mantiene las APIs legacy (`AgentExecutor`, `create_openai_tools_agent`) para migración gradual.

## Current state

```
langchain==0.1.0          (Jan 2024 — 27+ meses sin soporte)
langchain-openai==0.0.5   (30+ minor versions atrás)
langchain-community==0.0.13
openai>=1.0.0             (directo, separado)
```

## Latest stable versions (April 2026)

| Package | Version |
|---------|---------|
| `langchain` | 1.2.15 |
| `langchain-openai` | 1.1.12 |
| `langchain-core` | 1.2.27 |
| `langchain-community` | 0.4.1 |
| `langchain-classic` | 1.0.3 (bridge — AgentExecutor + create_openai_tools_agent) |

## Breaking change timeline

### 0.1 → 0.2 (May 2024)
- `langchain-community` decoupled — now needs explicit install
- `from langchain.schema import ...` → deprecated, warnings
- `AgentExecutor` officially deprecated (still works)
- Pydantic v1+v2 both accepted

### 0.2 → 0.3 (Sept 2024)
- Python 3.8 dropped (min 3.9)
- Pydantic v1 dropped internally
- `pydantic_v1` bridge removed
- `AgentExecutor` still importable but deprecated loud

### 0.3 → 1.0 (Oct 2025) ← THE BIG ONE
- Python 3.9 dropped (min **3.10**) — ClinicForge usa 3.12 ✅
- `AgentExecutor` **REMOVED** from `langchain` → `langchain-classic`
- `create_openai_tools_agent` **REMOVED** → `langchain-classic`
- `from langchain.schema import ...` → **REMOVED**
- `from langchain.callbacks import ...` → **REMOVED**
- `langchain_core.pydantic_v1` bridge → **REMOVED**

## LangChain usage map in ClinicForge (6 files, 5 APIs)

### 1. `ChatOpenAI` — 4 instanciaciones
| File | Params | Import path |
|------|--------|-------------|
| `main.py:8248` | `model, temperature, openai_api_key, openai_api_base` | `langchain_openai` ✅ |
| `agents/specialists.py:37` | `model, temperature, openai_api_key, openai_api_base` | `langchain_openai` ✅ |
| `core/openai_compat.py:109` | via factory `get_chat_model()` | `langchain_openai` ✅ |
| `jobs/lead_recovery.py:154` | hardcoded `gpt-4o-mini` | `langchain_openai` ✅ |

**Params**: `openai_api_key`/`openai_api_base` son Pydantic aliases que SIGUEN funcionando en 1.x. Renombrar a `api_key`/`base_url` es opcional (hygiene).

### 2. `AgentExecutor` + `create_openai_tools_agent` — 2 archivos
| File | Status |
|------|--------|
| `main.py:48-59` | Try/except shim (ya anticipa remoción) |
| `agents/specialists.py:16` | Import directo sin fallback ⚠️ |

**Acción**: `from langchain_classic.agents import AgentExecutor, create_openai_tools_agent`

### 3. `@tool` decorator — 21 tools en main.py
**Import**: `from langchain.tools import tool` → SAFE (re-exported en 1.x)

### 4. `ChatPromptTemplate`, `MessagesPlaceholder`
**Import**: `from langchain_core.prompts import ...` → SAFE

### 5. Messages (`SystemMessage`, `HumanMessage`, `AIMessage`)
| File | Import | Status |
|------|--------|--------|
| `main.py:64` | `langchain_core.messages` | ✅ |
| `agents/specialists.py:62` | `langchain_core.messages` | ✅ |
| `jobs/lead_recovery.py:150` | `langchain.schema` | ❌ ROTO en 1.x |

### 6. `get_openai_callback`
| File | Import | Status |
|------|--------|--------|
| `buffer_task.py:1867` | `langchain_community.callbacks` (try) | ✅ |
| `buffer_task.py:1872` | `langchain.callbacks` (fallback) | ❌ ROTO en 1.x |

## Direct OpenAI usage — ZERO impacto de migración LangChain

| Feature | File | Method | LangChain? |
|---------|------|--------|------------|
| Embeddings | `services/embedding_service.py` | `openai.AsyncOpenAI().embeddings.create()` | NO |
| Vision | `services/vision_service.py` | `AsyncOpenAI` directo | NO |
| Vision (clinical) | `services/digital_records_service.py` | `AsyncOpenAI` directo | NO |
| Whisper STT | `services/whisper_service.py` | `httpx.AsyncClient` POST directo | NO |
| Nova Realtime | `main.py:9627` | WebSocket `websockets.connect()` | NO |
| TTS | `routes/nova_routes.py` | `openai.AsyncOpenAI()` | NO |
| Telegram | `services/telegram_bot.py` | `openai.AsyncOpenAI()` | NO |
| Attachments | `services/attachment_summary.py` | `AsyncOpenAI` directo | NO |

**Conclusión**: voz, texto, imagen, vision, audio, Realtime — NINGUNO pasa por LangChain. La migración es 100% interna al agent pipeline TORA + multi-agent.

## OpenAI model deprecations relevantes
- `gpt-4o-realtime-preview-2024-10-01` → shutdown **May 7 2026** (1 mes). Actualizar a `gpt-realtime-1.5`.
- `text-embedding-3-small` → SAFE, activo
- `gpt-4o-mini` → SAFE, activo

## Bottom line: solo 4 cambios de código

| # | Cambio | Archivo | Riesgo |
|---|--------|---------|--------|
| 1 | Import AgentExecutor via langchain-classic | `main.py`, `specialists.py` | Bajo |
| 2 | Import Messages via langchain_core | `lead_recovery.py` | Cero |
| 3 | Eliminar fallback callback roto | `buffer_task.py` | Cero |
| 4 | Bump versions en requirements.txt | `requirements.txt` | Bajo-Medio (transitive deps) |
| 5 | (Opcional) Renombrar ChatOpenAI params | 4 archivos | Cero |
