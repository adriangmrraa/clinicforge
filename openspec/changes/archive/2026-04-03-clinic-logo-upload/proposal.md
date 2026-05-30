# Proposal: Clinic Logo Upload UI

## Intent

Provide CEO with UI to upload clinic logos, enabling brand personalization across digital documents and UI. Backend already supports logo upload and serving; frontend missing configuration interface.

## Scope

### In Scope
- New "Branding" tab in ConfigView for CEO role
- Tenant selector (dropdown) for multi‑clinic CEOs
- Upload component with drag‑and‑drop, preview, format validation (PNG, JPG, SVG, WebP, ICO), size limit (2 MB)
- Real‑time logo update in Sidebar via custom event `tenant-logo-updated`
- Translation keys for all new UI texts (es, en, fr)
- Respect existing multi‑tenant isolation (tenant_id from JWT)

### Out of Scope
- Changing backend logo endpoint
- Supporting other branding customizations (colors, fonts, favicon) – future
- Logo editing (crop, resize) – future
- Non‑CEO roles accessing logo upload

## Approach

Add a new "Branding" tab within the CEO‑only section of ConfigView, following the same pattern as YCloud and Chatwoot integration tabs. Use existing tenant dropdown component. Build upload UI with react‑dropzone or similar, validate file before upload, show current logo preview. On successful upload, emit custom event to trigger Sidebar logo refresh. Add i18n keys.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `frontend_react/src/views/ConfigView.tsx` | New | Add "Branding" tab with upload component and tenant selector |
| `frontend_react/src/locales/es.json`, `en.json`, `fr.json` | Modified | Add translation keys for branding UI |
| `frontend_react/src/components/Sidebar.tsx` | Modified | Listen for `tenant-logo-updated` event and reload logo |
| `frontend_react/src/api/axios.ts` | None (already supports multipart) | No changes needed |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Logo not updating immediately in Sidebar | Low | Emit custom event `tenant-logo-updated`; Sidebar listens and re‑executes logo fetch |
| CEO selects wrong clinic | Low | Reuse existing tenant selector with clear label; show current clinic name |
| Browser caches old logo | Low | Add timestamp query param `?t=${Date.now()}` on refresh |
| Frontend/backend validation mismatch | Low | Replicate same format and size rules in frontend validation |

## Rollback Plan

1. Remove "Branding" tab from ConfigView.tsx.
2. Delete added translation keys from locale files.
3. Remove event listener from Sidebar.tsx.
4. No backend changes required; existing logos remain stored.

## Dependencies

- Backend endpoint POST `/admin/tenants/{tenant_id}/logo` (already live)
- Backend endpoint GET `/admin/public/tenant-logo/{tenant_id}` (already live)
- Existing tenant dropdown component (already used in YCloud/Chatwoot tabs)

## Success Criteria

- [ ] CEO can select a clinic, upload a logo, and see a preview of the uploaded logo.
- [ ] Sidebar updates the displayed logo without requiring a page refresh.
- [ ] Uploaded logo appears in digital documents (already working via backend).
- [ ] All UI texts are translatable (keys added to i18n files).
- [ ] File validation rejects files >2 MB or unsupported formats before upload.