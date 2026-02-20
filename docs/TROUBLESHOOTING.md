# Troubleshooting Guide

Este documento recopila problemas comunes, errores conocidos y sus soluciones para el despliegue y mantenimiento de Dentalogic.

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

## 4. UI & Layout (Mobile First)

### 4.1. Scroll bloqueado en dashboard
**Síntoma**: En mobile o pantallas con poco alto, no se puede hacer scroll para ver la lista de campañas.
**Causa**: El contenedor principal (`Layout.tsx`) tenía un `overflow-hidden` rígido.
**Solución**: Aplicar `overflow-y-auto` en el contenedor de contenido de `Layout.tsx` y asegurar que el `main` sea un flexbox de alto completo (`h-screen`).

### 4.2. Datos solapados en móviles
**Síntoma**: Los números de Inversión y ROI se pisan en pantallas pequeñas.
**Causa**: Layout de grilla estático (`grid-cols-2`).
**Solución**: Usar grillas responsivas (`grid-cols-1 sm:grid-cols-2`) y clases `break-words` para valores monetarios grandes.
