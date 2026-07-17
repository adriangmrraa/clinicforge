# -*- coding: utf-8 -*-
"""Test LOCAL y GRATIS del candado de salida para paciente recurrente.

Decisión 2026-07-17 (Carlos: "dejemos de tirar plata a la basura"): en vez de
re-correr el banco pago N veces para ver si el mini obedece los candados de
texto, la conducta dura se garantiza por CÓDIGO (strip de salida en
buffer_task.py ~4760) y se valida acá con python puro, sin ninguna llamada a la
API. Corre en <1 segundo y cuesta $0.

SYNC: los regex de abajo son COPIA de los de buffer_task.py (candado de salida
recurrente). Si se cambian allá, actualizarlos acá. Se valida contra las
respuestas MALAS reales que el mini produjo en las corridas del banco del
2026-07-17 y contra respuestas BUENAS que el candado NO debe tocar.

Uso:  python orchestrator_service/eval/test_candado_salida.py
"""
import re
import sys

FALLBACK = "Contame qué necesitás y te lo coordino 😊"


def candado_salida(response_text: str, patient_context: str, last_user_msg: str) -> str:
    """Espejo EXACTO de la lógica de buffer_task.py (candado de salida recurrente)."""
    if not (
        response_text
        and patient_context
        and "HISTORIAL: Paciente recurrente" in patient_context
        and "Obra Social registrada" in patient_context
    ):
        return response_text
    _last_txt = (last_user_msg or "").lower()
    _asked_price = any(w in _last_txt for w in ("precio", "valor", "cuanto", "cuánto", "sale", "cuesta", "arancel"))
    response_text = re.sub(
        r"(?im)^.*cont[aá]s con alguna obra social.*$\n?", "", response_text
    ).strip()
    if not _asked_price:
        response_text = re.sub(
            r"(?is)la consulta de evaluaci[oó]n tiene un valor.*?presupuesto correspondiente\.?",
            "", response_text,
        ).strip()
    response_text = re.sub(r"\n{3,}", "\n\n", response_text).strip()
    if not response_text:
        response_text = FALLBACK
    return response_text


# Contextos de juguete (espejo de lo que arma buffer_task)
CTX_RECURRENTE_OS = (
    "• Nombre: Marta Gómez\n"
    "• Obra Social registrada: Jerárquicos Salud\n"
    "• HISTORIAL: Paciente recurrente (4 turnos registrados)."
)
CTX_NUEVO = "• Lead nuevo, sin historial."
CTX_RECURRENTE_PARTICULAR = (
    "• Nombre: Marta Gómez\n"
    "• Obra Social registrada: Particular\n"
    "  ⛔ COBERTURA YA RESUELTA: este paciente es PARTICULAR (registrado en su ficha).\n"
    "• HISTORIAL: Paciente recurrente (4 turnos registrados)."
)

CASOS = [
    # (nombre, respuesta_del_modelo, contexto, último_msj_paciente, chequeos)
    (
        "MALA-1: plantilla $60.000 sin que lo pidiera (corrida particular ❌)",
        "La consulta de evaluación tiene un valor de $60.000. Ahí la doctora te revisa "
        "y te arma el presupuesto correspondiente.\n\n"
        "Te paso opciones:\n1️⃣ lunes 20/07 — 10:00 hs\n2️⃣ martes 21/07 — 11:15 hs\n"
        "¿Cuál te queda mejor?",
        CTX_RECURRENTE_OS,
        "hola! quería un turno para control",
        lambda out: "$60.000" not in out and "valor" not in out.lower() and "1️⃣" in out and "2️⃣" in out,
    ),
    (
        "MALA-2: re-pregunta de cobertura con OS registrada (corrida continuidad ❌)",
        "¡Hola Marta! Como ya venís con el implante en curso, coordinamos la continuidad "
        "con la Dra. Laura.\n"
        "¿Contás con alguna obra social o te atenderías de forma particular?",
        CTX_RECURRENTE_OS,
        "hola, tengo que seguir con el implante",
        lambda out: "obra social" not in out.lower() and "implante en curso" in out,
    ),
    (
        "MALA-3: respuesta que ERA solo la pregunta prohibida → fallback útil",
        "¿Contás con alguna obra social o te atenderías de forma particular?",
        CTX_RECURRENTE_OS,
        "buenas!",
        lambda out: out == FALLBACK,
    ),
    (
        "MALA-4: PARTICULAR registrado + $60.000 no pedido (el flip de la última corrida)",
        "¡Hola Marta! La consulta de evaluación tiene un valor de $60.000. Ahí la doctora "
        "te revisa y te arma el presupuesto correspondiente.\n\n"
        "1️⃣ lunes 20/07 — 10:00 hs\n2️⃣ martes 21/07 — 11:15 hs",
        CTX_RECURRENTE_PARTICULAR,
        "necesito turno para limpieza",
        lambda out: "$60.000" not in out and "1️⃣" in out,
    ),
    (
        "MALA-5: PARTICULAR registrado re-interrogado (la corrida estable que fallaba)",
        "¿Contás con alguna obra social o te atenderías de forma particular?\n"
        "Así te coordino el turno.",
        CTX_RECURRENTE_PARTICULAR,
        "quiero un turno con la dra",
        lambda out: "obra social" not in out.lower() and "coordino el turno" in out,
    ),
    (
        "BUENA-1: paciente NUEVO → la pregunta de cobertura SOBREVIVE (flujo correcto)",
        "¡Hola! Para coordinarte el turno, ¿contás con alguna obra social o te "
        "atenderías de forma particular?",
        CTX_NUEVO,
        "hola quiero un turno",
        lambda out: "obra social" in out.lower(),
    ),
    (
        "BUENA-2: recurrente que SÍ preguntó el precio → el valor SOBREVIVE",
        "La consulta de evaluación tiene un valor de $60.000. Ahí la doctora te revisa "
        "y te arma el presupuesto correspondiente.",
        CTX_RECURRENTE_OS,
        "cuánto sale la consulta?",
        lambda out: "$60.000" in out,
    ),
    (
        "BUENA-3: respuesta normal de turnos → intacta byte a byte",
        "Te paso opciones con la Dra. Laura:\n1️⃣ lunes 20/07 — 10:00 hs\n"
        "2️⃣ martes 21/07 — 11:15 hs\n¿Cuál te queda mejor? 😊",
        CTX_RECURRENTE_OS,
        "dale, pasame horarios",
        lambda out, _in="Te paso opciones con la Dra. Laura:\n1️⃣ lunes 20/07 — 10:00 hs\n"
        "2️⃣ martes 21/07 — 11:15 hs\n¿Cuál te queda mejor? 😊": out == _in,
    ),
]


def main() -> int:
    fallas = 0
    for nombre, respuesta, ctx, ultimo, check in CASOS:
        out = candado_salida(respuesta, ctx, ultimo)
        ok = check(out)
        print(f"{'✅ PASA ' if ok else '❌ FALLA'} — {nombre}")
        if not ok:
            fallas += 1
            print(f"     salida: {out!r}")
    print()
    if fallas:
        print(f"RESULTADO: {fallas}/{len(CASOS)} FALLARON")
        return 1
    print(f"RESULTADO: {len(CASOS)}/{len(CASOS)} PASAN — candado determinista OK (costo: $0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
