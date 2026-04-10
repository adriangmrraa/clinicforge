"""
Tests for backup_service module.

Verifies pure helper functions: type coercion, table ordering,
exclusion guarantees, and checksum determinism.
No DB or Redis required — all pure-function tests.
"""

import sys
import os
from datetime import datetime, date, time
from decimal import Decimal
import uuid

# Add orchestrator_service to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service"))
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "orchestrator_service", "services"),
)


class TestCoerceValue:
    """Test _coerce_value for each supported type."""

    def test_coerce_value_datetime(self):
        from backup_service import _coerce_value

        dt = datetime(2026, 4, 10, 15, 30, 0)
        result = _coerce_value(dt)
        assert result == "2026-04-10T15:30:00"
        assert isinstance(result, str)

    def test_coerce_value_decimal(self):
        from backup_service import _coerce_value

        val = Decimal("123.45")
        result = _coerce_value(val)
        assert result == "Decimal:123.45"
        assert result.startswith("Decimal:")

    def test_coerce_value_uuid(self):
        from backup_service import _coerce_value

        uid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        result = _coerce_value(uid)
        assert result == "12345678-1234-5678-1234-567812345678"
        assert isinstance(result, str)

    def test_coerce_value_bytes(self):
        import base64
        from backup_service import _coerce_value

        raw = b"hello world"
        result = _coerce_value(raw)
        assert result.startswith("b64:")
        decoded = base64.b64decode(result[4:])
        assert decoded == raw

    def test_coerce_value_none(self):
        from backup_service import _coerce_value

        assert _coerce_value(None) is None

    def test_coerce_value_dict_passthrough(self):
        from backup_service import _coerce_value

        payload = {"key": "value", "nested": [1, 2, 3]}
        result = _coerce_value(payload)
        assert result is payload  # same object — no copy
        assert result["key"] == "value"

    def test_coerce_value_list_passthrough(self):
        from backup_service import _coerce_value

        payload = [1, "two", {"three": 3}]
        result = _coerce_value(payload)
        assert result is payload

    def test_coerce_value_date(self):
        from backup_service import _coerce_value

        d = date(2026, 4, 10)
        result = _coerce_value(d)
        assert result == "2026-04-10"
        assert isinstance(result, str)

    def test_coerce_value_time(self):
        from backup_service import _coerce_value

        t = time(9, 30, 0)
        result = _coerce_value(t)
        assert result == "09:30:00"
        assert isinstance(result, str)

    def test_coerce_value_int_passthrough(self):
        from backup_service import _coerce_value

        assert _coerce_value(42) == 42

    def test_coerce_value_str_passthrough(self):
        from backup_service import _coerce_value

        assert _coerce_value("hello") == "hello"


