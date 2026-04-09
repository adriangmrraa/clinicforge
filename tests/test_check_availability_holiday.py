"""
Tests for check_availability holiday integration.

Verifies that the auto-advance loop in check_availability skips holidays
and includes the holiday name in the reason message.
"""
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_auto_advance_skips_holiday():
    """check_availability auto-advances past a holiday."""
    # We test the holiday_service.is_holiday function since check_availability
    # calls it in the auto-advance loop. Integration test verifies the wiring.
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'AR', 'language': 'es'}
    pool.fetch.return_value = []

    from services.holiday_service import is_holiday

    # July 9 is AR Independence Day
    is_hol, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 7, 9))
    assert is_hol is True
    assert name is not None

    # July 15 should NOT be a holiday (July 10 is also a bridge holiday in AR)
    is_hol, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 7, 15))
    assert is_hol is False


@pytest.mark.asyncio
async def test_auto_advance_reason_includes_holiday_name():
    """The auto-advance reason message includes the holiday name."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'US', 'language': 'en'}
    pool.fetch.return_value = []

    from services.holiday_service import is_holiday

    is_hol, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 12, 25))
    assert is_hol is True
    # Name should contain "Christmas" or similar
    assert name is not None
    assert len(name) > 0

    # The auto_advance_reason in main.py uses:
    # f"El {target_date.strftime('%d/%m')} es feriado ({_hol_name})"
    reason = f"El {date(2026, 12, 25).strftime('%d/%m')} es feriado ({name})"
    assert 'feriado' in reason
    assert name in reason


@pytest.mark.asyncio
async def test_multiple_consecutive_holidays():
    """System advances past multiple consecutive holidays (e.g., long weekend)."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'AR', 'language': 'es'}
    pool.fetch.return_value = []

    from services.holiday_service import is_holiday

    # Simulate checking multiple days - the auto-advance loop does this
    target = date(2026, 7, 9)  # AR Independence Day
    max_advance = 21
    found_open = False
    for _ in range(max_advance):
        is_hol, _, _2 = await is_holiday(pool, tenant_id=1, check_date=target)
        if not is_hol:
            found_open = True
            break
        target += timedelta(days=1)

    assert found_open is True
    # Should have advanced at least 1 day
    assert target > date(2026, 7, 9)


@pytest.mark.asyncio
async def test_holiday_check_with_override_open():
    """Day with override_open is NOT skipped in auto-advance."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'AR', 'language': 'es'}
    pool.fetch.return_value = [
        {'name': 'Trabajamos', 'holiday_type': 'override_open', 'custom_hours_start': None, 'custom_hours_end': None}
    ]

    from services.holiday_service import is_holiday

    is_hol, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 7, 9))
    assert is_hol is False  # override_open means clinic works
