# -*- coding: utf-8 -*-
"""Test LOCAL y GRATIS de las variantes rotativas (confirmación + seguimiento).

Pedido Carlos 2026-07-20: mensajes automáticos que roten (no el mismo texto fijo)
y nombre humanizado ('FRANCESCO TOMAS' → 'Francesco'). Prueba el módulo REAL.

Uso:  python orchestrator_service/eval/test_message_variants.py
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.message_variants import (
    dia_humano,
    nombre_bonito,
    variante_confirmacion,
    variante_followup,
)

CASOS = [
    ("'FRANCESCO TOMAS' → 'Francesco' (primer nombre, capitalizado)",
     lambda: nombre_bonito("FRANCESCO TOMAS") == "Francesco"),
    ("'maría julia' → 'María'",
     lambda: nombre_bonito("maría julia") == "María"),
    ("nombre vacío no rompe",
     lambda: nombre_bonito(None) == ""),
    ("dia_humano: miércoles 23/07 (turno de Matías)",
     lambda: dia_humano(datetime(2026, 7, 23, 10, 0)) == "jueves 23/07"),
    ("confirmación CON día: la variante incluye el día",
     lambda: "jueves 23/07" in variante_confirmacion("+549x:20260723", "jueves 23/07")),
    ("confirmación determinista: mismo seed → misma variante (tests reproducibles)",
     lambda: variante_confirmacion("seedA", "lunes 20/07") == variante_confirmacion("seedA", "lunes 20/07")),
    ("confirmación ROTA: seeds distintos recorren más de una variante",
     lambda: len({variante_confirmacion(f"s{i}", "lunes 20/07") for i in range(12)}) >= 2),
    ("followup paciente: saluda con nombre bonito y pregunta por molestias",
     lambda: (lambda m: "Francesco" in m and "FRANCESCO" not in m and "molestia" in m.lower())(
         variante_followup("s1", "FRANCESCO TOMAS", "16/07"))),
    ("followup guardián: pregunta cómo sigue el/la paciente (no 'te sentís')",
     lambda: (lambda m: "Valentina" in m and "te sentís" not in m.lower() and "te sentiste" not in m.lower())(
         variante_followup("s2", "valentina", "16/07", para_guardian=True))),
    ("followup ROTA entre seeds",
     lambda: len({variante_followup(f"s{i}", "Ana", "16/07") for i in range(12)}) >= 2),
]


def main() -> int:
    fallas = 0
    for nombre, check in CASOS:
        try:
            ok = check()
        except Exception as e:
            ok = False
            print(f"     excepción: {e}")
        print(f"{'✅ PASA ' if ok else '❌ FALLA'} — {nombre}")
        if not ok:
            fallas += 1
    print()
    if fallas:
        print(f"RESULTADO: {fallas}/{len(CASOS)} FALLARON")
        return 1
    print(f"RESULTADO: {len(CASOS)}/{len(CASOS)} PASAN — mensajes rotativos y humanos (costo: $0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
