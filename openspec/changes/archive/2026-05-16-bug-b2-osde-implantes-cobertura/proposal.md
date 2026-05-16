# Proposal: Bug B2 — OSDE + implantes genera expectativa falsa de cobertura

## Intent

El bot Paula responde "Sí, trabajamos con OSDE 😊" cuando un paciente pregunta si OSDE cubre implantes. Esto genera expectativa falsa porque OSDE NO cubre implantes automáticamente. El bot debe distinguir entre "la consulta puede ser por OSDE" (correcto) y "el implante está cubierto" (falso), usando los datos de `coverage_by_treatment` que ya existen en la DB.

## Scope

### In Scope

4 cambios de texto en el prompt (`build_system_prompt()` en `main.py`):

1. **Línea 10015**: Modificar respuesta para `status="accepted"` para que no diga "Sí" genérico sino que verifique si el tratamiento específico está cubierto según `coverage_by_treatment`
2. **Línea 10025**: Eliminar la prohibición contradictoria "PROHIBIDO confirmar qué cubre o no cubre" y reemplazarla con una regla que PERMITA informar cobertura cuando los datos existen
3. **Línea 10029**: Reemplazar el anti-ejemplo "Sí, trabajamos con OSDE para consultas y tratamientos quirúrgicos" con un ejemplo correcto
4. **Línea 10005 (CAMINO 1)**: Ajustar el flujo de modalidad para que distinga entre "OS aceptada para consulta" vs "tratamiento no cubierto"

### Out of Scope

- Cambios en la tool `check_insurance_coverage` (no necesita cambios — los datos ya están en el prompt via `_format_insurance_providers`)
- Cambios en `_format_insurance_providers` (ya funciona correctamente)
- Cambios en DB o modelos
- ISSN como provider (es otro bug)
- Derivaciones al equipo (es otro grupo de bugs)

## Approach

4 modificaciones de texto en `build_system_prompt()`:

### Cambio A — Línea 10015: Respuesta diferenciada por tratamiento

Reemplazar el "Sí" genérico con una regla que cruce el status de la OS con el bloque de cobertura del prompt:

```
• Si status="accepted":
  - Si el tratamiento específico que consulta el paciente aparece en la sección "NO cubiertos" de {provider_name} en el bloque OBRAS SOCIALES del prompt → "Sí, trabajamos con {provider_name} para la consulta de evaluación. En cuanto a [tratamiento], no tiene cobertura directa. Se puede realizar de forma particular y te damos documentación para reintegro si corresponde. ¿Querés que te ayude a coordinar?"
  - Si el tratamiento no está especificado o está en "Cubiertos" → "Sí, trabajamos con {provider_name} 😊"
```

### Cambio B — Línea 10025: Eliminar contradicción

Reemplazar:
```
PROHIBIDO confirmar qué cubre o no cubre cada obra social. PROHIBIDO listar tratamientos incluidos/excluidos.
```
Por:
```
PERMITIDO informar cobertura basada en los datos: si un tratamiento está explícitamente listado como "NO cubiertos" en el bloque OBRAS SOCIALES del prompt, podés informárselo al paciente. PROHIBIDO inventar cobertura o hacer afirmaciones sin datos en el prompt.
```

### Cambio C — Línea 10029: Reemplazar ejemplo problemático

Reemplazar el anti-ejemplo con un ejemplo real correcto:
```
Ejemplo correcto: paciente pregunta "¿cubre implantes OSDE?" → "Sí, la consulta puede ser por OSDE 😊 En cuanto a los implantes, eso se define después de la evaluación. Se coordina según cobertura, particular o reintegro."
```

### Cambio D — Línea 10005: Ajustar CAMINO 1

Agregar matiz al CAMINO 1 para que no asuma cobertura total:
```
CAMINO 1 — TIENE OS ACEPTADA: Llamá check_insurance_coverage con el nombre de la OS. Si está aceptada → confirmar por nombre. Pero si el paciente ya especificó un tratamiento, verificá en el bloque OBRAS SOCIALES si ese tratamiento está cubierto. Si no lo está, informalo.
```

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` — `build_system_prompt()` | Modified | 4 cambios de texto, ~20 líneas |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Regla muy permisiva hace que el bot invente cobertura | Baja | Se reemplaza "PROHIBIDO confirmar" por "PERMITIDO si hay datos en el prompt. PROHIBIDO inventar." |
| Bot no encuentra el tratamiento en la lista y se confunde | Baja | La regla tiene fallback: si no está listado, deriva a evaluación |

## Rollback Plan

Revertir las 4 líneas modificadas.

## Dependencies

Ninguna. Cambios de texto autónomos.

## Success Criteria

- [ ] Paciente pregunta "me cubre el implante con OSDE?" → bot NO responde "Sí" genérico
- [ ] Bot distingue entre "la consulta puede ser por OSDE" y "el implante no está cubierto automáticamente"
- [ ] Bot NO repite "trabajamos con OSDE para consultas y tratamientos quirúrgicos"
- [ ] Bot usa los datos del bloque OBRAS SOCIALES del prompt para informar cobertura
