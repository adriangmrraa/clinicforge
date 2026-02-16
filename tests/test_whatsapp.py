import pytest
import hmac
import hashlib
import time
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import app AFTER env vars are set (which happens in conftest or here implicitly due to pytest order)
# However, we need to ensure redis/etc are mocked if they are instantiated at import time.
# In whatsapp_service/main.py, redis_client IS instantiated at module level.
# So we need to patch redis.from_url before importing main

with patch('redis.from_url') as mock_redis_from_url:
    from whatsapp_service.main import app, YCLOUD_WEBHOOK_SECRET

client = TestClient(app)

def generate_signature(body: str, secret: str = YCLOUD_WEBHOOK_SECRET):
    t = str(int(time.time()))
    payload = f"{t}.{body}"
    s = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"t={t},s={s}"

def test_signature_invalid_returns_401():
    response = client.post(
        "/webhook/ycloud",
        content="test",
        headers={"ycloud-signature": "t=123,s=invalid"}
    )
    assert response.status_code == 401
    assert "Invalid signature" in response.text or "Timestamp" in response.text or "format" in response.text

@patch("whatsapp_service.main.requests.post")
def test_signature_valid_forwards_to_orchestrator(mock_post):
    # Mock orchestrator response
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"status": "ok", "send": False}
    
    body = '[{"type": "whatsapp.inbound_message.received", "id": "evt_1", "whatsappInboundMessage": {"from": "123", "text": {"body": "hola"}}}]'
    sig = generate_signature(body)
    
    response = client.post(
        "/webhook/ycloud",
        content=body,
        headers={"ycloud-signature": sig}
    )
    
    assert response.status_code == 200
    assert mock_post.called
    # Check if correct URL and Headers
    args, kwargs = mock_post.call_args
    assert "/chat" in args[0]
    assert kwargs["headers"]["X-Internal-Token"] == "test_internal_token"
    assert "X-Correlation-Id" in kwargs["headers"]

