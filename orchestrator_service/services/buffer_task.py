"""
process_buffer_task: invoca agente IA y envía respuesta por Chatwoot (o YCloud).
CLINICASV1.0 - integrado con chat_conversations; usa get_agent_executable_for_tenant (Vault).
"""

import logging
import json
import os
import re
from typing import List

from db import get_pool
from langchain_core.messages import HumanMessage, AIMessage

try:
    from services.vision_service import analyze_attachments_batch, MAX_IMAGES, MAX_PDFS
except ImportError:
    analyze_attachments_batch = None
    MAX_IMAGES = 10
    MAX_PDFS = 5
try:
    from services.image_classifier import classify_message
except ImportError:
    classify_message = None
try:
    from services.attachment_summary import generate_attachment_summary
except ImportError:
    generate_attachment_summary = None

# Date validator for Bug #1 - post-LLM date validation
try:
    from services.date_validator import validate_dates_in_response, validate_day_of_week
except ImportError:
    validate_dates_in_response = None
    validate_day_of_week = None

# Conversation state for Bug #4 - state machine
try:
    from services.conversation_state import get_state, set_state, reset, VALID_STATES
except ImportError:
    get_state = None
    set_state = None
    reset = None
    VALID_STATES = []

# State guard constants for Bug #4
MAX_STATE_RETRIES = 1

# Regex patterns for intent detection (Bug #4 Phase C)
_SELECTION_INTENT_PATTERN = None
_RESEARCH_INTENT_PATTERN = None

logger = logging.getLogger(__name__)


# v8.2 — Statement dedup: hash agent output, suppress identical messages after 2 occurrences
def _hash_statement(text: str) -> str:
    """Return a deterministic 12-char hex hash of the statement text (sha256[:12])."""
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def compute_social_context(channel_type: str, tenant_row: dict) -> dict:
    """Compute social channel context for TurnContext.extra.

    Pure function — no I/O. Called from the engine dispatch point in
    _run_ai_for_phone to populate the 5 social keys before passing ctx to the
    engine router (multi path) or build_system_prompt (solo path).

    Args:
        channel_type: "instagram" | "facebook" | "whatsapp" | "chatwoot" | None
        tenant_row: asyncpg Record or dict from the tenants SELECT query.
                    Expected keys: social_ig_active, social_landings,
                    instagram_handle, facebook_page_id.  Missing keys default
                    to falsy values (backward compat).

    Returns:
        dict with keys: channel, is_social_channel, social_landings,
        instagram_handle, facebook_page_id.
    """
    effective_channel = channel_type or "whatsapp"
    is_social = effective_channel in ("instagram", "facebook") and bool(
        tenant_row.get("social_ig_active", False)
    )

    # JSONB gotcha from CLAUDE.md: asyncpg may return JSONB columns as raw strings.
    # Parse defensively so callers always receive a dict or None.
    social_landings = tenant_row.get("social_landings") if is_social else None
    if isinstance(social_landings, str):
        try:
            social_landings = json.loads(social_landings)
        except (json.JSONDecodeError, ValueError):
            social_landings = None

    # Build wa.me link for social channels so the agent can send it post-booking
    bot_phone = tenant_row.get("bot_phone_number") or ""
    # Normalize: strip non-digits, ensure no leading +
    bot_phone_clean = re.sub(r"\D", "", bot_phone)
    whatsapp_link = f"https://wa.me/{bot_phone_clean}" if bot_phone_clean else None

    return {
        "channel": effective_channel,
        "is_social_channel": is_social,
        "social_landings": social_landings,
        "instagram_handle": tenant_row.get("instagram_handle") if is_social else None,
        "facebook_page_id": tenant_row.get("facebook_page_id") if is_social else None,
        "whatsapp_link": whatsapp_link if is_social else None,
    }


def _detect_selection_intent(msg: str) -> bool:
    """
    Detect if user message indicates they want to SELECT one of the offered slots.
    Used for Bug #4 Phase C - Input-side state guard.
    """
    import re

    global _SELECTION_INTENT_PATTERN
    if _SELECTION_INTENT_PATTERN is None:
        # Patterns for selecting an offered slot
        patterns = [
            # Bare number: just "1" or "2" (most common selection)
            r"^[1-9]$",
            # Emoji numbers: 1️⃣, 2️⃣, 3️⃣ (the bot sends these, patients copy them)
            r"[1-9]\uFE0F?\u20E3",
            # Time confirmation: "a las 15", "a las 10 hs", "a las 15 está bien", "las 13 me queda"
            r"\ba\s+las\s+\d{1,2}\b",
            # Time in words: "a las tres", "a las dos"
            r"\ba\s+las\s+(una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|diecis[eé]is|diecisiete|dieciocho)\b",
            r"\blas\s+\d{1,2}\s*(hs|horas)?\s*(est[aá]\s+bien|me\s+queda|va|dale|sí|si)\b",
            # "está bien", "va bien", "me va", "me viene bien" as standalone confirmations
            r"\best[aá]\s+bien\b",
            r"\bva\s+bien\b",
            r"\bme\s+va\b",
            r"\bme\s+viene\s+(bien|perfecto|mejor|b[aá]rbaro)\b",  # "me viene bien"
            r"\bok\b",
            r"\bbueno\b",
            r"\bdale\s+[ea]s[ea]\b",  # "dale esa", "dale ese"
            # Numeric ordinals: "el 1", "el 1ro", "la 1", "la 2", etc.
            r"\b[el]l\s+[0-9]+(?:ro|do|er|°)?\b",  # "el 1", "el 1ro"
            r"\bla\s+[0-9]+(?:ra|da|°)?\b",  # "la 1", "la 2", "la 1ra"
            # "opción/opcion" + number: "opción 1", "la opción 2", "opcion 1"
            r"\b(?:la\s+)?opci[oó]n\s+[0-9]+\b",
            # "turno" + number: "turno 1", "el turno 2"
            r"\b(?:el\s+)?turno\s+[0-9]+\b",
            # Day names as selection: "el lunes", "lunes", "el miércoles", "miercoles"
            r"\b(?:el\s+)?(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\b",
            # Spanish ordinal words (with and without noun)
            r"\bel\s+primer(?:o|(?=\s))\b",  # "el primero", "el primer turno"
            r"\bla\s+primera\b",  # "la primera"
            r"\bel\s+segund(?:o|(?=\s))\b",  # "el segundo", "el segundo turno"
            r"\bla\s+segunda\b",  # "la segunda"
            r"\bel\s+tercer(?:o|(?=\s))\b",  # "el tercero", "el tercer turno"
            r"\bla\s+tercera\b",  # "la tercera"
            # Ordinal word forms: "uno", "dos", "el uno", "la dos"
            r"\b(?:el|la)\s+(uno|dos|tres)\b",  # "el uno", "la dos"
            r"\bconfirmo\b",  # "confirmo", "confirmar"
            # "si" / "sí" as standalone affirmation (NOT as conjunction meaning "if")
            # Only match at start of short messages to avoid "si atienden" false positives
            r"^s[ií]$",  # exactly "si" or "sí"
            r"^s[ií]\b",  # "si," or "si!" or "sí," at start
            r"\bsí\b",  # accented "sí" anywhere (rarer as conjunction)
            r"\bquiero\s+ese\b",  # "quiero ese"
            r"\bagéndame\s+ese\b",  # "agéndame ese"
            r"\breservar\b",  # "reservar"
            r"\b\d{1,2}\s*(de\s+)?(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)",  # "12 de mayo"
            r"\bde\s+la\s+tarde\b",  # "el de la tarde"
            r"\bde\s+la\s+ma[ñn]ana\b",  # "el de la mañana"
            # Additional selection signals
            r"(?:^|\s)(ese|eso|esa)\b",  # "ese", "eso", "esa"
            r"\bdal[ea]\b",  # "dale", "dala"
            r"\bcualquiera\b",  # "cualquiera"
            r"\bel\s+m[aá]s\s+temprano\b",  # "el más temprano"
            r"\bel\s+m[aá]s\s+cercano\b",  # "el más cercano"
            r"\bel\s+de\s+la\s+(mañana|tarde|noche)\b",  # "el de la tarde"
            r"\bel\s+de\s+las\s+\d{1,2}\b",  # "el de las 13"
            r"\b(?:ese|esa)\s+de\s+las\s+\d{1,2}\b",  # "ese de las 13"
            r"\bel\s+turno\s+de\s+las\s+\d{1,2}\b",  # "el turno de las 13"
            r"\blisto\b",  # "listo"
            r"\bperfecto\b",  # "perfecto"
            r"\bconfirm[oa]\b",  # "confirmo", "confirma"
            r"\bsi\s*,?\s*(dale|va|listo|ese|por\s+favor)\b",  # "sí dale", "sí va"
            r"\bvamos\s+con\s+(el|la|ese)\b",  # "vamos con el primero"
            r"\bme\s+queda\s+(bien|mejor|perfecto)\b",  # "me queda bien"
            r"\bquiero\s+el\b",  # "quiero el primero"
            r"\bquiero\s+el\s+del\b",  # "quiero el del lunes"
            r"\bprefiero\s+el\b",  # "prefiero el lunes" (NOT "prefiero otro" — caught by rejection)
            r"\bagend[aá](me|lo)\b",  # "agendame", "agendalo"
            r"\breserv[aá](me|lo)\b",  # "reservame", "reservalo"
        ]
        combined = "|".join(patterns)
        _SELECTION_INTENT_PATTERN = re.compile(combined, re.IGNORECASE)

    text = msg.strip()

    # Query/question exclusions: e.g. "quiero saber si atienden el lunes"
    text_lower = text.lower()
    if "?" in text_lower or "saber si" in text_lower or "si atienden" in text_lower or "saber que" in text_lower or "saber qué" in text_lower:
        return False

    if not _SELECTION_INTENT_PATTERN.search(text):
        return False

    # Rejection override: if the message starts with "no" or contains strong rejection
    # signals, treat it as rejection rather than selection even if a pattern matched.
    # e.g. "no, el miércoles" or "no puedo el lunes" should NOT be selection.
    import re as _re
    strong_rejection = r"^no\b|\bno\s+puedo\b|\bno\s+me\b|\bprefiero\s+otr[oa]\b|\bsolo\s+puedo\b|\brecién\s+puedo\b|\búnicamente\b|\bninguno\b|\bninguna\b"
    if _re.search(strong_rejection, text, _re.IGNORECASE):
        return False  # rejection override — "no, el lunes" is NOT a selection

    return True


def _detect_research_intent(msg: str) -> bool:
    """
    Detect if user wants to SEARCH AGAIN / look for different slots.
    Used for Bug #4 Phase C - Input-side state guard.
    Expanded with 20+ new patterns to catch natural rejection expressions.
    """
    import re

    global _RESEARCH_INTENT_PATTERN
    if _RESEARCH_INTENT_PATTERN is None:
        # Patterns for searching for different slots
        patterns = [
            # --- Original patterns ---
            r"\botra\s+fecha\b",         # "otra fecha"
            r"\botro\s+día\b",           # "otro día"
            r"\botra\s+hora\b",          # "otra hora"
            r"\botro\s+turno\b",         # "otro turno"
            r"\bbuscá\s+en\s+otra\b",    # "buscá en otra semana"
            r"\bno\s+me\s+sirve\b",      # "no me sirve"
            r"\botro\b",                 # "otro" / "otra" (any case, replaces OTRO/OTRA)
            r"\bcambiar\b",              # "cambiar" (any case)
            r"\bdiferente\b",            # "diferente"
            # --- Explicit rejection ---
            r"\bno\s+puedo\b",                   # "no puedo"
            r"\bno\s+me\s+(queda|va|viene)\b",   # "no me queda", "no me va", "no me viene"
            r"\bninguno\b",                       # "ninguno"
            r"\bninguna\b",                       # "ninguna"
            r"^no\b",                             # starts with "no" → "no, el viernes..."
            r"\bimposible\b",                     # "imposible"
            r"\bno\s+tengo\s+disponibilidad\b",   # "no tengo disponibilidad"
            # --- Request for different day/time ---
            r"\bprefiero\b",                      # "prefiero otro día"
            r"\bmejor\b.{0,20}\b(día|fecha|hora|semana)\b",  # "mejor otro día"
            r"\bsolo\s+puedo\b",                  # "solo puedo los jueves"
            r"\brecién\s+puedo\b",                # "recién puedo el viernes"
            r"\búnicamente\b",                    # "únicamente el viernes"
            r"\bla\s+semana\s+que\s+viene\b",     # "la semana que viene"
            r"\bsemana\s+próxima\b",              # "semana próxima"
            r"\bsemana\s+proxima\b",              # "semana proxima" (no accent)
            r"\bmás\s+(temprano|tarde|adelante)\b",  # "más temprano", "más tarde", "más adelante"
            r"\bmas\s+(temprano|tarde|adelante)\b",  # same without accent
            r"\ba\s+la\s+(mañana|manana|tarde|noche)\b",  # "a la tarde tenés?"
            r"\btenés\s+(algo|turno)\b",          # "tenés algo el viernes?"
            r"\bhay\s+(algo|turno)\b",            # "hay algo más temprano?"
            r"\bpuedo\s+solo\b",                  # "puedo solo el viernes"
            r"\bnecesito\s+que\s+sea\b",          # "necesito que sea por la tarde"
            r"\bprefiero\s+otro\b",               # "prefiero otro horario"
            r"\bprefiero\s+otra\b",               # "prefiero otra fecha"
            r"\bmejor\s+otro\b",                  # "mejor otro día"
            r"\bmejor\s+otra\b",                  # "mejor otra semana"
        ]
        combined = "|".join(patterns)
        _RESEARCH_INTENT_PATTERN = re.compile(combined, re.IGNORECASE)

    text = msg.strip()
    return _RESEARCH_INTENT_PATTERN.search(text) is not None


_PERIOD_CHANGE_PATTERN = None


def _detect_period_change(msg: str) -> bool:
    """Detecta si el paciente cambia a un MES o PERÍODO nuevo (para julio, en agosto,
    principios/mediados/fines de mes, el mes que viene, quincena, más adelante, etc.).
    Complementa _detect_research_intent (que NO cubre meses/períodos). Se usa para
    liberar el lock SLOT_LOCKED y re-buscar disponibilidad en vez de derivar.
    Los nombres de mes exigen una preposición previa (para/en/a/hacia) o un día (5 de
    julio) para NO confundir un nombre propio como 'Julio Gómez' con un cambio de fecha."""
    import re

    global _PERIOD_CHANGE_PATTERN
    if _PERIOD_CHANGE_PATTERN is None:
        _meses = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre"
        patterns = [
            rf"\b(para|en|a|hacia)\s+(el\s+)?({_meses})\b",  # "para julio", "en agosto"
            rf"\b\d{{1,2}}\s+de\s+({_meses})\b",             # "5 de julio" (el dígito evita apellidos)
            r"\b(principios?|mediados?|fin(es)?|final(es)?|inicio|comienzos?)\s+de\b",
            r"\bel\s+mes\s+que\s+viene\b",
            r"\bmes\s+pr[oó]ximo\b",
            r"\bpr[oó]ximo\s+mes\b",
            r"\bpara\s+el\s+mes\b",
            r"\bquincena\b",
            r"\bm[aá]s\s+adelante\b",
        ]
        _PERIOD_CHANGE_PATTERN = re.compile("|".join(patterns), re.IGNORECASE)

    return _PERIOD_CHANGE_PATTERN.search(msg.strip()) is not None


def classify_intent(messages: list) -> set:
    """
    Classify patient message intent via keyword detection (<1ms, no LLM).
    Returns a set of tags used to conditionally inject prompt sections.

    Tags: 'implant', 'media', 'payment'
    If no tags match, returns empty set — caller should inject all sections (safe default).
    """
    text = " ".join(messages).lower()
    tags = set()

    # Implant/prosthetics keywords
    implant_kw = [
        "implante",
        "prótesis",
        "protesis",
        "dentadura",
        "sin hueso",
        "no tengo hueso",
        "me rechazaron",
        "diente postizo",
        "dientes faltantes",
        "perdí un diente",
        "perdi un diente",
        "perdí varios",
        "perdi varios",
        "quiero algo fijo",
        "no tengo dientes",
        "se me cayeron",
    ]
    if any(kw in text for kw in implant_kw):
        tags.add("implant")

    # Media/attachment keywords (supplement has_recent_media flag from buffer_task)
    media_kw = [
        "foto",
        "imagen",
        "adjunto",
        "archivo",
        "radiografía",
        "radiografia",
        "tomografía",
        "tomografia",
        "estudio",
        "panorámica",
        "panoramica",
    ]
    if any(kw in text for kw in media_kw):
        tags.add("media")

    # Payment keywords
    payment_kw = [
        "pagar",
        "pago",
        "seña",
        "sena",
        "transferencia",
        "comprobante",
        "cuánto debo",
        "cuanto debo",
        "saldo",
        "cuota",
        "deuda",
        "factura",
        "recibo",
        "abonar",
    ]
    if any(kw in text for kw in payment_kw):
        tags.add("payment")

    return tags


# ═══════════════════════════════════════════════════════════════════
# v8.3: Multi-entity DNI parsing (resolve-13-booking-errors T5)
# ═══════════════════════════════════════════════════════════════════
_DNI_RE = re.compile(r"\b(\d{7,11})\b")
_ENTITY_MARKER_RE = re.compile(
    r"\b(?:"
    r"para mí|\bmi\b(?!\s*(?:mamá|papá|hijo|herman|espos|marido|señora|abuel|tí[ae]|prim))"
    r"|para\s+(?:él|ella|ellos|ellas|un|una)"
    r"|para\s+mi\s+(?:mamá|papá|hijo|hija|herman[oa]|espos[oa]|marido|señora|señor|abuel[oa]|tí[oa]|prim[oa]|sobrin[oa]|amig[oa]|compañer[oa])"
    r"|para\s+(?:\w+\s+)+"
    r")\b",
    re.IGNORECASE,
)


def extract_multi_dni(messages: list) -> list[dict]:
    """Extract multiple DNI entities from patient messages.
    
    Returns a list of {dni, relationship, inferred_name} dicts.
    Example: "es para mí DNI 12345678 y para mi mamá DNI 87654321"
    → [{dni: "12345678", relationship: "self", inferred_name: None},
        {dni: "87654321", relationship: "mother", inferred_name: None}]
    """
    text = " ".join(messages)
    dnis = _DNI_RE.findall(text)
    if len(dnis) <= 1:
        return []  # Single or no DNI — no multi-entity

    # If multiple DNIs found, try to associate each with an entity
    entities = []
    # Find all entity markers with their positions
    markers = []
    for m in _ENTITY_MARKER_RE.finditer(text):
        markers.append((m.start(), m.end(), m.group()))

    for dni in dnis:
        dni_pos = text.find(dni)
        # Find closest marker before this DNI
        closest = None
        closest_dist = float("inf")
        for start, end, marker in markers:
            if end <= dni_pos and dni_pos - end < closest_dist:
                closest = marker
                closest_dist = dni_pos - end
        # Infer relationship from marker
        if closest:
            cl = closest.lower().strip()
            if cl in ("para mí", "mi") or cl.startswith("para mí"):
                relationship = "self"
            elif "mamá" in cl or "mama" in cl:
                relationship = "mother"
            elif "papá" in cl or "papa" in cl:
                relationship = "father"
            elif "hijo" in cl or "hija" in cl:
                relationship = "child"
            elif "herman" in cl:
                relationship = "sibling"
            elif "espos" in cl or "marido" in cl or "señora" in cl or "señor" in cl:
                relationship = "spouse"
            elif "abuel" in cl:
                relationship = "grandparent"
            elif "tí" in cl or "tia" in cl or "tío" in cl:
                relationship = "aunt_uncle"
            else:
                relationship = "other"
        else:
            relationship = "self"  # default
        entities.append({
            "dni": dni,
            "relationship": relationship,
            "inferred_name": None,
        })
    return entities


# ═══════════════════════════════════════════════════════════════════
# v8.3: Compound intent detection (resolve-13-booking-errors T6)
# ═══════════════════════════════════════════════════════════════════
_COMPOUND_PATTERNS = [
    r"(?:también|además).*(?:para|quiero|necesito|darle|agendar|reservar)",
    r"(?:y|e|,).*(?:también|además)",
    r"para (?:él|ella|ellos|ellas)",
    r"y para (?:mi|el|la|un|una)",
    r"otr[oa]\s+(?:turno|persona|paciente|familiar)",
    r"también\s+(?:para|quiero|necesito)",
    r"(?:dos|2|ambos|las dos|los dos)\s+(?:turno|turnos|personas|pacientes)",
]
_COMPOUND_RE = re.compile("|".join(_COMPOUND_PATTERNS), re.IGNORECASE)


def detect_compound_intent(messages: list) -> bool:
    """Detect if the patient wants to book for multiple people (compound intent).
    
    Returns True if the messages suggest booking for more than one person.
    Example: "quiero turno para mí y también para mi mamá"
    """
    text = " ".join(messages).lower()
    return bool(_COMPOUND_RE.search(text))


# ═══════════════════════════════════════════════════════════════════
# v8.3: Frustration detection (resolve-13-booking-errors T14 fix)
# ═══════════════════════════════════════════════════════════════════

_FRUSTRATION_PATTERNS = [
    # Explicit frustration
    r"no\s+(entend[eií]s|entiendes|entend[íi]s|comprend[ei]s|captas|escuch[ai]s)",
    r"(ya\s+)?te\s+(dije|digo|expliqu[ée]|dijimos|estoy diciendo)",
    r"(est[áa]s\s+en\s+un\s+)?loop",
    r"(est[áa]s\s+|seg[uú]s\s+|volv[síi]s\s+)repet[ii]endo|repet[ií]s",
    r"(no\s+)?(es|era)\s+lo\s+que\s+(te\s+)?ped[ií]",
    r"no\s+es\s+(para\s+m[ií]|eso)",
    r"te\s+equivoc[ai]s|equivocado|mal\s+entend[íi]s",
    r"no\s+(quiero|necesito)\s+eso|no\s+es\s+lo\s+que\s+(quiero|necesito)",
    r"(hablo|habla|vas\s+a\s+entender)\s+con\s+(un|una)\s+(humano|persona|asesor[oa])",
    r"no\s+(me\s+)?(est[áa]s\s+)?(ayudando|entiendo|sirviendo)",
    r"dej[aá]\s+(de\s+)?(repetir|decir\s+lo\s+mismo|preguntar\s+lo\s+mismo)",
    r"(hace\s+)?rato\s+(que\s+)?(te\s+)?(lo\s+)?(estoy\s+)?(diciendo|explicando|pidiendo)",
]

