# Design: Clinic Logo Upload UI

## Technical Approach

Add a "Branding" tab to ConfigView (CEO-only) that allows uploading clinic logos. The tab follows the same pattern as existing integration tabs (YCloud, Chatwoot). It includes a tenant dropdown, current logo preview, drag‑and‑drop upload zone with validation, and real‑time sidebar update via a custom event. The backend endpoints are already live; the frontend integrates with `POST /admin/tenants/{tenant_id}/logo` and `GET /admin/public/tenant-logo/{tenant_id}`.

## Architecture Decisions

### Decision: Reuse ConfigView Tab Pattern

**Choice**: Add a new tab button and render function within ConfigView.tsx, reusing existing tenant dropdown, styling, and state management patterns.

**Alternatives considered**:
- Create a separate view for branding settings.
- Embed logo upload within the "Clinics" management view.

**Rationale**: Consistency with other configuration sections (YCloud, Chatwoot) reduces cognitive load and maintenance cost. The ConfigView already has CEO‑only access control and tenant‑scoped data loading.

### Decision: Native Drag‑and‑Drop (no new library)

**Choice**: Use HTML5 drag events and `<input type="file">` as implemented in DocumentGallery component.

**Alternatives considered**:
- Import `react‑dropzone` for more features.
- Use a third‑party upload component.

**Rationale**: Keep bundle size minimal; the existing pattern already works and is accessible. No need for additional dependencies.

### Decision: Custom Event for Cross‑Component Communication

**Choice**: Dispatch a `tenant‑logo‑updated` event on `window` after successful upload; Sidebar listens and refreshes its logo.

**Alternatives considered**:
- Propagate state via React context or global store.
- Trigger a Sidebar refetch by passing a callback through the component tree.

**Rationale**: Decouples ConfigView from Sidebar without introducing new global state. The event payload includes `tenant_id` so only the affected clinic updates.

### Decision: Validation Mirroring Backend

**Choice**: Frontend validation constants (`ACCEPTED_FILE_TYPES`, `MAX_FILE_SIZE`) are copied from backend source code.

**Alternatives considered**:
- Rely solely on backend validation.
- Use a shared validation module (requires backend‑frontend code sharing).

**Rationale**: Provides immediate user feedback, reduces unnecessary network requests, and ensures consistency. The constants are simple and unlikely to change often.

### Decision: Cache Busting with Query Parameter

**Choice**: Append `?t=${Date.now()}` to the logo URL when Sidebar re‑fetches after an update.

**Alternatives considered**:
- Use `Cache‑Control: no‑cache` headers (already present).
- Invalidate the blob URL by revoking the old object URL.

**Rationale**: Simple and effective; bypasses browser cache while keeping the existing endpoint unchanged.

## Data Flow

1. **User selects clinic** → `brandingTenantId` updated → `loadCurrentLogo()` fetches current logo.
2. **User selects file** → `validateFile()` → preview generated → `logoFile` and `logoPreview` set.
3. **User clicks upload** → `handleUpload()` → POST `/admin/tenants/{tenant_id}/logo` (multipart/form‑data).
4. **On success**:
   - `loadCurrentLogo()` refreshes preview.
   - `window.dispatchEvent('tenant‑logo‑updated', { tenant_id })` fired.
   - Sidebar's listener triggers → re‑fetches logo with cache busting → updates logo state and favicon.
   - Success toast shown.
5. **On error** → error message displayed inline.

Diagram:

    ConfigView (Branding Tab) ── POST logo ──> Backend (save file, update DB)
          │                                      │
          │                                      │
          └─── dispatch event ──> Sidebar ── GET logo ──┘
                     (tenant‑logo‑updated)         (cache‑busted)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `frontend_react/src/views/ConfigView.tsx` | Modify | Add import of `Image`, `Upload`, `Stethoscope`. Add branding state variables, constants, helper functions (`loadCurrentLogo`, `validateFile`, `handleFileSelect`, `handleUpload`). Add tab button in tabs header. Add `renderBrandingTab` function. Add conditional rendering in tab content switch. |
| `frontend_react/src/components/Sidebar.tsx` | Modify | Add `useEffect` listener for `tenant‑logo‑updated` event. On event, re‑fetch logo with cache‑busting query param and update state/favicon. |
| `frontend_react/src/locales/es.json` | Modify | Add `branding` object with 21 translation keys (per spec‑i18n). |
| `frontend_react/src/locales/en.json` | Modify | Same as Spanish. |
| `frontend_react/src/locales/fr.json` | Modify | Same as Spanish. |

## Interfaces / Contracts

### New State (ConfigView)

```typescript
const [brandingTenantId, setBrandingTenantId] = useState<number | null>(null);
const [logoFile, setLogoFile] = useState<File | null>(null);
const [logoPreview, setLogoPreview] = useState<string | null>(null);
const [uploadingLogo, setUploadingLogo] = useState(false);
const [logoError, setLogoError] = useState<string | null>(null);
const [currentLogoUrl, setCurrentLogoUrl] = useState<string | null>(null);
```

### Constants

```typescript
const ACCEPTED_FILE_TYPES = '.png,.jpg,.jpeg,.svg,.webp,.ico';
const MAX_FILE_SIZE = 2 * 1024 * 1024; // 2 MB
```

### Custom Event Type

```typescript
// Event dispatched on window
interface TenantLogoUpdatedEventDetail {
  tenant_id: number;
}
// Usage:
window.dispatchEvent(new CustomEvent('tenant-logo-updated', { detail: { tenant_id } }));
```

### API Endpoints (existing)

- `POST /admin/tenants/{tenant_id}/logo` – expects `multipart/form‑data` with field `logo`. Returns `{ "status": "ok", "logo_url": string }`.
- `GET /admin/public/tenant-logo/{tenant_id}` – returns the logo file as image blob.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `validateFile()` – rejects invalid extensions/sizes, accepts valid ones. | Jest with mocked File objects. |
| Unit | `handleFileSelect()` – creates preview URL, clears on null. | Mock `URL.createObjectURL`. |
| Unit | `handleUpload()` – calls API with correct form data, dispatches event on success. | Mock `api.post`, `window.dispatchEvent`. |
| Integration | CEO user sees Branding tab; other roles do not. | Render ConfigView with different user roles. |
| Integration | Tenant dropdown loads clinics, selection triggers logo fetch. | Mock `/admin/chat/tenants` endpoint. |
| Integration | Upload flow: select file → upload → success → Sidebar updates. | End‑to‑end test with mocked backend. |
| Manual QA | Drag‑and‑drop works across browsers, logo preview updates, Sidebar updates without refresh, favicon updates, translation switching. | Manual verification on Chrome, Firefox, Safari. |

## Migration / Rollout

No migration required. The change is purely frontend and uses existing backend endpoints. Rollout can be immediate after code review and passing tests.

## Open Questions

- **Translation keys**: The spec‑i18n lists 21 keys, but they are not yet present in locale files. Should we add them as part of implementation? **Answer**: Yes, they must be added before merging.
- **Icon color**: The branding tab uses purple (`purple‑600`) to differentiate from other tabs. Is this color consistent with the existing design system? **Answer**: The design system uses indigo, green, blue, amber for tabs; purple is a new accent but acceptable for branding.
- **Error handling for missing tenant**: Should we show an error if user tries to upload without selecting a clinic? **Answer**: Yes, the upload button will be disabled, and we can show a helper text.
- **SVG/ICO rendering issues**: Should we warn about recommended dimensions? **Answer**: Out of scope; backend validation ensures file is an image; rendering is handled by browser.

---
*Design created: 2026‑04‑03*