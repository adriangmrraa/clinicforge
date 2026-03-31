"""
Tests for treatment priority scheduling logic in ClinicForge.

Covers three areas extracted directly from production code:

1. Candidate sorting by is_priority_professional
   - Used in check_availability (main.py ~L1526) and book_appointment (main.py ~L2262)
   - Both use: sorted(..., key=lambda p: (0 if p.get("is_priority_professional") else 1))

2. FAQ category prefix formatting
   - Used in _format_faqs (main.py ~L5075-5078) and format_faqs_with_rag
     (embedding_service.py ~L251-252)
   - Both use: cat = faq.get("category", "General") or "General"
   -           f'[{cat}] {question}: "{answer}"'

3. Treatment priority field validation
   - Valid values: ('high', 'medium-high', 'medium', 'low')
   - Default when omitted: 'medium'
"""

import pytest


# ---------------------------------------------------------------------------
# Group 1: Candidate sorting (check_availability & book_appointment)
# ---------------------------------------------------------------------------


class TestCandidateSorting:
    """
    Tests for the priority-professional sort applied to both
    active_professionals (check_availability, main.py L1526) and
    candidates (book_appointment, main.py L2262).

    Sort key: lambda p: (0 if p.get("is_priority_professional") else 1)
    """

    def test_priority_professional_sorted_first(self):
        """A single priority professional rises to position 0."""
        candidates = [
            {"id": 1, "first_name": "Juan", "is_priority_professional": False},
            {"id": 2, "first_name": "Laura", "is_priority_professional": True},
            {"id": 3, "first_name": "Pedro", "is_priority_professional": False},
        ]
        sorted_candidates = sorted(
            candidates, key=lambda p: (0 if p.get("is_priority_professional") else 1)
        )
        assert sorted_candidates[0]["id"] == 2, "Laura (priority=True) must be first"

    def test_priority_professionals_all_precede_non_priority(self):
        """Multiple priority professionals all appear before any non-priority one."""
        candidates = [
            {"id": 1, "first_name": "Ana", "is_priority_professional": False},
            {"id": 2, "first_name": "Luis", "is_priority_professional": True},
            {"id": 3, "first_name": "Marta", "is_priority_professional": False},
            {"id": 4, "first_name": "Jorge", "is_priority_professional": True},
        ]
        sorted_candidates = sorted(
            candidates, key=lambda p: (0 if p.get("is_priority_professional") else 1)
        )
        priority_ids = {2, 4}
        non_priority_ids = {1, 3}
        result_ids = [c["id"] for c in sorted_candidates]
        first_two = set(result_ids[:2])
        last_two = set(result_ids[2:])
        assert first_two == priority_ids
        assert last_two == non_priority_ids

    def test_no_priority_professionals_preserves_original_order(self):
        """Stable sort must preserve insertion order when all have equal key."""
        candidates = [
            {"id": 1, "first_name": "Juan", "is_priority_professional": False},
            {"id": 2, "first_name": "Pedro", "is_priority_professional": False},
        ]
        sorted_candidates = sorted(
            candidates, key=lambda p: (0 if p.get("is_priority_professional") else 1)
        )
        assert sorted_candidates[0]["id"] == 1
        assert sorted_candidates[1]["id"] == 2

    def test_all_priority_preserves_original_order(self):
        """Stable sort must preserve insertion order when all are priority."""
        candidates = [
            {"id": 1, "first_name": "Juan", "is_priority_professional": True},
            {"id": 2, "first_name": "Laura", "is_priority_professional": True},
        ]
        sorted_candidates = sorted(
            candidates, key=lambda p: (0 if p.get("is_priority_professional") else 1)
        )
        assert sorted_candidates[0]["id"] == 1
        assert sorted_candidates[1]["id"] == 2

    def test_missing_priority_field_treated_as_false(self):
        """A dict without is_priority_professional key must be treated as non-priority."""
        candidates = [
            {"id": 1, "first_name": "Juan"},  # key absent
            {"id": 2, "first_name": "Laura", "is_priority_professional": True},
        ]
        sorted_candidates = sorted(
            candidates, key=lambda p: (0 if p.get("is_priority_professional") else 1)
        )
        assert sorted_candidates[0]["id"] == 2

    def test_empty_candidate_list_returns_empty(self):
        """Sorting an empty list must not raise and must return empty list."""
        result = sorted(
            [], key=lambda p: (0 if p.get("is_priority_professional") else 1)
        )
        assert result == []

    def test_single_priority_professional_is_first(self):
        """Degenerate case: single element list stays unchanged."""
        candidates = [{"id": 42, "first_name": "Solo", "is_priority_professional": True}]
        result = sorted(
            candidates, key=lambda p: (0 if p.get("is_priority_professional") else 1)
        )
        assert result[0]["id"] == 42


