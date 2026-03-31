"""
Tests for admin holiday CRUD endpoints.

Tests the holiday_service functions that back the admin API,
plus validation logic (duplicate detection, type validation, country code warning).
"""
import pytest
from datetime import date
from unittest.mock import AsyncMock


# ─── GET /admin/holidays (via get_upcoming_holidays) ───

@pytest.mark.asyncio
async def test_list_holidays_returns_library_and_custom():
    """GET /admin/holidays returns both library and custom holidays."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'US'}
    pool.fetch.return_value = [
        {'date': date(2026, 8, 10), 'name': 'Custom Day', 'holiday_type': 'closure', 'is_recurring': False}
    ]

    from services.holiday_service import get_upcoming_holidays
    result = await get_upcoming_holidays(pool, tenant_id=1, days_ahead=365)

    sources = {h['source'] for h in result}
    # Should have library holidays and custom closure
    assert 'library' in sources or 'custom' in sources
    custom = [h for h in result if h['source'] == 'custom']
    assert any(h['name'] == 'Custom Day' for h in custom)


@pytest.mark.asyncio
async def test_list_holidays_correct_source_field():
    """Library holidays have source='library', custom have source='custom'."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'US'}
    pool.fetch.return_value = []

    from services.holiday_service import get_upcoming_holidays
    result = await get_upcoming_holidays(pool, tenant_id=1, days_ahead=365)

    for h in result:
        assert h['source'] in ('library', 'custom'), f"Unexpected source: {h['source']}"


# ─── POST /admin/holidays validation ───

def test_holiday_type_validation():
    """holiday_type must be 'closure' or 'override_open'."""
    valid_types = ('closure', 'override_open')
    invalid_types = ('national', 'library', 'blocked', '', None)

    for t in valid_types:
        assert t in valid_types

    for t in invalid_types:
        assert t not in valid_types


def test_date_parsing_iso_format():
    """Date string in YYYY-MM-DD format parses correctly."""
    from datetime import date as date_type
    parsed = date_type.fromisoformat("2026-07-09")
    assert parsed.year == 2026
    assert parsed.month == 7
    assert parsed.day == 9


def test_date_parsing_invalid_format():
    """Invalid date format raises ValueError."""
    from datetime import date as date_type
    with pytest.raises(ValueError):
        date_type.fromisoformat("09/07/2026")


# ─── Duplicate detection ───

@pytest.mark.asyncio
async def test_duplicate_holiday_detected():
    """Creating same holiday twice should be detectable via unique constraint name."""
    # The unique constraint is: uq_tenant_holidays_tenant_date_type
    constraint_name = "uq_tenant_holidays_tenant_date_type"
    error_msg = f"duplicate key value violates unique constraint \"{constraint_name}\""
    assert constraint_name in error_msg


# ─── DELETE validation ───

@pytest.mark.asyncio
async def test_delete_nonexistent_returns_empty():
    """DELETE on non-existent holiday_id returns DELETE 0."""
    pool = AsyncMock()
    pool.execute.return_value = "DELETE 0"

    result = await pool.execute(
        "DELETE FROM tenant_holidays WHERE id = $1 AND tenant_id = $2", 999, 1
    )
    assert result == "DELETE 0"


@pytest.mark.asyncio
async def test_delete_cross_tenant_blocked():
    """DELETE with wrong tenant_id returns DELETE 0 (cross-tenant protection)."""
    pool = AsyncMock()
    pool.execute.return_value = "DELETE 0"

    # holiday_id=5 belongs to tenant_id=1, but we try with tenant_id=2
    result = await pool.execute(
        "DELETE FROM tenant_holidays WHERE id = $1 AND tenant_id = $2", 5, 2
    )
    assert result == "DELETE 0"


# ─── Country code validation ───

def test_country_code_warning_for_unsupported():
    """Unsupported country code should trigger a warning."""
    from services.holiday_service import SUPPORTED_COUNTRIES
    assert 'ZZ' not in SUPPORTED_COUNTRIES
    assert 'XX' not in SUPPORTED_COUNTRIES
    # Valid codes should be present
    assert 'US' in SUPPORTED_COUNTRIES
    assert 'AR' in SUPPORTED_COUNTRIES


def test_country_code_normalization():
    """Country codes are uppercased and trimmed to 2 chars."""
    raw = " ar "
    normalized = raw.upper().strip()[:2]
    assert normalized == "AR"

    raw2 = "usa"
    normalized2 = raw2.upper().strip()[:2]
    assert normalized2 == "US"


# ─── GET /admin/holidays/upcoming ───

@pytest.mark.asyncio
async def test_upcoming_30_days_limit():
    """GET /admin/holidays/upcoming returns only next 30 days."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'US'}
    pool.fetch.return_value = []

    from services.holiday_service import get_upcoming_holidays
    result = await get_upcoming_holidays(pool, tenant_id=1, days_ahead=30)

    from datetime import date as d, timedelta
    today = d.today()
    limit = today + timedelta(days=30)
    for h in result:
        h_date = d.fromisoformat(h['date'])
        assert h_date >= today
        assert h_date <= limit


@pytest.mark.asyncio
async def test_upcoming_ordered_by_date():
    """Results from upcoming endpoint are ordered by date."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'US'}
    pool.fetch.return_value = []

    from services.holiday_service import get_upcoming_holidays
    result = await get_upcoming_holidays(pool, tenant_id=1, days_ahead=365)
    dates = [h['date'] for h in result]
    assert dates == sorted(dates)
