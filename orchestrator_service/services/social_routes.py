"""CTA route definitions for the Instagram/Facebook social media agent.

Provides CTARoute dataclass, the hardcoded CTA_ROUTES registry, and
get_route_for_text() for accent/case-insensitive keyword matching.

Hardcoded for MVP. Future: replace load_routes_from_file() with a DB query
keyed by tenant_id. The CTARoute dataclass + get_route_for_text() signature
are the stable API — callers need not change when the source is swapped.

Pitches are rewritten from the original instagram rutas DraLauraDelgado.md
to drive DIRECT booking on IG/FB — no "¿te paso el WhatsApp?" redirect.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class CTARoute:
    """Represents one conversational CTA route for the social agent.

    group:           Unique route identifier (blanqueamiento | implantes | lift | evaluacion)
    keywords:        List of accent-normalised, uppercase keywords that trigger this route
    pitch_template:  Spanish (rioplatense) agent pitch ending with a direct booking trigger
    landing_url_key: Key into tenant.social_landings dict (e.g. "blanqueamiento")
    """

    group: str
    keywords: list[str]
    pitch_template: str
    landing_url_key: str


def _normalize(text: str) -> str:
    """NFKD normalise + strip combining diacritics + uppercase + strip whitespace."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return stripped.upper().strip()


CTA_ROUTES: list[CTARoute] = [
    CTARoute(
        group="blanqueamiento",
        keywords=["BLANQUEAMIENTO", "BLANQUEAR", "BEYOND", "DIAMANTE"],
        pitch_template=(
            "¡Qué bueno que te intereses por tu sonrisa! ✨ En la clínica usamos la tecnología "
            "**BEYOND®**, que es el estándar de oro en blanqueamiento profesional. Aclara de forma "
            "profunda pero cuidando al máximo tu esmalte. Como cada sonrisa es única, la Dra. Laura "
            "necesita evaluarte para definir el protocolo exacto.\n\n"
            "Podés ver cómo funciona acá: {landing_url}\n\n"
            "¿Querés que te proponga un horario para que la Dra. te haga la evaluación?"
        ),
        landing_url_key="blanqueamiento",
    ),
    CTARoute(
        group="implantes",
        keywords=["IMPLANTES", "IMPLANTE", "CIMA", "RISA"],
        pitch_template=(
            "¡Gracias por tu interés! La Dra. trabaja con planificación 3D e implantes de alta gama "
            "para recuperar función y estética, incluso en casos complejos con poco hueso. Para darte "
            "una solución responsable es indispensable una evaluación presencial.\n\n"
            "Conocé más sobre la metodología de la Dra. en: {landing_url}\n\n"
            "¿Te busco un horario de evaluación esta semana?"
        ),
        landing_url_key="main",
    ),
    CTARoute(
        group="lift",
        keywords=["LIFT"],
        pitch_template=(
            "¡Gracias por tu interés! El enfoque de la Dra. Laura Delgado es el 'Refrescamiento "
            "Natural': que te veas mejor, pero sin perder tu esencia. No usamos recetas genéricas; "
            "la Dra. diseña un plan según tus proporciones únicas en una consulta de valoración "
            "facial.\n\n"
            "Más info sobre la filosofía acá: {landing_url}\n\n"
            "¿Querés que te agende una evaluación?"
        ),
        landing_url_key="main",
    ),
    CTARoute(
        group="evaluacion",
        keywords=["EVALUACION", "EVALUACION", "CIRUGIA", "CONSULTA"],
        pitch_template=(
            "¡Gracias por tu mensaje! Sea por una cirugía o una consulta general, el punto de partida "
            "es la evaluación diagnóstica con la Dra. Laura Delgado para armar tu plan de tratamiento.\n\n"
            "¿Querés que te proponga horarios disponibles para agendar la evaluación?"
        ),
        landing_url_key="main",
    ),
]


def get_route_for_text(text: str) -> Optional[CTARoute]:
    """Return the first matching CTARoute for the given text, or None.

    Matching is accent-insensitive and case-insensitive.
    Returns None for empty, whitespace-only, or None input.
    """
    if not text:
        return None
    normalized_text = _normalize(text)
    if not normalized_text:
        return None
    for route in CTA_ROUTES:
        for kw in route.keywords:
            if _normalize(kw) in normalized_text:
                return route
    return None


def load_routes_from_file(path: str) -> list[CTARoute]:
    """Forward-compatibility stub. Returns CTA_ROUTES unchanged.

    Future: parse a markdown/YAML file or query a DB table keyed by tenant_id.
    Guaranteed to not raise — returns hardcoded defaults on any error.
    """
    try:
        # MVP: return hardcoded CTA_ROUTES. Future: parse path.
        return CTA_ROUTES
    except Exception as e:
        log.warning(
            "social_routes: failed to parse %s: %s — using defaults", path, e
        )
        return CTA_ROUTES
