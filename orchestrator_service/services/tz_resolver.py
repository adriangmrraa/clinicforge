"""Tenant-aware timezone resolution.

Maps `tenants.country_code` (ISO 3166-1 alpha-2) to a canonical IANA timezone.
The mapping covers every country exposed by the clinic-creation UI dropdown.

Usage:
    from services.tz_resolver import get_tenant_tz
    tz = await get_tenant_tz(tenant_id)
    now = datetime.now(tz)

A 5-minute in-process cache avoids hitting the DB on every call.
"""
import logging
import time
from datetime import timezone
from typing import Dict, Optional, Tuple, Union

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Tzdata is bundled with the `tzdata` PyPI package on Windows / minimal images;
# on standard Linux containers (including the production Docker image) it comes
# from /usr/share/zoneinfo and is always present.

# Type alias used by callers — both ZoneInfo and stdlib timezone are tzinfo-compatible.
TzInfoLike = Union[ZoneInfo, timezone]

logger = logging.getLogger("tz_resolver")

# Country (ISO 3166-1 alpha-2) → canonical IANA timezone identifier.
# Each country listed in the clinic-creation UI dropdown is covered.
# For multi-zone countries (US, BR, MX, CA, AR, CL) we pick the principal/capital zone;
# clinics needing finer granularity can be added a per-tenant override later.
COUNTRY_TO_TZ: Dict[str, str] = {
    "AR": "America/Argentina/Buenos_Aires",
    "BO": "America/La_Paz",
    "BR": "America/Sao_Paulo",
    "CA": "America/Toronto",
    "CL": "America/Santiago",
    "CO": "America/Bogota",
    "CR": "America/Costa_Rica",
    "CU": "America/Havana",
    "DE": "Europe/Berlin",
    "DO": "America/Santo_Domingo",
    "EC": "America/Guayaquil",
    "ES": "Europe/Madrid",
    "FR": "Europe/Paris",
    "GB": "Europe/London",
    "GT": "America/Guatemala",
    "HN": "America/Tegucigalpa",
    "IT": "Europe/Rome",
    "MX": "America/Mexico_City",
    "NI": "America/Managua",
    "PA": "America/Panama",
    "PE": "America/Lima",
    "PR": "America/Puerto_Rico",
    "PT": "Europe/Lisbon",
    "PY": "America/Asuncion",
    "SV": "America/El_Salvador",
    "US": "America/New_York",
    "UY": "America/Montevideo",
    "VE": "America/Caracas",
}

_FALLBACK_TZ_NAME = "America/Argentina/Buenos_Aires"

# Hard-coded fallback equivalent to old ARG_TZ — works without tzdata.
# Used only when even ZoneInfo("UTC") fails to load (extreme edge case).
_HARD_FALLBACK = timezone.__class__.__init__  # placeholder, replaced below
from datetime import timedelta as _timedelta
_HARD_FALLBACK = timezone(_timedelta(hours=-3))

# In-process cache: tenant_id → (TzInfoLike, expires_at_unix)
_CACHE: Dict[int, Tuple[TzInfoLike, float]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def resolve_tz_for_country(country_code: Optional[str]) -> TzInfoLike:
    """Synchronously resolve a country code to a tzinfo-compatible object.

    Returns the Buenos Aires ZoneInfo as a soft fallback for unknown codes,
    and a fixed UTC-3 timezone as a hard fallback if tzdata is unavailable.
    """
    if not country_code:
        logger.warning("resolve_tz_for_country called with empty country_code; using fallback")
        tz_name = _FALLBACK_TZ_NAME
    else:
        code = country_code.strip().upper()
        tz_name = COUNTRY_TO_TZ.get(code)
        if not tz_name:
            logger.warning(
                f"resolve_tz_for_country: unknown country_code '{code}', falling back to {_FALLBACK_TZ_NAME}"
            )
            tz_name = _FALLBACK_TZ_NAME
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.error(
            f"resolve_tz_for_country: tzdata missing for '{tz_name}'; falling back to fixed UTC-3"
        )
        return _HARD_FALLBACK


async def get_tenant_tz(tenant_id: int) -> TzInfoLike:
    """Async helper that resolves a tenant's timezone from `tenants.country_code`.

    Cached in-process for 5 minutes per tenant.
    """
    now_unix = time.monotonic()
    cached = _CACHE.get(tenant_id)
    if cached and cached[1] > now_unix:
        return cached[0]

    # Lazy import to avoid circular dependency with main.py at module load time.
    from db import db

    country_code: Optional[str] = None
    try:
        row = await db.pool.fetchrow(
            "SELECT country_code FROM tenants WHERE id = $1", tenant_id
        )
        if row:
            country_code = row["country_code"]
    except Exception as e:
        logger.warning(f"get_tenant_tz: DB lookup failed for tenant {tenant_id}: {e}")

    tz = resolve_tz_for_country(country_code)
    _CACHE[tenant_id] = (tz, now_unix + _CACHE_TTL_SECONDS)
    return tz


def invalidate_tenant_tz_cache(tenant_id: Optional[int] = None) -> None:
    """Drop the cached timezone for a tenant (or all tenants if None).

    Call this when a tenant's country_code is updated from the admin UI.
    """
    if tenant_id is None:
        _CACHE.clear()
    else:
        _CACHE.pop(tenant_id, None)
