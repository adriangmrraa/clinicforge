# Spec i18n: Clinic Logo Upload UI

**Change:** `clinic-logo-upload`
**Date:** 2026-04-03
**Status:** Spec
**Target:** `frontend_react/src/locales/es.json`, `en.json`, `fr.json`

---

## 1. Overview

All UI texts introduced by the Branding tab must be translatable via the existing i18n system (`useTranslation`). This spec defines the translation keys, their default English values, and the corresponding Spanish and French translations.

**Namespace:** `branding.*`

## 2. Translation Keys Table

| Key | English (default) | Spanish (es) | French (fr) | Notes |
|-----|-------------------|--------------|-------------|-------|
| `branding.tab_title` | Branding | Branding | Branding | Tab header label (used in tab button) |
| `branding.select_clinic` | Select Clinic | Seleccionar Clínica | Sélectionner la Clinique | Heading for tenant dropdown |
| `branding.select_clinic_hint` | Choose which clinic's logo you want to update. | Elegí de qué clínica querés actualizar el logo. | Choisissez la clinique dont vous souhaitez mettre à jour le logo. | Helper text below heading |
| `branding.current_logo` | Current Logo | Logo Actual | Logo Actuel | Heading for current logo preview |
| `branding.current_logo_hint` | The logo currently displayed in the Sidebar and documents. | El logo que se muestra actualmente en la barra lateral y en los documentos. | Le logo actuellement affiché dans la barre latérale et les documents. | Helper text |
| `branding.no_logo_uploaded` | No logo uploaded | No hay logo cargado | Aucun logo téléchargé | Shown when no logo exists for the clinic |
| `branding.upload_new_logo` | Upload New Logo | Subir Logo Nuevo | Télécharger un Nouveau Logo | Heading for upload section |
| `branding.upload_hint` | Upload a logo file to replace the current one. | Subí un archivo de logo para reemplazar el actual. | Téléchargez un fichier logo pour remplacer l'actuel. | Helper text |
| `branding.dropzone_text` | Drop logo here or click to browse | Arrastrá el logo acá o hacé clic para buscar | Déposez le logo ici ou cliquez pour parcourir | Text inside drag‑and‑drop zone |
| `branding.formats` | Formats | Formatos | Formats | Preceding list of allowed extensions |
| `branding.max_size` | Max size | Tamaño máximo | Taille maximale | Preceding size limit |
| `branding.browse_files` | Browse Files | Buscar Archivos | Parcourir les Fichiers | Button label for file picker |
| `branding.selected_file` | Selected File | Archivo Seleccionado | Fichier Sélectionné | Heading for selected file preview |
| `branding.preview` | Preview | Vista Previa | Aperçu | Alt text for preview image |
| `branding.upload_logo` | Upload Logo | Subir Logo | Télécharger le Logo | Primary upload button |
| `branding.uploading` | Uploading… | Subiendo… | Téléchargement… | Button label during upload |
| `branding.upload_success` | Logo uploaded successfully! | ¡Logo subido correctamente! | Logo téléchargé avec succès ! | Success toast message |
| `branding.upload_error` | Error uploading logo. Please try again. | Error al subir el logo. Intentá de nuevo. | Erreur lors du téléchargement du logo. Veuillez réessayer. | Generic upload error |
| `branding.error_unsupported_format` | File format not supported. Please use PNG, JPG, SVG, WebP, or ICO. | Formato de archivo no soportado. Usá PNG, JPG, SVG, WebP o ICO. | Format de fichier non pris en charge. Utilisez PNG, JPG, SVG, WebP ou ICO. | Validation error message |
| `branding.error_file_too_large` | File is too large. Maximum size is 2 MB. | El archivo es demasiado grande. El tamaño máximo es 2 MB. | Le fichier est trop volumineux. La taille maximale est de 2 Mo. | Validation error message |
| `branding.error_no_clinic_selected` | Please select a clinic first. | Primero seleccioná una clínica. | Veuillez d'abord sélectionner une clinique. | Shown when trying to upload without tenant selection |
| `branding.error_no_file_selected` | Please select a logo file first. | Primero seleccioná un archivo de logo. | Veuillez d'abord sélectionner un fichier logo. | Shown when upload button clicked without file |

## 3. Integration with Existing Keys

Some keys already exist in the configuration namespace and can be reused:

| Existing Key | Used For |
|--------------|----------|
| `config.select_placeholder` | Placeholder option in tenant dropdown (e.g., "Select…") |
| `common.remove` | Remove file button tooltip |
| `common.cancel` | Not used here, but available |
| `common.save` | Not used here, but available |

## 4. Adding Keys to Locale Files

Each locale file must be updated with the new `branding` object.

### 4.1 English (`en.json`)

Add under the root object:

