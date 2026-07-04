# Auditoria prompt — reprogramacion + P0/P1 (workflow wr34hxsd2)

## Summary
CAUSA RAÍZ de la reprogramación rota (regresión): NO es el prompt, es un GATE DE CÓDIGO en check_availability (main.py:2185-2194, introducido/endurecido por DLD-89/92 + AG-03). Cuando el paciente ya tiene turno (state BOOKED/PAYMENT_PENDING, TTL 24h), el gate exige que el texto matchee un regex allowlist `_intent_signals`; si no, NO busca y devuelve un [SYSTEM_NOTE] que ordena al LLM 'no llames check_availability, preguntale si quiere moverlo o cancelarlo'. Verifiqué ejecutando el regex REAL contra las 4 frases del transcript ('podemos moverlo...viajo ese dia', 'si movámoslo', 'por la tarde jueves o martes', 'para fines de julio'): las 4 son BLOQUEADAS (0 matches). El gate solo tiene 'mover el turno|mover turno' (no captura moverlo/movámoslo) y no cubre días pelados ni franjas. Resultado: el bot obedece el SYSTEM_NOTE y pide permiso en loop sin buscar nunca — EXACTAMENTE el transcript. El prompt SÍ ordena lo correcto (12173/12733), pero el código lo frena antes. Fix P0-1: ampliar el regex (código, 1 línea lógica, fail-open). Fix P0-2 (refuerzo prompt): generalizar la REGLA CERO anti-permiso a reprogramar. Todo lo demás (dos flujos paralelos R0-R2 vs PASO 0-4, contradicción 'mismo día', bloat de sigilo/compuerta triplicada) es deuda estructural real que causa la INCONSISTENCIA que reporta el dueño, pero su consolidación es reescritura riesgosa → P2 backlog. APPLY NOW: P0-1 (regex código) + P0-2 (REGLA CERO) + P1-1 (acotar precondición B5) + 2 fixes léxicos triviales (trigger sinónimos + emojis). Todo verificado file:line contra el código; regex probado con py/re.

## P0

### GATE DE CÓDIGO bloquea la reprogramación — regex _intent_signals no reconoce 'moverlo/movámoslo/jueves/tarde' → check_availability BLOQUEADO y bot pide permiso en loop (CAUSA RAÍZ, es CÓDIGO no prompt)
ancla: orchestrator_service/main.py:2185-2194 (regex _intent_signals dentro del gate DLD-89/92; bloqueo en :2218 con return del [SYSTEM_NOTE] :2226-2232)
```
REEMPLAZAR el bloque del regex (main.py:2185-2194).

VIEJO:
                    _intent_signals = (
                        r'\b(otro turno|nuevo turno|otra fecha|otro d[ii]a|quiero cambiar|'
                        r'reagend\w*|reprogram\w*|mover el turno|mover turno|cancel\w*|'
                        r'dame otro|dame otra|dame opciones|dame las opciones|agendame otro|'
                        r'necesito otro|sac[aa] otro|quiero uno m[aa]s|turno para|cambiar el turno|'
                        r'busc\w*|fijate|cualquier|disponib\w*|horario libre|otro horario|'
                        r'verif\w*|intento|intentalo|no puedo ir|no podr[ee] ir|no voy a poder|'
                        r'no llego|qu[ee] d[ii]a|para cuando|cuando puede|propon|lo que tengas|'
                        r'el que sea|vos decim)'
                    )

NUEVO:
                    _intent_signals = (
                        r'\b(otro turno|nuevo turno|otra fecha|otro d[ii]a|quiero cambiar|'
                        r'reagend\w*|reprogram\w*|mov\w*|corr[ae]\w*|pas[aá](?:me|rlo|r)?\b|viaj\w*|cancel\w*|'
                        r'dame otro|dame otra|dame opciones|dame las opciones|agendame otro|'
                        r'necesito otro|sac[aa] otro|quiero uno m[aa]s|turno para|cambiar el turno|'
                        r'busc\w*|fijate|cualquier|disponib\w*|horario libre|otro horario|'
                        r'verif\w*|intento|intentalo|no puedo ir|no podr[ee] ir|no voy a poder|'
                        r'no llego|qu[ee] d[ii]a|para cuando|cuando puede|propon|lo que tengas|'
                        r'el que sea|vos decim|'
                        r'lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo|'
                        r'ma[nñ]ana|tarde|noche|temprano|m[aa]s tarde|'
                        r'a las \d|a la (ma[nñ]ana|tarde|noche))'
                    )

NOTA: verificado con Python re — las 4 frases reales del transcript pasan de BLOCK a MATCH y las frases de cortesía/consulta lateral ('gracias', 'trabajan con osde?', 'cuanto sale') siguen sin matchear. El gate solo actúa en state BOOKED/PAYMENT_PENDING, así que el ámbito es acotado y el error es fail-open hacia el flujo correcto. Validar con py_compile antes de subir.
```

