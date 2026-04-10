"""
Tests for phone normalization in ycloud-sync.
"""

import unittest
from ycloud_client import normalize_phone_e164


class TestPhoneNormalization(unittest.TestCase):
    """Test cases for phone number normalization to E.164 format."""

    def test_already_e164_format(self):
        """Test already normalized E.164 numbers."""
        self.assertEqual(normalize_phone_e164("+5491144445555"), "+5491144445555")
        self.assertEqual(normalize_phone_e164("+5435112345678"), "+5435112345678")

    def test_549_format_without_plus(self):
        """Test 549 format without + prefix."""
        self.assertEqual(normalize_phone_e164("5491144445555"), "+5491144445555")
        self.assertEqual(normalize_phone_e164("54935112345678"), "+5435112345678")

    def test_buenos_aires_11(self):
        """Test Buenos Aires area code 11 without country code."""
        self.assertEqual(normalize_phone_e164("1144445555"), "+5491144445555")
        self.assertEqual(normalize_phone_e164("11 4444-5555"), "+5491144445555")

    def test_local_10_digits(self):
        """Test 10-digit local numbers assumed to be Argentina."""
        self.assertEqual(normalize_phone_e164("44445555"), "+5491144445555")
        self.assertEqual(normalize_phone_e164("3511234567"), "+5435112345678")

    def test_international_format_with_plus(self):
        """Test international format with + but different country."""
        self.assertEqual(normalize_phone_e164("+1 212 555 1234"), "+12125551234")
        self.assertEqual(normalize_phone_e164("+44 20 7946 0958"), "+442079460958")

    def test_spaces_and_dashes_removed(self):
        """Test that spaces and dashes are removed."""
        self.assertEqual(normalize_phone_e164("+54 9 11 4444 5555"), "+5491144445555")
        self.assertEqual(normalize_phone_e164("+54-9-11-4444-5555"), "+5491144445555")

    def test_empty_input(self):
        """Test empty input returns empty string."""
        self.assertEqual(normalize_phone_e164(""), "")

    def test_only_special_chars(self):
        """Test input with only special characters."""
        self.assertEqual(normalize_phone_e164("abc-xyz"), "abc-xyz")

    def test_whatsapp_format(self):
        """Test WhatsApp format typically seen in messages."""
        self.assertEqual(normalize_phone_e164("5491144445555"), "+5491144445555")
        self.assertEqual(normalize_phone_e164("+5491144445555"), "+5491144445555")


if __name__ == "__main__":
    unittest.main()
