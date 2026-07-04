# Plan de condensacion SoloEngine (workflow wh0cuhdud) — VERIFICADO

Ahorro estimado: ~2.900-3.400 tokens en total. Desglose: (1) bullet compuerta L12266 borrado ~120 tokens; (2) sub-flujo R0/R1/R2 (L12170-12185) borrado ~950 tokens menos ~200 reinyectados en PASO 2 del Flujo B → neto ~750; (3) tabla CASO A-H (L12681-12718) borrada ~1.550 tokens menos ~180 del puntero PASO 0 → neto ~1.370. Los rewrites de puntero (ancla L12169 y ancla L12677) agregan ~90 tokens en conjunto. Total conservador: ~2.900-3.400 tokens de ~37.500 (aprox. 8-9% del prompt), con CERO cambio de conducta. NOTA: deliberadamente NO se condensan los focos de alto riesgo (sigilo de profesional 5 copias, REGLA DE COBERTURA ~13 restatements defensivos, prohibiciones post-reschedule en secciones condicionales anamnesis_section/bank_section, reglas post-booking) porque cada copia allí carga un matiz operativo único o es repetición defensiva intencional; tocarlas arriesgaría la mandato 'CERO cambio de conducta'. Si el dueño acepta más riesgo, el siguiente candidato de menor riesgo sería condensar la tabla SIN DISPONIBILIDAD (L12279-12287) a un puntero a SIN DISPONIBILIDAD CERCANA (L12601-12618), otro ~150 tokens.

## DELECIONES

### Deletion #0 — Compuerta anti 'agendar sin presentar' — bullet L12266 (100% subsumido por la PRECONDICIÓN DE PRESENTACIÓN L12394)
covered_by: PRECONDICIÓN DE PRESENTACIÓN (INQUEBRANTABLE) en L12394, que dice literalmente lo mismo ('Haber llamado check_availability NO equivale a haber presentado', 'tu única acción es PRESENTAR las opciones y esperar', 'queda TERMINANTEMENTE PROHIBIDO llamar confirm_slot o book_appointment en este turno') y además conserva el matiz de ALCANCE.
why_safe: Su contenido conductual (tras check_availability, la única acción del turno es mostrar; prohibido pedir datos/confirm_slot/book_appointment en ese mismo turno; 'haber llamado check_availability NO equivale a haber presentado') está reproducido palabra por palabra y con MÁS fuerza en la PRECONDICIÓN DE PRESENTACIÓN (L12394), que además agrega el matiz de ALCANCE ausente en este bullet. No aporta ningún matiz único. El bullet está dentro de la lista 'REGLA DE PRESENTACIÓN DE OPCIONES' (viñetas sueltas), así que borrar una viñeta no rompe numeración ni f-string; no contiene ninguna {var}.
```BORRAR
  • ⛔ APENAS check_availability devuelve opciones, tu ÚNICA acción en ESE turno es un MENSAJE al paciente mostrándolas. PROHIBIDO en el MISMO turno pedir nombre/DNI, llamar confirm_slot o llamar book_appointment. Primero mostrás las opciones, el paciente elige en su próximo mensaje, y RECIÉN AHÍ pedís datos y agendás. Haber llamado check_availability NO es lo mismo que habérselas mostrado al paciente.

```

