---
description: Cierre de hito/sprint. Limpia el entorno y registra el éxito en la memoria global.
---

# 🏁 Antigravity Finish

Protocolo de cierre profesional para cada feature implementada.

1.  **Limpieza de Workspace**:
    - Elimina archivos temporales o logs de depuración.
2.  **Registro de Memoria**:
    - Invoca a `@agent-memory-mcp` para archivar el éxito del proyecto.
    - Actualiza el historial de hitos en `.project_memory.json`.
3.  **Resumen de Entrega**:
    - Muestra al usuario el impacto: "Feature X implementada con [X] tests pasados y [X] de deuda técnica corregida".
4.  **Promoción**: Sugiere el próximo paso lógico (ej: "¿Quieres documentar esto con `/docs`?").
