# Tasks: YCloud Full Message Sync

## Phase 1: Foundation

- [x] 1.1 Create alembic migration `044_whatsapp_messages.py` with 16-column table
- [x] 1.2 Add WhatsAppMessage model to `orchestrator_service/models.py`
- [x] 1.3 Extend YCloudClient with `fetch_messages(cursor, limit)`, `get_media_url(media_id)`, `download_media(url, timeout)`
- [x] 1.4 Add phone normalization helper (E.164 format: 549 + area + número)

## Phase 2: Backend

- [x] 2.1 Create `orchestrator_service/services/ycloud_sync_service.py` with:
  - `start_sync(tenant_id, password)` - BackgroundTasks entry point
  - `process_page(cursor)` - fetch + persist loop
  - `download_media(msg)` - download and save to filesystem
  - `update_progress(state)` - Redis progress updates
  - `acquire_lock(tenant_id)` / `release_lock(tenant_id)` - Redis lock
  - Exponential backoff: 1s → 2s → 4s → 8s (max 60s), 5 retries
- [x] 2.2 Add API endpoints to `orchestrator_service/admin_routes.py`:
  - `POST /admin/ycloud/sync/start` - Start sync (body: tenant_id, password)
  - `GET /admin/ycloud/sync/status/{task_id}` - Get progress
  - `POST /admin/ycloud/sync/cancel/{task_id}` - Cancel running sync
  - `GET /admin/ycloud/sync/config/{tenant_id}` - Get sync settings
  - `PATCH /admin/ycloud/sync/config/{tenant_id}` - Update sync settings
- [x] 2.3 Implement Redis progress tracking with key `ycloud_sync:{tenant_id}:{task_id}`
- [x] 2.4 Add rate limiting logic (429 handling with backoff)
- [x] 2.5 Implement 30-minute timeout global for sync task

## Phase 3: Frontend

- [x] 3.1 Create `frontend_react/src/api/ycloud.ts`:
  - `startYCloudSync(tenantId, password)` - POST /admin/ycloud/sync/start
  - `getSyncStatus(taskId)` - GET /admin/ycloud/sync/status/{task_id}
  - `cancelSync(taskId)` - POST /admin/ycloud/sync/cancel/{task_id}
- [x] 3.2 Create `frontend_react/src/components/YCloudSyncSection.tsx`:
  - Props: tenantId, className
  - Display sync status (queued/processing/completed/error/cancelled)
  - Show messages_fetched, messages_saved, media_downloaded counters
  - Show errors list if any
  - "Iniciar Sincronización" button with password modal
  - Progress polling every 3 seconds during processing
- [x] 3.3 Integrate YCloudSyncSection into ConfigView.tsx YCloud tab
- [x] 3.4 Add i18n keys to `frontend_react/src/locales/es.json`:
  - `ycloud.sync.title`, `ycloud.sync.start`, `ycloud.sync.cancel`, `ycloud.sync.status.*`, `ycloud.sync.errors.*`
- [x] 3.5 Add i18n keys to `frontend_react/src/locales/en.json` and `fr.json`

## Phase 4: Integration

- [x] 4.1 Test single-page sync (100 messages) with mock data
- [x] 4.2 Verify phone normalization (54911... → +54911...)
- [x] 4.3 Verify Redis lock prevents concurrent syncs per tenant
- [x] 4.4 Verify media download saves to `uploads/{tenant_id}/whatsapp_media/`
- [x] 4.5 Verify frontend polling updates progress in real-time
- [x] 4.6 Manual E2E test with real YCloud account

## Phase 5: Cleanup

- [x] 5.1 Add sync_enabled feature flag to config/env (default true)
- [x] 5.2 Add documentation to DEPLOY_INSTRUCTIONS.md
- [x] 5.3 Final code review (no TODO comments, proper error handling)