# Spec — DLD-7: Telegram +3h Timezone Offset

**Change ID:** `telegram-tz-offset`
**Ticket:** `DLD-7`
**Status:** Draft
**Fecha:** 2026-04-17

---

## 1. Problema

asyncpg devuelve columnas `TIMESTAMPTZ` como objetos `datetime` timezone-aware en UTC.
Ni `_format_datetime` en `telegram_notifier.py` ni el bloque de formateo en `nova_morning.py`
convierten esas fechas a la zona horaria local del tenant antes de llamar a `.strftime()`.

El resultado observable: en producción (servidor UTC) los turnos aparecen con **+3 horas**
de diferencia en los mensajes de Telegram. Un turno a las 10:00 ART aparece como las 13:00.

**Raíz técnica confirmada:**

| Archivo | Línea | Problema |
|---------|-------|----------|
| `orchestrator_service/services/telegram_notifier.py` | 22-34 | `_format_datetime` llama `dt.strftime` sobre un datetime UTC sin conversión de TZ. No recibe `tenant_id` ni `ZoneInfo`. |
| `orchestrator_service/jobs/nova_morning.py` | 202-216 | `first["appointment_datetime"].strftime("%H:%M")` y `last["appointment_datetime"].strftime("%H:%M")` llaman directamente sobre el datetime UTC retornado por asyncpg. `tenant_tz` está disponible en el scope pero no se usa aquí. |
| `orchestrator_service/jobs/nova_morning.py` | 122 | `date.today()` usa la fecha del servidor (UTC), no la fecha local del tenant. |

---

## 2. Alcance

### 2.1 En scope

| # | Componente | Cambio |
|---|-----------|--------|
| S1 | `telegram_notifier._format_datetime` | Aceptar parámetro opcional `tz: ZoneInfo` y convertir antes de formatear |
| S2 | `telegram_notifier.notify_telegram` | Resolver timezone del tenant desde la DB y pasarla a `_format_datetime` vía `_format_event` |
| S3 | `telegram_notifier._format_event` | Propagar `tz` a los lambdas de `EVENT_FORMATS` que formatean fechas |
| S4 | `nova_morning._send_tenant_summary` | Convertir `appointment_datetime` a `tenant_tz` antes de `.strftime()` |
| S5 | `nova_morning._send_tenant_summary` | Usar `datetime.now(tenant_tz).date()` en lugar de `date.today()` para `today_str` y `day_name` |
| S6 | `nova_morning._maybe_send_tenant_summary` | Pasar `tenant_tz` a `_send_tenant_summary` para evitar re-query de TZ |

### 2.2 Fuera de scope

- Cambios en el esquema de base de datos (`tenants.timezone` ya existe).
- Modificación de la lógica de deduplicación Redis de `nova_morning` (ya usa `tenant_tz` correctamente para la clave de dedup y la comparación de hora).
- Formateo de fechas en otros canales (WhatsApp, email, frontend). Esos formatos son correctos o están fuera de este ticket.
- Agregar cache de timezone por tenant (puede venir en mejora posterior).
- Cambios en eventos de la API de Meta, YCloud o Socket.IO (ellos emiten datos; el formato es responsabilidad del notificador).
- Tests de integración con Telegram (requieren mock de bot externo).

---

## 3. Requisitos

### R1 — `_format_datetime` MUST convert to tenant timezone before formatting

`_format_datetime(raw, tz=None)` recibe un parámetro opcional `tz: ZoneInfo`.
Si se provee y el datetime es timezone-aware, convierte con `.astimezone(tz)` antes de `strftime`.
Si el datetime es naive (sin TZ info), lo trata como UTC aplicando `replace(tzinfo=timezone.utc)` antes de convertir.
Si `tz` es `None`, mantiene el comportamiento actual (sin conversión) para no romper callers existentes que no pasan TZ.

### R2 — `nova_morning.py` MUST use `tenant_tz` for all appointment time formatting

En `_send_tenant_summary`, cada `appointment_datetime` retornado por asyncpg DEBE convertirse a `tenant_tz` antes de llamar `.strftime("%H:%M")`.
La fecha del encabezado del resumen (`today_str`, `day_name`) DEBE derivarse de `datetime.now(tenant_tz).date()`, no de `date.today()`.
El parámetro `tenant_tz` (ya resuelto en `_maybe_send_tenant_summary`) debe pasarse a `_send_tenant_summary` para evitar una segunda consulta a la DB.

### R3 — ALL user-facing datetime formatting in Telegram MUST use local timezone

Todo campo visible en notificaciones Telegram que contenga hora (hora de turno en `NEW_APPOINTMENT`, `APPOINTMENT_UPDATED`, `APPOINTMENT_DELETED`, hora en `LEAD_RECOVERY_CONVERSION.appointment_datetime`) DEBE reflejar la hora en la zona horaria del tenant.
Ningún formatter puede emitir una hora UTC a un usuario final.

---

## 4. Escenarios

### Escenario 1 — Notificación de nuevo turno muestra hora local (caso principal)

