# -*- coding: utf-8 -*-
"""Test LOCAL y GRATIS del módulo central de teléfonos familiares.

Pedido Carlos 2026-07-18: que los familiares/menores no dupliquen teléfonos y que
el seguimiento le llegue REALMENTE a la persona a cargo. Este módulo es la única
fuente de verdad (services/family_phones.py) usada por el panel (create_patient)
y los jobs (followups). Acá se prueba directo el módulo real (import, no espejo).

Uso:  python orchestrator_service/eval/test_family_phones.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.family_phones import (
    is_placeholder_phone,
    next_minor_phone,
    resolve_contact_phone,
    same_person,
)

CASOS = [
    # --- ¿a quién le escribo? (la regla del seguimiento) ---
    ("menor -M1 → se escribe al GUARDIÁN",
     lambda: resolve_contact_phone("+5493434732389-M1", "+5493434732389") == "+5493434732389"),
    ("menor -M2 (dos hijos) → guardián",
     lambda: resolve_contact_phone("+549111-M2", "+549111") == "+549111"),
    ("placeholder de import SIN-TEL → guardián si existe",
     lambda: resolve_contact_phone("SIN-TEL-042", "+549222") == "+549222"),
    ("menor SIN guardián cargado → None (no hay a quién escribir, se saltea)",
     lambda: resolve_contact_phone("+549111-M1", None) is None),
    ("adulto con número real → su propio número (el guardián NO pisa)",
     lambda: resolve_contact_phone("+5492995240803", "+549999") == "+5492995240803"),
    # --- detección de placeholder ---
    ("-M10 también es placeholder (dos dígitos)",
     lambda: is_placeholder_phone("+549111-M10") is True),
    ("número real NO es placeholder",
     lambda: is_placeholder_phone("+5493435201484") is False),
    # --- ¿misma persona? (la regla del panel para no pisar al padre) ---
    ("mismo primer nombre con tilde/mayúsculas → MISMA persona (update normal)",
     lambda: same_person("Valentína", "valentina lopez") is True),
    ("nombre distinto → OTRA persona (crear familiar -M, no pisar)",
     lambda: same_person("Carlos", "Valentina") is False),
    ("nombre vacío no decide → se asume misma persona (conservador)",
     lambda: same_person("", "Valentina") is True),
    # --- generación del -M ---
    ("primer familiar → -M1",
     lambda: next_minor_phone("+549111", 0) == "+549111-M1"),
    ("tercer familiar → -M3",
     lambda: next_minor_phone("+549111", 2) == "+549111-M3"),
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
    print(f"RESULTADO: {len(CASOS)}/{len(CASOS)} PASAN — familiares resueltos al adulto a cargo (costo: $0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
