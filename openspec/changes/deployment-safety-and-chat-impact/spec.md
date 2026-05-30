# Spec — DLD-5: Deployment Safety and Active Chat Impact

**Change ID:** `deployment-safety-and-chat-impact`
**Ticket:** DLD-5
**Status:** Draft
**Fecha:** 2026-04-17

---

## 1. Contexto

El orquestador reconstruye el system prompt en cada mensaje — no existe un snapshot por conversación. Esto implica que cualquier cambio de prompt entra en vigor de forma inmediata en todas las conversaciones activas, sin posibilidad de transición gradual.

Adicionalmente, el ciclo de vida actual presenta tres zonas de pérdida de mensajes:

1. **Restart abrupto**: `recover_orphaned_buffers()` (línea 9528 de `main.py`) detecta buffers huérfanos (sin timer ni `active_task`) y los **elimina** en lugar de reprocesarlos. Los mensajes que el paciente envió mientras el servidor no estaba disponible se pierden silenciosamente.

2. **Shutdown sin drain**: el bloque `lifespan` (línea 9686 de `main.py`) hace `yield`, deteniendo scheduler y DB, pero no espera a que las `asyncio.Task` de `process_user_buffer` activas en ese momento terminen. Los buffers en vuelo quedan truncados.

3. **Dead zone post-restart**: el lock `active_task:{provider}:{tenant_id}:{user}` tiene TTL de 300 segundos (`EX 300`, línea 139 de `buffer_manager.py`). Si un proceso muere sin liberar el lock, la próxima tarea para ese usuario no puede iniciarse durante hasta 5 minutos.

4. **Sin mecanismo de protección masiva**: no existe un endpoint para activar `human_override_until` en todas las conversaciones activas simultáneamente antes de un deploy con cambio de prompt significativo.

---

## 2. Objetivos

1. Que los mensajes recibidos durante un restart no se pierdan.
2. Que el orquestador no cierre conexiones mientras hay tareas activas procesando turnos de conversación.
3. Que el lock `active_task` no bloquee una conversación por más de 60 segundos después de un fallo.
4. Que el equipo técnico pueda proteger todas las conversaciones activas antes de un deploy con cambio de prompt.
5. Que exista una checklist operacional de deploy que formalice el procedimiento.

---

## 3. Alcance

### 3.1 En scope

| # | Componente | Descripción |
|---|------------|-------------|
| R1 | `recover_orphaned_buffers` | Re-procesar buffers huérfanos en lugar de eliminarlos |
| R2 | `lifespan` shutdown path | Agregar período de drain antes de cerrar DB |
| R3 | `active_task` lock TTL | Reducir de 300s a 60s |
| R4 | Documentación de deploy | Safe deployment checklist en `docs/` |
| R5 | Admin endpoint | Bulk human_override para conversaciones activas |

### 3.2 Out of scope

- **Conversation-scoped prompt snapshots**: capturar el system prompt en el momento en que inicia una conversación y usarlo durante toda esa conversación es trabajo futuro. Esta capacidad requiere un cambio de esquema (nuevo campo en `chat_conversations`) y modificaciones profundas en el path de construcción del prompt. No se incluye en este change.
- **Versionado de prompts**: un sistema de historial de versiones de system prompt (tipo deploy log) queda fuera de scope.
- **Rollback automático de prompt**: no se implementa ningún mecanismo que detecte degradación de conversaciones y revierta el prompt anterior.
- **Persistencia de buffers en PostgreSQL**: los buffers siguen siendo exclusivamente Redis. No se introduce durabilidad en base de datos para mensajes en vuelo.

---

## 4. Requisitos

### R1 — recover_orphaned_buffers DEBE re-procesar, no eliminar

**Archivo:** `orchestrator_service/main.py` (~línea 9528)

`recover_orphaned_buffers()` DEBE, para cada buffer huérfano encontrado:
1. Verificar que el buffer tiene al menos 1 mensaje (`llen > 0`).
2. Re-encolar el procesamiento llamando a `BufferManager.process_user_buffer(...)` (o equivalente) en lugar de `r.delete(buf_key)`.
3. Extraer `provider`, `tenant_id` y `external_user_id` del key (`buffer:{provider}:{tenant_id}:{user}`) para construir los parámetros correctos.
4. Loguear el re-procesamiento con nivel `INFO`: `"♻️ Re-processing orphaned buffer {buf_key} ({msg_count} msgs)"`.
5. Los buffers vacíos (llen == 0) PUEDEN ser eliminados — no contienen mensajes para el paciente.
6. Si la extracción del key falla por formato inesperado, el buffer DEBE eliminarse y loguearse con `WARNING`.

