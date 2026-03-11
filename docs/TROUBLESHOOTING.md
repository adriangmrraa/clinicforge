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

## 5. Base de Datos & Maintenance Robot

### 5.1. Error: Prepared statement "S_X" already exists / Transaction Error [NEW v8.1]
**Síntoma**: El servicio falla al arrancar con un error de base de datos relacionado con "prepared statements" o la transacción se cancela al ejecutar el script de inicialización.

**Causa**: El motor de `db.py` intentaba ejecutar scripts SQL largos (como `dentalogic_schema.sql`) dentro de una transacción ya abierta, lo que causaba colisiones en el driver `asyncpg` al intentar pre-compilar bloques con `;`.

**Solución**: Refactorizar `_run_evolution_pipeline` para adquirir una conexión fresca del pool por cada comando mayor, ejecutando los parches en sesiones aisladas. Esto evita que el estado fallido de un comando bloquee el canal del pool.

---
