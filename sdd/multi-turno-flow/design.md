# Design: Multi-turno flow

## Technical Approach

Agregar un nuevo PASO 3b entre ANTI-CESIÓN (L9871) y PASO 4 (L9872). Es texto en el system prompt, no toca tools ni DB.

## Architecture Decisions

### Decision: PASO 3b después de ANTI-CESIÓN, antes de PASO 4

**Rationale**: El orden lógico es: determinar profesional (PASO 3) → verificar si ya tiene turno (PASO 3b) → consultar disponibilidad (PASO 4).

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` ~9871 | Insert | Agregar PASO 3b entre ANTI-CESIÓN y PASO 4 |

## Data Flow

```
PASO 3 → determina profesional
  → PASO 3b (nuevo): ¿paciente ya tiene turno? Si sí, reconocerlo. El nuevo turno debe ser distinto horario.
  → PASO 4: check_availability
```

## Testing Strategy

| Scenario | Approach |
|----------|----------|
| Paciente con turno pide otro → ofrece slots sin incluir el ocupado | Manual |
| Paciente con turno pide otro misma hora → bloquea | Manual |
| Paciente con turno pide otro distinta hora mismo día → permite | Manual |
