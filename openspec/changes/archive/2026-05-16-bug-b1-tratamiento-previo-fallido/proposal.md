# Proposal: Bug B1 — Tratamiento previo fallido no debe asumir historial clínico

## Intent

El bot Paula asume que cualquier tratamiento previo fallido que menciona un paciente ocurrió en la clínica, cuando en realidad el paciente puede haber sido tratado en otro lado. Esto genera confusión, obliga al paciente a corregir al bot ("no, no me entendiste, fue en otro lado"), y da una mala impresión de la clínica.

## Scope

### In Scope
- Acotar los triggers de la sección `DETECCIÓN DE PACIENTE EXISTENTE SIN DATOS EN SISTEMA (MIGRACIÓN)` para que NO capturen casos de tratamiento previo en otro lugar
- Agregar una regla explícita de neutralidad: "Cuando un paciente menciona un tratamiento previo fallido, NO asumir que fue en la clínica"
- Agregar la respuesta modelo aprobada por Laura como referencia en el prompt
- Modificaciones exclusivamente en el texto del system prompt (`build_system_prompt()` en `main.py`)

### Out of Scope
- Cambios en la lógica de `derivhumano` o tools
- Modificaciones a otros flujos emocionales (F2-F9)
- Cambios en la DB o modelos
- Cambios en el frontend
- Cambios en otros archivos fuera de `main.py`

## Approach

Tres modificaciones de texto en el system prompt (`build_system_prompt()`, ~líneas 9464-9471 y zona adyacente):

1. **Acotar trigger de MIGRACIÓN**: Agregar excepción explícita: "EXCEPCIÓN: si el paciente menciona un tratamiento en otro lugar, una mala experiencia con otro profesional, o dice 'me hice implantes y me fue mal' sin especificar que fue en esta clínica → NO activar esta regla."
2. **Nueva regla de neutralidad**: Insertar entre la sección de MIGRACIÓN y PROHIBICIONES: "REGLAS DE NEUTRALIDAD EN TRATAMIENTO PREVIO:" con la respuesta modelo de Laura.
3. **Reforzar F1**: Agregar el trigger "me hice [tratamiento] y me fue mal" explícitamente a los triggers de F1.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` — `build_system_prompt()` | Modified | 3 cambios de texto en el prompt, ~15 líneas agregadas |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Regla de neutralidad demasiado restrictiva | Baja | Solo aplica cuando NO hay indicación explícita de que fue en la clínica |
| Regresión en detección de pacientes existentes | Baja | Los triggers de migración se acotan, no se eliminan |

## Rollback Plan

Revertir las líneas modificadas en `build_system_prompt()`. Es un cambio de texto puro, sin migraciones ni cambios estructurales.

## Dependencies

Ninguna. Es un cambio autónomo en el system prompt.

## Success Criteria

- [ ] Cuando un paciente dice "me hice implantes y me fue mal" SIN especificar lugar, el bot responde con empatía neutral sin asumir que fue en la clínica
- [ ] Cuando un paciente dice explícitamente "tengo un turno pendiente con la doctora", la MIGRACIÓN sigue funcionando correctamente
- [ ] La respuesta modelo de Laura está incorporada y disponible como referencia en el prompt
