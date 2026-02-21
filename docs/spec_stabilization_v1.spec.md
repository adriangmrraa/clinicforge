# Spec: Estabilización y Seguridad — Sprint Hardening v1.0

**Versión:** 1.0  
**Fecha:** 2026-02-21  
**Estado:** En implementación  
**Autor:** Agente Antigravity  
**Origen:** Resultado de `/audit` — Detección de drift, deuda técnica y vulnerabilidades reales

---

## Objetivo

Eliminar vulnerabilidades reales, deuda técnica activa y artefactos legacy detectados en la auditoría integral del proyecto. Este sprint **no agrega features**: corrige código que está en producción con comportamiento incorrecto, inseguro o inconsistente con la arquitectura documentada.

Usuarios afectados: todos los roles (CEO, profesional, secretaria) en todas las sedes.

---

## Hallazgos Identificados (Base de Esta Spec)

### 🔴 CRÍTICO — Debe resolverse antes de cualquier deploy

#### C-01: Endpoints `/credentials` duplicados — la versión insegura gana siempre

**Archivo:** `orchestrator_service/admin_routes.py`  
**Evidencia:**
- **Versión antigua** (líneas 411–498): define `GET /credentials`, `POST /credentials`, `PUT /credentials/{cred_id}`, `DELETE /credentials/{cred_id}`. Auth vía `Depends(verify_admin_token)` en firma + check manual `role != 'ceo'`. Sin filtro multi-tenant. No soporta que secretarias gestionen credenciales de su propio tenant.
- **Versión nueva** (líneas 1134–1262): define `GET /credentials`, `POST /credentials`, `DELETE /credentials/{id}`. Auth en decorador + firma. Filtra por `allowed_ids`, soporta scope `global`/`tenant`, upsert inteligente, logs de auditoría.
- **Comportamiento de FastAPI:** registra la **primera ruta coincidente**. La versión nueva **nunca se ejecuta**. El comportamiento observable es el de la versión antigua, que no cumple la Spec de Credenciales actual.

**Impacto:** Secretarias y admins no-CEO reciben HTTP 403 al intentar acceder a credenciales de su propio tenant, aunque la lógica de negocio lo permite. La versión más segura (con filtros multi-tenant y audit log) es letra muerta.

**Corrección:** Eliminar el bloque completo de líneas 411–498. Mantener exclusivamente el bloque de líneas 1134–1308 (versión nueva con `GET`, `POST`, `DELETE`). Agregar endpoint `PUT /credentials/{id}` faltante en la versión nueva.

---

#### C-02: `ENCRYPTION_KEY` con fallback hardcodeado en `utils.py`

**Archivo:** `orchestrator_service/utils.py`  
**Evidencia:** Línea 6:
```python
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "agente-js-secret-key-2024")
```
**Impacto:** Si `ENCRYPTION_KEY` no está configurada en producción, las contraseñas de profesionales se "encriptan" con una clave pública y conocida (`agente-js-secret-key-2024`). Además, el algoritmo es XOR+Base64, que **no es cifrado seguro** (reversible sin clave, solo ofuscación). Debería usar Fernet (ya disponible con `CREDENTIALS_FERNET_KEY`).

**Corrección:** 
1. Eliminar el fallback hardcodeado. Si `ENCRYPTION_KEY` no está presente, lanzar error en startup con mensaje claro.
2. Documentar que `encrypt_password`/`decrypt_password` es cifrado legacy de contraseñas de usuarios (diferente a `encrypt_value`/`decrypt_value` de Fernet para credenciales). 
3. Agregar `ENCRYPTION_KEY` a `docs/02_environment_variables.md` marcada como `✅ Requerida`.

---

### 🟡 MENOR — Resolver en este sprint

#### M-01: `LandingView.tsx` sin i18n y con datos hardcodeados de un tenant

**Archivo:** `frontend_react/src/views/LandingView.tsx`  
**Evidencia:** 
- Sin `useTranslation()`. Todo el texto en español hardcodeado.  
- Líneas 5–7: número de WhatsApp (`5493435256815`) y mensaje (`"turnos para limpieza dental"`) hardcodeados con datos de un tenant específico.
- La vista es pública (`/demo` en `App.tsx`, sin `ProtectedRoute`).

**Impacto:** La página demo/landing no puede servir clientes en inglés o francés (viola el requerimiento de i18n). El número de WhatsApp hardcodeado rompe el modelo multi-tenant si la plataforma se muestra a leads de otras clínicas.

