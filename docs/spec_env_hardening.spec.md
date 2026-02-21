# Spec: Hardening de Variables de Entorno y Whitelabel Backend

**Version:** 1.0
**Fecha:** 2026-02-21
**Estado:** En implementacion
**Autor:** Agente Antigravity

## Objetivo

Eliminar 6 deficiencias menores detectadas en la auditoria: secretos con valores por defecto debiles,
branding "Dentalogic" hardcodeado en el backend y variables de entorno sin documentar. Deja el
proyecto completamente whitelabel y con defaults seguros o inexistentes.

## Cambios en Backend

- Archivos afectados:
  - orchestrator_service/core/auth.py
  - orchestrator_service/email_service.py
  - orchestrator_service/main.py
  - orchestrator_service/routes/chat_api.py
- Nuevo endpoint: No
- Cambio en logica del agente IA: No
- Nuevo parche de BD requerido: No

### Detalle de cambios

1. core/auth.py: ADMIN_TOKEN sin fallback debil. Si la variable no esta definida en produccion,
   el servidor registra un error critico al arrancar. El default "admin-secret-token" es eliminado.
   Se agrega una advertencia de startup visible en logs.

2. email_service.py: El pie de pagina del email de derivacion usaba "Dentalogic" hardcodeado.
   Se reemplaza con os.getenv("CLINIC_NAME", "Sistema de Gestion") para ser whitelabel.

3. main.py: Titulo del Swagger API usaba "Dentalogic API". Se reemplaza con
   os.getenv("CLINIC_NAME", "ClinicForge") + " API (Nexus v8.0 Hardened)".

4. routes/chat_api.py: MEDIA_PROXY_SECRET tenia default predecible "dentalogic-media-proxy-secret-2026".
   Se reemplaza con un default generado dinamicamente (uuid4) con advertencia de seguridad en logs.

## Cambios en Base de Datos

No aplica.

## Cambios en Frontend

- Vista nueva o modificada: No
- Nuevas claves i18n requeridas: No
- Socket.IO events nuevos: No

## Cambios en Documentacion

- docs/02_environment_variables.md: Agregar seccion "Meta Ads Integration", ampliar seccion
  "Handoff", agregar variables faltantes: NOTIFICATIONS_EMAIL, MEDIA_PROXY_SECRET, META_APP_ID,
  META_APP_SECRET, META_REDIRECT_URI, META_ADS_TOKEN, META_AD_ACCOUNT_ID, META_GRAPH_API_VERSION,
  META_API_TIMEOUT, SMTP_SENDER, API_VERSION, WHATSAPP_SERVICE_PORT, CLINIC_HOURS_START,
  CLINIC_HOURS_END, ENVIRONMENT.

## Criterios de Aceptacion

- [ ] ADMIN_TOKEN sin fallback: si no esta definido, logs muestran CRITICAL al iniciar
- [ ] Email de derivacion no contiene la palabra "Dentalogic" en ningun lugar del HTML
- [ ] Titulo del Swagger es dinamico (usa CLINIC_NAME env var)
- [ ] MEDIA_PROXY_SECRET no tiene valor por defecto predecible fijo
- [ ] docs/02_environment_variables.md documenta todas las variables detectadas en codigo
- [ ] El .env de ejemplo al final del doc incluye las nuevas variables

## Riesgos identificados

- ADMIN_TOKEN sin fallback: si un operador no define la variable, el servidor ARRANCA pero rechaza
  todas las peticiones admin (falla en runtime, no en startup). Mitigacion: log CRITICAL claro al inicio.
- MEDIA_PROXY_SECRET dinamico: si el servidor reinicia sin la variable, cambia el secreto y las URLs
  firmadas existentes se invalidan. Esto es aceptable (TTL de 1h) y preferible al secreto predecible.
