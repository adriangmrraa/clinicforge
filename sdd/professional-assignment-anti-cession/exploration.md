# Exploration: Agent must respect professional assignment and resist cession

## Current State

### El problema (evidenciado en prueba del 18/05)
1. Paciente nuevo pregunta "Hacen endodoncia?" → agente responde bien "lo realiza nuestro equipo odontológico" ✅
2. Paciente insiste "Laura Delgado no hace endodoncia? Me gustaría atenderme con ella" → agente RESPONDE MAL: "Sí, la endodoncia la hace la Dra. Delgado" ❌

### Causa raíz: 3 gaps

#### GAP 1 — PASO 3 no prioriza `assigned_professional_id`
El paciente PUEDE tener un `assigned_professional_id` en la tabla `patients` (migración 024). `buffer_task.py` línea 711 lo lee y lo inyecta en el prompt como:
```
CONTEXTO DEL PACIENTE (Identidad y Turnos):
• PROFESIONAL ASIGNADO: Dr/a. Laura Delgado — ...
```
**PERO PASO 3 en el system prompt NO menciona esto**. Solo habla de reglas de derivación y list_services. El agente ve el dato pero no tiene instrucción de usarlo.

#### GAP 2 — El agente cede ante insistencia del paciente
No existe ninguna regla anti-cesión. Cuando el paciente insiste "quiero con Laura", el agente no tiene instrucción de mantenerse firme en que endodoncia → equipo.

#### GAP 3 — Orden de precedencia incorrecto en PASO 3
Actualmente PASO 3 pone derivación PRIMERO, pero debería ser:
1. assigned_professional_id del paciente (si existe)
2. treatment_type_professionals (profesionales designados para ese tratamiento)
3. derivation_rules
4. Fallback a list_services

### Lo que YA funciona
- `check_availability` tool ya filtra por `assigned_professional_id` (~línea 1684)
- `buffer_task.py` ya inyecta "PROFESIONAL ASIGNADO" en el contexto del paciente
- `treatment_type_professionals` ya se usa en list_services/get_service_details
- Las derivation_rules ya están en el prompt

## Affected Areas
- `orchestrator_service/main.py` ~9812-9826 — PASO 3 (reestructurar orden de precedencia)
- `orchestrator_service/main.py` ~9034-9047 — REGLAS DE USO DEL CONTEXTO DEL PACIENTE (agregar regla para PROFESIONAL ASIGNADO)

## Approaches

### Approach A (RECOMENDADA): Reestructurar PASO 3 + regla en contexto
**Qué**: 
1. Mover `assigned_professional_id` al primer lugar en PASO 3
2. Agregar regla en CONTEXTO DEL PACIENTE que diga qué hacer con PROFESIONAL ASIGNADO
3. Agregar regla anti-cesión: si paciente insiste con profesional equivocado, mantenerse firme
- **Pros**: Ataca raíz, mínimo riesgo, cambios textuales en prompt
- **Effort**: Bajo

### Approach B: Además modificar book_appointment para auto-asignar
**Qué**: Además de Approach A, modificar `book_appointment` para que setee `assigned_professional_id` automáticamente al agendar
- **Pros**: Automatiza la asignación
- **Cons**: Más cambios, riesgo de regresiones
- **Effort**: Medio

## Recommendation
**Approach A** — Solo cambios en system prompt. La asignación manual existe via admin. El problema es que el agente no usa el dato que ya tiene.

## Ready for Proposal
Sí.