class TestCoerceRow:
    """Test _coerce_row with mixed-type rows."""

    def test_coerce_row_full(self):
        from backup_service import _coerce_row

        uid = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        row = {
            "id": 1,
            "name": "Test Clinic",
            "amount": Decimal("99.99"),
            "created_at": datetime(2026, 1, 15, 12, 0, 0),
            "logo": b"\x89PNG",
            "token": uid,
            "config": {"key": "val"},
            "tags": ["a", "b"],
            "notes": None,
        }

        result = _coerce_row(row)

        assert result["id"] == 1
        assert result["name"] == "Test Clinic"
        assert result["amount"] == "Decimal:99.99"
        assert result["created_at"] == "2026-01-15T12:00:00"
        assert result["logo"].startswith("b64:")
        assert result["token"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert result["config"] == {"key": "val"}
        assert result["tags"] == ["a", "b"]
        assert result["notes"] is None

    def test_coerce_row_empty(self):
        from backup_service import _coerce_row

        result = _coerce_row({})
        assert result == {}

    def test_coerce_row_preserves_all_keys(self):
        from backup_service import _coerce_row

        row = {"a": 1, "b": "two", "c": Decimal("3.0"), "d": None}
        result = _coerce_row(row)
        assert set(result.keys()) == {"a", "b", "c", "d"}


class TestExportTables:
    """Test EXPORT_TABLES ordering and contents."""

    def test_export_tables_order_tenants_first(self):
        from backup_service import EXPORT_TABLES

        assert EXPORT_TABLES[0] == "tenants", (
            "tenants must be first in EXPORT_TABLES for FK-safe export"
        )

    def test_export_tables_contains_patients(self):
        from backup_service import EXPORT_TABLES

        assert "patients" in EXPORT_TABLES

    def test_export_tables_contains_appointments(self):
        from backup_service import EXPORT_TABLES

        assert "appointments" in EXPORT_TABLES

    def test_export_tables_is_list(self):
        from backup_service import EXPORT_TABLES

        assert isinstance(EXPORT_TABLES, list)

    def test_export_tables_no_duplicates(self):
        from backup_service import EXPORT_TABLES

        assert len(EXPORT_TABLES) == len(set(EXPORT_TABLES)), (
            "EXPORT_TABLES must not have duplicate entries"
        )

    def test_professionals_before_appointments(self):
        """Professionals must appear before appointments for FK safety."""
        from backup_service import EXPORT_TABLES

        idx_prof = EXPORT_TABLES.index("professionals")
        idx_appt = EXPORT_TABLES.index("appointments")
        assert idx_prof < idx_appt

    def test_patients_before_appointments(self):
        """Patients must appear before appointments for FK safety."""
        from backup_service import EXPORT_TABLES

        idx_patients = EXPORT_TABLES.index("patients")
        idx_appt = EXPORT_TABLES.index("appointments")
        assert idx_patients < idx_appt


class TestExcludedTables:
    """Test that EXCLUDED_TABLES and EXPORT_TABLES have no overlap."""

    def test_excluded_tables_not_in_export(self):
        from backup_service import EXPORT_TABLES, EXCLUDED_TABLES

        overlap = set(EXPORT_TABLES) & EXCLUDED_TABLES
        assert not overlap, (
            f"Tables in both EXPORT_TABLES and EXCLUDED_TABLES: {overlap}"
        )

    def test_excluded_tables_is_set(self):
        from backup_service import EXCLUDED_TABLES

        assert isinstance(EXCLUDED_TABLES, set)

    def test_credentials_excluded(self):
        from backup_service import EXCLUDED_TABLES

        assert "credentials" in EXCLUDED_TABLES

    def test_users_excluded(self):
        from backup_service import EXCLUDED_TABLES

        assert "users" in EXCLUDED_TABLES

    def test_alembic_version_excluded(self):
        from backup_service import EXCLUDED_TABLES

        assert "alembic_version" in EXCLUDED_TABLES


class TestComputeChecksum:
    """Test _compute_checksum determinism and format."""

    def test_compute_checksum_deterministic(self):
        from backup_service import _compute_checksum

        data = b'[{"id": 1, "name": "Test"}]'
        hash1 = _compute_checksum(data)
        hash2 = _compute_checksum(data)
        assert hash1 == hash2

    def test_compute_checksum_hex_string(self):
        from backup_service import _compute_checksum

        result = _compute_checksum(b"hello")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex digest

    def test_compute_checksum_different_input_different_output(self):
        from backup_service import _compute_checksum

        h1 = _compute_checksum(b"data A")
        h2 = _compute_checksum(b"data B")
        assert h1 != h2

    def test_compute_checksum_empty_bytes(self):
        from backup_service import _compute_checksum

        # SHA-256 of empty string is well-known
        result = _compute_checksum(b"")
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_compute_checksum_known_value(self):
        """Cross-check against Python's own hashlib for confidence."""
        import hashlib
        from backup_service import _compute_checksum

        data = b"ClinicForge backup integrity check"
        expected = hashlib.sha256(data).hexdigest()
        assert _compute_checksum(data) == expected
