# Exploration: CASO 1 — Agent derives instead of booking after coverage query

## Current State

### El problema
En CASO 1 de pruebas (18/05), paciente con dolor elige miércoles, pregunta por cobertura ISSN. El agente responde correctamente sobre CIMO pero inmediatamente deriva al paciente al equipo humano (`derivhumano`) en vez de continuar pidiendo nombre/DNI para agendar.

### Causa raíz: 3 factores encadenados

#### Factor 1 — Contaminación semántica "Derivar"
En `_format_insurance_providers()` (main.py ~8400), el prompt usa:
```
Derivación externa:
  • ISSN → Derivar a CIMO. Mensaje: "..."
```
La palabra "Derivar" asocia semánticamente con `derivhumano`. No hay instrucción que diga: "external_derivation es solo información de cobertura, no es motivo para llamar derivhumano".

#### Factor 2 — Sin instrucción post-respuesta
En la sección de respuestas `check_insurance_coverage` (~10026), la respuesta para `external_derivation` solo dice qué texto usar. No dice qué hacer DESPUÉS (continuar booking si el paciente ya eligió día).

#### Factor 3 — Regla catch-all
Linea ~9064: "Si por cualquier razón no podés procesar, entender o continuar → llamá derivhumano". El agente, en estado ambiguo post-consulta de cobertura, cae acá.

### Lo que NO hay que tocar
- La respuesta sobre ISSN/CIMO es correcta y está bien
- La tool `derivhumano` en sí está bien
- No se necesita cambiar datos de obras sociales en DB

## Affected Areas
- `orchestrator_service/main.py` ~8400 — `_format_insurance_providers()` texto "Derivación externa"/"Derivar a"
- `orchestrator_service/main.py` ~10026 — Sección respuestas `check_insurance_coverage` external_derivation

## Approaches

### Approach 1: Solo rename + regla de comportamiento
**Qué**: Cambiar "Derivación externa" → "Cobertura con centro externo" y "Derivar a" → "Centro externo:". Agregar instrucción: "Si paciente ya eligió día → continuar agendamiento".
- **Pros**: Mínimo cambio, elimina contaminación semántica
- **Cons**: No cubre todos los casos donde el agente podría derivar incorrectamente
- **Effort**: Bajo

### Approach 2: Approach 1 + instrucción explícita en check_insurance_coverage
**Qué**: Además del rename, agregar al final de la respuesta de external_derivation una instrucción de qué hacer después.
- **Pros**: Cubre el flujo específico donde ocurrió el bug
- **Cons**: Ligeramente más cambios
- **Effort**: Bajo

## Recommendation
**Approach 2** — Es el que cubre exactamente el bug detectado sin sobregeneralizar.

## Ready for Proposal
Sí. El cambio es puramente textual en el system prompt.