La función NO DEBE eliminar buffers con mensajes bajo ninguna otra circunstancia.

### R2 — Graceful shutdown DEBE esperar drain de tareas activas

**Archivo:** `orchestrator_service/main.py` (~línea 9686, bloque `# Shutdown` del lifespan)

El path de shutdown DEBE:
1. Registrar todas las `asyncio.Task` activas cuyo nombre comience con `buffer-task-` (las tareas de `process_user_buffer` DEBEN nombrarse con este prefijo — ver R2.1).
2. Esperar su finalización con un timeout de `DRAIN_TIMEOUT_SECONDS` (valor por defecto: 30 segundos, configurable vía variable de entorno `SHUTDOWN_DRAIN_TIMEOUT`).
3. Si el timeout expira antes de que todas las tareas terminen, loguear `WARNING` con los nombres de tareas que no completaron y continuar el shutdown.
4. Después de la espera (o timeout), continuar con el cierre de scheduler y DB como hoy.

**R2.1:** `asyncio.create_task(...)` en `BufferManager.process_user_buffer` DEBE asignar el parámetro `name=f"buffer-task-{provider}-{tenant_id}-{external_user_id}"` para permitir la identificación de tareas activas en el shutdown.

### R3 — TTL del lock active_task DEBE ser <= 60 segundos

**Archivo:** `orchestrator_service/services/buffer_manager.py` (línea 139)

El valor `ex=300` en `redis_client.set(lock_key, "1", nx=True, ex=300)` DEBE cambiarse a `ex=60`.

El nuevo TTL DEBE ser de 60 segundos. Dado que el timeout de turno del agente LangChain es de 45 segundos (definido en `agents/graph.py`), 60 segundos provee 15 segundos de margen antes de que el lock expire automáticamente.

Si el LLM tarda más de 60 segundos en responder (timeout de red, etc.), el lock expirar es el comportamiento correcto: el siguiente mensaje del mismo usuario podrá iniciar una nueva tarea sin esperar 5 minutos.

### R4 — Documentación DEBE incluir safe deployment checklist

**Archivo:** `docs/DEPLOYMENT_CHECKLIST.md` (archivo nuevo)

El documento DEBE incluir una sección titulada "Safe Deployment Checklist" con los siguientes ítems, en orden:

1. Verificar que no hay conversaciones activas de alta prioridad (pacientes en flujo de pago o agendamiento).
2. Activar human_override masivo si el deploy incluye cambios al system prompt (ver R5).
3. Confirmar que la nueva versión pasó `pytest tests/` sin regresiones.
4. Hacer deploy.
5. Verificar en logs que `recover_orphaned_buffers` se ejecutó y logueó re-procesamiento (si había buffers).
6. Confirmar que el drain completó dentro del `SHUTDOWN_DRAIN_TIMEOUT` (revisar logs del proceso saliente).
7. Desactivar human_override masivo (si fue activado en el paso 2).
8. Monitorear los primeros 15 minutos post-deploy buscando errores de LLM o timeouts de tool.

El documento DEBE incluir también la referencia al endpoint de bulk override (R5) con ejemplo de uso via `curl`.

### R5 — human_override DEBE ser activable en bulk

**Archivo:** `orchestrator_service/admin_routes.py`

DEBE existir un endpoint `POST /admin/conversations/bulk-override` que:

1. Requiera autenticación con `Depends(verify_admin_token)`.
2. Acepte un body JSON con los campos:
   - `duration_hours: float` (requerido) — duración del override en horas desde ahora.
   - `reason: str | None` (opcional) — razón del override para auditoría.
3. Resuelva `tenant_id` desde el token autenticado (Sovereignty Protocol — NUNCA desde el request body).
4. Ejecute un `UPDATE` en `patients` y un `UPDATE` en `chat_conversations` con `human_override_until = NOW() + interval '{duration_hours} hours'` filtrando por `tenant_id`.
5. Aplique el override SOLO a conversaciones con actividad en las últimas 24 horas (`last_message_at >= NOW() - INTERVAL '24 hours'` en `chat_conversations`).
6. Retorne un JSON con:
   - `overridden_conversations: int` — cantidad de conversaciones afectadas.
   - `overridden_patients: int` — cantidad de pacientes afectados.
   - `override_until: str` — timestamp ISO 8601 hasta el que dura el override.
