# -*- coding: utf-8 -*-
"""Test LOCAL y GRATIS de los candados del 'radar del turno agendado'
(2 casos de PROD 2026-07-20: Matías Castillo y Gisela López).

  1) POST-BOOKING: con PRÓXIMO TURNO en contexto y sin pedido de turno nuevo,
     la oferta "te paso turnos" se recorta (caso Gisela).
  2) RESERVA-FANTASMA: "se venció la reserva temporal" sin confirm_slot en el
     turno ni estado de slots del bot → se reemplaza (caso Matías).

SYNC: replica la lógica de buffer_task.py. Si se cambia allá, actualizar acá.

Uso:  python orchestrator_service/eval/test_candado_radar_turno.py
"""
import re
import sys


# SYNC con buffer_task.py: frases que "ofrecen turno" (clásicas + CTA del guion de precio).
_PB_OFFER = (
    r"te paso (?:turnos|opciones|las opciones|disponibilidad)"
    r"|quer[eé]s que te pase turnos"
    r"|te ayudo a coordinar(?:te)? (?:un turno|una consulta|una evaluaci[oó]n|una cita|el turno)"
    r"|coordin(?:amos|emos) (?:un turno|una consulta|una evaluaci[oó]n|una cita)"
)


def candado_post_booking(response_text: str, patient_context: str, last_user_msg: str) -> str:
    if not (
        response_text
        and patient_context
        and "PRÓXIMO TURNO" in patient_context
        and re.search(r"(?i)" + _PB_OFFER, response_text)
    ):
        return response_text
    _last = (last_user_msg or "").lower()
    _pidio = bool(re.search(r"(?i)(otro turno|un turno|sacar turno|nuevo turno|agendar|reprogram|cambiar (?:el |mi )?turno|cita para)", _last))
    if _pidio:
        return response_text
    response_text = re.sub(
        r"(?im)^.*(?:" + _PB_OFFER + r").*$\n?",
        "", response_text,
    ).strip()
    response_text = re.sub(r"\n{3,}", "\n\n", response_text).strip()
    return response_text if response_text else "Cualquier duda con tu turno, avisame 😊"


def candado_reserva_fantasma(response_text: str, tools: list, prev_state: str) -> str:
    if not (response_text and re.search(r"(?i)se venci[oó] la reserva|reserva temporal", response_text)):
        return response_text
    if "confirm_slot" in (tools or []) or (prev_state or "") in ("SLOT_LOCKED", "OFFERED_SLOTS"):
        return response_text
    response_text = re.sub(
        r"(?im)^.*(?:se venci[oó] la reserva|reserva temporal).*$\n?",
        "Dame un segundo que reviso tu agenda 😊",
        response_text, count=1,
    ).strip()
    response_text = re.sub(r"(?im)^.*(?:se venci[oó] la reserva|reserva temporal).*$\n?", "", response_text).strip()
    return re.sub(r"\n{3,}", "\n\n", response_text).strip()


def es_hilo_humano(role: str, platform_metadata_text: str) -> bool:
    """Espejo de la detección de HILO HUMANO RECIENTE en buffer_task (caso Matías):
    el último saliente lo escribió una persona si vino de la plataforma
    (human_supervisor) o del celular del consultorio (echo whatsapp_business_app)."""
    return role == "human_supervisor" or "whatsapp_business_app" in (platform_metadata_text or "")


CTX_CON_TURNO = (
    "• Nombre: Gisela Lopez\n"
    "• Obra Social registrada: OSDE\n"
    "• PRÓXIMO TURNO: Tiene un turno de Consulta General con la Dra. Laura el lunes 20/07 a las 14:00."
)