# ALL-CAPS message (50%+ uppercase excluding numbers)
_ALL_CAPS_RE = re.compile(
    r"^(?=[^0-9]*[A-ZÁÉÍÓÚÑ])[A-ZÁÉÍÓÚÑ0-9\s.,;:!¡¿?()\"'-]{15,}$"
)

# Repeated punctuation indicator
_REPEATED_PUNCTUATION_RE = re.compile(r"[!¡?¿]{3,}")


def _detect_frustration(messages: list) -> int:
    """Analyze patient messages for frustration signals.

    Returns a count of frustration signals detected (0-3+):
    - 1 signal: mild frustration
    - 2 signals: moderate frustration  
    - 3+ signals: strong frustration → escalate

    Checks:
    1. Frustration keywords ("no entendés", "ya te dije", etc.)
    2. ALL-CAPS message (50%+ uppercase)
    3. Repeated punctuation (!!!, ???)
    4. Very short repetitive questions
    """
    if not messages:
        return 0

    signals = 0
    text = messages[-1] if isinstance(messages, list) else messages
    full_text = " ".join(messages) if isinstance(messages, list) else messages

    # 1. Frustration keyword patterns
    for pattern in _FRUSTRATION_PATTERNS:
        if re.search(pattern, text.lower()):
            signals += 1
            logger.info(
                f"🧩 Frustration signal (keyword match): {pattern[:40]!r}"
            )
            break  # Only count once for keyword category

    # 2. ALL-CAPS (50%+ uppercase among letters)
    if len(text) >= 15:
        letters = [c for c in text if c.isalpha()]
        if letters:
            upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
            if upper_ratio >= 0.5:
                signals += 1
                logger.info(
                    f"🧩 Frustration signal (ALL-CAPS, ratio={upper_ratio:.2f})"
                )

    # 3. Repeated punctuation
    if _REPEATED_PUNCTUATION_RE.search(text):
        signals += 1
        logger.info("🧩 Frustration signal (repeated punctuation)")

    # 4. Very short message (< 30 chars) that repeats from recent history
    if len(text.strip()) < 30 and len(messages) >= 2:
        prev_text = messages[-2].strip().lower() if isinstance(messages[-2], str) else ""
        curr_text = text.strip().lower()
        if prev_text and curr_text and prev_text == curr_text:
            signals += 1
            logger.info("🧩 Frustration signal (exact repeat of previous message)")

    return signals


# ═══════════════════════════════════════════════════════════════════
# v8.3: Agent error post-processing (resolve-13-booking-errors T13 fix)
# ═══════════════════════════════════════════════════════════════════

# Pattern for [BOOK_ERROR:CODE:CATEGORY] or [BOOK_ERROR:CODE]
_BOOK_ERROR_RE = re.compile(
    r"\[BOOK_ERROR:([A-Z_]+)(?::([A-Z_]+))?\]\s*(.*?)(?=\n|$|\.\s|,\s)",
    re.IGNORECASE,
)

# Pattern for false system error phrases that the LLM invents
_FALSE_SYSTEM_ERROR_PHRASES = [
    "error del sistema",
    "error del servidor",
    "ocurrió un error",
    "hubo un error",
    "problema técnico",
    "error interno",
    "error inesperado",
    "fallo del sistema",
    "ocurrió un problema",
    "el sistema falló",
    "no pude procesar",
    "no se pudo completar",
    "algo salió mal",
]

# Human-friendly replacements for SYSTEM_ERROR
_SYSTEM_ERROR_FALLBACK = (
    "Podés intentarlo de nuevo en unos minutos. "
    "Si el problema persiste, un asesor va a comunicarse con vos para ayudarte."
)


def _handle_agent_error(response_text: str) -> str:
    """Post-process LLM response to handle error codes and false system errors.

    1. Strip [BOOK_ERROR:CODE:CATEGORY] prefixes, keep human-readable part
    2. Replace SYSTEM_ERROR codes with proper fallback
    3. Replace false "error del sistema" phrases with proper message
    """
    if not response_text or len(response_text.strip()) < 5:
        return response_text

    original = response_text
    text = response_text

    # 1. Process [BOOK_ERROR:CODE:CATEGORY] patterns
    def _replace_book_error(match):
        code = match.group(1).upper()
        category = match.group(2).upper() if match.group(2) else ""
        human_msg = match.group(3).strip() if match.group(3) else ""

        if category == "SYSTEM_ERROR":
            # SYSTEM_ERROR: replace with fallback
            logger.warning(
                f"[handle_agent_error] SYSTEM_ERROR '{code}' intercepted: "
                f"replacing with fallback. Original: {match.group(0)[:80]!r}"
            )
            return _SYSTEM_ERROR_FALLBACK

        if category in ("INPUT_ERROR", "BUSINESS_RULE"):
            # Client-side error: keep the human message, drop the code prefix
            logger.info(
                f"[handle_agent_error] {category} '{code}' stripped: "
                f"keeping human message. Code: {match.group(0)[:60]!r}"
            )
            return human_msg if human_msg else ""

        # RECOVERABLE or no category: strip code prefix, keep human part
        if human_msg:
            return human_msg
        return ""  # Empty — caller should handle with retry

    text = _BOOK_ERROR_RE.sub(_replace_book_error, text)

    # 2. Clean up empty parenthetical artifacts from stripping
    text = re.sub(r"\(\)", "", text)
    text = re.sub(r"[ \t]+", " ", text).strip()

    # 3. Replace false "error del sistema" phrases
    text_lower = text.lower()
    for phrase in _FALSE_SYSTEM_ERROR_PHRASES:
        if phrase in text_lower:
            logger.warning(
                f"[handle_agent_error] False system error phrase '{phrase}' detected and replaced"
            )
            # Replace the phrase with the corrected message
            _pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            text = _pattern.sub(
                "necesito un minuto para verificar",
                text,
            )
            break  # Only fix one occurrence per call

    # 4. Remove trailing/leading garbage from stripping operations.
    # OJO: NO sacar . ! ? — son cierres de oración legítimos (antes se comía el "?"
    # de las preguntas y quedaban sin cerrar). Solo limpiamos , ; : que sí son basura.
    text = text.strip().strip(",;:").strip()
    if not text:
        text = _SYSTEM_ERROR_FALLBACK

    if text != original:
        logger.info(
            f"[handle_agent_error] Response post-processed: "
            f"len {len(original)} → {len(text)} chars"
        )

    return text


