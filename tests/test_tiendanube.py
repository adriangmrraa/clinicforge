import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from tiendanube_service.main import app

client = TestClient(app)

def test_internal_token_required():
    response = client.post("/tools/productsq", json={"q": "test"})
    # Missing token
    assert response.status_code == 422 # FastAPI checks header presence first (Validation Error)
    
    # Invalid token
    response = client.post("/tools/productsq", json={"q": "test"}, headers={"X-Internal-Token": "wrong"})
    assert response.status_code == 401

@patch("tiendanube_service.main.requests.get")
def test_toolresponse_schema(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = [{"id": 1, "name": "Producto Test"}]
    
    response = client.post(
        "/tools/productsq", 
        json={"q": "test"}, 
        headers={"X-Internal-Token": "test_internal_token"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "ok" in data
    assert "data" in data
    assert data["ok"] is True
    assert data["data"][0]["name"] == "Producto Test"

@patch("tiendanube_service.main.requests.get")
def test_toolresponse_error_handling(mock_get):
    # Simulate Tienda Nube Error
    mock_get.side_effect = Exception("Network Error")
    
    response = client.post(
        "/tools/productsq", 
        json={"q": "test"}, 
        headers={"X-Internal-Token": "test_internal_token"}
    )
    
    assert response.status_code == 200 # We return 200 with ok=False
    data = response.json()
    assert data["ok"] is False
    assert data["error"]["code"] == "INTERNAL_ERROR"

