# Proposal: B4/B5/B9 — Derivaciones sin hardcode

## Intent

Eliminar el hardcodeo de `{prof_display_full}` (= "la Dra. Laura Delgado") de los CTAs de los flujos emocionales (F1, F8b). Las reglas de derivación ya existen en DB y el PASO 3 del flujo de agendamiento ya las respeta via `list_services`. El problema es que los flujos emocionales bypassan esas reglas con CTAs hardcodeados.

Además, F2 (urgencia/dolor) agenda directo sin escalar al equipo para casos de odontología general.

## Scope

### In Scope

5 cambios en `main.py` (`build_system_prompt()`):

1. **F1 (Mala experiencia)**: Reemplazar CTA `{prof_display_full}` por mención genérica
2. **F8b (Opiniones diferentes)**: Ídem
3. **F2 (Urgencia/Dolor)**: Agregar prohibición de listar profesionales + escalar endodoncia/caries al equipo
4. **Nueva prohibición global**: No decir "Sí, hacemos [tratamiento]" o "Eso entra en [tratamiento]"
5. **Regla en F2**: NO listar profesionales por nombre ("La consulta de urgencia la puede hacer X, Y o Z")

### Out of Scope

- Modificar las reglas de derivación en DB (están correctas)
- Modificar `_format_derivation_rules` (funciona bien)
- Modificar PASO 3 del flujo de agendamiento (funciona bien)
- Los otros 6 usos de `{prof_display_full}` en el prompt (son correctos porque se refieren a servicios de la Dra. Delgado)

## Approach

### Cambio A — F1: CTA sin profesional hardcodeado

**Antes (línea 9538):**
```
M3 — CTA: "Te ayudo a coordinar una evaluación con {prof_display_full}."
```

**Después:**
```
M3 — CTA: "Te ayudo a coordinar una evaluación. El equipo te va a indicar el profesional mas adecuado para tu caso."
```

### Cambio B — F8b: Ídem

**Antes (línea 9607):**
```
M3 — CTA: "Te ayudo a coordinar una evaluación con {prof_display_full}."
```

**Después:**
```
M3 — CTA: "Te ayudo a coordinar una evaluacion. El equipo te va a indicar el profesional mas adecuado para tu caso."
```

### Cambio C — F2: Prohibir listar profesionales + escalar odontología general

Agregar en F2 (después de línea 9548, antes de M3):

```
PROHIBIDO en F2:
  • NO listar profesionales por nombre ("la consulta de urgencia la puede hacer X, Y o Z").
  • NO decir "Sí, hacemos [tratamiento]" ni confirmar el tratamiento.
  • Si el paciente menciona endodoncia, conducto, caries, arreglo, limpieza o
    cualquier odontología general junto con el dolor → NO agendar directo.
    ESCALAR al equipo: "Entiendo, si estas con dolor lo ideal es que el equipo
    evalue tu caso. Te paso con ellos para que te contacten."
```

### Cambio D — Nueva prohibición global en PROHIBICIONES

Agregar en la sección PROHIBICIONES (después de línea 9514):

```
15. PROHIBIDO decir "Sí, hacemos [tratamiento]", "Eso entra en [tratamiento]" o
    confirmar que se realiza un tratamiento sin haberlo verificado con list_services
    Y sin seguir el flujo de derivación correspondiente. Si el paciente menciona un
    tratamiento, usar list_services para confirmar y luego aplicar la regla de
    derivación que corresponda.
```

### Cambio E — Verificar otros flujos

Confirmar que F3, F5, F6, F7, F8, F9 no tienen hardcode de profesional. ✅ Ya son genéricos.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` | Modified | 5 cambios de texto |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| F2 escalar todo al equipo sin discriminar urgencia real | Baja | triage_urgency ya clasifica; la escalación es solo para odontología general |
| Que el bot nunca mencione a la Dra. Delgado | Baja | PASO 3 + servicios de la Dra. (implantes, cirugías) siguen mencionándola |
| Prohibición 15 demasiado restrictiva | Baja | Aplica solo a "confirmar sin verificar", no impide usar list_services |

## Rollback Plan

Revertir las 5 líneas modificadas en `build_system_prompt()`.

## Success Criteria

- [ ] B4: Endodoncia/conducto → bot NO agenda con Dra. Delgado, escala al equipo
- [ ] B5: Urgencia + odontología general → bot NO lista profesionales, contiene + escala
- [ ] B9: Ortodoncia → bot NO menciona a la Dra. Delgado
- [ ] F1 y F8b no mencionan profesional específico en su CTA
- [ ] Bot no dice "Sí, hacemos [tratamiento]" como respuesta cerrada
- [ ] PASO 3 sigue funcionando para asignar profesional correcto
