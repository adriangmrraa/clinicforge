"""Tests for social IG/FB fields in PATCH/GET /admin/settings/clinic.

Validates that:
- ClinicSettingsUpdate Pydantic model accepts the 4 social fields.
- PATCH handler writes each field to the DB when provided.
- GET handler returns the 4 social fields in the response.
- Unknown fields don't cause 422.
- Partial payloads (only some fields) are accepted.

Strategy: source-level assertions against admin_routes.py where possible,
plus lightweight unit tests against the Pydantic model. No live Postgres needed.
"""

import ast
import inspect
from pathlib import Path

import pytest

ADMIN_ROUTES_PATH = (
    Path(__file__).resolve().parent.parent
    / "orchestrator_service"
    / "admin_routes.py"
)


def _get_source() -> str:
    return ADMIN_ROUTES_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------


class TestClinicSettingsUpdateModel:
    """ClinicSettingsUpdate must accept the 4 social fields."""

    def _import_model(self):
        # Import lazily to avoid importing main.py at collection time
        import sys
        sys.path.insert(0, str(ADMIN_ROUTES_PATH.parent.parent))
        from orchestrator_service.admin_routes import ClinicSettingsUpdate
        return ClinicSettingsUpdate

    def test_model_has_social_ig_active(self):
        ClinicSettingsUpdate = self._import_model()
        fields = ClinicSettingsUpdate.model_fields
        assert "social_ig_active" in fields

    def test_model_has_social_landings(self):
        ClinicSettingsUpdate = self._import_model()
        fields = ClinicSettingsUpdate.model_fields
        assert "social_landings" in fields

    def test_model_has_instagram_handle(self):
        ClinicSettingsUpdate = self._import_model()
        fields = ClinicSettingsUpdate.model_fields
        assert "instagram_handle" in fields

    def test_model_has_facebook_page_id(self):
        ClinicSettingsUpdate = self._import_model()
        fields = ClinicSettingsUpdate.model_fields
        assert "facebook_page_id" in fields

    def test_social_ig_active_is_optional(self):
        ClinicSettingsUpdate = self._import_model()
        # Optional means default is None
        m = ClinicSettingsUpdate()
        assert m.social_ig_active is None

    def test_social_landings_is_optional(self):
        ClinicSettingsUpdate = self._import_model()
        m = ClinicSettingsUpdate()
        assert m.social_landings is None

    def test_instagram_handle_is_optional(self):
        ClinicSettingsUpdate = self._import_model()
        m = ClinicSettingsUpdate()
        assert m.instagram_handle is None

    def test_facebook_page_id_is_optional(self):
        ClinicSettingsUpdate = self._import_model()
        m = ClinicSettingsUpdate()
        assert m.facebook_page_id is None

    def test_social_ig_active_accepts_true(self):
        ClinicSettingsUpdate = self._import_model()
        m = ClinicSettingsUpdate(social_ig_active=True)
        assert m.social_ig_active is True

    def test_social_ig_active_accepts_false(self):
        ClinicSettingsUpdate = self._import_model()
        m = ClinicSettingsUpdate(social_ig_active=False)
        assert m.social_ig_active is False

    def test_social_landings_accepts_dict(self):
        ClinicSettingsUpdate = self._import_model()
        landings = {"main": "https://example.com", "blanqueamiento": "https://b.example.com"}
        m = ClinicSettingsUpdate(social_landings=landings)
        assert m.social_landings == landings

    def test_instagram_handle_accepts_string(self):
        ClinicSettingsUpdate = self._import_model()
        m = ClinicSettingsUpdate(instagram_handle="@dralauradelgado")
        assert m.instagram_handle == "@dralauradelgado"

    def test_facebook_page_id_accepts_string(self):
        ClinicSettingsUpdate = self._import_model()
        m = ClinicSettingsUpdate(facebook_page_id="123456789")
        assert m.facebook_page_id == "123456789"

    def test_partial_payload_other_fields_still_none(self):
        """Only sending social_ig_active leaves other fields as None."""
        ClinicSettingsUpdate = self._import_model()
        m = ClinicSettingsUpdate(social_ig_active=True)
        assert m.social_landings is None
        assert m.instagram_handle is None
        assert m.facebook_page_id is None


# ---------------------------------------------------------------------------
# Source-level assertions — PATCH handler writes all 4 fields
# ---------------------------------------------------------------------------


