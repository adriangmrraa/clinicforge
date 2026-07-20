# -*- coding: utf-8 -*-
"""Test LOCAL y GRATIS del candado de salida del CIERRE del turno.

Optimización 2026-07-17 (Carlos, caso María Montes): el cierre saturaba con ~7
globitos. El candado (buffer_task ~4798) reagrupa el cierre de agendado en 2
globitos (confirmación | opcionales), saca el relleno y las re-confirmaciones
duplicadas. Determinista, no depende del modelo.

SYNC: la lógica de _candado_cierre replica la de buffer_task.py. Si se cambia allá,
actualizar acá.

Uso:  python orchestrator_service/eval/test_candado_cierre.py
"""
import re
import sys


def candado_cierre(response_text: str) -> str:
    """Espejo EXACTO del candado del cierre en buffer_task.py."""
    if not response_text:
        return response_text
    _rt = response_text
    # v2 (caso Lucas 2026-07-20, "los cierres son muy largos"): compresión de las
    # frases-plantilla ANTES de reagrupar. Mismo contenido, ~40% menos texto.
    _rt = re.sub(
        r"(?i)si quer[eé]s,? pod[eé]s adelantar una se[ñn]a de \$?([\d\.,]+)(?: por transferencia)?:?\s*\n",
        r"Seña opcional para asegurarlo: $\1 →\n", _rt)
    _rt = re.sub(
        r"(?i)Alias:\s*([^\n|]+?)\s*\n\s*CBU:\s*([^\n|]+?)\s*\n\s*Titular:\s*([^\n]+)",
        r"Alias: \1 · CBU: \2 · Titular: \3", _rt)
    _rt = re.sub(
        r"(?i)para ahorrar tiempo(?: en tu consulta)? pod[eé]s completar tu ficha m[eé]dica aqu[ií]:\s*",
        "Tu ficha médica (2 min): ", _rt)
    _rt = re.sub(
        r"(?i)cuando termines,? avisame(?: para corroborar los datos)?\.?",
        "Avisame cuando la completes 😊", _rt)
    _low = _rt.lower()
    _has_anamnesis = (
        ("anamnesis" in _low or "ficha médica" in _low or "ficha medica" in _low)
        and "http" in _low
    )
    _has_sena = bool(re.search(r"se[ñn]a", _rt, re.I)) and bool(re.search(r"alias|cbu", _rt, re.I))
    if not (_has_anamnesis or _has_sena):
        return _rt
    _paras = [p.strip() for p in re.split(r"\n\s*\n", _rt) if p.strip()]
    _filler = re.compile(
        r"(?i)^\s*(?:si quer[eé]s[,]?\s+despu[eé]s te ayudo"
        r"|cualquier (?:otra )?(?:duda|consulta)[,.]?\s+(?:me\s+)?avisa"
        r"|ante cualquier (?:otra )?(?:duda|consulta)"
        r"|quedo a (?:tu )?disposici[oó]n)"
    )
    _paras = [p for p in _paras if not _filler.search(p)]
    _seen_confirm = False
    _kept = []
    for _p in _paras:
        _is_confirm = bool(
            re.search(
                r"(?i)(?:turno.*(?:confirm|reserv)|qued[oó].*(?:confirmad|reservad)|ya ten[eé]s tu turno)",
                _p,
            )
        )
        if _is_confirm and _seen_confirm:
            continue
        if _is_confirm:
            _seen_confirm = True
        _kept.append(_p)
    _paras = _kept

    def _is_opt(_p):
        _pl = _p.lower()
        return (
            "alias" in _pl or "cbu" in _pl or bool(re.search(r"se[ñn]a", _pl))
            or "ficha médica" in _pl or "ficha medica" in _pl or "anamnesis" in _pl
        )

    _first_opt = next((i for i, _p in enumerate(_paras) if _is_opt(_p)), None)
    if _first_opt is not None and _first_opt > 0:
        _conf = "\n".join(_paras[:_first_opt]).strip()
        _opt = "\n".join(_paras[_first_opt:]).strip()
        _new = (_conf + "\n\n" + _opt) if (_conf and _opt) else (_conf or _opt)
    else:
        _new = "\n\n".join(_paras).strip()
    return _new if _new else _rt


def _globitos(text):
    """Los globitos que salen (ResponseSender parte por \\n\\n en el flujo del agente)."""
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


