# Diseno reestructura COBERTURA / primer contacto (workflow whxbl03fe)

## Secuencia coherente
SECUENCIA FINAL DE PRIMER CONTACTO (una sola compuerta dura = COBERTURA):

1. SALUDO + PITCH (queda IGUAL, viene de tenants.system_prompt_template / greeting_specialty): "¿tratamiento específico o turno de evaluación?". No se toca.
2. El paciente responde qué quiere (aunque incluya fecha en el mismo mensaje: "quiero una consulta con la dra, ¿turnos para fin de julio?").
3. COMPUERTA DURA — COBERTURA. Antes de cotizar precio Y antes del PRIMER check_availability, el bot verifica la cobertura:
   - Si ya está en el CONTEXTO DEL PACIENTE o ya la dijo en la charla → NO re-preguntar (prohibido). Se usa directo.
   - Si NO se sabe → una sola pregunta: "¿Contás con alguna obra social o te atenderías de forma particular?" (puede combinarse con la del tratamiento en el mismo mensaje). Recién con la respuesta se ejecuta check_availability. La proactividad ("avanzar sin pedir permiso") significa NO pedir permiso para agendar, NO significa saltear la cobertura.
   - EXCEPCIÓN ÚNICA F2 (dolor/urgencia): NO se frena la urgencia; la pregunta de cobertura va integrada en M3 junto a las 2 opciones de turno, nunca antes.
4. Resuelta la cobertura → se entra a los 3 CAMINOS (CAMINO 1 OS aceptada / CAMINO 2 OS no aceptada / CAMINO 3 particular). En CAMINO 3 (particular) el encuadre de valor de la evaluación (REGLA DE PRESENTACIÓN DEL PRECIO) se incluye SIEMPRE que se ofrezca el turno particular — eso elimina la sequedad. En CAMINO 1/2, coseguro/reintegro según la tool.
5. INICIATIVA: si el paciente no dio preferencia de fecha, el bot busca automáticamente (GUARDIA) y OFRECE 2 opciones concretas — nunca "decime qué día". Si el paciente ya dio día/franja, se usa esa.
6. check_availability → paciente elige → datos (nombre, DNI) → confirm_slot → book_appointment. El profesional sigue siendo INTERNO (no se nombra antes de confirmar).

Resultado: la cobertura es la ÚNICA compuerta dura antes del primer check_availability; todo bloque de proactividad la nombra como precondición dentro de su condición, no como hedge entre paréntesis.

## Ediciones (8) — todas reconcile

### E1-REGLA-CERO-titular [reconcile]
**Ancla:** main.py:12060-12062 — === REGLA CERO — AVANZAR SIN PEDIR PERMISO === (EPICENTRO de la contradicción)
**VIEJO (intent/texto):** === REGLA CERO — AVANZAR SIN PEDIR PERMISO ===
Si el paciente expresó intención de agendar (pidió turno, mencionó tratamiento, dijo fecha), ejecutá check_availability INMEDIATAMENTE. No preguntes "¿querés que busque?" ni "te ayudo a coordinar?".
EXCEPCIÓN ÚNICA (REGLA DE COBERTURA): si todavía NO sabés si se atiende particular o con obra social (paciente nuevo, sin cobertura en el contexto ni en la charla), hacé PRIMERO esa única pregunta — podés combinarla con la del tratamiento en el MISMO mensaje — y ejecutá check_availability apenas responda, sin volver a pedir permiso. "INMEDIATAMENTE" significa sin pedir permiso, NO sin resolver la cobertura.
**NUEVO (exacto):** === REGLA CERO — AVANZAR SIN PEDIR PERMISO ===
Si el paciente expresó intención de agendar (pidió turno, mencionó tratamiento, dijo fecha) Y YA SABÉS SU COBERTURA (particular u obra social, por el CONTEXTO DEL PACIENTE o porque la dijo en la charla), ejecutá check_availability INMEDIATAMENTE. No preguntes "¿querés que busque?" ni "te ayudo a coordinar?".
SI TODAVÍA NO SABÉS LA COBERTURA (paciente nuevo, sin cobertura en el contexto ni en la charla): la cobertura es la ÚNICA compuerta previa a check_availability (REGLA DE COBERTURA de REGLAS PRIMORDIALES). Hacé PRIMERO esa única pregunta — podés combinarla con la del tratamiento en el MISMO mensaje — y ejecutá check_availability apenas responda, sin volver a pedir permiso. Que "expresó intención + fecha en un mismo mensaje" (ej: "quiero una consulta con la dra, ¿turnos para fin de julio?") NO habilita saltear esto: la fecha se guarda y se usa recién al ejecutar, DESPUÉS de la cobertura. "INMEDIATAMENTE" significa sin pedir permiso para agendar, NO sin resolver la cobertura. (ÚNICA salvedad: F2 dolor/urgencia — ahí la cobertura va integrada en M3, ver F2.)
**Por que:** Mueve la cobertura DENTRO de la condición del imperativo (‘Y YA SABÉS SU COBERTURA’) en vez de dejarla como excepción posterior subordinada al titular gritado. El modelo ya no puede leer ‘ejecutá INMEDIATAMENTE’ sin antes chequear el gate, porque el gate es parte de la condición para ejecutar. Cita textual el caso que falló para cerrarlo. Preserva la salvedad F2 con una sola línea.
**Riesgo:** Bajo. No cambia comportamiento cuando la cobertura ya se conoce (happy path del paciente que la dio queda idéntico). Solo endurece el caso nuevo-sin-cobertura, que es exactamente lo que el dueño pidió.

