# Revisión de casos — agente ortodoncia (2026-07-03, pruebas, código `4f23942`)

Registro para la optimización consolidada del prompt (no editar reactivo caso por caso).

## ✅ CONFIRMADO: el fix de "fin de mes" (A2/A3) FUNCIONA
Conv 23:21, mensaje "podria ser los viernes??? y si es posible fines de julio":
- El bot ahora manda EXACTO lo correcto: `interpreted_date='2026-07-31'` (último viernes de julio) `search_mode='month'` `preferred_days='viernes'`. Antes fallaba por no mandar esto.
- Guardó `preferred_days=['viernes']` en constraints y lo inyectó en el turno siguiente. ✅
- NO derivó, NO loopeó, NO agendó mal. Respondió honesto: "por ahora no tengo viernes a fines de julio, busco otra semana o te paso las pendientes". ✅
- Booking del happy path OK: agendó Martes 07/07 con Elizabeth, particular, seña $25.000. ✅

## 🔴 HALLAZGO NUEVO: "viernes" da 0 turnos por CONFIG (no es bug del bot)
Log del `check_availability` de viernes 31/07:
- `DIAG prof=23 (Elizabeth) day=friday day_config={'slots':[{'start':'10:00','end':'15:00'}], enabled:True}` → Elizabeth SÍ atiende viernes 10-15.
- PERO: `day_start=18:00 day_end=19:00` → la ventana del DÍA (nivel clínica) es 18-19.
- Elizabeth (10-15) ∩ ventana clínica (18-19) = **vacío** → `generate_free_slots returned 0 slots`.
- **Causa raíz: el horario de VIERNES de la CLÍNICA (tenant working_hours) NO se solapa con el de Elizabeth.** La clínica figura 18-19 (posible resto de Laura, que atiende Vie 17:30-20) y Elizabeth 10-15 → no hay franja común.
- **RESUELTO (Carlos 2026-07-03):** la clínica SÍ abre los viernes, pero ese horario está bien cargado en **PRODUCCIÓN, no en PRUEBAS**. O sea el 0-turnos del viernes es un **artefacto de config de pruebas** (la DB de pruebas tiene el viernes mal: 18-19). En prod el viernes funciona. **NO es bug de código ni requiere fix.** Ojo al testear en pruebas: los viernes van a dar 0 hasta alinear la config de pruebas con prod. Opcional: alinear horario viernes en pruebas para poder testear.

## 🟠 INCONSISTENCIA DE ENCUADRE (el "seco") — es lo principal a optimizar
Dos conversaciones casi idénticas dieron aperturas opuestas:
- **Conv 23:21:** preguntó cobertura ✅ pero saltó directo a los turnos, SIN encuadre de evaluación, sin acusar la derivación ("me derivó mi odontólogo Juan"). → SECO.
- **Conv 23:27:** dio el encuadre lindo ("los tratamientos de ortodoncia se realizan a través del equipo... primero evaluamos... te ayudo a coordinar una evaluación") pero **NO preguntó cobertura** (particular/OS).
- Es variabilidad del modelo (gpt-5.4-mini): a veces hace A, a veces B. **Falta forzar en el prompt el ORDEN completo para primer contacto de alto ticket:** (1) acusar pedido + derivación si la hay, (2) encuadre breve de evaluación, (3) preguntar cobertura si no se sabe, (4) recién ofrecer/coordinar. Sin volverlo robótico ni re-romper el "particular particular".
- **CONFIRMADO REQUISITO (Carlos 2026-07-03):** el bot DEBE preguntar cobertura (particular/OS) en primer contacto si no la sabe — el conv 23:27 no lo hizo y eso está MAL. La pregunta de cobertura NO es opcional.
- **DECISIÓN (Carlos 2026-07-03):** una sola pasada consolidada del prompt (no reactivo). Carlos sigue documentando casos acá.