7. Loguear la operación con nivel `INFO`: `"[BulkOverride] tenant={tenant_id} duration={duration_hours}h affected_conversations={n} reason={reason}"`.

DEBE existir también un endpoint `DELETE /admin/conversations/bulk-override` que:
1. Requiera autenticación con `Depends(verify_admin_token)`.
2. Revoque el override masivo: `UPDATE patients SET human_override_until = NULL WHERE tenant_id = $1 AND human_override_until > NOW()` y el equivalente en `chat_conversations`.
3. Retorne `{"revoked_conversations": int, "revoked_patients": int}`.

---

## 5. Escenarios

### S1 — Re-procesamiento de buffer huérfano al startup

```
GIVEN que el orquestador fue reiniciado abruptamente
  AND hay un buffer Redis `buffer:whatsapp:3:+5491112345678` con 2 mensajes
  AND no existe la key `timer:whatsapp:3:+5491112345678`
  AND no existe la key `active_task:whatsapp:3:+5491112345678`
WHEN `recover_orphaned_buffers()` se ejecuta en el startup
THEN se crea una nueva task de procesamiento para ese buffer
  AND los 2 mensajes son procesados por el LLM
  AND el paciente recibe una respuesta
  AND el log contiene `"♻️ Re-processing orphaned buffer buffer:whatsapp:3:+5491112345678 (2 msgs)"`
  AND el buffer NO es eliminado antes del procesamiento
```

### S2 — Buffer huérfano vacío se elimina limpiamente

```
GIVEN que existe `buffer:whatsapp:3:+5491199999999` con llen = 0
  AND no existe timer ni active_task para esa key
WHEN `recover_orphaned_buffers()` se ejecuta
THEN el buffer es eliminado
  AND NO se crea ninguna task de procesamiento
  AND el log NO contiene ningún warning de mensajes perdidos
```

### S3 — Shutdown espera drain de tarea activa

```
GIVEN que el orquestador recibe señal de shutdown (SIGTERM)
  AND hay una task `buffer-task-whatsapp-3-+5491112345678` activa procesando un turno
WHEN el bloque de shutdown del lifespan se ejecuta
THEN el proceso espera a que `buffer-task-whatsapp-3-+5491112345678` complete
  AND solo después cierra el scheduler y la conexión a DB
  AND la tarea tiene hasta `SHUTDOWN_DRAIN_TIMEOUT` segundos para terminar
```

### S4 — Drain timeout no bloquea el shutdown indefinidamente

```
GIVEN que hay una task activa que excede el SHUTDOWN_DRAIN_TIMEOUT
WHEN el timeout expira
THEN el shutdown continúa de todas formas
  AND el log contiene `WARNING` con el nombre de la tarea que no completó
  AND la DB se cierra normalmente
```

### S5 — Lock expirado no bloquea la conversación

```
GIVEN que el proceso previo murió dejando el lock `active_task:whatsapp:3:+5491112345678` activo
  AND han pasado 60 segundos desde que ese lock fue creado
WHEN llega un nuevo mensaje de `+5491112345678`
THEN el lock ya expiró y puede ser adquirido
  AND se procesa el nuevo mensaje sin demora
  AND el tiempo máximo de bloqueo observado fue <= 60 segundos
```

### S6 — Lock con TTL 300s bloquea sin razón (escenario actual — validación de regresión)

```
GIVEN que el proceso previo murió hace 61 segundos
  AND el lock tiene TTL reducido a 60s
WHEN llega un nuevo mensaje
THEN el lock ya no existe en Redis
  AND el nuevo mensaje se procesa de inmediato (no hay dead zone de 5 minutos)
```

### S7 — Bulk override activa protección en todas las conversaciones recientes

```
GIVEN que hay 5 pacientes con actividad en las últimas 24 horas en el tenant 3
  AND el usuario autenticado tiene role de admin del tenant 3
WHEN se hace `POST /admin/conversations/bulk-override` con `{"duration_hours": 1.0}`
THEN las 5 conversaciones tienen `human_override_until = NOW() + 1 hour`
  AND los 5 pacientes tienen `human_override_until` actualizado
  AND el endpoint retorna `{"overridden_conversations": 5, "overridden_patients": 5, "override_until": "<ISO timestamp>"}`
  AND el bot no responde mensajes entrantes de esos pacientes durante 1 hora
```

### S8 — Bulk override no afecta conversaciones inactivas

