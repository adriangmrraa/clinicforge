"""
Lead Analysis — AI-powered lead conversation analysis and recovery message generation.

Used by the lead recovery job to:
1. analyze_conversation: decide if a lead warrants follow-up
2. generate_recovery_message: craft personalized touch messages (1, 2, 3)
3. get_real_availability: find real slots in the next 3 days (no OpenAI, pure DB)
"""

import os
import json
import logging
from datetime import datetime, timedelta, date

import openai

logger = logging.getLogger(__name__)

DEEPSEEK_MODELS = {"deepseek-chat", "deepseek-reasoner"}
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

_DAY_NAMES_ES = {
    0: "lunes",
    1: "martes",
    2: "miércoles",
    3: "jueves",
    4: "viernes",
    5: "sábado",
    6: "domingo",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _resolve_model(pool, tenant_id: int) -> str:
    """Read MODEL_LEAD_RECOVERY from system_config. Fallback: gpt-4o-mini."""
    try:
        row = await pool.fetchrow(
            "SELECT value FROM system_config WHERE key = 'MODEL_LEAD_RECOVERY' AND tenant_id = $1",
            tenant_id,
        )
        if row and row.get("value"):
            return str(row["value"]).strip()
    except Exception as e:
        logger.warning(f"lead_analysis: model resolution error for tenant {tenant_id}: {e}")
    return "gpt-4o-mini"


def _build_client(model: str) -> openai.AsyncOpenAI:
    """Return an AsyncOpenAI client configured for OpenAI or DeepSeek."""
    if model.lower() in DEEPSEEK_MODELS or "deepseek" in model.lower():
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        return openai.AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
    api_key = os.environ.get("OPENAI_API_KEY", "")
    return openai.AsyncOpenAI(api_key=api_key)


async def _track(pool, tenant_id: int, model: str, prompt_tokens: int, completion_tokens: int, source: str, phone: str = "system"):
    """Best-effort token tracking — never raises."""
    try:
        from dashboard.token_tracker import track_service_usage
        await track_service_usage(
            pool,
            tenant_id,
            model,
            prompt_tokens,
            completion_tokens,
            source=source,
            phone=phone,
        )
    except Exception as e:
        logger.debug(f"lead_analysis: token tracking skipped: {e}")


def _strip_markdown_json(text: str) -> str:
    """Remove ```json ... ``` wrappers if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (```json or ```) and last line (```)
        inner = lines[1:] if lines[0].startswith("```") else lines
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
    return text


# ---------------------------------------------------------------------------
# 1. analyze_conversation
# ---------------------------------------------------------------------------

_ANALYZE_SYSTEM_PROMPT = """\
Sos un analista de leads para una clínica dental. Analizá la conversación y decidí si vale la pena hacer seguimiento.

Respondé SOLO con JSON válido, sin markdown:
{"seguimiento": true/false, "servicio": "nombre del servicio mencionado o vacío", "resumen": "resumen de 1 línea"}

Criterios para seguimiento=true:
- Preguntó por un servicio específico
- Mostró interés en agendar
- Preguntó precios o disponibilidad
- Mencionó un problema dental

Criterios para seguimiento=false:
- Solo saludó sin más
- Dijo que no le interesa
- Ya tiene dentista
- Spam o mensaje irrelevante
- La conversación se cerró naturalmente\
"""


async def analyze_conversation(pool, tenant_id: int, phone: str, messages: list) -> dict:
    """Analyze a lead's conversation to decide if follow-up is warranted.

    Returns: {"seguimiento": bool, "servicio": str, "resumen": str}
    """
    _fallback = {"seguimiento": False, "servicio": "", "resumen": "parse_error"}

    try:
        model = await _resolve_model(pool, tenant_id)
        client = _build_client(model)

        # Format conversation
        lines = []
        for msg in messages:
            role = msg.get("role", "")
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                lines.append(f"Paciente: {content}")
            elif role in ("assistant", "tool"):
                lines.append(f"Asistente: {content}")
        conversation_text = "\n".join(lines) or "(sin mensajes)"

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _ANALYZE_SYSTEM_PROMPT},
                {"role": "user", "content": conversation_text},
            ],
            max_tokens=200,
            temperature=0,
        )

        content = (response.choices[0].message.content or "").strip()
        usage = response.usage

        await _track(
            pool,
            tenant_id,
            model,
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
            source="lead_recovery_analysis",
            phone=phone,
        )

        try:
            parsed = json.loads(_strip_markdown_json(content))
            return {
                "seguimiento": bool(parsed.get("seguimiento", False)),
                "servicio": str(parsed.get("servicio", "")),
                "resumen": str(parsed.get("resumen", "")),
            }
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"lead_analysis: JSON parse error for tenant {tenant_id} phone {phone}: {e} | raw={content!r}")
            return _fallback

    except Exception as e:
        logger.error(f"lead_analysis: analyze_conversation error tenant {tenant_id} phone {phone}: {e}")
        return _fallback


# ---------------------------------------------------------------------------
# 2. generate_recovery_message
# ---------------------------------------------------------------------------

_TOUCH_PROMPTS = {
    1: """\
Generá un mensaje de seguimiento cálido para un lead de clínica dental.
Contexto: {lead_name} consultó por {servicio} y no agendó.
{availability_line}
Clínica: {clinic_name}

Reglas:
- Máximo 300 caracteres
- Tuteo/voseo rioplatense
- Mencioná el servicio si lo hay
- Si hay disponibilidad, ofrecé el turno concreto
- Si no hay, preguntá si quiere que busques para la semana que viene
- Soná como una asistente real, no como un bot
- No uses emojis excesivos (máximo 1-2)
- Objetivo: que agende\
""",
    2: """\
Generá un segundo mensaje de seguimiento breve y con un toque de humor.
{lead_name} no respondió al primer mensaje sobre {servicio}.
Clínica: {clinic_name}

Reglas:
- Máximo 200 caracteres
- Breve y directo
- Un toque de humor sutil
- Referenciá que ya le escribiste antes
- Objetivo: que responda\
""",
    3: """\
Generá un último mensaje de cierre amable para un lead que no respondió.
{lead_name}, servicio: {servicio}. Clínica: {clinic_name}

Reglas:
- Máximo 250 caracteres
- Tono suave, sin presión
- Dejá la puerta abierta ("cuando quieras")
- Es el último mensaje, no va a haber más
- Despedida cálida\
""",
}

_TOUCH_MAX_TOKENS = {1: 120, 2: 80, 3: 100}


async def generate_recovery_message(
    pool, tenant_id: int, touch_number: int, context: dict
) -> str | None:
    """Generate a personalized recovery message for the given touch.

    context keys: lead_name, servicio, clinic_name, availability_text (touch 1 only)
    Returns message text or None on failure.
    """
    try:
        model = await _resolve_model(pool, tenant_id)
        client = _build_client(model)

        lead_name = context.get("lead_name") or "el/la paciente"
        servicio = context.get("servicio") or ""
        clinic_name = context.get("clinic_name") or "la clínica"
        availability_text = context.get("availability_text") or ""

        if touch_number not in _TOUCH_PROMPTS:
            logger.warning(f"lead_analysis: invalid touch_number={touch_number}")
            return None

        if touch_number == 1:
            if availability_text:
                availability_line = f"Disponibilidad: {availability_text}"
            else:
                availability_line = "No hay turnos disponibles esta semana."
            system_prompt = _TOUCH_PROMPTS[1].format(
                lead_name=lead_name,
                servicio=servicio,
                availability_line=availability_line,
                clinic_name=clinic_name,
            )
        elif touch_number == 2:
            system_prompt = _TOUCH_PROMPTS[2].format(
                lead_name=lead_name,
                servicio=servicio,
                clinic_name=clinic_name,
            )
        else:
            system_prompt = _TOUCH_PROMPTS[3].format(
                lead_name=lead_name,
                servicio=servicio,
                clinic_name=clinic_name,
            )

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": system_prompt},
            ],
            max_tokens=_TOUCH_MAX_TOKENS.get(touch_number, 120),
            temperature=0.7,
        )

        content = (response.choices[0].message.content or "").strip()
        usage = response.usage

        await _track(
            pool,
            tenant_id,
            model,
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
            source=f"lead_recovery_generate_t{touch_number}",
        )

        return content if content else None

    except Exception as e:
        logger.error(f"lead_analysis: generate_recovery_message error tenant {tenant_id} touch {touch_number}: {e}")
        return None


# ---------------------------------------------------------------------------
# 3. get_real_availability
# ---------------------------------------------------------------------------

_SLOT_DURATION_MINUTES = 30
_DAYS_AHEAD = 3
_DAY_KEY_MAP = {
    0: "monday",
    1: "tuesday",
    2: "wednesday",
    3: "thursday",
    4: "friday",
    5: "saturday",
    6: "sunday",
}


async def get_real_availability(pool, tenant_id: int, servicio: str = None) -> str | None:
    """Find real available slots for the next 3 days. Returns human-readable text or None.

    This function does NOT call OpenAI — no token tracking needed.
    """
    try:
        # 1. Get tenant working_hours and timezone
        tenant_row = await pool.fetchrow(
            "SELECT working_hours, timezone FROM tenants WHERE id = $1",
            tenant_id,
        )
        if not tenant_row:
            logger.warning(f"lead_analysis: tenant {tenant_id} not found")
            return None

        raw_wh = tenant_row["working_hours"]
        if isinstance(raw_wh, str):
            try:
                working_hours = json.loads(raw_wh)
            except Exception:
                working_hours = {}
        elif raw_wh is None:
            working_hours = {}
        else:
            working_hours = dict(raw_wh)

        # 2. Resolve professionals
        if servicio:
            # Try to find treatment type by name match
            treatment_row = await pool.fetchrow(
                "SELECT id FROM treatment_types WHERE tenant_id = $1 AND LOWER(name) LIKE LOWER($2) LIMIT 1",
                tenant_id,
                f"%{servicio}%",
            )
            if treatment_row:
                prof_rows = await pool.fetch(
                    """
                    SELECT p.id
                    FROM professionals p
                    JOIN treatment_type_professionals ttp ON ttp.professional_id = p.id
                    WHERE ttp.treatment_type_id = $1 AND p.tenant_id = $2 AND p.is_active = true
                    """,
                    treatment_row["id"],
                    tenant_id,
                )
                if not prof_rows:
                    # Backward compat: no assignments → all professionals
                    prof_rows = await pool.fetch(
                        "SELECT id FROM professionals WHERE tenant_id = $1 AND is_active = true",
                        tenant_id,
                    )
            else:
                prof_rows = await pool.fetch(
                    "SELECT id FROM professionals WHERE tenant_id = $1 AND is_active = true",
                    tenant_id,
                )
        else:
            prof_rows = await pool.fetch(
                "SELECT id FROM professionals WHERE tenant_id = $1 AND is_active = true",
                tenant_id,
            )

        if not prof_rows:
            return None

        prof_ids = [r["id"] for r in prof_rows]

        # 3. Iterate next DAYS_AHEAD business days
        found_slots = []
        today = date.today()

        for delta in range(1, _DAYS_AHEAD + 4):  # a few extra days in case clinic is closed
            if len(found_slots) >= 2:
                break

            check_date = today + timedelta(days=delta)
            weekday = check_date.weekday()  # 0=Monday
            day_key = _DAY_KEY_MAP[weekday]

            # Check if clinic is open this day
            day_config = working_hours.get(day_key) or {}
            if isinstance(day_config, str):
                try:
                    day_config = json.loads(day_config)
                except Exception:
                    day_config = {}

            if not day_config.get("enabled", False):
                continue

            start_str = day_config.get("start") or "08:00"
            end_str = day_config.get("end") or "18:00"

            try:
                start_h, start_m = [int(x) for x in start_str.split(":")]
                end_h, end_m = [int(x) for x in end_str.split(":")]
            except Exception:
                continue

            clinic_start = check_date.strftime("%Y-%m-%d") + f" {start_h:02d}:{start_m:02d}:00"
            clinic_end = check_date.strftime("%Y-%m-%d") + f" {end_h:02d}:{end_m:02d}:00"

            # 4. Get existing appointments for this day and these professionals
            existing = await pool.fetch(
                """
                SELECT appointment_datetime, duration_minutes
                FROM appointments
                WHERE tenant_id = $1
                  AND professional_id = ANY($2::int[])
                  AND appointment_datetime::date = $3
                  AND status NOT IN ('cancelled', 'no-show')
                ORDER BY appointment_datetime ASC
                """,
                tenant_id,
                prof_ids,
                check_date,
            )

            booked_slots = set()
            for appt in existing:
                appt_dt = appt["appointment_datetime"]
                if isinstance(appt_dt, datetime):
                    appt_time = appt_dt
                else:
                    continue
                duration = appt["duration_minutes"] or _SLOT_DURATION_MINUTES
                slot_count = max(1, duration // _SLOT_DURATION_MINUTES)
                for i in range(slot_count):
                    slot_start = appt_time + timedelta(minutes=i * _SLOT_DURATION_MINUTES)
                    booked_slots.add((slot_start.hour, slot_start.minute))

            # 5. Walk time slots
            current_h, current_m = start_h, start_m
            slot_found = False
            while True:
                slot_end_minutes = current_h * 60 + current_m + _SLOT_DURATION_MINUTES
                if slot_end_minutes > end_h * 60 + end_m:
                    break
                if (current_h, current_m) not in booked_slots:
                    day_name = _DAY_NAMES_ES[weekday]
                    # "mañana lunes" vs "el martes" etc.
                    if delta == 1:
                        prefix = f"mañana {day_name}"
                    else:
                        prefix = f"el {day_name}"
                    found_slots.append(f"{prefix} a las {current_h:02d}:{current_m:02d}")
                    slot_found = True
                    break
                current_m += _SLOT_DURATION_MINUTES
                if current_m >= 60:
                    current_h += current_m // 60
                    current_m = current_m % 60

        if not found_slots:
            return None

        return " o ".join(found_slots)

    except Exception as e:
        logger.error(f"lead_analysis: get_real_availability error tenant {tenant_id}: {e}")
        return None
