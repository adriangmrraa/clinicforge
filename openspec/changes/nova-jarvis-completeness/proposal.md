# Proposal: Nova Jarvis Completeness

## Intent

Completar la transformación de Nova en un asistente Jarvis real: proactivo, consciente del contexto, optimizado en velocidad y con tracking completo de costos. 6 features que cierran las brechas entre "chatbot reactivo" y "sistema nervioso central de la clínica".

## Scope

### In Scope
1. **Resumen matutino + alertas programadas** — job diario 7:30 AM → resumen del día → Telegram
2. **Memoria de pacientes proactiva** — 2 tools dedicadas + hook en Telegram para auto-extracción
3. **Alertas inteligentes** — morosidad (>30 días), no-shows recurrentes, turnos sin confirmar → Telegram proactivo
4. **Contexto de página en Realtime** — pasar appointment_id + context_summary desde frontend
5. **Optimización de velocidad** — OpenAI client singleton, tool filtering por página, prompt cache
6. **Token tracking completo** — Telegram Nova, Whisper, Vision, fichas digitales

### Out of Scope
- Nova que envíe WhatsApp proactivamente a pacientes (ya existe via tools)
- Dashboard de actividad de Nova (futuro)
- Reducción del número de tools (requiere análisis de uso)

## Approach

**Pieza central**: `send_proactive_message(tenant_id, html_text)` en `telegram_notifier.py` — desbloquea features 1 y 3.

**Patient Memory**: ya está 90% hecho (`patient_memory.py`). Solo agregar tools y hook.

**Token tracking**: mecánico — capturar `response.usage` después de cada LLM call.

**Speed**: OpenAI client singleton + `nova_tools_for_page(page)` filter.

## Risks

| Risk | Mitigation |
|------|------------|
| Mensajes proactivos molestos a las 7:30 AM | Configurable por tenant (hora + on/off) |
| Token tracking agrega latencia | Fire-and-forget con `asyncio.create_task` |
| Tool filtering rompe algo | Fallback a tools completas si page=unknown |

## Rollback Plan
Cada feature es independiente. Revert commit individual sin afectar las demás.

## Success Criteria
- [ ] A las 7:30 AM la doctora recibe resumen del día en Telegram
- [ ] Nova guarda memorias de pacientes desde Telegram automáticamente
- [ ] Alertas de morosidad/no-shows llegan sin que nadie las pida
- [ ] Token usage de Telegram aparece en métricas del dashboard
- [ ] Tiempo de respuesta de Nova en Telegram <5s para consultas simples
