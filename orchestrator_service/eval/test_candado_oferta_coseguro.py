# -*- coding: utf-8 -*-
"""Test LOCAL y GRATIS de dos candados nuevos (caso prod Lucas, pruebas 2026-07-18):
  1) OFERTA de turnos en UN globito (el mini la partía en 4).
  2) COSEGURO no es solo 'en efectivo' (el mini lo inventaba; es efectivo O transferencia).

SYNC: la lógica replica la de buffer_task.py. Si se cambia allá, actualizar acá.

Uso:  python orchestrator_service/eval/test_candado_oferta_coseguro.py
"""
import re
import sys


def candado_oferta(response_text: str) -> str:
    """Espejo del candado de oferta de buffer_task.py."""
    if (
        response_text
        and "1️⃣" in response_text
        and re.search(r"(2️⃣|cu[aá]l te queda mejor|opciones disponibles)", response_text, re.I)
        and not re.search(r"alias|cbu|anamnesis|ficha m[eé]dica", response_text, re.I)
    ):
        return re.sub(r"\n\s*\n", "\n", response_text).strip()
    return response_text


def candado_coseguro(response_text: str) -> str:
    """Espejo del candado de coseguro de buffer_task.py."""
    if response_text and re.search(r"coseguro", response_text, re.I) and re.search(r"en efectivo", response_text, re.I):
        response_text = re.sub(r"(?i)\bse abona en efectivo\b", "se abona (en efectivo o por transferencia)", response_text)
        response_text = re.sub(r"(?i)\bse paga en efectivo\b", "se paga (en efectivo o por transferencia)", response_text)
    return response_text


def _globitos(text):
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


# La oferta REAL de Lucas (salió en 4 globitos por los dobles saltos)
OFERTA_LUCAS = (
    "El 17/08 no hay atención.\nTe busqué los turnos más cercanos:\n\n"
    "🗓️ Opciones disponibles para tu Control / Revisión:\n\n"
    "1️⃣ Martes 18/08 — 10:00 hs\n2️⃣ Miércoles 19/08 — 10:00 hs\n\n"
    "¿Cuál te queda mejor?"
)

CASOS = [
    (
        "OFERTA: 4 globitos → 1 (sin perder ninguna opción)",
        candado_oferta,
        OFERTA_LUCAS,
        lambda out: len(_globitos(out)) == 1 and "1️⃣" in out and "2️⃣" in out and "¿Cuál te queda mejor?" in out and "17/08 no hay atención" in out,
    ),
    (
        "OFERTA con coseguro adelante → todo en 1 globito (espejo del ejemplo del prompt)",
        candado_oferta,
        "Genial 😊 Con OSDE, si corresponde coseguro se confirma en la clínica.\n\n"
        "Te paso opciones:\n1️⃣ Lunes 20/07 — 10:00 hs\n2️⃣ Martes 21/07 — 11:15 hs\n\n¿Cuál te queda mejor?",
        lambda out: len(_globitos(out)) == 1 and "OSDE" in out and "1️⃣" in out,
    ),
    (
        "OFERTA-NO: un cierre con seña NO lo toca el candado de oferta",
        candado_oferta,
        "¡Listo! Tu turno quedó confirmado.\n\n1️⃣ recordá traer tu DNI.\n\nAlias: dradelgadoml",
        lambda out: len(_globitos(out)) == 3,  # tiene 'alias' → el candado NO actúa
    ),
    (
        "COSEGURO: 'se abona en efectivo' → efectivo o transferencia",
        candado_coseguro,
        "Sí, trabajamos con OSDE 😊 El coseguro se abona en efectivo el día de la consulta.",
        lambda out: "en efectivo o por transferencia" in out and "abona en efectivo el" not in out,
    ),
    (
        "COSEGURO-NO: sin la palabra coseguro no se toca (un descuento por efectivo queda igual)",
        candado_coseguro,
        "Tenemos 10% de descuento por pago en efectivo 😊",
        lambda out: out == "Tenemos 10% de descuento por pago en efectivo 😊",
    ),
]


def main() -> int:
    fallas = 0
    for nombre, fn, entrada, check in CASOS:
        out = fn(entrada)
        ok = check(out)
        print(f"{'✅ PASA ' if ok else '❌ FALLA'} — {nombre}")
        if not ok:
            fallas += 1
            print(f"     salida: {out!r}")
    print()
    if fallas:
        print(f"RESULTADO: {fallas}/{len(CASOS)} FALLARON")
        return 1
    print(f"RESULTADO: {len(CASOS)}/{len(CASOS)} PASAN — oferta 1 globito + coseguro correcto (costo: $0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
