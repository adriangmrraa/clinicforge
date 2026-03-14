# Implementation Plan: Fix book_appointment (Paciente sin turno)

> Spec: `specs/2026-03-13_fix-book-appointment-patient-without-turno.spec.md`

## Goal Description

Reordenar la lógica de `book_appointment` para que la creación/actualización del paciente ocurra SOLO después de confirmar que hay un profesional disponible. Evitar pacientes persistidos sin turno cuando no hay disponibilidad.

## User Review Required

- **Decisión:** Para pacientes EXISTENTES, ¿actualizamos sus datos (nombre, DNI, etc.) antes o después del chequeo de disponibilidad?
  - **Opción A (Spec):** Mover todo después. Consistencia total; si no hay slot, no tocamos la BD (excepto lecturas).
  - **Opción B:** Actualizar existentes antes (solo UPDATE, no INSERT). No crea huérfanos; solo refresca datos. Si falla disponibilidad, el paciente ya tiene datos actualizados (puede retentar con otro horario).
  - **Recomendación:** Opción A para máxima consistencia y menor confusión.

## Proposed Changes

### Backend — `orchestrator_service/main.py`

1. **Bloque 1 (sin cambio):** Validación inicial: `parse_datetime`, fecha no pasada, normalización de campos, validación técnica (DNI, nombre, apellido).
2. **Bloque 2 (sin cambio):** Resolución de `treatment_reason` → `treatment_code`, `final_duration`. Si tratamiento no encontrado → return.
3. **Bloque 3 (sin cambio):** Cálculo de `end_apt = apt_datetime + timedelta(minutes=final_duration)`.
4. **Bloque 4 (sin cambio):** Búsqueda de profesionales y loop de disponibilidad (working_hours, JIT GCal si aplica, conflicto). Determinar `target_prof`.
5. **Bloque 5 (NUEVO orden):** Si `not target_prof` → return "no hay disponibilidad" (sin haber creado/actualizado paciente).
6. **Bloque 6 (movido):** Verificar/crear paciente (existente → UPDATE; nuevo → INSERT). Obtener `patient_id`.
7. **Bloque 7 (sin cambio):** INSERT en `appointments`.
8. **Bloque 8 (sin cambio):** GCal sync, Socket.IO, return mensaje de éxito.

### Verificación de Soberanía

- Todas las queries existentes ya incluyen `tenant_id`. No se añaden queries nuevas.
- Validar que el flujo no introduce lecturas/escrituras sin filtro `tenant_id`.

## Verification Plan

1. **Manual:** Ejecutar `book_appointment` con paciente nuevo y horario sin disponibilidad → verificar que no se crea fila en `patients`.
2. **Manual:** Ejecutar con disponibilidad → verificar que paciente y turno se crean.
3. **Logs:** Revisar que no hay excepciones en `book_appointment`.
4. **Opcional:** pytest para `book_appointment` (requiere BD; puede ejecutarse en integración).

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Lógica compleja, posible regresión | Cambio acotado: solo reordenar bloques. No modificar queries ni validaciones. |
| Paciente existente no actualizado hasta éxito | Aceptable: se actualizará en el próximo intento exitoso. |