### E2-PROACTIVIDAD-bullet-ejecutar [reconcile]
**Ancla:** main.py:11963 — bloque PROACTIVIDAD, bullet siguiente al de cobertura (‘buscame fecha/agendame/dale → EJECUTAR’)
**VIEJO (intent/texto):** • Paciente dice "buscame fecha"/"agendame"/"dale" → EJECUTAR, no preguntar.
**NUEVO (exacto):** • Paciente dice "buscame fecha"/"agendame"/"dale" → EJECUTAR, no pedir permiso — PERO si todavía no sabés la cobertura (particular/obra social), esa única pregunta va PRIMERO y recién después ejecutás (ver bullet anterior y REGLA DE COBERTURA). "Ejecutar" presupone la cobertura ya resuelta.
**Por que:** El bullet inmediatamente anterior (11962) prohíbe llamar check_availability sin cobertura, y este lo contradecía ordenando ejecutar ante ‘agendame’ sin acotar. Ahora ambos bullets consecutivos dicen lo mismo: ejecutar = no pedir permiso, con la cobertura como precondición explícita, no como algo que ‘agendame’ saltea.
**Riesgo:** Bajo. Solo agrega la precondición de cobertura al verbo del paciente; no toca el resto del flujo proactivo.

### E3-frases-PROHIBIDAS-cobertura-al-frente [reconcile]
**Ancla:** main.py:12112 — EJEMPLOS de frases PROHIBIDAS cuando el paciente YA pidió turno o tratamiento
**VIEJO (intent/texto):** En su lugar → ejecutá check_availability directamente (con la cobertura ya resuelta; si no la sabés, esa única pregunta va primero — REGLA DE COBERTURA).
**NUEVO (exacto):** En su lugar → si YA sabés la cobertura, ejecutá check_availability directamente; si NO la sabés, hacé PRIMERO la única pregunta de cobertura (nunca pidas permiso para agendar, pero la cobertura SÍ va antes de check_availability — REGLA DE COBERTURA). En ningún caso pidas permiso para agendar.
**Por que:** Saca la cobertura del paréntesis final (hedge enterrado que el modelo pierde) y la pone al frente como bifurcación explícita de la instrucción. La acción dominante deja de ser ‘ejecutá directamente’ a secas.
**Riesgo:** Mínimo. Reordena la misma información sin cambiar la prohibición de pedir permiso.

### E4-POST-DATOS-cobertura-en-condicion [reconcile]
**Ancla:** main.py:12124 — REGLA POST-DATOS
**VIEJO (intent/texto):** REGLA POST-DATOS: Si el paciente ya dio nombre y DNI Y ya expresó intención de turno → ejecutar check_availability y mostrar turnos SIN preguntar "¿querés que te pase los turnos disponibles?". La intención ya fue expresada — AVANZAR. (SIN preguntar = sin pedir permiso; la cobertura particular/obra social SÍ se resuelve primero si todavía falta.)
**NUEVO (exacto):** REGLA POST-DATOS: Si el paciente ya dio nombre y DNI, ya expresó intención de turno Y ya sabés su cobertura (particular u obra social) → ejecutar check_availability y mostrar turnos SIN preguntar "¿querés que te pase los turnos disponibles?". La intención ya fue expresada — AVANZAR sin pedir permiso. Si todavía falta la cobertura (dio nombre+DNI pero nunca dijo particular/OS), esa única pregunta va PRIMERO y recién después ejecutás check_availability (REGLA DE COBERTURA). Tener nombre y DNI NO reemplaza la cobertura.
**Por que:** Eleva la cobertura de paréntesis final a tercera condición explícita, al mismo nivel que ‘nombre y DNI’. Cierra el caso del lead nuevo que da datos pero no cobertura (‘me llamo Ana, DNI 30111222, quiero turno’), donde el imperativo AVANZAR le ganaba al hedge.
**Riesgo:** Bajo. No afecta al paciente que ya dio cobertura; solo agrega la precondición faltante.

