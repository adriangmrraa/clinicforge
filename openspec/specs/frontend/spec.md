# Spec Frontend: Clinic Logo Upload UI

**Change:** `clinic-logo-upload`
**Date:** 2026-04-03
**Status:** Spec
**Target:** `frontend_react/src/views/ConfigView.tsx`, `frontend_react/src/components/Sidebar.tsx`

---

## 1. Component Specifications

### 1.1 ConfigView Branding Tab

**Location:** `frontend_react/src/views/ConfigView.tsx`

#### New State Variables

```typescript
// Add to existing state declarations
const [brandingTenantId, setBrandingTenantId] = useState<number | null>(null);
const [logoFile, setLogoFile] = useState<File | null>(null);
const [logoPreview, setLogoPreview] = useState<string | null>(null);
const [uploading, setUploading] = useState(false);
const [logoError, setLogoError] = useState<string | null>(null);
const [currentLogoUrl, setCurrentLogoUrl] = useState<string | null>(null);
```

#### New Constants

```typescript
const ACCEPTED_FILE_TYPES = '.png,.jpg,.jpeg,.svg,.webp,.ico';
const MAX_FILE_SIZE = 2 * 1024 * 1024; // 2 MB
```

#### New Helper Functions

```typescript
const loadCurrentLogo = async (tenantId: number) => {
  try {
    const url = `/admin/public/tenant-logo/${tenantId}?t=${Date.now()}`;
    const response = await api.get(url, { responseType: 'blob' });
    const objectUrl = URL.createObjectURL(response.data);
    setCurrentLogoUrl(objectUrl);
  } catch (e) {
    setCurrentLogoUrl(null);
  }
};

const validateFile = (file: File): string | null => {
  const ext = file.name.split('.').pop()?.toLowerCase();
  const allowedExts = ['png', 'jpg', 'jpeg', 'svg', 'webp', 'ico'];
  if (!ext || !allowedExts.includes(ext)) {
    return t('branding.error_unsupported_format');
  }
  if (file.size > MAX_FILE_SIZE) {
    return t('branding.error_file_too_large');
  }
  return null;
};

const handleFileSelect = (file: File | null) => {
  setLogoError(null);
  if (!file) {
    setLogoFile(null);
    setLogoPreview(null);
    return;
  }
  const error = validateFile(file);
  if (error) {
    setLogoError(error);
    setLogoFile(null);
    setLogoPreview(null);
    return;
  }
  setLogoFile(file);
  const previewUrl = URL.createObjectURL(file);
  setLogoPreview(previewUrl);
};

const handleUpload = async () => {
  if (!logoFile || !brandingTenantId) return;
  setUploading(true);
  setLogoError(null);
  const formData = new FormData();
  formData.append('logo', logoFile);
  try {
    await api.post(`/admin/tenants/${brandingTenantId}/logo`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    // Refresh current logo preview
    await loadCurrentLogo(brandingTenantId);
    // Emit event for Sidebar
    window.dispatchEvent(new CustomEvent('tenant-logo-updated', { detail: { tenant_id: brandingTenantId } }));
    showSuccess(t('branding.upload_success'));
    // Reset file selection
    setLogoFile(null);
    setLogoPreview(null);
  } catch (err: any) {
    setLogoError(err.message || t('branding.upload_error'));
  } finally {
    setUploading(false);
  }
};
```

#### Tab Button Addition

Add to the tabs header (around line 687–733):

```typescript
<button
  onClick={() => setActiveTab('branding')}
  className={`px-6 py-4 font-medium text-sm whitespace-nowrap border-b-2 transition-all flex items-center gap-2 ${
    activeTab === 'branding'
      ? 'border-purple-600 text-purple-600 font-semibold'
      : 'border-transparent text-white/40 hover:text-purple-400 hover:border-purple-500/20'
  }`}
>
  <Image size={18} /> Branding
</button>
```

**Icon choice:** Use `Image` from lucide-react (or `Palette`). Import at top: `import { Image } from 'lucide-react';`.

#### Render Function: `renderBrandingTab()`

