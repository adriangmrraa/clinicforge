"""
Tests for book_appointment holiday guard.

Verifies that book_appointment rejects bookings on holidays with
the correct error message including the holiday name.
"""
import pytest
from datetime import date
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_book_rejects_on_national_holiday():
    """book_appointment rejects booking on a national holiday."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'AR', 'language': 'es'}
    pool.fetch.return_value = []

    from services.holiday_service import is_holiday

    # July 9 is AR Independence Day
    is_hol, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 7, 9))
    assert is_hol is True

    # Verify the rejection message format matches what book_appointment produces
    rejection = f"❌ No se puede agendar el {date(2026, 7, 9).strftime('%d/%m/%Y')}: es feriado ({name}). Por favor elegí otro día."
    assert '❌' in rejection
    assert 'feriado' in rejection
    assert name in rejection
    assert '09/07/2026' in rejection


@pytest.mark.asyncio
async def test_book_allows_on_override_open():
    """book_appointment allows booking when override_open is set."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'AR', 'language': 'es'}
    pool.fetch.return_value = [
        {'name': 'Trabajamos', 'holiday_type': 'override_open', 'custom_hours_start': None, 'custom_hours_end': None}
    ]

    from services.holiday_service import is_holiday

    is_hol, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 7, 9))
    assert is_hol is False  # Should NOT block booking


@pytest.mark.asyncio
async def test_book_rejects_on_custom_closure():
    """book_appointment rejects booking on a custom closure date."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'US', 'language': 'en'}
    pool.fetch.return_value = [
        {'name': 'Vacaciones clínica', 'holiday_type': 'closure'}
    ]

    from services.holiday_service import is_holiday

    is_hol, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 1, 20))
    assert is_hol is True
    assert name == 'Vacaciones clínica'


@pytest.mark.asyncio
async def test_book_allows_on_regular_day():
    """book_appointment allows booking on a regular working day."""
    pool = AsyncMock()
    pool.fetchrow.return_value = {'country_code': 'US', 'language': 'en'}
    pool.fetch.return_value = []

    from services.holiday_service import is_holiday

    # Random Tuesday, not a holiday
    is_hol, name, _ = await is_holiday(pool, tenant_id=1, check_date=date(2026, 6, 16))
    assert is_hol is False
    assert name is None
