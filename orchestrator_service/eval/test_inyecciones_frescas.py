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
    candado_compactar_cimo,
    candado_coseguro_frio,
    candado_derivar_clinico_especial,
    candado_issn_anti_ceder,
    candado_issn_no_deriva,
    candado_encuadre_valor,
    candado_formato,
    candado_mencion_coseguro,
    candado_multi_turno,
    candado_particular_incoherente,
    candado_quiere_antes_salida,
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
    iny_restriccion_dias,
    candado_dia_sin_consultar,
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
        "OS: 'Yo tengo IOMA' → rama sin-convenio (IOMA NO está en el panel real, sync 2026-07-20)",
        lambda: iny_os_en_mensaje("Bueno, quiero un turno. ¿Trabajan con alguna obra social? Yo tengo IOMA."),
        lambda out: out is not None and "NO tiene convenio" in out and "comprobante" in out.lower(),
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
        "quiere-antes: la inyección explica el porqué real + salida particular AMABLE + sin presionar",
        lambda: iny_quiere_antes("OSDE", 30, "19/08"),
        lambda out: out is not None
        and "OSDE" in out
        and "19/08" in out
        and "particular" in out.lower()
        and "no tengo disponibilidad" in out.lower()
        and "sin presionar" in out.lower()
        # v2 (caso 4 manual): la frase seca queda PROHIBIDA y se pide la versión amable
        and "PROHIBIDA la frase seca" in out
        and "elegís vos" in out,
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
    # ------------------- OS sin convenio (rama no-panel) -------------------
    (
        "OS no-panel: Swiss Medical → encuadre directo particular + comprobante (fallo v4 terce-madre)",
        lambda: iny_os_en_mensaje("Hola, necesito un turno para mi mamá María, ella tiene Swiss Medical, ¿cuánto es la consulta?"),
        lambda out: out is not None and "NO tiene convenio" in out and "comprobante" in out.lower(),
    ),
    (
        "OS no-panel: IOMA → mismo encuadre directo",
        lambda: iny_os_en_mensaje("tengo ioma, ¿atienden?"),
        lambda out: out is not None and "NO tiene convenio" in out,
    ),
    (
        "OS del panel (OSDE) → sigue la rama normal (reconocer + verificar), no la de sin-convenio",
        lambda: iny_os_en_mensaje("tengo OSDE, quiero un turno"),
        lambda out: out is not None and "NO tiene convenio" not in out and "OSDE" in out,
    ),
    # ------------------- candado salida quiere-antes -------------------
    (
        "quiere-antes salida: oferta por cobertura sin 'particular' → agrega la vía (fallo v4)",
        lambda: candado_quiere_antes_salida(
            "Te entiendo, ojalá pudiera adelantártelo 😊\nPara OSDE, la primera fecha disponible es a partir del 25/07.\n1️⃣ Lunes 27/07 — 10:00 hs\n2️⃣ Martes 28/07 — 11:15 hs\nCuál te queda mejor?"
        ),
        lambda out: "particular" in out.lower(),
    ),
    (
        "quiere-antes salida: ya menciona particular → NO duplica",
        lambda: candado_quiere_antes_salida(
            "Por tu cobertura arrancan el 25/07, o podés atenderte particular antes.\n1️⃣ Lunes 27/07 — 10:00 hs"
        ),
        lambda out: out.lower().count("particular") == 1,
    ),
    (
        "quiere-antes salida: respuesta sin oferta de slots → NO se toca",
        lambda: candado_quiere_antes_salida("Te entiendo. ¿Cómo preferís seguir?"),
        lambda out: "particular" not in out.lower(),
    ),
    # ------------------- compactador CIMO + mención coseguro v5 -------------------
    (
        "CIMO: el bloque ISSN sale en 1 globito (caso real de pruebas)",
        lambda: candado_compactar_cimo(
            "Para cirugía maxilofacial con ISSN, la atención se realiza a través de CIMO. Podés comunicarte al +54 9 299 329-4089.\n\nPara otros tratamientos, la atención en el consultorio es particular."
        ),
        lambda out: "\n\n" not in out and "CIMO" in out,
    ),
    (
        "CIMO: respuestas sin CIMO NO se tocan",
        lambda: candado_compactar_cimo("Hola!\n\n¿Contás con obra social?"),
        lambda out: "\n\n" in out,
    ),
    (
        "mención-coseguro v5: 'cobertura restringida... ¿te paso opciones?' sin coseguro → agrega la línea (fallo v5 os-osde)",
        lambda: candado_mencion_coseguro(
            "Con OSDE trabajamos con cobertura restringida; el detalle se confirma en la clínica.\nLa primera fecha disponible es a partir del 25/07/2026, ¿te paso opciones desde ahí? 📅",
            "Hola, soy Paula. Necesito un turno de limpieza. Tengo OSDE.",
            "Lead nuevo.",
        ),
        lambda out: "coseguro" in out.lower(),
    ),
    # ------------------- restricción de días (caso Lucas manual) -------------------
    (
        "restricción-días: 'puedo los lunes o viernes únicamente' → dispara (re-consultar la agenda)",
        lambda: iny_restriccion_dias("Para mañana o pasado no tenes??? ademas puedo los lunes o viernes unicamente"),
        lambda out: out is not None and "check_availability" in out,
    ),
    (
        "restricción-días: '¿tenés para el viernes?' → dispara",
        lambda: iny_restriccion_dias("¿Tenés algo para el viernes?"),
        lambda out: out is not None,
    ),
    (
        "restricción-días: mensaje sin días de semana NO dispara",
        lambda: iny_restriccion_dias("quiero un turno lo antes posible"),
        lambda out: out is None,
    ),
    (
        "día-sin-consultar: 'lunes o viernes no me quedan' SIN haber llamado la tool → recortado + ofrece revisar",
        lambda: candado_dia_sin_consultar(
            "Para mañana y pasado no tengo lugares, y además lunes o viernes no me quedan para este turno 😊\n"
            "Te quedan estos dos:\n1️⃣ Martes 28/07 — 18:30 hs\n2️⃣ Miércoles 29/07 — 10:45 hs\n¿Cuál te viene mejor?",
            [],
        ),
        lambda out: "no me quedan" not in out and "revise la agenda" in out,
    ),
    (
        "día-sin-consultar: la MISMA afirmación CON la tool llamada → NO se toca (la agenda es real)",
        lambda: candado_dia_sin_consultar(
            "Busqué y los viernes no hay lugar este mes 😊\n1️⃣ Martes 28/07 — 18:30 hs",
            ["check_availability"],
        ),
        lambda out: "no hay lugar" in out,
    ),
    (
        "día-sin-consultar: respuesta sin afirmaciones de día NO se toca",
        lambda: candado_dia_sin_consultar("¿Contás con alguna obra social?", []),
        lambda out: out == "¿Contás con alguna obra social?",
    ),
    (
        "quiere-antes ampliado: 'Para mañana o pasado no tenes???' con OS demorada → matchea",
        lambda: quiere_antes_matchea("Para mañana o pasado no tenes???"),
        lambda out: out is True,
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
    # ------------------- avance v2: pedido imperativo de datos (caso 5 manual) -------------------
    (
        "avance v2: 'me falta tu nombre y apellido, y tu DNI' (sin '?') → NO agrega pregunta redundante",
        lambda: candado_avance(
            "Perfecto, quedó reservado ese turno para vos 😊\nPara dejarlo agendado me falta tu nombre y apellido, y tu DNI solo con números.",
            "Agendame para el martes 11",
            [],
        ),
        lambda out: "tipo de consulta" not in out and "te busco opciones" not in out,
    ),
    (
        "avance v2: 'pasame tu nombre completo y DNI' → tampoco agrega",
        lambda: candado_avance(
            "Genial. Pasame tu nombre completo y DNI así lo dejo agendado.",
            "quiero el turno del lunes",
            [],
        ),
        lambda out: out == "Genial. Pasame tu nombre completo y DNI así lo dejo agendado.",
    ),
    (
        "avance: globito muerto REAL (sin pregunta ni pedido de datos) → sigue agregando la pregunta",
        lambda: candado_avance(
            "Vamos a coordinar esa continuidad.",
            "quiero un turno para terminar mi tratamiento",
            [],
        ),
        lambda out: "?" in out,
    ),
    # ------------------- coseguro frío (caso 7 manual) -------------------
    (
        "coseguro-frío: 'no te paso un monto por acá' → reemplazado por el porqué cálido",
        lambda: candado_coseguro_frio(
            "La consulta con OSDE puede tener un coseguro que se confirma en la clínica, no te paso un monto por acá.\nPara esta evaluación tengo: 1️⃣ Lunes 27/07 — 17:30 hs."
        ),
        lambda out: "no te paso" not in out and "depende del plan" in out and "sin sorpresas" in out and "1️⃣" in out,
    ),
    (
        "coseguro-frío: respuesta cálida normal → NO la toca",
        lambda: candado_coseguro_frio("El coseguro depende de tu plan y te lo confirman en la clínica 😊"),
        lambda out: out == "El coseguro depende de tu plan y te lo confirman en la clínica 😊",
    ),
    (
        "coseguro-frío v2 (regresión verif. 2026-07-21): 'no te doy un número de teléfono' → NO lo toca",
        lambda: candado_coseguro_frio("No te doy un número de teléfono de la doctora, pero te ayudo por acá 😊"),
        lambda out: out == "No te doy un número de teléfono de la doctora, pero te ayudo por acá 😊",
    ),
    # ------------------- particular incoherente (casos 1/8 manuales) -------------------
    (
        "particular-incoherente: opciones DESPUÉS del plazo + venta de 'antes particular' → se recorta la venta",
        lambda: candado_particular_incoherente(
            "Para turnos por cobertura, OSDE agenda a partir del 25/07. Si querés atenderte antes, también podés hacerlo de forma particular.\n"
            "1️⃣ Lunes 27/07 — 17:30 hs\n2️⃣ Martes 28/07 — 13:00 hs\n¿Cuál te viene mejor?"
        ),
        lambda out: "particular" not in out.lower() and "a partir del 25/07" in out and "1️⃣" in out and "2️⃣" in out,
    ),
    (
        "particular-incoherente: opciones ANTES del plazo (vía particular real) → NO toca nada",
        lambda: candado_particular_incoherente(
            "Por cobertura, OSDE agenda a partir del 09/08. Si querés atenderte antes, podés hacerlo de forma particular.\n"
            "1️⃣ Lunes 27/07 — 17:30 hs\n2️⃣ Martes 28/07 — 13:00 hs"
        ),
        lambda out: "particular" in out.lower(),
    ),
    (
        "particular-incoherente: sin plazo mencionado → NO toca nada",
        lambda: candado_particular_incoherente("1️⃣ Lunes 27/07 — 17:30 hs\n2️⃣ Martes 28/07 — 13:00 hs"),
        lambda out: out == "1️⃣ Lunes 27/07 — 17:30 hs\n2️⃣ Martes 28/07 — 13:00 hs",
    ),
    # ------------------- formato: párrafo-ladrillo (casos 3/6 manuales) -------------------
    (
        "formato: el ladrillo del pitch de implantes (caso 6) → una oración por línea, respetando 'Dra.'",
        lambda: candado_formato(
            "Hola 😊 Soy Paula, del equipo de Clínica Dra. Laura Delgado. Para implantes lo ideal es hacer primero una "
            "evaluación con la Dra. Laura Delgado. La consulta de evaluación tiene un valor de $60.000. Ahí la doctora "
            "evalúa tu caso y te orienta sobre las opciones de tratamiento más adecuadas para vos. Una vez realizada la "
            "evaluación, se informa el plan y el presupuesto correspondiente."
        ),
        lambda out: out.count("\n") >= 3 and "\n\n" not in out and "Dra.\n" not in out and "$60.000" in out,
    ),
    (
        "formato: párrafo corto → NO lo toca",
        lambda: candado_formato("Listo, quedó confirmado tu turno para el lunes 😊"),
        lambda out: out == "Listo, quedó confirmado tu turno para el lunes 😊",
    ),
    (
        "formato: oferta con 1️⃣ larga → NO la toca (ya tiene su propio formato)",
        lambda: candado_formato(
            "1️⃣ Lunes 27/07 — 17:30 hs con la doctora en el consultorio de Salta 147 primer piso, y también 2️⃣ Martes "
            "28/07 — 13:00 hs con la doctora en el mismo consultorio de siempre. Decime cuál te queda más cómodo y lo "
            "dejamos reservado con tus datos, además si tenés estudios previos traelos."
        ),
        lambda out: "\n" not in out,
    ),
    # ------------------- quiere-antes: salida v2 amable (caso 4 manual) -------------------
    (
        "quiere-antes-salida v2: la línea agregada es la versión amable (sin 'si preferís no esperar')",
        lambda: candado_quiere_antes_salida("Por tu cobertura, la primera fecha disponible es a partir del 09/08.\n1️⃣ Lunes 10/08 — 15:30 hs"),
        lambda out: "no esperar" not in out and "vía particular" in out and "elegís vos" in out,
    ),
    # ------------------- ISSN no se deriva (caso Griselda prod 2026-07-21) -------------------
    (
        "issn-no-deriva: Griselda (deriva al equipo sin ofrecer turno) → reconduce a consulta particular, conserva CIMO",
        lambda: candado_issn_no_deriva(
            "Para cirugía maxilofacial con ISSN, la atención se realiza a través de CIMO. Podés comunicarte al +54 9 299 329-4089.\n"
            "Para otros tratamientos, la atención en el consultorio es particular. Ya le pasé tu caso al equipo para que lo revisen y te contacten.",
            "Obra Social registrada: ISSN",
            "No no, es otro tipo de cirugía.",
        ),
        lambda out: ("pasé tu caso al equipo" not in out and "consulta de evaluación" in out
                     and "reintegro" in out and "CIMO" in out),
    ),
    (
        "issn-no-deriva: la respuesta YA ofrece consulta particular → NO toca",
        lambda: candado_issn_no_deriva(
            "Con ISSN todo es particular en el consultorio. ¿Te agendo una consulta de evaluación? Después gestionás el reintegro.",
            "ISSN", "dale",
        ),
        lambda out: out == "Con ISSN todo es particular en el consultorio. ¿Te agendo una consulta de evaluación? Después gestionás el reintegro.",
    ),
    (
        "issn-no-deriva: paciente pidió la cirugía maxilofacial → NO reconduce (CIMO es correcto)",
        lambda: candado_issn_no_deriva(
            "Para la cirugía maxilofacial coordinás con CIMO al 299. Ya le pasé tu caso al equipo.",
            "ISSN", "necesito la cirugía maxilofacial",
        ),
        lambda out: "pasé tu caso al equipo" in out,
    ),
    (
        "issn-no-deriva: sin ISSN en el contexto → NO toca (otra OS deriva legítimamente)",
        lambda: candado_issn_no_deriva(
            "Ya le pasé tu caso al equipo para que te contacten.",
            "Obra Social registrada: OSDE", "hola",
        ),
        lambda out: out == "Ya le pasé tu caso al equipo para que te contacten.",
    ),
    (
        "issn-no-deriva: ISSN pero el paciente INSISTE en cobertura → deja derivar (regla de insistencia)",
        lambda: candado_issn_no_deriva(
            "Con ISSN es particular. Ya le pasé tu caso al equipo para que lo revisen.",
            "ISSN", "insisto, la obra social me lo tiene que cubrir",
        ),
        lambda out: "pasé tu caso al equipo" in out,
    ),
    # ------------------- ISSN anti-ceder (casos prod 21/07: el bot "dice que sí") -------------------
    (
        "issn-anti-ceder: 'Sí, para la consulta odontológica trabajamos con ISSN' → forzar particular+CIMO",
        lambda: candado_issn_anti_ceder(
            "Sí, para la consulta odontológica trabajamos con ISSN.",
            "Obra Social registrada: ISSN", "Lo cubre issn?",
        ),
        lambda out: "trabajamos con issn" not in out.lower() and "particular" in out.lower() and "CIMO" in out,
    ),
    (
        "issn-anti-ceder: 'con ISSN la consulta se maneja según tu caso' → forzar aclaración",
        lambda: candado_issn_anti_ceder(
            "Sí, con ISSN la consulta se maneja según tu caso y en la clínica te confirman si corresponde coseguro 😊",
            "ISSN", "La consulta la cubre issn?",
        ),
        lambda out: "se maneja según tu caso" not in out.lower() and "particular" in out.lower(),
    ),
    (
        "issn-anti-ceder: preserva la oferta de turnos al reemplazar el ceder",
        lambda: candado_issn_anti_ceder(
            "Sí, para la consulta trabajamos con ISSN.\n\n1️⃣ Martes 28/07 — 18:30 hs\n2️⃣ Miércoles 29/07 — 10:45 hs\n¿Cuál te queda mejor?",
            "ISSN", "la consulta la cubre?",
        ),
        lambda out: "particular" in out.lower() and "1️⃣" in out and "28/07" in out,
    ),
    (
        "issn-anti-ceder: respuesta que YA dice 'de forma particular' → NO toca",
        lambda: candado_issn_anti_ceder(
            "La consulta con ISSN sería de forma particular 😊",
            "ISSN", "la cubre?",
        ),
        lambda out: out == "La consulta con ISSN sería de forma particular 😊",
    ),
    (
        "issn-anti-ceder: sin ISSN → NO toca (otra OS con convenio real puede decir 'sí trabajamos')",
        lambda: candado_issn_anti_ceder(
            "Sí, trabajamos con OSDE.",
            "Obra Social registrada: OSDE", "trabajan con osde?",
        ),
        lambda out: out == "Sí, trabajamos con OSDE.",
    ),
    # ------------------- clínico especial: derivar ante lo que requiere evaluación humana -------------------
    (
        "clínico-especial: '¿atienden bebés?' → deriva (no afirma la capacidad inventada)",
        lambda: candado_derivar_clinico_especial(
            "Sí, atendemos bebés y también pacientes pediátricos.",
            "quisiera saber si trabaja con bebés?", [],
        ),
        lambda out: "atendemos bebés" not in out and "derivé" in out.lower(),
    ),
    (
        "clínico-especial: 'mi bebé tiene malformación en el paladar' → deriva",
        lambda: candado_derivar_clinico_especial(
            "Te podemos ayudar con eso, ¿qué día te viene bien? 😊",
            "Mi bebé tiene una malformación en el paladar sin hundimiento de labios",
            [],
        ),
        lambda out: "derivé" in out.lower(),
    ),
    (
        "clínico-especial: turno normal de limpieza → NO deriva (no es tema especial)",
        lambda: candado_derivar_clinico_especial(
            "Te paso opciones para tu limpieza:\n1️⃣ Lunes 20/07 — 10:00 hs",
            "quiero una limpieza dental", [],
        ),
        lambda out: "derivé" not in out.lower() and "1️⃣" in out,
    ),
    (
        "clínico-especial: el bot YA llamó derivhumano → NO toca",
        lambda: candado_derivar_clinico_especial(
            "Ya derivé tu consulta sobre el bebé al equipo.",
            "atienden bebés?", ["derivhumano"],
        ),
        lambda out: out == "Ya derivé tu consulta sobre el bebé al equipo.",
    ),
    (
        "clínico-especial: enfermedad oncológica (quimioterapia) → deriva",
        lambda: candado_derivar_clinico_especial(
            "Claro, te agendo un turno normal 😊",
            "estoy en quimioterapia, puedo hacerme una extracción?", [],
        ),
        lambda out: "derivé" in out.lower(),
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
