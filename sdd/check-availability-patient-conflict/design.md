# Design: Patient self-conflict guard in check_availability

## Technical Approach

2 cambios en `main.py` dentro de la función `check_availability`:
1. Preservar `patient_id` después del patient lookup existente (L~1708)
2. Agregar bloque de patient conflict guard después del busy_map (L~2389) que fetchea los appointments del paciente y marca esos slots en TODOS los profesionales del busy_map

El busy_map es **por request** (se construye cada vez que se llama check_availability para un paciente específico), así que marcar todos los profesionales como ocupados en ese slot solo afecta a la request actual. Cuando otro paciente haga check_availability, su busy_map arranca limpio y los profesionales aparecen libres (excepto por sus propios turnos).

## Architecture Decisions

### Decision: Agregar bloque después de global_busy, antes de chair constraint

**Choice**: Insertar el nuevo bloque entre L2388 (global_busy) y L2425 (chair constraint)
**Rationale**: 
- Después de global_busy → no pisar slots globales
- Antes de chair constraint → el chair usa el busy_map completo
- Antes de generate_free_slots → los slots bloqueados por paciente se excluyen de la oferta
- Entre medio del bloque appointments existentes y generate_free_slots → es el punto natural

### Decision: Usar misma query pattern que appointments existentes

**Choice**: Copiar el mismo SQL pattern de la query de appointments (L2256-2267) pero filtrando por patient_id
**Rationale**: Mismo formato de fechas, misma lógica de overlap, mismo manejo de status. Consistente y predecible.

## Data Flow

```
check_availability("blanqueamiento", "martes 19/05")
  │
  ├── 1. Patient lookup → _ca_patient_id = 19  (NUEVO)
  │
  ├── ... (derivación, profesionales, fechas)
  │
  ├── 2. Fetch appointments → busy_map[eli] = {"10:00", "10:15", "10:30"}
  │
  ├── 3. global_busy → busy_map[eli] += {}, busy_map[laura] += {}
  │
  ├── 4. PATIENT CONFLICT GUARD (NUEVO)
  │     └── Fetch appointments WHERE patient_id=19
  │     └── → turno 10:00-10:30 con Eli
  │     └── busy_map[eli] += {"10:00", "10:15", "10:30"}
  │     └── busy_map[laura] += {"10:00", "10:15", "10:30"}  ← LAURA TAMBIÉN OCUPADA
  │
  ├── 5. Chair constraint (no afectado)
  │
  ├── 6. generate_free_slots
  │     └── 10:00 → Eli ocupado, Laura ocupada → NO SE OFRECE ✅
  │     └── 15:00 → Eli libre, Laura libre → SE OFRECE ✅
  │
  └── 7. Retorna opciones sin 10:00
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` ~1708 | Modify | Guardar `_ca_patient_id` del patient_row |
| `orchestrator_service/main.py` ~2389 | Insert | Bloque patient conflict guard |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Manual | Mismo paciente misma hora distinto prof | Paciente agenda a las 10, pide otro turno → no ofrece 10:00 |
| Manual | Distinto paciente misma hora | Paciente B pide 10:00 → se ofrece si el profesional está libre |
| Manual | Chair constraint + patient conflict | Ambos deben funcionar sin pisarse |

## Migration

No requiere migración.