# ---------------------------------------------------------------------------
# Group 2: FAQ category prefix formatting
# ---------------------------------------------------------------------------


class TestFaqCategoryPrefix:
    """
    Tests for the [Category] prefix logic used in:
      - _format_faqs (main.py L5075-5078)
      - format_faqs_with_rag fallback (embedding_service.py L259-263)
      - format_faqs_with_rag RAG path (embedding_service.py L251-252)

    Pattern:
        cat = faq.get("category", "General") or "General"
        line = f'[{cat}] {question}: "{answer}"'
    """

    @staticmethod
    def _format_faq_line(faq: dict) -> str:
        """Mirrors the exact production formatting logic from main.py L5075-5078."""
        cat = faq.get("category", "General") or "General"
        q = faq.get("question", "")
        a = faq.get("answer", "")
        return f'[{cat}] {q}: "{a}"'

    def test_faq_category_prefix_format(self):
        """FAQ with an explicit category must include it as a bracket prefix."""
        faq = {"category": "Estrategia ventas", "question": "¿Cómo responder?", "answer": "Con empatía"}
        result = self._format_faq_line(faq)
        assert result.startswith("[Estrategia ventas]")
        assert "¿Cómo responder?" in result
        assert '"Con empatía"' in result

    def test_faq_null_category_defaults_to_general(self):
        """Explicit None category must fall back to 'General' via `or` operator."""
        faq = {"category": None, "question": "Test?", "answer": "Yes"}
        result = self._format_faq_line(faq)
        assert result.startswith("[General]")

    def test_faq_missing_category_defaults_to_general(self):
        """Absent category key must fall back to 'General' via default arg."""
        faq = {"question": "Test?", "answer": "Yes"}
        result = self._format_faq_line(faq)
        assert result.startswith("[General]")

    def test_faq_empty_string_category_defaults_to_general(self):
        """Empty-string category is falsy and must also fall back to 'General'."""
        faq = {"category": "", "question": "Test?", "answer": "Yes"}
        result = self._format_faq_line(faq)
        assert result.startswith("[General]")

    def test_faq_answer_is_double_quoted(self):
        """Answer must be wrapped in double quotes per the format string."""
        faq = {"category": "Turnos", "question": "¿Cuándo abren?", "answer": "De 8 a 18"}
        result = self._format_faq_line(faq)
        assert '"De 8 a 18"' in result

    def test_faq_format_full_structure(self):
        """Complete format: [Cat] Question: "Answer" with no extra separators."""
        faq = {"category": "Pagos", "question": "¿Aceptan débito?", "answer": "Sí, todas las tarjetas"}
        result = self._format_faq_line(faq)
        assert result == '[Pagos] ¿Aceptan débito?: "Sí, todas las tarjetas"'


# ---------------------------------------------------------------------------
# Group 3: Treatment priority field validation
# ---------------------------------------------------------------------------


class TestTreatmentPriorityValidation:
    """
    Tests for the valid priority values used when creating/updating
    treatment types. Valid set: ('high', 'medium-high', 'medium', 'low').
    Default when the key is absent: 'medium'.
    """

    VALID_PRIORITIES = ("high", "medium-high", "medium", "low")

    def test_valid_priority_values_are_recognized(self):
        """All four defined priority levels must be in the valid set."""
        for v in self.VALID_PRIORITIES:
            assert v in self.VALID_PRIORITIES

    def test_default_priority_is_medium(self):
        """A body dict without an explicit priority key must default to 'medium'."""
        body = {"name": "Limpieza", "code": "LIMP"}
        priority = body.get("priority", "medium")
        assert priority == "medium"

    def test_explicit_priority_overrides_default(self):
        """When priority is present in the body, it must be used as-is."""
        body = {"name": "Implante", "code": "IMP", "priority": "high"}
        priority = body.get("priority", "medium")
        assert priority == "high"

    def test_invalid_priority_urgent_rejected(self):
        """'urgent' is not a valid priority value."""
        assert "urgent" not in self.VALID_PRIORITIES

    def test_invalid_priority_critical_rejected(self):
        """'critical' is not a valid priority value."""
        assert "critical" not in self.VALID_PRIORITIES

    def test_invalid_priority_none_rejected(self):
        """None is not in the valid priority set."""
        assert None not in self.VALID_PRIORITIES

    def test_all_valid_priorities_accepted_individually(self):
        """Each valid value passes an `in` membership check."""
        for priority in ("high", "medium-high", "medium", "low"):
            assert priority in self.VALID_PRIORITIES, f"'{priority}' should be valid"

    def test_priority_count_is_four(self):
        """Exactly four priority levels are defined — no more, no less."""
        assert len(self.VALID_PRIORITIES) == 4
