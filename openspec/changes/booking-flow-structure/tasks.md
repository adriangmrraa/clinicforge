# Tasks: Corrección de estructura del booking flow — numeración y orden (B1, B3, B7)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~30 (1 + 9 + 0 net) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | All 4 edits + verify | PR 1 | Single atomic change to `orchestrator_service/main.py`. All edits are independent string replacements. |

## Phase 1: Ediciones directas al system prompt

- [ ] **1.1 — B7: Renombrar PASO 1 de FAQs** (`orchestrator_service/main.py`, línea 10474)
  `oldString`: `PASO 1 — FAQs PARA TODO LO DEMÁS (VOZ OFICIAL):`
  `newString`: `SECCIÓN FAQ — VOZ OFICIAL:`

- [ ] **1.2 — B1a: Insertar PASO 5 entre PASO 4c y PASO 6** (`orchestrator_service/main.py`, línea 10832-10833)
  `oldString`:
  ```
  NUNCA ignores que el paciente ya confirmó un día — respetá su elección de fecha.
  PASO 6: AGENDAR
  ```
  `newString`:
  ```
  NUNCA ignores que el paciente ya confirmó un día — respetá su elección de fecha.

  PASO 5: VALIDACIÓN PRE-BOOKING — Antes de agendar, verificá:
  • ¿El CONTEXTO DEL PACIENTE tiene nombre y DNI? Si falta → volver a PASO 4b.
  • ¿check_availability devolvió [INTERNAL_DEBT:...] en el slot elegido? Si sí, avisá al paciente del saldo pendiente ANTES de llamar book_appointment. PROHIBIDO bloquear el turno por deuda — el paciente puede agendar igual, pero debe saber que tiene saldo registrado.
  • ¿El paciente confirmó el slot (PASO 4c exitoso)? Si no, no llamar book_appointment.
  • Todo OK → ir a PASO 6.

  PASO 6: AGENDAR
  ```
  ⚠️ `PASO 6: AGENDAR` en el newString mantiene el contenido original del resto de la línea (` — 'book_appointment' con los datos del paciente...`).

- [ ] **1.3 — B1b: Verificar referencia a PASO 5** (`orchestrator_service/main.py`, línea ~11006)
  `No hay cambio que aplicar.` Verificar que `NO repetir PASOS 2, 2b, 3 ni 5.` referencia correctamente al nuevo PASO 5 después de aplicar 1.2. Si el PASO 5 está insertado entre 4c y 6, la referencia ya es correcta.

- [ ] **1.4 — B3a: Eliminar POST-ATENCIÓN de ubicación actual** (`orchestrator_service/main.py`, líneas 10511-10520)
  `oldString`:
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
  `newString`: ` ` (vacío — se elimina el bloque)

- [ ] **1.5 — B3b: Insertar POST-ATENCIÓN al final, entre PASO 10 e INSTRUCCIONES DE TRATAMIENTO** (`orchestrator_service/main.py`, líneas 10921-10923)
  `oldString`:
  ```
  PASO 10: SEGUIMIENTO — Si el paciente no responde en 2-3 mensajes durante el flujo de agendamiento:
    No enviar más mensajes automáticos. Cuando vuelva a escribir, retomar donde quedó sin repetir pasos ya completados.

  INSTRUCCIONES DE TRATAMIENTO (POST-AGENDAMIENTO):
  ```
  `newString`:
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

## Phase 2: Verificación

- [ ] **2.1 — Lint: Python válido**
  `python -c "import ast; ast.parse(open('orchestrator_service/main.py').read())"` → exit 0

- [ ] **2.2 — Verificar B7: solo 1 ocurrencia de "PASO 1"**
  `grep -c "PASO 1" orchestrator_service/main.py` → 1 (SALUDO E IDENTIDAD). La sección FAQ ahora es "SECCIÓN FAQ".

- [ ] **2.3 — Verificar B1a: PASO 5 existe entre PASO 4c y PASO 6**
  `grep -A 2 "PASO 4c" orchestrator_service/main.py | head -3` → muestra PASO 5 antes de PASO 6.

- [ ] **2.4 — Verificar B1b: referencia a PASO 5 existe y es correcta**
  `grep "NO repetir PASOS" orchestrator_service/main.py` → contiene `NO repetir PASOS 2, 2b, 3 ni 5.` que referencia al nuevo PASO 5 creado en B1a.

- [ ] **2.5 — Verificar B3: POST-ATENCIÓN movido correctamente**
  `grep -A 2 "PASO 10:" orchestrator_service/main.py` → "SEGUIMIENTO POST-ATENCIÓN" aparece inmediatamente después de PASO 10.
  `grep -A 2 "DIFERENCIACIÓN DRA." orchestrator_service/main.py` → NO contiene "SEGUIMIENTO POST-ATENCIÓN".

- [ ] **2.6 — Verificar contenido POST-ATENCIÓN sin alteración**
  El bloque reinsertado en B3b es idéntico palabra por palabra al extraído en B3a.

- [ ] **2.7 — Diff final**
  `git diff orchestrator_service/main.py` — solo 4 regiones cambiadas, sin cambios no deseados.

## Resumen de ediciones

| Tarea | Líneas | oldString único? | Dependencias |
|-------|--------|------------------|-------------|
| 1.1 B7 | 10474 | ✅ sí | Ninguna |
| 1.2 B1a | 10832-10833 | ✅ sí | Ninguna |
| 1.3 B1b | ~11006 | Solo verificar | Depende de 1.2 |
| 1.4 B3a | 10511-10520 | ✅ sí | Ninguna |
| 1.5 B3b | 10921-10923 | ✅ sí | Ninguna |

> Todos los oldString son únicos en el archivo. Las 4 ediciones (1.1, 1.2, 1.4, 1.5) son independientes y pueden aplicarse en cualquier orden o en paralelo.
