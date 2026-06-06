# Proposal: Corrección de estructura del booking flow — numeración y orden (B1, B3, B7)

## Intent

El flujo de agendamiento en el system prompt tiene 3 bugs de estructura que confunden al LLM: (B1) falta el PASO 5 — el flujo salta de PASO 4c a PASO 6, pero la línea 11006 lo referencia como paso existente; (B3) la sección "SEGUIMIENTO POST-ATENCIÓN" está incrustada entre SERVICIOS DEL EQUIPO y el inicio del booking flow, cuando debería ir al final; (B7) hay dos secciones llamadas "PASO 1" (FAQ en línea 10474 y SALUDO en línea 10584), lo que genera colisión semántica.

## Scope

### In Scope
- B1: Crear PASO 5 con validación pre-booking (verificar datos del paciente, manejar `[INTERNAL_DEBT]`)
- B3: Mover sección POST-ATENCIÓN (líneas 10511-10520) al final del prompt, después de PASO 10
- B7: Renombrar "PASO 1 — FAQs" (línea 10474) a "SECCIÓN FAQ — VOZ OFICIAL"

### Out of Scope
- NO renumerar pasos existentes (mantener PASO 1..10 con salto 4c→6)
- NO cambiar lógica de backend, tools ni schemas de DB
- NO modificar contenido de la sección POST-ATENCIÓN (solo moverla)
- NO tocar el GREETING (ya está bien definido en 3 variantes)

## Capabilities

### New Capabilities
- None — esta propuesta no introduce nuevas capacidades, solo corrige estructura del prompt existente

### Modified Capabilities
- None — cambios puramente estructurales, no modifican comportamiento a nivel de spec

## Approach

### B1 — Crear PASO 5 (insertar entre PASO 4c y PASO 6, ~línea 10833)
Contenido del nuevo paso:
```
PASO 5: VALIDACIÓN PRE-BOOKING — Antes de agendar, verificá:
• ¿El CONTEXTO DEL PACIENTE tiene nombre y DNI? Si falta → volver a PASO 4b.
• ¿check_availability devolvió [INTERNAL_DEBT:...]? Si sí, avisá al paciente del saldo pendiente ANTES de llamar book_appointment. PROHIBIDO bloquear el turno por deuda.
• ¿El paciente confirmó el slot (PASO 4c exitoso)? Si no, no llamar book_appointment.
• Todo OK → ir a PASO 6.
```
Esto resuelve la referencia en línea 11006 que espera que PASO 5 exista.

### B3 — Mover POST-ATENCIÓN (líneas 10511-10520 → después de PASO 10 ~línea 10921)
- Extraer bloque `SEGUIMIENTO POST-ATENCIÓN (PROTOCOLO ESTRICTO)` (10 líneas)
- Insertarlo después de `PASO 10: SEGUIMIENTO` (línea 10921), antes de `INSTRUCCIONES DE TRATAMIENTO`

### B7 — Renombrar PASO 1 de FAQ (línea 10474)
- Cambiar `PASO 1 — FAQs PARA TODO LO DEMÁS (VOZ OFICIAL):` → `SECCIÓN FAQ — VOZ OFICIAL:`

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `main.py` L10474 | Modified | Renombrar "PASO 1 — FAQs" → "SECCIÓN FAQ — VOZ OFICIAL" |
| `main.py` L10511-L10520 | Moved | POST-ATENCIÓN → después de PASO 10 (L10921) |
| `main.py` L10833 | New | Insertar PASO 5 entre PASO 4c y PASO 6 |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM ignore PASO 5 por estar en medio del flujo | Low | PASO 5 está donde el flujo lo necesita — entre 4c y 6. Ya hay referencias existentes que lo esperan |
| POST-ATENCIÓN movido al final reduzca adherencia | Low | Es protocolo post-consulta, no afecta booking. Al final del prompt aprovecha recency bias del LLM |
| Renombrar FAQ rompa referencia en otros pasos | Low | Ningún paso referencia "PASO 1 — FAQs". Solo se autodenomina así |

## Rollback Plan

Revertir los 3 cambios en `main.py`:
1. Eliminar bloque PASO 5 insertado
2. Mover POST-ATENCIÓN de vuelta a línea 10511
3. Restaurar "PASO 1 — FAQs" en línea 10474
Sin migraciones, sin cambios de schema, sin dependencias externas.

## Dependencies

Ninguna. Son cambios de texto plano sobre el system prompt de `main.py`.

## Success Criteria

- [ ] B1: PASO 5 existe en el prompt con validación pre-booking (deuda + datos + slot confirmado)
- [ ] B1: Línea 11006 ("NO repetir PASOS 2, 2b, 3 ni 5") es consistente con un paso que ahora existe
- [ ] B3: "SEGUIMIENTO POST-ATENCIÓN" aparece después de PASO 10, no entre SERVICIOS DEL EQUIPO y FLUJO DE AGENDAMIENTO
- [ ] B7: Solo UNA sección llamada "PASO 1" existe en el prompt (la de SALUDO)
- [ ] B7: La sección FAQ se llama "SECCIÓN FAQ — VOZ OFICIAL"
- [ ] No hay cambios semánticos en el contenido del prompt — solo estructura y numeración
