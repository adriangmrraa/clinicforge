# Specs Pendientes — ClinicForge

## Estado: Lo que ya se arregló (commit 723d776)

### Seguridad (6 fixes aplicados)
- [x] Debug endpoints protegidos con auth
- [x] Token interno sin default hardcodeado
- [x] SSRF bloqueado en media proxy
- [x] Error messages genéricos (no exponer str(e))
- [x] Validación de uploads (extensiones + tamaño)
- [x] Path traversal protegido en documentos

### UX (4 fixes aplicados)
- [x] AdContextCard dark mode
- [x] AnamnesisPublicView placeholder contrast
- [x] AppointmentForm aria-label en close button
- [x] PatientsView columnas con i18n

---

## Pendientes de Seguridad

### SEC-1: Tenant isolation en listado de usuarios
**Archivo**: `admin_routes.py:316-335`
**Problema**: GET /users y /users/pending no filtran por tenant_id. Un CEO ve usuarios de TODAS las clínicas.
**Fix**: Agregar `WHERE tenant_id = $1` o filtrar por las clínicas del usuario.
**Prioridad**: HIGH

### SEC-2: Rate limiting en autenticación
**Archivo**: `auth_routes.py`
**Problema**: Sin límite de intentos de login. Brute force posible.
**Fix**: Instalar `slowapi`. Limitar a 5 intentos/15min por IP en `/auth/login`.
**Prioridad**: MEDIUM

### SEC-3: Rate limiting en endpoints costosos
**Archivos**: `admin_routes.py` (stats, dashboard, analytics)
**Problema**: Queries pesadas sin rate limit → DoS posible.
**Fix**: Limitar a 10 req/min en `/admin/stats/*`, `/admin/dashboard/*`. Cachear resultados 5 min.
**Prioridad**: MEDIUM

### SEC-4: IDOR en delete de documentos
**Archivo**: `admin_routes.py:3217`
**Problema**: Solo verifica tenant_id pero no si el usuario tiene acceso al paciente.
**Fix**: Verificar que el profesional está asignado al paciente, o que es CEO/secretary.
**Prioridad**: MEDIUM

### SEC-5: PII en logs
**Archivo**: `core/auth.py:147` y múltiples
**Problema**: Patient IDs, emails, teléfonos en logs sin cifrar.
**Fix**: Hashear IDs en logs: `hash(patient_id)`. Política de retención 90 días.
**Prioridad**: MEDIUM

### SEC-6: SQL injection defensiva en Nova CRUD
**Archivo**: `nova_tools.py:3178+`
**Problema**: Tablas dinámicas en queries. Whitelist existe pero defense-in-depth falta.
**Fix**: Usar mapping dict `ALLOWED_TABLES_MAP = {"patients": "patients", ...}` y acceder por key, no por string directo.
**Prioridad**: LOW (whitelist ya protege, pero defense-in-depth es buena práctica)

---

## Pendientes de UX/UI

### UX-1: NovaWidget — texto hardcodeado en español
**Archivo**: `components/NovaWidget.tsx`
**Problema**: 50+ strings en español sin usar `t()`. Si se cambia el idioma, Nova queda en español.
**Instancias**: "Turnos hoy", "Pacientes totales", "Pagos pendientes", "Continuar configuracion", etc.
**Fix**: Crear keys `nova.appointments_today`, `nova.total_patients`, etc. en es/en/fr.json.
**Prioridad**: HIGH

### UX-2: OnboardingGuide — texto hardcodeado
**Archivo**: `components/OnboardingGuide.tsx`
**Problema**: Todas las guías (15+ páginas) están en español hardcodeado.
**Fix**: Mover a i18n o al menos a un archivo de constantes separado.
**Prioridad**: MEDIUM

### UX-3: AnamnesisPanel — labels hardcodeados
**Archivo**: `components/AnamnesisPanel.tsx`
**Problema**: Labels como "Medicación habitual", "Cirugías previas" hardcodeados.
**Fix**: Crear keys i18n `anamnesis.habitual_medication`, etc.
**Prioridad**: MEDIUM

### UX-4: Tablas sin scroll horizontal en mobile
**Archivos**: `PatientsView.tsx`, `DashboardView.tsx`
**Problema**: Tablas con columnas fijas se cortan en pantallas chicas.
**Fix**: Envolver tablas en `<div className="overflow-x-auto">`.
**Prioridad**: MEDIUM

### UX-5: ConfigView tabs overflow en mobile
**Archivo**: `views/ConfigView.tsx`
**Problema**: 7 tabs (General, YCloud, Chatwoot, Others, Maintenance, Leads, Meta) no caben en mobile.
**Fix**: Agregar `overflow-x-auto` al contenedor de tabs.
**Prioridad**: MEDIUM

### UX-6: Loading states sin spinner
**Archivos**: `PatientsView.tsx`, `ClinicsView.tsx`, `NovaWidget.tsx`
**Problema**: Loading muestra solo texto, sin spinner/skeleton.
**Fix**: Agregar `<Loader2 className="animate-spin" />` o skeleton loader.
**Prioridad**: LOW

### UX-7: Touch targets menores a 44px
**Archivo**: `components/Odontogram.tsx`
**Problema**: Botones de dientes son 40x40px en mobile, menor al mínimo recomendado de 44x44px.
**Fix**: Cambiar a `min-w-[44px] min-h-[44px]`.
**Prioridad**: LOW

### UX-8: Imágenes sin alt text contextual
**Archivos**: `chat/MessageMedia.tsx`, `DocumentGallery.tsx`
**Problema**: `alt="attachment"` — demasiado genérico.
**Fix**: `alt="Archivo adjunto del paciente"` o `alt={document.filename}`.
**Prioridad**: LOW

---

## Pendientes de Funcionalidad (de sesiones anteriores)

### FUNC-1: Vista Lista en mobile — scroll libre
**Archivo**: `components/MobileAgenda.tsx`
**Problema**: La vista Lista filtra solo por mes. Debería mostrar todos los turnos con scroll libre y auto-scroll a HOY.
**Fix**: Cambiar filtro de lista a mostrar todos los eventos. Agregar `scrollIntoView` al grupo de hoy. Cada vista mantiene su propia fecha.
**Prioridad**: HIGH

### FUNC-2: Comprobante de pago — imagen visible en Facturación
**Archivo**: `components/AppointmentForm.tsx`
**Problema**: La imagen del comprobante usa ruta del server (`/app/uploads/...`) que no es accesible desde el browser.
**Fix**: El `receipt_file_path` debe convertirse a URL pública via el proxy de documentos: `/admin/patients/{id}/documents/{doc_id}/proxy`.
**Prioridad**: MEDIUM

### FUNC-3: Excedente de seña — lógica de acumulado
**Archivo**: `main.py` (verify_payment_receipt)
**Problema**: El excedente se calcula mal cuando hay múltiples verificaciones. "[Excedente seña: $20000] [Excedente seña: $20000]" duplicado en notas.
**Fix**: Al guardar billing_notes de excedente, verificar si ya existe una nota de excedente y reemplazarla en vez de concatenar.
**Prioridad**: MEDIUM

### FUNC-4: Console.log de debug en AppointmentForm
**Archivo**: `components/AppointmentForm.tsx`
**Problema**: Hay console.log temporales de debug que deben removerse.
**Fix**: Buscar y eliminar `console.log('🧾` lines.
**Prioridad**: LOW
