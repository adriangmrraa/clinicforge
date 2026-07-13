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

# Contexto por-caso (lo setea run.py antes de cada turno). Permite que un caso
# fuerce "sin disponibilidad cercana" (avail_days) para reproducir el caso Mirta
# sin depender de una obra social con demora.
_CTX: dict = {}


def set_context(ctx) -> None:
    global _CTX
    _CTX = ctx or {}


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
        # Override por-caso: fuerza que el turno mas cercano este a +N dias
        # (caso Mirta: agenda llena, sin OS). Gana el mayor entre demora OS y override.
        override = _CTX.get("avail_days")
        if override is not None:
            try:
                delay = max(delay, int(override))
            except (TypeError, ValueError):
                pass
        s1, s2 = _slots(delay)
        note = ""
        if cfg and cfg["mode"] == "delayed":
            first_ok = date.today() + timedelta(days=cfg["delay_days"])
            note = (
                f"SYSTEM_NOTE: disponibilidad para {canon} a partir del "
                f"{first_ok.strftime('%d/%m')}.\n"
            )
        elif delay >= 5:
            # Sin OS pero agenda sin cupos cercanos: avisar el turno mas cercano real
            note = (
                f"SYSTEM_NOTE: el turno mas cercano disponible es {_fmt(s1)} "
                f"(a +{delay} dias de hoy).\n"
            )
        return (
            note
            + "DISPONIBLE:\n"
            + f"1) {_fmt(s1)} — 10:00 hs\n"
            + f"2) {_fmt(s2)} — 11:15 hs"
        )

    if name == "confirm_slot":
        return f"RESERVADO 30 min: {args.get('slot_datetime', '')}."

    if name == "book_appointment":
        # Simular el bug offer!=bookable (caso Graciela): la reserva falla con
        # UNAVAILABLE aunque check_availability haya ofrecido el slot.
        _bf = _CTX.get("book_fails")
        if _bf == "escalate":
            # 2º "se ocupó" seguido: el book_appointment REAL devuelve el mensaje
            # de ESCALACIÓN del cortacircuito determinista. Testea que el bot
            # derive ante ese mensaje explícito.
            return (
                "[BOOK_ERROR:UNAVAILABLE:RECOVERABLE] LOOP DE AGENDA DETECTADO: es el 2º "
                "horario que el paciente eligió y no se pudo confirmar. NO re-ofrezcas otra vez. "
                "[ACTION:DERIVÁ YA: llamá derivhumano (motivo 'No se pudo confirmar el turno por "
                "conflicto de agenda — reservar manualmente') y respondé UNA sola vez, cálido y sin "
                "caritas: 'Te lo estamos reservando y el equipo te lo confirma a la brevedad'. "
                "PROHIBIDO volver a ofrecer horarios.]"
            )
        if _bf:
            return (
                "[BOOK_ERROR:UNAVAILABLE:RECOVERABLE] Ese horario se ocupó recién. "
                "Ofrecé otros horarios cercanos una vez."
            )
        return (
            "TURNO CONFIRMADO: "
            f"{args.get('slot_datetime', '')} — {args.get('treatment_code', 'consulta')}. "
            "Sede Córdoba, Av. Ejemplo 123."
        )

    if name == "check_insurance_coverage":
        # SOLO DATOS — sin dictar frases: el prompt ya sabe qué decir con esto.
        canon, cfg = _match_insurance(args.get("provider_name", ""))
        if not cfg:
            return json.dumps(
                {"cobertura": args.get("provider_name", ""), "convenio": False},
                ensure_ascii=False,
            )
        if cfg["status"] == "rejected":
            return json.dumps({"cobertura": canon, "convenio": False}, ensure_ascii=False)
        data = {"cobertura": canon, "convenio": True, "coseguro": cfg["copay"]}
        if cfg["mode"] == "delayed":
            first_ok = date.today() + timedelta(days=cfg["delay_days"])
            data["turnos_desde"] = first_ok.strftime("%d/%m/%Y")
        return json.dumps(data, ensure_ascii=False)

    if name == "triage_urgency":
        # SOLO el nivel — la conducta ante cada nivel la define el prompt.
        text = (args.get("symptoms") or "").lower()
        hard = any(k in text for k in ["sangr", "hincha", "inflam", "no puedo comer", "golpe", "se me cay", "fiebre"])
        pain = any(k in text for k in ["dolor", "duele", "molestia"])
        if hard or (pain and any(k in text for k in ["mucho", "muchísimo", "fuerte", "no dorm", "insoport"])):
            return "NIVEL: EMERGENCY"
        if pain:
            return "NIVEL: HIGH"
        return "NIVEL: NORMAL"

    if name == "derivhumano":
        return "OK — equipo notificado por email."

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
