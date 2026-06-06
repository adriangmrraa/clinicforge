# Proposal: Grupo 2 — Duplicación y contradicciones (B2, B6, B10)

## Intent

Corregir 3 bugs en el system prompt del agente IA (`orchestrator_service/main.py`) que generan comportamiento contradictorio o duplicado en el LLM. Las instrucciones absolutas ("SIEMPRE", "PROHIBIDO") crean tensión entre reglas que el agente no puede resolver, degradando la calidad de las respuestas.

## Scope

### In Scope
- B2: Unificar MENSAJE COMBINADO como subítem de COMPOSICIÓN MULTI-TEMA (líneas 10535-10557)
- B6: Resolver fricción entre "Usá SIEMPRE 'te ayudo a coordinar'" y Anti-Repetición de CTA (líneas 10170, 10564-10573)
- B10: Resolver contradicción address_info "SIEMPRE respondé con la dirección" vs prohibición condicional en horarios (líneas 9826, 10263)

### Out of Scope
- Bugs de otros grupos (B1, B3-B5, B7-B9, B11+)
- Refactor estructural del system prompt
- Validación post-fix con tests de LLM

## Capabilities

### New Capabilities
None — son correcciones de prompt, no nuevas funcionalidades.

### Modified Capabilities
None — no cambian requisitos de especificación existentes.

## Approach

Tres ediciones localizadas en `main.py`. Cada bug se resuelve independientemente:

| Bug | Archivo | Acción |
|-----|---------|--------|
| B2 | main.py (L10535-10557) | Reemplazar 2 secciones solapadas por 1 sección unificada: COMPOSICIÓN MULTI-TEMA con MENSAJE COMBINADO como subítem |
| B6 | main.py (L10170) | Suavizar "Usá SIEMPRE" a "preferí variaciones como..."; agregar EXCEPCIÓN que referencia la regla Anti-Repetición |
| B10 | main.py (L9826) | Agregar "(NUNCA antes de book_appointment exitoso)" a la instrucción absoluta |

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `orchestrator_service/main.py:9826` | Modified | B10: address_info — agregar excepción de timing |
| `orchestrator_service/main.py:10170` | Modified | B6: suavizar wording absoluto + referencia a Anti-Repetición |
| `orchestrator_service/main.py:10535-10557` | Modified | B2: fusionar MENSAJE COMBINADO dentro de COMPOSICIÓN MULTI-TEMA |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| B2: perder matiz del caso específico (slot+OS) al unificar | Low | El subítem preserva el ejemplo exacto y el orden "1. confirmar turno, 2. responder OS" |
| B6: suavizar demasiado el "Usá SIEMPRE" y perder consistencia en cierre consultivo | Low | Se mantiene la recomendación, solo se quita el carácter absoluto |
| B10: error de tipeo al editar string multilínea | Low | Revisar que el join de `address_info` quede sintácticamente válido |

## Rollback Plan

Revertir los 3 cambios con `git checkout -- orchestrator_service/main.py` y re-ejecutar `start.sh`. Son ediciones localizadas sin dependencias externas.

## Dependencies

Ninguna. Cambios autónomos en un solo archivo.

## Success Criteria

- [ ] B2: El prompt tiene UNA sola sección de composición multi-tema (con subítem de mensaje combinado), sin contenido duplicado entre líneas 10535-10557
- [ ] B6: Línea 10170 usa wording no-absoluto ("preferí variaciones como...") y referencia explícita a la Anti-Repetición
- [ ] B10: Línea 9826 incluye "(NUNCA antes de book_appointment exitoso)" como excepción de timing
- [ ] No hay regresiones sintácticas — el archivo mantiene su estructura de f-string multilínea
