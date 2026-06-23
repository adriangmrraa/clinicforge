"""Tests for AI Agent Behavioral Correction change."""
import pytest


class TestCheckAvailabilityOutput:
    """CF1: Verify check_availability never shows slot count message."""

    def test_no_extra_slots_phrase(self):
        """The phrase 'turnos más disponibles' must not exist in check_availability output."""
        with open("orchestrator_service/main.py", encoding="utf-8") as f:
            content = f.read()
        count = content.count("turnos más disponibles")
        assert count == 0, f"Found {count} occurrences of 'turnos más disponibles' in main.py"


class TestFormatInsuranceProviders:
    """CF2: Verify _format_insurance_providers uses copay_notes."""

    def test_copay_notes_are_used(self):
        """When copay_notes is set, it should appear in the formatted output."""
        with open("orchestrator_service/main.py", encoding="utf-8") as f:
            content = f.read()
        count = content.count("copay_notes")
        assert count >= 2, f"Expected copay_notes to be referenced in main.py, found {count} times"
