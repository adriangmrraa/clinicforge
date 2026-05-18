# Design: CASO 2 — Agent uses derivation rules for professional assignment

## Technical Approach

2 cambios en `main.py`. El principal es reestructurar PASO 3 del system prompt para que consulte `derivation_section` ANTES que `list_services`/`get_service_details`. El secundario es modificar `get_service_details` para que no appende profesionales cuando existe `ai_response_template`.

## Architecture Decisions

### Decision: PASO 3 con orden de precedencia

**Choice**: Reemplazar PASO 3 por una estructura con 3 niveles: (1) derivation_rules, (2) fallback a list_services/get_service_details
**Alternatives**: Eliminar PASO 3 por completo, modificar solo list_professionals
**Rationale**: Las derivation_rules son la fuente de verdad. Tener un solo lugar donde se define el orden de consulta es más mantenible y evita que el LLM tenga que decidir qué fuente usar. El fallback garantiza que si no hay reglas configuradas, el agente sigue funcionando como antes.

### Decision: get_service_details sin appender profesionales

**Choice**: No incluir "Profesionales:" cuando existe ai_response_template
**Alternatives**: Dejar el append pero marcar como "interno"
**Rationale**: El ai_response_template ya dice "lo realiza el equipo odontológico". Appender nombres individuales contradice eso y confunde al LLM. Si no hay template, el comportamiento actual se mantiene (la info de profesionales sigue disponible vía list_services).

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` ~9812-9815 | Modify | Reemplazar PASO 3 con orden de precedencia que prioriza derivation_rules |
| `orchestrator_service/main.py` ~5392-5395 | Modify | No appender "Profesionales:" cuando existe ai_response_template |

## Data Flow

```
PASO 3 (nuevo):
  ¿El tratamiento/categoría aparece en DERIVACIÓN DE PACIENTES?
    ├── Sí, y dice "equipo" → "nuestro equipo odontológico" (sin nombres)
    ├── Sí, y dice profesional específico → nombrar solo ese profesional
    └── No → fallback a list_services/get_service_details (comportamiento actual)
```

```
get_service_details (modificado):
  ¿Tiene ai_response_template?
    ├── Sí → devolver SOLO el template (sin appender profesionales)
    └── No → devolver datos completos con profesionales (comportamiento actual)
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Manual | CASO 2 endodoncia | Preguntar "Con quién me atiendo una endodoncia?" → debe responder "equipo" sin nombres |
| Manual | CASO 2 implantes | Preguntar "Quién hace implantes?" → debe responder "Dra. Laura Delgado" |
| Unit | get_service_details output | Verificar que con template no appendea profesionales |

## Migration

No requiere migración.