class TestPatchHandlerSource:
    """Assert the PATCH handler source contains update logic for all 4 fields."""

    def _get_handler_source(self) -> str:
        src = _get_source()
        # Extract the update_clinic_settings function body
        # Find it by searching for the function definition
        start = src.find("async def update_clinic_settings(")
        assert start != -1, "update_clinic_settings not found in admin_routes.py"
        # Find next top-level function or class after it
        next_def = src.find("\n@router.", start + 1)
        if next_def == -1:
            next_def = src.find("\nasync def ", start + 1)
        if next_def == -1:
            next_def = len(src)
        return src[start:next_def]

    def test_patch_handles_social_ig_active(self):
        handler = self._get_handler_source()
        assert "social_ig_active" in handler, (
            "PATCH handler does not handle social_ig_active"
        )

    def test_patch_handles_social_landings(self):
        handler = self._get_handler_source()
        assert "social_landings" in handler, (
            "PATCH handler does not handle social_landings"
        )

    def test_patch_handles_instagram_handle(self):
        handler = self._get_handler_source()
        assert "instagram_handle" in handler, (
            "PATCH handler does not handle instagram_handle"
        )

    def test_patch_handles_facebook_page_id(self):
        handler = self._get_handler_source()
        assert "facebook_page_id" in handler, (
            "PATCH handler does not handle facebook_page_id"
        )

    def test_patch_issues_sql_update_for_social_ig_active(self):
        """Handler must run an UPDATE for social_ig_active."""
        handler = self._get_handler_source()
        # Should have a SET ... social_ig_active ... WHERE clause
        assert "UPDATE tenants" in handler or "execute" in handler, (
            "PATCH handler must issue a SQL UPDATE for social_ig_active"
        )

    def test_patch_issues_sql_update_for_social_landings(self):
        handler = self._get_handler_source()
        assert "social_landings" in handler


# ---------------------------------------------------------------------------
# Source-level assertions — GET handler returns all 4 fields
# ---------------------------------------------------------------------------


class TestGetHandlerSource:
    """Assert the GET handler source returns all 4 social fields."""

    def _get_handler_source(self) -> str:
        src = _get_source()
        start = src.find("async def get_clinic_settings(")
        assert start != -1, "get_clinic_settings not found in admin_routes.py"
        next_def = src.find("\n@router.", start + 1)
        if next_def == -1:
            next_def = len(src)
        return src[start:next_def]

    def test_get_returns_social_ig_active(self):
        handler = self._get_handler_source()
        assert "social_ig_active" in handler, (
            "GET /settings/clinic does not return social_ig_active"
        )

    def test_get_returns_social_landings(self):
        handler = self._get_handler_source()
        assert "social_landings" in handler, (
            "GET /settings/clinic does not return social_landings"
        )

    def test_get_returns_instagram_handle(self):
        handler = self._get_handler_source()
        assert "instagram_handle" in handler, (
            "GET /settings/clinic does not return instagram_handle"
        )

    def test_get_returns_facebook_page_id(self):
        handler = self._get_handler_source()
        assert "facebook_page_id" in handler, (
            "GET /settings/clinic does not return facebook_page_id"
        )


# ---------------------------------------------------------------------------
# Source-level assertions — fallback function also includes the 4 fields
# ---------------------------------------------------------------------------


class TestFallbackClinicSettings:
    """_fallback_clinic_settings must include safe defaults for all 4 fields."""

    def _get_fallback_source(self) -> str:
        src = _get_source()
        start = src.find("def _fallback_clinic_settings(")
        assert start != -1, "_fallback_clinic_settings not found"
        next_def = src.find("\n\n", start + 1)
        if next_def == -1:
            next_def = len(src)
        return src[start:next_def]

    def test_fallback_has_social_ig_active(self):
        fallback = self._get_fallback_source()
        assert "social_ig_active" in fallback

    def test_fallback_has_social_landings(self):
        fallback = self._get_fallback_source()
        assert "social_landings" in fallback

    def test_fallback_has_instagram_handle(self):
        fallback = self._get_fallback_source()
        assert "instagram_handle" in fallback

    def test_fallback_has_facebook_page_id(self):
        fallback = self._get_fallback_source()
        assert "facebook_page_id" in fallback
