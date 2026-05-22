"""
Holiday service for ClinicForge.

Hybrid approach: Python `holidays` library (baseline) + tenant_holidays DB table (custom overrides).

Priority chain:
  1. override_open in tenant_holidays → NOT a holiday (clinic works despite national holiday)
  2. closure in tenant_holidays     → IS a holiday (custom closure)
  3. holidays library               → IS a holiday (national holiday)
  4. default                        → NOT a holiday

Return type of is_holiday():
  Tuple[bool, Optional[str], Optional[Dict[str, str]]]
  - (False, None, None)                           → not a holiday
  - (True, name, None)                            → closed all day (closure or library)
  - (True, name, {"start": "HH:MM", "end": "HH:MM"})  → override_open WITH custom hours
"""

import logging
from datetime import date, timedelta
from typing import Optional, Tuple, List, Dict, Any

try:
    import holidays as holidays_lib
    HOLIDAYS_AVAILABLE = True
except ImportError:
    holidays_lib = None
    HOLIDAYS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Module-level cache: {cache_key: holidays_instance}
# cache_key format: "{country_code}:{language or 'default'}:{year}"
# Max 200 entries (~30 countries × 3 langs × 2 years); oldest evicted on overflow
_holidays_cache: Dict[str, Any] = {}
_HOLIDAYS_CACHE_MAX = 200

# Supported countries (subset of holidays library, most common for ClinicForge)
SUPPORTED_COUNTRIES = {
    'AR': 'Argentina',
    'US': 'United States',
    'MX': 'Mexico',
    'CO': 'Colombia',
    'CL': 'Chile',
    'PE': 'Peru',
    'EC': 'Ecuador',
    'UY': 'Uruguay',
    'PY': 'Paraguay',
    'BR': 'Brazil',
    'ES': 'Spain',
    'VE': 'Venezuela',
    'BO': 'Bolivia',
    'CR': 'Costa Rica',
    'PA': 'Panama',
    'DO': 'Dominican Republic',
    'GT': 'Guatemala',
    'HN': 'Honduras',
    'SV': 'El Salvador',
    'NI': 'Nicaragua',
    'CU': 'Cuba',
    'PR': 'Puerto Rico',
    'CA': 'Canada',
    'GB': 'United Kingdom',
    'DE': 'Germany',
    'FR': 'France',
    'IT': 'Italy',
    'PT': 'Portugal',
}

# Language code mapping: app language → holidays library locale
_LANGUAGE_MAP: Dict[str, str] = {
    'es': 'es',
    'en': 'en_US',
    'fr': 'fr',
}


