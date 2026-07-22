"""Inyecciones frescas + candados puros COMPARTIDOS (banco v2, 2026-07-20).

Funciones PURAS (sin BD, sin logger): reciben strings y devuelven la inyección
de contexto (o None) / la respuesta ajustada. Las usa buffer_task.py en prod y
eval/run.py en el banco — UNA sola fuente de verdad, sin espejos a mano.

Origen (17 fallos del banco v2, 95/112):
- derivacion-humano-explicito: prometió "te paso con el equipo" SIN derivhumano.
- rp-cancelar / reprog-cancelar-definitivo: pidió cancelar y el bot re-pregunta.
- turnos-dobles x2: no reconoce que son DOS personas / cobertura de cada uno.
- os-ioma / os-galeno: OS nombrada ignorada o con precio particular encima.
- edge-enojado: queja de precio sin defensa del valor.
- terce-hermana / recurrente-implante: globito muerto (pide turno, bot no avanza).
- matias-elige-uno: confirma 1 de 2 turnos y no pregunta por el otro.
"""
from __future__ import annotations

import re

# OS de la clínica SIN issn (ISSN tiene su bloque específico en buffer_task).
_OS_MSG_PATTERN = (
    r"\b(osde|sancor|swiss(?:\s+medical)?|galeno|ioma|osdepym|sosunc|osseg"
    r"|jer[aá]rquicos|medif[eé]|omint|luis pasteur|prevenci[oó]n"
    r"|apsot|mca|am[eé]rica|bancarios|siaco|credi.?gu[ií]a|federada|medicus|poder judicial)\b"
)


def iny_derivacion_explicita(last_user: str) -> str | None:
    """El paciente PIDE hablar con una persona → la única acción válida es derivhumano."""
    t = (last_user or "").lower()
    if not re.search(
        r"(hablar|comunicar(?:me)?|contactar(?:me)?|atienda|charlar|escribir)"
        r".{0,40}(persona|humano|alguien del equipo|una chica|secretari|recepci[oó]n|doctora|equipo)"
        r"|con una persona (?:del equipo|real)"
        r"|no quiero hablar con (?:un )?(?:bot|robot|una m[aá]quina)"
        r"|quiero que me atienda (?:una persona|alguien)"
        r"|pasame con (?:alguien|una persona|la secretaria|el equipo)",
        t,
    ):
        return None
    return (
        "🚨 EL PACIENTE PIDE EXPLÍCITAMENTE HABLAR CON UNA PERSONA: tu ÚNICA acción válida es "
        "llamar derivhumano AHORA (motivo: 'pide hablar con una persona del equipo') y recién "
        "después confirmarle que lo pasás. ⛔ PROHIBIDO responder 'te paso con el equipo' SIN "
        "haber llamado derivhumano en ESTE turno — la promesa sin la herramienta deja al "
        "paciente colgado esperando a nadie."
    )


def iny_pide_cancelar(user_texts: list[str] | None, last_bot: str = "") -> str | None:
    """El paciente pidió CANCELAR (en este mensaje o en los recientes) → ejecutar, no re-preguntar.

    user_texts: mensajes del PACIENTE recientes (el actual último). Si el último
    mensaje del bot ya confirmó la cancelación, no dispara (pedido ya cumplido).
    """
    joined = " ".join(user_texts or []).lower()
    if not joined:
        return None
    pide = re.search(r"\b(cancelar?|cancelame|cancel[aá]|anular?|dar de baja)\b", joined)
    reprograma = re.search(r"reprogram|cambiar|mover|pasar(?:lo)? (?:a|para)|otro d[íi]a", joined)
    if not pide or reprograma:
        return None
    if re.search(r"(?i)cancelad[oa]|cancel[eé] tu turno|qued[oó] cancelado", last_bot or ""):
        return None  # ya se canceló en el hilo
    return (
        "🚨 EL PACIENTE PIDE CANCELAR SU TURNO (no reprogramar): EJECUTALO en este turno. "
        "1) Mirá sus turnos con list_my_appointments si aún no lo hiciste. "
        "2) Si tiene UN solo turno futuro, llamá cancel_appointment YA y confirmale la cancelación "
        "— ⛔ PROHIBIDO re-preguntar '¿querés que lo cancele?' o '¿cuál?' cuando hay uno solo: ya lo pidió. "
        "3) Si tiene VARIOS, nombralos y preguntá cuál. "
        "4) NO insistas en reagendarlo: cancelá, decile que queda hecho y que cuando quiera "
        "retomar te escriba. Si no podés ejecutar la cancelación ahora, decile que la gestionás "
        "con el equipo (y llamá derivhumano) — nunca lo dejes sin respuesta concreta."
    )


def iny_multi_persona(last_user: str) -> str | None:
    """Piden turno para DOS personas → reconocer los dos turnos + cobertura de CADA UNO."""
    t = (last_user or "").lower()
    if not re.search(
        r"para m[ií]\w*.{0,12}y (?:tambi[eé]n )?(?:para )?mi \w+"
        r"|para mi \w+.{0,28}y (?:tambi[eé]n )?para m[ií]\b"
        r"|los dos (?:queremos|necesitamos|nos)"
        r"|ambos (?:queremos|necesitamos)"
        r"|mi (?:espos[oa]|marido|mujer|se[ñn]ora|mam[aá]|madre|pap[aá]|padre|herman[oa]|hij[oa]|novi[oa]|suegr[oa]) y yo\b",
        t,
    ):
        return None
    return (
        "👥 SON DOS PERSONAS (DOS turnos): reconocé explícitamente que vas a coordinar los DOS "
        "turnos ('coordinamos los dos turnos' / 'para ambos') y preguntá la cobertura DE CADA UNO "
        "por separado — por ejemplo: '¿Cada uno cuenta con obra social, o alguno se atendería de "
        "forma particular?'. ⛔ NO asumas que comparten cobertura ni preguntes en singular como si "
        "fuera una sola persona. Al agendar, cada uno lleva su propio turno con sus propios datos."
    )


_QUEJA_PRECIO_PAT = re.compile(
    r"es (?:un|una) (?:robo|locura|estafa|barbaridad)"
    r"|(?:es|me parece|qu[eé]|re|muy|super|tan) car[oa]\b|car[íi]sim[oa]"
    r"|no puede (?:ser|salir) (?:tan caro|eso)|es mucho para una consulta"
    r"|no pienso pagar eso|una fortuna"
)


def queja_precio_matchea(texto: str) -> bool:
    return bool(_QUEJA_PRECIO_PAT.search((texto or "").lower()))


def iny_queja_precio(last_user: str) -> str | None:
    """Queja del precio → defender el VALOR con calidez, sin disculpas ni descuentos."""
    if not queja_precio_matchea(last_user):
        return None
    return (
        "💬 EL PACIENTE SE QUEJA DEL PRECIO: NO pidas disculpas, NO regatees ni inventes descuentos, "
        "y NO cambies de tema. Defendé el VALOR con calidez: explicá brevemente QUÉ INCLUYE la "
        "consulta de evaluación (evaluación clínica completa con la doctora, diagnóstico y plan de "
        "tratamiento con su presupuesto) y que ese paso evita gastos de más después. Validá su "
        "preocupación ('entiendo que es una inversión') y dejale la puerta abierta a coordinar "
        "cuando quiera — sin presionar."
    )


