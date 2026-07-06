"""Juez del banco de pruebas: evalúa una respuesta contra lo esperado.

Combina dos capas:
  1. Chequeos deterministas (baratos, exactos): `prohibido` (subcadenas que NO
     deben aparecer) y `requiere` (subcadenas que SÍ deben aparecer).
  2. Juez IA: para cada criterio en `espera` (lenguaje natural), otro modelo
     dictamina PASA/FALLA con una razón corta. Se usa un modelo fuerte e
     independiente del que está bajo prueba, para que el juicio sea confiable.
"""
from __future__ import annotations

import json
from typing import Any


_JUDGE_SYSTEM = """Sos un evaluador de un asistente de WhatsApp de una clínica dental (agente "Paula", del equipo de "Clínica Dra. Laura Delgado", habla en español rioplatense con voseo).
Te doy: el contexto previo y el mensaje del paciente, la respuesta del asistente, y una lista de CRITERIOS.
Para CADA criterio, decidí si la respuesta lo cumple (PASA) o no (FALLA), con una razón corta.

REGLAS DE INTERPRETACIÓN (respetalas para NO marcar falsos errores):
- Que el asistente diga su identidad o el nombre de la clínica ("Soy Paula, del equipo de Clínica Dra. Laura Delgado") NO es "nombrar a un profesional". Solo contá como nombrar profesional si OFRECE agendar CON una persona concreta o le pide al paciente que ELIJA profesional.
- Voseo rioplatense incluye "tenés, querés, contás, atendés, pasame, atenderías, agendás". "Contás" y "atenderías" SON voseo correcto, NO tuteo. Solo es tuteo (incorrecto) si usa "tú / tienes / quieres / puedes / contigo".
- Preguntar la cobertura ("¿tenés obra social o te atendés de forma particular?") ANTES de dar precios u ofrecer turnos es el comportamiento CORRECTO y CUENTA como "avanzar hacia el turno".
- Si la respuesta es "[SILENCIO]", significa que el asistente decidió no responder (comportamiento válido ante un simple agradecimiento).

Sé literal con el resto: si el criterio dice "no debe X" y la respuesta hace X, FALLA.
Respondé SOLO con JSON válido, sin texto extra:
{"resultados": [{"criterio": "<texto del criterio>", "pasa": true/false, "razon": "<motivo en 1 frase corta>"}]}"""


def _hard_checks(case: dict, response_text: str) -> list[dict[str, Any]]:
    """Chequeos deterministas de subcadenas (case-insensitive)."""
    out: list[dict[str, Any]] = []
    low = (response_text or "").lower()
    for bad in case.get("prohibido", []) or []:
        present = bad.lower() in low
        out.append(
            {
                "criterio": f"[deterministic] NO debe contener: «{bad}»",
                "pasa": not present,
                "razon": "aparece en la respuesta" if present else "ok, no aparece",
            }
        )
    for req in case.get("requiere", []) or []:
        present = req.lower() in low
        out.append(
            {
                "criterio": f"[deterministic] DEBE contener: «{req}»",
                "pasa": present,
                "razon": "ok, aparece" if present else "falta en la respuesta",
            }
        )
    return out


async def judge_case(
    client, judge_model: str, case: dict, response_text: str
) -> dict[str, Any]:
    """Devuelve {pasa: bool, criterios: [...], error: str|None}."""
    criterios: list[dict[str, Any]] = _hard_checks(case, response_text)

    espera = case.get("espera", []) or []
    judge_error = None
    if espera:
        user_payload = json.dumps(
            {
                "contexto_previo": case.get("patient_context", "") or "",
                "historial": case.get("history", []) or [],
                "mensaje_paciente": case.get("user", ""),
                "respuesta_asistente": response_text or "",
                "criterios": espera,
            },
            ensure_ascii=False,
        )
        try:
            resp = await client.chat.completions.create(
                model=judge_model,
                messages=[
                    {"role": "system", "content": _JUDGE_SYSTEM},
                    {"role": "user", "content": user_payload},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content or "{}"
            parsed = json.loads(raw)
            for item in parsed.get("resultados", []):
                criterios.append(
                    {
                        "criterio": item.get("criterio", "?"),
                        "pasa": bool(item.get("pasa")),
                        "razon": item.get("razon", ""),
                    }
                )
        except Exception as e:  # el juez falló → marcamos el caso como indeterminado
            judge_error = str(e)
            for c in espera:
                criterios.append(
                    {
                        "criterio": c,
                        "pasa": False,
                        "razon": f"juez no disponible: {e}",
                    }
                )

    pasa = all(c["pasa"] for c in criterios) if criterios else True
    return {"pasa": pasa, "criterios": criterios, "error": judge_error}
