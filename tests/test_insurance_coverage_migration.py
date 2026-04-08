"""Unit tests for migration 034 data migration logic.

These test the pure functions `_migrate_restrictions_to_coverage` and
`_migrate_coverage_to_restrictions` exported from the migration module.
No database is required — they are pure string/dict transforms.

Run: pytest tests/test_insurance_coverage_migration.py -v
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Dynamically import the migration module since it lives under a hyphenated
# directory name (alembic/versions/) that is not a package.
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "orchestrator_service"
    / "alembic"
    / "versions"
    / "034_insurance_coverage_by_treatment.py"
)
_spec = importlib.util.spec_from_file_location(
    "migration_034_insurance_coverage", _MIGRATION_PATH
)
_module = importlib.util.module_from_spec(_spec)
sys.modules["migration_034_insurance_coverage"] = _module
# The migration imports alembic.op at module load; we stub it out for tests
# so the import does not fail when running pytest outside alembic context.
try:
    _spec.loader.exec_module(_module)
except Exception:
    # Fallback: stub alembic.op and retry
    import types

    alembic_stub = types.ModuleType("alembic")
    alembic_stub.op = types.SimpleNamespace(
        add_column=lambda *a, **k: None,
        drop_column=lambda *a, **k: None,
        get_bind=lambda: None,
    )
    sys.modules.setdefault("alembic", alembic_stub)
    sys.modules.setdefault("alembic.op", alembic_stub.op)
    _spec.loader.exec_module(_module)

_migrate_restrictions_to_coverage = _module._migrate_restrictions_to_coverage
_migrate_coverage_to_restrictions = _module._migrate_coverage_to_restrictions
_default_coverage_entry = _module._default_coverage_entry


class TestInsuranceCoverageMigration:
    """Forward migration: restrictions JSON array → coverage_by_treatment dict."""

    def test_upgrade_migrates_valid_restrictions_array(self):
        result = _migrate_restrictions_to_coverage('["IMPT", "CONS"]')
        assert "IMPT" in result
        assert "CONS" in result
        assert result["IMPT"]["covered"] is True
        assert result["CONS"]["covered"] is True
        assert result["IMPT"]["copay_percent"] == 0.0
        assert result["IMPT"]["requires_pre_authorization"] is False
        assert result["IMPT"]["waiting_period_days"] == 0
        assert result["IMPT"]["max_annual_coverage"] is None

    def test_upgrade_handles_null_restrictions(self):
        assert _migrate_restrictions_to_coverage(None) == {}

    def test_upgrade_handles_empty_string_restrictions(self):
        assert _migrate_restrictions_to_coverage("") == {}

    def test_upgrade_handles_invalid_json_restrictions(self):
        # Free-form text → empty coverage (no crash)
        assert _migrate_restrictions_to_coverage("texto libre") == {}

    def test_upgrade_handles_non_list_json(self):
        # Valid JSON but not a list → empty coverage
        assert _migrate_restrictions_to_coverage('{"not": "a list"}') == {}
        assert _migrate_restrictions_to_coverage('"just a string"') == {}
        assert _migrate_restrictions_to_coverage("42") == {}

    def test_upgrade_skips_empty_codes(self):
        # Empty strings and whitespace-only codes are filtered out
        result = _migrate_restrictions_to_coverage('["IMPT", "", "   ", "CONS"]')
        assert set(result.keys()) == {"IMPT", "CONS"}

    def test_upgrade_trims_whitespace_from_codes(self):
        result = _migrate_restrictions_to_coverage('["  IMPT  ", "CONS"]')
        assert "IMPT" in result
        assert "  IMPT  " not in result
        assert "CONS" in result

    def test_upgrade_skips_non_string_entries(self):
        # Numbers and null entries are ignored
        result = _migrate_restrictions_to_coverage('["IMPT", 42, null, "CONS"]')
        assert set(result.keys()) == {"IMPT", "CONS"}


class TestInsuranceCoverageDowngrade:
    """Reverse migration: coverage_by_treatment dict → restrictions JSON array."""

    def test_downgrade_restores_covered_codes(self):
        coverage = {
            "IMPT": {"covered": True, "copay_percent": 30},
            "CONS": {"covered": False},
        }
        result = _migrate_coverage_to_restrictions(coverage)
        assert result == '["IMPT"]'

    def test_downgrade_empty_coverage_gives_null(self):
        assert _migrate_coverage_to_restrictions({}) is None
        assert _migrate_coverage_to_restrictions(None) is None

    def test_downgrade_all_not_covered_gives_null(self):
        coverage = {
            "IMPT": {"covered": False},
            "CONS": {"covered": False},
        }
        assert _migrate_coverage_to_restrictions(coverage) is None

    def test_downgrade_handles_string_coverage_value(self):
        # asyncpg may return JSONB as string — function should parse it
        coverage_str = '{"IMPT": {"covered": true}, "CONS": {"covered": false}}'
        result = _migrate_coverage_to_restrictions(coverage_str)
        assert result == '["IMPT"]'

    def test_downgrade_handles_invalid_string(self):
        assert _migrate_coverage_to_restrictions("not json") is None

    def test_downgrade_handles_non_dict_entries(self):
        # Entries that are not dicts should be ignored
        coverage = {
            "IMPT": {"covered": True},
            "BAD1": "just a string",
            "BAD2": 42,
            "CONS": {"covered": True},
        }
        result = _migrate_coverage_to_restrictions(coverage)
        parsed = json.loads(result)
        assert set(parsed) == {"IMPT", "CONS"}

    def test_downgrade_missing_covered_key_treated_as_false(self):
        coverage = {
            "IMPT": {"copay_percent": 30},  # no 'covered' key → defaults to False
            "CONS": {"covered": True},
        }
        result = _migrate_coverage_to_restrictions(coverage)
        assert result == '["CONS"]'


class TestDefaultCoverageEntry:
    """The default entry shape must match the Pydantic TreatmentCoverage model."""

    def test_default_entry_has_all_fields(self):
        entry = _default_coverage_entry()
        expected = {
            "covered",
            "copay_percent",
            "requires_pre_authorization",
            "pre_auth_leadtime_days",
            "waiting_period_days",
            "max_annual_coverage",
            "notes",
        }
        assert set(entry.keys()) == expected

    def test_default_entry_values(self):
        entry = _default_coverage_entry()
        assert entry["covered"] is True
        assert entry["copay_percent"] == 0.0
        assert entry["requires_pre_authorization"] is False
        assert entry["pre_auth_leadtime_days"] == 0
        assert entry["waiting_period_days"] == 0
        assert entry["max_annual_coverage"] is None
        assert entry["notes"] == ""


class TestRoundTrip:
    """Migrating forward then backward must preserve the covered=true codes."""

    def test_round_trip_preserves_covered_codes(self):
        original = '["IMPT", "CONS", "EXTRAC"]'
        coverage = _migrate_restrictions_to_coverage(original)
        roundtripped = _migrate_coverage_to_restrictions(coverage)
        assert json.loads(roundtripped) == ["IMPT", "CONS", "EXTRAC"]

    def test_round_trip_empty_stays_empty(self):
        assert _migrate_restrictions_to_coverage(None) == {}
        assert _migrate_coverage_to_restrictions({}) is None
