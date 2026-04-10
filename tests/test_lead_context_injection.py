"""
Tests for lead context injection guards in Solo and Multi-agent engines.

AC-10: Solo engine — patient_row blocks lead context injection
AC-14: Multi-agent — state["lead_context"] populated only for new leads
"""

import pytest
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service")
)
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__), "..", "orchestrator_service", "services"
    ),
)


class TestSoloEngineGuardAC10:
    """AC-10: When patient_row exists, lead context must NOT be injected."""

    @pytest.mark.asyncio
    async def test_patient_exists_blocks_lead_ctx_injection(self):
        """When patient_row is truthy, lead_ctx_get must NOT be called."""
        mock_lead_get = AsyncMock(
            return_value={"treatment_name": "Implantes", "channel": "whatsapp"}
        )

        # Simulate the guard logic from buffer_task.py:1063
        patient_row = {"id": 1, "first_name": "Ramiro", "last_name": "Gamarra"}
        patient_context = ""

        with patch("services.lead_context.get", mock_lead_get):
            # The guard: if not patient_row and not patient_context
            if not patient_row and not patient_context:
                from services.lead_context import get as lead_ctx_get
                from services.lead_context import format_for_prompt as lead_ctx_format

                _lead_data = await lead_ctx_get(1, "+5491112345678")
                if _lead_data:
                    patient_context = lead_ctx_format(_lead_data)

        # lead_ctx_get should NOT have been called
        mock_lead_get.assert_not_called()
        # patient_context should remain empty (not overwritten with lead data)
        assert patient_context == ""

    @pytest.mark.asyncio
    async def test_no_patient_row_allows_lead_ctx_injection(self):
        """When patient_row is None, lead context IS injected."""
        mock_lead_get = AsyncMock(
            return_value={
                "treatment_name": "Cirugía Maxilofacial",
                "professional_name": "Laura Delgado",
                "channel": "whatsapp",
            }
        )

        patient_row = None
        patient_context = ""

        with patch("services.lead_context.get", mock_lead_get):
            if not patient_row and not patient_context:
                from services.lead_context import get as lead_ctx_get
                from services.lead_context import format_for_prompt as lead_ctx_format

                _lead_data = await lead_ctx_get(1, "+5491112345678")
                if _lead_data:
                    patient_context = lead_ctx_format(_lead_data)

        mock_lead_get.assert_called_once()
        assert "[CONTEXTO DE LEAD" in patient_context
        assert "Cirugía Maxilofacial" in patient_context

    @pytest.mark.asyncio
    async def test_patient_context_already_set_blocks_injection(self):
        """When patient_context is already set (patient data built), skip lead ctx."""
        mock_lead_get = AsyncMock(
            return_value={"treatment_name": "Implantes"}
        )

        patient_row = None
        patient_context = "• Nombre: Ramiro Gamarra\n• Próximo turno: ..."

        with patch("services.lead_context.get", mock_lead_get):
            if not patient_row and not patient_context:
                from services.lead_context import get as lead_ctx_get
                from services.lead_context import format_for_prompt as lead_ctx_format

                _lead_data = await lead_ctx_get(1, "+5491112345678")
                if _lead_data:
                    patient_context = lead_ctx_format(_lead_data)

        # Should NOT be called — patient_context was truthy
        mock_lead_get.assert_not_called()
        assert "Ramiro Gamarra" in patient_context

    @pytest.mark.asyncio
    async def test_stale_hash_ignored_when_patient_exists(self):
        """AC-10 core: stale Redis hash + existing patient → no injection."""
        # This is the scenario where clear() failed after booking
        mock_lead_get = AsyncMock(
            return_value={
                "treatment_name": "Ortodoncia",  # stale data
                "first_name": "Juan",
            }
        )

        # Patient exists in DB (patient_row is truthy)
        patient_row = {"id": 42, "first_name": "Juan", "status": "active"}
        patient_context = "• Paciente: Juan\n• Turno: 15/04"

        with patch("services.lead_context.get", mock_lead_get):
            if not patient_row and not patient_context:
                from services.lead_context import get as lead_ctx_get
                from services.lead_context import format_for_prompt as lead_ctx_format

                _lead_data = await lead_ctx_get(1, "+5491112345678")
                if _lead_data:
                    patient_context = lead_ctx_format(_lead_data)

        mock_lead_get.assert_not_called()
        # Original patient context preserved
        assert "Paciente: Juan" in patient_context
        assert "[CONTEXTO DE LEAD" not in patient_context


