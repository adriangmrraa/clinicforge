# Delta for Frontend: YCloud Sync UI

**Change:** `ycloud-sync`
**Date:** 2026-04-10
**Status:** Spec

---

## 1. Overview

This specification defines the frontend requirements for the YCloud synchronization UI. The sync functionality will be integrated into the existing YCloud tab in ConfigView, allowing CEOs to initiate and monitor message synchronization from YCloud.

## 2. ADDED Requirements

### Requirement: Sync UI Integration

The system MUST add sync controls to the existing YCloud tab in ConfigView.

#### Scenario: CEO views YCloud tab

- GIVEN the user has role `ceo` and navigates to Settings → YCloud
- THEN the YCloud tab renders with existing webhook configuration
- AND new "Sync" section appears at the bottom of the tab
- AND "Sync Now" button is enabled (if no sync in progress)

#### Scenario: Non-CEO views YCloud tab

- GIVEN the user has role `secretary` or `professional`
- WHEN navigating to Settings → YCloud
- THEN the Sync section is NOT visible
- AND the tab shows only the webhook configuration

---

### Requirement: Sync Control Section UI

The sync UI MUST display the following elements:

#### Layout Structure
```jsx
<div className="ycloud-sync-section">
  {/* Header */}
  <div className="sync-header">
    <RefreshCcw className="icon" />
    <h3>Sincronización de Mensajes</h3>
  </div>

  {/* Status Info */}
  <div className="sync-status">
    <Clock className="icon" />
    <span>Última sincronización: {lastSyncAt || 'Nunca'}</span>
  </div>

  {/* Progress (when syncing) */}
  {isSyncing && (
    <div className="sync-progress">
      <Loader2 className="animate-spin" />
      <span>Mensajes recuperados: {progress.messages_fetched}...</span>
      <span>Guardados: {progress.messages_saved}</span>
      <span>Medios: {progress.media_downloaded}</span>
    </div>
  )}

  {/* Action Button */}
  <button
    onClick={handleStartSync}
    disabled={isSyncing}
    className="sync-button"
  >
    {isSyncing ? 'Sincronizando...' : 'Sincronizar Ahora'}
  </button>
</div>
```

---

### Requirement: Sync Button States

The system MUST reflect the current sync state in the button.

#### Scenario: Idle state

- GIVEN no sync is running and rate limit allows
- WHEN the button renders
- THEN it shows "Sincronizar Ahora" (or "Sync Now")
- AND it is enabled (not disabled)

#### Scenario: Syncing state

- GIVEN a sync task is in progress
- WHEN the button renders
- THEN it shows "Sincronizando..." with loading icon
- AND it is disabled
- AND progress counter is visible

#### Scenario: Rate limited state

- GIVEN last sync was less than 60 minutes ago
- WHEN the button renders
- THEN it shows "Espera {minutes} min"
- AND it is disabled

---

### Requirement: Password Verification Modal

The system MUST verify the CEO's password before starting a sync.

#### Scenario: Click sync button

- GIVEN the user clicks "Sincronizar Ahora"
- WHEN the confirmation modal appears
- THEN it asks for password: "Confirmá tu contraseña para iniciar la sincronización"
- AND the user must enter their password
- AND click "Confirmar" to proceed

#### Scenario: Invalid password

- GIVEN incorrect password is entered
- WHEN "Confirmar" is clicked
- THEN error message: "Contraseña inválida"
- AND the modal remains open

#### Scenario: Cancel modal

- GIVEN the modal is open
- WHEN the user clicks "Cancelar"
- THEN the modal closes
- AND no sync starts

---

### Requirement: Progress Updates via Polling

The system MUST poll for progress updates every 2 seconds during sync.

#### Scenario: Poll progress endpoint

- GIVEN a sync is in progress
- WHEN 2 seconds have passed since last poll
- THEN the component calls GET `/admin/ycloud/sync/status/{task_id}`
- AND updates the progress counters in the UI

#### Scenario: Sync completes

- GIVEN the polling returns `status: "completed"`
- WHEN the response is processed
- THEN the component stops polling
- AND displays success message
- AND updates "Última sincronización" timestamp

