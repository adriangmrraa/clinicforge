# Histórico de Problemas y Soluciones

Este documento registra problemas encontrados y sus soluciones para referencia futura.

## Startup, Routing y Persistencia (v4)

**Problema (2026-02-05):**
- **401 Unauthorized**: Frontend fallaba al conectar con Orchestrator por falta de token en build.
- **404 Not Found**: YCloud enviaba webhooks a `/webhook` pero el servicio esperaba `/webhook/ycloud`.
- **422 Unprocessable**: Mismatch de nombres en JSON entre WhatsApp de entrada (`from_number`/`text`) y Orchestrator (`phone`/`message`).
- **500 Internal Error (Bcrypt)**: `passlib` fallaba al chocar con `bcrypt 4.x` en Linux. Esto se manifestaba como un error de CORS en el navegador porque el servidor moría antes de inyectar los headers.
- **Pantalla en Blanco (Navigation)**: Al navegar a `/agenda` o `/pacientes`, la aplicación desaparecía.

**Solución Aplicada:**
- **Frontend (CORS/Auth)**: Se inyectó `VITE_ADMIN_TOKEN` en el Dockerfile y se agregó un `@app.exception_handler(Exception)` global en `main.py` para devolver JSON siempre, asegurando que los headers de CORS estén presentes incluso en errores 500.
- **Bcrypt Fix**: Se fijó `bcrypt==3.2.0` en `requirements.txt` y se agregó truncado de 72 bytes en las contraseñas para evitar el límite físico de la librería.
- **Navigation Fix**: Se cambió `path="/"` por `path="/*"` en `App.tsx` para permitir el matching de rutas anidadas en React Router 6.
- **Maintenance Robot (db.py)**: 
  - Se implementó un **Smart SQL Splitter** que divide el schema por `;` (respetando bloques `$$`).
  - Se creó un sistema de **Evolución por Parches** con auto-activación de CEO (Omega Prime).

**Estado:**
- ✅ Completamente estabilizado en v7.6 "Sovereign Platinum".

---

## Calendario e IA: "La IA no puede ver disponibilidad" (v7.6+)

**Problema:** El asistente por WhatsApp responde que no puede consultar disponibilidad o que no hay huecos, cuando la clínica espera usar Google Calendar o tiene turnos en la agenda.

**Causas típicas y qué revisar:**

1. **Clínica con `calendar_provider = 'local'`**  
   Si en BD la sede tiene `tenants.config.calendar_provider = 'local'`, la IA **no** llama a Google; solo usa la tabla `appointments` y horarios de profesionales. Si no hay turnos cargados o los profesionales no tienen `working_hours` configurados, puede devolver "no hay huecos".  
   **Solución:** Confirmar en Gestión de Clínicas que la sede tenga guardado **Google** como proveedor de calendario si se quiere usar GCal.

2. **`calendar_provider` no se persiste al guardar**  
   Si al guardar en el modal de sedes el valor Google no se escribe en `tenants.config`, la clínica sigue en local.  
   **Solución:** Revisar que el frontend/backend persistan correctamente `calendar_provider` al actualizar la sede.

3. **Clínica en Google pero profesionales sin `google_calendar_id`**  
   Para cada profesional con `calendar_provider == 'google'`, la tool `check_availability` necesita su `google_calendar_id`. Si **ningún** profesional del tenant tiene ese ID, no se consulta ningún calendario de Google.  
   **Solución:** En Perfil o en la gestión de profesionales, asignar a cada profesional el ID del calendario de Google creado en la cuenta de la clínica.

4. **Credenciales de Google**  
   Si `GOOGLE_CREDENTIALS` (o la integración connect-sovereign con Auth0) no está definida o es inválida, `gcal_service` no puede llamar a la API.  
   **Solución:** Verificar variables de entorno y/o flujo connect-sovereign en docs/03_deployment_guide.md y docs/API_REFERENCE.md (POST /admin/calendar/connect-sovereign).

5. **Excepciones en `check_availability`**  
   Si falla el parseo de fecha, la consulta a BD o la llamada a GCal, la tool devuelve un mensaje genérico y la IA repite que no pudo consultar.  
   **Solución:** Revisar logs del orchestrator en el momento de la petición del paciente para ver el traceback.

**Resumen:** Para que la IA "vea" disponibilidad con Google hace falta: (a) `calendar_provider = 'google'` persistido para la sede; (b) cada profesional con `google_calendar_id`; (c) credenciales correctas; (d) que no falle parseo ni consulta.

---

*Histórico de Problemas y Soluciones Nexus v3 © 2026*
