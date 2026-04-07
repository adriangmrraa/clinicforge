# Spec: OpenAI Parameter Compatibility Helper

## Module: `core/openai_compat.py`

### `is_modern_openai_model(model: str) -> bool`

**Input:** nombre de modelo (case-sensitive, sin espacios extra).
**Output:** `True` si el modelo pertenece a la familia moderna que requiere `max_completion_tokens`.

**Reglas de detección (prefijo):**
- `gpt-5*` → modern
- `o1*`, `o3*`, `o4*` → modern
- Cualquier otro → legacy

### `build_openai_chat_kwargs(model, max_tokens, temperature=None, **extra) -> dict`

**Input:**
- `model: str` — nombre del modelo
- `max_tokens: int` — límite deseado de tokens de salida
- `temperature: float | None` — temperatura deseada (opcional)
- `**extra` — kwargs adicionales que se mezclan tal cual

**Output:** dict listo para pasar a `client.chat.completions.create(**kwargs)` o como cuerpo JSON a `POST /v1/chat/completions`.

**Reglas:**
1. Siempre incluye `"model": model`.
2. Si el modelo es **modern**: usa `max_completion_tokens=max_tokens` y omite `temperature` salvo que sea exactamente `1` (o `None`).
3. Si el modelo es **legacy**: usa `max_tokens=max_tokens` e incluye `temperature` si fue provisto.
4. Los `**extra` se mezclan al final sin sobrescribir las claves anteriores.

### Comportamiento esperado

| Modelo | max_tokens | temperature | Resultado |
|--------|-----------|-------------|-----------|
| `gpt-4o-mini` | 500 | 0 | `{model, max_tokens:500, temperature:0}` |
| `gpt-5-mini` | 500 | 0 | `{model, max_completion_tokens:500}` (sin temperature) |
| `gpt-5-mini` | 500 | 1 | `{model, max_completion_tokens:500, temperature:1}` |
| `o3-mini` | 1000 | 0.3 | `{model, max_completion_tokens:1000}` |
| `gpt-4o` | 300 | None | `{model, max_tokens:300}` |

## Integración: `services/patient_memory.py`

Las dos llamadas (`extract_and_store_memories` y `compact_memories`) construyen su payload con `build_openai_chat_kwargs(...)` en vez de hardcodear `max_tokens`/`temperature`. El resto del payload (`messages`, `response_format`) se pasa como `**extra`.
