---
description: Ejecuta el plan de implementación de manera autónoma, escribiendo código, pasando tests y registrando cambios.
---

# 🚀 Implement Workflow — ClinicForge (SDD v2.0)

Ejecución disciplinada de cambios técnicos. **Pre-requisito:** Tener un `.spec.md` aprobado en `specs/`.

## Stack de Referencia (ClinicForge)
- **Backend:** `orchestrator_service/` — FastAPI + LangChain + asyncpg + Socket.IO
- **Frontend:** `frontend_react/src/` — React 18 + TypeScript + Vite + Tailwind + FullCalendar
- **DB Migrations:** `orchestrator_service/db.py` (Maintenance Robot — parches idempotentes en startup)
- **Infra:** Docker Compose (`docker-compose.yml`) / EasyPanel

---

## Orden de Ejecución

### 1. Backend — DB (si hay cambios de esquema)
- **Regla:** Añadir parche idempotente al final de `db.py` (Maintenance Robot). Nunca SQL manual.
- **Patrón:**
  ```sql
  DO $$ BEGIN
    ALTER TABLE patients ADD COLUMN IF NOT EXISTS medical_history JSONB;
  EXCEPTION WHEN others THEN NULL; END $$;
  ```
- **Idempotencia:** Siempre usar `IF NOT EXISTS`, `IF EXISTS`, `ON CONFLICT DO NOTHING`.

### 2. Backend — Nuevas Tools del Agente (`main.py`)
- Definir la función con `@tool` y su docstring completo (el agente lee el docstring para decidir cuándo usarla).
- Añadirla al array `DENTAL_TOOLS` al final.
- Usar `current_tenant_id.get()` y `current_customer_phone.get()` para contexto.
- Toda query SQL: `WHERE tenant_id = $x`.

### 3. Backend — System Prompt (`main.py` → `build_system_prompt`)
- La función retorna un f-string. Modificar bloques específicos sin romper el resto.
- Siempre respetar la POLÍTICA DE PUNTUACIÓN (no `¿` ni `¡`).
- Probar la coherencia del flujo de pasos 1-8 antes de guardar.

### 4. Backend — Nuevos Endpoints (`admin_routes.py`)
- Auth obligatoria: `current_user = Depends(verify_admin_token)`.
- Extraer `tenant_id` del usuario autenticado, nunca de query params.
- Patrón:
  ```python
  @admin_router.get("/admin/patients/by-phone/{phone}")
  async def get_patient_by_phone(phone: str, current_user=Depends(verify_admin_token)):
      tenant_id = current_user["tenant_id"]
      row = await db.pool.fetchrow(
          "SELECT * FROM patients WHERE tenant_id = $1 AND phone_number = $2",
          tenant_id, phone
      )
  ```
- Emitir eventos Socket.IO si la operación cambia datos del dashboard (`await sio.emit(...)`).

### 5. Backend — Servicios (`buffer_task.py`, `relay.py`, `chatwoot_client.py`)
- `buffer_task.py`: proceso central que invoca el agente, parsea respuestas e intercepta `[LOCAL_IMAGE:url]` para enviar imágenes.
- `relay.py`: buffer inteligente (10s texto/audio, 20s imagen).
- Modificar estas capas solo si la feature requiere cambiar cómo se procesa o envía un mensaje.

### 6. Frontend — Componentes nuevos (`components/`)
- Usar Tailwind. Scroll Isolation si el componente tiene contenido largo: `overflow-y-auto` interno.
- Iconos: `lucide-react` (ya instalado).
- i18n: todo texto visible usa `const { t } = useTranslation()` + clave en `es.json`, `en.json`, `fr.json`.
- Llamadas API: siempre vía `import api from '../api/axios'` (inyecta `Authorization` y `X-Admin-Token`).

### 7. Frontend — Vistas (`views/`)
- Si la vista tiene scroll propio: `<div className="flex-1 min-h-0 overflow-y-auto">` (Scroll Isolation).
- Formularios nuevos: no usar `dangerouslySetInnerHTML`. Para contenido dinámico: `<SafeHTML html={...} />`.
- Si es una ruta con hijos: `path="/*"` en `App.tsx`.

### 8. Frontend — i18n (`locales/`)
- Al añadir cualquier texto nuevo, agregar la clave en los 3 archivos: `es.json`, `en.json`, `fr.json`.
- Nunca hardcodear strings visibles en el JSX directamente.

---

## Checkpoints Obligatorios

| Antes de... | Verificar... |
|---|---|
| Modificar queries SQL | ¿Tiene `WHERE tenant_id = $x`? |
| Crear endpoint | ¿`Depends(verify_admin_token)` presente? ¿`tenant_id` viene del JWT? |
| Crear/editar sistema prompt | ¿No hay `¿` ni `¡`? ¿El flujo de pasos 1-8 es coherente? |
| Modificar Layout/contenedor UI | ¿Se preserva Scroll Isolation? |
| Añadir texto visible en React | ¿Está en los 3 archivos de locales? |
| Añadir parche de DB | ¿Es idempotente (`IF NOT EXISTS`)? |

---

## Verificación Post-Implementación
1. Ejecutar `/verify` (o el equivalente manual de revisar el código).
2. Si hay Docker local: `docker compose up -d --build` (o reiniciar solo el servicio: `docker compose restart orchestrator_service`).
3. Revisar logs: `docker compose logs -f orchestrator_service`.

---

## Regla de Oro
> Si durante la implementación se descubre que el plan o la spec están incompletos, **actualizar primero la spec** (`specs/*.spec.md`) y el `implementation_plan.md`, **luego continuar el código**. Nunca improvisar código sin actualizar el plano.
