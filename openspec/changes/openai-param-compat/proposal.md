# Proposal: OpenAI Parameter Compatibility Helper

## Intent

Eliminar fallos silenciosos en llamadas a la API de OpenAI cuando un tenant configura un modelo moderno (gpt-5, serie o*) en `system_config`. Estos modelos rechazan `max_tokens` (requieren `max_completion_tokens`) y solo aceptan `temperature=1`. Hoy el código asume el comportamiento legacy de gpt-4o, lo que rompe la "Memoria de pacientes" y otros servicios cuando el operador cambia el modelo desde la UI de Tokens & Métricas.

## Scope

### In Scope
1. **Helper compartido** `core/openai_compat.py` con dos funciones:
   - `is_modern_openai_model(model: str) -> bool`
   - `build_openai_chat_kwargs(model, max_tokens, temperature, **extra) -> dict` que devuelve el dict de parámetros correcto según el modelo.
2. **Aplicar el helper** en `services/patient_memory.py` (extracción + compactación).
3. **Documentar** el patrón para futuras integraciones en el spec.

### Out of Scope
- Refactorizar `nova_daily_analysis.py`, `digital_records_service.py` o `attachment_summary.py` (ya manejan el caso por su cuenta — se migrarán en un cambio posterior).
- Cambios en `vision_service.py` y `telegram_bot.py` (modelos hardcodeados a gpt-4o, no afectados).
- Cambios en la UI del dashboard de tokens.

## Approach

Helper puro sin dependencias de OpenAI SDK: detecta familias modernas por prefijo (`gpt-5`, `o1`, `o3`, `o4`) y mapea la clave del límite de tokens. Para modelos modernos también descarta `temperature` cuando es distinto a 1 (gpt-5 family rechaza valores custom).

`patient_memory.py` arma su `json={}` para httpx usando `build_openai_chat_kwargs` en lugar de hardcodear `max_tokens`/`temperature`.

## Affected Areas

| Área | Impacto | Descripción |
|------|---------|-------------|
| `core/openai_compat.py` | Nuevo | Helper de compatibilidad de parámetros |
| `services/patient_memory.py` | Modificado | Extracción y compactación usan el helper |
| `tests/test_openai_compat.py` | Nuevo | Tests unitarios del helper |

## Risks

| Riesgo | Probabilidad | Mitigación |
|--------|--------------|------------|
| Falso positivo en detección de modelo (ej: `gpt-5-legacy`) | Baja | Solo se usa el prefijo de familia oficial documentada por OpenAI |
| Romper comportamiento existente en gpt-4o-mini | Baja | Tests cubren ambas ramas; el helper solo cambia kwargs cuando el prefijo coincide |