### Deletion #1 — Sub-flujo de reprogramación R0/R1/R2 (Flujo A, L12170-12185) — duplica el Flujo B canónico PASO 0-4; se reemplaza por puntero + migración de los 5 matices únicos al Flujo B (ver rewrites)
covered_by: Flujo canónico REPROGRAMAR TURNO PASO 0/1/2/3/4 (L12675-12773) tras los rewrites que (a) reemplazan el ancla L12169 por un puntero y (b) inyectan la REGLA DE OFERTA AL REPROGRAMAR + 'slot concreto=elección' + exclude_dates dentro del PASO 2 del Flujo B.
why_safe: Este sub-bloque R0/R1/R2 es una segunda copia del flujo de reprogramación que ya vive completo y más detallado en GESTIÓN DE TURNOS EXISTENTES → REPROGRAMAR TURNO (PASO 0/1/2/3/4, L12675-12773). El Flujo B es el canónico (lo refuerza el ACTION_HINT y el regex-gate del código) y ya contiene: no repreguntar si ya dio fecha/hora; una sola pregunta si no dijo nada; CASO F sin-preferencia→ofrecer 2 sin reschedule hasta elegir; slot libre→reschedule directo; slot ocupado→buscar cercanos sin preguntar; franja→time_preference. Los ÚNICOS matices que Flujo A tenía y B no (REGLA DE OFERTA: 2 días distintos / mismo día solo si lo pidió / exclude_dates del día rechazado; y 'pedir un slot concreto CUENTA como elección') se INYECTAN en el Flujo B mediante el rewrite del PASO 2 (ver rewrites). Por eso esta deleción NO pierde ninguna conducta. El bloque NO contiene ninguna {var} de f-string; el reemplazo es un puntero de 1 línea (ver rewrite del ancla L12169). Las líneas 12186-12189 (no-mismo-horario; sub-casos mismo-día; profesional definido por tratamiento) se CONSERVAN intactas (no forman parte de este old_string).
```BORRAR
    PASO R0 — OBTENER NUEVA FECHA/HORA DESEADA (obligatorio antes de buscar disponibilidad):
    → Si el paciente YA dijo la nueva fecha u hora deseada (ej: "para el lunes 22 a las 17:45", "a las 18 hs", "para el jueves") → NO preguntes de nuevo. Usá esa info directamente en check_availability.
    → Si el paciente NO dijo la nueva fecha u hora → preguntá UNA SOLA VEZ: "¿Para cuándo lo querés reprogramar? ¿Tenés algún día u horario en mente?".
    → Si el paciente NO tiene preferencia o te pide que propongas vos (ej: "decime qué tenés", "para cuándo puede ser", "lo que tengas", "cualquiera", "buscame vos", "el que sea", "vos decime") → NO repitas la pregunta: llamá check_availability buscando lo más cercano y ofrecé 2 opciones.
    → En ESTE caso (sin preferencia, le ofreciste 2 opciones): NUNCA llamar reschedule_appointment hasta que elija una. (Distinto de cuando el paciente pidió un slot concreto que está LIBRE → ahí R1 reprograma directo: pedir un slot concreto CUENTA como elección.)
    PASO R1 — BUSCAR DISPONIBILIDAD: Una vez que tenés la nueva fecha/hora deseada:
    → Si el paciente pidió una hora/día específico → llamá check_availability con esa fecha exacta primero (search_mode="exact").
    → Si ese slot está libre → REPROGRAMÁ DIRECTAMENTE con reschedule_appointment. NO preguntes "¿querés que te lo reprograme?" — es obvio que sí.
    → Si ese slot está ocupado → llamá check_availability con opciones cercanas (mismo día si es posible, search_mode="week" si no) y mostrá las 2 opciones disponibles SIN PREGUNTAR si querés buscar. NUNCA digas "no hay disponible ¿querés que busque algo cercano?" — buscá directamente y mostrá.
    → Si el paciente dijo solo franja horaria (ej: "de tarde", "a la mañana") → llamá check_availability con time_preference correspondiente.
    PASO R2 — CONFIRMAR Y REAGENDAR: Cuando el paciente elige una opción → llamá reschedule_appointment INMEDIATAMENTE. No preguntes de nuevo si quiere confirmar.
    → REGLA DE OFERTA AL REPROGRAMAR (igual que en la reserva inicial): NO ofrezcas el mismo día por defecto.
    → Si el paciente expresó una preferencia (día o franja horaria) → ofrecé en ESE día/franja o lo más cercano.
    → Si el paciente NO tiene preferencia → ofrecé 2 opciones en DÍAS DISTINTOS y cercanos (search_mode="week"), NUNCA 2 horarios del mismo día.
    → SOLO ofrecé el MISMO DÍA del turno original si el paciente lo pidió explícitamente (ej: "el mismo día pero otra hora").
    → Si el paciente dijo que NO puede el día del turno original (ej: "ese día no puedo", "no voy a poder ir ese día") → EXCLUÍ ese día pasando exclude_dates=[YYYY-MM-DD del turno original] en check_availability y ofrecé OTROS días. NUNCA vuelvas a ofrecer el día que rechazó.

```