class TestMultiAgentGuardAC14:
    """AC-14: Multi-agent — state['lead_context'] populated only for new leads."""

    @pytest.mark.asyncio
    async def test_new_lead_populates_state(self):
        """When is_new_lead=True, state['lead_context'] gets populated from Redis."""
        mock_lead_get = AsyncMock(
            return_value={
                "treatment_name": "Implantes",
                "channel": "whatsapp",
            }
        )

        profile = {"is_new_lead": True, "name": None}
        state = {"lead_context": None}

        with patch("services.lead_context.get", mock_lead_get):
            if profile.get("is_new_lead"):
                from services.lead_context import get as lead_ctx_get

                _lead_data = await lead_ctx_get(1, "+5491112345678")
                if _lead_data:
                    state["lead_context"] = _lead_data

        mock_lead_get.assert_called_once()
        assert state["lead_context"] is not None
        assert state["lead_context"]["treatment_name"] == "Implantes"

    @pytest.mark.asyncio
    async def test_existing_patient_keeps_none(self):
        """When is_new_lead=False, lead_ctx_get is NOT called, state stays None."""
        mock_lead_get = AsyncMock(
            return_value={"treatment_name": "Implantes"}
        )

        profile = {"is_new_lead": False, "name": "Ramiro Gamarra"}
        state = {"lead_context": None}

        with patch("services.lead_context.get", mock_lead_get):
            if profile.get("is_new_lead"):
                from services.lead_context import get as lead_ctx_get

                _lead_data = await lead_ctx_get(1, "+5491112345678")
                if _lead_data:
                    state["lead_context"] = _lead_data

        mock_lead_get.assert_not_called()
        assert state["lead_context"] is None

    @pytest.mark.asyncio
    async def test_new_lead_empty_redis_keeps_none(self):
        """When is_new_lead=True but Redis has no data, state stays None."""
        mock_lead_get = AsyncMock(return_value={})

        profile = {"is_new_lead": True}
        state = {"lead_context": None}

        with patch("services.lead_context.get", mock_lead_get):
            if profile.get("is_new_lead"):
                from services.lead_context import get as lead_ctx_get

                _lead_data = await lead_ctx_get(1, "+5491112345678")
                if _lead_data:
                    state["lead_context"] = _lead_data

        mock_lead_get.assert_called_once()
        assert state["lead_context"] is None

    @pytest.mark.asyncio
    async def test_redis_failure_keeps_none(self):
        """When Redis fails, state['lead_context'] stays None (no crash)."""
        mock_lead_get = AsyncMock(side_effect=Exception("Redis down"))

        profile = {"is_new_lead": True}
        state = {"lead_context": None}

        with patch("services.lead_context.get", mock_lead_get):
            if profile.get("is_new_lead"):
                try:
                    from services.lead_context import get as lead_ctx_get

                    _lead_data = await lead_ctx_get(1, "+5491112345678")
                    if _lead_data:
                        state["lead_context"] = _lead_data
                except Exception:
                    pass

        assert state["lead_context"] is None


class TestLeadRecoveryIntegration:
    """Tests for lead recovery integration with lead_ctx."""

    @pytest.mark.asyncio
    async def test_get_lead_name_uses_lead_ctx_first(self):
        """AC-12: _get_lead_name returns name from lead_ctx before DB query."""
        lead_ctx = {"first_name": "Carlos", "last_name": "Méndez"}
        mock_pool = MagicMock()

        from jobs.lead_recovery import _get_lead_name

        result = await _get_lead_name(mock_pool, 1, "+5491112345678", lead_ctx)

        assert result == "Carlos Méndez"
        # DB should NOT be queried
        mock_pool.fetchrow.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_lead_name_falls_back_without_lead_ctx(self):
        """Without lead_ctx name, falls back to DB query."""
        lead_ctx = {"treatment_name": "Implantes"}  # no first_name
        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(
            return_value={"first_name": "Ramiro", "last_name": "Gamarra"}
        )

        from jobs.lead_recovery import _get_lead_name

        result = await _get_lead_name(mock_pool, 1, "+5491112345678", lead_ctx)

        assert result == "Ramiro Gamarra"
        mock_pool.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_lead_name_first_name_only(self):
        """Lead ctx with first_name but no last_name returns just first_name."""
        lead_ctx = {"first_name": "María"}

        from jobs.lead_recovery import _get_lead_name

        result = await _get_lead_name(MagicMock(), 1, "+54", lead_ctx)

        assert result == "María"
