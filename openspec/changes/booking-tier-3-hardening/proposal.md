# Booking Flow — TIER 3 Hardening

## Intent

Cerrar las últimas tres deudas técnicas críticas del flujo de agenda, garantizando que el sistema sea **100% coherente entre lo que el paciente entiende y lo que el agente IA gestiona**, incluso bajo cambios de horario estacional, errores humanos en la UI, y disputas legales.

## Why now

- TIER 1 (commits `950a7c7` + `3f47ffe`) eliminó las race conditions a nivel base de datos.
- TIER 2 (commits `5c495c8` + `877fa92`) agregó notificación al profesional y aviso de deuda no bloqueante.
- Quedan tres riesgos operativos identificados en la auditoría arquitectónica que **deben** cerrarse antes de escalar a más clínicas:

  1. **Timezone hardcoded a `-3`**: rompe ante (a) reinstauración eventual de DST en Argentina, (b) onboarding de clínicas en países con horario de verano (Chile, México, España), y (c) cualquier cambio legal de huso horario en cualquier país soportado. Hoy hay **57 usos** de `ARG_TZ` en el código.
  2. **`reschedule_appointment` no valida `max_chairs`**: la validación de capacidad de sillas existe en `book_appointment` pero **no** en reschedule. Una secretaria reprogramando desde la UI puede meter un 5° turno en una clínica con 4 sillas, sin que el sistema lo detecte.
  3. **No hay audit log de mutaciones de turnos**: hoy es imposible auditar quién modificó un turno, cuándo, desde dónde, ni qué valores tenía antes. Una clínica seria necesita esta trazabilidad por motivos legales y de disputa con pacientes.

## Scope

### IN SCOPE

1. **Timezone dinámico por tenant**, derivado del `tenants.country_code` ya existente:
   - Tabla de mapeo `country_code → IANA timezone` (configurable, no hardcoded en código).
   - Helper `get_tenant_tz(tenant_id)` cacheado en memoria.
   - Refactor de los 57 usos de `ARG_TZ` / `get_now_arg()` para aceptar `tenant_id` y resolver dinámicamente.
   - Soporte completo para DST automático vía `zoneinfo` (Python 3.9+, ya disponible en runtime).
   - Migración para validar que todos los tenants existentes tengan `country_code` válido (default seguro: `AR` para los actuales).

2. **`reschedule_appointment` con chair check transaccional**:
   - Wrap UPDATE en `async with conn.transaction()`.
   - Validar `max_chairs` ANTES del UPDATE: contar turnos activos en el nuevo slot para el tenant; si excede `max_chairs`, rechazar.
   - Soportar la misma `UniqueViolationError` ya capturada en TIER 1.

3. **Audit log de mutaciones de turnos**:
   - Nueva tabla `appointment_audit_log` con: `id`, `tenant_id`, `appointment_id`, `action` (`created` | `rescheduled` | `cancelled` | `status_changed` | `payment_updated`), `actor_type` (`ai_agent` | `staff_user` | `patient_self` | `system`), `actor_id` (nullable, FK a `users.id` o tag IA/sistema), `before_values` (JSONB nullable), `after_values` (JSONB nullable), `source_channel` (`whatsapp` | `instagram` | `facebook` | `web_admin` | `nova_voice`), `reason` (text nullable), `created_at`.
   - Helper `await log_appointment_mutation(...)` invocado desde:
     - `book_appointment` (AI tool, después del INSERT exitoso)
     - `cancel_appointment` (AI tool)
     - `reschedule_appointment` (AI tool)
     - `admin_routes.py` endpoints de modificación de appointments (UI staff)
     - Nova tools que tocan appointments (`agendar_turno`, `cancelar_turno`, `reprogramar_turno`, `cambiar_estado_turno`)
   - Best-effort: el log NO debe romper la mutación si falla, pero debe loggear warning.
   - Endpoint admin `GET /admin/appointments/{id}/audit` para leer el historial (solo CEO/admin).

### OUT OF SCOPE (NO HACER)

- Lista de espera (prohibido por usuario, ya removido en TIER 1).
- Recordatorios automáticos desde backend (es responsabilidad de YCloud HSM).
- Multi-sesión / treatment plans bookeados juntos (lo gestiona la secretaria manual).
- Workload leveling entre profesionales.
- Pre-generación de slots para performance.
- Event sourcing completo de appointments (el audit log es suficiente).
- UI nueva para visualizar el audit log (solo el endpoint API; UI es trabajo posterior).

## Success Criteria

1. **Timezone**: cambiar `tenants.country_code` de `AR` a `CL` y verificar que `check_availability` y `book_appointment` razonan los slots en horario chileno (incluyendo DST). 0 referencias hardcoded a `-3` o `ARG_TZ` en código de producción.
2. **Reschedule chair check**: intentar reprogramar un turno a un slot donde ya hay `max_chairs` turnos activos → debe ser rechazado con mensaje claro al usuario, sin UPDATE en DB.
3. **Audit log**: cualquier mutación de appointment (vía AI, Nova, UI staff) deja una fila en `appointment_audit_log` con `before_values` y `after_values` cuando aplica. Endpoint `/admin/appointments/{id}/audit` retorna el historial completo cronológico.
4. **0 regresiones**: TIER 1 + TIER 2 siguen funcionando. Todas las pruebas existentes pasan.

## Risks

| Riesgo | Mitigación |
|--------|------------|
| Refactor de 57 usos de `ARG_TZ` rompe alguna ruta no testeada | Hacer el cambio en dos pasos: (1) introducir `get_tenant_tz()` que internamente devuelve `ARG_TZ` para no romper nada; (2) migrar usos uno a uno, con tests por archivo. |
| Audit log se vuelve hot table y degrada performance | Índice por `(tenant_id, appointment_id, created_at DESC)`. Sin foreign-key cascade hard a `appointments` (solo `ON DELETE SET NULL`) para conservar el historial aún si se borra el turno. |
| Reschedule chair check rechaza turnos legítimos por count incorrecto | Excluir el propio turno que se está reprogramando del COUNT (no contarse a sí mismo). |
| Tenants existentes con `country_code = 'US'` (default) terminan con timezone equivocada | Migración explícita: para todos los tenants en producción hoy (Dra. Laura), forzar `country_code = 'AR'` antes de activar el resolver dinámico. |

## Dependencies

- TIER 1 + TIER 2 ya mergeados en `main` (✅).
- Tabla `tenants.country_code` ya existe (✅, models.py:182).
- `zoneinfo` disponible en runtime Python 3.9+ (✅, ya usado por `dateutil`).
- Sin nuevas dependencias de paquetes externos.