```
GIVEN que hay 2 pacientes sin mensajes en las últimas 24 horas en el tenant 3
  AND hay 3 pacientes con actividad reciente
WHEN se hace `POST /admin/conversations/bulk-override` con `{"duration_hours": 0.5}`
THEN solo los 3 pacientes recientes son afectados
  AND los 2 inactivos NO tienen su `human_override_until` modificado
  AND el endpoint retorna `{"overridden_conversations": 3, "overridden_patients": 3, ...}`
```

### S9 — Bulk override no afecta otras tenants (Sovereignty)

```
GIVEN que el admin del tenant 3 hace POST /admin/conversations/bulk-override
  AND el tenant 7 tiene conversaciones activas
WHEN el endpoint se ejecuta
THEN NINGÚN paciente del tenant 7 tiene su human_override modificado
  AND solo los pacientes con tenant_id = 3 son afectados
```

### S10 — Revocación de bulk override

```
GIVEN que el bulk override está activo para 4 conversaciones del tenant 3
WHEN se hace `DELETE /admin/conversations/bulk-override`
THEN las 4 conversaciones tienen `human_override_until = NULL`
  AND el bot vuelve a responder mensajes entrantes
  AND el endpoint retorna `{"revoked_conversations": 4, "revoked_patients": 4}`
```

---

## 6. Criterios de aceptación

| ID | Criterio | Verificable por |
|----|----------|-----------------|
| AC-1 | `recover_orphaned_buffers` no llama `r.delete(buf_key)` cuando `llen > 0` | Revisión de código + test unitario mock |
| AC-2 | `recover_orphaned_buffers` dispara procesamiento para cada buffer con mensajes | Test unitario: mock Redis con 1 buffer de 2 mensajes → assert `process_user_buffer` llamado 1 vez |
| AC-3 | Shutdown espera hasta `SHUTDOWN_DRAIN_TIMEOUT` segundos antes de continuar | Test de integración: tarea artificial que dura 5s + DRAIN_TIMEOUT=10s → shutdown completa tras 5s |
| AC-4 | Shutdown no espera indefinidamente si tarea no termina | Test: tarea que dura 999s + DRAIN_TIMEOUT=2s → shutdown completa en ~2s con WARNING en log |
| AC-5 | Todas las `create_task` de `process_user_buffer` incluyen `name=f"buffer-task-..."` | Revisión de código |
| AC-6 | El lock `active_task` se crea con `ex=60` | Revisión de código + grep en `buffer_manager.py` |
| AC-7 | `POST /admin/conversations/bulk-override` requiere `verify_admin_token` | Test: request sin token → 401 |
| AC-8 | `POST /admin/conversations/bulk-override` filtra por tenant del token, no del body | Test: tenant 3 no puede sobrescribir pacientes del tenant 7 |
| AC-9 | `POST /admin/conversations/bulk-override` solo afecta conversaciones con actividad en 24h | Test: 2 pacientes recientes + 1 antiguo → overridden_conversations = 2 |
| AC-10 | `DELETE /admin/conversations/bulk-override` revoca correctamente | Test: override activo → DELETE → human_override_until = NULL en DB |
| AC-11 | `docs/DEPLOYMENT_CHECKLIST.md` existe con los 8 ítems de la checklist | Revisión de archivo |
| AC-12 | La checklist incluye ejemplo de curl para el bulk override endpoint | Revisión de archivo |
| AC-13 | `pytest tests/` pasa sin regresiones nuevas | CI/CD / ejecución local |

---

## 7. Out of scope (futuro)

- **Conversation-scoped prompt snapshots**: guardar el system prompt vigente en el momento de inicio de cada conversación (campo `prompt_snapshot` en `chat_conversations`) y usarlo hasta que la conversación concluya. Requiere cambio de esquema Alembic, modificación del path de construcción del prompt en `buffer_task.py`, y política de expiración del snapshot (ej: 24 horas de inactividad). Es la solución definitiva al problema de impacto de prompt changes en mid-flight, pero fuera del alcance de este change por su complejidad y riesgo de regresión.
- **Versionado de prompts con rollback automático**: historial de versiones del system prompt con capacidad de revertir si se detecta degradación (drop en conversion rate o aumento en derivaciones humanas). Trabajo futuro en change dedicado.
- **Durabilidad de buffers en PostgreSQL**: mover los buffers de Redis a una tabla `message_buffer` en PostgreSQL para garantizar cero pérdida de mensajes incluso ante fallo total de Redis. Fuera de scope — requiere análisis de performance y cambio de arquitectura de mensajería.
