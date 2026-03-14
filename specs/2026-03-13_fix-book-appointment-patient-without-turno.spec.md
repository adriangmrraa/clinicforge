# Fix book_appointment: Paciente guardado sin turno

> Origen: Conversación usuario — agenda falla al agendar desde IA; paciente se guarda pero el turno no; comportamiento intermitente (una prueba pasa, otra falla).

## 1. Contexto y Objetivos

- **Problema:** La tool `book_appointment` crea o actualiza el paciente ANTES de verificar disponibilidad de profesionales. Si no hay slot disponible (conflicto con otro turno, bloques GCal, o working_hours), devuelve "no hay disponibilidad" sin insertar el turno — pero el paciente ya fue persistido. Resultado: pacientes sin turno, confusión de datos, UX degradada.
- **Solución:** Reordenar la lógica para que la creación/actualización del paciente ocurra SOLO cuando se haya confirmado un profesional disponible. Si no hay disponibilidad, no persistir al paciente (nuevo) ni hacer cambios; retornar el mensaje de error sin efectos secundarios.
- **KPIs:** (1) No más pacientes creados sin turno por falta de disponibilidad. (2) Pacientes existentes: seguir actualizando sus datos si se proporcionan, pero solo tras confirmar disponibilidad (opcional: mantener update de existentes antes del chequeo para no perder datos de contacto).

## 2. Esquemas de Datos

- **Entradas:** Sin cambios. Parámetros actuales de `book_appointment`: `date_time`, `treatment_reason`, `first_name`, `last_name`, `dni`, etc.
- **Salidas:** Mismos mensajes de éxito/error. Sin cambio de contrato.
- **Persistencia:** Sin cambios de esquema. Solo cambio de orden de operaciones dentro de la misma transacción lógica.

## 3. Lógica de Negocio (Invariantes)

- **ANTES:** `validate → create/update patient → find professional → if no target_prof: return error (patient already saved)`.
- **DESPUÉS:** `validate → find professional (target_prof) → if no target_prof: return error (no patient change) → create/update patient → INSERT appointment`.
- **RESTRICCIÓN:** Para pacientes NUEVOS: no crear en `patients` hasta tener `target_prof` confirmado.
- **EXCEPCIÓN (Pacientes existentes):** Se puede mantener el UPDATE de pacientes existentes antes del chequeo de disponibilidad, ya que es idempotente y no crea registros huérfanos; o moverlo después para consistencia total. La spec recomienda mover TODO después de `target_prof` para máxima consistencia.
- **SOBERANÍA:** Toda query mantiene `tenant_id`. No se añaden queries nuevas; solo se reordena el flujo.

## 4. Stack y Restricciones

- **Backend:** `orchestrator_service/main.py` — función `book_appointment` (aprox. líneas 687–997).
- **Frontend:** Ninguno.
- **API:** Tool interna (LangChain). Sin cambios de contrato.
- **DB:** Sin parches. Mismas queries, distinto orden.

## 5. Criterios de Aceptación (Gherkin)

**Escenario 1: Paciente nuevo, sin disponibilidad**
- DADO que el usuario es nuevo (no existe en `patients` por teléfono ni DNI)
- Y que no hay profesional disponible en el horario solicitado (conflicto o working_hours)
- CUANDO se llama `book_appointment` con todos los datos obligatorios
- ENTONCES no se crea fila en `patients` y se retorna "no hay disponibilidad"

**Escenario 2: Paciente nuevo, con disponibilidad**
- DADO que el usuario es nuevo
- Y que hay al menos un profesional disponible
- CUANDO se llama `book_appointment` con datos correctos
- ENTONCES se crea el paciente Y se inserta el turno en `appointments`

**Escenario 3: Paciente existente, sin disponibilidad**
- DADO que el paciente ya existe (por teléfono o DNI)
- Y que no hay disponibilidad
- CUANDO se llama `book_appointment`
- ENTONCES no se inserta turno; el UPDATE del paciente es opcional (spec recomienda no actualizar hasta confirmar disponibilidad para consistencia)

**Escenario 4: Comportamiento actual de éxito preservado**
- DADO un flujo válido (tratamiento, profesional, horario libre)
- CUANDO `book_appointment` retorna éxito
- ENTONCES paciente y turno existen; mensaje de confirmación correcto

## 6. Archivos Afectados

| Archivo | Tipo | Cambio |
|---------|------|--------|
| `orchestrator_service/main.py` | MODIFY | Reordenar bloques en `book_appointment`: validación tratamiento → búsqueda profesional → si no target_prof, return → crear/actualizar paciente → INSERT appointment |
| `specs/2026-03-13_fix-book-appointment-patient-without-turno.spec.md` | CREATE | Especificación (este archivo) |

## 7. Casos Borde y Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Paciente existente con datos nuevos (nombre, DNI) — si no actualizamos hasta después, perdemos el intento de actualización | Aceptable: el usuario puede volver a intentar con otro horario; la actualización se hará en ese intento exitoso. Alternativa: actualizar existentes antes (solo UPDATE, no INSERT) para no perder datos. |
| Validación de datos obligatorios (first_name, last_name, dni) para nuevos | Mantener validación al inicio; si faltan datos, retornar error sin cambiar estado. La validación ocurre antes de cualquier persistencia. |
| Tratamiento no encontrado, parse_datetime fallido | Sin cambio: ya retornan antes de crear paciente. |

## 8. Checkpoints de Soberanía

- ✅ Toda query existente ya incluye `tenant_id`.
- ✅ Sin cambios de esquema; no se requieren parches en `db.py`.
- ✅ Sin endpoints nuevos; tool interna.
- ✅ Sin cambios de texto visible (sin i18n).