# OS que el paciente puede nombrar pero NO tienen convenio con la clínica (panel
# real tenant 1, sync 2026-07-20) → encuadre directo: particular + comprobante.
_OS_NO_PANEL_PAT = re.compile(
    r"(?i)\b(swiss(?:\s+medical)?|ioma|osdepym|omint|luis pasteur|prevenci[oó]n)\b"
)


def iny_os_en_mensaje(last_user: str) -> str | None:
    """OS nombrada en el mensaje → reconocerla, verificar antes de afirmar, sin precio particular."""
    t = (last_user or "").lower()
    m_np = _OS_NO_PANEL_PAT.search(t)
    if m_np:
        os_np = m_np.group(1).title()
        return (
            f"🏥 EL PACIENTE NOMBRÓ {os_np}, que NO tiene convenio con la clínica: "
            f"1) Reconocela y aclaráselo con calidez, SIN inventar convenio ('con {os_np} no tenemos "
            "convenio directo'). 2) El encuadre es atención PARTICULAR y SIEMPRE mencionás que la "
            "clínica entrega el comprobante/recibo para que pueda gestionar el reintegro con su "
            "cobertura. 3) Después seguí el flujo normal hacia el turno (si es para un tercero, "
            "detectalo y sus datos se piden al agendar)."
        )
    m = re.search(_OS_MSG_PATTERN, t)
    if not m:
        return None
    os_name = m.group(1).upper()
    return (
        f"🏥 EL PACIENTE NOMBRÓ SU OBRA SOCIAL ({os_name}): "
        f"1) RECONOCELA explícitamente en tu respuesta (aunque haya dolor/urgencia: un 'anotado lo "
        f"de {os_name}' basta — no la ignores). "
        f"2) Si tenés la herramienta check_insurance_coverage y todavía no verificaste {os_name} en "
        "esta conversación, verificala ANTES de afirmar 'sí, trabajamos con ella'. "
        "3) Si su OS tiene convenio, NO le des el valor particular de la consulta como si fuera su "
        "precio (su encuadre es por cobertura, con coseguro si corresponde y SIN cifras del "
        "coseguro por chat) — la única excepción es que pregunte explícitamente cuánto sale "
        "atenderse particular."
    )


# ---------------------------------------------------------------------------
# Regex del MANEJO DE COSEGURO (compartidos con buffer_task; ampliados con el
# caso post-confirmacion: "No debo abonar algo adicional?" también es pregunta
# de coseguro y merece el encuadre cálido, no un "sí, trabajamos con OSDE" seco)
# ---------------------------------------------------------------------------

def es_pregunta_monto_coseguro(texto: str) -> bool:
    t = (texto or "").lower()
    return bool(
        re.search(
            r"(cu[aá]nto|de cu[aá]nto|qu[eé] monto|qu[eé] valor).{0,30}coseguro"
            r"|coseguro.{0,35}(cu[aá]nto|monto|valor|sale)"
            r"|(?:debo|tengo que|hay que|deber[íi]a|va a haber que)\s*(?:abonar|pagar).{0,25}(?:adicional|algo m[aá]s|extra|aparte)"
            r"|abonar algo (?:adicional|m[aá]s|extra)"
            r"|alg[uú]n (?:adicional|extra|copago|coseguro)"
            r"|cubre todo o (?:pago|abono) algo",
            t,
        )
    )


def es_confusion_sena(texto: str) -> bool:
    t = (texto or "").lower()
    return bool(
        re.search(
            r"(solo|solamente|nada m[aá]s).{0,25}(consulta|x consulta|por consulta).{0,20}(30|treinta|se[ñn]a|mil)"
            r"|consulta son \$?\s?\d",
            t,
        )
    )


def es_insistencia_monto(texto: str) -> bool:
    """Insistencia por un monto SIN nombrar 'coseguro' ('dale pero un aproximado...',
    '10, 20, 50 lucas?', 'cuánta plata llevo') — cuenta como pregunta de coseguro
    SOLO si el hilo de coseguro ya estaba abierto (ya_explicado >= 1)."""
    t = (texto or "").lower()
    return bool(
        re.search(
            r"aproximad|m[aá]s o menos|una cifra|un n[uú]mero|aunque sea"
            r"|decime cu[aá]nto|\d+\s*(?:lucas|mil|k)\b|cu[aá]nta plata|qu[eé] monto",
            t,
        )
    )


def iny_acepto_ofrecimiento(last_user: str, last_bot: str) -> str | None:
    """El bot ofreció algo condicional ('si querés te busco...' / 'le paso tu consulta
    al equipo, ¿te sirve?' / 'si querés te confirmo qué traer') y el paciente respondió
    que sí → EJECUTAR ya (caso Luis prod 2026-07-20; rama equipo por el coseguro nivel
    2; rama INFO por el caso Braian prod 2026-07-20: 'te confirmo qué te conviene
    traer' + 'dale' quedaba sin red — loop o inventaba requisitos)."""
    t = (last_user or "").lower().strip()
    _es_si = bool(
        re.fullmatch(
            r"(bueno|dale|s[ií]|ok(a|ey)?|listo|de una|obvio|perfecto|genial|joya|buen[íi]simo"
            r"|s[ií] dale|dale s[ií]|bueno dale|dale bueno|me parece( bien)?|est[aá] bien|me sirve"
            r"|s[ií],? dale,?( me sirve)?|s[ií],? me sirve|dale,? me sirve)[.!,\s😊👍🙏]*",
            t,
        )
    )
    # Aceptación con re-pedido corto ("dale, decime", "sí, decime qué llevo") — sin
    # señales de OTRA pregunta ("sí pero cuánto sale" NO es aceptación de la oferta).
    _es_si_corto = (
        not _es_si
        and len(t.split()) <= 6
        and bool(re.search(r"\b(dale|s[ií]|bueno|ok|decime|contame|me sirve)\b", t))
        and not re.search(r"\bpero\b|cu[aá]nto|precio|valor|d[oó]nde|direcci[oó]n", t)
    )
    if not (_es_si or _es_si_corto):
        return None
    b = (last_bot or "").lower()
    if not re.search(
        r"decime y te busco|te busco opciones|te paso (?:turnos|opciones|las opciones)"
        r"|quer[eé]s que (?:te )?(?:busque|pase|coordine|diga|confirme|cuente)|decime para qu[eé] d[íi]a"
        r"|si quer[eé]s.{0,45}(?:te )?(?:busco|paso|coordino|confirmo|digo|cuento|indico|detallo|aviso|explico)"
        r"|(?:le |te )?paso tu consulta al equipo|te sirve\?",
        b,
    ):
        return None
    if re.search(r"equipo|te confirman", b):
        return (
            "⚡ EL PACIENTE ACEPTÓ TU OFRECIMIENTO de pasar su consulta al EQUIPO: llamá "
            "derivhumano AHORA (motivo: lo que ofreciste que el equipo confirme, ej. 'confirmar "
            "el monto del coseguro de su plan') y avisale cálido que el equipo le responde a la "
            "brevedad. ⛔ PROHIBIDO re-preguntar o dejarlo en una promesa sin ejecutar."
        )
    if re.search(
        r"(?:confirmo|digo|cuento|indico|detallo|explico) qu[eé]"
        r"|qu[eé] (?:te )?conviene (?:traer|llevar)|qu[eé] (?:traer|llevar|necesit[aá]s (?:traer|llevar))",
        b,
    ):
        return (
            "⚡ EL PACIENTE ACEPTÓ TU OFRECIMIENTO DE INFORMACIÓN (qué traer/requisitos): "
            "respondé la INFO CONCRETA AHORA, en un solo mensaje, con los datos que TENGAS "
            "(requisitos del tratamiento del catálogo, FAQs de la clínica). Si no tenés el dato "
            "específico, decile lo estándar y seguro: DNI, credencial/carnet de la obra social si "
            "tiene, la orden (que puede mostrar virtual) y estudios previos si los tiene. "
            "⛔ PROHIBIDO volver a ofrecer ('¿querés que te diga?') — ya aceptó — y PROHIBIDO "
            "INVENTAR requisitos clínicos que nadie te dio (ayunos, suspender medicación, "
            "preparaciones): si te preguntan algo clínico que no sabés, se confirma con la doctora."
        )
    return (
        "⚡ EL PACIENTE ACEPTÓ TU OFRECIMIENTO: en tu último mensaje le ofreciste buscar/pasar "
        "opciones y respondió que SÍ ('bueno/dale'). EJECUTALO EN ESTA RESPUESTA: llamá la herramienta "
        "que corresponda (check_availability para opciones de turno; derivhumano si lo ofrecido fue "
        "pasar la consulta al equipo) y entregá el RESULTADO concreto. "
        "⛔ PROHIBIDO volver a preguntar 'decime cuándo/para qué día' o re-ofrecer sin resultados — "
        "eso ya lo dijiste y el paciente ya aceptó."
    )


