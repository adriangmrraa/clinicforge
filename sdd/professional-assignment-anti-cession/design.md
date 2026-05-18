# Design: Professional assignment precedence and anti-cession

## Technical Approach

2 cambios textuales en el system prompt de `main.py`. No se tocan tools ni DB. El cambio clave es reestructurar PASO 3 con el orden de precedencia correcto y agregar regla anti-cesión.

## Architecture Decisions

### Decision: Orden de precedencia en PASO 3

**Choice**: `assigned_professional_id` → `treatment_type_professionals` → `derivation_rules` → fallback
**Rationale**: La asignación explícita del paciente (hecha por el admin) es la fuente de verdad más fuerte. Le siguen los profesionales designados al tratamiento. Las reglas de derivación son un mecanismo general. El fallback es para cuando nada está configurado.

### Decision: Anti-cesión como regla separada

**Choice**: Regla anti-cesión al final de PASO 3, fuera del orden de precedencia.
**Rationale**: La anti-cesión no es un paso más en la precedencia — es un guard que aplica SIEMPRE que el paciente insiste en un profesional incorrecto. Separarla del orden de precedencia la hace más visible y fácil de entender para el LLM.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` ~9812-9826 | Modify | Reestructurar PASO 3 con nuevo orden + anti-cesión |
| `orchestrator_service/main.py` ~9043 | Modify | Agregar regla para "PROFESIONAL ASIGNADO" en REGLAS DE USO DEL CONTEXTO |

## Data Flow

```
PASO 3 - ORDEN DE PRECEDENCIA:

¿Paciente tiene "PROFESIONAL ASIGNADO" en su contexto?
├── Sí → Usar ESE profesional. Prioridad absoluta.
└── No ↓

¿El tratamiento tiene profesionales designados (treatment_type_professionals)?
├── Sí, UNO → Nombrar solo ese profesional.
├── Sí, VARIOS → Ofrecer opciones.
└── No ↓

¿Hay regla de derivación que coincida?
├── Sí, "equipo" → "nuestro equipo odontológico" sin nombres.
├── Sí, profesional específico → Nombrar solo ese.
└── No → Fallback (sin filtro).

REGLA ANTI-CESIÓN:
Si paciente insiste con profesional NO designado → mantenerse firme.
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Manual | Anti-cesión endodoncia | Chat: "endodoncia?" → "equipo" → "quiero con Laura" → NO ceder |
| Manual | assigned_professional_id | Chat con paciente que tiene Laura asignada → ofrecer Laura aunque sea limpieza |

## Migration

No requiere migración.
