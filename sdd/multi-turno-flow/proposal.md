# Proposal: Multi-turno flow in system prompt

## Intent

Cuando un paciente YA tiene un turno agendado y pide OTRO turno (para otro tratamiento), el agente no tiene instrucciones claras. Improvisa, ofrece el mismo horario, se enreda. Se necesita un nuevo PASO 3b que cubra este flujo.

## Scope

### In Scope
1. Agregar **PASO 3b: PACIENTE CON TURNO EXISTENTE** entre PASO 3 y PASO 4
2. Cubrir: reconocer turno existente, validar que el nuevo horario no sea el mismo, permitir mismo día si distinta hora

### Out of Scope
- Arreglar DLD-59 (es otro fix)
- Modificar tools (check_availability, book_appointment)

## Approach

### Cambio único — Agregar PASO 3b (~L9871)

```
PASO 3b: PACIENTE CON TURNO EXISTENTE — Si el paciente YA TIENE un turno agendado
    (aparece "PRÓXIMO TURNO" en su contexto) y pide OTRO turno:
  • Reconocé el turno existente: "Ya tenés turno el [día] a las [hora] para [tratamiento]."
  • El nuevo turno NO puede ser en el mismo horario. Ofrecé otras opciones.
  • Si pide el mismo día pero distinta hora → OK, agendá normalmente si hay disponibilidad.
  • Si pide el mismo día y misma hora → NO, ya está ocupado. Ofrecé otro día/hora.
  • El profesional se define por el tratamiento (PASO 3). No preguntes "querés con el mismo profesional?"
```

## Risks

| Risk | Mitigation |
|------|------------|
| LLM ignore el nuevo paso | Instrucción clara y específica, mismo estilo que PASO 3 |

## Success Criteria
- [ ] Paciente con turno el martes 10 pide blanqueamiento → ofrece opciones SIN incluir martes 10
- [ ] Paciente con turno el martes 10 pide otro el martes 15 → se agenda correctamente
- [ ] Paciente con turno el martes 10 pide otro el viernes → se agenda correctamente
