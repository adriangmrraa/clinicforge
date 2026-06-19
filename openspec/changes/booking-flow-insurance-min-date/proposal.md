# Proposal: Booking Flow Insurance + Min Date

## Intent

El agente (Solo y BookingAgent) debe preguntar cobertura ANTES de `check_availability`, combinar fecha mínima con días de espera de OS, y recordar si ya preguntó. Hoy el BookingAgent no tiene la instrucción ni el tool, el Solo Agent la tiene en orden incorrecto, y falta el flag `insurance_asked`.

## Scope

### In Scope
1. **BookingAgent prompt**: agregar instrucción de preguntar OS antes de `check_availability`
2. **BookingAgent tools**: agregar `check_insurance_coverage` a tool list
3. **SPECIALIST_BLOCKS["booking"]**: agregar `insurance_section` al whitelist
4. **Solo Agent prompt**: mover regla de OS (línea 10487-10490) ANTES del bloque PROACTIVIDAD (línea 10691)
5. **Conversation state**: agregar flag `insurance_asked` + setter helper
6. **Min date + OS wait days combinados**: ambos motores deben considerar `min_appointment_date` + `min_days_wait` juntos

### Out of Scope
- Cambios en tools `check_availability` o `book_appointment`
- Cambios en UI de configuración de fecha mínima
- Cambios en `check_insurance_coverage` tool
- Nuevos tests E2E (unitaria/integración existente alcanza)

## Capabilities

### New Capabilities
None

### Modified Capabilities
- `system-prompt`: C1 "Modalidad de atención (PASO 2c)" se expande para cubrir ambos motores (Solo + BookingAgent), y la regla cambia de posición a ANTES de las reglas de proactividad

## Approach

**A1** (`specialists.py`–BookingAgent prompt): insertar bloque "⚠️ REGLA CRÍTICA: OBRAS SOCIALES" idéntico al Solo Agent (preguntar antes de `check_availability`) en la sección de REGLAS INMUTABLES (después de línea 298, cuando el booking flow arranca).

**A2** (`specialists.py`–tools): agregar `check_insurance_coverage` al array de tools en `_get_tools()` (línea 253).

**A3** (`tenant_context.py`–SPECIALIST_BLOCKS): agregar `"insurance_section"` a la lista `"booking"` (línea 44).

**A4** (`main.py`–Solo Agent prompt): mover el bloque "⚠️ REGLA CRÍTICA: OBRAS SOCIALES Y SEMÁFORO" (actualmente en línea 10487-10490, después de PROACTIVIDAD) a ANTES del bloque "PROACTIVIDAD (LO MÁS IMPORTANTE)" (línea 10691).

**A5** (`conversation_state.py`): agregar helper `set_insurance_asked` y leer `insurance_asked` del payload. Mantener el flag en `_raw_write` merge.

**A6** (ambos prompts): agregar instrucción explícita: "Combiná `min_appointment_date` con los `min_days_wait` de la OS. Si la OS tiene 40 días de espera y la fecha mínima es 16/06, el turno más cercano es 16/06 + 40d."

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `specialists.py` | Modified | BookingAgent prompt + tool list |
| `tenant_context.py` | Modified | SPECIALIST_BLOCKS[booking] |
| `main.py` | Modified | Solo Agent prompt reorder |
| `conversation_state.py` | Modified | Nuevo flag + helper |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| BookingAgent prompt size crece (LLM context) | Low | 5-10 líneas extra, margen amplio |
| `insurance_asked` flag se pierde por TTL | Low | TTL es 30 min — merge existente lo preserva |
| Regla de OS en BookingAgent contradice proactividad | Med | Poner la regla como REQUISITO PREVIO con semántica de gate |
| min_days_wait + min_date combinados confunden al LLM | Med | Instrucción explícita con ejemplo concreto |

## Rollback Plan

Revert commit. Cada cambio (A1-A6) está en archivos separados — revertir por archivo si es necesario.

## Dependencies

None. Todos los cambios son internos al orchestrator_service.

## Success Criteria

- [ ] BookingAgent pregunta OS antes de `check_availability` y tiene el tool disponible
- [ ] BookingAgent recibe `insurance_section` en su contexto
- [ ] Solo Agent pregunta OS ANTES de ejecutar proactividad (no al revés)
- [ ] `insurance_asked` flag persiste en Redis y el agente lo consulta
- [ ] Ambos prompts indican combinar `min_appointment_date` con `min_days_wait`
