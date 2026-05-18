# Proposal: CASO 1 — Fix agent deriving instead of booking after coverage query

## Intent

El agente responde correctamente sobre cobertura external_derivation (ISSN→CIMO), pero en vez de continuar con el agendamiento cuando el paciente ya eligió día, deriva al equipo humano. El fix elimina la contaminación semántica "Derivar" en el prompt y agrega instrucciones claras post-respuesta de cobertura.

## Scope

### In Scope
1. Renombrar `"Derivación externa:"` → `"Cobertura con centro externo:"` en `_format_insurance_providers()`
2. Cambiar `"→ Derivar a {target}"` → `"→ Centro externo: {target}"`
3. Agregar instrucción en respuesta de `check_insurance_coverage` para external_derivation: si paciente ya eligió día → continuar booking

### Out of Scope
- Modificar tool `derivhumano`
- Cambiar datos de obras sociales en DB
- Refactor general del system prompt
- CASO 2 (endodoncia/derivación) — se maneja por separado

## Approach

### Cambio 1 — Renombrar en `_format_insurance_providers()` (~línea 8400-8409)
```python
# Antes:
lines.append("Derivación externa:")
lines.append(f'  • {name} → Derivar a {target}. Mensaje: "{msg}"')

# Después:
lines.append("Cobertura con centro externo:")
lines.append(f'  • {name} → Centro externo: {target}. Mensaje: "{msg}"')
```

### Cambio 2 — Instrucción post-respuesta (~línea 10026)
Agregar al final del bloque de `external_derivation`:
```
  IMPORTANTE: Si el paciente ya había elegido un día/horario antes de preguntar 
  por cobertura, continuá con el agendamiento después de informar. Pedí nombre 
  y DNI para agendar. No derivar a humano solo por external_derivation.
```

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `main.py` ~8400 | Modified | Renombrar "Derivación externa" |
| `main.py` ~8408 | Modified | Cambiar "Derivar a" → "Centro externo" |
| `main.py` ~10026 | Modified | Agregar instrucción post-respuesta |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM ignore nueva instrucción | Low | Prompt ya tiene reglas que el LLM respeta ("PROHIBIDO informar montos") |
| Renombrar rompa otras referencias | Low | Solo cambia texto en prompt, no lógica |

## Rollback Plan
Revertir los cambios en `main.py`. Sin migraciones ni cambios de schema.

## Success Criteria
- [ ] Paciente con dolor elige miércoles y pregunta por ISSN → agente responde sobre CIMO y CONTINÚA pidiendo nombre/DNI
- [ ] No se llama derivhumano solo por external_derivation
- [ ] Respuesta sobre ISSN/CIMO sigue siendo correcta
