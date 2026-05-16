# Design: Bug B2 — OSDE + implantes genera expectativa falsa de cobertura

## Technical Approach

4 cambios de texto en `build_system_prompt()` de `main.py`. Sin cambios en DB, tools, ni frontend. Los datos de `coverage_by_treatment` ya existen en DB y `_format_insurance_providers` ya los inyecta en el prompt. El problema es que 4 reglas del prompt le impiden al LLM usar esa información correctamente.

## Architecture Decisions

### Decision: No modificar `check_insurance_coverage` tool

**Choice**: No tocar la tool. Solo cambiar las reglas del prompt que interpretan su output.

**Rationale**: La tool devuelve `status: "accepted"` correctamente. El problema es que el prompt dice "si accepted → decí que sí" sin mirar el tratamiento específico. Los datos de cobertura por tratamiento YA están en el prompt via `_format_insurance_providers`. El LLM puede cruzarlos.

### Decision: No modificar `_format_insurance_providers`

**Choice**: Dejarlo como está. Ya genera el bloque correcto con cubiertos/no cubiertos.

**Rationale**: El formateador funciona perfecto. El problema es que la regla de línea 10025 le dice al LLM "PROHIBIDO listar tratamientos incluidos/excluidos", contradiciendo los datos que el formateador pone en el prompt.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` | Modify | 4 cambios de texto en `build_system_prompt()` |

### Cambio A — CAMINO 1 (línea 10005)

**Antes:**
```
  CAMINO 1 — TIENE OS ACEPTADA: Llamá check_insurance_coverage con el nombre de la OS. Si está aceptada → confirmar por nombre ("Sí, trabajamos con [nombre]") + avisar posible coseguro + continuar con agendamiento.
```

**Después:**
```
  CAMINO 1 — TIENE OS ACEPTADA: Llamá check_insurance_coverage con el nombre de la OS. Si está aceptada → confirmar por nombre. Si el paciente ya especificó un tratamiento, verificá en el bloque OBRAS SOCIALES del prompt si ese tratamiento está en "NO cubiertos". Si lo está, informalo: "Sí, la consulta puede ser por [nombre] 😊 En cuanto a [tratamiento], eso se define después de la evaluación según cobertura, particular o reintegro."
```

### Cambio B — Respuesta para accepted (línea 10015)

**Antes:**
```
• Si status="accepted": "Sí, trabajamos con [provider_name] 😊" + si has_copay: "Según tu plan puede haber coseguro, se abona el día de la consulta."
```

**Después:**
```
• Si status="accepted":
    - Si el paciente preguntó por un tratamiento específico → verificá en el bloque OBRAS SOCIALES si ese tratamiento está listado como "NO cubiertos". Si lo está: "Sí, la consulta puede ser por [provider_name] 😊 En cuanto a [tratamiento], eso se define después de la evaluación, según cobertura, particular o reintegro."
    - Si el paciente NO preguntó por un tratamiento específico → "Sí, trabajamos con [provider_name] 😊" + si has_copay: "Según tu plan puede haber coseguro, se abona el día de la consulta."
```

### Cambio C — Eliminar prohibición contradictoria (línea 10025)

**Antes:**
```
• PROHIBIDO confirmar qué cubre o no cubre cada obra social. PROHIBIDO listar tratamientos incluidos/excluidos.
```

**Después:**
```
• PERMITIDO informar cobertura basada en los datos del bloque OBRAS SOCIALES del prompt. Si un tratamiento está explícitamente listado como "NO cubiertos", podés informarlo claramente al paciente. PROHIBIDO inventar cobertura o hacer afirmaciones sin datos en el prompt.
```

### Cambio D — Reemplazar anti-ejemplo (línea 10029)

**Antes:**
```
• REGLA ANTI-REPETICIÓN OS/COSEGURO: Si ya le informaste al paciente sobre su obra social y coseguro en esta conversación, NO volver a llamar check_insurance_coverage ni repetir el mismo bloque. Si vuelve a preguntar, respondé SOLO la parte específica que pregunta, reformulando brevemente. Ejemplo: paciente pregunta "cuánto es el coseguro?" después de que ya le dijiste → NO repetir "Sí, trabajamos con OSDE para consultas y tratamientos quirúrgicos." → SOLO responder "El coseguro varía según tu plan, se confirma en la clínica el día de la consulta."
```

**Después:**
```
• REGLA ANTI-REPETICIÓN OS/COSEGURO: Si ya le informaste al paciente sobre su obra social y coseguro en esta conversación, NO volver a llamar check_insurance_coverage ni repetir el mismo bloque. Si vuelve a preguntar, respondé SOLO la parte específica que pregunta, reformulando brevemente. Ejemplo: paciente pregunta "¿cuánto es el coseguro?" después de que ya le informaste → "El coseguro varía según tu plan, se confirma en la clínica el día de la consulta."
```

## Data Flow (corregido)

```
Paciente: "me cubre el implante con OSDE?"
                    │
                    ▼
    1. check_insurance_coverage("OSDE")
       → DB: OSDE status="accepted"
       → Tool devuelve {"status": "accepted", ...}
                    │
                    ▼
    2. LLM lee NUEVA regla (10015):
       "Si accepted + paciente preguntó tratamiento
        específico → verificar bloque OBRAS SOCIALES"
                    │
                    ▼
    3. LLM busca "IMPLANTE" en el bloque OBRAS SOCIALES
       → Lo encuentra en "NO cubiertos"
                    │
                    ▼
    4. LLM lee NUEVA regla (10025):
       "PERMITIDO informar si hay datos. Prohibido inventar."
                    │
                    ▼
    5. RESPUESTA CORRECTA:
       "Sí, la consulta puede ser por OSDE 😊
        En cuanto a los implantes, eso se define después
        de la evaluación, según cobertura, particular o reintegro."
```

## Testing Strategy

Escenarios manuales de verificación (no hay tests automatizados para prompt text):

| Escenario | Input | Expected |
|-----------|-------|----------|
| A | "me cubre el implante con OSDE?" | NO dice "sí" genérico. Distingue consulta vs implante. |
| B | "la consulta me cubre con OSDE?" | "Sí, la consulta puede ser por OSDE" |
| C | "tengo OSDE" (sin tratamiento) | Confirma OSDE aceptada, ofrece turno |
| D | "Sí, trabajamos con OSDE para..." | NO aparece esa frase en la respuesta |

## Migration / Rollout

No requiere migración. Rollback: revertir los 4 cambios.

## Open Questions

Ninguna.
