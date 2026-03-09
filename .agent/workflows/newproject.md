---
description: Scaffolding automático para nuevos proyectos Antigravity. Vincula Workflows/Skills globales y se contextualiza con la Memoria del Proyecto.
---

# 🏗️ Antigravity New Project Setup

1.  **Preguntar Nombre**: Solicita el nombre del proyecto.
2.  **Crear Directorio**: `mkdir [NombreProyecto]`.
3.  **Vinculación Híbrida (Local + Global)**:
    - // turbo
      `mkdir .agent\workflows, .agent\skills -Force`
    - // turbo
      `New-Item -ItemType Junction -Path ".agent\workflows\global" -Value "$GLOBAL_AGENT_PATH\workflows" -Force`
    - // turbo
      `New-Item -ItemType Junction -Path ".agent\skills\global" -Value "$GLOBAL_AGENT_PATH\skills" -Force`
4.  **Constitución Global (Vínculo Directo)**:
    - // turbo
      `New-Item -ItemType HardLink -Path ".antigravity_rules" -Value "$GLOBAL_AGENT_PATH\.antigravity_rules" -Force`
5.  **Contextualización Inmediata**:
    - **Acción del Agente**: Debes leer e interpretar obligatoriamente los archivos de reglas globales para asegurar consistencia arquitectónica.
6.  **Estructura de Carpetas**:
    - `src/`: Código fuente.
    - `docs/specs/`: Especificaciones `.spec.md`.
    - `docs/plans/`: Planes de implementación.
7.  **Inicialización**:
    - `git init`
    - Inicializar el entorno según el lenguaje del proyecto.
8.  **Siguiente Paso**:
    - Invoca automáticamente `/advisor` para empezar a discutir la idea del proyecto.