```json
"branding": {
  "tab_title": "Branding",
  "select_clinic": "Select Clinic",
  "select_clinic_hint": "Choose which clinic's logo you want to update.",
  "current_logo": "Current Logo",
  "current_logo_hint": "The logo currently displayed in the Sidebar and documents.",
  "no_logo_uploaded": "No logo uploaded",
  "upload_new_logo": "Upload New Logo",
  "upload_hint": "Upload a logo file to replace the current one.",
  "dropzone_text": "Drop logo here or click to browse",
  "formats": "Formats",
  "max_size": "Max size",
  "browse_files": "Browse Files",
  "selected_file": "Selected File",
  "preview": "Preview",
  "upload_logo": "Upload Logo",
  "uploading": "Uploading…",
  "upload_success": "Logo uploaded successfully!",
  "upload_error": "Error uploading logo. Please try again.",
  "error_unsupported_format": "File format not supported. Please use PNG, JPG, SVG, WebP, or ICO.",
  "error_file_too_large": "File is too large. Maximum size is 2 MB.",
  "error_no_clinic_selected": "Please select a clinic first.",
  "error_no_file_selected": "Please select a logo file first."
}
```

### 4.2 Spanish (`es.json`)

Add under the root object:

```json
"branding": {
  "tab_title": "Branding",
  "select_clinic": "Seleccionar Clínica",
  "select_clinic_hint": "Elegí de qué clínica querés actualizar el logo.",
  "current_logo": "Logo Actual",
  "current_logo_hint": "El logo que se muestra actualmente en la barra lateral y en los documentos.",
  "no_logo_uploaded": "No hay logo cargado",
  "upload_new_logo": "Subir Logo Nuevo",
  "upload_hint": "Subí un archivo de logo para reemplazar el actual.",
  "dropzone_text": "Arrastrá el logo acá o hacé clic para buscar",
  "formats": "Formatos",
  "max_size": "Tamaño máximo",
  "browse_files": "Buscar Archivos",
  "selected_file": "Archivo Seleccionado",
  "preview": "Vista Previa",
  "upload_logo": "Subir Logo",
  "uploading": "Subiendo…",
  "upload_success": "¡Logo subido correctamente!",
  "upload_error": "Error al subir el logo. Intentá de nuevo.",
  "error_unsupported_format": "Formato de archivo no soportado. Usá PNG, JPG, SVG, WebP o ICO.",
  "error_file_too_large": "El archivo es demasiado grande. El tamaño máximo es 2 MB.",
  "error_no_clinic_selected": "Primero seleccioná una clínica.",
  "error_no_file_selected": "Primero seleccioná un archivo de logo."
}
```

### 4.3 French (`fr.json`)

Add under the root object:

```json
"branding": {
  "tab_title": "Branding",
  "select_clinic": "Sélectionner la Clinique",
  "select_clinic_hint": "Choisissez la clinique dont vous souhaitez mettre à jour le logo.",
  "current_logo": "Logo Actuel",
  "current_logo_hint": "Le logo actuellement affiché dans la barre latérale et les documents.",
  "no_logo_uploaded": "Aucun logo téléchargé",
  "upload_new_logo": "Télécharger un Nouveau Logo",
  "upload_hint": "Téléchargez un fichier logo pour remplacer l'actuel.",
  "dropzone_text": "Déposez le logo ici ou cliquez pour parcourir",
  "formats": "Formats",
  "max_size": "Taille maximale",
  "browse_files": "Parcourir les Fichiers",
  "selected_file": "Fichier Sélectionné",
  "preview": "Aperçu",
  "upload_logo": "Télécharger le Logo",
  "uploading": "Téléchargement…",
  "upload_success": "Logo téléchargé avec succès !",
  "upload_error": "Erreur lors du téléchargement du logo. Veuillez réessayer.",
  "error_unsupported_format": "Format de fichier non pris en charge. Utilisez PNG, JPG, SVG, WebP ou ICO.",
  "error_file_too_large": "Le fichier est trop volumineux. La taille maximale est de 2 Mo.",
  "error_no_clinic_selected": "Veuillez d'abord sélectionner une clinique.",
  "error_no_file_selected": "Veuillez d'abord sélectionner un fichier logo."
}
```

## 5. Verification Steps

After adding the keys, verify:

1. **No duplicate keys** – Ensure `branding` object does not already exist in locale files.
2. **JSON syntax** – Validate each file with a JSON linter.
3. **Missing translations** – If a key is missing in a locale, the fallback will be English; but all three files should be updated.
4. **Interpolation** – None of these keys require interpolation (no `{variable}` placeholders).

## 6. Usage in Components

All UI strings must be wrapped with `t('branding.key')`. Example:

```typescript
<h2 className="text-lg font-semibold text-white">{t('branding.select_clinic')}</h2>
<p className="text-sm text-white/40 mb-4">{t('branding.select_clinic_hint')}</p>
```

## 7. Future Extensibility

If additional branding settings (colors, fonts, favicon) are added later, new keys should be placed under the same `branding` namespace with descriptive sub‑keys (e.g., `branding.colors_primary`, `branding.font_family`).

---

**Next Phase:** Design (component mockups, layout adjustments).