## 🟡 MENOR: "dame los que tengas" agendó la opción 1 sin re-mostrar
Conv 23:21: tras "bueno dame los que tengas" (que es "mostrame las que tengas"), STATE_GUARD lo tomó como selección=True y agendó la opción 1 (Martes 07/07) sin volver a mostrar las 2 ni preguntar cuál. Debería re-mostrar y preguntar "¿el 1 o el 2?". Borderline con "agenda solo".

## 🟠 FALTA DE INICIATIVA (conv 23:37-23:45) — para la pasada consolidada
- Tras dar el precio, dijo "**Decime qué día te viene bien** y te ayudo a coordinar" en vez de OFRECER slots concretos de una. Carlos: "acá tengamos la iniciativa nosotros".
- **REPROGRAMACIÓN especialmente pasiva:** paciente pide mover el turno → bot "¿querés que lo mueva? decime un día" → paciente "por la tarde jueves o martes" → bot "tengo en cuenta jueves o martes por la tarde, ¿querés que busque?" (¡otra vez pregunta en vez de mostrar!). 3 turnos sin mostrar NUNCA una opción concreta. Carlos: "todo esto está muy mal". → En reprogramación, apenas el paciente da preferencia, LLAMAR check_availability y MOSTRAR opciones, no re-preguntar.
- $60k/Laura para consulta general con lunes = CORRECTO (excepción Laura, no es bug). El texto de $60k sale de la plantilla REGLA DE PRESENTACIÓN DEL PRECIO (main.py:11337) + campo consultation_price. Carlos OK con el texto.

## ⭐ FLUJO CANÓNICO (Carlos, palabras textuales 2026-07-04) — FUENTE DE VERDAD
El bot DEBE seguir SIEMPRE esta secuencia (validar ambas reestructuras contra esto):
1. **Pitch:** ver qué quiere → "¿tratamiento específico o turno de evaluación?"
2. **Cobertura:** "¿obra social o particular?" (siempre, salvo ya dada / urgencia).
3. **Si es NUEVO / no hay registro:** pedir **NOMBRE COMPLETO + DNI** antes de agendar (si no los tiene).
4. **Si YA tiene todos esos datos:** proceder a dar turno con las opciones que tenemos.
5. **Si el paciente dice que puede [tal día/franja]:** buscar las opciones que se **adecúen** a eso.
6. **Si mandan documentos que no entendemos / preguntas de autorizaciones / cosas sin parámetros:** NO improvisar → **asignar y ELEVAR el caso al equipo** (derivar a humano).

### Error puntual (23:58): pidió SOLO DNI, no "nombre completo + DNI"
- "ya te lo reservé... me falta tu DNI" → debió pedir nombre completo Y DNI (paso 3).
- CAUSA PROBABLE: el número de PRUEBAS 3434732389 acumuló ~5 pacientes fantasma esta noche (Juan Pérez, Lucas Gonzales, Juan Esquivel, Juan Mendez...) → el bot tomó un nombre viejo del CONTEXTO DEL PACIENTE y por eso pidió solo el DNI. En prod (número limpio) pide ambos. **Recomendación: resetear el número de pruebas para testear limpio** (ver [[clinicforge-reset-memoria-pruebas]]). Igual reforzar en la reestructura que, al agendar sin nombre confirmado en ESTA conversación, pida nombre completo + DNI.

## Plan
- NO editar reactivo por cada caso. Carlos documenta varios casos → UNA pasada consolidada + verificada del prompt (encuadre consistente + INICIATIVA al ofrecer/reprogramar) + fix de config del viernes.
- **PROMOCIÓN A PROD (Carlos pidió 2026-07-03 noche):** primero revisión adversarial del código (workflow), luego cherry-pick 1f8ae61+83c7d4c a main y `git push origin main:PRODUCCION`. OJO: PRODUCCION estaba en 286b87c VIEJO (prod nunca tuvo los fixes). Ver [[clinicforge-branch-drift-promotions]].
