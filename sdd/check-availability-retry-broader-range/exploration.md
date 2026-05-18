# Exploration: check_availability retry with broader date range

## Current State

### El problema (evidenciado en prueba del 18/05)
Paciente pide viernes 15:00 para blanqueamiento. Agente dice "No pude dejarlo confirmado... no había disponibilidad". Paciente insiste y finalmente agenda bien. Algo falló en el medio.

### Causa
Hay **2 posibles causas**:

#### Causa 1 — PASO 4 dice "UNA vez"
El prompt dice: "Llamá check_availability UNA vez con treatment_name". Si devuelve 0 slots, el agente no tiene instrucción de reintentar. No puede expandir el rango de búsqueda.

#### Causa 2 — El agente no interpreta bien cuando check_availability devuelve resultado parcial
En el log de la prueba, check_availability devolvió slots para viernes 15:00 (línea 93-94 del log: ofreció viernes 22/05 15:00). Pero después dijo "no pude dejarlo confirmado". Esto sugiere que el problema fue en confirm_slot o book_appointment, no en check_availability. Posiblemente:
- DLD-59 bloqueó por misma fecha? No, era viernes vs martes.
- El profesional no estaba disponible? Posible.
- La tool falló por otro motivo y el agente malinterpretó el error.

### Lo que YA existe
- `pick_representative_slots` ya expande búsqueda hacia adelante si no hay slots suficientes (L1498-1501)
- `search_range_days` ya existe y se calcula según el search_mode
- Escalation (derivation_rules con enable_escalation) ya retry con fallback professional

### Lo que FALTA
- **El prompt no dice "si check_availability devuelve 0 slots, intentá con otro rango de fechas"**
- **El prompt no dice "si book_appointment falla por disponibilidad, intentá de nuevo con otro horario"**

### Regla de negocio
El usuario dijo: "si no hay disponibilidad, reintentar con otro rango de fechas (días diferentes), NO con otro profesional. El profesional se decide por el tratamiento."

## Affected Areas
- `orchestrator_service/main.py` ~9872 (PASO 4) — agregar instrucción de retry

## Approaches

### Approach A: Agregar instrucción en PASO 4
```
PASO 4: CONSULTAR DISPONIBILIDAD — Llamá check_availability con treatment_name y professional_name.
  Si devuelve 0 slots → llamá de nuevo con search_mode='week' o 'month' para ampliar el rango.
  Si sigue sin slots → informá al paciente y ofrecé lista de espera.
  NO cambiar de profesional. El profesional lo define el tratamiento.
```
- **Effort**: Bajo
- **Riesgo**: Bajo

### Approach B: Modificar check_availability internamente para auto-retry
- **Effort**: Medio
- **Riesgo**: Medio (tocar lógica interna)

## Recommendation
**Approach A** — Solo texto en prompt, mismo approach que todos los fixes de esta sesión.

## Ready for Proposal
Sí.
