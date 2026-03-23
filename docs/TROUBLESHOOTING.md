# Troubleshooting Guide

Este documento recopila problemas comunes, errores conocidos y sus soluciones para el despliegue y mantenimiento de ClinicForge.

## 1. YCloud (WhatsApp)

### 1.1. Error: Missing YCloud Credentials
**Síntoma**: El log del orchestrator muestra `ERROR:services.buffer_task:❌ Missing YCloud Credentials for tenant X` y el bot no responde en WhatsApp.

**Causa**: La tabla `credentials` no tiene la fila `YCLOUD_WHATSAPP_NUMBER` para el tenant indicado, o falta la `YCLOUD_API_KEY`.

**Solución**:
Ejecutar el siguiente SQL en la base de datos (reemplazando `1` por el tenant_id y el número por el del bot):
```sql
INSERT INTO credentials (tenant_id, name, value, created_at, updated_at) 
VALUES (1, 'YCLOUD_WHATSAPP_NUMBER', '+549...', NOW(), NOW()) 
ON CONFLICT (tenant_id, name) DO UPDATE SET value = EXCLUDED.value;
```

### 1.2. Regresión: Webhook silenciado
**Síntoma**: El webhook recibe mensajes pero no hay respuesta ni error en `buffer_task`.
**Causa**: Si `chat_webhooks.py` fuerza el proveedor a "chatwoot", los mensajes de YCloud se procesan buscando IDs inexistentes de Chatwoot.
**Validación**: Verificar que `_process_canonical_messages` reciba la variable `provider` dinámica, no un string hardcoded.

### 1.3. Error 500 / Webhooks ignorados (Silenciados) [YCloud API v2]
**Síntoma**: Los webhooks de YCloud devuelven `200 OK` en el access log, pero no se inyectan en base de datos ni disparan el agente IA.
**Causa**: Discrepancia de payloads. El adaptador intentó buscar campos V1 antiguos (`type == "message"`). YCloud V2 usa `type == "whatsapp.inbound_message.received"` almacenando la información bajo la llave `whatsappInboundMessage`.
**Solución**: El `YCloudAdapter` ha sido actualizado a formato V2. Si esto ocurre en el futuro, verificar que YCloud no haya cambiado su esquema de payload nuevamente mirando el Log `YCLOUD_RAW_PAYLOAD`.

### 1.4. Buffer Error: ModuleNotFoundError en `buffer_manager.py`
**Síntoma**: Entra el mensaje, pero la IA falla casi instantáneamente. El log marca: `ModuleNotFoundError: No module named 'orchestrator_service'`.
**Causa**: En el entorno Docker, el app root es `/app`. El uso de imports absolutos largos (ej. `from orchestrator_service.services...`) rompe la resolución en algunos despliegues de EasyPanel.
**Solución**: Usar siempre importaciones relativas (`from services.buffer_task import process_buffer_task`) o dependientes del `sys.path`.

### 1.5. Error 403: WHATSAPP_PHONE_NUMBER_UNAVAILABLE al enviar
**Síntoma**: La IA formula la respuesta correctamente pero falla en el envío final hacia WhatsApp. El cliente de YCloud loggea un error HTTP 403 indicando que no tienes acceso al número de teléfono X.
**Causa**: La configuración del número origen está incorrecta o mal referenciada. El Orquestador estaba usando un fallback genérico (`+5491162793009`) al no encontrar el número en `credentials`.
**Solución**: Validar que en el Frontend ("Sedes / Clínicas") el "Bot Phone (YCloud)" esté correcto. El archivo `response_sender.py` lee este número directamente de la tabla `tenants` columna `bot_phone_number`.

## 2. Chatwoot (Instagram/Facebook)