#### Scenario: Sync fails

- GIVEN the polling returns `status: "error"`
- WHEN the response is processed
- THEN the component stops polling
- AND displays error message with details

---

### Requirement: Error Display

The system MUST show sync errors to the user.

#### Scenario: Show error message

- GIVEN sync has encountered errors (e.g., media download failed)
- WHEN the sync completes or progress is displayed
- THEN errors are shown in a collapsible "Errores" section
- AND each error is listed with timestamp and description

#### Scenario: No errors

- GIVEN sync completed with no errors
- WHEN the sync completes
- THEN no error section is shown
- AND success message: "Sincronización completada: {count} mensajes"

---

## 3. Component Specifications

### New Component: YCloudSyncSection

**Path:** `src/components/admin/YCloudSyncSection.tsx`

**Props:**
```typescript
interface YCloudSyncSectionProps {
  tenantId: number;
  onStartSync: (password: string) => Promise<void>;
  onCancelSync: (taskId: string) => Promise<void>;
  className?: string;
}
```

**State:**
```typescript
interface SyncState {
  lastSyncAt: string | null;
  syncEnabled: boolean;
  isSyncing: boolean;
  progress: {
    task_id: string;
    status: 'queued' | 'processing' | 'completed' | 'error';
    messages_fetched: number;
    messages_saved: number;
    media_downloaded: number;
    errors: string[];
    started_at: string;
    completed_at: string | null;
  } | null;
}
```

---

### Integration: ConfigView.tsx Modification

The existing YCloud tab (`renderYCloudTab()`) will be modified to include the new sync section.

**Location:** After the existing credential table, before the closing `</div>` of the main grid container.

**Estimated added lines:** ~80 lines

---

## 4. API Integration

### Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/ycloud/sync/config` | GET | Load sync config and last sync time |
| `/admin/ycloud/sync/start` | POST | Start sync (with password) |
| `/admin/ycloud/sync/status/{task_id}` | GET | Poll progress |
| `/admin/ycloud/sync/cancel/{task_id}` | POST | Cancel running sync |

---

## 5. Acceptance Criteria

| ID | Criterion | Validation Method |
|----|-----------|-------------------|
| FC-01 | Sync section visible for CEO only | login as secretary, verify hidden |
| FC-02 | Button disabled during sync | Start sync, verify button disabled |
| FC-03 | Progress counter updates | Start sync, verify counter increments |
| FC-04 | Password required | Click button, verify modal appears |
| FC-05 | Invalid password shows error | Enter wrong password, verify error |
| FC-06 | Rate limiting enforced | Try sync < 60 min, verify disabled |
| FC-07 | Last sync time updates | Complete sync, verify timestamp shown |
| FC-08 | Errors displayed | Trigger error, verify error section appears |
| FC-09 | Cancel works | Click cancel, verify sync stops |
| FC-10 | i18n keys working | Switch language, verify translations |

---

## 6. Edge Cases

### EC-01: Network error during poll

- GIVEN polling fails (network timeout)
- WHEN error occurs
- THEN retry up to 3 times
- AND if all fail, show "Conexión perdida" message

### EC-02: Tab switch during sync

- GIVEN sync is running
- WHEN user navigates to different tab
- THEN sync continues in background
- AND progress is saved to component state

### EC-03: Page refresh during sync

- GIVEN sync is running
- WHEN user refreshes the page
- THEN sync continues (backend is independent)
- AND user can re-open tab to see progress

### EC-04: Very large message count

- GIVEN sync fetches 10,000+ messages
- WHEN pagination completes
- THEN UI shows final count
- AND completion message: "Sincronización completada"

---

## 7. Styling Guidelines

The sync section should follow the existing YCloud tab styling:

- **Background:** `bg-white/[0.03]` with `border-white/[0.06]`
- **Border radius:** `rounded-2xl`
- **Padding:** `p-4 sm:p-6`
- **Text colors:** Use `text-white`, `text-white/60`, `text-white/40`
- **Button:** Green primary button matching existing buttons
- **Loader:** Use existing `Loader2` with `animate-spin`

---

**Next Phase:** Design (detailed component mockups, layout adjustments).