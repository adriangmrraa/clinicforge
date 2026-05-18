# Exploration: check_availability must exclude patient's own existing appointments

## Current State

### El problema (evidenciado en prueba del 18/05)

1. Paciente agenda endodoncia con Eli → **Martes 19/05 10:00** ✅
2. Paciente pide turno para blanqueamiento
3. `check_availability` ofrece **Martes 19/05 10:00** de vuelta ← **MAL, el paciente ya tiene turno ahí**
4. Paciente dice "ya tengo un turno a las 10" y pide viernes 15:00
5. Agente dice "no pude dejarlo confirmado... no había disponibilidad" ← **MAL, el viernes 15:00 sí estaba libre**
6. Paciente insiste → finalmente agenda viernes 15:00 ✅

### Causa raíz: 2 bugs

#### Bug 1 — busy_map se organiza por profesional, no por paciente

`check_availability` construye `busy_map[professional_id] = set()`. Cuando el paciente ya tiene turno con Eli a las 10:00, ese slot se marca ocupado SOLO para Eli. Laura está libre → slot 10:00 se ofrece.

**No existe el concepto de "el paciente ya está ocupado a esta hora, no importa con qué profesional".**

#### Bug 2 — DLD-59 en book_appointment es por fecha, no por hora

La guardia existente (línea 3659-3674) chequea si el paciente ya tiene turno en la **misma fecha**, no en el mismo horario. Esto es incorrecto porque:
- Si el paciente tiene turno a las 10:00 y pide otro a las 15:00 el mismo día → DLD-59 lo rechazaría (falso positivo)
- Si el paciente tiene turno a las 10:00 con Eli y le ofrecen 10:00 con Laura → DLD-59 lo agarra, pero el daño ya está hecho: el paciente vio un slot inválido

### Arquitectura actual

```
check_availability()
├── Patient lookup: obtiene patient_row (con p.id) solo para assigned_professional_id y deuda
├── ... (derivation, professionals, dates)
├── Fetch appointments: SOLO por professional_id (línea 2256-2267)
│     WHERE tenant_id=$1 AND professional_id=ANY($2) → sin filtro de paciente
├── Build busy_map: marca slots ocupados SOLO para ese professional_id (línea 2359-2381)
├── generate_free_slots: slot libre si ALGÚN profesional está libre (línea 2473-2482)
└── Ofrece slots → puede incluir slots donde el paciente ya está ocupado

book_appointment()
├── DLD-59 (línea 3659-3674): chequea mismo paciente + misma fecha → rechazo
└── Pero es DEMASIADO TARDE y DEMASIADO AMPLIO
```

### Datos sensibles a no romper

| Dato | Dónde | Riesgo |
|------|-------|--------|
| Chair constraint (max_chairs) | Línea 2425-2460 | Marca ocupado para TODOS los profesionales cuando se exceden sillas |
| DLD-59 en book_appointment | Línea 3659-3674 | Protege contra doble agendamiento en mismo día (aunque mal implementado) |
| Multi-silla: paciente con cita 10-11 con Eli, otro paciente puede tener 10-11 con Laura | Todo el sistema | Esto SÍ debe funcionar |
| generate_free_slots: ANY prof free → slot libre | Línea 766-779 | No romper, solo agregar filtro de paciente |
| Patient lookup query | Línea 1680-1707 | Ya trae `p.id` pero no se guarda |

### Lo que NO hay que tocar

- `generate_free_slots` — la lógica de "cualquier profesional libre" es correcta para multi-silla
- `book_appointment` — DLD-59 se puede refinar pero no es el fix principal
- Chair constraint — ya funciona para multi-silla
- Las reglas de derivación, treatment_type_professionals, assigned_professional_id

## Affected Areas
- `orchestrator_service/main.py` ~1680-1725 — Patient lookup: preservar `patient_row["id"]`
- `orchestrator_service/main.py` ~2359-2381 — Busy_map construcción: agregar slots del paciente a TODOS los profesionales

## Approaches

### Approach A (RECOMENDADA): Preservar patient_id y marcar slots en busy_map
1. Guardar `_ca_patient_id` después del patient lookup exitoso (~línea 1708)
2. Después de construir busy_map con appointments existentes (~línea 2385), buscar appointments del paciente y marcar esos slots en TODOS los `busy_map[pid]`
3. No tocar `generate_free_slots` ni `book_appointment`
- **Riesgo**: Bajo — solo agrega slots ocupados. Si patient_id no está disponible, skip.
- **Effort**: Bajo

### Approach B: Modificar DLD-59 para chequear por hora exacta
1. Cambiar DLD-59 de `DATE(...) = DATE(...)` a chequear overlap de horario específico
2. Mover la lógica ANTES de check_availability (en el flujo de booking)
- **Riesgo**: Medio — DLD-59 está en book_appointment, cambiar su lógica puede tener side effects
- **Effort**: Medio

### Approach C: Ambos (A + refinar DLD-59)
1. Approach A para evitar ofrecer slots inválidos
2. Refinar DLD-59 para chequear por hora exacta y no por fecha completa
- **Riesgo**: Medio-Bajo
- **Effort**: Medio

## Recommendation
**Approach A** → Mínimo cambio, máximo impacto. Resuelve el problema de raíz (no ofrecer slots donde el paciente ya está ocupado) sin tocar generate_free_slots ni book_appointment.

## Ready for Proposal
Sí.
