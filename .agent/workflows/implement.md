---
description: Ejecuta el plan de implementación de manera autónoma, escribiendo código, pasando tests y registrando cambios.
---

# 🚀 Implement Workflow - Dentalogic

Ejecución disciplinada de cambios técnicos.

1.  **Backend Changes**:
    - Modificar `main.py` para tools/agents.
    - Modificar `admin_routes.py` para endpoints.
    - Modificar `db.py` o `gcal_service.py` para lógica de datos.
2.  **Frontend Changes**:
    - Actualizar `views/` o `components/` en `frontend_react`.
3.  **Verification**:
    - Ejecutar `/verify` para asegurar que el sistema sigue íntegro.
    - Reiniciar contenedores: `docker compose up -d --build`.
