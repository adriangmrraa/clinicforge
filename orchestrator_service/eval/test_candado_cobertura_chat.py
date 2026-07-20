# -*- coding: utf-8 -*-
"""Test LOCAL y GRATIS de 2 candados del análisis del banco completo (2026-07-18):
  1) COBERTURA-CHAT: si el paciente nombró su OS o dijo 'particular' EN el mensaje,
     la pregunta canónica de cobertura no puede volver a salir (caso Sancor).
  2) REINTEGRO: atención particular por OS sin convenio (ISSN/Swiss/etc.) SIEMPRE
     menciona el comprobante para reintegro (falló x3 en el banco). Aditivo.

SYNC: replica la lógica de buffer_task.py. Si se cambia allá, actualizar acá.

Uso:  python orchestrator_service/eval/test_candado_cobertura_chat.py
"""
import re
import sys


def candado_cobertura_chat(response_text: str, last_user_msg: str) -> str:
    if not (response_text and re.search(r"cont[aá]s con alguna obra social", response_text, re.I)):
        return response_text
    _last = (last_user_msg or "").lower()
    _named = "particular" in _last or bool(
        re.search(
            r"\b(osde|sancor|swiss|galeno|ioma|issn|osdepym|sosunc|osseg|jer[aá]rquicos|medif[eé]|omint|luis pasteur|prevenci[oó]n)\b",
            _last,
        )
    ) or bool(re.search(r"\b(tengo|con|soy de)\s+(la\s+)?(obra social|prepaga)\b", _last))
    if _named:
        response_text = re.sub(r"(?im)^.*cont[aá]s con alguna obra social.*$\n?", "", response_text).strip()
        response_text = re.sub(r"\n{3,}", "\n\n", response_text).strip()
        if not response_text:
            response_text = "Contame qué necesitás y te lo coordino 😊"
    return response_text


def candado_reintegro(response_text: str, patient_context: str, last_user_msg: str) -> str:
    _ctx_low = (patient_context or "").lower()
    _dispara = bool(response_text) and not re.search(r"(?i)comprobante|recibo|reintegro", response_text or "") and (
        bool(re.search(r"(?i)(ser[íi]a de forma particular|atenci[oó]n.*particular|consulta particular|es particular)", response_text or ""))
        or (bool(re.search(r"\bissn\b", _ctx_low)) and bool(re.search(r"(?i)tiene un valor", response_text or "")))
    )
    if not _dispara:
        return response_text
    _ctx = _ctx_low
    _last = (last_user_msg or "").lower()
    _os_context = (
        bool(re.search(r"\bissn\b", _ctx)) or "instituto de seguridad" in _ctx
        or bool(re.search(r"\b(swiss|sancor|prevenci[oó]n|no trabajamos)\b", (response_text or "").lower()))
        or bool(re.search(r"\b(issn|swiss|prevenci[oó]n)\b", _last))
    )
    if _os_context:
        response_text = (
            response_text.rstrip()
            + "\nIgual te entregamos el comprobante para que puedas gestionar reintegro con tu cobertura, si te corresponde."
        )
    return response_text


CASOS = [
    (
        "SANCOR (caso real del banco): re-pregunta tras usar la OS → recortada",
        lambda: candado_cobertura_chat(
            "Sí, con Sancor la consulta sería de forma particular.\n1️⃣ Martes 21/07 — 10:00 hs\n2️⃣ Miércoles 22/07 — 11:15 hs\n\n¿Contás con alguna obra social o te atenderías de forma particular?",
            "Hola, tengo Sancor y quiero hacerme una extracción de muela",
        ),
        lambda out: "obra social o te atender" not in out.lower() and "1️⃣" in out and "Sancor" in out,
    ),
    (
        "Dijo 'particular' → la re-pregunta se recorta",
        lambda: candado_cobertura_chat(
            "Perfecto.\n¿Contás con alguna obra social o te atenderías de forma particular?",
            "buenisimo, particular",
        ),
        lambda out: "obra social" not in out.lower(),
    ),
    (
        "NO nombró cobertura → la pregunta SOBREVIVE (flujo correcto para nuevos)",
        lambda: candado_cobertura_chat(
            "¡Hola! ¿Contás con alguna obra social o te atenderías de forma particular?",
            "hola quiero un turno",
        ),
        lambda out: "obra social" in out.lower(),
    ),
    (
        "SWISS sin convenio y sin mención de comprobante → se agrega la línea de reintegro",
        lambda: candado_reintegro(
            "Para Swiss Medical no trabajamos con convenio directo, así que la atención sería de forma particular.",
            "",
            "turno para mi mamá, tiene Swiss Medical",
        ),
        lambda out: "comprobante" in out.lower() and "reintegro" in out.lower(),
    ),
    (
        "ISSN + consulta particular sin reintegro → se agrega",
        lambda: candado_reintegro(
            "Con la clínica cualquier tratamiento es particular. Si querés te oriento con una consulta particular en el consultorio.",
            "⛔ ISSN (respondé VOS...): la cirugía se coordina con CIMO",
            "¿a ese número coordino la cirugía?",
        ),
        lambda out: "comprobante" in out.lower(),
    ),
    (
        "Ya menciona el comprobante → NO duplica",
        lambda: candado_reintegro(
            "La atención sería particular. Igual te damos el comprobante para gestionar reintegro.",
            "",
            "tengo swiss",
        ),
        lambda out: out.lower().count("comprobante") == 1,
    ),
    (
        "'Particular' sin contexto de OS rechazada (particular común) → NO se agrega nada",
        lambda: candado_reintegro(
            "La consulta particular tiene un valor de $60.000.",
            "",
            "cuanto sale particular?",
        ),
        lambda out: "comprobante" not in out.lower(),
    ),
    (
        "ISSN + VALOR sin la palabra 'particular' (fallo issn-precio) → se agrega el comprobante",
        lambda: candado_reintegro(
            "La consulta de evaluación tiene un valor de $60.000. Ahí la doctora evalúa tu caso.",
            "⛔ ISSN (respondé VOS...): con la clínica cualquier tratamiento ISSN es particular",
            "Ah, ¿y cuánto sale la consulta?",
        ),
        lambda out: "comprobante" in out.lower() and "reintegro" in out.lower(),
    ),
]


def main() -> int:
    fallas = 0
    for nombre, fn, check in CASOS:
        out = fn()
        ok = check(out)
        print(f"{'✅ PASA ' if ok else '❌ FALLA'} — {nombre}")
        if not ok:
            fallas += 1
            print(f"     salida: {out!r}")
    print()
    if fallas:
        print(f"RESULTADO: {fallas}/{len(CASOS)} FALLARON")
        return 1
    print(f"RESULTADO: {len(CASOS)}/{len(CASOS)} PASAN — cobertura-chat + reintegro garantizados (costo: $0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
