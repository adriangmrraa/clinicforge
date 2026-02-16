# Auditoría: contrato API y documentación (2026-02-09)

**Workflow:** Audit (detección de drift).  
**Objetivo:** Verificar que el contrato OpenAPI/Swagger y la documentación (API_REFERENCE) coinciden con los endpoints reales del Orchestrator y que no falte ningún endpoint.

---

## 1. Fuentes comparadas

| Fuente | Descripción |
|--------|-------------|
| **Código** | `orchestrator_service/main.py`, `admin_routes.py`, `auth_routes.py` (rutas registradas en la app FastAPI). |
| **Contrato OpenAPI** | Generado por FastAPI en `/openapi.json` y expuesto en `/docs` (Swagger UI). |
| **Documentación** | `docs/API_REFERENCE.md` (referencia escrita de endpoints). |

---

## 2. Inventario de endpoints en código

- **Auth** (prefix `/auth`): 6 endpoints (clinics, register, login, me, profile GET, profile PATCH).
- **Raíz** (main): 2 endpoints (`POST /chat`, `GET /health`).
- **Admin** (prefix `/admin`): 48 endpoints en los grupos Usuarios, Sedes, Pacientes, Turnos, Profesionales, Chat, Calendario, Tratamientos, Estadísticas, Configuración, Analítica, Internal.

**Total: 56 endpoints de API** (excl. `/docs`, `/redoc`, `/openapi.json`).

Ningún endpoint tiene `include_in_schema=False`, por lo que todos deben aparecer en OpenAPI.

---

## 3. Contrato OpenAPI (Swagger)

- **Resultado:** **Match.**
- FastAPI genera el esquema a partir de `app.routes`. Los routers `auth_router` y `admin_router` se incluyen antes de envolver la app con Socket.IO, por lo que todas las rutas HTTP forman parte del contrato.
- Los **securitySchemes** (Bearer, X-Admin-Token) se inyectan en `_custom_openapi()` sin alterar la lista de paths.
- **Conclusión:** No falta ningún endpoint en el contrato; la salud del contrato es correcta.

---

## 4. Documentación API_REFERENCE.md

- **Resultado:** **Drift detectado y corregido.**
- **Discrepancia:** El endpoint **`GET /admin/professionals/{id}/analytics`** existía en código y en el contrato OpenAPI pero **no estaba documentado** en `API_REFERENCE.md`.
- **Acción correctiva:** Añadida la sección "Analíticas por profesional" en la sección Profesionales de `API_REFERENCE.md`, documentando `GET /admin/professionals/{id}/analytics`.

---

## 5. Resumen

| Criterio | Estado |
|----------|--------|
| Todos los endpoints del código aparecen en OpenAPI | ✅ Match |
| Contrato OpenAPI accesible y con tags/security | ✅ OK |
| API_REFERENCE.md alineado con endpoints reales | ✅ Corregido (1 endpoint añadido) |

**Veredicto final:** **Match** tras la corrección. El contrato está completo y la documentación queda alineada con el código.

---

*Auditoría ejecutada según `.agent/workflows/audit.md`.*