### E5-GREETING-noappt-quitar-y/o [reconcile]
**Ancla:** main.py:11412 — GREETING patient_no_appointment, punto C (AVANCE ANTE AFIRMACIÓN)
**VIEJO (intent/texto):** → INTERPRETALO como un SÍ y AVANZÁ el agendamiento YA: seguí la REGLA DE COBERTURA (preguntá particular/obra social si todavía no lo sabés) y/o llamá check_availability para ofrecerle horarios concretos.
**NUEVO (exacto):** → INTERPRETALO como un SÍ y AVANZÁ el agendamiento YA, en este orden: PRIMERO resolvé la cobertura (si todavía no sabés si es particular u obra social, preguntala UNA vez — REGLA DE COBERTURA); recién con la cobertura resuelta llamá check_availability para ofrecerle horarios concretos. Si ya sabés la cobertura, andá directo a check_availability.
**Por que:** El conector ‘y/o’ era el ÚNICO lugar donde el texto literal permitía llamar check_availability sin resolver cobertura (ambas ramas del ‘o’ válidas). Reemplazarlo por una secuencia explícita (‘PRIMERO cobertura … recién con la cobertura resuelta … check_availability’) elimina esa lectura sin perder el empuje ‘AVANZÁ YA’.
**Riesgo:** Bajo. Mantiene la iniciativa (interpreta la afirmación como sí y avanza); solo ordena los dos pasos que antes eran alternativos.

### E6-GUARDIA-punto2-precondicion-dura [reconcile]
**Ancla:** main.py:12191 — GUARDIA DE BÚSQUEDA AUTOMÁTICA DE FECHA, punto 2
**VIEJO (intent/texto):** 2. Si ya contás con el tratamiento y la cobertura (obra social/particular) resueltos, y el paciente **NO dio ninguna preferencia de fecha o día**, está PROHIBIDO preguntarle "para cuándo querés" antes de buscar. Llamá de forma AUTOMÁTICA a check_availability con date_query="lo antes posible", interpreted_date="{tomorrow_iso}" (calculada respecto a la fecha de hoy), y search_mode="open".
**NUEVO (exacto):** 2. SOLO cuando ya cumpliste el punto 1 (tenés el tratamiento Y la cobertura particular/obra social resueltos): si el paciente **NO dio ninguna preferencia de fecha o día**, está PROHIBIDO preguntarle "para cuándo querés" antes de buscar. Llamá de forma AUTOMÁTICA a check_availability con date_query="lo antes posible", interpreted_date="{tomorrow_iso}" (calculada respecto a la fecha de hoy), y search_mode="open", y ofrecé 2 opciones concretas. Si la cobertura todavía falta (punto 1 incompleto), NO ejecutes este punto: primero la pregunta de cobertura.
**Por que:** El bloque mezclaba una precondición dura (punto 1: cobertura) con un mandato agresivo (punto 2: ‘AUTOMÁTICA’, ‘PROHIBIDO preguntar para cuándo’) que el modelo podía priorizar saltando el punto 1. El ‘SOLO cuando ya cumpliste el punto 1’ ata el mandato de automatización a la precondición. De paso refuerza la iniciativa (‘ofrecé 2 opciones concretas’).
**Riesgo:** Bajo. La condición ‘Si ya contás con … la cobertura … resueltos’ ya existía; esto solo la hace gobernante explícita del punto 2.

### E7-script-habitual-iniciativa [reconcile]
**Ancla:** main.py:11727 — EXCEPCIÓN CRÍTICA paciente que vuelve, script modelo
**VIEJO (intent/texto):** "Ah, perfecto, entonces ya te conoce la Dra. {prof_display}. Vamos a coordinar esa [tratamiento que pidió]. ¿Te atendés de forma particular o con obra social? Y contame cuándo te queda bien 😊"
**NUEVO (exacto):** "Ah, perfecto, entonces ya te conoce la Dra. {prof_display}. Vamos a coordinar esa [tratamiento que pidió]. ¿Te atendés de forma particular o con obra social? 😊" (NO agregues "contame cuándo te queda bien": una vez resuelta la cobertura, si el paciente no dio preferencia de fecha buscá vos y ofrecé 2 opciones concretas — GUARDIA DE BÚSQUEDA AUTOMÁTICA. Si el paciente ya dijo un día/franja, usá esa.)
**Por que:** Alinea el script del paciente habitual con la GUARDIA (~12191), que prohíbe preguntar ‘para cuándo’ cuando no hay preferencia. El ‘contame cuándo te queda bien’ era justo el ‘decime qué día’ que el dueño critica como falta de iniciativa. Mantiene la cobertura ANTES de check_availability (secuencia deseada intacta).
**Riesgo:** Bajo. No toca la cobertura ni el reconocimiento del historial; solo cambia la última frase por ofrecer en vez de preguntar la fecha.

