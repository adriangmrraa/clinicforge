---
description: Ronda de clarificación técnica. Identifica lagunas de lógica y ambigüedades en la especificación antes de planificar.
---

# 🔍 Antigravity Clarify

Este comando es el "Detector de Ambigüedades" para asegurar que la Spec sea perfecta.

1.  **Lectura Profunda**: Lee el archivo `.spec.md` actual.
2.  **Análisis Crítico**: Busca:
    - Casos de borde (edge cases) no contemplados.
    - Suposiciones implícitas del usuario.
    - Contradicciones entre la lógica de negocio y los esquemas de datos.
3.  **Cuestionario de Blindaje**:
    - Genera un máximo de 5 preguntas clave para el usuario.
    - No proceedas al `/plan` hasta que estas dudas estén resueltas.
4.  **Actualización**: Incorpora las respuestas directamente en la sección "Clarificaciones" del `.spec.md`.
