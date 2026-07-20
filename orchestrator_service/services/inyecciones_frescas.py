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


def iny_queja_precio(last_user: str) -> str | None:
    """Queja del precio → defender el VALOR con calidez, sin disculpas ni descuentos."""
    t = (last_user or "").lower()
    if not re.search(
        r"es (?:un|una) (?:robo|locura|estafa|barbaridad)"
        r"|(?:es|me parece|qu[eé]|re|muy|super|tan) car[oa]\b|car[íi]sim[oa]"
        r"|no puede (?:ser|salir) (?:tan caro|eso)|es mucho para una consulta"
        r"|no pienso pagar eso|una fortuna",
        t,
    ):
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


def aplicar_inyecciones(
    last_user: str,
    user_texts: list[str] | None = None,
    last_bot: str = "",
) -> str:
    """Concatena todas las inyecciones que disparen (para el banco / run.py)."""
    partes = [
        iny_derivacion_explicita(last_user),
        iny_pide_cancelar(user_texts or [last_user], last_bot),
        iny_multi_persona(last_user),
        iny_queja_precio(last_user),
        iny_os_en_mensaje(last_user),
    ]
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
