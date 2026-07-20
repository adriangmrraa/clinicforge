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
    candado_multi_turno,
    es_pregunta_monto_coseguro,
    iny_derivacion_explicita,
    iny_multi_persona,
    iny_os_en_mensaje,
    iny_pide_cancelar,
    iny_queja_precio,
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
