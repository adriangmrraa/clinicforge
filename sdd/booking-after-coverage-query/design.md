# Design: CASO 1 — Booking after coverage query

## Technical Approach

3 cambios puramente textuales en `main.py` sobre el system prompt. No se tocan tools, ni lógica de booking, ni DB. Los cambios eliminan contaminación semántica "Derivar" y agregan instrucciones post-respuesta para external_derivation.

## Architecture Decisions

### Decision: Text replacement en _format_insurance_providers

**Choice**: Reemplazar cadenas literales en `_format_insurance_providers()` 
**Alternatives**: Dejar el texto como está y agregar regla negativa
**Rationale**: La palabra "Derivar" es el trigger semántico. Sacarla es más efectivo que agregar "no hacer X". El LLM responde mejor a instrucciones positivas que a prohibiciones.

### Decision: Instrucción condicional post-respuesta

**Choice**: Instrucción que dice "SI paciente ya eligió día → continuar booking"
**Alternatives**: Instrucción genérica "siempre continuar booking"
**Rationale**: El user pidió explícitamente que no sea "siempre" — solo cuando el paciente ya mostró intención de agendar.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` ~8400 | Modify | `"Derivación externa:"` → `"Cobertura con centro externo:"` |
| `orchestrator_service/main.py` ~8408 | Modify | `"→ Derivar a {target}"` → `"→ Centro externo: {target}"` |
| `orchestrator_service/main.py` ~10026 | Modify | Agregar instrucción post-respuesta para external_derivation |

## Data Flow

```
_format_insurance_providers() 
  → genera bloque OBRAS SOCIALES para system prompt
  → Cambio 1+2: renombra etiquetas en sección external_derivation
  → LLM ya no asocia "derivar" con derivhumano

check_insurance_coverage response section
  → Cambio 3: agrega instrucción post-respuesta
  → Si paciente ya eligió día → continuar booking
  → No llamar derivhumano
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Text output de _format_insurance_providers | Verificar que no contenga "Derivación" ni "Derivar" para external_derivation |
| Manual | CASO 1 completo en pruebas | Simular: paciente con dolor, elige día, pregunta ISSN → verificar que agenda |

## Migration

No requiere migración.
