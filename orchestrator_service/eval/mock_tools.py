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

# ESPEJO REAL del panel de prod (sync 2026-07-20 — pegado por Carlos tras el import).
# 16 OS reales. Las que NO figuran (Swiss, IOMA, OSDEPYM, Omint...) son not_found →
# particular + comprobante/reintegro, igual que prod.
INSURANCE_FIXTURE = {
    "AMÉRICA SERVICIOS (MCA)": {"status": "accepted", "mode": "delayed", "delay_days": 15, "copay": 30000},
    "APSOT": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "BANCARIOS (SIACO)": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "CREDI-GUÍA": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "FEDERADA SALUD": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "GALENO": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "ISSN": {"status": "external_derivation", "mode": "immediate", "delay_days": 0, "copay": None},
    "JERÁRQUICOS SALUD": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "MEDICUS": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "MEDICUS ESPECIALISTAS": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "MEDIFÉ": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "OSDE": {"status": "restricted", "mode": "delayed", "delay_days": 5, "copay": 30000},
    "OSSEG": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "PODER JUDICIAL": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "SANCOR SALUD": {"status": "restricted", "mode": "immediate", "delay_days": 0, "copay": 30000},
    "SOSUNC": {"status": "accepted", "mode": "immediate", "delay_days": 0, "copay": 30000},
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


def fechas_futuras_two() -> list[str]:
    """Fechas %d/%m de los DOS turnos del modo mock 'two' (candado multi-turno).

    Misma lógica que list_my_appointments modo 'two' — si cambia allá, cambiar acá.
    """
    d1 = _next_weekday(date.today() + timedelta(days=3))
    d2 = _next_weekday(d1 + timedelta(days=1))
    return [d1.strftime("%d/%m"), d2.strftime("%d/%m")]


def _sin_tildes(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


_TOKENS_GENERICOS = {"SALUD", "SERVICIOS"}  # no identifican una OS por sí solos


def _match_insurance(name: str) -> tuple[str, dict] | tuple[None, None]:
    """Match por PALABRA COMPLETA (no substring: 'OSDEPYM' NO es 'OSDE')."""
    import re as _re

    raw = _sin_tildes((name or "").strip().upper())
    if not raw:
        return None, None

    def toks(s):
        return {t for t in _re.split(r"[^A-Z0-9]+", s) if len(t) >= 3 and t not in _TOKENS_GENERICOS}

    for canon, cfg in INSURANCE_FIXTURE.items():
        c = _sin_tildes(canon)
        if raw == c or _re.search(r"\b" + _re.escape(c) + r"\b", raw):
            return canon, cfg
    raw_toks = toks(raw)
    for canon, cfg in INSURANCE_FIXTURE.items():
        if raw_toks & toks(_sin_tildes(canon)):
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
        # GATE DE COBERTURA (espejo del real 2026-07-20, opt-in con "cov_gate" en el
        # caso): sin cobertura conocida, la PRIMERA búsqueda no devuelve horarios —
        # devuelve la orden de preguntar. Una sola vez (espejo del flag anti-loop).
        if _CTX.get("cov_gate") and not str(args.get("insurance_provider") or "").strip():
            _CTX["cov_gate"] = False
            return (
                "COBERTURA_DESCONOCIDA — NO ofrezcas horarios todavía (la agenda NO se consultó). "
                "Primero preguntá en UN solo mensaje: '¿Contás con alguna obra social o te "
                "atenderías de forma particular?' (si el turno es para OTRA persona, preguntá la "
                "cobertura de ESA persona). Cuando conteste: si nombra una obra social, verificala "
                "con check_insurance_coverage y volvé a llamar check_availability pasando "
                "insurance_provider con ese nombre; si dice particular, volvé a llamar "
                "check_availability con insurance_provider='particular'. ⛔ NO inventes fechas ni "
                "digas que no hay lugar: la agenda todavía no se miró."
            )
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
        # Espejo de la tool real: cada slot incluye el profesional (la real lo trae
        # de la BD; sin esto, el banco marcaba "no dijo con la Dra" como fallo del
        # bot cuando en prod el nombre viene servido en el resultado de la tool).
        return (
            note
            + "DISPONIBLE:\n"
            + f"1) {_fmt(s1)} — 10:00 hs — Dra. Laura Delgado\n"
            + f"2) {_fmt(s2)} — 11:15 hs — Dra. Laura Delgado"
        )

    if name == "confirm_slot":
        return f"RESERVADO 30 min: {args.get('slot_datetime', '')}."

    if name == "book_appointment":
        # CANDADO DATOS (espejo del real, caso Lucas 2026-07-20): un paciente NUEVO
        # sin nombre/apellido/DNI NO se reserva — se piden los datos primero.
        if (_CTX.get("patient_status") or "") in ("new_lead", "lead") and not args.get("is_minor") and not args.get("is_art"):
            # v2 ANTI-INVENTO (espejo del real, casos "Nombre Apellido"/"Abuela Garnier"):
            # placeholders y parentescos NO cuentan como dato — se tratan como faltantes.
            _placeholders = {
                "nombre", "apellido", "paciente", "cliente", "desconocido", "desconocida",
                "test", "prueba", "nn", "xx", "sin nombre", "no especificado",
                "abuela", "abuelo", "mama", "mamá", "papa", "papá", "madre", "padre",
                "hijo", "hija", "tia", "tía", "tio", "tío", "hermano", "hermana",
                "esposa", "esposo", "señora", "senora", "señor", "senor", "amigo", "amiga",
                "novia", "novio", "nena", "nene", "bebe", "bebé", "menor", "tambien", "también",
            }

            def _vale(k):
                _v = str(args.get(k) or "").strip()
                return bool(_v) and _v.lower() not in _placeholders and len(_v) >= 2

            _faltan = [n for n, k in (("nombre", "first_name"), ("apellido", "last_name"), ("DNI", "dni"))
                       if not _vale(k)]
            if _faltan:
                return (
                    "FALTAN_DATOS — el turno NO se reservó todavía. Es un paciente NUEVO y antes de "
                    "reservar necesitás: " + ", ".join(_faltan) + ". "
                    "Pedile esos datos en UN solo mensaje amable y RECIÉN después volvé a llamar "
                    "book_appointment con todos los datos (el horario elegido sigue disponible unos "
                    "minutos). ⛔ NUNCA inventes nombre/apellido/DNI ni uses placeholders o "
                    "parentescos ('Nombre Apellido', 'Abuela'): preguntale a la persona sus datos REALES."
                )
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
            # Espejo del not_found real: particular + comprobante para reintegro.
            return json.dumps(
                {
                    "status": "not_found",
                    "cobertura": args.get("provider_name", ""),
                    "convenio": False,
                    "alternative": "particular_con_reintegro",
                    "nota_obligatoria": "Decile EXPLÍCITAMENTE que la clínica le entrega el comprobante/recibo para que pueda gestionar el reintegro con su cobertura.",
                },
                ensure_ascii=False,
            )
        if cfg["status"] == "external_derivation":
            # ISSN → texto fijo real del panel (ai_response_template).
            return (
                "Para cirugía maxilofacial con ISSN, la atención se realiza a través de CIMO. "
                "Podés comunicarte al +54 9 299 329-4089. Para otros tratamientos, la atención "
                "en el consultorio es particular."
            )
        if cfg["status"] == "restricted":
            data = {
                "status": "restricted",
                "cobertura": canon,
                "convenio": "restringido",
                "nota": "cubre solo algunos tratamientos según el plan; el detalle se confirma con la clínica",
                "coseguro": cfg["copay"],
            }
            if cfg["mode"] == "delayed":
                first_ok = date.today() + timedelta(days=cfg["delay_days"])
                data["turnos_desde"] = first_ok.strftime("%d/%m/%Y")
                data["nota_obligatoria"] = (
                    f"⏳ {canon} agenda turnos POR COBERTURA a partir del {first_ok.strftime('%d/%m')} (plazo de la "
                    "obra social, NO falta de agenda — nunca digas 'no tengo disponibilidad'). Si el paciente quiere "
                    "atenderse antes, puede hacerlo de forma PARTICULAR sin ese plazo — opción, sin presionar."
                )
            return json.dumps(data, ensure_ascii=False)
        if cfg["status"] == "rejected":
            return json.dumps({"cobertura": canon, "convenio": False}, ensure_ascii=False)
        data = {"cobertura": canon, "convenio": True, "coseguro": cfg["copay"]}
        if cfg["mode"] == "delayed":
            first_ok = date.today() + timedelta(days=cfg["delay_days"])
            data["turnos_desde"] = first_ok.strftime("%d/%m/%Y")
            # Espejo del nota_obligatoria de prod (check_insurance_coverage 2026-07-20):
            # el plazo es de la OS (no falta de agenda) y la vía particular no lo lleva.
            data["nota_obligatoria"] = (
                f"⏳ {canon} agenda turnos POR COBERTURA a partir del {first_ok.strftime('%d/%m')} (plazo de la "
                "obra social, NO falta de agenda — nunca digas 'no tengo disponibilidad'). Si el paciente quiere "
                "atenderse antes, puede hacerlo de forma PARTICULAR sin ese plazo — opción, sin presionar."
            )
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
        # Override por-caso (mock_my_appointments: "none"): casos patient_no_appointment
        # — el default inventaba un turno fantasma que contradecía el caso y desviaba
        # la conversación a "ya tenés un turno" (falso FALLA de los casos recurrentes).
        if _CTX.get("my_appointments") == "none":
            return "Sin turnos. ¿Agendamos?"
        if _CTX.get("my_appointments") == "two":
            # Caso Matías (prod 2026-07-20): la secretaria cargó las DOS opciones como
            # turnos reales mientras el paciente decidía.
            d1 = _next_weekday(date.today() + timedelta(days=3))
            d2 = _next_weekday(d1 + timedelta(days=1))
            return (
                f"TURNOS DEL PACIENTE:\n1) {_fmt(d1)} — 10:00 hs — Checkup. Sede Córdoba.\n"
                f"2) {_fmt(d2)} — 18:20 hs — Checkup. Sede Córdoba."
            )
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