def iny_manejo_coseguro(pregunta_monto: bool, confusion_sena: bool, ya_explicado: int = 0) -> str | None:
    """Manejo EMPÁTICO del coseguro (caso Agustín; pedido Carlos: 'llevarlos bien sin
    hacerlos enojar'). El monto es INTERNO (nunca una cifra por chat): lo que cambia
    es CÓMO se acompaña. 3 niveles: porqué cálido → salida concreta con el equipo →
    aclarar la confusión seña↔precio. Texto único compartido prod/banco."""
    if not (pregunta_monto or confusion_sena):
        return None
    gate = "💬 MANEJO DEL COSEGURO (el paciente pregunta el monto o confunde la seña con el precio — llevalo BIEN, sin frustrar): "
    if confusion_sena:
        gate += (
            "Está confundiendo la SEÑA con el precio de la consulta. Aclaráselo DIRECTO y amable: "
            "'No, tranquilo/a — ese monto es la seña OPCIONAL para reservar el turno, no el precio de la consulta. "
            "Con tu obra social la consulta va por tu cobertura; si corresponde un coseguro, te lo confirman en la clínica.' "
            "⛔ NO repitas la explicación completa del coseguro ni des cifras del valor de consulta. "
        )
    elif int(ya_explicado) >= 2:
        gate += (
            "YA le explicaste el coseguro en esta charla: NO repitas la misma frase (lo frustra). Dale una SALIDA CONCRETA: "
            "'El monto exacto depende del plan que tengas — si querés, le paso tu consulta al equipo y te confirman el valor "
            "de TU plan antes del turno, ¿te sirve?'. Si acepta, llamá derivhumano (motivo: 'Paciente quiere el monto exacto "
            "del coseguro de su plan — confirmarle'). Si su apuro es práctico (ej. 'cuánta plata llevo'), reconocéselo con "
            "empatía antes de la salida. ⛔ Nunca una cifra ni un rango por chat. "
        )
    else:
        gate += (
            "Explicale el PORQUÉ con calidez (no la muletilla seca): el coseguro depende del PLAN específico que tenga con su "
            "obra social — por eso no hay una cifra única — y se lo confirman en la clínica ANTES de atenderse, sin sorpresas. "
            "Cerrá con tranquilidad ('quedate tranquilo/a que te lo confirman apenas llegues, antes de atenderte') y seguí "
            "con el turno. ⛔ Nunca una cifra por chat. "
        )
    return gate


# ---------------------------------------------------------------------------
# "QUIERE ANTES" — semáforo de OS con demora (pedido Carlos 2026-07-20)
# ---------------------------------------------------------------------------

_QUIERE_ANTES_PAT = re.compile(
    r"(?i)no puedo esperar|esperar tanto|tanto tiempo|tan (?:lejos|adelante|tarde)"
    r"|(?:nada|algo|un hueco|un huequito|turno)s? (?:m[aá]s )?(?:antes|cerca|cercano)"
    r"|antes no (?:hay|ten[eé]s|se puede)|¿?no (?:hay|ten[eé]s) (?:nada|algo) antes"
    r"|m[aá]s pronto|lo antes posible no|es un mont[oó]n de (?:tiempo|d[íi]as|espera)"
    r"|reci[eé]n (?:para|el|en) .{0,20}\?|me urge|necesito (?:que sea )?antes|quiero (?:ir |atenderme )?antes"
    # Caso Lucas manual 2026-07-20: "Para mañana o pasado no tenes???" con OS demorada
    r"|para (?:hoy|ma[ñn]ana|pasado(?: ma[ñn]ana)?)(?: o (?:hoy|ma[ñn]ana|pasado(?: ma[ñn]ana)?))? no (?:ten[eé]s|hay|habr[aá])"
    r"|¿?(?:ten[eé]s|hay) (?:algo |turno |lugar )?para (?:hoy|ma[ñn]ana|pasado(?: ma[ñn]ana)?)\b"
)


def quiere_antes_matchea(last_user: str) -> bool:
    """¿El mensaje pide atenderse ANTES del plazo? (gate barato antes de la query)."""
    return bool(_QUIERE_ANTES_PAT.search(last_user or ""))


def iny_quiere_antes(os_name: str, delay_days: int, min_date: str) -> str | None:
    """El paciente con OS demorada insiste en atenderse antes → porqué real + salida
    particular, presentada como opción y SIN presionar. (El match del mensaje se
    valida antes con quiere_antes_matchea; acá solo se arma el texto.)"""
    if not os_name or int(delay_days or 0) <= 0:
        return None
    return (
        f"⏳ EL PACIENTE QUIERE ATENDERSE ANTES DEL PLAZO DE SU OBRA SOCIAL ({os_name} agenda "
        f"turnos por cobertura recién a partir del {min_date}, demora de {int(delay_days)} días): "
        "1) Explicale el PORQUÉ REAL con calidez: es el plazo que su obra social maneja para turnos "
        "por cobertura — ⛔ PROHIBIDO decir 'no tengo disponibilidad' (es falso: la agenda existe, "
        "el plazo es de la cobertura) y PROHIBIDO repetir el mismo bloqueo si ya se lo dijiste. "
        "2) Ofrecele la SALIDA con calidez, como AYUDA y no como venta: la vía particular tiene "
        "fechas más próximas porque no pasa por ese plazo. ⛔ PROHIBIDA la frase seca 'si preferís "
        "no esperar, podés atenderte de forma particular' (suena comercial y cae mal) — decilo como "
        "'si lo necesitás resolver antes, te busco fechas por la vía particular y elegís vos'. Si le "
        "interesa, buscá disponibilidad llamando check_availability con insurance_provider='particular' "
        "y pasale opciones concretas. "
        "3) Presentalo como OPCIÓN, sin presionar: si elige esperar por su cobertura, está perfecto — "
        "pasale opciones desde esa fecha y listo."
    )


