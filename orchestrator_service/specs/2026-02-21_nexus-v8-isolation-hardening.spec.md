# Nexus v8.0 — Multi-Tenant Isolation Hardening Spec
**Fecha:** 2026-02-21 | **Autor:** Antigravity Audit | **Estado:** `[APPROVED]`

---

## 1. Contexto y Motivación

Durante el re-audit global de `admin_routes.py` se detectaron **5 vulnerabilidades críticas de aislamiento multi-tenant** (Regla de Oro). Los endpoints afectados permiten a un usuario autenticado de la Clínica A leer y/o mutar datos de la Clínica B, lo que viola directamente el Protocolo de Soberanía Nexus.

**Alcance de impacto:**
- Lectura cross-tenant de datos PII (seguros, síntomas, pacientes)
- Mutación cross-tenant de turnos (cambio de estado, eliminación)
- Mutación cross-tenant de profesionales (edición sin verificar sede)

---

## 2. Aclaraciones Incorporadas

| ID | Pregunta | Respuesta del Usuario |
|----|---|---|
| C1 | ¿Orden de prioridad? | Ambos tipos (lectura y escritura) en simultáneo |
| C2 | CEO: ¿global o per-sede en update_professional? | CEO tiene múltiples clínicas — debe validarse contra `allowed_ids` (todas sus sedes). La lógica debe ser coherente en backend, frontend y BD. |
| C3 | `search_patients_by_symptoms`: ¿global para CEO? | CEO = global (todas sus sedes). Profesional/Secretaria = solo su sede activa. |
| C4 | `delete_appointment`: ¿soft o hard delete? | Mantener DELETE físico pero protegido con `tenant_id`. |
| C5 | ¿5 fixes juntos o por fases? | Todos juntos, usando formato `/tasks`. |

---

## 3. Esquema de Datos y Roles

### 3.1 Roles
| Rol | `allowed_ids` | Comportamiento esperado |
|-----|---|---|
| `ceo` | Todas las sedes registradas en su cuenta | Vista global en búsquedas; puede operar sobre cualquier sede propia |
| `secretary` | Solo su `tenant_id` de registro | Scoped estrictamente a su sede |
| `professional` | Solo su `tenant_id` de registro | Scoped estrictamente a su sede |

### 3.2 Dependencias de FastAPI a usar
- `tenant_id = Depends(get_resolved_tenant_id)` → sede activa del usuario
- `allowed_ids = Depends(get_allowed_tenant_ids)` → todas las sedes a las que tiene acceso

---

## 4. Vulnerabilidades y Correcciones Requeridas

### VUL-01: `GET /patients/search-semantic` (L.1685)
**Problema:** `chat_messages` y `patients` no filtran por `tenant_id`. Retorna pacientes de todas las clínicas del sistema.

**Corrección:**
- Si `user_data.role == 'ceo'`: filtrar `patients.tenant_id = ANY(allowed_ids)` y `chat_messages` sin filtro adicional (ya aislado por `patient_id`).
- Si `user_data.role != 'ceo'`: agregar `WHERE tenant_id = $X AND content ILIKE $Y` en `chat_messages` y `WHERE id = ANY(...) AND tenant_id = $X` en `patients`.
- **Agregar** `user_data = Depends(verify_admin_token)` y `allowed_ids = Depends(get_allowed_tenant_ids)` como parámetros.

### VUL-02: `GET /patients/{id}/insurance-status` (L.1731)
**Problema:** Solo filtra `WHERE id = $1 AND status = 'active'`, sin `tenant_id`.

**Corrección:**
- Agregar `tenant_id = Depends(get_resolved_tenant_id)` al endpoint.
- Cambiar query a `WHERE id = $1 AND tenant_id = $2 AND status = 'active'`.

### VUL-03: `PUT/PATCH /appointments/{id}/status` (L.2436)
**Problema:** `UPDATE appointments SET status = $1 WHERE id = $2` no incluye `tenant_id`. Cualquier usuario autenticado puede cambiar el estado de cualquier turno.

**Corrección:**
- Agregar `tenant_id = Depends(get_resolved_tenant_id)` como parámetro.
- Verificar ownership: `SELECT tenant_id FROM appointments WHERE id = $1` y validar contra `allowed_ids`.
- Cambiar query a `WHERE id = $1 AND tenant_id = $2`.

### VUL-04: `DELETE /appointments/{id}` (L.2596)
**Problema:** El `SELECT` y el `DELETE` no filtran por `tenant_id`. Permite borrar turnos ajenos.

