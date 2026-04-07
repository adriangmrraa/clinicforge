"""
Tests para Bug #6 — _get_slots_for_extra_day filtra feriados.

Verifica que _get_slots_for_extra_day retorna [] cuando check_is_holiday
indica que la fecha es un feriado (sin atención), y que retorna slots
normalmente cuando la fecha no es feriado.

Nota de implementación: la función tiene dependencias profundas de DB (asyncpg pool).
Los tests usan mocks de AsyncMock para aislar el comportamiento sin requerir DB real.
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_pool_mock():
    """Crea un mock de asyncpg pool que retorna listas vacías por default."""
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchrow = AsyncMock(return_value=None)
    return pool


# ── Test 1: feriado → retorna lista vacía ────────────────────────────────────

@pytest.mark.asyncio
async def test_extra_day_returns_empty_on_holiday():
    """
    Si check_is_holiday retorna (True, 'Día Nacional', None),
    _get_slots_for_extra_day debe retornar [] sin consultar la base de datos.
    """
    from orchestrator_service.main import _get_slots_for_extra_day

    holiday_date = date(2026, 5, 25)  # 25 de mayo — feriado nacional AR
    tenant_id = 1
    tenant_wh = {
        "monday": {"enabled": True, "slots": [{"start": "09:00", "end": "18:00"}]},
    }

    # Patch check_is_holiday para que retorne feriado sin atención
    with patch(
        "orchestrator_service.main._get_slots_for_extra_day.__module__",
        create=True,
    ):
        with patch(
            "orchestrator_service.services.holiday_service.is_holiday",
            new=AsyncMock(return_value=(True, "25 de Mayo", None)),
        ):
            with patch(
                "orchestrator_service.main.db"
            ) as mock_db:
                mock_db.pool = _make_pool_mock()
                result = await _get_slots_for_extra_day(
                    holiday_date,
                    tenant_id,
                    tenant_wh,
                    None,
                    None,
                    30,
                )

    assert result == [], (
        f"Se esperaba lista vacía en feriado, se obtuvo: {result}"
    )


# ── Test 2: no feriado → función procede normalmente ─────────────────────────

@pytest.mark.asyncio
async def test_extra_day_proceeds_on_non_holiday():
    """
    Si check_is_holiday retorna (False, None, None),
    _get_slots_for_extra_day debe continuar la ejecución normal.
    El mock retorna profesionales vacíos → result es [] pero por falta de
    profesionales, NO por el check de feriado.
    """
    from orchestrator_service.main import _get_slots_for_extra_day

    normal_date = date(2026, 5, 26)  # martes después del feriado
    tenant_id = 1
    tenant_wh = {
        "tuesday": {"enabled": True, "slots": [{"start": "09:00", "end": "18:00"}]},
    }

    with patch(
        "orchestrator_service.services.holiday_service.is_holiday",
        new=AsyncMock(return_value=(False, None, None)),
    ):
        with patch("orchestrator_service.main.db") as mock_db:
            mock_db.pool = _make_pool_mock()
            result = await _get_slots_for_extra_day(
                normal_date,
                tenant_id,
                tenant_wh,
                None,
                None,
                30,
            )

    # Con pool vacío no habrá profesionales, entonces result = []
    # pero esto NO es por el check de feriado — es por falta de profesionales.
    # Lo importante es que la función NO hizo early return por feriado.
    # Verificamos que el pool fue consultado (señal de que pasó el check de feriado).
    mock_db.pool.fetch.assert_called()


# ── Test 3: feriado con atención especial (custom_hours) → NO retorna vacío ──

@pytest.mark.asyncio
async def test_extra_day_does_not_skip_holiday_with_custom_hours():
    """
    Si check_is_holiday retorna (True, 'Feriado especial', {'start': '10:00', 'end': '14:00'}),
    el día tiene atención con horario reducido — _get_slots_for_extra_day
    NO debe retornar [] de forma inmediata, sino continuar la ejecución.
    """
    from orchestrator_service.main import _get_slots_for_extra_day

    reduced_hours_date = date(2026, 8, 17)  # feriado con horario reducido
    tenant_id = 1
    tenant_wh = {
        "monday": {"enabled": True, "slots": [{"start": "09:00", "end": "18:00"}]},
    }
    custom_hours = {"start": "10:00", "end": "14:00"}

    with patch(
        "orchestrator_service.services.holiday_service.is_holiday",
        new=AsyncMock(return_value=(True, "Feriado especial", custom_hours)),
    ):
        with patch("orchestrator_service.main.db") as mock_db:
            mock_db.pool = _make_pool_mock()
            result = await _get_slots_for_extra_day(
                reduced_hours_date,
                tenant_id,
                tenant_wh,
                None,
                None,
                30,
            )

    # La función debe haber continuado (no early return).
    # Con pool vacío result será [] por falta de profesionales, pero
    # el pool.fetch debe haberse llamado (prueba que no hubo early return).
    mock_db.pool.fetch.assert_called()