### REGLA CERO — AVANZAR SIN PEDIR PERMISO solo cubre AGENDAR, no REPROGRAMAR → falta el contrapeso proactivo fuerte al reprogramar (refuerzo prompt-side del P0 de código)
ancla: orchestrator_service/main.py:12061 — 'Si el paciente expresó intención de agendar (pidió turno, mencionó tratamiento, dijo fecha), ejecutá check_availability INMEDIATAMENTE. No preguntes "¿querés que busque?"...'
```
main.py:12061 — extender la imperativa anti-permiso para que cubra reprogramar con el MISMO lenguaje ya existente (reconciliación, no instrucción nueva).

VIEJO:
Si el paciente expresó intención de agendar (pidió turno, mencionó tratamiento, dijo fecha), ejecutá check_availability INMEDIATAMENTE. No preguntes "¿querés que busque?" ni "te ayudo a coordinar?".

NUEVO:
Si el paciente expresó intención de agendar (pidió turno, mencionó tratamiento, dijo fecha) O de reprogramar (dijo "moverlo", "cambiarlo", "reagendar" y confirmó que quiere hacerlo), ejecutá check_availability INMEDIATAMENTE. No preguntes "¿querés que busque?", "te ayudo a coordinar?" ni "si querés busco las opciones". Apenas el paciente da una preferencia de día o franja (ej. "por la tarde jueves o martes", "fines de julio") tu ÚNICA acción es llamar check_availability y MOSTRAR opciones — está PROHIBIDO responder prometiendo buscar sin haber llamado la tool.
```

## P1

### Acotar el ALCANCE de la PRECONDICIÓN DE PRESENTACIÓN (B5, commit 83c7d4c): dejar explícito que solo frena confirm_slot/book_appointment (AGENDAR), NUNCA frena check_availability (BUSCAR) — corta el efecto chilling sobre la reprogramación
ancla: orchestrator_service/main.py:12390 — '⚠️ PRECONDICIÓN DE PRESENTACIÓN (INQUEBRANTABLE): ... Si no podés señalar tu mensaje previo con las opciones + la elección del paciente, NO agendes: presentá.'
```
main.py:12390 — AGREGAR al final de esa misma línea (tras 'NO agendes: presentá.'):

AGREGAR:
 ⚠️ ALCANCE: esta precondición SÓLO frena confirm_slot y book_appointment (AGENDAR). NUNCA frena llamar check_availability para BUSCAR y MOSTRAR opciones — buscar y presentar es siempre lo que corresponde hacer YA, tanto al agendar como al reprogramar. No uses esta regla como excusa para pedir permiso antes de buscar.
```

