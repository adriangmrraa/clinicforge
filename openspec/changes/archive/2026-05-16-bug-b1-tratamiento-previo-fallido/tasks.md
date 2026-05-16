# Tasks: Bug B1 — Tratamiento previo fallido no debe asumir historial clínico

## Phase 1: Gate de prioridad (INSERTAR nuevo bloque)

- [ ] 1.1 Insertar bloque `REGLAS DE PRIORIDAD — TRATAMIENTO PREVIO FALLIDO (GATE)` entre línea 9463 y 9464 de `main.py` — antes de la sección MIGRACIÓN
- [ ] 1.2 Incluir en el bloque: condiciones de activación (tratamiento en otro lado / sin especificar), regla de no entrar a migración, y respuesta modelo de Laura

## Phase 2: Refuerzo en F1 (MODIFICAR existente)

- [ ] 2.1 Agregar triggers adicionales a F1 en línea 9515: "me hice [tratamiento] y me fue mal", "en otro lugar/dentista/profesional", "no me resultó", "no funcionó"
- [ ] 2.2 Agregar respuesta modelo de Laura como referencia en F1 (después del M3 existente, ~línea 9519)

## Phase 3: Verificación manual

- [ ] 3.1 Probar escenario 1: "me hice implantes y me fue mal" → debe responder con F1, sin migración
- [ ] 3.2 Probar escenario 2: "me hice implantes en otro lugar y me fue mal" → debe responder con F1, sin migración
- [ ] 3.3 Probar escenario 3: "tengo un turno pendiente con la doctora" → debe activar migración correctamente
- [ ] 3.4 Probar escenario 4: "la doctora me dijo que vuelva a control" → debe activar migración correctamente
- [ ] 3.5 Probar escenario 5: "fui a otro dentista y me trataron mal" → debe responder con F1
- [ ] 3.6 Probar escenario 6: "no me fue bien con implantes" → debe responder con F1 por neutralidad