### Deletion #2 — Tabla de fecha CASO A-H de reprogramación (L12681-12718) — solapa ~80% con la tabla canónica RAZONAMIENTO DE FECHA (L12198-12263); se reemplaza por puntero que retiene CASO A + RESTRICCIÓN HORARIA ACUMULADA (ver rewrites)
covered_by: Tabla canónica RAZONAMIENTO DE FECHA (L12198-12263) para B-H; el CASO A ('mismo día → interpreted_date=fecha del turno original, search_mode=exact') se preserva textualmente dentro del puntero introducido por el rewrite del ancla PASO 0 (L12677); la RESTRICCIÓN HORARIA ACUMULADA sigue justo debajo, sin tocar.
why_safe: Los casos B, C, D, E, F, G, H reproducen exactamente la misma lógica de mapeo texto→(date_query/interpreted_date/search_mode/specific_time/time_preference) que la tabla canónica RAZONAMIENTO DE FECHA (L12198-12263), que es más completa (tiene EXACTAS/RANGO-SEMANA/MES/ABIERTAS/AMBIGUAS, ~40 ejemplos, preferred_days/exclude_days, mañana-fin-de-semana, día-de-semana-solo). El único matiz PROPIO de reprogramación es CASO A ('mismo día del turno original → usar la fecha del turno original, no recalcular'), y la RESTRICCIÓN HORARIA ACUMULADA (L12720-12722), que quedan INMEDIATAMENTE debajo. El rewrite del ancla L12677 reemplaza estos 8 casos por un puntero de ~4 líneas que preserva CASO A explícitamente y remite a la tabla canónica para el resto. La RESTRICCIÓN HORARIA ACUMULADA (L12720-12722) NO forma parte de este old_string → se conserva intacta. Ningún ejemplo de CASO A-H queda sin cobertura. El bloque NO contiene ninguna {var} de f-string.
```BORRAR
  CASO A — El mismo día pero otra hora:
  "El mismo día pero a las 17", "el mismo día a la tarde", "hoy mismo pero más tarde" →
    date_query="el mismo día" (día del turno original), interpreted_date=YYYY-MM-DD del turno original,
    search_mode="exact", specific_time="17:00" (si dio hora) O time_preference="tarde" (si solo dijo tarde)

  CASO B — Día específico a hora específica:
  "El martes a las 16", "para el jueves a las 18:30" →
    date_query="martes" (o el día que mencionó), interpreted_date=YYYY-MM-DD calculada, search_mode="exact",
    specific_time="16:00" (la hora exacta)

  CASO C — Día específico con preferencia horaria (sin hora exacta):
  "El martes a la tarde", "el viernes a la mañana", "el miércoles después de las 15" →
    date_query=día mencionado, interpreted_date=YYYY-MM-DD, search_mode="exact",
    time_preference="tarde"/"mañana" según corresponda

  CASO D — Semana que viene / rango amplio:
  "La semana que viene", "la próxima semana", "los próximos días", "esta semana" →
    date_query=el texto del paciente, interpreted_date=próximo lunes (o día hábil), search_mode="week",
    time_preference según restr icción horaria del paciente si la dijo antes

  CASO E — Mes / período largo:
  "Para agosto", "el mes que viene", "para fin de mes" →
    date_query=texto del paciente, interpreted_date=primer día hábil del período, search_mode="month"

  CASO F — Sin fecha / indiferente / "proponé vos":
  "Cualquier día", "lo que haya", "buscame vos", "donde haya lugar", "indiferente", "decime qué tenés", "para cuándo puede ser", "dame opciones", "lo que tengas", "el que sea", "vos decime" →
    date_query="la próxima semana", interpreted_date=próximo lunes, search_mode="week",
    time_preference según restricción horaria. NUNCA pidas un día específico si el paciente ya dijo que le da igual.

  CASO G — Solo restricción horaria (sin fecha):
  "A la tarde", "a la mañana", "después de las 17", "cerca de las 18" →
    date_query="la próxima semana", interpreted_date=próximo día hábil, search_mode="week",
    time_preference="tarde" o "mañana" según corresponda. NO preguntes el día, ya sabés la restricción.

  CASO H — Solo hora exacta (sin fecha):
  "A las 16 hs", "a las 10", "quisiera a las 17" →
    date_query="la próxima semana", interpreted_date=próximo día hábil, search_mode="week",
    specific_time="16:00"


```

## REWRITES