def _get_country_holidays(country_code: str, year: int, language: Optional[str] = None):
    """
    Get holidays instance for a country/year, with module-level caching.

    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g. 'AR')
        year: The year to load holidays for
        language: Optional app language code ('es', 'en', 'fr'). Maps to holidays lib locale.

    Returns:
        holidays instance or None if unavailable
    """
    if not HOLIDAYS_AVAILABLE:
        return None

    locale = _LANGUAGE_MAP.get(language or '', None)
    cache_key = f"{country_code}:{language or 'default'}:{year}"

    if cache_key in _holidays_cache:
        return _holidays_cache[cache_key]

    instance = None
    try:
        kwargs = {'years': year}
        if locale:
            kwargs['language'] = locale
        instance = holidays_lib.country_holidays(country_code, **kwargs)
    except (NotImplementedError, AttributeError, KeyError, ValueError):
        # Language not supported for this country — retry without it
        if locale:
            logger.warning(
                f"Language '{locale}' not supported for country '{country_code}' "
                f"in holidays library. Retrying without language param."
            )
            try:
                instance = holidays_lib.country_holidays(country_code, years=year)
            except NotImplementedError:
                logger.warning(f"Country {country_code} not supported by holidays library")
                instance = None
        else:
            logger.warning(f"Country {country_code} not supported by holidays library")
            instance = None

    # Evict oldest entries if cache exceeds max size
    if len(_holidays_cache) >= _HOLIDAYS_CACHE_MAX:
        # Remove oldest 25% of entries
        keys_to_remove = list(_holidays_cache.keys())[:_HOLIDAYS_CACHE_MAX // 4]
        for k in keys_to_remove:
            del _holidays_cache[k]
    _holidays_cache[cache_key] = instance
    return instance


async def is_holiday(
    pool,
    tenant_id: int,
    check_date: date,
    professional_id: Optional[int] = None,
) -> Tuple[bool, Optional[str], Optional[Dict[str, str]]]:
    """
    Check if a date is a holiday for the given tenant.

    Args:
        pool: Database pool
        tenant_id: Tenant ID
        check_date: Date to check
        professional_id: Optional — if provided, checks per-professional blocks (scope='professional')
                         If omitted, only checks global holidays (scope='global' or professional_id IS NULL)

    Returns: Tuple[bool, Optional[str], Optional[Dict[str, str]]]

    Return matrix:
      - Not a holiday          → (False, None, None)
      - Closure (custom)       → (True, name, None)
      - override_open, no hrs  → (False, None, None)   ← normal working day
      - override_open, w/ hrs  → (True, name, {"start": "HH:MM", "end": "HH:MM"})
      - Library holiday        → (True, name, None)

    Priority chain (professional context — professional_id provided):
      1. professional scope='closure'          → (True, name, None)
      2. professional scope='override_open'    → (False/True, name, hours)
      3. Fall through to global chain below

    Priority chain (global context — no professional_id):
      1. override_open (global or professional_id IS NULL)
      2. closure (global or professional_id IS NULL)
      3. library holiday
      4. default
    """
    # Fetch tenant country_code + language in one query
    tenant_row = await pool.fetchrow(
        """
        SELECT country_code,
               COALESCE(config->>'language', config->>'ui_language', 'es') AS language
        FROM tenants WHERE id = $1
        """,
        tenant_id
    )
    if not tenant_row:
        return (False, None, None)

    country_code = (tenant_row['country_code'] or 'US').upper()
    language = tenant_row['language'] or 'es'

    # Check custom holidays (both exact date AND recurring by month/day)
    # When professional_id is provided, include scope='professional' blocks for that prof
    # When not provided, include only global entries (scope='global' or professional_id IS NULL)
    if professional_id is not None:
        custom_rows = await pool.fetch(
            """
            SELECT name, holiday_type, custom_hours_start, custom_hours_end, scope
            FROM tenant_holidays
            WHERE tenant_id = $1
              AND (
                date = $2
                OR (is_recurring = true AND EXTRACT(MONTH FROM date) = $3 AND EXTRACT(DAY FROM date) = $4)
              )
              AND (
                (scope = 'professional' AND professional_id = $5)
                OR (scope = 'global' AND professional_id IS NULL)
              )
            """,
            tenant_id, check_date, check_date.month, check_date.day, professional_id
        )
    else:
        custom_rows = await pool.fetch(
            """
            SELECT name, holiday_type, custom_hours_start, custom_hours_end, scope
            FROM tenant_holidays
            WHERE tenant_id = $1
              AND (
                date = $2
                OR (is_recurring = true AND EXTRACT(MONTH FROM date) = $3 AND EXTRACT(DAY FROM date) = $4)
              )
              AND (scope = 'global' OR professional_id IS NULL)
            """,
            tenant_id, check_date, check_date.month, check_date.day
        )

    # Priority 1: override_open takes precedence
    for row in custom_rows:
        if row['holiday_type'] == 'override_open':
            hs = row['custom_hours_start']
            he = row['custom_hours_end']
            if hs and he:
                # Reduced hours on a normally-holiday day
                custom_hours = {
                    'start': hs.strftime('%H:%M'),
                    'end': he.strftime('%H:%M'),
                }
                return (True, row['name'], custom_hours)
            # No custom hours → treat as normal working day
            return (False, None, None)

    # Priority 2: custom closure
    for row in custom_rows:
        if row['holiday_type'] == 'closure':
            return (True, row['name'], None)

    # Priority 3: library holiday (only for global context)
    # Professional-specific blocks don't affect library holidays — a prof block
    # on a national holiday means the prof is simply blocked, clinic may be closed.
    if professional_id is None:
        country_hols = _get_country_holidays(country_code, check_date.year, language)
        if country_hols and check_date in country_hols:
            return (True, country_hols.get(check_date), None)

    # Priority 4: not a holiday
    return (False, None, None)


async def get_upcoming_holidays(pool, tenant_id: int, days_ahead: int = 30) -> List[Dict[str, Any]]:
    """
    Get upcoming holidays for the next N days (merged: library + custom closures).
    Excludes dates with override_open (unless they have custom hours).

    Each item includes:
      - date: ISO date string
      - name: localized holiday name
      - source: 'library' | 'custom'
      - holiday_type: 'closure' | 'override_open' (for custom) | 'library'
      - custom_hours: None | {"start": "HH:MM", "end": "HH:MM"}
    """
    tenant_row = await pool.fetchrow(
        """
        SELECT country_code,
               COALESCE(config->>'language', config->>'ui_language', 'es') AS language
        FROM tenants WHERE id = $1
        """,
        tenant_id
    )
    if not tenant_row:
        return []

    country_code = (tenant_row['country_code'] or 'US').upper()
    language = tenant_row['language'] or 'es'
    today = date.today()
    end_date = today + timedelta(days=days_ahead)

    # Get all custom holidays in range (include professional_id and prof name)
    custom_rows = await pool.fetch(
        """
        SELECT th.id, th.date, th.name, th.holiday_type, th.is_recurring,
               th.custom_hours_start, th.custom_hours_end,
               th.professional_id, th.scope,
               CONCAT(p.first_name, ' ', COALESCE(p.last_name, '')) AS professional_name
        FROM tenant_holidays th
        LEFT JOIN professionals p ON th.professional_id = p.id
        WHERE th.tenant_id = $1
          AND (
            (th.date >= $2 AND th.date <= $3)
            OR th.is_recurring = true
          )
        """,
        tenant_id, today, end_date
    )

    # Build sets for overrides and closures
    override_dates: set = set()
    override_hours: Dict[date, Optional[Dict[str, str]]] = {}
    override_names: Dict[date, str] = {}
    override_ids: Dict[date, int] = {}
    closures: Dict[date, Dict[str, Any]] = {}

    for row in custom_rows:
        hs = row['custom_hours_start']
        he = row['custom_hours_end']
        custom_hours = (
            {'start': hs.strftime('%H:%M'), 'end': he.strftime('%H:%M')}
            if hs and he else None
        )

        projected_dates = []
        if row['is_recurring']:
            for year in range(today.year, end_date.year + 1):
                try:
                    projected = date(year, row['date'].month, row['date'].day)
                except ValueError:
                    continue  # Feb 29 in non-leap year
                if today <= projected <= end_date:
                    projected_dates.append(projected)
        else:
            if today <= row['date'] <= end_date:
                projected_dates.append(row['date'])

        prof_id = row.get('professional_id')
        prof_name = row.get('professional_name') or None
        scope = row.get('scope', 'global')

        for d in projected_dates:
            if row['holiday_type'] == 'override_open':
                override_dates.add(d)
                override_hours[d] = custom_hours
                override_names[d] = row['name']
                override_ids[d] = row['id']
            elif row['holiday_type'] == 'closure':
                closures[d] = {
                    'id': row['id'],
                    'name': row['name'],
                    'custom_hours': custom_hours,
                    'professional_id': prof_id,
                    'professional_name': prof_name,
                    'scope': scope,
                }

    # Get library holidays
    country_hols = _get_country_holidays(country_code, today.year, language)
    country_hols_next = None
    if today.year != end_date.year:
        country_hols_next = _get_country_holidays(country_code, end_date.year, language)

    result = []

    # Add library holidays (excluding plain overrides — but include override_open WITH hours)
    for hols in [h for h in [country_hols, country_hols_next] if h]:
        for d, name in sorted(hols.items()):
            if not (today <= d <= end_date):
                continue
            if d in override_dates:
                hours = override_hours.get(d)
                if hours:
                    # override_open with custom hours → report as reduced schedule
                    result.append({
                        'id': override_ids.get(d),
                        'date': d.isoformat(),
                        'name': override_names.get(d, name),
                        'source': 'custom',
                        'holiday_type': 'override_open',
                        'custom_hours': hours,
                        'professional_id': None,
                        'professional_name': None,
                        'scope': 'global',
                    })
                # else: plain override_open → clinic works normally, skip
            else:
                result.append({
                    'id': None,
                    'date': d.isoformat(),
                    'name': name,
                    'source': 'library',
                    'holiday_type': 'library',
                    'custom_hours': None,
                    'professional_id': None,
                    'professional_name': None,
                    'scope': 'global',
                })

    # Add custom closures
    for d, info in closures.items():
        if d not in override_dates:
            result.append({
                'id': info.get('id'),
                'date': d.isoformat(),
                'name': info['name'],
                'source': 'custom',
                'holiday_type': 'closure',
                'custom_hours': info['custom_hours'],
                'professional_id': info.get('professional_id'),
                'professional_name': info.get('professional_name'),
                'scope': info.get('scope', 'global'),
            })

    # Sort by date, deduplicate (prefer custom over library for same date)
    result.sort(key=lambda x: (x['date'], 0 if x['source'] == 'custom' else 1))
    seen: set = set()
    deduped = []
    for item in result:
        if item['date'] not in seen:
            seen.add(item['date'])
            deduped.append(item)

    return deduped
