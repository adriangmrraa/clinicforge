# Proposal: Exclude patient's own appointments from check_availability slots

## Intent

Cuando un paciente ya tiene un turno agendado y pide un NUEVO turno para otro tratamiento, `check_availability` le ofrece el mismo horario donde ya está ocupado. Esto ocurre porque el sistema marca slots ocupados por profesional, no por paciente. Se necesita que los turnos existentes del paciente bloqueen ese horario para TODOS los profesionales.

## Scope

### In Scope
1. Preservar `patient_id` después del patient lookup en `check_availability` (~L1708)
2. Fetch de appointments del paciente para el `target_date` después del busy_map actual (~L2385)
3. Marcar esos slots en TODOS los profesionales del `busy_map`

### Out of Scope
- Refinar DLD-59 en `book_appointment` (se puede hacer después)
- Modificar `generate_free_slots`
- Modificar `book_appointment`

## Approach

### Cambio 1 — Preservar patient_id (~L1708)

Donde ya existe `patient_row`, guardar `_ca_patient_id`:

```python
if patient_row:
    _ca_patient_id = patient_row["id"]  # ← NUEVO
    if patient_row["assigned_professional_id"]:
        ...
```

### Cambio 2 — Fetch appointments del paciente (~L2385, después del busy_map de appointments)

Después de procesar todos los appointments existentes en busy_map, y DESPUÉS de agregar global_busy (L2388), buscar los turnos del paciente:

```python
# Patient self-conflict guard: if patient already has an appointment at a time,
# block that time for ALL professionals (patient can't be in two places at once)
if _ca_patient_id:
    try:
        patient_apts = await db.pool.fetch(
            """SELECT appointment_datetime as start, duration_minutes
               FROM appointments
               WHERE tenant_id = $1 AND patient_id = $2
                 AND status IN ('scheduled', 'confirmed')
                 AND (appointment_datetime < $4
                      AND (appointment_datetime + interval '1 minute' * COALESCE(duration_minutes, 60)) > $3)""",
            tenant_id, _ca_patient_id, start_day, end_day,
        )
        for pa in patient_apts:
            it = pa["start"].astimezone(get_active_tz())
            dur = pa["duration_minutes"] or 60
            if dur <= 0: dur = 30
            end_it = it + timedelta(minutes=dur)
            check = it.replace(second=0, microsecond=0)
            while check < end_it:
                hm = check.strftime("%H:%M")
                for pid in busy_map:
                    busy_map[pid].add(hm)
                check += timedelta(minutes=15)
            # Also mark 30-min boundaries
            boundary = it.replace(minute=(it.minute//30)*30, second=0, microsecond=0)
            while boundary < end_it:
                hm = boundary.strftime("%H:%M")
                for pid in busy_map:
                    busy_map[pid].add(hm)
                boundary += timedelta(minutes=30)
    except Exception as e:
        logger.warning(f"📅 patient conflict check skipped: {e}")
```

### ¿Por qué este lugar?

- DESPUÉS del busy_map de appointments existentes (L2385) → los datos ya están disponibles
- DESPUÉS de global_busy (L2388) → no pisar slots que ya estaban ocupados globalmente
- ANTES de chair constraint (L2425) → el chair constraint usa el busy_map ya completo
- ANTES del diagnóstico DIAG FINAL (L2462) → el log mostrará el estado correcto

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `main.py` ~1708 | Nuevo | Guardar `_ca_patient_id = patient_row["id"]` |
| `main.py` ~2389-2420 | Nuevo | Bloque de patient conflict guard |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| patient_id no existe (paciente nuevo, sin registro) | Bajo | Guard con `if _ca_patient_id:` |
| TypeError si busy_map cambia estructura | Bajo | Se itera `busy_map` con `for pid in busy_map` — no asume keys |
| Romper chair constraint | Bajo | El bloque se agrega ANTES del chair constraint, así que el chair usa el busy_map completo |
| Romper DLD-59 | Bajo | DLD-59 se mantiene intacto. Es un safety net adicional |
| Performance: query extra por cada check_availability | Medio | Una query simple con index por patient_id. Mismo patrón que chair constraint (L2429) |

## Success Criteria
- [ ] Paciente con turno a las 10:00 pide nuevo turno → check_availability NO ofrece 10:00
- [ ] Paciente con turno a las 10:00 con Eli → Laura aparece libre a las 10:00 para OTROS pacientes
- [ ] Paciente puede tener dos turnos el mismo día en diferentes horarios
