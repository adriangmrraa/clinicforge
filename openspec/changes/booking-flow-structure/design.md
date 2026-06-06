# Design: Corrección de estructura del booking flow — numeración y orden (B1, B3, B7)

## Technical Approach

Tres ediciones localizadas en `orchestrator_service/main.py` sobre el system prompt. Son cambios de texto plano sin alteración de comportamiento semántico ni lógica de backend. Se aplican en paralelo porque afectan a strings únicos y disjuntos del archivo.

**Modo**: openspec (archivo `openspec/changes/booking-flow-structure/design.md` + persistencia Engram)

---

## Architecture Decisions

### Decision: Ediciones directas sobre string literales (no AST ni refactor)

**Choice**: Usar el `edit` tool con oldString/newString exactos sobre `orchestrator_service/main.py`
**Alternatives considered**: Refactorizar `build_system_prompt()` para generar PASO 5 dinámicamente; usar plantillas Jinja2
**Rationale**: El system prompt es un string multilineal armado en una función Python. No hay estructura de datos intermedia — el prompt es el texto literal. Editar el string existente es la intervención mínima y más segura. Crear infraestructura de plantillas para 3 cambios pequeños es overkill.

### Decision: B3 implementado como remove + insert simultáneos (no move atómico)

**Choice**: Dos ediciones independientes en el mismo mensaje: (1) eliminar bloque de su posición actual, (2) insertar copia idéntica en la nueva posición
**Alternatives considered**: Extraer el bloque a una variable Python y referenciarla desde dos lugares
**Rationale**: El `edit` tool no tiene operación "move". Aplicar remove + insert en paralelo sobre el mismo archivo funciona porque ambas operaciones buscan strings únicos y no hay solapamiento entre las regiones editadas. El resultado es idempotente.

### Decision: No renumerar PASO 1..10

**Choice**: Mantener la numeración actual (1, 2, 2b, 2c, 3, 3b, 4, 4b, 4c, 5, 6, 7, 8b, 8c, 9, 10)
**Rationale**: Renumerar rompería referencias existentes en el prompt y potencialmente en logs/documentación. Crear PASO 5 donde el flujo lo espera (entre 4c y 6) es suficiente para resolver el bug semántico.

---

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` | Modified | 3 regiones afectadas: L10474 (B7), L10832-10833 (B1), L10511-10520 y L10921-10923 (B3) |

---

## Edits Específicos

### B7 — Renombrar PASO 1 de FAQs

**Ubicación**: `orchestrator_service/main.py`
**Orden**: 1 (sin dependencias)
**oldString**: `PASO 1 — FAQs PARA TODO LO DEMÁS (VOZ OFICIAL):`
**newString**: `SECCIÓN FAQ — VOZ OFICIAL:`

**Verificación**: `grep "PASO 1"` muestra solo 1 ocurrencia (SALUDO E IDENTIDAD). La sección FAQ se llama "SECCIÓN FAQ".

---

### B1 — Crear PASO 5 entre PASO 4c y PASO 6

**Ubicación**: `orchestrator_service/main.py`
**Orden**: 2 (sin dependencias de B3 o B7)
**oldString**:
```
NUNCA ignores que el paciente ya confirmó un día — respetá su elección de fecha.
PASO 6: AGENDAR
```
**newString**:
```
NUNCA ignores que el paciente ya confirmó un día — respetá su elección de fecha.

PASO 5: VALIDACIÓN PRE-BOOKING — Antes de agendar, verificá:
• ¿El CONTEXTO DEL PACIENTE tiene nombre y DNI? Si falta → volver a PASO 4b.
• ¿check_availability devolvió [INTERNAL_DEBT:...] en el slot elegido? Si sí, avisá al paciente del saldo pendiente ANTES de llamar book_appointment. PROHIBIDO bloquear el turno por deuda — el paciente puede agendar igual, pero debe saber que tiene saldo registrado.
• ¿El paciente confirmó el slot (PASO 4c exitoso)? Si no, no llamar book_appointment.
• Todo OK → ir a PASO 6.

PASO 6: AGENDAR
```

**Edición adicional**: Actualizar referencia en línea 11006.
**oldString**: `NO repetir PASOS 2, 2b, 3 ni 5.`
**newString**: `NO repetir PASOS 2, 2b, 3 ni 5 (PASO 5 está definido más arriba en su sección).`

---

### B3 — Mover POST-ATENCIÓN al final del prompt

**Orden**: 3 (independiente de B1 y B7)

#### Paso B3a: Eliminar bloque de posición actual (L10511-L10520)

**oldString**:
```
SEGUIMIENTO POST-ATENCIÓN (PROTOCOLO ESTRICTO):
• Si el paciente responde POSITIVO ("todo bien", "perfecto", "sin molestias"):
  → Respondé empáticamente: "¡Qué bueno 😊! Cualquier duda, podés escribirnos. Estamos para acompañarte 💛"
  → NO requiere acción adicional. NO ofrecer turno innecesario.