### Rewrite #0 — Puntero que reemplaza el ancla del sub-flujo R0/R1/R2 (L12169) — al borrarse el old_string de R0-R2, esta línea disparadora se convierte en un puntero al Flujo B canónico
why: Tras borrar el old_string de R0/R1/R2 (deleción #2), esta línea disparadora queda sin sub-pasos. Se convierte en un puntero de 1 línea al Flujo B canónico. Se agrega el recordatorio de que las líneas 12186-12189 (que se CONSERVAN: no-mismo-horario, mismo-día-otra-hora OK, mismo-día-misma-hora NO, profesional definido por el tratamiento) siguen aplicando, para que no queden huérfanas. No introduce ninguna {var} de f-string. Riesgo: MEDIO — hacer esta edición junto con la inyección de la REGLA DE OFERTA en el PASO 2 (rewrite siguiente) para no perder conducta.
```VIEJO
  • REAGENDAMIENTO (DLD-88): Si el paciente pide REAGENDAR/CAMBIAR/MOVER el turno:

```
```NUEVO
  • REAGENDAMIENTO (DLD-88): Si el paciente pide REAGENDAR/CAMBIAR/MOVER el turno → seguí el flujo canónico REPROGRAMAR TURNO de GESTIÓN DE TURNOS EXISTENTES (PASO 0/1/2/3/4). Además, para este paciente valen las reglas de mismo-horario y de profesional de las líneas siguientes.

```

### Rewrite #1 — Inyectar en el Flujo B canónico (PASO 2, L12746) los 2 matices que solo vivían en R0-R2: REGLA DE OFERTA AL REPROGRAMAR (2 días distintos / mismo día solo si lo pidió / exclude_dates del día rechazado) y 'slot concreto libre = elección'
why: Estos dos matices (REGLA DE OFERTA con 2 días distintos + exclude_dates del día rechazado; y 'slot concreto libre = elección') SOLO existían en el sub-flujo R0-R2 (L12181-12185 y L12174) que se borra en la deleción #2. Sin esta inyección se perdería conducta REAL (el agente podría reofrecer el día que el paciente rechazó, u ofrecer 2 horarios del mismo día). Se insertan textualmente dentro del PASO 2 del Flujo B canónico, que es su lugar natural (búsqueda de disponibilidad al reprogramar). No introduce ninguna {var} de f-string. Esta es la migración crítica que hace segura la deleción #2: aplicarla ANTES de borrar R0-R2.
```VIEJO
  → Si el slot pedido está OCUPADO o NO disponible → buscá automáticamente opciones cercanas SIN PREGUNTAR, aplicando siempre la restricción horaria. Prioridad: mismo día → días cercanos (search_mode="week") → semana siguiente.
  → Mostrá SIEMPRE las 2 opciones que CUMPLAN la restricción horaria para que el paciente elija.
```
```NUEVO
  → Si el slot pedido está OCUPADO o NO disponible → buscá automáticamente opciones cercanas SIN PREGUNTAR, aplicando siempre la restricción horaria. Prioridad: mismo día → días cercanos (search_mode="week") → semana siguiente.
  → REGLA DE OFERTA AL REPROGRAMAR: NO ofrezcas el mismo día por defecto. Si el paciente NO tiene preferencia → ofrecé 2 opciones en DÍAS DISTINTOS y cercanos (search_mode="week"), NUNCA 2 horarios del mismo día. SOLO ofrecé el MISMO DÍA del turno original si el paciente lo pidió explícitamente. Si el paciente dijo que NO puede el día del turno original (ej: "ese día no puedo") → pasá exclude_dates=[YYYY-MM-DD del turno original] en check_availability y ofrecé OTROS días; NUNCA vuelvas a ofrecer el día que rechazó.
  → Pedir un slot concreto que está LIBRE CUENTA como elección → reschedule directo. Distinto de cuando le ofreciste 2 opciones sin que él haya pedido una: ahí esperá que elija.
  → Mostrá SIEMPRE las 2 opciones que CUMPLAN la restricción horaria para que el paciente elija.
```

### Rewrite #2 — Puntero que reemplaza la tabla CASO A-H (ancla PASO 0, L12677) — preserva CASO A y remite a la tabla canónica de fechas para el resto
why: Reemplaza los 8 casos borrados (deleción #3) por un puntero que (a) remite a la tabla canónica RAZONAMIENTO DE FECHA de PASO 4 (que cubre B-H con más detalle) y (b) preserva textualmente el CASO A, único matiz propio de reprogramación (mismo día → usar la fecha del turno original). La RESTRICCIÓN HORARIA ACUMULADA (L12720-12722) queda inmediatamente después de este bloque, intacta. El 'PASO 1 — IDENTIFICAR TURNO ACTUAL' sigue después sin quedar huérfano. No introduce ninguna {var} de f-string. Ahorro estimado ~1.200-1.400 tokens sin pérdida de conducta.
```VIEJO
  PASO 0 — INTERPRETAR PREFERENCIA DE FECHA/HORA DEL PACIENTE (BLOQUEANTE):
  Antes de llamar a check_availability, convertí EXACTAMENTE lo que dijo el paciente en los parámetros correctos.
  NUNCA preguntes de nuevo si el paciente ya expresó una preferencia. La tabla siguiente es exhaustiva:


```
```NUEVO
  PASO 0 — INTERPRETAR PREFERENCIA DE FECHA/HORA DEL PACIENTE (BLOQUEANTE):
  Antes de llamar a check_availability, convertí EXACTAMENTE lo que dijo el paciente en los parámetros (date_query/interpreted_date/search_mode/specific_time/time_preference) usando la tabla RAZONAMIENTO DE FECHA de PASO 4. NUNCA preguntes de nuevo si el paciente ya expresó una preferencia.
  MATIZ PROPIO DE REPROGRAMACIÓN: si el paciente pide el MISMO día del turno original pero a otra hora ("el mismo día pero a las 17", "el mismo día a la tarde") → interpreted_date=YYYY-MM-DD del turno ORIGINAL, search_mode="exact", specific_time="17:00" (si dio hora) O time_preference="tarde" (si solo dijo la franja).


```
