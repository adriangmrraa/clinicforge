"""Herramientas SIMULADAS para el banco de pruebas (T1, 2026-07-12).

El banco corría al agente "desenchufado" (sin herramientas), así que ~8 casos
eran imposibles de aprobar por buenos que fuéramos: pedían mirar agenda,
semáforo de OS o confirmar turnos. Este módulo le da al examen una AGENDA DE
JUGUETE determinista: fechas fijas relativas a hoy, config de OS de mentira
(espejo de la real de la clínica) y confirmaciones canónicas.

SOLO se usa en eval/ (jamás se promueve a producción). Determinismo: nada de
random; las fechas derivan de date.today() para que el prompt (que inyecta la
fecha real) y las herramientas cuenten la misma historia.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Config de juguete (espejo de la clínica real — actualizar si cambia el panel)
# ---------------------------------------------------------------------------

INSURANCE_FIXTURE = {
    # nombre canónico -> config
    "OSDE": {"status": "restricted", "mode": "delayed", "delay_days": 30, "copay": 30000},
    "GALENO": {"status": "accepted", "mode": "delayed", "delay_days": 15, "copay": 30000},
    "IOMA": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "OSDEPYM": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "SOSUNC": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "OSSEG": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "SWISS MEDICAL": {"status": "rejected", "mode": "immediate", "delay_days": 0, "copay": None},
}

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _fmt(d: date) -> str:
    return f"{_DIAS[d.weekday()]} {d.strftime('%d/%m')}"


def _next_weekday(start: date) -> date:
    """Primer día hábil (lun-vie) desde start inclusive."""
    d = start
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _match_insurance(name: str) -> tuple[str, dict] | tuple[None, None]:
    raw = (name or "").strip().upper()
    if not raw:
        return None, None
    for canon, cfg in INSURANCE_FIXTURE.items():
        if canon in raw or raw in canon:
            return canon, cfg
    return None, None


# ---------------------------------------------------------------------------
# Schemas (nombres = los reales de DENTAL_TOOLS; args mínimos compatibles)
# ---------------------------------------------------------------------------

def tool_schemas() -> list[dict]:
    def f(name, desc, props, required):
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        }

    return [
        f(
            "check_availability",
            "Consulta disponibilidad real de turnos. Devuelve 2-3 opciones concretas.",
            {
                "treatment_code": {"type": "string", "description": "Código del tratamiento"},
                "interpreted_date": {"type": "string", "description": "YYYY-MM-DD o vacío"},
                "search_mode": {"type": "string", "enum": ["exact", "week", "month", "open"]},
                "insurance_provider": {"type": "string", "description": "Obra social del paciente si la mencionó (PASALA SIEMPRE)"},
            },
            ["treatment_code"],
        ),
        f(
            "confirm_slot",
            "Reserva blanda del horario elegido por 30 minutos antes de pedir datos.",
            {
                "slot_datetime": {"type": "string"},
                "treatment_code": {"type": "string"},
            },
            ["slot_datetime"],
        ),
        f(
            "book_appointment",
            "Registra el turno definitivo una vez confirmados los datos del paciente.",
            {
                "slot_datetime": {"type": "string"},
                "treatment_code": {"type": "string"},
                "patient_name": {"type": "string"},
                "patient_dni": {"type": "string"},
                "is_minor": {"type": "boolean"},
                "patient_phone": {"type": "string"},
            },
            ["slot_datetime"],
        ),
        f(
            "check_insurance_coverage",
            "Verifica cobertura/convenio de una obra social y su modalidad de turnos.",
            {"provider_name": {"type": "string"}},
            ["provider_name"],
        ),
        f(
            "triage_urgency",
            "Analiza la urgencia de los síntomas descriptos.",
            {"symptoms": {"type": "string"}},
            ["symptoms"],
        ),
        f(
            "derivhumano",
            "Deriva la conversación a un humano del equipo y silencia al bot 24h.",
            {"motivo": {"type": "string"}},
            ["motivo"],
        ),
        f(
            "list_my_appointments",
            "Lista los próximos turnos del paciente.",
            {},
            [],
        ),
    ]


# ---------------------------------------------------------------------------
# Ejecución simulada
# ---------------------------------------------------------------------------

def _slots(min_from_today: int) -> list[date]:
    base = _next_weekday(date.today() + timedelta(days=max(min_from_today, 2)))
    second = _next_weekday(base + timedelta(days=1))
    return [base, second]


def execute(name: str, args: dict) -> str:
    """Devuelve el resultado de juguete de una herramienta. Siempre string."""
    args = args or {}

    if name == "check_availability":
        canon, cfg = _match_insurance(args.get("insurance_provider", ""))
        delay = cfg["delay_days"] if (cfg and cfg["mode"] == "delayed") else 0
        wanted = (args.get("interpreted_date") or "").strip()
        note = ""
        if delay:
            first_ok = date.today() + timedelta(days=delay)
            note = (
                f"SYSTEM_NOTE: por la modalidad de {canon}, hay disponibilidad "
                f"a partir del {first_ok.strftime('%d/%m')}. "
            )
            if wanted:
                try:
                    w = date.fromisoformat(wanted)
                    if w < first_ok:
                        return (
                            note
                            + "No ofrecer fechas anteriores. Opciones válidas:\n"
                            + "\n".join(
                                f"{i+1}) {_fmt(s)} — {h} hs"
                                for i, (s, h) in enumerate(zip(_slots(delay), ["10:00", "11:15"]))
                            )
                        )
                except ValueError:
                    pass
        s1, s2 = _slots(delay)
        return (
            note
            + "OPCIONES DISPONIBLES (elegí y ofrecé máximo 2):\n"
            + f"1) {_fmt(s1)} — 10:00 hs\n"
            + f"2) {_fmt(s2)} — 11:15 hs\n"
            + "Sede: Córdoba (incluir dirección solo al confirmar)."
        )

    if name == "confirm_slot":
        return (
            f"RESERVADO por 30 minutos: {args.get('slot_datetime', '')}. "
            "Pedí ahora nombre completo y DNI para confirmar."
        )

    if name == "book_appointment":
        return (
            "TURNO CONFIRMADO ✔ "
            f"{args.get('slot_datetime', '')} — {args.get('treatment_code', 'consulta')}. "
            "Sede Córdoba, Av. Ejemplo 123. Seña: $30.000 por transferencia para sostener el turno."
        )

    if name == "check_insurance_coverage":
        canon, cfg = _match_insurance(args.get("provider_name", ""))
        if not cfg:
            return (
                "SIN CONVENIO DIRECTO con esa cobertura. La atención es particular "
                "($60.000 la consulta) y se entregan recibos para gestionar reintegro."
            )
        if cfg["status"] == "rejected":
            return (
                f"{canon}: SIN CONVENIO. Atención particular ($60.000) con recibo "
                "para reintegro si corresponde."
            )
        out = f"{canon}: CON CONVENIO. Coseguro: ${cfg['copay']:,}".replace(",", ".")
        if cfg["mode"] == "delayed":
            first_ok = date.today() + timedelta(days=cfg["delay_days"])
            out += (
                f". Modalidad: turnos a partir del {first_ok.strftime('%d/%m')} "
                f"(+{cfg['delay_days']} días). No ofrecer fechas anteriores ni "
                "atribuir la demora a la obra social."
            )
        else:
            out += ". Modalidad: turnos con disponibilidad normal."
        return out

    if name == "triage_urgency":
        text = (args.get("symptoms") or "").lower()
        hard = any(k in text for k in ["sangr", "hincha", "inflam", "no puedo comer", "golpe", "se me cay", "fiebre"])
        pain = any(k in text for k in ["dolor", "duele", "molestia"])
        if hard or (pain and any(k in text for k in ["mucho", "muchísimo", "fuerte", "no dorm", "insoport"])):
            return (
                "NIVEL: EMERGENCY. Acción: derivar YA con derivhumano(motivo) y "
                "contener; NO seguir ofreciendo turnos lejanos."
            )
        if pain:
            return "NIVEL: HIGH. Priorizar turno cercano y ofrecer derivación si pide inmediatez."
        return "NIVEL: NORMAL."

    if name == "derivhumano":
        return (
            "DERIVADO ✔ El equipo fue notificado por email con el motivo: "
            f"{args.get('motivo', '')}. Respondé con UNA frase de contención "
            "(ya avisamos al equipo, te contactan a la brevedad) y nada más."
        )

    if name == "list_my_appointments":
        prox = _next_weekday(date.today() + timedelta(days=3))
        return f"PRÓXIMO TURNO: {_fmt(prox)} 10:00 hs — Consulta. Sede Córdoba."

    return f"ERROR: herramienta desconocida {name}"


def execute_tool_call(tc) -> str:
    """Adapter para tool_calls del SDK de OpenAI."""
    try:
        parsed = json.loads(tc.function.arguments or "{}")
    except (json.JSONDecodeError, TypeError):
        parsed = {}
    return execute(tc.function.name, parsed)