_DIAS_SEMANA = r"(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?)"


def iny_restriccion_dias(last_user: str) -> str | None:
    """El paciente restringe o pregunta por DÍAS puntuales (caso Lucas manual
    2026-07-20: 'puedo los lunes o viernes únicamente' → el bot respondió la agenda
    DE MEMORIA infiriendo de las opciones ya ofrecidas, y mintió: el lunes 27 existía).
    La agenda por día la resuelve check_availability — incluido el respaldo con el
    otro profesional si el titular no atiende ese día."""
    t = (last_user or "").lower()
    if not re.search(
        rf"(?:puedo|me queda[n]?|me viene[n]?|prefiero|solo|[uú]nicamente) (?:los |el |ir )?.{{0,20}}{_DIAS_SEMANA}"
        rf"|{_DIAS_SEMANA}.{{0,25}}(?:[uú]nicamente|solo puedo|nada m[aá]s)"
        rf"|(?:ten[eé]s|hay|habr[aá]).{{0,18}}(?:para )?(?:el |los )?{_DIAS_SEMANA}",
        t,
    ):
        return None
    return (
        "📅 EL PACIENTE RESTRINGIÓ O PREGUNTÓ POR DÍAS PUNTUALES DE LA SEMANA: NO respondas la "
        "agenda de memoria ni infieras de las opciones que ya ofreciste (eso es INVENTAR agenda). "
        "Llamá check_availability DE NUEVO con esa preferencia (date_query con el día pedido, ej. "
        "'próximo lunes' o 'viernes'). La herramienta resuelve la agenda REAL de ese día — incluido "
        "el respaldo con OTRO profesional del equipo si el titular no atiende ese día y el "
        "tratamiento es compartido. ⛔ PROHIBIDO afirmar 'ese día no tengo / no me quedan / no "
        "atendemos' sin haber llamado la herramienta con ese día EN ESTE turno."
    )


def candado_dia_sin_consultar(response_text: str, tools_names: list[str] | None = None) -> str:
    """RED del caso Lucas: la respuesta AFIRMA que un día de la semana no tiene lugar
    pero check_availability NO se llamó en este turno → la afirmación es inventada.
    Se recorta y se ofrece revisar la agenda (el 'sí' del paciente dispara el
    aceptó-ofrecimiento → la herramienta de verdad)."""
    if not response_text:
        return response_text
    if "check_availability" in (tools_names or []):
        return response_text
    if re.search(r"(?i)\[[^\[\]]*silencio[^\[\]]*\]", response_text):
        return response_text
    pat = re.compile(
        rf"(?im)^.*{_DIAS_SEMANA}[^.\n]{{0,35}}no (?:me quedan|tengo|hay|atiende[n]?|atendemos)[^\n]*$\n?"
        rf"|^.*no (?:me quedan|tengo|hay)[^\n]{{0,35}}{_DIAS_SEMANA}[^\n]*$\n?"
    )
    if not pat.search(response_text):
        return response_text
    nuevo = pat.sub("", response_text).strip()
    nuevo = re.sub(r"\n{3,}", "\n\n", nuevo).strip()
    linea = "¿Querés que revise la agenda para esos días puntuales? Así te confirmo con lo que hay de verdad 😊"
    return (nuevo + "\n" + linea).strip() if nuevo else linea


def iny_gate_cobertura(minor_booking: bool, cov_conocida: bool) -> str | None:
    """Gate A1 de cobertura (texto único compartido prod/banco, extraído de
    buffer_task 2026-07-20 + línea multi-pregunta del caso edge-triple): con
    cobertura NO resuelta, primero se pregunta la cobertura y el VALOR no sale —
    pero las OTRAS preguntas del mensaje (horarios, dirección) se responden ya."""
    if not (minor_booking or not cov_conocida):
        return None
    return (
        "⛔ COBERTURA NO RESUELTA: no sabés si la persona que se atiende es particular o tiene "
        "obra social. ANTES QUE NADA: si el mensaje trae ADEMÁS otras preguntas (horarios de "
        "atención, dirección, si se puede agendar tal día), respondé ESAS directamente en esta "
        "misma respuesta — solo el PRECIO espera la cobertura; no dejes al paciente sin sus otras "
        "respuestas. EXCEPCIÓN ESTÉTICA: carillas, blanqueamiento y diseño de sonrisa son SIEMPRE "
        "particulares (ninguna obra social los cubre): para esos NO preguntes cobertura — aclaralo, "
        "informá el valor de la consulta de evaluación con su encuadre y coordiná el turno. "
        + (
            "⚠️ Estás agendando para un HIJO/A MENOR: la 'Obra Social registrada' del contexto es "
            "la del INTERLOCUTOR (quien escribe), NO la del menor — preguntá la cobertura DEL MENOR "
            "y NO le apliques a él el coseguro de la OS del interlocutor. "
            if minor_booking
            else ""
        )
        + "Si pide turno/precio y TODAVÍA no sabés su cobertura (ni 'particular' ni una OS nombrada "
        "en el chat), tu PRIMER movimiento es preguntar '¿Contás con alguna obra social o te "
        "atenderías de forma particular?'. ⛔ PROHIBIDO la plantilla 'la consulta sería de forma "
        "particular / te damos el comprobante para el reintegro' Y TAMBIÉN dar el VALOR/monto de "
        "la consulta (ni '$60.000' ni ningún número) hasta que (a) diga EXPLÍCITAMENTE "
        "que es particular, o (b) nombre una OS y la verifiques con check_insurance_coverage. "
        "Y NUNCA des el valor si el paciente NO lo preguntó — pidió un turno, no un precio."
    )


def aplicar_inyecciones(
    last_user: str,
    user_texts: list[str] | None = None,
    last_bot: str = "",
    coseguro_ya_explicado: int = 0,
    os_delayed: dict | None = None,
) -> str:
    """Concatena todas las inyecciones que disparen (para el banco / run.py).

    os_delayed: {"name", "delay_days", "min_date"} si la OS del caso tiene demora.
    coseguro_ya_explicado: cuántas veces el bot ya explicó el coseguro en el hilo.
    """
    _preg_monto = es_pregunta_monto_coseguro(last_user) or (
        int(coseguro_ya_explicado) >= 1 and es_insistencia_monto(last_user)
    )
    partes = [
        iny_derivacion_explicita(last_user),
        iny_pide_cancelar(user_texts or [last_user], last_bot),
        iny_multi_persona(last_user),
        iny_queja_precio(last_user),
        iny_os_en_mensaje(last_user),
        iny_restriccion_dias(last_user),
        iny_acepto_ofrecimiento(last_user, last_bot),
        iny_manejo_coseguro(
            _preg_monto,
            es_confusion_sena(last_user),
            coseguro_ya_explicado,
        ),
    ]
    if os_delayed and quiere_antes_matchea(last_user):
        partes.append(
            iny_quiere_antes(
                str(os_delayed.get("name", "")),
                int(os_delayed.get("delay_days", 0) or 0),
                str(os_delayed.get("min_date", "")),
            )
        )
    return "".join(f"\n{p}" for p in partes if p)


