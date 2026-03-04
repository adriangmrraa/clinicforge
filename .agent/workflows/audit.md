---
description: Detector de Desviación de la Especificación (Spec Drift). Compara el código contra la intención original.
---

# 🕵️ Antigravity Audit

Garantiza que el código no haya "olvidado" la razón por la que fue escrito.

1.  **Comparativa**:
    - Lee el `.spec.md` (SSOT).
    - Lee el código implementado en los archivos afectados.
2.  **Detección de Brechas**:
    - ¿Se implementaron todos los Criterios de Aceptación?
    - ¿Se respetaron los Esquemas de Datos?
    - ¿Hay lógica extra no pedida que ensucie la arquitectura?
3.  **Informe de Audit**:
    - ✅ **Match**: Todo en orden.
    - ⚠️ **Drift**: Lista las discrepancias encontradas.
4.  **Acción Correctiva**: Si hay Drift, sugiere crear una tarea de corrección inmediata.
