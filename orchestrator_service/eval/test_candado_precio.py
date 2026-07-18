# -*- coding: utf-8 -*-
"""Test LOCAL y GRATIS del candado 'no repetir el precio' (cross-turn).

Optimización 2026-07-17 (Carlos, caso María Montes: el párrafo de $60.000 salió 2
veces enteras). Si el párrafo largo del valor de la consulta YA se envió en un
mensaje reciente del bot, la segunda vez va corto (una línea con el número). No
borra el precio; evita repetir el discurso. La detección de "ya enviado" es una
consulta a chat_messages (acá se simula con la bandera already_priced).

SYNC: la transformación replica la de buffer_task.py. Si se cambia allá, actualizar acá.

Uso:  python orchestrator_service/eval/test_candado_precio.py
"""
import re
import sys


def candado_precio(response_text: str, already_priced: bool) -> str:
    """Espejo de la transformación de buffer_task.py (already_priced = ¿ya se mandó antes?)."""
    if not (response_text and re.search(r"tiene un valor", response_text, re.I)):
        return response_text
    if not already_priced:
        return response_text  # primera vez → el párrafo largo sale entero (correcto)
    _amt = re.search(r"\$\s?[\d.]+", response_text)
    _short = (
        f"Como te comenté, la consulta es de {_amt.group(0).replace(' ', '')} 😊"
        if _amt
        else "Como te comenté, ese es el valor de la consulta 😊"
    )
    return re.sub(
        r"(?is)la consulta de evaluaci[oó]n tiene un valor.*?presupuesto correspondiente\.?",
        _short,
        response_text,
    ).strip()


PARRAFO_LARGO = (
    "La consulta de evaluación tiene un valor de $60.000. Ahí la doctora evalúa tu caso "
    "y te orienta sobre las opciones de tratamiento más adecuadas para vos. Una vez "
    "realizada la evaluación, se informa el plan y el presupuesto correspondiente."
)

CASOS = [
    (
        "PRIMERA vez (no enviado antes) → párrafo largo SOBREVIVE",
        PARRAFO_LARGO,
        False,
        lambda out: out == PARRAFO_LARGO,
    ),
    (
        "SEGUNDA vez (ya enviado) → va CORTO con el número",
        PARRAFO_LARGO,
        True,
        lambda out: "$60.000" in out and "doctora evalúa" not in out and "Como te comenté" in out,
    ),
    (
        "Segunda vez + horarios: acorta el precio pero conserva los turnos",
        PARRAFO_LARGO + "\n\n1️⃣ Miércoles 29/07 — 10:45 hs\n2️⃣ Viernes 31/07 — 11:30 hs",
        True,
        lambda out: "$60.000" in out and "doctora evalúa" not in out and "1️⃣" in out and "2️⃣" in out,
    ),
    (
        "Respuesta SIN precio → no se toca aunque already_priced",
        "Te paso opciones:\n1️⃣ Lunes 20/07 — 10:00 hs\n2️⃣ Martes 21/07 — 11:15 hs",
        True,
        lambda out: out == "Te paso opciones:\n1️⃣ Lunes 20/07 — 10:00 hs\n2️⃣ Martes 21/07 — 11:15 hs",
    ),
]


def main() -> int:
    fallas = 0
    for nombre, entrada, already, check in CASOS:
        out = candado_precio(entrada, already)
        ok = check(out)
        print(f"{'✅ PASA ' if ok else '❌ FALLA'} — {nombre}")
        if not ok:
            fallas += 1
            print(f"     salida: {out!r}")
    print()
    if fallas:
        print(f"RESULTADO: {fallas}/{len(CASOS)} FALLARON")
        return 1
    print(f"RESULTADO: {len(CASOS)}/{len(CASOS)} PASAN — precio no se repite (costo: $0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