```typescript
const renderBrandingTab = () => (
  <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-300">
    {/* 1. Tenant Selection */}
    <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6">
      <div className="flex items-center gap-2 mb-4">
        <Stethoscope size={20} className="text-white/60" />
        <h2 className="text-lg font-semibold text-white">{t('branding.select_clinic')}</h2>
      </div>
      <p className="text-sm text-white/40 mb-4">{t('branding.select_clinic_hint')}</p>
      <select
        className="w-full px-4 py-2 bg-white/[0.04] border-white/[0.08] rounded-xl text-white focus:ring-2 focus:ring-purple-500 outline-none transition-all"
        value={brandingTenantId === null ? '' : brandingTenantId}
        onChange={(e) => {
          const tid = e.target.value ? Number(e.target.value) : null;
          setBrandingTenantId(tid);
          if (tid) loadCurrentLogo(tid);
        }}
      >
        <option value="">{t('config.select_placeholder')}</option>
        {tenants.map(t => <option key={t.id} value={t.id}>{t.clinic_name}</option>)}
      </select>
    </div>

    {/* 2. Current Logo Preview */}
    {brandingTenantId && (
      <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6">
        <div className="flex items-center gap-2 mb-4">
          <Image size={20} className="text-white/60" />
          <h2 className="text-lg font-semibold text-white">{t('branding.current_logo')}</h2>
        </div>
        <p className="text-sm text-white/40 mb-4">{t('branding.current_logo_hint')}</p>
        <div className="flex items-center justify-center p-8 bg-white/[0.02] rounded-xl border border-dashed border-white/[0.06]">
          {currentLogoUrl ? (
            <img src={currentLogoUrl} alt={t('branding.current_logo')} className="max-h-32 max-w-full object-contain rounded-lg" />
          ) : (
            <div className="text-center text-white/30">
              <Image size={48} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">{t('branding.no_logo_uploaded')}</p>
            </div>
          )}
        </div>
      </div>
    )}

    {/* 3. Upload Zone */}
    <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6">
      <div className="flex items-center gap-2 mb-4">
        <Upload size={20} className="text-white/60" />
        <h2 className="text-lg font-semibold text-white">{t('branding.upload_new_logo')}</h2>
      </div>
      <p className="text-sm text-white/40 mb-4">{t('branding.upload_hint')}</p>

      {/* Drag‑and‑drop zone */}
      <div
        className={`border-2 border-dashed rounded-2xl p-8 text-center transition-colors ${
          logoError ? 'border-red-500/30 bg-red-500/5' : 'border-white/[0.08] hover:border-purple-500/40'
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        onDrop={(e) => {
          e.preventDefault();
          e.stopPropagation();
          const file = e.dataTransfer.files[0];
          handleFileSelect(file);
        }}
      >
        <Upload size={48} className="mx-auto mb-4 text-white/20" />
        <p className="text-white/60 mb-2">{t('branding.dropzone_text')}</p>
        <p className="text-xs text-white/30 mb-4">
          {t('branding.formats')}: PNG, JPG, SVG, WebP, ICO • {t('branding.max_size')}: 2MB
        </p>
        <label className="inline-block px-6 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-medium cursor-pointer transition-colors">
          {t('branding.browse_files')}
          <input
            type="file"
            className="hidden"
            accept={ACCEPTED_FILE_TYPES}
            onChange={(e) => handleFileSelect(e.target.files?.[0] || null)}
          />
        </label>
      </div>

      {/* Selected file preview */}
      {logoPreview && (
        <div className="mt-6 p-4 bg-white/[0.02] rounded-xl border border-white/[0.06]">
          <h3 className="text-sm font-medium text-white/70 mb-2">{t('branding.selected_file')}</h3>
          <div className="flex items-center gap-4">
            <img src={logoPreview} alt={t('branding.preview')} className="w-16 h-16 object-cover rounded-lg" />
            <div className="flex-1">
              <p className="text-white font-mono text-sm truncate">{logoFile?.name}</p>
              <p className="text-xs text-white/40">{logoFile && (logoFile.size / 1024).toFixed(0)} KB</p>
            </div>
            <button
              onClick={() => handleFileSelect(null)}
              className="p-2 text-white/40 hover:text-red-400 hover:bg-red-500/10 rounded-lg"
              title={t('common.remove')}
            >
              <Trash2 size={16} />
            </button>
          </div>
        </div>
      )}

      {/* Error message */}
      {logoError && (
        <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-xl flex items-center gap-2">
          <AlertCircle size={16} /> {logoError}
        </div>
      )}

      {/* Upload button */}
      <button
        onClick={handleUpload}
        disabled={!logoFile || !brandingTenantId || uploading}
        className="w-full py-3 mt-6 bg-purple-600 hover:bg-purple-700 disabled:bg-white/[0.06] disabled:text-white/30 text-white rounded-xl font-semibold shadow-lg shadow-purple-600/20 transition-all flex justify-center items-center gap-2"
      >
        {uploading ? <Loader2 className="animate-spin" /> : <CheckCircle2 size={18} />}
        {uploading ? t('branding.uploading') : t('branding.upload_logo')}
      </button>
    </div>
  </div>
);
```

**Note:** Import `Upload`, `Trash2`, `AlertCircle`, `CheckCircle2`, `Loader2` from lucide-react.

#### Integration into Tab Switch

Add to the tab content switch (around line 740–750):

```typescript
{activeTab === 'branding' && user?.role === 'ceo' && renderBrandingTab()}
```

### 1.2 Sidebar Logo Update Listener

**Location:** `frontend_react/src/components/Sidebar.tsx`

Add a useEffect to listen for the custom event and refresh the logo.

```typescript
// Add inside the Sidebar component, after existing useEffect hooks
useEffect(() => {
  const handleLogoUpdated = (event: CustomEvent<{ tenant_id: number }>) => {
    const currentTenantId = localStorage.getItem('X-Tenant-ID');
    // Only refresh if the updated logo belongs to the currently viewed tenant
    if (currentTenantId && parseInt(currentTenantId) === event.detail.tenant_id) {
      // Re‑fetch logo with cache busting
      const logoPath = `/admin/public/tenant-logo/${currentTenantId}?t=${Date.now()}`;
      api.get(logoPath, { responseType: 'blob' })
        .then(res => {
          const url = URL.createObjectURL(res.data);
          setLogoUrl(url);
          localStorage.setItem('CLINIC_LOGO', logoPath);
          const link = document.querySelector("link[rel~='icon']") as HTMLLinkElement;
          if (link) link.href = url;
        })
        .catch(() => {
          // Logo may have been removed; clear local storage
          localStorage.removeItem('CLINIC_LOGO');
          setLogoUrl('');
        });
    }
  };
  // Cast to any because TypeScript doesn't know about detail typing
  window.addEventListener('tenant-logo-updated', handleLogoUpdated as EventListener);
  return () => window.removeEventListener('tenant-logo-updated', handleLogoUpdated as EventListener);
}, []);
```

## 2. Validation Rules

### 2.1 File Extensions
- **Allowed:** `.png`, `.jpg`, `.jpeg`, `.svg`, `.webp`, `.ico`
- **Validation:** Check file extension case‑insensitively.
- **Backend match:** Same list in `admin_routes.py` (lines 2950‑2955).

### 2.2 File Size
- **Maximum:** 2 MB (2 097 152 bytes).
- **Validation:** Compare `file.size` with constant.
- **Backend match:** Same limit in `admin_routes.py` (line 2955).

### 2.3 MIME Types (Optional)
Frontend can also check `file.type` against a mapping:
- `image/png`, `image/jpeg`, `image/svg+xml`, `image/webp`, `image/x-icon`
- But rely primarily on extension because MIME types can be unreliable.

## 3. Event Flow

### 3.1 Upload Success Sequence

```
1. User selects clinic → `brandingTenantId` set → `loadCurrentLogo()` called.
2. User selects file → `validateFile()` → `logoPreview` set.
3. User clicks Upload → `handleUpload()` → POST /admin/tenants/{id}/logo.
4. On success:
   a. `loadCurrentLogo()` refreshes preview.
   b. `window.dispatchEvent('tenant-logo-updated', { tenant_id })` fired.
   c. Sidebar's listener triggers → re‑fetches logo → updates state and favicon.
   d. Success toast shown.
