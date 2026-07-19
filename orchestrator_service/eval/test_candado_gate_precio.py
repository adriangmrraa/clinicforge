# -*- coding: utf-8 -*-
"""Test LOCAL y GRATIS del candado GATE-PRECIO (enforcement determinista del A1).

Regla de negocio: NUNCA dar el valor de la consulta si la cobertura no está
resuelta (ni Particular ni OS conocida). El gate A1 lo pide por texto y el mini
lo saltea a veces (fallo edge-triple del banco). Este candado lo garantiza por
código. Excepciones: pidió explícitamente "particular", o tratamiento ESTÉTICO
(carillas/blanqueamiento = siempre particular).

SYNC: replica la lógica de buffer_task.py. Si se cambia allá, actualizar acá.

Uso:  python orchestrator_service/eval/test_candado_gate_precio.py
"""
import re
import sys


def candado_gate_precio(response_text: str, patient_context: str, last_user_msg: str) -> str:
    """Espejo EXACTO del candado gate-precio de buffer_task.py."""
    if not (response_text and re.search(r"tiene un valor", response_text, re.I)):
        return response_text
    _ctx = patient_context or ""
    _cov_resuelta = bool(_ctx) and (
        "Obra Social registrada" in _ctx
        or bool(re.search(r"\bissn\b", _ctx, re.I))
        or "instituto de seguridad" in _ctx.lower()
        or "particular" in _ctx.lower()
    )
    _minor = bool(_ctx) and ("HIJO/A MENOR" in _ctx or "[INTERNAL_BOOKING_CONTEXT]" in _ctx)
    _last = (last_user_msg or "").lower()
    _pidio_particular = "particular" in _last
    _estetico = any(k in _last for k in ("carilla", "blanqueamiento", "diseño de sonrisa", "estetic", "estétic"))
    if (_minor or not _cov_resuelta) and not _pidio_particular and not _estetico:
        response_text = re.sub(
            r"(?is)la consulta de evaluaci[oó]n tiene un valor.*?presupuesto correspondiente\.?",
            "", response_text,
        ).strip()
        response_text = re.sub(r"\n{3,}", "\n\n", response_text).strip()
        if "obra social" not in response_text.lower():
            q = "¿Contás con alguna obra social o te atenderías de forma particular?"
            response_text = (response_text + "\n" + q).strip() if response_text else q
    return response_text


PARRAFO = (
    "La consulta de evaluación tiene un valor de $60.000. Ahí la doctora evalúa tu caso "
    "y te orienta sobre las opciones de tratamiento más adecuadas para vos. Una vez "
    "realizada la evaluación, se informa el plan y el presupuesto correspondiente."
)

CASOS = [
    (
        "NUEVO sin cobertura pregunta precio → NO se regala el valor, se pregunta cobertura (edge-triple)",
        "Hola! Soy Paula, del equipo de Clínica Dra. Laura Delgado.\n\n" + PARRAFO,
        "",  # lead nuevo: sin contexto
        "necesito saber el precio de la consulta, a qué hora atienden y si puedo agendar",
        lambda out: "$60.000" not in out and "obra social" in out.lower(),
    ),
    (
        "NUEVO que pide EXPLÍCITO el particular → el valor SÍ sale",
        PARRAFO,
        "",
        "¿cuánto sale la consulta particular?",
        lambda out: "$60.000" in out,
    ),
    (
        "ESTÉTICO (carillas = siempre particular) → el valor SÍ sale",
        PARRAFO,
        "",
        "quiero carillas, ¿cuánto saldría?",
        lambda out: "$60.000" in out,
    ),
    (
        "PARTICULAR ya resuelto en contexto → el valor SÍ sale",
        PARRAFO,
        "• Obra Social registrada: Particular",
        "¿cuánto sale la consulta?",
        lambda out: "$60.000" in out,
    ),
    (
        "MENOR (la OS del contexto es de la madre) → NO dar el valor, preguntar cobertura del menor",
        PARRAFO,
        "• Obra Social registrada: OSDE\n⚠️ Estás agendando para un HIJO/A MENOR",
        "y para mi hijo cuánto sale la consulta?",
        lambda out: "$60.000" not in out and "obra social" in out.lower(),
    ),
    (
        "Respuesta sin párrafo del valor → no se toca",
        "Te paso opciones:\n1️⃣ Lunes 20/07 — 10:00 hs",
        "",
        "quiero un turno",
        lambda out: out == "Te paso opciones:\n1️⃣ Lunes 20/07 — 10:00 hs",
    ),
]


def main() -> int:
    fallas = 0
    for nombre, resp, ctx, last, check in CASOS:
        out = candado_gate_precio(resp, ctx, last)
        ok = check(out)
        print(f"{'✅ PASA ' if ok else '❌ FALLA'} — {nombre}")
        if not ok:
            fallas += 1
            print(f"     salida: {out!r}")
    print()
    if fallas:
        print(f"RESULTADO: {fallas}/{len(CASOS)} FALLARON")
        return 1
    print(f"RESULTADO: {len(CASOS)}/{len(CASOS)} PASAN — gate de precio garantizado (costo: $0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
