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
    r"|jer[aá]rquicos|medif[eé]|omint|luis pasteur|prevenci[oó]n)\b"
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


def iny_os_en_mensaje(last_user: str) -> str | None:
    """OS nombrada en el mensaje → reconocerla, verificar antes de afirmar, sin precio particular."""
    t = (last_user or "").lower()
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
    al equipo, ¿te sirve?') y el paciente respondió una afirmación corta → EJECUTAR ya
    (caso Luis, prod 2026-07-20; extendido al equipo por el coseguro nivel 2)."""
    t = (last_user or "").lower().strip()
    if not re.fullmatch(
        r"(bueno|dale|s[ií]|ok(a|ey)?|listo|de una|obvio|perfecto|genial|joya|buen[íi]simo"
        r"|s[ií] dale|dale s[ií]|bueno dale|dale bueno|me parece( bien)?|est[aá] bien|me sirve"
        r"|s[ií],? dale,?( me sirve)?|s[ií],? me sirve|dale,? me sirve)[.!,\s😊👍🙏]*",
        t,
    ):
        return None
    b = (last_bot or "").lower()
    if not re.search(
        r"decime y te busco|te busco opciones|te paso (?:turnos|opciones|las opciones)"
        r"|quer[eé]s que (?:te )?(?:busque|pase|coordine)|decime para qu[eé] d[íi]a"
        r"|si quer[eé]s.{0,40}(?:busco|paso|coordino)"
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
        "2) Ofrecele la SALIDA: si prefiere no esperar, puede atenderse de forma PARTICULAR mucho "
        "antes (la atención particular no pasa por ese plazo) — si le interesa, buscá disponibilidad "
        "llamando check_availability con insurance_provider='particular' y pasale opciones concretas. "
        "3) Presentalo como OPCIÓN, sin presionar: si elige esperar por su cobertura, está perfecto — "
        "pasale opciones desde esa fecha y listo."
    )


def iny_gate_cobertura(minor_booking: bool, cov_conocida: bool) -> str | None:
    """Gate A1 de cobertura (texto único compartido prod/banco, extraído de
    buffer_task 2026-07-20 + línea multi-pregunta del caso edge-triple): con
    cobertura NO resuelta, primero se pregunta la cobertura y el VALOR no sale —
    pero las OTRAS preguntas del mensaje (horarios, dirección) se responden ya."""
    if not (minor_booking or not cov_conocida):
        return None
    return (
        "⛔ COBERTURA NO RESUELTA: no sabés si la persona que se atiende es particular o tiene "
        "obra social. "
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
        "Y NUNCA des el valor si el paciente NO lo preguntó — pidió un turno, no un precio. "
        "OJO: si el mensaje trae ADEMÁS otras preguntas (horarios de atención, dirección, si se "
        "puede agendar), respondé ESAS directamente en la MISMA respuesta — solo el PRECIO espera "
        "la respuesta de cobertura; no dejes al paciente sin sus otras respuestas."
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


# OS aceptadas CON coseguro del tenant 1 (nacido del banco, mismo precedente que
# el set de rechazadas del candado reintegro). Swiss/Sancor/Prevención NO van acá
# (rechazadas → candado reintegro); ISSN tampoco (bloque propio).
_OS_CON_COSEGURO_PAT = re.compile(
    r"(?i)\b(osde|galeno|ioma|osdepym|sosunc|osseg|jer[aá]rquicos|medif[eé]|omint|luis pasteur)\b"
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
        oferta_o_valor = ("1️⃣" in response_text) or bool(
            re.search(r"(?i)tiene un valor|particular tiene", response_text)
        )
        if oferta_o_valor:
            return (
                response_text.rstrip()
                + "\nCon tu obra social, si corresponde un coseguro, te lo confirman en la clínica 😊"
            )
    return response_text


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
