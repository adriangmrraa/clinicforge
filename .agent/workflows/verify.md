```
---
description: Ciclo de Auto-verificación y Corrección. Ejecuta tests y arregla fallos sin intervención humana.
---

# 🧪 Verify Workflow - Dentalogic

Ciclo de auto-verificación técnica y funcional.

1.  **Backend Verification**:
    - Ejecutar scripts de validación:
      ```powershell
      ./verify_backend.ps1
      python verify_phases.py
      ```
    - Correr tests con Pytest: `pytest`.
2.  **Frontend Verification**:
    - Build test: `npm run build` en `frontend_react`.
3.  **Integrations Verification**:
    - Verificar conexión a PostgreSQL.
    - Test de sincronización GCal (crear/cancelar turno de prueba).
4.  **Security Audit**:
    - Ejecutar `/audit` para detectar drift de especificación.
3.  **Cross-Verification**: Prueba manualmente (vía terminal o scripts) que el resultado visual o de datos sea el esperado por la Spec.
4.  **Habilitación de Skill**: Si el fallo es persistente, invoca a `@systematic-debugging` para un análisis profundo.
```
