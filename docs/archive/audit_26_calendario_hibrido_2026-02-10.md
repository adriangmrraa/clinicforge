# Informe de Audit – Spec 26 (Calendario híbrido clínica/profesional)

**Fecha:** 2026-02-10  
**Spec de referencia:** contenido migrado a `docs/01_architecture.md`, `docs/08_troubleshooting_history.md` (sección Calendario e IA) y `docs/SPECS_IMPLEMENTADOS_INDICE.md`.  
**Workflow:** `.agent/workflows/audit.md`

---

## 1. Comparativa (código vs SSOT)

### 1.1 Backend – Persistencia de `calendar_provider`

| Criterio spec | Implementación | Estado |
|---------------|----------------|--------|
| PUT `/admin/tenants/{id}` acepta `calendar_provider` en body y actualiza `tenants.config` | `admin_routes.py`: `update_tenant` lee `data.get("calendar_provider")`, normaliza a `local`/`google`, hace `config = COALESCE(config,'{}')::jsonb \|\| jsonb_build_object('calendar_provider', ...)` | ✅ Match |
| GET devuelve `config` | GET `/admin/tenants` hace `SELECT id, clinic_name, bot_phone_number, config, ...` | ✅ Match |

### 1.2 Frontend – Modal clínicas

| Criterio spec | Implementación | Estado |
|---------------|----------------|--------|
| Al guardar se envía `calendar_provider` en el body | ClinicsView: PUT/POST con `calendar_provider: formData.calendar_provider` | ✅ Match |
| Al abrir modal se muestra `config.calendar_provider` | `formData.calendar_provider = clinica.config?.calendar_provider === 'google' ? 'google' : 'local'` al editar | ✅ Match |
| Tras guardar se refresca la lista | `fetchClinicas()` después de PUT/POST | ✅ Match |

### 1.3 Frontend – Modal Editar perfil (profesional)

| Criterio spec | Implementación | Estado |
|---------------|----------------|--------|
| Campo "ID Calendario (Google)" | UserApprovalView: input con `editFormData.google_calendar_id`, labels i18n | ✅ Match |
| Persistencia vía endpoint existente | PUT `/admin/professionals/{id}` con `google_calendar_id` en body; backend actualiza columna | ✅ Match |
| GET devuelve el valor para rellenar | GET `/admin/professionals/by-user/{user_id}` incluye `google_calendar_id` en SELECT (y fallback sin columna) | ✅ Match |

### 1.4 Frontend – Registro de profesional

| Criterio spec | Implementación | Estado |
|---------------|----------------|--------|
| Campo opcional "ID Calendario (Google)" | LoginView: estado `googleCalendarId`, campo en formulario | ✅ Match |
| Backend persiste en `professionals` | auth_routes: INSERT con `google_calendar_id`; fallback UndefinedColumnError si no existe columna | ✅ Match |

### 1.5 Backend – Tools y system prompt

| Criterio spec | Implementación | Estado |
|---------------|----------------|--------|
| `check_availability` usa `get_tenant_calendar_provider(tenant_id)` y, si google, `google_calendar_id` por profesional | main.py: calendar_provider; loop por profesionales con `gcal_service.get_events_for_day(calendar_id=cal_id)` cuando `cal_id` no nulo | ✅ Match |
| `book_appointment` / cancel / reschedule mismo criterio | book_appointment y cancel/reschedule usan `get_tenant_calendar_provider` y `google_calendar_id` del profesional | ✅ Match |
| System prompt explica local vs Google | Texto en prompt: "La disponibilidad se consulta en la agenda interna (local) o en Google Calendar por profesional según la configuración de la clínica" | ✅ Match |

### 1.6 Credenciales y documentación

| Criterio spec | Implementación | Estado |
|---------------|----------------|--------|
| `GOOGLE_CREDENTIALS` documentado | docs/02_environment_variables.md: fila en tabla Orchestrator con descripción y ejemplo | ✅ Match |
| Uso solo desde env | gcal_service lee variable de entorno | ✅ Match (según spec) |

---

## 2. Detección de brechas

- **Criterios de aceptación:** Los puntos del checklist de la spec 26 están cubiertos en código y flujos (tenants, profesionales, registro, tools, prompt, env).
- **Esquemas de datos:** Se respeta `tenants.config` (JSONB con `calendar_provider`) y `professionals.google_calendar_id`; fallbacks para BD sin columna.
- **Lógica extra:** Resolución de tenant por dígitos (`bot_number_clean` + REGEXP_REPLACE) es mejora operativa, no contradice la spec.

---

## 3. Drift corregido durante el audit

- **PostgreSQL REGEXP_REPLACE:** La búsqueda de tenant por número normalizado usaba el patrón `\D` (no dígito). En PostgreSQL el motor de regex es POSIX y **no soporta `\D`**. Se reemplazó por `[^0-9]` para que la comparación por solo dígitos funcione correctamente.
  - Archivo: `orchestrator_service/main.py`, endpoint `/chat`.

---

## 4. Verificación rápida de errores

- **check_availability con working_hours vacío:** Corregido previamente: si el día no tiene `enabled`+`slots`, no se marca el día como ocupado y se considera horario clínica.
- **Sin profesionales activos:** Se devuelve mensaje claro; no se llama a `generate_free_slots` con mapa vacío.
- **Logging /chat y check_availability:** Hay logs al recibir chat, al resolver tenant y al entrar/salir/fallar check_availability para facilitar diagnóstico en producción.

---

## 5. Conclusión

- **Match:** La implementación cumple la spec 26 (calendario híbrido por clínica y profesional, persistencia, frontend, tools, prompt, documentación de env).
- **Drift corregido:** Uso de `[^0-9]` en REGEXP_REPLACE para resolución de tenant por número.
- **Recomendación:** Tras desplegar, comprobar en entorno real: (1) Clínica con `calendar_provider: google`, (2) Al menos un profesional con `google_calendar_id` y (3) `GOOGLE_CREDENTIALS` válido; luego probar “¿Tenés turnos el miércoles?” y revisar logs del orchestrator si la respuesta no muestra disponibilidad.