```

### 3.2 Error Handling Sequence

```
1. Validation error (format/size) → `logoError` set → inline message.
2. Network error → catch block → `logoError` set with server message.
3. Server error (HTTP 4xx/5xx) → same.
```

## 4. Styling Guidelines

- Use existing ConfigView card styles: `bg-white/[0.03]`, `border-white/[0.06]`, `rounded-2xl`, `p-4 sm:p-6`.
- Purple accent color (`purple-600`) for branding tab to distinguish from other integrations.
- Icons from Lucide with consistent size (20px for headings, 48px for empty states).
- Responsive design: stack vertically on mobile, maintain padding.

## 5. Accessibility

- All buttons have `aria-label` where appropriate.
- File input uses `<label>` as trigger for better touch targets.
- Error messages are announced via `aria-live` polite region (can be added via `role="alert"`).
- Color contrast meets WCAG AA (dark theme already compliant).

## 6. Testing Scenarios

### 6.1 Unit Tests (Frontend)
- `validateFile()` returns correct errors for invalid extensions/sizes.
- `handleFileSelect()` creates preview URL and clears on null.
- `handleUpload()` calls API with correct form data and dispatches event.

### 6.2 Integration Tests
- CEO user sees Branding tab; other roles do not.
- Tenant dropdown loads clinics and selects default.
- Upload flow: select file → upload → success → Sidebar updates.
- Error states display correctly.

### 6.3 Manual QA
- Drag‑and‑drop works across browsers.
- Logo preview updates in real‑time.
- Sidebar logo updates without page refresh.
- Favicon updates accordingly.
- Translation switching works (all keys present).

---

**Next Phase:** i18n translation keys specification.