**Corrección:**
1. Agregar `useTranslation()` y extraer todos los textos a `i18n/es.json`, `en.json`, `fr.json`.
2. Reemplazar `WHATSAPP_NUMBER` por una variable de entorno del frontend (`VITE_DEMO_WHATSAPP_NUMBER`) o leer desde configuración pública del sistema.

---

#### M-02: `docs/02_environment_variables.md` desactualizado (referencias legacy e-commerce)

**Archivo:** `docs/02_environment_variables.md`  
**Evidencia:** El documento referencia variables de un proyecto anterior:
- `TIENDANUBE_STORE_ID`, `TIENDANUBE_ACCESS_TOKEN` — No existen en el orquestador actual
- `SHIPPING_PARTNERS`, `STORE_CATALOG_KNOWLEDGE` — Variables de e-commerce sin uso en clínica dental
- `ENCRYPTION_KEY` — No documentada aunque se usa en `utils.py`
- `GOOGLE_CALENDAR_CREDENTIALS_JSON`, `GOOGLE_CALENDAR_TOKEN_JSON` — No están en la tabla (usadas en `google_calendar_service.py`)

**Corrección:** Reescribir sección por sección: eliminar variables legacy, agregar variables reales faltantes, marcar obsoletas claramente.

---

### 🔵 DEUDA TÉCNICA — Resolver antes del lanzamiento público

#### D-01: Vistas legacy sin rutas registradas en `App.tsx`

**Archivos en `frontend_react/src/views/`:**
| Archivo | En `App.tsx` | Estado |
|---|---|---|
| `Tools.tsx` | ❌ No | Legacy — sin funcionalidad activa |
| `Stores.tsx` | ❌ No | Legacy — referencia a Tienda Nube |
| `Setup.tsx` | ❌ No | Legacy — reemplazado por `ConfigView.tsx` |
| `Logs.tsx` | ❌ No | Legacy — sin datos ni endpoint relacionado |
| `Dashboard.tsx` | ❌ No | Duplicado de `DashboardView.tsx` |
| `ProfessionalsView.tsx` | ❌ No | App.tsx redirige `/profesionales` → `/aprobaciones` |

**Impacto:** Archivos confusos para el agente IA (puede creer que están activos cuando no lo están). Aumentan el bundle innecesariamente.

**Corrección:** Eliminar los 6 archivos. Verificar que ningún componente activo los importe antes de eliminar.

---

#### D-02: `result.txt` en el repositorio

**Archivo:** `result.txt` (raíz del proyecto)  
**Evidencia:** Archivo de debug/prueba que contiene output de una ejecución manual. No debería estar commiteado.

**Corrección:** Eliminar el archivo. Agregar `result.txt` a `.gitignore`.

---

#### D-03: `PUT /credentials/{id}` ausente en la versión nueva

**Contexto:** Al resolver C-01, se elimina el `PUT` de la versión antigua (línea 461). La versión nueva solo tiene `GET`, `POST` (upsert por `id`) y `DELETE`. Verificar que el frontend usa `POST` para actualizar (enviando `id` en el payload) y no `PUT`. Si usa `PUT`, crear el endpoint faltante en la versión nueva.

---

## Cambios en Backend

**Archivo afectado:** `orchestrator_service/admin_routes.py`
- **Eliminar:** bloque completo líneas 411–498 (endpoints `/credentials` versión antigua)
- **Verificar:** bloque líneas 1134–1308 (versión nueva) queda como único punto de verdad
- **Agregar:** `PUT /credentials/{id}` en la versión nueva si el frontend lo usa

**Archivo afectado:** `orchestrator_service/utils.py`
- **Modificar:** línea 6 — eliminar fallback hardcodeado de `ENCRYPTION_KEY`
- **Agregar:** validación en startup que levante `ValueError` si `ENCRYPTION_KEY` es `None`

**Nuevo parche de BD requerido:** No (los cambios son de lógica, no de esquema).

---

## Cambios en Base de Datos

Ninguno. Esta spec no altera el esquema.

---

## Cambios en Frontend

**Archivo afectado:** `frontend_react/src/views/LandingView.tsx`
- Agregar `useTranslation()` hook
- Extraer todos los textos a los archivos de traducción
- Reemplazar constantes `WHATSAPP_NUMBER` y `WHATSAPP_PREDEFINED_MESSAGE` con valores de config o env

**Archivos a eliminar:**
- `frontend_react/src/views/Tools.tsx`
- `frontend_react/src/views/Stores.tsx`
- `frontend_react/src/views/Setup.tsx`
- `frontend_react/src/views/Logs.tsx`
- `frontend_react/src/views/Dashboard.tsx`
- `frontend_react/src/views/ProfessionalsView.tsx`

