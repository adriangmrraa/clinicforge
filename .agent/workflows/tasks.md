---
description: (Opcional) Descompone un plan masivo en tickets individuales si la complejidad es alta.
---

# 📋 Antigravity Tasks

Gestión de granularidad para proyectos grandes.

1.  **Input**: Plan de implementación (`docs/plans/...md`).
2.  **Análisis de Complejidad**:
    - Si el plan tiene > 15 pasos.
    - O si involucra múltiples agentes simultáneos.
3.  **Generación de Tickets**:
    - Crea un archivo JSON o Markdown checklist con estados: `[ ]`, `[IN_PROGRESS]`, `[DONE]`.
4.  **Asignación**:
    - Sugiere qué agente (Sonnet vs Haiku) es mejor para cada tarea.