async def process_buffer_task(
    tenant_id: int,
    conversation_id: str,
    external_user_id: str,
    messages: List[str],
    provider: str = None,
    channel: str = None,
) -> None:
    pool = get_pool()
    row = await pool.fetchrow(
        """
         SELECT provider, external_chatwoot_id, external_account_id, channel,
               linked_patient_id, linked_at, family_patient_ids
         FROM chat_conversations
        WHERE id = $1 AND tenant_id = $2
        """,
        conversation_id,
        tenant_id,
    )
    if not row:
        logger.warning(
            "process_buffer_task_conversation_not_found", conv_id=conversation_id
        )
        return
    provider = row["provider"] or "chatwoot"
    logger.info(
        f"🦾 Processing Buffer Task | tenant={tenant_id} conv={conversation_id} user={external_user_id} provider={provider} msgs={len(messages)}"
    )

    if not messages:
        return

    # Spec 24: Human Override Check (Parity)
    # Check if human took control during buffer wait
    override_row = await pool.fetchrow(
        "SELECT human_override_until FROM chat_conversations WHERE id = $1",
        conversation_id,
    )
    if override_row and override_row["human_override_until"]:
        from datetime import datetime, timezone

        now_utc = datetime.now(timezone.utc)
        override_until = override_row["human_override_until"]
        if override_until.tzinfo is None:
            override_until = override_until.replace(tzinfo=timezone.utc)
        else:
            override_until = override_until.astimezone(timezone.utc)

        if override_until > now_utc:
            logger.info(
                f"🔇 Buffer task silenced by Human Override until {override_until} for {external_user_id}"
            )
            return

    # Reset lead recovery cycle — when the patient replies we stop the recovery
    # sequence so they aren't bombarded after they've re-engaged.
    try:
        await pool.execute(
            "UPDATE chat_conversations SET recovery_touch_count = 0, last_recovery_at = NULL "
            "WHERE tenant_id = $1 AND external_user_id = $2 AND recovery_touch_count > 0",
            tenant_id,
            external_user_id,
        )
    except Exception:
        pass  # Non-blocking — recovery reset is best-effort

    # Invocar agente con clave por tenant (Vault)
    try:
        from main import (
            get_agent_executable_for_tenant,
            build_system_prompt,
            get_now_arg,
            normalize_phone_digits,
            CLINIC_NAME,
            CLINIC_HOURS_START,
            CLINIC_HOURS_END,
            db,  # Import db wrapper for get_chat_history
            current_customer_phone,
            current_tenant_id,
            current_patient_id,
            current_family_patient_ids,
            current_source_channel,
            current_tenant_tz,
        )

        # C3: Engine router for dual-engine system (solo/multi)
        from services.engine_router import get_engine_for_tenant

        # ✅ FIX: Establecer ContextVars para que las tools (book_appointment, etc)
        # puedan identificar al paciente en la tarea background
        current_customer_phone.set(external_user_id)
        current_tenant_id.set(tenant_id)
        current_source_channel.set(channel or "whatsapp")

        # ── Patient resolution: linked_patient_id or phone fallback ──
        resolved_patient_phone = None
        linked_patient_id = row.get("linked_patient_id")
        if linked_patient_id:
            linked_patient_row = await pool.fetchrow(
                "SELECT id, phone_number FROM patients WHERE id = $1 AND tenant_id = $2",
                linked_patient_id,
                tenant_id,
            )
            if linked_patient_row:
                current_patient_id.set(linked_patient_row["id"])
                resolved_patient_phone = linked_patient_row["phone_number"]
                logger.info(
                    f"🔗 Patient resolved via linked_patient_id={linked_patient_id} phone={resolved_patient_phone}"
                )
        if current_patient_id.get() is None:
            patient_by_phone = await pool.fetchrow(
                "SELECT id, phone_number FROM patients WHERE tenant_id = $1 AND phone_number = $2",
                tenant_id,
                external_user_id,
            )
            if patient_by_phone:
                current_patient_id.set(patient_by_phone["id"])
                resolved_patient_phone = patient_by_phone["phone_number"]
                logger.info(
                    f"📞 Patient resolved via phone={external_user_id} id={patient_by_phone['id']}"
                )

        # v8.3: 2-of-3 patient resolution scoring (resolve-13-booking-errors T9)
        # Try name + DNI + phone scoring if initial resolution didn't find a match
        if current_patient_id.get() is None:
            try:
                _messages_text = " ".join(messages)
                _dni_matches = re.findall(r"\b(\d{7,11})\b", _messages_text)
                # Score existing patients by matching phone, DNI, and name fragments
                _candidates = await pool.fetch(
                    """SELECT id, first_name, last_name, phone_number, dni
                       FROM patients WHERE tenant_id = $1 LIMIT 100""",
                    tenant_id,
                )
                _best_score = 0
                _best_id = None
                for _c in _candidates:
                    _score = 0
                    # Phone match
                    if _c["phone_number"] and external_user_id in _c["phone_number"]:
                        _score += 1
                    # DNI match
                    if _dni_matches and _c.get("dni") and any(d in _c["dni"] for d in _dni_matches):
                        _score += 1
                    # Name match (any word from messages in patient name)
                    _full_name = f"{_c.get('first_name', '')} {_c.get('last_name', '')}".lower()
                    _name_words = set(w for w in _messages_text.lower().split() if len(w) > 2)
                    if _name_words and any(w in _full_name for w in _name_words):
                        _score += 1
                    if _score > _best_score:
                        _best_score = _score
                        _best_id = _c["id"]
                if _best_id and _best_score >= 2:
                    current_patient_id.set(_best_id)
                    logger.info(f"📊 T9 patient resolved via 2-of-3 scoring: id={_best_id} score={_best_score}")
            except Exception as _t9_err:
                logger.debug(f"T9 2-of-3 resolution skipped: {_t9_err}")

        # ── Family resolution: load family_patient_ids ──
        family_ids_raw = row.get("family_patient_ids")
        if family_ids_raw:
            # Convert asyncpg ARRAY to Python list
            family_ids_list = list(family_ids_raw)
            current_family_patient_ids.set(family_ids_list)
            logger.info(
                f"👨‍👩‍👧‍👦 Family members loaded for conv {conversation_id}: {family_ids_list}"
            )

        # TIER 3 cap.1 — resolve tenant timezone once per request and bind it.
        # All datetime constructors via get_active_tz() / get_now_arg() will honor it.
        try:
            from services.tz_resolver import get_tenant_tz as _get_tz

            _resolved_tz = await _get_tz(tenant_id)
            current_tenant_tz.set(_resolved_tz)
        except Exception as _tz_err:
            # Never block the booking flow on tz resolution failure — fallback to ARG_TZ.
            import logging as _lg

            _lg.getLogger("buffer_task").warning(
                f"tz_resolver: failed for tenant {tenant_id}, falling back to ARG_TZ: {_tz_err}"
            )

        tenant_row = await pool.fetchrow(
            """SELECT clinic_name, address, google_maps_url, working_hours,
                      consultation_price, bank_cbu, bank_alias, bank_holder_name,
                      system_prompt_template, bot_name,
                      payment_methods, financing_available, max_installments,
                      installments_interest_free, financing_provider, financing_notes,
                      cash_discount_percent, accepts_crypto,
                      accepts_pregnant_patients, pregnancy_restricted_treatments,
                      pregnancy_notes, accepts_pediatric, min_pediatric_age_years,
                      pediatric_notes, high_risk_protocols, requires_anamnesis_before_booking,
                      complaint_escalation_email, complaint_escalation_phone,
                      expected_wait_time_minutes, revision_policy, review_platforms,
                      complaint_handling_protocol, auto_send_review_link_after_followup,
                      social_ig_active, social_landings, instagram_handle, facebook_page_id,
                      bot_phone_number, config
               FROM tenants WHERE id = $1""",
            tenant_id,
        )
        clinic_name = (
            (tenant_row["clinic_name"] or CLINIC_NAME) if tenant_row else CLINIC_NAME
        )
        # Editable bot display name (migration 033). NULL or empty → fallback to "TORA".
        bot_name = (tenant_row.get("bot_name") or "TORA") if tenant_row else "TORA"
        clinic_address = (tenant_row["address"] or "") if tenant_row else ""
        clinic_maps_url = (tenant_row["google_maps_url"] or "") if tenant_row else ""
        consultation_price = (
            float(tenant_row["consultation_price"])
            if tenant_row and tenant_row.get("consultation_price")
            else None
        )
        bank_cbu = (tenant_row["bank_cbu"] or "") if tenant_row else ""
        bank_alias = (tenant_row["bank_alias"] or "") if tenant_row else ""
        bank_holder_name = (tenant_row["bank_holder_name"] or "") if tenant_row else ""

        # Payment & financing (migración 035). asyncpg puede devolver JSONB como
        # string en algunas versiones → parse defensivo idéntico al de working_hours.
        _pm_raw = tenant_row.get("payment_methods") if tenant_row else None
        if isinstance(_pm_raw, str):
            try:
                _pm_raw = json.loads(_pm_raw)
            except (json.JSONDecodeError, TypeError):
                _pm_raw = []
        payment_methods = _pm_raw if isinstance(_pm_raw, list) else []
        financing_available = bool(
            tenant_row.get("financing_available") if tenant_row else False
        )
        max_installments = tenant_row.get("max_installments") if tenant_row else None
        _iif = tenant_row.get("installments_interest_free") if tenant_row else None
        installments_interest_free = bool(_iif) if _iif is not None else True
        financing_provider = (
            (tenant_row.get("financing_provider") or "") if tenant_row else ""
        )
        financing_notes = (
            (tenant_row.get("financing_notes") or "") if tenant_row else ""
        )
        _cdp = tenant_row.get("cash_discount_percent") if tenant_row else None
        try:
            cash_discount_percent = float(_cdp) if _cdp is not None else None
        except (TypeError, ValueError):
            cash_discount_percent = None
        accepts_crypto = bool(tenant_row.get("accepts_crypto") if tenant_row else False)

        # --- Clinic special conditions (migración 036) ---
        # Computamos el bloque pre-formateado acá para que build_system_prompt
        # sólo reciba un string (wiring simple, testeable y non-fatal).
        special_conditions_block = ""
        try:
            if tenant_row:
                # Resolver treatment_name_map para mostrar nombres amigables
                treatment_name_map: dict = {}
                try:
                    _tt_rows = await pool.fetch(
                        "SELECT code, COALESCE(patient_display_name, name) AS display_name "
                        "FROM treatment_types WHERE tenant_id = $1 AND is_active = true",
                        tenant_id,
                    )
                    treatment_name_map = {
                        r["code"]: r["display_name"] for r in _tt_rows
                    }
                except Exception:
                    treatment_name_map = {}

                from main import _format_special_conditions

                special_conditions_block = _format_special_conditions(
                    dict(tenant_row),
                    treatment_name_map=treatment_name_map,
                )
        except Exception as _sc_err:
            logger.debug(f"_format_special_conditions skipped (non-fatal): {_sc_err}")
            special_conditions_block = ""

        # --- Clinic support / complaints / review config (migration 039) ---
        support_policy_block = ""
        try:
            if tenant_row:
                from main import _format_support_policy

                support_policy_block = _format_support_policy(dict(tenant_row))
        except Exception as _sp_err:
            logger.debug(f"_format_support_policy skipped (non-fatal): {_sp_err}")
            support_policy_block = ""

        system_prompt_template = (
            (tenant_row.get("system_prompt_template") or "") if tenant_row else ""
        )
        # Normalize whitespace in the tenant-configured greeting/specialty pitch.
        # The UI textarea may save it with hard line-breaks and leading spaces
        # (Python triple-quoted style), which then leak into the WhatsApp/IG/FB
        # message as visible indented broken lines. We collapse single newlines
        # into spaces, preserve intentional double-newlines as paragraph breaks,
        # and strip per-line leading/trailing whitespace.
        if system_prompt_template:
            import re as _re

            _paragraphs = _re.split(r"\n\s*\n", system_prompt_template)
            _clean_paragraphs = []
            for _p in _paragraphs:
                # Join wrapped lines into a single line, collapse repeated spaces
                _flat = " ".join(
                    line.strip() for line in _p.splitlines() if line.strip()
                )
                _flat = _re.sub(r"[ \t]{2,}", " ", _flat).strip()
                if _flat:
                    _clean_paragraphs.append(_flat)
            system_prompt_template = "\n\n".join(_clean_paragraphs)
        clinic_working_hours = None
        if tenant_row and tenant_row.get("working_hours"):
            wh = tenant_row["working_hours"]
            clinic_working_hours = json.loads(wh) if isinstance(wh, str) else wh

        # Resolve lead professional name for prompt positioning
        lead_professional_name = ""
        try:
            prof_row = await pool.fetchrow(
                "SELECT first_name, last_name FROM professionals WHERE tenant_id = $1 AND is_active = true ORDER BY id ASC LIMIT 1",
                tenant_id,
            )
            if prof_row:
                lead_professional_name = f"{prof_row['first_name']} {prof_row.get('last_name', '') or ''}".strip()
        except Exception:
            pass

        # Fetch FAQs for this tenant (no limit — RAG will select relevant ones)
        faq_rows = await pool.fetch(
            "SELECT category, question, answer FROM clinic_faqs WHERE tenant_id = $1 ORDER BY sort_order ASC, id ASC",
            tenant_id,
        )
        faqs = [dict(r) for r in faq_rows] if faq_rows else []

        # Fetch insurance providers for this tenant (migration 034 shape)
        insurance_providers = []
        try:
            ins_rows = await pool.fetch(
                """
                SELECT id, provider_name, status, coverage_by_treatment, is_prepaid,
                       employee_discount_percent, default_copay_percent, external_target,
                       requires_copay, copay_notes, ai_response_template,
                       scheduling_mode, scheduling_delay_days
                FROM tenant_insurance_providers
                WHERE tenant_id = $1 AND is_active = true
                ORDER BY sort_order, provider_name
                """,
                tenant_id,
            )
            insurance_providers = []
            for r in ins_rows or []:
                d = dict(r)
                # asyncpg may return JSONB as a string in some versions
                if isinstance(d.get("coverage_by_treatment"), str):
                    try:
                        import json as _json_cov

                        d["coverage_by_treatment"] = _json_cov.loads(
                            d["coverage_by_treatment"]
                        )
                    except (ValueError, TypeError):
                        d["coverage_by_treatment"] = {}
                insurance_providers.append(d)
        except Exception as ins_err:
            logger.debug(f"Insurance providers fetch (non-fatal): {ins_err}")

        # Fetch active treatment types for treatment_display_map in the prompt
        # (used by _format_insurance_providers to render human-readable names).
        treatment_types_list = []
        try:
            tt_rows = await pool.fetch(
                """
                SELECT code, name, patient_display_name, consultation_requirements
                FROM treatment_types
                WHERE tenant_id = $1 AND is_active = true
                ORDER BY name
                """,
                tenant_id,
            )
            treatment_types_list = [dict(r) for r in tt_rows] if tt_rows else []
        except Exception as tt_err:
            logger.debug(f"Treatment types fetch (non-fatal): {tt_err}")

        # Fetch derivation rules for this tenant (migration 038: includes
        # escalation fallback fields and enriches with fallback_professional_name
        # via a second LEFT JOIN so the prompt formatter can render the
        # full escalation block).
        derivation_rules = []
        try:
            der_rows = await pool.fetch(
                """
                SELECT dr.id, dr.rule_name, dr.patient_condition, dr.treatment_categories,
                       dr.target_type, dr.target_professional_id, dr.priority_order,
                       dr.enable_escalation, dr.fallback_professional_id,
                       dr.fallback_team_mode, dr.max_wait_days_before_escalation,
                       dr.escalation_message_template,
                       p.first_name AS target_professional_name,
                       fp.first_name AS fallback_professional_name
                FROM professional_derivation_rules dr
                LEFT JOIN professionals p ON dr.target_professional_id = p.id
                LEFT JOIN professionals fp ON dr.fallback_professional_id = fp.id
                WHERE dr.tenant_id = $1 AND dr.is_active = true
                ORDER BY dr.priority_order ASC, dr.id ASC
                """,
                tenant_id,
            )
            derivation_rules = [dict(r) for r in der_rows] if der_rows else []
        except Exception as der_err:
            logger.debug(f"Derivation rules fetch (non-fatal): {der_err}")

        # --- OPERATIONAL RULES (temporary/strategic) ---
        operational_rules_block = ""
        try:
            op_rows = await pool.fetch(
                """SELECT rule_name, rule_type, prompt_injection, valid_until
                   FROM clinic_operational_rules
                   WHERE tenant_id = $1 AND is_active = true
                     AND (valid_from IS NULL OR valid_from <= NOW())
                     AND (valid_until IS NULL OR valid_until >= NOW())
                     AND ('all' = ANY(applies_to) OR 'tora' = ANY(applies_to))
                   ORDER BY priority_order ASC, id ASC""",
                tenant_id,
            )
            if op_rows:
                parts = ["⚠️ REGLAS OPERATIVAS VIGENTES (deben aplicarse SIEMPRE):"]
                for opr in op_rows:
                    until = (
                        f" (vigente hasta {opr['valid_until'].strftime('%d/%m/%Y')})"
                        if opr.get("valid_until")
                        else ""
                    )
                    parts.append(
                        f"[{opr['rule_type'].upper()}] {opr['rule_name']}{until}:"
                    )
                    parts.append(opr["prompt_injection"])
                    parts.append("")
                operational_rules_block = "\n".join(parts)
        except Exception as op_err:
            logger.debug(f"Operational rules fetch (non-fatal): {op_err}")

        # --- PATIENT MEMORY SYSTEM: Ensure table exists (first call only) ---
        try:
            from services.patient_memory import (
                ensure_memory_table,
                format_memories_for_prompt,
                extract_and_store_memories,
            )

            await ensure_memory_table(pool)
        except Exception as mem_init_err:
            logger.warning(f"⚠️ Patient memory init (non-fatal): {mem_init_err}")

        # Spec 24 / Spec 06 / v7.6: Patient Identity & Appointment Context
        # Fetch patient data — search by phone (WhatsApp) or PSID (Instagram/Facebook)
        # or by external_ids JSONB (for IG/FB patients linked post-creation)
        phone_digits = normalize_phone_digits(external_user_id)
        patient_row = await pool.fetchrow(
            """SELECT id, first_name, last_name, dni, email, phone_number, birth_date, acquisition_source, anamnesis_token, medical_history, assigned_professional_id, insurance_provider FROM patients
               WHERE tenant_id = $1 AND (
                   REGEXP_REPLACE(phone_number, '[^0-9]', '', 'g') = $2
                   OR phone_number = $3
                   OR instagram_psid = $3
                   OR facebook_psid = $3
                   OR external_ids->>'instagram' = $3
                   OR external_ids->>'facebook' = $3
                   OR external_ids->>'chatwoot' = $3
               )
               ORDER BY updated_at DESC NULLS LAST
               LIMIT 1""",
            tenant_id,
            phone_digits,
            external_user_id,
        )

        patient_context = ""
        ad_context = ""
        patient_status = "new_lead"
        anamnesis_url = ""

        if patient_row:
            p_id = patient_row["id"]
            p_first = patient_row["first_name"] or ""
            p_last = patient_row["last_name"] or ""
            p_dni = patient_row["dni"] or ""

            # 1. Building Identity Context
            identity_lines = []
            if p_first or p_last:
                identity_lines.append(
                    f"• Nombre registrado: {p_first} {p_last}".strip()
                )
            if p_dni:
                identity_lines.append(f"• DNI registrado: {p_dni}")

            # Phone — check if patient has a real phone number in DB
            p_phone = patient_row.get("phone_number") or ""
            p_phone_is_real = p_phone and not p_phone.startswith("SIN-TEL")
            if p_phone_is_real:
                identity_lines.append(f"• Teléfono registrado: {p_phone}")

            # Email
            p_email = patient_row.get("email") or ""
            if p_email:
                identity_lines.append(f"• Email registrado: {p_email}")

            # Birth date
            if patient_row.get('birth_date'):
                identity_lines.append(f"• Fecha de nacimiento: {patient_row['birth_date']}")

            # Obra Social / Prepaga / Cobertura
            p_insurance = patient_row.get("insurance_provider") or ""
            if p_insurance:
                identity_lines.append(f"• Obra Social registrada: {p_insurance}")

            # Assigned Professional (persistent patient→professional relationship)
            assigned_prof_id = patient_row.get("assigned_professional_id")
            if assigned_prof_id:
                try:
                    assigned_prof = await pool.fetchrow(
                        "SELECT first_name, last_name FROM professionals WHERE id = $1 AND tenant_id = $2 AND is_active = true",
                        assigned_prof_id,
                        tenant_id,
                    )
                    if assigned_prof:
                        assigned_name = f"{assigned_prof['first_name']} {assigned_prof.get('last_name', '') or ''}".strip()
                        identity_lines.append(
                            f"• PROFESIONAL ASIGNADO: Dr/a. {assigned_name} — Este paciente es paciente habitual de este profesional. "
                            f"PRIORIDAD ALTA por ser paciente propio (independientemente de la complejidad del tratamiento). "
                            f"Si menciona DOLOR → prioridad inmediata/urgencia. Sin dolor → prioridad media. "
                            f"SIEMPRE ofrecer turnos con este profesional primero. Si no hay disponibilidad, "
                            f"mencionar que es su profesional habitual y ofrecer la próxima fecha disponible."
                        )
                except Exception:
                    pass

            # 2. Building Ad Context (Spec 06)
            meta_headline = ""  # Already in patient_row if we joined or updated, checking current db state
            # Acquisition source check
            meta_source = patient_row.get("acquisition_source") or ""

            # Quick check for meta headline if not in main row (some schemas store it differently)
            # For simplicity, we assume attributes might have it or use what's in 'patients'

            # 3. Fetching Next Appointment Context
            next_apt = await pool.fetchrow(
                """
                SELECT a.appointment_datetime, tt.name as treatment_name, 
                       prof.first_name as professional_name
                FROM appointments a
                LEFT JOIN treatment_types tt ON a.appointment_type = tt.code
                LEFT JOIN professionals prof ON a.professional_id = prof.id
                WHERE a.tenant_id = $1 AND a.patient_id = $2 
                AND a.appointment_datetime >= NOW()
                AND a.status IN ('scheduled', 'confirmed')
                ORDER BY a.appointment_datetime ASC
                LIMIT 1
            """,
                tenant_id,
                p_id,
            )

            if next_apt:
                dt = next_apt["appointment_datetime"]
                from main import get_active_tz

                if hasattr(dt, "astimezone"):
                    dt = dt.astimezone(get_active_tz())
                dias_semana = [
                    "Lunes",
                    "Martes",
                    "Miércoles",
                    "Jueves",
                    "Viernes",
                    "Sábado",
                    "Domingo",
                ]
                dia_nombre = dias_semana[dt.weekday()]
                dt_str = f"{dia_nombre} {dt.strftime('%d/%m/%Y')} a las {dt.strftime('%H:%M')}"
                # Tiempo hasta turno para saludo proactivo
                now_arg = get_now_arg()
                delta = dt - now_arg
                total_hours = delta.total_seconds() / 3600.0
                if total_hours < 0.5:
                    time_until = "menos de 30 minutos"
                elif total_hours < 1:
                    time_until = "menos de 1 hora"
                elif total_hours < 24:
                    h = int(total_hours)
                    time_until = f"faltan {h} {'hora' if h == 1 else 'horas'}"
                elif total_hours < 48:
                    time_until = f"mañana a las {dt.strftime('%H:%M')}"
                else:
                    time_until = f"el {dt_str}"
                identity_lines.append(
                    f"• PRÓXIMO TURNO: Tiene un turno de {next_apt['treatment_name'] or 'Consulta'} con el/la Dr/a. {next_apt['professional_name']} el {dt_str}."
                )
                identity_lines.append(
                    f"• FECHA EXACTA DEL TURNO: {dt.strftime('%d/%m/%Y')} a las {dt.strftime('%H:%M')}. {time_until}."
                )

            # 3b. Fetch LAST completed appointment (for post-treatment follow-up)
            last_apt = await pool.fetchrow(
                """
                SELECT a.appointment_datetime, tt.name as treatment_name,
                       prof.first_name as professional_name, a.status
                FROM appointments a
                LEFT JOIN treatment_types tt ON a.appointment_type = tt.code
                LEFT JOIN professionals prof ON a.professional_id = prof.id
                WHERE a.tenant_id = $1 AND a.patient_id = $2
                AND a.appointment_datetime < NOW()
                AND a.status IN ('completed', 'confirmed', 'scheduled')
                ORDER BY a.appointment_datetime DESC
                LIMIT 1
            """,
                tenant_id,
                p_id,
            )

            if last_apt:
                ldt = last_apt["appointment_datetime"]
                if hasattr(ldt, "astimezone"):
                    from main import get_active_tz as _get_tz

                    ldt = ldt.astimezone(_get_tz())
                ldias = [
                    "Lunes",
                    "Martes",
                    "Miércoles",
                    "Jueves",
                    "Viernes",
                    "Sábado",
                    "Domingo",
                ]
                ldt_str = f"{ldias[ldt.weekday()]} {ldt.strftime('%d/%m/%Y')} a las {ldt.strftime('%H:%M')}"
                days_since = (
                    (now_arg - ldt).days
                    if "now_arg" in dir()
                    else (get_now_arg() - ldt).days
                )
                identity_lines.append(
                    f"• ÚLTIMO TURNO: {last_apt['treatment_name'] or 'Consulta'} con Dr/a. {last_apt['professional_name']} el {ldt_str} (hace {days_since} días). Estado: {last_apt['status']}."
                )
                if days_since <= 7:
                    identity_lines.append(
                        f"• SEGUIMIENTO POST-TRATAMIENTO: El paciente tuvo un turno hace {days_since} días. Si escribe, preguntale cómo se siente después del tratamiento."
                    )

            # 3c. Count total visits (recurrent vs first-timer)
            visit_count = await pool.fetchval(
                """
                SELECT COUNT(*) FROM appointments
                WHERE tenant_id = $1 AND patient_id = $2
                AND status IN ('completed', 'confirmed', 'scheduled')
            """,
                tenant_id,
                p_id,
            )
            if visit_count and visit_count > 1:
                identity_lines.append(
                    f"• HISTORIAL: Paciente recurrente ({visit_count} turnos registrados)."
                )
            elif visit_count == 1:
                identity_lines.append("• HISTORIAL: Primera visita del paciente.")

            # Determine patient_status
            if next_apt:
                patient_status = "patient_with_appointment"
                # Resolve sede for appointment day
                if clinic_working_hours:
                    days_en = [
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                    ]
                    apt_day_en = days_en[dt.weekday()]
                    apt_day_cfg = clinic_working_hours.get(apt_day_en, {})
                    if apt_day_cfg.get("location"):
                        identity_lines.append(
                            f"• SEDE DEL TURNO: {apt_day_cfg['location']}"
                        )
                        if apt_day_cfg.get("address"):
                            identity_lines.append(
                                f"• DIRECCIÓN SEDE: {apt_day_cfg['address']}"
                            )
                        if apt_day_cfg.get("maps_url"):
                            identity_lines.append(
                                f"• MAPS SEDE: {apt_day_cfg['maps_url']}"
                            )
                    elif clinic_address:
                        # Fallback: day has no specific location, use general address
                        identity_lines.append(
                            f"• SEDE DEL TURNO: {clinic_address}"
                        )
            else:
                patient_status = "patient_no_appointment"

            # Generate anamnesis URL (always — patient may need to update)
            import uuid as uuid_mod

            anamnesis_token = (
                patient_row.get("anamnesis_token") if patient_row else None
            )
            if not anamnesis_token:
                anamnesis_token = str(uuid_mod.uuid4())
                await pool.execute(
                    "UPDATE patients SET anamnesis_token = $1 WHERE id = $2 AND tenant_id = $3",
                    anamnesis_token,
                    p_id,
                    tenant_id,
                )
            frontend_url = (
                os.getenv("FRONTEND_URL", "http://localhost:4173")
                .split(",")[0]
                .strip()
                .rstrip("/")
            )
            anamnesis_url = f"{frontend_url}/anamnesis/{tenant_id}/{anamnesis_token}"

            # Check if anamnesis is already completed
            mh = patient_row.get("medical_history")
            if isinstance(mh, str):
                mh = json.loads(mh) if mh else {}
            anamnesis_completed = bool(
                mh and isinstance(mh, dict) and mh.get("anamnesis_completed_at")
            )
            if anamnesis_completed:
                identity_lines.append(
                    "• ANAMNESIS: Ya completó su ficha médica (NO enviar link automáticamente al agendar, SOLO si el paciente pide actualizar)."
                )

            # Load linked minor patients (children) via guardian_phone
            # Use ANY() to match both chat phone and resolved patient phone when linked
            # Normalize phone values to strip non-digits for reliable matching
            _guardian_phones = [re.sub(r'\D', '', p) for p in [external_user_id]]
            if resolved_patient_phone and re.sub(r'\D', '', resolved_patient_phone) not in _guardian_phones:
                _guardian_phones.append(re.sub(r'\D', '', resolved_patient_phone))
            minor_rows = await pool.fetch(
                "SELECT id, first_name, last_name, dni, phone_number, anamnesis_token FROM patients WHERE tenant_id = $1 AND REGEXP_REPLACE(COALESCE(guardian_phone, ''), '[^0-9]', '', 'g') = ANY(SELECT REGEXP_REPLACE(v, '[^0-9]', '', 'g') FROM unnest($2::text[]) AS v)",
                tenant_id,
                _guardian_phones,
            )
            if minor_rows:
                identity_lines.append("• HIJOS/MENORES VINCULADOS:")
                for minor in minor_rows:
                    m_name = (
                        f"{minor['first_name']} {minor.get('last_name', '')}".strip()
                    )
                    m_token = minor.get("anamnesis_token")
                    if not m_token:
                        m_token = str(uuid_mod.uuid4())
                        await pool.execute(
                            "UPDATE patients SET anamnesis_token = $1 WHERE id = $2",
                            m_token,
                            minor["id"],
                        )
                    m_anamnesis = f"{frontend_url}/anamnesis/{tenant_id}/{m_token}"
                    identity_lines.append(
                        f"  - {m_name} (DNI: {minor.get('dni', 'N/A')}, phone_interno: {minor['phone_number']}, link ficha: {m_anamnesis})"
                    )
                    # Check minor's next appointment
                    minor_apt = await pool.fetchrow(
                        """
                        SELECT a.appointment_datetime, tt.name as treatment_name, prof.first_name as professional_name
                        FROM appointments a
                        LEFT JOIN treatment_types tt ON a.appointment_type = tt.code
                        LEFT JOIN professionals prof ON a.professional_id = prof.id
                        WHERE a.tenant_id = $1 AND a.patient_id = $2 AND a.appointment_datetime >= NOW() AND a.status IN ('scheduled', 'confirmed')
                        ORDER BY a.appointment_datetime ASC LIMIT 1
                    """,
                        tenant_id,
                        minor["id"],
                    )
                    if minor_apt:
                        mdt = minor_apt["appointment_datetime"]
                        if hasattr(mdt, "astimezone"):
                            from main import get_active_tz as _get_tz

                            mdt = mdt.astimezone(_get_tz())
                        identity_lines.append(
                            f"    Próximo turno: {minor_apt['treatment_name'] or 'Consulta'} el {dias_semana[mdt.weekday()]} {mdt.strftime('%d/%m')} a las {mdt.strftime('%H:%M')}"
                        )

            # --- TREATMENT PLAN / BUDGET CONTEXT ---
            try:
                plan_row = await pool.fetchrow(
                    """
                    SELECT tp.id, tp.name, tp.status, tp.estimated_total, tp.approved_total,
                           tp.notes,
                           COALESCE(SUM(tpp.amount), 0) AS total_paid
                    FROM treatment_plans tp
                    LEFT JOIN treatment_plan_payments tpp ON tpp.plan_id = tp.id AND tpp.tenant_id = tp.tenant_id
                    WHERE tp.tenant_id = $1 AND tp.patient_id = $2
                      AND tp.status IN ('draft', 'approved', 'in_progress')
                    GROUP BY tp.id
                    ORDER BY tp.created_at DESC
                    LIMIT 1
                    """,
                    tenant_id,
                    p_id,
                )
                if plan_row:
                    approved = float(
                        plan_row["approved_total"] or plan_row["estimated_total"] or 0
                    )
                    paid = float(plan_row["total_paid"] or 0)
                    pending = round(approved - paid, 2)

                    # Parse budget config from notes JSON
                    budget_cfg = {}
                    if plan_row["notes"]:
                        try:
                            budget_cfg = (
                                json.loads(plan_row["notes"])
                                if isinstance(plan_row["notes"], str)
                                else plan_row["notes"]
                            )
                        except Exception:
                            budget_cfg = {}

                    installments = int(budget_cfg.get("installments") or 1)
                    per_installment = (
                        round(pending / installments, 2)
                        if installments > 0 and pending > 0
                        else 0
                    )

                    identity_lines.append("")
                    identity_lines.append("PRESUPUESTO ACTIVO:")
                    identity_lines.append(f"  Plan: {plan_row['name']}")
                    identity_lines.append(f"  Estado: {plan_row['status']}")
                    identity_lines.append(
                        f"  Total aprobado: ${approved:,.0f}".replace(",", ".")
                    )
                    identity_lines.append(f"  Pagado: ${paid:,.0f}".replace(",", "."))
                    identity_lines.append(
                        f"  Pendiente: ${pending:,.0f}".replace(",", ".")
                    )
                    if installments > 1:
                        identity_lines.append(
                            f"  Cuotas: {installments} (${per_installment:,.0f}/cuota)".replace(
                                ",", "."
                            )
                        )
                    discount_pct = float(budget_cfg.get("discount_pct") or 0)
                    discount_amt = float(budget_cfg.get("discount_amount") or 0)
                    if discount_pct > 0:
                        identity_lines.append(f"  Descuento: {discount_pct}%")
                    if discount_amt > 0:
                        identity_lines.append(
                            f"  Descuento fijo: ${discount_amt:,.0f}".replace(",", ".")
                        )
                    conditions = budget_cfg.get("payment_conditions")
                    if conditions:
                        identity_lines.append(f"  Condiciones: {conditions}")
                    logger.info(
                        f"💰 Treatment plan context injected for patient {p_id}"
                    )
            except Exception as plan_err:
                logger.warning(f"⚠️ Treatment plan context (non-fatal): {plan_err}")

            # --- PATIENT MEMORY: Retrieve persistent memories ---
            try:
                memory_query = " ".join(messages) if messages else ""
                memory_text = await format_memories_for_prompt(
                    pool, external_user_id, tenant_id, query=memory_query
                )
                if memory_text:
                    identity_lines.append("")
                    identity_lines.append(memory_text)
                    logger.info(f"🧠 Patient memories injected for {external_user_id}")
            except Exception as mem_err:
                logger.warning(f"⚠️ Memory retrieval (non-fatal): {mem_err}")

            # --- FAMILY MEMBERS: inject context for additional linked patients (F4, F7) ---
            try:
                _family_ids = current_family_patient_ids.get()
                if _family_ids:
                    family_lines = []
                    for _fid in _family_ids:
                        _frow = await pool.fetchrow(
                            "SELECT id, first_name, last_name, phone_number FROM patients WHERE id = $1 AND tenant_id = $2",
                            _fid,
                            tenant_id,
                        )
                        if not _frow:
                            continue
                        _fname = f"{_frow['first_name'] or ''} {_frow['last_name'] or ''}".strip()
                        _fphone = _frow.get("phone_number") or ""
                        _fctx = f"• {_fname}" + (f" (tel: {_fphone})" if _fphone else "")
                        family_lines.append(_fctx)

                        # Fetch next appointment for this family member
                        _f_next = await pool.fetchrow(
                            """SELECT a.appointment_datetime, tt.name as treatment_name,
                                      prof.first_name as professional_name
                               FROM appointments a
                               LEFT JOIN treatment_types tt ON a.appointment_type = tt.code
                               LEFT JOIN professionals prof ON a.professional_id = prof.id
                               WHERE a.tenant_id = $1 AND a.patient_id = $2
                               AND a.appointment_datetime >= NOW()
                               AND a.status IN ('scheduled', 'confirmed')
                               ORDER BY a.appointment_datetime ASC LIMIT 1""",
                            tenant_id, _fid,
                        )
                        if _f_next:
                            _dt = _f_next["appointment_datetime"]
                            if hasattr(_dt, "astimezone"):
                                from main import get_active_tz as _fam_tz
                                _dt = _dt.astimezone(_fam_tz())
                            _dias = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
                            _dt_str = f"{_dias[_dt.weekday()]} {_dt.strftime('%d/%m/%Y')} a las {_dt.strftime('%H:%M')}"
                            family_lines.append(
                                f"  └ PRÓXIMO TURNO: {_f_next['treatment_name'] or 'Consulta'} con Dr/a. {_f_next['professional_name']} el {_dt_str}."
                            )

                        # Fetch last completed appointment
                        _f_last = await pool.fetchrow(
                            """SELECT a.appointment_datetime, tt.name as treatment_name,
                                      prof.first_name as professional_name, a.status
                               FROM appointments a
                               LEFT JOIN treatment_types tt ON a.appointment_type = tt.code
                               LEFT JOIN professionals prof ON a.professional_id = prof.id
                               WHERE a.tenant_id = $1 AND a.patient_id = $2
                               AND a.appointment_datetime < NOW()
                               AND a.status IN ('completed', 'confirmed', 'scheduled')
                               ORDER BY a.appointment_datetime DESC LIMIT 1""",
                            tenant_id, _fid,
                        )
                        if _f_last:
                            _ldt = _f_last["appointment_datetime"]
                            if hasattr(_ldt, "astimezone"):
                                from main import get_active_tz as _fam_tz2
                                _ldt = _ldt.astimezone(_fam_tz2())
                            _ldias = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
                            _ldt_str = f"{_ldias[_ldt.weekday()]} {_ldt.strftime('%d/%m/%Y')} a las {_ldt.strftime('%H:%M')}"
                            _days_since = (get_now_arg() - _ldt).days
                            family_lines.append(
                                f"  └ ÚLTIMO TURNO: {_f_last['treatment_name'] or 'Consulta'} el {_ldt_str} (hace {_days_since} días). Estado: {_f_last['status']}."
                            )

                        # Visit count
                        _f_visits = await pool.fetchval(
                            "SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND patient_id = $2 AND status IN ('completed','confirmed','scheduled')",
                            tenant_id, _fid,
                        )
                        if _f_visits and _f_visits > 0:
                            family_lines.append(f"  └ Historial: {_f_visits} turnos registrados.")

                        # Latest clinical record
                        _f_cr = await pool.fetchrow(
                            """SELECT treatment_plan, diagnosis FROM clinical_records
                               WHERE tenant_id = $1 AND patient_id = $2
                               ORDER BY created_at DESC LIMIT 1""",
                            tenant_id, _fid,
                        )
                        if _f_cr:
                            if _f_cr.get("diagnosis"):
                                family_lines.append(f"  └ Diagnóstico: {_f_cr['diagnosis']}")
                            if _f_cr.get("treatment_plan"):
                                family_lines.append(f"  └ Plan de tratamiento: {_f_cr['treatment_plan']}")

                    if family_lines:
                        identity_lines.append("")
                        identity_lines.append("📋 Familiares a cargo desde este chat:")
                        identity_lines.extend(family_lines)
                        identity_lines.append("")
                        identity_lines.append(
                            "REGLAS PARA FAMILIARES: "
                            "1) list_my_appointments YA incluye turnos de todos los pacientes (titular + familiares). "
                            "2) Para agendar un turno para un familiar, usá book_appointment con patient_id=<ID_del_familiar>. "
                            "3) check_availability, cancel_appointment y reschedule_appointment operan sobre el paciente TITULAR del chat. "
                            "4) SIEMPRE que menciones turnos, datos clínicos o historial, "
                            "INCLUÍ la información de TODOS los pacientes listados (titular + familiares)."
                        )
                        logger.info(
                            f"👨‍👩‍👧‍👦 Family context injected: {len(family_lines)} lines for {len(_family_ids)} members ({external_user_id})"
                        )
            except Exception as _fam_err:
                logger.debug(f"Family context injection (non-fatal): {_fam_err}")

            if identity_lines:
                patient_context = "\n".join(identity_lines)

        now = get_now_arg()
        dias = [
            "Lunes",
            "Martes",
            "Miércoles",
            "Jueves",
            "Viernes",
            "Sábado",
            "Domingo",
        ]
        current_time_str = f"{dias[now.weekday()]} {now.strftime('%d/%m/%Y %H:%M')}"

        # RAG: Unified semantic search across FAQs, insurance, derivation, instructions
        rag_faqs_section = ""
        rag_insurance_section = ""
        rag_derivation_section = ""
        rag_instructions_section = ""
        try:
            from services.embedding_service import format_all_context_with_rag

            user_text_for_rag = " ".join(messages) if messages else ""
            rag_context = await format_all_context_with_rag(
                tenant_id, user_text_for_rag, faqs
            )
            rag_faqs_section = rag_context.get("faqs_section", "")
            rag_insurance_section = rag_context.get("insurance_section", "")
            rag_derivation_section = rag_context.get("derivation_section", "")
            rag_instructions_section = rag_context.get("instructions_section", "")
        except Exception as rag_err:
            logger.debug(f"RAG context fallback (non-fatal): {rag_err}")
            # Fallback to old FAQ-only RAG
            try:
                from services.embedding_service import format_faqs_with_rag

                user_text_for_rag = " ".join(messages) if messages else ""
                rag_faqs_section = await format_faqs_with_rag(
                    tenant_id, user_text_for_rag, faqs
                )
            except Exception:
                pass

        # Obtener feriados próximos para inyectar en el prompt
        _upcoming_holidays = []
        try:
            from services.holiday_service import get_upcoming_holidays

            _upcoming_holidays = await get_upcoming_holidays(
                db.pool, tenant_id, days_ahead=30
            )
        except Exception as hol_err:
            logger.debug(f"Holiday fetch fallback (non-fatal): {hol_err}")

        # Lead context injection: for leads (not yet patients), load accumulated
        # data from Redis and inject into patient_context so the AI has continuity.
        if not patient_row and not patient_context:
            try:
                from services.lead_context import (
                    get as lead_ctx_get,
                    format_for_prompt as lead_ctx_format,
                )

                _lead_data = await lead_ctx_get(tenant_id, external_user_id)
                if _lead_data:
                    patient_context = lead_ctx_format(_lead_data)
            except Exception:
                pass

        # Pre-booking minor context: detect from current messages AND cached lead_context
        # Check user messages for minor booking indicators BEFORE the LLM call
        _MINOR_STOP_WORDS = {"de", "un", "una", "el", "la", "los", "las", "y", "e", "a", "para", "con", "por", "en", "del", "que"}

        try:
            _msg_text = " ".join(messages).lower()
            _minor_patterns = [
                "mi hija", "mi hijo", "mi nena", "mi nene", "mi beba", "mi bebe",
                "para la nena", "para el nene", "para mi hija", "para mi hijo",
                "es menor",
            ]
            _has_minor_indicator = any(p in _msg_text for p in _minor_patterns)

            if _has_minor_indicator:
                # Save minor context to lead_context BEFORE any tool call
                from services.lead_context import merge as _lc_merge
                # Extract potential name: look for words after "para" or "mi hija/o/nena/nene"
                _minor_first = ""
                _minor_last = ""
                _minor_dni = ""

                # Try to extract names after "para" or "mi hija/o/nena/nene"
                _name_match = re.search(r'(?:para|mi hija|mi hijo|mi nena|mi nene)\s+(?:mi\s+)?(\w+)(?:\s+(\w+))?', _msg_text)
                if _name_match:
                    _raw_first = _name_match.group(1).lower()
                    _raw_last = _name_match.group(2).lower() if _name_match.group(2) else ""
                    # Skip stop words — "para mi nena de 11 años" → "de" is not a name
                    if _raw_first not in _MINOR_STOP_WORDS:
                        _minor_first = _name_match.group(1).capitalize()
                    if _raw_last and _raw_last not in _MINOR_STOP_WORDS and len(_raw_last) > 2 and not _raw_last.isdigit():
                        _minor_last = _name_match.group(2).capitalize()

                # Direct name pattern: message starts with "[Word] [Word] [7-8 digit DNI]" (no keywords needed)
                # e.g. "Luisana Zúñiga 54492865 - por favor de tarde"
                if not _minor_first:
                    _direct_name = re.search(r'^(\w+)\s+(\w+)\s+\b(\d{7,8})\b', _msg_text)
                    if _direct_name:
                        _dn_first = _direct_name.group(1).lower()
                        _dn_last = _direct_name.group(2).lower()
                        if _dn_first not in _MINOR_STOP_WORDS and _dn_last not in _MINOR_STOP_WORDS:
                            _minor_first = _direct_name.group(1).capitalize()
                            _minor_last = _direct_name.group(2).capitalize()
                            _minor_dni = _direct_name.group(3)

                # Try to extract DNI (8 digits) from messages if not already set
                if not _minor_dni:
                    _dni_match = re.search(r'\b(\d{7,8})\b', _msg_text)
                    if _dni_match:
                        _minor_dni = _dni_match.group(1)

                _lc_fields = {"is_minor": "true"}
                if _minor_first:
                    _lc_fields["minor_first_name"] = _minor_first
                if _minor_last:
                    _lc_fields["minor_last_name"] = _minor_last
                if _minor_dni:
                    _lc_fields["minor_dni"] = _minor_dni

                await _lc_merge(tenant_id, external_user_id, _lc_fields)
                logger.info(f"📌 MINOR CONTEXT DETECTED: name={_minor_first or '?'} {_minor_last or ''}, dni={_minor_dni or '?'}")

                # Also save to convstate booking_targets if possible
                try:
                    from services.conversation_state import set_booking_targets as _cs_set_minor
                    _cs_phone = current_customer_phone.get() if current_customer_phone else None
                    if _cs_phone:
                        _minor_target = {
                            "type": "third_party",
                            "is_minor": True,
                            "first_name": _minor_first,
                            "last_name": _minor_last,
                            "dni": _minor_dni,
                            "status": "pending",
                            "relationship": "hijo/a"
                        }
                        await _cs_set_minor(tenant_id, _cs_phone, [_minor_target])
                        logger.info(f"📌 MINOR BOOKING TARGET saved to convstate")
                except Exception as _cs_minor_err:
                    logger.debug(f"📌 convstate booking_targets save skipped: {_cs_minor_err}")
        except Exception:
            pass

        # Minor booking context: even for KNOWN patients, inject the cached
        # is_minor flag so the AI remembers "this parent is booking for a child"
        # across long conversations where the original message fell out of history.
        try:
            from services.lead_context import get as _lc_get
            from services.lead_context import merge as _lc_merge_ctx

            _lc_data = await _lc_get(tenant_id, external_user_id)
            if _lc_data and _lc_data.get("is_minor") == "true":
                # Even if no MINOR keywords in CURRENT message, try to extract
                # name/DNI from it and update lead_context incrementally.
                # This handles: msg1="para mi nena" → msg2="Luisana Zúñiga 54492865"
                if not _lc_data.get("minor_first_name") or not _lc_data.get("minor_dni"):
                    _msg_lower = " ".join(messages).lower()
                    _incr_dni = re.search(r'\b(\d{7,8})\b', _msg_lower)
                    _incr_name = re.search(r'^(\w+)\s+(\w+)\s+\b(\d{7,8})\b', _msg_lower)
                    _incr_fields = {}
                    if _incr_name:
                        _f = _incr_name.group(1).capitalize()
                        _l = _incr_name.group(2).capitalize()
                        if _f.lower() not in _MINOR_STOP_WORDS and _l.lower() not in _MINOR_STOP_WORDS:
                            _incr_fields["minor_first_name"] = _f
                            _incr_fields["minor_last_name"] = _l
                            _incr_fields["minor_dni"] = _incr_name.group(3)
                    elif _incr_dni and not _lc_data.get("minor_dni"):
                        _incr_fields["minor_dni"] = _incr_dni.group(1)
                    if _incr_fields:
                        await _lc_merge_ctx(tenant_id, external_user_id, _incr_fields)
                        logger.info(f"📌 MINOR CONTEXT INCREMENTAL: updated with {_incr_fields}")

                _minor_name = f"{_lc_data.get('minor_first_name', '')} {_lc_data.get('minor_last_name', '')}".strip()
                # Re-read after potential update
                _lc_data2 = await _lc_get(tenant_id, external_user_id)
                if _lc_data2:
                    _minor_name2 = f"{_lc_data2.get('minor_first_name', '')} {_lc_data2.get('minor_last_name', '')}".strip()
                    _minor_dni2 = _lc_data2.get("minor_dni", "")
                    _minor_ctx = f"\n[INTERNAL_BOOKING_CONTEXT] Este interlocutor está agendando para su HIJO/A MENOR: {_minor_name2 or 'nombre pendiente'}"
                    if _minor_dni2:
                        _minor_ctx += f" | DNI: {_minor_dni2}"
                    _minor_ctx += ". Usá is_minor=true en book_appointment. NO pidas teléfono del menor."
                    if patient_context:
                        patient_context += _minor_ctx
                    else:
                        patient_context = _minor_ctx
        except Exception:
            pass

        # Classify intent for conditional prompt injection (keyword-based, <1ms)
        intent_tags = classify_intent(messages)
        # Supplement with pending payment context from patient data
        if patient_context and (
            "payment_status" in patient_context.lower()
            or "pendiente" in patient_context.lower()
        ):
            intent_tags.add("payment")

        # Bug #8: Check greeting state to avoid repeating institutional greeting
        is_greeting_pending = True
        try:
            from services.greeting_state import has_greeted

            is_greeting_pending = not await has_greeted(tenant_id, external_user_id)
        except Exception:
            pass  # Conservative fallback: greet if check fails

        system_prompt = build_system_prompt(
            clinic_name=clinic_name,
            current_time=current_time_str,
            response_language="es",
            hours_start=CLINIC_HOURS_START,
            hours_end=CLINIC_HOURS_END,
            ad_context=ad_context,
            patient_context=patient_context,
            clinic_address=clinic_address,
            clinic_maps_url=clinic_maps_url,
            clinic_working_hours=clinic_working_hours,
            faqs=faqs if not rag_faqs_section else None,
            patient_status=patient_status,
            consultation_price=consultation_price,
            anamnesis_url=anamnesis_url,
            bank_cbu=bank_cbu,
            bank_alias=bank_alias,
            bank_holder_name=bank_holder_name,
            upcoming_holidays=_upcoming_holidays,
            insurance_providers=insurance_providers
            if not rag_insurance_section
            else None,
            derivation_rules=derivation_rules if not rag_derivation_section else None,
            specialty_pitch=system_prompt_template,
            professional_name=lead_professional_name,
            bot_name=bot_name,
            intent_tags=intent_tags,
            is_greeting_pending=is_greeting_pending,
            treatment_types=treatment_types_list,
            # Payment & financing (migración 035)
            payment_methods=payment_methods,
            financing_available=financing_available,
            max_installments=max_installments,
            installments_interest_free=installments_interest_free,
            financing_provider=financing_provider,
            financing_notes=financing_notes,
            cash_discount_percent=cash_discount_percent,
            accepts_crypto=accepts_crypto,
            # Clinic special conditions (migración 036)
            special_conditions_block=special_conditions_block,
            support_policy_block=support_policy_block,
        )

        # Inject RAG context sections if available
        rag_sections = [
            s
            for s in [
                rag_faqs_section,
                rag_insurance_section,
                rag_derivation_section,
                rag_instructions_section,
            ]
            if s
        ]
        if rag_sections:
            system_prompt += "\n\n" + "\n\n".join(rag_sections)

        # Inject operational rules (temporary/strategic)
        if operational_rules_block:
            system_prompt += "\n\n" + operational_rules_block

        # v8.2: Inject conversation-state anti-loop context (failed slots, exclusions, anchor_date)
        try:
            from services.conversation_state import get_state as _cs_inject

            _cs_inject_phone = current_customer_phone.get() if current_customer_phone else None
            if _cs_inject_phone:
                _cs_inject_data = await _cs_inject(tenant_id, _cs_inject_phone)
                if isinstance(_cs_inject_data, dict):
                    # Failed slots blacklist
                    _failed = _cs_inject_data.get("failed_slots") or []
                    if _failed:
                        _failed_dates = sorted(set(f["date"] for f in _failed if f.get("date")))
                        _failed_block = "SLOTS FALLIDOS (PROHIBIDO re-ofrecer):\n" + "\n".join(
                            f"  • {f['date']} {f.get('time', '??:??')} — {f.get('code', 'UNAVAILABLE')}"
                            for f in _failed
                        )
                        system_prompt += f"\n\n{_failed_block}\nREGLA: NO ofrezcas ninguno de estos slots al paciente. Si check_availability los incluye, filtralos antes de presentar."

                    # Patient exclusions
                    _exd = _cs_inject_data.get("excluded_days") or []
                    _exdt = _cs_inject_data.get("excluded_dates") or []
                    if _exd or _exdt:
                        _exc_lines = []
                        if _exd:
                            _exc_lines.append(f"DÍAS EXCLUIDOS: {', '.join(_exd)}")
                        if _exdt:
                            _exc_lines.append(f"FECHAS EXCLUIDAS: {', '.join(_exdt)}")
                        _exc_lines.append("REGLA: NO ofrezcas turnos en estos días/fechas. El paciente los rechazó explícitamente.")
                        system_prompt += f"\n\nEXCLUSIONES DEL PACIENTE:\n" + "\n".join(_exc_lines)

                    # Booking attempts warning
                    _batt = _cs_inject_data.get("booking_attempts") or 0
                    if _batt > 0:
                        _batt_remaining = max(0, 3 - _batt)
                        system_prompt += (
                            f"\n\n⚠️ INTENTOS DE AGENDAMIENTO FALLIDOS: {_batt} de {3}."
                            f" Te quedan {_batt_remaining} intentos."
                            f" Al llegar a 3 fallos → llamá derivhumano inmediatamente."
                        )

                    # Anchor date propagation
                    _anc = _cs_inject_data.get("anchor_date")
                    if _anc:
                        system_prompt += (
                            f"\n\n📅 ANCHOR_DATE: {_anc}"
                            f" — Usá esta fecha en confirm_slot y book_appointment. NO recalcules fechas relativas."
                        )

                    # v8.3: Correction awareness context (resolve-13-booking-errors T10)
                    if _cs_inject_data.get("has_correction"):
                        system_prompt += (
                            "\n\n⚠️ EL PACIENTE CORRIGIÓ INFORMACIÓN PREVIA en su último mensaje."
                            " Revisá los datos del paciente ANTES de continuar con el agendamiento."
                            " Usá los NUEVOS datos que dio, no los anteriores."
                        )

                    # v8.3: Anchor date cross-validation (resolve-13-booking-errors T12)
                    if _anc:
                        _msg_text = " ".join(messages).lower()
                        _dias_es = ["lunes", "martes", "miércoles", "miercoles", "jueves", "viernes", "sábado", "sabado", "domingo"]
                        _day_in_msg = next((d for d in _dias_es if d in _msg_text), None)
                        if _day_in_msg:
                            _dow_map = {"lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6}
                            try:
                                from datetime import datetime as _dt_t12
                                _parsed_date = _dt_t12.strptime(_anc.split("T")[0] if "T" in _anc else _anc, "%Y-%m-%d")
                                _actual_dow = _parsed_date.weekday()
                                _expected_dow = _dow_map.get(_day_in_msg)
                                if _expected_dow is not None and _actual_dow != _expected_dow:
                                    system_prompt += (
                                        f"\n⚠️ DAY_MISMATCH: El paciente mencionó '{_day_in_msg}' pero la fecha ANCHOR_DATE ({_anc}) cae en "
                                        f"{['lunes','martes','miércoles','jueves','viernes','sábado','domingo'][_actual_dow]}."
                                        f" Verificá con el paciente antes de agendar."
                                    )
                            except Exception:
                                pass

                    # v8.3: Error history context injection (resolve-13-booking-errors T15)
                    _err_history = _cs_inject_data.get("error_history") or []
                    if _err_history:
                        _err_lines = ["⚠️ ERRORES PREVIOS EN ESTA CONVERSACIÓN:"]
                        for _err in _err_history[-3:]:  # last 3 errors max
                            _cat = _err.get("category", "UNKNOWN")
                            _msg = _err.get("message", "")
                            _turn = _err.get("turn_number", "?")
                            _err_lines.append(f"  • [{_cat}] turno {_turn}: {_msg}")
                        _err_lines.append("REGLA: NO repitas el mismo error. Si fue RECOVERABLE, intentá un slot diferente.")
                        system_prompt += "\n\n" + "\n".join(_err_lines)

                    # v8.3: Frustration detection injection (resolve-13-booking-errors T14)
                    _frust_count = _cs_inject_data.get("frustration_count") or 0
                    _frust_mode = _cs_inject_data.get("frustration_mode") or False
                    if _frust_count >= 2 and _frust_count < 4:
                        system_prompt += (
                            f"\n\n[FRUSTRATION_DETECTED: modo conciliación — disculparse UNA vez y ofrecer opciones concretas. "
                            f"El paciente mostró {_frust_count} señales de frustración.]"
                        )
                    if _frust_count >= 4:
                        system_prompt += (
                            "\n\n[FRUSTRATION_ESCALATED: derivar a humano inmediatamente. "
                            "Usá la herramienta derivhumano con motivo 'Paciente frustrado después de múltiples intentos'."
                        )

                    # v8.3: Multi-booking context injection (resolve-13-booking-errors T11)
                    _btargets = _cs_inject_data.get("booking_targets") or []
                    _btarget_idx = _cs_inject_data.get("current_booking_target_index") or 0
                    if len(_btargets) > 1:
                        _current = _btargets[_btarget_idx] if _btarget_idx < len(_btargets) else _btargets[-1]
                        _pending = [t for t in _btargets if t.get("status") == "pending"]
                        _booked = [t for t in _btargets if t.get("status") == "booked"]
                        _ctx_lines = []
                        _ctx_lines.append(f"MULTI_BOOKING: Hay {len(_btargets)} personas para agendar.")
                        _ctx_lines.append(f"Ya agendados: {len(_booked)}. Pendientes: {len(_pending)}.")
                        _ctx_lines.append(f"ACTUAL: Agendando para {_current.get('type', 'self')} ({_current.get('relationship', 'el paciente')})")
                        _ctx_lines.append("REGLA: Agendá UNA persona a la vez. Después de confirmar el turno actual, continuá con la siguiente.")
                        system_prompt += "\n\n" + "\n".join(_ctx_lines)

                    # Single-target minor booking context injection (fix-minor-booking-flow)
                    if len(_btargets) == 1:
                        _bt = _btargets[0]
                        if _bt.get("is_minor") or _bt.get("relationship") in ("hijo/a", "hijo", "hija", "menor"):
                            _minor_name_bt = f"{_bt.get('first_name', '')} {_bt.get('last_name', '')}".strip()
                            _minor_dni_bt = _bt.get("dni", "")
                            _ctx_minor_lines = [
                                "MINOR BOOKING IN PROGRESS: El turno que se está gestionando es para un MENOR.",
                                f"Nombre del menor: {_minor_name_bt or 'pendiente'}",
                            ]
                            if _minor_dni_bt:
                                _ctx_minor_lines.append(f"DNI del menor: {_minor_dni_bt}")
                            _ctx_minor_lines.append("REGLAS:")
                            _ctx_minor_lines.append("- Usá is_minor=true en book_appointment.")
                            _ctx_minor_lines.append("- NO le pidas teléfono del menor al paciente.")
                            _ctx_minor_lines.append("- La vinculación con el padre/madre es automática.")
                            system_prompt += "\n\n" + "\n".join(_ctx_minor_lines)
                            logger.info(
                                f"📌 MINOR BOOKING CONTEXT injected: {_minor_name_bt or 'pending'}"
                            )
                    # v8.4: Scheduling constraints injection (persistent across context truncation)
                    _sched_constraints = _cs_inject_data.get("scheduling_constraints") or {}
                    if _sched_constraints:
                        _sc_lines = ["RESTRICCIONES HORARIAS DEL PACIENTE (PERSISTIDAS - SIEMPRE VIGENTES):"]
                        _tp = _sched_constraints.get("time_preference")
                        _mt = _sched_constraints.get("min_time")
                        _mxt = _sched_constraints.get("max_time")
                        _exd2 = _sched_constraints.get("exclude_days") or []
                        _exdt2 = _sched_constraints.get("exclude_dates") or []
                        if _tp:
                            _sc_lines.append(f"  - Preferencia horaria: {_tp.upper()} - Solo ofrecer turnos {_tp}.")
                        if _mt:
                            _sc_lines.append(f"  - Hora minima: {_mt} - PROHIBIDO ofrecer slots antes de {_mt}.")
                        if _mxt:
                            _sc_lines.append(f"  - Hora maxima: {_mxt} - PROHIBIDO ofrecer slots despues de {_mxt}.")
                        if _exd2:
                            _sc_lines.append(f"  - Dias excluidos: {', '.join(_exd2)} - NO ofrecer turnos esos dias.")
                        if _exdt2:
                            _sc_lines.append(f"  - Fechas excluidas: {', '.join(_exdt2)} - NO ofrecer esas fechas.")
                        _sc_lines.append(
                            "REGLA CRITICA: Estas restricciones fueron declaradas por el paciente. "
                            "Aplicarlas en TODOS los check_availability siguientes, sin excepciones, "
                            "aunque hayan pasado varios mensajes o el paciente no las repita."
                        )
                        system_prompt += "\n\n" + "\n".join(_sc_lines)
                        logger.info(f"[buffer_task] scheduling_constraints injected: {_sched_constraints}")

        except Exception as _cs_inject_err:
            logger.debug(f"convstate context injection skipped: {_cs_inject_err}")

        # Inject booking flow guard rules (booking-agent-errors fix)
        system_prompt += """

REGLA DE NOTIFICACIÓN ÚNICA: Si el paciente no tiene turno, informalo UNA sola vez. Luego pasá DIRECTO a ofrecer alternativas (check_availability o preguntar fecha preferida). PROHIBIDO repetir "no tenés turno activo" o "no figura ningún turno" más de una vez por conversación.

REGLA DLD-67 (MISMO DÍA): El sistema NO permite agendar turnos para el día de hoy. Se requiere mínimo 1 día de margen operativo. NUNCA ofrezcas turnos para hoy — si el paciente pide "hoy", la tool auto-avanza al día siguiente.

REGLA DE EXCLUSIÓN DE FECHAS ESPECÍFICAS: Si el paciente dice que una FECHA ESPECÍFICA no puede (ej: "el 3 de junio tengo que viajar", "mañana no puedo", "el 15 no me sirve"), pasá exclude_dates con esa fecha en formato YYYY-MM-DD en TODAS las llamadas siguientes a check_availability. NUNCA ofrezcas turnos para una fecha que el paciente explícitamente rechazó.

REGLA ANTI-LOOP DE AGENDAMIENTO:
• Si book_appointment falla 2 veces para el MISMO día → PROHIBIDO intentar ese día nuevamente. Ofrecé turnos para otro día.
• Si book_appointment falla 3 veces en total en la conversación → llamá derivhumano con motivo "No se pudo agendar después de 3 intentos". NO sigas intentando.
• PROHIBIDO ofrecer el mismo horario o un horario 15 minutos corrido como alternativa después de un fallo.
• ERROR PROTOCOL: book_appointment ahora retorna errores en formato [BOOK_ERROR:CÓDIGO] mensaje [ACTION:directiva]. Seguí SIEMPRE la directiva ACTION. Ej: [BOOK_ERROR:UNAVAILABLE] → [ACTION:Pick next slot; do NOT re-offer] significa que NO debés re-ofrecer ESE slot específico.

REGLA DE CONFIRMACIÓN EXACTA: Cuando el paciente pregunta por su turno ("¿para cuándo quedó?", "¿qué día es mi turno?"):
1. Llamá list_my_appointments PRIMERO para obtener los datos reales.
2. Respondé con la fecha EXACTA del turno (ej: "jueves 04/06 a las 10:30").
3. PROHIBIDO usar referencias relativas ("mañana", "pasado mañana", "esta semana") sin haber calculado los días exactos usando el TIEMPO ACTUAL.
4. Si tenés duda sobre la fecha, llamá list_my_appointments de nuevo. NUNCA adivines.

REGLA ANTI-REPETICIÓN DE CTA (EXPANDIDA): PROHIBIDO ofrecer CUALQUIERA de estas frases más de 2 veces en total (combinadas) en toda la conversación:
- "Si querés, te ayudo a coordinar"
- "Te gustaría agendar?"
- "Querés que te busque turno?"
- "Te agendo?"
- "Te busco turno"
- "Querés que te ayudo a coordinar un turno?"
- "Si querés, te busco un turno"
- CUALQUIER variación que ofrezca agendar sin que el paciente lo pida
Después de 2 veces, NO insistas. Respondé a sus preguntas sin volver a ofrecer hasta que el paciente lo pida explícitamente.

# v8.3: PROACTIVE BOOKING (resolve-13-booking-errors T7) — No magic word gate
# NO necesitás que el paciente diga "quiero turno" para activar booking.
# Si el paciente menciona un tratamiento ("implantes", "limpieza", "consulta"), pregunta por precios
# o dice "quisiera saber sobre [tratamiento]", interpretálo como INTENCIÓN DE AGENDAR y ofrecé
# coordinar un turno para evaluación. Esta regla va por ENCIMA del límite de 2 CTAs.
"""

        # Inject min appointment date if configured
        tenant_config = dict(tenant_row).get("config") if tenant_row else {}
        if isinstance(tenant_config, str):
            try:
                tenant_config = json.loads(tenant_config)
            except Exception:
                tenant_config = {}
        if not isinstance(tenant_config, dict):
            tenant_config = {}
        min_apt_date = tenant_config.get("min_appointment_date")
        if min_apt_date:
            system_prompt += f"""

# 📅 FECHA MÍNIMA PARA TURNOS
Por temas de reorganización de la agenda, los turnos se están dando a partir del {min_apt_date}.
Si el paciente pide un turno para ANTES de esa fecha, decile:
"Por temas de reorganización de la agenda, los turnos se están dando a partir del {min_apt_date}. ¿Te parece bien o preferís otra fecha?"

Si el paciente pide un turno para {min_apt_date} o después, continuar normalmente.

Recordá que cada obra social puede tener días de espera adicionales configurados. Combiná la fecha mínima con los días de espera de la OS para determinar la fecha más temprana disponible.
"""

        chat_history = []
        vision_context_str = ""
        audio_context_str = ""
        seen_multimodal = set()

        # --- Wait for pending audio transcriptions before processing ---
        # Check if recent messages have audio without transcription and wait up to 15s
        try:
            pending_audio = await pool.fetch(
                """
                SELECT id, content_attributes FROM chat_messages
                WHERE conversation_id = $1 AND tenant_id = $2
                AND content_attributes::text LIKE '%audio%'
                AND content_attributes::text NOT LIKE '%transcription%'
                ORDER BY created_at DESC LIMIT 3
            """,
                conversation_id,
                tenant_id,
            )
            if pending_audio:
                import asyncio as _asyncio

                logger.info(
                    f"🎙️ Esperando transcripción de {len(pending_audio)} audio(s)..."
                )
                for attempt in range(6):  # Max 15 seconds (6 x 2.5s)
                    await _asyncio.sleep(2.5)
                    # Re-check if transcriptions are now available
                    still_pending = await pool.fetchval(
                        """
                        SELECT COUNT(*) FROM chat_messages
                        WHERE id = ANY($1) AND content_attributes::text NOT LIKE '%transcription%'
                    """,
                        [r["id"] for r in pending_audio],
                    )
                    if not still_pending or still_pending == 0:
                        logger.info(
                            f"✅ Transcripciones completadas tras {(attempt + 1) * 2.5}s"
                        )
                        break
                else:
                    logger.warning(
                        f"⚠️ Timeout esperando transcripciones. Procesando sin audio."
                    )
        except Exception as audio_wait_err:
            logger.warning(f"⚠️ Error checking pending transcriptions: {audio_wait_err}")

        def extract_multimodal(msg_attrs):
            nonlocal vision_context_str, audio_context_str
            if not msg_attrs:
                return
            try:
                attrs = msg_attrs
                if isinstance(attrs, str):
                    import json

                    attrs = json.loads(attrs)
                if isinstance(attrs, list):
                    for att in attrs:
                        # Vision
                        desc = att.get("description")
                        if desc and desc not in seen_multimodal:
                            vision_context_str += f"\n[IMAGEN: {desc}]"
                            seen_multimodal.add(desc)
                        # Audio (Spec 21/28)
                        trans = att.get("transcription")
                        if trans and trans not in seen_multimodal:
                            audio_context_str += f"\n[AUDIO: {trans}]"
                            seen_multimodal.add(trans)
            except Exception:
                pass

        # 4. Fetching Recent History (Spec 23)
        # Re-fetch AFTER transcription wait to get updated content_attributes
        db_history_dicts = await db.get_chat_history(
            external_user_id, limit=40, tenant_id=tenant_id
        )

        # --- WAIT FOR VISION if recent images lack description ---
        import asyncio

        try:
            pending_vision = await pool.fetchval(
                """
                SELECT COUNT(*) FROM chat_messages
                WHERE conversation_id = $1 AND tenant_id = $2
                AND content_attributes::text LIKE '%image%'
                AND content_attributes::text NOT LIKE '%description%'
                AND created_at > NOW() - INTERVAL '30 seconds'
            """,
                conversation_id,
                tenant_id,
            )
            if pending_vision and pending_vision > 0:
                logger.info(
                    f"👁️ Waiting for vision analysis ({pending_vision} pending)..."
                )
                for attempt in range(6):  # Wait up to 15s
                    await asyncio.sleep(2.5)
                    still_pending = await pool.fetchval(
                        """
                        SELECT COUNT(*) FROM chat_messages
                        WHERE conversation_id = $1 AND tenant_id = $2
                        AND content_attributes::text LIKE '%image%'
                        AND content_attributes::text NOT LIKE '%description%'
                        AND created_at > NOW() - INTERVAL '30 seconds'
                    """,
                        conversation_id,
                        tenant_id,
                    )
                    if not still_pending or still_pending == 0:
                        logger.info(
                            f"✅ Vision analysis completed after {(attempt + 1) * 2.5}s"
                        )
                        break
                else:
                    logger.warning(
                        "⚠️ Timeout waiting for vision. Proceeding without image description."
                    )
                # Re-fetch history with updated descriptions
                db_history_dicts = await db.get_chat_history(
                    external_user_id, limit=20, tenant_id=tenant_id
                )
        except Exception as vision_wait_err:
            logger.warning(f"⚠️ Error checking pending vision: {vision_wait_err}")

        # --- EXTRACT CONTEXT BEFORE DEDUPLICATION (VISION FIX) ---
        for msg in db_history_dicts:
            extract_multimodal(msg.get("content_attributes"))

        # Deduplication: If the last message in DB matches the first in Buffer, remove it from history
        if db_history_dicts and messages:
            last_db_msg = db_history_dicts[-1]["content"]
            first_buffer_msg = messages[0]
            if last_db_msg.strip() == first_buffer_msg.strip():
                db_history_dicts.pop()

        # CONTEXT COMPRESSION: Keep last 10 messages full, compress older ones
        if len(db_history_dicts) > 10:
            # Compress older messages into a summary line each (save ~60% tokens)
            old_msgs = db_history_dicts[:-10]
            recent_msgs = db_history_dicts[-10:]
            # Keywords that indicate third-party/minor bookings — preserve these messages in full
            _preserve_keywords = {
                "hijo",
                "hija",
                "menor",
                "nene",
                "nena",
                "niño",
                "niña",
                "bebé",
                "familiar",
                "esposa",
                "esposo",
                "mamá",
                "papá",
                "abuelo",
                "abuela",
                "para mi",
                "para él",
                "para ella",
            }
            for msg in old_msgs:
                role = msg["role"]
                content = msg["content"]
                # Preserve full content if it mentions family/minor booking context
                content_lower = content.lower() if content else ""
                has_family_keyword = any(
                    kw in content_lower for kw in _preserve_keywords
                )
                if has_family_keyword:
                    truncated = content[:200] + "..." if len(content) > 200 else content
                else:
                    truncated = content[:80] + "..." if len(content) > 80 else content
                if role == "user":
                    chat_history.append(HumanMessage(content=truncated))
                else:
                    chat_history.append(AIMessage(content=truncated))
            for msg in recent_msgs:
                role = msg["role"]
                content = msg["content"]
                if role == "user":
                    chat_history.append(HumanMessage(content=content))
                else:
                    chat_history.append(AIMessage(content=content))
        else:
            for msg in db_history_dicts:
                role = msg["role"]
                content = msg["content"]
                if role == "user":
                    chat_history.append(HumanMessage(content=content))
                else:
                    chat_history.append(AIMessage(content=content))

        # Append buffered messages as ONE block
        user_input = "\n".join(messages)

        if vision_context_str:
            logger.info(
                f"👁️ Inyectando contexto visual: {len(vision_context_str)} chars"
            )
            user_input += (
                f"\n\nCONTEXTO VISUAL (Imágenes recientes):{vision_context_str}"
            )

        if audio_context_str:
            logger.info(
                f"🎙️ Inyectando contexto de audio: {len(audio_context_str)} chars"
            )
            user_input += (
                f"\n\nCONTEXTO DE AUDIO (Transcripciones recientes):{audio_context_str}"
            )

        # --- Bug #4 Phase C: Input-side state guard ---
        # Check previous conversation state and inject hint if needed
        state_hint = ""
        if get_state is not None and current_customer_phone is not None:
            try:
                phone = current_customer_phone.get()
                if phone:
                    prev_state = await get_state(tenant_id, phone)
                    prev_state_str = (
                        prev_state.get("state", "IDLE")
                        if isinstance(prev_state, dict)
                        else "IDLE"
                    )

                    logger.info(
                        f"📊 BOOKING_FLOW | phone={phone} | state={prev_state_str} | msg={chr(10).join(messages)[:120]!r}"
                    )

                    user_msg = "\n".join(messages)
                    if prev_state_str == "SLOT_LOCKED" and (_detect_research_intent(user_msg) or _detect_period_change(user_msg)):
                        logger.info(f"🔒 STATE_GUARD: Rejection/cambio-de-período detectado en SLOT_LOCKED para phone={phone}. Libero el lock y vuelvo a OFFERED_SLOTS.")
                        _slot = prev_state.get("last_locked_slot") or {}
                        _date = _slot.get("date")
                        _time = _slot.get("time")
                        if _date and _time:
                            _prof_id = _slot.get("professional_id") or 0
                            try:
                                from services.relay import get_redis
                                r = get_redis()
                                if r:
                                    _spec_lock_key = f"slot_lock:{tenant_id}:{_prof_id}:{_date}:{_time}"
                                    _generic_lock_key = f"slot_lock:{tenant_id}:0:{_date}:{_time}"
                                    await r.delete(_spec_lock_key)
                                    await r.delete(_generic_lock_key)
                                    logger.info(f"🔒 STATE_GUARD: Released Redis locks: {_spec_lock_key}, {_generic_lock_key}")
                            except Exception as redis_err:
                                logger.warning(f"🔒 STATE_GUARD: Failed to release Redis lock: {redis_err}")
                        try:
                            from services.conversation_state import set_state
                            await set_state(
                                tenant_id,
                                phone,
                                "OFFERED_SLOTS",
                                last_offered_slots=prev_state.get("last_offered_slots") or []
                            )
                            prev_state_str = "OFFERED_SLOTS"
                            prev_state = await get_state(tenant_id, phone)
                        except Exception as state_err:
                            logger.warning(f"🔒 STATE_GUARD: Failed to set state to OFFERED_SLOTS: {state_err}")
                        # Un cambio de fecha/período NO es un fallo de agendamiento: reseteo los
                        # contadores para que el cambio de mes/preferencia no acerque a la derivación.
                        try:
                            from services.conversation_state import reset_booking_attempts, reset_availability_attempts
                            await reset_booking_attempts(tenant_id, phone)
                            await reset_availability_attempts(tenant_id, phone)
                        except Exception as _reset_err:
                            logger.warning(f"🔒 STATE_GUARD: reset de contadores falló: {_reset_err}")

                    # If previous state was OFFERED_SLOTS and user is selecting a slot
                    if prev_state_str == "OFFERED_SLOTS":
                        user_msg = "\n".join(messages)
                        _is_selection = _detect_selection_intent(user_msg)
                        _is_research = _detect_research_intent(user_msg) or _detect_period_change(user_msg)
                        logger.info(f"🔒 STATE_GUARD EVAL | state={prev_state_str} msg={user_msg[:80]!r} selection={_is_selection} research={_is_research}")
                        if _is_selection:
                            # Build a detailed hint including the actual offered slots
                            _last_offered_slots = prev_state.get("last_offered_slots") or []
                            if _last_offered_slots:
                                _slots_lines = []
                                for _idx, _slot in enumerate(_last_offered_slots, 1):
                                    _date_display = _slot.get("date_display") or _slot.get("date", "")
                                    _time = _slot.get("time", "")
                                    _prof = _slot.get("professional") or _slot.get("professional_name") or ""
                                    _date_iso = _slot.get("date", "")
                                    _prof_suffix = f" (profesional: {_prof})" if _prof else ""
                                    _slots_lines.append(
                                        f"  Opción {_idx}: {_date_display} — {_time} hs{_prof_suffix} [ISO: {_date_iso} {_time}]"
                                    )
                                _slots_block = "\nSLOTS OFRECIDOS:\n" + "\n".join(_slots_lines)
                            else:
                                _slots_block = ""

                            state_hint = (
                                f"\n\n[STATE_HINT: El paciente ya tiene opciones de turno ofrecidas.{_slots_block}\n\n"
                                "INSTRUCCIONES CRÍTICAS:\n"
                                "- El paciente está SELECCIONANDO uno de los turnos ofrecidos.\n"
                                "- Si estás AGENDANDO un turno nuevo: DEBES llamar confirm_slot con slot_index=N (N = número de opción).\n"
                                "- Si estás REPROGRAMANDO un turno existente: DEBES llamar reschedule_appointment DIRECTAMENTE (NUNCA llames confirm_slot ni book_appointment para reprogramar). Pasá original_date=fecha de tu turno actual, y new_date_time=fecha y hora de la Opción N.\n"
                                "- 'el primero', 'el 1', 'opción 1', o el día/hora de Opción 1 → N=1\n"
                                "- 'el segundo', 'el 2', 'opción 2', o el día/hora de Opción 2 → N=2\n"
                                "- 'cualquiera' o no especifica → N=1\n"
                                "- NO llamés check_availability de nuevo.]"
                            )
                            logger.info(
                                f"🔒 STATE_GUARD: Injecting hint for slot selection with {len(_last_offered_slots)} slots. prev_state={prev_state_str}"
                            )
                        elif _detect_research_intent(user_msg):
                            # User is rejecting offered slots and asking for different date/time
                            # This is OK — the LLM SHOULD call check_availability with the new preference
                            state_hint = (
                                "\n\n[STATE_HINT: El paciente ya tenía opciones de turno ofrecidas pero las RECHAZÓ o pidió otro día/horario.\n\n"
                                "INSTRUCCIONES CRÍTICAS:\n"
                                "- DEBES llamar check_availability con la nueva preferencia de fecha/horario que indica el paciente.\n"
                                "- Si el paciente dice un día específico ('el viernes', 'mañana', 'la semana que viene') → usá ese día como interpreted_date.\n"
                                "- Si el paciente dice un horario específico ('a las 10', 'por la tarde') → pasá specific_time o time_preference.\n"
                                "- Si rechazó un día de la semana ('el lunes no puedo') → pasá exclude_days con ese día en TODAS las búsquedas siguientes.\n"
                                "- Si rechazó una FECHA ESPECÍFICA ('el 3 de junio no puedo', 'mañana no puedo') → pasá exclude_dates con esa fecha en formato YYYY-MM-DD en TODAS las búsquedas siguientes.\n"
                                "- NO ofrezcas los turnos anteriores — busca disponibilidad nueva.\n"
                                "- Cuando check_availability devuelva opciones y el paciente ACEPTE → usá slot_index para confirmar, luego pedí datos (PASO 4b) y reservá.\n"
                                "- Si el paciente pidió un día/hora exacto y ESE slot está disponible en los resultados → decile que sí está disponible y procedé a pedir datos directamente.]"
                            )
                            logger.info(
                                f"🔒 STATE_GUARD: Re-search intent detected, injecting rejection hint. prev_state={prev_state_str}"
                            )
                        else:
                            # No clear selection or rejection — could be a lateral question or ambiguous response
                            # Build slots reminder so the LLM can re-offer after answering
                            _last_offered_amb = prev_state.get("last_offered_slots") or []
                            _slots_reminder = ""
                            if _last_offered_amb:
                                _rem_lines = []
                                for _ri, _rs in enumerate(_last_offered_amb, 1):
                                    _rem_lines.append(f"  {_ri}️⃣ {_rs.get('date_display', _rs.get('date', ''))} — {_rs.get('time', '')} hs")
                                _slots_reminder = "\n" + "\n".join(_rem_lines)

                            state_hint = (
                                f"\n\n[STATE_HINT: El paciente tiene opciones de turno PENDIENTES de respuesta:{_slots_reminder}\n\n"
                                "El paciente parece estar haciendo una pregunta lateral o un comentario NO relacionado con la selección de turno.\n"
                                "INSTRUCCIONES:\n"
                                "1. Respondé la pregunta o comentario del paciente normalmente.\n"
                                "2. DESPUÉS de responder, recordale las opciones pendientes de forma natural.\n"
                                "   Ejemplo: 'Y respecto al turno, ¿te queda mejor el 1️⃣ o el 2️⃣?'\n"
                                "3. NO pierdas el contexto del turno — el paciente NO canceló la búsqueda.\n"
                                "4. Si es ambiguo si acepta o rechaza los turnos, preguntá: '¿Querés alguna de estas opciones o preferís otro día?']"
                            )
                            logger.info(
                                f"🔒 STATE_GUARD: No clear intent detected, injecting clarification hint. prev_state={prev_state_str}, user_msg={user_msg[:50]}..."
                            )
                    elif prev_state_str == "SLOT_LOCKED":
                        _slot = prev_state.get("last_locked_slot") or {}
                        _slot_details = ""
                        if _slot:
                            _date = _slot.get("date_display") or _slot.get("date") or ""
                            _time = _slot.get("time") or ""
                            _prof = _slot.get("professional") or _slot.get("professional_name") or ""
                            _treatment = _slot.get("treatment") or _slot.get("treatment_name") or ""
                            _details_list = []
                            if _date:
                                _details_list.append(f"Fecha: {_date}")
                            if _time:
                                _details_list.append(f"Hora: {_time}")
                            if _prof:
                                _details_list.append(f"Profesional: {_prof}")
                            if _treatment:
                                _details_list.append(f"Tratamiento: {_treatment}")
                            _slot_details = " (" + ", ".join(_details_list) + ")" if _details_list else ""

                        state_hint = (
                            f"\n\n[STATE_HINT: El paciente tiene un turno pre-reservado (bloqueado){_slot_details}.\n\n"
                            "INSTRUCCIONES CRÍTICAS PARA SLOT_LOCKED:\n"
                            "1. El turno ya está pre-reservado. Tu único objetivo es confirmar la reserva solicitando los datos faltantes:\n"
                            "   - Nombre completo (si no lo tenés)\n"
                            "   - Número de DNI (debe ser numérico de 7 a 11 dígitos, ej: 12345678). Si el usuario da una respuesta ambigua o no numérica como 'Sí' o 'Así es', insistí educadamente en que proporcione el DNI numérico.\n"
                            "2. REGLA ESTRICTA CONTRA LOOPS Y RE-OFERTAS:\n"
                            "   - PROHIBIDO llamar a check_availability para buscar otras fechas o profesionales.\n"
                            "   - PROHIBIDO ofrecer nuevos slots u horarios alternativos a menos que el paciente solicite explícitamente reprogramar o cancelar.\n"
                            "   - No inicies un nuevo flujo de reserva.\n"
                            "   - EXCEPCIÓN (anula lo anterior): si el paciente pide OTRA fecha, otro mes, otra semana o un período distinto (ej: \"para julio\", \"la semana que viene\", \"otro día\") o RECHAZA este horario, eso NO es un loop ni un fallo de agendamiento: re-buscá disponibilidad con la nueva preferencia llamando a check_availability. NO insistas con el turno pre-reservado ni reintentes book_appointment. Esto nunca es motivo de derivación.\n"
                            "3. PREGUNTAS LATERALES:\n"
                            "   - Si el paciente hace una pregunta lateral (ej: si aceptan cierta obra social), respondé la pregunta y luego solicitá inmediatamente el nombre/DNI para terminar de confirmar su reserva en el turno pre-reservado.\n"
                            "   - ⚠️ PREGUNTAS LATERALES / MULTI-TEMA: Si el paciente menciona varios temas a la vez (ej: obra social + nombre sin DNI, o turno + estacionamiento), respondé a TODOS. Podés llamar herramientas si necesitás verificar (check_insurance_coverage está permitido), pero al responder cubrí todos los temas pendientes. Usá burbujas separadas si ayuda a la claridad. Ejemplo: paciente dice \"Valentina Pérez, OSDE\" → \"¡Sí, trabajamos con OSDE 😊!\" y en la burbuja siguiente \"¿Me pasás tu DNI solo números para agendarte?\".\n"
                            "4. Si recibís el DNI numérico y/o nombre, usalos para completar la reserva llamando a book_appointment.]"
                        )
                        logger.info(
                            f"🔒 STATE_GUARD: Injecting hint for SLOT_LOCKED state. Details: {_slot_details}"
                        )

                    # Inject failed_slots into STATE_HINT for all non-IDLE states (fix-minor-booking-flow T2.2)
                    if prev_state_str not in ("IDLE",):
                        _state_failed_slots = prev_state.get("failed_slots") or []
                        if _state_failed_slots:
                            _failed_block = "\n\nSLOTS FALLIDOS (PROHIBIDO re-ofrecer):\n" + "\n".join(
                                f"  • {f.get('date', '??')} {f.get('time', '??')} — {f.get('code', 'UNAVAILABLE')}"
                                for f in _state_failed_slots
                            )
                            _failed_block += "\nREGLA: NO ofrezcas ninguno de estos slots al paciente."
                            state_hint += _failed_block
                            logger.info(
                                f"📊 BOOKING_FLOW | FAILED_SLOTS injected into STATE_HINT: {len(_state_failed_slots)} slots"
                            )
            except Exception as state_err:
                logger.warning(f"[STATE_GUARD] Failed to get state: {state_err}")

        if state_hint:
            user_input += state_hint
            logger.info(f"📊 BOOKING_FLOW | STATE_HINT injected ({len(state_hint)} chars): {state_hint[:200]!r}")
        else:
            # Log when NO hint was injected — helps detect missing guards
            if get_state is not None and current_customer_phone is not None:
                try:
                    _dbg_phone = current_customer_phone.get()
                    if _dbg_phone:
                        _dbg_state = await get_state(tenant_id, _dbg_phone)
                        _dbg_state_str = _dbg_state.get("state", "IDLE") if isinstance(_dbg_state, dict) else "IDLE"
                        if _dbg_state_str not in ("IDLE",):
                            logger.warning(
                                f"📊 BOOKING_FLOW | ⚠️ NO STATE_HINT for non-IDLE state={_dbg_state_str} | phone={_dbg_phone} | msg={chr(10).join(messages)[:100]!r}"
                            )
                except Exception:
                    pass

        # --- DETECCIÓN DE CONTEXTO ESPECIAL ---
        # Verificar si hay contexto especial (multimedia, seguimientos, etc.)
        has_recent_media = False
        is_followup_response = False
        media_types = []
        channel_type = "whatsapp"  # Default
        followup_context = ""

        try:
            # Obtener el último mensaje del usuario y el último del asistente
            context_rows = await pool.fetch(
                """
                SELECT cm.role, cm.content, cm.content_attributes, cc.channel 
                FROM chat_messages cm
                JOIN chat_conversations cc ON cm.conversation_id = cc.id
                WHERE cm.conversation_id = $1 
                ORDER BY cm.created_at DESC 
                LIMIT 2
            """,
                conversation_id,
            )

            if context_rows:
                for ctx_row in context_rows:
                    if ctx_row["role"] == "user":
                        # Verificar archivos multimedia en mensaje del usuario
                        attrs = ctx_row["content_attributes"]
                        channel_type = ctx_row["channel"] or "whatsapp"

                        if attrs:
                            if isinstance(attrs, str):
                                attrs = json.loads(attrs)

                            if isinstance(attrs, list):
                                for att in attrs:
                                    media_type = att.get("type", "")
                                    if media_type in ["image", "document"]:
                                        has_recent_media = True
                                        media_types.append(media_type)

                    elif ctx_row["role"] == "assistant":
                        # Verificar si el último mensaje del asistente fue un seguimiento
                        attrs = ctx_row["content_attributes"]
                        if attrs:
                            if isinstance(attrs, str):
                                attrs = json.loads(attrs)

                            # Buscar metadata de seguimiento
                            if isinstance(attrs, dict) and attrs.get("is_followup"):
                                is_followup_response = True
                                followup_context = (
                                    "⚠️ ATENCIÓN: El paciente está respondiendo a un mensaje de "
                                    "seguimiento post-atención. Evaluá los síntomas con 'triage_urgency'. "
                                    "SEGÚN EL GRADO: "
                                    "(a) Si reporta DOLOR FUERTE, una COMPLICACIÓN (punto/sutura suelta, "
                                    "inflamación que no baja, sangrado, fiebre, supuración) o ya pasaron "
                                    "varios días/semanas del turno → es una complicación: DERIVÁ al equipo "
                                    "con 'derivhumano' para que lo vean (triage_urgency ya avisa a Telegram "
                                    "si es grave). "
                                    "(b) Si es una MOLESTIA LEVE y el turno fue reciente (pocos días) → "
                                    "tranquilizá: es esperable los primeros días; deciles que quedás atento "
                                    "a cualquier cosa. NO derives si es leve."
                                )
                                logger.info(
                                    f"🔍 Detectada respuesta a seguimiento post-atención"
                                )

        except Exception as e:
            logger.warning(f"Error al verificar contexto especial: {e}")

        # Late supplement: if media detected after prompt build, inject adjuntos section
        if has_recent_media and "media" not in intent_tags:
            intent_tags.add("media")
            from main import _get_adjuntos_section

            system_prompt += "\n\n" + _get_adjuntos_section()

        # --- Social channel context (phase 6) ---
        # channel_type is now resolved from the DB JOIN above (line ~1361).
        # compute_social_context is a pure function so this is always fast.
        _social_ctx = compute_social_context(
            channel_type, dict(tenant_row) if tenant_row else {}
        )

        # SOLO path: prepend social preamble to system_prompt when IG/FB active.
        # This path calls build_system_prompt before channel_type is known, so
        # we inject the preamble here after both are available.
        if _social_ctx["is_social_channel"]:
            try:
                from services.social_prompt import build_social_preamble
                from services.social_routes import CTA_ROUTES

                _social_preamble = build_social_preamble(
                    tenant_id=tenant_id,
                    channel=_social_ctx["channel"],
                    social_landings=_social_ctx["social_landings"],
                    instagram_handle=_social_ctx["instagram_handle"],
                    facebook_page_id=_social_ctx["facebook_page_id"],
                    cta_routes=CTA_ROUTES,
                    whatsapp_link=_social_ctx.get("whatsapp_link"),
                )
                system_prompt = _social_preamble + "\n\n---\n\n" + system_prompt
                logger.info(
                    f"📱 Social preamble injected for tenant {tenant_id} "
                    f"channel={_social_ctx['channel']}"
                )
            except Exception as _social_err:
                logger.warning(
                    f"⚠️ Social preamble injection failed (non-fatal): {_social_err}"
                )

        # v8.3: Multi-entity DNI preprocessing (resolve-13-booking-errors T5)
        try:
            _dnis = extract_multi_dni(messages)
            if len(_dnis) > 1:
                logger.info(f"🔢 T5 multi-dni detected: {len(_dnis)} entities: {_dnis}")
                from services.conversation_state import _read_payload as _cs_payload, _raw_write as _cs_raw
                _cs_phone = current_customer_phone.get()
                if _cs_phone:
                    _cs_data = await _cs_payload(tenant_id, _cs_phone) or {}
                    _targets = _cs_data.get("booking_targets", [])
                    for _e in _dnis:
                        # Avoid duplicates
                        if not any(t.get("dni") == _e["dni"] for t in _targets):
                            _targets.append({
                                "dni": _e["dni"],
                                "relationship": _e["relationship"],
                                "status": "pending",
                                "type": "self" if _e["relationship"] == "self" else "third_party",
                            })
                    await _cs_raw(tenant_id, _cs_phone, _cs_data)
            elif _dnis:
                # Single DNI — store as current booking dni via convstate
                from services.conversation_state import set_booking_targets as _cs_set_targets
                _cs_phone_s = current_customer_phone.get()
                if _cs_phone_s:
                    await _cs_set_targets(tenant_id, _cs_phone_s, [
                        {"dni": _dnis[0]["dni"], "relationship": _dnis[0]["relationship"],
                         "status": "pending", "type": "self"}
                    ])
        except Exception as _t5_err:
            logger.debug(f"T5 multi-dni preprocessing skipped: {_t5_err}")

        # v8.3: Compound intent detection (resolve-13-booking-errors T6)
        try:
            if detect_compound_intent(messages):
                logger.info(f"🔢 T6 compound intent detected")
                from services.conversation_state import _read_payload as _cs_payload_cpd, _raw_write as _cs_raw_cpd
                _cs_phone_c = current_customer_phone.get()
                if _cs_phone_c:
                    _cs_data_cpd = await _cs_payload_cpd(tenant_id, _cs_phone_c) or {}
                    _cs_data_cpd["compound_intent"] = True
                    await _cs_raw_cpd(tenant_id, _cs_phone_c, _cs_data_cpd)
        except Exception as _t6_err:
            logger.debug(f"T6 compound intent detection skipped: {_t6_err}")

        # v8.3: Correction awareness (resolve-13-booking-errors T10)
        # Detect when patient corrects a previous statement (e.g. "no, es mi mamá")
        try:
            _user_msg = "\n".join(messages).lower()
            _is_correction = any(
                word in _user_msg
                for word in ["no es", "no, es", "corrijo", "me equivoqué", "me equivoque",
                            "rectifico", "digo mal", "dije mal", "perdón", "disculpa",
                            "no, para", "no es para", "en realidad", "mejor dicho",
                            "es al revés", "al revés"]
            )
            if _is_correction:
                logger.info(f"🔧 T10 correction detected in patient message: {_user_msg[:80]!r}")
                from services.conversation_state import _read_payload as _cs_payload_t10, _raw_write as _cs_raw_t10
                _cs_phone_t10 = current_customer_phone.get()
                if _cs_phone_t10:
                    _cs_data_t10 = await _cs_payload_t10(tenant_id, _cs_phone_t10) or {}
                    _cs_data_t10["has_correction"] = True
                    await _cs_raw_t10(tenant_id, _cs_phone_t10, _cs_data_t10)
        except Exception as _t10_err:
            logger.debug(f"T10 correction awareness skipped: {_t10_err}")

        # v8.3: Frustration detection BEFORE LLM invocation (resolve-13-booking-errors T14 fix)
        try:
            _frust_signals = _detect_frustration(messages)
            if _frust_signals > 0:
                logger.info(f"🧩 T14 frustration detected: {_frust_signals} signal(s)")
                _cs_phone_f = current_customer_phone.get()
                if _cs_phone_f:
                    from services.conversation_state import increment_frustration as _cs_inc_frust
                    _new_count = await _cs_inc_frust(tenant_id, _cs_phone_f)
                    logger.info(f"🧩 T14 frustration_count incremented to {_new_count}")
                    if _frust_signals >= 3:
                        from services.conversation_state import set_frustration_mode as _cs_set_fmode
                        await _cs_set_fmode(tenant_id, _cs_phone_f, True)
        except Exception as _t14_err:
            logger.debug(f"T14 frustration detection skipped: {_t14_err}")

        executor = await get_agent_executable_for_tenant(tenant_id)
        logger.info(f"🧠 Invoking Agent for {external_user_id}...")

        # C3: Check engine mode and log which engine is being used.
        # MULTI path: populate ctx.extra with social context so graph.run_turn
        # can wire it into AgentState (phase 5 wiring via ctx.extra).
        try:
            from services.engine_router import get_engine_for_tenant

            engine = await get_engine_for_tenant(tenant_id)
            logger.info(f"🎛️ Engine mode for tenant {tenant_id}: {engine.name}")
            # When multi-agent engine is active, ctx.extra must carry social context.
            # The TurnContext is created per-dispatch so we store it on the engine
            # via a thread-local is not feasible. Instead, the social_ctx dict is
            # already available and will be passed when TurnContext dispatch is
            # fully wired (phase 9 integration wiring — currently buffer_task
            # still dispatches through executor.ainvoke for both paths).
        except Exception as eng_err:
            logger.warning(f"⚠️ Engine router check failed, using default: {eng_err}")

        # Inyectar contexto especial si es necesario
        special_context = []

        # Contexto de archivos multimedia
        if has_recent_media:
            channel_name = "WhatsApp"
            if channel_type == "instagram":
                channel_name = "Instagram"
            elif channel_type == "facebook":
                channel_name = "Facebook"
            elif channel_type == "chatwoot":
                channel_name = "el chat"

            # =======================================================
            # MULTI-ATTACHMENT PROCESSING (Fase 2)
            # =======================================================
            all_attachments = []  # each item: {url, mime_type, type, description, index}
            try:
                # Fetch all media attachments from this conversation (last 20 messages)
                rows = await pool.fetch(
                    """
                    SELECT id, content_attributes
                    FROM chat_messages
                    WHERE conversation_id = $1 AND tenant_id = $2
                      AND content_attributes IS NOT NULL
                      AND (content_attributes::text LIKE '%"type":"image"%' OR content_attributes::text LIKE '%"type":"document"%')
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    conversation_id,
                    tenant_id,
                )
                index = 0
                for row in rows:
                    attrs = row["content_attributes"]
                    if isinstance(attrs, str):
                        attrs = json.loads(attrs)
                    if isinstance(attrs, list):
                        for att in attrs:
                            media_type = att.get("type")
                            if media_type not in ("image", "document"):
                                continue
                            url = att.get("url")
                            if not url:
                                continue
                            mime_type = att.get("mime_type", "")
                            description = att.get("description")
                            all_attachments.append(
                                {
                                    "url": url,
                                    "mime_type": mime_type,
                                    "type": media_type,
                                    "description": description,
                                    "index": index,
                                }
                            )
                            index += 1
                # Deduplicate by URL (keep first occurrence)
                seen_urls = set()
                unique_attachments = []
                for att in all_attachments:
                    if att["url"] not in seen_urls:
                        seen_urls.add(att["url"])
                        unique_attachments.append(att)
                all_attachments = unique_attachments
                # Apply limits
                images = [
                    a for a in all_attachments if a["mime_type"].startswith("image/")
                ]
                pdfs = [
                    a for a in all_attachments if a["mime_type"] == "application/pdf"
                ]
                if len(images) > MAX_IMAGES or len(pdfs) > MAX_PDFS:
                    logger.warning(
                        f"超越MAX_ATTACHMENTS, truncating (images={len(images)} pdfs={len(pdfs)})"
                    )
                    # Truncate: keep first MAX_IMAGES images and first MAX_PDFS PDFs
                    images = images[:MAX_IMAGES]
                    pdfs = pdfs[:MAX_PDFS]
                    # Recombine preserving order? Simpler: keep all attachments but skip extra ones.
                    # We'll just keep the first MAX_IMAGES images and MAX_PDFS PDFs.
                    # Since order may be mixed, we'll just truncate all_attachments to first MAX_IMAGES+MAX_PDFS.
                    # For simplicity, we'll just keep first MAX_IMAGES+MAX_PDFS attachments.
                    all_attachments = all_attachments[: MAX_IMAGES + MAX_PDFS]
                # Batch analyze attachments missing descriptions
                attachments_to_analyze = [
                    a for a in all_attachments if not a.get("description")
                ]
                if attachments_to_analyze and analyze_attachments_batch:
                    logger.info(
                        f"🔄 Batch analyzing {len(attachments_to_analyze)} attachments"
                    )
                    analyses = await analyze_attachments_batch(
                        attachments=[
                            {
                                "url": a["url"],
                                "mime_type": a["mime_type"],
                                "index": a["index"],
                            }
                            for a in attachments_to_analyze
                        ],
                        tenant_id=tenant_id,
                    )
                    # Update descriptions in all_attachments based on analyses
                    for analysis in analyses:
                        idx = analysis.get("index")
                        if idx is not None and idx < len(all_attachments):
                            all_attachments[idx]["description"] = analysis.get(
                                "vision_description"
                            )
                # Classify each attachment and save to patient_documents if patient exists
                if patient_row and classify_message:
                    patient_id = patient_row["id"]
                    for att in all_attachments:
                        classification = await classify_message(
                            text="",
                            tenant_id=tenant_id,
                            vision_description=att.get("description"),
                        )
                        is_payment = classification.get("is_payment", False)
                        document_type = "payment_receipt" if is_payment else "clinical"
                        # Prepare source_details JSONB
                        source_details = {
                            "vision_description": att.get("description"),
                            "attachment_index": att["index"],
                            "mime_type": att["mime_type"],
                        }
                        # Determine file_name from URL
                        file_name = (
                            att["url"].split("/")[-1] or f"attachment_{att['index']}"
                        )
                        # Insert into patient_documents (ignore duplicate on unique constraint)
                        try:
                            await pool.execute(
                                """
                                INSERT INTO patient_documents
                                (tenant_id, patient_id, file_name, file_path, mime_type, document_type, source, source_details)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                                ON CONFLICT (tenant_id, patient_id, file_name) DO NOTHING
                                """,
                                tenant_id,
                                patient_id,
                                file_name,
                                att["url"],  # file_path = URL for now
                                att["mime_type"],
                                document_type,
                                "whatsapp",
                                json.dumps(source_details),
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to save attachment to patient_documents: {e}"
                            )
                # Generate LLM summary if we have attachments and patient
                if patient_row and generate_attachment_summary and all_attachments:
                    summary = await generate_attachment_summary(
                        tenant_id=tenant_id,
                        patient_id=patient_row["id"],
                        attachments=all_attachments,
                    )
                    if summary:
                        # Save to clinical_record_summaries
                        try:
                            await pool.execute(
                                """
                                INSERT INTO clinical_record_summaries
                                (tenant_id, patient_id, conversation_id, summary_text, attachments_count, attachments_types)
                                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                                ON CONFLICT (tenant_id, patient_id, conversation_id) DO UPDATE
                                SET summary_text = EXCLUDED.summary_text,
                                    attachments_count = EXCLUDED.attachments_count,
                                    attachments_types = EXCLUDED.attachments_types
                                """,
                                tenant_id,
                                patient_row["id"],
                                conversation_id,
                                summary,
                                len(all_attachments),
                                json.dumps([a["type"] for a in all_attachments]),
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to save clinical_record_summaries: {e}"
                            )
            except Exception as e:
                logger.warning(f"Multi-attachment processing error (non-fatal): {e}")
                # Continue with single-attachment context

            # =======================================================
            # END MULTI-ATTACHMENT PROCESSING
            # =======================================================

            media_context = "IMPORTANTE: El paciente acaba de enviar "
            if "image" in media_types and "document" in media_types:
                media_context += "imágenes y documentos"
            elif "image" in media_types:
                media_context += "una imagen"
            elif "document" in media_types:
                media_context += "un documento"

            media_context += f" por {channel_name}. "

            # Check if interlocutor has linked minors — if so, ask who the file belongs to
            try:
                _guardian_phones = [re.sub(r'\D', '', external_user_id or '')]
                if resolved_patient_phone and re.sub(r'\D', '', resolved_patient_phone) not in _guardian_phones:
                    _guardian_phones.append(re.sub(r'\D', '', resolved_patient_phone))
                minor_count = (
                    await pool.fetchval(
                        "SELECT COUNT(*) FROM patients WHERE tenant_id = $1 AND REGEXP_REPLACE(COALESCE(guardian_phone, ''), '[^0-9]', '', 'g') = ANY(SELECT REGEXP_REPLACE(v, '[^0-9]', '', 'g') FROM unnest($2::text[]) AS v)",
                        tenant_id,
                        _guardian_phones,
                    )
                    or 0
                )
            except Exception:
                minor_count = 0

            # Check if patient exists before mentioning medical record
            has_patient = False
            try:
                clean_ext = (
                    external_user_id.replace("+", "") if external_user_id else ""
                )
                patient_exists = await pool.fetchval(
                    """
                    SELECT id FROM patients WHERE tenant_id = $1 AND (
                        phone_number = $2 OR phone_number = $3 OR
                        instagram_psid = $2 OR facebook_psid = $2
                    ) LIMIT 1
                """,
                    tenant_id,
                    external_user_id,
                    clean_ext,
                )
                has_patient = patient_exists is not None
            except Exception:
                has_patient = False

            # Classify image BEFORE branching — needed in ALL paths (patient, non-patient)
            is_classified_payment = False
            is_classified_medical = False
            try:
                from services.image_classifier import classify_message as _clf_msg

                _clf_text = messages[-1] if messages else ""
                _clf_result = await _clf_msg(
                    text=_clf_text,
                    tenant_id=tenant_id,
                    vision_description=vision_context_str
                    if vision_context_str
                    else None,
                )
                is_classified_payment = _clf_result.get("is_payment", False)
                is_classified_medical = _clf_result.get("is_medical", False)
                logger.info(
                    f"🖼️ Pre-classification: payment={is_classified_payment}, medical={is_classified_medical}"
                )
            except Exception as _pre_clf_err:
                logger.debug(f"Pre-classification skipped: {_pre_clf_err}")

            if has_patient and minor_count > 0:
                media_context += (
                    "IMPORTANTE: Este paciente tiene hijos/menores vinculados. "
                    "ANTES de confirmar que guardaste el archivo, PREGUNTÁ: 'Este archivo es para tu ficha o para la de [nombre del hijo/a]?' "
                    "Si es para un menor, usá la tool 'reassign_document' con el phone_interno del menor (ej: +549...-M1) "
                    "que aparece en el contexto de HIJOS/MENORES VINCULADOS. "
                    "Si es para el interlocutor, no hagas nada extra, ya está guardado."
                )
            elif has_patient:
                # Check if patient has a pending payment (seña) — if so, the image is likely a payment receipt
                has_pending_payment = False
                payment_on_cooldown = False

                # Check cooldown first - if payment verification was recently attempted, skip re-triggering
                try:
                    from services.payment_cooldown import check_payment_cooldown

                    payment_on_cooldown = await check_payment_cooldown(
                        tenant_id, external_user_id
                    )
                except Exception as cooldown_err:
                    logger.warning(f"Error checking payment cooldown: {cooldown_err}")

                # Fase 2 - Task 2.3: Integrate image classifier
                # If cooldown is active, skip payment verification context
                if payment_on_cooldown:
                    media_context += "Confirmo que recibí tu archivo. Lo guardamos en tu ficha médica."
                else:
                    # Classify the image using Vision context and message text
                    classification_result = {
                        "classification": "neutral",
                        "is_payment": False,
                        "is_medical": False,
                    }
                    try:
                        # NO re-importar classify_message acá: ya está importado a nivel
                        # módulo (~línea 22). Un import local lo vuelve variable local de
                        # TODA la función y rompe la referencia previa (~2865) con
                        # UnboundLocalError al procesar imagen + texto juntos.
                        # Combine text messages and vision context for classification
                        text_for_classification = messages[-1] if messages else ""
                        classification_result = await classify_message(
                            text=text_for_classification,
                            tenant_id=tenant_id,
                            vision_description=vision_context_str
                            if vision_context_str
                            else None,
                        )
                        logger.info(
                            f"🖼️ Image classification: {classification_result.get('classification')} "
                            f"(payment={classification_result.get('is_payment')}, "
                            f"medical={classification_result.get('is_medical')})"
                        )
                    except Exception as clf_err:
                        logger.warning(f"Error in image classification: {clf_err}")
                        # Continue with default behavior (treat as potentially payment if pending)

                    # If classified as MEDICAL, override payment detection
                    is_classified_medical = classification_result.get(
                        "is_medical", False
                    )
                    is_classified_payment = classification_result.get(
                        "is_payment", False
                    )
                    try:
                        clean_ext_pay = (
                            external_user_id.replace("+", "")
                            if external_user_id
                            else ""
                        )
                        pending_apt = await pool.fetchval(
                            """
                            SELECT a.id FROM appointments a
                            JOIN patients p ON p.id = a.patient_id
                            WHERE a.tenant_id = $1
                              AND (p.phone_number = $2 OR p.phone_number = $3
                                   OR REGEXP_REPLACE(p.phone_number, '[^0-9]', '', 'g') = REGEXP_REPLACE($2, '[^0-9]', '', 'g'))
                              AND a.status IN ('scheduled', 'confirmed')
                              AND (a.payment_status IS NULL OR a.payment_status = 'pending' OR a.payment_status = 'partial')
                            ORDER BY a.appointment_datetime ASC LIMIT 1
                        """,
                            tenant_id,
                            external_user_id,
                            clean_ext_pay,
                        )
                        has_pending_payment = pending_apt is not None
                    except Exception as pay_check_err:
                        logger.warning(
                            f"Error checking pending payment: {pay_check_err}"
                        )

                    # --- Fallback: check treatment plan pending balance ---
                    has_pending_plan = False
                    if not has_pending_payment:
                        try:
                            pending_plan = await pool.fetchval(
                                """
                                SELECT tp.id FROM treatment_plans tp
                                LEFT JOIN (
                                    SELECT plan_id, SUM(amount) as total_paid
                                    FROM treatment_plan_payments WHERE tenant_id = $1
                                    GROUP BY plan_id
                                ) pay ON pay.plan_id = tp.id
                                WHERE tp.tenant_id = $1 AND tp.patient_id = $2
                                  AND tp.status IN ('approved', 'in_progress')
                                  AND tp.approved_total > COALESCE(pay.total_paid, 0)
                                LIMIT 1
                                """,
                                tenant_id,
                                patient_row["id"],
                            )
                            if pending_plan:
                                has_pending_payment = True
                                has_pending_plan = True
                                logger.info(
                                    f"💰 buffer_task: patient has pending treatment plan balance, "
                                    f"activating payment receipt context (plan_id={pending_plan})"
                                )
                        except Exception as plan_check_err:
                            logger.warning(
                                f"Error checking plan pending: {plan_check_err}"
                            )

                    if has_pending_payment:
                        # Fase 2 - Task 2.3: Override payment context if classified as medical
                        # Medical documents take priority over payment verification
                        if is_classified_medical:
                            logger.info(
                                f"🖼️ Image classified as MEDICAL, overriding payment context"
                            )
                            media_context += "Responde confirmando que recibiste el archivo y que ya lo guardaste en su ficha médica para que la Dra. lo vea. Usa un tono amable y profesional."
                        elif is_classified_payment:
                            # Explicitly classified as payment - inject payment verification context
                            if has_pending_plan:
                                media_context += (
                                    "PROBABLE COMPROBANTE DE PAGO: El paciente tiene un plan de tratamiento con saldo pendiente y acaba de enviar una imagen/documento. "
                                    "Es MUY probable que sea un comprobante de transferencia bancaria para abonar una cuota del plan. "
                                    "ACCIÓN OBLIGATORIA: Usá 'verify_payment_receipt' para verificar el comprobante. "
                                    "Pasá la descripción de la imagen del CONTEXTO VISUAL como 'receipt_description' y el monto que detectes como 'amount_detected'. "
                                    "NO digas 'ya lo guardé en tu ficha'. Decí 'Recibí tu comprobante, voy a verificarlo' y ejecutá la tool. "
                                    "Si la verificación es exitosa → confirmá el pago al plan. Si falla → explicá qué falló."
                                )
                            else:
                                media_context += (
                                    "PROBABLE COMPROBANTE DE PAGO: El paciente tiene un turno con seña pendiente y acaba de enviar una imagen/documento. "
                                    "Es MUY probable que sea un comprobante de transferencia bancaria. "
                                    "ACCIÓN OBLIGATORIA: Usá 'verify_payment_receipt' para verificar el comprobante. "
                                    "Pasá la descripción de la imagen del CONTEXTO VISUAL como 'receipt_description' y el monto que detectes como 'amount_detected'. "
                                    "NO digas 'ya lo guardé en tu ficha'. Decí 'Recibí tu comprobante, voy a verificarlo' y ejecutá la tool. "
                                    "Si la verificación es exitosa → confirmá el pago. Si falla → explicá qué falló."
                                )
                        else:
                            # Not classified - use legacy behavior with pending payment check
                            if has_pending_plan:
                                media_context += (
                                    "PROBABLE COMPROBANTE DE PAGO: El paciente tiene un plan de tratamiento con saldo pendiente y acaba de enviar una imagen/documento. "
                                    "Es MUY probable que sea un comprobante de transferencia bancaria para abonar una cuota del plan. "
                                    "ACCIÓN OBLIGATORIA: Usá 'verify_payment_receipt' para verificar el comprobante. "
                                    "Pasá la descripción de la imagen del CONTEXTO VISUAL como 'receipt_description' y el monto que detectes como 'amount_detected'. "
                                    "NO digas 'ya lo guardé en tu ficha'. Decí 'Recibí tu comprobante, voy a verificarlo' y ejecutá la tool. "
                                    "Si la verificación es exitosa → confirmá el pago al plan. Si falla → explicá qué falló."
                                )
                            else:
                                media_context += (
                                    "PROBABLE COMPROBANTE DE PAGO: El paciente tiene un turno con seña pendiente y acaba de enviar una imagen/documento. "
                                    "Es MUY probable que sea un comprobante de transferencia bancaria. "
                                    "ACCIÓN OBLIGATORIA: Usá 'verify_payment_receipt' para verificar el comprobante. "
                                    "Pasá la descripción de la imagen del CONTEXTO VISUAL como 'receipt_description' y el monto que detectes como 'amount_detected'. "
                                    "NO digas 'ya lo guardé en tu ficha'. Decí 'Recibí tu comprobante, voy a verificarlo' y ejecutá la tool. "
                                    "Si la verificación es exitosa → confirmá el pago. Si falla → explicá qué falló."
                                )
                    else:
                        # No pending payment for THIS person
                        if is_classified_payment:
                            # Image looks like a receipt but this patient has no debt
                            # → likely paying on behalf of a family member
                            media_context += (
                                "COMPROBANTE DE PAGO RECIBIDO pero este contacto NO tiene turnos ni planes con saldo pendiente. "
                                "Es probable que esté pagando POR UN FAMILIAR (hijo/a, padre/madre, etc.). "
                                "ACCIÓN: Preguntá amablemente: 'Recibí tu comprobante! ¿Este pago es para vos o para un familiar? "
                                "Si es para otra persona, decime su nombre así lo asocio a su ficha.' "
                                "Cuando te diga el nombre, usá la tool 'link_payment_to_patient' con el nombre del paciente, "
                                "la descripción del comprobante (del CONTEXTO VISUAL), el monto detectado, y la relación (hijo, madre, etc.). "
                                "La tool busca al paciente, vincula el comprobante a su ficha, registra el pago y notifica a la clínica. "
                                "NO digas que ya verificaste el pago. Esperá a saber PARA QUIÉN es."
                            )
                        else:
                            media_context += "Responde confirmando que recibiste el archivo y que ya lo guardaste en su ficha médica para que la Dra. lo vea. Usa un tono amable y profesional."
            else:
                # Contact is NOT a patient
                if is_classified_payment:
                    # Non-patient sending a payment receipt → paying for someone else
                    media_context += (
                        "COMPROBANTE DE PAGO RECIBIDO de un contacto que NO es paciente registrado. "
                        "Es MUY probable que esté pagando POR UN FAMILIAR que sí es paciente (hijo/a pagando por padre/madre, etc.). "
                        "ACCIÓN: Preguntá amablemente: 'Recibí tu comprobante! ¿Para qué paciente es este pago? "
                        "Decime el nombre completo así lo asocio a su ficha.' "
                        "Cuando te diga el nombre, usá la tool 'link_payment_to_patient' con el nombre del paciente, "
                        "la descripción del comprobante (del CONTEXTO VISUAL), el monto detectado, y la relación. "
                        "La tool busca al paciente, vincula el comprobante a su ficha, registra el pago y notifica a la clínica. "
                        "NO digas que verificaste ni guardaste nada HASTA que el interlocutor te diga para quién es."
                    )
                else:
                    media_context += (
                        "NOTA: Este contacto AUN NO tiene ficha de paciente registrada. "
                        "NO digas que guardaste el archivo en su ficha porque no existe. "
                        "Si hay CONTEXTO VISUAL disponible, usalo para responder sobre la imagen. "
                        "Si el contacto necesita agendar un turno, pedile sus datos (nombre, telefono, DNI) primero."
                    )

            special_context.append(media_context)

        # Contexto de respuesta a seguimiento post-atención
        if is_followup_response and followup_context:
            special_context.append(followup_context)
            logger.info("✅ Contexto de seguimiento post-atención inyectado")

        # Meta Direct channel rule: only ask phone if patient doesn't have one
        if channel_type in ("instagram", "facebook"):
            # Check if this patient already has a real phone number in DB
            patient_has_phone = False
            if patient_row:
                existing_phone = patient_row.get("phone_number") or ""
                patient_has_phone = bool(
                    existing_phone
                ) and not existing_phone.startswith("SIN-TEL")

            if patient_has_phone:
                special_context.append(
                    f"REGLA CANAL ({channel_type.upper()}): El paciente escribe por {channel_type.capitalize()} "
                    f"pero YA tiene teléfono registrado ({patient_row.get('phone_number')}). "
                    "NO le pidas teléfono, ya lo tenés. Podés usar todas las herramientas normalmente."
                )
                logger.info(
                    f"IG/FB patient already has phone, skipping phone-request rule"
                )
            else:
                special_context.append(
                    f"REGLA CANAL ({channel_type.upper()}): El paciente escribe por {channel_type.capitalize()}. "
                    "En este canal NO tenemos su numero de telefono. "
                    "ANTES de poder agendar un turno, registrar datos o buscar turnos, DEBES pedirle su numero de telefono con codigo de area. "
                    "Sin telefono no podes usar ninguna herramienta de gestion de pacientes. "
                    'Ejemplo: "Para poder ayudarte con turnos, necesito tu numero de telefono con codigo de area. Me lo compartes?"'
                )
                logger.info(
                    f"Injected Meta Direct phone-request rule for {channel_type}"
                )

        # INYECCIÓN FORZADA: Si el paciente ya existe, meter sus datos en el input
        # para que sea IMPOSIBLE que el agente los ignore y los pida de nuevo
        if patient_row and (
            patient_row.get("first_name") or patient_row.get("last_name")
        ):
            p_fn = patient_row.get("first_name") or ""
            p_ln = patient_row.get("last_name") or ""
            p_dn = patient_row.get("dni") or ""
            p_em = patient_row.get("email") or ""
            forced_context = (
                f"[DATOS DEL PACIENTE - YA REGISTRADO EN EL SISTEMA - NO PEDIR ESTOS DATOS]\n"
                f"Nombre: {p_fn} {p_ln}\n"
            )
            if p_dn:
                forced_context += f"DNI: {p_dn}\n"
            if p_em:
                forced_context += f"Email: {p_em}\n"
            forced_context += "INSTRUCCIÓN: Este paciente YA ESTÁ en la base de datos. NO le pidas nombre, apellido ni DNI. Usá estos datos directamente para agendar.\n"
            special_context.insert(0, forced_context)
            logger.info(
                f"💉 Forced patient context injected: {p_fn} {p_ln} (DNI: {p_dn})"
            )

        # Aplicar todos los contextos especiales
        if special_context:
            context_block = "\n\n".join(special_context)
            user_input = f"{context_block}\n\nMensaje del paciente: {user_input}"

        # --- Retry Logic con Exponential Backoff ---
        response_text = ""
        media_urls = []
        max_retries = 3
        token_cb = None

        # Import callback (non-fatal if unavailable)
        _get_cb = None
        try:
            from langchain_community.callbacks import get_openai_callback as _get_cb_fn

            _get_cb = _get_cb_fn
        except ImportError:
            logger.warning(
                "⚠️ get_openai_callback not available, tokens will be estimated"
            )

        # --- Multi-agent dispatch (C3 F3) ---
        # When the tenant's ai_engine_mode is "multi", route through the LangGraph
        # supervisor + specialist system. Falls back to SoloEngine if the multi-agent
        # fails (response_text stays "" and the retry loop below runs the solo path).
        _engine = locals().get('engine')
        if _engine is not None and hasattr(_engine, 'name') and _engine.name == 'multi':
            try:
                from services.engine_router import TurnContext

                _extra = dict(_social_ctx) if '_social_ctx' in dir() and _social_ctx else {}

                _multi_ctx = TurnContext(
                    tenant_id=tenant_id,
                    phone_number=external_user_id,
                    user_message=user_input,
                    thread_id=str(conversation_id),
                    extra=_extra,
                )

                _multi_result = await _engine.process_turn(_multi_ctx)
                response_text = _multi_result.output or "[Sin respuesta]"
                token_cb = None
                logger.info(
                    f"🤖 Multi-agent dispatch OK for tenant {tenant_id} — "
                    f"agent={_multi_result.agent_used} "
                    f"duration={_multi_result.duration_ms}ms"
                )
            except Exception as _multi_err:
                logger.exception(
                    f"⚠️ Multi-agent dispatch failed for tenant {tenant_id}: {_multi_err} "
                    f"— falling back to SoloEngine"
                )
                response_text = ""  # Reset so the solo retry loop handles it

        # Solo retry loop — skip if multi-agent already produced a response
        response = {}  # Guard: multi-agent may skip this loop, prevent UnboundLocalError on response.get() below
        for attempt in range(max_retries):
            if response_text:
                break  # Multi-agent handled it
            try:
                if _get_cb:
                    with _get_cb() as cb:
                        response = await executor.ainvoke(
                            {
                                "input": user_input,
                                "chat_history": chat_history,
                                "system_prompt": system_prompt,
                            }
                        )
                        token_cb = cb
                else:
                    response = await executor.ainvoke(
                        {
                            "input": user_input,
                            "chat_history": chat_history,
                            "system_prompt": system_prompt,
                        }
                    )
                response_text = response.get("output", "") or "[Sin respuesta]"
                # v8.2: Statement dedup — track and suppress identical agent messages
                try:
                    if response_text and len(response_text.strip()) > 10:
                        from services.conversation_state import track_statement as _cs_track

                        _hash = _hash_statement(response_text.strip())
                        _cs_track_phone = current_customer_phone.get() if current_customer_phone else None
                        if _cs_track_phone:
                            _count = await _cs_track(tenant_id, _cs_track_phone, _hash)
                            if _count >= 3:
                                logger.warning(
                                    f"🔇 STATEMENT DEDUP: suppressing message (hash={_hash}, count={_count})"
                                    f" — original text: {response_text[:80]!r}"
                                )
                                response_text = ""  # Silencio total — NUNCA mandar texto interno al paciente
                            elif _count == 2:
                                logger.info(
                                    f"⚠️ STATEMENT DEDUP: message repeated (hash={_hash}, count={_count})"
                                    f" — will suppress on next occurrence"
                                )
                except Exception as _dedup_err:
                    logger.debug(f"Statement dedup failed (non-blocking): {_dedup_err}")

                # v8.3: Error post-processing — strip BOOK_ERROR codes from patient output
                # (resolve-13-booking-errors T13 fix)
                if response_text:
                    try:
                        response_text = _handle_agent_error(response_text)
                    except Exception as _err_post_err:
                        logger.debug(f"Error post-processing skipped: {_err_post_err}")

                # Bug #9: Extract intermediate_steps to know if a tool was actually called
                intermediate_steps = response.get("intermediate_steps", [])
                tool_was_called = len(intermediate_steps) > 0
                cb_tokens = token_cb.total_tokens if token_cb else 0

                # --- BOOKING_FLOW: Log all tools called by LLM ---
                _tools_names = []
                for _step in intermediate_steps:
                    if isinstance(_step, tuple) and len(_step) > 0:
                        _tn = _step[0].get("name", "") if hasattr(_step[0], "get") else ""
                        if not _tn and hasattr(_step[0], "tool"):
                            _tn = _step[0].tool
                        if _tn:
                            _tools_names.append(_tn)
                logger.info(
                    f"📊 BOOKING_FLOW | LLM_RESULT | tools={_tools_names} | response={response_text[:150]!r} | tokens={cb_tokens}"
                )

                # --- Bug #4 Phase D: Output-side state guard ---
                # Check if LLM called check_availability when it should have called confirm_slot
                state_retry_count = 0
                if get_state is not None and current_customer_phone is not None:
                    try:
                        phone = current_customer_phone.get()
                        if phone:
                            prev_state = await get_state(tenant_id, phone)
                            prev_state_str = (
                                prev_state.get("state", "IDLE")
                                if isinstance(prev_state, dict)
                                else "IDLE"
                            )

                            # If previous state was OFFERED_SLOTS and LLM called check_availability
                            if prev_state_str == "OFFERED_SLOTS":
                                intermediate_steps = response.get(
                                    "intermediate_steps", []
                                )
                                tools_called = []
                                for step in intermediate_steps:
                                    if isinstance(step, tuple) and len(step) > 0:
                                        tool_name = (
                                            step[0].get("name", "")
                                            if hasattr(step[0], "get")
                                            else str(step[0])
                                        )
                                        tools_called.append(tool_name)

                                user_msg = "\n".join(messages)
                                has_research_intent = _detect_research_intent(user_msg)

                                # If check_availability was called without research intent, retry
                                if (
                                    "check_availability" in tools_called
                                    and not has_research_intent
                                    and state_retry_count < MAX_STATE_RETRIES
                                ):
                                    logger.warning(
                                        f"🔒 STATE_GUARD: LLM called check_availability in OFFERED_SLOTS state. "
                                        f"tenant_id={tenant_id} phone={phone} prev_state={prev_state_str} "
                                        f"tools_called={tools_called} user_msg={user_msg[:50]}..."
                                    )
                                    state_retry_count += 1

                                    # Retry with stronger nudge
                                    nudge_input = f"{user_input}\n\n[SISTEMA: IMPORTANTE - El paciente YA tiene opciones de turnos ofrecidas. "
                                    f"Si el paciente quiere SELECCIONAR un turno, usa 'confirm_slot', NO 'check_availability'. "
                                    f"Ve a 'confirm_slot' directamente.]"

                                    if _get_cb:
                                        with _get_cb() as cb3:
                                            response3 = await executor.ainvoke(
                                                {
                                                    "input": nudge_input,
                                                    "chat_history": chat_history,
                                                    "system_prompt": system_prompt,
                                                }
                                            )
                                    else:
                                        response3 = await executor.ainvoke(
                                            {
                                                "input": nudge_input,
                                                "chat_history": chat_history,
                                                "system_prompt": system_prompt,
                                            }
                                        )
                                    retry_text = response3.get("output", "")
                                    if retry_text and len(retry_text) > len(
                                        response_text
                                    ):
                                        response_text = retry_text
                                        logger.info(f"🔒 STATE_GUARD: Retry successful")
                                    else:
                                        logger.warning(
                                            f"🔒 STATE_GUARD: Retry failed, degrading gracefully"
                                        )

                            # SLOT_LOCKED output guard (fix-minor-booking-flow T2.1)
                            # If LLM is in SLOT_LOCKED state and calls check_availability, retry with stronger instructions
                            elif prev_state_str == "SLOT_LOCKED":
                                _sl_tools_called = []
                                _sl_steps = response.get("intermediate_steps", [])
                                for _sl_step in _sl_steps:
                                    if isinstance(_sl_step, tuple) and len(_sl_step) > 0:
                                        _sl_tn = (
                                            _sl_step[0].get("name", "")
                                            if hasattr(_sl_step[0], "get")
                                            else str(_sl_step[0])
                                        )
                                        _sl_tools_called.append(_sl_tn)

                                if "check_availability" in _sl_tools_called:
                                    _sl_retry_count = 0
                                    logger.warning(
                                        f"🔒 SLOT_LOCKED GUARD: LLM called check_availability in SLOT_LOCKED state. "
                                        f"tenant_id={tenant_id} phone={phone} tools_called={_sl_tools_called}"
                                    )

                                    # Retry with strong nudge to use book_appointment
                                    _sl_retry_count += 1
                                    logger.warning(
                                        f"🔒 SLOT_LOCKED GUARD: Retry attempt {_sl_retry_count}"
                                    )
                                    _sl_nudge = (
                                        f"{user_input}\n\n[SISTEMA: IMPORTANTE - Estás en estado SLOT_LOCKED. "
                                        f"Ya hay un turno pre-reservado. NO llames check_availability. "
                                        f"Debes llamar book_appointment con los datos del turno bloqueado. "
                                        f"NO check_availability. Usá book_appointment.]"
                                    )

                                    if _get_cb:
                                        with _get_cb() as _sl_cb:
                                            _sl_response = await executor.ainvoke(
                                                {
                                                    "input": _sl_nudge,
                                                    "chat_history": chat_history,
                                                    "system_prompt": system_prompt,
                                                }
                                            )
                                    else:
                                        _sl_response = await executor.ainvoke(
                                            {
                                                "input": _sl_nudge,
                                                "chat_history": chat_history,
                                                "system_prompt": system_prompt,
                                            }
                                        )

                                    _sl_retry_text = _sl_response.get("output", "")
                                    # Check if retry still calls check_availability
                                    _sl_retry_steps = _sl_response.get("intermediate_steps", [])
                                    _sl_retry_tools = []
                                    for _sl_rs in _sl_retry_steps:
                                        if isinstance(_sl_rs, tuple) and len(_sl_rs) > 0:
                                            _sl_rtn = (
                                                _sl_rs[0].get("name", "")
                                                if hasattr(_sl_rs[0], "get")
                                                else str(_sl_rs[0])
                                            )
                                            _sl_retry_tools.append(_sl_rtn)

                                    if "check_availability" in _sl_retry_tools:
                                        logger.warning(
                                            f"🔒 SLOT_LOCKED GUARD: Retry also called check_availability. Returning error. "
                                            f"retry_tools={_sl_retry_tools}"
                                        )
                                        response_text = "No se pudo completar el agendamiento. Derivando a un operador."
                                    elif _sl_retry_text and len(_sl_retry_text) > len(response_text):
                                        response_text = _sl_retry_text
                                        logger.info(f"🔒 SLOT_LOCKED GUARD: Retry successful — LLM proceeded with booking.")
                                    else:
                                        logger.warning(f"🔒 SLOT_LOCKED GUARD: Retry failed, degrading gracefully")
                    except Exception as state_guard_err:
                        logger.warning(
                            f"[STATE_GUARD] Output guard failed: {state_guard_err}"
                        )

                # SAFETY NET: Detect "un momento" / "voy a buscar" dead-end responses
                # If agent said it will do something but didn't actually execute a tool,
                # re-invoke with a nudge to actually complete the action.
                # Bug #9: Only trigger if NO tool was called. If a tool ran, the response
                # is a presentation issue, not a dead-end — re-invoking would duplicate side effects.
                dead_end_phrases = [
                    "un momento",
                    "un instante",
                    "dejame buscar",
                    "voy a buscar",
                    "voy a verificar",
                    "voy a consultar",
                    "voy a agendar",
                    "voy a proceder",
                    "ya verifico",
                    "ya busco",
                    "permití",
                    "dame un segundo",
                ]
                response_lower = response_text.lower()
                is_dead_end = any(
                    phrase in response_lower for phrase in dead_end_phrases
                )
                # Only trigger if the response is short (< 200 chars) — real results are longer
                # Bug #9: and NOT tool_was_called — if a tool ran, don't re-invoke
                if (
                    is_dead_end
                    and not tool_was_called
                    and len(response_text) < 200
                    and attempt < max_retries - 1
                ):
                    logger.warning(
                        f"⚠️ Dead-end response detected: '{response_text[:80]}...' — re-invoking agent"
                    )
                    # Re-invoke with the same input + nudge
                    nudge_input = f"{user_input}\n\n[SISTEMA: Ejecutá la tool ahora y respondé con el resultado. NO digas 'un momento'.]"
                    try:
                        if _get_cb:
                            with _get_cb() as cb2:
                                response2 = await executor.ainvoke(
                                    {
                                        "input": nudge_input,
                                        "chat_history": chat_history,
                                        "system_prompt": system_prompt,
                                    }
                                )
                                token_cb = cb2
                        else:
                            response2 = await executor.ainvoke(
                                {
                                    "input": nudge_input,
                                    "chat_history": chat_history,
                                    "system_prompt": system_prompt,
                                }
                            )
                        retry_text = response2.get("output", "")
                        if retry_text and len(retry_text) > len(response_text):
                            response_text = retry_text
                            logger.info(
                                f"🔄 Dead-end recovery successful: {response_text[:50]}..."
                            )
                    except Exception as e2:
                        logger.warning(f"⚠️ Dead-end recovery failed: {e2}")

                break
            except Exception as e:
                logger.warning(
                    f"⚠️ process_buffer_task_agent_error (intento {attempt + 1}/{max_retries}): {str(e)}"
                )
                if attempt < max_retries - 1:
                    import asyncio

                    await asyncio.sleep(2**attempt)
                else:
                    logger.exception(
                        "process_buffer_task_agent_error_final", exc_info=e
                    )
                    response_text = "Disculpas, estoy experimentando intermitencias técnicas. Consultame de nuevo en unos minutos."

        # --- PATIENT MEMORY: Extract and store new memories from this conversation ---
        if response_text and patient_row:
            try:
                import asyncio as _mem_asyncio

                _mem_asyncio.create_task(
                    extract_and_store_memories(
                        pool,
                        external_user_id,
                        tenant_id,
                        user_input,
                        response_text,
                        patient_name=f"{patient_row.get('first_name', '')} {patient_row.get('last_name', '')}".strip(),
                    )
                )
                logger.info(f"🧠 Memory extraction queued for {external_user_id}")
            except Exception as mem_store_err:
                logger.warning(f"⚠️ Memory extraction (non-fatal): {mem_store_err}")

        # --- Token Tracking (dual: callback or estimate) ---
        if (
            response_text
            and response_text
            != "Disculpas, estoy experimentando intermitencias técnicas. Consultame de nuevo en unos minutos."
        ):
            try:
                from dashboard.token_tracker import token_tracker, TokenUsage
                from datetime import datetime, timezone as tz

                if token_tracker:
                    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

                    # Use callback tokens if available, otherwise estimate
                    if token_cb and token_cb.total_tokens > 0:
                        input_t = token_cb.prompt_tokens
                        output_t = token_cb.completion_tokens
                        total_t = token_cb.total_tokens
                        logger.info(
                            f"📊 Token source: callback | in={input_t} out={output_t} total={total_t}"
                        )
                    else:
                        # Estimate: ~1 token per 4 chars (conservative for Spanish)
                        input_text = (system_prompt or "") + (user_input or "")
                        input_t = max(len(input_text) // 4, 100)
                        output_t = max(len(response_text) // 4, 20)
                        total_t = input_t + output_t
                        logger.info(
                            f"📊 Token source: estimate | in={input_t} out={output_t} total={total_t}"
                        )

                    usage = TokenUsage(
                        conversation_id=conversation_id,
                        patient_phone=external_user_id,
                        model=model_name,
                        input_tokens=input_t,
                        output_tokens=output_t,
                        total_tokens=total_t,
                        cost_usd=token_tracker.calculate_cost(
                            model_name, input_t, output_t
                        ),
                        timestamp=datetime.now(tz.utc),
                        tenant_id=tenant_id,
                    )
                    await token_tracker.track_usage(usage)
                    # Update tenant totals
                    await pool.execute(
                        "UPDATE tenants SET total_tokens_used = COALESCE(total_tokens_used, 0) + $1, total_tool_calls = COALESCE(total_tool_calls, 0) + 1 WHERE id = $2",
                        total_t,
                        tenant_id,
                    )
                    logger.info(
                        f"📊 Tokens tracked: {total_t} | cost: ${usage.cost_usd}"
                    )
                else:
                    logger.warning("⚠️ token_tracker is None, skipping tracking")
            except Exception as tk_err:
                logger.warning(f"⚠️ Token tracking error (non-fatal): {tk_err}")

        # --- Extracción Multimedia Oculta ---
        if "[LOCAL_IMAGE:" in response_text:
            img_pattern = r"\[LOCAL_IMAGE:(.*?)\]"
            media_urls = re.findall(img_pattern, response_text)
            response_text = re.sub(img_pattern, "", response_text).strip()
            # Limpiar posible basura arrastrada por el tag markdown
            response_text = response_text.replace(
                "¡IMPORTANTE PARA LA IA! El tratamiento cuenta con imágenes. Agrega obligatoriamente el siguiente texto (invisible para el usuario) en tu respuesta para que el sistema le envíe las imágenes:",
                "",
            ).strip()

        # --- DATE VALIDATOR (Bug #1) ---
        # Validate dates in response against canonical dates from tool outputs
        # Fixes DD↔MM swap issue in LLM response text
        if validate_dates_in_response and response.get("intermediate_steps"):
            try:
                response_text = validate_dates_in_response(
                    response_text, response.get("intermediate_steps", [])
                )
            except Exception as dv_err:
                logger.warning(f"⚠️ Date validator error (non-fatal): {dv_err}")

    except Exception as e:
        logger.exception("process_buffer_task_fatal_error", exc_info=e)
        response_text = "Disculpas, estoy experimentando intermitencias. Consultame de nuevo en unos minutos."
        media_urls = []
    finally:
        # Reset ContextVars to avoid state leakage between concurrent background tasks
        _ctx_vars = []
        try:
            from main import (  # type: ignore
                current_customer_phone as _cv_phone,
                current_tenant_id as _cv_tenant,
                current_patient_id as _cv_patient,
                current_source_channel as _cv_channel,
                current_tenant_tz as _cv_tz,
            )
            _ctx_vars = [_cv_phone, _cv_tenant, _cv_patient, _cv_channel, _cv_tz]
        except Exception:
            pass
        for _cv in _ctx_vars:
            try:
                _cv.set(None)
            except Exception:
                pass

    # --- SAFETY STRIP: remove any leaked internal tags before sending ---
    if response_text:
        import re as _re_safety
        # Strip bracket tags like [CONSULTA_PREVIA_REQUISITOS:...], [INTERNAL_*:...], [BOOK_HINT:...], [SYSTEM_NOTE: ...]
        response_text = _re_safety.sub(r"\[(?:CONSULTA_PREVIA_REQUISITOS|INTERNAL_\w+|BOOK_HINT|ACTION_HINT|SYSTEM_NOTE)[:\s\-][^\]]*\]", "", response_text).strip()
        # AG-03: nunca filtrar al paciente las directivas internas crudas del gate de turnos
        response_text = _re_safety.sub(
            r"(?im)^.*\b(?:BOOKING_ALREADY_EXISTS|BOOKING_ALREADY_IN_PROGRESS|AVAILABILITY_BLOCKED)\b.*$",
            "",
            response_text,
        ).strip()

    # --- SUPPRESS ERROR FALLBACK: don't send internal error messages to patients ---
    _ERROR_FALLBACKS = (
        "Disculpas, estoy experimentando intermitencias",
    )
    if response_text and any(response_text.startswith(fb) for fb in _ERROR_FALLBACKS):
        logger.warning(f"🔇 Suppressing error fallback message (not sending to patient): {response_text[:80]}")
        response_text = ""

    # AG-12: nunca enviar el placeholder interno "[Sin respuesta]" al paciente.
    # Si el motor no generó texto, queda vacío y el guard de abajo omite el envío.
    if response_text and response_text.strip() == "[Sin respuesta]":
        logger.warning("🔇 Suppressing placeholder '[Sin respuesta]' — not sending to patient")
        response_text = ""

    # --- SEND RESPONSE ---
    from response_sender import ResponseSender

    if not response_text and not media_urls:
        logger.info(f"🔇 No response to send (empty text, no media) — skipping send for {external_user_id}")
        return

    # --- ABORT-AND-RECOMPUTE (anti "mensajes que se pisan") ---
    # Si el paciente mandó mensajes nuevos mientras corría el LLM, esta respuesta
    # quedó vieja. NO la enviamos: el loop de BufferManager ve el buffer con mensajes,
    # reinicia el debounce y recombina. El mensaje anterior ya está en el historial,
    # así que la próxima respuesta cubre ambos de forma coherente y se evita el
    # doble-reply / contestar el mensaje pasado.
    try:
        from services.relay import get_redis as _get_redis_recompute
        from services.buffer_manager import BufferManager as _BufferManager_recompute

        _r_recompute = _get_redis_recompute()
        if _r_recompute is not None:
            _buffer_key_recompute = _BufferManager_recompute.get_buffer_key(
                provider, tenant_id, external_user_id
            )
            _pending_new = await _r_recompute.llen(_buffer_key_recompute)
            if _pending_new and _pending_new > 0:
                logger.info(
                    f"♻️ ABORT-AND-RECOMPUTE: {_pending_new} mensaje(s) nuevo(s) llegaron durante el LLM — "
                    f"descarto respuesta stale y dejo recombinar para {external_user_id}"
                )
                return
    except Exception as _recompute_err:
        logger.warning(f"abort-and-recompute check failed (non-blocking): {_recompute_err}")

    if provider == "chatwoot":
        account_id = row.get("external_account_id")
        cw_conv_id = row.get("external_chatwoot_id")
        logger.info(
            f"📋 Chatwoot delivery check | conv={conversation_id} | account_id={account_id} | cw_conv_id={cw_conv_id} | row_keys={list(row.keys()) if row else 'None'}"
        )

        if account_id and cw_conv_id:
            logger.info(
                f"🚀 Sending Chatwoot Response | tenant={tenant_id} to={external_user_id} media={len(media_urls)}"
            )
            await ResponseSender.send_sequence(
                tenant_id=tenant_id,
                external_user_id=external_user_id,
                conversation_id=conversation_id,
                provider=provider,
                channel=row.get("channel") or "chatwoot",
                account_id=account_id,
                cw_conv_id=cw_conv_id,
                messages_text=response_text,
                media_urls=media_urls,
            )
        else:
            logger.warning(
                f"Chatwoot IDs missing for conv {conversation_id}. Persisting response locally only."
            )
            # Persist the agent response in DB even if we can't send via Chatwoot
            await pool.execute(
                "INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number) VALUES ($1, $2, 'assistant', $3, $4)",
                tenant_id,
                conversation_id,
                response_text,
                external_user_id,
            )

    elif provider == "ycloud":
        logger.info(
            f"🚀 Sending YCloud Response | tenant={tenant_id} to={external_user_id} media={len(media_urls)}"
        )
        await ResponseSender.send_sequence(
            tenant_id=tenant_id,
            external_user_id=external_user_id,
            conversation_id=conversation_id,
            provider=provider,
            channel="whatsapp",
            account_id="",  # Irrelevant for ycloud
            cw_conv_id="",
            messages_text=response_text,
            media_urls=media_urls,
        )

    elif provider == "meta_direct":
        logger.info(
            f"🚀 Sending Meta Direct Response | tenant={tenant_id} to={external_user_id} channel={row.get('channel')} media={len(media_urls)}"
        )
        await ResponseSender.send_sequence(
            tenant_id=tenant_id,
            external_user_id=external_user_id,
            conversation_id=conversation_id,
            provider=provider,
            channel=row.get("channel") or "facebook",
            account_id="",
            cw_conv_id="",
            messages_text=response_text,
            media_urls=media_urls,
        )

    # Bug #8: Mark greeting as sent after successful response delivery
    if is_greeting_pending:
        try:
            from services.greeting_state import mark_greeted

            await mark_greeted(tenant_id, external_user_id)
        except Exception:
            pass  # Non-critical — worst case greeting repeats next message

    # --- Spec 14: Socket.IO Notification (Real-time AI Response) ---
    try:
        from main import app

        sio = getattr(app.state, "sio", None)
        to_json_safe = getattr(app.state, "to_json_safe", lambda x: x)

        if sio and response_text:
            await sio.emit(
                "NEW_MESSAGE",
                to_json_safe(
                    {
                        "phone_number": external_user_id,
                        "tenant_id": tenant_id,
                        "message": response_text,
                        "attachments": [],
                        "role": "assistant",
                        "channel": row.get("channel") or "whatsapp",
                    }
                ),
                room=f"tenant:{tenant_id}",
            )
            logger.info(f"📡 Socket AI NEW_MESSAGE emitted for {external_user_id}")

            # Sincronizar conversación para el preview inmediato
            from db import db as db_inst

            await db_inst.sync_conversation(
                tenant_id=tenant_id,
                channel=row.get("channel") or "whatsapp",
                external_user_id=external_user_id,
                last_message=response_text,
                is_user=False,
            )
    except Exception as sio_err:
        logger.error(f"⚠️ Error emitting SocketIO response: {sio_err}")
