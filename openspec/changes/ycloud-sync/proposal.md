# Proposal: YCloud Full Message Sync

## Intent

Implementar sincronización completa de mensajes históricos desde la API de YCloud hacia la base de datos local. El sistema actual solo captura mensajes nuevos via webhooks; los mensajes antiguos (anteriores al webhook) y mensajes de conversaciones existentes no están sincronizados. Esta feature permite al CEO visualizar todo el historial de conversaciones y mantener un backup local de medios que expiran en 30 días en los servidores de Meta/YCloud.

## Scope

### In Scope
- **Backend**: Extend `YCloudClient` con métodos para fetch paginado de mensajes (`GET /v2/whatsapp/messages?limit=100`)
- **Backend**: Implementar upsert logic usando `external_id` (YCloud message ID) como unique constraint
- **Backend**: Descarga automática de media (imágenes, PDFs, audio, video) con almacenamiento local
- **Backend**: Patient linking mediante matching de números telefónicos con tabla `patients`
- **Frontend**: UI de sincronización con last sync time, botón "Sync Now", y contador de progreso en tiempo real
- **Frontend**: Restricción CEO-only para iniciar sincronización

### Out of Scope
- Sincronización de mensajes de otras plataformas (Chatwoot, Telegram)
- Exportación de historial a formatos externos (CSV, PDF)
- Reprocesamiento de mensajes ya sincronizados (solo sync nuevo)

## Approach

**Arquitectura híbrida asíncrona**: El sync será un proceso background celery/periodic task que itera sobre el cursor de paginación hasta obtener todos los mensajes. El frontend mostrará progreso mediante WebSocket o polling a un endpoint de estado.

**Pasos principales**:
1. Agregar método `fetch_messages(cursor_after: str)` a `YCloudClient`
2. Agregar método `download_media(media_id: str)` a `YCloudClient`
3. Crear nuevo endpoint `POST /admin/ycloud/sync` (CEO-only)
4. Almacenar media en `uploads/ycloud_media/{tenant_id}/{message_id}/`
5. Upsert en `chat_messages` usando `platform_metadata->>'provider_message_id'` como clave única
6. Linking de paciente: buscar en `patients` por `phone_number` matching `from` o `to`

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `orchestrator_service/ycloud_client.py` | Modified | Agregar métodos fetch_messages, download_media, get_media_url |
| `orchestrator_service/models.py` | Modified | Agregar campo `ycloud_external_id` unique constraint a ChatMessage |
| `orchestrator_service/admin_routes.py` | Modified | Nuevo endpoint `/admin/ycloud/sync` |
| `orchestrator_service/services/sync_service.py` | New | Lógica de sync, paginación, media download |
| `src/components/admin/YCloudSync.tsx` | New | Componente UI para CEO |
| `src/views/ConfigView.tsx` | Modified | Agregar pestaña "Sincronización YCloud" |
| `src/locales/es.json`, `en.json`, `fr.json` | Modified | Agregar claves de traducción |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Rate limiting YCloud API durante sync largo | High | Implementar retry con exponential backoff, batches de 100 mensajes |
| Media files muy grandes (>10MB) agotan storage | Medium | Limitar a 10MB por archivo, skip y loguear errores |
| Duplicados si sync corre dos veces en paralelo | Medium | Lock idempotente por tenant, marcar sync en ejecución |
| Timeout en sync de clínicas con muchos mensajes | High | Sync paginado, guardar cursor entre ejecuciones, endpoint de estado |

## Rollback Plan

1. **Deshabilitar endpoint de sync**: Quitar ruta `/admin/ycloud/sync` de admin_routes.py
2. **Revertir migraciones**: Eliminar columna `ycloud_external_id` si se agregó unique constraint
3. **Limpiar medios descargados**: Script para eliminar carpeta `uploads/ycloud_media/`
4. **Revertir frontend**: Remover компонент YCloudSync de ConfigView

## Dependencies

- `YCloudClient` existente en `orchestrator_service/ycloud_client.py`
- Tabla `chat_messages` con campos `tenant_id`, `from_number`, `platform_metadata`
- Tabla `patients` con campo `phone_number`
- CEO-only middleware en `/admin/*` routes

## Success Criteria

- [ ] CEO puede iniciar sync desde UI y ver progreso en tiempo real
- [ ] Todos los mensajes históricos se almacenan en chat_messages sin duplicados
- [ ] Medios (imágenes, PDFs, audio) se descargan y almacenan localmente
- [ ] Teléfonos de mensaje se linking con pacientes existentes en DB
- [ ] Sync es idempotente (correcciones no crean duplicados)
- [ ] Rate limiting y errores de red se manejan gracefully