CASOS = [
    (
        "GISELA (real): pregunta cobertura con turno confirmado → la oferta de turnos se recorta",
        lambda: candado_post_booking(
            "Sí, trabajamos con OSDE 😊\nLa consulta podría llegar a tener un coseguro, que se abona el mismo día del turno.\nSi querés, te paso turnos para la evaluación.",
            CTX_CON_TURNO,
            "Consulta, cubre osde cierto? No debo abonar algo adicional",
        ),
        lambda out: "te paso turnos" not in out.lower() and "OSDE" in out and "coseguro" in out,
    ),
    (
        "PRECIO con turno: 'te ayudo a coordinar un turno de evaluación' se recorta (caso prod 24/07)",
        lambda: candado_post_booking(
            "El valor de la consulta es $60.000.\nTe ayudo a coordinar un turno de evaluación.",
            CTX_CON_TURNO,
            "cuanto sale la consulta?",
        ),
        lambda out: "coordinar un turno" not in out.lower() and "60.000" in out,
    ),
    (
        "PRECIO con turno pero PIDE otro turno → la oferta de coordinar SOBREVIVE (legítima)",
        lambda: candado_post_booking(
            "El valor es $60.000.\nTe ayudo a coordinar un turno de evaluación.",
            CTX_CON_TURNO,
            "quiero sacar otro turno para una evaluación",
        ),
        lambda out: "coordinar un turno" in out.lower(),
    ),
    (
        "Con turno PERO pide OTRO turno explícito → la oferta SOBREVIVE (legítima)",
        lambda: candado_post_booking(
            "¡Dale! Te paso opciones para el nuevo turno 📅",
            CTX_CON_TURNO,
            "quiero sacar otro turno para mi señora",
        ),
        lambda out: "opciones" in out.lower(),
    ),
    (
        "SIN próximo turno en contexto → no se toca (flujo normal de nuevos)",
        lambda: candado_post_booking(
            "Si querés, te paso turnos disponibles 📅",
            "Nuevo lead. Sin cobertura indicada.",
            "hola, info de implantes",
        ),
        lambda out: "te paso turnos" in out.lower(),
    ),
    (
        "MATÍAS (real): 'se venció la reserva temporal' sin slot-lock → reemplazada",
        lambda: candado_reserva_fantasma(
            "Aguantá un segundo, Matías. Se venció la reserva temporal de ese turno 🙏\nTe busco de nuevo la disponibilidad para el jueves y te paso opciones enseguida.",
            ["list_my_appointments"],
            "IDLE",
        ),
        lambda out: "reserva" not in out.lower() and "reviso tu agenda" in out,
    ),
    (
        "Reserva vencida REAL (hubo confirm_slot) → el mensaje SOBREVIVE (es correcto)",
        lambda: candado_reserva_fantasma(
            "Se venció la reserva temporal de ese horario, te busco opciones de nuevo 🙏",
            ["confirm_slot"],
            "SLOT_LOCKED",
        ),
        lambda out: "reserva" in out.lower(),
    ),
    (
        "Estado OFFERED_SLOTS previo (slots del bot vivos) → sobrevive",
        lambda: candado_reserva_fantasma(
            "Uy, se venció la reserva temporal 🙏 Te paso horarios de nuevo.",
            [],
            "OFFERED_SLOTS",
        ),
        lambda out: "reserva" in out.lower(),
    ),
    (
        "HILO HUMANO: secretaria por plataforma (human_supervisor) → detectado",
        lambda: es_hilo_humano("human_supervisor", None),
        lambda out: out is True,
    ),
    (
        "HILO HUMANO: secretaria por celular (echo whatsapp_business_app) → detectado",
        lambda: es_hilo_humano("assistant", '{"source": "whatsapp_business_app"}'),
        lambda out: out is True,
    ),
    (
        "Mensaje normal del BOT → NO es hilo humano (no se inyecta nada)",
        lambda: es_hilo_humano("assistant", '{"delivery_status": "sent"}'),
        lambda out: out is False,
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
    print(f"RESULTADO: {len(CASOS)}/{len(CASOS)} PASAN — radar del turno agendado garantizado (costo: $0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
