import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

# Must mock dependencies before import because they are init at module level
with patch('redis.from_url'), \
     patch('db.db.connect', new_callable=AsyncMock), \
     patch('langchain_openai.ChatOpenAI'), \
     patch('orchestrator_service.main.db', new_callable=MagicMock) as mock_db_instance: # Mocking the 'db' IMPORTED in main
    
    from orchestrator_service.main import app
    
    # We need to ensure startup event works or is mocked?
    # TestClient doesn't run startup events by default unless using Asyncclient with lifespan, 
    # but for unit tests we often just need endpoints.
    # However, 'db' is global. We mocked it above.
    
    client = TestClient(app)

    @pytest.mark.asyncio
    async def test_auth_internal_required():
        # Using async client or standard client? Standard client is sync but calls async endpoints fine (fastapi magic)
        response = client.post("/chat", json={
            "provider": "test",
            "event_id": "1",
            "provider_message_id": "1",
            "from_number": "123",
            "text": "hola",
            "event_type": "text",
            "correlation_id": "1"
        })
        assert response.status_code == 422 # Missing header
        
        response = client.post("/chat", json={
            "provider": "test",
            "event_id": "1",
            "provider_message_id": "1",
            "from_number": "123",
            "text": "hola",
            "event_type": "text",
            "correlation_id": "1"
        }, headers={"X-Internal-Token": "wrong"})
        assert response.status_code == 401

    @patch("orchestrator_service.main.db.try_insert_inbound", new_callable=AsyncMock)
    @patch("orchestrator_service.main.db.mark_inbound_processing", new_callable=AsyncMock)
    @patch("orchestrator_service.main.db.append_chat_message", new_callable=AsyncMock)
    @patch("orchestrator_service.main.db.mark_inbound_done", new_callable=AsyncMock)
    @patch("orchestrator_service.main.redis_client.lock")
    @patch("orchestrator_service.main.AgentExecutor")
    def test_dedupe_option_a(mock_agent_executor, mock_lock, mock_mark_done, mock_append, mock_mark_proc, mock_try_insert):
        # Setup mocks
        mock_try_insert.return_value = True # First time: is_new = True
        mock_lock.return_value.acquire.return_value = True
        
        mock_agent_instance = MagicMock()
        mock_agent_instance.ainvoke = AsyncMock(return_value={"output": "Response from agent"})
        mock_agent_executor.return_value = mock_agent_instance

        payload = {
            "provider": "test",
            "event_id": "evt_1",
            "provider_message_id": "msg_1",
            "from_number": "12345",
            "text": "hola",
            "event_type": "text",
            "correlation_id": "corr_1"
        }
        headers = {"X-Internal-Token": "test_internal_token"}

        # First call: OK
        response = client.post("/chat", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["send"] is True
        assert data["text"] == "Response from agent"
        
        # Second call: Duplicate
        mock_try_insert.return_value = False # is_new = False
        response = client.post("/chat", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "duplicate"
        assert data["send"] is False
