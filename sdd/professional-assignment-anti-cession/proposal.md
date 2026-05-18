# Proposal: Agent must respect professional assignment and resist cession

## Intent

El agente cede cuando el paciente insiste en un profesional que NO hace ese tratamiento (ej: endodoncia con Laura Delgado). Además, ignora el `assigned_professional_id` del paciente. Se necesita: (1) PASO 3 debe priorizar assigned_professional_id, (2) regla anti-cesión, (3) regla en CONTEXTO DEL PACIENTE.

## Scope

### In Scope
1. Reestructurar **PASO 3**: assigned_professional_id → treatment_type_professionals → derivation_rules → fallback
2. Agregar **regla anti-cesión**: si paciente insiste con profesional que no hace el tratamiento, mantenerse firme
3. Agregar **regla en CONTEXTO DEL PACIENTE** para "PROFESIONAL ASIGNADO"

### Out of Scope
- Modificar `book_appointment` para auto-asignar professional_id
- Modificar tools (`check_availability`, `list_services`)
- CASO 1 (cobertura ISSN) — ya resuelto

## Approach

### Cambio 1 — Reestructurar PASO 3 (~L9812-9826)
Nuevo orden de precedencia:

```
PASO 3: PROFESIONAL ASIGNADO — ORDEN DE PRECEDENCIA:

  1. PROFESIONAL ASIGNADO DEL PACIENTE (si aparece en CONTEXTO DEL PACIENTE):
     → Usá ESE profesional. No preguntes preferencia. No importa el tratamiento.
     → El paciente es habitual de ese profesional.
  
  2. PROFESIONALES DEL TRATAMIENTO (vía list_services/get_service_details):
     → Solo los profesionales designados para este tratamiento pueden realizarlo.
     → Si tiene UNO → nombrá solo ese. Si tiene VARIOS → ofrecé opciones.
     → Si NO tiene → seguí al paso 3.
  
  3. REGLAS DE DERIVACIÓN (bloque DERIVACIÓN DE PACIENTES):
     → Si dice "equipo" → "nuestro equipo odontológico" sin nombres.
     → Si dice profesional específico → nombrá solo ese.
  
  4. FALLBACK → sin filtro de profesional.
  
  REGLA ANTI-CESIÓN (CRÍTICA):
  Si el paciente insiste en atenderse con un profesional que NO está designado
  para ese tratamiento (ni por assigned_professional_id, ni por profesionales
  del tratamiento, ni por reglas de derivación):
  → "Ese tratamiento lo realiza [profesional/equipo correcto]. ¿Querés que te
     agende un turno con [profesional/equipo correcto]?"
  → NO cedas. NO digas que lo hace si no lo hace.
```

### Cambio 2 — Agregar regla en CONTEXTO DEL PACIENTE (~L9034)
Agregar al bloque de REGLAS DE USO DEL CONTEXTO DEL PACIENTE:

```
• Si tiene "PROFESIONAL ASIGNADO" → ESE es su profesional de cabecera.
  Usalo en check_availability sin preguntar preferencia. Prioridad ABSOLUTA
  sobre cualquier otra regla de derivación.
```

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `main.py` ~9812-9826 | Modified | PASO 3: nuevo orden + anti-cesión |
| `main.py` ~9034-9047 | Modified | Agregar regla para PROFESIONAL ASIGNADO |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Paciente con assigned_professional_id que no trabaja ese día | Bajo | check_availability ya maneja profesionales cerrados (auto-advance) |
| Regla anti-cesión muy rígida para casos válidos | Bajo | Solo aplica cuando el profesional NO está designado para el tratamiento en NINGUNA fuente |

## Rollback Plan
Revertir cambios en `main.py`. Sin migraciones.

## Success Criteria
- [ ] Paciente nuevo pregunta por endodoncia → agente responde "equipo odontológico"
- [ ] Paciente insiste "quiero con Laura" → agente NO cede, repite que es con equipo
- [ ] Paciente con assigned_professional_id=Laura pregunta por cualquier tratamiento → agente ofrece con Laura
