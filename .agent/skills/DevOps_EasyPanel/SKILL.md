---
name: "EasyPanel DevOps"
description: "Experto en Dockerización, Docker Compose y despliegue en EasyPanel."
trigger: "Cuando toque Dockerfile, docker-compose.yml o variables de entorno."
scope: "DEVOPS"
auto-invoke: true
---

# Protocolo de Despliegue EasyPanel

1. **Gestión de Puertos:**
   - El `orchestrator` SIEMPRE escucha en `8000` (interno).
   - El frontend escucha en `80` (dentro de Nginx).
   - Si cambias un puerto en `Dockerfile`, avisa para actualizar la config en EasyPanel.

2. **Persistencia (Volúmenes):**
   - Si agregas una funcionalidad que guarda archivos (ej. `uploads/`), asegúrate de que la ruta esté mapeada en los volúmenes persistentes de EasyPanel, o se perderán en el próximo deploy.

3. **Variables de Entorno (Build vs Runtime):**
   - `VITE_` variables se inyectan en **BUILD TIME**. Si las cambias, hay que reconstruir la imagen.
   - Variables de Backend (Python) son **RUNTIME**. Solo requieren reinicio.

4. **Webhooks y Redirección:**
   - Para servicios como YCloud, el orquestador debe aceptar tanto `/webhook` como `/webhook/ycloud` para evitar errores 404 si el usuario olvida la ruta específica.

5. **Troubleshooting 401/422:**
   - 401 en Frontend → Falta `VITE_ADMIN_TOKEN` en build.
   - 422 en Orchestrator → Mismatch de nombres de campos en payload (normalizar en Pydantic).