# ---------------------------------------------------------------------------
# Candados de SALIDA puros (post-LLM)
# ---------------------------------------------------------------------------

_PIDE_TURNO_PAT = re.compile(
    r"(?i)\b(turno|agendar|agendame|agendarme|cita)\b|quiero (?:ir|atenderme)|necesito (?:atenderme|que me atiendan|ver a la)"
)
_TRATAMIENTO_PAT = re.compile(
    r"(?i)implante|ortodoncia|limpieza|blanqueamiento|carilla|conducto|cirug|extracci|muela"
    r"|caries|control|checkup|revisi[oó]n|continuidad|urgencia|placa|pr[oó]tesis|corona"
    r"|tratamiento (?:en curso|a terminar)|a terminar|evaluaci[oó]n"
)
_PROMESA_HUMANO_PAT = re.compile(
    r"(?i)te paso con el equipo|lo paso con el equipo|pas[eé] tu caso|derivo tu|ya (?:lo )?deriv[eé]"
    r"|el equipo (?:lo revisa|te contacta|te va a contactar)"
)


def candado_avance(response_text: str, last_user: str, tools_names: list[str] | None = None) -> str:
    """GLOBITO MUERTO: el paciente pidió un turno y la respuesta no avanza (sin
    pregunta, sin opciones, sin link) → se agrega UNA pregunta de avance. Aditivo.

    Casos banco: terce-adulto-hermana ("con OSDE primero verifico y después te
    paso opciones" — punto muerto) y recurrente-continuidad-implante ("vamos a
    coordinar esa continuidad." — sin ofrecer nada concreto).
    """
    if not response_text or not last_user:
        return response_text
    if not _PIDE_TURNO_PAT.search(last_user):
        return response_text
    # La respuesta YA avanza: pregunta algo, ofrece opciones numeradas, manda un
    # link (anamnesis/pago), pide datos, o deriva a un humano.
    # v2 (caso 5 manual 2026-07-20): un pedido de datos en IMPERATIVO ("me falta tu
    # nombre y apellido, y tu DNI") avanza AUNQUE no tenga '?'. Agregar acá la
    # pregunta genérica ("¿para qué tipo de consulta sería?") era redundante y
    # mareaba: el tratamiento ya estaba elegido y el turno ya reservado.
    if re.search(
        r"(?i)(?:decime|pasame|p[aá]same|contame|indicame|ind[ií]came|me falta[n]?|necesito|falta[n]? tu)"
        r"[^\n]{0,80}(?:nombre|apellido|dni|datos)",
        response_text,
    ):
        return response_text
    if "?" in response_text or "¿" in response_text:
        return response_text
    if "1️⃣" in response_text or "http" in response_text.lower():
        return response_text
    if re.search(r"(?i)\[[^\[\]]*silencio[^\[\]]*\]", response_text):
        return response_text
    if _PROMESA_HUMANO_PAT.search(response_text):
        return response_text
    if "derivhumano" in (tools_names or []):
        return response_text
    if _TRATAMIENTO_PAT.search(last_user):
        pregunta = "¿Qué día y horario te quedan más cómodos? Así te busco opciones 😊"
    else:
        pregunta = "¿Para qué tipo de consulta sería y qué día te queda cómodo? Así te busco opciones 😊"
    return response_text.rstrip() + "\n" + pregunta


def candado_multi_turno(response_text: str, fechas_futuras: list[str] | None) -> str:
    """RADAR DEL OTRO TURNO (caso Matías): el paciente tiene 2+ turnos futuros y la
    respuesta confirma/queda con UNO solo sin mencionar el resto → se agrega la
    pregunta por el otro ('¿lo dejamos o lo cancelo?'). Aditivo, nunca recorta.

    fechas_futuras: fechas dd/mm de los turnos futuros del paciente (BD en prod,
    mock en el banco).
    """
    if not response_text or not fechas_futuras or len(fechas_futuras) < 2:
        return response_text
    if re.search(r"(?i)\[[^\[\]]*silencio[^\[\]]*\]", response_text):
        return response_text
    if re.search(r"(?i)cancel", response_text):
        return response_text  # ya está manejando el otro turno
    if not re.search(r"(?i)confirmad|queda(?:\b|n)|listo,? (?:tu|el) turno|✅", response_text):
        return response_text
    mencionadas = [f for f in fechas_futuras if f and f in response_text]
    if len(mencionadas) != 1:
        return response_text
    otras = [f for f in fechas_futuras if f not in mencionadas]
    if not otras:
        return response_text
    if len(otras) == 1:
        pregunta = f"Veo que también tenés un turno el {otras[0]} — ¿ese lo dejamos o lo cancelo? 😊"
    else:
        pregunta = (
            "Veo que también tenés turnos el "
            + " y el ".join(otras)
            + " — ¿esos los dejamos o cancelo alguno? 😊"
        )
    return response_text.rstrip() + "\n" + pregunta


# OS del PANEL REAL (sync 2026-07-20) que llevan coseguro — accepted + restricted
# (OSDE/Sancor restringidas TAMBIÉN tienen convenio con coseguro en lo cubierto).
# Las NO-panel (swiss/ioma/osdepym/omint/luis pasteur) NO van acá: su encuadre es
# particular + reintegro (candado reintegro); ISSN tampoco (bloque propio).
_OS_CON_COSEGURO_PAT = re.compile(
    r"(?i)\b(osde|galeno|sancor|sosunc|osseg|jer[aá]rquicos|medif[eé]|medicus"
    r"|apsot|mca|am[eé]rica|bancarios|siaco|credi.?gu[ií]a|federada|poder judicial)\b"
)


