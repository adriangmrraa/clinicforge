# Tasks: OpenAI Parameter Compatibility Helper

- [x] Crear `orchestrator_service/core/openai_compat.py` con `is_modern_openai_model` y `build_openai_chat_kwargs`.
- [x] Crear `tests/test_openai_compat.py` cubriendo gpt-4o-mini, gpt-5-mini (temp 0 y temp 1), o3-mini, modelo sin temperature.
- [x] Refactor `services/patient_memory.py::extract_and_store_memories` para usar el helper.
- [x] Refactor `services/patient_memory.py::compact_memories` para usar el helper.
- [ ] (Follow-up) Migrar `nova_daily_analysis.py`, `digital_records_service.py`, `attachment_summary.py` al helper.
