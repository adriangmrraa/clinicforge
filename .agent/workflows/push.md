---
description: Sincroniza el éxito local con GitHub. Crea automáticamente un repositorio privado si no existe.
---

# 🚀 Antigravity Push (Auto-Github)

Este comando gestiona la persistencia de tu código en la nube con un enfoque de "Privacidad por Defecto".

1.  **Detección de Repositorio**:
    - Verifica si la carpeta actual es un repositorio Git (`git status`).
    - Si no lo es, ejecuta `git init`.

2.  **Creación Automática en GitHub**:
    - Verifica si existe un "remote" llamado `origin`.
    - Si **no existe**:
      - Crea un nuevo repositorio en tu cuenta de GitHub con el nombre de la carpeta actual.
      - **CRÍTICO**: El repositorio se crea en modo **PRIVADO** por defecto.
      - Configura el remoto: `git remote add origin [URL]`.

3.  **Preparación de Archivos**:
    - Verifica la existencia de un `.gitignore` robusto (basado en el stack detectado).
    - Ejecuta `git add .`.

4.  **Commit y Envío**:
    - Genera un mensaje de commit semántico (ej: `feat: initial sdd structure` o `fix: according to audit`).
    - Ejecuta `git push -u origin main` (o la rama activa).

5.  **Confirmación**:
    - Entrega el link del repositorio privado al usuario.
    - Registra la URL en `.project_memory.json`.

// turbo
_Nota: Este comando asume que el repositorio no existe y lo crea de forma segura._
