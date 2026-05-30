"""
Tests para Bug #7 — time_preference propagado a _get_slots_for_extra_day.

Verifica que el parámetro time_preference es aceptado por _get_slots_for_extra_day
y que el filtro horario (mañana/tarde) se aplica correctamente en los slots retornados.

Estrategia: se testea generate_free_slots (función sincrónica pura que aplica el filtro)
directamente para los casos de filtrado, y se verifica la firma de _get_slots_for_extra_day
con un test de introspección. Esto evita la complejidad de mockear el pool asyncpg completo
mientras verifica el comportamiento real del filtro horario.
"""

import inspect
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_pool_mock():
    """Mock de asyncpg pool que retorna vacío."""
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchrow = AsyncMock(return_value=None)
    return pool


def _build_single_prof_busy_map(prof_id: int = 1) -> dict:
    """busy_map con un profesional sin horas ocupadas."""
    return {prof_id: set()}


# ── Test 1: firma acepta time_preference ─────────────────────────────────────

def test_signature_accepts_time_preference():
    """
    _get_slots_for_extra_day debe tener time_preference como parámetro opcional
    con default None en su firma.
    """
    from orchestrator_service.main import _get_slots_for_extra_day

    sig = inspect.signature(_get_slots_for_extra_day)
    params = sig.parameters

    assert "time_preference" in params, (
        "La función _get_slots_for_extra_day debe aceptar el parámetro time_preference"
    )
    assert params["time_preference"].default is None, (
        "time_preference debe tener default=None"
    )


# ── Test 2: time_preference='tarde' filtra slots de mañana ───────────────────

def test_generate_free_slots_tarde_filtra_manana():
    """
    Con time_preference='tarde', generate_free_slots no debe retornar
    ningún slot con hora < 13. Este es el filtro que _get_slots_for_extra_day
    delega a generate_free_slots.
    """
    from orchestrator_service.main import generate_free_slots

    target = date(2026, 5, 26)
    busy_map = _build_single_prof_busy_map()

    slots = generate_free_slots(
        target,
        busy_map,
        start_time_str="09:00",
        end_time_str="18:00",
        interval_minutes=30,
        duration_minutes=30,
        limit=50,
        time_preference="tarde",
    )

    assert len(slots) > 0, "Deben existir slots de tarde (13:00-18:00)"
    for slot in slots:
        hour = int(slot.split(":")[0])
        assert hour >= 13, (
            f"Con time_preference='tarde', el slot {slot} no debería aparecer (hora < 13)"
        )


# ── Test 3: time_preference='mañana' filtra slots de tarde ───────────────────

def test_generate_free_slots_manana_filtra_tarde():
    """
    Con time_preference='mañana', generate_free_slots no debe retornar
    ningún slot con hora >= 13.
    """
    from orchestrator_service.main import generate_free_slots

    target = date(2026, 5, 26)
    busy_map = _build_single_prof_busy_map()

    slots = generate_free_slots(
        target,
        busy_map,
        start_time_str="09:00",
        end_time_str="18:00",
        interval_minutes=30,
        duration_minutes=30,
        limit=50,
        time_preference="mañana",
    )

    assert len(slots) > 0, "Deben existir slots de mañana (09:00-12:30)"
    for slot in slots:
        hour = int(slot.split(":")[0])
        assert hour < 13, (
            f"Con time_preference='mañana', el slot {slot} no debería aparecer (hora >= 13)"
        )


# ── Test 4: time_preference=None retorna slots de ambos turnos ───────────────

def test_generate_free_slots_none_retorna_ambos_turnos():
    """
    Con time_preference=None no se aplica ningún filtro horario —
    se deben retornar slots de mañana Y tarde.
    """
    from orchestrator_service.main import generate_free_slots

    target = date(2026, 5, 26)
    busy_map = _build_single_prof_busy_map()

    slots = generate_free_slots(
        target,
        busy_map,
        start_time_str="09:00",
        end_time_str="18:00",
        interval_minutes=30,
        duration_minutes=30,
        limit=50,
        time_preference=None,
    )

    assert len(slots) > 0, "Deben existir slots sin filtro"
    hours = [int(s.split(":")[0]) for s in slots]
    has_morning = any(h < 13 for h in hours)
    has_afternoon = any(h >= 13 for h in hours)
    assert has_morning, "Sin filtro debe haber slots de mañana"
    assert has_afternoon, "Sin filtro debe haber slots de tarde"


# ── Test 5: time_preference='tarde' con solo slots de mañana → lista vacía ───

def test_generate_free_slots_tarde_solo_manana_disponible_retorna_vacio():
    """
    Si todos los slots disponibles son de mañana (09:00-12:30) y
    time_preference='tarde', generate_free_slots retorna lista vacía.
    Este es el contrato documentado: el caller debe avanzar al siguiente día.
    """
    from orchestrator_service.main import generate_free_slots

    target = date(2026, 5, 26)
    busy_map = _build_single_prof_busy_map()

    # Horario de clínica solo de mañana
    slots = generate_free_slots(
        target,
        busy_map,
        start_time_str="09:00",
        end_time_str="13:00",  # solo mañana
        interval_minutes=30,
        duration_minutes=30,
        limit=50,
        time_preference="tarde",
    )

    assert slots == [], (
        "Con horario 09:00-13:00 y time_preference='tarde', no debe haber slots"
    )


# ── Test 6: pick_representative_slots firma acepta time_preference ────────────

def test_pick_representative_slots_signature_accepts_time_preference():
    """
    pick_representative_slots debe tener time_preference como parámetro opcional
    con default None — necesario para propagar desde check_availability.
    """
    from orchestrator_service.main import pick_representative_slots

    sig = inspect.signature(pick_representative_slots)
    params = sig.parameters

    assert "time_preference" in params, (
        "pick_representative_slots debe aceptar time_preference"
    )
    assert params["time_preference"].default is None, (
        "time_preference debe tener default=None en pick_representative_slots"
    )
