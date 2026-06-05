"""Tests for Booking Omission and Reschedule Fallback Fixes."""
from __future__ import annotations

import os
import sys
import pytest

# Ensure orchestrator_service is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service"))

from agents.supervisor import SupervisorAgent
from agents.specialists import BookingAgent
from main import build_system_prompt


@pytest.mark.asyncio
class TestSupervisorRoutingFixes:
    """Verify that SupervisorAgent correctly routes confirmation inputs (DNI) to booking."""

    async def test_route_dni_with_clinical_pain(self):
        """DNI with clinical description must route to booking to prevent triage detour."""
        agent = SupervisorAgent()
        state = {
            "user_message": "Mi DNI es 12345678 y además me duele muchísimo la muela de abajo",
            "hop_count": 0,
            "max_hops": 5,
            "patient_profile": {}
        }
        res = await agent.route(state)
        assert res == "booking"

    async def test_route_dni_alone(self):
        """DNI alone must route to booking."""
        agent = SupervisorAgent()
        state = {
            "user_message": "98765432",
            "hop_count": 0,
            "max_hops": 5,
            "patient_profile": {}
        }
        res = await agent.route(state)
        assert res == "booking"

    async def test_route_clinical_pain_alone(self):
        """Clinical pain alone must route to triage."""
        agent = SupervisorAgent()
        state = {
            "user_message": "Me duele la muela un montón, me sangra",
            "hop_count": 0,
            "max_hops": 5,
            "patient_profile": {}
        }
        res = await agent.route(state)
        assert res == "triage"

    async def test_route_greeting_alone(self):
        """Greeting alone must route to reception."""
        agent = SupervisorAgent()
        state = {
            "user_message": "Hola, buenas tardes",
            "hop_count": 0,
            "max_hops": 5,
            "patient_profile": {}
        }
        res = await agent.route(state)
        assert res == "reception"


class TestPromptInstructions:
    """Verify that the required DNI and reschedule fallback blocks are present in the prompts."""

    def test_monolithic_prompt_contains_rules(self):
        """The monolithic system prompt must contain both rules."""
        prompt = build_system_prompt(
            clinic_name="Test Clinic",
            current_time="2026-06-05T12:00:00",
            response_language="es",
            bot_name="TestBot",
            upcoming_holidays=[],
            patient_status="new_lead",
            is_greeting_pending=True
        )
        assert "⚠️ REGLA DE CONFIRMACIÓN CON DNI" in prompt
        assert "⚠️ FALLBACK SI NO TIENE TURNOS FUTUROS ACTIVOS" in prompt

    def test_booking_agent_prompt_contains_rules(self):
        """The BookingAgent system prompt must contain both rules."""
        agent = BookingAgent()
        # BookingAgent's run method builds the prompt from specialist.py internally,
        # but the base prompt template is within the class or run method itself.
        # Let's inspect class attributes or view specialists.py where we checked.
        # We can also mock run or verify the string content directly on specialists.py.
        # In specialists.py, class BookingAgent.run uses a local prompt string.
        # Let's write a simple import check to verify it has the rules.
        import inspect
        source = inspect.getsource(BookingAgent.run)
        assert "⚠️ REGLA DE CONFIRMACIÓN CON DNI" in source
        assert "⚠️ FALLBACK SI NO TIENE TURNOS FUTUROS ACTIVOS" in source
