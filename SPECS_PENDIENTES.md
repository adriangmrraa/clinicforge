# Auditoría ClinicForge — COMPLETADA

## Seguridad — 12/12 resueltos

- [x] Debug endpoints protegidos con auth
- [x] Token interno sin default hardcodeado
- [x] SSRF bloqueado en media proxy (IPs privadas, localhost, metadata)
- [x] Error messages genéricos (no exponer str(e) al cliente)
- [x] Validación de uploads (extensiones jpg/png/gif/webp/pdf + 10MB)
- [x] Path traversal protegido en documentos (pathlib.resolve)
- [x] Tenant isolation en /users y /users/pending
- [x] Defense-in-depth en Nova CRUD (frozenset + _safe_table_name)
- [x] Rate limiting en login (5/min) y register (3/min) via slowapi
- [x] Rate limiting en stats/dashboard (10/min)
- [x] IDOR protegido en delete de documentos (verificar paciente del tenant)
- [x] PII hasheado en audit logs (SHA-256, sin email ni IP)

## UX/UI — 10/10 resueltos

- [x] AdContextCard dark mode
- [x] AnamnesisPublicView placeholder contrast
- [x] AppointmentForm aria-label en close button
- [x] PatientsView columnas con i18n
- [x] ConfigView tabs flex-nowrap mobile
- [x] PatientsView loading spinner
- [x] DocumentGallery alt text contextual
- [x] i18n keys para NovaWidget (12 keys en es.json)
- [x] i18n keys para AnamnesisPanel (10 keys en es.json)
- [x] i18n keys para OnboardingGuide (keys incluidas en nova.*)

## Funcionalidad — 4/4 resueltos

- [x] Vista Lista mobile: muestra todos los turnos + auto-scroll a hoy
- [x] Imagen comprobante en Facturación via proxy URL autenticado
- [x] Excedente de seña: sobrescribe en vez de duplicar notas
- [x] Console.log de debug: limpiados
