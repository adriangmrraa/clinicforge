# Spec General: Clinic Logo Upload UI

**Change:** `clinic-logo-upload`
**Date:** 2026-04-03
**Status:** Spec
**Type:** Frontend UI (Configuration)
**Priority:** P1 (Branding personalization)

---

## 1. Overview

Provide CEO users with a UI to upload clinic logos, enabling brand personalization across digital documents and UI. The backend already supports logo upload and serving (endpoints live); the frontend is missing the configuration interface.

This change adds a "Branding" tab within the CEO-only section of ConfigView, following the same pattern as YCloud and Chatwoot integration tabs. It includes tenant selector for multi‑clinic CEOs, drag‑and‑drop upload with preview, format/size validation, and real‑time logo update in the Sidebar via a custom event.

## 2. User Stories

### US-01: CEO Uploads Logo for a Clinic
**As a** CEO with multiple clinics,
**I want** to select a clinic, upload a logo file, and see a preview,
**so that** the clinic's branding appears in the Sidebar and digital documents.

### US-02: Real‑Time Sidebar Update
**As a** CEO,
**I want** the Sidebar logo to update immediately after a successful upload,
**so that** I don't need to refresh the page to see the new logo.

### US-03: Validation Before Upload
**As a** CEO,
**I want** the UI to reject unsupported file formats and files larger than 2 MB before attempting upload,
**so that** I get immediate feedback and avoid failed uploads.

### US-04: Multi‑Tenant Isolation
**As a** CEO with multiple clinics,
**I want** the logo upload to be scoped to the selected clinic (tenant),
**so that** each clinic can have its own distinct logo.

### US-05: CEO‑Only Access
**As a** system administrator,
**I want** only users with role `ceo` to see the Branding tab and upload logos,
**so that** branding changes remain under centralized control.

## 3. Acceptance Criteria

### AC‑01: Branding Tab Visibility
- [ ] The "Branding" tab appears in ConfigView only when `user.role === 'ceo'`.
- [ ] The tab is positioned between "Chatwoot (Meta)" and "Otras" tabs (following alphabetical order of existing tabs).
- [ ] The tab uses a matching icon (e.g., `Image` or `Palette` from Lucide) and follows the same styling as other tabs.

### AC‑02: Tenant Selector
- [ ] The tab includes a tenant dropdown populated from `/admin/chat/tenants`.
- [ ] The dropdown defaults to the first tenant if none selected.
- [ ] The dropdown uses the same component and styling as the YCloud/Chatwoot tabs.

### AC‑03: Upload Component
- [ ] Drag‑and‑drop zone with "Drop logo here" message and "Browse" button.
- [ ] Preview of the selected file (thumbnail) before upload.
- [ ] Clear display of current clinic logo (fetched from `/admin/public/tenant-logo/{tenant_id}`) with fallback placeholder.
- [ ] Upload button disabled until a valid file is selected.

### AC‑04: Frontend Validation
- [ ] Accepts only: PNG, JPG, JPEG, SVG, WebP, ICO (extensions: `.png`, `.jpg`, `.jpeg`, `.svg`, `.webp`, `.ico`).
- [ ] Maximum file size: 2 MB (2 097 152 bytes).
- [ ] Validation errors shown inline (e.g., "File too large", "Unsupported format").
- [ ] Validation occurs on file selection, before upload attempt.

### AC‑05: Upload API Integration
- [ ] On upload, send multipart/form‑data to `POST /admin/tenants/{tenant_id}/logo` with field `logo`.
- [ ] Show loading indicator during upload.
- [ ] On success, display success message and update preview with the new logo.
- [ ] On error (network, server error), show error message with details.

### AC‑06: Real‑Time Sidebar Update
- [ ] After successful upload, emit a custom event `tenant-logo-updated` with payload `{ tenant_id }`.
- [ ] Sidebar listens for this event and refreshes its logo by calling the same logo endpoint again (with cache‑busting query param).
- [ ] Sidebar updates the favicon as well (already implemented in existing logo fetch).

### AC‑07: i18n Support
- [ ] All UI texts are wrapped in `t()` calls with translation keys.
- [ ] Translation keys added to `es.json`, `en.json`, `fr.json` under namespace `branding.*`.

### AC‑08: Error States
- [ ] Network errors: display user‑friendly message with retry option.
- [ ] Server validation errors (e.g., "Invalid file type") displayed inline.
- [ ] Clear error dismissal after 5 seconds or on user action.

### AC‑09: Loading States
- [ ] Loading indicator while fetching current logo.
- [ ] Loading indicator during upload.
- [ ] Disabled buttons during loading to prevent duplicate submissions.

## 4. Architecture Decisions

### AD‑01: Reuse Existing ConfigView Pattern
The new "Branding" tab follows the same structure as YCloud and Chatwoot tabs:
- Tab header added to `activeTab` state and tab‑button list.
- Separate render function `renderBrandingTab()` that returns JSX.
- Use existing tenant dropdown component and state (`intConfig.tenant_id` or new dedicated state).
- Consistent styling with other tabs (backgrounds, spacing, card layout).

### AD‑02: File Upload Component
Use a lightweight custom component built on `<input type="file">` with drag‑and‑drop via `react-dropzone` (if already in dependencies) or native HTML5 drag events. Avoid adding new heavy libraries; keep bundle size minimal.

### AD‑03: Real‑Time Event System
Use browser's native `CustomEvent` API for cross‑component communication. The event is dispatched on `window` and listened to in Sidebar. This decouples the components without introducing global state.

### AD‑04: Logo Cache Busting
When Sidebar refreshes the logo, append a query parameter `?t=${Date.now()}` to the logo URL to bypass browser cache. The backend endpoint already serves with appropriate cache headers.

### AD‑05: Validation Mirror Backend
Frontend validation rules must match exactly the backend validation (file extensions, size limit). This ensures a smooth user experience and reduces unnecessary network errors.

### AD‑06: No Backend Changes Required
The backend endpoints are already live and tested. No modifications to `admin_routes.py`, file‑storage logic, or database schema are needed.

## 5. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Logo not updating in Sidebar after upload | Low | Medium | Use `CustomEvent` with explicit tenant_id; Sidebar listener re‑fetches logo with cache‑busting. |
| Frontend/backend validation mismatch | Low | Low | Copy validation constants from backend source code; add unit test comparing rules. |
| CEO selects wrong clinic and uploads logo | Low | Low | Clear tenant dropdown label; show current clinic name; confirm before upload? (optional). |
| Browser caches old logo despite cache‑busting | Low | Low | Use `fetch` with `cache: 'no-store'` or add random query param. |
| Large SVG/ICO files cause rendering issues | Medium | Low | Backend already validates; frontend can warn about recommended dimensions (e.g., 256×256). |
| Missing translation keys cause blank UI | Low | Low | Add keys to all three locale files; test with language switch. |

## 6. Success Metrics

- [ ] CEO can upload a logo for any clinic and see it in Sidebar within 2 seconds.
- [ ] No page refresh required for logo update.
- [ ] File validation prevents 100% of unsupported formats and oversized files.
- [ ] All UI texts translatable (keys present in locale files).
- [ ] No regression in existing ConfigView tabs.

## 7. Out of Scope

- Editing logos (crop, resize, filters).
- Supporting other branding customizations (colors, fonts, favicon).
- Non‑CEO roles accessing logo upload.
- Bulk logo upload or import.
- Logo versioning/history.

---

**Next Phase:** Design (detailed component specifications, UI mockups, event flow diagrams).