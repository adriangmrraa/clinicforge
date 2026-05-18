# Design: Retry availability

## Technical Approach

Modificar PASO 4 en el system prompt para agregar instrucciones de retry con rango más amplio cuando check_availability devuelve 0 slots.

## Architecture Decisions

### Decision: Modificar PASO 4 existente, no crear PASO nuevo

**Rationale**: Es una extensión del mismo paso, no un paso independiente. El retry es parte de "consultar disponibilidad".

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` ~9872 | Modify | Agregar instrucciones de retry en PASO 4 |

## Data Flow

```
PASO 4 check_availability(..., search_mode='exact')
  ├── ¿0 slots? → check_availability(..., search_mode='week')
  │     ├── ¿0 slots? → check_availability(..., search_mode='month')
  │     │     ├── ¿0 slots? → informar: "no encontré disponibilidad"
  │     └── → ofrecer slots
  └── → ofrecer slots
```

## Testing Strategy

| Scenario | Approach |
|----------|----------|
| Fecha exacta sin slots → reintenta con semana → encuentra | Manual |
| book_appointment falla → ofrece otro horario de los existentes | Manual |