• Si el paciente responde NEGATIVO (dolor, inflamación, sangrado, molestia, "no me siento bien"):
  → OBLIGATORIO: llamar 'derivhumano' INMEDIATAMENTE para escalar a equipo humano.
  → Mensaje al paciente: "Gracias por contarnos 😊 Es importante que podamos evaluarte para acompañarte correctamente. Ya derivamos tu caso para que te contactemos a la brevedad 💛"
  → Después podés ofrecer control: "Si lo necesitás, podemos coordinarte un control para revisarte 😊"
  → Esta es UNA de las pocas excepciones donde derivhumano es OBLIGATORIO (junto con emergencias y solicitud explícita).
• Evaluar también con 'triage_urgency' si hay síntomas claros de urgencia clínica.
```
**newString**: `` (cadena vacía — el bloque se elimina)

#### Paso B3b: Insertar bloque entre PASO 10 e INSTRUCCIONES DE TRATAMIENTO (L10921-L10923)

**oldString**:
```
PASO 10: SEGUIMIENTO — Si el paciente no responde en 2-3 mensajes durante el flujo de agendamiento:
  No enviar más mensajes automáticos. Cuando vuelva a escribir, retomar donde quedó sin repetir pasos ya completados.

INSTRUCCIONES DE TRATAMIENTO (POST-AGENDAMIENTO):
```
**newString**:
```
PASO 10: SEGUIMIENTO — Si el paciente no responde en 2-3 mensajes durante el flujo de agendamiento:
  No enviar más mensajes automáticos. Cuando vuelva a escribir, retomar donde quedó sin repetir pasos ya completados.

SEGUIMIENTO POST-ATENCIÓN (PROTOCOLO ESTRICTO):
• Si el paciente responde POSITIVO ("todo bien", "perfecto", "sin molestias"):
  → Respondé empáticamente: "¡Qué bueno 😊! Cualquier duda, podés escribirnos. Estamos para acompañarte 💛"
  → NO requiere acción adicional. NO ofrecer turno innecesario.
• Si el paciente responde NEGATIVO (dolor, inflamación, sangrado, molestia, "no me siento bien"):
  → OBLIGATORIO: llamar 'derivhumano' INMEDIATAMENTE para escalar a equipo humano.
  → Mensaje al paciente: "Gracias por contarnos 😊 Es importante que podamos evaluarte para acompañarte correctamente. Ya derivamos tu caso para que te contactemos a la brevedad 💛"
  → Después podés ofrecer control: "Si lo necesitás, podemos coordinarte un control para revisarte 😊"
  → Esta es UNA de las pocas excepciones donde derivhumano es OBLIGATORIO (junto con emergencias y solicitud explícita).
• Evaluar también con 'triage_urgency' si hay síntomas claros de urgencia clínica.

INSTRUCCIONES DE TRATAMIENTO (POST-AGENDAMIENTO):
```

---

## Dependencias Entre Cambios

| # | Cambio | Depende de | Afecta |
|---|--------|-----------|--------|
| 1 | B7 — Renombrar FAQ | Ninguna | Ninguno |
| 2 | B1 — Insertar PASO 5 | Ninguna | Validar línea 11006 |
| 3a | B3a — Eliminar POST-ATENCIÓN en origen | Ninguna | Ninguno |
| 3b | B3b — Insertar POST-ATENCIÓN en destino | Ninguna | Ninguno |

Todos los cambios son independientes y pueden aplicarse en paralelo o en cualquier orden secuencial. Cada oldString es único dentro del archivo.

---

## Testing Strategy

| Layer | Qué probar | Cómo |
|-------|-----------|------|
| **Diff** | Los 3 cambios aplicados correctamente | `git diff` contra el original: verificar que las regiones esperadas cambiaron y que NO hay cambios no deseados |
| **Lint** | El archivo sigue siendo Python válido | `python -c "import ast; ast.parse(open('orchestrator_service/main.py').read())"` |
| **Verificación grep B7** | Solo 1 "PASO 1" en el archivo | `grep -c "PASO 1" orchestrator_service/main.py` → 1 (SALUDO) |
| **Verificación grep B1** | PASO 5 existe entre 4c y 6 | `grep -A 1 "PASO 4c" orchestrator_service/main.py | head -1` y confirmar que PASO 5 sigue |
| **Verificación grep B1b** | Línea 11006 actualizada | `grep "NO repetir PASOS" orchestrator_service/main.py` contiene "(PASO 5 está definido más arriba)" |
| **Verificación grep B3** | POST-ATENCIÓN aparece después de PASO 10 | `grep -A 2 "PASO 10:" orchestrator_service/main.py` → POST-ATENCIÓN aparece inmediatamente después |
| **Verificación grep B3** | POST-ATENCIÓN NO aparece entre DIFERENCIACIÓN y FLUJO | `grep -A 2 "DIFERENCIACIÓN DRA." orchestrator_service/main.py` → NO contiene "SEGUIMIENTO POST-ATENCIÓN" |
| **Verificación contenido** | POST-ATENCIÓN sin alteración | `diff <(grep -A 15 "^SEGUIMIENTO POST-ATENCIÓN" original.md) <(grep -A 15 "^SEGUIMIENTO POST-ATENCIÓN" modified.md)` — debe dar vacío |

### Rollback

Revertir con `git checkout -- orchestrator_service/main.py`. No hay migraciones, schemas ni cambios de infraestructura.

---

## Open Questions

- Ninguno. Todos los oldString fueron verificados contra el archivo actual y son únicos.
