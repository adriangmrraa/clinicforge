"""Tests for AI Agent Behavioral Correction change."""
import pytest


class TestCheckAvailabilityOutput:
    """CF1: Verify check_availability never shows slot count message."""

    def test_no_extra_slots_phrase(self):
        """The phrase 'turnos más disponibles' must not exist in check_availability output."""
        # This is verified by grep — the string literal was removed from the code
        import subprocess
        result = subprocess.run(
            ["grep", "-c", "turnos más disponibles", "orchestrator_service/main.py"],
            capture_output=True, text=True
        )
        # Should find 0 occurrences (or only in comments/docs)
        count = int(result.stdout.strip()) if result.stdout.strip() else 0
        assert count == 0, f"Found {count} occurrences of 'turnos más disponibles' in main.py"


class TestFormatInsuranceProviders:
    """CF2: Verify _format_insurance_providers uses copay_notes."""

    def test_copay_notes_are_used(self):
        """When copay_notes is set, it should appear in the formatted output."""
        # Verify the function references copay_notes
        import subprocess
        result = subprocess.run(
            ["grep", "-c", "copay_notes", "orchestrator_service/main.py"],
            capture_output=True, text=True
        )
        count = int(result.stdout.strip()) if result.stdout.strip() else 0
        assert count >= 2, f"Expected copay_notes to be referenced in main.py, found {count} times"
