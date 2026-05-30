# Spec i18n: YCloud Sync UI

**Change:** `ycloud-sync`
**Date:** 2026-04-10
**Target:** `frontend_react/src/locales/es.json`, `en.json`, `fr.json`

---

## 1. Overview

All UI texts introduced by the YCloud Sync section must be translatable via the existing i18n system (`useTranslation`). This spec defines the translation keys, their default English values, and the corresponding Spanish and French translations.

**Namespace:** `ycloud_sync.*`

---

## 2. Translation Keys Table

| Key | English (default) | Spanish (es) | French (fr) | Notes |
|-----|-------------------|--------------|-------------|-------|
| `ycloud_sync.section_title` | Mensajes WhatsApp | Mensajes WhatsApp | Messages WhatsApp | Section header |
| `ycloud_sync.last_sync` | Última sincronización | Última sincronización | Dernière synchronisation | Label for last sync timestamp |
| `ycloud_sync.never_synced` | Nunca | Nunca | Jamais | Shown when no sync has run |
| `ycloud_sync.sync_now` | Sincronizar Ahora | Sincronizar Ahora | Synchroniser Maintenant | Primary button |
| `ycloud_sync.syncing` | Sincronizando... | Sincronizando... | Synchronisation... | Button state during sync |
| `ycloud_sync.wait_minutes` | Espera {minutes} min | Espera {minutes} min | Attendez {minutes} min | Rate limit message |
| `ycloud_sync.progress_fetched` | Mensajes recuperados | Mensajes recovering | Messages récupérés | Progress label |
| `ycloud_sync.progress_saved` | Guardados | Guardados | Enregistrés | Progress counter |
| `ycloud_sync.progress_media` | Medios | Medios | Médias | Media download counter |
| `ycloud_sync.confirm_title` | Confirmar Sincronización | Confirmar Sincronización | Confirmer la synchronisation | Modal title |
| `ycloud_sync.confirm_password` | Ingresá tu contraseña para iniciar | Ingresá tu contraseña para iniciar | Entrez votre mot de passe pour démarrer | Modal description |
| `ycloud_sync.cancel` | Cancelar | Cancelar | Annuler | Cancel button |
| `ycloud_sync.confirm` | Confirmar | Confirmar | Confirmer | Confirm button |
| `ycloud_sync.invalid_password` | Contraseña inválida | Contraseña inválida | Mot de passe invalide | Error message |
| `ycloud_sync.success` | Sincronización completada | Sincronización completada | Synchronisation terminée | Success message |
| `ycloud_sync.success_detail` | {count} mensajes sincronizados | {count} mensajes sincronizados | {count} messages synchronisés | Success details |
| `ycloud_sync.error` | Error en sincronización | Error en synchronisation | Erreur de synchronisation | Error header |
| `ycloud_sync.errors_title` | Errores | Errores | Erreurs | Error section title |
| `ycloud_sync.cancel_sync` | Cancelar | Cancelar | Annuler | Cancel button |
| `ycloud_sync.rate_limited` | Rate limited: wait {minutes} min | Rate limited: wait {minutes} min | Rate limited: wait {minutes} min | Rate limit error |
| `ycloud_sync.already_running` | Sincronización en curso | Sincronización en curso | Synchronisation en cours | Already syncing error |
| `ycloud_sync.network_error` | Error de conexión | Error de conexión | Erreur de connexion | Network error |
| `ycloud_sync.network_retry` | Reintentando... | Reintentando... | Réessai... | Retry message |

---

## 3. Integration with Existing Keys

Some existing keys can be reused:

| Existing Key | Used For |
|--------------|----------|
| `common.save` | Not used here |
| `common.cancel` | Cancel button in modal |
| `common.confirm` | Confirm button in modal |
| `common.error` | Generic error prefix |
| `config.field_tenant` | Not used here - tenant comes from context |

---

## 4. Adding Keys to Locale Files

### 4.1 English (`en.json`)

Add under the root object:

```json
"ycloud_sync": {
  "section_title": "WhatsApp Messages",
  "last_sync": "Last synchronization",
  "never_synced": "Never",
  "sync_now": "Sync Now",
  "syncing": "Syncing...",
  "wait_minutes": "Wait {minutes} min",
  "progress_fetched": "Messages recovered",
  "progress_saved": "Saved",
  "progress_media": "Media",
  "confirm_title": "Confirm Synchronization",
  "confirm_password": "Enter your password to start the synchronization",
  "cancel": "Cancel",
  "confirm": "Confirm",
  "invalid_password": "Invalid password",
  "success": "Synchronization completed",
  "success_detail": "{count} messages synchronized",
  "error": "Synchronization error",
  "errors_title": "Errors",
  "cancel_sync": "Cancel",
  "rate_limited": "Rate limited: wait {minutes} min",
  "already_running": "Synchronization already in progress",
  "network_error": "Connection error",
  "network_retry": "Retrying..."
}
```

### 4.2 Spanish (`es.json`)

Add under the root object:

```json
"ycloud_sync": {
  "section_title": "Mensajes WhatsApp",
  "last_sync": "Última sincronización",
  "never_synced": "Nunca",
  "sync_now": "Sincronizar Ahora",
  "syncing": "Sincronizando...",
  "wait_minutes": "Espera {minutes} min",
  "progress_fetched": "Mensajes recuperados",
  "progress_saved": "Guardados",
  "progress_media": "Medios",
  "confirm_title": "Confirmar Sincronización",
  "confirm_password": "Ingresá tu contraseña para iniciar la sincronización",
  "cancel": "Cancelar",
  "confirm": "Confirmar",
  "invalid_password": "Contraseña inválida",
  "success": "Sincronización completada",
  "success_detail": "{count} mensajes sincronizados",
  "error": "Error en sincronización",
  "errors_title": "Errores",
  "cancel_sync": "Cancelar",
  "rate_limited": "Rate limited: wait {minutes} min",
  "already_running": "Sincronización en curso",
  "network_error": "Error de conexión",
  "network_retry": "Reintentando..."
}
```

### 4.3 French (`fr.json`)

Add under the root object:

```json
"ycloud_sync": {
  "section_title": "Messages WhatsApp",
  "last_sync": "Dernière synchronisation",
  "never_synced": "Jamais",
  "sync_now": "Synchroniser Maintenant",
  "syncing": "Synchronisation...",
  "wait_minutes": "Attendez {minutes} min",
  "progress_fetched": "Messages récupérés",
  "progress_saved": "Enregistrés",
  "progress_media": "Médias",
  "confirm_title": "Confirmer la synchronisation",
  "confirm_password": "Entrez votre mot de passe pour démarrer la synchronisation",
  "cancel": "Annuler",
  "confirm": "Confirmer",
  "invalid_password": "Mot de passe invalide",
  "success": "Synchronisation terminée",
  "success_detail": "{count} messages synchronisés",
  "error": "Erreur de synchronisation",
  "errors_title": "Erreurs",
  "cancel_sync": "Annuler",
  "rate_limited": "Rate limited: wait {minutes} min",
  "already_running": "Synchronisation en cours",
  "network_error": "Erreur de connexion",
  "network_retry": "Réessai..."
}
```

---

## 5. Usage in Components

All UI strings must be wrapped with `t('ycloud_sync.key')`. Example:

```typescript
// Section header
<h3>{t('ycloud_sync.section_title')}</h3>

// Last sync timestamp
<span>{t('ycloud_sync.last_sync')}: {lastSyncAt || t('ycloud_sync.never_synced')}</span>

// Progress counters
<span>{t('ycloud_sync.progress_fetched')}: {progress.messages_fetched}</span>
<span>{t('ycloud_sync.progress_saved')}: {progress.messages_saved}</span>
<span>{t('ycloud_sync.progress_media')}: {progress.media_downloaded}</span>

// Error message (with interpolation)
<p>{t('ycloud_sync.wait_minutes', { minutes: remainingMinutes })}</p>
```

---

## 6. Verification Steps

After adding the keys, verify:

1. **No duplicate keys** – Ensure `ycloud_sync` object does not already exist in locale files.
2. **JSON syntax** – Validate each file with a JSON linter.
3. **Missing translations** – If a key is missing in a locale, the fallback will be English.
4. **Interpolation** – Ensure `{minutes}` and `{count}` placeholders are preserved correctly in all three languages.

---

## 7. Edge Cases

- **Empty strings** – If a translation key is missing, the system falls back to English.
- **Special characters** – Ensure proper escaping of quotes in JSON.
- **RTL languages** – Not supported in this project, but the structure should allow for future expansion.

---

**Next Phase:** Design (component mockups, layout adjustments).