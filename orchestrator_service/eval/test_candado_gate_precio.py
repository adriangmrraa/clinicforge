# -*- coding: utf-8 -*-
"""Test LOCAL y GRATIS del candado GATE-PRECIO (enforcement determinista del A1).

Regla de negocio: NUNCA dar el valor PARTICULAR de la consulta si la cobertura no
está resuelta (ni Particular ni OS conocida), o si el paciente nombró una OS CON
convenio (ej. Sancor). El gate A1 lo pide por texto y el mini lo saltea a veces;
este candado lo garantiza por código.

Excepciones (el valor SÍ sale): pidió EXPLÍCITAMENTE atenderse particular (intención,
no la palabra suelta), tratamiento ESTÉTICO (siempre particular), u OS FUERA de panel
(Swiss/IOMA/OSDEPYM/Omint/Luis Pasteur/Prevención/ISSN → es particular, lo encuadra
el candado REINTEGRO). OS CON convenio → recorta el valor y anexa la línea de coseguro
sin cifra, sin re-preguntar.

SYNC: replica la lógica de buffer_task.py (gate-precio + _dijo_particular). Si se
cambia allá, actualizar acá.

Uso:  python orchestrator_service/eval/test_candado_gate_precio.py
"""
import re
import sys


def _dijo_particular(text: str) -> bool:
    """Espejo de buffer_task._dijo_particular: intención de auto-pago, no el substring."""
    t = (text or "").lower()
    if re.search(r"\bsin\s+(?:obra\s+social|cobertura|prepaga)\b|\bno\s+tengo\s+(?:obra\s+social|cobertura|prepaga)\b", t):
        return True
    for mt in re.finditer(r"\bparticular\b", t):
        pre = t[max(0, mt.start() - 24):mt.start()]
        post = t[mt.end():mt.end() + 6]
        if re.search(r"\ben\s+$", pre):
            continue
        if re.search(r"\b(algo|nada|cosa|caso|dolor|molestia|muela|diente|tema|situaci[oó]n|"
                     r"detalle|pregunta|duda|zona|parte|problema)\s+$", pre):
            continue
        if re.search(r"\b(es|sea|ser[aá]|ser[ií]a)\s+$", pre):
            continue
        if re.search(r"^\s*o\b", post):
            continue
        return True
    return False


def candado_gate_precio(response_text: str, patient_context: str, last_user_msg: str) -> str:
    """Espejo del candado gate-precio de buffer_task.py (con fix P2 + audit 2026-07-22)."""
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
    _pidio_particular = _dijo_particular(_last)
    _estetico = any(k in _last for k in ("carilla", "blanqueamiento", "diseño de sonrisa", "estetic", "estétic"))
    _os_en_msg = bool(
        re.search(
            r"\b(osde|sancor|swiss|galeno|ioma|issn|osdepym|sosunc|osseg|jer[aá]rquicos|medif[eé]|omint|luis pasteur|prevenci[oó]n|apsot|mca|am[eé]rica|bancarios|siaco|credi.?gu[ií]a|federada|medicus|poder judicial)\b",
            _last,
        )
    )
    _os_fuera_panel = bool(
        re.search(r"\b(swiss(?:\s+medical)?|ioma|osdepym|omint|luis pasteur|prevenci[oó]n|issn|instituto de seguridad)\b", _last)
    )
    _os_convenio = _os_en_msg and not _os_fuera_panel
    if (_minor or not _cov_resuelta or _os_convenio) and not _pidio_particular and not _estetico and not _os_fuera_panel:
        response_text = re.sub(
            r"(?is)la consulta de evaluaci[oó]n tiene un valor.*?presupuesto correspondiente\.?",
            "", response_text,
        ).strip()
        response_text = re.sub(r"\n{3,}", "\n\n", response_text).strip()
        if _os_convenio:
            if re.search(r"(?i)tiene un valor", response_text):
                response_text = re.sub(r"(?im)^.*\btiene un valor\b.*$\n?", "", response_text).strip()
                response_text = re.sub(r"\n{3,}", "\n\n", response_text).strip()
            response_text = re.sub(r"(?im)^.*(?:reintegro|comprobante).*$\n?", "", response_text).strip()
            response_text = re.sub(r"(?im)^.*\b(?:es|ser[ií]a|de forma|forma)\s+particular\b.*$\n?", "", response_text).strip()
            response_text = re.sub(r"\n{3,}", "\n\n", response_text).strip()
            if not re.search(r"(?i)va con tu obra social|seg[uú]n tu plan|coseguro", response_text):
                coseg = (
                    "La consulta de evaluación va con tu obra social 😊 Si corresponde algún "
                    "coseguro, se evalúa según tu plan y se confirma en la clínica el día del turno. "
                    "¿Te paso opciones de turno?"
                )
                response_text = (response_text.rstrip() + "\n" + coseg).strip() if response_text.strip() else coseg
        elif "obra social" not in response_text.lower():
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
        "",
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
    (
        "SANCOR (CON convenio) nombrada → el valor NO sale (recortado) y NO re-pregunta cobertura",
        "Con Sancor la consulta sería de forma particular. " + PARRAFO + "\n1️⃣ Miércoles 22/07 — 10:00 hs",
        "",
        "Hola, tengo Sancor y quiero hacerme una extracción de muela",
        lambda out: "$60.000" not in out and "contás con alguna obra social" not in out.lower()
        and ("coseguro" in out.lower() or "va con tu obra social" in out.lower()),
    ),
    (
        "ISSN (FUERA de panel = particular): el valor SÍ sale (lo encuadra REINTEGRO), sin línea de convenio",
        PARRAFO,
        "• Obra Social registrada: ISSN",
        "hola tengo ISSN, ¿cuánto sale la consulta?",
        lambda out: "$60.000" in out and "va con tu obra social" not in out.lower(),
    ),
    (
        "SANCOR interrogativo '¿es particular?' NO apaga el gate → el valor se recorta",
        PARRAFO,
        "",
        "tengo Sancor, la consulta es particular o me la cubre la obra social? cuánto sale?",
        lambda out: "$60.000" not in out,
    ),
    (
        "SANCOR + pidió EXPLÍCITO particular → el valor SÍ sale (eligió particular)",
        PARRAFO,
        "",
        "tengo Sancor pero quiero atenderme particular, ¿cuánto sale?",
        lambda out: "$60.000" in out,
    ),
    (
        "SANCOR forma-corta '$60.000' → recorte por LÍNEA, sin dejar basura '000' (separador de miles)",
        "Con Sancor la consulta tiene un valor de $60.000, pero podés verlo con tu obra social.",
        "",
        "tengo Sancor, ¿cuánto sale la consulta?",
        lambda out: "$60.000" not in out and "000," not in out and not out.strip().startswith("000"),
    ),
]


def main() -> int:
    fallas = 0
    for nombre, resp, ctx, last, check in CASOS:
        out = candado_gate_precio(resp, ctx, last)
        ok = check(out)
        print(f"{'OK   ' if ok else 'FALLA'} — {nombre}")
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
