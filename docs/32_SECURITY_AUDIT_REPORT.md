# SECURITY AUDIT REPORT: ClinicForge Sovereign OS
> **Versión del Protocolo:** Nexus v8.0 | **Última actualización:** 2026-02-21

Este reporte resume la auditoría de seguridad realizada sobre los componentes de Backend, Frontend y Base de Datos del proyecto CLINICASV1.0.

## 🛡️ Fortalezas Arquitectónicas

### 1. Sistema de Triple Capa + Capa 4 (Nexus v8.0)
El sistema implementa una defensa en profundidad para todas las rutas administrativas:
- **Capa 1: Infraestructura (X-Admin-Token)**: Filtra peticiones que no provengan del cliente oficial.
- **Capa 2: Identidad (JWT + HttpOnly Cookie)**: Valida la sesión y autenticidad del usuario (CEO, Prof, Sec). ✅ **Migrado a HttpOnly Cookie** (anti-XSS, Nexus v8.0).
- **Capa 3: Soberanía (Tenant Isolation)**: Resuelve el `tenant_id` en el servidor y filtra todas las consultas a la base de datos por clínica.
- **Capa 4: Multi-Sede CEO (v8.0)**: El CEO puede operar sobre múltiples sedes mediante `get_allowed_tenant_ids`. Lectura por `ANY(allowed_ids)`, mutaciones protegidas por guard 403.

### 2. Bóveda de Credenciales (Credential Vault)
- **Encryption-at-Rest**: Las llaves sensibles (Google, Chatwoot, Meta) se almacenan encriptadas con **Fernet** (AES-128).
- **Tenant Context**: Las credenciales son privadas por clínica; una fuga en el Tenant A no compromete al Tenant B.

### 3. Sanitización de Logs
- Se ha implementado un `SensitiveDataFilter` que detecta y redacta automáticamente tokens, contraseñas y claves de API antes de que lleguen a la consola o archivos de log.

### 4. Security Headers Middleware ✅ [Nexus v8.0]
- `HSTS`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `CSP` dinámico en todas las respuestas.

### 5. AI Guardrails ✅ [Nexus v8.0]
- `detect_prompt_injection` y `sanitize_input` invocados mandatoriamente antes de cualquier procesamiento de mensaje del Agente.
- `SafeHTML` con DOMPurify en el Frontend para neutralizar XSS en contenido de chat.

---

## 🚩 Hallazgos y Vulnerabilidades Identificadas

### 1. ~~Riesgo de XSS en Token Storage~~ [RESUELTO ✅]
**Descripción original**: El JWT y el `X-Admin-Token` se almacenaban en `localStorage`.
> **Resolución (Nexus v8.0):** JWT migrado a **HttpOnly Cookie**. El `X-Admin-Token` permanece en `localStorage` por diseño (token de infraestructura, no de sesión).

### 2. ~~Fragilidad en Patrones SQL~~ [RESUELTO ✅]
**Descripción original**: Algunas consultas en `marketing_service.py` usaban f-strings para inyectar intervalos temporales.
> **Resolución (Nexus v8.0):** `marketing_service.py` usa `timedelta` nativo en lugar de f-strings para intervalos. Todas las queries usan exclusivamente parámetros `$1`, `$2`, etc.

### 3. Fallback en Credenciales [MEDIO] [EN PROGRESO]
**Descripción**: `get_tenant_credential` cae en variables de entorno globales si no encuentra el valor en la base de datos.
**Impacto**: Facilita el desarrollo pero introduce ambigüedad en producción. Si una variable de entorno se filtra, afecta a todos los tenants que no tengan una llave específica.
**Recomendación**: Desactivar el fallback a `os.getenv` en entornos de producción para llaves críticas de proveedores (YCloud/Meta).

### 4. ~~Aislamiento Multi-Tenant en 5 Endpoints Críticos~~ [RESUELTO ✅]
**Descripción original**: Audit global (2026-02-21) detectó 5 endpoints sin filtro `tenant_id`: `search_patients_by_symptoms`, `get_patient_insurance_status`, `update_appointment_status`, `delete_appointment`, `update_professional`.
> **Resolución (Nexus v8.0 — 2026-02-21):** Se parcharon los 5 endpoints en `admin_routes.py`:
> - `GET /patients/search-semantic`: CEO = `ANY(allowed_ids)`, Staff = `tenant_id` único.
> - `GET /patients/{id}/insurance-status`: `AND tenant_id = $2` en WHERE.
> - `PUT/PATCH /appointments/{id}/status`: `AND tenant_id = $3` + guard 404 si `UPDATE 0`.
> - `DELETE /appointments/{id}`: SELECT y DELETE con `AND tenant_id = $2`.
> - `PUT /professionals/{id}`: Guard 403 con `allowed_ids` check antes de UPDATE.
> Spec de referencia: `orchestrator_service/specs/2026-02-21_nexus-v8-isolation-hardening.spec.md`

---

## 🚀 Plan de Hardening (Endurecimiento)

### ✅ Completado

- [x] Implementar `cookie-based auth` para el frontend (HttpOnly Cookie).
- [x] Eliminar f-strings de los servicios de Marketing y Dashboards (`timedelta` nativo).
- [x] Implementar Security Headers Middleware (`HSTS`, `CSP`, `XFO`, `XCTO`).
- [x] Implementar AI Guardrails (`detect_prompt_injection`, `SafeHTML` + DOMPurify).
- [x] Parchear 5 endpoints críticos con aislamiento `tenant_id` completo.

### ✅ Completado Recientemente (Febrero 2026)

1. **Backend**:
   - [x] **Console.log solo en DEV** - Implementado en commit `3af9a9a`: `console.log` solo se ejecuta en entorno de desarrollo, eliminado en producción
   - [x] **Limpieza automática de JWT en 401** - Implementado en commit `3af9a9a`: Cuando el backend devuelve 401, el frontend limpia automáticamente el JWT
   - [x] **Autenticación en Socket.IO** - Implementado en commit `3af9a9a`: Validación de JWT en conexiones Socket.IO
   - [x] **Fix loop infinito en agenda** - Implementado en commit `8f1c4a7`: Socket.IO accept-all + reconnect delay de 5 segundos
   - [x] **Guardian de rango en agenda** - Implementado en commit `18bc91b`: Fetch solo al navegar, no en re-renders internos

2. **Frontend**:
   - [x] **Persistent media secret** - Implementado en commit `c806283`: Secret persistente para media handling
   - [x] **Whitelabel fallbacks** - Implementado en commit `c806283`: Fallbacks robustos para configuración whitelabel
   - [x] **Socket.IO stability** - Implementado en commit `c806283`: Mejoras de estabilidad en conexiones Socket.IO

3. **Base de Datos**:
   - [x] **Actualización de Vite** - Implementado en commit `483f69a`: Vite actualizado a versión 5.4.21
   - [x] **Mejora persistencia de vista en agenda** - Implementado en commit `483f69a`: Persistencia mejorada de vistas de calendario

### ⏳ Pendiente

1. **Backend**:
   - [ ] Forzar error si `ADMIN_TOKEN` o `CREDENTIALS_FERNET_KEY` mantienen valores por defecto en producción.
   - [ ] Desactivar fallback `os.getenv` en producción para llaves de proveedores.

2. **Base de Datos**:
   - [ ] Completar `ReadAuditLogger` para tablas de pacientes/DNI (acceso a PII).