def candado_mencion_coseguro(response_text: str, last_user: str, patient_context: str = "") -> str:
    """MENCIÓN DEL COSEGURO (banco v3: os-osde-coseguro, post-confirmacion,
    os-pregunta-particular): con OS que lleva coseguro, la respuesta que ofrece
    turnos o da el valor particular — o que responde una pregunta directa de
    'algo adicional' — debe nombrar el coseguro (sin monto). Aditivo, 1 línea.
    A recurrentes NO se les agrega en la oferta (regla Myriam: el coseguro va en
    una línea recién al confirmar) — solo si lo PREGUNTAN."""
    if not response_text or re.search(r"(?i)coseguro", response_text):
        return response_text
    if re.search(r"(?i)\[[^\[\]]*silencio[^\[\]]*\]", response_text):
        return response_text
    _ctx = (patient_context or "").lower()
    pregunta_directa = es_pregunta_monto_coseguro(last_user or "")
    os_presente = bool(_OS_CON_COSEGURO_PAT.search(last_user or "")) or "obra social registrada" in _ctx
    if pregunta_directa and (os_presente or re.search(r"(?i)trabajamos con", response_text)):
        return (
            response_text.rstrip()
            + "\nSobre lo adicional: si tu plan tiene coseguro, te lo confirman en la clínica antes de atenderte — sin sorpresas 😊"
        )
    if os_presente and "paciente recurrente" not in _ctx:
        # v5: también dispara al hablar de cobertura restringida u ofrecer opciones/fechas
        # con la OS (os-osde-coseguro: 'cobertura restringida... ¿te paso opciones?' sin
        # nombrar el coseguro).
        oferta_o_valor = ("1️⃣" in response_text) or bool(
            re.search(
                r"(?i)tiene un valor|particular tiene|cobertura restringida|te paso opciones|primera fecha disponible",
                response_text,
            )
        )
        if oferta_o_valor:
            return (
                response_text.rstrip()
                + "\nCon tu obra social, si corresponde un coseguro, te lo confirman en la clínica 😊"
            )
    return response_text


def candado_compactar_cimo(response_text: str) -> str:
    """El bloque ISSN→CIMO salía en DOS globitos (el template trae doble salto y el
    sender parte por \\n\\n — caso real de pruebas 2026-07-20). Con CIMO en la
    respuesta, se compacta a UN globito. No toca nada más."""
    if not response_text or "CIMO" not in response_text:
        return response_text
    if "\n\n" not in response_text:
        return response_text
    return response_text.replace("\n\n", "\n")


def candado_encuadre_valor(response_text: str, last_user: str = "") -> str:
    """ENCUADRE DEL VALOR (banco v3: edge-enojado, os-pregunta-particular): cuando
    la respuesta da el valor de la consulta — o responde a una QUEJA de precio —
    sin explicar qué incluye, se agrega el encuadre (evaluación + diagnóstico +
    plan con presupuesto). Aditivo, 1 línea."""
    if not response_text:
        return response_text
    if re.search(r"(?i)eval[uú]a (?:tu|su) caso|qu[eé] incluye|incluye la|diagn[oó]stico|plan de tratamiento", response_text):
        return response_text
    if re.search(r"(?i)\[[^\[\]]*silencio[^\[\]]*\]", response_text):
        return response_text
    da_valor = bool(re.search(r"(?i)tiene un valor de \$", response_text))
    hay_queja = queja_precio_matchea(last_user)
    if not (da_valor or hay_queja):
        return response_text
    return (
        response_text.rstrip()
        + "\nEn esa consulta la doctora evalúa tu caso completo, te da el diagnóstico y te arma el plan de tratamiento con su presupuesto — es lo que evita gastos de más después."
    )


def candado_quiere_antes_salida(response_text: str) -> str:
    """SALIDA del quiere-antes (banco v4, os-osde-quiere-antes): el paciente con OS
    demorada pidió atenderse antes y la respuesta ofrece slots por cobertura SIN
    mencionar la vía particular → se agrega la opción en una línea, sin presionar.
    El CALLER decide la activación (la inyección quiere-antes disparó este turno).
    Aditivo, nunca recorta."""
    if not response_text:
        return response_text
    if re.search(r"(?i)particular", response_text):
        return response_text
    if re.search(r"(?i)\[[^\[\]]*silencio[^\[\]]*\]", response_text):
        return response_text
    if not ("1️⃣" in response_text or re.search(r"(?i)primera fecha|opciones dispon|a partir del", response_text)):
        return response_text
    # Texto v2 (caso 4 manual 2026-07-20: "si preferís no esperar... particular"
    # sonaba a venta seca): se presenta como ayuda, sin presión.
    return (
        response_text.rstrip()
        + "\nSi lo necesitás resolver antes, contame y te busco fechas más próximas por la vía particular — sin compromiso, elegís vos 😊"
    )


def candado_coseguro_frio(response_text: str) -> str:
    """CASO 7 manual (2026-07-20): 'no te paso un monto por acá' — seco, sin empatía
    (pedido Carlos: 'debemos explicarle'). La frase-bloqueo se reemplaza por el
    PORQUÉ cálido: depende del plan, se confirma en la clínica, sin sorpresas.
    Determinista: solo reemplaza esa frase, no toca el resto."""
    if not response_text:
        return response_text
    # v2 (verificación 2026-07-21): se QUITÓ 'número' de la alternancia — era ambiguo
    # ("no te doy un número de teléfono" se convertía en el mensaje de precio). Solo
    # monto/valor/cifra, que son inequívocamente monetarios.
    pat = re.compile(
        r"(?i)(?:no te (?:paso|doy|digo) (?:un |el |una )?(?:monto|valor|cifra)"
        r"|no (?:puedo|podemos) (?:pasarte|darte|decirte) (?:el |un |una )?(?:monto|valor|cifra))"
        r"[^.\n]*"
    )
    if not pat.search(response_text):
        return response_text
    calido = (
        "el monto exacto depende del plan que tengas — te lo confirman en la clínica "
        "antes de atenderte, así vas sin sorpresas 😊"
    )
    return pat.sub(calido, response_text)


def candado_particular_incoherente(response_text: str) -> str:
    """CASOS 1/8 manuales (2026-07-20): 'por cobertura a partir del 25/07' + opciones
    27/07 y 28/07 → las opciones YA cumplen el plazo de la obra social, y el 'si
    querés antes, podés de forma particular' SOBRA y confunde (parece que esas
    fechas fueran solo pagando). Si TODAS las opciones ofrecidas son >= la fecha
    del plazo, la venta de la vía particular se recorta. Si hay fechas antes del
    plazo (vía particular real), no toca nada."""
    if not response_text:
        return response_text
    if re.search(r"(?i)\[[^\[\]]*silencio[^\[\]]*\]", response_text):
        return response_text
    m = re.search(r"(?i)a partir del (\d{1,2})/(\d{1,2})", response_text)
    if not m:
        return response_text
    _min = (int(m.group(2)), int(m.group(1)))  # (mes, día) para comparar cronológico
    slots = re.findall(r"[1-3]️?⃣[^\n]*?(\d{1,2})/(\d{1,2})", response_text)
    if not slots:
        return response_text
    if not all((int(mm), int(dd)) >= _min for dd, mm in slots):
        return response_text  # hay opciones ANTES del plazo → la vía particular es real
    pat = re.compile(
        r"(?i)[^.\n]*(?:si (?:quer[eé]s|prefer[ií]s|lo )[^.\n]{0,45}antes[^.\n]{0,70}particular"
        r"|particular[^.\n]{0,70}antes)[^.\n]*[.!?]?\s*"
    )
    nuevo = pat.sub("", response_text)
    nuevo = re.sub(r"\n{3,}", "\n\n", nuevo).strip()
    nuevo = re.sub(r"[ \t]{2,}", " ", nuevo)
    return nuevo if nuevo else response_text


