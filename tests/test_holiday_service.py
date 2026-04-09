"""
Tests for holiday_service.py — is_holiday() and get_upcoming_holidays()

Covers:
- Priority chain: override_open > closure > library > open
- Recurring holidays (month/day match)
- Unsupported country fallback
- get_upcoming_holidays merged output
"""
import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch


# ─── is_holiday tests ───

@pytest.mark.asyncio
async def test_is_holiday_national_holiday_ar():
    """AR national holiday (July 9 - Independence Day) detected by library."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'AR', 'language': 'es'}
    pool.fetch.return_value = []  # No custom holidays

    from services.holiday_service import is_holiday
    result, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 7, 9))
    assert result is True
    assert name is not None
    assert 'independencia' in name.lower() or 'Independence' in name


@pytest.mark.asyncio
async def test_is_holiday_regular_day():
    """A normal working day is NOT a holiday."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'AR', 'language': 'es'}
    pool.fetch.return_value = []

    from services.holiday_service import is_holiday
    # July 15 is a regular day in AR (July 10 is also a bridge holiday)
    result, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 7, 15))
    assert result is False
    assert name is None


@pytest.mark.asyncio
async def test_is_holiday_us_independence_day():
    """US national holiday (July 4) detected."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'US', 'language': 'en'}
    pool.fetch.return_value = []

    from services.holiday_service import is_holiday
    result, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 7, 4))
    assert result is True
    assert name is not None


@pytest.mark.asyncio
async def test_is_holiday_custom_closure():
    """Custom closure (clinic anniversary) is detected as holiday."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'US', 'language': 'en'}
    pool.fetch.return_value = [
        {'name': 'Aniversario clínica', 'holiday_type': 'closure', 'custom_hours_start': None, 'custom_hours_end': None}
    ]

    from services.holiday_service import is_holiday
    result, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 3, 15))
    assert result is True
    assert name == 'Aniversario clínica'


@pytest.mark.asyncio
async def test_is_holiday_override_open():
    """override_open overrides a national holiday — clinic works that day."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'AR', 'language': 'es'}
    # DB returns an override_open for July 9
    pool.fetch.return_value = [
        {'name': 'Trabajamos feriado', 'holiday_type': 'override_open', 'custom_hours_start': None, 'custom_hours_end': None}
    ]

    from services.holiday_service import is_holiday
    result, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 7, 9))
    assert result is False
    assert name is None


@pytest.mark.asyncio
async def test_is_holiday_override_beats_closure():
    """override_open takes priority over closure for same date."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'US', 'language': 'en'}
    pool.fetch.return_value = [
        {'name': 'Custom closure', 'holiday_type': 'closure', 'custom_hours_start': None, 'custom_hours_end': None},
        {'name': 'Override', 'holiday_type': 'override_open', 'custom_hours_start': None, 'custom_hours_end': None},
    ]

    from services.holiday_service import is_holiday
    result, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 6, 15))
    assert result is False
    assert name is None


@pytest.mark.asyncio
async def test_is_holiday_unsupported_country():
    """Unsupported country code falls back gracefully (no library holidays, custom still works)."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'ZZ', 'language': 'es'}
    pool.fetch.return_value = [
        {'name': 'Custom day off', 'holiday_type': 'closure', 'custom_hours_start': None, 'custom_hours_end': None}
    ]

    from services.holiday_service import is_holiday
    result, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 5, 1))
    assert result is True
    assert name == 'Custom day off'


@pytest.mark.asyncio
async def test_is_holiday_unsupported_country_no_custom():
    """Unsupported country with no custom holidays → not a holiday."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'ZZ', 'language': 'es'}
    pool.fetch.return_value = []

    from services.holiday_service import is_holiday
    result, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 5, 1))
    assert result is False
    assert name is None