# La avalancha REAL de María (un solo turno de cierre, como lo arma el modelo)
MARIA_FLOOD = (
    "Listo, quedó confirmado tu turno para el viernes 31/07 a las 11:30 hs 😊\n"
    "Con la Dra. Elizabeth, en consultorios Santa Monica — Salta 147, 1er piso, consul 9.\n"
    "Maps: https://maps.app.goo.gl/iQHbGYWSRPypzDEw5\n\n"
    "Si querés, podés adelantar una seña de $25.000 por transferencia:\n"
    "Alias: dradelgadoml | CBU: 0970099455003515270012 | Titular: Delgado Maria Laura\n\n"
    "Para ahorrar tiempo en tu consulta podés completar tu ficha médica aquí: "
    "https://app.dralauradelgado.com/anamnesis/1/be493afa\n"
    "Cuando termines avisame para corroborar los datos.\n\n"
    "Ya tenés tu turno confirmado para el viernes 31/07 a las 11:30 hs 😊\n\n"
    "Si querés, después te ayudo con cualquier otra duda."
)

CASOS = [
    (
        "María: cierre de 5 globitos → 2 (sin relleno ni re-confirmación)",
        MARIA_FLOOD,
        lambda out: (
            len(_globitos(out)) == 2
            and "Alias: dradelgadoml" in out            # la seña sobrevive
            and "anamnesis/1/" in out                    # el link sobrevive
            and out.count("confirmado") == 1             # una sola confirmación
            and "después te ayudo" not in out            # relleno fuera
        ),
    ),
    (
        "Habitual: solo confirmación + ficha (sin seña) → 2 globitos, nada perdido",
        "¡Listo, Marta! Tu turno quedó confirmado para el lunes 20/07 a las 10:00 hs con la Dra. Laura.\n\n"
        "Para ahorrar tiempo completá tu ficha médica aquí: https://app.dralauradelgado.com/anamnesis/1/abc\n"
        "Cuando termines avisame.",
        lambda out: len(_globitos(out)) == 2 and "anamnesis/1/abc" in out and "confirmado" in out,
    ),
    (
        "NO es cierre (charla normal) → el candado NO toca nada",
        "Te paso opciones:\n1️⃣ Lunes 20/07 — 10:00 hs\n\n2️⃣ Martes 21/07 — 11:15 hs\n\n¿Cuál te queda mejor?",
        lambda out: out == "Te paso opciones:\n1️⃣ Lunes 20/07 — 10:00 hs\n\n2️⃣ Martes 21/07 — 11:15 hs\n\n¿Cuál te queda mejor?",
    ),
    (
        "Cierre con seña pero SIN ficha (anamnesis ya completa) → confirmación | seña",
        "¡Listo! Tu turno quedó confirmado para el martes 22/07 a las 13:00 hs.\n\n"
        "Si querés, podés adelantar una seña de $25.000: Alias: dradelgadoml\n\n"
        "Ya tenés tu turno confirmado 😊",
        lambda out: len(_globitos(out)) == 2 and "Alias: dradelgadoml" in out and out.count("confirmado") == 1,
    ),
    (
        "Lucas (real 2026-07-20): el cierre largo se COMPRIME (~40% menos) sin perder nada",
        "Listo, quedó tu evaluación para limpieza dental el miércoles 29/07 a las 10:45 😊\n"
        "Consultorios Santa Monica — Salta 147, 1er piso, consultorio 9\n"
        "Maps: https://maps.app.goo.gl/iQHbGYWSRPypzDEw5\n\n"
        "Si querés, podés adelantar una seña de $25.000 por transferencia:\n"
        "Alias: dradelgadoml\n"
        "CBU: 0970099455003515270012\n"
        "Titular: Delgado Maria Laura\n"
        "Para ahorrar tiempo en tu consulta podés completar tu ficha médica aquí: https://x.host/anamnesis/1/abc\n"
        "Cuando termines avisame para corroborar los datos.",
        lambda out: (
            len(_globitos(out)) == 2
            and "Seña opcional para asegurarlo: $25.000" in out
            and "Alias: dradelgadoml · CBU: 0970099455003515270012 · Titular: Delgado Maria Laura" in out
            and "Tu ficha médica (2 min):" in out
            and "Avisame cuando la completes 😊" in out
            and "por transferencia" not in out
            and "corroborar" not in out
        ),
    ),
]


def main() -> int:
    fallas = 0
    for nombre, entrada, check in CASOS:
        out = candado_cierre(entrada)
        n = len(_globitos(out))
        ok = check(out)
        print(f"{'✅ PASA ' if ok else '❌ FALLA'} — {nombre}  ({n} globito/s)")
        if not ok:
            fallas += 1
            print(f"     salida:\n{out}\n")
    print()
    if fallas:
        print(f"RESULTADO: {fallas}/{len(CASOS)} FALLARON")
        return 1
    print(f"RESULTADO: {len(CASOS)}/{len(CASOS)} PASAN — cierre en 2 globitos, sin saturar (costo: $0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
