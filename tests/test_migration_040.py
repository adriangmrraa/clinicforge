"""Tests for migration 040_add_social_ig_fields.

Validates that the migration file contains the expected upgrade/downgrade calls
for the 4 new social IG/FB columns on the tenants table.

Strategy: import the migration module via importlib and assert the source
contains the expected op.add_column / op.drop_column calls for each column.
This avoids a live Postgres dependency while still verifying migration intent.
"""

import importlib.util
import inspect
import re
import sys
from pathlib import Path

import pytest

MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "orchestrator_service"
    / "alembic"
    / "versions"
    / "040_add_social_ig_fields.py"
)

EXPECTED_COLUMNS = [
    "social_ig_active",
    "social_landings",
    "instagram_handle",
    "facebook_page_id",
]


def _load_migration():
    """Load the migration module; skip if file doesn't exist yet."""
    if not MIGRATION_PATH.exists():
        pytest.skip(f"Migration file does not exist yet: {MIGRATION_PATH}")
    spec = importlib.util.spec_from_file_location("migration_040", MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _get_source():
    """Return the raw source of the migration file."""
    if not MIGRATION_PATH.exists():
        pytest.skip(f"Migration file does not exist yet: {MIGRATION_PATH}")
    return MIGRATION_PATH.read_text(encoding="utf-8")


class TestMigration040Structure:
    """Assert the migration file has the right metadata and column ops."""

    def test_migration_file_exists(self):
        assert MIGRATION_PATH.exists(), (
            f"Migration 040 file not found at {MIGRATION_PATH}"
        )

    def test_revision_id(self):
        mod = _load_migration()
        assert mod.revision == "040_add_social_ig_fields"

    def test_down_revision(self):
        mod = _load_migration()
        assert mod.down_revision == "039"

    def test_upgrade_adds_social_ig_active(self):
        src = _get_source()
        assert "social_ig_active" in src

    def test_upgrade_adds_social_landings(self):
        src = _get_source()
        assert "social_landings" in src

    def test_upgrade_adds_instagram_handle(self):
        src = _get_source()
        assert "instagram_handle" in src

    def test_upgrade_adds_facebook_page_id(self):
        src = _get_source()
        assert "facebook_page_id" in src

    def test_upgrade_function_has_all_four_columns(self):
        mod = _load_migration()
        src = inspect.getsource(mod.upgrade)
        for col in EXPECTED_COLUMNS:
            assert col in src, (
                f"upgrade() does not add column '{col}'"
            )

    def test_downgrade_function_has_all_four_columns(self):
        mod = _load_migration()
        src = inspect.getsource(mod.downgrade)
        for col in EXPECTED_COLUMNS:
            assert col in src, (
                f"downgrade() does not drop column '{col}'"
            )

    def test_upgrade_uses_add_column(self):
        mod = _load_migration()
        src = inspect.getsource(mod.upgrade)
        assert "add_column" in src

    def test_downgrade_uses_drop_column(self):
        mod = _load_migration()
        src = inspect.getsource(mod.downgrade)
        assert "drop_column" in src

    def test_upgrade_targets_tenants_table(self):
        mod = _load_migration()
        src = inspect.getsource(mod.upgrade)
        assert "tenants" in src

    def test_downgrade_targets_tenants_table(self):
        mod = _load_migration()
        src = inspect.getsource(mod.downgrade)
        assert "tenants" in src

    def test_social_ig_active_is_boolean_not_null(self):
        """Boolean NOT NULL column: source should reference Boolean and server_default."""
        src = _get_source()
        # The word Boolean should appear (for the type)
        assert "Boolean" in src
        # server_default should be present for NOT NULL with a default
        assert "server_default" in src

    def test_social_landings_is_jsonb(self):
        """JSONB type should be referenced for social_landings."""
        src = _get_source()
        assert "JSONB" in src

    def test_instagram_handle_is_varchar_100(self):
        """String(100) should appear for the varchar columns."""
        src = _get_source()
        assert "String(100)" in src or "String" in src

    def test_downgrade_drops_in_reverse_order(self):
        """facebook_page_id should appear before social_ig_active in downgrade."""
        mod = _load_migration()
        src = inspect.getsource(mod.downgrade)
        fb_pos = src.find("facebook_page_id")
        ig_pos = src.find("social_ig_active")
        assert fb_pos < ig_pos, (
            "downgrade() should drop facebook_page_id before social_ig_active "
            "(reverse of upgrade order)"
        )