**Corrección:**
- Agregar `tenant_id = Depends(get_resolved_tenant_id)`.
- Cambiar `SELECT ... WHERE id = $1` a `WHERE id = $1 AND tenant_id = $2`.
- Cambiar `DELETE ... WHERE id = $1` a `WHERE id = $1 AND tenant_id = $2`.
- Si no existe la fila (404), retornar `HTTPException(404)`.

### VUL-05: `PUT /professionals/{id}` (L.2065)
**Problema:** El `SELECT 1 FROM professionals WHERE id = $1` y todos los `UPDATE ... WHERE id = $X` no verifican `tenant_id`. Un usuario de otra sede puede editar cualquier profesional.

**Corrección:**
- Agregar `allowed_ids = Depends(get_allowed_tenant_ids)` como parámetro.
- Cambiar la verificación de existencia a `SELECT tenant_id FROM professionals WHERE id = $1`.
- Verificar que `professional['tenant_id'] in allowed_ids`; si no, devolver `403`.
- Los `UPDATE ... WHERE id = $X` pueden permanecer ya que la verificación previa de ownership los protege. Sin embargo, para mayor idempotencia incluir `AND tenant_id = $Y` en todos los fallback UPDATE queries también.

---

## 5. Criterios de Aceptación (Gherkin)

### Escenario 1: Aislamiento de lectura de seguros
```gherkin
DADO un profesional autenticado en Clínica A (tenant_id=1)
CUANDO llama a GET /patients/42/insurance-status donde patient_id=42 pertenece a Clínica B (tenant_id=2)
ENTONCES el endpoint retorna HTTP 404 "Paciente no encontrado"
```

### Escenario 2: Aislamiento cross-tenant en búsqueda semántica
```gherkin
DADO una secretaria autenticada en Clínica A (tenant_id=1)
CUANDO llama a GET /patients/search-semantic?query=gingivitis
ENTONCES el resultado solo contiene pacientes con tenant_id=1

DADO un CEO autenticado con allowed_ids=[1, 2, 3]
CUANDO llama a GET /patients/search-semantic?query=gingivitis
ENTONCES el resultado contiene pacientes de las sedes 1, 2 y 3
```

### Escenario 3: Aislamiento de mutación de turnos
```gherkin
DADO un usuario autenticado en Clínica A (tenant_id=1)
CUANDO intenta PATCH /appointments/{id_de_turno_clinica_B}/status con payload={status: "cancelled"}
ENTONCES el endpoint retorna HTTP 404 "Turno no encontrado"
Y el turno de Clínica B NO es modificado en la base de datos
```

### Escenario 4: Aislamiento de eliminación de turnos
```gherkin
DADO un usuario autenticado en Clínica A (tenant_id=1)
CUANDO intenta DELETE /appointments/{id_de_turno_clinica_B}
ENTONCES el endpoint retorna HTTP 404 "Turno no encontrado"
Y el turno de Clínica B permanece en la base de datos
```

### Escenario 5: Aislamiento de edición de profesionales por CEO
```gherkin
DADO un CEO con allowed_ids=[1, 2] (sus propias sedes)
CUANDO intenta PUT /professionals/{id_de_profesional_clinica_3}
ENTONCES el endpoint retorna HTTP 403 "No tienes acceso a esta sede"
```

### Escenario 6: CEO edita profesional propio
```gherkin
DADO un CEO con allowed_ids=[1, 2]
CUANDO intenta PUT /professionals/{id_de_profesional_clinica_2}
ENTONCES el endpoint retorna HTTP 200 y el profesional es actualizado exitosamente
```

---

## 6. Stack y Restricciones

- **Backend:** Python 3.10+, FastAPI, asyncpg, Pydantic v2
- **Base de datos:** PostgreSQL (sin cambios de schema requeridos)
- **Frontend:** Sin cambios requeridos para estas correcciones backend (las APIs ya reciben `tenant_id` automáticamente via cookie/header)
- **Principio de mínimo cambio:** Solo tocar las líneas necesarias para corregir la vulnerabilidad, sin refactorizar lógica de negocio adyacente
- **No romper GCal sync:** Los cambios en `delete_appointment` y `update_appointment_status` deben preservar la lógica de sincronización con Google Calendar

---

## 7. Notas de Coherencia Frontend/Backend

- El frontend ya envía el `X-Tenant-ID` header según la sede activa seleccionada por el usuario.
- El `get_resolved_tenant_id` en `core/auth.py` ya maneja correctamente el header para CEO vs staff.
- No se requieren cambios en el frontend para estas correcciones; la lógica de roles ya funciona.
- Para el CEO, `get_allowed_tenant_ids` ya devuelve todas las sedes registradas correctamente.
