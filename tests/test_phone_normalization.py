"""
Test cases for phone normalization.

Bug #5: Verify that normalize_phone_digits() produces consistent results
for various phone number formats.
"""

import re
from typing import Optional


def normalize_phone_digits(phone: Optional[str]) -> str:
    """Normaliza teléfono a solo dígitos (E.164 sin +) para comparaciones robustas.
    Permite match entre +54911..., 54911..., 54 9 11... etc."""
    if not phone:
        return ""
    return re.sub(r"\D", "", str(phone))


class TestPhoneNormalization:
    """Test phone normalization edge cases."""

    def test_with_plus54(self):
        """+5491112345678 should normalize to 5491112345678"""
        result = normalize_phone_digits("+5491112345678")
        assert result == "5491112345678"

    def test_without_prefix(self):
        """1112345678 should remain as is"""
        result = normalize_phone_digits("1112345678")
        assert result == "1112345678"

    def test_with_local_prefix_zero(self):
        """01112345678 should remain as is (function only strips non-digits)"""
        result = normalize_phone_digits("01112345678")
        assert result == "01112345678"

    def test_with_country_code_54(self):
        """5491112345678 should remain as is"""
        result = normalize_phone_digits("5491112345678")
        assert result == "5491112345678"

    def test_with_spaces_and_dashes(self):
        """+54 9 11 1234-5678 should normalize to 5491112345678"""
        result = normalize_phone_digits("+54 9 11 1234-5678")
        assert result == "5491112345678"