### 2.1. Conversaciones Fantasma (ID Numérico)
**Síntoma**: Se crean conversaciones con nombres numéricos (ej. "27") y sin mensajes.
**Causa**: `ChatwootAdapter` usaba el `sender_id` (agente) como `external_user_id` en mensajes salientes.
**Solución**: Asegurar que `ChatwootAdapter.normalize_payload` ignore mensajes donde `sender_type: "User"` si el ID coincide con un agente conocido, o usar el `conversation_id` para mapear correctamente.

### 2.2. Mensajes Duplicados (Echo)
**Síntoma**: El usuario ve su mensaje duplicado o el bot responde dos veces.
**Causa**: El webhook de Chatwoot envía un evento `message_created` tanto para el mensaje del usuario como para el mensaje enviado por la API (echo).
**Solución**: Implementar deduplicación por `provider_message_id`. Si el ID del evento coincide con un ID ya guardado en `platform_metadata`, se ignora.

## 3. Marketing & ROI

### 3.1. Meta Ads "DISCONNECTED" persistente
**Síntoma**: El frontend muestra "DISCONNECTED" aunque el token sea válido.
**Causa**: Sombra de rutas (Shadowing). Existía un endpoint duplicado en `admin_routes.py` que no devolvía el campo `is_connected`, bloqueando al de `marketing.py`.
**Solución**: Eliminar el endpoint legacy en `admin_routes.py`. Asegurar que el frontend envíe el header `X-Tenant-ID` para que el backend resuelva las credenciales correctas.

### 3.2. No se ven campañas históricas (9 meses+)
**Síntoma**: El selector "Lifetime" no muestra datos antiguos.
**Causa**: La API de Meta requiere un `date_preset` específico para datos históricos extensos.
**Solución**: El `MetaAdsClient` implementa `date_preset="maximum"` para el rango "lifetime".

### 3.3. Anuncios faltantes en Marketing Hub (Creativos) [NEW M6]
**Síntoma**: El sistema detecta 0 anuncios o faltan varios creativos que sí están en Ads Manager.
**Causa**: Si se expande el campo `insights` en el listado inicial, Meta omite anuncios que tienen gasto 0 en el periodo, incluso si están activos.
**Solución**: Usar la estrategia **Master Ad List**. Primero listar anuncios con `include_insights=False` y luego enriquecer el rendimiento en una etapa posterior de reconciliación en el backend.

### 3.4. Estado "Archived" o campañas faltantes por pausa [NEW M6]
**Síntoma**: No aparecen anuncios de campañas que están pausadas.
**Causa**: El filtro `effective_status` por defecto no incluía estados heredados.
**Solución**: Ampliar el filtro `effective_status` para incluir `CAMPAIGN_PAUSED`, `ADSET_PAUSED` y `WITH_ISSUES`.

## 4. UI & Layout (Mobile First)

### 4.1. Scroll bloqueado en dashboard
**Síntoma**: En mobile o pantallas con poco alto, no se puede hacer scroll para ver la lista de campañas.
**Causa**: El contenedor principal (`Layout.tsx`) tenía un `overflow-hidden` rígido.
**Solución**: Aplicar `overflow-y-auto` en el contenedor de contenido de `Layout.tsx` y asegurar que el `main` sea un flexbox de alto completo (`h-screen`).

### 4.3. Indicador de "Reconectando..." persistente [NEW v8.1]
**Síntoma**: El sistema muestra "Reconectando..." permanentemente o el icono de Wifi está en naranja.
**Causa**: El servidor de Socket.IO no es accesible o hay un firewall bloqueando WebSockets.
**Validación**:
1. Verificar que `BACKEND_URL` en el frontend apunte al dominio correcto del Orchestrator.
2. Confirmar que el puerto del orchestrator esté expuesto en la configuración de EasyPanel.
3. El frontend reintentará infinitamente con backoff exponencial. Si el internet vuelve y sigue en naranja, refrescar la página (`F5`).

### 4.2. Datos solapados en móviles
**Síntoma**: Los números de Inversión y ROI se pisan en pantallas pequeñas.
**Causa**: Layout de grilla estático (`grid-cols-2`).
**Solución**: Usar grillas responsivas (`grid-cols-1 sm:grid-cols-2`) y clases `break-words` para valores monetarios grandes.

