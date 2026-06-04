"""
Tests for anti-loop booking fixes (v8.2: fix-agent-booking-loop).

Covers:
- Statement hash dedup (_hash_statement from buffer_task)
- Book error protocol (_format_book_error, BOOKING_ERROR_CODES from main)
- Anti-loop constants (MAX_BOOKING_ATTEMPTS, SLOT_LOCK_TTL_SECONDS)

Note: main.py has heavy dependencies (gcal_service, asyncpg, etc.) so we use
importlib to extract constants and pure functions without triggering the full
import chain.
"""

import unittest
import hashlib
import sys
import os
import importlib.util

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def _extract_main_constants():
    """Extract constants and pure helpers from main.py without full import.

    Parses the module-level constants before the heavy import block that
    triggers gcal_service/googleapiclient.
    """
    main_path = os.path.join(PROJECT_ROOT, "main.py")
    with open(main_path, "r", encoding="utf-8") as f:
        source = f.read()

    # Extract constants from the module-level scope (before tool definitions)
    import re

    result = {}

    # SLOT_LOCK_TTL_SECONDS = 600
    m = re.search(r"SLOT_LOCK_TTL_SECONDS\s*=\s*(\d+)", source)
    if m:
        result["SLOT_LOCK_TTL_SECONDS"] = int(m.group(1))

    # MAX_BOOKING_ATTEMPTS = 3
    m = re.search(r"MAX_BOOKING_ATTEMPTS\s*=\s*(\d+)", source)
    if m:
        result["MAX_BOOKING_ATTEMPTS"] = int(m.group(1))

    # BOOKING_ERROR_CODES = { ... }
    # Count the number of entries
    codes_section = re.search(
        r'BOOKING_ERROR_CODES\s*=\s*\{(.*?)\}',
        source,
        re.DOTALL,
    )
    if codes_section:
        # Count quoted keys
        result["BOOKING_ERROR_CODES_COUNT"] = len(
            re.findall(r'"([A-Z_]+)"\s*:', codes_section.group(1))
        )

    # _format_book_error function body — verify its structure
    m = re.search(
        r"def _format_book_error\(code: str, msg: str = \"\", action: str = \"\"\) -> str:(.*?)(?=\n\ndef |\n\n@|\n\n# v8|\n\nclass |\n\nasync |\Z)",
        source,
        re.DOTALL,
    )
    if m:
        result["_format_book_error_body"] = m.group(1)

    return result


class TestStatementHashDedup(unittest.TestCase):
    """Test _hash_statement deterministic output and dedup logic."""

    def test_deterministic_hash_same_input(self):
        """Same text produces same hash."""
        from services.buffer_task import _hash_statement

        text = "No tenés turnos activos en este momento."
        h1 = _hash_statement(text)
        h2 = _hash_statement(text)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 12)

    def test_different_inputs_different_hash(self):
        """Different texts produce different hashes."""
        from services.buffer_task import _hash_statement

        h1 = _hash_statement("Hola, ¿cómo estás?")
        h2 = _hash_statement("Buen día, ¿en qué te puedo ayudar?")
        self.assertNotEqual(h1, h2)

    def test_hash_is_hex(self):
        """Hash is 12-char lowercase hex."""
        from services.buffer_task import _hash_statement

        import re

        h = _hash_statement("test")
        self.assertTrue(
            re.match(r"^[0-9a-f]{12}$", h), f"Hash '{h}' is not 12-char hex"
        )

    def test_hash_uses_sha256(self):
        """Verify hash is sha256[:12] as designed."""
        from services.buffer_task import _hash_statement

        text = "verification"
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        actual = _hash_statement(text)
        self.assertEqual(actual, expected)


class TestBookErrorConstants(unittest.TestCase):
    """Test anti-loop constants from main.py (extracted via source parsing)."""

    @classmethod
    def setUpClass(cls):
        cls.constants = _extract_main_constants()

    def test_slot_lock_ttl_is_600(self):
        """SLOT_LOCK_TTL_SECONDS is 600 (10 min)."""
        self.assertEqual(
            self.constants.get("SLOT_LOCK_TTL_SECONDS"),
            600,
            "SLOT_LOCK_TTL_SECONDS should be 600",
        )

    def test_max_booking_attempts_is_3(self):
        """MAX_BOOKING_ATTEMPTS is 3."""
        self.assertEqual(
            self.constants.get("MAX_BOOKING_ATTEMPTS"),
            3,
            "MAX_BOOKING_ATTEMPTS should be 3",
        )

    def test_booking_error_codes_count_is_8(self):
        """All 8 error codes are defined in BOOKING_ERROR_CODES."""
        self.assertEqual(
            self.constants.get("BOOKING_ERROR_CODES_COUNT"),
            8,
            "BOOKING_ERROR_CODES should have 8 entries",
        )

    def test_format_book_error_function_exists(self):
        """_format_book_error function is defined in main.py."""
        body = self.constants.get("_format_book_error_body")
        self.assertIsNotNone(body, "_format_book_error function not found")
        # Verify it produces the correct format pattern
        self.assertIn("[BOOK_ERROR:", body, "Function must emit [BOOK_ERROR: prefix")
        self.assertIn("[ACTION:", body, "Function must emit [ACTION: prefix when action provided")
        self.assertIn("BOOKING_ERROR_CODES.get", body, "Function must use BOOKING_ERROR_CODES dict")


if __name__ == "__main__":
    unittest.main()
