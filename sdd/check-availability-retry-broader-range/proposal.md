# Proposal: check_availability retry with broader date range

## Intent

Cuando `check_availability` devuelve 0 slots, el agente no tiene instrucción de reintentar con un rango de fechas más amplio. Tampoco tiene instrucción de qué hacer cuando `book_appointment` falla por disponibilidad. Se necesita una instrucción de retry en PASO 4.

## Scope

### In Scope
1. Agregar instrucción en **PASO 4**: si check_availability devuelve 0 slots → reintentar con search_mode='week' o 'month'
2. NO reintentar con otro profesional — el profesional se define por el tratamiento

### Out of Scope
- Modificar tools (check_availability, book_appointment)
- Modificar lógica interna de retry en check_availability

## Approach

### Cambio único — Modificar PASO 4 (~L9872)

```
PASO 4: CONSULTAR DISPONIBILIDAD — Llamá 'check_availability' con treatment_name y, si el paciente eligió profesional, con professional_name.
  RAZONAMIENTO DE FECHA (...)
  
  SI NO HAY DISPONIBILIDAD:
  • Si check_availability devuelve 0 slots o mensaje de "no encontré":
    → Llamá check_availability de NUEVO con search_mode='week' o 'month' para ampliar el rango.
    → NO cambies de profesional. El profesional lo define el tratamiento.
  • Si book_appointment falla con "no hay disponibilidad":
    → Ofrecé otro horario de los que ya tenías. No inventes.
  • Si sigue sin haber disponibilidad después de intentar:
    → Informá al paciente: "No encontré disponibilidad para las próximas semanas.
       ¿Querés que te avisemos si se libera un turno?"
```

## Risks

| Risk | Mitigation |
|------|------------|
| Loop infinito de retry | Solo 1 reintento, no más |
| Agente ofrezca otro profesional | Instrucción explícita: NO cambiar de profesional |

## Success Criteria
- [ ] Paciente pide fecha sin disponibilidad → agente reintenta con semana/mes
- [ ] Si reintento también falla → agente informa y ofrece lista de espera
- [ ] Agente NO cambia de profesional en el reintento
