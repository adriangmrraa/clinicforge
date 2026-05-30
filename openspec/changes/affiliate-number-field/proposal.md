# Proposal: DLD-33 — Número de afiliado

## Intent

Exponer el campo `insurance_id` (ya existente en la tabla `patients` desde el baseline) a través de todo el stack: backend Pydantic → endpoints → frontend formulario + ficha de paciente.

El campo existe en base de datos hace tiempo pero nunca fue conectado. Esto significa que los pacientes con obra social no tienen dónde registrar su número de afiliado, forzando a la clínica a guardar ese dato por fuera del sistema (papel, notas libres, etc.). El impacto operativo es bajo pero la usabilidad es deficiente para clínicas que trabajan con obras sociales.

## Scope

### Se toca
- `orchestrator_service/models.py` — verificar que `insurance_id` ya está mapeado (columna existente, sin cambio de DDL)
- `orchestrator_service/admin_routes.py` — `PatientCreate`, `PatientUpdate` Pydantic schemas; INSERT, UPDATE, SELECT list, SELECT detail
- `frontend_react/src/views/PatientsView.tsx` — input en formulario alta/edición + columna/render en tabla
- `frontend_react/src/views/PatientDetail.tsx` — render del campo junto a obra social
- `frontend_react/src/locales/es.json`, `en.json`, `fr.json` — claves i18n

### No se toca
- Alembic migrations — la columna `insurance_id VARCHAR(50)` ya existe desde el baseline (migración 001). Cero cambios de esquema.
- WhatsApp bot / IA tools — el número de afiliado no es relevante para el flujo conversacional
- Importación bulk CSV — futura mejora independiente
- Validación de formato — el campo es libre (VARCHAR 50), sin regex ni longitud mínima

## Approach

Plumbing puro en cuatro capas, sin lógica de negocio nueva:

1. **Pydantic schemas** (`PatientCreate`, `PatientUpdate`): agregar `insurance_id: Optional[str] = None`. Convención de mapeo establecida: backend `insurance_id` → frontend `obra_social_number` (alias ya en la interfaz TS).

2. **Endpoints backend**:
   - `POST /admin/patients` — incluir `insurance_id` en el INSERT SQL
   - `PUT /admin/patients/{id}` — incluir `insurance_id` en el UPDATE SQL (COALESCE o SET directo)
   - `GET /admin/patients` — agregar `insurance_id` al SELECT de la lista
   - `GET /admin/patients/{id}` — agregar `insurance_id` al SELECT del detalle

3. **Frontend — formulario** (`PatientsView.tsx`): input de texto opcional justo debajo del campo obra social (`obra_social`), usando la misma clase visual. Bindeado a `obra_social_number` en el estado local del modal.

4. **Frontend — ficha** (`PatientDetail.tsx`): renderizar `obra_social_number` en la sección de información de cobertura/obra social, como campo de solo lectura con la misma tipografía de los demás campos.

5. **i18n**: claves `patients.insurance_number` (label), `patients.insurance_number_placeholder` (placeholder).

## Risks

**Bajo.** La columna ya existe y acepta NULL, por lo que:
- No hay riesgo de migración fallida
- No hay riesgo de rotura en registros existentes (el campo queda NULL para pacientes ya creados)
- El único riesgo es un SELECT que no incluya el campo y devuelva `undefined` en frontend — mitigado por los escenarios de testing en la spec