```
Given: tenant con timezone = "America/Argentina/Buenos_Aires" (UTC-3)
  And: turno creado a las 13:00:00 UTC (= 10:00 ART)
  And: asyncpg retorna appointment_datetime como datetime(2026-04-17, 13, 0, 0, tzinfo=UTC)
When: se dispara evento NEW_APPOINTMENT y notify_telegram lo procesa
Then: el mensaje de Telegram muestra "Vie 17/04 10:00"
  And: NO muestra "Vie 17/04 13:00"
```

### Escenario 2 — Resumen matutino muestra hora local del primer y último turno

```
Given: tenant con timezone = "America/Argentina/Buenos_Aires"
  And: el resumen matutino se ejecuta para el tenant
  And: primer turno del día a las 12:00:00 UTC (= 09:00 ART)
  And: último turno del día a las 22:00:00 UTC (= 19:00 ART)
When: _send_tenant_summary construye el mensaje
Then: "Primer turno: 09:00" aparece en el mensaje
  And: "Último turno: 19:00" aparece en el mensaje
  And: la fecha del encabezado refleja la fecha local del tenant (no UTC)
```

### Escenario 3 — Servidor en UTC, tenant en zona sin offset

```
Given: tenant con timezone = "UTC"
When: se procesa un turno a las 15:00:00 UTC
Then: el mensaje muestra "15:00" (sin cambio — conversión es identidad)
```

### Escenario 4 — Datetime naive en el payload del evento

```
Given: un evento contiene appointment_datetime como string ISO sin offset ("2026-04-17T10:00:00")
  And: tenant timezone = "America/Argentina/Buenos_Aires"
When: _format_datetime(raw, tz=ZoneInfo("America/Argentina/Buenos_Aires")) procesa el valor
Then: el datetime naive se interpreta como UTC y se convierte a ART → "07:00"
  And: no lanza excepción
```

### Escenario 5 — Timezone inválida o desconocida en la DB

```
Given: tenant.timezone = "Timezone/Invalida" (corrupción o error de carga)
When: notify_telegram intenta resolver la TZ
Then: se usa el fallback "America/Argentina/Buenos_Aires"
  And: el mensaje se envía igual (no se bloquea la notificación)
  And: se loggea un warning con el tenant_id y el valor inválido
```

### Escenario 6 — `_format_datetime` sin TZ (backward compat)

```
Given: un caller existente llama _format_datetime(raw) sin pasar tz
When: se formatea el datetime
Then: el comportamiento es idéntico al actual (sin conversión)
  And: no se introduce ninguna regresión
```

### Escenario 7 — Resumen matutino en medianoche de cambio de fecha

```
Given: tenant timezone = "America/New_York" (UTC-5)
  And: la hora UTC del servidor es 05:00 (= 00:00 New York — cambio de día)
When: _maybe_send_tenant_summary calcula la fecha local para dedup y encabezado
Then: today_str refleja la nueva fecha en New York, no la fecha UTC del día anterior
```

---

## 5. Criterios de aceptación

| ID | Criterio | Verificable |
|----|---------|-------------|
| AC1 | `_format_datetime(raw, tz)` convierte el datetime a `tz` antes de formatear cuando `tz` no es `None` | Unit test: datetime UTC → resultado en ART |
| AC2 | `_format_datetime(raw)` sin `tz` tiene salida idéntica al comportamiento previo | Unit test: misma entrada, mismo output con y sin `tz=None` |
| AC3 | `notify_telegram` resuelve `tenants.timezone` de la DB y lo pasa a `_format_event` | Inspección de código + unit test con mock de DB |
| AC4 | `_send_tenant_summary` convierte `appointment_datetime` a `tenant_tz` antes de `.strftime()` | Unit test: asyncpg row UTC → hora formateada en ART |
| AC5 | `_send_tenant_summary` usa `datetime.now(tenant_tz).date()` para la fecha del encabezado | Unit test: servidor UTC, tenant ART → encabezado con fecha ART |
| AC6 | `_send_tenant_summary` recibe `tenant_tz` como parámetro (no re-consulta la DB) | Inspección de código: firma `_send_tenant_summary(tenant_id, tenant_tz)` |
| AC7 | Datetime naive sin TZ info se trata como UTC antes de convertir | Unit test: ISO sin offset → convertido correctamente |
| AC8 | Timezone inválida en DB → fallback a Buenos Aires + warning loggeado | Unit test: mock ZoneInfo raises KeyError → fallback + logger.warning |
| AC9 | Ningún test existente se rompe | `pytest` sin regresiones |

---

## 6. Notas de implementación (no normativas)

- `ZoneInfo` está importado en `nova_morning.py` con fallback a `backports.zoneinfo`. El mismo patrón de import debe usarse en `telegram_notifier.py`.
- La consulta de TZ en `notify_telegram` puede agregar ~1ms de latencia por notificación (asyncpg connection pool). Es aceptable dado el contexto fire-and-forget de Telegram.
- `_format_event` recibe `data: Any` y actualmente no recibe parámetros de contexto. La firma deberá extenderse a `_format_event(event, data, tz=None)` para propagar el TZ a los lambdas que invocan `_format_datetime`.
- El parámetro `tenant_tz` en `_send_tenant_summary` rompe la firma actual `_send_tenant_summary(tenant_id)`. Dado que el único caller es `_maybe_send_tenant_summary` (en el mismo módulo), no hay impacto externo.
