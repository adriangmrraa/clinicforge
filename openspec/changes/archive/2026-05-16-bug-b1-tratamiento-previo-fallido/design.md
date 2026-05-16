# Design: Bug B1 — Tratamiento previo fallido no debe asumir historial clínico

## Technical Approach

Agregar una **compuerta de prioridad** (gate) ANTES de la sección de MIGRACIÓN, más un refuerzo en F1. No se modifica ni elimina la MIGRACIÓN — solo se antepone una regla que desambigua cuándo aplica.

La MIGRACIÓN sigue exactamente igual para los casos legítimos (paciente real de la Dra. que dice "la doctora me dijo" o "tengo turno pendiente").

## Architecture Decisions

### Decision: Gate de prioridad antes de MIGRACIÓN

**Choice**: Insertar un nuevo bloque `REGLAS DE PRIORIDAD — TRATAMIENTO PREVIO` entre la línea 9463 (fin de IDENTIDAD Y TONO) y la línea 9464 (inicio de MIGRACIÓN).

**Alternatives considered**:
1. Modificar los triggers de MIGRACIÓN directamente — Riesgo: romper casos legítimos
2. Eliminar la MIGRACIÓN — Riesgo: perder detección de pacientes reales no migrados
3. Agregar la regla dentro de la MIGRACIÓN como excepción — Funcional pero menos visible

**Rationale**: El gate ANTES de MIGRACIÓN es la opción más limpia porque:
- La MIGRACIÓN queda intacta para sus casos legítimos
- La nueva regla establece prioridad: "si es tratamiento en otro lado → F1, NO migración"
- Es fácil de leer y mantener porque están separadas
- Sigue el principio de "early return" — si pasa el gate, sigue a migración

### Decision: Refuerzo en F1 (Mala experiencia previa)

**Choice**: Agregar triggers adicionales al flujo F1.

**Alternatives considered**: Crear un nuevo flujo F10 específico para "tratamiento previo fallido" — Overkill, F1 ya cubre esto.

**Rationale**: F1 ya existe y su protocolo M1→M2→M3 cubre EXACTAMENTE el caso. Solo faltan los triggers. Un flujo separado sería innecesario.

## Data Flow

``` 
Mensaje del paciente
         │
         ▼
┌─────────────────────────────────────┐
│ GATE: Tratamiento previo fallido    │ ← NUEVO
│ "me hice implantes y me fue mal"    │
│ "en otro lugar"                     │
│ "fui a otro dentista"              │
│         │                           │
│   ┌─────┴─────┐                     │
│   │ SÍ        │ NO                  │
│   ▼           ▼                     │
│  F1       ┌──────────────────┐      │
│           │ MIGRACIÓN        │      │ ← EXISTENTE (intacto)
│           │ "la Dra. me dijo"│      │
│           │ "tengo turno"    │      │
│           └──────────────────┘      │
└─────────────────────────────────────┘
         │
         ▼
    PROHIBICIONES → ... → FLUJOS F2-F9
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` | Modify | 3 cambios de texto en `build_system_prompt()` |

### Cambio 1: Gate de prioridad (INSERTAR entre línea 9463 y 9464)

Se agrega un nuevo bloque después de la línea 9463 y ANTES de `## DETECCIÓN DE PACIENTE EXISTENTE`:

```python
## REGLA DE PRIORIDAD — TRATAMIENTO PREVIO FALLIDO (GATE)
# Se evalúa ANTES que la detección de migración.
# Si el paciente menciona un tratamiento, cirugía o procedimiento previo
# SIN indicar que fue en ESTA clínica → NO entrar a MIGRACIÓN, aplicar F1.

CUANDO el paciente diga:
• "me hice [tratamiento] y me fue mal" (sin especificar dónde)
• "en otro lugar", "fui a otro lado", "otro dentista", "otro profesional"
• "me hicieron [tratamiento] pero no me resultó"
• Cualquier mención de tratamiento previo SIN referirse a "la doctora", "la Dra.", "esta clínica"

→ APLICAR FLUJO F1 (Mala experiencia previa).
→ NO activar la detección de paciente existente.

RESPUESTA MODELO (aprobada por Dra. Laura Delgado):
"Entiendo, lamento que hayas tenido una mala experiencia previa. En estos casos
lo mejor es evaluar bien qué ocurrió y qué opciones reales hay antes de avanzar.
Si tenés estudios previos, podés traerlos a la consulta.
¿Querés que coordinemos una evaluación?"
```

### Cambio 2: Trigger en F1 (MODIFICAR línea 9515)

Agregar los nuevos triggers a F1:

```python
TRIGGER: "no me fue bien", "mala experiencia", "me hicieron mal", "fui a otro y...",
         "me arruinaron", "no confío", "me hice [tratamiento] y me fue mal",
         "en otro lugar/dentista/profesional", "no me resultó", "no funcionó"
```

### Cambio 3: Respuesta modelo en F1 (MODIFICAR línea 9517)

Agregar la respuesta modelo de Laura como referencia dentro de F1, después del M3 existente:

```python
RESPUESTA MODELO (cuando el tratamiento fue en otro lugar o no se especifica):
"Entiendo, lamento que hayas tenido una mala experiencia previa. En estos casos
lo mejor es evaluar bien qué ocurrió y qué opciones reales hay antes de avanzar.
Si tenés estudios previos, podés traerlos a la consulta.
¿Querés que coordinemos una evaluación?"
```

## Testing Strategy

No hay tests automatizados para el system prompt (es texto interpretado por el LLM). La verificación se hace con escenarios manuales:

| Escenario | Entrada | Resultado esperado |
|-----------|---------|-------------------|
| Happy path | "me hice implantes y me fue mal" | NO menciona "historial con la clínica". Aplica F1. |
| En otro lado | "me hice implantes en otro lugar y me fue mal" | NO activa migración. Aplica F1. |
| Paciente real | "tengo un turno pendiente con la doctora" | SÍ activa migración. Deriva a equipo. |
| Paciente real 2 | "la doctora me dijo que vuelva a control" | SÍ activa migración. |
| Experiencia externa | "fui a otro dentista y me trataron mal" | NO activa migración. Aplica F1. |
| Sin especificar | "no me fue bien con implantes" | NO activa migración. Aplica F1 por neutralidad. |

## Migration / Rollout

No requiere migración. Rollback: revertir los 3 cambios de texto.

## Open Questions

Ninguna.