### Trigger de SINÓNIMOS REPROGRAMAR no cubre 'moverlo/movámoslo/pasarlo/correr' — mismo hueco léxico que el gate de código; alinear ambos lados para coherencia end-to-end
ancla: orchestrator_service/main.py:11940 — '• REPROGRAMAR → `reschedule_appointment`: "reprogramar", "cambiar turno", "mover turno", "otro día", "reagendar"'
```
main.py:11940 —
VIEJO:
• REPROGRAMAR → `reschedule_appointment`: "reprogramar", "cambiar turno", "mover turno", "otro día", "reagendar"

NUEVO:
• REPROGRAMAR → `reschedule_appointment`: "reprogramar", "cambiar turno", "mover turno", "moverlo", "movámoslo", "pasarlo/pasame el turno", "correr el turno", "otro día", "reagendar"

Riesgo nulo: solo agrega ejemplos a una lista ya abierta ('No esperes palabras exactas', 11942).
```

### Contradicción de prioridad entre los dos flujos de reprogramación: 12180 dice 'NO ofrezcas el mismo día por defecto' vs 12742 dice 'Prioridad: mismo día → días cercanos' — órdenes opuestas ante la misma situación (fuente de inconsistencia)
ancla: orchestrator_service/main.py:12742 — 'Prioridad: mismo día → días cercanos (search_mode="week") → semana siguiente.'
```
main.py:12742 — alinear con la regla correcta (no reofrecer el día que el paciente está evitando), que ya está en 12180.

VIEJO:
Prioridad: mismo día → días cercanos (search_mode="week") → semana siguiente.

NUEVO:
Prioridad: días cercanos distintos al del turno original (search_mode="week") → semana siguiente. Solo ofrecé el MISMO día del turno original si el paciente lo pidió explícitamente.

Riesgo bajo: alinea el Bloque B con el Bloque A (12180) y con la intención semántica correcta. No toca reglas intocables.
```

### Contradicción en allowlist de emojis: 11663 declara lista cerrada 'Solo: 😊 ✨ ❤️ 📅 📍 ✅' pero 11948 (y flujos F2/F6) mandan usar 🦷 y ⏰ que la lista excluye → uso inconsistente de emojis
ancla: orchestrator_service/main.py:11663 — 'Máximo 1-2 emojis por mensaje. Solo: 😊 ✨ ❤️ 📅 📍 ✅'
```
main.py:11663 — ampliar la allowlist para incluir los emojis que otras reglas ya mandan usar (reconciliar hacia el uso intencional, editar solo esta línea, no tocar 11948).

VIEJO:
Máximo 1-2 emojis por mensaje. Solo: 😊 ✨ ❤️ 📅 📍 ✅

NUEVO:
Máximo 1-2 emojis por mensaje. Solo: 😊 ✨ ❤️ 📅 📍 ✅ 🦷 ⏰
```

## P2 backlog

