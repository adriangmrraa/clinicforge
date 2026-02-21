# Auditoría de seguridad según OWASP Top 10 (referencia 2025)

Este documento mapea el estado de seguridad del proyecto Dentalogic frente al estándar **OWASP Top 10** (edición 2025) y describe las medidas aplicadas o recomendadas. No sustituye una auditoría externa; sirve como línea base y checklist interno.

**Referencia:** [OWASP Top 10:2025](https://owasp.org/Top10/2025/)

---

## Cómo gestiona la seguridad el backend (lenguaje natural)

Esta sección explica con palabras sencillas cómo el backend protege las distintas páginas y acciones.

### Qué es público y qué es privado

- **Público (cualquiera, sin estar logueado):**  
  - **Registro** (`POST /auth/register`): crear cuenta; el usuario queda en estado "pendiente" hasta que un CEO lo apruebe.  
  - **Login** (`POST /auth/login`): enviar email y contraseña; si son correctos, el backend devuelve un **token JWT** y los datos del usuario. Ese token es la "llave" para todo lo demás.  
  - **Lista de clínicas** (`GET /auth/clinics`): solo devuelve id y nombre de sedes, para el selector del formulario de registro. No expone datos sensibles.  

- **Todo lo que hace la plataforma (agenda, pacientes, chats, sedes, configuración, etc.)** está bajo rutas que empiezan por `/admin/...`. Esas rutas **no son públicas**: el backend exige que cada petición traiga dos cosas: **identidad** (quién eres) y **autorización de infraestructura** (que la petición viene de la app legítima).

### Cómo te identificas: el token JWT

Cuando inicias sesión con email y contraseña, el backend comprueba la contraseña (hash en base de datos) y, si es correcta, genera un **JWT** (JSON Web Token). Ese token contiene, de forma firmada, tu **user_id**, tu **rol** (CEO, secretaria o profesional) y tu **email**. El frontend guarda ese token y lo envía en **todas** las peticiones a la API dentro del header `Authorization: Bearer <token>`.

Así, en cada acción el backend **sabe quién eres** sin tener que volver a pedir la contraseña. Si el token está caducado o es inválido, el backend responde 401 y el frontend te manda al login.

### La doble comprobación en cada acción admin

Para **cualquier** ruta bajo `/admin/...`, el backend no se fía solo del JWT. Usa una función llamada `verify_admin_token` que hace **dos comprobaciones**:

1. **Header `X-Admin-Token`:** debe coincidir con un valor secreto que está solo en el servidor (y en la app que hace las peticiones). Así se evita que alguien con un JWT robado pueda llamar a la API desde otro sitio (por ejemplo un script suelto) si no conoce ese segundo secreto.  
2. **JWT:** se valida que el token sea correcto, no esté caducado y que el **rol** del usuario sea uno de los permitidos (CEO, secretaria o profesional). Si el rol no está en esa lista, se responde 403 (sin permisos).

Solo si **ambas** comprobaciones pasan, la petición sigue. Por eso se habla de "triple capa" o doble factor en administración: identidad (JWT) + autorización de infraestructura (X-Admin-Token) + rol válido.

### Cómo sabe el backend "en qué clínica" estás

Muchas acciones dependen de la **sede** (clínica): ver pacientes, ver chats, ver agenda, etc. El backend no usa un "tenant_id" que venga del frontend sin más, porque podría ser manipulado. En su lugar:

- Para un **profesional**, consulta en base de datos a qué `tenant_id` está vinculado (tabla `professionals`). Ese es su "tenant resuelto": solo puede ver datos de esa sede.  
- Para una **secretaria**, igual: se resuelve su sede desde `professionals`.  
- Para el **CEO**, puede ver todas las sedes; la lista de "tenant_ids permitidos" son todos los que existen. En endpoints que piden "una" sede (por ejemplo dashboard o configuración), se usa un tenant por defecto (por ejemplo la primera clínica) si no se elige otra.

Esa resolución se hace con funciones como `get_resolved_tenant_id` y `get_allowed_tenant_ids`: siempre basadas en el usuario que sacamos del JWT y en la base de datos, nunca en un número que envíe el cliente sin validar.

### Cómo se protegen los datos de cada clínica (multi-tenant)

En todas las consultas que tocan pacientes, turnos, chats, profesionales, etc., el backend **filtra por `tenant_id`**. Es la "regla de soberanía": una clínica no puede ver ni modificar datos de otra. Por tanto, en cada acción:

- Se sabe **quién** eres (JWT).  
- Se sabe **qué sedes** te están permitidas (resolución por rol y por tabla `professionals`).  
- Todas las lecturas y escrituras usan ese `tenant_id` (o lista de tenant_ids para CEO) en la cláusula WHERE, de forma que solo ves y modificas datos de "tu" clínica o de las que te corresponden.

Algunas rutas además comprueban explícitamente el **rol**: por ejemplo, crear o borrar sedes, ver analíticas globales o cambiar configuración de idioma solo lo puede hacer un CEO. Si un profesional o secretaria intenta acceder, el backend responde 403.

### Resumen por tipo de acción

- **Login / registro:** Público; el registro deja al usuario pendiente; el login devuelve JWT.  
- **Cualquier cosa en `/admin/...`:** Exige JWT + X-Admin-Token y rol permitido; luego resuelve tenant y aplica filtro por sede en todos los datos.  
- **Chat desde WhatsApp (paciente):** Es otro flujo: el mensaje llega por webhook desde el proveedor (YCloud). El backend identifica la sede por el **número de teléfono** al que el paciente escribió y procesa el mensaje en nombre de esa sede; aquí no hay JWT de usuario de la plataforma, sino validación del webhook y aislamiento por tenant según el número.

En conjunto: la seguridad se gestiona **por capas** (identidad, infraestructura, rol, sede) y **por regla fija** (siempre filtrar por `tenant_id` en los datos). Así se protegen todas las páginas y acciones que dependen del backend.

---

## JWT "expuesto" y por qué no basta para hacerse pasar por el usuario

### Qué observó Facu

El **JWT** (el token que devuelve el login) es visible en el cliente: se envía en cada petición en el header `Authorization: Bearer <token>`. Cualquiera con acceso al navegador (pestaña de red, almacenamiento donde se guarde el token, etc.) puede **copiar ese token**. Si solo eso bastara para llamar a la API, quien lo copie podría hacerse pasar por ese usuario (en el ejemplo, el CEO).

Eso es cierto: **el JWT está "expuesto" en el sentido de que el cliente lo tiene y se puede extraer**. Es inherente a cómo funcionan los JWTs en aplicaciones web.

### Qué hace el backend para que el JWT solo no alcance

En este proyecto las rutas **admin** no aceptan solo el JWT. Exigen **además** el header **`X-Admin-Token`**, que debe coincidir con un secreto del servidor (y de la app legítima). Ese valor no lo ve el usuario en la interfaz; lo inyecta el frontend desde su configuración (variable de entorno en build). Por tanto:

- Si alguien **solo** roba el JWT y llama a `/admin/...` desde su propia consola o script **sin** enviar el `X-Admin-Token` correcto, el backend responde **401 Unauthorized**.
- Los logs que compartió Facu muestran exactamente eso: tras un login correcto (POST `/auth/login` 200), las peticiones a `GET /admin/treatment-types`, `POST /admin/patients`, `GET /admin/chat/sessions`, etc. devuelven **401** cuando se hacen con el JWT pero **sin** el `X-Admin-Token` válido (o desde un cliente que no lo envía).

En resumen: **tener el JWT no basta para suplantar al usuario en la API admin**; hace falta también el secreto de infraestructura. Eso reduce el riesgo de que un token robado (por ejemplo por XSS o por mirar la pestaña de red) se use desde otro sitio.

### Qué sigue siendo cierto

- El JWT **sí** identifica al usuario (user_id, rol, email, tenant_id) y tiene fecha de expiración (`exp`). Mientras sea válido, quien tenga **JWT + X-Admin-Token** puede actuar como ese usuario.
- Si un atacante consiguiera **ambos** (por ejemplo comprometiendo el frontend o la variable de entorno donde está el admin token), podría suplantar al usuario hasta que el JWT expire.
- Por eso en producción el `X-Admin-Token` debe estar solo en el servidor/build de la app legítima, no en código público, y las peticiones deben ir por **HTTPS** para evitar que alguien capture el token en tránsito.

### Recomendaciones adicionales (endurecimiento)

- **Vida corta del JWT:** Mantener una expiración razonable (por ejemplo 24 h o menos); si se implementa refresh token, acortar aún más la vida del access token.
- **No registrar JWTs:** En logs del orchestrator no imprimir el valor del token; solo, si acaso, "token presente" / "token inválido".
- **Almacenamiento del JWT en el frontend:** Si el token se guarda en `localStorage`, un script malicioso (XSS) podría leerlo. Valorar en el futuro guardar el token en una **cookie httpOnly** (enviada solo al mismo origen y no accesible desde JavaScript) y que el backend la lea; eso exige cambios en el flujo de login y en CORS.
- **CSP y buenas prácticas frontend:** Reducir superficie de XSS para que sea más difícil robar el JWT o el contexto de la sesión.

Con esto queda documentado: el JWT está expuesto en el cliente por diseño, pero el backend **no** confía solo en él para las acciones admin; los 401 que vio Facu son el comportamiento esperado cuando se usa solo el JWT sin el segundo factor.

---

## Resumen OWASP Top 10:2025

| # | Categoría | Descripción breve |
|---|-----------|-------------------|
| A01 | Broken Access Control | Control de acceso insuficiente (rutas, datos, roles). |
| A02 | Security Misconfiguration | Configuración por defecto insegura, headers, errores verbosos. |
| A03 | Software Supply Chain Failures | Dependencias vulnerables, builds no firmados. |
| A04 | Cryptographic Failures | Datos sensibles sin cifrar o cifrado débil. |
| A05 | Injection | SQL, NoSQL, OS, XSS, etc. |
| A06 | Insecure Design | Diseño que facilita ataques (flujos, límites). |
| A07 | Authentication Failures | Credenciales débiles, sesiones, MFA. |
| A08 | Software or Data Integrity Failures | CI/CD, deserialización, actualizaciones no firmadas. |
| A09 | Security Logging and Alerting Failures | Falta de logs de seguridad o alertas. |
| A10 | Mishandling of Exceptional Conditions | Errores que revelan información o dejan el sistema en estado inconsistente. |

---

## Estado por categoría (Dentalogic)

### A01 – Broken Access Control

- **Rutas admin:** Protegidas con `verify_admin_token` (JWT + X-Admin-Token); roles (CEO vs professional/secretary) comprobados donde aplica.
- **Multi-tenant:** Consultas filtradas por `tenant_id` (regla de soberanía). `get_resolved_tenant_id` para endpoints que requieren tenant.
- **Rutas públicas:** Solo `/login` y `/demo`; el resto bajo `ProtectedRoute`.
- **Recomendación:** Revisar periódicamente que ningún endpoint admin olvide el filtro `tenant_id` ni la comprobación de rol.

### A02 – Security Misconfiguration

- **CORS:** Configurado en el orchestrator; revisar orígenes permitidos en producción.
- **Headers:** Valorar añadir políticas de seguridad (CSP, X-Content-Type-Options, etc.) en respuestas HTTP.
- **Errores:** Evitar devolver stack traces o rutas internas al cliente en producción.

### A03 – Software Supply Chain Failures

- **Acción:** Mantener dependencias actualizadas (`npm audit`, `pip audit` o similar) y revisar fuentes de paquetes.
- **Documentar:** Versiones mínimas recomendadas en README o en documento de despliegue.

### A04 – Cryptographic Failures

- **Credenciales Google:** Almacenadas cifradas con Fernet (`CREDENTIALS_FERNET_KEY`); clave no en repo.
- **JWT:** Firma con `JWT_SECRET_KEY`; no almacenar secret en frontend.
- **Contraseñas:** Deben hashearse en backend (bcrypt/argon2); verificar en auth (registro/login).
- **HTTPS:** Obligatorio en producción para login y APIs.

### A05 – Injection

- **SQL:** Consultas parametrizadas (`$1`, `$2`, etc.) en `main.py`, `admin_routes.py`, `auth_routes.py`. Se corrigió el uso de f-string en una query de dashboard (intervalo de días) para usar parámetro.
- **XSS:** React escapa por defecto. No usar `dangerouslySetInnerHTML` con contenido de usuario sin sanitizar.
- **Recomendación:** No construir SQL con f-strings o concatenación con entrada de usuario; usar siempre parámetros.

### A06 – Insecure Design

- **Demo:** La landing y el flujo de login demo están pensados para no depender de credenciales en texto plano en la interfaz (ver medida de redacción).
- **Límites:** Valorar rate limiting en `/auth/login` y en POST `/chat` para mitigar fuerza bruta y abuso.

### A07 – Authentication Failures

- **Login:** JWT con expiración; contraseñas deben estar hasheadas en BD.
- **Demo:** Credenciales demo usadas solo en backend (LoginView envía las constantes al API); no se muestran en la UI de la landing (mostrar [REDACTED]).
- **Recomendación:** No exponer en el DOM ni en el HTML generado emails, teléfonos ni contraseñas de cuentas demo o reales en páginas públicas.

### A08 – Software or Data Integrity Failures

- **Builds:** No se documenta firma de artefactos en este spec; valorar en canal de CI/CD.
- **Dependencias:** Idem A03.

### A09 – Security Logging and Alerting Failures

- **Logs:** El orchestrator registra errores y eventos relevantes (chat, tenant, excepciones). No se detalla aquí un formato estándar de auditoría (quién, qué, cuándo).
- **Recomendación:** Definir qué eventos se consideran de seguridad (login fallido, cambios de rol, acceso a datos sensibles) y registrarlos de forma estructurada.

### A10 – Mishandling of Exceptional Conditions

- **API:** Uso de `HTTPException` y manejador global para no filtrar stack traces al cliente.
- **Frontend:** Mensajes de error genéricos al usuario; no exponer detalles internos en producción.

---

## Medida implementada: redacción en modo demo (UI)

**Objetivo:** Reducir la superficie de extracción de datos sensibles desde el DOM en páginas accesibles sin login (p. ej. scripts o extensiones que lean el DOM).

**Regla:** En contexto "demo" o en páginas públicas, no mostrar en texto plano en la interfaz:
- Emails de cuentas demo.
- Contraseñas (ni demo ni reales).
- Opcionalmente, números de teléfono de demo (según política; el enlace de WhatsApp puede seguir funcionando con el número real en la URL, pero el texto visible puede ser genérico).

**Implementación actual:**

1. **Landing (`/demo`):** En el bloque colapsable "Credenciales de prueba" se muestra:
   - `Email: [REDACTED]`
   - `Contraseña: [REDACTED]`
   Las credenciales reales siguen en constantes en el frontend (LoginView) para el flujo "Probar app" → `/login?demo=1` → "Entrar a la demo"; no se renderizan en el DOM de la landing, por lo que no son extraíbles desde esa página mediante lectura del DOM.
2. **Login con `?demo=1`:** No se muestran los campos de email/contraseña; solo el botón "Entrar a la demo". Los valores se envían por API desde estado de React; no aparecen como texto en la interfaz.
3. **Notificaciones (Layout):** El toast de derivación muestra el número de teléfono del lead. En un entorno exclusivamente demo se podría extender la redacción a este componente (p. ej. mostrar `[REDACTED]` cuando el número coincida con un demo conocido); no implementado en esta fase.

**Límite:** Los datos siguen accesibles vía API con sesión válida; la medida solo evita que estén "regalados" en el HTML/DOM de la landing y del flujo demo, aumentando el esfuerzo para un atacante que solo pueda leer la interfaz.

---

## Checklist de revisión periódica

- [ ] Todas las consultas SQL usan parámetros (no f-strings con entrada de usuario).
- [ ] Ningún endpoint admin omite el filtro `tenant_id` ni la comprobación de rol cuando aplica.
- [ ] Variables de entorno sensibles (JWT_SECRET_KEY, CREDENTIALS_FERNET_KEY, ADMIN_TOKEN, etc.) no están en el repositorio.
- [ ] En páginas públicas y flujo demo, no se muestran emails, contraseñas ni (según política) teléfonos en texto plano; usar [REDACTED] o equivalente.
- [ ] Dependencias (npm/pip) sin vulnerabilidades críticas conocidas.
- [ ] HTTPS y cabeceras de seguridad configurados en producción.

---

## Referencias

- OWASP Top 10:2025: https://owasp.org/Top10/2025/
- AGENTS.md (reglas de soberanía y auth).
- docs/02_environment_variables.md (variables sensibles).