**Nuevas claves i18n requeridas:** Sí — todos los textos de `LandingView.tsx`  
**Socket.IO events nuevos:** No

---

## Cambios en Documentación

**Archivo afectado:** `docs/02_environment_variables.md`
- Eliminar: referencias a Tienda Nube, Shipping Partners y variables e-commerce legacy
- Agregar: `ENCRYPTION_KEY`, `GOOGLE_CALENDAR_CREDENTIALS_JSON`, `GOOGLE_CALENDAR_TOKEN_JSON`
- Marcar como `[LEGACY/NO USAR]` variables que permanezcan por compatibilidad

**Archivo a crear:** entrada en `.gitignore` para `result.txt`

---

## Criterios de Aceptación

### C-01 (Credentials duplicadas)
- [ ] `GET /admin/credentials` ejecuta la lógica de la versión nueva (verificable: una secretaria puede listar credenciales de su tenant sin recibir 403)
- [ ] `POST /admin/credentials` ejecuta la versión nueva (verificable: upsert funciona con payload `{id: N, ...}`)
- [ ] No existen rutas duplicadas en `admin_routes.py` para `/credentials` (verificable: `grep "@router.*credentials"` retorna máximo 3 resultados: GET, POST, DELETE)
- [ ] Los logs de creación/actualización incluyen `user_data.email` (trazabilidad)

### C-02 (ENCRYPTION_KEY)
- [ ] `utils.py` no contiene el string literal `agente-js-secret-key-2024`
- [ ] Si `ENCRYPTION_KEY` no está en el entorno, el servicio lanza error descriptivo en startup (no silencioso)
- [ ] `docs/02_environment_variables.md` contiene `ENCRYPTION_KEY` marcada como `✅ Requerida`

### M-01 (LandingView i18n)
- [ ] `LandingView.tsx` importa y usa `useTranslation()`
- [ ] No hay strings de texto directos en español en el JSX de `LandingView.tsx`
- [ ] `WHATSAPP_NUMBER` no está hardcodeada con el número `5493435256815`
- [ ] La vista cambia de idioma al seleccionar inglés o francés desde el selector de idioma

### M-02 (Env vars doc)
- [ ] `docs/02_environment_variables.md` no menciona `TIENDANUBE_STORE_ID` ni `SHIPPING_PARTNERS` como variables activas
- [ ] Las variables `ENCRYPTION_KEY` y `GOOGLE_CALENDAR_CREDENTIALS_JSON` tienen entrada documentada

### D-01 (Vistas legacy)
- [ ] Los 6 archivos legacy no existen en `frontend_react/src/views/`
- [ ] El build de React (`npm run build`) completa sin errores después de eliminarlos

### D-02 (result.txt)
- [ ] `result.txt` no existe en el repositorio
- [ ] `.gitignore` contiene entrada `result.txt`

---

## Orden de Implementación Recomendado

```
1. D-02     → Eliminar result.txt (trivial, 2 min)
2. D-01     → Eliminar vistas legacy (verificar imports primero)
3. C-01     → Eliminar endpoints /credentials duplicados (riesgo medio)
4. C-02     → Hardening de ENCRYPTION_KEY (riesgo bajo)
5. M-02     → Actualizar docs/02_environment_variables.md
6. M-01     → i18n en LandingView.tsx (más tiempo, menor urgencia)
```

---

## Riesgos Identificados

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| El frontend usa `PUT /credentials/{cred_id}` (con el ID en la URL) en lugar de `POST` con `id` en body | Media | Alto — formulario de credenciales se rompe | Verificar en `ConfigView.tsx` qué método HTTP usa antes de eliminar el `PUT` de la versión antigua |
| `LandingView.tsx` usa claves i18n que no existen en `en.json` / `fr.json` | Alta | Medio — texto en blanco | Crear todas las claves en los 3 idiomas antes de hacer el commit |
| Alguna vista legacy es importada por un componente activo | Baja | Medio — build failure | Ejecutar `grep -r "Tools\|Stores\|Setup\|Logs" src/` antes de eliminar |
| `ENCRYPTION_KEY` no está configurada en el `.env` de desarrollo | Alta | Alto — crash en startup | Agregar `ENCRYPTION_KEY` al `.env.example` y al README antes de subir el cambio |

---

## Prerequisito

Este spec no requiere `/advisor` previo ya que los hallazgos provienen directamente del `/audit`. Se puede pasar directamente a `/plan` → `/implement`.

**Siguiente paso:** `/plan`
