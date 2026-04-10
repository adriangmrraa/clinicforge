"""
Tests for restore_service module.

Verifies pure helper functions: manifest validation, type de-coercion,
and tenant ID remapping. No DB or Redis required.
"""

import sys
import os
import base64
from datetime import datetime, date
from decimal import Decimal

# Add orchestrator_service to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator_service"))
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "orchestrator_service", "services"),
)


class TestValidateManifest:
    """Test validate_manifest with all valid/invalid scenarios."""

    def _valid_manifest(self):
        return {
            "version": "1.0",
            "alembic_head": "032_multi_agent_tables",
            "tenant_id": 1,
            "created_at": "2026-04-10T12:00:00",
            "table_counts": {"tenants": 1, "patients": 42},
        }

    def test_validate_manifest_valid(self):
        from restore_service import validate_manifest

        is_valid, error = validate_manifest(self._valid_manifest())
        assert is_valid is True
        assert error == ""

    def test_validate_manifest_wrong_version(self):
        from restore_service import validate_manifest

        manifest = self._valid_manifest()
        manifest["version"] = "9.9"

        is_valid, error = validate_manifest(manifest)
        assert is_valid is False
        assert "9.9" in error
        assert "versión" in error.lower() or "version" in error.lower()

    def test_validate_manifest_missing_key_alembic_head(self):
        from restore_service import validate_manifest

        manifest = self._valid_manifest()
        del manifest["alembic_head"]

        is_valid, error = validate_manifest(manifest)
        assert is_valid is False
        assert "alembic_head" in error

    def test_validate_manifest_missing_key_tenant_id(self):
        from restore_service import validate_manifest

        manifest = self._valid_manifest()
        del manifest["tenant_id"]

        is_valid, error = validate_manifest(manifest)
        assert is_valid is False
        assert "tenant_id" in error

    def test_validate_manifest_missing_key_created_at(self):
        from restore_service import validate_manifest

        manifest = self._valid_manifest()
        del manifest["created_at"]

        is_valid, error = validate_manifest(manifest)
        assert is_valid is False
        assert "created_at" in error

    def test_validate_manifest_missing_key_table_counts(self):
        from restore_service import validate_manifest

        manifest = self._valid_manifest()
        del manifest["table_counts"]

        is_valid, error = validate_manifest(manifest)
        assert is_valid is False
        assert "table_counts" in error

    def test_validate_manifest_empty_dict(self):
        from restore_service import validate_manifest

        is_valid, error = validate_manifest({})
        # Empty dict has no "version" key, returns False
        assert is_valid is False

    def test_validate_manifest_none(self):
        from restore_service import validate_manifest

        is_valid, error = validate_manifest(None)
        assert is_valid is False
        assert error != ""

    def test_validate_manifest_returns_tuple(self):
        from restore_service import validate_manifest

        result = validate_manifest(self._valid_manifest())
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestDecoerceValue:
    """Test _decoerce_value for each type marker."""

    def test_decoerce_value_decimal(self):
        from restore_service import _decoerce_value

        result = _decoerce_value("Decimal:123.45")
        assert result == Decimal("123.45")
        assert isinstance(result, Decimal)

    def test_decoerce_value_decimal_zero(self):
        from restore_service import _decoerce_value

        result = _decoerce_value("Decimal:0.00")
        assert result == Decimal("0.00")

    def test_decoerce_value_decimal_large(self):
        from restore_service import _decoerce_value

        result = _decoerce_value("Decimal:9999999.99")
        assert result == Decimal("9999999.99")

    def test_decoerce_value_base64(self):
        from restore_service import _decoerce_value

        raw = b"\x89PNG\r\n"
        encoded = "b64:" + base64.b64encode(raw).decode()
        result = _decoerce_value(encoded)
        assert result == raw
        assert isinstance(result, bytes)

    def test_decoerce_value_base64_empty(self):
        from restore_service import _decoerce_value

        encoded = "b64:" + base64.b64encode(b"").decode()
        result = _decoerce_value(encoded)
        assert result == b""

    def test_decoerce_value_datetime(self):
        from restore_service import _decoerce_value

        result = _decoerce_value("2026-04-10T15:30:00")
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 10
        assert result.hour == 15
        assert result.minute == 30

    def test_decoerce_value_datetime_with_microseconds(self):
        from restore_service import _decoerce_value

        result = _decoerce_value("2026-04-10T15:30:00.123456")
        assert isinstance(result, datetime)
        assert result.microsecond == 123456

    def test_decoerce_value_date(self):
        from restore_service import _decoerce_value

        result = _decoerce_value("2026-04-10")
        assert isinstance(result, date)
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 10

    def test_decoerce_value_none(self):
        from restore_service import _decoerce_value

        assert _decoerce_value(None) is None

    def test_decoerce_value_int_passthrough(self):
        from restore_service import _decoerce_value

        assert _decoerce_value(42) == 42

    def test_decoerce_value_plain_string_passthrough(self):
        from restore_service import _decoerce_value

        assert _decoerce_value("hello world") == "hello world"

    def test_decoerce_value_dict_passthrough(self):
        from restore_service import _decoerce_value

        payload = {"key": "value"}
        result = _decoerce_value(payload)
        assert result == payload

    def test_decoerce_value_known_decimal_column_without_marker(self):
        """Backward compat: plain numeric string in a known decimal column."""
        from restore_service import _decoerce_value

        result = _decoerce_value("500.00", col_name="billing_amount")
        assert isinstance(result, Decimal)
        assert result == Decimal("500.00")

    def test_decoerce_value_unknown_column_plain_numeric_stays_str(self):
        """Non-decimal column: plain numeric string stays as string."""
        from restore_service import _decoerce_value

        result = _decoerce_value("500.00", col_name="some_other_column")
        assert isinstance(result, str)
        assert result == "500.00"


