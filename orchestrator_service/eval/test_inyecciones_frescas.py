# -*- coding: utf-8 -*-
"""Test LOCAL y GRATIS del módulo compartido services/inyecciones_frescas.py
(banco v2 2026-07-20 — 17 fallos: derivación explícita, pide-cancelar, dos
personas, queja de precio, OS nombrada, coseguro 'algo adicional', globito
muerto y multi-turno).

A diferencia de las otras suites, acá NO hay espejo: se importa la MISMA
función que usan buffer_task.py (prod) y eval/run.py (banco).

Uso:  python -m eval.test_inyecciones_frescas   (desde orchestrator_service/)
"""
import sys

from services.inyecciones_frescas import (
    aplicar_inyecciones,
    candado_avance,
    candado_encuadre_valor,
    candado_mencion_coseguro,
    candado_multi_turno,
    es_insistencia_monto,
    es_pregunta_monto_coseguro,
    iny_acepto_ofrecimiento,
    iny_derivacion_explicita,
    iny_gate_cobertura,
    iny_manejo_coseguro,
    iny_multi_persona,
    iny_os_en_mensaje,
    iny_pide_cancelar,
    iny_queja_precio,
    iny_quiere_antes,
    quiere_antes_matchea,
)

CASOS = [
    # ------------------- derivación explícita -------------------
    (
        "derivación: 'hablar con una persona del equipo' (fallo real del banco) → dispara",
        lambda: iny_derivacion_explicita("queria hablar directamente con una persona del equipo por favor"),
        lambda out: out is not None and "derivhumano" in out,
    ),
    (
        "derivación: 'no quiero hablar con un bot' → dispara",
        lambda: iny_derivacion_explicita("no quiero hablar con un bot, pasame con alguien"),
        lambda out: out is not None,
    ),
    (
        "derivación: pedir un turno común NO dispara",
        lambda: iny_derivacion_explicita("hola quiero un turno para limpieza"),
        lambda out: out is None,
    ),
    # ------------------- pide cancelar -------------------
    (
        "cancelar: pedido en el historial ('quiero cancelar mi turno' → luego 'María') → dispara",
        lambda: iny_pide_cancelar(
            ["Hola, quiero cancelar mi turno, no voy a poder ir", "María"], "¿Me decís tu nombre?"
        ),
        lambda out: out is not None and "cancel_appointment" in out,
    ),
    (
        "cancelar: si menciona reprogramar/cambiar NO dispara (es reprogramación)",
        lambda: iny_pide_cancelar(["quiero cambiar mi turno para otro día"], ""),
        lambda out: out is None,
    ),
    (
        "cancelar: si el bot YA confirmó la cancelación NO re-dispara",
        lambda: iny_pide_cancelar(
            ["quiero cancelar mi turno", "gracias"], "Listo, tu turno quedó cancelado ✅"
        ),
        lambda out: out is None,
    ),
    # ------------------- multi-persona -------------------
    (
        "dos personas: 'para mi esposo y para mí también' (fallo del banco) → dispara",
        lambda: iny_multi_persona("¡Hola Paula! Necesito sacar un turno para mi esposo y para mí también."),
        lambda out: out is not None and "CADA UNO" in out,
    ),
    (
        "dos personas: 'para mi mamá Susana y para mí también' (fallo del banco) → dispara",
        lambda: iny_multi_persona("Quiero agendar para mi mamá Susana y para mí también, los dos necesitamos limpieza"),
        lambda out: out is not None,
    ),
    (
        "dos personas: turno para UNO solo NO dispara",
        lambda: iny_multi_persona("quiero un turno para mí para el jueves"),
        lambda out: out is None,
    ),
    (
        "dos personas: tercero SIN el interlocutor ('para mi hermana') NO dispara (flujo tercero normal)",
        lambda: iny_multi_persona("quiero sacar un turno para mi hermana Laura, ella tiene OSDE"),
        lambda out: out is None,
    ),
    # ------------------- queja de precio -------------------
    (
        "queja: 'eso es un robo, es muy caro' (fallo del banco) → dispara con defensa del valor",
        lambda: iny_queja_precio("¿60 mil la consulta? Eso es un robo, es muy caro para una consulta."),
        lambda out: out is not None and "QUÉ INCLUYE" in out,
    ),
    (
        "queja: pregunta de precio normal NO dispara",
        lambda: iny_queja_precio("hola, ¿cuánto sale la consulta?"),
        lambda out: out is None,
    ),
    # ------------------- OS en el mensaje -------------------
    (
        "OS: 'Yo tengo IOMA' (fallo del banco) → dispara con verificar + sin precio particular",
        lambda: iny_os_en_mensaje("Bueno, quiero un turno. ¿Trabajan con alguna obra social? Yo tengo IOMA."),
        lambda out: out is not None and "IOMA" in out and "check_insurance_coverage" in out,
    ),
    (
        "OS: 'Tengo Galeno' con dolor (fallo del banco) → dispara (reconocerla aunque haya urgencia)",
        lambda: iny_os_en_mensaje("Hola, me duele una muela. Quiero venir mañana. Tengo Galeno."),
        lambda out: out is not None and "GALENO" in out,
    ),
    (
        "OS: ISSN NO dispara acá (tiene su bloque específico)",
        lambda: iny_os_en_mensaje("tengo issn, ¿atienden?"),
        lambda out: out is None,
    ),
    (
        "OS: mensaje sin OS NO dispara",
        lambda: iny_os_en_mensaje("hola, quiero un turno para limpieza"),
        lambda out: out is None,
    ),
    # ------------------- coseguro ampliado -------------------
    (
        "coseguro: '¿No debo abonar algo adicional?' (fallo post-confirmacion del banco) → es pregunta de coseguro",
        lambda: es_pregunta_monto_coseguro("Consulta, cubre osde cierto? No debo abonar algo adicional"),
        lambda out: out is True,
    ),
    (
        "coseguro: 'de cuánto es el coseguro' sigue disparando (regresión)",
        lambda: es_pregunta_monto_coseguro("De cuanto es el coseguro?"),
        lambda out: out is True,
    ),
    (
        "coseguro: pedido de turno normal NO dispara",
        lambda: es_pregunta_monto_coseguro("quiero un turno para el martes"),
        lambda out: out is False,
    ),
    # ------------------- candado AVANCE (globito muerto) -------------------
    (
        "avance: declaración sin pregunta ante pedido de turno (fallo terce-hermana) → agrega pregunta",
        lambda: candado_avance(
            "Perfecto, para tu hermana Laura 😊\nCon OSDE primero tengo que verificar la cobertura y después te paso las opciones de turno.",
            "Buen día, quiero sacar un turno para mi hermana Laura, ella tiene OSDE",
        ),
        lambda out: "?" in out and "tipo de consulta" in out.lower(),
    ),
    (
        "avance: continuidad de implante sin oferta (fallo Myriam) → agrega pregunta de día (no re-pregunta tratamiento)",
        lambda: candado_avance(
            "¡Hola Myriam! 😊 Como ya te atiende la Dra. Laura Delgado, vamos a coordinar esa continuidad de implante.",
            "Hola, tengo un implante con la dra a terminar, necesito turno",
        ),
        lambda out: "?" in out and "día y horario" in out.lower() and "tipo de consulta" not in out.lower(),
    ),
    (
        "avance: respuesta que YA pregunta algo NO se toca",
        lambda: candado_avance(
            "¡Hola! ¿Contás con alguna obra social o te atenderías de forma particular?",
            "hola quiero un turno",
        ),
        lambda out: out.count("?") == 1,
    ),
    (
        "avance: oferta con opciones 1️⃣ NO se toca",
        lambda: candado_avance(
            "Tengo estas opciones:\n1️⃣ Martes 10:00 hs\n2️⃣ Miércoles 11:15 hs",
            "quiero un turno",
        ),
        lambda out: "tipo de consulta" not in out.lower() and "día y horario te quedan" not in out.lower(),
    ),
    (
        "avance: derivación a humano NO se toca (el flujo termina ahí)",
        lambda: candado_avance(
            "Ya te paso con el equipo para que te ayuden con eso.",
            "necesito un turno especial",
            ["derivhumano"],
        ),
        lambda out: "?" not in out,
    ),
    (
        "avance: mensaje que NO pide turno NO se toca",
        lambda: candado_avance("Gracias por avisar.", "les mando el comprobante más tarde"),
        lambda out: out == "Gracias por avisar.",
    ),
    # ------------------- candado MULTI-TURNO -------------------
    (
        "multi-turno: confirma el jueves con otro turno el viernes (caso Matías) → pregunta por el otro",
        lambda: candado_multi_turno(
            "Perfecto, Matías! Queda confirmado tu turno del jueves 23/07 a las 10:00 hs para Checkup 😊",
            ["23/07", "24/07"],
        ),
        lambda out: "24/07" in out and "cancelo" in out.lower(),
    ),
    (
        "multi-turno: la respuesta ya maneja la cancelación del otro → NO duplica",
        lambda: candado_multi_turno(
            "Queda confirmado el jueves 23/07. ¿El del viernes 24/07 lo cancelo?",
            ["23/07", "24/07"],
        ),
        lambda out: out.count("24/07") == 1,
    ),
    (
        "multi-turno: con UN solo turno futuro NO hace nada",
        lambda: candado_multi_turno(
            "Queda confirmado tu turno del jueves 23/07 a las 10:00 hs 😊",
            ["23/07"],
        ),
        lambda out: "cancelo" not in out.lower(),
    ),
    (
        "multi-turno: respuesta que NO confirma nada NO se toca",
        lambda: candado_multi_turno(
            "Contame qué necesitás y te ayudo 😊",
            ["23/07", "24/07"],
        ),
        lambda out: "24/07" not in out,
    ),
    # ------------------- aplicar_inyecciones (integración run.py) -------------------
    (
        "integración: mensaje con OS + queja junta las dos inyecciones",
        lambda: aplicar_inyecciones("tengo OSDE y me parece carísimo lo que cobran"),
        lambda out: "OSDE" in out and "QUÉ INCLUYE" in out,
    ),
    (
        "integración: mensaje neutro no inyecta nada",
        lambda: aplicar_inyecciones("hola, buen día"),
        lambda out: out == "",
    ),
    # ------------------- quiere-antes (semáforo OS) -------------------
    (
        "quiere-antes: '¿¿30 días?? no puedo esperar tanto... ¿no tenés nada antes?' → matchea",
        lambda: quiere_antes_matchea("¿¿30 días?? Uf, no puedo esperar tanto... ¿no tenés nada antes?"),
        lambda out: out is True,
    ),
    (
        "quiere-antes: pedido de turno normal NO matchea",
        lambda: quiere_antes_matchea("hola, quiero un turno para la semana que viene"),
        lambda out: out is False,
    ),
    (
        "quiere-antes: la inyección explica el porqué real + salida particular + sin presionar",
        lambda: iny_quiere_antes("OSDE", 30, "19/08"),
        lambda out: out is not None
        and "OSDE" in out
        and "19/08" in out
        and "PARTICULAR" in out
        and "no tengo disponibilidad" in out.lower()
        and "sin presionar" in out.lower(),
    ),
    (
        "quiere-antes: sin demora (delay 0) NO inyecta",
        lambda: iny_quiere_antes("IOMA", 0, "21/07"),
        lambda out: out is None,
    ),
    (
        "quiere-antes integración: os_delayed + mensaje que insiste → la inyección entra",
        lambda: aplicar_inyecciones(
            "uf no puedo esperar tanto, ¿nada antes?",
            os_delayed={"name": "OSDE", "delay_days": 30, "min_date": "19/08"},
        ),
        lambda out: "PLAZO DE SU OBRA SOCIAL" in out,
    ),
    # ------------------- manejo del coseguro (texto compartido) -------------------
    (
        "coseguro nivel 1: primera pregunta → porqué cálido, sin cifras",
        lambda: iny_manejo_coseguro(True, False, 0),
        lambda out: out is not None and "PORQUÉ" in out and "Nunca una cifra" in out,
    ),
    (
        "coseguro nivel 2: ya explicado 2 veces → salida concreta con el equipo (derivhumano)",
        lambda: iny_manejo_coseguro(True, False, 2),
        lambda out: out is not None and "SALIDA CONCRETA" in out and "derivhumano" in out,
    ),
    (
        "coseguro confusión seña: aclara directo que la seña no es el precio",
        lambda: iny_manejo_coseguro(False, True, 0),
        lambda out: out is not None and "SEÑA" in out,
    ),
    (
        "coseguro insistencia sin la palabra ('10, 20, 50 lucas? cuánta plata llevo') → detectada",
        lambda: es_insistencia_monto("dale pero decime aunque sea un aproximado, 10, 20, 50 lucas? es para saber cuanta plata llevar"),
        lambda out: out is True,
    ),
    (
        "coseguro insistencia integración: hilo abierto (ya_explicado=2) + insistencia → nivel 2 entra",
        lambda: aplicar_inyecciones(
            "dale pero decime aunque sea un aproximado, es para saber cuanta plata llevar",
            coseguro_ya_explicado=2,
        ),
        lambda out: "SALIDA CONCRETA" in out,
    ),
    (
        "coseguro insistencia SIN hilo abierto (ya_explicado=0) → NO inyecta (podría ser otra cosa)",
        lambda: aplicar_inyecciones("decime un aproximado de lo que sale mas o menos"),
        lambda out: "COSEGURO" not in out,
    ),
    # ------------------- aceptó-ofrecimiento (compartido, con rama equipo) -------------------
    (
        "aceptó-ofrecimiento: 'Bueno' tras 'decime y te busco opciones' → ejecutar (caso Luis)",
        lambda: iny_acepto_ofrecimiento("Bueno", "Decime y te busco opciones para la semana que viene 😊"),
        lambda out: out is not None and "check_availability" in out,
    ),
    (
        "aceptó-ofrecimiento equipo: 'si dale, me sirve' tras 'le paso tu consulta al equipo ¿te sirve?' → derivhumano",
        lambda: iny_acepto_ofrecimiento(
            "si dale, me sirve 🙏",
            "si querés, le paso tu consulta al equipo y te confirman el valor de TU plan antes del turno, ¿te sirve?",
        ),
        lambda out: out is not None and "derivhumano" in out and "EQUIPO" in out,
    ),
    (
        "aceptó-ofrecimiento: mensaje largo con contenido NO dispara (no es afirmación corta)",
        lambda: iny_acepto_ofrecimiento(
            "dale pero antes decime cuánto sale la consulta porque no estoy seguro",
            "Decime y te busco opciones 😊",
        ),
        lambda out: out is None,
    ),
    (
        "aceptó-ofrecimiento: 'dale' sin oferta previa del bot NO dispara",
        lambda: iny_acepto_ofrecimiento("dale", "Tu turno quedó confirmado para el jueves 😊"),
        lambda out: out is None,
    ),
    (
        "aceptó-ofrecimiento INFO (caso Braian): 'Dale' tras 'te confirmo qué te conviene traer' → rama info",
        lambda: iny_acepto_ofrecimiento(
            "Dale", "Si querés, también te confirmo qué te conviene traer para la consulta de hoy."
        ),
        lambda out: out is not None and "INFORMACIÓN" in out and "INVENTAR" in out,
    ),
    (
        "aceptó-ofrecimiento INFO: 'dale, decime qué llevo' (aceptación con re-pedido corto) → dispara",
        lambda: iny_acepto_ofrecimiento(
            "dale, decime qué llevo", "Si querés, también te confirmo qué te conviene traer para la consulta de hoy."
        ),
        lambda out: out is not None and "INFORMACIÓN" in out,
    ),
    (
        "aceptó-ofrecimiento: 'sí pero cuánto sale?' NO es aceptación (pregunta otra cosa)",
        lambda: iny_acepto_ofrecimiento(
            "sí pero cuánto sale?", "Si querés, también te confirmo qué te conviene traer."
        ),
        lambda out: out is None,
    ),
    # ------------------- candado MENCIÓN COSEGURO -------------------
    (
        "mención-coseguro: pregunta '¿debo abonar algo adicional?' respondida seca → completa (fallo v3 post-confirmacion)",
        lambda: candado_mencion_coseguro(
            "Sí, trabajamos con OSDE 😊",
            "Consulta, cubre osde cierto? No debo abonar algo adicional",
            "PRÓXIMO TURNO: jueves 23/07 10:00",
        ),
        lambda out: "coseguro" in out.lower() and "clínica" in out.lower(),
    ),
    (
        "mención-coseguro: oferta de slots a OSDE sin nombrar el coseguro → agrega la línea (fallo v3 os-osde-coseguro)",
        lambda: candado_mencion_coseguro(
            "Con OSDE, te paso las opciones:\n1️⃣ Miércoles 19/08 — 10:00 hs\n2️⃣ Jueves 20/08 — 11:15 hs\nCuál te queda mejor?",
            "Hola, soy Paula. Necesito un turno de limpieza. Tengo OSDE.",
            "Lead nuevo.",
        ),
        lambda out: "coseguro" in out.lower(),
    ),
    (
        "mención-coseguro: valor particular pedido con OSDE → agrega la comparación (fallo v3 os-pregunta-particular)",
        lambda: candado_mencion_coseguro(
            "Sí, con OSDE te lo confirmo: la consulta particular tiene un valor de $60.000.",
            "tengo OSDE pero decime cuánto es particular",
            "",
        ),
        lambda out: "coseguro" in out.lower(),
    ),
    (
        "mención-coseguro: recurrente que recibe oferta NO se toca (regla Myriam: coseguro recién al confirmar)",
        lambda: candado_mencion_coseguro(
            "1️⃣ Martes 10:00 hs\n2️⃣ Miércoles 11:15 hs",
            "quiero un turno",
            "HISTORIAL: Paciente recurrente. Obra Social registrada: OSDE.",
        ),
        lambda out: "coseguro" not in out.lower(),
    ),
    (
        "mención-coseguro: ya nombra el coseguro → NO duplica",
        lambda: candado_mencion_coseguro(
            "Con OSDE hay un coseguro que te confirman en la clínica 😊\n1️⃣ Martes 10:00 hs",
            "tengo OSDE, quiero turno",
            "",
        ),
        lambda out: out.lower().count("coseguro") == 1,
    ),
    (
        "mención-coseguro: paciente sin OS nombrada NO se toca",
        lambda: candado_mencion_coseguro(
            "1️⃣ Martes 10:00 hs\n2️⃣ Miércoles 11:15 hs",
            "quiero un turno para limpieza",
            "Lead nuevo.",
        ),
        lambda out: "coseguro" not in out.lower(),
    ),
    # ------------------- candado ENCUADRE VALOR -------------------
    (
        "encuadre-valor: da el valor sin explicar qué incluye → agrega el encuadre (fallo v3 os-pregunta-particular)",
        lambda: candado_encuadre_valor(
            "Sí, con OSDE te lo confirmo: la consulta particular tiene un valor de $60.000.\nSi querés, te paso opciones 😊",
            "tengo OSDE pero decime cuánto es particular",
        ),
        lambda out: "evalúa tu caso" in out.lower() or "diagnóstico" in out.lower(),
    ),
    (
        "encuadre-valor: queja de precio sin defensa del contenido → agrega el encuadre (fallo v3 edge-enojado)",
        lambda: candado_encuadre_valor(
            "Entiendo que te parezca una inversión importante.\nSi querés, te ayudo a coordinar un turno de evaluación.",
            "¿60 mil la consulta? Eso es un robo, es muy caro para una consulta.",
        ),
        lambda out: "diagnóstico" in out.lower(),
    ),
    (
        "encuadre-valor: la plantilla completa ('evalúa tu caso') NO se toca",
        lambda: candado_encuadre_valor(
            "La consulta de evaluación tiene un valor de $60.000. Ahí la doctora evalúa tu caso y te orienta.",
            "cuánto sale?",
        ),
        lambda out: "diagnóstico" not in out.lower(),
    ),
    (
        "encuadre-valor: respuesta sin valor ni queja NO se toca",
        lambda: candado_encuadre_valor("¿Contás con alguna obra social o te atenderías de forma particular?", "quiero un turno"),
        lambda out: "diagnóstico" not in out.lower(),
    ),
    # ------------------- gate A1 compartido -------------------
    (
        "gate-A1: cobertura no resuelta → gate completo con la línea multi-pregunta (fallo v3 edge-triple)",
        lambda: iny_gate_cobertura(False, False),
        lambda out: out is not None and "COBERTURA NO RESUELTA" in out and "otras preguntas" in out.lower(),
    ),
    (
        "gate-A1: cobertura conocida y sin menor → NO inyecta",
        lambda: iny_gate_cobertura(False, True),
        lambda out: out is None,
    ),
    (
        "gate-A1: menor con cobertura del interlocutor conocida → inyecta igual (la del MENOR no se sabe)",
        lambda: iny_gate_cobertura(True, True),
        lambda out: out is not None and "HIJO/A MENOR" in out,
    ),
]


def main() -> int:
    fallas = 0
    for nombre, fn, check in CASOS:
        out = fn()
        try:
            ok = check(out)
        except Exception:
            ok = False
        print(f"{'✅ PASA ' if ok else '❌ FALLA'} — {nombre}")
        if not ok:
            fallas += 1
            print(f"     salida: {out!r}")
    print()
    if fallas:
        print(f"RESULTADO: {fallas}/{len(CASOS)} FALLARON")
        return 1
    print(f"RESULTADO: {len(CASOS)}/{len(CASOS)} PASAN — inyecciones frescas + candados compartidos (costo: $0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
