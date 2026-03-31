"""
Holiday service for ClinicForge.

Hybrid approach: Python `holidays` library (baseline) + tenant_holidays DB table (custom overrides).

Priority chain:
  1. override_open in tenant_holidays → NOT a holiday (clinic works despite national holiday)
  2. closure in tenant_holidays     → IS a holiday (custom closure)
  3. holidays library               → IS a holiday (national holiday)
  4. default                        → NOT a holiday
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

# Module-level cache: {country_code: {year: holidays_instance}}
_holidays_cache: Dict[str, Dict[int, Any]] = {}

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


def _get_country_holidays(country_code: str, year: int):
    """Get holidays instance for a country/year, with module-level caching."""
    if not HOLIDAYS_AVAILABLE:
        return None

    if country_code not in _holidays_cache:
        _holidays_cache[country_code] = {}

    if year not in _holidays_cache[country_code]:
        try:
            _holidays_cache[country_code][year] = holidays_lib.country_holidays(country_code, years=year)
        except NotImplementedError:
            logger.warning(f"Country {country_code} not supported by holidays library")
            _holidays_cache[country_code][year] = None

    return _holidays_cache[country_code][year]


async def is_holiday(pool, tenant_id: int, check_date: date) -> Tuple[bool, Optional[str]]:
    """
    Check if a date is a holiday for the given tenant.

    Returns: (is_holiday: bool, holiday_name: str | None)

    Priority chain:
      1. override_open → (False, None)
      2. closure       → (True, name)
      3. library       → (True, name)
      4. default       → (False, None)
    """
    # Fetch tenant country_code + custom holidays for this date in one query
    tenant_row = await pool.fetchrow(
        "SELECT country_code FROM tenants WHERE id = $1", tenant_id
    )
    if not tenant_row:
        return (False, None)

    country_code = (tenant_row['country_code'] or 'US').upper()

    # Check custom holidays (both exact date AND recurring by month/day)
    custom_rows = await pool.fetch(
        """
        SELECT name, holiday_type FROM tenant_holidays
        WHERE tenant_id = $1
          AND (
            date = $2
            OR (is_recurring = true AND EXTRACT(MONTH FROM date) = $3 AND EXTRACT(DAY FROM date) = $4)
          )
        """,
        tenant_id, check_date, check_date.month, check_date.day
    )

    # Priority 1: override_open takes precedence
    for row in custom_rows:
        if row['holiday_type'] == 'override_open':
            return (False, None)

    # Priority 2: custom closure
    for row in custom_rows:
        if row['holiday_type'] == 'closure':
            return (True, row['name'])

    # Priority 3: library holiday
    country_hols = _get_country_holidays(country_code, check_date.year)
    if country_hols and check_date in country_hols:
        return (True, country_hols.get(check_date))

    # Priority 4: not a holiday
    return (False, None)


async def get_upcoming_holidays(pool, tenant_id: int, days_ahead: int = 30) -> List[Dict[str, Any]]:
    """
    Get upcoming holidays for the next N days (merged: library + custom closures).
    Excludes dates with override_open.
    """
    tenant_row = await pool.fetchrow(
        "SELECT country_code FROM tenants WHERE id = $1", tenant_id
    )
    if not tenant_row:
        return []

    country_code = (tenant_row['country_code'] or 'US').upper()
    today = date.today()
    end_date = today + timedelta(days=days_ahead)

    # Get all custom holidays in range
    custom_rows = await pool.fetch(
        """
        SELECT date, name, holiday_type, is_recurring FROM tenant_holidays
        WHERE tenant_id = $1
          AND (
            (date >= $2 AND date <= $3)
            OR is_recurring = true
          )
        """,
        tenant_id, today, end_date
    )

    # Build sets for overrides and closures
    override_dates = set()
    closures = {}
    for row in custom_rows:
        if row['is_recurring']:
            # Project recurring to current year window
            for year in range(today.year, end_date.year + 1):
                try:
                    projected = date(year, row['date'].month, row['date'].day)
                except ValueError:
                    continue  # Feb 29 in non-leap year
                if today <= projected <= end_date:
                    if row['holiday_type'] == 'override_open':
                        override_dates.add(projected)
                    elif row['holiday_type'] == 'closure':
                        closures[projected] = row['name']
        else:
            if row['holiday_type'] == 'override_open':
                override_dates.add(row['date'])
            elif row['holiday_type'] == 'closure':
                closures[row['date']] = row['name']

    # Get library holidays
    result = []
    country_hols = _get_country_holidays(country_code, today.year)
    if today.year != end_date.year:
        country_hols_next = _get_country_holidays(country_code, end_date.year)
    else:
        country_hols_next = None

    # Add library holidays (excluding overrides)
    if country_hols:
        for d, name in sorted(country_hols.items()):
            if today <= d <= end_date and d not in override_dates:
                result.append({'date': d.isoformat(), 'name': name, 'source': 'library'})

    if country_hols_next:
        for d, name in sorted(country_hols_next.items()):
            if today <= d <= end_date and d not in override_dates:
                result.append({'date': d.isoformat(), 'name': name, 'source': 'library'})

    # Add custom closures (excluding overrides)
    for d, name in closures.items():
        if d not in override_dates:
            result.append({'date': d.isoformat(), 'name': name, 'source': 'custom'})

    # Sort by date, deduplicate
    result.sort(key=lambda x: x['date'])
    seen = set()
    deduped = []
    for item in result:
        if item['date'] not in seen:
            seen.add(item['date'])
            deduped.append(item)

    return deduped