- DUPLICACIÓN MAYOR: dos flujos completos y paralelos de reprogramación (PASO R0/R1/R2 @12165-12185 vs PASO 0/1/2/3/4 + CASO A-H @12671-12769) — causa estructural de la INCONSISTENCIA que reporta el dueño :: DIAGNÓSTICO, NO aplicar en este run (es reescritura, riesgo medio). Dos 'mapas' del mismo territorio con numeración y triggers distintos gobernando la misma reschedule_appointment. El modelo mezcla fragmentos → misma situación, respuesta distinta. Plan futuro (pack dedicado con verificación adversarial): dejar el Bloque B (12671, el más completo: tabla CASO A-H, resolución multi-turno, ambigüedad del 'sí', prohibiciones, post-reschedule) como fuente ÚNICA y reducir el Bloque A (R0-R2) a un puntero. ANTES de recortar: diff línea por línea para garantizar que el canónico cubre las sub-reglas que hoy solo viven en A (ej. exclude_dates del día original @12181, 'no ofrecer mismo día por defecto' @12180). Toca reglas intocables (no re-preguntar, oferta al reprogramar, post-reschedule sin seña/anamnesis) → no aplicar a ciegas.
- BLOAT: tabla de interpretación de fechas duplicada casi textual — 'RAZONAMIENTO DE FECHA' (booking, ~12194-12259) vs 'PASO 0 CASO A-H' (reprogramación, 12673-12714) :: ~2800 tokens sobre la MISMA lógica de parseo de fecha (que además ya vive en parse_date() del código). Infla el prompt (parte del gasto 48k-290k tok/msg que preocupa al dueño) y obliga a mantener dos listados sincronizados que ya divergen. Fix futuro: reemplazar la tabla CASO A-H por un puntero a RAZONAMIENTO DE FECHA, conservando SOLO las 2-3 reglas propias de reprogramación (CASO A 'mismo día otra hora' + RESTRICCIÓN HORARIA ACUMULADA @12716). Ahorra ~900 tok. Verificar cobertura caso por caso antes de borrar. No hacer en la misma pasada que la consolidación de flujos.
- REDUNDANCIA: la misma compuerta anti 'agendar sin presentar' está escrita 3 veces — bullet @12262, PRECONDICIÓN @12390 (B5) y COMPUERTA DE SELECCIÓN @12391 :: No es contradicción (todas empujan igual), pero es carga redundante que diluye la señal, encarece cada turno y es terreno fértil para que un fix futuro edite una copia y deje las otras divergentes (el patrón que ya generó la doble-especificación de reprogramación). Fix futuro: fusionar en una sola, quitando el bullet @12262 (subsumido por 12390+12391). El P1 de acotar el ALCANCE de 12390 ya cubre lo urgente; la fusión completa es limpieza. NO tocar el candado de código anti agenda-solo (está diferido).
- DUPLICACIÓN: regla de 'sigilo de profesional' (no nombrar antes de confirmar) restated 3+ veces — PASO 3 @12157, regla #8 @11779, 'SIGILO GENERALIZADA' @12264 :: Consistentes entre sí (no causan inconsistencia), pero cientos de tokens repetidos. Fix futuro: condensar el restate de 12264 a un puntero al PASO 3 (12157), que queda como fuente única intra-flujo. Nota: 11779 cae en zona de primer-contacto/pitch que cubre OTRO run — no tocar acá para evitar branch-drift. Solo el restate intra-flujo (12264) es de este ámbito.
- DUPLICACIÓN: prohibiciones post-reschedule (no seña/CBU, no anamnesis, no pago) repetidas en 4 lugares — PASO 4 @12753-12755, anamnesis @11439, pago @11472 y @11484 :: Consistentes (bloat, no contradicción). Fix futuro: dejar el PASO 4 (12751-12755) como fuente única y reducir los restates a punteros. ADVERTENCIA: 11439/11472/11484 viven en secciones armadas condicionalmente (anamnesis_section/payment_section) que cruzan con el run de pago/pitch — coordinar para no editar las mismas líneas en paralelo (branch-drift, CLAUDE.md). No aplicar en este run.
- GUARDA DE DÍA PEDIDO (B6, @12431) no cubre el camino reschedule_appointment — hueco de cobertura, no contradicción :: La GUARDA DE DÍA PEDIDO vive en PASO 6 y habla de confirm_slot/book_appointment. La reprogramación usa reschedule_appointment directo (PASO 3 @12747), donde la guarda queda huérfana: si el paciente pidió 'jueves o martes' y la tool devuelve un miércoles, no hay barrera explícita antes de reschedule. Fix futuro de bajo riesgo (reutiliza regla ya validada): tras la línea 12748 agregar un puntero '→ GUARDA DE DÍA PEDIDO (igual que en reserva): si pidió día(s) concreto(s) o excluyó días, verificá que el nuevo turno caiga en un día pedido antes de reschedule_appointment; si no, re-buscá con preferred_days'. Se puede aplicar aislado si se decide, pero lo dejo en P2 por no ser bloqueante del bug.
- Divergencia menor de redacción: pregunta única de reprogramación difiere entre bloques — '¿Para cuándo lo querés reprogramar?' @12168 vs '¿Para cuándo lo querés cambiar?' @12721 :: Cosmético, no causa el loop. Se resuelve solo cuando se consolide el flujo (P2 de duplicación mayor). No editar aislado para no fragmentar más.