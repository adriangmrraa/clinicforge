"""
Integration tests for odontogram endpoints (GET/PUT) with v2.0 and v3.0 payloads.
Tests normalization, tenant isolation, and database integration.
"""

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

# Patch dependencies before importing app (to avoid real DB/Redis connections)
with (
    patch("redis.from_url"),
    patch("db.db.connect", new_callable=AsyncMock),
    patch("langchain_openai.ChatOpenAI"),
    patch("langchain.agents.AgentExecutor", create=True),  # create attribute if missing
    patch("langchain.agents.create_openai_tools_agent", create=True),
):
    from orchestrator_service.main import app

    client = TestClient(app)

# Patch the auth dependencies used by admin_routes
# (they are already imported, but we can replace them)
auth_patcher1 = patch(
    "orchestrator_service.admin_routes.verify_admin_token",
    return_value={"user_id": 1, "tenant_id": 42},
)
auth_patcher2 = patch(
    "orchestrator_service.admin_routes.get_resolved_tenant_id", return_value=42
)
auth_patcher1.start()
auth_patcher2.start()


# Ensure patches are stopped after all tests (optional but clean)
def stop_patches():
    auth_patcher1.stop()
    auth_patcher2.stop()


# Register stop on pytest session finish (simplistic)
import atexit

atexit.register(stop_patches)


# Sample test tenant and IDs
TEST_TENANT_ID = 42
TEST_PATIENT_ID = 123
TEST_RECORD_ID = "abc-123"


def mock_record_exists(odontogram_data=None):
    """Return a mock database row with optional odontogram_data."""
    if odontogram_data is None:
        odontogram_data = {}
    # asyncpg returns a dict-like Record with column access
    return {
        "id": TEST_RECORD_ID,
        "odontogram_data": odontogram_data,  # JSONB column as dict
    }


