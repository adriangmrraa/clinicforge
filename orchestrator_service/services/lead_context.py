"""
Lead Context Accumulator.

Persists structured data about leads (not yet patients) in Redis
so AI agents don't lose context during long conversations.

Key format: lead_ctx:{tenant_id}:{phone_digits}
TTL: 24 hours (reset on every write)
"""

import json
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

LEAD_CTX_TTL = 86400  # 24 hours
LEAD_CTX_PREFIX = "lead_ctx"


def _normalize_identifier(identifier: str) -> str:
    """Normalize phone/PSID to digits-only for Redis key."""
    return re.sub(r"\D", "", identifier)


def _build_key(tenant_id: int, identifier: str) -> str:
    normalized = _normalize_identifier(identifier)
    return f"{LEAD_CTX_PREFIX}:{tenant_id}:{normalized}"


async def merge(
    tenant_id: int,
    identifier: str,
    fields: Dict[str, str],
    skip_if_exists_fields: Optional[List[str]] = None,
) -> None:
    """
    Merge fields into the lead context hash.

    Args:
        tenant_id: Tenant ID
        identifier: Phone number or PSID
        fields: Dict of field_name -> value to write
        skip_if_exists_fields: List of field names that should NOT be
            overwritten if they already have a non-empty value in Redis.
    """
    if not fields:
        return

    try:
        from services.relay import get_redis

        r = get_redis()
        if r is None:
            return

        key = _build_key(tenant_id, identifier)

        # Filter out empty values
        to_write = {k: v for k, v in fields.items() if v}
        if not to_write:
            return

        # Handle skip-if-exists: read current values for those fields
        if skip_if_exists_fields:
            existing = await r.hmget(key, *skip_if_exists_fields)
            for i, field_name in enumerate(skip_if_exists_fields):
                if existing[i] and field_name in to_write:
                    del to_write[field_name]

        if not to_write:
            return

        # Always update timestamp
        from datetime import datetime

        to_write["last_updated_at"] = datetime.now().isoformat()
        if not await r.exists(key):
            to_write["first_seen_at"] = to_write["last_updated_at"]

        await r.hset(key, mapping=to_write)
        await r.expire(key, LEAD_CTX_TTL)

        logger.info(
            f"[lead_context] merge {key} fields={list(to_write.keys())}"
        )
    except Exception as e:
        logger.warning(f"[lead_context] merge failed (non-blocking): {e}")


async def get(tenant_id: int, identifier: str) -> Dict[str, str]:
    """
    Get all lead context fields from Redis.

    Returns empty dict on failure or missing key.
    """
    try:
        from services.relay import get_redis

        r = get_redis()
        if r is None:
            return {}

        key = _build_key(tenant_id, identifier)
        data = await r.hgetall(key)
        return data or {}
    except Exception as e:
        logger.warning(f"[lead_context] get failed (non-blocking): {e}")
        return {}


async def clear(tenant_id: int, identifier: str) -> None:
    """
    Delete the lead context hash (called when lead becomes patient).
    """
    try:
        from services.relay import get_redis

        r = get_redis()
        if r is None:
            return

        key = _build_key(tenant_id, identifier)
        await r.delete(key)
        logger.info(f"[lead_context] cleared {key}")
    except Exception as e:
        logger.warning(f"[lead_context] clear failed (non-blocking): {e}")


_FIELD_LABELS = {
    "treatment_name": "Tratamiento de interés",
    "professional_name": "Profesional preferido",
    "first_name": "Nombre",
    "last_name": "Apellido",
    "dni": "DNI",
    "email": "Email",
    "date_query": "Fecha consultada",
    "interpreted_date": "Fecha interpretada",
    "search_mode": "Modo de búsqueda",
    "channel": "Canal",
}


def format_for_prompt(data: Dict[str, str]) -> str:
    """
    Format lead context dict into a prompt-injectable string.

    Only includes fields that have non-empty values.
    Excludes internal fields (timestamps, codes, IDs).
    """
    if not data:
        return ""

    lines = ["[CONTEXTO DE LEAD — datos acumulados de la conversación]"]
    for field, label in _FIELD_LABELS.items():
        value = data.get(field)
        if value:
            lines.append(f"• {label}: {value}")

    if len(lines) == 1:
        return ""

    lines.append("[/CONTEXTO DE LEAD]")
    return "\n".join(lines)
