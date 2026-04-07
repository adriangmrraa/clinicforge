"""
Tests for date validator module.

Bug #1: Test cases for detecting and correcting DD↔MM swaps in LLM responses.
"""

import pytest
import sys
import os
from datetime import date

# Add orchestrator_service to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service")
)
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service", "services")
)

from date_validator import (
    CanonicalDate,
    extract_canonical_dates,
    validate_and_correct,
    validate_dates_in_response,
)


class TestDateValidator:
    """Test date validation and correction."""

    def test_swap_dd_mm_detected(self):
        """Case 1: Swap detected - LLM wrote 05/12 but tool returned 12/05"""
        canonical = [
            CanonicalDate(
                date_obj=date(2025, 5, 12),
                display="12/05",
                source_tool="check_availability",
            )
        ]
        text = "Te confirmo el turno para el 05/12"

        result, corrections = validate_and_correct(text, canonical)

        assert "12/05" in result
        assert "05/12" not in result
        assert len(corrections) == 1

    def test_swap_with_weekday(self):
        """Case 2: Swap in weekday context - 'Sábado 05/12' should become 'Sábado 12/05'"""
        canonical = [
            CanonicalDate(
                date_obj=date(2025, 5, 12),
                display="12/05",
                source_tool="check_availability",
            )
        ]
        text = "Sábado 05/12 a las 14:00"

        result, corrections = validate_and_correct(text, canonical)

        assert "12/05" in result
        assert "05/12" not in result

    def test_correct_date_unchanged(self):
        """Case 3: Date already correct - no change needed"""
        canonical = [
            CanonicalDate(
                date_obj=date(2025, 5, 12),
                display="12/05",
                source_tool="check_availability",
            )
        ]
        text = "12/05 a las 10:00"

        result, corrections = validate_and_correct(text, canonical)

        assert "12/05" in result
        assert "05/12" not in result
        assert len(corrections) == 0

    def test_no_dates_in_response(self):
        """Case 4: No dates in response - should not modify text"""
        canonical = [
            CanonicalDate(
                date_obj=date(2025, 5, 12),
                display="12/05",
                source_tool="check_availability",
            )
        ]
        text = "Perfecto, te confirmo el turno"

        result, corrections = validate_and_correct(text, canonical)

        assert result == text
        assert len(corrections) == 0

    def test_no_canonical_dates(self):
        """Case 5: No canonical dates - should not modify text"""
        canonical = []
        text = "Te confirmo para el 05/12"

        result, corrections = validate_and_correct(text, canonical)

        assert result == text
        assert len(corrections) == 0

    def test_date_with_year_correct(self):
        """Case 6: Date with year - correct format"""
        canonical = [
            CanonicalDate(
                date_obj=date(2025, 6, 3),
                display="03/06/2025",
                source_tool="book_appointment",
            )
        ]
        text = "03/06/2025 a las 10:00"

        result, corrections = validate_and_correct(text, canonical)

        assert result == text
        assert len(corrections) == 0

    def test_date_with_year_swapped(self):
        """Case 7: Date with year - swap detected"""
        canonical = [
            CanonicalDate(
                date_obj=date(2025, 6, 3),
                display="03/06/2025",
                source_tool="book_appointment",
            )
        ]
        text = "06/03/2025 a las 10:00"

        result, corrections = validate_and_correct(text, canonical)

        assert "03/06/2025" in result
        assert len(corrections) == 1

    def test_multiple_dates_correct(self):
        """Case 8: Multiple dates, both correct - no changes"""
        canonical = [
            CanonicalDate(
                date_obj=date(2025, 4, 7),
                display="07/04",
                source_tool="check_availability",
            ),
            CanonicalDate(
                date_obj=date(2025, 4, 9),
                display="09/04",
                source_tool="check_availability",
            ),
        ]
        text = "Lunes 07/04 y Miércoles 09/04"

        result, corrections = validate_and_correct(text, canonical)

        assert result == text
        assert len(corrections) == 0

    def test_multiple_dates_both_swapped(self):
        """Case 9: Multiple dates, both swapped - both corrected"""
        canonical = [
            CanonicalDate(
                date_obj=date(2025, 4, 7),
                display="07/04",
                source_tool="check_availability",
            ),
            CanonicalDate(
                date_obj=date(2025, 4, 9),
                display="09/04",
                source_tool="check_availability",
            ),
        ]
        text = "Lunes 04/07 y Miércoles 04/09"

        result, corrections = validate_and_correct(text, canonical)

        assert "07/04" in result
        assert "09/04" in result
        assert "04/07" not in result
        assert "04/09" not in result

    def test_intermediate_steps_as_string(self):
        """Case 10: Intermediate steps as string (not dict) - should not crash"""
        # Simulate broken intermediate step
        intermediate_steps = [("some_action", "this is not a dict, just a string")]

        text = "Te confirmo para el 05/12"

        # Should not raise, should return original
        result = validate_dates_in_response(text, intermediate_steps)

        assert result == text


class TestExtractCanonicalDates:
    """Test extraction of canonical dates from intermediate steps."""

    def test_extract_from_dict_observation(self):
        """Extract date from dict observation with date_display key"""

        # Mock action with tool attribute
        class MockAction:
            tool = "check_availability"

        observation = {"date_display": "12/05", "slots": []}
        intermediate_steps = [(MockAction(), observation)]

        result = extract_canonical_dates(intermediate_steps)

        assert len(result) == 1
        assert result[0].display == "12/05"
        assert result[0].source_tool == "check_availability"

    def test_extract_multiple_dates(self):
        """Extract multiple dates from intermediate steps"""

        class MockAction:
            tool = "book_appointment"

        observation = {"date_display": "15/06/2025", "appointment_id": 123}
        intermediate_steps = [(MockAction(), observation)]

        result = extract_canonical_dates(intermediate_steps)

        assert len(result) == 1

    def test_empty_intermediate_steps(self):
        """Empty intermediate steps returns empty list"""
        result = extract_canonical_dates([])
        assert result == []