---

## 6. Archivos y Archivos Adjuntos (Uploads)

### 6.1. Error 404 al descargar un archivo previamente subido
**Síntoma**: Al intentar descargar o previsualizar un documento subido a la historia clínica del paciente, el proxy devuelve un error HTTP `404 Not Found` que dice `"Falta el archivo en el servidor. (Posible reinicio del contenedor sin volumen persistente)"`. Sin embargo, en la UI el archivo sí figura listado.

**Causa**: Los archivos en el container Docker se guardan físicamente en `/app/uploads`. Como en EasyPanel (o el entorno de despliegue) no se configuró un **Volumen Persistente**, al reiniciarse la aplicación o implementarse una actualización, el contenedor se vuelve a construir perdiendo los archivos previos (mientras que la base de datos Postgres sí sobrevive y recuerda sus metadatos).

**Solución**:
1. Entrar al panel de EasyPanel para el servicio Orchestrator.
2. Navegar a **Almacenamiento (Storage)** -> **Puntos de montaje (Mounts)** -> **Agregar montaje de volumen**.
3. Crear un volumen con `Nombre: orchestrator_uploads` y `Ruta de montaje (Mount Path): /app/uploads`.
4. Volver a "Implementar" el servicio para que el contenedor use siempre este disco duro persistente externo. Los archivos anteriores lamentablemente se han perdido, pero los nuevos ya no se perderán.

---

## 7. Configuración de Clínica (Working Hours / Multi-Sede)

### 7.1. Working hours no persisten al crear o editar clínica
**Síntoma**: Se configuran horarios por día en el modal de editar clínica, se guarda con éxito (200 OK), pero al reabrir el modal los horarios vuelven a los valores por defecto (Lun-Vie 09:00-18:00).

**Causas (corregidas en v2026-03-21)**:
1. **POST /admin/tenants** no incluía `working_hours`, `address`, `google_maps_url` ni `consultation_price` en el INSERT SQL. Los datos se enviaban desde el frontend pero se descartaban silenciosamente.
2. **asyncpg devuelve JSONB como strings**: Dependiendo de la versión de asyncpg, los campos JSONB se devuelven como strings en vez de objetos parseados. `parseWorkingHours()` en el frontend rechazaba strings (`typeof raw === 'object'` → false) y retornaba defaults.

**Solución**:
- Backend: `POST /admin/tenants` ahora incluye todos los campos en el INSERT.
- Backend: `GET /admin/tenants` aplica `json.loads` defensivo a campos JSONB (`config`, `working_hours`).
- Frontend: `parseWorkingHours()` ahora intenta `JSON.parse()` si recibe un string.
- Frontend: Todos los `onChange` del modal usan `setFormData(prev => ...)` (functional updater) en vez de closure directa para evitar pérdida de estado por stale closures.

### 7.2. Agente IA no respeta horarios ni sede configurados por día
**Síntoma**: Se configura miércoles 12:00-18:00 con sede "Córdoba", pero el agente IA responde con disponibilidad 09:00-18:00 y sede incorrecta.

**Causa**: `check_availability` usaba env vars hardcodeadas (`CLINIC_HOURS_START=08:00`, `CLINIC_HOURS_END=19:00`) para TODOS los días, ignorando `tenants.working_hours`. La respuesta no incluía información de sede.

**Solución**: `check_availability` ahora:
1. Lee `tenants.working_hours` para el día consultado.
2. Usa los slots del día como rango horario (en vez de env vars globales).
3. Si el día está deshabilitado, responde "la clínica no atiende ese día".
4. Incluye sede, dirección y link de Maps en la respuesta.
`book_appointment` también incluye la sede del día en el mensaje de confirmación.

---

## 5. Base de Datos & Maintenance Robot