# Abreviaturas que NO cortan oración ("la Dra. Laura" no es fin de frase).
_ABREV_NO_CORTE = ("dra", "dr", "sra", "sr", "lic", "od", "esp", "prof", "av")


def candado_formato(response_text: str) -> str:
    """LEGIBILIDAD (pedido Carlos, casos 3/6 manuales 2026-07-20: 'está tan junto
    que no se entiende... agregar saltos de línea para diferenciar la info'): un
    párrafo-ladrillo (>240 chars sin ningún salto) se parte en UNA oración por
    línea, con saltos SIMPLES (mismo globito — no crea burbujas nuevas). No toca
    ofertas 1️⃣, URLs ni abreviaturas (Dra., Sr.). Determinista, corre al final."""
    if not response_text:
        return response_text
    if re.search(r"(?i)\[[^\[\]]*silencio[^\[\]]*\]", response_text):
        return response_text

    def _partir(linea: str) -> str:
        if len(linea) <= 240 or "1️⃣" in linea:
            return linea
        out, ini = [], 0
        for m in re.finditer(r"[.!?] +", linea):
            prev = linea[ini:m.start()]
            ult = re.search(r"([\wÁÉÍÓÚáéíóúñÑ]+)$", prev)
            if ult and ult.group(1).lower() in _ABREV_NO_CORTE:
                continue
            nxt = linea[m.end():m.end() + 1]
            if nxt and (nxt.isupper() or nxt in "¿¡"):
                out.append(linea[ini:m.start() + 1])
                ini = m.end()
        out.append(linea[ini:])
        partes = [p.strip() for p in out if p.strip()]
        return "\n".join(partes) if partes else linea

    paras = response_text.split("\n\n")
    nuevos = ["\n".join(_partir(l) for l in p.split("\n")) for p in paras]
    return "\n\n".join(nuevos)


def candado_issn_no_deriva(response_text: str, patient_context: str = "", last_user: str = "") -> str:
    """ISSN NO SE DERIVA — caso Griselda (prod 2026-07-21). El prompt YA ordena 4 veces
    'con ISSN no derivar, ofrecé turno particular con reintegro' (main.py 14056-14059,
    buffer_task 2494) pero el modelo igual derivó al equipo ('ya le pasé tu caso'). Este
    candado hace determinista lo que Carlos hizo a mano: con ISSN activo, si la respuesta
    promete DERIVAR al equipo SIN ofrecer el turno particular, y el paciente NO insiste en
    cobertura ni pidió la cirugía maxilofacial en la clínica → se recorta la derivación y se
    ofrece la consulta particular con reintegro. Conserva la info de CIMO (esa es correcta)."""
    if not response_text:
        return response_text
    if re.search(r"(?i)\[[^\[\]]*silencio[^\[\]]*\]", response_text):
        return response_text
    _ctx = (patient_context or "").lower()
    if not (re.search(r"\bissn\b", _ctx) or "instituto de seguridad" in _ctx):
        return response_text
    # ¿la respuesta deriva al equipo? (promesa-fantasma de handoff)
    if not re.search(
        r"(?i)(?:ya )?(?:le |te )?pas[eé] tu caso al equipo|elev[eé] tu caso"
        r"|el equipo[^.\n]{0,30}(?:lo revis|te contact|te va a contactar)"
        r"|para que (?:lo revisen|te contacten)",
        response_text,
    ):
        return response_text
    # Si YA ofrece el turno/consulta particular, no hace falta reconducir
    if re.search(
        r"(?i)consulta particular|evaluaci[oó]n particular|te paso turnos|te agendo"
        r"|¿te paso|turno[^.\n]{0,20}particular|te busco (?:un )?turno",
        response_text,
    ):
        return response_text
    # Excepción: pidió la cirugía maxilofacial EN LA CLÍNICA o insiste en cobertura → dejar derivar
    if re.search(
        r"(?i)maxilofacial|insist|me lo cubr|tiene que cubrir|s[ií] o s[ií] por (?:la )?obra|exijo|reclamo",
        last_user or "",
    ):
        return response_text
    # Reconducir: recortar SOLO la frase de derivación (conserva CIMO + 'el resto es particular')
    _nuevo = re.sub(
        r"(?i)[^.\n]*(?:ya )?(?:le |te )?pas[eé] tu caso al equipo[^.\n]*[.\n]?", "", response_text)
    _nuevo = re.sub(
        r"(?i)[^.\n]*el equipo[^.\n]{0,30}(?:lo revis|te contact|te va a contactar)[^.\n]*[.\n]?", "", _nuevo)
    _nuevo = re.sub(r"(?i)[^.\n]*para que (?:lo revisen|te contacten)[^.\n]*[.\n]?", "", _nuevo)
    _nuevo = re.sub(r"\n{3,}", "\n\n", _nuevo).strip()
    _oferta = (
        "Con ISSN, cualquier tratamiento en el consultorio es particular 😊 ¿Te agendo una "
        "consulta de evaluación? Después podés gestionar el reintegro con tu obra social."
    )
    return (_nuevo + "\n" + _oferta).strip() if _nuevo else _oferta


# Aclaración ÚNICA y correcta para ISSN (misma que el mensaje predeterminado de la OS).
_ISSN_ACLARA = (
    "Con ISSN, la cirugía maxilofacial se coordina con CIMO 😊 El resto de los tratamientos "
    "(consultas, coronas, limpieza, etc.) se atiende de forma PARTICULAR en el consultorio, y "
    "te damos el comprobante para que gestiones el reintegro con tu obra social."
)


