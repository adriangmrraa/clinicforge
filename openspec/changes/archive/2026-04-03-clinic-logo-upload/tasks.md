# Tasks: Clinic Logo Upload UI

## Phase 1: Foundation & Translation

- [x] 1.1 Add branding translation keys to `frontend_react/src/locales/es.json` – insert the `branding` object with 21 keys as per spec-i18n.md.
- [x] 1.2 Add branding translation keys to `frontend_react/src/locales/en.json` – same keys as Spanish.
- [x] 1.3 Add branding translation keys to `frontend_react/src/locales/fr.json` – same keys as Spanish.
- [x] 1.4 Define constants `ACCEPTED_FILE_TYPES` and `MAX_FILE_SIZE` in ConfigView.tsx (frontend validation matching backend).

## Phase 2: Core Implementation (ConfigView Branding Tab)

- [x] 2.1 Add new state variables to ConfigView.tsx: `brandingTenantId`, `logoFile`, `logoPreview`, `uploadingLogo`, `logoError`, `currentLogoUrl`.
- [x] 2.2 Implement helper function `loadCurrentLogo(tenantId)` to fetch current logo via GET `/admin/public/tenant-logo/{tenant_id}` with cache busting.
- [x] 2.3 Implement helper function `validateFile(file)` that checks extension and size, returns error message key.
- [x] 2.4 Implement helper function `handleFileSelect(file)` that validates, creates preview URL, updates state.
- [x] 2.5 Implement helper function `handleUpload()` that POSTs logo file, dispatches custom event, refreshes preview, shows success toast.
- [x] 2.6 Add tab button for "Branding" in ConfigView tabs header (purple accent, Image icon, uses `t('branding.tab_title')`).
- [x] 2.7 Implement `renderBrandingTab()` function with tenant selector, current logo preview, drag‑and‑drop upload zone, selected file preview, error display, upload button.
- [x] 2.8 Integrate branding tab into tab content switch: conditionally render when `activeTab === 'branding'` and `user?.role === 'ceo'`.

## Phase 3: Integration & Real‑time Updates

- [x] 3.1 Add `useEffect` listener in Sidebar.tsx for custom event `tenant-logo-updated`; re‑fetch logo with cache busting and update state/favicon.
- [x] 3.2 Verify that `window.dispatchEvent` in ConfigView's `handleUpload` includes correct `tenant_id` detail.
- [x] 3.3 Ensure drag‑and‑drop zone uses proper event handlers (`onDragOver`, `onDrop`) and hidden file input.

## Phase 4: Testing

- [ ] 4.1 Write unit test for `validateFile()` – rejects invalid extensions, rejects oversized files, accepts valid files (reference spec‑frontend section 2.1–2.2).
- [ ] 4.2 Write unit test for `handleFileSelect()` – creates preview URL via `URL.createObjectURL`, clears preview on null.
- [ ] 4.3 Write unit test for `handleUpload()` – mocks API call, dispatches custom event on success.
- [ ] 4.4 Integration test: CEO user sees Branding tab, other roles do not (reference spec‑frontend section 6.2).
- [ ] 4.5 Integration test: Tenant dropdown loads clinics, selection triggers `loadCurrentLogo` (mock API).
- [ ] 4.6 Integration test: Upload flow – select file, upload, success, Sidebar updates (mock endpoints).
- [x] 4.7 Manual QA: drag‑and‑drop works across browsers, logo preview updates, Sidebar updates without refresh, favicon updates, translation switching.

## Phase 5: Cleanup & Verification

- [ ] 5.1 Verify all translation keys are used in UI and no missing keys.
- [ ] 5.2 Check accessibility: file input has label, error messages have `role="alert"`, buttons have appropriate ARIA labels.
- [ ] 5.3 Remove any debug console logs, ensure no lint errors.
- [x] 5.4 Confirm that uploaded logo appears in Sidebar and documents (backend already handles).