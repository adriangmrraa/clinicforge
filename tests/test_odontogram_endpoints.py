"""
Integration tests for odontogram endpoints (GET/PUT) with v2.0 and v3.0 payloads.
Tests normalization, tenant isolation, and database integration.
"""

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from contextlib import contextmanager


# Sample test tenant and IDs
TEST_TENANT_ID = 42
TEST_PATIENT_ID = 123
TEST_RECORD_ID = "abc-123"


def mock_record_exists(odontogram_data=None):
    """Return a mock database row with optional odontogram_data."""
    if odontogram_data is None:
        odontogram_data = {}
    return {
        "id": TEST_RECORD_ID,
        "odontogram_data": odontogram_data,
    }


@contextmanager
def override_auth(app):
    """Override verify_admin_token and get_resolved_tenant_id on the FastAPI app."""
    # Import from the same place admin_routes does so the key matches the Depends() reference
    import orchestrator_service.admin_routes as _ar
    verify_admin_token = _ar.verify_admin_token
    get_resolved_tenant_id = _ar.get_resolved_tenant_id

    async def _fake_verify_admin():
        return {"user_id": 1, "tenant_id": TEST_TENANT_ID}

    async def _fake_tenant_id():
        return TEST_TENANT_ID

    app.dependency_overrides[verify_admin_token] = _fake_verify_admin
    app.dependency_overrides[get_resolved_tenant_id] = _fake_tenant_id
    try:
        yield
    finally:
        app.dependency_overrides.pop(verify_admin_token, None)
        app.dependency_overrides.pop(get_resolved_tenant_id, None)


def _get_app():
    """Import the FastAPI app (already loaded via app_with_mock_pool fixture)."""
    from orchestrator_service.main import app
    return app