### 5.1. Error: Prepared statement "S_X" already exists / Transaction Error [NEW v8.1]
**Síntoma**: El servicio falla al arrancar con un error de base de datos relacionado con "prepared statements" o la transacción se cancela al ejecutar el script de inicialización.

**Causa**: El motor de `db.py` intentaba ejecutar scripts SQL largos (como `dentalogic_schema.sql`) dentro de una transacción ya abierta, lo que causaba colisiones en el driver `asyncpg` al intentar pre-compilar bloques con `;`.

**Solución**: Refactorizar `_run_evolution_pipeline` para adquirir una conexión fresca del pool por cada comando mayor, ejecutando los parches en sesiones aisladas. Esto evita que el estado fallido de un comando bloquee el canal del pool.

---

## Meta Native Connection (Agregado 2026-03-22)

### El popup de Facebook SDK no carga / queda "Cargando SDK..."

**Sintoma**: En Settings > Meta, el boton queda en "Cargando SDK..." y la consola muestra `VITE_FACEBOOK_APP_ID missing`.

**Causa**: Las variables `VITE_*` se inyectan en runtime via `env-config.js`, no en build time. Si las variables no estan en el template del Dockerfile, no se inyectan.

**Solucion**: Verificar que `frontend_react/Dockerfile` tiene las variables en el `env-config.js.template` y que `utils/env.ts` tiene las variables en `RuntimeEnv`. El hook `useFacebookSdk.ts` debe usar `getEnv('VITE_FACEBOOK_APP_ID')` (no `import.meta.env`).

### Error 422 al conectar (internal-sync)

**Sintoma**: El popup completa pero muestra "Meta Service Connection Failed". En logs del meta_service: `422 Unprocessable Entity`.

**Causa**: El endpoint `/admin/credentials/internal-sync` esperaba un body con tipos estrictos de Pydantic. `tenant_id` llegaba como int pero se esperaba str.

**Solucion**: El endpoint ahora parsea `request.json()` directamente sin modelo Pydantic estricto (fix aplicado 2026-03-22).

### Webhook challenge falla con "invalid literal for int()"

**Sintoma**: Meta no puede verificar la URL del webhook. En logs: `ValueError: invalid literal for int() with base 10`.

**Causa**: `verify_challenge()` hacia `int(challenge)` pero el challenge puede no ser numerico.

**Solucion**: Ahora retorna `PlainTextResponse(content=challenge)` sin conversion (fix aplicado 2026-03-22).

### Mensajes de Instagram no llegan (webhooks)

**Sintoma**: Facebook Messenger funciona pero Instagram DMs no generan webhooks.

**Causas posibles**:
1. El permiso `instagram_manage_messages` no esta en **Advanced Access** (solo Standard). Requiere App Review de Meta.
2. La cuenta de Instagram no tiene habilitado "Allow access to messages" en Instagram Settings > Privacy > Connected Tools.
3. Los webhooks de Instagram DM en realidad requieren la page subscription correcta (no solo el producto Instagram).

**Solucion**: Solicitar Advanced Access para `instagram_manage_messages` via App Review. Mientras tanto, usar Chatwoot para Instagram.

### Agente no envia respuesta (Chatwoot IDs missing)

**Sintoma**: El agente genera respuesta pero en logs aparece `Chatwoot IDs missing for conv X`.

**Causa**: La variable `row` (con datos de la conversacion) era sobreescrita por un loop `for row in context_rows` en `buffer_task.py`.

**Solucion**: Renombrada variable del loop a `ctx_row` (fix aplicado 2026-03-22).

### Token tracking error: "cannot access local variable 'os'"

**Sintoma**: Warning en logs: `Token tracking error (non-fatal): cannot access local variable 'os'`.

**Causa**: `import os` local dentro de un bloque condicional en `buffer_task.py` shadowed el import global.

**Solucion**: Eliminado el `import os` local redundante (fix aplicado 2026-03-22).

---