class TestOdontogramEndpoints:
    """Integration tests for /patients/{patient_id}/records/{record_id}/odontogram"""

    @patch("orchestrator_service.admin_routes.db.pool.fetchrow", new_callable=AsyncMock)
    @patch("orchestrator_service.admin_routes.db.pool.execute", new_callable=AsyncMock)
    def test_update_odontogram_v3(self, mock_execute, mock_fetchrow):
        """PUT with full v3.0 payload should be accepted and normalize_to_v3 called."""
        # Mock record exists
        mock_fetchrow.return_value = mock_record_exists()
        mock_execute.return_value = None

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
                            "mesial": {
                                "state": "healthy",
                                "condition": None,
                                "color": None,
                            },
                            "distal": {
                                "state": "healthy",
                                "condition": None,
                                "color": None,
                            },
                            "buccal": {
                                "state": "healthy",
                                "condition": None,
                                "color": None,
                            },
                            "lingual": {
                                "state": "healthy",
                                "condition": None,
                                "color": None,
                            },
                        },
                        "notes": "Caries incipiente",
                    }
                ]
            },
            "deciduous": {"teeth": []},
        }

        response = client.put(
            f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
            json={"odontogram_data": v3_payload},
            headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "message": "Odontograma actualizado"}

        # Ensure fetchrow was called with correct tenant isolation
        mock_fetchrow.assert_called_once()
        call_args = mock_fetchrow.call_args[0][0]
        assert "$3" in call_args  # tenant_id placeholder
        assert mock_fetchrow.call_args[0][3] == TEST_TENANT_ID

        # Ensure execute was called with normalized v3 data (as JSON string)
        mock_execute.assert_called_once()
        execute_args = mock_execute.call_args[0]
        assert len(execute_args) >= 3
        # First argument should be JSON string (normalized)
        normalized = json.loads(execute_args[0])
        assert normalized["version"] == "3.0"
        assert normalized["permanent"]["teeth"][0]["id"] == 18
        assert normalized["permanent"]["teeth"][0]["state"] == "caries"
        # Ensure deciduous teeth are present (normalizer adds defaults)
        assert len(normalized["deciduous"]["teeth"]) == 20

    @patch("orchestrator_service.admin_routes.db.pool.fetchrow", new_callable=AsyncMock)
    @patch("orchestrator_service.admin_routes.db.pool.execute", new_callable=AsyncMock)
    def test_update_odontogram_v2(self, mock_execute, mock_fetchrow):
        """PUT with v2.0 payload (backward compatibility) should be upgraded to v3.0."""
        mock_fetchrow.return_value = mock_record_exists()
        mock_execute.return_value = None

        v2_payload = {
            "version": "2.0",
            "teeth": [
                {"id": 18, "state": "caries", "surfaces": {}, "notes": ""},
                {"id": 21, "state": "restoration", "surfaces": {}, "notes": ""},
            ],
            "last_updated": "2026-01-01T00:00:00Z",
        }

        response = client.put(
            f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
            json={"odontogram_data": v2_payload},
            headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
        )

        assert response.status_code == 200

        # Verify that the saved data is v3.0 (normalizer converts)
        mock_execute.assert_called_once()
        saved_json = json.loads(mock_execute.call_args[0][0])
        assert saved_json["version"] == "3.0"
        # Ensure legacy state mapping applied
        perm_map = {t["id"]: t for t in saved_json["permanent"]["teeth"]}
        assert perm_map[18]["state"] == "caries"
        assert perm_map[21]["state"] == "restauracion_resina"  # mapped
        # Deciduous teeth should be present (defaults)
        assert len(saved_json["deciduous"]["teeth"]) == 20

    @patch("orchestrator_service.admin_routes.db.pool.fetchrow", new_callable=AsyncMock)
    @patch("orchestrator_service.admin_routes.db.pool.execute", new_callable=AsyncMock)
    def test_update_odontogram_v1_legacy(self, mock_execute, mock_fetchrow):
        """PUT with v1 legacy format (backward compatibility)."""
        mock_fetchrow.return_value = mock_record_exists()
        mock_execute.return_value = None

        v1_payload = {"18": "caries", "21": "healthy"}

        response = client.put(
            f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
            json={"odontogram_data": v1_payload},
            headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
        )

        assert response.status_code == 200

        saved_json = json.loads(mock_execute.call_args[0][0])
        assert saved_json["version"] == "3.0"
        perm_map = {t["id"]: t for t in saved_json["permanent"]["teeth"]}
        assert perm_map[18]["state"] == "caries"
        assert perm_map[21]["state"] == "healthy"

    @patch("orchestrator_service.admin_routes.db.pool.fetchrow", new_callable=AsyncMock)
    def test_get_odontogram_with_v3_data(self, mock_fetchrow):
        """GET returns v3.0 data, unchanged if already v3."""
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
        mock_fetchrow.return_value = mock_record_exists(v3_data)

        response = client.get(
            f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
            headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
        )

        assert response.status_code == 200
        result = response.json()
        assert "odontogram_data" in result
        # Should be normalized (still v3)
        od_data = result["odontogram_data"]
        assert od_data["version"] == "3.0"
        assert od_data["active_dentition"] == "deciduous"
        # Should have full 32 permanent teeth (normalizer fills missing)
        assert len(od_data["permanent"]["teeth"]) == 32
        # The caries tooth should be preserved
        caries_18 = next(t for t in od_data["permanent"]["teeth"] if t["id"] == 18)
        assert caries_18["state"] == "caries"

    @patch("orchestrator_service.admin_routes.db.pool.fetchrow", new_callable=AsyncMock)
    def test_get_odontogram_with_v2_data(self, mock_fetchrow):
        """GET upgrades v2.0 data to v3.0 on‑read."""
        v2_data = {
            "version": "2.0",
            "teeth": [{"id": 18, "state": "caries", "surfaces": {}, "notes": ""}],
            "last_updated": "2026-01-01T00:00:00Z",
        }
        mock_fetchrow.return_value = mock_record_exists(v2_data)

        response = client.get(
            f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
            headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
        )

        assert response.status_code == 200
        od_data = response.json()["odontogram_data"]
        assert od_data["version"] == "3.0"
        # v2 teeth array becomes permanent.teeth
        assert len(od_data["permanent"]["teeth"]) == 32
        caries_18 = next(t for t in od_data["permanent"]["teeth"] if t["id"] == 18)
        assert caries_18["state"] == "caries"
        # deciduous should be default 20 healthy teeth
        assert len(od_data["deciduous"]["teeth"]) == 20

    @patch("orchestrator_service.admin_routes.db.pool.fetchrow", new_callable=AsyncMock)
    def test_get_odontogram_with_v1_data(self, mock_fetchrow):
        """GET upgrades v1 legacy dict to v3.0."""
        v1_data = {"18": "caries", "21": "healthy"}
        mock_fetchrow.return_value = mock_record_exists(v1_data)

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

    @patch("orchestrator_service.admin_routes.db.pool.fetchrow", new_callable=AsyncMock)
    def test_get_odontogram_not_found(self, mock_fetchrow):
        """GET returns 404 when record does not exist."""
        mock_fetchrow.return_value = None

        response = client.get(
            f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
            headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
        )

        assert response.status_code == 404
        assert "Registro clínico no encontrado" in response.json()["detail"]

    @patch("orchestrator_service.admin_routes.db.pool.fetchrow", new_callable=AsyncMock)
    @patch("orchestrator_service.admin_routes.db.pool.execute", new_callable=AsyncMock)
    def test_update_odontogram_record_not_found(self, mock_execute, mock_fetchrow):
        """PUT returns 404 when record does not exist."""
        mock_fetchrow.return_value = None
        mock_execute.return_value = None

        response = client.put(
            f"/admin/patients/{TEST_PATIENT_ID}/records/{TEST_RECORD_ID}/odontogram",
            json={"odontogram_data": {"version": "3.0"}},
            headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
        )

        assert response.status_code == 404
        mock_execute.assert_not_called()

    # Note: Color validation is not performed at endpoint level (SurfaceState validation
    # only happens inside Pydantic models, which are not used in the endpoint).
    # Therefore, invalid HEX colors will pass through and be stored as-is.
    # This is acceptable for now.