@pytest.mark.asyncio
async def test_is_holiday_null_country_defaults_us():
    """NULL country_code defaults to US."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': None, 'language': 'es'}
    pool.fetch.return_value = []

    from services.holiday_service import is_holiday
    # July 4 is US Independence Day
    result, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 7, 4))
    assert result is True


@pytest.mark.asyncio
async def test_is_holiday_no_tenant():
    """Non-existent tenant returns (False, None)."""
    pool = AsyncMock()
    pool.fetchrow.return_value = None

    from services.holiday_service import is_holiday
    result, name, _ = await is_holiday(pool, tenant_id=999, check_date=date(2026, 7, 4))
    assert result is False
    assert name is None


# ─── get_upcoming_holidays tests ───

@pytest.mark.asyncio
async def test_upcoming_holidays_returns_library_holidays():
    """get_upcoming_holidays returns library holidays with source='library'."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'US', 'language': 'en'}
    pool.fetch.return_value = []  # No custom

    from services.holiday_service import get_upcoming_holidays
    result = await get_upcoming_holidays(pool, tenant_id=1, days_ahead=365)
    assert len(result) > 0
    assert all(h['source'] == 'library' for h in result)
    assert all('date' in h and 'name' in h for h in result)


@pytest.mark.asyncio
async def test_upcoming_holidays_sorted_by_date():
    """Results are sorted by date ascending."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'US', 'language': 'en'}
    pool.fetch.return_value = []

    from services.holiday_service import get_upcoming_holidays
    result = await get_upcoming_holidays(pool, tenant_id=1, days_ahead=365)
    dates = [h['date'] for h in result]
    assert dates == sorted(dates)


@pytest.mark.asyncio
async def test_upcoming_holidays_excludes_override():
    """Dates with override_open are excluded from upcoming list."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'US', 'language': 'en'}
    # Override July 4 (US holiday)
    pool.fetch.return_value = [
        {'id': 1, 'date': date(2026, 7, 4), 'name': 'We work July 4', 'holiday_type': 'override_open', 'is_recurring': False, 'custom_hours_start': None, 'custom_hours_end': None}
    ]

    from services.holiday_service import get_upcoming_holidays
    result = await get_upcoming_holidays(pool, tenant_id=1, days_ahead=365)
    dates = [h['date'] for h in result]
    assert '2026-07-04' not in dates


@pytest.mark.asyncio
async def test_upcoming_holidays_includes_custom_closure():
    """Custom closures appear in upcoming list with source='custom'."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'US', 'language': 'en'}
    pool.fetch.return_value = [
        {'id': 2, 'date': date(2026, 6, 15), 'name': 'Clinic Anniversary', 'holiday_type': 'closure', 'is_recurring': False, 'custom_hours_start': None, 'custom_hours_end': None}
    ]

    from services.holiday_service import get_upcoming_holidays
    result = await get_upcoming_holidays(pool, tenant_id=1, days_ahead=365)
    custom = [h for h in result if h['source'] == 'custom']
    assert len(custom) >= 1
    assert any(h['name'] == 'Clinic Anniversary' for h in custom)


@pytest.mark.asyncio
async def test_upcoming_holidays_no_tenant():
    """Non-existent tenant returns empty list."""
    pool = AsyncMock()
    pool.fetchrow.return_value = None

    from services.holiday_service import get_upcoming_holidays
    result = await get_upcoming_holidays(pool, tenant_id=999, days_ahead=30)
    assert result == []


# ─── SUPPORTED_COUNTRIES tests ───

def test_supported_countries_includes_key_countries():
    """Verify key countries are in the supported list."""
    from services.holiday_service import SUPPORTED_COUNTRIES
    assert 'US' in SUPPORTED_COUNTRIES
    assert 'AR' in SUPPORTED_COUNTRIES
    assert 'MX' in SUPPORTED_COUNTRIES
    assert 'CO' in SUPPORTED_COUNTRIES
    assert 'ES' in SUPPORTED_COUNTRIES
    assert 'BR' in SUPPORTED_COUNTRIES
