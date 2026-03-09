---
description: Revisión técnica multi-perspectiva. Evalúa Seguridad, Performance y Clean Code.
---

# 👁️ Antigravity Review

Simula una revisión de código (PR Review) por ingenieros senior especializados.

1.  **Activación de Mini-Agentes**:
    - **Reviewer A (Arquitectura/Loki)**: Busca violaciones a la arquitectura de la Skill original.
    - **Reviewer B (Seguridad)**: Busca credenciales hardcoded, inyecciones o fugas de datos.
    - **Reviewer C (Clean Code)**: Evalúa legibilidad, nombrado y principios SOLID.
2.  **Consolidación**: Genera una lista de cambios recomendados (Minor) o bloqueantes (Critical).
3.  **Habilidad Maestra**: Usa `@agent-tool-builder` para sugerir refactorizaciones precisas que mejoren la deuda técnica.