class TestOdontogramEndpoints:
    """Integration tests for /patients/{patient_id}/records/{record_id}/odontogram"""

    def test_update_odontogram_v3(self, app_with_mock_pool):
        """PUT with full v3.0 payload should be accepted and normalize_to_v3 called."""
        client, mock_pool = app_with_mock_pool

        mock_pool.fetchrow = AsyncMock(return_value=mock_record_exists())
        mock_pool.execute = AsyncMock(return_value=None)

        v3_payload = {
            "version": "3.0",
            "last_updated": "2026-04-02T15:30:00Z",
            "active_dentition": "permanent",
            "permanent": {
                "teeth": [
                    {
                        "id": 18,
                        "state": "caries",
                        "surfaces": {
                            "occlusal": {
                                "state": "caries",
                                "condition": "malo",
                                "color": "#ef4444",
                            },
                            "mesial": {"state": "healthy", "condition": None, "color": None},
                            "distal": {"state": "healthy", "condition": None, "color": None},
                            "buccal": {"state": "healthy", "condition": None, "color": None},
                            "lingual": {"state": "healthy", "condition": None, "color": None},
                        },
                        "notes": "Caries incipiente",
                    }
                ]
            },
            "deciduous": {"teeth": []},
        }

        with override_auth(_get_app()):
            response = client.put(
                f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
                json={"odontogram_data": v3_payload},
                headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "message": "Odontograma actualizado"}

        mock_pool.fetchrow.assert_called_once()
        mock_pool.execute.assert_called_once()

        execute_args = mock_pool.execute.call_args[0]
        # execute(SQL, json_data, record_id, tenant_id) → json is args[1]
        normalized = json.loads(execute_args[1])
        assert normalized["version"] == "3.0"
        assert normalized["permanent"]["teeth"][0]["id"] == 18
        assert normalized["permanent"]["teeth"][0]["state"] == "caries"
        assert len(normalized["deciduous"]["teeth"]) == 20

    def test_update_odontogram_v2(self, app_with_mock_pool):
        """PUT with v2.0 payload (backward compatibility) should be upgraded to v3.0."""
        client, mock_pool = app_with_mock_pool

        mock_pool.fetchrow = AsyncMock(return_value=mock_record_exists())
        mock_pool.execute = AsyncMock(return_value=None)

        v2_payload = {
            "version": "2.0",
            "teeth": [
                {"id": 18, "state": "caries", "surfaces": {}, "notes": ""},
                {"id": 21, "state": "restoration", "surfaces": {}, "notes": ""},
            ],
            "last_updated": "2026-01-01T00:00:00Z",
        }

        with override_auth(_get_app()):
            response = client.put(
                f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
                json={"odontogram_data": v2_payload},
                headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
            )

        assert response.status_code == 200

        mock_pool.execute.assert_called_once()
        # execute(SQL, json_data, record_id, tenant_id) → json is args[1]
        saved_json = json.loads(mock_pool.execute.call_args[0][1])
        assert saved_json["version"] == "3.0"
        perm_map = {t["id"]: t for t in saved_json["permanent"]["teeth"]}
        assert perm_map[18]["state"] == "caries"
        assert perm_map[21]["state"] == "restauracion_resina"
        assert len(saved_json["deciduous"]["teeth"]) == 20

    def test_update_odontogram_v1_legacy(self, app_with_mock_pool):
        """PUT with v1 legacy format (backward compatibility)."""
        client, mock_pool = app_with_mock_pool

        mock_pool.fetchrow = AsyncMock(return_value=mock_record_exists())
        mock_pool.execute = AsyncMock(return_value=None)

        v1_payload = {"18": "caries", "21": "healthy"}

        with override_auth(_get_app()):
            response = client.put(
                f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
                json={"odontogram_data": v1_payload},
                headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
            )

        assert response.status_code == 200

        # execute(SQL, json_data, record_id, tenant_id) → json is args[1]
        saved_json = json.loads(mock_pool.execute.call_args[0][1])
        assert saved_json["version"] == "3.0"
        perm_map = {t["id"]: t for t in saved_json["permanent"]["teeth"]}
        assert perm_map[18]["state"] == "caries"
        assert perm_map[21]["state"] == "healthy"

    def test_get_odontogram_with_v3_data(self, app_with_mock_pool):
        """GET returns v3.0 data, unchanged if already v3."""
        client, mock_pool = app_with_mock_pool

        v3_data = {
            "version": "3.0",
            "last_updated": "2026-04-02T15:30:00Z",
            "active_dentition": "deciduous",
            "permanent": {
                "teeth": [{"id": 18, "state": "caries", "surfaces": {}, "notes": ""}]
            },
            "deciduous": {
                "teeth": [{"id": 51, "state": "caries", "surfaces": {}, "notes": ""}]
            },
        }
        mock_pool.fetchrow = AsyncMock(return_value=mock_record_exists(v3_data))

        with override_auth(_get_app()):
            response = client.get(
                f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
                headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
            )

        assert response.status_code == 200
        result = response.json()
        assert "odontogram_data" in result
        od_data = result["odontogram_data"]
        assert od_data["version"] == "3.0"
        assert od_data["active_dentition"] == "deciduous"
        assert len(od_data["permanent"]["teeth"]) == 32
        caries_18 = next(t for t in od_data["permanent"]["teeth"] if t["id"] == 18)
        assert caries_18["state"] == "caries"

    def test_get_odontogram_with_v2_data(self, app_with_mock_pool):
        """GET upgrades v2.0 data to v3.0 on‑read."""
        client, mock_pool = app_with_mock_pool

        v2_data = {
            "version": "2.0",
            "teeth": [{"id": 18, "state": "caries", "surfaces": {}, "notes": ""}],
            "last_updated": "2026-01-01T00:00:00Z",
        }
        mock_pool.fetchrow = AsyncMock(return_value=mock_record_exists(v2_data))

        with override_auth(_get_app()):
            response = client.get(
                f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
                headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
            )

        assert response.status_code == 200
        od_data = response.json()["odontogram_data"]
        assert od_data["version"] == "3.0"
        assert len(od_data["permanent"]["teeth"]) == 32
        caries_18 = next(t for t in od_data["permanent"]["teeth"] if t["id"] == 18)
        assert caries_18["state"] == "caries"
        assert len(od_data["deciduous"]["teeth"]) == 20

    def test_get_odontogram_with_v1_data(self, app_with_mock_pool):
        """GET upgrades v1 legacy dict to v3.0."""
        client, mock_pool = app_with_mock_pool

        v1_data = {"18": "caries", "21": "healthy"}
        mock_pool.fetchrow = AsyncMock(return_value=mock_record_exists(v1_data))

        with override_auth(_get_app()):
            response = client.get(
                f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
                headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
            )

        assert response.status_code == 200
        od_data = response.json()["odontogram_data"]
        assert od_data["version"] == "3.0"
        perm_map = {t["id"]: t for t in od_data["permanent"]["teeth"]}
        assert perm_map[18]["state"] == "caries"
        assert perm_map[21]["state"] == "healthy"

    def test_get_odontogram_not_found(self, app_with_mock_pool):
        """GET returns 404 when record does not exist."""
        client, mock_pool = app_with_mock_pool

        mock_pool.fetchrow = AsyncMock(return_value=None)

        with override_auth(_get_app()):
            response = client.get(
                f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
                headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
            )

        assert response.status_code == 404
        assert "Registro clínico no encontrado" in response.json()["detail"]

    def test_update_odontogram_record_not_found(self, app_with_mock_pool):
        """PUT returns 404 when record does not exist."""
        client, mock_pool = app_with_mock_pool

        mock_pool.fetchrow = AsyncMock(return_value=None)
        mock_pool.execute = AsyncMock(return_value=None)

        with override_auth(_get_app()):
            response = client.put(
                f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
                json={"odontogram_data": {"version": "3.0"}},
                headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
            )

        assert response.status_code == 404
        mock_pool.execute.assert_not_called()