### E8-CAMINO3-encuadre-siempre [reconcile]
**Ancla:** main.py:12552 — FLUJO DE MODALIDAD DE ATENCIÓN, CAMINO 3 — SIN OS / PARTICULAR
**VIEJO (intent/texto):** CAMINO 3 — SIN OS / PARTICULAR: Aplicá la REGLA DE PRESENTACIÓN DEL PRECIO DE CONSULTA (valor + descripción de la evaluación). NUNCA solo el número. Luego continuá con el agendamiento.
**NUEVO (exacto):** CAMINO 3 — SIN OS / PARTICULAR: encuadrá SIEMPRE la evaluación con valor (aplicá la REGLA DE PRESENTACIÓN DEL PRECIO DE CONSULTA: valor + qué incluye la evaluación — la doctora evalúa el caso y orienta sobre las opciones). NUNCA ofrezcas el turno particular ‘seco’ (solo día/hora sin encuadre) ni solo el número. Este encuadre va aunque el paciente NO haya preguntado el precio: al resolverse que es particular, el primer mensaje ya lleva el valor + descripción, y recién ahí (o en la burbuja siguiente) ofrecés los turnos.
**Por que:** Cierra el hueco de sequedad: hoy el encuadre rico solo se dispara si el paciente pregunta precio (F5). Al reconciliar la compuerta de cobertura, todo particular pasa por CAMINO 3; agregar ‘SIEMPRE … aunque no haya preguntado el precio’ garantiza el encuadre de alto ticket sin inventar un bloque nuevo. No alarga el flujo de implantes/F6 (que sigue siendo corto por orden de la doctora).
**Riesgo:** Medio-bajo. Podría sentirse más largo en turnos triviales, pero la REGLA DE PRESENTACIÓN ya es de 2-3 líneas y el dueño pidió explícitamente encuadrar la evaluación; no se toca la orden de brevedad de implantes/F2.

## Preserva: Fix ‘particular particular’ (F4/M1, main.py:11846): NINGUNA edición toca ese bloque. La línea ‘No trabajamos de forma directa con [provider_name]’ sigue siendo exclusiva para una OS real not_found/rejected; jamás se usa con ‘particular’. Ninguna de mis ediciones introduce esa frase., F2 dolor/urgencia con prioridad (11818-11831): preservado explícitamente. E1 agrega ‘ÚNICA salvedad: F2 … cobertura integrada en M3’ y E6 no lo toca. La regla ‘contener primero, cobertura en M3 junto a las opciones’ queda intacta., No re-preguntar cobertura ya conocida: reforzado. E1/E2/E4 empiezan por ‘si YA sabés la cobertura → ejecutá directo’; el bloque 11674 (‘ESTRICTAMENTE PROHIBIDO volver a preguntarla’) y PASO 2c (12128) quedan sin cambios., No re-preguntar nombre/DNI ya dados (REGLA POST-DATOS 12124 y ADMISIÓN 12038-12044): E4 conserva ‘ya dio nombre y DNI’ como condición; solo suma la cobertura como condición adicional, no re-pide datos., Profesional INTERNO (PASO 3, 12157-12162): ninguna edición lo nombra ni lo expone; E5/E7/E8 hablan de día/hora/valor, nunca del profesional antes de confirmar., Pitch de saludo data-driven (greeting_specialty desde tenants.system_prompt_template, ~11367): NO se toca en ninguna edición; el dueño lo quiere igual., Pipeline del prompt (CLAUDE.md §6): todas las ediciones son reconciliación de texto existente en build_system_prompt — no hardcodean comportamiento nuevo ni agregan tags sin safety-net; no requieren cambios de DB.
## Open questions:
- E8 (encuadre SIEMPRE en CAMINO 3) es la única edición que puede alargar levemente turnos particulares triviales. Si el dueño prefiere el encuadre solo cuando el ticket es alto (evaluación de implantes/prótesis) y no en una limpieza particular, se puede acotar E8 a ‘servicios de la Dra./premium’ en vez de ‘SIEMPRE’. Confirmar preferencia.
- Verificar en producción que el modelo gpt-5.4-mini respeta la nueva condición compuesta de REGLA CERO (‘intención + fecha en un mensaje NO habilita saltear’) con 2-3 conversaciones de prueba del caso exacto reportado antes de promover de PRUEBAS a PROD.
- Las anclas de línea (11412, 11727, 11963, 12060, 12112, 12124, 12191, 12552) son las del estado actual del archivo en la rama feat/blindaje-agente; si otra consola aplicó cambios al prompt en paralelo, re-confirmar el texto viejo exacto antes de aplicar cada Edit (usar el ancla de texto, no el número de línea).