class TestRemapTenantId:
    """Test _remap_tenant_id for cross-tenant restore."""

    def test_remap_tenant_id_replaces_tenant_id(self):
        from restore_service import _remap_tenant_id

        rows = [
            {"id": 1, "tenant_id": 10, "name": "Alice"},
            {"id": 2, "tenant_id": 10, "name": "Bob"},
        ]
        result = _remap_tenant_id(rows, source_tid=10, target_tid=99)
        assert result[0]["tenant_id"] == 99
        assert result[1]["tenant_id"] == 99

    def test_remap_tenant_id_preserves_other_fields(self):
        from restore_service import _remap_tenant_id

        rows = [{"id": 7, "tenant_id": 10, "name": "Alice"}]
        result = _remap_tenant_id(rows, source_tid=10, target_tid=99)
        assert result[0]["id"] == 7
        assert result[0]["name"] == "Alice"

    def test_remap_tenant_id_same_source_target_returns_unchanged(self):
        from restore_service import _remap_tenant_id

        rows = [{"id": 1, "tenant_id": 10, "name": "Alice"}]
        result = _remap_tenant_id(rows, source_tid=10, target_tid=10)
        # Same source and target → returns the original list unchanged
        assert result is rows

    def test_remap_tenant_id_empty_list(self):
        from restore_service import _remap_tenant_id

        result = _remap_tenant_id([], source_tid=10, target_tid=99)
        assert result == []

    def test_remap_tenant_id_row_without_tenant_id_field(self):
        """Rows without tenant_id column (e.g. junction tables) are left as-is."""
        from restore_service import _remap_tenant_id

        rows = [{"treatment_type_id": 1, "professional_id": 2}]
        result = _remap_tenant_id(rows, source_tid=10, target_tid=99)
        assert "tenant_id" not in result[0]
        assert result[0]["treatment_type_id"] == 1

    def test_remap_tenant_id_does_not_mutate_original_rows(self):
        """Must not mutate the original dicts."""
        from restore_service import _remap_tenant_id

        rows = [{"id": 1, "tenant_id": 10}]
        _remap_tenant_id(rows, source_tid=10, target_tid=99)
        # Original row should still have tenant_id=10
        assert rows[0]["tenant_id"] == 10

    def test_remap_tenant_id_multiple_rows_correct_count(self):
        from restore_service import _remap_tenant_id

        rows = [{"id": i, "tenant_id": 5} for i in range(20)]
        result = _remap_tenant_id(rows, source_tid=5, target_tid=42)
        assert len(result) == 20
        assert all(r["tenant_id"] == 42 for r in result)
