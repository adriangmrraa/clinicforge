# Specs — ClinicForge Audit Results

## Seguridad — TODO RESUELTO

- [x] Debug endpoints protegidos con auth (commit 723d776)
- [x] Token interno sin default hardcodeado (commit 723d776)
- [x] SSRF bloqueado en media proxy (commit 723d776)
- [x] Error messages genéricos — no exponer str(e) (commit 723d776)
- [x] Validación de uploads — extensiones + 10MB (commit 723d776)
- [x] Path traversal protegido en documentos (commit 723d776)
- [x] SEC-1: Tenant isolation en /users y /users/pending (commit 83c097c)
- [x] SEC-6: Defense-in-depth en Nova CRUD — frozenset + _safe_table_name (commit 83c097c)

### Pendientes menores (no críticos)
- [ ] SEC-2: Rate limiting en login (slowapi) — requiere instalar dependencia
- [ ] SEC-3: Rate limiting en endpoints costosos — requiere slowapi
- [ ] SEC-4: IDOR en delete documentos — verificar permisos por rol
- [ ] SEC-5: PII en logs — hashear patient_id en logs de auditoría

## UX/UI — TODO RESUELTO

- [x] AdContextCard dark mode (commit 723d776)
- [x] AnamnesisPublicView placeholder contrast (commit 723d776)
- [x] AppointmentForm aria-label en close button (commit 723d776)
- [x] PatientsView columnas con i18n (commit 723d776)
- [x] UX-5: ConfigView tabs flex-nowrap mobile (commit 83c097c)
- [x] UX-6: PatientsView loading spinner (commit 83c097c)
- [x] UX-7/UX-8: DocumentGallery alt text (commit 83c097c)

### Pendientes menores
- [ ] UX-1: NovaWidget — 50+ strings hardcodeados en español sin i18n
- [ ] UX-2: OnboardingGuide — guías hardcodeadas sin i18n
- [ ] UX-3: AnamnesisPanel — labels hardcodeados sin i18n

## Funcionalidad — TODO RESUELTO

- [x] FUNC-1: Vista Lista mobile — muestra todos los turnos + auto-scroll a hoy (commit 83c097c)
- [x] FUNC-3: Excedente de seña — sobrescribe en vez de concatenar duplicados (commit 83c097c)
- [x] FUNC-4: Console.log de debug — ya no existían en el código

### Pendientes menores
- [ ] FUNC-2: Imagen del comprobante en Facturación — ruta del server no accesible desde browser (necesita proxy URL)
