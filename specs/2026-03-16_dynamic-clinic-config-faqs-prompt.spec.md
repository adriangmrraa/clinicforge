# Spec: Configuración Dinámica de Clínica, FAQs y System Prompt

**Fecha:** 2026-03-16
**Versión:** 1.0
**Estado:** Aprobado (clarificado con usuario)

---

## 1. Contexto y Objetivos

El system prompt del agente IA tiene datos hardcodeados (nombre doctora, dirección, horarios por día, FAQs) que impiden la reutilización multi-tenant. Se requiere:

1. Que los datos de la sede (dirección, Google Maps URL, horarios por día) se gestionen desde la UI y se persistan en DB.
2. Que las FAQs sean configurables por clínica desde un modal en la vista de Clínicas y Sedes.
3. Que el system prompt consuma datos dinámicos de DB en vez de hardcodeados.
4. Optimizar el prompt para reducir tokens sin perder efectividad.
5. Eliminar placeholders falsos (sin_email@placeholder.com, 00/00/0000) y usar NULL.
6. Sanitizar ad_context antes de inyectarlo al prompt.

---

## 2. Requerimientos Técnicos

### 2.1 Base de Datos

**Nuevas columnas en `tenants`:**
- `address TEXT` — Dirección texto libre
- `google_maps_url TEXT` — Link de Google Maps
- `working_hours JSONB DEFAULT '{}'` — Misma estructura que professionals: `{ "monday": { "enabled": true, "slots": [{"start":"13:00","end":"19:00"}] }, ... }`

**Nueva tabla `clinic_faqs`:**
```sql
CREATE TABLE IF NOT EXISTS clinic_faqs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    category VARCHAR(100) NOT NULL DEFAULT 'General',
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_clinic_faqs_tenant ON clinic_faqs(tenant_id);
```

### 2.2 Backend — Endpoints

**Extender `GET /admin/tenants`:** Retornar `address`, `google_maps_url`, `working_hours`.

**Extender `PUT /admin/tenants/{id}`:** Aceptar y persistir `address`, `google_maps_url`, `working_hours`.

**CRUD FAQs:**
- `GET /admin/tenants/{tenant_id}/faqs` — Listar FAQs de un tenant (ordenadas por sort_order)
- `POST /admin/tenants/{tenant_id}/faqs` — Crear FAQ
- `PUT /admin/faqs/{faq_id}` — Actualizar FAQ
- `DELETE /admin/faqs/{faq_id}` — Eliminar FAQ

Auth: `Depends(verify_admin_token)` en todos. Validar `tenant_id` desde JWT.

### 2.3 Backend — System Prompt

**Nuevos parámetros de `build_system_prompt`:**
- `clinic_address: str` — Dirección de la sede
- `clinic_maps_url: str` — Link Google Maps
- `clinic_working_hours: dict` — Horarios por día de la sede
- `faqs: list[dict]` — Lista de FAQs `[{category, question, answer}]`

**Eliminar del prompt:**
- Nombre hardcodeado "Dra. María Laura Delgado"
- Dirección "Calle Córdoba 431"
- Horarios específicos por día hardcodeados
- FAQs fijas (obra social, costos, duele, etc.)
- Placeholders (sin_email@placeholder.com, 00/00/0000)

**Inyectar dinámicamente:**
- Dirección y Maps URL desde parámetros
- Horarios por día desde `clinic_working_hours`
- FAQs desde lista dinámica
- Usar clinic_name (que ya se recibe como parámetro)

**Optimización:**
- Eliminar redundancias (horarios repetidos, identidad repetida, reglas duplicadas)
- Consolidar secciones similares
- Mantener todas las directivas de comportamiento

**Sanitización:**
- Escapar/limpiar `ad_context` antes de inyectar al prompt
- Usar NULL en vez de placeholders para datos de pacientes

**Regla de puntuación:** Mantener prohibición de signos de apertura (¿ ¡). Corregir ejemplos que los usen.

### 2.4 Frontend — ClinicsView

**Expandir modal de edición de sede con:**
- Campo "Dirección" (texto libre)
- Campo "Link Google Maps" (texto)
- Editor de horarios por día (replicar patrón de UserApprovalView):
  - 7 días con toggle enabled/disabled
  - Slots de horario con hora inicio/fin
  - Botón agregar/quitar slots
- Botón "Gestionar FAQs" que abre modal de FAQs

**Nuevo modal de FAQs:**
- Lista de FAQs existentes con edición inline o modal
- Campos: Categoría (input editable), Pregunta, Respuesta
- Botones: Agregar, Editar, Eliminar
- Ordenamiento por sort_order

### 2.5 Frontend — i18n

Agregar claves en `es.json`, `en.json`, `fr.json` para todos los textos nuevos.

---

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Feature: Configuración dinámica de clínica

Scenario: CEO edita dirección y horarios de sede
  Given el CEO abre el modal de edición de una sede
  When carga dirección, Maps URL y configura horarios por día
  And guarda los cambios
  Then los datos se persisten en la tabla tenants
  And el agente IA usa esos datos en su próxima conversación

Scenario: CEO gestiona FAQs
  Given el CEO abre el modal de FAQs de una clínica
  When agrega una FAQ con categoría "Pagos", pregunta y respuesta
  Then la FAQ aparece en la lista
  And el agente IA incluye esa FAQ en su system prompt

Scenario: Agente usa datos dinámicos
  Given una clínica con dirección, horarios y FAQs configurados
  When un paciente pregunta "dónde están?"
  Then el agente responde con la dirección y Maps URL de la DB, no hardcodeados

Scenario: Paciente sin email se guarda con NULL
  Given un paciente nuevo que no proporcionó email
  When se ejecuta book_appointment
  Then el campo email se guarda como NULL, no como placeholder
```

---

## 4. Esquema de Datos

### tenants (columnas nuevas)
| Columna | Tipo | Default | Descripción |
|---------|------|---------|-------------|
| address | TEXT | NULL | Dirección de la sede |
| google_maps_url | TEXT | NULL | Link de Google Maps |
| working_hours | JSONB | '{}' | Horarios por día (mismo formato que professionals) |

### clinic_faqs (tabla nueva)
| Columna | Tipo | Default | Descripción |
|---------|------|---------|-------------|
| id | SERIAL | PK | ID único |
| tenant_id | INTEGER | FK→tenants | Clínica asociada |
| category | VARCHAR(100) | 'General' | Etiqueta de categoría |
| question | TEXT | NOT NULL | Pregunta |
| answer | TEXT | NOT NULL | Respuesta |
| sort_order | INTEGER | 0 | Orden de visualización |
| created_at | TIMESTAMPTZ | NOW() | Timestamp creación |
| updated_at | TIMESTAMPTZ | NOW() | Timestamp actualización |

---

## 5. Riesgos y Mitigación

| Riesgo | Mitigación |
|--------|-----------|
| Prompt muy largo con muchas FAQs | Limitar a 20 FAQs por tenant; truncar si excede |
| Horarios no configurados (vacíos) | Fallback a "Consultar en sede" si working_hours está vacío |
| Migración rompe datos existentes | Parches idempotentes con IF NOT EXISTS |
| ad_context con inyección | Sanitizar removiendo caracteres de control y limitando longitud |