def candado_issn_anti_ceder(response_text: str, patient_context: str = "", last_user: str = "") -> str:
    """ISSN ANTI-CEDER — casos prod 21/07 (4 chats). El paciente pregunta '¿lo cubre ISSN?'
    / '¿trabajan con ISSN?' y el bot AFIRMA/insinúa cobertura ('sí, trabajamos con ISSN',
    'la consulta se maneja según tu caso', 'se ve en la evaluación si corresponde') cuando la
    respuesta correcta es SIEMPRE: cirugía maxilofacial→CIMO, el resto PARTICULAR+reintegro.
    El prompt lo prohíbe (main.py 14058 'PROHIBIDO CEDER') pero el modelo cede → candado
    determinista: detecta el ceder y reemplaza por la aclaración clara, preservando la oferta
    de turnos si la había. NO toca si la respuesta ya aclara 'particular' sin afirmar cobertura."""
    if not response_text:
        return response_text
    if re.search(r"(?i)\[[^\[\]]*silencio[^\[\]]*\]", response_text):
        return response_text
    _ctx = (patient_context or "").lower()
    _lu = (last_user or "").lower()
    _issn = bool(re.search(r"\bissn\b", _ctx)) or "instituto de seguridad" in _ctx or bool(re.search(r"\bissn\b", _lu))
    if not _issn:
        return response_text
    # ¿la respuesta CEDE (afirma/insinúa cobertura ISSN o es evasiva sobre si cubre)?
    _cede = bool(re.search(
        r"(?i)trabajamos con issn"
        r"|con issn (?:la consulta|el tratamiento|eso)"
        r"|(?:la consulta|eso) se maneja seg[uú]n tu caso"
        r"|se maneja seg[uú]n tu caso"
        r"|(?:se (?:ve|define)|definici[oó]n)[^.\n]{0,30}(?:evaluaci|consulta)"
        r"|si corresponde cobertura o no"
        r"|no puedo confirmar\w*[^.\n]{0,45}sin (?:evaluar|ver)",
        response_text,
    ))
    # Afirmación seca "Sí..." a una pregunta directa de cobertura del paciente.
    # (flag reutilizado en la escotilla de abajo: si ABRE con "Sí" a "¿me cubre?", ni siquiera
    #  aclarar "particular" después alcanza — el "Sí" inicial ya engaña.)
    _abre_si = bool(re.match(r"(?i)\s*s[íi]\b", response_text)) and bool(re.search(
        r"(?i)(?:lo|la|me) cubre|trabaj\w* con issn|cobertura|cubiert[oa]|coseguro", _lu
    ))
    if not _cede and _abre_si:
        _cede = True
    if not _cede:
        return response_text
    # ¿ya está la aclaración correcta (dice 'particular') y NO afirma cobertura falsa? → dejar.
    # OJO (caso 1 prod 22/07): NO tomar este escape si la respuesta ABRE con "Sí" pelado a una
    # pregunta de cobertura ("Sí, ... de forma particular") — el "Sí" inicial engaña igual.
    if re.search(r"(?i)particular", response_text) and not _abre_si and not re.search(
        r"(?i)trabajamos con issn|se maneja seg[uú]n tu caso|corresponde cobertura o no", response_text
    ):
        return response_text
    # Preservar la oferta de turnos si la había; reemplazar la parte que cede por la aclaración.
    _oferta_lineas = [
        l for l in response_text.split("\n")
        if re.search(r"[1-3]️⃣|🗓️|ℹ️|opciones disponibles|¿cu[aá]l te|te queda mejor|te viene mejor", l, re.I)
    ]
    if _oferta_lineas:
        return _ISSN_ACLARA + "\n\n" + "\n".join(_oferta_lineas).strip()
    return _ISSN_ACLARA


# Temas clínicos que requieren evaluación HUMANA — no un turno estándar del bot. Son
# CATEGORÍAS (no casos puntuales): pediátrico complejo, malformaciones, condiciones
# especiales, enfermedad sistémica grave. Pedido Carlos 21/07 (caso bebé con malformación
# de paladar): "no podemos cubrir todas las boludeces que manda la gente — derivemos".
_CLINICO_ESPECIAL_PAT = re.compile(
    r"(?i)\b(beb[eé]s?|lactantes?|reci[eé]n nacid\w*|prematur\w*|neonat\w*|"
    r"malformaci[oó]n\w*|paladar (?:hendido|fisurado|leporino)|labio leporino|fisura palatina|"
    r"s[ií]ndrome de |condici[oó]n gen[eé]tica|"
    r"(?:enfermedad|patolog[ií]a|tratamiento) (?:oncol[oó]g\w*|autoinmune)|"
    r"quimioterapia|radioterapia|inmunodeprimid\w*|trasplant\w*)\b"
)


def candado_derivar_clinico_especial(response_text: str, last_user: str = "", tools_names=None) -> str:
    """DERIVÁ ANTE LO CLÍNICO ESPECIAL (caso bebé prod 21/07; pedido Carlos: 'no podemos
    cubrir todas las boludeces, derivemos'). Si el paciente introduce un tema que requiere
    evaluación HUMANA — bebés/prematuros, malformaciones, síndromes, enfermedad sistémica
    grave — y el bot NO está derivando (ni afirma capacidad ni agenda), se reemplaza la
    respuesta por una derivación al equipo. El texto dice 'ya lo derivé', así que el guard
    promesa-fantasma (posterior en la cadena) EJECUTA la derivación real (email + pendiente).
    NO toca lo estándar (limpieza, extracción común, cobertura): solo las categorías del patrón."""
    if not response_text:
        return response_text
    if re.search(r"(?i)\[[^\[\]]*silencio[^\[\]]*\]", response_text):
        return response_text
    if not _CLINICO_ESPECIAL_PAT.search(last_user or ""):
        return response_text
    # ¿el bot YA está derivando? no tocar (la derivación ya está en curso).
    if "derivhumano" in (tools_names or []):
        return response_text
    if re.search(
        r"(?i)(?:ya )?(?:lo )?deriv[eé]|el equipo (?:te contacta|lo revisa|te va a contactar)|pas[eé] tu caso",
        response_text,
    ):
        return response_text
    return (
        "Este tipo de caso lo ve directamente el equipo para poder orientarte bien 😊\n"
        "Ya lo derivé y te van a contactar a la brevedad."
    )


def candado_saludo_pregunta(response_text: str) -> str:
    """CONSOLIDAR GLOBITOS (pedido Carlos 21/07 — Meta cobra por mensaje desde octubre):
    el saludo de apertura de Paula ('Soy Paula, del equipo…') + la pregunta de avance
    (obra social / tipo de consulta) salían en 2 globitos por el doble salto. Los junta
    en 1 (colapsa \\n\\n → \\n = mismo globito). Solo actúa si es un saludo de apertura y
    hay una pregunta; NO toca ofertas de turnos (1️⃣) ni cierres (seña/anamnesis).
    Determinista, defensivo: ante cualquier duda deja el texto como estaba."""
    if not response_text or "\n\n" not in response_text:
        return response_text
    rt = response_text
    if not re.search(r"(?i)soy paula|del equipo de", rt):
        return response_text
    if "?" not in rt and "¿" not in rt:
        return response_text
    # No tocar ofertas de turnos ni cierres (tienen su propio candado)
    if re.search(r"(?i)1️⃣|alias|cbu|anamnesis|ficha m[eé]dica", rt):
        return response_text
    return re.sub(r"\n\s*\n", "\n", rt).strip()


def candado_confirmacion_datos(response_text: str) -> str:
    """CONSOLIDAR GLOBITOS (pedido Carlos 21/07): la confirmación de la reserva del
    horario + el pedido de datos (nombre/apellido/DNI) salían en 2 globitos. Los junta
    en 1 (colapsa \\n\\n → \\n). Solo actúa cuando están AMBAS partes; NO toca cierres con
    seña/anamnesis (esos tienen su propio candado de 2 globitos). Determinista, defensivo."""
    if not response_text or "\n\n" not in response_text:
        return response_text
    rt = response_text
    _reserva = re.search(
        r"(?i)qued[óo] reservad|reserv[ée] (?:el|tu) (?:horario|turno)|te reserv[ée]|ya (?:te )?reserv",
        rt,
    )
    _pide_datos = re.search(
        r"(?i)(?:necesito|dejame|pas[aá]me|decime)[^.\n]{0,30}(?:nombre|apellido|dni|documento)"
        r"|nombre[^.\n]{0,20}(?:apellido|dni|documento)",
        rt,
    )
    if not (_reserva and _pide_datos):
        return response_text
    if re.search(r"(?i)alias|cbu|anamnesis", rt):
        return response_text
    return re.sub(r"\n\s*\n", "\n", rt).strip()
